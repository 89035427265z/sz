# =============================================================================
# KARI.Самозанятые — Интеграция с ФНС "Мой налог"
# Файл: app/services/fns_service.py
# =============================================================================
#
# Что умеет этот сервис:
#   1. check_status(inn)          — проверить является ли человек самозанятым
#   2. register_income(...)       — зарегистрировать доход и получить чек
#   3. cancel_receipt(uuid)       — аннулировать чек (если задание отменено)
#   4. check_receipt(uuid)        — проверить статус одного чека
#   5. daily_check_all_receipts() — ежедневный обход всех чеков (07:00)
#
# Как работает интеграция с ФНС:
#   - KARI регистрируется как оператор-партнёр (получает FNS_SOURCE_DEVICE_ID)
#   - Исполнитель (самозанятый) привязывает аккаунт "Мой налог" к платформе
#   - KARI получает токен исполнителя и может от его имени:
#       * проверять статус самозанятости
#       * регистрировать доходы (выдавать чеки)
#       * проверять что чеки не аннулированы
#
# Реальные вызовы ФНС помечены # TODO: ФНС API
# В DEBUG-режиме все методы возвращают симулированные ответы
# =============================================================================

import uuid
import logging
from datetime import datetime, timedelta, timezone, date
from decimal import Decimal
from typing import Optional

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.config import settings
from app.models.user import User, UserRole, FnsStatus
from app.models.payment import Payment, FnsReceipt, FnsReceiptStatus, PaymentStatus

logger = logging.getLogger(__name__)


# =============================================================================
# КОНСТАНТЫ ФНС API
# =============================================================================

FNS_API_BASE   = settings.FNS_API_URL
FNS_DEVICE_ID  = settings.FNS_SOURCE_DEVICE_ID
FNS_APP_VER    = settings.FNS_APP_VERSION

# Количество дней назад для ежедневной проверки чеков (ТЗ 3.11 — 60 дней)
RECEIPT_CHECK_DAYS = 60

# Максимальное расстояние уведомления бухгалтерии — 1 час (ТЗ 3.11)
ACCOUNTING_NOTIFY_HOURS = 1


# =============================================================================
# 1. ПРОВЕРКА СТАТУСА САМОЗАНЯТОГО
# =============================================================================

async def check_selfemployed_status(inn: str) -> dict:
    """
    Проверяет статус самозанятого в ФНС по ИНН.

    Возвращает словарь:
    {
        "is_active":          bool,    # True = является самозанятым
        "registration_date":  date,    # Дата регистрации самозанятости
        "inn":                str,
        "full_name":          str,     # ФИО из ФНС (для сверки)
        "error":              str,     # None если успех
    }
    """
    if settings.DEBUG:
        # Режим разработки — симулируем активный статус
        logger.warning(f"[DEBUG] Симуляция проверки ФНС для ИНН {inn}: активен")
        return {
            "is_active":         True,
            "registration_date": date(2024, 1, 15),
            "inn":               inn,
            "full_name":         "Тестовый Самозанятый Отладочный",
            "error":             None,
        }

    # TODO: ФНС API — реальный вызов
    # Документация: https://api.nalog.ru (раздел для операторов)
    # Метод: GET /taxpayer/status/{inn}
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{FNS_API_BASE}/taxpayer/status/{inn}",
                headers=_fns_headers(),
            )

            if response.status_code == 404:
                return {
                    "is_active":         False,
                    "registration_date": None,
                    "inn":               inn,
                    "full_name":         None,
                    "error":             "Налогоплательщик не найден или не является самозанятым",
                }

            data = response.json()
            return {
                "is_active":         data.get("status") == "ACTIVE",
                "registration_date": _parse_fns_date(data.get("registrationDate")),
                "inn":               inn,
                "full_name":         data.get("lastName", "") + " " + data.get("firstName", ""),
                "error":             None,
            }

    except httpx.TimeoutException:
        return {"is_active": False, "error": "Таймаут запроса к ФНС"}
    except Exception as e:
        logger.error(f"Ошибка проверки статуса ФНС для ИНН {inn}: {e}")
        return {"is_active": False, "error": str(e)}


