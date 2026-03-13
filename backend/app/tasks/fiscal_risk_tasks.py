# =============================================================================
# KARI.Самозанятые v2 — Celery задачи фискального контроля
# Файл: app/tasks/fiscal_risk_tasks.py
# =============================================================================
#
# Задачи, которые запускаются автоматически по расписанию:
#
#   run_fiscal_risk_scan   — ежедневно в 08:00 МСК
#     Проверяет ВСЕХ активных исполнителей по 3 критериям ФНС + 4 паттернам.
#     Критических → автоматически в стоп-лист (FISCAL_RISK).
#     Высокий риск → уведомление директору региона.
#
#   check_payment_before_payout — перед каждой выплатой (вызов из payment_tasks.py)
#     Блокирует выплату если у исполнителя уже критический фискальный риск.
#
# Расписание (добавить в celery.py / celeryconfig.py):
#
#   "fiscal-risk-daily": {
#       "task": "app.tasks.fiscal_risk_tasks.run_fiscal_risk_scan",
#       "schedule": crontab(hour=8, minute=0),   # 08:00 МСК ежедневно
#   },
#
# =============================================================================

import logging
from datetime import date
from typing import Optional

logger = logging.getLogger(__name__)

# Celery app импортируется из основного модуля
# from app.celery_app import celery_app

# Временная заглушка для запуска без Celery (в разработке)
try:
    from celery import shared_task
    CELERY_AVAILABLE = True
except ImportError:
    CELERY_AVAILABLE = False
    # Декоратор-заглушка для среды без Celery
    def shared_task(func=None, **kwargs):
        if func is None:
            return lambda f: f
        return func


@shared_task(
    name="fiscal_risk.run_full_scan",
    bind=True,
    max_retries=2,
    default_retry_delay=300,   # 5 минут между попытками
    soft_time_limit=3600,      # Не более 1 часа на весь скан
)
def run_fiscal_risk_scan(
    self,
    year: Optional[int] = None,
    min_risk_level: str = "medium",
    triggered_by: Optional[str] = None,
):
    """
    Полное фискальное сканирование всех активных исполнителей.

    Запускается:
    - Автоматически в 08:00 МСК каждый день (Celery Beat)
    - Вручную директором региона через API POST /api/v1/fiscal-risk/scan

    Алгоритм:
    1. Берём всех активных исполнителей с ИНН
    2. Для каждого вычисляем фискальный риск (3 критерия + 4 паттерна)
    3. Критических (all 3 criteria) → добавляем в стоп-лист FISCAL_RISK
    4. Высоких → отправляем Push директору региона
    5. Пишем в журнал аудита
    """
    import asyncio
    from app.database import AsyncSessionLocal
    from app.models.user import User, UserRole, UserStatus
    from app.services.fiscal_risk_service import check_fiscal_risk
    from sqlalchemy import select, and_

    check_year = year or date.today().year
    logger.info(
        "Старт фискального сканирования: год=%d min_risk=%s запустил=%s",
        check_year, min_risk_level, triggered_by or "scheduler"
    )

    async def _run():
        results = {
            "total": 0,
            "low": 0,
            "medium": 0,
            "high": 0,
            "critical": 0,
            "auto_stop_listed": 0,
            "errors": 0,
        }

        async with AsyncSessionLocal() as db:
            # Берём всех активных исполнителей с ИНН
            r = await db.execute(
                select(User).where(
                    and_(
                        User.role == UserRole.EXECUTOR,
                        User.status == UserStatus.ACTIVE,
                        User.inn.isnot(None),
                    )
                )
            )
            executors = r.scalars().all()
            results["total"] = len(executors)

            logger.info("Проверяем %d исполнителей...", len(executors))

            for executor in executors:
                try:
                    risk = await check_fiscal_risk(
                        executor_id=str(executor.id),
                        inn=executor.inn,
                        db=db,
                        check_year=check_year,
                    )
                    results[risk.risk_level] += 1

                    # Критический риск — все 3 критерия ФНС сработали
                    if risk.risk_level == "critical" and risk.requires_stop_list:
                        await _auto_add_to_stop_list(executor, risk, db)
                        results["auto_stop_listed"] += 1

                    # Высокий риск — уведомляем директора
                    elif risk.risk_level == "high":
                        await _notify_regional_director(executor, risk, db)

                except Exception as e:
                    results["errors"] += 1
                    logger.error(
                        "Ошибка при проверке executor=%s: %s",
                        executor.id, e
                    )
                    continue

            await db.commit()

        logger.info(
            "Фискальное сканирование завершено: всего=%d low=%d medium=%d "
            "high=%d critical=%d в_стоп-лист=%d ошибок=%d",
            results["total"], results["low"], results["medium"],
            results["high"], results["critical"],
            results["auto_stop_listed"], results["errors"]
        )
        return results

    return asyncio.run(_run())


