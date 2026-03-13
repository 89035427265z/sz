# =============================================================================
# KARI.Самозанятые v2 — API фискального контроля
# Файл: app/api/fiscal_risk.py
# =============================================================================
#
# Эндпоинты мониторинга рисков переквалификации самозанятых.
#
#   GET  /fiscal-risk/executor/{executor_id}   — полная проверка исполнителя
#   GET  /fiscal-risk/at-risk                  — все исполнители в зоне риска
#   GET  /fiscal-risk/summary                  — сводка по региону (для дашборда)
#   POST /fiscal-risk/scan                     — запустить проверку всего реестра
#
# Кто имеет доступ:
#   - Директор региона — все эндпоинты
#   - HRD             — просмотр + scan
#   - Директор подразделения — только свои магазины
#
# Когда используется:
#   - Ежедневно в 08:00 автоматически (Celery Beat)
#   - Вручную директором региона перед крупными выплатами
#   - HRD при проверке нового исполнителя перед заключением договора
# =============================================================================

import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.user import User, UserRole
from app.core.security import get_current_user, require_role
from app.services.fiscal_risk_service import (
    check_fiscal_risk,
    format_risk_for_api,
    get_all_at_risk_executors,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# =============================================================================
# PYDANTIC СХЕМЫ
# =============================================================================

class ScanRequest(BaseModel):
    """Запрос на запуск полного сканирования реестра."""
    year: Optional[int] = None          # Год проверки (по умолчанию текущий)
    min_risk_level: str = "medium"      # Минимальный уровень для включения в отчёт


class ScanResponse(BaseModel):
    """Ответ на запуск сканирования."""
    task_id: str                        # ID фоновой задачи Celery
    message: str
    executors_to_scan: int


class RiskSummary(BaseModel):
    """Сводка рисков по региону для дашборда."""
    check_year: int
    check_date: str
    total_executors_checked: int
    low_risk: int
    medium_risk: int
    high_risk: int
    critical_risk: int
    requires_action: int                # medium + high + critical
    auto_stop_listed: int               # Автоматически добавлены в стоп-лист


# =============================================================================
# ЭНДПОИНТЫ
# =============================================================================

@router.get("/executor/{executor_id}")
async def check_executor_risk(
    executor_id: str,
    year: Optional[int] = Query(None, description="Год проверки (по умолчанию текущий)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Полная фискальная проверка одного исполнителя.

    Возвращает:
    - Статус трёх критериев ФНС (доход, срок, доля)
    - Анализ паттернов выплат (ритмичность, суммы, сроки актов)
    - Итоговый уровень риска и рекомендацию
    """
    # Только директор региона и HRD
    if current_user.role not in (
        UserRole.REGIONAL_DIRECTOR, UserRole.HRD
    ):
        raise HTTPException(
            status_code=403,
            detail="Фискальный контроль доступен директору региона и HRD"
        )

    # Получаем ИНН исполнителя
    result = await db.execute(select(User).where(User.id == executor_id))
    executor = result.scalar_one_or_none()
    if not executor:
        raise HTTPException(status_code=404, detail="Исполнитель не найден")
    if not executor.inn:
        raise HTTPException(
            status_code=422,
            detail="У исполнителя не заполнен ИНН — проверка невозможна"
        )

    # Запускаем проверку
    risk_result = await check_fiscal_risk(
        executor_id=executor_id,
        inn=executor.inn,
        db=db,
        check_year=year,
    )

    # Если критический риск — логируем
    if risk_result.requires_stop_list:
        logger.warning(
            "КРИТИЧЕСКИЙ ФИСКАЛЬНЫЙ РИСК: executor=%s ИНН=%s "
            "требует добавления в стоп-лист",
            executor_id, executor.inn
        )

    return format_risk_for_api(risk_result)


@router.get("/at-risk")
async def get_at_risk_list(
    year: Optional[int] = Query(None),
    min_risk_level: str = Query("medium", description="Минимальный уровень: medium или high"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Список всех исполнителей в зоне фискального риска.

    Используется на дашборде директора региона в разделе «Фискальный контроль».
    Быстрый SQL-запрос (не полная проверка каждого — только критерии 1 и 2).
    """
    if current_user.role not in (
        UserRole.REGIONAL_DIRECTOR, UserRole.HRD
    ):
        raise HTTPException(status_code=403, detail="Недостаточно прав")

    check_year = year or date.today().year
    at_risk = await get_all_at_risk_executors(db, check_year, min_risk_level)

    return {
        "check_year": check_year,
        "min_risk_level": min_risk_level,
        "total_at_risk": len(at_risk),
        "executors": at_risk,
    }


@router.get("/summary", response_model=RiskSummary)
async def get_risk_summary(
    year: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Сводка фискальных рисков по региону — плитка для дашборда.
    Показывает общую картину: сколько исполнителей в каждой зоне риска.
    """
    if current_user.role not in (
        UserRole.REGIONAL_DIRECTOR, UserRole.HRD, UserRole.DIVISION_DIRECTOR
    ):
        raise HTTPException(status_code=403, detail="Недостаточно прав")

    check_year = year or date.today().year
    at_risk = await get_all_at_risk_executors(db, check_year, "medium")

    medium = sum(1 for e in at_risk if e["risk_level"] == "medium")
    high   = sum(1 for e in at_risk if e["risk_level"] == "high")
    crit   = sum(1 for e in at_risk if e["risk_level"] == "critical")

    # Получаем общее число активных исполнителей
    from app.models.user import UserStatus
    r_total = await db.execute(
        select(User).where(
            User.role == UserRole.EXECUTOR,
            User.status == UserStatus.ACTIVE,
        )
    )
    total = len(r_total.scalars().all())
    low = max(0, total - medium - high - crit)

    return RiskSummary(
        check_year=check_year,
        check_date=date.today().isoformat(),
        total_executors_checked=total,
        low_risk=low,
        medium_risk=medium,
        high_risk=high,
        critical_risk=crit,
        requires_action=medium + high + crit,
        auto_stop_listed=crit,
    )


@router.post("/scan", response_model=ScanResponse)
async def run_full_scan(
    body: ScanRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.REGIONAL_DIRECTOR)),
):
    """
    Запустить полное сканирование всех исполнителей в фоне.
    Только директор региона.

    Celery-задача проверяет каждого исполнителя по всем критериям
    и паттернам, критических добавляет в стоп-лист автоматически.
    """
    from app.tasks.fiscal_risk_tasks import run_fiscal_risk_scan

    check_year = body.year or date.today().year

    # Считаем сколько исполнителей нужно проверить
    from app.models.user import UserStatus
    r = await db.execute(
        select(User).where(
            User.role == UserRole.EXECUTOR,
            User.status == UserStatus.ACTIVE,
            User.inn.isnot(None),
        )
    )
    executors = r.scalars().all()

    # Запускаем Celery-задачу асинхронно
    task = run_fiscal_risk_scan.delay(
        year=check_year,
        min_risk_level=body.min_risk_level,
        triggered_by=str(current_user.id),
    )

    logger.info(
        "Запущено полное фискальное сканирование: %d исполнителей, год=%d, задача=%s",
        len(executors), check_year, task.id
    )

    return ScanResponse(
        task_id=task.id,
        message=f"Сканирование запущено. Будет проверено {len(executors)} исполнителей.",
        executors_to_scan=len(executors),
    )
