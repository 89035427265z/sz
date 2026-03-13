# =============================================================================
# KARI.Самозанятые — Dockerfile для Backend (FastAPI + Python)
# =============================================================================

FROM python:3.12-slim

WORKDIR /app

# Системные зависимости (нужны для asyncpg, Pillow, reportlab)
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Сначала копируем только requirements — Docker кэширует этот слой
# и не переустанавливает пакеты при изменении кода приложения
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Копируем весь код проекта
COPY . .

# Скрипт запуска (миграции → сервер)
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
