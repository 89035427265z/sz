# =============================================================================
# KARI.Самозанятые — Модель выплат
# Файл: app/models/payment.py
# =============================================================================
# Описывает четыре таблицы:
#
#   1. Payment            — отдельная выплата за выполненное задание
#   2. PaymentRegistry    — реестр массовой выплаты (загружается Excel-файлом, ТЗ 3.12)
#   3. PaymentRegistryItem — строки реестра (один исполнитель = одна строка)
#   4. FnsReceipt         — чеки ФНС "Мой налог" (контроль аннулирования, ТЗ 3.11)
# =============================================================================

import uuid
from decimal import Decimal
from enum import Enum

from sqlalchemy import (
    Column, String, Boolean, DateTime, Date,
    Integer, Numeric, Text, Float, SmallInteger,
    ForeignKey, Index, JSON,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


# =============================================================================
# ПЕРЕЧИСЛЕНИЯ
# =============================================================================

class PaymentStatus(str, Enum):
    """Статус отдельной выплаты."""
    PENDING    = "pending"    # Создана, ожидает обработки
    PROCESSING = "processing" # Отправлена в Совкомбанк, ждём ответа
    COMPLETED  = "completed"  # Деньги зачислены на карту исполнителя
    FAILED     = "failed"     # Ошибка при выплате (подробности в error_message)
    CANCELLED  = "cancelled"  # Отменена до обработки


class RegistryStatus(str, Enum):
    """Статус реестра массовых выплат."""
    UPLOADED   = "uploaded"   # Файл загружен, ещё не проверен
    VALIDATING = "validating" # Идёт автоматическая проверка строк
    VALIDATED  = "validated"  # Проверка пройдена, ожидает подтверждения
    REJECTED   = "rejected"   # Не прошёл проверку — есть критические ошибки
    PROCESSING = "processing" # Выплаты отправляются в Совкомбанк
    COMPLETED  = "completed"  # Все выплаты выполнены
    PARTIAL    = "partial"    # Часть выплат выполнена, часть с ошибками
    FAILED     = "failed"     # Полный сбой при обработке


class RegistryItemStatus(str, Enum):
    """Статус одной строки реестра."""
    PENDING  = "pending"  # Ожидает валидации
    VALID    = "valid"    # Прошёл все 5 проверок — готов к выплате
    INVALID  = "invalid"  # Не прошёл проверку — ошибки в validation_errors
    PAID     = "paid"     # Выплата проведена успешно
    FAILED   = "failed"   # Ошибка при выплате


class FnsReceiptStatus(str, Enum):
    """Статус чека ФНС "Мой налог"."""
    CREATED   = "created"   # Чек выдан и действителен
    CANCELLED = "cancelled" # Чек аннулирован исполнителем — КРИТИЧНО, нужно уведомить бухгалтерию
    ERROR     = "error"     # Ошибка при выдаче или проверке чека


# =============================================================================
# ТАБЛИЦА ВЫПЛАТ
# =============================================================================

class Payment(Base):
    """
    Выплата исполнителю за выполненное задание.

    Каждая принятая задача порождает одну выплату.
    Выплаты проходят через Совкомбанк на карту любого банка РФ.
    После успешной выплаты регистрируется чек в ФНС.
    """
    __tablename__ = "payments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # -------------------------------------------------------------------------
    # СВЯЗИ
    # -------------------------------------------------------------------------
    task_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tasks.id"),
        nullable=False,
        unique=True,  # Одна задача = одна выплата
        comment="ID задания за которое выплачиваются деньги",
    )
    executor_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
        comment="ID самозанятого — получателя выплаты",
    )
    registry_item_id = Column(
        UUID(as_uuid=True),
        ForeignKey("payment_registry_items.id"),
        nullable=True,
        comment="ID строки реестра (если выплата через массовый реестр)",
    )

    # -------------------------------------------------------------------------
    # СУММЫ
    # -------------------------------------------------------------------------
    amount = Column(
        Numeric(10, 2),
        nullable=False,
        comment="Сумма выплаты исполнителю (чистыми, без налога)",
    )
    tax_amount = Column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Сумма налога 6% — компенсируется KARI исполнителю",
    )
    total_amount = Column(
        Numeric(10, 2),
        nullable=False,
        comment="Итоговая сумма перевода = amount + tax_amount",
    )

    # -------------------------------------------------------------------------
    # СТАТУС
    # -------------------------------------------------------------------------
    status = Column(
        SAEnum(PaymentStatus, name="payment_status"),
        nullable=False,
        default=PaymentStatus.PENDING,
        index=True,
        comment="Текущий статус выплаты",
    )
    error_message = Column(
        Text,
        nullable=True,
        comment="Сообщение об ошибке при статусе FAILED",
    )
    retry_count = Column(
        SmallInteger,
        default=0,
        nullable=False,
        comment="Количество попыток повторной отправки",
    )

    # -------------------------------------------------------------------------
    # РЕКВИЗИТЫ ПОЛУЧАТЕЛЯ (копируются на момент выплаты — карта может смениться)
    # -------------------------------------------------------------------------
    bank_card_masked = Column(
        String(19),
        nullable=True,
        comment="Маскированный номер карты: **** **** **** 1234",
    )
    bank_name = Column(
        String(100),
        nullable=True,
        comment="Название банка получателя",
    )
    bank_card_token = Column(
        Text,
        nullable=True,
        comment="Токен карты в Совкомбанке (для выполнения перевода)",
    )

    # -------------------------------------------------------------------------
    # ДАННЫЕ ОТ СОВКОМБАНКА
    # -------------------------------------------------------------------------
    sovcombank_transaction_id = Column(
        String(100),
        nullable=True,
        unique=True,
        comment="ID транзакции в системе Совкомбанка",
    )
    sovcombank_status = Column(
        String(50),
        nullable=True,
        comment="Статус транзакции от Совкомбанка (raw)",
    )
    sovcombank_response = Column(
        JSON,
        nullable=True,
        comment="Полный ответ Совкомбанка (для отладки и аудита)",
    )

    # -------------------------------------------------------------------------
    # ЧЕК ФНС
    # -------------------------------------------------------------------------
    fns_receipt_id = Column(
        UUID(as_uuid=True),
        ForeignKey("fns_receipts.id"),
        nullable=True,
        comment="ID чека ФНС, выданного после успешной выплаты",
    )

    # -------------------------------------------------------------------------
    # ХРОНОЛОГИЯ
    # -------------------------------------------------------------------------
    created_at     = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    processing_at  = Column(DateTime(timezone=True), nullable=True, comment="Когда отправлено в Совкомбанк")
    completed_at   = Column(DateTime(timezone=True), nullable=True, comment="Когда деньги зачислены")
    updated_at     = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    # -------------------------------------------------------------------------
    # СВЯЗИ
    # -------------------------------------------------------------------------
    fns_receipt = relationship("FnsReceipt", foreign_keys=[fns_receipt_id])

    __table_args__ = (
        Index("ix_payments_executor_status", "executor_id", "status"),
        Index("ix_payments_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Payment id={self.id} executor={self.executor_id} amount={self.total_amount} [{self.status}]>"


# =============================================================================
# ТАБЛИЦА РЕЕСТРОВ МАССОВЫХ ВЫПЛАТ (ТЗ 3.12)
# =============================================================================

class PaymentRegistry(Base):
    """
    Реестр массовой выплаты — загружается Excel-файлом.

    Процесс:
      1. Бухгалтер загружает Excel (до 1000 строк)
      2. Система автоматически проверяет каждую строку (5 проверок)
      3. При успехе — директор подтверждает, запускается пакетная выплата
      4. Система формирует XML для 1С
    """
    __tablename__ = "payment_registries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # -------------------------------------------------------------------------
    # ИДЕНТИФИКАЦИЯ
    # -------------------------------------------------------------------------
    name = Column(
        String(200),
        nullable=False,
        comment="Название реестра (например: 'Выплаты ноябрь 2025 Юг')",
    )
    number = Column(
        String(30),
        unique=True,
        nullable=True,
        comment="Порядковый номер: РЕЕ-YYYY-NNNN",
    )

    # -------------------------------------------------------------------------
    # КТО И ГДЕ
    # -------------------------------------------------------------------------
    created_by_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        comment="Кто загрузил реестр (бухгалтер или директор региона)",
    )
    region_id = Column(
        UUID(as_uuid=True),
        nullable=True,
        comment="Регион (для контроля бюджетного лимита)",
    )
    approved_by_id = Column(
        UUID(as_uuid=True),
        nullable=True,
        comment="Кто подтвердил реестр к оплате",
    )

    # -------------------------------------------------------------------------
    # ФАЙЛ
    # -------------------------------------------------------------------------
    file_path = Column(
        String(500),
        nullable=False,
        comment="Путь к Excel-файлу в MinIO",
    )
    file_name_original = Column(
        String(255),
        nullable=False,
        comment="Оригинальное имя загруженного файла",
    )
    file_size_bytes = Column(
        Integer,
        nullable=True,
        comment="Размер файла в байтах",
    )

    # -------------------------------------------------------------------------
    # СТАТУС И РЕЗУЛЬТАТЫ ВАЛИДАЦИИ
    # -------------------------------------------------------------------------
    status = Column(
        SAEnum(RegistryStatus, name="registry_status"),
        nullable=False,
        default=RegistryStatus.UPLOADED,
        index=True,
    )

    # Статистика строк
    total_rows = Column(Integer, default=0, comment="Всего строк в реестре")
    valid_rows = Column(Integer, default=0, comment="Строк прошли все 5 проверок")
    invalid_rows = Column(Integer, default=0, comment="Строк с ошибками")
    paid_rows = Column(Integer, default=0, comment="Строк успешно оплачены")
    failed_rows = Column(Integer, default=0, comment="Строк с ошибкой оплаты")

    # Суммы
    total_amount = Column(
        Numeric(14, 2),
        default=Decimal("0.00"),
        comment="Общая сумма выплат по реестру",
    )
    paid_amount = Column(
        Numeric(14, 2),
        default=Decimal("0.00"),
        comment="Уже выплаченная сумма",
    )

    # Общие ошибки реестра (не конкретных строк)
    validation_summary = Column(
        JSON,
        nullable=True,
        comment="Сводка по валидации: {'errors': [...], 'warnings': [...]}",
    )

    # -------------------------------------------------------------------------
    # XML ДЛЯ 1С
    # -------------------------------------------------------------------------
    xml_export_path = Column(
        String(500),
        nullable=True,
        comment="Путь к сформированному XML для выгрузки в 1С",
    )
    xml_exported_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Когда был сформирован XML",
    )

    # -------------------------------------------------------------------------
    # ХРОНОЛОГИЯ
    # -------------------------------------------------------------------------
    created_at     = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    validated_at   = Column(DateTime(timezone=True), nullable=True, comment="Когда завершена валидация")
    approved_at    = Column(DateTime(timezone=True), nullable=True, comment="Когда подтверждён к оплате")
    processing_at  = Column(DateTime(timezone=True), nullable=True, comment="Когда запущена пакетная выплата")
    completed_at   = Column(DateTime(timezone=True), nullable=True, comment="Когда все выплаты завершены")

    # -------------------------------------------------------------------------
    # СВЯЗИ
    # -------------------------------------------------------------------------
    items = relationship(
        "PaymentRegistryItem",
        back_populates="registry",
        cascade="all, delete-orphan",
        order_by="PaymentRegistryItem.row_number",
    )

    def __repr__(self) -> str:
        return f"<PaymentRegistry '{self.name}' rows={self.total_rows} [{self.status}]>"


