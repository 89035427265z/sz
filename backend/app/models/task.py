# =============================================================================
# KARI.Самозанятые — Модель заданий
# Файл: app/models/task.py
# =============================================================================
# Описывает три таблицы:
#   1. Task         — задания на бирже (создаёт директор магазина)
#   2. TaskPhoto    — фотоотчёты к заданиям (загружает исполнитель при сдаче)
#   3. TaskTemplate — шаблоны заданий (чтобы директор не заполнял каждый раз)
# =============================================================================

import uuid
from decimal import Decimal
from enum import Enum

from sqlalchemy import (
    Column, String, Boolean, DateTime, Date, Time,
    Integer, Numeric, Text, Float, ForeignKey, Index, SmallInteger,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


# =============================================================================
# ПЕРЕЧИСЛЕНИЯ
# =============================================================================

class TaskStatus(str, Enum):
    """Жизненный цикл задания — от создания до оплаты."""
    DRAFT       = "draft"       # Черновик — создан, но не опубликован
    PUBLISHED   = "published"   # Опубликован на бирже — исполнители видят
    TAKEN       = "taken"       # Взят исполнителем — другим недоступен
    IN_PROGRESS = "in_progress" # Исполнитель начал работу (отметил старт)
    SUBMITTED   = "submitted"   # Сдан — ожидает проверки директора магазина
    ACCEPTED    = "accepted"    # Принят директором — запущена оплата
    REJECTED    = "rejected"    # Отклонён директором — причина обязательна
    COMPLETED   = "completed"   # Завершён — акт подписан, деньги выплачены
    CANCELLED   = "cancelled"   # Отменён (до взятия в работу)
    EXPIRED     = "expired"     # Истёк срок — никто не взял


class TaskCategory(str, Enum):
    """Категории работ для самозанятых в KARI."""
    CLEANING        = "cleaning"        # Уборка торгового зала / подсобки
    MERCHANDISING   = "merchandising"   # Выкладка товара, оформление витрин
    INVENTORY       = "inventory"       # Инвентаризация (пересчёт товара)
    UNLOADING       = "unloading"       # Разгрузка товара
    PROMOTION       = "promotion"       # Промо-акция, консультирование покупателей
    MARKING         = "marking"         # Маркировка и ценники
    OTHER           = "other"           # Прочие работы


class PhotoVerificationStatus(str, Enum):
    """Статус проверки геолокации фотографии (ТЗ 3.10)."""
    PENDING   = "pending"   # Ещё не проверено
    VERIFIED  = "verified"  # Фото сделано в нужном месте (в радиусе 300м от магазина)
    FAILED    = "failed"    # Фото не в нужном месте — требует ручной проверки


# =============================================================================
# ТАБЛИЦА ЗАДАНИЙ
# =============================================================================

class Task(Base):
    """
    Задание на бирже заданий KARI.Самозанятые.

    Жизненный цикл:
    DRAFT → PUBLISHED → TAKEN → IN_PROGRESS → SUBMITTED → ACCEPTED → COMPLETED
                                                         ↘ REJECTED (возвращается к исполнителю)
    """
    __tablename__ = "tasks"

    # -------------------------------------------------------------------------
    # ИДЕНТИФИКАЦИЯ
    # -------------------------------------------------------------------------
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Порядковый номер для отображения (ТЗ-2025-001, ТЗ-2025-002 ...)
    number = Column(
        String(30),
        unique=True,
        nullable=True,
        comment="Человекочитаемый номер задания: ТЗ-YYYY-NNNNNN",
    )

    # -------------------------------------------------------------------------
    # СОДЕРЖАНИЕ ЗАДАНИЯ
    # -------------------------------------------------------------------------
    title = Column(
        String(200),
        nullable=False,
        comment="Краткое название задания (отображается в списке биржи)",
    )
    description = Column(
        Text,
        nullable=False,
        comment="Подробное описание — что нужно сделать, особые требования",
    )
    category = Column(
        SAEnum(TaskCategory, name="task_category"),
        nullable=False,
        comment="Категория работ",
    )
    status = Column(
        SAEnum(TaskStatus, name="task_status"),
        nullable=False,
        default=TaskStatus.DRAFT,
        index=True,
        comment="Текущий статус задания",
    )

    # -------------------------------------------------------------------------
    # КТО И ГДЕ
    # -------------------------------------------------------------------------
    store_id = Column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="ID магазина, где выполняется задание",
    )
    store_address = Column(
        String(500),
        nullable=False,
        comment="Адрес магазина (копируется при создании — не меняется)",
    )
    store_latitude = Column(
        Float,
        nullable=True,
        comment="Широта магазина — для проверки геолокации фото",
    )
    store_longitude = Column(
        Float,
        nullable=True,
        comment="Долгота магазина — для проверки геолокации фото",
    )

    # Кто создал задание
    created_by_id = Column(
        UUID(as_uuid=True),
        nullable=False,
        comment="ID директора магазина, создавшего задание",
    )

    # Кто взял задание (заполняется когда исполнитель берёт задание)
    executor_id = Column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="ID исполнителя (самозанятого). NULL пока никто не взял.",
    )

    # -------------------------------------------------------------------------
    # СТОИМОСТЬ И ОПЛАТА
    # -------------------------------------------------------------------------
    price = Column(
        Numeric(10, 2),
        nullable=False,
        comment="Стоимость задания в рублях (сумма выплаты исполнителю)",
    )
    price_includes_tax = Column(
        Boolean,
        default=True,
        nullable=False,
        comment="True = в цену включён налог 6% (KARI компенсирует исполнителю)",
    )

    # -------------------------------------------------------------------------
    # СРОКИ ВЫПОЛНЕНИЯ
    # -------------------------------------------------------------------------
    scheduled_date = Column(
        Date,
        nullable=False,
        comment="Дата выполнения задания",
    )
    scheduled_time_start = Column(
        Time,
        nullable=True,
        comment="Время начала работы",
    )
    scheduled_time_end = Column(
        Time,
        nullable=True,
        comment="Плановое время окончания работы",
    )
    deadline_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Жёсткий дедлайн — после него задание переходит в EXPIRED",
    )

    # Фактическое время (заполняет исполнитель)
    actual_start_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Фактическое начало (исполнитель нажал 'Начать')",
    )
    actual_end_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Фактическое завершение (исполнитель нажал 'Сдать')",
    )

    # -------------------------------------------------------------------------
    # ФОТООТЧЁТ (ТЗ 3.10)
    # -------------------------------------------------------------------------
    required_photo_count = Column(
        SmallInteger,
        default=1,
        nullable=False,
        comment="Сколько фото нужно приложить при сдаче (от 1 до 3)",
    )
    photo_instructions = Column(
        Text,
        nullable=True,
        comment="Инструкция что именно фотографировать (показывается исполнителю)",
    )
    photos_verified = Column(
        Boolean,
        default=False,
        nullable=False,
        comment="Все фото прошли проверку геолокации (True = кнопка приёмки активна)",
    )

    # -------------------------------------------------------------------------
    # ПРИЁМКА И ОТКЛОНЕНИЕ
    # -------------------------------------------------------------------------
    accepted_by_id = Column(
        UUID(as_uuid=True),
        nullable=True,
        comment="ID директора магазина, принявшего работу",
    )
    rejection_reason = Column(
        Text,
        nullable=True,
        comment="Причина отклонения (обязательна при статусе REJECTED)",
    )
    rejection_count = Column(
        SmallInteger,
        default=0,
        nullable=False,
        comment="Сколько раз задание было отклонено (история)",
    )

    # -------------------------------------------------------------------------
    # ШАБЛОН (если задание создано из шаблона)
    # -------------------------------------------------------------------------
    template_id = Column(
        UUID(as_uuid=True),
        nullable=True,
        comment="ID шаблона из которого создано задание (если применялся)",
    )

    # -------------------------------------------------------------------------
    # ХРОНОЛОГИЯ (ключевые моменты)
    # -------------------------------------------------------------------------
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    published_at = Column(DateTime(timezone=True), nullable=True, comment="Когда опубликовано на бирже")
    taken_at = Column(DateTime(timezone=True), nullable=True, comment="Когда взято исполнителем")
    submitted_at = Column(DateTime(timezone=True), nullable=True, comment="Когда сдано на проверку")
    accepted_at = Column(DateTime(timezone=True), nullable=True, comment="Когда принято директором")
    completed_at = Column(DateTime(timezone=True), nullable=True, comment="Когда полностью завершено (с оплатой)")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    # -------------------------------------------------------------------------
    # СВЯЗИ С ДРУГИМИ ТАБЛИЦАМИ
    # -------------------------------------------------------------------------
    photos = relationship(
        "TaskPhoto",
        back_populates="task",
        cascade="all, delete-orphan",
        order_by="TaskPhoto.sequence_number",
    )

    # -------------------------------------------------------------------------
    # ИНДЕКСЫ
    # -------------------------------------------------------------------------
    __table_args__ = (
        # Биржа заданий — показываем опубликованные задания по дате
        Index("ix_tasks_status_scheduled", "status", "scheduled_date"),
        # Задания конкретного магазина
        Index("ix_tasks_store_status", "store_id", "status"),
        # Задания конкретного исполнителя
        Index("ix_tasks_executor_status", "executor_id", "status"),
    )

    @property
    def duration_minutes(self) -> int | None:
        """Фактическая продолжительность работы в минутах."""
        if self.actual_start_at and self.actual_end_at:
            delta = self.actual_end_at - self.actual_start_at
            return int(delta.total_seconds() / 60)
        return None

    @property
    def price_tax_amount(self) -> Decimal:
        """Сумма налога 6% которую компенсирует KARI."""
        return (self.price * Decimal("0.06")).quantize(Decimal("0.01"))

    def __repr__(self) -> str:
        return f"<Task {self.number or self.id} [{self.status}] '{self.title}'>"


