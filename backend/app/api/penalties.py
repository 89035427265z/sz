# =============================================================================
# KARI.Самозанятые v2 — API штрафов и нарушений
# Файл: app/api/penalties.py
# =============================================================================
#
# Эндпоинты:
#
#   POST /penalties/                        — выписать штраф (директор / HRD)
#   GET  /penalties/                        — список штрафов (с фильтрами)
#   GET  /penalties/executor/{executor_id} — штрафы конкретного исполнителя
#   GET  /penalties/{penalty_id}           — подробности штрафа
#   PUT  /penalties/{penalty_id}/resolve   — снять штраф (только HRD)
#   GET  /penalties/executor/{executor_id}/risk — уровень риска исполнителя
#
# Логика эскалации:
#   3+ активных штрафа за 90 дней → метка «на проверке HR»
#   5+ активных штрафов           → автоматическая блокировка
#
# =============================================================================

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from app.database import get_db
from app.models.penalty import Penalty, PenaltyType
from app.models.user import User, UserRole, UserStatus
from app.core.security import get_current_user, require_role
from app.services import push_service

logger = logging.getLogger(__name__)
router = APIRouter()


# =============================================================================
# PYDANTIC СХЕМЫ
# =============================================================================

class PenaltyCreateRequest(BaseModel):
    """Тело запроса: выписать штраф."""
    executor_id: str
    task_id: Optional[str] = None              # Задание-источник нарушения
    penalty_type: PenaltyType
    reason: str = Field(..., min_length=10, max_length=1000)
    amount: Optional[float] = Field(None, ge=0, description="Финансовое удержание (руб.)")


class PenaltyResolveRequest(BaseModel):
    """Тело запроса: снять штраф."""
    resolution_note: str = Field(..., min_length=5, max_length=500)


class PenaltyResponse(BaseModel):
    """Ответ: один штраф."""
    id: str
    executor_id: str
    task_id: Optional[str]
    created_by_id: str
    penalty_type: str
    reason: str
    amount: Optional[float]
    is_active: bool
    resolved_at: Optional[str]
    resolved_by_id: Optional[str]
    resolution_note: Optional[str]
    created_at: str

    class Config:
        from_attributes = True


class ExecutorRiskResponse(BaseModel):
    """Уровень риска исполнителя по штрафам."""
    executor_id: str
    active_penalties_total: int          # Всего активных штрафов
    active_penalties_90d: int            # Активных штрафов за последние 90 дней
    risk_level: str                      # "low" / "medium" / "high" / "blocked"
    needs_hr_review: bool                # 3+ за 90 дней
    auto_blocked: bool                   # 5+ активных
    penalty_breakdown: dict[str, int]    # По типу нарушения


# =============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =============================================================================

async def _get_penalty_or_404(penalty_id: str, db: AsyncSession) -> Penalty:
    """Получает штраф или выбрасывает 404."""
    result = await db.execute(
        select(Penalty).where(Penalty.id == penalty_id)
    )
    penalty = result.scalar_one_or_none()
    if not penalty:
        raise HTTPException(status_code=404, detail="Штраф не найден")
    return penalty


async def _check_auto_block(executor_id: str, db: AsyncSession) -> bool:
    """
    Проверяет нужна ли автоматическая блокировка исполнителя.
    Возвращает True если нужно заблокировать (5+ активных штрафов).
    """
    result = await db.execute(
        select(func.count(Penalty.id))
        .where(
            and_(
                Penalty.executor_id == executor_id,
                Penalty.is_active == True,
            )
        )
    )
    total_active = result.scalar_one()
    return total_active >= 5


# =============================================================================
# ЭНДПОИНТЫ
# =============================================================================

