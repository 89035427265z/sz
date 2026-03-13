# =============================================================================
# KARI.Самозанятые — API стоп-листа
# Файл: app/api/stop_list.py
# =============================================================================
#
# Эндпоинты:
#
#   GET  /stop-list/              — список записей (HRD, директор региона)
#   POST /stop-list/              — добавить вручную
#   POST /stop-list/import/       — импорт из Excel (массовая загрузка)
#   GET  /stop-list/check/{inn}   — проверить ИНН (для биржи)
#   PUT  /stop-list/{id}/deactivate — снять блокировку досрочно
#   DELETE /stop-list/{id}        — удалить запись (только региональный директор)
#
# Кто имеет доступ:
#   - Директор региона  — полный доступ (CRUD)
#   - HRD (роль hrd)    — добавить / просмотреть / снять
#   - Исполнитель       — только check (через take_task, не напрямую)
#
# =============================================================================

import io
import logging
from datetime import date, datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_

from app.database import get_db
from app.models.stop_list import StopList, StopListReason
from app.models.user import User, UserRole
from app.core.security import get_current_user, require_role

logger = logging.getLogger(__name__)
router = APIRouter()


# =============================================================================
# PYDANTIC СХЕМЫ
# =============================================================================

class StopListCreateRequest(BaseModel):
    """Тело запроса: добавить одну запись в стоп-лист."""
    inn: str                                   # ИНН физлица (12 цифр)
    full_name: Optional[str] = None            # ФИО для справки
    reason: StopListReason                     # Причина блокировки
    reason_details: Optional[str] = None       # Подробности
    employment_end_date: Optional[date] = None # Дата увольнения (для former_employee)
    blocked_until: Optional[date] = None       # Явная дата снятия (NULL = авто)


class StopListResponse(BaseModel):
    """Ответ: данные одной записи стоп-листа."""
    id: str
    inn: str
    full_name: Optional[str]
    reason: str
    reason_label: str       # Человеко-читаемая причина
    reason_details: Optional[str]
    employment_end_date: Optional[str]
    blocked_until: Optional[str]
    created_at: str
    is_active: bool
    is_expired: bool        # Истёк ли срок блокировки (для автоочистки)


class StopListListResponse(BaseModel):
    """Ответ: список записей с пагинацией."""
    items: list[StopListResponse]
    total: int
    page: int
    size: int
    pages: int


class StopListCheckResponse(BaseModel):
    """Ответ: результат проверки ИНН."""
    inn: str
    is_blocked: bool
    reason: Optional[str] = None             # Код причины (для мобилки)
    reason_label: Optional[str] = None       # Текст причины
    reason_details: Optional[str] = None     # Подробности
    blocked_until: Optional[str] = None      # Дата снятия (если известна)
    message_for_executor: Optional[str] = None  # Текст для показа исполнителю


class ImportResultResponse(BaseModel):
    """Ответ: результат импорта из Excel."""
    imported: int     # Успешно добавлено
    skipped: int      # Пропущено (уже есть в стоп-листе)
    errors: list[str] # Ошибки по строкам


# =============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =============================================================================

# Человеко-читаемые метки причин
REASON_LABELS = {
    StopListReason.FORMER_EMPLOYEE: "Бывший сотрудник KARI (< 2 лет)",
    StopListReason.FNS_FINE:        "Штраф ФНС по этому ИНН",
    StopListReason.MANUAL:          "Ручная блокировка HR",
    StopListReason.FISCAL_RISK:     "Фискальный риск (переквалификация)",  # v2: добавлено миграцией 0005
}

# Текст сообщения для исполнителя по причине
EXECUTOR_MESSAGES = {
    StopListReason.FORMER_EMPLOYEE: (
        "По закону 422-ФЗ (ст. 6, п. 2) вы не можете получать задания "
        "от бывшего работодателя в течение 2 лет с даты увольнения. "
        "Это ограничение исходит от Федеральной налоговой службы, не от KARI."
    ),
    StopListReason.FNS_FINE: (
        "По вашему ИНН в ФНС зафиксированы нарушения. "
        "Для выяснения подробностей обратитесь в HR-службу KARI."
    ),
    StopListReason.MANUAL: (
        "Выдача заданий временно приостановлена. "
        "Для выяснения причин обратитесь в HR-службу KARI."
    ),
    StopListReason.FISCAL_RISK: (
        "Выдача заданий приостановлена в связи с выявленными фискальными рисками. "
        "Система зафиксировала признаки переквалификации договора ГПХ в трудовой "
        "(422-ФЗ). Для выяснения подробностей обратитесь в HR-службу KARI."
    ),
}


