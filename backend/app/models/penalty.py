# =============================================================================
# KARI.Самозанятые v2 — Модель штрафов и нарушений исполнителей
# Файл: app/models/penalty.py
# =============================================================================
#
# Система штрафов помогает контролировать дисциплину исполнителей:
#
#   CANCEL     — самовольный отказ от задания после взятия (штраф рейтинга)
#   NO_SHOW    — не явился на задание без предупреждения (серьёзное нарушение)
#   QUALITY    — работа выполнена некачественно (несколько отклонений директором)
#   LATE       — систематические опоздания
#   DOCS       — проблемы с документами (аннулированный чек, и т.д.)
#
# Последствия накопленных штрафов:
#   3+ штрафа за 90 дней → исполнитель попадает в очередь на проверку HR
#   5+ штрафов → автоматическая блокировка до решения HR-службы
#
# =============================================================================

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import (
    Column, String, Boolean, DateTime, Date, Text, Numeric, Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Enum as SAEnum
from sqlalchemy.sql import func

from app.database import Base


class PenaltyType(str, Enum):
    """Тип нарушения."""
    CANCEL   = "cancel"    # Отказ от задания после взятия
    NO_SHOW  = "no_show"   # Неявка без предупреждения
    QUALITY  = "quality"   # Низкое качество (повторные отклонения)
    LATE     = "late"      # Систематические опоздания
    DOCS     = "docs"      # Нарушения с документами / чеками ФНС


class Penalty(Base):
    """
    Запись о нарушении исполнителя.
    Накапливаются и влияют на рейтинг и доступ к бирже заданий.
    """
    __tablename__ = "penalties"

    # -------------------------------------------------------------------------
    # ИДЕНТИФИКАЦИЯ
    # -------------------------------------------------------------------------
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # -------------------------------------------------------------------------
    # СВЯЗИ
    # -------------------------------------------------------------------------
    executor_id = Column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="Исполнитель которому выписан штраф",
    )
    task_id = Column(
        UUID(as_uuid=True),
        nullable=True,
        comment="Задание из-за которого возник штраф (если применимо)",
    )
    created_by_id = Column(
        UUID(as_uuid=True),
        nullable=False,
        comment="Директор магазина или HR, выписавший штраф",
    )

    # -------------------------------------------------------------------------
    # НАРУШЕНИЕ
    # -------------------------------------------------------------------------
    penalty_type = Column(
        SAEnum(PenaltyType, name="penalty_type"),
        nullable=False,
        comment="Тип нарушения",
    )
    reason = Column(
        Text,
        nullable=False,
        comment="Описание нарушения для исполнителя",
    )

    # Штраф может включать финансовое удержание (например, при аннулировании чека)
    amount = Column(
        Numeric(10, 2),
        nullable=True,
        comment="Сумма финансового удержания (если применимо, руб.)",
    )

    # -------------------------------------------------------------------------
    # СТАТУС
    # -------------------------------------------------------------------------
    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
        comment="Активен ли штраф. False = снят HR-службой",
    )
    resolved_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Дата снятия штрафа (если HR принял решение отменить)",
    )
    resolved_by_id = Column(
        UUID(as_uuid=True),
        nullable=True,
        comment="Кто снял штраф",
    )
    resolution_note = Column(
        Text,
        nullable=True,
        comment="Причина снятия штрафа",
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
    # ИНДЕКСЫ
    # =========================================================================
    __table_args__ = (
        # Все активные штрафы конкретного исполнителя
        Index("ix_penalty_executor_active", "executor_id", "is_active"),
        # Штрафы по типу (для статистики)
        Index("ix_penalty_type_created", "penalty_type", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<Penalty executor={self.executor_id} "
            f"type={self.penalty_type} active={self.is_active}>"
        )