@router.post("/", response_model=PenaltyResponse, status_code=201)
async def create_penalty(
    body: PenaltyCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Выписать штраф исполнителю.
    Директор магазина — может выписать за своё задание.
    HRD / Директор региона — может выписать без привязки к заданию.

    После создания штрафа:
    - Проверяем порог 5+ → автоматическая блокировка
    - Отправляем push исполнителю
    """
    # Проверяем роль
    allowed_roles = (
        UserRole.STORE_DIRECTOR,
        UserRole.DIVISION_DIRECTOR,
        UserRole.REGIONAL_DIRECTOR,
        UserRole.HRD,
    )
    if current_user.role not in allowed_roles:
        raise HTTPException(
            status_code=403,
            detail="Недостаточно прав для выписки штрафов"
        )

    # Создаём штраф
    penalty = Penalty(
        executor_id=body.executor_id,
        task_id=body.task_id,
        created_by_id=str(current_user.id),
        penalty_type=body.penalty_type,
        reason=body.reason,
        amount=body.amount,
        is_active=True,
    )
    db.add(penalty)
    await db.flush()  # Получаем ID до commit

    # Проверяем автоблокировку (5+ активных)
    should_block = await _check_auto_block(body.executor_id, db)
    if should_block:
        exec_result = await db.execute(
            select(User).where(User.id == body.executor_id)
        )
        executor = exec_result.scalar_one_or_none()
        if executor and executor.status != UserStatus.BLOCKED:
            executor.status = UserStatus.BLOCKED
            logger.warning(
                "Автоблокировка исполнителя %s: 5+ активных штрафов",
                body.executor_id
            )

    await db.commit()
    await db.refresh(penalty)

    # Push-уведомление исполнителю
    try:
        exec_result = await db.execute(
            select(User).where(User.id == body.executor_id)
        )
        executor = exec_result.scalar_one_or_none()
        if executor and executor.push_token:
            type_labels = {
                PenaltyType.CANCEL: "Отмена задания",
                PenaltyType.NO_SHOW: "Неявка на задание",
                PenaltyType.QUALITY: "Низкое качество работы",
                PenaltyType.LATE: "Систематические опоздания",
                PenaltyType.DOCS: "Нарушение с документами",
            }
            await push_service.send_push(
                token=executor.push_token,
                title=f"⚠️ Нарушение: {type_labels.get(body.penalty_type, 'штраф')}",
                body=body.reason[:100],
                data={
                    "type": "PENALTY_ISSUED",
                    "penalty_id": str(penalty.id),
                },
            )
    except Exception as e:
        logger.warning("Не удалось отправить push о штрафе: %s", e)

    logger.info(
        "Штраф выписан: executor=%s type=%s by=%s",
        body.executor_id, body.penalty_type, current_user.id
    )

    return _penalty_to_response(penalty)


@router.get("/", response_model=list[PenaltyResponse])
async def list_penalties(
    executor_id: Optional[str] = Query(None),
    penalty_type: Optional[PenaltyType] = Query(None),
    is_active: Optional[bool] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Список штрафов с фильтрами.
    HRD и директора — видят все.
    Исполнитель — только свои.
    """
    query = select(Penalty)

    # Исполнитель видит только свои штрафы
    if current_user.role == UserRole.EXECUTOR:
        query = query.where(Penalty.executor_id == str(current_user.id))
    elif executor_id:
        query = query.where(Penalty.executor_id == executor_id)

    if penalty_type:
        query = query.where(Penalty.penalty_type == penalty_type)
    if is_active is not None:
        query = query.where(Penalty.is_active == is_active)

    query = query.order_by(Penalty.created_at.desc()).limit(limit).offset(offset)

    result = await db.execute(query)
    penalties = result.scalars().all()

    return [_penalty_to_response(p) for p in penalties]


@router.get("/executor/{executor_id}", response_model=list[PenaltyResponse])
async def get_executor_penalties(
    executor_id: str,
    is_active: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Штрафы конкретного исполнителя."""
    # Исполнитель — только свои
    if current_user.role == UserRole.EXECUTOR and str(current_user.id) != executor_id:
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    query = select(Penalty).where(Penalty.executor_id == executor_id)
    if is_active is not None:
        query = query.where(Penalty.is_active == is_active)

    result = await db.execute(query.order_by(Penalty.created_at.desc()))
    return [_penalty_to_response(p) for p in result.scalars().all()]


@router.get("/executor/{executor_id}/risk", response_model=ExecutorRiskResponse)
async def get_executor_risk(
    executor_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Уровень риска исполнителя.
    Считает штрафы за 90 дней и определяет риск-уровень.
    Используется HR-службой и директорами при принятии решений.
    """
    threshold_90d = datetime.now(timezone.utc) - timedelta(days=90)

    # Всего активных
    r1 = await db.execute(
        select(func.count(Penalty.id))
        .where(and_(Penalty.executor_id == executor_id, Penalty.is_active == True))
    )
    total_active = r1.scalar_one()

    # За 90 дней
    r2 = await db.execute(
        select(func.count(Penalty.id))
        .where(and_(
            Penalty.executor_id == executor_id,
            Penalty.is_active == True,
            Penalty.created_at >= threshold_90d,
        ))
    )
    active_90d = r2.scalar_one()

    # Разбивка по типу
    r3 = await db.execute(
        select(Penalty.penalty_type, func.count(Penalty.id))
        .where(and_(Penalty.executor_id == executor_id, Penalty.is_active == True))
        .group_by(Penalty.penalty_type)
    )
    breakdown = {str(row[0]): row[1] for row in r3.all()}

    # Определяем уровень риска
    needs_hr_review = active_90d >= 3
    auto_blocked = total_active >= 5

    if auto_blocked:
        risk_level = "blocked"
    elif needs_hr_review:
        risk_level = "high"
    elif active_90d >= 1:
        risk_level = "medium"
    else:
        risk_level = "low"

    return ExecutorRiskResponse(
        executor_id=executor_id,
        active_penalties_total=total_active,
        active_penalties_90d=active_90d,
        risk_level=risk_level,
        needs_hr_review=needs_hr_review,
        auto_blocked=auto_blocked,
        penalty_breakdown=breakdown,
    )


@router.get("/{penalty_id}", response_model=PenaltyResponse)
async def get_penalty(
    penalty_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Подробности конкретного штрафа."""
    penalty = await _get_penalty_or_404(penalty_id, db)

    # Исполнитель видит только свои
    if (current_user.role == UserRole.EXECUTOR
            and str(current_user.id) != str(penalty.executor_id)):
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    return _penalty_to_response(penalty)


@router.put("/{penalty_id}/resolve", response_model=PenaltyResponse)
async def resolve_penalty(
    penalty_id: str,
    body: PenaltyResolveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Снять штраф (HR-служба или директор региона).
    Штраф деактивируется, причина сохраняется в resolution_note.
    Если было 5+ активных → проверяем нужна ли разблокировка.
    """
    if current_user.role not in (UserRole.HRD, UserRole.REGIONAL_DIRECTOR):
        raise HTTPException(
            status_code=403,
            detail="Снимать штрафы может только HRD или директор региона"
        )

    penalty = await _get_penalty_or_404(penalty_id, db)

    if not penalty.is_active:
        raise HTTPException(status_code=400, detail="Штраф уже снят")

    # Снимаем штраф
    penalty.is_active = False
    penalty.resolved_at = datetime.now(timezone.utc)
    penalty.resolved_by_id = str(current_user.id)
    penalty.resolution_note = body.resolution_note

    await db.commit()
    await db.refresh(penalty)

    # Проверяем — если теперь меньше 5 активных, снимаем автоблокировку
    should_still_block = await _check_auto_block(str(penalty.executor_id), db)
    if not should_still_block:
        exec_result = await db.execute(
            select(User).where(User.id == penalty.executor_id)
        )
        executor = exec_result.scalar_one_or_none()
        if executor and executor.status == UserStatus.BLOCKED:
            executor.status = UserStatus.ACTIVE
            await db.commit()
            logger.info(
                "Разблокировка исполнителя %s: активных штрафов < 5",
                penalty.executor_id
            )

    logger.info(
        "Штраф %s снят: by=%s note=%s",
        penalty_id, current_user.id, body.resolution_note[:50]
    )

    return _penalty_to_response(penalty)


# =============================================================================
# ВНУТРЕННИЕ ХЕЛПЕРЫ
# =============================================================================

def _penalty_to_response(p: Penalty) -> PenaltyResponse:
    """Конвертация модели в схему ответа."""
    return PenaltyResponse(
        id=str(p.id),
        executor_id=str(p.executor_id),
        task_id=str(p.task_id) if p.task_id else None,
        created_by_id=str(p.created_by_id),
        penalty_type=str(p.penalty_type),
        reason=p.reason,
        amount=float(p.amount) if p.amount else None,
        is_active=p.is_active,
        resolved_at=p.resolved_at.isoformat() if p.resolved_at else None,
        resolved_by_id=str(p.resolved_by_id) if p.resolved_by_id else None,
        resolution_note=p.resolution_note,
        created_at=p.created_at.isoformat(),
    )