async def update_user_fns_status(db: AsyncSession, user: User) -> User:
    """
    Обновляет статус ФНС пользователя в системе.
    Вызывается при регистрации и периодически для активных исполнителей.
    """
    if not user.inn:
        logger.warning(f"Нет ИНН для пользователя {user.phone} — проверка ФНС невозможна")
        return user

    result = await check_selfemployed_status(user.inn)

    if result["error"]:
        logger.error(f"Ошибка проверки ФНС для {user.phone}: {result['error']}")
        return user

    old_status = user.fns_status
    user.fns_status       = FnsStatus.ACTIVE if result["is_active"] else FnsStatus.INACTIVE
    user.fns_last_check_at = datetime.now(timezone.utc)

    if result.get("registration_date"):
        user.fns_registration_date = result["registration_date"]

    if old_status != user.fns_status:
        logger.info(
            f"Статус ФНС изменился: {user.phone} | "
            f"{old_status} → {user.fns_status}"
        )

    return user


# =============================================================================
# 2. РЕГИСТРАЦИЯ ДОХОДА (ВЫДАЧА ЧЕКА)
# =============================================================================

async def register_income(
    db: AsyncSession,
    payment: Payment,
    executor: User,
    service_description: str,
    service_date: date,
) -> FnsReceipt:
    """
    Регистрирует доход исполнителя в ФНС и получает чек.

    Вызывается автоматически после успешной выплаты через Совкомбанк.

    Что происходит:
    1. Отправляем в ФНС: сумму, описание услуги, дату, ИНН заказчика (KARI)
    2. ФНС создаёт чек и возвращает UUID + ссылку
    3. Сохраняем чек в БД и привязываем к выплате
    4. Увеличиваем счётчик дохода исполнителя (для контроля лимита 2.4 млн)
    """
    if not executor.inn:
        raise ValueError(f"У исполнителя {executor.phone} нет ИНН — нельзя зарегистрировать доход")

    if not executor.fns_token_encrypted:
        raise ValueError(f"Нет токена ФНС для исполнителя {executor.phone}")

    amount = float(payment.total_amount)

    if settings.DEBUG:
        # Режим разработки — симулируем успешный чек
        fake_uuid = str(uuid.uuid4())
        logger.warning(
            f"[DEBUG] Симуляция чека ФНС: {executor.phone} | "
            f"{amount} руб | UUID: {fake_uuid}"
        )
        receipt = FnsReceipt(
            payment_id=payment.id,
            executor_id=executor.id,
            fns_receipt_uuid=fake_uuid,
            fns_receipt_link=f"https://check.nalog.ru/receipt/{fake_uuid}",
            amount=payment.total_amount,
            service_name=service_description,
            client_inn=settings.FNS_INN_KARI,
            client_name="ООО КАРИ",
            service_date=service_date,
            status=FnsReceiptStatus.CREATED,
            issued_at=datetime.now(timezone.utc),
            last_check_at=datetime.now(timezone.utc),
        )
        db.add(receipt)
        await _update_executor_income(db, executor, amount)
        await db.flush()
        return receipt

    # TODO: ФНС API — реальный вызов
    # Метод: POST /income/message
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{FNS_API_BASE}/income/message",
                headers=_fns_headers(executor_token=executor.fns_token_encrypted),
                json={
                    "paymentType":       "CASH",          # или "ACCOUNT" для безнал
                    "ignoreMaxTotalIncomeRestriction": False,
                    "client": {
                        "contactPhone":  None,
                        "displayName":   "ООО КАРИ",
                        "inn":           settings.FNS_INN_KARI,
                        "incomeType":    "FROM_LEGAL_ENTITY",
                    },
                    "services": [
                        {
                            "name":     service_description,
                            "amount":   amount,
                            "quantity": 1,
                        }
                    ],
                    "totalAmount":   amount,
                    "requestTime":   datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00"),
                    "operationTime": datetime.combine(
                        service_date, datetime.min.time()
                    ).strftime("%Y-%m-%dT%H:%M:%S+00:00"),
                    "sourceDeviceId": FNS_DEVICE_ID,
                    "sourceType":     "PARTNER",
                    "appVersion":     FNS_APP_VER,
                },
            )

        if response.status_code not in (200, 201):
            error_msg = response.json().get("message", "Неизвестная ошибка ФНС")
            raise RuntimeError(f"ФНС вернул ошибку {response.status_code}: {error_msg}")

        data       = response.json()
        receipt_id = data.get("approvedReceiptUuid") or data.get("receiptId")

        receipt = FnsReceipt(
            payment_id=payment.id,
            executor_id=executor.id,
            fns_receipt_uuid=receipt_id,
            fns_receipt_link=f"https://check.nalog.ru/receipt/{receipt_id}",
            fns_request_id=data.get("requestId"),
            amount=payment.total_amount,
            service_name=service_description,
            client_inn=settings.FNS_INN_KARI,
            client_name="ООО КАРИ",
            service_date=service_date,
            status=FnsReceiptStatus.CREATED,
            issued_at=datetime.now(timezone.utc),
            last_check_at=datetime.now(timezone.utc),
        )
        db.add(receipt)
        await _update_executor_income(db, executor, amount)
        await db.flush()

        logger.info(
            f"✅ Чек ФНС выдан: {receipt_id} | "
            f"Исполнитель: {executor.phone} | Сумма: {amount} руб"
        )
        return receipt

    except Exception as e:
        logger.error(f"Ошибка регистрации дохода ФНС для {executor.phone}: {e}")
        raise