def _to_response(entry: StopList) -> StopListResponse:
    """Конвертирует запись StopList в Pydantic ответ."""
    today = date.today()
    is_expired = bool(entry.blocked_until and entry.blocked_until <= today)

    return StopListResponse(
        id=str(entry.id),
        inn=entry.inn,
        full_name=entry.full_name,
        reason=entry.reason,
        reason_label=REASON_LABELS.get(entry.reason, entry.reason),
        reason_details=entry.reason_details,
        employment_end_date=entry.employment_end_date.isoformat() if entry.employment_end_date else None,
        blocked_until=entry.blocked_until.isoformat() if entry.blocked_until else None,
        created_at=entry.created_at.isoformat(),
        is_active=entry.is_active,
        is_expired=is_expired,
    )


async def _check_inn_in_db(inn: str, db: AsyncSession) -> Optional[StopList]:
    """
    Проверяет ИНН в стоп-листе.
    Возвращает активную запись (не истёкшую) или None.
    """
    today = date.today()
    result = await db.execute(
        select(StopList).where(
            and_(
                StopList.inn == inn,
                StopList.is_active == True,  # noqa: E712
                or_(
                    StopList.blocked_until == None,    # noqa: E711 — бессрочная
                    StopList.blocked_until > today,     # срок не истёк
                ),
            )
        ).limit(1)
    )
    return result.scalar_one_or_none()


# =============================================================================
# ПРОВЕРКА ИНН (используется из tasks.py при take_task)
# =============================================================================

@router.get(
    "/check/{inn}",
    response_model=StopListCheckResponse,
    summary="Проверить ИНН в стоп-листе",
    description="Проверяет, заблокирован ли исполнитель по ИНН. Вызывается автоматически при взятии задания.",
)
async def check_inn(
    inn: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StopListCheckResponse:

    entry = await _check_inn_in_db(inn, db)

    if not entry:
        return StopListCheckResponse(inn=inn, is_blocked=False)

    return StopListCheckResponse(
        inn=inn,
        is_blocked=True,
        reason=entry.reason,
        reason_label=REASON_LABELS.get(entry.reason, entry.reason),
        reason_details=entry.reason_details,
        blocked_until=entry.blocked_until.isoformat() if entry.blocked_until else None,
        message_for_executor=EXECUTOR_MESSAGES.get(entry.reason),
    )


# =============================================================================
# СПИСОК ЗАПИСЕЙ
# =============================================================================

@router.get(
    "/",
    response_model=StopListListResponse,
    summary="Список стоп-листа",
    description="Все записи стоп-листа с фильтрами. Только для HRD и директора региона.",
)
async def list_stop_list(
    search:     Optional[str]  = Query(None,  description="Поиск по ИНН или ФИО"),
    reason:     Optional[str]  = Query(None,  description="Фильтр по причине"),
    active_only: bool          = Query(True,  description="Только активные блокировки"),
    page:       int            = Query(1, ge=1),
    size:       int            = Query(50, ge=1, le=200),
    current_user: User = Depends(require_role("regional_director", "hrd")),
    db: AsyncSession = Depends(get_db),
) -> StopListListResponse:
    import math

    query = select(StopList)

    # Фильтр по активности
    if active_only:
        today = date.today()
        query = query.where(
            and_(
                StopList.is_active == True,  # noqa: E712
                or_(
                    StopList.blocked_until == None,   # noqa: E711
                    StopList.blocked_until > today,
                ),
            )
        )

    # Поиск по ИНН или ФИО
    if search:
        query = query.where(
            or_(
                StopList.inn.ilike(f"%{search}%"),
                StopList.full_name.ilike(f"%{search}%"),
            )
        )

    # Фильтр по причине
    if reason:
        query = query.where(StopList.reason == reason)

    # Подсчёт
    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar() or 0

    # Пагинация
    offset = (page - 1) * size
    result = await db.execute(
        query.order_by(StopList.created_at.desc()).offset(offset).limit(size)
    )
    entries = result.scalars().all()

    return StopListListResponse(
        items=[_to_response(e) for e in entries],
        total=total,
        page=page,
        size=size,
        pages=math.ceil(total / size) if total else 0,
    )


# =============================================================================
# ДОБАВИТЬ ВРУЧНУЮ
# =============================================================================

@router.post(
    "/",
    response_model=StopListResponse,
    status_code=201,
    summary="Добавить ИНН в стоп-лист",
    description="Ручное добавление записи. Для бывших сотрудников дата снятия рассчитывается автоматически (дата_увольнения + 2 года).",
)
async def add_to_stop_list(
    body: StopListCreateRequest,
    current_user: User = Depends(require_role("regional_director", "hrd")),
    db: AsyncSession = Depends(get_db),
) -> StopListResponse:

    # Валидация ИНН
    if not body.inn.isdigit() or len(body.inn) != 12:
        raise HTTPException(
            status_code=400,
            detail="ИНН должен содержать ровно 12 цифр",
        )

    # Проверяем, нет ли уже активной записи
    existing = await _check_inn_in_db(body.inn, db)
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"ИНН {body.inn} уже находится в стоп-листе (причина: {existing.reason})",
        )

    # Рассчитываем дату снятия для бывших сотрудников
    blocked_until = body.blocked_until
    if body.reason == StopListReason.FORMER_EMPLOYEE and body.employment_end_date:
        # По закону: 2 года с даты увольнения
        auto_until = date(
            body.employment_end_date.year + 2,
            body.employment_end_date.month,
            body.employment_end_date.day,
        )
        # Берём более позднюю из явной и автоматической
        if blocked_until:
            blocked_until = max(blocked_until, auto_until)
        else:
            blocked_until = auto_until

    entry = StopList(
        inn=body.inn,
        full_name=body.full_name,
        reason=body.reason,
        reason_details=body.reason_details,
        employment_end_date=body.employment_end_date,
        blocked_until=blocked_until,
        created_by_id=current_user.id,
        is_active=True,
    )
    db.add(entry)
    await db.flush()

    logger.info(
        f"[STOP_LIST] ИНН {body.inn} добавлен. "
        f"Причина: {body.reason}. Заблокировано до: {blocked_until}. "
        f"Добавил: {current_user.phone}"
    )

    return _to_response(entry)


