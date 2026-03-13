# =============================================================================
# KARI.Самозанятые — Celery-задачи выплат
# Файл: app/tasks/payment_tasks.py
# =============================================================================
#
# Задачи:
#   process_payment(payment_id)   — одиночная выплата через Совкомбанк
#   process_registry(registry_id) — пакетная выплата всех строк реестра
#   retry_failed_payments()       — ежедневный повтор неуспешных выплат
#
# Запуск вручную из консоли:
#   celery -A app.tasks.celery_app worker -Q payments --loglevel=info
# =============================================================================

import asyncio
import logging
from datetime import datetime, timezone

from celery import Celery
from sqlalchemy import select

from app.config import settings

logger = logging.getLogger(__name__)

# Celery-приложение (брокер — Redis)
celery_app = Celery(
    "kari_payments",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Europe/Moscow",
    enable_utc=True,
    # Задачи выплат — отдельная очередь с высоким приоритетом
    task_routes={
        "app.tasks.payment_tasks.process_payment":  {"queue": "payments"},
        "app.tasks.payment_tasks.process_registry": {"queue": "payments"},
        "app.tasks.payment_tasks.retry_failed_payments": {"queue": "payments"},
    },
    # Повторные попытки при сбое брокера
    task_acks_late=True,
    task_reject_on_worker_lost=True,
)


# =============================================================================
# ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ: получить сессию БД для синхронного Celery
# =============================================================================

