# =============================================================================
# KARI.Самозанятые — Сервис генерации PDF-документов
# Файл: app/services/pdf_service.py
# =============================================================================
# Генерирует PDF-файлы двух типов:
#   1. Договор ГПХ (гражданско-правового характера)
#   2. Акт выполненных работ
#
# Используем библиотеку reportlab — чистый Python, без системных зависимостей.
# PDF сохраняется в MinIO через storage_service.
#
# Формат договоров соответствует шаблонам из 05_Документы_шаблоны/KARI_dogovory.html
# =============================================================================

import io
import logging
import uuid
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


# =============================================================================
# КОНСТАНТЫ KARI
# =============================================================================

KARI_FULL_NAME    = 'Общество с ограниченной ответственностью "КАРИ"'
KARI_SHORT_NAME   = 'ООО "КАРИ"'
KARI_INN          = "7702748210"
KARI_OGRN         = "1107746726210"
KARI_ADDRESS      = "г. Москва, ул. Беговая, д. 3, стр. 1"
KARI_SIGNATORY    = "Генеральный директор Антипов С.А."
KARI_BRAND_COLOR  = (160, 31, 114)   # #A01F72 — малиновый KARI (R, G, B)
KARI_DARK_COLOR   = (36, 45, 74)     # #242D4A — тёмно-синий


# =============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =============================================================================

def _format_date_ru(dt: datetime | None, date_str: str | None = None) -> str:
    """Форматирует дату по-русски: '01 апреля 2026 г.'"""
    months = {
        1: "января", 2: "февраля", 3: "марта", 4: "апреля",
        5: "мая", 6: "июня", 7: "июля", 8: "августа",
        9: "сентября", 10: "октября", 11: "ноября", 12: "декабря",
    }
    if dt:
        return f"{dt.day:02d} {months[dt.month]} {dt.year} г."
    if date_str:
        return date_str
    d = datetime.now(timezone.utc)
    return f"{d.day:02d} {months[d.month]} {d.year} г."


def _next_doc_number(doc_type: str, year: int) -> str:
    """
    Генерирует номер документа.
    В продакшне берётся из счётчика БД — здесь используем uuid-хвост.
    """
    short_id = str(uuid.uuid4()).split("-")[0].upper()
    prefix = "ДГ" if doc_type == "contract" else "АКТ"
    return f"KARI-{year}-{prefix}-{short_id}"


# =============================================================================
# ГЕНЕРАЦИЯ ДОГОВОРА ГПХ
# =============================================================================

