"""documents table

Revision ID: 20260304_0002
Revises: 20260303_0001
Create Date: 2026-03-04 10:00:00.000000

Создаёт таблицу documents для хранения договоров ГПХ и актов выполненных работ.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260304_0002"
down_revision = "20260303_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Тип документа ---
    op.execute("""
        CREATE TYPE document_type AS ENUM ('contract', 'act')
    """)

    # --- Статус документа ---
    op.execute("""
        CREATE TYPE document_status AS ENUM
        ('draft', 'pending_sign', 'signed', 'cancelled')
    """)

    # --- Таблица documents ---
    op.create_table(
        "documents",
        sa.Column("id",             postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("number",         sa.String(40),  nullable=True,  unique=True),

        # Связь с заданием
        sa.Column("task_id",        postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tasks.id", ondelete="RESTRICT"),
                  nullable=False),

        # Тип и статус
        sa.Column("doc_type",       sa.Enum("contract", "act",
                                             name="document_type",
                                             create_type=False),
                  nullable=False),
        sa.Column("status",         sa.Enum("draft", "pending_sign", "signed", "cancelled",
                                             name="document_status",
                                             create_type=False),
                  nullable=False, server_default="draft"),

        # Участники (копия на момент создания)
        sa.Column("executor_id",    postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("executor_name",  sa.String(255), nullable=False),
        sa.Column("executor_inn",   sa.String(12),  nullable=False),
        sa.Column("executor_phone", sa.String(20),  nullable=False),

        # Содержание
        sa.Column("task_title",     sa.String(200), nullable=False),
        sa.Column("task_number",    sa.String(30),  nullable=True),
        sa.Column("store_address",  sa.String(500), nullable=False),
        sa.Column("amount",         sa.String(20),  nullable=False),
        sa.Column("work_date",      sa.String(20),  nullable=True),

        # Файл в MinIO
        sa.Column("file_path",      sa.String(500), nullable=True),
        sa.Column("file_size_bytes",sa.String(20),  nullable=True),

        # Подпись исполнителя (ПЭП)
        sa.Column("sign_request_at",    sa.DateTime(timezone=True), nullable=True),
        sa.Column("executor_signed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("executor_sign_ip",   sa.String(50),  nullable=True),
        sa.Column("executor_sign_device", sa.String(200), nullable=True),

        # Подпись директора
        sa.Column("director_id",        postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("director_name",      sa.String(255), nullable=True),
        sa.Column("director_signed_at", sa.DateTime(timezone=True), nullable=True),

        # Хронология
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # --- Индексы ---
    op.create_index("ix_documents_task_type",  "documents", ["task_id", "doc_type"])
    op.create_index("ix_documents_executor",   "documents", ["executor_id", "status"])
    op.create_index("ix_documents_status",     "documents", ["status"])


def downgrade() -> None:
    op.drop_index("ix_documents_status")
    op.drop_index("ix_documents_executor")
    op.drop_index("ix_documents_task_type")
    op.drop_table("documents")
    op.execute("DROP TYPE IF EXISTS document_status")
    op.execute("DROP TYPE IF EXISTS document_type")
