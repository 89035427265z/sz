# =============================================================================
# KARI.Самозанятые — API интеграции с ФНС
# Файл: app/api/fns.py
# =============================================================================
#
#   GET  /fns/check/{inn}            — проверить статус самозанятого по ИНН
#   POST /fns/check-user/{user_id}   — обновить статус ФНС конкретного пользователя
#   POST /fns/check-all-users        — обновить статус ФНС всех активных исполнителей
#   POST /fns/receipts/check-all     — запустить ежедневную проверку чеков вручную
#   POST /fns/receipts/{id}/check    — проверить один чек
#   POST /fns/receipts/{id}/cancel   — аннулировать чек
# =============================================================================

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.database import get_db
from app.models.user import User, UserRole, FnsStatus, UserStatus
from app.models.payment import FnsReceipt, FnsReceiptStatus
from app.core.security import get_current_user, require_director, require_regional
from app.services.fns_service import (
    check_selfemployed_status,
    update_user_fns_status,
    check_receipt_status,
    cancel_receipt,
    daily_check_all_receipts,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# =============================================================================
# ПРОВЕРКА СТАТУСА САМОЗАНЯТОГО
# =============================================================================

@router.get(
    "/check/{inn}",
    summary="Проверить статус самозанятого по ИНН",
    description="""
Делает запрос в ФНС и возвращает актуальный статус самозанятого.

Используется:
- При регистрации нового исполнителя
- При возникновении сомнений в статусе
- Перед выдачей крупного задания

Результат **не сохраняется** в БД — только проверка.
Для обновления в БД используйте `POST /fns/check-user/{user_id}`.
    """,
)
async def check_inn_status(
    inn: str,
    current_user: User = Depends(get_current_user),   # доступно всем авторизованным (в т.ч. исполнителям при регистрации)
) -> dict:

    # Базовая валидация ИНН
    digits = "".join(c for c in inn if c.isdigit())
    if len(digits) != 12:
        raise HTTPException(
            status_code=400,
            detail="ИНН физического лица должен содержать 12 цифр",
        )

    result = await check_selfemployed_status(digits)

    if result.get("error"):
        raise HTTPException(
            status_code=502,
            detail=f"Ошибка запроса к ФНС: {result['error']}",
        )

    return {
        "inn":               digits,
        "status":            "active" if result["is_active"] else "inactive",   # ← мобильное приложение ожидает это поле
        "is_active":         result["is_active"],
        "status_label":      "Самозанятый (активен)" if result["is_active"] else "Не является самозанятым",
        "registration_date": str(result["registration_date"]) if result.get("registration_date") else None,
        "full_name":         result.get("full_name"),
        "checked_at":        datetime.now(timezone.utc).isoformat(),
    }


@router.post(
    "/check-user/{user_id}",
    summary="Обновить статус ФНС пользователя",
    description="Проверяет ФНС и сохраняет результат в БД. Доступно директорам.",
)
async def refresh_user_fns_status(
    user_id: str,
    current_user: User = Depends(require_director),
    db: AsyncSession = Depends(get_db),
) -> dict:

    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    if user.role != UserRole.EXECUTOR:
        raise HTTPException(
            status_code=400,
            detail="Проверка ФНС доступна только для исполнителей (самозанятых)",
        )

    old_status = user.fns_status
    user = await update_user_fns_status(db, user)

    logger.info(
        f"Статус ФНС обновлён: {user.phone} | "
        f"{old_status} → {user.fns_status} | "
        f"Запросил: {current_user.phone}"
    )

    return {
        "user_id":      str(user.id),
        "phone":        user.phone,
        "full_name":    user.full_name,
        "inn":          user.inn,
        "old_status":   old_status,
        "new_status":   user.fns_status,
        "status_changed": old_status != user.fns_status,
        "checked_at":   user.fns_last_check_at.isoformat() if user.fns_last_check_at else None,
    }


@router.post(
    "/check-all-users",
    summary="Обновить статус ФНС всех активных исполнителей",
    description="""
**Только директор региона.**

Проходит по всем активным исполнителям и обновляет их статус в ФНС.
Тех, у кого статус изменился на INACTIVE — помечает для проверки.

Может занять несколько минут при большом числе исполнителей.
    """,
)
async def refresh_all_users_fns_status(
    current_user: User = Depends(require_regional),
    db: AsyncSession = Depends(get_db),
) -> dict:

    # Берём всех активных исполнителей с ИНН
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

    stats = {
        "total":      len(executors),
        "checked":    0,
        "active":     0,
        "inactive":   0,
        "changed":    0,
        "errors":     0,
    }

    logger.info(f"Массовая проверка ФНС: {len(executors)} исполнителей")

    for executor in executors:
        try:
            old_status = executor.fns_status
            await update_user_fns_status(db, executor)
            stats["checked"] += 1

            if executor.fns_status == FnsStatus.ACTIVE:
                stats["active"] += 1
            else:
                stats["inactive"] += 1

            if old_status != executor.fns_status:
                stats["changed"] += 1
                logger.info(
                    f"Статус изменился: {executor.phone} | "
                    f"{old_status} → {executor.fns_status}"
                )

        except Exception as e:
            stats["errors"] += 1
            logger.error(f"Ошибка проверки {executor.phone}: {e}")

    logger.info(f"Массовая проверка ФНС завершена: {stats}")
    return stats


# =============================================================================
# УПРАВЛЕНИЕ ЧЕКАМИ ФНС
# =============================================================================

@router.post(
    "/receipts/check-all",
    summary="Запустить проверку всех чеков вручную",
    description="""
**Только директор региона.**

Вручную запускает ту же проверку что происходит автоматически каждый день в 07:00.

Полезно если:
- Нужно срочно проверить статус всех чеков
- Автоматическая задача упала с ошибкой
- После технических работ ФНС
    """,
)
async def manual_check_all_receipts(
    current_user: User = Depends(require_regional),
    db: AsyncSession = Depends(get_db),
) -> dict:

    logger.info(f"Ручной запуск проверки чеков ФНС — инициатор: {current_user.phone}")

    stats = await daily_check_all_receipts(db)

    return {
        "success":   True,
        "message":   f"Проверка завершена. Проверено: {stats['checked']}, аннулировано: {stats['cancelled']}",
        "stats":     stats,
        "run_at":    datetime.now(timezone.utc).isoformat(),
        "run_by":    current_user.phone,
    }


@router.post(
    "/receipts/{receipt_id}/check",
    summary="Проверить статус одного чека",
    description="Делает запрос в ФНС и обновляет статус конкретного чека в БД.",
)
async def check_single_receipt(
    receipt_id: str,
    current_user: User = Depends(require_director),
    db: AsyncSession = Depends(get_db),
) -> dict:

    receipt = await db.get(FnsReceipt, receipt_id)
    if not receipt:
        raise HTTPException(status_code=404, detail="Чек не найден")

    old_status = receipt.status
    receipt    = await check_receipt_status(db, receipt)

    return {
        "receipt_id":      str(receipt.id),
        "fns_uuid":        receipt.fns_receipt_uuid,
        "old_status":      old_status,
        "new_status":      receipt.status,
        "status_changed":  old_status != receipt.status,
        "cancelled_at":    receipt.cancelled_at.isoformat() if receipt.cancelled_at else None,
        "cancel_reason":   receipt.cancel_reason,
        "checked_at":      receipt.last_check_at.isoformat() if receipt.last_check_at else None,
    }


@router.post(
    "/receipts/{receipt_id}/cancel",
    summary="Аннулировать чек",
    description="""
**Только директор региона.**

Аннулирует чек в ФНС. Используется в редких случаях:
- Задание было ошибочно оплачено
- Обнаружена ошибка в сумме

После аннулирования доход исполнителя уменьшается на сумму чека.
    """,
)
async def cancel_fns_receipt(
    receipt_id: str,
    reason:     str = Query(..., description="Причина аннулирования"),
    current_user: User = Depends(require_regional),
    db: AsyncSession = Depends(get_db),
) -> dict:

    receipt = await db.get(FnsReceipt, receipt_id)
    if not receipt:
        raise HTTPException(status_code=404, detail="Чек не найден")

    if receipt.status != FnsReceiptStatus.CREATED:
        raise HTTPException(
            status_code=400,
            detail=f"Чек уже не активен (статус: {receipt.status}). Аннулирование невозможно.",
        )

    executor = await db.get(User, receipt.executor_id)
    if not executor:
        raise HTTPException(status_code=404, detail="Исполнитель не найден")

    success = await cancel_receipt(db, receipt, executor, reason)

    if not success:
        raise HTTPException(
            status_code=502,
            detail="Не удалось аннулировать чек в ФНС. Попробуйте позже.",
        )

    logger.info(
        f"Чек аннулирован вручную: {receipt.fns_receipt_uuid} | "
        f"Причина: {reason} | Директор: {current_user.phone}"
    )

    return {
        "success":         True,
        "receipt_id":      str(receipt.id),
        "fns_uuid":        receipt.fns_receipt_uuid,
        "cancelled_at":    receipt.cancelled_at.isoformat() if receipt.cancelled_at else None,
        "cancel_reason":   receipt.cancel_reason,
        "executor_phone":  executor.phone,
        "amount_reversed": float(receipt.amount),
    }
