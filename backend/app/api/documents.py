# =============================================================================
# KARI.Самозанятые — API модуля документов (ЭДО)
# Файл: app/api/documents.py
# =============================================================================
# Эндпоинты для работы с документами: договоры ГПХ и акты выполненных работ.
#
# Маршруты:
#   POST /documents/generate          — сформировать документ для задания
#   GET  /documents/                   — список документов (с фильтрами)
#   GET  /documents/{doc_id}           — карточка документа
#   GET  /documents/{doc_id}/download  — скачать PDF
#   POST /documents/{doc_id}/sign/request  — запросить SMS-код подписи
#   POST /documents/{doc_id}/sign/confirm  — подтвердить подпись кодом
# =============================================================================

import logging
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.database import get_db
from app.core.security import get_current_user
from app.models.user import User, UserRole
from app.models.document import Document, DocumentType, DocumentStatus
from app.models.task import Task, TaskStatus
from app.schemas.document import (
    DocumentDetail,
    DocumentListResponse,
    DocumentShort,
    DocumentGenerateRequest,
    SignRequestInput,
    SignRequestResponse,
    SignConfirmInput,
    SignConfirmResponse,
)
from app.services import pdf_service
from app.services.sms_service import create_and_send_sms_code, verify_sms_code
from app.services.storage_service import StorageService

logger = logging.getLogger(__name__)

router = APIRouter()
storage = StorageService()


# =============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =============================================================================

def _make_doc_number(doc_type: str) -> str:
    """Генерирует номер документа."""
    year   = datetime.now(timezone.utc).year
    prefix = "ДГ" if doc_type == "contract" else "АКТ"
    short  = str(uuid4()).split("-")[0].upper()
    return f"KARI-{year}-{prefix}-{short}"


def _format_amount(amount_decimal) -> str:
    """Форматирует сумму: 1500.00 → '1 500,00'"""
    try:
        val = float(amount_decimal)
        return f"{val:,.2f}".replace(",", " ").replace(".", ",")
    except Exception:
        return str(amount_decimal)


def _format_date_ru(dt: datetime | None) -> str:
    months = ["января","февраля","марта","апреля","мая","июня",
              "июля","августа","сентября","октября","ноября","декабря"]
    if dt:
        return f"{dt.day:02d} {months[dt.month-1]} {dt.year} г."
    d = datetime.now(timezone.utc)
    return f"{d.day:02d} {months[d.month-1]} {d.year} г."


async def _get_task_or_404(task_id: UUID, db: AsyncSession) -> Task:
    """Получает задание или бросает 404."""
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Задание не найдено")
    return task