# =============================================================================
# ТАБЛИЦА СТРОК РЕЕСТРА
# =============================================================================

class PaymentRegistryItem(Base):
    """
    Одна строка реестра массовых выплат.

    Каждая строка проходит 5 автоматических проверок (ТЗ 3.12):
      1. Статус ФНС — исполнитель является самозанятым?
      2. Лимит дохода — не превышен ли порог 2 400 000 руб/год?
      3. Дубли — нет ли уже выплаты этому исполнителю за эту дату?
      4. Сумма — корректна (> 0, не превышает разовый лимит)?
      5. Бюджет — есть ли остаток бюджета в регионе/подразделении?
    """
    __tablename__ = "payment_registry_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # -------------------------------------------------------------------------
    # СВЯЗЬ С РЕЕСТРОМ
    # -------------------------------------------------------------------------
    registry_id = Column(
        UUID(as_uuid=True),
        ForeignKey("payment_registries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    row_number = Column(
        Integer,
        nullable=False,
        comment="Номер строки в Excel (для показа ошибок пользователю)",
    )

    # -------------------------------------------------------------------------
    # ДАННЫЕ ИЗ EXCEL (то что загрузил пользователь)
    # -------------------------------------------------------------------------
    executor_inn = Column(
        String(12),
        nullable=False,
        comment="ИНН исполнителя из Excel",
    )
    executor_name = Column(
        String(255),
        nullable=True,
        comment="ФИО исполнителя из Excel (для сверки)",
    )
    service_description = Column(
        String(500),
        nullable=False,
        comment="Описание услуги — попадёт в чек ФНС",
    )
    amount = Column(
        Numeric(10, 2),
        nullable=False,
        comment="Сумма выплаты из Excel",
    )
    work_date = Column(
        Date,
        nullable=False,
        comment="Дата выполнения работ (для чека ФНС)",
    )

    # -------------------------------------------------------------------------
    # РЕЗУЛЬТАТ СОПОСТАВЛЕНИЯ (ИНН → пользователь в системе)
    # -------------------------------------------------------------------------
    executor_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
        comment="ID исполнителя в системе (найден по ИНН). NULL если не найден.",
    )

    # -------------------------------------------------------------------------
    # СТАТУС И ВАЛИДАЦИЯ
    # -------------------------------------------------------------------------
    status = Column(
        SAEnum(RegistryItemStatus, name="registry_item_status"),
        nullable=False,
        default=RegistryItemStatus.PENDING,
        index=True,
    )

    # Результаты 5 проверок (True = прошёл, False = не прошёл, None = не проверялось)
    check_fns_status   = Column(Boolean, nullable=True, comment="Проверка 1: статус ФНС активен")
    check_income_limit = Column(Boolean, nullable=True, comment="Проверка 2: лимит дохода не превышен")
    check_duplicate    = Column(Boolean, nullable=True, comment="Проверка 3: нет дубля")
    check_amount       = Column(Boolean, nullable=True, comment="Проверка 4: сумма корректна")
    check_budget       = Column(Boolean, nullable=True, comment="Проверка 5: бюджет есть")

    # Детальные ошибки для показа пользователю
    validation_errors = Column(
        JSON,
        nullable=True,
        comment="Список ошибок: [{'code': 'INCOME_LIMIT', 'message': 'Превышен лимит...'}]",
    )

    # -------------------------------------------------------------------------
    # РЕЗУЛЬТАТ ВЫПЛАТЫ
    # -------------------------------------------------------------------------
    payment_id = Column(
        UUID(as_uuid=True),
        ForeignKey("payments.id"),
        nullable=True,
        comment="ID созданной выплаты (после одобрения реестра)",
    )
    error_message = Column(
        Text,
        nullable=True,
        comment="Ошибка при проведении выплаты",
    )

    # -------------------------------------------------------------------------
    # СВЯЗИ
    # -------------------------------------------------------------------------
    registry = relationship("PaymentRegistry", back_populates="items")

    __table_args__ = (
        # Быстрый поиск по ИНН в рамках одного реестра
        Index("ix_registry_items_inn", "registry_id", "executor_inn"),
    )

    @property
    def all_checks_passed(self) -> bool:
        """Прошли ли все 5 проверок."""
        return all([
            self.check_fns_status,
            self.check_income_limit,
            self.check_duplicate,
            self.check_amount,
            self.check_budget,
        ])

    def __repr__(self) -> str:
        return f"<RegistryItem row={self.row_number} inn={self.executor_inn} amount={self.amount} [{self.status}]>"


