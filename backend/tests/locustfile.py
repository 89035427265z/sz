# =============================================================================
# KARI.Самозанятые — Нагрузочное тестирование (Locust)
# Файл: tests/locustfile.py
#
# Запуск:
#   pip install locust
#   locust -f tests/locustfile.py --host=http://localhost:8000
#   Открыть: http://localhost:8089
#
# Целевые параметры пилота:
#   500 самозанятых + 100 директоров магазинов = 600 пользователей
#   Пиковая нагрузка: 600 concurrent users
#   Целевой RPS: 200 запросов/сек
#   P95 latency: < 500 мс
# =============================================================================

import random
import json
from locust import HttpUser, TaskSet, task, between, events


# =============================================================================
# ДЕМО-ДАННЫЕ ДЛЯ ТЕСТОВ
# =============================================================================

DEMO_PHONE_EXECUTORS = [f"+7914{str(i).zfill(7)}" for i in range(1, 501)]
DEMO_PHONE_DIRECTORS = [f"+7913{str(i).zfill(7)}" for i in range(1, 101)]
DEMO_INN_LIST        = [f"38{str(i).zfill(10)}" for i in range(1, 501)]

DEMO_TASK_TITLES = [
    "Уборка торгового зала",
    "Выкладка весенней коллекции",
    "Переоценка товаров",
    "Инвентаризация склада",
    "Промо-акция: раздача листовок",
    "Мерчандайзинг обуви",
    "Разгрузка поставки",
    "Помощь в торговом зале",
]

DEMO_STORES = [
    {"name": "ТЦ «Карамель»", "address": "г. Иркутск, ул. Байкальская, 253А"},
    {"name": "ТЦ «Мегас»",    "address": "г. Иркутск, Сергеева, 3"},
    {"name": "ТЦ «Аквамолл»", "address": "г. Иркутск, ул. Баумана, 220"},
]


# =============================================================================
# СЦЕНАРИЙ 1: ИСПОЛНИТЕЛЬ (самозанятый)
# Вес: 500 пользователей — основная нагрузка
# =============================================================================

class ExecutorBehavior(TaskSet):
    """
    Типичные действия исполнителя:
    - Авторизация по SMS
    - Просмотр биржи заданий
    - Взятие задания
    - Отправка фотоотчёта
    - Просмотр кошелька
    """
    token: str = None

    def on_start(self):
        """Авторизация при старте."""
        self._auth()

    def _auth(self):
        """Запрашивает SMS и подтверждает код."""
        phone = random.choice(DEMO_PHONE_EXECUTORS)

        # Запрос SMS-кода
        resp = self.client.post(
            "/api/v1/auth/request-code",
            json={"phone": phone},
            name="/auth/request-code",
        )
        if resp.status_code != 200:
            return

        # Подтверждение кода (в тестовой среде принимается любой 4-значный код)
        resp = self.client.post(
            "/api/v1/auth/confirm-code",
            json={"phone": phone, "code": "1234"},
            name="/auth/confirm-code",
        )
        if resp.status_code == 200:
            data = resp.json()
            self.token   = data.get("access_token")
            self.headers = {"Authorization": f"Bearer {self.token}"}

    def _headers(self):
        return getattr(self, "headers", {})

    @task(5)
    def browse_tasks(self):
        """Просмотр биржи заданий (самый частый сценарий)."""
        self.client.get(
            "/api/v1/tasks?status=available&limit=20",
            headers=self._headers(),
            name="/tasks [browse]",
        )

    @task(3)
    def view_task_detail(self):
        """Открыть карточку задания."""
        # Сначала получаем список
        resp = self.client.get(
            "/api/v1/tasks?status=available&limit=5",
            headers=self._headers(),
            name="/tasks [list for detail]",
        )
        if resp.status_code == 200:
            items = resp.json().get("items", [])
            if items:
                task_id = random.choice(items)["id"]
                self.client.get(
                    f"/api/v1/tasks/{task_id}",
                    headers=self._headers(),
                    name="/tasks/{id} [detail]",
                )

    @task(2)
    def view_wallet(self):
        """Открыть кошелёк."""
        self.client.get(
            "/api/v1/payments/my",
            headers=self._headers(),
            name="/payments/my [wallet]",
        )

    @task(2)
    def view_profile(self):
        """Просмотр профиля."""
        self.client.get(
            "/api/v1/users/me",
            headers=self._headers(),
            name="/users/me [profile]",
        )

    @task(1)
    def accept_task(self):
        """Взять задание (реже всего — ограничено реальными заданиями)."""
        resp = self.client.get(
            "/api/v1/tasks?status=available&limit=10",
            headers=self._headers(),
            name="/tasks [for accept]",
        )
        if resp.status_code == 200:
            items = resp.json().get("items", [])
            available = [t for t in items if t.get("executors_taken", 0) < t.get("executors_needed", 1)]
            if available:
                task_id = random.choice(available)["id"]
                self.client.post(
                    f"/api/v1/tasks/{task_id}/accept",
                    headers=self._headers(),
                    name="/tasks/{id}/accept",
                )

    @task(1)
    def view_documents(self):
        """Просмотр документов (договоры, акты)."""
        self.client.get(
            "/api/v1/documents",
            headers=self._headers(),
            name="/documents [list]",
        )


