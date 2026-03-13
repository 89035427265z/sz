# =============================================================================
# KARI.Самозанятые — Сервис отправки SMS
# Файл: app/services/sms_service.py
# =============================================================================
# Отправляет SMS через SMSC.ru (популярный российский сервис).
# При DEBUG=True SMS не отправляется — код пишется в лог и возвращается
# в ответе API (удобно при разработке, не тратим деньги на SMS).
# =============================================================================

import random
import string
import logging
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.config import settings
from app.models.user import SmsCode

logger = logging.getLogger(__name__)


# =============================================================================
# ГЕНЕРАЦИЯ КОДА
# =============================================================================

def generate_sms_code(length: int = 6) -> str:
    """Генерирует случайный цифровой код нужной длины."""
    return "".join(random.choices(string.digits, k=length))


# =============================================================================
# ОТПРАВКА SMS
# =============================================================================

async def send_sms(phone: str, message: str) -> bool:
    """
    Отправляет SMS через SMSC.ru API.

    В режиме DEBUG (settings.DEBUG=True) SMS не отправляется — код только
    логируется, что удобно при разработке.

    Возвращает True при успехе, False при ошибке.
    """
    if settings.DEBUG:
        # Режим разработки — просто выводим код в консоль
        logger.warning(f"[DEBUG] SMS на {phone}: {message}")
        return True

    if not settings.SMS_API_KEY:
        logger.error("SMS_API_KEY не задан в .env — SMS не отправлено!")
        return False

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                settings.SMS_API_URL,
                params={
                    "login":   settings.SMS_API_KEY.split(":")[0],  # логин:пароль
                    "psw":     settings.SMS_API_KEY.split(":")[1],
                    "phones":  phone,
                    "mes":     message,
                    "sender":  settings.SMS_SENDER,
                    "charset": "utf-8",
                    "fmt":     1,  # ответ в виде числа: 0=ошибка, N=кол-во SMS
                },
            )

        # SMSC возвращает 0 при ошибке или число отправленных SMS
        result = response.text.strip()
        if result.startswith("0"):
            logger.error(f"SMSC ошибка при отправке на {phone}: {result}")
            return False

        logger.info(f"SMS отправлено на {phone}")
        return True

    except httpx.TimeoutException:
        logger.error(f"Таймаут при отправке SMS на {phone}")
        return False
    except Exception as e:
        logger.error(f"Ошибка отправки SMS на {phone}: {e}")
        return False


# =============================================================================
# СОЗДАНИЕ И СОХРАНЕНИЕ КОДА В БД
# =============================================================================

async def create_and_send_sms_code(
    db: AsyncSession,
    phone: str,
    purpose: str = "auth",
    context_id: str | None = None,
) -> tuple[bool, str | None]:
    """
    Создаёт SMS-код, сохраняет в БД и отправляет на телефон.

    Защиты:
    - Инвалидирует все предыдущие активные коды для этого телефона и цели
    - В DEBUG-режиме возвращает сам код (для тестирования без реального SMS)

    Возвращает: (успех: bool, код_если_debug: str|None)
    """
    # Инвалидируем все предыдущие коды для этого номера и цели
    await db.execute(
        update(SmsCode)
        .where(
            SmsCode.phone == phone,
            SmsCode.purpose == purpose,
            SmsCode.is_used == False,
        )
        .values(is_used=True)
    )

    # Генерируем новый код
    code = generate_sms_code()
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.SMS_CODE_EXPIRE_MINUTES
    )

    # Сохраняем в БД
    sms_record = SmsCode(
        phone=phone,
        code=code,
        purpose=purpose,
        context_id=context_id,
        expires_at=expires_at,
    )
    db.add(sms_record)
    await db.flush()  # Сохраняем без commit — commit сделает get_db()

    # Формируем текст SMS
    if purpose == "auth":
        message = f"Код для входа в KARI.Самозанятые: {code}. Действителен {settings.SMS_CODE_EXPIRE_MINUTES} мин."
    elif purpose == "sign":
        message = f"Код для подписи акта KARI: {code}. Действителен {settings.SMS_CODE_EXPIRE_MINUTES} мин."
    else:
        message = f"Ваш код KARI: {code}"

    # Отправляем SMS
    sent = await send_sms(phone, message)
    if not sent:
        return False, None

    # В DEBUG возвращаем код — чтобы можно было тестировать без SMS
    debug_code = code if settings.DEBUG else None
    return True, debug_code


# =============================================================================
# ПРОВЕРКА КОДА
# =============================================================================

async def verify_sms_code(
    db: AsyncSession,
    phone: str,
    code: str,
    purpose: str = "auth",
) -> tuple[bool, str]:
    """
    Проверяет SMS-код.

    Возвращает: (успех: bool, сообщение об ошибке: str)

    Логика:
    - Ищем последний активный код для этого телефона и цели
    - Если код неверный — увеличиваем счётчик попыток
    - После 3 неверных попыток — инвалидируем код
    - При успехе — помечаем как использованный
    """
    now = datetime.now(timezone.utc)

    # Ищем актуальный код (не использован, не истёк)
    result = await db.execute(
        select(SmsCode)
        .where(
            SmsCode.phone == phone,
            SmsCode.purpose == purpose,
            SmsCode.is_used == False,
            SmsCode.expires_at > now,
        )
        .order_by(SmsCode.created_at.desc())
        .limit(1)
    )
    sms_record = result.scalar_one_or_none()

    if not sms_record:
        return False, "Код не найден или срок действия истёк. Запросите новый код."

    # Проверяем количество попыток
    if sms_record.attempts >= 3:
        sms_record.is_used = True  # Инвалидируем после 3 неверных попыток
        return False, "Превышено количество попыток. Запросите новый код."

    # Проверяем сам код
    if sms_record.code != code:
        sms_record.attempts += 1
        remaining = 3 - sms_record.attempts
        return False, f"Неверный код. Осталось попыток: {remaining}"

    # Код верный — помечаем как использованный
    sms_record.is_used = True
    logger.info(f"SMS-код подтверждён: {phone} ({purpose})")
    return True, "OK"
