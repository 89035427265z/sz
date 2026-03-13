# =============================================================================
# KARI.Самозанятые v2 — Сервис проверки ФССП (судебные приставы)
# Файл: app/services/fssp_service.py
# =============================================================================
#
# Федеральная служба судебных приставов (ФССП) — проверка исполнителей
# на наличие исполнительных производств (долги, алименты, штрафы).
#
# Зачем нужно:
#   - Исполнитель с крупными долгами — финансовый риск для компании
#   - При выплате через банк возможен арест средств → конфликты
#   - Проверяется при регистрации и периодически (раз в 30 дней)
#
# Как работает:
#   1. Запрос к открытому API ФССП (api.fssp.gov.ru)
#   2. Поиск по ФИО + дате рождения (или ИНН)
#   3. Возвращаем список активных исполнительных производств
#   4. Результат кэшируется в Redis на 24 часа
#
# API ФССП: https://api.fssp.gov.ru/
# Документация: https://fssp.gov.ru/iss/ip
#
# ВАЖНО: Официальный API ФССП требует регистрации и токена.
#        В демо-режиме возвращаем мок-данные.
#        Для production — нужен токен от ФССП.
#
# =============================================================================

import logging
import json
from datetime import date, datetime
from typing import Optional
from dataclasses import dataclass, field

import httpx

logger = logging.getLogger(__name__)

# URL официального API ФССП
FSSP_API_URL = "https://api.fssp.gov.ru/api/v1.0/ip"

# Режим работы (True = мок для разработки/пилота)
DEMO_MODE = True


# =============================================================================
# СТРУКТУРЫ ДАННЫХ
# =============================================================================

@dataclass
class FsspProduction:
    """Одно исполнительное производство из ФССП."""
    case_number: str               # Номер дела (напр. 12345/23/77001-ИП)
    debtor_name: str               # ФИО должника
    creditor: str                  # Взыскатель (кому должен)
    amount: float                  # Сумма долга (руб.)
    reason: str                    # Основание (алименты, кредит, штраф, etc.)
    date_start: str                # Дата возбуждения производства
    bailiff_department: str        # Отдел ФССП
    is_active: bool = True         # Активное производство (не закрыто)


@dataclass
class FsspCheckResult:
    """Результат проверки исполнителя в ФССП."""
    inn: str
    full_name: str
    check_date: str                # Дата проверки (ISO)
    has_debt: bool                 # Есть ли долги
    total_debt_amount: float       # Общая сумма долгов (руб.)
    productions: list[FsspProduction] = field(default_factory=list)
    risk_level: str = "low"        # low / medium / high
    error: Optional[str] = None    # Ошибка (если API недоступен)


# =============================================================================
# ОСНОВНАЯ ФУНКЦИЯ ПРОВЕРКИ
# =============================================================================

async def check_fssp(
    inn: str,
    full_name: str,
    birth_date: Optional[date] = None,
    fssp_token: Optional[str] = None,
) -> FsspCheckResult:
    """
    Проверить исполнителя в базе ФССП.

    Args:
        inn: ИНН исполнителя (12 цифр для физлиц)
        full_name: ФИО полностью (для поиска)
        birth_date: Дата рождения (повышает точность поиска)
        fssp_token: Токен API ФССП (из настроек)

    Returns:
        FsspCheckResult — результат с производствами и уровнем риска
    """
    logger.info("Проверка ФССП: ИНН=%s ФИО=%s", inn, full_name)

    if DEMO_MODE:
        return _demo_check(inn, full_name)

    try:
        result = await _real_fssp_check(inn, full_name, birth_date, fssp_token)
        return result
    except Exception as e:
        logger.error("Ошибка API ФССП для ИНН %s: %s", inn, e)
        # При недоступности API — возвращаем результат без данных (не блокируем)
        return FsspCheckResult(
            inn=inn,
            full_name=full_name,
            check_date=datetime.now().date().isoformat(),
            has_debt=False,
            total_debt_amount=0.0,
            risk_level="unknown",
            error=f"API ФССП недоступен: {str(e)}",
        )


