# =============================================================================
# KARI.Самозанятые — Фоновые задачи ФНС (Celery)
# Файл: app/tasks/fns_tasks.py
# =============================================================================
#
# Celery — это система фоновых задач.
# Задачи запускаются:
#   - По расписанию (Celery Beat)
#   - Вручную из API
#   - Автоматически при определённых событиях
#
# Расписание (celery_app.conf.beat_schedule):
#   Каждый день в 07:00 МСК → check_all_fns_receipts_task()
#   Каждый день в 06:00 МСК → check_all_users_fns_status_task()
#
# Запуск воркера (IT поддержка):
#   celery -A app.tasks.celery_app worker --loglevel=info
#   celery -A app.tasks.celery_app beat --loglevel=info
# =============================================================================

import asyncio
import logging

from celery import Celery
from celery.schedules import crontab

from app.config import settings

logger = logging.getLogger(__name__)


# =============================================================================
# ИНИЦИАЛИЗАЦИЯ CELERY
# =============================================================================

celery_app = Celery(
    "kari_samozanyatye",
    broker=settings.REDIS_URL,   # Redis как брокер сообщений
    backend=settings.REDIS_URL,  # Redis хранит результаты задач
)

celery_app.conf.update(
    task_serializer     = "json",
    result_serializer   = "json",
    accept_content      = ["json"],
    timezone            = "Europe/Moscow",  # Московское время для расписания
    enable_utc          = True,
    task_track_started  = True,

    # Расписание автоматических задач
    beat_schedule = {

        # ТЗ 3.11: Ежедневная проверка аннулирования чеков в 07:00 МСК
        "check-fns-receipts-daily": {
            "task":     "app.tasks.fns_tasks.check_all_receipts",
            "schedule": crontab(hour=7, minute=0),
        },

        # Ежедневная проверка статуса самозанятости всех исполнителей в 06:00 МСК
        "check-fns-users-daily": {
            "task":     "app.tasks.fns_tasks.check_all_users_status",
            "schedule": crontab(hour=6, minute=0),
        },

        # Ежедневное снятие истёкших блокировок стоп-листа в 01:00 МСК
        # (тихое время: меньше нагрузки, до проверки ФНС и выплат)
        "expire-stop-list-daily": {
            "task":     "app.tasks.fns_tasks.expire_stop_list",
            "schedule": crontab(hour=1, minute=0),
        },
    },
)


# =============================================================================
# ЗАДАЧА 1: ЕЖЕДНЕВНАЯ ПРОВЕРКА ЧЕКОВ ФНС (07:00)
# =============================================================================

@celery_app.task(
    name="app.tasks.fns_tasks.check_all_receipts",
    bind=True,
    max_retries=3,
    default_retry_delay=300,   # Повтор через 5 минут при ошибке
)
def check_all_receipts(self):
    """
    Ежедневная проверка всех активных чеков ФНС (ТЗ 3.11).
    Запускается каждый день в 07:00 МСК через Celery Beat.

    Что делает:
    1. Берёт все чеки со статусом CREATED за последние 60 дней
    2. Для каждого делает запрос в ФНС
    3. Если чек аннулирован — блокирует исполнителя и уведомляет директора и бухгалтерию
    """
    logger.info("⏰ Celery: запуск ежедневной проверки чеков ФНС (07:00)")

    async def _run():
        from app.database import AsyncSessionLocal
        from app.services.fns_service import daily_check_all_receipts

        async with AsyncSessionLocal() as db:
            try:
                stats = await daily_check_all_receipts(db)
                await db.commit()
                return stats
            except Exception as e:
                await db.rollback()
                raise e

    try:
        stats = asyncio.get_event_loop().run_until_complete(_run())
        logger.info(f"✅ Celery: проверка чеков завершена — {stats}")
        return stats

    except Exception as exc:
        logger.error(f"❌ Celery: ошибка проверки чеков ФНС: {exc}")
        raise self.retry(exc=exc)


# =============================================================================
# ЗАДАЧА 2: ЕЖЕДНЕВНАЯ ПРОВЕРКА СТАТУСА САМОЗАНЯТЫХ (06:00)
# =============================================================================