def _run_async(coro):
    """Запускает async-функцию из синхронного Celery-воркера."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _get_db_session():
    """Создаёт сессию PostgreSQL для задачи."""
    from app.database import async_session_factory
    async with async_session_factory() as session:
        return session


# =============================================================================
# ЗАДАЧА 1: ОДИНОЧНАЯ ВЫПЛАТА
# =============================================================================

@celery_app.task(
    bind=True,
    name="app.tasks.payment_tasks.process_payment",
    max_retries=3,
    default_retry_delay=60,   # повтор через 60 секунд
    soft_time_limit=120,      # предупреждение через 2 минуты
    time_limit=180,           # жёсткий лимит 3 минуты
)
def process_payment(self, payment_id: str):
    """
    Отправляет одиночную выплату в Совкомбанк и обновляет статус.

    Запускается автоматически после приёмки задания директором магазина.
    При ошибке делает до 3 попыток с интервалом 60 секунд.
    """
    logger.info(f"[PAYMENT] Начало обработки выплаты {payment_id}")

    async def _process():
        from app.database import async_session_factory
        from app.models.payment import Payment, PaymentStatus, FnsReceipt, FnsReceiptStatus
        from app.services.payment_service import send_to_sovcombank
        from app.services.fns_service import register_fns_receipt

        async with async_session_factory() as db:
            # Получаем выплату
            payment = await db.get(Payment, payment_id)
            if not payment:
                logger.error(f"[PAYMENT] Выплата {payment_id} не найдена в БД")
                return

            if payment.status not in (PaymentStatus.PENDING, PaymentStatus.FAILED):
                logger.warning(
                    f"[PAYMENT] Выплата {payment_id} в статусе {payment.status} — пропускаем"
                )
                return

            # Переводим в статус PROCESSING
            payment.status       = PaymentStatus.PROCESSING
            payment.processing_at = datetime.now(timezone.utc)
            await db.commit()

            try:
                # Отправляем в Совкомбанк
                result = await send_to_sovcombank(payment)

                if result["success"]:
                    # ✅ Успешная выплата
                    payment.status                   = PaymentStatus.COMPLETED
                    payment.sovcombank_transaction_id = result["transaction_id"]
                    payment.completed_at              = datetime.now(timezone.utc)
                    payment.error_message             = None

                    logger.info(
                        f"[PAYMENT] ✅ Выплата {payment_id} выполнена | "
                        f"Транзакция: {result['transaction_id']} | "
                        f"Сумма: {payment.total_amount} руб"
                    )

                    # Push: уведомляем исполнителя о поступлении денег 💰
                    try:
                        from app.models.user import User as UserModel
                        from app.services import push_service
                        executor = await db.get(UserModel, payment.executor_id)
                        if executor and executor.fcm_token:
                            await push_service.notify_payment_done(
                                executor_token=executor.fcm_token,
                                amount=float(payment.total_amount),
                                card_masked=payment.bank_card_masked or "",
                            )
                    except Exception as push_err:
                        # Push — не критично, не ломаем задачу выплаты
                        logger.warning(f"[PAYMENT] Push не отправлен: {push_err}")

                    # Регистрируем чек в ФНС
                    try:
                        await register_fns_receipt(db, payment)
                        logger.info(f"[PAYMENT] Чек ФНС зарегистрирован для выплаты {payment_id}")
                    except Exception as fns_err:
                        # Ошибка ФНС не отменяет выплату — логируем и продолжаем
                        logger.error(
                            f"[PAYMENT] ⚠️ Ошибка регистрации чека ФНС для {payment_id}: {fns_err}"
                        )

                else:
                    # ❌ Ошибка Совкомбанка
                    payment.status        = PaymentStatus.FAILED
                    payment.error_message = result["error"]
                    payment.retry_count   = (payment.retry_count or 0) + 1

                    logger.warning(
                        f"[PAYMENT] ❌ Ошибка выплаты {payment_id}: {result['error']} "
                        f"(попытка {payment.retry_count}/3)"
                    )

            except Exception as exc:
                payment.status        = PaymentStatus.FAILED
                payment.error_message = str(exc)
                payment.retry_count   = (payment.retry_count or 0) + 1
                logger.exception(f"[PAYMENT] Исключение при выплате {payment_id}: {exc}")

            await db.commit()

    try:
        _run_async(_process())
    except Exception as exc:
        logger.exception(f"[PAYMENT] Задача упала для {payment_id}: {exc}")
        # Celery повторит задачу автоматически
        raise self.retry(exc=exc)


# =============================================================================
# ЗАДАЧА 2: ПАКЕТНАЯ ВЫПЛАТА ПО РЕЕСТРУ (ТЗ 3.12)
# =============================================================================

@celery_app.task(
    bind=True,
    name="app.tasks.payment_tasks.process_registry",
    max_retries=1,
    soft_time_limit=3600,   # предупреждение через 1 час (до 1000 строк)
    time_limit=7200,        # жёсткий лимит 2 часа
)
def process_registry(self, registry_id: str):
    """
    Пакетная выплата: обрабатывает все VALID строки реестра.

    Запускается после подтверждения реестра директором региона.
    Каждая строка → отдельная задача process_payment (параллельно).

    Логика:
      1. Берём все строки реестра со статусом VALID
      2. Для каждой создаём Payment и запускаем process_payment
      3. По завершении всех — обновляем статус реестра (COMPLETED / PARTIAL)
    """
    logger.info(f"[REGISTRY] Начало обработки реестра {registry_id}")

    async def _process():
        from app.database import async_session_factory
        from app.models.payment import (
            Payment, PaymentRegistry, PaymentRegistryItem,
            PaymentStatus, RegistryStatus, RegistryItemStatus,
        )
        from app.models.user import User

        async with async_session_factory() as db:
            # Загружаем реестр
            registry = await db.get(PaymentRegistry, registry_id)
            if not registry:
                logger.error(f"[REGISTRY] Реестр {registry_id} не найден")
                return

            if registry.status != RegistryStatus.PROCESSING:
                logger.warning(
                    f"[REGISTRY] Реестр {registry_id} в статусе {registry.status} — "
                    "ожидался PROCESSING, пропускаем"
                )
                return

            # Получаем все VALID строки
            result = await db.execute(
                select(PaymentRegistryItem).where(
                    PaymentRegistryItem.registry_id == registry_id,
                    PaymentRegistryItem.status == RegistryItemStatus.VALID,
                ).order_by(PaymentRegistryItem.row_number)
            )
            items = result.scalars().all()

            if not items:
                logger.warning(f"[REGISTRY] Реестр {registry_id}: нет VALID строк для выплаты")
                registry.status       = RegistryStatus.COMPLETED
                registry.completed_at = datetime.now(timezone.utc)
                await db.commit()
                return

            logger.info(f"[REGISTRY] Реестр {registry_id}: обрабатываем {len(items)} строк")

            paid_count   = 0
            failed_count = 0
            paid_amount  = 0.0

            for item in items:
                # Находим исполнителя по ИНН (сопоставление было в validate_registry_item)
                executor = None
                if item.executor_id:
                    executor = await db.get(User, item.executor_id)

                if not executor:
                    # Исполнитель не найден — помечаем строку как ошибку
                    item.status        = RegistryItemStatus.FAILED
                    item.error_message = f"Исполнитель с ИНН {item.executor_inn} не найден в системе"
                    failed_count += 1
                    db.add(item)
                    continue

                try:
                    # Создаём запись выплаты
                    from decimal import Decimal
                    amount     = Decimal(str(item.amount))
                    tax_amount = (amount * Decimal("0.06")).quantize(Decimal("0.01"))
                    total      = amount + tax_amount

                    payment = Payment(
                        # Для реестровых выплат task_id отсутствует — используем UUID реестра
                        task_id          = registry_id,
                        executor_id      = executor.id,
                        registry_item_id = item.id,
                        amount           = amount,
                        tax_amount       = tax_amount,
                        total_amount     = total,
                        status           = PaymentStatus.PENDING,
                        bank_card_masked = executor.bank_card_masked,
                        bank_name        = executor.bank_name,
                        bank_card_token  = executor.bank_card_token,
                    )
                    db.add(payment)
                    await db.flush()   # получаем payment.id

                    # Связываем строку реестра с выплатой
                    item.payment_id = payment.id
                    db.add(item)

                    # Запускаем одиночную задачу выплаты (асинхронно)
                    process_payment.apply_async(
                        args=[str(payment.id)],
                        queue="payments",
                        countdown=0,
                    )

                    paid_count  += 1
                    paid_amount += float(total)

                    logger.info(
                        f"[REGISTRY] Строка {item.row_number}: "
                        f"выплата {payment.id} поставлена в очередь | "
                        f"{executor.phone} | {float(total)} руб"
                    )

                except Exception as exc:
                    item.status        = RegistryItemStatus.FAILED
                    item.error_message = str(exc)
                    failed_count += 1
                    db.add(item)
                    logger.exception(
                        f"[REGISTRY] Ошибка при создании выплаты для строки {item.row_number}: {exc}"
                    )

            # Обновляем итоги реестра
            registry.paid_rows  = paid_count
            registry.failed_rows = failed_count
            registry.paid_amount = paid_amount

            if failed_count == 0:
                registry.status = RegistryStatus.COMPLETED
                logger.info(
                    f"[REGISTRY] ✅ Реестр {registry_id} завершён: "
                    f"все {paid_count} выплат отправлены | {paid_amount:.2f} руб"
                )
            else:
                registry.status = RegistryStatus.PARTIAL
                logger.warning(
                    f"[REGISTRY] ⚠️ Реестр {registry_id} частично выполнен: "
                    f"✅ {paid_count} / ❌ {failed_count}"
                )

            registry.completed_at = datetime.now(timezone.utc)
            await db.commit()

    try:
        _run_async(_process())
    except Exception as exc:
        logger.exception(f"[REGISTRY] Задача упала для реестра {registry_id}: {exc}")
        raise self.retry(exc=exc)


# =============================================================================
# ЗАДАЧА 3: ЕЖЕДНЕВНЫЙ ПОВТОР НЕУСПЕШНЫХ ВЫПЛАТ
# =============================================================================

@celery_app.task(
    name="app.tasks.payment_tasks.retry_failed_payments",
)
def retry_failed_payments():
    """
    Ежедневная задача (03:00 МСК): повторяет выплаты со статусом FAILED.

    Условие повтора: retry_count < 3.
    Подключается через Celery Beat в celery_beat_schedule.
    """
    logger.info("[RETRY] Запуск ежедневного повтора неуспешных выплат")

    async def _retry():
        from app.database import async_session_factory
        from app.models.payment import Payment, PaymentStatus

        async with async_session_factory() as db:
            result = await db.execute(
                select(Payment).where(
                    Payment.status == PaymentStatus.FAILED,
                    Payment.retry_count < 3,
                )
            )
            failed = result.scalars().all()

            if not failed:
                logger.info("[RETRY] Нет выплат для повтора")
                return

            logger.info(f"[RETRY] Найдено {len(failed)} выплат для повтора")

            for payment in failed:
                payment.status = PaymentStatus.PENDING
                db.add(payment)
                process_payment.apply_async(
                    args=[str(payment.id)],
                    queue="payments",
                    countdown=5,
                )
                logger.info(
                    f"[RETRY] Выплата {payment.id} поставлена на повтор "
                    f"(попытка {payment.retry_count + 1}/3)"
                )

            await db.commit()

    _run_async(_retry())


# =============================================================================
# CELERY BEAT: расписание периодических задач
# =============================================================================

celery_app.conf.beat_schedule = {
    # Повтор неуспешных выплат — каждую ночь в 03:00 МСК
    "retry-failed-payments-daily": {
        "task": "app.tasks.payment_tasks.retry_failed_payments",
        "schedule": {"hour": 3, "minute": 0},
        "options": {"queue": "payments"},
    },
}
