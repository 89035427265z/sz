"""Добавление таблицы стоп-листа (422-ФЗ ст.6 п.2 пп.8)

Revision ID: 20260306_0003
Revises: 20260304_0002
Create Date: 2026-03-06

Что делает эта миграция:
  - Создаёт ENUM тип stop_list_reason
  - Создаёт таблицу stop_list
  - Добавляет индексы для быстрой проверки ИНН при выдаче заданий
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260306_0003"
down_revision = "20260304_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Создаём ENUM тип для причин блокировки
    # ------------------------------------------------------------------
    stop_list_reason = postgresql.ENUM(
        "former_employee",   # Бывший сотрудник KARI (< 2 лет с увольнения)
        "fns_fine",          # Штраф от ФНС по этому ИНН
        "manual",            # Добавлен вручную HR/директором
        name="stop_list_reason",
    )
    stop_list_reason.create(op.get_bind())

    # ------------------------------------------------------------------
    # Создаём таблицу стоп-листа
    # ------------------------------------------------------------------
    op.create_table(
        "stop_list",

        # Идентификатор записи
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            comment="Уникальный идентификатор записи стоп-листа",
        ),

        # Данные заблокированного лица
        sa.Column(
            "inn",
            sa.String(12),
            nullable=False,
            comment="ИНН физлица (12 цифр)",
        ),
        sa.Column(
            "full_name",
            sa.String(255),
            nullable=True,
            comment="ФИО для справки",
        ),

        # Причина блокировки
        sa.Column(
            "reason",
            sa.Enum("former_employee", "fns_fine", "manual", name="stop_list_reason"),
            nullable=False,
            comment="Причина блокировки",
        ),
        sa.Column(
            "reason_details",
            sa.Text,
            nullable=True,
            comment="Подробности: номер приказа, дата штрафа ФНС, комментарий",
        ),

        # Период блокировки
        sa.Column(
            "employment_end_date",
            sa.Date,
            nullable=True,
            comment="Дата увольнения (для former_employee)",
        ),
        sa.Column(
            "blocked_until",
            sa.Date,
            nullable=True,
            comment="Дата окончания блокировки (NULL = бессрочно)",
        ),

        # Служебная информация
        sa.Column(
            "created_by_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="Кто добавил (NULL = авто-импорт)",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Дата добавления",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Дата последнего изменения",
        ),
        sa.Column(
            "deactivated_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Дата досрочного снятия блокировки",
        ),
        sa.Column(
            "deactivated_by_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="Кто снял блокировку досрочно",
        ),
        sa.Column(
            "is_active",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("true"),
            comment="Активна ли блокировка",
        ),
    )

    # ------------------------------------------------------------------
    # Создаём индексы
    # ------------------------------------------------------------------

    # Главный индекс: быстрая проверка ИНН при выдаче задания
    op.create_index(
        "ix_stop_list_inn",
        "stop_list",
        ["inn"],
    )

    # Составной индекс: ИНН + флаг активности
    op.create_index(
        "ix_stop_list_inn_active",
        "stop_list",
        ["inn", "is_active"],
    )

    # Индекс для планового снятия истёкших блокировок (Celery задача)
    op.create_index(
        "ix_stop_list_blocked_until",
        "stop_list",
        ["blocked_until", "is_active"],
    )


def downgrade() -> None:
    # Удаляем индексы
    op.drop_index("ix_stop_list_blocked_until", table_name="stop_list")
    op.drop_index("ix_stop_list_inn_active",    table_name="stop_list")
    op.drop_index("ix_stop_list_inn",           table_name="stop_list")

    # Удаляем таблицу
    op.drop_table("stop_list")

    # Удаляем ENUM тип
    sa.Enum(name="stop_list_reason").drop(op.get_bind())