# =============================================================================
# ТАБЛИЦА ЧЕКОВ ФНС (ТЗ 3.11 — Контроль аннулирования)
# =============================================================================

class FnsReceipt(Base):
    """
    Чек ФНС "Мой налог", выданный исполнителю при регистрации дохода.

    Ежедневно в 07:00 система проверяет все чеки за последние 60 дней.
    Если чек аннулирован — немедленно:
      1. Блокируется исполнитель
      2. Уведомляется директор магазина
      3. Уведомляется бухгалтерия (в течение 1 часа)
    """
    __tablename__ = "fns_receipts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # -------------------------------------------------------------------------
    # СВЯЗИ
    # -------------------------------------------------------------------------
    payment_id = Column(
        UUID(as_uuid=True),
        ForeignKey("payments.id"),
        nullable=False,
        unique=True,
        comment="ID выплаты к которой относится чек",
    )
    executor_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
        comment="ID исполнителя (самозанятого)",
    )

    # -------------------------------------------------------------------------
    # ДАННЫЕ ЧЕКА ОТ ФНС
    # -------------------------------------------------------------------------
    fns_receipt_uuid = Column(
        String(100),
        unique=True,
        nullable=True,
        comment="UUID чека в системе ФНС 'Мой налог'",
    )
    fns_receipt_link = Column(
        String(500),
        nullable=True,
        comment="Ссылка на чек (можно отправить покупателю)",
    )
    fns_request_id = Column(
        String(100),
        nullable=True,
        comment="ID запроса в ФНС (для отслеживания)",
    )

    # -------------------------------------------------------------------------
    # СОДЕРЖАНИЕ ЧЕКА
    # -------------------------------------------------------------------------
    amount = Column(
        Numeric(10, 2),
        nullable=False,
        comment="Сумма дохода в чеке",
    )
    service_name = Column(
        String(500),
        nullable=False,
        comment="Наименование услуги (из описания задания)",
    )
    client_inn = Column(
        String(12),
        nullable=False,
        comment="ИНН заказчика — KARI",
    )
    client_name = Column(
        String(255),
        nullable=True,
        comment="Наименование заказчика — KARI",
    )
    service_date = Column(
        Date,
        nullable=False,
        comment="Дата оказания услуги (дата выполнения задания)",
    )

    # -------------------------------------------------------------------------
    # СТАТУС И АННУЛИРОВАНИЕ
    # -------------------------------------------------------------------------
    status = Column(
        SAEnum(FnsReceiptStatus, name="fns_receipt_status"),
        nullable=False,
        default=FnsReceiptStatus.CREATED,
        index=True,
        comment="Текущий статус чека",
    )
    cancelled_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Дата и время аннулирования чека исполнителем",
    )
    cancel_reason = Column(
        Text,
        nullable=True,
        comment="Причина аннулирования (из ответа ФНС)",
    )

    # -------------------------------------------------------------------------
    # КОНТРОЛЬ ПРОВЕРОК (ТЗ 3.11 — ежедневная проверка в 07:00)
    # -------------------------------------------------------------------------
    last_check_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Когда последний раз проверяли статус в ФНС",
    )
    check_count = Column(
        Integer,
        default=0,
        nullable=False,
        comment="Сколько раз проверяли статус",
    )

    # -------------------------------------------------------------------------
    # УВЕДОМЛЕНИЯ ПРИ АННУЛИРОВАНИИ
    # -------------------------------------------------------------------------
    director_notified_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Когда уведомлён директор магазина об аннулировании",
    )
    accounting_notified_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Когда уведомлена бухгалтерия (требование: в течение 1 часа)",
    )
    resolved_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Когда ситуация разрешена (новый чек или возврат средств)",
    )
    resolution_note = Column(
        Text,
        nullable=True,
        comment="Комментарий по итогу разрешения ситуации",
    )

    # -------------------------------------------------------------------------
    # ХРОНОЛОГИЯ
    # -------------------------------------------------------------------------
    issued_at  = Column(DateTime(timezone=True), nullable=True, comment="Дата выдачи чека в ФНС")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    __table_args__ = (
        # Быстрый поиск действующих чеков для ежедневной проверки
        Index("ix_fns_receipts_status_check", "status", "last_check_at"),
        # Чеки конкретного исполнителя
        Index("ix_fns_receipts_executor", "executor_id", "status"),
    )

    @property
    def is_cancelled(self) -> bool:
        return self.status == FnsReceiptStatus.CANCELLED

    @property
    def accounting_notified_in_time(self) -> bool | None:
        """Успела ли система уведомить бухгалтерию в течение 1 часа после аннулирования."""
        if not self.cancelled_at or not self.accounting_notified_at:
            return None
        delta = self.accounting_notified_at - self.cancelled_at
        return delta.total_seconds() <= 3600  # 1 час = 3600 секунд

    def __repr__(self) -> str:
        return f"<FnsReceipt uuid={self.fns_receipt_uuid} amount={self.amount} [{self.status}]>"
