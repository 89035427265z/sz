# =============================================================================
# KARI.Самозанятые v2 — Сервис фискального контроля
# Файл: app/services/fiscal_risk_service.py
# =============================================================================
#
# Мониторинг рисков переквалификации самозанятых в штатных сотрудников.
#
# ФНС проверяет три критерия одновременно (все три = налоговые претензии к KARI):
#
#   ❌ КРИТЕРИЙ 1: Среднемесячный доход от KARI > 35 000 руб.
#      ФНС делит сумму НЕ на 12 месяцев, а только на количество месяцев,
#      в которых была хотя бы одна выплата. Это даёт бо́льшую цифру!
#
#   ❌ КРИТЕРИЙ 2: Сотрудничество с KARI > 3 месяцев
#      Любые 3 месяца в календарном году (не обязательно подряд).
#
#   ❌ КРИТЕРИЙ 3: Доля KARI в общем доходе НПД > 75%
#      Если исполнитель работает только на KARI — это признак трудовых отношений.
#
# Дополнительные зоны риска (независимо от трёх критериев):
#
#   ❌ ПАТТЕРН 1: Выплаты ровно 2 раза в месяц (или кратно 2 неделям)
#      Имитирует зарплату + аванс штатного сотрудника.
#
#   ❌ ПАТТЕРН 2: Повторяющиеся одинаковые суммы выплат
#      Фиксированный оклад — признак трудовых, а не гражданско-правовых отношений.
#
#   ❌ ПАТТЕРН 3: Акт на большую сумму в первые 4 дня работы
#      Подозрительно: невозможно выполнить большой объём работ за 1-4 дня.
#      Первый акт должен выставляться минимум через 5 дней после начала работ.
#
#   ❌ ПАТТЕРН 4: Нереально большой объём работ (например, 42 500 чеков)
#      Физически невозможный объём = административный штраф + проверка.
#
# Источник: комментарии юриста Юлии, 6 марта 2026 г.
# =============================================================================

import logging
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# =============================================================================
# КОНСТАНТЫ — ПОРОГОВЫЕ ЗНАЧЕНИЯ
# =============================================================================

INCOME_THRESHOLD_RUB      = Decimal("35000")  # Среднемесячный доход от KARI
MONTHS_THRESHOLD          = 3                  # Количество месяцев в году
KARI_SHARE_THRESHOLD      = 0.75               # 75% — доля KARI в общем НПД доходе
SALARY_PATTERN_COUNT      = 2                  # Выплат в месяц = зарплатный паттерн
SALARY_PATTERN_MONTHS     = 2                  # Подозрительно, если в 2+ месяцах подряд
ACT_MIN_DAYS_AFTER_START  = 5                  # Первый акт не ранее 5 дней от начала работ
IMPOSSIBLE_VOLUME_AMOUNT  = Decimal("100000")  # Сумма одного акта, требующая проверки


# =============================================================================
# СТРУКТУРЫ ДАННЫХ
# =============================================================================

@dataclass
class FiscalRiskCriteria:
    """Результат проверки трёх основных критериев ФНС."""
    executor_id: str
    inn: str
    check_year: int

    # Критерий 1: среднемесячный доход
    total_income_rub: Decimal = Decimal("0")
    months_with_payment: int = 0
    avg_monthly_income: Decimal = Decimal("0")
    criterion_1_triggered: bool = False

    # Критерий 2: количество месяцев сотрудничества
    active_months: list[str] = field(default_factory=list)  # ["2026-01", "2026-03", ...]
    criterion_2_triggered: bool = False

    # Критерий 3: доля KARI в доходе (если данные доступны)
    kari_share_percent: Optional[float] = None
    criterion_3_triggered: bool = False
    criterion_3_data_available: bool = False


@dataclass
class PaymentPattern:
    """Результат анализа паттернов выплат."""
    executor_id: str

    # Паттерн 1: ритмичность (2 раза в месяц)
    salary_rhythm_detected: bool = False
    salary_rhythm_months: list[str] = field(default_factory=list)  # Месяцы с 2 выплатами

    # Паттерн 2: одинаковые суммы
    repeating_amounts: list[str] = field(default_factory=list)  # Суммы, встречающиеся 3+
    repeating_amounts_detected: bool = False

    # Паттерн 3: ранний акт
    early_acts: list[dict] = field(default_factory=list)  # [{"task_id": ..., "days": ...}]
    early_act_detected: bool = False

    # Паттерн 4: невозможный объём
    impossible_volume_acts: list[dict] = field(default_factory=list)
    impossible_volume_detected: bool = False


