# =============================================================================
# KARI.Самозанятые — API пользователей
# Файл: app/api/users.py
# =============================================================================
#
# Эндпоинты:
#
#   POST /api/v1/users/init           — создать первого директора региона (один раз)
#   POST /api/v1/users/register       — регистрация самозанятого (мобильное приложение)
#   POST /api/v1/users/directors      — создать директора (только директор региона)
#
#   GET  /api/v1/users/               — список пользователей (директора)
#   GET  /api/v1/users/executors      — список исполнителей
#   GET  /api/v1/users/me             — мой профиль
#   GET  /api/v1/users/{user_id}      — профиль любого пользователя
#
#   PUT  /api/v1/users/me/card        — привязать карту (исполнитель)
#   PUT  /api/v1/users/me/fcm-token   — обновить FCM токен (мобильное приложение)
#
#   POST /api/v1/users/{user_id}/block    — заблокировать
#   POST /api/v1/users/{user_id}/unblock  — разблокировать
# =============================================================================

import logging
import math
from typing import Optional
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_

from app.config import settings
from app.database import get_db
from app.models.user import User, UserRole, UserStatus, FnsStatus
from app.core.security import get_current_user, require_role, require_regional, require_director
from app.schemas.user import (
    InitAdminRequest,
    RegisterExecutorRequest,
    CreateDirectorRequest,
    UpdateBankCardRequest,
    UpdateFcmTokenRequest,
    UpdateProfileRequest,
    BlockUserRequest,
    UserResponse,
    UserListResponse,
    RegisterExecutorResponse,
)
from app.services.sms_service import create_and_send_sms_code

logger = logging.getLogger(__name__)

router = APIRouter()


# =============================================================================
# ИНИЦИАЛИЗАЦИЯ: СОЗДАНИЕ ПЕРВОГО АДМИНИСТРАТОРА
# =============================================================================

@router.post(
    "/init",
    response_model=UserResponse,
    summary="Создать первого директора региона",
    description="""
**Вызывается один раз** при первом запуске системы.

Создаёт учётную запись директора региона с полным доступом.
Требует секретную фразу `INIT_SECRET` из файла `.env`.

После создания этот эндпоинт **перестаёт работать** — пока в системе
есть хотя бы один директор региона, повторный вызов будет отклонён.
    """,
    tags=["Инициализация"],
)
async def init_admin(
    body: InitAdminRequest,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:

    # Проверяем секретную фразу
    init_secret = getattr(settings, "INIT_SECRET", "KARI_INIT_2025")
    if body.secret != init_secret:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Неверная секретная фраза",
        )

    # Проверяем что директоров региона ещё нет
    result = await db.execute(
        select(func.count(User.id)).where(User.role == UserRole.REGIONAL_DIRECTOR)
    )
    count = result.scalar()
    if count and count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Директор региона уже существует. Повторная инициализация запрещена.",
        )

    # Проверяем что телефон не занят
    existing = await db.execute(select(User).where(User.phone == body.phone))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Пользователь с таким номером телефона уже зарегистрирован",
        )

    # Создаём первого директора региона
    admin = User(
        phone=body.phone,
        full_name=body.full_name,
        role=UserRole.REGIONAL_DIRECTOR,
        status=UserStatus.ACTIVE,
    )
    db.add(admin)
    await db.flush()

    logger.info(f"✅ Создан первый директор региона: {body.phone} ({body.full_name})")

    return _to_response(admin)


# =============================================================================
# РЕГИСТРАЦИЯ ИСПОЛНИТЕЛЯ (мобильное приложение)
# =============================================================================

@router.post(
    "/register",
    response_model=RegisterExecutorResponse,
    summary="Регистрация самозанятого исполнителя",
    description="""
Регистрирует нового исполнителя и **сразу отправляет SMS** для подтверждения.

После регистрации:
1. Приходит SMS с кодом
2. Нужно вызвать `POST /auth/verify-code` чтобы получить токен

**Повторная регистрация** с тем же телефоном — обновляет ФИО и ИНН
(на случай если исполнитель переустановил приложение).
    """,
)
async def register_executor(
    body: RegisterExecutorRequest,
    db: AsyncSession = Depends(get_db),
) -> RegisterExecutorResponse:

    # Проверяем: возможно исполнитель уже зарегистрирован
    result = await db.execute(select(User).where(User.phone == body.phone))
    existing_user = result.scalar_one_or_none()

    if existing_user:
        # Пользователь с этим телефоном уже есть
        if existing_user.role != UserRole.EXECUTOR:
            # Телефон принадлежит директору — нельзя
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Номер телефона уже используется сотрудником KARI",
            )
        if existing_user.status == UserStatus.BLOCKED:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Аккаунт заблокирован. Причина: {existing_user.blocked_reason or 'не указана'}",
            )
        # Обновляем данные (переустановка приложения)
        existing_user.full_name = body.full_name
        existing_user.inn = body.inn
        user = existing_user
        logger.info(f"Повторная регистрация исполнителя: {body.phone}")
    else:
        # Новый исполнитель — проверяем ИНН на уникальность
        inn_check = await db.execute(select(User).where(User.inn == body.inn))
        if inn_check.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Исполнитель с таким ИНН уже зарегистрирован",
            )

        # Создаём нового пользователя
        user = User(
            phone=body.phone,
            full_name=body.full_name,
            role=UserRole.EXECUTOR,
            status=UserStatus.ACTIVE,
            inn=body.inn,
            fns_status=FnsStatus.INACTIVE,  # Статус ФНС уточним при проверке
            income_tracking_year=datetime.now(timezone.utc).year,
        )
        db.add(user)
        await db.flush()
        logger.info(f"Новый исполнитель: {body.phone} ИНН={body.inn}")

    # Отправляем SMS для подтверждения телефона
    sent, debug_code = await create_and_send_sms_code(
        db=db,
        phone=body.phone,
        purpose="auth",
    )

    if not sent:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Не удалось отправить SMS. Попробуйте через несколько минут.",
        )

    return RegisterExecutorResponse(
        phone=body.phone,
        expires_in_seconds=settings.SMS_CODE_EXPIRE_MINUTES * 60,
        debug_code=debug_code,
    )


