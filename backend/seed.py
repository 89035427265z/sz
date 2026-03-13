"""
=============================================================================
KARI.Самозанятые — Сид-скрипт (заполнение БД тестовыми данными)
=============================================================================
Запуск:
    cd 04_Разработка/backend
    python seed.py

Создаёт:
    - 1  директор региона     (Юрий Петров, Иркутский регион)
    - 1  HRD                  (Алёна Фомина)
    - 3  директора подразделения
    - 10 директоров магазинов
    - 32 исполнителя (самозанятых) — разные статусы
    - 85 заданий               — все статусы жизненного цикла
    - 48 выплат                — завершённые и в обработке
=============================================================================
"""

import asyncio
import uuid
from datetime import datetime, date, timedelta
from decimal import Decimal
import random
import sys
import os

# Добавляем корневую папку backend в путь
sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy import text
from app.database import engine, AsyncSessionLocal, Base
from app.models.user import User, UserRole, UserStatus, FnsStatus
from app.models.task import Task, TaskStatus, TaskCategory
from app.models.payment import Payment, PaymentStatus, FnsReceipt, FnsReceiptStatus


# =============================================================================
# ИДЕНТИФИКАТОРЫ СТРУКТУРЫ KARI (регион / подразделения / магазины)
# =============================================================================

REGION_ID     = uuid.UUID("11111111-0000-0000-0000-000000000001")

DIV_CENTRE    = uuid.UUID("22222222-0000-0000-0000-000000000001")  # Иркутск Центр
DIV_WEST      = uuid.UUID("22222222-0000-0000-0000-000000000002")  # Иркутск Запад
DIV_NORTH     = uuid.UUID("22222222-0000-0000-0000-000000000003")  # Иркутск Север

# 10 магазинов — 3-4 на подразделение
STORES = [
    # Центр (3 магазина)
    {"id": uuid.UUID("33333333-0000-0000-0000-000000000001"), "name": "KARI ТЦ Сибирь",         "div": DIV_CENTRE},
    {"id": uuid.UUID("33333333-0000-0000-0000-000000000002"), "name": "KARI ТЦ Карамель",        "div": DIV_CENTRE},
    {"id": uuid.UUID("33333333-0000-0000-0000-000000000003"), "name": "KARI ТЦ Модный квартал", "div": DIV_CENTRE},
    # Запад (4 магазина)
    {"id": uuid.UUID("33333333-0000-0000-0000-000000000004"), "name": "KARI ТЦ Мегас",           "div": DIV_WEST},
    {"id": uuid.UUID("33333333-0000-0000-0000-000000000005"), "name": "KARI ТЦ Фортуна",         "div": DIV_WEST},
    {"id": uuid.UUID("33333333-0000-0000-0000-000000000006"), "name": "KARI ТЦ Радуга",          "div": DIV_WEST},
    {"id": uuid.UUID("33333333-0000-0000-0000-000000000007"), "name": "KARI ул. Ленина",         "div": DIV_WEST},
    # Север (3 магазина)
    {"id": uuid.UUID("33333333-0000-0000-0000-000000000008"), "name": "KARI ТЦ Альтаир",         "div": DIV_NORTH},
    {"id": uuid.UUID("33333333-0000-0000-0000-000000000009"), "name": "KARI ТЦ Версаль",         "div": DIV_NORTH},
    {"id": uuid.UUID("33333333-0000-0000-0000-000000000010"), "name": "KARI ТЦ Ручей",           "div": DIV_NORTH},
]


# =============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ДАННЫЕ
# =============================================================================

FIRST_NAMES = ["Иван", "Алексей", "Дмитрий", "Сергей", "Андрей", "Михаил",
               "Николай", "Денис", "Артём", "Владимир", "Олег", "Максим",
               "Анна", "Мария", "Елена", "Ольга", "Наталья", "Юлия",
               "Татьяна", "Светлана", "Екатерина", "Ирина"]

LAST_NAMES  = ["Иванов", "Петров", "Сидоров", "Кузнецов", "Попов", "Волков",
               "Новиков", "Морозов", "Соколов", "Лебедев", "Козлов", "Николаев",
               "Орлов", "Захаров", "Смирнов", "Федоров", "Малинин", "Борисов",
               "Громов", "Тихонов", "Беляев", "Шевченко"]

BANKS = [
    ("Сбербанк",    "**** **** **** 4821"),
    ("Тинькофф",    "**** **** **** 7734"),
    ("ВТБ",         "**** **** **** 2290"),
    ("Альфа-Банк",  "**** **** **** 9115"),
    ("Совкомбанк",  "**** **** **** 6643"),
    ("Газпромбанк", "**** **** **** 3378"),
]

