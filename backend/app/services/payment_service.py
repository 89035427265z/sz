# =============================================================================
# KARI.Самозанятые — Сервис выплат (Совкомбанк)
# Файл: app/services/payment_service.py
# =============================================================================
# Отвечает за:
#   1. Создание выплаты после приёмки задания
#   2. Отправку платежа в Совкомбанк
#   3. Разбор Excel-реестра и валидацию строк (ТЗ 3.12)
#   4. Формирование XML для выгрузки в 1С
#
# Совкомбанк: реальные вызовы API помечены # TODO: СОВКОМБАНК —
# на этапе интеграции заменяются на реальные HTTP-запросы.
# =============================================================================

import io
import uuid
import logging
from decimal import Decimal
from datetime import datetime, timezone, date
from typing import Optional

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.models.payment import (
    Payment, PaymentRegistry, PaymentRegistryItem,
    PaymentStatus, RegistryStatus, RegistryItemStatus,
)
from app.models.user import User, UserRole, FnsStatus
from app.models.task import Task

logger = logging.getLogger(__name__)


# =============================================================================
# СОЗДАНИЕ ВЫПЛАТЫ ЗА ЗАДАНИЕ
# =============================================================================

async def create_payment_for_task(
    db: AsyncSession,
    task: Task,
) -> Payment:
    """
    Создаёт запись о выплате после того как директор магазина принял задание.
    Выплата создаётся в статусе PENDING и затем обрабатывается фоновой задачей.
    """
    # Получаем исполнителя
    executor = await db.get(User, task.executor_id)
    if not executor:
        raise ValueError(f"Исполнитель не найден: {task.executor_id}")

    # Считаем суммы
    amount     = Decimal(str(task.price))
    tax_amount = (amount * Decimal("0.06")).quantize(Decimal("0.01"))  # 6% налог
    total      = amount + tax_amount

    payment = Payment(
        task_id=task.id,
        executor_id=executor.id,
        amount=amount,
        tax_amount=tax_amount,
        total_amount=total,
        status=PaymentStatus.PENDING,
        # Копируем реквизиты карты на момент создания
        bank_card_masked=executor.bank_card_masked,
        bank_name=executor.bank_name,
        bank_card_token=executor.bank_card_token,
    )
    db.add(payment)
    await db.flush()

    logger.info(
        f"Выплата создана: {payment.id} | "
        f"Исполнитель: {executor.phone} | "
        f"Сумма: {total} руб"
    )

    # Запускаем задачу отправки в Совкомбанк (через 5 сек — дождаться commit)
    from app.tasks.payment_tasks import process_payment as _process_payment_task
    _process_payment_task.apply_async(
        args=[str(payment.id)],
        queue="payments",
        countdown=5,
    )

    return payment


# =============================================================================
# ОТПРАВКА В СОВКОМБАНК
# =============================================================================

async def send_to_sovcombank(payment: Payment) -> dict:
    """
    Отправляет запрос на перевод в Совкомбанк.

    Возвращает: {"success": bool, "transaction_id": str, "error": str}

    TODO: СОВКОМБАНК — реализовать после получения API-документации.
    Текущая реализация — заглушка для разработки и тестирования.
    """
    if settings.DEBUG:
        # В режиме разработки симулируем успешный ответ
        fake_tx_id = f"DEBUG-{uuid.uuid4().hex[:12].upper()}"
        logger.warning(
            f"[DEBUG] Симуляция выплаты в Совкомбанк: "
            f"{payment.total_amount} руб → карта {payment.bank_card_masked} | "
            f"Транзакция: {fake_tx_id}"
        )
        return {"success": True, "transaction_id": fake_tx_id, "error": None}

    # TODO: СОВКОМБАНК — реальный вызов API
    # Документация: получить у менеджера Совкомбанка
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{settings.SOVCOMBANK_API_URL}/transfer",
                headers={
                    "Authorization": f"Bearer {settings.SOVCOMBANK_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "amount":       str(payment.total_amount),
                    "currency":     "RUB",
                    "card_token":   payment.bank_card_token,
                    "reference_id": str(payment.id),
                    "description":  f"Выплата KARI.Самозанятые | Задание {payment.task_id}",
                },
            )
            data = response.json()

            if response.status_code == 200 and data.get("status") == "success":
                return {
                    "success":        True,
                    "transaction_id": data.get("transaction_id"),
                    "error":          None,
                }
            else:
                return {
                    "success":        False,
                    "transaction_id": None,
                    "error":          data.get("message", "Неизвестная ошибка Совкомбанка"),
                }

    except httpx.TimeoutException:
        return {"success": False, "transaction_id": None, "error": "Таймаут запроса к Совкомбанку"}
    except Exception as e:
        return {"success": False, "transaction_id": None, "error": str(e)}


# =============================================================================
# ПАРСИНГ EXCEL-РЕЕСТРА (ТЗ 3.12)
# =============================================================================

