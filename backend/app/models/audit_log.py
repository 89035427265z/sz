# =============================================================================
# KARI.Самозанятые v2 — Модель журнала аудита
# Файл: app/models/audit_log.py
# =============================================================================
#
# Журнал аудита — полная история всех значимых действий в системе.
#
# Зачем нужен:
#   - Кто и когда изменил зарплату / статус / документы исполнителя
#   - Кто добавил запись в стоп-лист
#   - Кто одобрил реестр выплат на миллионы рублей
#   - Что произошло в системе до инцидента (для расследований)
#   - Доказательная база при спорах с исполнителями или ФНС
#
# Записывается автоматически через декоратор @audit на API роутах.
#
# =============================================================================

import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, DateTime, Text, Index,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func

from app.database import Base


class AuditLog(Base):
    """
    Запись журнала аудита. Неизменяемая — только INSERT, никогда UPDATE/DELETE.
    Хранится минимум 5 лет (требование бухгалтерского учёта).
    """
    __tablename__ = "audit_logs"

    # -------------------------------------------------------------------------
    # ИДЕНТИФИКАЦИЯ
    # -------------------------------------------------------------------------
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # -------------------------------------------------------------------------
    # КТО СДЕЛАЛ
    # -------------------------------------------------------------------------
    user_id = Column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="ID пользователя. NULL = системное действие (Celery, планировщик)",
    )
    user_phone = Column(
        String(20),
        nullable=True,
        comment="Телефон на момент действия (для истории после удаления аккаунта)",
    )
    user_role = Column(
        String(30),
        nullable=True,
        comment="Роль пользователя на момент действия",
    )
    ip_address = Column(
        String(45),
        nullable=True,
        comment="IP-адрес запроса (IPv4 или IPv6)",
    )

    # -------------------------------------------------------------------------
    # ЧТО СДЕЛАЛ
    # -------------------------------------------------------------------------
    action = Column(
        String(100),
        nullable=False,
        index=True,
        comment="Код действия: USER_BLOCKED, PAYMENT_APPROVED, STOP_LIST_ADDED и т.д.",
    )
    entity = Column(
        String(50),
        nullable=True,
        comment="Тип объекта: User, Task, Payment, StopList, Document",
    )
    entity_id = Column(
        String(36),
        nullable=True,
        comment="ID изменённого объекта",
    )
    details = Column(
        JSONB,
        nullable=True,
        comment="Подробности: старое и новое значение, причина, сумма и т.д.",
    )

    # -------------------------------------------------------------------------
    # КОГДА
    # -------------------------------------------------------------------------
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    # =========================================================================
    # ИНДЕКСЫ
    # =========================================================================
    __table_args__ = (
        # Поиск всех действий конкретного пользователя
        Index("ix_audit_user_action", "user_id", "action"),
        # Поиск всех изменений конкретного объекта
        Index("ix_audit_entity", "entity", "entity_id"),
        # Хронологический поиск по типу действия
        Index("ix_audit_action_created", "action", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<AuditLog action={self.action} "
            f"user={self.user_phone} entity={self.entity}/{self.entity_id}>"
        )
