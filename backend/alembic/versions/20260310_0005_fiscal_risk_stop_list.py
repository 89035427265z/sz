"""Добавление причины FISCAL_RISK в стоп-лист

Revision ID: 20260310_0005
Revises: 20260310_0004
Create Date: 2026-03-10

Что делает эта миграция:
  - Добавляет новое значение 'fiscal_risk' в ENUM stop_list_reason
  - Добавляет колонку fiscal_check_year в stop_list (для какого года проверка)
  - Создаёт индекс для быстрой выборки FISCAL_RISK записей

Контекст:
  ФНС проверяет исполнителей по трём критериям переквалификации
  (доход, срок, доля в НПД). При срабатывании всех трёх — автоматическое
  добавление в стоп-лист с причиной FISCAL_RISK через Celery-задачу.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260310_0005"
down_revision = "20260310_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # =========================================================================
    # 1. Добавляем новое значение в ENUM stop_list_reason
    #
    # PostgreSQL не позволяет просто ALTER TYPE ADD VALUE внутри транзакции
    # в ряде версий. Используем COMMIT-безопасный подход.
    # =========================================================================
    op.execute("ALTER TYPE stop_list_reason ADD VALUE IF NOT EXISTS 'fiscal_risk'")

    # =========================================================================
    # 2. Добавляем вспомогательную колонку в таблицу stop_list
    # =========================================================================
    op.add_column(
        "stop_list",
        sa.Column(
            "fiscal_check_year",
            sa.Integer,
            nullable=True,
            comment=(
                "Год, за который обнаружен фискальный риск. "
                "Заполняется только для reason=fiscal_risk."
            ),
        ),
    )

    op.add_column(
        "stop_list",
        sa.Column(
            "fiscal_risk_level",
            sa.String(20),
            nullable=True,
            comment="Уровень риска: medium / high / critical",
        ),
    )

    op.add_column(
        "stop_list",
        sa.Column(
            "fiscal_criteria_flags",
            postgresql.JSONB,
            nullable=True,
            comment=(
                "Какие именно критерии сработали: "
                '{"c1_income": true, "c2_months": true, "c3_share": false}'
            ),
        ),
    )

    # =========================================================================
    # 3. Индекс для быстрой выборки активных FISCAL_RISK записей
    # =========================================================================
    op.create_index(
        "ix_stop_list_fiscal_risk",
        "stop_list",
        ["reason", "fiscal_check_year", "is_active"],
    )


def downgrade() -> None:
    # Удаляем индекс
    op.drop_index("ix_stop_list_fiscal_risk", table_name="stop_list")

    # Удаляем добавленные колонки
    op.drop_column("stop_list", "fiscal_criteria_flags")
    op.drop_column("stop_list", "fiscal_risk_level")
    op.drop_column("stop_list", "fiscal_check_year")

    # ВНИМАНИЕ: PostgreSQL не поддерживает удаление значений из ENUM.
    # Значение 'fiscal_risk' останется в типе, но не будет использоваться.
    # При полном откате БД — пересоздать ENUM вручную.