@dataclass
class FiscalRiskResult:
    """Итоговая оценка фискального риска для исполнителя."""
    executor_id: str
    inn: str
    check_date: str                   # ISO дата проверки
    check_year: int

    criteria: FiscalRiskCriteria
    patterns: PaymentPattern

    # Итоговый уровень риска
    risk_level: str = "low"           # low / medium / high / critical
    criteria_triggered_count: int = 0
    pattern_triggered_count: int = 0

    # Рекомендованное действие
    recommended_action: str = ""
    requires_stop_list: bool = False  # Автоматически добавить в стоп-лист?


# =============================================================================
# ГЛАВНАЯ ФУНКЦИЯ
# =============================================================================

async def check_fiscal_risk(
    executor_id: str,
    inn: str,
    db: AsyncSession,
    check_year: Optional[int] = None,
) -> FiscalRiskResult:
    """
    Полная проверка фискального риска для одного исполнителя.

    Запрашивает историю выплат из БД и проверяет все критерии ФНС
    и паттерны выплат.

    Args:
        executor_id: UUID исполнителя
        inn: ИНН исполнителя (12 цифр)
        db: AsyncSession сессия БД
        check_year: год проверки (по умолчанию текущий)

    Returns:
        FiscalRiskResult с уровнем риска и рекомендацией
    """
    year = check_year or date.today().year
    today_str = date.today().isoformat()

    logger.info("Фискальная проверка: executor=%s ИНН=%s год=%d", executor_id, inn, year)

    # Получаем историю выплат за год
    payments = await _get_year_payments(executor_id, year, db)

    # Проверяем три критерия ФНС
    criteria = _check_fns_criteria(executor_id, inn, year, payments)

    # Проверяем паттерны выплат
    patterns = await _check_payment_patterns(executor_id, payments, db)

    # Считаем итоговый уровень риска
    criteria_count = sum([
        criteria.criterion_1_triggered,
        criteria.criterion_2_triggered,
        criteria.criterion_3_triggered,
    ])
    pattern_count = sum([
        patterns.salary_rhythm_detected,
        patterns.repeating_amounts_detected,
        patterns.early_act_detected,
        patterns.impossible_volume_detected,
    ])

    risk_level, action, requires_stop = _calculate_risk_level(criteria_count, pattern_count)

    result = FiscalRiskResult(
        executor_id=executor_id,
        inn=inn,
        check_date=today_str,
        check_year=year,
        criteria=criteria,
        patterns=patterns,
        risk_level=risk_level,
        criteria_triggered_count=criteria_count,
        pattern_triggered_count=pattern_count,
        recommended_action=action,
        requires_stop_list=requires_stop,
    )

    if risk_level in ("high", "critical"):
        logger.warning(
            "⚠️ Высокий фискальный риск: executor=%s ИНН=%s уровень=%s "
            "критериев=%d паттернов=%d",
            executor_id, inn, risk_level, criteria_count, pattern_count
        )

    return result


# =============================================================================
# ПОЛУЧЕНИЕ ДАННЫХ ИЗ БД
# =============================================================================

async def _get_year_payments(
    executor_id: str,
    year: int,
    db: AsyncSession,
) -> list[dict]:
    """
    Получает все завершённые выплаты исполнителю за указанный год.

    Возвращает список словарей:
    {
        "id": UUID,
        "amount": Decimal,
        "completed_at": datetime,
        "task_id": UUID,         # Для проверки паттерна "ранний акт"
        "task_start_date": date, # Дата начала работ в задании
    }
    """
    from app.models.payment import Payment, PaymentStatus

    dt_from = datetime(year, 1, 1, tzinfo=timezone.utc)
    dt_to   = datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc)

    result = await db.execute(
        select(Payment).where(
            and_(
                Payment.executor_id == executor_id,
                Payment.status == PaymentStatus.COMPLETED,
                Payment.completed_at >= dt_from,
                Payment.completed_at <= dt_to,
            )
        ).order_by(Payment.completed_at.asc())
    )
    payments_raw = result.scalars().all()

    payments = []
    for p in payments_raw:
        payments.append({
            "id": str(p.id),
            "amount": p.amount,
            "completed_at": p.completed_at,
            "task_id": str(p.task_id) if p.task_id else None,
        })

    return payments


