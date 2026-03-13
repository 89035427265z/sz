# =============================================================================
# KARI.Самозанятые — Безопасность и JWT токены
# Файл: app/core/security.py
# =============================================================================
# JWT (JSON Web Token) — это "пропуск" пользователя в систему.
# После успешного входа по SMS-коду сервер выдаёт токен.
# Дальше клиент передаёт токен в каждом запросе (заголовок Authorization).
# Сервер проверяет токен и знает кто делает запрос и какая у него роль.
# =============================================================================

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.database import get_db

# Схема авторизации — Bearer токен в заголовке Authorization: Bearer <token>
bearer_scheme = HTTPBearer(auto_error=False)


# =============================================================================
# СОЗДАНИЕ JWT ТОКЕНА
# =============================================================================

def create_access_token(
    user_id: str,
    phone: str,
    role: str,
) -> str:
    """
    Создаёт JWT токен для пользователя.

    Токен содержит:
    - sub (subject) — ID пользователя
    - phone — номер телефона
    - role — роль (regional_director, executor и т.д.)
    - exp — время истечения
    - iat — время создания

    Токен подписан SECRET_KEY — подделать без ключа невозможно.
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    payload = {
        "sub":   str(user_id),
        "phone": phone,
        "role":  role,
        "iat":   now,
        "exp":   expire,
    }

    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return token


# =============================================================================
# РАСШИФРОВКА И ПРОВЕРКА ТОКЕНА
# =============================================================================

def decode_token(token: str) -> dict:
    """
    Проверяет подпись токена и возвращает его содержимое.

    Выбрасывает ValueError если:
    - Токен поддельный (неверная подпись)
    - Токен истёк (exp в прошлом)
    - Токен повреждён
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        return payload
    except JWTError as e:
        raise ValueError(f"Недействительный токен: {e}")


# =============================================================================
# ЗАВИСИМОСТИ FASTAPI — используются в защищённых эндпоинтах
# =============================================================================

async def get_current_user_id(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> str:
    """
    Извлекает ID текущего пользователя из токена.

    Использование в эндпоинте:
        async def my_endpoint(user_id: str = Depends(get_current_user_id)):
            ...
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется авторизация. Передайте токен в заголовке Authorization: Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_token(credentials.credentials)
        user_id: str = payload.get("sub")
        if not user_id:
            raise ValueError("Токен не содержит ID пользователя")
        return user_id
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Возвращает объект текущего пользователя из БД.

    Использование:
        async def my_endpoint(user = Depends(get_current_user)):
            print(user.full_name, user.role)
    """
    from app.models.user import User, UserStatus

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Пользователь не найден",
        )

    if user.status == UserStatus.BLOCKED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Аккаунт заблокирован. Причина: {user.blocked_reason or 'не указана'}",
        )

    if user.status == UserStatus.ARCHIVED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Аккаунт удалён из системы",
        )

    return user


# =============================================================================
# ПРОВЕРКА РОЛИ — используется для ограничения доступа
# =============================================================================

def require_role(*allowed_roles: str):
    """
    Фабрика зависимостей: проверяет что у пользователя нужная роль.

    Использование:
        @router.get("/admin-only")
        async def admin_page(
            user = Depends(require_role("regional_director"))
        ):
            ...
    """
    async def check_role(user = Depends(get_current_user)):
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Доступ запрещён. Требуется роль: {', '.join(allowed_roles)}",
            )
        return user
    return check_role


# Готовые зависимости для частых случаев
require_director   = require_role("regional_director", "division_director", "store_director")
require_regional   = require_role("regional_director")
require_executor   = require_role("executor")