def generate_contract_pdf(
    *,
    executor_name:  str,
    executor_inn:   str,
    executor_phone: str,
    task_title:     str,
    task_number:    str,
    store_address:  str,
    amount:         str,
    work_date:      str | None = None,
    doc_number:     str | None = None,
) -> bytes:
    """
    Генерирует PDF-договор ГПХ и возвращает его как bytes.

    Стороны договора:
    - Заказчик: ООО КАРИ (KARI)
    - Исполнитель: самозанятый (данные из параметров)

    Возвращает bytes — готовый PDF для сохранения в MinIO.
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.lib import colors
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
        )
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
    except ImportError:
        logger.error("reportlab не установлен. Запустите: pip install reportlab")
        raise RuntimeError("Библиотека reportlab не установлена")

    buffer = io.BytesIO()
    today  = datetime.now(timezone.utc)
    year   = today.year
    number = doc_number or _next_doc_number("contract", year)
    date_str = _format_date_ru(today)
    work_date_str = work_date or date_str

    # Цвета KARI
    kari_color = colors.Color(
        KARI_BRAND_COLOR[0] / 255,
        KARI_BRAND_COLOR[1] / 255,
        KARI_BRAND_COLOR[2] / 255,
    )
    dark_color = colors.Color(
        KARI_DARK_COLOR[0] / 255,
        KARI_DARK_COLOR[1] / 255,
        KARI_DARK_COLOR[2] / 255,
    )

    # Настраиваем документ (отступы: 20мм слева/справа, 15мм сверху/снизу)
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )

    # Стили текста
    styles = getSampleStyleSheet()

    style_title = ParagraphStyle(
        "KariTitle",
        parent=styles["Normal"],
        fontSize=14,
        leading=18,
        alignment=TA_CENTER,
        textColor=dark_color,
        spaceAfter=4,
        fontName="Helvetica-Bold",
    )
    style_subtitle = ParagraphStyle(
        "KariSubtitle",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        alignment=TA_CENTER,
        textColor=colors.grey,
        spaceAfter=2,
    )
    style_body = ParagraphStyle(
        "KariBody",
        parent=styles["Normal"],
        fontSize=10,
        leading=15,
        alignment=TA_JUSTIFY,
        spaceAfter=8,
    )
    style_bold = ParagraphStyle(
        "KariBold",
        parent=styles["Normal"],
        fontSize=10,
        leading=15,
        fontName="Helvetica-Bold",
        spaceAfter=4,
    )
    style_small = ParagraphStyle(
        "KariSmall",
        parent=styles["Normal"],
        fontSize=8,
        leading=12,
        textColor=colors.grey,
    )
    style_sign_header = ParagraphStyle(
        "KariSignHeader",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        fontName="Helvetica-Bold",
        textColor=dark_color,
        spaceAfter=4,
    )
    style_sign_line = ParagraphStyle(
        "KariSignLine",
        parent=styles["Normal"],
        fontSize=10,
        leading=18,
        spaceAfter=2,
    )

    # =========================================================================
    # СОДЕРЖИМОЕ PDF
    # =========================================================================
    story = []

    # --- Шапка: логотип-текст + название ---
    story.append(Paragraph(
        f'<font color="#A01F72"><b>KARI</b></font>',
        ParagraphStyle("Logo", parent=styles["Normal"], fontSize=20,
                       alignment=TA_LEFT, leading=24, textColor=kari_color)
    ))
    story.append(HRFlowable(width="100%", thickness=2, color=kari_color, spaceAfter=8))

    # --- Заголовок ---
    story.append(Paragraph("ДОГОВОР № " + number, style_title))
    story.append(Paragraph(
        "возмездного оказания услуг (договор ГПХ)",
        style_subtitle,
    ))
    story.append(Paragraph(
        f"г. Москва&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
        f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
        f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
        f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
        f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
        f"«{today.day:02d}» {_format_date_ru(today).replace(str(today.year)+' г.', '').strip()} {today.year} г.",
        ParagraphStyle("DateLine", parent=styles["Normal"], fontSize=10,
                       spaceAfter=12),
    ))

    # --- Преамбула ---
    story.append(Paragraph(
        f'<b>{KARI_SHORT_NAME}</b>, ОГРН {KARI_OGRN}, ИНН {KARI_INN}, '
        f'адрес: {KARI_ADDRESS}, в лице {KARI_SIGNATORY}, '
        f'действующего на основании Устава, именуемое в дальнейшем '
        f'<b>«Заказчик»</b>, с одной стороны, и',
        style_body,
    ))
    story.append(Paragraph(
        f'<b>{executor_name}</b>, ИНН {executor_inn}, '
        f'зарегистрированный в качестве плательщика налога на профессиональный '
        f'доход (самозанятый) в соответствии с Федеральным законом № 422-ФЗ от '
        f'27.11.2018, именуемый в дальнейшем <b>«Исполнитель»</b>, '
        f'с другой стороны, заключили настоящий договор о следующем:',
        style_body,
    ))

    # --- Разделы договора ---
    sections = [
        ("1. ПРЕДМЕТ ДОГОВОРА",
         f'1.1. Исполнитель обязуется по заданию Заказчика оказать следующие услуги: '
         f'<b>{task_title}</b> по адресу: {store_address} '
         f'(Задание № {task_number}, дата выполнения: {work_date_str}).<br/>'
         f'1.2. Заказчик обязуется принять и оплатить оказанные услуги в соответствии '
         f'с условиями настоящего договора.'),

        ("2. СТОИМОСТЬ И ПОРЯДОК ОПЛАТЫ",
         f'2.1. Стоимость услуг по настоящему договору составляет '
         f'<b>{amount} рублей</b>.<br/>'
         f'2.2. Оплата производится безналичным перечислением на банковскую карту '
         f'Исполнителя в течение 3 (трёх) рабочих дней после подписания акта '
         f'выполненных работ.<br/>'
         f'2.3. Заказчик дополнительно компенсирует Исполнителю сумму налога на '
         f'профессиональный доход (6%) от стоимости услуг.'),

        ("3. ОБЯЗАННОСТИ СТОРОН",
         f'3.1. Исполнитель обязан: оказать услуги лично, качественно и в срок; '
         f'иметь действующий статус самозанятого на момент оказания услуг; '
         f'предоставить фотоотчёт о выполненной работе через приложение KARI; '
         f'зарегистрировать полученный доход в приложении ФНС «Мой налог» и '
         f'выдать чек Заказчику в течение 1 рабочего дня после оплаты.<br/>'
         f'3.2. Заказчик обязан: предоставить Исполнителю доступ к месту оказания услуг; '
         f'принять результат в течение 1 рабочего дня после сдачи; '
         f'произвести оплату в сроки, установленные п. 2.2.'),

        ("4. ОТВЕТСТВЕННОСТЬ СТОРОН",
         f'4.1. Стороны несут ответственность в соответствии с действующим '
         f'законодательством Российской Федерации.<br/>'
         f'4.2. Исполнитель несёт полную материальную ответственность за '
         f'ущерб, причинённый Заказчику по его вине.<br/>'
         f'4.3. Настоящий договор не является трудовым договором. '
         f'Исполнитель выполняет работы самостоятельно, без подчинения '
         f'внутреннему трудовому распорядку Заказчика.'),

        ("5. ЭЛЕКТРОННЫЙ ДОКУМЕНТООБОРОТ (ЭДО)",
         f'5.1. Стороны договорились об использовании простой электронной подписи '
         f'(ПЭП) для подписания настоящего договора и акта выполненных работ '
         f'в соответствии с Федеральным законом № 63-ФЗ «Об электронной подписи».<br/>'
         f'5.2. ПЭП Исполнителя — одноразовый код, направляемый на номер телефона '
         f'{executor_phone}. Ввод кода равнозначен собственноручной подписи.<br/>'
         f'5.3. Электронные документы, подписанные ПЭП, имеют юридическую силу, '
         f'равную документам на бумажном носителе.'),

        ("6. СРОК ДЕЙСТВИЯ И ПРОЧИЕ УСЛОВИЯ",
         f'6.1. Договор вступает в силу с момента его подписания обеими сторонами '
         f'и действует до полного исполнения обязательств.<br/>'
         f'6.2. Все изменения и дополнения к настоящему договору оформляются '
         f'в том же порядке, что и сам договор.<br/>'
         f'6.3. Споры разрешаются путём переговоров, а при недостижении соглашения — '
         f'в судебном порядке по месту нахождения Заказчика.'),
    ]

    for title, content in sections:
        story.append(Spacer(1, 4 * mm))
        story.append(Paragraph(title, style_bold))
        story.append(Paragraph(content, style_body))

    # --- Реквизиты и подписи ---
    story.append(Spacer(1, 8 * mm))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.lightgrey))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("7. РЕКВИЗИТЫ И ПОДПИСИ СТОРОН", style_bold))

    sign_data = [
        [
            Paragraph("<b>ЗАКАЗЧИК</b>", style_sign_header),
            Paragraph("<b>ИСПОЛНИТЕЛЬ</b>", style_sign_header),
        ],
        [
            Paragraph(
                f"{KARI_FULL_NAME}<br/>"
                f"ИНН: {KARI_INN}<br/>"
                f"ОГРН: {KARI_OGRN}<br/>"
                f"Адрес: {KARI_ADDRESS}<br/><br/>"
                f"{KARI_SIGNATORY}<br/><br/>"
                f"Подпись: ____________________<br/>"
                f"Дата: {date_str}",
                style_sign_line,
            ),
            Paragraph(
                f"{executor_name}<br/>"
                f"ИНН: {executor_inn}<br/>"
                f"Телефон: {executor_phone}<br/>"
                f"Самозанятый (плательщик НПД)<br/><br/>"
                f"Подписано ПЭП (SMS-код)<br/><br/>"
                f"Подпись: ____________________<br/>"
                f"Дата: ____________________",
                style_sign_line,
            ),
        ],
    ]

    sign_table = Table(sign_data, colWidths=["50%", "50%"])
    sign_table.setStyle(TableStyle([
        ("VALIGN",    (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",  (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING",   (0, 0), (-1, -1), 6),
        ("LINEAFTER",  (0, 0), (0, -1), 0.5, colors.lightgrey),
    ]))
    story.append(sign_table)

    # --- Нижний колонтитул ---
    story.append(Spacer(1, 8 * mm))
    story.append(HRFlowable(width="100%", thickness=1, color=kari_color))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(
        f"Документ сформирован автоматически платформой KARI.Самозанятые | "
        f"Договор № {number} | {date_str}",
        style_small,
    ))

    # --- Строим PDF ---
    doc.build(story)
    buffer.seek(0)
    return buffer.read()


# =============================================================================
# ГЕНЕРАЦИЯ АКТА ВЫПОЛНЕННЫХ РАБОТ
# =============================================================================

def generate_act_pdf(
    *,
    executor_name:      str,
    executor_inn:       str,
    executor_phone:     str,
    task_title:         str,
    task_number:        str,
    store_address:      str,
    amount:             str,
    work_date:          str | None = None,
    contract_number:    str | None = None,
    doc_number:         str | None = None,
    director_name:      str | None = None,
) -> bytes:
    """
    Генерирует PDF акт выполненных работ и возвращает bytes.
    Акт подтверждает факт выполнения работ и служит основанием для оплаты.
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.lib import colors
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
        )
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
    except ImportError:
        logger.error("reportlab не установлен. Запустите: pip install reportlab")
        raise RuntimeError("Библиотека reportlab не установлена")

    buffer  = io.BytesIO()
    today   = datetime.now(timezone.utc)
    year    = today.year
    number  = doc_number or _next_doc_number("act", year)
    date_str = _format_date_ru(today)
    work_date_str = work_date or date_str

    kari_color = colors.Color(
        KARI_BRAND_COLOR[0] / 255,
        KARI_BRAND_COLOR[1] / 255,
        KARI_BRAND_COLOR[2] / 255,
    )
    dark_color = colors.Color(
        KARI_DARK_COLOR[0] / 255,
        KARI_DARK_COLOR[1] / 255,
        KARI_DARK_COLOR[2] / 255,
    )

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )

    styles = getSampleStyleSheet()

    style_title = ParagraphStyle("AKT_Title", parent=styles["Normal"],
                                  fontSize=14, leading=18, alignment=TA_CENTER,
                                  textColor=dark_color, spaceAfter=4,
                                  fontName="Helvetica-Bold")
    style_subtitle = ParagraphStyle("AKT_Sub", parent=styles["Normal"],
                                     fontSize=10, leading=14, alignment=TA_CENTER,
                                     textColor=colors.grey, spaceAfter=10)
    style_body = ParagraphStyle("AKT_Body", parent=styles["Normal"],
                                 fontSize=10, leading=15, alignment=TA_JUSTIFY,
                                 spaceAfter=6)
    style_bold = ParagraphStyle("AKT_Bold", parent=styles["Normal"],
                                 fontSize=10, leading=15, fontName="Helvetica-Bold",
                                 spaceAfter=4)
    style_small = ParagraphStyle("AKT_Small", parent=styles["Normal"],
                                  fontSize=8, leading=12, textColor=colors.grey)
    style_sign_header = ParagraphStyle("AKT_SignH", parent=styles["Normal"],
                                        fontSize=10, leading=14,
                                        fontName="Helvetica-Bold",
                                        textColor=dark_color, spaceAfter=4)
    style_sign_line = ParagraphStyle("AKT_SignL", parent=styles["Normal"],
                                      fontSize=10, leading=18, spaceAfter=2)

    story = []

    # --- Логотип ---
    story.append(Paragraph(
        '<font color="#A01F72"><b>KARI</b></font>',
        ParagraphStyle("Logo2", parent=styles["Normal"], fontSize=20,
                       alignment=TA_LEFT, leading=24, textColor=kari_color)
    ))
    story.append(HRFlowable(width="100%", thickness=2, color=kari_color, spaceAfter=8))

    # --- Заголовок ---
    story.append(Paragraph("АКТ № " + number, style_title))
    story.append(Paragraph("выполненных работ (оказанных услуг)", style_subtitle))
    story.append(Paragraph(
        f"к Договору № {contract_number or '—'} от {date_str}",
        ParagraphStyle("RefLine", parent=styles["Normal"],
                       fontSize=10, alignment=TA_CENTER, spaceAfter=12,
                       textColor=kari_color),
    ))
    story.append(Paragraph(
        f"г. Москва"
        f"{'&nbsp;' * 60}"
        f"«{today.day:02d}» {_format_date_ru(today).replace(str(today.year)+' г.','').strip()} {today.year} г.",
        ParagraphStyle("DateLine2", parent=styles["Normal"], fontSize=10, spaceAfter=12),
    ))

    # --- Стороны ---
    story.append(Paragraph(
        f'<b>{KARI_SHORT_NAME}</b> (Заказчик) в лице {director_name or KARI_SIGNATORY} '
        f'и <b>{executor_name}</b>, ИНН {executor_inn} (Исполнитель, самозанятый), '
        f'составили настоящий акт о нижеследующем:',
        style_body,
    ))

    # --- Таблица услуг ---
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("1. ПЕРЕЧЕНЬ ВЫПОЛНЕННЫХ РАБОТ", style_bold))

    table_data = [
        ["№", "Наименование услуги", "Место оказания", "Дата", "Сумма, руб."],
        ["1", task_title, store_address[:40] + ("..." if len(store_address) > 40 else ""),
         work_date_str, amount],
        ["", "", "", "ИТОГО:", f"<b>{amount}</b>"],
    ]

    col_widths = [10 * mm, 65 * mm, 55 * mm, 25 * mm, 22 * mm]
    services_table = Table(table_data, colWidths=col_widths)
    services_table.setStyle(TableStyle([
        # Заголовок таблицы
        ("BACKGROUND",   (0, 0), (-1, 0), dark_color),
        ("TEXTCOLOR",    (0, 0), (-1, 0), colors.white),
        ("FONTNAME",     (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",     (0, 0), (-1, -1), 9),
        ("ALIGN",        (0, 0), (-1, -1), "LEFT"),
        ("ALIGN",        (-1, 0), (-1, -1), "RIGHT"),  # сумма — по правому краю
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",   (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 5),
        ("LEFTPADDING",  (0, 0), (-1, -1), 5),
        # Границы
        ("GRID",         (0, 0), (-1, 1), 0.5, colors.lightgrey),
        ("LINEABOVE",    (0, 2), (-1, 2), 1, dark_color),
        # Строка ИТОГО
        ("FONTNAME",     (0, 2), (-1, 2), "Helvetica-Bold"),
        ("SPAN",         (0, 2), (2, 2)),  # объединяем пустые ячейки
    ]))
    story.append(services_table)

    # --- Подтверждение ---
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph("2. ПОДТВЕРЖДЕНИЕ ВЫПОЛНЕНИЯ", style_bold))
    story.append(Paragraph(
        f'Заказчик подтверждает, что работы по Заданию № {task_number} выполнены '
        f'Исполнителем в полном объёме и с надлежащим качеством. '
        f'Претензий к качеству и срокам оказания услуг не имеется.',
        style_body,
    ))
    story.append(Paragraph(
        f'Настоящий акт является основанием для выплаты вознаграждения '
        f'в размере <b>{amount} рублей</b>.',
        style_body,
    ))
    story.append(Paragraph(
        f'Исполнитель обязан зарегистрировать доход на сумму <b>{amount} рублей</b> '
        f'в приложении ФНС «Мой налог» и выдать чек Заказчику в течение '
        f'1 (одного) рабочего дня с момента получения оплаты.',
        style_body,
    ))

    # --- Подписи ---
    story.append(Spacer(1, 6 * mm))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.lightgrey))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("3. ПОДПИСИ СТОРОН", style_bold))

    sign_data = [
        [
            Paragraph("<b>ЗАКАЗЧИК</b>", style_sign_header),
            Paragraph("<b>ИСПОЛНИТЕЛЬ</b>", style_sign_header),
        ],
        [
            Paragraph(
                f"{KARI_SHORT_NAME}<br/>"
                f"{director_name or KARI_SIGNATORY}<br/><br/>"
                f"Подпись: ____________________<br/>"
                f"Дата: {date_str}",
                style_sign_line,
            ),
            Paragraph(
                f"{executor_name}<br/>"
                f"ИНН: {executor_inn}<br/>"
                f"Самозанятый (НПД)<br/><br/>"
                f"<b>Подписано ПЭП (SMS-код)<br/>"
                f"Телефон: {executor_phone}</b><br/><br/>"
                f"Дата подписи: ____________________",
                style_sign_line,
            ),
        ],
    ]

    sign_table = Table(sign_data, colWidths=["50%", "50%"])
    sign_table.setStyle(TableStyle([
        ("VALIGN",       (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",  (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING",   (0, 0), (-1, -1), 6),
        ("LINEAFTER",    (0, 0), (0, -1), 0.5, colors.lightgrey),
    ]))
    story.append(sign_table)

    # --- Нижний колонтитул ---
    story.append(Spacer(1, 8 * mm))
    story.append(HRFlowable(width="100%", thickness=1, color=kari_color))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(
        f"Документ сформирован автоматически платформой KARI.Самозанятые | "
        f"Акт № {number} | {date_str}",
        style_small,
    ))

    doc.build(story)
    buffer.seek(0)
    return buffer.read()