# =============================================================================
# ТАБЛИЦА ФОТООТЧЁТОВ
# =============================================================================

class TaskPhoto(Base):
    """
    Фотографии, прикреплённые к заданию при его сдаче (ТЗ 3.10).

    Требования:
    - Минимальное разрешение: 1280×720 пикселей
    - Максимальный размер файла: 10 МБ
    - Геометка обязательна (из EXIF или GPS телефона)
    - Фото должно быть сделано в радиусе 300 м от магазина
    - Срок хранения: 3 года (требование ТЗ)
    """
    __tablename__ = "task_photos"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # -------------------------------------------------------------------------
    # СВЯЗЬ С ЗАДАНИЕМ
    # -------------------------------------------------------------------------
    task_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="ID задания к которому относится фото",
    )
    executor_id = Column(
        UUID(as_uuid=True),
        nullable=False,
        comment="ID исполнителя, загрузившего фото",
    )
    sequence_number = Column(
        SmallInteger,
        nullable=False,
        default=1,
        comment="Порядковый номер фото (1, 2, 3)",
    )

    # -------------------------------------------------------------------------
    # ФАЙЛ В MinIO
    # -------------------------------------------------------------------------
    file_path = Column(
        String(500),
        nullable=False,
        comment="Путь к файлу в MinIO: kari-photos/2025/01/task_id/1.jpg",
    )
    file_size_bytes = Column(
        Integer,
        nullable=True,
        comment="Размер файла в байтах (макс 10 МБ = 10 485 760)",
    )
    image_width = Column(Integer, nullable=True, comment="Ширина в пикселях")
    image_height = Column(Integer, nullable=True, comment="Высота в пикселях")

    # -------------------------------------------------------------------------
    # ГЕОЛОКАЦИЯ (из EXIF или GPS телефона)
    # -------------------------------------------------------------------------
    photo_latitude = Column(
        Float,
        nullable=True,
        comment="Широта места съёмки (из EXIF фото)",
    )
    photo_longitude = Column(
        Float,
        nullable=True,
        comment="Долгота места съёмки (из EXIF фото)",
    )
    distance_from_store_meters = Column(
        Float,
        nullable=True,
        comment="Расстояние от магазина в метрах (считается автоматически)",
    )
    geo_verification = Column(
        SAEnum(PhotoVerificationStatus, name="photo_geo_status"),
        nullable=False,
        default=PhotoVerificationStatus.PENDING,
        comment="Результат проверки геолокации (в радиусе 300м от магазина?)",
    )

    # -------------------------------------------------------------------------
    # ВРЕМЯ СЪЁМКИ
    # -------------------------------------------------------------------------
    taken_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Время съёмки по данным EXIF",
    )
    uploaded_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Время загрузки на сервер",
    )

    # -------------------------------------------------------------------------
    # РУЧНАЯ ПРОВЕРКА (если геолокация не прошла автопроверку)
    # -------------------------------------------------------------------------
    manually_verified = Column(
        Boolean,
        default=False,
        nullable=False,
        comment="Директор вручную подтвердил фото (при failed геолокации)",
    )
    manually_verified_by_id = Column(
        UUID(as_uuid=True),
        nullable=True,
        comment="Кто вручную подтвердил",
    )

    # -------------------------------------------------------------------------
    # СВЯЗИ
    # -------------------------------------------------------------------------
    task = relationship("Task", back_populates="photos")

    @property
    def file_size_mb(self) -> float | None:
        """Размер файла в мегабайтах."""
        if self.file_size_bytes:
            return round(self.file_size_bytes / 1_048_576, 2)
        return None

    @property
    def resolution_ok(self) -> bool | None:
        """Соответствует ли разрешение минимальному (1280×720)."""
        if self.image_width and self.image_height:
            return self.image_width >= 1280 and self.image_height >= 720
        return None

    def __repr__(self) -> str:
        return f"<TaskPhoto task={self.task_id} #{self.sequence_number} geo={self.geo_verification}>"


