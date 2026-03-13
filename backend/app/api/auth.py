# =============================================================================
# KARI.Самозанятые — API авторизации
# Файл: app/api/auth.py
# =============================================================================
# Эндпоинты для входа в систему через SMS:
#
#   POST /api/v1/auth/send-code    — отправить SMS с кодом
#   POST /api/v1/auth/verify-code  — проверить код → получить JWT токен
#   GET  /api/v1/auth/me           — получить данные текущего пользователя
#   POST /api/v1/auth/logout       — выход из системы
#
# Весь флоу за 2 шага:
#   1. Клиент отправляет телефон → сервер шлёт SMS с 6-значным кодом
#   2. Клиент отправляет телефон + код → сервер возвращает JWT токен
# =============================================================================

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.database import get_db
from app.models.user import User, UserRole, UserStatus, FnsStatus
from app.core.security import create_access_token, get_current_user
from app.schemas.auth import (
    SendCodeRequest,
    SendCodeResponse,
    VerifyCodeRequest,
    AuthResponse,
    UserInfoResponse,
)
from app.services.sms_service import create_and_send_sms_code, verify_sms_code

logger = logging.getLogger(__name__)

# Создаём роутер — все пути будут с префиксом /api/v1/auth
router = APIRouter()


# =============================================================================
# ШАГ 1: ОТПРАВИТЬ SMS-КОД
# =============================================================================

@router.post(
    "/send-code",
    response_model=SendCodeResponse,
    summary="Отправить SMS-код на телефон",
    description="""
Отправляет 6-значный код подтверждения на указанный номер телефона.

**Ограничения:**
- Не более 3 SMS за 10 минут на один номер
- Код действителен 5 минут
- Принимаются только российские номера (+7 или 8)

**Примечание:** При включённом DEBUG-режиме SMS не отправляется,
код возвращается в поле `debug_code` ответа.
    """,
)
async def send_code(
    body: SendCodeRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> SendCodeResponse:

    # Проверяем что пользователь с таким телефоном существует в системе
    result = await db.execute(
        select(User).where(User.phone == body.phone)
    )
    user = result.scalar_one_or_none()

    if not user:
        # Возвращаем такой же ответ как при успехе — не раскрываем что номер не найден
        # (защита от перебора номеров)
        logger.warning(f"Попытка входа с незарегистрированным номером: {body.phone}")
        return SendCodeResponse(
            phone=body.phone,
            expires_in_seconds=settings.SMS_CODE_EXPIRE_MINUTES * 60,
            message="Если номер зарегистрирован, SMS будет отправлено",
        )

    # Проверяем что пользователь не заблокирован
    if user.status == UserStatus.BLOCKED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Аккаунт заблокирован. Причина: {user.blocked_reason or 'не указана'}",
        )

    # Отправляем SMS
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

    logger.info(f"SMS-код запрошен для: {body.phone}")

    return SendCodeResponse(
        phone=body.phone,
        expires_in_seconds=settings.SMS_CODE_EXPIRE_MINUTES * 60,
        debug_code=debug_code,  # None в продакшне, код при DEBUG=True
    )


# =============================================================================
# ШАГ 2: ПРОВЕРИТЬ КОД → ПОЛУЧИТЬ ТОКЕН
# =============================================================================

@router.post(
    "/verify-code",
    response_model=AuthResponse,
    summary="Проверить SMS-код и получить токен",
    description="""
Проверяет SMS-код и при успехе возвращает JWT access token.

**Токен нужно передавать** в каждом защищённом запросе:
```
Authorization: Bearer <token>
```

**Ошибки:**
- 400 — неверный или просроченный код
- 403 — аккаунт заблокирован
    """,
)
async def verify_code(
    body: VerifyCodeRequest,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:

    # Проверяем SMS-код
    ok, error_message = await verify_sms_code(
        db=db,
        phone=body.phone,
        code=body.code,
        purpose="auth",
    )

    if not ok:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_message,
        )

    # Код верный — получаем пользователя
    result = await db.execute(
        select(User).where(User.phone == body.phone)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден",
        )

    if user.status == UserStatus.BLOCKED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Аккаунт заблокирован. Причина: {user.blocked_reason or 'не указана'}",
        )

    # Обновляем дату последнего входа
    user.last_login_at = datetime.now(timezone.utc)

    # Создаём JWT токен
    access_token = create_access_token(
        user_id=str(user.id),
        phone=user.phone,
        role=user.role,
    )

    logger.info(f"Успешный вход: {user.phone} ({user.role})")

    # Формируем информацию о пользователе для ответа
    user_info = _build_user_info(user)

    return AuthResponse(
        access_token=access_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=user_info,
    )


# =============================================================================
# ТЕКУЩИЙ ПОЛЬЗОВАТЕЛЬ (для проверки токена)
# =============================================================================

@router.get(
    "/me",
    response_model=UserInfoResponse,
    summary="Получить данные текущего пользователя",
    description="Возвращает профиль пользователя чей токен передан в заголовке Authorization.",
)
async def get_me(
    current_user: User = Depends(get_current_user),
) -> UserInfoResponse:
    return _build_user_info(current_user)


# =============================================================================
# ВЫХОД ИЗ СИСТЕМЫ
# =============================================================================

@router.post(
    "/logout",
    summary="Выйти из системы",
    description="""
Фиксирует выход пользователя.

JWT токены нельзя "отозвать" на сервере — они действуют до истечения срока.
Клиент должен удалить токен из памяти устройства.
    """,
)
async def logout(
    current_user: User = Depends(get_current_user),
) -> dict:
    logger.info(f"Выход из системы: {current_user.phone}")
    return {
        "success": True,
        "message": "Выход выполнен. Удалите токен на устройстве.",
    }


# =============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =============================================================================

def _build_user_info(user: User) -> UserInfoResponse:
    """Формирует объект UserInfoResponse из модели пользователя."""
    info = UserInfoResponse(
        id=str(user.id),
        phone=user.phone,
        full_name=user.full_name,
        role=user.role,
        status=user.status,
    )

    # Для исполнителей добавляем дополнительные поля
    if user.role == UserRole.EXECUTOR:
        info.inn = user.inn                          # ← приложение проверяет inn чтобы пропустить онбординг
        info.fns_status = user.fns_status
        info.income_limit_remaining = user.income_limit_remaining
        info.is_high_risk = user.is_high_risk

    return info