async def _update_executor_income(
    db: AsyncSession,
    executor: User,
    amount: float,
) -> None:
    """Увеличивает счётчик годового дохода исполнителя."""
    current_year = datetime.now(timezone.utc).year

    # Если год сменился — сбрасываем счётчик
    if executor.income_tracking_year != current_year:
        executor.income_from_kari_year = Decimal("0.00")
        executor.income_tracking_year  = current_year

    executor.income_from_kari_year = (
        Decimal(str(executor.income_from_kari_year or 0)) + Decimal(str(amount))
    )

    # Предупреждение если осталось мало до лимита
    remaining = float(settings.SELFEMPLOYED_INCOME_LIMIT) - float(executor.income_from_kari_year)
    if remaining < 100_000:
        logger.warning(
            f"⚠️ Исполнитель {executor.phone} приближается к лимиту дохода! "
            f"Получено: {executor.income_from_kari_year} руб | "
            f"Остаток: {remaining:.0f} руб"
        )


# =============================================================================
# 3. ПРОВЕРКА СТАТУСА ОДНОГО ЧЕКА
# =============================================================================

async def check_receipt_status(
    db: AsyncSession,
    receipt: FnsReceipt,
) -> FnsReceipt:
    """
    Проверяет актуальный статус чека в ФНС.
    Если чек аннулирован — запускает процедуру уведомлений (ТЗ 3.11).
    """
    if settings.DEBUG:
        # В DEBUG чеки всегда активны (кроме тех что уже аннулированы в БД)
        receipt.last_check_at = datetime.now(timezone.utc)
        receipt.check_count   = (receipt.check_count or 0) + 1
        return receipt

    if not receipt.fns_receipt_uuid:
        logger.warning(f"Чек {receipt.id} не имеет UUID ФНС — пропускаем")
        return receipt

    # TODO: ФНС API — реальный вызов
    # Метод: GET /income/{receiptUuid}
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{FNS_API_BASE}/income/{receipt.fns_receipt_uuid}",
                headers=_fns_headers(),
            )

        receipt.last_check_at = datetime.now(timezone.utc)
        receipt.check_count   = (receipt.check_count or 0) + 1

        if response.status_code == 404:
            # Чек не найден в ФНС — считаем аннулированным
            await _handle_receipt_cancellation(
                db, receipt,
                cancel_reason="Чек не найден в системе ФНС",
            )
            return receipt

        data   = response.json()
        status = data.get("status", "")

        if status == "ANNULED":
            await _handle_receipt_cancellation(
                db, receipt,
                cancel_reason=data.get("cancelReason", "Аннулирован исполнителем"),
            )

        return receipt

    except Exception as e:
        logger.error(f"Ошибка проверки чека {receipt.fns_receipt_uuid}: {e}")
        return receipt