TASK_TITLES = {
    TaskCategory.CLEANING:      ["Уборка торгового зала", "Генеральная уборка склада",
                                  "Мытьё витрин и примерочных", "Уборка подсобного помещения"],
    TaskCategory.MERCHANDISING: ["Выкладка нового ассортимента", "Оформление сезонной витрины",
                                  "Перекладка коллекции Весна-2026", "Мерчандайзинг детской зоны"],
    TaskCategory.INVENTORY:     ["Инвентаризация обуви (женский зал)", "Пересчёт детской коллекции",
                                  "Инвентаризация склада — мужская обувь", "Полная инвентаризация"],
    TaskCategory.UNLOADING:     ["Разгрузка товара (поставка 40 коробок)", "Приёмка новой коллекции",
                                  "Разгрузка склада и сортировка по зонам"],
    TaskCategory.PROMOTION:     ["Промо-акция 'Весенние скидки'", "Консультирование покупателей",
                                  "Промо у входа в ТЦ"],
    TaskCategory.MARKING:       ["Перемаркировка обуви (новые цены)", "Нанесение ценников на коллекцию",
                                  "Маркировка склада"],
    TaskCategory.OTHER:         ["Помощь при переезде склада", "Расстановка оборудования",
                                  "Подготовка зала к инвентаризации"],
}

AMOUNTS_BY_CATEGORY = {
    TaskCategory.CLEANING:      (800,  2500),
    TaskCategory.MERCHANDISING: (1200, 4000),
    TaskCategory.INVENTORY:     (2000, 6000),
    TaskCategory.UNLOADING:     (1500, 3500),
    TaskCategory.PROMOTION:     (1000, 3000),
    TaskCategory.MARKING:       (800,  2000),
    TaskCategory.OTHER:         (1000, 3000),
}


def rnd_phone(i: int) -> str:
    """Генерирует уникальный телефон для сид-данных."""
    return f"+7991{i:07d}"


def rnd_inn(i: int) -> str:
    """Генерирует ИНН-заглушку (12 цифр)."""
    base = f"381{i:09d}"
    return base[:12]


def rnd_name(seed_i: int) -> str:
    """Случайное ФИО на основе индекса."""
    random.seed(seed_i)
    first = random.choice(FIRST_NAMES)
    last  = random.choice(LAST_NAMES)
    mid   = random.choice(["Александрович", "Николаевич", "Сергеевич",
                            "Владимировна", "Михайловна", "Петровна", "Андреевна"])
    return f"{last} {first} {mid}"


def rnd_date(days_ago_min: int, days_ago_max: int) -> datetime:
    """Случайная дата в прошлом."""
    delta = random.randint(days_ago_min, days_ago_max)
    return datetime.utcnow() - timedelta(days=delta)


# =============================================================================
# СОЗДАНИЕ ПОЛЬЗОВАТЕЛЕЙ
# =============================================================================

