"""Начальная миграция — создание всех таблиц KARI.Самозанятые v3.0

Revision ID: 20260303_0001
Revises: —
Create Date: 2026-03-03

Создаёт все таблицы платформы:
  1.  ENUM-типы PostgreSQL (роли, статусы)
  2.  users           — пользователи (директора + самозанятые)
  3.  sms_codes       — одноразовые SMS-коды для авторизации и подписи
  4.  task_templates  — шаблоны заданий
  5.  tasks           — задания биржи
  6.  task_photos     — фотоотчёты (ТЗ 3.10)
  7.  payment_registries      — реестры массовых выплат (ТЗ 3.12)
  8.  payment_registry_items  — строки реестра
  9.  payments        — выплаты за задания
  10. fns_receipts    — чеки ФНС (ТЗ 3.11)
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op


# Идентификатор ревизии (Alembic использует чтобы отслеживать состояние БД)
revision: str = "20260303_0001"
down_revision: Union[str, None] = None   # Первая миграция — родителя нет
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# =============================================================================
# UPGRADE — применяем миграцию (создаём таблицы)
# =============================================================================

def upgrade() -> None:

    # ─────────────────────────────────────────────────────────────────────────
    # 1. ENUM ТИПЫ PostgreSQL
    # Создаём до таблиц — таблицы на них ссылаются
    # ─────────────────────────────────────────────────────────────────────────

    # Роль пользователя
    op.execute("""
        CREATE TYPE user_role AS ENUM (
            'regional_director',
            'division_director',
            'store_director',
            'executor'
        )
    """)

    # Статус пользователя
    op.execute("""
        CREATE TYPE user_status AS ENUM (
            'active',
            'blocked',
            'archived'
        )
    """)

    # Статус самозанятого в ФНС
    op.execute("""
        CREATE TYPE fns_status AS ENUM (
            'active',
            'inactive',
            'blocked'
        )
    """)

    # Статус задания
    op.execute("""
        CREATE TYPE task_status AS ENUM (
            'draft',
            'published',
            'taken',
            'in_progress',
            'submitted',
            'accepted',
            'rejected',
            'completed',
            'cancelled',
            'expired'
        )
    """)

    # Категория задания
    op.execute("""
        CREATE TYPE task_category AS ENUM (
            'cleaning',
            'merchandising',
            'inventory',
            'unloading',
            'promotion',
            'marking',
            'other'
        )
    """)

    # Статус геопроверки фото
    op.execute("""
        CREATE TYPE photo_geo_status AS ENUM (
            'pending',
            'verified',
            'failed'
        )
    """)

    # Статус выплаты
    op.execute("""
        CREATE TYPE payment_status AS ENUM (
            'pending',
            'processing',
            'completed',
            'failed',
            'cancelled'
        )
    """)

    # Статус реестра выплат
    op.execute("""
        CREATE TYPE registry_status AS ENUM (
            'uploaded',
            'validating',
            'validated',
            'rejected',
            'processing',
            'completed',
            'partial',
            'failed'
        )
    """)

    # Статус строки реестра
    op.execute("""
        CREATE TYPE registry_item_status AS ENUM (
            'pending',
            'valid',
            'invalid',
            'paid',
            'failed'
        )
    """)

    # Статус чека ФНС
    op.execute("""
        CREATE TYPE fns_receipt_status AS ENUM (
            'created',
            'cancelled',
            'error'
        )
    """)

    # Статус категории для шаблонов (отдельный тип чтобы не конфликтовать)
    op.execute("""
        CREATE TYPE template_category AS ENUM (
            'cleaning',
            'merchandising',
            'inventory',
            'unloading',
            'promotion',
            'marking',
            'other'
        )
    """)

    # ─────────────────────────────────────────────────────────────────────────
    # 2. ТАБЛИЦА ПОЛЬЗОВАТЕЛЕЙ
    # Все пользователи системы: директора KARI + самозанятые исполнители
    # ─────────────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id",         postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("phone",      sa.String(20),   nullable=False, unique=True),
        sa.Column("full_name",  sa.String(255),  nullable=False),
        sa.Column("role",       sa.Enum("regional_director","division_director","store_director","executor",
                                        name="user_role", create_type=False), nullable=False),
        sa.Column("status",     sa.Enum("active","blocked","archived",
                                        name="user_status", create_type=False), nullable=False,
                  server_default="active"),

        # Блокировка
        sa.Column("blocked_reason",    sa.Text,  nullable=True),
        sa.Column("blocked_at",        sa.DateTime(timezone=True), nullable=True),
        sa.Column("blocked_by_user_id",postgresql.UUID(as_uuid=True), nullable=True),

        # Привязка к структуре KARI (только для директоров)
        sa.Column("region_id",   postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("division_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("store_id",    postgresql.UUID(as_uuid=True), nullable=True),

        # Временные метки
        sa.Column("created_at",    sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at",    sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),

        # ФНС (только для самозанятых)
        sa.Column("inn",                      sa.String(12),   nullable=True, unique=True),
        sa.Column("fns_status",               sa.Enum("active","inactive","blocked",
                                                       name="fns_status", create_type=False), nullable=True),
        sa.Column("fns_registration_date",    sa.Date,         nullable=True),
        sa.Column("fns_token_encrypted",      sa.Text,         nullable=True),
        sa.Column("fns_last_check_at",        sa.DateTime(timezone=True), nullable=True),

        # Контроль доходов
        sa.Column("income_from_kari_year",  sa.Numeric(12, 2), nullable=True, server_default="0.00"),
        sa.Column("income_total_year",      sa.Numeric(12, 2), nullable=True, server_default="0.00"),
        sa.Column("income_tracking_year",   sa.Integer,        nullable=True),

        # Банковские реквизиты
        sa.Column("bank_card_masked",  sa.String(19), nullable=True),
        sa.Column("bank_name",         sa.String(100),nullable=True),
        sa.Column("bank_card_token",   sa.Text,       nullable=True),

        # Push-уведомления
        sa.Column("fcm_token", sa.Text, nullable=True),
    )

    # Индексы для быстрого поиска
    op.create_index("ix_users_phone",          "users", ["phone"],       unique=True)
    op.create_index("ix_users_inn",            "users", ["inn"],         unique=True)
    op.create_index("ix_users_role_fns_status","users", ["role", "fns_status"])
    op.create_index("ix_users_store_id",       "users", ["store_id"])
    op.create_index("ix_users_region_id",      "users", ["region_id"])

    # ─────────────────────────────────────────────────────────────────────────
    # 3. ТАБЛИЦА SMS-КОДОВ
    # ─────────────────────────────────────────────────────────────────────────
    op.create_table(
        "sms_codes",
        sa.Column("id",         postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("phone",      sa.String(20), nullable=False),
        sa.Column("code",       sa.String(6),  nullable=False),
        sa.Column("purpose",    sa.String(20), nullable=False, server_default="auth"),
        sa.Column("context_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("attempts",   sa.Integer,  nullable=False, server_default="0"),
        sa.Column("is_used",    sa.Boolean,  nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_sms_codes_phone_purpose", "sms_codes", ["phone", "purpose", "is_used"])

    # ─────────────────────────────────────────────────────────────────────────
    # 4. ШАБЛОНЫ ЗАДАНИЙ
    # ─────────────────────────────────────────────────────────────────────────
    op.create_table(
        "task_templates",
        sa.Column("id",            postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("store_id",      postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("region_id",     postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title",         sa.String(200), nullable=False),
        sa.Column("description",   sa.Text,        nullable=False),
        sa.Column("category",      sa.Enum("cleaning","merchandising","inventory",
                                           "unloading","promotion","marking","other",
                                           name="template_category", create_type=False), nullable=False),
        sa.Column("default_price",         sa.Numeric(10, 2), nullable=False),
        sa.Column("required_photo_count",  sa.SmallInteger,   nullable=False, server_default="1"),
        sa.Column("photo_instructions",    sa.Text,           nullable=True),
        sa.Column("is_active",     sa.Boolean, nullable=False, server_default="true"),
        sa.Column("usage_count",   sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at",    sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at",    sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_task_templates_store_id", "task_templates", ["store_id"])

    # ─────────────────────────────────────────────────────────────────────────
    # 5. ЗАДАНИЯ
    # ─────────────────────────────────────────────────────────────────────────
    op.create_table(
        "tasks",
        sa.Column("id",     postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("number", sa.String(30), nullable=True, unique=True),
        sa.Column("title",       sa.String(200), nullable=False),
        sa.Column("description", sa.Text,        nullable=False),
        sa.Column("category",    sa.Enum("cleaning","merchandising","inventory",
                                         "unloading","promotion","marking","other",
                                         name="task_category", create_type=False), nullable=False),
        sa.Column("status",      sa.Enum("draft","published","taken","in_progress","submitted",
                                         "accepted","rejected","completed","cancelled","expired",
                                         name="task_status", create_type=False),
                  nullable=False, server_default="draft"),

        # Где выполняется
        sa.Column("store_id",        postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("store_address",   sa.String(500), nullable=False),
        sa.Column("store_latitude",  sa.Float, nullable=True),
        sa.Column("store_longitude", sa.Float, nullable=True),

        # Кто создал / кто выполняет
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("executor_id",   postgresql.UUID(as_uuid=True), nullable=True),

        # Оплата
        sa.Column("price",              sa.Numeric(10, 2), nullable=False),
        sa.Column("price_includes_tax", sa.Boolean, nullable=False, server_default="true"),

        # Сроки
        sa.Column("scheduled_date",       sa.Date, nullable=False),
        sa.Column("scheduled_time_start", sa.Time, nullable=True),
        sa.Column("scheduled_time_end",   sa.Time, nullable=True),
        sa.Column("deadline_at",          sa.DateTime(timezone=True), nullable=True),
        sa.Column("actual_start_at",      sa.DateTime(timezone=True), nullable=True),
        sa.Column("actual_end_at",        sa.DateTime(timezone=True), nullable=True),

        # Фотоотчёт (ТЗ 3.10)
        sa.Column("required_photo_count", sa.SmallInteger, nullable=False, server_default="1"),
        sa.Column("photo_instructions",   sa.Text, nullable=True),
        sa.Column("photos_verified",      sa.Boolean, nullable=False, server_default="false"),

        # Приёмка
        sa.Column("accepted_by_id",   postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("rejection_reason", sa.Text, nullable=True),
        sa.Column("rejection_count",  sa.SmallInteger, nullable=False, server_default="0"),

        # Шаблон
        sa.Column("template_id", postgresql.UUID(as_uuid=True), nullable=True),

        # Хронология
        sa.Column("created_at",    sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("published_at",  sa.DateTime(timezone=True), nullable=True),
        sa.Column("taken_at",      sa.DateTime(timezone=True), nullable=True),
        sa.Column("submitted_at",  sa.DateTime(timezone=True), nullable=True),
        sa.Column("accepted_at",   sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at",  sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at",    sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_tasks_status",          "tasks", ["status"])
    op.create_index("ix_tasks_store_id",        "tasks", ["store_id"])
    op.create_index("ix_tasks_executor_id",     "tasks", ["executor_id"])
    op.create_index("ix_tasks_status_scheduled","tasks", ["status", "scheduled_date"])
    op.create_index("ix_tasks_store_status",    "tasks", ["store_id", "status"])
    op.create_index("ix_tasks_executor_status", "tasks", ["executor_id", "status"])

    # ─────────────────────────────────────────────────────────────────────────
    # 6. ФОТООТЧЁТЫ К ЗАДАНИЯМ (ТЗ 3.10)
    # ─────────────────────────────────────────────────────────────────────────
    op.create_table(
        "task_photos",
        sa.Column("id",          postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("task_id",     postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("executor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sequence_number", sa.SmallInteger, nullable=False, server_default="1"),

        # Файл в MinIO
        sa.Column("file_path",       sa.String(500), nullable=False),
        sa.Column("file_size_bytes", sa.Integer, nullable=True),
        sa.Column("image_width",     sa.Integer, nullable=True),
        sa.Column("image_height",    sa.Integer, nullable=True),

        # Геолокация из EXIF
        sa.Column("photo_latitude",            sa.Float, nullable=True),
        sa.Column("photo_longitude",           sa.Float, nullable=True),
        sa.Column("distance_from_store_meters",sa.Float, nullable=True),
        sa.Column("geo_verification",
                  sa.Enum("pending","verified","failed",
                           name="photo_geo_status", create_type=False),
                  nullable=False, server_default="pending"),

        # Время
        sa.Column("taken_at",    sa.DateTime(timezone=True), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),

        # Ручная проверка
        sa.Column("manually_verified",       sa.Boolean, nullable=False, server_default="false"),
        sa.Column("manually_verified_by_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_task_photos_task_id", "task_photos", ["task_id"])

    # ─────────────────────────────────────────────────────────────────────────
    # 7. РЕЕСТРЫ МАССОВЫХ ВЫПЛАТ (ТЗ 3.12)
    # ─────────────────────────────────────────────────────────────────────────
    op.create_table(
        "payment_registries",
        sa.Column("id",           postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_by_id",postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status",
                  sa.Enum("uploaded","validating","validated","rejected",
                           "processing","completed","partial","failed",
                           name="registry_status", create_type=False),
                  nullable=False, server_default="uploaded"),

        # Файл
        sa.Column("file_name",      sa.String(255), nullable=False),
        sa.Column("file_path",      sa.String(500), nullable=True),
        sa.Column("file_size_bytes",sa.Integer,     nullable=True),

        # Счётчики строк
        sa.Column("total_rows",   sa.Integer,     nullable=False, server_default="0"),
        sa.Column("valid_rows",   sa.Integer,     nullable=False, server_default="0"),
        sa.Column("invalid_rows", sa.Integer,     nullable=False, server_default="0"),
        sa.Column("paid_rows",    sa.Integer,     nullable=False, server_default="0"),

        # Суммы
        sa.Column("total_amount",   sa.Numeric(14, 2), nullable=False, server_default="0.00"),
        sa.Column("paid_amount",    sa.Numeric(14, 2), nullable=False, server_default="0.00"),

        # XML для 1С
        sa.Column("xml_export_path", sa.String(500), nullable=True),
        sa.Column("approved_by_id",  postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approved_at",     sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes",           sa.Text, nullable=True),

        # Временные метки
        sa.Column("created_at",    sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("processed_at",  sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at",    sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_payment_registries_status",      "payment_registries", ["status"])
    op.create_index("ix_payment_registries_created_by",  "payment_registries", ["created_by_id"])

    # ─────────────────────────────────────────────────────────────────────────
    # 8. СТРОКИ РЕЕСТРА
    # ─────────────────────────────────────────────────────────────────────────
    op.create_table(
        "payment_registry_items",
        sa.Column("id",          postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("registry_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("payment_registries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("row_number",  sa.Integer, nullable=False),

        # Данные из Excel
        sa.Column("executor_inn",  sa.String(12),  nullable=True),
        sa.Column("executor_name", sa.String(255), nullable=True),
        sa.Column("description",   sa.Text,        nullable=True),
        sa.Column("amount",        sa.Numeric(10, 2), nullable=False),
        sa.Column("service_date",  sa.Date,        nullable=True),
        sa.Column("note",          sa.Text,        nullable=True),

        # Найденный пользователь (после валидации)
        sa.Column("executor_id",   postgresql.UUID(as_uuid=True), nullable=True),

        # Результаты 5 проверок (ТЗ 3.12)
        sa.Column("check_fns_status",  sa.Boolean, nullable=True),  # 1. Статус ФНС активен?
        sa.Column("check_income_limit",sa.Boolean, nullable=True),  # 2. Лимит 2.4М не превышен?
        sa.Column("check_duplicate",   sa.Boolean, nullable=True),  # 3. Нет дубля в реестре?
        sa.Column("check_amount",      sa.Boolean, nullable=True),  # 4. Сумма > 0?
        sa.Column("check_budget",      sa.Boolean, nullable=True),  # 5. Бюджет позволяет?
        sa.Column("validation_errors", sa.JSON,    nullable=True),  # Список ошибок

        # Статус строки
        sa.Column("status",
                  sa.Enum("pending","valid","invalid","paid","failed",
                           name="registry_item_status", create_type=False),
                  nullable=False, server_default="pending"),

        # Результат выплаты
        sa.Column("payment_id",        postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("sovcombank_tx_id",  sa.String(100), nullable=True),
        sa.Column("error_message",     sa.Text,        nullable=True),
        sa.Column("processed_at",      sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_payment_registry_items_registry", "payment_registry_items", ["registry_id"])
    op.create_index("ix_payment_registry_items_executor", "payment_registry_items", ["executor_id"])

    # ─────────────────────────────────────────────────────────────────────────
    # 9. ВЫПЛАТЫ
    # ─────────────────────────────────────────────────────────────────────────
    op.create_table(
        "payments",
        sa.Column("id",          postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("task_id",     postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tasks.id"),                nullable=False, unique=True),
        sa.Column("executor_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id"),                nullable=False),
        sa.Column("registry_item_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("payment_registry_items.id"), nullable=True),

        # Суммы
        sa.Column("amount",       sa.Numeric(10, 2), nullable=False),
        sa.Column("tax_amount",   sa.Numeric(10, 2), nullable=False, server_default="0.00"),
        sa.Column("total_amount", sa.Numeric(10, 2), nullable=False),

        # Статус
        sa.Column("status",
                  sa.Enum("pending","processing","completed","failed","cancelled",
                           name="payment_status", create_type=False),
                  nullable=False, server_default="pending"),
        sa.Column("attempts", sa.SmallInteger, nullable=False, server_default="0"),

        # Совкомбанк
        sa.Column("sovcombank_tx_id",    sa.String(100), nullable=True),
        sa.Column("sovcombank_request",  sa.JSON,        nullable=True),
        sa.Column("sovcombank_response", sa.JSON,        nullable=True),
        sa.Column("error_message",       sa.Text,        nullable=True),

        # Чек ФНС (связь)
        sa.Column("fns_receipt_id", postgresql.UUID(as_uuid=True), nullable=True),

        # Временные метки
        sa.Column("created_at",   sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at",   sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_payments_executor_id", "payments", ["executor_id"])
    op.create_index("ix_payments_status",      "payments", ["status"])
    op.create_index("ix_payments_task_id",     "payments", ["task_id"], unique=True)

    # ─────────────────────────────────────────────────────────────────────────
    # 10. ЧЕКИ ФНС (ТЗ 3.11 — контроль аннулирования)
    # ─────────────────────────────────────────────────────────────────────────
    op.create_table(
        "fns_receipts",
        sa.Column("id",         postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("payment_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("payments.id"), nullable=False, unique=True),
        sa.Column("executor_id",postgresql.UUID(as_uuid=True), nullable=False),

        # Данные чека от ФНС
        sa.Column("fns_receipt_uuid",   sa.String(100), nullable=True),
        sa.Column("fns_receipt_link",   sa.Text,        nullable=True),
        sa.Column("service_description",sa.Text,        nullable=False),
        sa.Column("service_date",       sa.Date,        nullable=False),
        sa.Column("amount",             sa.Numeric(10, 2), nullable=False),

        # Статус
        sa.Column("status",
                  sa.Enum("created","cancelled","error",
                           name="fns_receipt_status", create_type=False),
                  nullable=False, server_default="created"),

        # Аннулирование (ТЗ 3.11)
        sa.Column("cancellation_reason", sa.Text,               nullable=True),
        sa.Column("cancelled_at",        sa.DateTime(timezone=True), nullable=True),

        # Уведомления (должны быть отправлены в течение 1 часа после аннулирования)
        sa.Column("director_notified_at",    sa.DateTime(timezone=True), nullable=True),
        sa.Column("accounting_notified_at",  sa.DateTime(timezone=True), nullable=True),

        # Последняя проверка (ежедневно в 07:00 по расписанию Celery)
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),

        # Временные метки
        sa.Column("created_at",  sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at",  sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_fns_receipts_payment_id",  "fns_receipts", ["payment_id"], unique=True)
    op.create_index("ix_fns_receipts_executor_id", "fns_receipts", ["executor_id"])
    op.create_index("ix_fns_receipts_status",      "fns_receipts", ["status"])


# =============================================================================
# DOWNGRADE — откатываем миграцию (удаляем таблицы)
# ВНИМАНИЕ: удаляет ВСЕ данные! Использовать только на тестовой БД.
# =============================================================================

def downgrade() -> None:
    # Удаляем в обратном порядке (сначала зависимые таблицы)
    op.drop_table("fns_receipts")
    op.drop_table("payments")
    op.drop_table("payment_registry_items")
    op.drop_table("payment_registries")
    op.drop_table("task_photos")
    op.drop_table("tasks")
    op.drop_table("task_templates")
    op.drop_table("sms_codes")
    op.drop_table("users")

    # Удаляем ENUM типы (тоже в обратном порядке)
    op.execute("DROP TYPE IF EXISTS template_category")
    op.execute("DROP TYPE IF EXISTS fns_receipt_status")
    op.execute("DROP TYPE IF EXISTS registry_item_status")
    op.execute("DROP TYPE IF EXISTS registry_status")
    op.execute("DROP TYPE IF EXISTS payment_status")
    op.execute("DROP TYPE IF EXISTS photo_geo_status")
    op.execute("DROP TYPE IF EXISTS task_category")
    op.execute("DROP TYPE IF EXISTS task_status")
    op.execute("DROP TYPE IF EXISTS fns_status")
    op.execute("DROP TYPE IF EXISTS user_status")
    op.execute("DROP TYPE IF EXISTS user_role")
