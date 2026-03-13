# =============================================================================
# KARI.Самозанятые — Сервис Push-уведомлений (Expo Push API)
# Файл: app/services/push_service.py
# =============================================================================
#
# Используем Expo Push API — единый шлюз для iOS (APNs) и Android (FCM).
# Expo сам разбирает куда доставить уведомление по типу токена.
#
# Токены хранятся в поле user.fcm_token в формате: ExponentPushToken[xxxxx]
#
# Типы уведомлений и когда они отправляются:
#   • task_published   → все исполнители без активного задания
#                        "📦 Новое задание: Выкладка товара — ТЦ Иркутск"
#   • task_taken       → директор магазина, создавший задание
#                        "✅ Исполнитель взял ваше задание"
#   • task_submitted   → директор магазина
#                        "👀 Работа сдана — требует вашей проверки"
#   • task_accepted    → исполнитель
#                        "🎉 Работа принята! Выплата начислена"
#   • task_rejected    → исполнитель
#                        "❌ Работа отклонена. Причина: ..."
#   • payment_done     → исполнитель
#                        "💰 Выплата 3 500 руб. отправлена на карту"
#
# =============================================================================

import logging
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# Endpoint Expo Push API (бесплатный, без ключей)
EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"


# =============================================================================
# ОТПРАВКА ОДНОГО PUSH-УВЕДОМЛЕНИЯ
# =============================================================================

async def send_push(
    token: str,
    title: str,
    body: str,
    data: Optional[dict] = None,
    sound: str = "default",
    badge: Optional[int] = None,
) -> bool:
    """
    Отправляет push-уведомление одному пользователю через Expo Push API.

    Аргументы:
        token   — Expo Push Token из user.fcm_token (формат: ExponentPushToken[xxx])
        title   — Заголовок уведомления (жирный текст)
        body    — Текст уведомления
        data    — Дополнительные данные (для навигации при тапе)
        sound   — Звук: "default" или null для беззвучного
        badge   — Число на иконке приложения (iOS)

    Возвращает True при успехе, False при ошибке.
    """
    # В режиме DEBUG не отправляем реальные push — только логируем
    if settings.DEBUG:
        logger.warning(f"[DEBUG] Push → {token[:35] if token else 'no-token'}... | {title}: {body}")
        return True

    # Проверяем формат токена
    if not token or not token.startswith("ExponentPushToken"):
        logger.warning(f"Невалидный Expo Push Token: {token!r}")
        return False

    # Формируем сообщение
    message: dict = {
        "to":    token,
        "title": title,
        "body":  body,
        "sound": sound,
        "data":  data or {},
    }
    if badge is not None:
        message["badge"] = badge

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                EXPO_PUSH_URL,
                json=message,
                headers={
                    "Accept":          "application/json",
                    "Accept-Encoding": "gzip, deflate",
                    "Content-Type":    "application/json",
                },
            )

        result = response.json()
        ticket = result.get("data", {})

        if ticket.get("status") == "ok":
            logger.info(f"✅ Push отправлен → {title}")
            return True
        else:
            err = ticket.get("message", "неизвестная ошибка")
            logger.error(f"❌ Push ошибка: {err}")
            return False

    except httpx.TimeoutException:
        logger.error(f"Push timeout — Expo Push API не ответил")
        return False
    except Exception as e:
        logger.error(f"Push exception: {e}")
        return False


# =============================================================================
# МАССОВАЯ ОТПРАВКА (batch — до 100 за запрос)
# =============================================================================

async def send_push_many(
    tokens: list[str],
    title: str,
    body: str,
    data: Optional[dict] = None,
) -> int:
    """
    Отправляет push-уведомление нескольким пользователям.
    Expo принимает до 100 сообщений в одном запросе.

    Возвращает количество успешно доставленных.
    """
    # Фильтруем валидные токены
    valid = [t for t in tokens if t and t.startswith("ExponentPushToken")]
    if not valid:
        return 0

    # В DEBUG режиме — только логируем
    if settings.DEBUG:
        logger.warning(f"[DEBUG] Push-рассылка ({len(valid)} получателей): {title}")
        return len(valid)

    total_sent = 0

    # Разбиваем на батчи по 100 токенов
    for i in range(0, len(valid), 100):
        batch = valid[i : i + 100]
        messages = [
            {
                "to":    token,
                "title": title,
                "body":  body,
                "sound": "default",
                "data":  data or {},
            }
            for token in batch
        ]

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    EXPO_PUSH_URL,
                    json=messages,
                    headers={
                        "Accept":          "application/json",
                        "Accept-Encoding": "gzip, deflate",
                        "Content-Type":    "application/json",
                    },
                )
            results = response.json().get("data", [])
            batch_sent = sum(1 for r in results if r.get("status") == "ok")
            total_sent += batch_sent
            logger.info(f"Push batch {i//100 + 1}: {batch_sent}/{len(batch)} доставлено")

        except Exception as e:
            logger.error(f"Push batch error: {e}")

    logger.info(f"Массовая push-рассылка итого: {total_sent}/{len(valid)}")
    return total_sent


