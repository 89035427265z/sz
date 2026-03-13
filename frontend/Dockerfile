# =============================================================================
# KARI.Самозанятые — Dockerfile для Frontend (React + Vite → nginx)
# Двухэтапная сборка: 1) Node собирает, 2) nginx раздаёт
# =============================================================================

# ── ЭТАП 1: Сборка React-приложения ──────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

# ARG позволяет передать URL API при сборке из docker-compose
ARG VITE_API_URL=http://79.174.78.53:8000
ENV VITE_API_URL=$VITE_API_URL

# Сначала зависимости (кэш Docker)
COPY package*.json ./
RUN npm ci --silent

# Затем весь код
COPY . .

# Собираем продакшн-сборку (папка dist/)
RUN npm run build

# ── ЭТАП 2: Раздача статики через nginx ──────────────────────────────────────
FROM nginx:1.25-alpine

# Копируем собранные файлы
COPY --from=builder /app/dist /usr/share/nginx/html

# Копируем наш конфиг nginx
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
