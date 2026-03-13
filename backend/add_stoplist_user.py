"""
=============================================================================
KARI.Самозанятые — Добавление тестового пользователя в стоп-лист
=============================================================================
Запуск:
    cd 04_Разработка/backend
    python add_stoplist_user.py

Что делает:
    1. Создаёт исполнителя +70000000006 (Козлов Иван Стоплист)
       БЕЗ ИНН — онбординг обязателен
    2. Добавляет ИНН 381000000006 в стоп-лист (бывший сотрудник KARI)

Путь тестирования (в мобильном приложении):
    ① Войти: +70000000006 (любой 6-значный код)
    ② Онбординг шаг 1: ввести ФИО (например: Козлов Иван Стоплист)
    ③ Онбординг шаг 2: ввести ИНН 381000000006 → ФНС вернёт "активен" (режим DEBUG)
    ④ Кнопка "Начать работать" → переход в главный экран
    ⑤ Биржа заданий → выбрать любое задание → нажать "Взять задание"
    ⑥ Система вернёт ошибку STOP_LIST_BLOCKED → откроется экран StopListBlockedScreen
=============================================================================
"""

import asyncio
import sys
import os
from datetime import date

# Добавляем корневую папку backend в путь
sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy import text, select
from app.database import engine, AsyncSessionLocal, Base
from app.models.user import User, UserRole, UserStatus, FnsStatus
from app.models.stop_list import StopList, StopListReason


# =============================================================================
# ДАННЫЕ ТЕСТОВОГО ПОЛЬЗОВАТЕЛЯ
# =============================================================================

# Телефон — следующий после +70000000005
TEST_PHONE    = "+70000000006"
TEST_NAME     = "Козлов Иван Стоплист"   # узнаваемое имя для тестов
TEST_ROLE     = UserRole.EXECUTOR
TEST_STATUS   = UserStatus.ACTIVE
TEST_FNS      = FnsStatus.ACTIVE

# ИНН который нужно ввести при онбординге
# Этот же ИНН будет в стоп-листе — задание взять не получится
STOP_INN      = "381000000006"

# Данные записи стоп-листа
STOP_REASON        = StopListReason.FORMER_EMPLOYEE   # Бывший сотрудник KARI
STOP_END_DATE      = date(2026, 3, 10)                 # Дата увольнения (сегодня)
STOP_BLOCKED_UNTIL = date(2028, 3, 1)                  # Блокировка до (2 года вперёд)
STOP_DETAILS       = (
    "Уволен 10.03.2026. По 422-ФЗ ст.6 п.2 пп.8 — двухлетний запрет "
    "на работу с бывшим работодателем как самозанятый. "
    "Приказ об увольнении №КА-0142/2026."
)


# =============================================================================
# ОСНОВНАЯ ФУНКЦИЯ
# =============================================================================

async def add_stoplist_user():
    print("\n" + "="*65)
    print("  KARI — Добавление тестового пользователя в стоп-лист")
    print("="*65)

    async with AsyncSessionLocal() as session:

        # ──────────────────────────────────────────────────────────────────
        # 1. Проверяем — может пользователь уже существует
        # ──────────────────────────────────────────────────────────────────
        existing = await session.execute(
            select(User).where(User.phone == TEST_PHONE)
        )
        user = existing.scalar_one_or_none()

        if user:
            print(f"\n⚠️  Пользователь {TEST_PHONE} уже существует.")
            print(f"   ID:     {user.id}")
            print(f"   Имя:    {user.full_name}")
            print(f"   ИНН:    {user.inn or '(не задан)'}")
            print(f"   Статус: {user.status}")
        else:
            # Создаём нового исполнителя
            user = User(
                phone      = TEST_PHONE,
                full_name  = TEST_NAME,
                role       = TEST_ROLE,
                status     = TEST_STATUS,
                fns_status = TEST_FNS,
                # inn оставляем пустым — онбординг будет нужен
            )
            session.add(user)
            await session.flush()  # получаем user.id
            print(f"\n✅ Создан исполнитель:")
            print(f"   Телефон: {TEST_PHONE}")
            print(f"   Имя:     {TEST_NAME}")
            print(f"   ИНН:     (пустой — нужен онбординг)")
            print(f"   ID:      {user.id}")

        # ──────────────────────────────────────────────────────────────────
        # 2. Проверяем — есть ли уже запись в стоп-листе с этим ИНН
        # ──────────────────────────────────────────────────────────────────
        existing_stop = await session.execute(
            select(StopList).where(StopList.inn == STOP_INN)
        )
        stop_entry = existing_stop.scalar_one_or_none()

        if stop_entry:
            print(f"\n⚠️  В стоп-листе уже есть запись с ИНН {STOP_INN}.")
            print(f"   Причина:        {stop_entry.reason}")
            print(f"   Активна:        {stop_entry.is_active}")
            print(f"   Заблокирован до: {stop_entry.blocked_until or 'бессрочно'}")
        else:
            # Добавляем запись в стоп-лист
            stop_entry = StopList(
                inn                = STOP_INN,
                full_name          = TEST_NAME,
                reason             = STOP_REASON,
                reason_details     = STOP_DETAILS,
                employment_end_date = STOP_END_DATE,
                blocked_until      = STOP_BLOCKED_UNTIL,
                is_active          = True,
                created_by_id      = None,  # NULL = системное добавление
            )
            session.add(stop_entry)
            print(f"\n✅ Добавлена запись в стоп-лист:")
            print(f"   ИНН:             {STOP_INN}")
            print(f"   Причина:         Бывший сотрудник KARI (422-ФЗ)")
            print(f"   Уволен:          {STOP_END_DATE}")
            print(f"   Заблокирован до: {STOP_BLOCKED_UNTIL}")

        # ──────────────────────────────────────────────────────────────────
        # 3. Сохраняем всё в БД
        # ──────────────────────────────────────────────────────────────────
        await session.commit()
        print("\n✅ Данные сохранены в БД!")

    # ──────────────────────────────────────────────────────────────────────
    # Инструкции для тестирования
    # ──────────────────────────────────────────────────────────────────────
    print("\n" + "="*65)
    print("  КАК ПРОТЕСТИРОВАТЬ СТОП-ЛИСТ В ПРИЛОЖЕНИИ:")
    print("="*65)
    print()
    print("  1. Открыть приложение KARI")
    print(f"  2. Войти с номером: {TEST_PHONE}")
    print("     Код придёт автоматически (режим DEBUG)")
    print()
    print("  3. Онбординг — Шаг 1 «Как вас зовут?»:")
    print(f"     Фамилия:  Козлов")
    print(f"     Имя:      Иван")
    print(f"     Отчество: Стоплист  (или любое)")
    print()
    print("  4. Онбординг — Шаг 2 «Ваш ИНН»:")
    print(f"     ИНН:  {STOP_INN}  ← ВАЖНО! Именно этот ИНН!")
    print("     ФНС вернёт «активен» (тестовый режим)")
    print()
    print("  5. Нажать «Начать работать» → попасть в главный экран")
    print()
    print("  6. Перейти на вкладку «Биржа заданий»")
    print("     Выбрать любое задание → нажать «Взять задание»")
    print()
    print("  7. ✅ Откроется экран СТОП-ЛИСТА с текстом:")
    print("     «По закону 422-ФЗ вы не можете получать задания")
    print("      от бывшего работодателя в течение 2 лет...»")
    print()
    print("  Альтернативы на экране стоп-листа:")
    print("     ① Оформиться в штат KARI")
    print("     ② Принять заказы партнёров")
    print("="*65 + "\n")


if __name__ == "__main__":
    asyncio.run(add_stoplist_user())