async def _get_executor_or_404(executor_id: UUID, db: AsyncSession) -> User:
    """Получает исполнителя или бросает 404."""
    result = await db.execute(select(User).where(User.id == executor_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Исполнитель не найден")
    return user


async def _get_document_or_404(doc_id: UUID, db: AsyncSession) -> Document:
    """Получает документ или бросает 404."""
    result = await db.execute(select(Document).where(Document.id == doc_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Документ не найден")
    return doc


# =============================================================================
# СФОРМИРОВАТЬ ДОКУМЕНТ
# =============================================================================

@router.post(
    "/generate",
    response_model=DocumentDetail,
    summary="Сформировать договор или акт для задания",
    description="""
Генерирует PDF-документ (договор ГПХ или акт выполненных работ) для задания.

**Когда вызывается:**
- Договор ГПХ — автоматически когда исполнитель берёт задание (TAKEN)
- Акт выполненных работ — когда директор принимает задание (ACCEPTED)

Документ сохраняется в MinIO и доступен для скачивания.
    """,
)
async def generate_document(
    body:         DocumentGenerateRequest,
    current_user: User = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
) -> Document:

    # Проверяем права: только директора могут инициировать формирование
    if current_user.role == UserRole.EXECUTOR:
        raise HTTPException(
            status_code=403,
            detail="Исполнитель не может инициировать формирование документа",
        )

    # Получаем задание
    task = await _get_task_or_404(body.task_id, db)

    # Проверяем что документ ещё не создан
    existing = await db.execute(
        select(Document).where(
            and_(
                Document.task_id == body.task_id,
                Document.doc_type == body.doc_type,
            )
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail=f"Документ типа '{body.doc_type}' для этого задания уже существует",
        )

    # Получаем исполнителя
    if not task.executor_id:
        raise HTTPException(
            status_code=400,
            detail="У задания нет исполнителя — невозможно создать документ",
        )
    executor = await _get_executor_or_404(task.executor_id, db)

    # Генерируем номер документа
    doc_number = _make_doc_number(body.doc_type)
    amount_str = _format_amount(task.price)
    work_date  = _format_date_ru(
        datetime.combine(task.scheduled_date, datetime.min.time())
        if task.scheduled_date else None
    )

    # Генерируем PDF
    try:
        if body.doc_type == DocumentType.CONTRACT:
            pdf_bytes = pdf_service.generate_contract_pdf(
                executor_name  = executor.full_name,
                executor_inn   = executor.inn or "—",
                executor_phone = executor.phone,
                task_title     = task.title,
                task_number    = task.number or str(task.id)[:8],
                store_address  = task.store_address,
                amount         = amount_str,
                work_date      = work_date,
                doc_number     = doc_number,
            )
        else:
            # Для акта ищем номер связанного договора
            contract_result = await db.execute(
                select(Document).where(
                    and_(
                        Document.task_id == body.task_id,
                        Document.doc_type == DocumentType.CONTRACT,
                    )
                )
            )
            contract = contract_result.scalar_one_or_none()

            pdf_bytes = pdf_service.generate_act_pdf(
                executor_name   = executor.full_name,
                executor_inn    = executor.inn or "—",
                executor_phone  = executor.phone,
                task_title      = task.title,
                task_number     = task.number or str(task.id)[:8],
                store_address   = task.store_address,
                amount          = amount_str,
                work_date       = work_date,
                contract_number = contract.number if contract else None,
                doc_number      = doc_number,
                director_name   = current_user.full_name,
            )
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Сохраняем PDF в MinIO
    now      = datetime.now(timezone.utc)
    prefix   = "contracts" if body.doc_type == DocumentType.CONTRACT else "acts"
    file_path = f"kari-docs/{now.year}/{now.month:02d}/{prefix}/{doc_number}.pdf"

    try:
        await storage.upload_bytes(
            bucket  = "kari-docs",
            path    = file_path,
            data    = pdf_bytes,
            content_type = "application/pdf",
        )
    except Exception as e:
        # Если MinIO недоступен — продолжаем без сохранения файла (для пилота терпимо)
        logger.warning(f"MinIO недоступен, PDF не сохранён: {e}")
        file_path = None

    # Сохраняем запись в БД
    doc = Document(
        id            = uuid4(),
        number        = doc_number,
        task_id       = body.task_id,
        doc_type      = body.doc_type,
        status        = DocumentStatus.DRAFT,
        executor_id   = executor.id,
        executor_name = executor.full_name,
        executor_inn  = executor.inn or "—",
        executor_phone= executor.phone,
        task_title    = task.title,
        task_number   = task.number or str(task.id)[:8],
        store_address = task.store_address,
        amount        = amount_str,
        work_date     = work_date,
        file_path     = file_path,
        file_size_bytes = str(len(pdf_bytes)) if pdf_bytes else None,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    logger.info(f"Документ сформирован: {doc_number} для задания {task.number}")
    return doc


# =============================================================================
# СПИСОК ДОКУМЕНТОВ
# =============================================================================

@router.get(
    "/",
    response_model=DocumentListResponse,
    summary="Список документов",
)
async def list_documents(
    task_id:      UUID | None = None,
    executor_id:  UUID | None = None,
    doc_type:     DocumentType | None = None,
    status:       DocumentStatus | None = None,
    skip:         int = 0,
    limit:        int = 50,
    current_user: User = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
) -> DocumentListResponse:

    filters = []

    # Исполнитель видит только свои документы
    if current_user.role == UserRole.EXECUTOR:
        filters.append(Document.executor_id == current_user.id)
    elif executor_id:
        filters.append(Document.executor_id == executor_id)

    if task_id:
        filters.append(Document.task_id == task_id)
    if doc_type:
        filters.append(Document.doc_type == doc_type)
    if status:
        filters.append(Document.status == status)

    # Подсчёт total
    from sqlalchemy import func
    count_q = select(func.count(Document.id))
    if filters:
        count_q = count_q.where(and_(*filters))
    total = (await db.execute(count_q)).scalar() or 0

    # Список с пагинацией
    q = select(Document).order_by(Document.created_at.desc()).offset(skip).limit(limit)
    if filters:
        q = q.where(and_(*filters))
    items = (await db.execute(q)).scalars().all()

    return DocumentListResponse(
        items=[DocumentShort.model_validate(d) for d in items],
        total=total,
        skip=skip,
        limit=limit,
    )


# =============================================================================
# КАРТОЧКА ДОКУМЕНТА
# =============================================================================

@router.get(
    "/{doc_id}",
    response_model=DocumentDetail,
    summary="Карточка документа",
)
async def get_document(
    doc_id:       UUID,
    current_user: User = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
) -> Document:

    doc = await _get_document_or_404(doc_id, db)

    # Исполнитель видит только свои документы
    if current_user.role == UserRole.EXECUTOR and doc.executor_id != current_user.id:
        raise HTTPException(status_code=403, detail="Нет доступа к этому документу")

    return doc


# =============================================================================
# СКАЧАТЬ PDF
# =============================================================================

@router.get(
    "/{doc_id}/download",
    summary="Скачать PDF документа",
    response_class=Response,
)
async def download_document(
    doc_id:       UUID,
    current_user: User = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    doc = await _get_document_or_404(doc_id, db)

    # Права доступа
    if current_user.role == UserRole.EXECUTOR and doc.executor_id != current_user.id:
        raise HTTPException(status_code=403, detail="Нет доступа к этому документу")

    if not doc.file_path:
        raise HTTPException(status_code=404, detail="PDF файл не найден")

    # Скачиваем из MinIO
    try:
        pdf_bytes = await storage.download_bytes(
            bucket = "kari-docs",
            path   = doc.file_path,
        )
    except Exception as e:
        logger.error(f"Ошибка скачивания PDF {doc.file_path}: {e}")
        raise HTTPException(status_code=503, detail="Файл временно недоступен")

    filename = f"{doc.number or doc_id}.pdf"
    return Response(
        content     = pdf_bytes,
        media_type  = "application/pdf",
        headers     = {"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# =============================================================================
# ЗАПРОСИТЬ SMS-КОД ДЛЯ ПОДПИСИ
# =============================================================================

@router.post(
    "/{doc_id}/sign/request",
    response_model=SignRequestResponse,
    summary="Отправить SMS-код для подписи документа",
    description="""
Отправляет 6-значный SMS-код на телефон исполнителя.
Вызывается когда исполнитель нажимает кнопку «Подписать» в мобильном приложении.

В режиме DEBUG код не отправляется реально — он возвращается в поле `debug_code`.
    """,
)
async def request_sign(
    doc_id:       UUID,
    current_user: User = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
) -> SignRequestResponse:

    doc = await _get_document_or_404(doc_id, db)

    # Подписывать может только сам исполнитель
    if current_user.role != UserRole.EXECUTOR or doc.executor_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Только исполнитель, указанный в документе, может его подписать",
        )

    # Нельзя переподписать уже подписанный документ
    if doc.status == DocumentStatus.SIGNED:
        raise HTTPException(status_code=400, detail="Документ уже подписан")

    if doc.status == DocumentStatus.CANCELLED:
        raise HTTPException(status_code=400, detail="Документ отменён")

    # Отправляем SMS
    sent, debug_code = await create_and_send_sms_code(
        db         = db,
        phone      = doc.executor_phone,
        purpose    = "sign",
        context_id = doc.id,
    )

    if not sent:
        raise HTTPException(
            status_code=503,
            detail="Не удалось отправить SMS. Попробуйте позже.",
        )

    # Обновляем время запроса подписи
    doc.status          = DocumentStatus.PENDING_SIGN
    doc.sign_request_at = datetime.now(timezone.utc)
    await db.commit()

    return SignRequestResponse(
        ok         = True,
        message    = f"SMS-код отправлен на {doc.executor_phone[-4:].rjust(10, '*')}",
        debug_code = debug_code,
    )


# =============================================================================
# ПОДТВЕРДИТЬ ПОДПИСЬ (ввести SMS-код)
# =============================================================================

@router.post(
    "/{doc_id}/sign/confirm",
    response_model=SignConfirmResponse,
    summary="Подтвердить подпись документа — ввести SMS-код",
    description="""
Исполнитель вводит SMS-код для подписи документа (ПЭП по 63-ФЗ).
После успешного подтверждения документ переходит в статус `signed`.

**Юридическая значимость:** подпись SMS-кодом равнозначна собственноручной
подписи в соответствии с соглашением о ПЭП, включённым в договор.
    """,
)
async def confirm_sign(
    doc_id:       UUID,
    body:         SignConfirmInput,
    request:      Request,
    current_user: User = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
) -> SignConfirmResponse:

    doc = await _get_document_or_404(doc_id, db)

    # Только исполнитель документа может подписать
    if current_user.role != UserRole.EXECUTOR or doc.executor_id != current_user.id:
        raise HTTPException(status_code=403, detail="Нет прав для подписи документа")

    if doc.status == DocumentStatus.SIGNED:
        raise HTTPException(status_code=400, detail="Документ уже подписан")

    if doc.status != DocumentStatus.PENDING_SIGN:
        raise HTTPException(
            status_code=400,
            detail="Сначала запросите SMS-код (POST /sign/request)",
        )

    # Проверяем SMS-код
    ok, error_msg = await verify_sms_code(
        db      = db,
        phone   = doc.executor_phone,
        code    = body.code,
        purpose = "sign",
    )

    if not ok:
        return SignConfirmResponse(ok=False, message=error_msg, document_id=doc.id)

    # Код верный — фиксируем подпись
    now = datetime.now(timezone.utc)
    doc.status              = DocumentStatus.SIGNED
    doc.executor_signed_at  = now
    doc.executor_sign_ip    = request.client.host if request.client else None
    doc.executor_sign_device= request.headers.get("User-Agent", "")[:200]

    await db.commit()

    logger.info(
        f"Документ {doc.number} подписан исполнителем {current_user.full_name} "
        f"в {now.isoformat()}"
    )

    return SignConfirmResponse(
        ok          = True,
        message     = "Документ успешно подписан",
        document_id = doc.id,
        signed_at   = now,
    )