# =============================================================================
# ИМПОРТ ИЗ EXCEL
# =============================================================================

@router.post(
    "/import/",
    response_model=ImportResultResponse,
    summary="Импорт стоп-листа из Excel",
    description="""
Массовая загрузка ИНН из Excel-файла.

**Формат Excel:**
| ИНН (12 цифр) | ФИО | Причина | Дата увольнения (ДД.ММ.ГГГГ) | Комментарий |
|---|---|---|---|---|
| 123456789012 | Иванов Иван | former_employee | 15.01.2025 | ... |

Причины: `former_employee`, `fns_fine`, `manual`

Уже существующие активные записи — пропускаются (не дублируются).
    """,
)
async def import_stop_list_excel(
    file: UploadFile = File(..., description="Excel файл (.xlsx)"),
    current_user: User = Depends(require_role("regional_director", "hrd")),
    db: AsyncSession = Depends(get_db),
) -> ImportResultResponse:

    # Проверяем тип файла
    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(
            status_code=400,
            detail="Поддерживаются только Excel файлы (.xlsx, .xls)",
        )

    try:
        import openpyxl
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="Библиотека openpyxl не установлена. Добавьте openpyxl в requirements.txt",
        )

    # Читаем файл
    contents = await file.read()
    wb = openpyxl.load_workbook(io.BytesIO(contents), data_only=True)
    ws = wb.active

    imported = 0
    skipped = 0
    errors = []

    # Пропускаем заголовок (строка 1)
    for row_num, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        if not row or not row[0]:
            continue  # Пустая строка

        try:
            inn_raw = str(row[0]).strip().replace(" ", "")
            full_name = str(row[1]).strip() if row[1] else None
            reason_raw = str(row[2]).strip().lower() if row[2] else "manual"
            date_raw = row[3]  # Дата увольнения (может быть datetime из Excel)
            reason_details = str(row[4]).strip() if len(row) > 4 and row[4] else None

            # Валидация ИНН
            if not inn_raw.isdigit() or len(inn_raw) != 12:
                errors.append(f"Строка {row_num}: ИНН '{inn_raw}' неверный формат (нужно 12 цифр)")
                continue

            # Разбираем причину
            try:
                reason = StopListReason(reason_raw)
            except ValueError:
                reason = StopListReason.MANUAL
                if reason_details:
                    reason_details = f"Исходная причина: {reason_raw}. {reason_details}"
                else:
                    reason_details = f"Исходная причина: {reason_raw}"

            # Разбираем дату увольнения
            employment_end_date = None
            if date_raw:
                if isinstance(date_raw, datetime):
                    employment_end_date = date_raw.date()
                elif isinstance(date_raw, date):
                    employment_end_date = date_raw
                elif isinstance(date_raw, str):
                    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y"):
                        try:
                            employment_end_date = datetime.strptime(date_raw, fmt).date()
                            break
                        except ValueError:
                            continue

            # Проверяем дубликат
            existing = await _check_inn_in_db(inn_raw, db)
            if existing:
                skipped += 1
                continue

            # Рассчитываем дату снятия
            blocked_until = None
            if reason == StopListReason.FORMER_EMPLOYEE and employment_end_date:
                blocked_until = date(
                    employment_end_date.year + 2,
                    employment_end_date.month,
                    employment_end_date.day,
                )

            # Создаём запись
            entry = StopList(
                inn=inn_raw,
                full_name=full_name,
                reason=reason,
                reason_details=reason_details,
                employment_end_date=employment_end_date,
                blocked_until=blocked_until,
                created_by_id=current_user.id,
                is_active=True,
            )
            db.add(entry)
            imported += 1

        except Exception as e:
            errors.append(f"Строка {row_num}: непредвиденная ошибка — {str(e)}")
            continue

    if imported > 0:
        await db.flush()

    logger.info(
        f"[STOP_LIST] Импорт завершён: добавлено {imported}, "
        f"пропущено {skipped}, ошибок {len(errors)}. "
        f"Импортировал: {current_user.phone}"
    )

    return ImportResultResponse(imported=imported, skipped=skipped, errors=errors)