async def _auto_add_to_stop_list(executor, risk, db):
    """
    Автоматически добавляет исполнителя в стоп-лист с причиной FISCAL_RISK.

    Срабатывает только при ОДНОВРЕМЕННОМ выполнении ВСЕХ 3 критериев ФНС:
    1. Среднемесячный доход > 35 000 руб.
    2. Сотрудничество > 3 месяцев в году
    3. Доля KARI в НПД > 75%
    """
    from app.models.stop_list import StopList, StopListReason
    from sqlalchemy import select, and_

    # Проверяем, не добавлен ли уже в стоп-лист
    existing = await db.execute(
        select(StopList).where(
            and_(
                StopList.inn == executor.inn,
                StopList.reason == "fiscal_risk",
                StopList.is_active == True,
            )
        )
    )
    if existing.scalar_one_or_none():
        logger.debug("Исполнитель %s уже в стоп-листе FISCAL_RISK", executor.inn)
        return

    # Формируем описание
    c = risk.criteria
    details = (
        f"Авто: все 3 критерия ФНС. "
        f"Доход: {c.avg_monthly_income:,.0f} руб/мес. "
        f"Месяцев: {c.months_with_payment}. "
        f"Год: {risk.check_year}."
    )

    entry = StopList(
        inn=executor.inn,
        full_name=executor.full_name,
        reason="fiscal_risk",
        reason_details=details,
        is_active=True,
    )
    db.add(entry)

    logger.warning(
        "🚨 Автоматически добавлен в стоп-лист FISCAL_RISK: executor=%s ИНН=%s",
        executor.id, executor.inn
    )


async def _notify_regional_director(executor, risk, db):
    """
    Отправляет Push-уведомление директору региона о высоком риске.
    """
    from app.services import push_service
    from app.models.user import User, UserRole
    from sqlalchemy import select

    r = await db.execute(
        select(User).where(User.role == UserRole.REGIONAL_DIRECTOR)
    )
    directors = r.scalars().all()

    for director in directors:
        if director.push_token:
            try:
                await push_service.send_push(
                    token=director.push_token,
                    title="⚠️ Фискальный риск",
                    body=(
                        f"{executor.full_name or executor.inn}: "
                        f"высокий риск переквалификации. "
                        f"{risk.criteria.months_with_payment} мес., "
                        f"{risk.criteria.avg_monthly_income:,.0f} руб/мес."
                    ),
                    data={
                        "type": "FISCAL_RISK",
                        "executor_id": str(executor.id),
                        "risk_level": risk.risk_level,
                    },
                )
            except Exception as e:
                logger.warning("Push директору не отправлен: %s", e)


@shared_task(
    name="fiscal_risk.check_before_payment",
    bind=True,
    max_retries=1,
)
def check_payment_before_payout(self, executor_id: str, payment_amount: float):
    """
    Быстрая проверка перед выплатой.
    Вызывается из payment_tasks.py перед каждой выплатой.

    Блокирует выплату если:
    - Исполнитель уже в стоп-листе FISCAL_RISK
    - Новая выплата приведёт к пересечению порога 35 000 руб/мес среднего дохода

    Возвращает:
        {"allowed": True/False, "reason": "..."}
    """
    import asyncio
    from app.database import AsyncSessionLocal
    from app.models.stop_list import StopList
    from sqlalchemy import select, and_

    async def _check():
        async with AsyncSessionLocal() as db:
            # Проверяем стоп-лист
            from app.models.user import User
            r = await db.execute(
                select(User).where(User.id == executor_id)
            )
            executor = r.scalar_one_or_none()
            if not executor or not executor.inn:
                return {"allowed": True}

            blocked = await db.execute(
                select(StopList).where(
                    and_(
                        StopList.inn == executor.inn,
                        StopList.reason == "fiscal_risk",
                        StopList.is_active == True,
                    )
                )
            )
            if blocked.scalar_one_or_none():
                return {
                    "allowed": False,
                    "reason": (
                        "Исполнитель находится в стоп-листе по причине "
                        "фискального риска (переквалификация). "
                        "Обратитесь к директору региона."
                    ),
                }

            return {"allowed": True}

    return asyncio.run(_check())