class ExecutorUser(HttpUser):
    tasks = [ExecutorBehavior]
    weight = 5                    # 500 из 600 пользователей — исполнители
    wait_time = between(2, 8)     # задержка между запросами 2–8 секунд


# =============================================================================
# СЦЕНАРИЙ 2: ДИРЕКТОР МАГАЗИНА
# Вес: 100 пользователей
# =============================================================================

class StoreDirectorBehavior(TaskSet):
    """
    Типичные действия директора магазина:
    - Просмотр заданий своего магазина
    - Приёмка выполненных заданий
    - Создание новых заданий
    """
    token: str = None

    def on_start(self):
        phone = random.choice(DEMO_PHONE_DIRECTORS)
        resp = self.client.post(
            "/api/v1/auth/confirm-code",
            json={"phone": phone, "code": "1234"},
            name="/auth/confirm-code [director]",
        )
        if resp.status_code == 200:
            self.token   = resp.json().get("access_token")
            self.headers = {"Authorization": f"Bearer {self.token}"}

    def _headers(self):
        return getattr(self, "headers", {})

    @task(4)
    def view_store_tasks(self):
        """Просмотр заданий магазина."""
        self.client.get(
            "/api/v1/tasks?limit=20",
            headers=self._headers(),
            name="/tasks [store director view]",
        )

    @task(3)
    def view_pending_review(self):
        """Задания на проверке."""
        self.client.get(
            "/api/v1/tasks?status=pending_review&limit=10",
            headers=self._headers(),
            name="/tasks [pending_review]",
        )

    @task(2)
    def view_executors(self):
        """Список исполнителей."""
        self.client.get(
            "/api/v1/users?role=executor&limit=20",
            headers=self._headers(),
            name="/users [executors list]",
        )

    @task(2)
    def create_task(self):
        """Создать задание."""
        store = random.choice(DEMO_STORES)
        self.client.post(
            "/api/v1/tasks",
            headers=self._headers(),
            json={
                "title":            random.choice(DEMO_TASK_TITLES),
                "description":      "Нагрузочный тест",
                "store_name":       store["name"],
                "store_address":    store["address"],
                "price":            random.choice([900, 1200, 1500, 2000, 2500]),
                "executors_needed": random.randint(1, 3),
                "deadline":         "2026-04-30",
                "duration_hours":   random.randint(2, 8),
                "category":         "Уборка",
            },
            name="/tasks [create]",
        )

    @task(1)
    def accept_task_work(self):
        """Принять выполненную работу."""
        resp = self.client.get(
            "/api/v1/tasks?status=pending_review&limit=5",
            headers=self._headers(),
            name="/tasks [for acceptance]",
        )
        if resp.status_code == 200:
            items = resp.json().get("items", [])
            if items:
                task_id = random.choice(items)["id"]
                self.client.post(
                    f"/api/v1/tasks/{task_id}/accept-work",
                    headers=self._headers(),
                    name="/tasks/{id}/accept-work",
                )

    @task(1)
    def view_payments(self):
        """Просмотр выплат."""
        self.client.get(
            "/api/v1/payments?limit=20",
            headers=self._headers(),
            name="/payments [director view]",
        )


class StoreDirectorUser(HttpUser):
    tasks = [StoreDirectorBehavior]
    weight = 1                    # 100 из 600 пользователей — директора
    wait_time = between(3, 15)    # директора делают запросы реже


# =============================================================================
# СОБЫТИЯ: вывод статистики в консоль
# =============================================================================

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    print("\n" + "=" * 60)
    print("KARI.Самозанятые — Нагрузочный тест")
    print("Цель пилота: 600 пользователей, P95 < 500 мс")
    print("=" * 60 + "\n")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    stats = environment.stats
    print("\n" + "=" * 60)
    print("ИТОГИ НАГРУЗОЧНОГО ТЕСТА")
    print("=" * 60)
    total = stats.total
    print(f"Всего запросов:    {total.num_requests}")
    print(f"Ошибок:            {total.num_failures} ({total.fail_ratio * 100:.1f}%)")
    print(f"Среднее время:     {total.avg_response_time:.0f} мс")
    print(f"P95:               {total.get_response_time_percentile(0.95):.0f} мс")
    print(f"P99:               {total.get_response_time_percentile(0.99):.0f} мс")
    print(f"RPS (пиковый):     {total.current_rps:.1f}")

    # Критерий прохождения теста
    p95 = total.get_response_time_percentile(0.95)
    fail_pct = total.fail_ratio * 100

    if p95 < 500 and fail_pct < 1:
        print("\n✅ ТЕСТ ПРОЙДЕН: P95 < 500 мс, ошибок < 1%")
    else:
        print(f"\n❌ ТЕСТ НЕ ПРОЙДЕН: P95={p95:.0f} мс (норма < 500), ошибок={fail_pct:.1f}% (норма < 1%)")
    print("=" * 60 + "\n")