# =============================================================================
# СНЯТЬ БЛОКИРОВКУ ДОСРОЧНО
# =============================================================================

@router.put(
    "/{entry_id}/deactivate",
    response_model=StopListResponse,
    summary="Снять блокировку досрочно",
    description="Деактивирует запись. Исполнитель сможет снова брать задания.",
)
async def deactivate_stop_list(
    entry_id: str,
    current_user: User = Depends(require_role("regional_director", "hrd")),
    db: AsyncSession = Depends(get_db),
) -> StopListResponse:

    entry = await db.get(StopList, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Запись стоп-листа не найдена")

    if not entry.is_active:
        raise HTTPException(status_code=400, detail="Запись уже деактивирована")

    entry.is_active = False
    entry.deactivated_at = datetime.now(timezone.utc)
    entry.deactivated_by_id = current_user.id
    await db.flush()

    logger.info(
        f"[STOP_LIST] ИНН {entry.inn} снят с блокировки. "
        f"Снял: {current_user.phone}"
    )

    return _to_response(entry)


# =============================================================================
# УДАЛИТЬ ЗАПИСЬ (только директор региона)
# =============================================================================

@router.delete(
    "/{entry_id}",
    summary="Удалить запись из стоп-листа",
    description="Полное удаление. Только для директора региона.",
)
async def delete_stop_list_entry(
    entry_id: str,
    current_user: User = Depends(require_role("regional_director")),
    db: AsyncSession = Depends(get_db),
) -> dict:

    entry = await db.get(StopList, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Запись не найдена")

    inn = entry.inn
    await db.delete(entry)

    logger.warning(
        f"[STOP_LIST] ИНН {inn} УДАЛЁН из стоп-листа. "
        f"Удалил: {current_user.phone} (role={current_user.role})"
    )

    return {"success": True, "message": f"ИНН {inn} удалён из стоп-листа"}


# =============================================================================
# ПЛАНОВОЕ СНЯТИЕ ИСТЁКШИХ БЛОКИРОВОК
# (вызывается из Celery задачи)
# =============================================================================

async def auto_expire_stop_list(db: AsyncSession) -> int:
    """
    Снимает блокировки, у которых истёк срок (blocked_until < сегодня).
    Вызывается Celery задачей, например, каждую ночь в 01:00 МСК.
    Возвращает количество деактивированных записей.
    """
    today = date.today()
    result = await db.execute(
        select(StopList).where(
            and_(
                StopList.is_active == True,         # noqa: E712
                StopList.blocked_until != None,      # noqa: E711
                StopList.blocked_until <= today,     # срок истёк
            )
        )
    )
    expired = result.scalars().all()

    for entry in expired:
        entry.is_active = False
        entry.deactivated_at = datetime.now(timezone.utc)

    if expired:
        await db.flush()
        logger.info(f"[STOP_LIST] Автоматически снято {len(expired)} истёкших блокировок")

    return len(expired)