# =============================================================================
# ПРОВЕРКА ТРЁХ КРИТЕРИЕВ ФНС
# =============================================================================

def _check_fns_criteria(
    executor_id: str,
    inn: str,
    year: int,
    payments: list[dict],
) -> FiscalRiskCriteria:
    """
    Проверяет три основных критерия ФНС.

    Ключевой нюанс по критерию 1:
    ФНС делит сумму дохода НЕ на 12 месяцев, а только на количество
    месяцев, в которых было хотя бы одна выплата!
    Это даёт значительно б о́ льшую среднемесячную цифру.
    """
    criteria = FiscalRiskCriteria(
        executor_id=executor_id,
        inn=inn,
        check_year=year,
    )

    if not payments:
        return criteria

    # --- Критерий 1 и 2: считаем по месяцам ---
    months_set = set()
    total = Decimal("0")

    for p in payments:
        month_key = p["completed_at"].strftime("%Y-%m")
        months_set.add(month_key)
        total += p["amount"]

    criteria.total_income_rub = total
    criteria.months_with_payment = len(months_set)
    criteria.active_months = sorted(months_set)

    # Критерий 1: СРЕДНЕМЕСЯЧНЫЙ ДОХОД
    # ФНС делит на количество месяцев с выплатами, не на 12!
    if criteria.months_with_payment > 0:
        criteria.avg_monthly_income = total / criteria.months_with_payment
    criteria.criterion_1_triggered = criteria.avg_monthly_income > INCOME_THRESHOLD_RUB

    # Критерий 2: КОЛИЧЕСТВО МЕСЯЦЕВ СОТРУДНИЧЕСТВА
    criteria.criterion_2_triggered = criteria.months_with_payment >= MONTHS_THRESHOLD

    # Критерий 3: ДОЛЯ В ОБЩЕМ НПД ДОХОДЕ
    # Мы НЕ знаем суммарный НПД-доход из других источников.
    # Если у нас есть данные из ФНС (через API) — используем.
    # Иначе: помечаем как "данные недоступны".
    criteria.criterion_3_data_available = False
    criteria.criterion_3_triggered = False
    # TODO: когда ФНС API вернёт total_npd_income — раскомментировать:
    # if total_npd_income and total_npd_income > 0:
    #     criteria.kari_share_percent = float(total / total_npd_income * 100)
    #     criteria.criterion_3_triggered = criteria.kari_share_percent > 75.0
    #     criteria.criterion_3_data_available = True

    return criteria


# =============================================================================
# ПРОВЕРКА ПАТТЕРНОВ ВЫПЛАТ
# =============================================================================

async def _check_payment_patterns(
    executor_id: str,
    payments: list[dict],
    db: AsyncSession,
) -> PaymentPattern:
    """
    Анализирует паттерны выплат на предмет имитации зарплаты.
    """
    pattern = PaymentPattern(executor_id=executor_id)

    if len(payments) < 2:
        return pattern

    # --- Паттерн 1: РИТМИЧНОСТЬ (ровно 2 выплаты в месяц) ---
    payments_by_month: dict[str, list] = defaultdict(list)
    for p in payments:
        month_key = p["completed_at"].strftime("%Y-%m")
        payments_by_month[month_key].append(p)

    salary_months = []
    for month, month_pays in payments_by_month.items():
        if len(month_pays) == SALARY_PATTERN_COUNT:
            # Дополнительно: проверяем интервал ~2 недели (13-15 дней)
            if len(month_pays) == 2:
                days_diff = abs(
                    (month_pays[1]["completed_at"] - month_pays[0]["completed_at"]).days
                )
                if 12 <= days_diff <= 16:  # Примерно 2 недели
                    salary_months.append(month)

    if len(salary_months) >= SALARY_PATTERN_MONTHS:
        pattern.salary_rhythm_detected = True
        pattern.salary_rhythm_months = salary_months

    # --- Паттерн 2: ОДИНАКОВЫЕ СУММЫ ---
    # Округляем до рублей для сравнения
    amount_counter = Counter(
        str(p["amount"].quantize(Decimal("1"))) for p in payments
    )
    # Суммы, встречающиеся 3 и более раз
    repeating = [amt for amt, cnt in amount_counter.items() if cnt >= 3]
    if repeating:
        pattern.repeating_amounts = repeating
        pattern.repeating_amounts_detected = True

    # --- Паттерн 3 и 4: РАННИЙ АКТ и НЕРЕАЛЬНЫЙ ОБЪЁМ ---
    # Эти паттерны требуют данных по заданиям (task start date)
    # Проверяем те выплаты, у которых есть task_id
    task_ids = [p["task_id"] for p in payments if p["task_id"]]
    if task_ids:
        from app.models.task import Task

        result = await db.execute(
            select(Task.id, Task.created_at, Task.started_at, Task.amount_rub).where(
                Task.id.in_(task_ids)
            )
        )
        tasks_map = {str(r.id): r for r in result.all()}

        for p in payments:
            if not p["task_id"]:
                continue
            task = tasks_map.get(p["task_id"])
            if not task:
                continue

            # Паттерн 4: нереальный объём
            if p["amount"] >= IMPOSSIBLE_VOLUME_AMOUNT:
                pattern.impossible_volume_acts.append({
                    "task_id": p["task_id"],
                    "amount": str(p["amount"]),
                    "payment_date": p["completed_at"].isoformat(),
                })
                pattern.impossible_volume_detected = True

            # Паттерн 3: ранний акт (выплата раньше чем через 5 дней от начала работ)
            work_start = task.started_at or task.created_at
            if work_start:
                days_after_start = (p["completed_at"] - work_start).days
                if 0 <= days_after_start < ACT_MIN_DAYS_AFTER_START:
                    pattern.early_acts.append({
                        "task_id": p["task_id"],
                        "days_after_start": days_after_start,
                        "amount": str(p["amount"]),
                    })
                    pattern.early_act_detected = True

    return pattern