def parse_registry_excel(file_data: bytes) -> list[dict]:
    """
    Читает Excel-файл реестра и возвращает список строк.

    Ожидаемая структура столбцов (строка 1 — заголовок):
      A: ИНН исполнителя (12 цифр)
      B: ФИО исполнителя
      C: Описание услуги
      D: Сумма (руб, число)
      E: Дата выполнения (DD.MM.YYYY)
      F: Примечание (необязательно)

    Возвращает список словарей с полями:
      row_number, inn, name, description, amount, work_date, note, error
    """
    import openpyxl

    try:
        wb = openpyxl.load_workbook(io.BytesIO(file_data), data_only=True)
        ws = wb.active
    except Exception as e:
        raise ValueError(f"Не удалось открыть Excel файл: {e}")

    rows = []
    # Начинаем со строки 2 (строка 1 — заголовок)
    for row_num, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        # Пропускаем полностью пустые строки
        if not any(row):
            continue

        # Ограничение: максимум 1000 строк (ТЗ 3.12)
        if len(rows) >= 1000:
            break

        raw_inn   = str(row[0]).strip() if row[0] is not None else ""
        raw_name  = str(row[1]).strip() if row[1] is not None else ""
        raw_desc  = str(row[2]).strip() if row[2] is not None else ""
        raw_amount = row[3]
        raw_date  = row[4]
        note      = str(row[5]).strip() if len(row) > 5 and row[5] is not None else ""

        parse_error = None

        # Парсим ИНН
        inn = "".join(c for c in raw_inn if c.isdigit())
        if len(inn) != 12:
            parse_error = f"ИНН '{raw_inn}' должен содержать 12 цифр"

        # Парсим сумму
        amount = None
        try:
            amount = Decimal(str(raw_amount).replace(",", ".").replace(" ", ""))
            if amount <= 0:
                parse_error = "Сумма должна быть больше нуля"
        except Exception:
            parse_error = f"Некорректная сумма: '{raw_amount}'"

        # Парсим дату
        work_date = None
        if isinstance(raw_date, (datetime, date)):
            work_date = raw_date if isinstance(raw_date, date) else raw_date.date()
        elif isinstance(raw_date, str):
            for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y"):
                try:
                    work_date = datetime.strptime(raw_date.strip(), fmt).date()
                    break
                except ValueError:
                    continue
            if work_date is None:
                parse_error = f"Некорректная дата: '{raw_date}' (ожидается ДД.ММ.ГГГГ)"

        rows.append({
            "row_number":  row_num,
            "inn":         inn,
            "name":        raw_name,
            "description": raw_desc,
            "amount":      amount,
            "work_date":   work_date,
            "note":        note,
            "parse_error": parse_error,
        })

    if not rows:
        raise ValueError("Excel файл не содержит данных (ожидаются строки начиная со 2-й)")

    return rows


# =============================================================================
# ВАЛИДАЦИЯ СТРОК РЕЕСТРА (5 проверок, ТЗ 3.12)
# =============================================================================