# =============================================================================
# СОЗДАНИЕ ДИРЕКТОРА (только директор региона)
# =============================================================================

@router.post(
    "/directors",
    response_model=UserResponse,
    summary="Создать директора подразделения или магазина",
    description="Доступно только директору региона.",
)
async def create_director(
    body: CreateDirectorRequest,
    current_user: User = Depends(require_regional),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:

    # Проверяем уникальность телефона
    existing = await db.execute(select(User).where(User.phone == body.phone))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Пользователь с таким номером телефона уже существует",
        )

    director = User(
        phone=body.phone,
        full_name=body.full_name,
        role=UserRole(body.role),
        status=UserStatus.ACTIVE,
        region_id=body.region_id,
        division_id=body.division_id,
        store_id=body.store_id,
    )
    db.add(director)
    await db.flush()

    logger.info(
        f"Директор создан: {body.phone} ({body.role}) — создал {current_user.phone}"
    )
    return _to_response(director)


# =============================================================================
# СПИСОК ПОЛЬЗОВАТЕЛЕЙ
# =============================================================================

@router.get(
    "/",
    response_model=UserListResponse,
    summary="Список пользователей",
    description="Директора — видят пользователей своего региона/подразделения.",
)
async def list_users(
    role:     Optional[str] = Query(None, description="Фильтр по роли"),
    status_f: Optional[str] = Query(None, alias="status", description="Фильтр по статусу"),
    search:   Optional[str] = Query(None, description="Поиск по имени или телефону"),
    page:     int           = Query(1, ge=1),
    size:     int           = Query(20, ge=1, le=100),
    current_user: User = Depends(require_director),
    db: AsyncSession = Depends(get_db),
) -> UserListResponse:

    query = select(User)

    # Директор региона видит всех, директор магазина — только исполнителей
    if current_user.role == UserRole.STORE_DIRECTOR:
        query = query.where(User.role == UserRole.EXECUTOR)

    # Фильтры
    if role:
        query = query.where(User.role == role)
    if status_f:
        query = query.where(User.status == status_f)
    if search:
        query = query.where(
            or_(
                User.full_name.ilike(f"%{search}%"),
                User.phone.ilike(f"%{search}%"),
            )
        )

    # Считаем итого
    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar() or 0

    # Получаем страницу
    offset = (page - 1) * size
    result = await db.execute(
        query.order_by(User.created_at.desc()).offset(offset).limit(size)
    )
    users = result.scalars().all()

    return UserListResponse(
        items=[_to_response(u) for u in users],
        total=total,
        page=page,
        size=size,
        pages=math.ceil(total / size) if total else 0,
    )


@router.get(
    "/executors",
    response_model=UserListResponse,
    summary="Список исполнителей (самозанятых)",
    description="Фильтрует только исполнителей. Удобно для биржи заданий.",
)
async def list_executors(
    fns_status: Optional[str] = Query(None, description="Фильтр по статусу ФНС"),
    search:     Optional[str] = Query(None, description="Поиск по имени, телефону или ИНН"),
    page:       int           = Query(1, ge=1),
    size:       int           = Query(20, ge=1, le=100),
    current_user: User = Depends(require_director),
    db: AsyncSession = Depends(get_db),
) -> UserListResponse:

    query = select(User).where(User.role == UserRole.EXECUTOR)

    if fns_status:
        query = query.where(User.fns_status == fns_status)
    if search:
        query = query.where(
            or_(
                User.full_name.ilike(f"%{search}%"),
                User.phone.ilike(f"%{search}%"),
                User.inn.ilike(f"%{search}%"),
            )
        )

    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar() or 0

    offset = (page - 1) * size
    result = await db.execute(
        query.order_by(User.created_at.desc()).offset(offset).limit(size)
    )
    users = result.scalars().all()

    return UserListResponse(
        items=[_to_response(u) for u in users],
        total=total,
        page=page,
        size=size,
        pages=math.ceil(total / size) if total else 0,
    )


