# =============================================================================
# KARI.Самозанятые — Pydantic-схемы для документов ЭДО
# Файл: app/schemas/document.py
# =============================================================================
# Схемы описывают что принимает и возвращает API документов.
# Pydantic автоматически валидирует данные и генерирует документацию Swagger.
# =============================================================================

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.document import DocumentType, DocumentStatus


# =============================================================================
# БАЗОВЫЕ СХЕМЫ
# =============================================================================

class DocumentBase(BaseModel):
    """Базовые поля документа."""
    task_id:     UUID
    doc_type:    DocumentType
    executor_id: UUID


# =============================================================================
# ОТВЕТ — КРАТКАЯ ИНФОРМАЦИЯ О ДОКУМЕНТЕ (в списках)
# =============================================================================

class DocumentShort(BaseModel):
    """Краткая карточка документа для списков."""
    id:           UUID
    number:       str | None
    doc_type:     DocumentType
    status:       DocumentStatus
    task_number:  str | None
    task_title:   str
    executor_name: str
    amount:       str
    created_at:   datetime

    # Даты подписей
    executor_signed_at: datetime | None = None
    director_signed_at: datetime | None = None

    class Config:
        from_attributes = True


# =============================================================================
# ОТВЕТ — ПОЛНАЯ ИНФОРМАЦИЯ О ДОКУМЕНТЕ (детальная карточка)
# =============================================================================

class DocumentDetail(BaseModel):
    """Полная карточка документа."""
    id:            UUID
    number:        str | None
    doc_type:      DocumentType
    status:        DocumentStatus

    # Задание
    task_id:       UUID
    task_number:   str | None
    task_title:    str
    store_address: str
    work_date:     str | None

    # Исполнитель
    executor_id:   UUID
    executor_name: str
    executor_inn:  str
    executor_phone: str

    # Директор
    director_id:   UUID | None = None
    director_name: str | None = None

    # Финансы
    amount:        str

    # Файл
    file_path:     str | None = None

    # Подпись исполнителя
    sign_request_at:     datetime | None = None
    executor_signed_at:  datetime | None = None
    executor_sign_ip:    str | None = None

    # Подпись директора
    director_signed_at:  datetime | None = None

    # Хронология
    created_at:    datetime
    updated_at:    datetime | None = None

    class Config:
        from_attributes = True


# =============================================================================
# ЗАПРОС — СФОРМИРОВАТЬ ДОКУМЕНТ
# =============================================================================

class DocumentGenerateRequest(BaseModel):
    """
    Запрос на формирование документа для задания.
    Вызывается автоматически сервером при смене статуса задания.
    """
    task_id:  UUID = Field(..., description="ID задания")
    doc_type: DocumentType = Field(..., description="Тип документа: contract или act")


# =============================================================================
# ЗАПРОС — ОТПРАВИТЬ SMS-КОД ДЛЯ ПОДПИСИ
# =============================================================================

class SignRequestInput(BaseModel):
    """
    Запрос на отправку SMS-кода для подписи документа.
    Исполнитель нажимает кнопку «Подписать» в мобильном приложении.
    """
    document_id: UUID = Field(..., description="ID документа для подписи")


class SignRequestResponse(BaseModel):
    """Ответ на запрос SMS-кода."""
    ok:      bool
    message: str
    # В режиме DEBUG возвращаем код — чтобы тестировать без реального SMS
    debug_code: str | None = None


# =============================================================================
# ЗАПРОС — ПОДТВЕРДИТЬ ПОДПИСЬ (ввести SMS-код)
# =============================================================================

class SignConfirmInput(BaseModel):
    """
    Подтверждение подписи документа — исполнитель вводит SMS-код.
    После успеха документ переходит в статус SIGNED.
    """
    document_id: UUID  = Field(..., description="ID документа")
    code:        str   = Field(..., min_length=6, max_length=6, description="6-значный SMS-код")


class SignConfirmResponse(BaseModel):
    """Ответ после подтверждения подписи."""
    ok:          bool
    message:     str
    document_id: UUID | None = None
    signed_at:   datetime | None = None


# =============================================================================
# ОТВЕТ — СПИСОК ДОКУМЕНТОВ
# =============================================================================

class DocumentListResponse(BaseModel):
    """Список документов с пагинацией."""
    items: list[DocumentShort]
    total: int
    skip:  int
    limit: int