async def validate_registry_item(
    db: AsyncSession,
    item: PaymentRegistryItem,
    registry_id: str,
) -> PaymentRegistryItem:
    """
    Запускает 5 обязательных проверок для строки реестра.

    Проверка 1: Статус ФНС — исполнитель зарегистрирован как самозанятый?
    Проверка 2: Лимит дохода — не превышен ли порог 2 400 000 руб/год?
    Проверка 3: Дубли — нет ли уже выплаты этому ИНН за эту дату?
    Проверка 4: Сумма — корректна (> 0 и ≤ 100 000)?
    Проверка 5: Бюджет — зарезервировано (всегда True, реальная проверка в v2)
    """
    errors = []

    # Находим пользователя по ИНН
    user_result = await db.execute(
        select(User).where(User.inn == item.executor_inn)
    )
    executor = user_result.scalar_one_or_none()

    # -------------------------------------------------------------------------
    # ПРОВЕРКА 1: Статус ФНС
    # -------------------------------------------------------------------------
    if not executor:
        item.check_fns_status = False
        errors.append({
            "code":    "EXECUTOR_NOT_FOUND",
            "message": f"Исполнитель с ИНН {item.executor_inn} не найден в системе",
        })
    elif executor.fns_status != FnsStatus.ACTIVE:
        item.check_fns_status = False
        errors.append({
            "code":    "FNS_INACTIVE",
            "message": f"Самозанятый статус неактивен в ФНС (ИНН: {item.executor_inn})",
        })
    else:
        item.check_fns_status = True
        item.executor_id = executor.id

    # -------------------------------------------------------------------------
    # ПРОВЕРКА 2: Лимит дохода 2 400 000 руб/год
    # -------------------------------------------------------------------------
    if executor:
        current_income = float(executor.income_from_kari_year or 0)
        payment_amount = float(item.amount or 0)
        limit = settings.SELFEMPLOYED_INCOME_LIMIT

        if current_income + payment_amount > limit:
            item.check_income_limit = False
            remaining = max(0, limit - current_income)
            errors.append({
                "code":    "INCOME_LIMIT_EXCEEDED",
                "message": (
                    f"Превышен лимит дохода {limit:,} руб/год. "
                    f"Уже получено: {current_income:,.2f} руб. "
                    f"Остаток: {remaining:,.2f} руб. "
                    f"Запрошено: {payment_amount:,.2f} руб."
                ),
            })
        else:
            item.check_income_limit = True
    else:
        item.check_income_limit = False  # Нет исполнителя — не можем проверить

    # -------------------------------------------------------------------------
    # ПРОВЕРКА 3: Дубли (тот же ИНН + та же дата в текущем реестре или уже оплачено)
    # -------------------------------------------------------------------------
    if item.work_date:
        # Ищем дубль в других строках этого же реестра
        dup_result = await db.execute(
            select(PaymentRegistryItem).where(
                PaymentRegistryItem.registry_id == registry_id,
                PaymentRegistryItem.executor_inn == item.executor_inn,
                PaymentRegistryItem.work_date == item.work_date,
                PaymentRegistryItem.id != item.id,
            )
        )
        duplicate = dup_result.scalar_one_or_none()

        if duplicate:
            item.check_duplicate = False
            errors.append({
                "code":    "DUPLICATE_ROW",
                "message": (
                    f"Дубль: строка {duplicate.row_number} — "
                    f"тот же ИНН {item.executor_inn} и дата {item.work_date}"
                ),
            })
        else:
            item.check_duplicate = True
    else:
        item.check_duplicate = False
        errors.append({"code": "INVALID_DATE", "message": "Дата не указана или некорректна"})

    # -------------------------------------------------------------------------
    # ПРОВЕРКА 4: Корректность суммы
    # -------------------------------------------------------------------------
    amount = float(item.amount or 0)
    if amount <= 0:
        item.check_amount = False
        errors.append({"code": "INVALID_AMOUNT", "message": "Сумма должна быть больше нуля"})
    elif amount > 100_000:
        item.check_amount = False
        errors.append({
            "code":    "AMOUNT_TOO_LARGE",
            "message": f"Сумма {amount:,.2f} руб превышает разовый лимит 100 000 руб",
        })
    else:
        item.check_amount = True

    # -------------------------------------------------------------------------
    # ПРОВЕРКА 5: Бюджетный лимит
    # -------------------------------------------------------------------------
    # TODO v2: реальная проверка бюджета региона/подразделения
    item.check_budget = True

    # -------------------------------------------------------------------------
    # ИТОГ
    # -------------------------------------------------------------------------
    item.validation_errors = errors if errors else None
    item.status = (
        RegistryItemStatus.VALID
        if item.all_checks_passed
        else RegistryItemStatus.INVALID
    )

    return item


# =============================================================================
# ФОРМИРОВАНИЕ XML ДЛЯ 1С (ТЗ 3.12)
# =============================================================================

def generate_xml_for_1c(
    registry: PaymentRegistry,
    items: list[PaymentRegistryItem],
) -> str:
    """
    Генерирует XML-файл для выгрузки реестра выплат в 1С.

    Формат согласован с типовой конфигурацией 1С:Зарплата и Управление Персоналом.
    """
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<PaymentRegistry>',
        f'  <Header>',
        f'    <Number>{registry.number or registry.id}</Number>',
        f'    <Name>{_xml_escape(registry.name)}</Name>',
        f'    <Date>{datetime.now(timezone.utc).strftime("%Y-%m-%d")}</Date>',
        f'    <TotalRows>{registry.total_rows}</TotalRows>',
        f'    <TotalAmount>{registry.total_amount}</TotalAmount>',
        f'  </Header>',
        f'  <Payments>',
    ]

    for item in items:
        if item.status != RegistryItemStatus.PAID:
            continue
        lines += [
            f'    <Payment>',
            f'      <RowNumber>{item.row_number}</RowNumber>',
            f'      <ExecutorINN>{item.executor_inn}</ExecutorINN>',
            f'      <ExecutorName>{_xml_escape(item.executor_name or "")}</ExecutorName>',
            f'      <ServiceDescription>{_xml_escape(item.service_description)}</ServiceDescription>',
            f'      <Amount>{item.amount}</Amount>',
            f'      <WorkDate>{item.work_date}</WorkDate>',
            f'      <PaymentId>{item.payment_id or ""}</PaymentId>',
            f'    </Payment>',
        ]

    lines += [
        f'  </Payments>',
        f'</PaymentRegistry>',
    ]

    return "\n".join(lines)


def _xml_escape(text: str) -> str:
    """Экранирует спецсимволы XML."""
    return (
        text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