# =============================================================================
# ТАБЛИЦА ШАБЛОНОВ ЗАДАНИЙ
# =============================================================================

class TaskTemplate(Base):
    """
    Шаблоны заданий для директоров магазинов.

    Директор магазина один раз создаёт шаблон "Уборка торгового зала",
    и дальше создаёт задания в один клик — все поля заполнены автоматически.
    """
    __tablename__ = "task_templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # -------------------------------------------------------------------------
    # КОМУ ПРИНАДЛЕЖИТ ШАБЛОН
    # -------------------------------------------------------------------------
    store_id = Column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="ID магазина (шаблон только для этого магазина). NULL = для всего региона.",
    )
    region_id = Column(
        UUID(as_uuid=True),
        nullable=True,
        comment="ID региона (шаблон для всех магазинов региона)",
    )
    created_by_id = Column(
        UUID(as_uuid=True),
        nullable=False,
        comment="Кто создал шаблон",
    )

    # -------------------------------------------------------------------------
    # СОДЕРЖАНИЕ ШАБЛОНА
    # -------------------------------------------------------------------------
    title = Column(String(200), nullable=False, comment="Название шаблона")
    description = Column(Text, nullable=False, comment="Описание задания")
    category = Column(
        SAEnum(TaskCategory, name="template_category"),
        nullable=False,
    )
    default_price = Column(
        Numeric(10, 2),
        nullable=False,
        comment="Стандартная стоимость (можно изменить при создании задания)",
    )
    required_photo_count = Column(
        SmallInteger,
        default=1,
        nullable=False,
        comment="Сколько фото требовать при сдаче",
    )
    photo_instructions = Column(
        Text,
        nullable=True,
        comment="Инструкция что фотографировать",
    )

    # -------------------------------------------------------------------------
    # УПРАВЛЕНИЕ
    # -------------------------------------------------------------------------
    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
        comment="False = шаблон скрыт, не предлагается при создании заданий",
    )
    usage_count = Column(
        Integer,
        default=0,
        nullable=False,
        comment="Сколько раз использован (для статистики)",
    )

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    def __repr__(self) -> str:
        return f"<TaskTemplate '{self.title}' store={self.store_id}>"
