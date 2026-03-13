# =============================================================================
# KARI.Самозанятые — API заданий
# Файл: app/api/tasks.py
# =============================================================================
#
# Эндпоинты:
#
#   POST /tasks/                       — создать задание (директор магазина)
#   GET  /tasks/                       — мои задания (по роли)
#   GET  /tasks/exchange               — биржа заданий (только исполнители)
#   GET  /tasks/{task_id}              — подробности задания
#   PUT  /tasks/{task_id}              — редактировать (только DRAFT)
#   DELETE /tasks/{task_id}            — удалить (только DRAFT)
#
#   POST /tasks/{task_id}/publish      — опубликовать на бирже
#   POST /tasks/{task_id}/take         — взять задание (исполнитель)
#   POST /tasks/{task_id}/start        — начать работу (исполнитель)
#   POST /tasks/{task_id}/submit       — сдать выполненное (исполнитель)
#   POST /tasks/{task_id}/accept       — принять работу (директор магазина)
#   POST /tasks/{task_id}/reject       — отклонить работу (директор магазина)
#   POST /tasks/{task_id}/cancel       — отменить (до взятия в работу)
#
#   POST /tasks/{task_id}/photos       — загрузить фото (исполнитель, multipart)
#   GET  /tasks/{task_id}/photos       — список фото задания
#   DELETE /tasks/{task_id}/photos/{photo_id} — удалить фото (до сдачи)
#
#   GET  /tasks/templates/             — мои шаблоны заданий
#   POST /tasks/templates/             — создать шаблон
# =============================================================================

import math
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import get_db
from app.models.task import Task, TaskPhoto, TaskTemplate, TaskStatus, TaskCategory, PhotoVerificationStatus
from app.models.user import User, UserRole, UserStatus
from app.core.security import get_current_user, require_director, require_role
from app.schemas.task import (
    CreateTaskRequest,
    UpdateTaskRequest,
    RejectTaskRequest,
    CreateTemplateRequest,
    TaskResponse,
    TaskListResponse,
    TaskPhotoResponse,
    TaskTemplateResponse,
)
from app.services.storage_service import (
    upload_photo,
    validate_and_get_image_info,
    verify_photo_location,
    delete_photo,
)
from app.services import push_service  # Push-уведомления (Expo Push API)

logger = logging.getLogger(__name__)
router = APIRouter()


# =============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =============================================================================