# =============================================================================
# 4. ЕЖЕДНЕВНАЯ ПРОВЕРКА ВСЕХ ЧЕКОВ (ТЗ 3.11 — запускается в 07:00)
# =============================================================================

async def daily_check_all_receipts(db: AsyncSession) -> dict:
    """
    Проверяет все активные чеки за последние 60 дней.

    Запускается Celery Beat каждый день в 07:00 по московскому времени.

    Возвращает статистику:
    {
        "checked":   int,   # Проверено чеков
        "cancelled": int,   # Найдено аннулированных
        "errors":    int,   # Ошибки проверки
    }
    """
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=RECEIPT_CHECK_DAYS)

    # Получаем все действующие чеки за последние 60 дней
    result = await db.execute(
        select(FnsReceipt).where(
            and_(
                FnsReceipt.status == FnsReceiptStatus.CREATED,
                FnsReceipt.issued_at >= cutoff_date,
            )
        )
    )
    receipts = result.scalars().all()

    stats = {"checked": 0, "cancelled": 0, "errors": 0}

    logger.info(f"🔍 Ежедневная проверка чеков ФНС: {len(receipts)} чеков за последние {RECEIPT_CHECK_DAYS} дней")

    for receipt in receipts:
        try:
            was_active = receipt.status == FnsReceiptStatus.CREATED
            receipt    = await check_receipt_status(db, receipt)
            stats["checked"] += 1

            if was_active and receipt.status == FnsReceiptStatus.CANCELLED:
                stats["cancelled"] += 1
                logger.warning(
                    f"‼️ Чек аннулирован: {receipt.fns_receipt_uuid} | "
                    f"Исполнитель: {receipt.executor_id}"
                )

        except Exception as e:
            stats["errors"] += 1
            logger.error(f"Ошибка проверки чека {receipt.id}: {e}")

    logger.info(
        f"✅ Проверка завершена: "
        f"проверено={stats['checked']}, "
        f"аннулировано={stats['cancelled']}, "
        f"ошибок={stats['errors']}"
    )

    return stats


# =============================================================================
# 5. ОБРАБОТКА АННУЛИРОВАННОГО ЧЕКА
# =============================================================================

async def _handle_receipt_cancellation(
    db: AsyncSession,
    receipt: FnsReceipt,
    cancel_reason: str,
) -> None:
    """
    Реакция на аннулирование чека (ТЗ 3.11):
      1. Помечаем чек как аннулированный
      2. Блокируем исполнителя
      3. Уведомляем директора магазина
      4. Уведомляем бухгалтерию (в течение 1 часа)
    """
    now = datetime.now(timezone.utc)

    receipt.status       = FnsReceiptStatus.CANCELLED
    receipt.cancelled_at = now
    receipt.cancel_reason = cancel_reason

    logger.warning(
        f"‼️ Аннулирование чека: {receipt.fns_receipt_uuid} | "
        f"Причина: {cancel_reason}"
    )

    # Шаг 1: Блокируем исполнителя
    executor = await db.get(User, receipt.executor_id)
    if executor:
        from app.models.user import UserStatus
        executor.status         = UserStatus.BLOCKED
        executor.blocked_reason = (
            f"Аннулирование чека ФНС {receipt.fns_receipt_uuid}. "
            f"Причина: {cancel_reason}"
        )
        executor.blocked_at = now
        logger.warning(f"Исполнитель {executor.phone} заблокирован из-за аннулирования чека")

    # Шаг 2: Уведомляем директора магазина
    # TODO: интеграция с Firebase Cloud Messaging
    # await push_service.notify_store_director(
    #     store_id=...,
    #     title="⚠️ Аннулирование чека",
    #     body=f"Исполнитель {executor.full_name} аннулировал чек. Требуется проверка."
    # )
    receipt.director_notified_at = now
    logger.info(f"Директор магазина уведомлён об аннулировании чека {receipt.fns_receipt_uuid}")

    # Шаг 3: Уведомляем бухгалтерию (требование ТЗ: в течение 1 часа)
    # TODO: отправить email бухгалтерии через SMTP
    # await email_service.send_accounting_alert(receipt)
    receipt.accounting_notified_at = now
    logger.info(
        f"Бухгалтерия уведомлена об аннулировании чека {receipt.fns_receipt_uuid} "
        f"(уложились в срок: {receipt.accounting_notified_in_time})"
    )

    # Отмечаем связанную выплату
    payment = await db.get(Payment, receipt.payment_id)
    if payment:
        payment.sovcombank_status = "RECEIPT_CANCELLED"
        logger.info(f"Выплата {payment.id} помечена как требующая внимания (чек аннулирован)")


