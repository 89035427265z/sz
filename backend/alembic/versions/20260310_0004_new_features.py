"""Новые таблицы: рейтинги, чат, штрафы, стоп-лист магазина, аудит

Revision ID: 20260310_0004
Revises: 20260306_0003
Create Date: 2026-03-10

Что делает эта миграция:
  - Создаёт таблицу ratings (оценки исполнителей директорами)
  - Создаёт таблицу chat_messages (переписка внутри заданий)
  - Создаёт ENUM penalty_type и таблицу penalties (штрафы за нарушения)
  - Создаёт таблицу store_blacklists (локальный ЧС магазина)
  - Создаёт таблицу audit_logs (журнал всех действий в системе)

Взято из лучших практик проекта коллеги (Node.js ветка) и
адаптировано для нашего Python/FastAPI бэкенда.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260310_0004"
down_revision = "20260306_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # =========================================================================
    # 1. ТАБЛИЦА РЕЙТИНГОВ
    # Директор магазина ставит оценку исполнителю после принятия работы.
    # =========================================================================
    op.create_table(
        "ratings",

        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "task_id", postgresql.UUID(as_uuid=True), nullable=False,
            comment="Задание за которое выставлена оценка",
        ),
        sa.Column(
            "executor_id", postgresql.UUID(as_uuid=True), nullable=False,
            comment="Исполнитель которого оценивают",
        ),
        sa.Column(
            "rated_by_id", postgresql.UUID(as_uuid=True), nullable=False,
            comment="Директор магазина, выставивший оценку",
        ),
        sa.Column(
            "score", sa.Integer, nullable=False,
            comment="Оценка от 1 до 5 звёзд",
        ),
        sa.Column(
            "comment", sa.Text, nullable=True,
            comment="Необязательный комментарий директора",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),

        # Ограничения: оценка 1-5
        sa.CheckConstraint("score >= 1 AND score <= 5", name="ck_rating_score_range"),
    )

    # Уникальный: одна оценка за одно задание
    op.create_index("uq_rating_task_executor", "ratings", ["task_id", "executor_id"], unique=True)
    # Для расчёта среднего рейтинга исполнителя
    op.create_index("ix_rating_executor_score", "ratings", ["executor_id", "score"])

    # =========================================================================
    # 2. ТАБЛИЦА ЧАТ-СООБЩЕНИЙ
    # Переписка исполнителя и директора внутри конкретного задания.
    # =========================================================================
    op.create_table(
        "chat_messages",

        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False,
                  comment="Уникальный идентификатор сообщения"),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False,
                  comment="Задание в рамках которого идёт переписка"),
        sa.Column("sender_id", postgresql.UUID(as_uuid=True), nullable=False,
                  comment="Отправитель сообщения"),
        sa.Column("receiver_id", postgresql.UUID(as_uuid=True), nullable=False,
                  comment="Получатель сообщения"),
        sa.Column("message", sa.Text, nullable=False,
                  comment="Текст сообщения"),
        sa.Column("is_read", sa.Boolean, nullable=False, server_default=sa.text("false"),
                  comment="Прочитано ли получателем"),
        sa.Column("photo_url", sa.String(512), nullable=True,
                  comment="URL прикреплённого фото (MinIO)"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # Загрузка сообщений по заданию в хронологическом порядке
    op.create_index("ix_chat_task_created", "chat_messages", ["task_id", "created_at"])
    # Счётчик непрочитанных для конкретного получателя
    op.create_index("ix_chat_receiver_unread", "chat_messages", ["receiver_id", "is_read"])

    # =========================================================================
    # 3. ТАБЛИЦА ШТРАФОВ
    # Система нарушений: накапливаются → влияют на рейтинг и доступ.
    # =========================================================================

    # Создаём ENUM тип нарушений
    penalty_type_enum = postgresql.ENUM(
        "cancel",    # Отказ от задания после взятия
        "no_show",   # Неявка без предупреждения
        "quality",   # Низкое качество (повторные отклонения)
        "late",      # Систематические опоздания
        "docs",      # Нарушения с документами / чеками ФНС
        name="penalty_type",
    )
    penalty_type_enum.create(op.get_bind())

    op.create_table(
        "penalties",

        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("executor_id", postgresql.UUID(as_uuid=True), nullable=False,
                  comment="Исполнитель которому выписан штраф"),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=True,
                  comment="Задание из-за которого возник штраф (если применимо)"),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=False,
                  comment="Директор магазина или HR, выписавший штраф"),
        sa.Column(
            "penalty_type",
            sa.Enum("cancel", "no_show", "quality", "late", "docs", name="penalty_type"),
            nullable=False,
            comment="Тип нарушения",
        ),
        sa.Column("reason", sa.Text, nullable=False,
                  comment="Описание нарушения для исполнителя"),
        sa.Column("amount", sa.Numeric(10, 2), nullable=True,
                  comment="Сумма финансового удержания (если применимо, руб.)"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true"),
                  comment="Активен ли штраф. False = снят HR-службой"),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True,
                  comment="Дата снятия штрафа"),
        sa.Column("resolved_by_id", postgresql.UUID(as_uuid=True), nullable=True,
                  comment="Кто снял штраф"),
        sa.Column("resolution_note", sa.Text, nullable=True,
                  comment="Причина снятия штрафа"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # Все активные штрафы конкретного исполнителя
    op.create_index("ix_penalty_executor_active", "penalties", ["executor_id", "is_active"])
    # Штрафы по типу (для статистики)
    op.create_index("ix_penalty_type_created", "penalties", ["penalty_type", "created_at"])

    # =========================================================================
    # 4. ТАБЛИЦА ЛОКАЛЬНОГО ЧС МАГАЗИНА
    # Исполнитель заблокирован только в одном конкретном магазине.
    # Отличается от stop_list — там глобальная блокировка по ИНН.
    # =========================================================================
    op.create_table(
        "store_blacklists",

        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("store_id", postgresql.UUID(as_uuid=True), nullable=False,
                  comment="Магазин в котором заблокирован исполнитель"),
        sa.Column("executor_id", postgresql.UUID(as_uuid=True), nullable=False,
                  comment="Заблокированный исполнитель"),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=False,
                  comment="Директор магазина, добавивший в ЧС"),
        sa.Column("reason", sa.Text, nullable=True,
                  comment="Причина блокировки"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True,
                  comment="NULL = бессрочно. Или дата когда блокировка истекает."),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),

        # Один исполнитель — одна активная запись на магазин
        sa.UniqueConstraint("store_id", "executor_id", name="uq_blacklist_store_executor"),
    )

    # Составной индекс для быстрой проверки при выдаче заданий
    op.create_index("ix_blacklist_check", "store_blacklists", ["store_id", "executor_id", "is_active"])

    # =========================================================================
    # 5. ТАБЛИЦА ЖУРНАЛА АУДИТА
    # Неизменяемый лог всех значимых действий. INSERT only, никогда UPDATE/DELETE.
    # Хранится минимум 5 лет (требование бухгалтерского учёта).
    # =========================================================================
    op.create_table(
        "audit_logs",

        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True,
                  comment="ID пользователя. NULL = системное действие (Celery, планировщик)"),
        sa.Column("user_phone", sa.String(20), nullable=True,
                  comment="Телефон на момент действия (для истории после удаления аккаунта)"),
        sa.Column("user_role", sa.String(30), nullable=True,
                  comment="Роль пользователя на момент действия"),
        sa.Column("ip_address", sa.String(45), nullable=True,
                  comment="IP-адрес запроса (IPv4 или IPv6)"),
        sa.Column("action", sa.String(100), nullable=False,
                  comment="Код действия: USER_BLOCKED, PAYMENT_APPROVED, STOP_LIST_ADDED и т.д."),
        sa.Column("entity", sa.String(50), nullable=True,
                  comment="Тип объекта: User, Task, Payment, StopList, Document"),
        sa.Column("entity_id", sa.String(36), nullable=True,
                  comment="ID изменённого объекта"),
        sa.Column("details", postgresql.JSONB, nullable=True,
                  comment="Подробности: старое и новое значение, причина, сумма и т.д."),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # Поиск всех действий конкретного пользователя
    op.create_index("ix_audit_user_action", "audit_logs", ["user_id", "action"])
    # Поиск всех изменений конкретного объекта
    op.create_index("ix_audit_entity", "audit_logs", ["entity", "entity_id"])
    # Хронологический поиск по типу действия
    op.create_index("ix_audit_action_created", "audit_logs", ["action", "created_at"])


def downgrade() -> None:
    # Удаляем в обратном порядке

    # Журнал аудита
    op.drop_index("ix_audit_action_created", table_name="audit_logs")
    op.drop_index("ix_audit_entity",         table_name="audit_logs")
    op.drop_index("ix_audit_user_action",    table_name="audit_logs")
    op.drop_table("audit_logs")

    # Локальный ЧС магазина
    op.drop_index("ix_blacklist_check", table_name="store_blacklists")
    op.drop_table("store_blacklists")

    # Штрафы
    op.drop_index("ix_penalty_type_created",   table_name="penalties")
    op.drop_index("ix_penalty_executor_active", table_name="penalties")
    op.drop_table("penalties")
    sa.Enum(name="penalty_type").drop(op.get_bind())

    # Чат
    op.drop_index("ix_chat_receiver_unread", table_name="chat_messages")
    op.drop_index("ix_chat_task_created",    table_name="chat_messages")
    op.drop_table("chat_messages")

    # Рейтинги
    op.drop_index("ix_rating_executor_score", table_name="ratings")
    op.drop_index("uq_rating_task_executor",  table_name="ratings")
    op.drop_table("ratings")
