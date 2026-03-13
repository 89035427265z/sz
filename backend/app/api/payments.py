# =============================================================================
# KARI.Самозанятые — API выплат
# Файл: app/api/payments.py
# =============================================================================
#
# Эндпоинты:
#
#   --- Индивидуальные выплаты ---
#   GET  /payments/                        — список выплат
#   GET  /payments/{payment_id}            — детали выплаты
#   POST /payments/{payment_id}/retry      — повторить неуспешную выплату
#
#   --- Реестры массовых выплат (ТЗ 3.12) ---
#   POST /payments/registries/             — загрузить Excel-реестр
#   GET  /payments/registries/             — список реестров
#   GET  /payments/registries/{id}         — детали реестра
#   GET  /payments/registries/{id}/items   — строки реестра с результатами проверок
#   POST /payments/registries/{id}/approve — подтвердить реестр к оплате
#   GET  /payments/registries/{id}/export  — скачать XML для 1С
#
#   --- Чеки ФНС (ТЗ 3.11) ---
#   GET  /payments/receipts/               — список чеков
#   GET  /payments/receipts/{id}           — детали чека
# =============================================================================

import io
import math
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from app.config import settings
from app.database import get_db
from app.models.payment import (
    Payment, PaymentRegistry, PaymentRegistryItem, FnsReceipt,
    PaymentStatus, RegistryStatus, RegistryItemStatus,
)
from app.models.user import User, UserRole
from app.core.security import get_current_user, require_director, require_regional
from app.schemas.payment import (
    PaymentResponse, PaymentListResponse,
    RegistryResponse, RegistryListResponse, RegistryItemResponse,
    FnsReceiptResponse,
)
from app.services.payment_service import (
    parse_registry_excel,
    validate_registry_item,
    generate_xml_for_1c,
)
from app.services.storage_service import upload_photo  # переиспользуем для Excel

logger = logging.getLogger(__name__)
router = APIRouter()


# =============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =============================================================================

def _payment_to_response(p: Payment, executor: Optional[User] = None) -> PaymentResponse:
    return PaymentResponse(
        id=str(p.id),
        task_id=str(p.task_id),
        executor_id=str(p.executor_id),
        executor_name=executor.full_name if executor else None,
        executor_phone=executor.phone if executor else None,
        amount=float(p.amount),
        tax_amount=float(p.tax_amount),
        total_amount=float(p.total_amount),
        status=p.status,
        bank_card_masked=p.bank_card_masked,
        bank_name=p.bank_name,
        sovcombank_transaction_id=p.sovcombank_transaction_id,
        error_message=p.error_message,
        retry_count=p.retry_count,
        fns_receipt_id=str(p.fns_receipt_id) if p.fns_receipt_id else None,
        created_at=p.created_at.isoformat(),
        processing_at=p.processing_at.isoformat() if p.processing_at else None,
        completed_at=p.completed_at.isoformat() if p.completed_at else None,
    )


def _registry_to_response(r: PaymentRegistry) -> RegistryResponse:
    return RegistryResponse(
        id=str(r.id),
        name=r.name,
        number=r.number,
        status=r.status,
        file_name_original=r.file_name_original,
        total_rows=r.total_rows,
        valid_rows=r.valid_rows,
        invalid_rows=r.invalid_rows,
        paid_rows=r.paid_rows,
        failed_rows=r.failed_rows,
        total_amount=float(r.total_amount or 0),
        paid_amount=float(r.paid_amount or 0),
        validation_summary=r.validation_summary,
        xml_export_path=r.xml_export_path,
        created_at=r.created_at.isoformat(),
        validated_at=r.validated_at.isoformat() if r.validated_at else None,
        approved_at=r.approved_at.isoformat() if r.approved_at else None,
        completed_at=r.completed_at.isoformat() if r.completed_at else None,
    )


def _item_to_response(item: PaymentRegistryItem) -> RegistryItemResponse:
    return RegistryItemResponse(
        id=str(item.id),
        row_number=item.row_number,
        executor_inn=item.executor_inn,
        executor_name=item.executor_name,
        service_description=item.service_description,
        amount=float(item.amount or 0),
        work_date=str(item.work_date) if item.work_date else "",
        status=item.status,
        check_fns_status=item.check_fns_status,
        check_income_limit=item.check_income_limit,
        check_duplicate=item.check_duplicate,
        check_amount=item.check_amount,
        check_budget=item.check_budget,
        all_checks_passed=item.all_checks_passed,
        validation_errors=item.validation_errors,
        error_message=item.error_message,
        payment_id=str(item.payment_id) if item.payment_id else None,
    )


