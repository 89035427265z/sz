# =============================================================================
# KARI.Самозанятые — Схемы данных для авторизации
# Файл: app/schemas/auth.py
# =============================================================================
# Pydantic-схемы описывают формат данных которые:
#   - клиент ПРИСЫЛАЕТ нам (Request)
#   - мы ОТДАЁМ клиенту (Response)
# FastAPI автоматически проверяет входные данные по этим схемам
# и показывает их в Swagger документации (/docs)
# =============================================================================

import re
from typing import Optional
from pydantic import BaseModel, field_validator, model_validator


# =============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =============================================================================

def normalize_phone(phone: str) -> str:
    """
    Приводит номер телефона к единому формату +7XXXXXXXXXX.

    Принимает:  89991234567 / +79991234567 / 79991234567 / 8(999)123-45-67
    Возвращает: +79991234567
    """
    # Убираем всё кроме цифр
    digits = re.sub(r"\D", "", phone)

    # Российские номера: 11 цифр начинающихся на 7 или 8
    if len(digits) == 11 and digits[0] in ("7", "8"):
        return "+7" + digits[1:]

    # Если уже в международном формате без плюса
    if len(digits) == 10:
        return "+7" + digits

    raise ValueError(f"Некорректный номер телефона: {phone}")


# =============================================================================
# ЗАПРОСЫ (то что присылает клиент)
# =============================================================================

class SendCodeRequest(BaseModel):
    """Запрос на отправку SMS с кодом подтверждения."""

    phone: str

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        try:
            return normalize_phone(v)
        except ValueError:
            raise ValueError(
                "Некорректный номер телефона. "
                "Ожидается российский номер в формате +79991234567 или 89991234567"
            )

    model_config = {
        "json_schema_extra": {
            "example": {"phone": "+79991234567"}
        }
    }


class VerifyCodeRequest(BaseModel):
    """Запрос на проверку SMS-кода и получение JWT токена."""

    phone: str
    code: str

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        try:
            return normalize_phone(v)
        except ValueError:
            raise ValueError("Некорректный номер телефона")

    @field_validator("code")
    @classmethod
    def validate_code(cls, v: str) -> str:
        code = v.strip()
        if not re.match(r"^\d{6}$", code):
            raise ValueError("Код должен состоять из 6 цифр")
        return code

    model_config = {
        "json_schema_extra": {
            "example": {"phone": "+79991234567", "code": "123456"}
        }
    }


class RefreshTokenRequest(BaseModel):
    """Запрос на обновление токена."""
    refresh_token: str


# =============================================================================
# ОТВЕТЫ (то что мы отдаём клиенту)
# =============================================================================

class SendCodeResponse(BaseModel):
    """Ответ после отправки SMS."""

    success: bool = True
    message: str = "SMS-код отправлен"
    phone: str
    expires_in_seconds: int  # Через сколько секунд код устареет (обычно 300 = 5 минут)
    # В DEBUG-режиме сюда попадает сам код (чтобы не тратить SMS при разработке)
    debug_code: Optional[str] = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "success": True,
                "message": "SMS-код отправлен",
                "phone": "+79991234567",
                "expires_in_seconds": 300,
            }
        }
    }


class UserInfoResponse(BaseModel):
    """Информация о пользователе — включается в ответ при авторизации."""

    id: str
    phone: str
    full_name: str
    role: str                      # regional_director / executor и т.д.
    status: str                    # active / blocked

    # Только для исполнителей (для директоров = None)
    inn: Optional[str] = None                      # ← нужно для проверки онбординга
    fns_status: Optional[str] = None
    income_limit_remaining: Optional[float] = None
    is_high_risk: Optional[bool] = None

    model_config = {
        "from_attributes": True,   # Позволяет создавать из SQLAlchemy объектов
        "json_schema_extra": {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "phone": "+79991234567",
                "full_name": "Иванов Иван Иванович",
                "role": "executor",
                "status": "active",
                "fns_status": "active",
                "income_limit_remaining": 2150000.00,
                "is_high_risk": False,
            }
        }
    }


class AuthResponse(BaseModel):
    """Ответ после успешной авторизации — токен + данные пользователя."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int          # Время жизни токена в секундах

    user: UserInfoResponse

    model_config = {
        "json_schema_extra": {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "expires_in": 86400,
                "user": {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "phone": "+79991234567",
                    "full_name": "Иванов Иван Иванович",
                    "role": "executor",
                    "status": "active",
                }
            }
        }
    }


class ErrorResponse(BaseModel):
    """Стандартный формат ошибки."""
    success: bool = False
    error: str
    detail: Optional[str] = None