async def _get_task_or_404(task_id: str, db: AsyncSession) -> Task:
    """Получает задание или выбрасывает 404."""
    result = await db.execute(
        select(Task)
        .where(Task.id == task_id)
        .options(selectinload(Task.photos))  # Сразу загружаем фото
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Задание не найдено")
    return task


def _generate_task_number(task_id_suffix: str) -> str:
    """Генерирует читаемый номер задания: ТЗ-2025-000123"""
    year = datetime.now(timezone.utc).year
    short = str(abs(hash(task_id_suffix)))[:6].zfill(6)
    return f"ТЗ-{year}-{short}"


def _to_response(task: Task) -> TaskResponse:
    """Конвертирует SQLAlchemy Task в Pydantic TaskResponse."""
    photos = [
        TaskPhotoResponse(
            id=str(p.id),
            sequence_number=p.sequence_number,
            file_path=p.file_path,
            file_size_mb=p.file_size_mb,
            image_width=p.image_width,
            image_height=p.image_height,
            photo_latitude=p.photo_latitude,
            photo_longitude=p.photo_longitude,
            distance_from_store_meters=p.distance_from_store_meters,
            geo_verification=p.geo_verification,
            taken_at=p.taken_at.isoformat() if p.taken_at else None,
            resolution_ok=p.resolution_ok,
        )
        for p in (task.photos or [])
    ]

    return TaskResponse(
        id=str(task.id),
        number=task.number,
        title=task.title,
        description=task.description,
        category=task.category,
        status=task.status,
        store_id=str(task.store_id),
        store_address=task.store_address,
        store_latitude=task.store_latitude,
        store_longitude=task.store_longitude,
        created_by_id=str(task.created_by_id),
        executor_id=str(task.executor_id) if task.executor_id else None,
        price=float(task.price),
        price_includes_tax=task.price_includes_tax,
        price_tax_amount=float(task.price_tax_amount),
        scheduled_date=task.scheduled_date.isoformat(),
        scheduled_time_start=str(task.scheduled_time_start) if task.scheduled_time_start else None,
        scheduled_time_end=str(task.scheduled_time_end) if task.scheduled_time_end else None,
        actual_start_at=task.actual_start_at.isoformat() if task.actual_start_at else None,
        actual_end_at=task.actual_end_at.isoformat() if task.actual_end_at else None,
        duration_minutes=task.duration_minutes,
        required_photo_count=task.required_photo_count,
        photo_instructions=task.photo_instructions,
        photos_verified=task.photos_verified,
        rejection_reason=task.rejection_reason,
        rejection_count=task.rejection_count,
        photos=photos,
        created_at=task.created_at.isoformat(),
        published_at=task.published_at.isoformat() if task.published_at else None,
        taken_at=task.taken_at.isoformat() if task.taken_at else None,
        submitted_at=task.submitted_at.isoformat() if task.submitted_at else None,
        completed_at=task.completed_at.isoformat() if task.completed_at else None,
    )


# =============================================================================
# СОЗДАНИЕ И РЕДАКТИРОВАНИЕ ЗАДАНИЙ
# =============================================================================

@router.post(
    "/",
    response_model=TaskResponse,
    summary="Создать задание",
    description="Директор магазина создаёт задание. Статус — DRAFT (черновик).",
)
async def create_task(
    body: CreateTaskRequest,
    current_user: User = Depends(require_role("store_director", "regional_director", "division_director")),
    db: AsyncSession = Depends(get_db),
) -> TaskResponse:

    task = Task(
        title=body.title,
        description=body.description,
        category=TaskCategory(body.category),
        status=TaskStatus.DRAFT,
        store_id=body.store_id,
        store_address=body.store_address,
        store_latitude=body.store_latitude,
        store_longitude=body.store_longitude,
        created_by_id=current_user.id,
        price=body.price,
        scheduled_date=body.scheduled_date,
        scheduled_time_start=body.scheduled_time_start,
        scheduled_time_end=body.scheduled_time_end,
        required_photo_count=body.required_photo_count,
        photo_instructions=body.photo_instructions,
        template_id=body.template_id,
    )
    db.add(task)
    await db.flush()

    # Присваиваем читаемый номер
    task.number = _generate_task_number(str(task.id))

    # Увеличиваем счётчик использования шаблона
    if body.template_id:
        tmpl = await db.get(TaskTemplate, body.template_id)
        if tmpl:
            tmpl.usage_count += 1

    logger.info(f"Создано задание {task.number}: '{task.title}' директором {current_user.phone}")
    await db.flush()
    return _to_response(task)


@router.get(
    "/",
    response_model=TaskListResponse,
    summary="Мои задания",
    description="""
- **Директор магазина** — задания своего магазина
- **Директор региона/подразделения** — все задания региона
- **Исполнитель** — задания которые он взял или завершил
    """,
)
async def list_tasks(
    status_f:   Optional[str] = Query(None, alias="status", description="Фильтр по статусу"),
    category:   Optional[str] = Query(None, description="Фильтр по категории"),
    store_id:   Optional[str] = Query(None, description="Фильтр по магазину"),
    date_from:  Optional[str] = Query(None, description="Дата от (YYYY-MM-DD)"),
    date_to:    Optional[str] = Query(None, description="Дата до (YYYY-MM-DD)"),
    page:       int           = Query(1, ge=1),
    size:       int           = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TaskListResponse:

    query = select(Task).options(selectinload(Task.photos))

    # Фильтруем по роли
    if current_user.role == UserRole.EXECUTOR:
        # Исполнитель видит только свои задания
        query = query.where(Task.executor_id == current_user.id)
    elif current_user.role == UserRole.STORE_DIRECTOR:
        # Директор магазина — задания своего магазина
        if current_user.store_id:
            query = query.where(Task.store_id == current_user.store_id)

    # Дополнительные фильтры
    if status_f:
        query = query.where(Task.status == status_f)
    if category:
        query = query.where(Task.category == category)
    if store_id:
        query = query.where(Task.store_id == store_id)
    if date_from:
        from datetime import date
        query = query.where(Task.scheduled_date >= date.fromisoformat(date_from))
    if date_to:
        from datetime import date
        query = query.where(Task.scheduled_date <= date.fromisoformat(date_to))

    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar() or 0

    offset = (page - 1) * size
    result = await db.execute(
        query.order_by(Task.scheduled_date.desc(), Task.created_at.desc())
        .offset(offset).limit(size)
    )
    tasks = result.scalars().all()

    return TaskListResponse(
        items=[_to_response(t) for t in tasks],
        total=total, page=page, size=size,
        pages=math.ceil(total / size) if total else 0,
    )


@router.get(
    "/exchange",
    response_model=TaskListResponse,
    summary="Биржа заданий — доступные задания",
    description="""
Показывает опубликованные задания которые ещё никто не взял.
Доступно только исполнителям (самозанятым).

Автоматически скрывает задания если:
- Исполнитель достиг лимита дохода 2 400 000 руб/год
- Статус ФНС исполнителя неактивен
    """,
)
async def get_exchange(
    category: Optional[str] = Query(None, description="Фильтр по категории"),
    date_from: Optional[str] = Query(None, description="Дата от (YYYY-MM-DD)"),
    page:      int           = Query(1, ge=1),
    size:      int           = Query(20, ge=1, le=100),
    current_user: User = Depends(require_role("executor")),
    db: AsyncSession = Depends(get_db),
) -> TaskListResponse:

    # Проверяем что исполнитель не достиг лимита
    if current_user.is_income_limit_exceeded:
        return TaskListResponse(items=[], total=0, page=1, size=size, pages=0)

    query = (
        select(Task)
        .options(selectinload(Task.photos))
        .where(Task.status == TaskStatus.PUBLISHED)
    )

    if category:
        query = query.where(Task.category == category)
    if date_from:
        from datetime import date
        query = query.where(Task.scheduled_date >= date.fromisoformat(date_from))

    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar() or 0

    offset = (page - 1) * size
    result = await db.execute(
        query.order_by(Task.scheduled_date.asc(), Task.created_at.asc())
        .offset(offset).limit(size)
    )
    tasks = result.scalars().all()

    return TaskListResponse(
        items=[_to_response(t) for t in tasks],
        total=total, page=page, size=size,
        pages=math.ceil(total / size) if total else 0,
    )


@router.get(
    "/{task_id}",
    response_model=TaskResponse,
    summary="Подробности задания",
)
async def get_task(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TaskResponse:
    task = await _get_task_or_404(task_id, db)
    return _to_response(task)


@router.put(
    "/{task_id}",
    response_model=TaskResponse,
    summary="Редактировать задание",
    description="Редактирование доступно только в статусе DRAFT.",
)
async def update_task(
    task_id: str,
    body: UpdateTaskRequest,
    current_user: User = Depends(require_role("store_director", "regional_director", "division_director")),
    db: AsyncSession = Depends(get_db),
) -> TaskResponse:

    task = await _get_task_or_404(task_id, db)

    if task.status != TaskStatus.DRAFT:
        raise HTTPException(
            status_code=400,
            detail=f"Нельзя редактировать задание в статусе '{task.status}'. Только DRAFT.",
        )
    if task.created_by_id != current_user.id and current_user.role != UserRole.REGIONAL_DIRECTOR:
        raise HTTPException(status_code=403, detail="Нет доступа к этому заданию")

    # Обновляем только переданные поля
    if body.title is not None:               task.title = body.title
    if body.description is not None:         task.description = body.description
    if body.price is not None:               task.price = body.price
    if body.scheduled_date is not None:      task.scheduled_date = body.scheduled_date
    if body.scheduled_time_start is not None: task.scheduled_time_start = body.scheduled_time_start
    if body.scheduled_time_end is not None:  task.scheduled_time_end = body.scheduled_time_end
    if body.required_photo_count is not None: task.required_photo_count = body.required_photo_count
    if body.photo_instructions is not None:  task.photo_instructions = body.photo_instructions

    return _to_response(task)


# =============================================================================
# ЖИЗНЕННЫЙ ЦИКЛ ЗАДАНИЯ
# =============================================================================

@router.post(
    "/{task_id}/publish",
    response_model=TaskResponse,
    summary="Опубликовать задание на бирже",
    description="DRAFT → PUBLISHED. Задание становится видимым исполнителям.",
)
async def publish_task(
    task_id: str,
    current_user: User = Depends(require_role("store_director", "regional_director", "division_director")),
    db: AsyncSession = Depends(get_db),
) -> TaskResponse:

    task = await _get_task_or_404(task_id, db)

    if task.status != TaskStatus.DRAFT:
        raise HTTPException(status_code=400, detail=f"Нельзя опубликовать из статуса '{task.status}'")

    task.status       = TaskStatus.PUBLISHED
    task.published_at = datetime.now(timezone.utc)

    logger.info(f"Задание {task.number} опубликовано на бирже")

    # Push: уведомляем всех активных исполнителей с push-токеном
    executors = await db.execute(
        select(User.fcm_token).where(
            User.role       == UserRole.EXECUTOR,
            User.fcm_token  != None,  # noqa: E711
        )
    )
    tokens = [row[0] for row in executors.fetchall()]
    if tokens:
        await push_service.notify_task_published(
            executor_tokens=tokens,
            task_title=task.title,
            store_name=task.store_address or "магазин KARI",
            task_id=str(task.id),
        )

    return _to_response(task)


@router.post(
    "/{task_id}/take",
    response_model=TaskResponse,
    summary="Взять задание (исполнитель)",
    description="PUBLISHED → TAKEN. Задание закрепляется за исполнителем.",
)
async def take_task(
    task_id: str,
    current_user: User = Depends(require_role("executor")),
    db: AsyncSession = Depends(get_db),
) -> TaskResponse:

    task = await _get_task_or_404(task_id, db)

    if task.status != TaskStatus.PUBLISHED:
        raise HTTPException(status_code=400, detail="Задание уже взято или недоступно")

    # -------------------------------------------------------------------------
    # ПРОВЕРКА СТОП-ЛИСТА (422-ФЗ ст.6 п.2 пп.8)
    # Проверяем ИНН исполнителя по базе бывших сотрудников и штрафников ФНС.
    # При совпадении — задание категорически не выдаётся.
    # Исполнителю отправляется push с причиной и двумя альтернативами.
    # -------------------------------------------------------------------------
    if current_user.inn:
        from app.models.stop_list import StopList
        from datetime import date as dt_date
        from sqlalchemy import and_, or_

        today = dt_date.today()
        stop_result = await db.execute(
            select(StopList).where(
                and_(
                    StopList.inn == current_user.inn,
                    StopList.is_active == True,           # noqa: E712
                    or_(
                        StopList.blocked_until == None,   # noqa: E711 — бессрочная
                        StopList.blocked_until > today,    # срок не истёк
                    ),
                )
            ).limit(1)
        )
        stop_entry = stop_result.scalar_one_or_none()

        if stop_entry:
            # Отправляем push с причиной и экраном StopListBlocked
            if current_user.fcm_token:
                try:
                    await push_service.notify_stop_list_blocked(
                        executor_token=current_user.fcm_token,
                        reason=stop_entry.reason,
                        blocked_until=(
                            stop_entry.blocked_until.isoformat()
                            if stop_entry.blocked_until else None
                        ),
                    )
                except Exception as push_err:
                    logger.warning(f"[STOP_LIST] Push не отправлен: {push_err}")

            logger.warning(
                f"[STOP_LIST] Исполнитель {current_user.phone} (ИНН {current_user.inn}) "
                f"заблокирован стоп-листом. Причина: {stop_entry.reason}. "
                f"Задание: {task.number}"
            )

            # Возвращаем структурированную ошибку — мобилка читает reason и blocked_until
            raise HTTPException(
                status_code=403,
                detail={
                    "code":          "STOP_LIST_BLOCKED",
                    "reason":        stop_entry.reason,
                    "reason_label":  {
                        "former_employee": "Бывший сотрудник KARI",
                        "fns_fine":        "Нарушение по ИНН в ФНС",
                        "manual":          "Блокировка HR-службой",
                    }.get(stop_entry.reason, "Блокировка"),
                    "message":       {
                        "former_employee": (
                            "По закону 422-ФЗ (ст. 6, п. 2) вы не можете получать "
                            "задания от бывшего работодателя в течение 2 лет "
                            "с даты увольнения. Это требование ФНС, не KARI."
                        ),
                        "fns_fine": (
                            "По вашему ИНН в ФНС зафиксированы нарушения. "
                            "Для уточнения обратитесь в HR-службу KARI."
                        ),
                        "manual": (
                            "Выдача заданий временно приостановлена. "
                            "Обратитесь в HR-службу KARI для уточнения."
                        ),
                    }.get(stop_entry.reason, "Выдача заданий недоступна."),
                    "blocked_until": (
                        stop_entry.blocked_until.isoformat()
                        if stop_entry.blocked_until else None
                    ),
                },
            )
    # -------------------------------------------------------------------------
    # КОНЕЦ ПРОВЕРКИ СТОП-ЛИСТА
    # -------------------------------------------------------------------------

    # Проверяем лимит дохода исполнителя
    if current_user.is_income_limit_exceeded:
        raise HTTPException(
            status_code=403,
            detail="Вы достигли лимита дохода 2 400 000 руб/год. Новые задания недоступны.",
        )

    # Проверяем статус ФНС
    from app.models.user import FnsStatus
    if current_user.fns_status != FnsStatus.ACTIVE:
        raise HTTPException(
            status_code=403,
            detail="Ваш статус самозанятого неактивен в ФНС. Обратитесь в поддержку.",
        )

    task.status      = TaskStatus.TAKEN
    task.executor_id = current_user.id
    task.taken_at    = datetime.now(timezone.utc)

    logger.info(f"Задание {task.number} взято исполнителем {current_user.phone}")

    # Push: уведомляем директора магазина который создал задание
    creator = await db.get(User, task.created_by_id)
    if creator and creator.fcm_token:
        await push_service.notify_task_taken(
            director_token=creator.fcm_token,
            executor_name=current_user.full_name,
            task_title=task.title,
            task_id=str(task.id),
        )

    return _to_response(task)


@router.post(
    "/{task_id}/start",
    response_model=TaskResponse,
    summary="Начать выполнение (исполнитель)",
    description="TAKEN → IN_PROGRESS. Фиксирует фактическое время начала.",
)
async def start_task(
    task_id: str,
    current_user: User = Depends(require_role("executor")),
    db: AsyncSession = Depends(get_db),
) -> TaskResponse:

    task = await _get_task_or_404(task_id, db)

    if task.executor_id != current_user.id:
        raise HTTPException(status_code=403, detail="Это не ваше задание")
    if task.status != TaskStatus.TAKEN:
        raise HTTPException(status_code=400, detail=f"Нельзя начать из статуса '{task.status}'")

    task.status         = TaskStatus.IN_PROGRESS
    task.actual_start_at = datetime.now(timezone.utc)

    logger.info(f"Задание {task.number} начато исполнителем {current_user.phone}")
    return _to_response(task)


@router.post(
    "/{task_id}/submit",
    response_model=TaskResponse,
    summary="Сдать выполненное задание (исполнитель)",
    description="""
IN_PROGRESS → SUBMITTED.

Перед сдачей система проверяет:
- Загружено нужное количество фото (required_photo_count)
- Все фото прошли или проходят геопроверку
    """,
)
async def submit_task(
    task_id: str,
    current_user: User = Depends(require_role("executor")),
    db: AsyncSession = Depends(get_db),
) -> TaskResponse:

    task = await _get_task_or_404(task_id, db)

    if task.executor_id != current_user.id:
        raise HTTPException(status_code=403, detail="Это не ваше задание")
    if task.status != TaskStatus.IN_PROGRESS:
        raise HTTPException(status_code=400, detail=f"Нельзя сдать из статуса '{task.status}'")

    # Проверяем количество загруженных фото
    loaded_photos = len(task.photos or [])
    if loaded_photos < task.required_photo_count:
        raise HTTPException(
            status_code=400,
            detail=f"Необходимо загрузить {task.required_photo_count} фото. "
                   f"Загружено: {loaded_photos}.",
        )

    # Проверяем прошли ли фото геопроверку
    failed_photos = [p for p in task.photos if p.geo_verification == PhotoVerificationStatus.FAILED]
    if failed_photos and not task.photos_verified:
        raise HTTPException(
            status_code=400,
            detail=f"{len(failed_photos)} фото не прошли проверку геолокации. "
                   "Обратитесь к директору магазина для ручного подтверждения.",
        )

    task.status        = TaskStatus.SUBMITTED
    task.actual_end_at = datetime.now(timezone.utc)
    task.submitted_at  = datetime.now(timezone.utc)

    logger.info(f"Задание {task.number} сдано исполнителем {current_user.phone}")

    # Push: уведомляем директора магазина что работа ждёт проверки
    creator = await db.get(User, task.created_by_id)
    if creator and creator.fcm_token:
        await push_service.notify_task_submitted(
            director_token=creator.fcm_token,
            executor_name=current_user.full_name,
            task_title=task.title,
            task_id=str(task.id),
        )

    return _to_response(task)


@router.post(
    "/{task_id}/accept",
    response_model=TaskResponse,
    summary="Принять выполненное задание (директор магазина)",
    description="""
SUBMITTED → ACCEPTED.

После принятия автоматически:
1. Запускается выплата исполнителю
2. Регистрируется чек в ФНС
3. Формируется акт выполненных работ
    """,
)
async def accept_task(
    task_id: str,
    current_user: User = Depends(require_role("store_director", "regional_director", "division_director")),
    db: AsyncSession = Depends(get_db),
) -> TaskResponse:

    task = await _get_task_or_404(task_id, db)

    if task.status != TaskStatus.SUBMITTED:
        raise HTTPException(status_code=400, detail=f"Нельзя принять из статуса '{task.status}'")

    task.status         = TaskStatus.ACCEPTED
    task.accepted_by_id = current_user.id
    task.accepted_at    = datetime.now(timezone.utc)

    logger.info(
        f"Задание {task.number} принято директором {current_user.phone}. "
        "Запускается выплата..."
    )

    # Запускаем Celery-задачу: создать Payment + зарегистрировать чек ФНС
    from app.services.payment_service import create_payment_for_task
    payment = await create_payment_for_task(db=db, task=task)

    # Push: уведомляем исполнителя что работа принята и выплата начислена
    if task.executor_id:
        executor = await db.get(User, task.executor_id)
        if executor and executor.fcm_token:
            await push_service.notify_task_accepted(
                executor_token=executor.fcm_token,
                task_title=task.title,
                amount=float(task.price),
                task_id=str(task.id),
            )

    return _to_response(task)


@router.post(
    "/{task_id}/reject",
    response_model=TaskResponse,
    summary="Отклонить выполненное задание (директор магазина)",
    description="""
SUBMITTED → REJECTED.

Исполнитель получает уведомление с причиной.
Может исправить замечания и сдать снова (загрузить новые фото).
    """,
)
async def reject_task(
    task_id: str,
    body: RejectTaskRequest,
    current_user: User = Depends(require_role("store_director", "regional_director", "division_director")),
    db: AsyncSession = Depends(get_db),
) -> TaskResponse:

    task = await _get_task_or_404(task_id, db)

    if task.status != TaskStatus.SUBMITTED:
        raise HTTPException(status_code=400, detail=f"Нельзя отклонить из статуса '{task.status}'")

    task.status           = TaskStatus.REJECTED
    task.rejection_reason = body.reason
    task.rejection_count  += 1

    # Возвращаем задание в IN_PROGRESS чтобы исполнитель мог исправить
    task.status       = TaskStatus.IN_PROGRESS
    task.submitted_at = None

    logger.info(
        f"Задание {task.number} отклонено директором {current_user.phone}. "
        f"Причина: {body.reason}"
    )

    # Push: уведомляем исполнителя с причиной отклонения
    if task.executor_id:
        executor = await db.get(User, task.executor_id)
        if executor and executor.fcm_token:
            await push_service.notify_task_rejected(
                executor_token=executor.fcm_token,
                task_title=task.title,
                reason=body.reason,
                task_id=str(task.id),
            )

    return _to_response(task)


@router.post(
    "/{task_id}/cancel",
    response_model=TaskResponse,
    summary="Отменить задание",
    description="Отмена доступна только до взятия в работу (DRAFT или PUBLISHED).",
)
async def cancel_task(
    task_id: str,
    current_user: User = Depends(require_role("store_director", "regional_director", "division_director")),
    db: AsyncSession = Depends(get_db),
) -> TaskResponse:

    task = await _get_task_or_404(task_id, db)

    if task.status not in (TaskStatus.DRAFT, TaskStatus.PUBLISHED):
        raise HTTPException(
            status_code=400,
            detail=f"Нельзя отменить задание в статусе '{task.status}'. "
                   "Задание уже взято исполнителем.",
        )

    task.status = TaskStatus.CANCELLED
    logger.info(f"Задание {task.number} отменено директором {current_user.phone}")
    return _to_response(task)


# =============================================================================
# ФОТООТЧЁТ (ТЗ 3.10)
# =============================================================================

@router.post(
    "/{task_id}/photos",
    response_model=TaskPhotoResponse,
    summary="Загрузить фото к заданию (исполнитель)",
    description="""
Загружает фотографию как часть отчёта о выполнении задания.

**Требования к фото:**
- Формат: JPEG или PNG
- Минимальное разрешение: 1280×720 пикселей
- Максимальный размер: 10 МБ
- Геолокация в EXIF (фото должно быть сделано с включённым GPS)

**Геопроверка:** фото должно быть сделано в радиусе 300 м от магазина.
    """,
)
async def upload_task_photo(
    task_id: str,
    file: UploadFile = File(..., description="Фотография (JPEG/PNG, мин 1280×720, макс 10МБ)"),
    current_user: User = Depends(require_role("executor")),
    db: AsyncSession = Depends(get_db),
) -> TaskPhotoResponse:

    task = await _get_task_or_404(task_id, db)

    # Проверяем права и статус
    if task.executor_id != current_user.id:
        raise HTTPException(status_code=403, detail="Это не ваше задание")
    if task.status not in (TaskStatus.TAKEN, TaskStatus.IN_PROGRESS, TaskStatus.REJECTED):
        raise HTTPException(
            status_code=400,
            detail=f"Нельзя загружать фото в статусе '{task.status}'",
        )

    # Проверяем лимит фотографий
    existing_count = len(task.photos or [])
    if existing_count >= task.required_photo_count:
        raise HTTPException(
            status_code=400,
            detail=f"Уже загружено максимальное количество фото ({task.required_photo_count}). "
                   "Удалите существующее фото чтобы загрузить новое.",
        )

    # Проверяем тип файла
    if file.content_type not in ("image/jpeg", "image/jpg", "image/png"):
        raise HTTPException(
            status_code=400,
            detail="Поддерживаются только форматы JPEG и PNG",
        )

    # Читаем файл
    file_data = await file.read()

    # Валидируем изображение и извлекаем EXIF
    try:
        image_info = validate_and_get_image_info(file_data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Определяем номер фото
    sequence_number = existing_count + 1

    # Загружаем в MinIO
    try:
        file_path = await upload_photo(
            file_data=file_data,
            task_id=task_id,
            sequence_number=sequence_number,
            content_type=file.content_type,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    # Геопроверка — сравниваем координаты фото и магазина
    geo_status   = PhotoVerificationStatus.PENDING
    distance     = None

    if image_info["latitude"] and image_info["longitude"]:
        if task.store_latitude and task.store_longitude:
            status_str, distance = verify_photo_location(
                photo_lat=image_info["latitude"],
                photo_lon=image_info["longitude"],
                store_lat=task.store_latitude,
                store_lon=task.store_longitude,
            )
            geo_status = (
                PhotoVerificationStatus.VERIFIED
                if status_str == "verified"
                else PhotoVerificationStatus.FAILED
            )
        else:
            # Координаты магазина не заданы — пропускаем геопроверку
            geo_status = PhotoVerificationStatus.VERIFIED

    # Сохраняем запись о фото в БД
    photo = TaskPhoto(
        task_id=task.id,
        executor_id=current_user.id,
        sequence_number=sequence_number,
        file_path=file_path,
        file_size_bytes=len(file_data),
        image_width=image_info["width"],
        image_height=image_info["height"],
        photo_latitude=image_info["latitude"],
        photo_longitude=image_info["longitude"],
        distance_from_store_meters=distance,
        geo_verification=geo_status,
        taken_at=image_info["taken_at"],
    )
    db.add(photo)

    # Обновляем флаг photos_verified на задании
    # Все фото проверены если нет ни одного с FAILED или PENDING
    await db.flush()
    # Перечитываем все фото задания для пересчёта
    all_photos_result = await db.execute(
        select(TaskPhoto).where(TaskPhoto.task_id == task.id)
    )
    all_photos = all_photos_result.scalars().all()
    task.photos_verified = all(
        p.geo_verification == PhotoVerificationStatus.VERIFIED or p.manually_verified
        for p in all_photos
    )

    logger.info(
        f"Фото #{sequence_number} загружено к заданию {task.number}. "
        f"Геопроверка: {geo_status} ({distance} м от магазина)"
    )

    return TaskPhotoResponse(
        id=str(photo.id),
        sequence_number=photo.sequence_number,
        file_path=photo.file_path,
        file_size_mb=photo.file_size_mb,
        image_width=photo.image_width,
        image_height=photo.image_height,
        photo_latitude=photo.photo_latitude,
        photo_longitude=photo.photo_longitude,
        distance_from_store_meters=photo.distance_from_store_meters,
        geo_verification=photo.geo_verification,
        taken_at=photo.taken_at.isoformat() if photo.taken_at else None,
        resolution_ok=photo.resolution_ok,
    )


@router.delete(
    "/{task_id}/photos/{photo_id}",
    summary="Удалить фото (до сдачи задания)",
)
async def delete_task_photo(
    task_id: str,
    photo_id: str,
    current_user: User = Depends(require_role("executor")),
    db: AsyncSession = Depends(get_db),
) -> dict:

    task = await _get_task_or_404(task_id, db)

    if task.executor_id != current_user.id:
        raise HTTPException(status_code=403, detail="Это не ваше задание")
    if task.status == TaskStatus.SUBMITTED:
        raise HTTPException(status_code=400, detail="Нельзя удалить фото сданного задания")

    result = await db.execute(
        select(TaskPhoto).where(
            and_(TaskPhoto.id == photo_id, TaskPhoto.task_id == task.id)
        )
    )
    photo = result.scalar_one_or_none()
    if not photo:
        raise HTTPException(status_code=404, detail="Фото не найдено")

    await delete_photo(photo.file_path)
    await db.delete(photo)

    return {"success": True, "message": "Фото удалено"}


# =============================================================================
# ШАБЛОНЫ ЗАДАНИЙ
# =============================================================================

@router.get(
    "/templates/list",
    response_model=list[TaskTemplateResponse],
    summary="Список шаблонов заданий",
)
async def list_templates(
    current_user: User = Depends(require_role("store_director", "regional_director", "division_director")),
    db: AsyncSession = Depends(get_db),
) -> list[TaskTemplateResponse]:

    query = select(TaskTemplate).where(TaskTemplate.is_active == True)

    # Директор магазина видит шаблоны своего магазина и региона
    if current_user.role == UserRole.STORE_DIRECTOR:
        query = query.where(
            or_(
                TaskTemplate.store_id == current_user.store_id,
                TaskTemplate.region_id == current_user.region_id,
                and_(TaskTemplate.store_id == None, TaskTemplate.region_id == None),
            )
        )

    result = await db.execute(query.order_by(TaskTemplate.usage_count.desc()))
    templates = result.scalars().all()

    return [
        TaskTemplateResponse(
            id=str(t.id),
            title=t.title,
            description=t.description,
            category=t.category,
            default_price=float(t.default_price),
            required_photo_count=t.required_photo_count,
            photo_instructions=t.photo_instructions,
            usage_count=t.usage_count,
            is_active=t.is_active,
        )
        for t in templates
    ]


@router.post(
    "/templates/",
    response_model=TaskTemplateResponse,
    summary="Создать шаблон задания",
)
async def create_template(
    body: CreateTemplateRequest,
    current_user: User = Depends(require_role("store_director", "regional_director", "division_director")),
    db: AsyncSession = Depends(get_db),
) -> TaskTemplateResponse:

    template = TaskTemplate(
        title=body.title,
        description=body.description,
        category=TaskCategory(body.category),
        store_id=body.store_id,
        region_id=body.region_id,
        created_by_id=current_user.id,
        default_price=body.default_price,
        required_photo_count=body.required_photo_count,
        photo_instructions=body.photo_instructions,
    )
    db.add(template)
    await db.flush()

    logger.info(f"Создан шаблон '{body.title}' директором {current_user.phone}")

    return TaskTemplateResponse(
        id=str(template.id),
        title=template.title,
        description=template.description,
        category=template.category,
        default_price=float(template.default_price),
        required_photo_count=template.required_photo_count,
        photo_instructions=template.photo_instructions,
        usage_count=0,
        is_active=True,
    )