def _generate_registry_number() -> str:
    """Генерирует номер реестра: РЕЕ-2025-000123"""
    year = datetime.now(timezone.utc).year
    suffix = str(abs(hash(str(datetime.now()))))[:6].zfill(6)
    return f"РЕЕ-{year}-{suffix}"


# =============================================================================
# ИНДИВИДУАЛЬНЫЕ ВЫПЛАТЫ
# =============================================================================

@router.get(
    "/",
    response_model=PaymentListResponse,
    summary="Список выплат",
    description="""
- **Директор региона** — все выплаты региона
- **Директор магазина** — выплаты по заданиям своего магазина
- **Исполнитель** — свои выплаты
    """,
)
async def list_payments(
    status_f:    Optional[str] = Query(None, alias="status"),
    executor_id: Optional[str] = Query(None, description="Фильтр по исполнителю"),
    page:        int           = Query(1, ge=1),
    size:        int           = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaymentListResponse:

    query = select(Payment)

    if current_user.role == UserRole.EXECUTOR:
        query = query.where(Payment.executor_id == current_user.id)
    elif executor_id:
        query = query.where(Payment.executor_id == executor_id)

    if status_f:
        query = query.where(Payment.status == status_f)

    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar() or 0

    offset = (page - 1) * size
    result = await db.execute(
        query.order_by(Payment.created_at.desc()).offset(offset).limit(size)
    )
    payments = result.scalars().all()

    return PaymentListResponse(
        items=[_payment_to_response(p) for p in payments],
        total=total, page=page, size=size,
        pages=math.ceil(total / size) if total else 0,
    )


@router.get(
    "/{payment_id}",
    response_model=PaymentResponse,
    summary="Детали выплаты",
)
async def get_payment(
    payment_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaymentResponse:

    payment = await db.get(Payment, payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Выплата не найдена")

    # Исполнитель видит только свои выплаты
    if current_user.role == UserRole.EXECUTOR and payment.executor_id != current_user.id:
        raise HTTPException(status_code=403, detail="Нет доступа")

    executor = await db.get(User, payment.executor_id)
    return _payment_to_response(payment, executor)


@router.post(
    "/{payment_id}/retry",
    response_model=PaymentResponse,
    summary="Повторить неуспешную выплату",
    description="Доступно только для выплат со статусом FAILED. Не более 3 попыток.",
)
async def retry_payment(
    payment_id: str,
    current_user: User = Depends(require_director),
    db: AsyncSession = Depends(get_db),
) -> PaymentResponse:

    payment = await db.get(Payment, payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Выплата не найдена")

    if payment.status != PaymentStatus.FAILED:
        raise HTTPException(
            status_code=400,
            detail=f"Повтор доступен только для выплат со статусом FAILED. Текущий статус: {payment.status}",
        )

    if payment.retry_count >= 3:
        raise HTTPException(
            status_code=400,
            detail="Превышено максимальное количество попыток (3). Обратитесь в поддержку.",
        )

    payment.status      = PaymentStatus.PENDING
    payment.retry_count += 1
    payment.error_message = None

    logger.info(f"Выплата {payment_id} поставлена на повтор (попытка {payment.retry_count})")

    # TODO: запустить Celery-задачу повторной отправки
    # from app.tasks.payment_tasks import process_payment
    # process_payment.delay(str(payment.id))

    return _payment_to_response(payment)


# =============================================================================
# РЕЕСТРЫ МАССОВЫХ ВЫПЛАТ (ТЗ 3.12)
# =============================================================================

@router.post(
    "/registries/",
    response_model=RegistryResponse,
    summary="Загрузить Excel-реестр для массовых выплат",
    description="""
Загружает файл Excel с реестром выплат и **автоматически запускает проверку** каждой строки.

**Шаблон Excel** (6 столбцов, начиная со строки 2):
| A | B | C | D | E | F |
|---|---|---|---|---|---|
| ИНН (12 цифр) | ФИО | Описание услуги | Сумма (руб) | Дата (ДД.ММ.ГГГГ) | Примечание |

**Ограничения:**
- Формат: .xlsx
- Максимум строк: 1 000
- Максимум размер: 5 МБ
    """,
)
async def upload_registry(
    name: str = Query(..., description="Название реестра, например 'Выплаты декабрь 2025'"),
    file: UploadFile = File(..., description="Excel файл (.xlsx)"),
    current_user: User = Depends(require_director),
    db: AsyncSession = Depends(get_db),
) -> RegistryResponse:

    # Проверка формата файла
    if not file.filename.endswith(".xlsx"):
        raise HTTPException(
            status_code=400,
            detail="Поддерживается только формат .xlsx (Excel 2007+)",
        )

    file_data = await file.read()

    # Проверка размера (5 МБ)
    if len(file_data) > 5 * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail=f"Файл слишком большой: {len(file_data) / 1_048_576:.1f} МБ. Максимум: 5 МБ",
        )

    # Парсим Excel
    try:
        rows = parse_registry_excel(file_data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Создаём реестр в БД
    registry = PaymentRegistry(
        name=name,
        number=_generate_registry_number(),
        created_by_id=current_user.id,
        region_id=current_user.region_id,
        status=RegistryStatus.UPLOADED,
        file_path=f"registries/{datetime.now(timezone.utc).strftime('%Y/%m/%d')}/{file.filename}",
        file_name_original=file.filename,
        file_size_bytes=len(file_data),
        total_rows=len(rows),
    )
    db.add(registry)
    await db.flush()

    logger.info(
        f"Реестр загружен: {registry.number} | "
        f"{len(rows)} строк | Загрузил: {current_user.phone}"
    )

    # Создаём строки реестра и запускаем валидацию
    registry.status = RegistryStatus.VALIDATING
    valid_count   = 0
    invalid_count = 0
    total_amount  = 0

    for row in rows:
        item = PaymentRegistryItem(
            registry_id=registry.id,
            row_number=row["row_number"],
            executor_inn=row["inn"],
            executor_name=row["name"],
            service_description=row["description"],
            amount=row["amount"],
            work_date=row["work_date"],
            status=RegistryItemStatus.PENDING,
        )

        # Если парсинг строки провалился — сразу помечаем как невалидную
        if row["parse_error"]:
            item.status            = RegistryItemStatus.INVALID
            item.validation_errors = [{"code": "PARSE_ERROR", "message": row["parse_error"]}]
            item.check_fns_status   = False
            item.check_income_limit = False
            item.check_duplicate    = False
            item.check_amount       = False
            item.check_budget       = False
            invalid_count += 1
        else:
            db.add(item)
            await db.flush()
            # Запускаем 5 проверок
            item = await validate_registry_item(db, item, str(registry.id))
            if item.status == RegistryItemStatus.VALID:
                valid_count  += 1
                total_amount += float(item.amount or 0)
            else:
                invalid_count += 1

        db.add(item)

    # Обновляем счётчики реестра
    registry.valid_rows   = valid_count
    registry.invalid_rows = invalid_count
    registry.total_amount = total_amount
    registry.validated_at = datetime.now(timezone.utc)
    registry.status = (
        RegistryStatus.VALIDATED
        if invalid_count == 0
        else RegistryStatus.REJECTED
    )

    # Формируем сводку валидации
    registry.validation_summary = {
        "total":   len(rows),
        "valid":   valid_count,
        "invalid": invalid_count,
        "ready_to_approve": invalid_count == 0,
        "message": (
            f"Все {valid_count} строк прошли проверку. Реестр готов к подтверждению."
            if invalid_count == 0
            else f"Найдено ошибок: {invalid_count}. Исправьте файл и загрузите заново."
        ),
    }

    logger.info(
        f"Реестр {registry.number} проверен: "
        f"✅ {valid_count} / ❌ {invalid_count} строк"
    )

    return _registry_to_response(registry)


@router.get(
    "/registries/",
    response_model=RegistryListResponse,
    summary="Список реестров выплат",
)
async def list_registries(
    status_f: Optional[str] = Query(None, alias="status"),
    page:     int           = Query(1, ge=1),
    size:     int           = Query(20, ge=1, le=100),
    current_user: User = Depends(require_director),
    db: AsyncSession = Depends(get_db),
) -> RegistryListResponse:

    query = select(PaymentRegistry)

    if status_f:
        query = query.where(PaymentRegistry.status == status_f)

    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar() or 0

    offset = (page - 1) * size
    result = await db.execute(
        query.order_by(PaymentRegistry.created_at.desc()).offset(offset).limit(size)
    )
    registries = result.scalars().all()

    return RegistryListResponse(
        items=[_registry_to_response(r) for r in registries],
        total=total, page=page, size=size,
        pages=math.ceil(total / size) if total else 0,
    )


@router.get(
    "/registries/{registry_id}",
    response_model=RegistryResponse,
    summary="Детали реестра",
)
async def get_registry(
    registry_id: str,
    current_user: User = Depends(require_director),
    db: AsyncSession = Depends(get_db),
) -> RegistryResponse:

    registry = await db.get(PaymentRegistry, registry_id)
    if not registry:
        raise HTTPException(status_code=404, detail="Реестр не найден")
    return _registry_to_response(registry)


@router.get(
    "/registries/{registry_id}/items",
    response_model=list[RegistryItemResponse],
    summary="Строки реестра с результатами проверок",
    description="Возвращает все строки реестра — с результатами каждой из 5 проверок.",
)
async def get_registry_items(
    registry_id: str,
    status_f:   Optional[str] = Query(None, alias="status", description="valid / invalid / paid / failed"),
    page:       int           = Query(1, ge=1),
    size:       int           = Query(100, ge=1, le=1000),
    current_user: User = Depends(require_director),
    db: AsyncSession = Depends(get_db),
) -> list[RegistryItemResponse]:

    query = select(PaymentRegistryItem).where(
        PaymentRegistryItem.registry_id == registry_id
    )
    if status_f:
        query = query.where(PaymentRegistryItem.status == status_f)

    offset = (page - 1) * size
    result = await db.execute(
        query.order_by(PaymentRegistryItem.row_number).offset(offset).limit(size)
    )
    items = result.scalars().all()
    return [_item_to_response(i) for i in items]


@router.post(
    "/registries/{registry_id}/approve",
    response_model=RegistryResponse,
    summary="Подтвердить реестр к оплате",
    description="""
**Только директор региона.**

Запускает пакетную выплату по всем валидным строкам реестра.
После подтверждения реестр нельзя отменить.

Предварительно убедитесь что все строки прошли проверку (статус реестра VALIDATED).
    """,
)
async def approve_registry(
    registry_id: str,
    current_user: User = Depends(require_regional),
    db: AsyncSession = Depends(get_db),
) -> RegistryResponse:

    registry = await db.get(PaymentRegistry, registry_id)
    if not registry:
        raise HTTPException(status_code=404, detail="Реестр не найден")

    if registry.status != RegistryStatus.VALIDATED:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Реестр нельзя подтвердить в статусе '{registry.status}'. "
                "Для подтверждения нужен статус VALIDATED (все строки прошли проверку)."
            ),
        )

    registry.status         = RegistryStatus.PROCESSING
    registry.approved_by_id = current_user.id
    registry.approved_at    = datetime.now(timezone.utc)
    registry.processing_at  = datetime.now(timezone.utc)

    await db.commit()

    logger.info(
        f"Реестр {registry.number} подтверждён директором {current_user.phone}. "
        f"Запускаются выплаты ({registry.valid_rows} строк, {registry.total_amount} руб)..."
    )

    # Запускаем Celery-задачу пакетной выплаты
    from app.tasks.payment_tasks import process_registry as _process_registry_task
    _process_registry_task.apply_async(
        args=[str(registry.id)],
        queue="payments",
        countdown=2,  # небольшая задержка чтобы commit успел применится
    )

    return _registry_to_response(registry)


@router.get(
    "/registries/{registry_id}/export",
    summary="Скачать XML для выгрузки в 1С",
    description="Генерирует XML-файл по оплаченным строкам реестра для импорта в 1С.",
)
async def export_registry_xml(
    registry_id: str,
    current_user: User = Depends(require_director),
    db: AsyncSession = Depends(get_db),
):
    registry = await db.get(PaymentRegistry, registry_id)
    if not registry:
        raise HTTPException(status_code=404, detail="Реестр не найден")

    if registry.status not in (RegistryStatus.COMPLETED, RegistryStatus.PARTIAL, RegistryStatus.PROCESSING):
        raise HTTPException(
            status_code=400,
            detail="XML доступен только для реестров в обработке или завершённых",
        )

    # Получаем оплаченные строки
    result = await db.execute(
        select(PaymentRegistryItem).where(
            and_(
                PaymentRegistryItem.registry_id == registry_id,
                PaymentRegistryItem.status == RegistryItemStatus.PAID,
            )
        ).order_by(PaymentRegistryItem.row_number)
    )
    items = result.scalars().all()

    xml_content = generate_xml_for_1c(registry, items)
    filename = f"{registry.number or registry_id}_1C.xml"

    logger.info(f"XML для 1С сформирован: {filename} ({len(items)} строк)")

    return StreamingResponse(
        io.StringIO(xml_content),
        media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# =============================================================================
# ЧЕКИ ФНС (ТЗ 3.11 — Контроль аннулирования)
# =============================================================================

@router.get(
    "/receipts/",
    response_model=list[FnsReceiptResponse],
    summary="Список чеков ФНС",
    description="""
Показывает чеки ФНС. Фильтр по статусу:
- **created** — действующие чеки
- **cancelled** — аннулированные (требуют внимания бухгалтерии)
- **error** — ошибка при выдаче
    """,
)
async def list_receipts(
    status_f:    Optional[str] = Query(None, alias="status"),
    executor_id: Optional[str] = Query(None),
    page:        int           = Query(1, ge=1),
    size:        int           = Query(50, ge=1, le=200),
    current_user: User = Depends(require_director),
    db: AsyncSession = Depends(get_db),
) -> list[FnsReceiptResponse]:

    query = select(FnsReceipt)

    if status_f:
        query = query.where(FnsReceipt.status == status_f)
    if executor_id:
        query = query.where(FnsReceipt.executor_id == executor_id)

    offset = (page - 1) * size
    result = await db.execute(
        query.order_by(FnsReceipt.issued_at.desc()).offset(offset).limit(size)
    )
    receipts = result.scalars().all()

    return [
        FnsReceiptResponse(
            id=str(r.id),
            payment_id=str(r.payment_id),
            executor_id=str(r.executor_id),
            fns_receipt_uuid=r.fns_receipt_uuid,
            fns_receipt_link=r.fns_receipt_link,
            amount=float(r.amount),
            service_name=r.service_name,
            service_date=str(r.service_date),
            status=r.status,
            cancelled_at=r.cancelled_at.isoformat() if r.cancelled_at else None,
            cancel_reason=r.cancel_reason,
            last_check_at=r.last_check_at.isoformat() if r.last_check_at else None,
            director_notified_at=r.director_notified_at.isoformat() if r.director_notified_at else None,
            accounting_notified_at=r.accounting_notified_at.isoformat() if r.accounting_notified_at else None,
            accounting_notified_in_time=r.accounting_notified_in_time,
            issued_at=r.issued_at.isoformat() if r.issued_at else None,
        )
        for r in receipts
    ]


@router.get(
    "/receipts/{receipt_id}",
    response_model=FnsReceiptResponse,
    summary="Детали чека ФНС",
)
async def get_receipt(
    receipt_id: str,
    current_user: User = Depends(require_director),
    db: AsyncSession = Depends(get_db),
) -> FnsReceiptResponse:

    receipt = await db.get(FnsReceipt, receipt_id)
    if not receipt:
        raise HTTPException(status_code=404, detail="Чек не найден")

    return FnsReceiptResponse(
        id=str(receipt.id),
        payment_id=str(receipt.payment_id),
        executor_id=str(receipt.executor_id),
        fns_receipt_uuid=receipt.fns_receipt_uuid,
        fns_receipt_link=receipt.fns_receipt_link,
        amount=float(receipt.amount),
        service_name=receipt.service_name,
        service_date=str(receipt.service_date),
        status=receipt.status,
        cancelled_at=receipt.cancelled_at.isoformat() if receipt.cancelled_at else None,
        cancel_reason=receipt.cancel_reason,
        last_check_at=receipt.last_check_at.isoformat() if receipt.last_check_at else None,
        director_notified_at=receipt.director_notified_at.isoformat() if receipt.director_notified_at else None,
        accounting_notified_at=receipt.accounting_notified_at.isoformat() if receipt.accounting_notified_at else None,
        accounting_notified_in_time=receipt.accounting_notified_in_time,
        issued_at=receipt.issued_at.isoformat() if receipt.issued_at else None,
    )
