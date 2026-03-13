# =============================================================================
# KARI.Самозанятые v2 — API аналитики
# Файл: app/api/analytics.py
# =============================================================================
#
# Эндпоинты (все GET, только чтение):
#
#   GET /analytics/dashboard           — главная сводка (для директора региона)
#   GET /analytics/tasks               — статистика по заданиям
#   GET /analytics/payments            — статистика по выплатам
#   GET /analytics/executors           — топ/антирейтинг исполнителей
#   GET /analytics/stores              — сравнение магазинов
#   GET /analytics/fns                 — статистика ФНС (чеки, аннулирования)
#
# Параметры фильтрации (общие для всех):
#   ?date_from=YYYY-MM-DD  — начало периода
#   ?date_to=YYYY-MM-DD    — конец периода
#   ?store_id=...          — конкретный магазин
#   ?division_id=...       — конкретное подразделение
#
# Кэширование:
#   Данные кэшируются в Redis на 5 минут.
#   Директор региона видит все магазины своего региона.
#   Директор подразделения — только свои магазины.
#   Директор магазина — только свой магазин.
#
# =============================================================================

import logging
from datetime import datetime, timezone, date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, case

from app.database import get_db
from app.models.user import User, UserRole, UserStatus
from app.models.penalty import Penalty
from app.models.rating import Rating
from app.core.security import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


# =============================================================================
# PYDANTIC СХЕМЫ ОТВЕТОВ
# =============================================================================

class DashboardSummary(BaseModel):
    """Главная сводка — плитки цифр на дашборде."""
    period_from: str
    period_to: str
    # Исполнители
    executors_total: int            # Всего зарегистрированных
    executors_active: int           # Активных за период
    executors_new: int              # Новых за период
    executors_blocked: int          # Заблокированных
    # Задания
    tasks_published: int            # Опубликованных заданий
    tasks_completed: int            # Завершённых
    tasks_cancelled: int            # Отменённых
    tasks_completion_rate: float    # % выполнения
    # Финансы
    payments_total_rub: float       # Сумма всех выплат (руб.)
    payments_count: int             # Количество транзакций
    avg_task_cost: float            # Средняя стоимость задания
    # Качество
    avg_rating: float               # Средний рейтинг исполнителей
    penalties_issued: int           # Штрафов выписано за период
    stop_list_entries: int          # Записей в стоп-листе


class TasksStats(BaseModel):
    """Статистика по заданиям."""
    by_status: dict[str, int]       # { "completed": 120, "cancelled": 5, ... }
    by_category: dict[str, int]     # { "cleaning": 80, "inventory": 40, ... }
    avg_completion_hours: float     # Среднее время выполнения (часы)
    by_day: list[dict]              # [{"date": "2026-03-01", "count": 12}, ...]


class PaymentsStats(BaseModel):
    """Статистика по выплатам."""
    total_amount: float
    total_count: int
    avg_amount: float
    by_status: dict[str, float]     # { "completed": 1500000.0, "failed": 5000.0 }
    by_month: list[dict]            # [{"month": "2026-03", "amount": 500000.0}]
    tax_compensated: float          # Сумма компенсации 6% налога


class ExecutorStats(BaseModel):
    """Статистика по исполнителям."""
    top_by_rating: list[dict]       # Топ-10 по рейтингу
    top_by_tasks: list[dict]        # Топ-10 по количеству заданий
    low_rating: list[dict]          # Исполнители с рейтингом < 3.0
    at_risk: list[dict]             # Исполнители с 3+ штрафами за 90 дней


class StoreStats(BaseModel):
    """Сравнение магазинов."""
    stores: list[dict]              # Список магазинов с метриками
    top_store_id: Optional[str]     # Лучший магазин (по % выполнения)
    bottom_store_id: Optional[str]  # Худший магазин


class FnsStats(BaseModel):
    """Статистика ФНС."""
    checks_issued: int              # Чеков сформировано
    checks_cancelled: int           # Аннулировано
    cancellation_rate: float        # % аннулирования
    executors_not_self_employed: int  # Потерявших статус
    total_tax_amount: float         # Общая сумма налогов (6%)


# =============================================================================
# ЭНДПОИНТЫ
# =============================================================================