# =============================================================================
# ИТОГОВЫЙ УРОВЕНЬ РИСКА
# =============================================================================

def _calculate_risk_level(
    criteria_count: int,
    pattern_count: int,
) -> tuple[str, str, bool]:
    """
    Определяет уровень риска, рекомендацию и необходимость стоп-листа.

    Возвращает:
        (risk_level, recommended_action, requires_stop_list)
    """
    total_signals = criteria_count + pattern_count

    if criteria_count == 3:
        # ВСЕ три критерия ФНС одновременно → КРИТИЧЕСКИЙ
        return (
            "critical",
            "Все три критерия ФНС сработали одновременно. "
            "Немедленно остановить выплаты и передать в юр.службу. "
            "Рекомендуется добавить в стоп-лист.",
            True,
        )
    elif criteria_count == 2:
        return (
            "high",
            "2 из 3 критериев ФНС сработали. "
            "Контролировать долю дохода KARI. "
            "Предложить исполнителю диверсифицировать клиентов.",
            False,
        )
    elif criteria_count == 1 and pattern_count >= 2:
        return (
            "high",
            "1 критерий ФНС + несколько паттернов зарплаты. "
            "Проверить документацию, исправить паттерны выплат.",
            False,
        )
    elif total_signals >= 3:
        return (
            "medium",
            "Несколько сигналов риска. "
            "Проверить паттерны выплат, разнообразить суммы и даты.",
            False,
        )
    elif total_signals >= 1:
        return (
            "medium",
            "Обнаружены отдельные сигналы риска. Мониторинг.",
            False,
        )
    else:
        return (
            "low",
            "Нарушений не обнаружено. Плановый контроль.",
            False,
        )


# =============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ API
# =============================================================================