async def _real_fssp_check(
    inn: str,
    full_name: str,
    birth_date: Optional[date],
    token: Optional[str],
) -> FsspCheckResult:
    """
    Реальный запрос к API ФССП.
    Требует регистрации на api.fssp.gov.ru и получения токена.
    """
    if not token:
        raise ValueError("Токен API ФССП не настроен (FSSP_TOKEN в .env)")

    # Парсим ФИО
    name_parts = full_name.strip().split()
    params = {
        "token": token,
        "region": "77",     # По умолчанию — Москва. В проде — все регионы
        "last_name": name_parts[0] if len(name_parts) > 0 else "",
        "first_name": name_parts[1] if len(name_parts) > 1 else "",
        "patronymic": name_parts[2] if len(name_parts) > 2 else "",
        "type": "ip",
    }
    if birth_date:
        params["date"] = birth_date.strftime("%d.%m.%Y")

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(FSSP_API_URL, params=params)
        response.raise_for_status()
        data = response.json()

    productions = []
    total_amount = 0.0

    # Парсим ответ ФССП
    for item in data.get("result", {}).get("items", []):
        if item.get("status", "").lower() == "активно":
            amount = float(item.get("amount", 0) or 0)
            total_amount += amount
            productions.append(FsspProduction(
                case_number=item.get("number", ""),
                debtor_name=item.get("name", full_name),
                creditor=item.get("creditor", ""),
                amount=amount,
                reason=item.get("subject", ""),
                date_start=item.get("date", ""),
                bailiff_department=item.get("department", ""),
                is_active=True,
            ))

    risk_level = _calculate_risk(total_amount, len(productions))

    return FsspCheckResult(
        inn=inn,
        full_name=full_name,
        check_date=datetime.now().date().isoformat(),
        has_debt=len(productions) > 0,
        total_debt_amount=total_amount,
        productions=productions,
        risk_level=risk_level,
    )


def _demo_check(inn: str, full_name: str) -> FsspCheckResult:
    """
    Мок для разработки и пилота.
    Симулирует разные ситуации в зависимости от ИНН:
    - Заканчивается на 9 → есть долги (высокий риск)
    - Заканчивается на 7 → небольшой долг (средний риск)
    - Все остальные → чисто
    """
    last_digit = inn[-1] if inn else "0"

    if last_digit == "9":
        # Высокий риск — крупный долг
        productions = [
            FsspProduction(
                case_number="12345/23/77001-ИП",
                debtor_name=full_name,
                creditor="ПАО Сбербанк",
                amount=450000.0,
                reason="Задолженность по кредитному договору",
                date_start="2023-06-15",
                bailiff_department="ОСССП по Ленинскому р-ну г. Москвы",
                is_active=True,
            ),
            FsspProduction(
                case_number="67890/24/77001-ИП",
                debtor_name=full_name,
                creditor="ИФНС России",
                amount=85000.0,
                reason="Задолженность по налогам",
                date_start="2024-01-20",
                bailiff_department="ОСССП по Ленинскому р-ну г. Москвы",
                is_active=True,
            ),
        ]
        return FsspCheckResult(
            inn=inn,
            full_name=full_name,
            check_date=datetime.now().date().isoformat(),
            has_debt=True,
            total_debt_amount=535000.0,
            productions=productions,
            risk_level="high",
        )
    elif last_digit == "7":
        # Средний риск — небольшой штраф
        productions = [
            FsspProduction(
                case_number="11111/24/77002-ИП",
                debtor_name=full_name,
                creditor="ГИБДД",
                amount=5000.0,
                reason="Штраф за нарушение ПДД",
                date_start="2024-08-01",
                bailiff_department="ОСССП по Пресненскому р-ну г. Москвы",
                is_active=True,
            )
        ]
        return FsspCheckResult(
            inn=inn,
            full_name=full_name,
            check_date=datetime.now().date().isoformat(),
            has_debt=True,
            total_debt_amount=5000.0,
            productions=productions,
            risk_level="medium",
        )
    else:
        # Чисто
        return FsspCheckResult(
            inn=inn,
            full_name=full_name,
            check_date=datetime.now().date().isoformat(),
            has_debt=False,
            total_debt_amount=0.0,
            productions=[],
            risk_level="low",
        )


def _calculate_risk(total_amount: float, count: int) -> str:
    """
    Определяет уровень риска по сумме долга.

    low    — нет производств или сумма до 10 тыс. руб.
    medium — 10–100 тыс. руб.
    high   — свыше 100 тыс. руб. или 3+ производства
    """
    if count == 0 or total_amount < 10_000:
        return "low"
    elif count >= 3 or total_amount >= 100_000:
        return "high"
    else:
        return "medium"


# =============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =============================================================================

def format_fssp_result_for_log(result: FsspCheckResult) -> str:
    """Форматирует результат ФССП для записи в аудит-лог."""
    if result.error:
        return f"ФССП: ошибка API — {result.error}"
    if not result.has_debt:
        return "ФССП: чисто, производств нет"
    return (
        f"ФССП: {len(result.productions)} производств, "
        f"сумма {result.total_debt_amount:,.0f} руб., "
        f"риск={result.risk_level}"
    )