@router.get("/dashboard", response_model=DashboardSummary)
async def get_dashboard(
    date_from: Optional[date] = Query(None, description="Начало периода (YYYY-MM-DD)"),
    date_to: Optional[date] = Query(None, description="Конец периода (YYYY-MM-DD)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Главный дашборд — сводка ключевых метрик.
    По умолчанию показывает текущий месяц.
    Директор региона видит все магазины своего региона.
    """
    # Период по умолчанию — текущий месяц
    today = date.today()
    if not date_from:
        date_from = today.replace(day=1)
    if not date_to:
        date_to = today

    # Конвертируем в datetime с timezone
    dt_from = datetime.combine(date_from, datetime.min.time()).replace(tzinfo=timezone.utc)
    dt_to = datetime.combine(date_to, datetime.max.time()).replace(tzinfo=timezone.utc)

    # ---- Исполнители ----
    r_total = await db.execute(select(func.count(User.id)).where(User.role == UserRole.EXECUTOR))
    executors_total = r_total.scalar_one()

    r_active = await db.execute(
        select(func.count(User.id)).where(
            and_(User.role == UserRole.EXECUTOR, User.status == UserStatus.ACTIVE)
        )
    )
    executors_active = r_active.scalar_one()

    r_new = await db.execute(
        select(func.count(User.id)).where(
            and_(
                User.role == UserRole.EXECUTOR,
                User.created_at >= dt_from,
                User.created_at <= dt_to,
            )
        )
    )
    executors_new = r_new.scalar_one()

    r_blocked = await db.execute(
        select(func.count(User.id)).where(
            and_(User.role == UserRole.EXECUTOR, User.status == UserStatus.BLOCKED)
        )
    )
    executors_blocked = r_blocked.scalar_one()

    # ---- Рейтинг ----
    r_avg = await db.execute(
        select(func.avg(Rating.score)).where(
            Rating.created_at.between(dt_from, dt_to)
        )
    )
    avg_rating = float(r_avg.scalar_one() or 0)

    # ---- Штрафы ----
    r_pen = await db.execute(
        select(func.count(Penalty.id)).where(
            Penalty.created_at.between(dt_from, dt_to)
        )
    )
    penalties_issued = r_pen.scalar_one()

    # ---- Задания / Выплаты / ФНС — заглушки ----
    # В реальной системе здесь JOIN с таблицами tasks и payments
    # Данные будут подтянуты после интеграции с основным backend

    return DashboardSummary(
        period_from=date_from.isoformat(),
        period_to=date_to.isoformat(),
        executors_total=executors_total,
        executors_active=executors_active,
        executors_new=executors_new,
        executors_blocked=executors_blocked,
        tasks_published=0,          # TODO: JOIN с tasks
        tasks_completed=0,          # TODO: JOIN с tasks
        tasks_cancelled=0,          # TODO: JOIN с tasks
        tasks_completion_rate=0.0,
        payments_total_rub=0.0,     # TODO: JOIN с payments
        payments_count=0,
        avg_task_cost=0.0,
        avg_rating=round(avg_rating, 2),
        penalties_issued=penalties_issued,
        stop_list_entries=0,        # TODO: JOIN с stop_list
    )


@router.get("/executors", response_model=ExecutorStats)
async def get_executors_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Статистика исполнителей:
    - Топ-10 по рейтингу
    - Топ-10 по количеству заданий
    - Список с низким рейтингом (< 3.0)
    - Список «в зоне риска» (3+ штрафа за 90 дней)
    """
    threshold_90d = datetime.now(timezone.utc) - timedelta(days=90)

    # Топ исполнителей по среднему рейтингу (минимум 3 оценки)
    r_top_rating = await db.execute(
        select(
            Rating.executor_id.label("executor_id"),
            func.avg(Rating.score).label("avg_score"),
            func.count(Rating.id).label("total_ratings"),
        )
        .group_by(Rating.executor_id)
        .having(func.count(Rating.id) >= 3)
        .order_by(func.avg(Rating.score).desc())
        .limit(10)
    )
    top_by_rating = [
        {
            "executor_id": str(row.executor_id),
            "avg_score": round(float(row.avg_score), 2),
            "total_ratings": row.total_ratings,
        }
        for row in r_top_rating.all()
    ]

    # Исполнители с низким рейтингом < 3.0 (минимум 5 оценок)
    r_low = await db.execute(
        select(
            Rating.executor_id.label("executor_id"),
            func.avg(Rating.score).label("avg_score"),
            func.count(Rating.id).label("total_ratings"),
        )
        .group_by(Rating.executor_id)
        .having(
            and_(
                func.count(Rating.id) >= 5,
                func.avg(Rating.score) < 3.0,
            )
        )
        .order_by(func.avg(Rating.score).asc())
    )
    low_rating = [
        {
            "executor_id": str(row.executor_id),
            "avg_score": round(float(row.avg_score), 2),
            "total_ratings": row.total_ratings,
        }
        for row in r_low.all()
    ]

    # Исполнители в зоне риска (3+ штрафа за 90 дней)
    r_risk = await db.execute(
        select(
            Penalty.executor_id.label("executor_id"),
            func.count(Penalty.id).label("penalty_count"),
        )
        .where(
            and_(
                Penalty.is_active == True,
                Penalty.created_at >= threshold_90d,
            )
        )
        .group_by(Penalty.executor_id)
        .having(func.count(Penalty.id) >= 3)
        .order_by(func.count(Penalty.id).desc())
    )
    at_risk = [
        {
            "executor_id": str(row.executor_id),
            "penalty_count_90d": row.penalty_count,
        }
        for row in r_risk.all()
    ]

    return ExecutorStats(
        top_by_rating=top_by_rating,
        top_by_tasks=[],    # TODO: JOIN с tasks
        low_rating=low_rating,
        at_risk=at_risk,
    )


@router.get("/tasks", response_model=TasksStats)
async def get_tasks_stats(
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Статистика по заданиям: по статусам, категориям, динамика по дням.
    Данные для графиков на дашборде директора.
    """
    # TODO: Реализовать после интеграции с моделью Task
    # Здесь будут JOIN с таблицей tasks
    return TasksStats(
        by_status={},
        by_category={},
        avg_completion_hours=0.0,
        by_day=[],
    )


@router.get("/payments", response_model=PaymentsStats)
async def get_payments_stats(
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Финансовая статистика: суммы, динамика по месяцам, компенсация налога.
    Данные для отчётов бухгалтерии.
    """
    # TODO: Реализовать после интеграции с моделью Payment
    return PaymentsStats(
        total_amount=0.0,
        total_count=0,
        avg_amount=0.0,
        by_status={},
        by_month=[],
        tax_compensated=0.0,
    )


@router.get("/fns", response_model=FnsStats)
async def get_fns_stats(
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Статистика ФНС: чеки, аннулирования, исполнители потерявшие статус.
    Критично для контроля налоговых рисков (422-ФЗ).
    """
    # TODO: Реализовать после интеграции с таблицей fns_checks
    return FnsStats(
        checks_issued=0,
        checks_cancelled=0,
        cancellation_rate=0.0,
        executors_not_self_employed=0,
        total_tax_amount=0.0,
    )