def format_risk_for_api(result: FiscalRiskResult) -> dict:
    """
    Форматирует результат проверки для возврата через REST API.
    """
    c = result.criteria
    p = result.patterns

    return {
        "executor_id": result.executor_id,
        "inn": result.inn,
        "check_date": result.check_date,
        "check_year": result.check_year,
        "risk_level": result.risk_level,
        "risk_label": {
            "low": "✅ Норма",
            "medium": "🟡 Внимание",
            "high": "🟠 Высокий риск",
            "critical": "🔴 Критический риск",
        }.get(result.risk_level, result.risk_level),
        "recommended_action": result.recommended_action,
        "requires_stop_list": result.requires_stop_list,

        # Критерии ФНС
        "fns_criteria": {
            "summary": f"{result.criteria_triggered_count}/3 критериев сработало",
            "criterion_1": {
                "name": "Среднемесячный доход от KARI",
                "threshold": f"{INCOME_THRESHOLD_RUB:,.0f} руб.",
                "value": f"{c.avg_monthly_income:,.0f} руб.",
                "note": f"Расчёт: {c.total_income_rub:,.0f} руб. ÷ {c.months_with_payment} мес. "
                        f"(только месяцы с выплатами, не 12!)",
                "triggered": c.criterion_1_triggered,
            },
            "criterion_2": {
                "name": "Количество месяцев сотрудничества в году",
                "threshold": f">= {MONTHS_THRESHOLD} мес.",
                "value": f"{c.months_with_payment} мес.",
                "active_months": c.active_months,
                "triggered": c.criterion_2_triggered,
            },
            "criterion_3": {
                "name": "Доля KARI в общем НПД доходе",
                "threshold": f"> {int(KARI_SHARE_THRESHOLD * 100)}%",
                "value": (
                    f"{c.kari_share_percent:.1f}%"
                    if c.kari_share_percent is not None
                    else "нет данных ФНС"
                ),
                "data_available": c.criterion_3_data_available,
                "triggered": c.criterion_3_triggered,
            },
        },

        # Паттерны выплат
        "payment_patterns": {
            "summary": f"{result.pattern_triggered_count} паттернов обнаружено",
            "salary_rhythm": {
                "name": "Ритмичность (2 выплаты в месяц с интервалом ~2 недели)",
                "detected": p.salary_rhythm_detected,
                "months": p.salary_rhythm_months,
                "risk": "Имитирует зарплату + аванс штатного сотрудника",
            },
            "repeating_amounts": {
                "name": "Повторяющиеся одинаковые суммы",
                "detected": p.repeating_amounts_detected,
                "amounts": p.repeating_amounts,
                "risk": "Фиксированный оклад — признак трудовых отношений",
            },
            "early_acts": {
                "name": f"Акт выставлен в первые {ACT_MIN_DAYS_AFTER_START - 1} дня работ",
                "detected": p.early_act_detected,
                "cases": p.early_acts,
                "risk": "Подозрительно быстрое закрытие — нельзя выполнить большой объём за 1–4 дня",
            },
            "impossible_volume": {
                "name": f"Нереальный объём (акт > {IMPOSSIBLE_VOLUME_AMOUNT:,.0f} руб.)",
                "detected": p.impossible_volume_detected,
                "cases": p.impossible_volume_acts,
                "risk": "Привлекает внимание ФНС. Разбить на несколько меньших актов.",
            },
        },
    }


async def get_all_at_risk_executors(
    db: AsyncSession,
    year: Optional[int] = None,
    min_risk_level: str = "medium",
) -> list[dict]:
    """
    Возвращает всех исполнителей в зоне риска.
    Используется для дашборда директора региона и аналитики.

    Метод упрощённый: проверяет только критерии 1 и 2 через SQL,
    без полного расчёта паттернов (для производительности).
    """
    year = year or date.today().year
    from app.models.payment import Payment, PaymentStatus
    from app.models.user import User, UserRole

    dt_from = datetime(year, 1, 1, tzinfo=timezone.utc)
    dt_to   = datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc)

    # Агрегируем выплаты по исполнителям
    result = await db.execute(
        select(
            Payment.executor_id.label("executor_id"),
            func.sum(Payment.amount).label("total_income"),
            func.count(
                func.distinct(
                    func.date_trunc("month", Payment.completed_at)
                )
            ).label("active_months"),
        )
        .where(
            and_(
                Payment.status == PaymentStatus.COMPLETED,
                Payment.completed_at >= dt_from,
                Payment.completed_at <= dt_to,
            )
        )
        .group_by(Payment.executor_id)
        .having(
            # Хотя бы один критерий сработал
            func.count(
                func.distinct(func.date_trunc("month", Payment.completed_at))
            ) >= MONTHS_THRESHOLD
        )
    )
    rows = result.all()

    at_risk = []
    for row in rows:
        months = int(row.active_months)
        total = Decimal(str(row.total_income or 0))
        avg = total / months if months > 0 else Decimal("0")

        c1 = avg > INCOME_THRESHOLD_RUB
        c2 = months >= MONTHS_THRESHOLD

        signals = int(c1) + int(c2)

        if signals == 0:
            continue

        risk = "medium" if signals == 1 else "high"
        if min_risk_level == "high" and risk != "high":
            continue

        at_risk.append({
            "executor_id": str(row.executor_id),
            "total_income_rub": float(total),
            "active_months": months,
            "avg_monthly_income_rub": float(avg),
            "criterion_1": c1,
            "criterion_2": c2,
            "signals_count": signals,
            "risk_level": risk,
        })

    # Сортируем по количеству сигналов (самые рискованные первыми)
    at_risk.sort(key=lambda x: x["signals_count"], reverse=True)
    return at_risk