# =============================================================================
# ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ
# =============================================================================

@router.get(
    "/me",
    response_model=UserResponse,
    summary="Мой профиль",
)
async def get_my_profile(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    return _to_response(current_user)


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Профиль пользователя по ID",
)
async def get_user(
    user_id: str,
    current_user: User = Depends(require_director),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден",
        )
    return _to_response(user)


# =============================================================================
# ОБНОВЛЕНИЕ СВОЕГО ПРОФИЛЯ (исполнитель)
# =============================================================================

@router.patch(
    "/me",
    response_model=UserResponse,
    summary="Обновить профиль (ФИО и/или ИНН)",
    description="Исполнитель заполняет своё ФИО и ИНН при регистрации через мобильное приложение.",
)
async def update_my_profile(
    body: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    if body.full_name is not None:
        current_user.full_name = body.full_name.strip()
    if body.inn is not None:
        # Оставляем только цифры
        inn_digits = "".join(c for c in body.inn if c.isdigit())
        if len(inn_digits) != 12:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="ИНН должен содержать 12 цифр",
            )
        current_user.inn = inn_digits
    await db.commit()
    await db.refresh(current_user)
    return _to_response(current_user)


@router.put(
    "/me/card",
    response_model=UserResponse,
    summary="Привязать банковскую карту",
    description="Исполнитель привязывает карту для получения выплат.",
)
async def update_bank_card(
    body: UpdateBankCardRequest,
    current_user: User = Depends(require_role("executor")),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:

    current_user.bank_card_token  = body.card_token
    current_user.bank_card_masked = body.card_masked
    current_user.bank_name        = body.bank_name

    logger.info(f"Карта обновлена: {current_user.phone} → {body.bank_name} {body.card_masked}")
    return _to_response(current_user)


@router.put(
    "/me/fcm-token",
    summary="Обновить FCM-токен для push-уведомлений",
    description="Вызывается мобильным приложением при каждом запуске.",
)
async def update_fcm_token(
    body: UpdateFcmTokenRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:

    current_user.fcm_token = body.fcm_token
    return {"success": True}


# =============================================================================
# БЛОКИРОВКА / РАЗБЛОКИРОВКА
# =============================================================================

@router.post(
    "/{user_id}/block",
    response_model=UserResponse,
    summary="Заблокировать пользователя",
    description="Причина блокировки обязательна. Доступно директорам.",
)
async def block_user(
    user_id: str,
    body: BlockUserRequest,
    current_user: User = Depends(require_director),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Нельзя заблокировать самого себя")

    if user.status == UserStatus.BLOCKED:
        raise HTTPException(status_code=400, detail="Пользователь уже заблокирован")

    user.status         = UserStatus.BLOCKED
    user.blocked_reason = body.reason
    user.blocked_at     = datetime.now(timezone.utc)
    user.blocked_by_user_id = current_user.id

    logger.info(
        f"Пользователь заблокирован: {user.phone} | "
        f"Причина: {body.reason} | Кто: {current_user.phone}"
    )
    return _to_response(user)


@router.post(
    "/{user_id}/unblock",
    response_model=UserResponse,
    summary="Разблокировать пользователя",
)
async def unblock_user(
    user_id: str,
    current_user: User = Depends(require_director),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    if user.status != UserStatus.BLOCKED:
        raise HTTPException(status_code=400, detail="Пользователь не заблокирован")

    user.status             = UserStatus.ACTIVE
    user.blocked_reason     = None
    user.blocked_at         = None
    user.blocked_by_user_id = None

    logger.info(f"Пользователь разблокирован: {user.phone} | Кто: {current_user.phone}")
    return _to_response(user)


# =============================================================================
# ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ
# =============================================================================

def _to_response(user: User) -> UserResponse:
    """Конвертирует SQLAlchemy объект User в Pydantic схему UserResponse."""
    return UserResponse(
        id=str(user.id),
        phone=user.phone,
        full_name=user.full_name,
        role=user.role,
        status=user.status,
        region_id=str(user.region_id)   if user.region_id   else None,
        division_id=str(user.division_id) if user.division_id else None,
        store_id=str(user.store_id)     if user.store_id     else None,
        inn=user.inn,
        fns_status=user.fns_status,
        bank_card_masked=user.bank_card_masked,
        bank_name=user.bank_name,
        income_from_kari_year=float(user.income_from_kari_year) if user.income_from_kari_year else 0.0,
        income_limit_remaining=user.income_limit_remaining if user.role == UserRole.EXECUTOR else None,
        income_risk_percent=user.income_risk_percent if user.role == UserRole.EXECUTOR else None,
        is_high_risk=user.is_high_risk if user.role == UserRole.EXECUTOR else None,
        created_at=user.created_at.isoformat() if user.created_at else None,
        last_login_at=user.last_login_at.isoformat() if user.last_login_at else None,
    )
