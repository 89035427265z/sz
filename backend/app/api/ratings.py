# =============================================================================
# KARI.Самозанятые v2 — API рейтинга исполнителей
# Файл: app/api/ratings.py
# =============================================================================
#
# Эндпоинты:
#
#   POST /ratings/                          — выставить оценку (директор магазина)
#   GET  /ratings/executor/{executor_id}   — все оценки исполнителя
#   GET  /ratings/executor/{executor_id}/summary — средний рейтинг + статистика
#   GET  /ratings/task/{task_id}           — оценка за конкретное задание
#   GET  /ratings/store/{store_id}         — все оценки выданные магазином
#   DELETE /ratings/{rating_id}            — удалить оценку (только директор региона)
#
# Кто имеет доступ:
#   - Директор магазина — выставить оценку за своё принятое задание
#   - Директор подразделения — просмотр оценок исполнителей в своих магазинах
#   - Директор региона — полный доступ включая удаление
#   - HRD — просмотр оценок всех исполнителей
#
# =============================================================================

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models.rating import Rating
from app.models.user import User, UserRole
from app.core.security import get_current_user, require_role

logger = logging.getLogger(__name__)
router = APIRouter()


# =============================================================================
# PYDANTIC СХЕМЫ
# =============================================================================

class RatingCreateRequest(BaseModel):
    """Тело запроса: выставить оценку исполнителю."""
    task_id: str            # ID задания (должно быть принято/завершено)
    executor_id: str        # ID исполнителя
    score: int = Field(..., ge=1, le=5, description="Оценка от 1 до 5 звёзд")
    comment: Optional[str] = Field(None, max_length=500, description="Комментарий директора")


class RatingResponse(BaseModel):
    """Ответ: одна оценка."""
    id: str
    task_id: str
    executor_id: str
    rated_by_id: str
    score: int
    comment: Optional[str]
    created_at: str

    class Config:
        from_attributes = True


class RatingSummaryResponse(BaseModel):
    """Сводный рейтинг исполнителя."""
    executor_id: str
    total_ratings: int          # Всего оценок
    average_score: float        # Средний балл (округлённый до 2 знаков)
    score_1: int                # Количество оценок 1 звезда
    score_2: int
    score_3: int
    score_4: int
    score_5: int
    is_low_rating: bool         # True если средний < 3.0 (метка «низкий рейтинг»)


# =============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =============================================================================

async def _get_rating_or_404(rating_id: str, db: AsyncSession) -> Rating:
    """Получает оценку или выбрасывает 404."""
    result = await db.execute(select(Rating).where(Rating.id == rating_id))
    rating = result.scalar_one_or_none()
    if not rating:
        raise HTTPException(status_code=404, detail="Оценка не найдена")
    return rating


# =============================================================================
# ЭНДПОИНТЫ
# =============================================================================

