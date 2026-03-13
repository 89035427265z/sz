# =============================================================================
# KARI.Самозанятые — Модель документов ЭДО
# Файл: app/models/document.py
# =============================================================================
# Описывает таблицу documents — договоры ГПХ и акты выполненных работ.
#
# Жизненный цикл документа:
#   DRAFT → PENDING_SIGN → SIGNED
#          ↘ CANCELLED
#
# ТЗ 3.3: Документы подписываются через ПЭП (простая электронная подпись)
#         — исполнитель получает SMS-код и подтверждает подпись.
# =============================================================================

import uuid
from enum import Enum

from sqlalchemy import (
    Column, String, Boolean, DateTime, Text, ForeignKey, Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Enum as SAEnum
from sqlalchemy.sql import func

from app.database import Base


# =============================================================================
# ПЕРЕЧИСЛЕНИЯ
# =============================================================================

class DocumentType(str, Enum):
    """Тип документа."""
    CONTRACT = "contract"  # Договор ГПХ (гражданско-правового характера)
    ACT      = "act"       # Акт выполненных работ


class DocumentStatus(str, Enum):
    """Статус документа."""
    DRAFT        = "draft"        # PDF сформирован, ещё не отправлен на подпись
    PENDING_SIGN = "pending_sign" # Отправлен SMS-код, ждём подпись исполнителя
    SIGNED       = "signed"       # Подписан ПЭП — юридически значимый
    CANCELLED    = "cancelled"    # Отменён (задание отменено / отклонено)


# =============================================================================
# ТАБЛИЦА ДОКУМЕНТОВ
# =============================================================================

class Document(Base):
    """
    Документ ЭДО: договор ГПХ или акт выполненных работ.

    Один документ привязан к одному заданию.
    На одно задание создаётся 2 документа:
      1. Договор ГПХ — при взятии задания исполнителем (статус TAKEN)
      2. Акт выполненных работ — при приёмке директором (статус ACCEPTED)

    Подпись: исполнитель получает SMS-код и вводит его в мобильном приложении.
    Это ПЭП — простая электронная подпись (признаётся судами по 63-ФЗ).
    """
    __tablename__ = "documents"

    # -------------------------------------------------------------------------
    # ИДЕНТИФИКАЦИЯ
    # -------------------------------------------------------------------------
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Человекочитаемый номер: KARI-2026-ДГ-000001 (договор) / KARI-2026-АКТ-000001 (акт)
    number = Column(
        String(40),
        unique=True,
        nullable=True,
        comment="Номер документа: KARI-YYYY-ДГ-NNNNNN или KARI-YYYY-АКТ-NNNNNN",
    )

    # -------------------------------------------------------------------------
    # СВЯЗЬ С ЗАДАНИЕМ
    # -------------------------------------------------------------------------
    task_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="ID задания, к которому относится документ",
    )

    # -------------------------------------------------------------------------
    # ТИП И СТАТУС
    # -------------------------------------------------------------------------
    doc_type = Column(
        SAEnum(DocumentType, name="document_type"),
        nullable=False,
        comment="Тип: CONTRACT (договор ГПХ) или ACT (акт выполненных работ)",
    )
    status = Column(
        SAEnum(DocumentStatus, name="document_status"),
        nullable=False,
        default=DocumentStatus.DRAFT,
        index=True,
        comment="Текущий статус документа",
    )

    # -------------------------------------------------------------------------
    # УЧАСТНИКИ ДОКУМЕНТА (копируется при создании — не меняется)
    # -------------------------------------------------------------------------
    executor_id = Column(
        UUID(as_uuid=True),
        nullable=False,
        comment="ID исполнителя (самозанятого) — сторона по договору",
    )
    executor_name = Column(
        String(255),
        nullable=False,
        comment="ФИО исполнителя на момент создания (копия из users)",
    )
    executor_inn = Column(
        String(12),
        nullable=False,
        comment="ИНН исполнителя на момент создания (копия из users)",
    )
    executor_phone = Column(
        String(20),
        nullable=False,
        comment="Телефон исполнителя для отправки SMS-кода подписи",
    )

    # -------------------------------------------------------------------------
    # СОДЕРЖАНИЕ ДОКУМЕНТА (для отображения и формирования PDF)
    # -------------------------------------------------------------------------
    task_title = Column(
        String(200),
        nullable=False,
        comment="Название задания (копия из tasks.title)",
    )
    task_number = Column(
        String(30),
        nullable=True,
        comment="Номер задания (копия из tasks.number)",
    )
    store_address = Column(
        String(500),
        nullable=False,
        comment="Адрес магазина (копия из tasks.store_address)",
    )
    amount = Column(
        String(20),
        nullable=False,
        comment="Сумма вознаграждения в рублях (строка: '1500.00')",
    )
    work_date = Column(
        String(20),
        nullable=True,
        comment="Дата выполнения работ (строка для PDF: '01 апреля 2026 г.')",
    )

    # -------------------------------------------------------------------------
    # ФАЙЛ PDF (хранится в MinIO)
    # -------------------------------------------------------------------------
    file_path = Column(
        String(500),
        nullable=True,
        comment="Путь к PDF в MinIO: kari-docs/2026/04/contract_uuid.pdf",
    )
    file_size_bytes = Column(
        String(20),
        nullable=True,
        comment="Размер PDF-файла в байтах (для отображения)",
    )

    # -------------------------------------------------------------------------
    # ПОДПИСЬ (ПЭП через SMS)
    # -------------------------------------------------------------------------

    # --- Подпись исполнителя ---
    sign_request_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Когда отправлен SMS-код на подпись",
    )
    executor_signed_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Когда исполнитель подписал (ввёл SMS-код)",
    )
    executor_sign_ip = Column(
        String(50),
        nullable=True,
        comment="IP-адрес устройства при подписи (для юридической значимости)",
    )
    executor_sign_device = Column(
        String(200),
        nullable=True,
        comment="User-Agent устройства при подписи (iOS/Android + версия)",
    )

    # --- Подпись директора ---
    # Директор подтверждает документ кликом в кабинете (без SMS-кода)
    director_id = Column(
        UUID(as_uuid=True),
        nullable=True,
        comment="ID директора, принявшего работу",
    )
    director_name = Column(
        String(255),
        nullable=True,
        comment="ФИО директора (копия при подписи)",
    )
    director_signed_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Когда директор подтвердил документ",
    )

    # -------------------------------------------------------------------------
    # ХРОНОЛОГИЯ
    # -------------------------------------------------------------------------
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Когда создан документ (сформирован PDF)",
    )
    updated_at = Column(
        DateTime(timezone=True),
        onupdate=func.now(),
        nullable=True,
    )

    # -------------------------------------------------------------------------
    # ИНДЕКСЫ
    # -------------------------------------------------------------------------
    __table_args__ = (
        # Все документы по одному заданию
        Index("ix_documents_task_type", "task_id", "doc_type"),
        # Документы конкретного исполнителя
        Index("ix_documents_executor", "executor_id", "status"),
    )

    @property
    def is_signed(self) -> bool:
        """Полностью подписан обеими сторонами."""
        return self.status == DocumentStatus.SIGNED

    @property
    def is_contract(self) -> bool:
        return self.doc_type == DocumentType.CONTRACT

    @property
    def is_act(self) -> bool:
        return self.doc_type == DocumentType.ACT

    def __repr__(self) -> str:
        return f"<Document {self.number or self.id} [{self.doc_type}] [{self.status}]>"