# =============================================================================
# ГОТОВЫЕ ФУНКЦИИ ДЛЯ КАЖДОГО СОБЫТИЯ
# =============================================================================

async def notify_task_published(
    executor_tokens: list[str],
    task_title: str,
    store_name: str,
    task_id: str,
) -> int:
    """
    Уведомляет исполнителей о новом задании на бирже.
    Вызывается при публикации задания директором магазина.
    """
    return await send_push_many(
        tokens=executor_tokens,
        title="📦 Новое задание",
        body=f"{task_title} — {store_name}",
        data={"screen": "TaskDetail", "taskId": task_id, "event": "task_published"},
    )


async def notify_task_taken(
    director_token: str,
    executor_name: str,
    task_title: str,
    task_id: str,
) -> bool:
    """
    Уведомляет директора магазина что исполнитель взял задание.
    Вызывается при POST /tasks/{id}/take.
    """
    return await send_push(
        token=director_token,
        title="✅ Задание взято",
        body=f"{executor_name} взял(а): «{task_title}»",
        data={"screen": "TaskDetail", "taskId": task_id, "event": "task_taken"},
    )


async def notify_task_submitted(
    director_token: str,
    executor_name: str,
    task_title: str,
    task_id: str,
) -> bool:
    """
    Уведомляет директора магазина что работа сдана и ждёт проверки.
    Вызывается при POST /tasks/{id}/submit.
    """
    return await send_push(
        token=director_token,
        title="👀 Работа сдана",
        body=f"«{task_title}» — проверьте и примите работу",
        data={"screen": "TaskDetail", "taskId": task_id, "event": "task_submitted"},
    )


async def notify_task_accepted(
    executor_token: str,
    task_title: str,
    amount: float,
    task_id: str,
) -> bool:
    """
    Уведомляет исполнителя что работа принята и начислена выплата.
    Вызывается при POST /tasks/{id}/accept.
    """
    return await send_push(
        token=executor_token,
        title="🎉 Работа принята!",
        body=f"«{task_title}» — выплата {amount:,.0f} руб. начислена",
        data={"screen": "Wallet", "taskId": task_id, "event": "task_accepted"},
    )


async def notify_task_rejected(
    executor_token: str,
    task_title: str,
    reason: str,
    task_id: str,
) -> bool:
    """
    Уведомляет исполнителя что работа отклонена.
    Вызывается при POST /tasks/{id}/reject.
    """
    return await send_push(
        token=executor_token,
        title="❌ Работа отклонена",
        body=f"«{task_title}»: {reason[:80]}",
        data={"screen": "TaskDetail", "taskId": task_id, "event": "task_rejected"},
    )


async def notify_payment_done(
    executor_token: str,
    amount: float,
    card_masked: str,
) -> bool:
    """
    Уведомляет исполнителя о поступлении выплаты на карту.
    Вызывается из Celery-задачи process_payment после успешного перевода.
    """
    card_str = f" на карту {card_masked}" if card_masked else ""
    return await send_push(
        token=executor_token,
        title="💰 Выплата отправлена",
        body=f"{amount:,.0f} руб.{card_str}",
        data={"screen": "Wallet", "event": "payment_done"},
    )


async def notify_stop_list_blocked(
    executor_token: str,
    reason: str,
    blocked_until: Optional[str] = None,
) -> bool:
    """
    Уведомляет исполнителя что он попал в стоп-лист и не может получать задания.
    Вызывается при POST /tasks/{id}/take если ИНН найден в stop_list.

    Мобильное приложение по event='stop_list_blocked' откроет экран
    StopListBlockedScreen с причиной и двумя вариантами действий:
      1) Оформиться в штат KARI
      2) Посмотреть заказы партнёров
    """
    # Текст в зависимости от причины
    reason_texts = {
        "former_employee": "По закону 422-ФЗ задания от бывшего работодателя недоступны 2 года",
        "fns_fine":        "По вашему ИНН зафиксированы нарушения в ФНС",
        "manual":          "Выдача заданий временно приостановлена HR-службой",
    }
    body_text = reason_texts.get(reason, "Обратитесь в HR-службу KARI для уточнения")

    if blocked_until:
        body_text += f". До: {blocked_until}"

    return await send_push(
        token=executor_token,
        title="⛔ Задания временно недоступны",
        body=body_text,
        data={
            "screen":       "StopListBlocked",
            "event":        "stop_list_blocked",
            "reason":       reason,
            "blocked_until": blocked_until or "",
        },
    )