@router.post("/", response_model=RatingResponse, status_code=201)
async def create_rating(
    body: RatingCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Выставить оценку исполнителю за выполненное задание.
    Только директор магазина, только после принятия работы.
    Одно задание — одна оценка (повторный запрос → 409).
    """
    # Проверяем роль — только директор магазина
    if current_user.role not in (
        UserRole.STORE_DIRECTOR, UserRole.REGIONAL_DIRECTOR
    ):
        raise HTTPException(
            status_code=403,
            detail="Выставлять оценки может только директор магазина"
        )

    # Проверяем дубликат: одно задание — одна оценка
    existing = await db.execute(
        select(Rating).where(
            Rating.task_id == body.task_id,
            Rating.executor_id == body.executor_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail="Оценка за это задание уже выставлена"
        )

    # Создаём оценку
    rating = Rating(
        task_id=body.task_id,
        executor_id=body.executor_id,
        rated_by_id=str(current_user.id),
        score=body.score,
        comment=body.comment,
    )
    db.add(rating)
    await db.commit()
    await db.refresh(rating)

    logger.info(
        "Оценка выставлена: executor=%s task=%s score=%d by=%s",
        body.executor_id, body.task_id, body.score, current_user.id
    )

    return RatingResponse(
        id=str(rating.id),
        task_id=str(rating.task_id),
        executor_id=str(rating.executor_id),
        rated_by_id=str(rating.rated_by_id),
        score=rating.score,
        comment=rating.comment,
        created_at=rating.created_at.isoformat(),
    )


@router.get("/executor/{executor_id}", response_model=list[RatingResponse])
async def get_executor_ratings(
    executor_id: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Список всех оценок конкретного исполнителя.
    Доступно: директоры, HRD. Исполнитель видит только свои.
    """
    # Исполнитель может смотреть только свой рейтинг
    if current_user.role == UserRole.EXECUTOR:
        if str(current_user.id) != executor_id:
            raise HTTPException(
                status_code=403,
                detail="Вы можете просматривать только свои оценки"
            )

    result = await db.execute(
        select(Rating)
        .where(Rating.executor_id == executor_id)
        .order_by(Rating.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    ratings = result.scalars().all()

    return [
        RatingResponse(
            id=str(r.id),
            task_id=str(r.task_id),
            executor_id=str(r.executor_id),
            rated_by_id=str(r.rated_by_id),
            score=r.score,
            comment=r.comment,
            created_at=r.created_at.isoformat(),
        )
        for r in ratings
    ]


@router.get("/executor/{executor_id}/summary", response_model=RatingSummaryResponse)
async def get_executor_rating_summary(
    executor_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Сводный рейтинг исполнителя: средний балл и распределение по звёздам.
    Используется в профиле исполнителя и карточках на бирже заданий.
    """
    # Подсчёт всех оценок
    result = await db.execute(
        select(
            func.count(Rating.id).label("total"),
            func.avg(Rating.score).label("avg_score"),
            func.sum((Rating.score == 1).cast(type_=func.Integer)).label("s1"),
            func.sum((Rating.score == 2).cast(type_=func.Integer)).label("s2"),
            func.sum((Rating.score == 3).cast(type_=func.Integer)).label("s3"),
            func.sum((Rating.score == 4).cast(type_=func.Integer)).label("s4"),
            func.sum((Rating.score == 5).cast(type_=func.Integer)).label("s5"),
        ).where(Rating.executor_id == executor_id)
    )
    row = result.one()

    total = row.total or 0
    avg = float(row.avg_score or 0)

    return RatingSummaryResponse(
        executor_id=executor_id,
        total_ratings=total,
        average_score=round(avg, 2),
        score_1=int(row.s1 or 0),
        score_2=int(row.s2 or 0),
        score_3=int(row.s3 or 0),
        score_4=int(row.s4 or 0),
        score_5=int(row.s5 or 0),
        is_low_rating=(avg < 3.0 and total > 0),
    )


@router.get("/task/{task_id}", response_model=Optional[RatingResponse])
async def get_task_rating(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Оценка за конкретное задание.
    Возвращает None если оценка ещё не выставлена.
    """
    result = await db.execute(
        select(Rating).where(Rating.task_id == task_id)
    )
    rating = result.scalar_one_or_none()

    if not rating:
        return None

    return RatingResponse(
        id=str(rating.id),
        task_id=str(rating.task_id),
        executor_id=str(rating.executor_id),
        rated_by_id=str(rating.rated_by_id),
        score=rating.score,
        comment=rating.comment,
        created_at=rating.created_at.isoformat(),
    )


@router.delete("/{rating_id}", status_code=204)
async def delete_rating(
    rating_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.REGIONAL_DIRECTOR)),
):
    """
    Удалить оценку.
    Только директор региона (например, ошибочно выставленная оценка).
    """
    rating = await _get_rating_or_404(rating_id, db)

    logger.warning(
        "Удаление оценки %s (executor=%s score=%d) директором региона %s",
        rating_id, rating.executor_id, rating.score, current_user.id
    )

    await db.delete(rating)
    await db.commit()
