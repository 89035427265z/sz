#!/bin/bash
# =============================================================================
# KARI.Самозанятые — Скрипт деплоя на VDS
# Сервер: 79.174.78.53
#
# Использование:
#   chmod +x deploy.sh   (один раз)
#   ./deploy.sh          (запустить деплой)
# =============================================================================

set -e  # Остановить при любой ошибке

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # Без цвета

echo ""
echo -e "${BLUE}=========================================="
echo -e "  KARI.Самозанятые — Деплой на сервер"
echo -e "  $(date '+%d.%m.%Y %H:%M')"
echo -e "==========================================${NC}"
echo ""

# --- Проверка: файл .env ---
if [ ! -f ".env" ]; then
    echo -e "${RED}❌ Файл .env не найден!${NC}"
    echo "   Создайте .env с правильными ключами"
    exit 1
fi
echo -e "${GREEN}✅ .env найден${NC}"

# --- Проверка: Docker установлен ---
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker не установлен!${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Docker доступен: $(docker --version)${NC}"

# --- Проверка: docker compose (новый синтаксис) ---
if ! docker compose version &> /dev/null; then
    echo -e "${RED}❌ docker compose не доступен!${NC}"
    echo "   Обновите Docker до версии с поддержкой compose v2"
    exit 1
fi
echo -e "${GREEN}✅ docker compose доступен${NC}"

echo ""
echo -e "${YELLOW}📦 Шаг 1/4: Собираем образы...${NC}"
docker compose build --no-cache

echo ""
echo -e "${YELLOW}🚀 Шаг 2/4: Запускаем сервисы...${NC}"
docker compose up -d

echo ""
echo -e "${YELLOW}⏳ Шаг 3/4: Ждём готовности базы данных (15 сек)...${NC}"
sleep 15

echo ""
echo -e "${YELLOW}🗄️  Шаг 4/4: Применяем миграции...${NC}"
docker compose exec backend alembic upgrade head

echo ""
echo -e "${GREEN}=================================================="
echo -e "  ✅ ДЕПЛОЙ ЗАВЕРШЁН УСПЕШНО!"
echo -e "=================================================="
echo ""
echo -e "  🌐 Веб-кабинет:   http://79.174.78.53"
echo -e "  📡 API (Swagger): http://79.174.78.53:8000/docs"
echo -e "  🗂️  MinIO консоль: http://79.174.78.53:9001"
echo ""
echo -e "  Логин MinIO: kari_minio / kari_minio_secret_2026"
echo ""
echo -e "  Для просмотра логов:"
echo -e "    docker compose logs -f backend"
echo -e "    docker compose logs -f celery"
echo -e "${NC}"

# --- Статус всех контейнеров ---
echo -e "${BLUE}Статус контейнеров:${NC}"
docker compose ps
