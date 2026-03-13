# =============================================================================
# KARI.Самозанятые — Схемы данных пользователей
# Файл: app/schemas/user.py
# =============================================================================

import re
from typing import Optional
from pydantic import BaseModel, field_validator


# =============================================================================
# ЗАПРОСЫ
# =============================================================================

class InitAdminRequest(BaseModel):
    """
    Создание первого директора региона (только если БД пустая).
    Вызывается один раз при первом запуске системы.
    """
    phone:     str
    full_name: str
    secret:    str  # Секретная фраза из .env — защита от случайного вызова

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        digits = re.sub(r"\D", "", v)
        if len(digits) == 11 and digits[0] in ("7", "8"):
            return "+7" + digits[1:]
        raise ValueError("Некорректный номер телефона")

    model_config = {
        "json_schema_extra": {
            "example": {
                "phone": "+79991234567",
                "full_name": "Юрий Иванов",
                "secret": "KARI_INIT_SECRET",
            }
        }
    }


class RegisterExecutorRequest(BaseModel):
    """
    Регистрация исполнителя (самозанятого) через мобильное приложение.
    Шаг 1 из 2 — после этого придёт SMS для подтверждения.
    """
    phone:     str
    full_name: str
    inn:       str  # ИНН физлица — 12 цифр

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        digits = re.sub(r"\D", "", v)
        if len(digits) == 11 and digits[0] in ("7", "8"):
            return "+7" + digits[1:]
        raise ValueError("Некорректный номер телефона")

    @field_validator("inn")
    @classmethod
    def validate_inn(cls, v: str) -> str:
        inn = re.sub(r"\D", "", v)
        if len(inn) != 12:
            raise ValueError("ИНН физического лица должен состоять из 12 цифр")
        return inn

    model_config = {
        "json_schema_extra": {
            "example": {
                "phone": "+79991234567",
                "full_name": "Петров Пётр Петрович",
                "inn": "123456789012",
            }
        }
    }


class CreateDirectorRequest(BaseModel):
    """
    Создание директора (подразделения или магазина).
    Выполняется директором региона через веб-кабинет.
    """
    phone:       str
    full_name:   str
    role:        str   # division_director или store_director
    region_id:   Optional[str] = None
    division_id: Optional[str] = None
    store_id:    Optional[str] = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        digits = re.sub(r"\D", "", v)
        if len(digits) == 11 and digits[0] in ("7", "8"):
            return "+7" + digits[1:]
        raise ValueError("Некорректный номер телефона")

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        allowed = ("division_director", "store_director")
        if v not in allowed:
            raise ValueError(f"Роль должна быть одной из: {', '.join(allowed)}")
        return v

    model_config = {
        "json_schema_extra": {
            "example": {
                "phone": "+79991234567",
                "full_name": "Сидоров Иван Петрович",
                "role": "store_director",
                "store_id": "550e8400-e29b-41d4-a716-446655440000",
            }
        }
    }


class UpdateBankCardRequest(BaseModel):
    """Привязка банковской карты исполнителем."""
    card_token:       str    # Токен карты из Совкомбанка
    card_masked:      str    # Маскированный номер: **** **** **** 1234
    bank_name:        str    # Название банка

    model_config = {
        "json_schema_extra": {
            "example": {
                "card_token": "tok_sovcom_xxxx",
                "card_masked": "**** **** **** 1234",
                "bank_name": "Сбербанк",
            }
        }
    }


class UpdateFcmTokenRequest(BaseModel):
    """Обновление FCM-токена для push-уведомлений (вызывается мобильным приложением)."""
    fcm_token: str


class UpdateProfileRequest(BaseModel):
    """Обновление профиля исполнителем — ФИО и/или ИНН."""
    full_name: Optional[str] = None
    inn:       Optional[str] = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "full_name": "Петров Пётр Петрович",
                "inn": "381234567890",
            }
        }
    }


class BlockUserRequest(BaseModel):
    """Блокировка пользователя — причина обязательна."""
    reason: str

    model_config = {
        "json_schema_extra": {
            "example": {"reason": "Аннулирование чека ФНС 12.11.2025"}
        }
    }


# =============================================================================
# ОТВЕТЫ
# =============================================================================

class UserResponse(BaseModel):
    """Данные пользователя — возвращаются в большинстве ответов."""

    id:         str
    phone:      str
    full_name:  str
    role:       str
    status:     str

    # Для директоров
    region_id:   Optional[str] = None
    division_id: Optional[str] = None
    store_id:    Optional[str] = None

    # Для исполнителей
    inn:                    Optional[str]   = None
    fns_status:             Optional[str]   = None
    bank_card_masked:       Optional[str]   = None
    bank_name:              Optional[str]   = None
    income_from_kari_year:  Optional[float] = None
    income_limit_remaining: Optional[float] = None
    income_risk_percent:    Optional[float] = None
    is_high_risk:           Optional[bool]  = None

    created_at:    Optional[str] = None
    last_login_at: Optional[str] = None

    model_config = {"from_attributes": True}


class UserListResponse(BaseModel):
    """Постраничный список пользователей."""
    items:   list[UserResponse]
    total:   int
    page:    int
    size:    int
    pages:   int


class RegisterExecutorResponse(BaseModel):
    """Ответ после регистрации исполнителя."""
    success:            bool = True
    message:            str  = "Регистрация выполнена. SMS-код отправлен."
    phone:              str
    expires_in_seconds: int
    debug_code:         Optional[str] = None  # Только при DEBUG=True