async def create_users(session) -> dict:
    """
    Возвращает словарь:
      users["regional"]    — директор региона
      users["hrd"]         — HRD
      users["divisions"]   — список директоров подразделений
      users["stores"]      — список директоров магазинов
      users["executors"]   — список исполнителей
    """
    result = {}

    # ------------------------------------------------------------------
    # 1. Директор региона (Юрий Петров)
    # ------------------------------------------------------------------
    regional = User(
        phone     = "+79991000001",
        full_name = "Петров Юрий Александрович",
        role      = UserRole.REGIONAL_DIRECTOR,
        status    = UserStatus.ACTIVE,
        region_id = REGION_ID,
    )
    session.add(regional)
    result["regional"] = regional
    print("  ✅ Директор региона: Петров Юрий Александрович")

    # ------------------------------------------------------------------
    # 2. HRD / Бухгалтерия
    # ------------------------------------------------------------------
    hrd = User(
        phone     = "+79991000002",
        full_name = "Фомина Алёна Дмитриевна",
        role      = UserRole.REGIONAL_DIRECTOR,   # роль hrd — в системе пока regional
        status    = UserStatus.ACTIVE,
        region_id = REGION_ID,
    )
    session.add(hrd)
    result["hrd"] = hrd
    print("  ✅ HRD: Фомина Алёна Дмитриевна")

    # ------------------------------------------------------------------
    # 3. Директора подразделений (3 штуки)
    # ------------------------------------------------------------------
    div_data = [
        {"name": "Крылов Михаил Сергеевич",    "div": DIV_CENTRE, "phone": "+79991000010"},
        {"name": "Захарова Ирина Владимировна", "div": DIV_WEST,   "phone": "+79991000011"},
        {"name": "Лебедев Антон Николаевич",    "div": DIV_NORTH,  "phone": "+79991000012"},
    ]
    divisions = []
    for d in div_data:
        u = User(
            phone       = d["phone"],
            full_name   = d["name"],
            role        = UserRole.DIVISION_DIRECTOR,
            status      = UserStatus.ACTIVE,
            region_id   = REGION_ID,
            division_id = d["div"],
        )
        session.add(u)
        divisions.append(u)
        print(f"  ✅ Директор подразделения: {d['name']}")
    result["divisions"] = divisions

    # ------------------------------------------------------------------
    # 4. Директора магазинов (10 штук, по одному на магазин)
    # ------------------------------------------------------------------
    store_director_names = [
        "Воронова Светлана Игоревна",    "Тихонов Олег Борисович",
        "Малинина Юлия Петровна",        "Соколов Владимир Олегович",
        "Орлова Наталья Васильевна",     "Борисов Денис Андреевич",
        "Громова Ксения Максимовна",     "Шевченко Роман Алексеевич",
        "Беляева Анастасия Олеговна",    "Федоров Кирилл Николаевич",
    ]
    store_directors = []
    for i, store in enumerate(STORES):
        u = User(
            phone       = f"+7999100{i+20:04d}",
            full_name   = store_director_names[i],
            role        = UserRole.STORE_DIRECTOR,
            status      = UserStatus.ACTIVE,
            region_id   = REGION_ID,
            division_id = store["div"],
            store_id    = store["id"],
        )
        session.add(u)
        store_directors.append({"user": u, "store": store})
        print(f"  ✅ Директор магазина [{store['name']}]: {store_director_names[i]}")
    result["stores"] = store_directors

    # ------------------------------------------------------------------
    # 5. Исполнители (32 самозанятых)
    # ------------------------------------------------------------------
    executors = []

    # Распределяем по статусам:
    # 25 активных, 3 неактивных (утратили статус), 2 близко к лимиту, 2 заблокированы
    fns_statuses = (
        [FnsStatus.ACTIVE] * 25 +
        [FnsStatus.INACTIVE] * 3 +
        [FnsStatus.BLOCKED] * 2
    )
    # Для 2 — особые доходы (близко к лимиту 2.4 млн)
    NEAR_LIMIT_IDX = {2, 7}

    for i in range(30):
        random.seed(100 + i)
        bank      = random.choice(BANKS)
        fns_stat  = fns_statuses[i] if i < len(fns_statuses) else FnsStatus.ACTIVE
        u_status  = UserStatus.BLOCKED if fns_stat == FnsStatus.BLOCKED else UserStatus.ACTIVE

        if i in NEAR_LIMIT_IDX:
            income = Decimal(str(random.randint(2_100_000, 2_350_000)))
        elif fns_stat == FnsStatus.INACTIVE:
            income = Decimal(str(random.randint(50_000, 300_000)))
        else:
            income = Decimal(str(random.randint(30_000, 800_000)))

        u = User(
            phone                  = f"+7999200{i:04d}",
            full_name              = rnd_name(200 + i),
            role                   = UserRole.EXECUTOR,
            status                 = u_status,
            inn                    = rnd_inn(300 + i),
            fns_status             = fns_stat,
            fns_registration_date  = (date.today() - timedelta(days=random.randint(60, 730))),
            income_from_kari_year  = income,
            income_total_year      = income,
            income_tracking_year   = 2026,
            bank_card_masked       = bank[1],
            bank_name              = bank[0],
        )
        session.add(u)
        executors.append(u)

    print(f"  ✅ Исполнителей создано: {len(executors)} (25 активных, 3 неактивных, 2 заблокировано)")
    result["executors"] = executors

    await session.flush()  # получаем id без commit
    return result


# =============================================================================
# СОЗДАНИЕ ЗАДАНИЙ
# =============================================================================

