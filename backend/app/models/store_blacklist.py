# =============================================================================
# KARI.Самозанятые v2 — Чёрный список магазина
# Файл: app/models/store_blacklist.py
# =============================================================================
#
# Чёрный список на уровне магазина — в дополнение к глобальному стоп-листу.
#
# Разница:
#   StopList         — глобальная блокировка ИНН (422-ФЗ), исполнитель
#                      не может работать ни в одном магазине KARI
#   StoreBlacklist   — локальная блокировка: исполнитель заблокирован
#                      только в конкретном магазине, в других — может работать
#
# Когда используется StoreBlacklist:
#   - Конфликт с конкретным директором магазина
#   - Кража / порча имущества в конкретном магазине
#   - Нарушение дисциплины в конкретном магазине
#
# =============================================================================

import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, Boolean, DateTime, Text, Index, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.database import Base


class StoreBlacklist(Base):
    """
    Запись о запрете исполнителю работать в конкретном магазине.
    Проверяется при попытке взять задание конкретного магазина.
    """
    __tablename__ = "store_blacklists"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # -------------------------------------------------------------------------
    # СВЯЗИ
    # -------------------------------------------------------------------------
    store_id = Column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="Магазин в котором заблокирован исполнитель",
    )
    executor_id = Column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="Заблокированный исполнитель",
    )
    created_by_id = Column(
        UUID(as_uuid=True),
        nullable=False,
        comment="Директор магазина, добавивший в ЧС",
    )

    # -------------------------------------------------------------------------
    # ПРИЧИНА
    # -------------------------------------------------------------------------
    reason = Column(
        Text,
        nullable=True,
        comment="Причина блокировки",
    )

    # -------------------------------------------------------------------------
    # СТАТУС
    # -------------------------------------------------------------------------
    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
    )
    expires_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="NULL = бессрочно. Или дата когда блокировка истекает.",
    )

    # -------------------------------------------------------------------------
    # СЛУЖЕБНЫЕ
    # -------------------------------------------------------------------------
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # =========================================================================
    # ОГРАНИЧЕНИЯ И ИНДЕКСЫ
    # =========================================================================
    __table_args__ = (
        # Один исполнитель — одна активная запись на магазин
        UniqueConstraint("store_id", "executor_id", name="uq_blacklist_store_executor"),
        Index("ix_blacklist_check", "store_id", "executor_id", "is_active"),
    )

    def __repr__(self) -> str:
        return (
            f"<StoreBlacklist store={self.store_id} "
            f"executor={self.executor_id} active={self.is_active}>"
        )
