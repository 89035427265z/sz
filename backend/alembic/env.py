# =============================================================================
# KARI.Самозанятые — Alembic environment
# Файл: alembic/env.py
# =============================================================================
# Этот файл настраивает Alembic для работы с нашей БД.
# Ключевое: импортируем все модели → Alembic "знает" о всех таблицах.
# =============================================================================

import asyncio
import os
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# ─────────────────────────────────────────────────────────────────────────────
# Импортируем Base и ВСЕ модели — без этого Alembic не увидит таблицы
# ─────────────────────────────────────────────────────────────────────────────
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database import Base         # DeclarativeBase
from app.models.user      import User, SmsCode                       # noqa
from app.models.task      import Task, TaskPhoto, TaskTemplate        # noqa
from app.models.payment   import (                                    # noqa
    Payment, PaymentRegistry, PaymentRegistryItem, FnsReceipt
)
from app.models.stop_list import StopList                            # noqa
from app.models.document  import Document                            # noqa

# ─────────────────────────────────────────────────────────────────────────────
# Конфигурация Alembic
# ─────────────────────────────────────────────────────────────────────────────
config = context.config

# Настройка логирования из alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Указываем Alembic откуда брать схему таблиц
target_metadata = Base.metadata

# ─────────────────────────────────────────────────────────────────────────────
# URL базы данных
# Сначала смотрим в переменную окружения DATABASE_URL,
# потом — в alembic.ini
# ─────────────────────────────────────────────────────────────────────────────
def get_url() -> str:
    """
    Возвращает URL подключения к БД.

    Приоритет:
    1. Переменная окружения DATABASE_URL (устанавливает IT при деплое)
    2. Значение из alembic.ini (для разработки)

    ВАЖНО: asyncpg (async) заменяем на psycopg2 (sync) — Alembic работает синхронно.
    Async-миграции настраиваются отдельно ниже.
    """
    url = os.environ.get("DATABASE_URL") or config.get_main_option("sqlalchemy.url")
    # Приводим URL к async-формату для async engine
    if url and url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url and url.startswith("postgresql+psycopg2://"):
        url = url.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
    return url


# ─────────────────────────────────────────────────────────────────────────────
# OFFLINE-режим: генерирует SQL-скрипт без подключения к БД
# (используется редко — для проверки SQL перед применением)
# ─────────────────────────────────────────────────────────────────────────────
def run_migrations_offline() -> None:
    """
    Генерирует SQL миграций без подключения к базе данных.
    Удобно для проверки SQL перед применением на проде.

    Запуск: alembic upgrade head --sql > migration.sql
    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # Сравниваем типы столбцов при autogenerate
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


# ─────────────────────────────────────────────────────────────────────────────
# ONLINE-режим: подключается к БД и применяет миграции
# ─────────────────────────────────────────────────────────────────────────────
def do_run_migrations(connection: Connection) -> None:
    """Выполняет миграции в рамках существующего соединения."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        # Позволяет Alembic корректно работать с ENUM типами PostgreSQL
        include_schemas=False,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """
    Запускает async движок и выполняет миграции через run_sync.
    Это нужно потому что наш бэкенд использует asyncpg,
    но Alembic требует синхронное соединение.
    """
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_url()

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,  # Без пула — каждая миграция = новое соединение
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Точка входа для online-миграций (запускается командой alembic upgrade)."""
    asyncio.run(run_async_migrations())


# ─────────────────────────────────────────────────────────────────────────────
# Определяем режим и запускаем
# ─────────────────────────────────────────────────────────────────────────────
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
