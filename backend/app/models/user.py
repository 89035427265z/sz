# =============================================================================
# KARI.Самозанятые — Модель пользователей
# Файл: app/models/user.py
# =============================================================================
# Один файл описывает ВСЕХ пользователей системы:
#   - Директоров (региона, подразделения, магазина) — сотрудники KARI
#   - Исполнителей (самозанятых) — внешние подрядчики
#
# Поля для самозанятых (ИНН, доходы, ФНС) заполнены только у исполнителей.
# У директоров эти поля пустые (NULL).
# =============================================================================

import uuid
from datetime import datetime, date
from enum import Enum
from decimal import Decimal

from sqlalchemy import (
    Column, String, Boolean, DateTime, Date,
    Integer, Numeric, Text, Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Enum as SAEnum
from sqlalchemy.sql import func

from app.database import Base


# =============================================================================
# ПЕРЕЧИСЛЕНИЯ (ENUM) — фиксированные наборы значений
# =============================================================================

class UserRole(str, Enum):
    """Роли пользователей в системе KARI.Самозанятые."""
    REGIONAL_DIRECTOR = "regional_director"   # Директор региона — полный доступ
    DIVISION_DIRECTOR = "division_director"   # Директор подразделения
    STORE_DIRECTOR    = "store_director"      # Директор магазина
    HRD               = "hrd"                 # HRD / Бухгалтерия — управление исполнителями
    EXECUTOR          = "executor"            # Исполнитель (самозанятый)


class FnsStatus(str, Enum):
    """Статус самозанятого по данным ФНС "Мой налог"."""
    ACTIVE   = "active"    # Активный самозанятый — можно выдавать задания
    INACTIVE = "inactive"  # Не является самозанятым — нельзя нанимать
    BLOCKED  = "blocked"   # Заблокирован системой (аннулированный чек или иное)


class UserStatus(str, Enum):
    """Текущий статус пользователя в системе."""
    ACTIVE   = "active"    # Работает в штатном режиме
    BLOCKED  = "blocked"   # Заблокирован администратором
    ARCHIVED = "archived"  # Удалён из системы (данные сохранены)


# =============================================================================
# ТАБЛИЦА ПОЛЬЗОВАТЕЛЕЙ
# =============================================================================

class User(Base):
    """
    Все пользователи системы: директора KARI и самозанятые исполнители.

    Директора идентифицируются по номеру телефона (корпоративный).
    Самозанятые — по номеру телефона, привязанному к ФНС "Мой налог".
    """
    __tablename__ = "users"

    # -------------------------------------------------------------------------
    # ИДЕНТИФИКАЦИЯ
    # -------------------------------------------------------------------------
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Уникальный идентификатор пользователя",
    )
    phone = Column(
        String(20),
        unique=True,
        nullable=False,
        index=True,
        comment="Номер телефона — основной логин (+7XXXXXXXXXX)",
    )

    # -------------------------------------------------------------------------
    # ЛИЧНЫЕ ДАННЫЕ
    # -------------------------------------------------------------------------
    full_name = Column(
        String(255),
        nullable=False,
        comment="ФИО полностью",
    )
    role = Column(
        SAEnum(UserRole, name="user_role"),
        nullable=False,
        comment="Роль в системе",
    )
    status = Column(
        SAEnum(UserStatus, name="user_status"),
        nullable=False,
        default=UserStatus.ACTIVE,
        comment="Текущий статус пользователя",
    )

    # -------------------------------------------------------------------------
    # БЛОКИРОВКА
    # -------------------------------------------------------------------------
    blocked_reason = Column(
        Text,
        nullable=True,
        comment="Причина блокировки (заполняется при статусе BLOCKED)",
    )
    blocked_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Дата и время блокировки",
    )
    blocked_by_user_id = Column(
        UUID(as_uuid=True),
        nullable=True,
        comment="Кто заблокировал (ID пользователя-администратора)",
    )

    # -------------------------------------------------------------------------
    # ПРИВЯЗКА К СТРУКТУРЕ KARI (только для директоров)
    # Исполнители к структуре не привязаны — у них эти поля NULL
    # -------------------------------------------------------------------------
    region_id = Column(
        UUID(as_uuid=True),
        nullable=True,
        comment="ID региона (заполняется у директора региона)",
    )
    division_id = Column(
        UUID(as_uuid=True),
        nullable=True,
        comment="ID подразделения (заполняется у директора подразделения)",
    )
    store_id = Column(
        UUID(as_uuid=True),
        nullable=True,
        comment="ID магазина (заполняется у директора магазина)",
    )

    # -------------------------------------------------------------------------
    # ВРЕМЕННЫЕ МЕТКИ
    # -------------------------------------------------------------------------
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Дата регистрации в системе",
    )
    updated_at = Column(
        DateTime(timezone=True),
        onupdate=func.now(),
        nullable=True,
        comment="Дата последнего обновления профиля",
    )
    last_login_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Дата и время последнего входа",
    )

    # =========================================================================
    # ПОЛЯ ТОЛЬКО ДЛЯ ИСПОЛНИТЕЛЕЙ (самозанятых)
    # У директоров все поля ниже = NULL
    # =========================================================================

    # -------------------------------------------------------------------------
    # ФНС "МОЙ НАЛОГ"
    # -------------------------------------------------------------------------
    inn = Column(
        String(12),
        unique=True,
        nullable=True,
        index=True,
        comment="ИНН (12 цифр для физлиц). Только для самозанятых.",
    )
    fns_status = Column(
        SAEnum(FnsStatus, name="fns_status"),
        nullable=True,
        comment="Статус самозанятого по данным ФНС",
    )
    fns_registration_date = Column(
        Date,
        nullable=True,
        comment="Дата регистрации в качестве самозанятого",
    )
    fns_token_encrypted = Column(
        Text,
        nullable=True,
        comment="Токен ФНС API (зашифрован). Нужен для регистрации доходов.",
    )
    fns_last_check_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Когда последний раз проверяли статус в ФНС",
    )

    # -------------------------------------------------------------------------
    # КОНТРОЛЬ ДОХОДОВ
    # Лимит по закону: 2 400 000 руб в год (ст. 4 422-ФЗ)
    # Риск переквалификации: если >80% дохода от одного заказчика (KARI)
    # -------------------------------------------------------------------------
    income_from_kari_year = Column(
        Numeric(12, 2),
        default=Decimal("0.00"),
        nullable=True,
        comment="Доход от KARI за текущий год (из зарегистрированных чеков)",
    )
    income_total_year = Column(
        Numeric(12, 2),
        default=Decimal("0.00"),
        nullable=True,
        comment="Общий годовой доход по всем источникам (для расчёта риска 80%)",
    )
    income_tracking_year = Column(
        Integer,
        nullable=True,
        comment="Год, за который ведётся учёт дохода",
    )

    # -------------------------------------------------------------------------
    # БАНКОВСКИЕ РЕКВИЗИТЫ ДЛЯ ВЫПЛАТ (через Совкомбанк)
    # -------------------------------------------------------------------------
    bank_card_masked = Column(
        String(19),
        nullable=True,
        comment="Маскированный номер карты: **** **** **** 1234",
    )
    bank_name = Column(
        String(100),
        nullable=True,
        comment="Название банка (отображается в интерфейсе)",
    )
    bank_card_token = Column(
        Text,
        nullable=True,
        comment="Токен карты в системе Совкомбанка (реальный номер не хранится)",
    )

    # -------------------------------------------------------------------------
    # PUSH-УВЕДОМЛЕНИЯ
    # -------------------------------------------------------------------------
    fcm_token = Column(
        Text,
        nullable=True,
        comment="Firebase Cloud Messaging токен — для отправки уведомлений на телефон",
    )

    # =========================================================================
    # ИНДЕКСЫ ДЛЯ БЫСТРОГО ПОИСКА
    # =========================================================================
    __table_args__ = (
        # Быстрый поиск всех самозанятых по статусу ФНС
        Index("ix_users_role_fns_status", "role", "fns_status"),
        # Быстрый поиск сотрудников по магазину
        Index("ix_users_store_id", "store_id"),
        # Быстрый поиск по региону
        Index("ix_users_region_id", "region_id"),
    )

    # =========================================================================
    # ВЫЧИСЛЯЕМЫЕ СВОЙСТВА (не хранятся в БД, считаются на лету)
    # =========================================================================

    @property
    def income_risk_percent(self) -> float:
        """
        Процент дохода от KARI относительно общего дохода.
        Если больше 80% — риск переквалификации в сотрудника (нарушение закона).
        """
        if not self.income_total_year or float(self.income_total_year) == 0:
            return 0.0
        return round(
            float(self.income_from_kari_year or 0) /
            float(self.income_total_year) * 100,
            1
        )

    @property
    def income_limit_remaining(self) -> float:
        """
        Остаток разрешённого дохода до конца года.
        Лимит: 2 400 000 руб/год. При достижении — нельзя выдавать новые задания.
        """
        limit = 2_400_000.0
        used = float(self.income_from_kari_year or 0)
        return max(0.0, limit - used)

    @property
    def is_income_limit_exceeded(self) -> bool:
        """Достиг ли исполнитель годового лимита дохода 2 400 000 руб."""
        return float(self.income_from_kari_year or 0) >= 2_400_000.0

    @property
    def is_high_risk(self) -> bool:
        """
        Находится ли исполнитель в зоне риска переквалификации.
        Риск = более 80% дохода от KARI.
        """
        return self.income_risk_percent > 80.0

    def __repr__(self) -> str:
        return f"<User id={self.id} phone={self.phone} role={self.role}>"


