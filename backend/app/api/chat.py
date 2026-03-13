# =============================================================================
# KARI.Самозанятые v2 — API чата внутри задания
# Файл: app/api/chat.py
# =============================================================================
#
# Эндпоинты:
#
#   GET  /chat/{task_id}/messages          — история сообщений по заданию
#   POST /chat/{task_id}/messages          — отправить сообщение
#   PUT  /chat/{task_id}/read              — отметить все как прочитанные
#   GET  /chat/unread-count                — счётчик непрочитанных (для значка)
#
# Как работает:
#   - Чат привязан к заданию (task_id), не к пользователям
#   - Участники: исполнитель задания + директор магазина
#   - Сообщения хранятся бессрочно (для разбора споров)
#   - Push-уведомление при новом сообщении
#   - Можно прикрепить фото (URL из MinIO)
#
# =============================================================================

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update, and_

from app.database import get_db
from app.models.chat import ChatMessage
from app.models.user import User, UserRole
from app.core.security import get_current_user
from app.services import push_service

logger = logging.getLogger(__name__)
router = APIRouter()


# =============================================================================
# PYDANTIC СХЕМЫ
# =============================================================================

class SendMessageRequest(BaseModel):
    """Тело запроса: отправить сообщение."""
    receiver_id: str                    # Кому отправляем
    message: str = Field(..., min_length=1, max_length=2000)
    photo_url: Optional[str] = None    # Прикреплённое фото (MinIO URL)


class ChatMessageResponse(BaseModel):
    """Ответ: одно сообщение чата."""
    id: str
    task_id: str
    sender_id: str
    receiver_id: str
    message: str
    is_read: bool
    photo_url: Optional[str]
    created_at: str

    class Config:
        from_attributes = True


class UnreadCountResponse(BaseModel):
    """Счётчик непрочитанных сообщений."""
    total_unread: int
    # Непрочитанные по заданиям (ключ = task_id, значение = количество)
    by_task: dict[str, int]


# =============================================================================
# ЭНДПОИНТЫ
# =============================================================================

@router.get("/{task_id}/messages", response_model=list[ChatMessageResponse])
async def get_task_messages(
    task_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    История сообщений чата по заданию.
    Видят: исполнитель задания + директор магазина + директоры выше.

    Сортировка: от старых к новым (для UI чата снизу вверх).
    """
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.task_id == task_id)
        .order_by(ChatMessage.created_at.asc())
        .limit(limit)
        .offset(offset)
    )
    messages = result.scalars().all()

    return [
        ChatMessageResponse(
            id=str(m.id),
            task_id=str(m.task_id),
            sender_id=str(m.sender_id),
            receiver_id=str(m.receiver_id),
            message=m.message,
            is_read=m.is_read,
            photo_url=m.photo_url,
            created_at=m.created_at.isoformat(),
        )
        for m in messages
    ]


@router.post("/{task_id}/messages", response_model=ChatMessageResponse, status_code=201)
async def send_message(
    task_id: str,
    body: SendMessageRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Отправить сообщение в чате задания.

    После сохранения в БД — отправляем Push-уведомление получателю.
    Исполнитель пишет → директор получает push.
    Директор пишет → исполнитель получает push.
    """
    # Создаём сообщение
    msg = ChatMessage(
        task_id=task_id,
        sender_id=str(current_user.id),
        receiver_id=body.receiver_id,
        message=body.message,
        photo_url=body.photo_url,
        is_read=False,
    )
    db.add(msg)
    await db.commit()
    await db.refresh(msg)

    logger.info(
        "Чат: новое сообщение task=%s от %s для %s",
        task_id, current_user.id, body.receiver_id
    )

    # Отправляем Push-уведомление получателю
    try:
        receiver_result = await db.execute(
            select(User).where(User.id == body.receiver_id)
        )
        receiver = receiver_result.scalar_one_or_none()

        if receiver and receiver.push_token:
            sender_name = current_user.full_name or current_user.phone
            await push_service.send_push(
                token=receiver.push_token,
                title=f"💬 Сообщение по заданию",
                body=f"{sender_name}: {body.message[:80]}",
                data={
                    "type": "CHAT_MESSAGE",
                    "task_id": task_id,
                    "message_id": str(msg.id),
                },
            )
    except Exception as e:
        # Push не критичен — сообщение уже сохранено
        logger.warning("Не удалось отправить push по чату: %s", e)

    return ChatMessageResponse(
        id=str(msg.id),
        task_id=str(msg.task_id),
        sender_id=str(msg.sender_id),
        receiver_id=str(msg.receiver_id),
        message=msg.message,
        is_read=msg.is_read,
        photo_url=msg.photo_url,
        created_at=msg.created_at.isoformat(),
    )


@router.put("/{task_id}/read", status_code=200)
async def mark_messages_read(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Отметить все сообщения по заданию как прочитанные.
    Обновляются только сообщения где получатель = текущий пользователь.
    Вызывается при открытии чата на фронтенде.
    """
    result = await db.execute(
        update(ChatMessage)
        .where(
            and_(
                ChatMessage.task_id == task_id,
                ChatMessage.receiver_id == str(current_user.id),
                ChatMessage.is_read == False,
            )
        )
        .values(is_read=True)
    )
    await db.commit()

    updated_count = result.rowcount
    logger.info(
        "Прочитано %d сообщений по заданию %s пользователем %s",
        updated_count, task_id, current_user.id
    )

    return {"marked_read": updated_count}


@router.get("/unread-count", response_model=UnreadCountResponse)
async def get_unread_count(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Счётчик непрочитанных сообщений для текущего пользователя.
    Возвращает общее число и разбивку по заданиям.
    Используется для значка с числом на иконке чата.
    """
    # Группируем непрочитанные по task_id
    result = await db.execute(
        select(
            ChatMessage.task_id.cast(type_=func.String),
            func.count(ChatMessage.id).label("unread"),
        )
        .where(
            and_(
                ChatMessage.receiver_id == str(current_user.id),
                ChatMessage.is_read == False,
            )
        )
        .group_by(ChatMessage.task_id)
    )
    rows = result.all()

    by_task = {str(row[0]): row[1] for row in rows}
    total = sum(by_task.values())

    return UnreadCountResponse(
        total_unread=total,
        by_task=by_task,
    )