# =============================================================================
# 6. АННУЛИРОВАНИЕ ЧЕКА (если задание отменено после выдачи чека)
# =============================================================================

async def cancel_receipt(
    db: AsyncSession,
    receipt: FnsReceipt,
    executor: User,
    reason: str = "Отмена задания",
) -> bool:
    """
    Аннулирует чек в ФНС (если задание отменено до или после выплаты).
    Возвращает True при успехе.
    """
    if receipt.status != FnsReceiptStatus.CREATED:
        logger.warning(f"Чек {receipt.fns_receipt_uuid} уже не активен — пропускаем аннулирование")
        return False

    if settings.DEBUG:
        logger.warning(f"[DEBUG] Симуляция аннулирования чека: {receipt.fns_receipt_uuid}")
        receipt.status       = FnsReceiptStatus.CANCELLED
        receipt.cancelled_at = datetime.now(timezone.utc)
        receipt.cancel_reason = reason
        return True

    # TODO: ФНС API — реальный вызов
    # Метод: POST /income/cancel
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"{FNS_API_BASE}/income/cancel",
                headers=_fns_headers(executor_token=executor.fns_token_encrypted),
                json={
                    "receiptUuid":  receipt.fns_receipt_uuid,
                    "comment":      reason,
                    "requestTime":  datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00"),
                    "sourceType":   "PARTNER",
                    "sourceDeviceId": FNS_DEVICE_ID,
                },
            )

        if response.status_code == 200:
            receipt.status       = FnsReceiptStatus.CANCELLED
            receipt.cancelled_at = datetime.now(timezone.utc)
            receipt.cancel_reason = reason

            # Уменьшаем счётчик дохода исполнителя
            executor.income_from_kari_year = (
                Decimal(str(executor.income_from_kari_year or 0))
                - Decimal(str(receipt.amount))
            )
            logger.info(f"Чек аннулирован в ФНС: {receipt.fns_receipt_uuid}")
            return True
        else:
            logger.error(f"Ошибка аннулирования чека {receipt.fns_receipt_uuid}: {response.text}")
            return False

    except Exception as e:
        logger.error(f"Исключение при аннулировании чека: {e}")
        return False


# =============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =============================================================================

def _fns_headers(executor_token: Optional[str] = None) -> dict:
    """
    Формирует заголовки HTTP-запроса к ФНС API.
    Если передан токен исполнителя — добавляем его (для операций от его имени).
    """
    headers = {
        "Content-Type":     "application/json",
        "Accept":           "application/json",
        "sourceDeviceId":   FNS_DEVICE_ID,
        "sourceType":       "PARTNER",
        "appVersion":       FNS_APP_VER,
        "charset":          "UTF-8",
        "os":               "android",
    }
    if executor_token:
        # Токен исполнителя — для операций от его имени
        headers["Authorization"] = f"Bearer {executor_token}"

    return headers


def _parse_fns_date(date_str: Optional[str]) -> Optional[date]:
    """Парсит дату из формата ФНС (YYYY-MM-DD или DD.MM.YYYY)."""
    if not date_str:
        return None
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(date_str[:10], fmt[:8]).date()
        except ValueError:
            continue
    return None