# =============================================================================
# ТАБЛИЦА SMS-КОДОВ
# Временные коды для авторизации и подписи актов (ПЭП)
# =============================================================================

class SmsCode(Base):
    """
    Одноразовые SMS-коды.

    Используются для двух целей:
    - purpose='auth' — вход в систему по номеру телефона
    - purpose='sign' — подпись акта выполненных работ (ПЭП)

    Код действителен 5 минут (настраивается в config.py).
    После 3 неверных попыток код блокируется.
    """
    __tablename__ = "sms_codes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    phone = Column(
        String(20),
        nullable=False,
        index=True,
        comment="Номер телефона получателя",
    )
    code = Column(
        String(6),
        nullable=False,
        comment="6-значный цифровой код",
    )
    purpose = Column(
        String(20),
        nullable=False,
        default="auth",
        comment="Цель: 'auth' — авторизация, 'sign' — подпись акта",
    )

    # Дополнительный контекст (например, ID акта для подписи)
    context_id = Column(
        UUID(as_uuid=True),
        nullable=True,
        comment="ID связанного объекта (например, ID акта при purpose='sign')",
    )

    attempts = Column(
        Integer,
        default=0,
        nullable=False,
        comment="Количество неверных попыток ввода (блокируем после 3)",
    )
    is_used = Column(
        Boolean,
        default=False,
        nullable=False,
        comment="Использован ли код (True = нельзя использовать повторно)",
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    expires_at = Column(
        DateTime(timezone=True),
        nullable=False,
        comment="Время истечения кода (created_at + 5 минут)",
    )

    __table_args__ = (
        # Быстрый поиск активных кодов по телефону
        Index("ix_sms_codes_phone_purpose", "phone", "purpose", "is_used"),
    )

    def __repr__(self) -> str:
        return f"<SmsCode phone={self.phone} purpose={self.purpose} used={self.is_used}>"