async def create_tasks(session, users: dict) -> list:
    """
    Создаёт 85 заданий по всем магазинам с разными статусами.
    Каждому активному исполнителю присваивается несколько заданий.
    """
    executors       = [u for u in users["executors"] if u.fns_status == FnsStatus.ACTIVE]
    store_directors = users["stores"]
    tasks           = []

    # Статусы с нужным распределением
    STATUS_DIST = (
        [TaskStatus.COMPLETED]   * 30 +   # Завершённые (история)
        [TaskStatus.ACCEPTED]    * 8  +   # Принято, идёт оплата
        [TaskStatus.SUBMITTED]   * 7  +   # Сдано, ждёт проверки
        [TaskStatus.IN_PROGRESS] * 10 +   # В работе прямо сейчас
        [TaskStatus.TAKEN]       * 8  +   # Взято исполнителем
        [TaskStatus.PUBLISHED]   * 12 +   # Открытая биржа
        [TaskStatus.REJECTED]    * 5  +   # Отклонено директором
        [TaskStatus.CANCELLED]   * 3  +   # Отменено
        [TaskStatus.EXPIRED]     * 2  ,   # Истекло
    )
    random.shuffle(STATUS_DIST)

    for idx, status in enumerate(STATUS_DIST):
        random.seed(500 + idx)
        category = random.choice(list(TaskCategory))
        store    = random.choice(store_directors)["store"]
        sd_user  = random.choice(store_directors)["user"]

        amt_min, amt_max = AMOUNTS_BY_CATEGORY[category]
        amount   = Decimal(str(random.randint(amt_min, amt_max) // 100 * 100))  # кратно 100

        title    = random.choice(TASK_TITLES[category])

        # Даты в зависимости от статуса
        created  = rnd_date(90, 2)

        executor_id     = None
        taken_at        = None
        started_at      = None
        submitted_at    = None
        accepted_at     = None
        completed_at    = None
        rejected_at     = None
        rejection_reason= None

        if status in (TaskStatus.TAKEN, TaskStatus.IN_PROGRESS, TaskStatus.SUBMITTED,
                      TaskStatus.ACCEPTED, TaskStatus.REJECTED, TaskStatus.COMPLETED):
            executor_id = random.choice(executors).id
            taken_at    = created + timedelta(hours=random.randint(1, 24))

        if status in (TaskStatus.IN_PROGRESS, TaskStatus.SUBMITTED,
                      TaskStatus.ACCEPTED, TaskStatus.COMPLETED):
            started_at  = taken_at + timedelta(hours=random.randint(1, 8))

        if status in (TaskStatus.SUBMITTED, TaskStatus.ACCEPTED,
                      TaskStatus.REJECTED, TaskStatus.COMPLETED):
            submitted_at = started_at + timedelta(hours=random.randint(1, 12))

        if status == TaskStatus.ACCEPTED:
            accepted_at  = submitted_at + timedelta(hours=random.randint(1, 6))

        if status == TaskStatus.COMPLETED:
            accepted_at  = submitted_at + timedelta(hours=random.randint(1, 6))
            completed_at = accepted_at  + timedelta(hours=random.randint(1, 24))

        if status == TaskStatus.REJECTED:
            rejected_at      = submitted_at + timedelta(hours=random.randint(1, 4))
            rejection_reason = random.choice([
                "Фотоотчёт не соответствует объёму работ",
                "Задание выполнено не в полном объёме",
                "Требуется повторная уборка — остались загрязнения",
                "Ценники расставлены некорректно",
            ])

        # Дедлайн — через 1-7 дней после создания
        deadline = (created + timedelta(days=random.randint(1, 7))).date()

        t = Task(
            store_id         = store["id"],
            created_by_id    = sd_user.id,
            executor_id      = executor_id,
            title            = title,
            category         = category,
            status           = status,
            amount           = amount,
            deadline         = deadline,
            description      = f"Задание #{idx+1:03d} — {title}. Магазин: {store['name']}.",
            created_at       = created,
            taken_at         = taken_at,
            started_at       = started_at,
            submitted_at     = submitted_at,
            accepted_at      = accepted_at,
            completed_at     = completed_at,
            rejected_at      = rejected_at,
            rejection_reason = rejection_reason,
        )
        session.add(t)
        tasks.append(t)

    print(f"  ✅ Заданий создано: {len(tasks)}")
    print(f"     Завершено: 30 | Принято: 8 | Сдано: 7 | В работе: 10")
    print(f"     Взято: 8 | Опубликовано: 12 | Отклонено: 5 | Прочие: 5")

    await session.flush()
    return tasks


# =============================================================================
# СОЗДАНИЕ ВЫПЛАТ
# =============================================================================

async def create_payments(session, tasks: list, users: dict) -> list:
    """
    Создаёт выплаты для завершённых и принятых заданий.
    Добавляет чеки ФНС к завершённым выплатам (один — аннулирован).
    """
    payments = []
    receipts = []

    accepted_tasks = [t for t in tasks if t.status in (TaskStatus.COMPLETED, TaskStatus.ACCEPTED)]

    for idx, task in enumerate(accepted_tasks):
        random.seed(900 + idx)

        if task.status == TaskStatus.COMPLETED:
            p_status = PaymentStatus.COMPLETED
        else:
            p_status = random.choice([PaymentStatus.PENDING, PaymentStatus.PROCESSING])

        paid_at = None
        if p_status == PaymentStatus.COMPLETED:
            paid_at = task.completed_at + timedelta(hours=random.randint(2, 48))

        # Налог 6% оплачивает KARI
        tax_amount = round(float(task.amount) * 0.06, 2)

        p = Payment(
            task_id          = task.id,
            executor_id      = task.executor_id,
            amount           = task.amount,
            tax_amount       = Decimal(str(tax_amount)),
            status           = p_status,
            created_at       = task.accepted_at or task.created_at,
            paid_at          = paid_at,
            sovcombank_ref   = f"SCB-{uuid.uuid4().hex[:10].upper()}" if p_status == PaymentStatus.COMPLETED else None,
        )
        session.add(p)
        payments.append(p)

        # Чеки ФНС для завершённых выплат
        if p_status == PaymentStatus.COMPLETED:
            # Один чек аннулируем (первый из завершённых)
            r_status = FnsReceiptStatus.CANCELLED if idx == 0 else FnsReceiptStatus.CREATED
            r = FnsReceipt(
                payment_id     = p.id,
                executor_id    = task.executor_id,
                amount         = task.amount,
                receipt_uuid   = str(uuid.uuid4()),
                receipt_number = f"ФНС-2026-{idx+1:05d}",
                status         = r_status,
                issued_at      = paid_at,
                cancelled_at   = paid_at + timedelta(days=3) if r_status == FnsReceiptStatus.CANCELLED else None,
            )
            session.add(r)
            receipts.append(r)

    print(f"  ✅ Выплат создано: {len(payments)}")
    print(f"     Завершено: {sum(1 for p in payments if p.status == PaymentStatus.COMPLETED)}")
    print(f"     В обработке/ожидании: {sum(1 for p in payments if p.status != PaymentStatus.COMPLETED)}")
    print(f"  ✅ Чеков ФНС: {len(receipts)} (1 аннулирован)")

    return payments


# =============================================================================
# ОСНОВНАЯ ФУНКЦИЯ
# =============================================================================

async def seed():
    print("\n" + "="*65)
    print("  KARI.Самозанятые — Заполнение БД тестовыми данными")
    print("="*65)

    async with engine.begin() as conn:
        print("\n📦 Создаём таблицы (если не существуют)...")
        await conn.run_sync(Base.metadata.create_all)
        print("  ✅ Таблицы готовы")

    async with AsyncSessionLocal() as session:
        # Проверим — может уже что-то есть
        result = await session.execute(text("SELECT COUNT(*) FROM users"))
        count  = result.scalar()
        if count and count > 0:
            print(f"\n⚠️  В БД уже есть {count} пользователей.")
            answer = input("   Очистить и заполнить заново? [y/N]: ").strip().lower()
            if answer != "y":
                print("❌ Отменено.")
                return
            # Очистка в правильном порядке (из-за FK)
            await session.execute(text("TRUNCATE fns_receipts, payments, tasks, users RESTART IDENTITY CASCADE"))
            await session.commit()
            print("  ✅ Таблицы очищены")

        print("\n👥 Создаём пользователей...")
        users = await create_users(session)

        print("\n📋 Создаём задания...")
        tasks = await create_tasks(session, users)

        print("\n💰 Создаём выплаты и чеки ФНС...")
        await create_payments(session, tasks, users)

        await session.commit()
        print("\n✅ Данные сохранены в БД!")

    print("\n" + "="*65)
    print("  Данные для входа в систему:")
    print("="*65)
    print("  Директор региона:       +79991000001")
    print("  HRD:                    +79991000002")
    print("  Директор подразд. 1:    +79991000010  (Иркутск Центр)")
    print("  Директор подразд. 2:    +79991000011  (Иркутск Запад)")
    print("  Директор подразд. 3:    +79991000012  (Иркутск Север)")
    print("  Директор магазина 1:    +79991002000")
    print("  Исполнитель 1:          +79992000000")
    print("  (SMS-код любой в режиме DEBUG)")
    print("="*65 + "\n")


if __name__ == "__main__":
    asyncio.run(seed())