@celery_app.task(
    name="app.tasks.fns_tasks.check_all_users_status",
    bind=True,
    max_retries=2,
    default_retry_delay=600,
)
def check_all_users_status(self):
    """
    Ежедневная проверка статуса самозанятости всех исполнителей.
    Запускается в 06:00 МСК — до проверки чеков.

    Зачем нужно: исполнитель мог в любой момент сняться с учёта как самозанятый.
    Система должна это знать заранее, до выплаты.
    """
    logger.info("⏰ Celery: запуск ежедневной проверки статуса ФНС пользователей (06:00)")

    async def _run():
        from app.database import AsyncSessionLocal
        from app.models.user import User, UserRole, UserStatus
        from app.services.fns_service import update_user_fns_status
        from sqlalchemy import select, and_

        async with AsyncSessionLocal() as db:
            try:
                result = await db.execute(
                    select(User).where(
                        and_(
                            User.role == UserRole.EXECUTOR,
                            User.status == UserStatus.ACTIVE,
                            User.inn.isnot(None),
                        )
                    )
                )
                executors = result.scalars().all()

                stats = {"total": len(executors), "changed": 0, "errors": 0}

                for executor in executors:
                    try:
                        old = executor.fns_status
                        await update_user_fns_status(db, executor)
                        if old != executor.fns_status:
                            stats["changed"] += 1
                    except Exception as e:
                        stats["errors"] += 1
                        logger.error(f"Ошибка обновления {executor.phone}: {e}")

                await db.commit()
                return stats

            except Exception as e:
                await db.rollback()
                raise e

    try:
        stats = asyncio.get_event_loop().run_until_complete(_run())
        logger.info(f"✅ Celery: статус пользователей обновлён — {stats}")
        return stats

    except Exception as exc:
        logger.error(f"❌ Celery: ошибка обновления статусов: {exc}")
        raise self.retry(exc=exc)


# =============================================================================
# ЗАДАЧА 3: ОБРАБОТКА ОДНОЙ ВЫПЛАТЫ (запускается из API после accept задания)
# =============================================================================

@celery_app.task(
    name="app.tasks.fns_tasks.process_single_payment",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def process_single_payment(self, payment_id: str):
    """
    Обрабатывает одну выплату:
    1. Отправляет перевод в Совкомбанк
    2. При успехе — регистрирует чек в ФНС
    3. Обновляет статус выплаты в БД

    Запускается из api/tasks.py после accept_task().
    """
    logger.info(f"⚙️ Celery: обработка выплаты {payment_id}")

    async def _run():
        from app.database import AsyncSessionLocal
        from app.models.payment import Payment, PaymentStatus
        from app.models.task import Task
        from app.services.payment_service import send_to_sovcombank
        from app.services.fns_service import register_income
        from datetime import datetime, timezone

        async with AsyncSessionLocal() as db:
            try:
                payment = await db.get(Payment, payment_id)
                if not payment:
                    logger.error(f"Выплата {payment_id} не найдена")
                    return

                from app.models.user import User
                executor = await db.get(User, payment.executor_id)
                task     = await db.get(Task, payment.task_id)

                # Отправляем в Совкомбанк
                payment.status       = PaymentStatus.PROCESSING
                payment.processing_at = datetime.now(timezone.utc)

                result = await send_to_sovcombank(payment)

                if result["success"]:
                    payment.status                    = PaymentStatus.COMPLETED
                    payment.sovcombank_transaction_id  = result["transaction_id"]
                    payment.sovcombank_status          = "SUCCESS"
                    payment.completed_at              = datetime.now(timezone.utc)

                    # Регистрируем чек ФНС
                    if executor and task:
                        receipt = await register_income(
                            db=db,
                            payment=payment,
                            executor=executor,
                            service_description=task.title,
                            service_date=task.scheduled_date,
                        )
                        payment.fns_receipt_id = receipt.id

                    logger.info(f"✅ Выплата {payment_id} завершена: {result['transaction_id']}")

                else:
                    payment.status        = PaymentStatus.FAILED
                    payment.error_message = result["error"]
                    logger.error(f"❌ Выплата {payment_id} не прошла: {result['error']}")

                await db.commit()

            except Exception as e:
                await db.rollback()
                raise e

    try:
        asyncio.get_event_loop().run_until_complete(_run())

    except Exception as exc:
        logger.error(f"❌ Celery: ошибка обработки выплаты {payment_id}: {exc}")
        raise self.retry(exc=exc)


# =============================================================================
# ЗАДАЧА 4: АВТО-СНЯТИЕ ИСТЁКШИХ БЛОКИРОВОК СТОП-ЛИСТА (01:00 МСК)
# =============================================================================

@celery_app.task(
    name="app.tasks.fns_tasks.expire_stop_list",
    bind=True,
    max_retries=2,
    default_retry_delay=300,
)
def expire_stop_list(self):
    """
    Ежедневно в 01:00 МСК снимает блокировки в стоп-листе, у которых истёк срок.

    Логика: если blocked_until < сегодня, запись помечается is_active=False.
    Актуально для former_employee: через 2 года с даты увольнения — авто-разблокировка.

    Без этой задачи HRD пришлось бы вручную отслеживать истёкшие блокировки.
    """
    logger.info("⏰ Celery: авто-снятие истёкших блокировок стоп-листа (01:00)")

    async def _run():
        from app.database import AsyncSessionLocal
        from app.api.stop_list import auto_expire_stop_list

        async with AsyncSessionLocal() as db:
            try:
                count = await auto_expire_stop_list(db)
                await db.commit()
                return count
            except Exception as e:
                await db.rollback()
                raise e

    try:
        count = asyncio.get_event_loop().run_until_complete(_run())
        logger.info(f"✅ Celery: снято {count} истёкших блокировок стоп-листа")
        return count

    except Exception as exc:
        logger.error(f"❌ Celery: ошибка авто-снятия стоп-листа: {exc}")
        raise self.retry(exc=exc)
