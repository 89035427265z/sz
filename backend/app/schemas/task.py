# =============================================================================
# KARI.Самозанятые — Схемы данных заданий
# Файл: app/schemas/task.py
# =============================================================================

from typing import Optional
from datetime import date, time
from pydantic import BaseModel, field_validator


# =============================================================================
# ЗАПРОСЫ
# =============================================================================

class CreateTaskRequest(BaseModel):
    """Создание нового задания (директор магазина)."""
    title:                str
    description:          str
    category:             str            # cleaning / merchandising / inventory / ...
    store_id:             str
    store_address:        str
    store_latitude:       Optional[float] = None
    store_longitude:      Optional[float] = None
    price:                float
    scheduled_date:       date
    scheduled_time_start: Optional[time] = None
    scheduled_time_end:   Optional[time] = None
    required_photo_count: int            = 1   # 1–3
    photo_instructions:   Optional[str]  = None
    template_id:          Optional[str]  = None  # Если создаётся из шаблона

    @field_validator("price")
    @classmethod
    def validate_price(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Стоимость должна быть больше нуля")
        if v > 100_000:
            raise ValueError("Стоимость задания не может превышать 100 000 руб")
        return round(v, 2)

    @field_validator("required_photo_count")
    @classmethod
    def validate_photo_count(cls, v: int) -> int:
        if not 1 <= v <= 3:
            raise ValueError("Количество фото должно быть от 1 до 3")
        return v

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        allowed = ("cleaning", "merchandising", "inventory", "unloading", "promotion", "marking", "other")
        if v not in allowed:
            raise ValueError(f"Категория должна быть одной из: {', '.join(allowed)}")
        return v

    model_config = {
        "json_schema_extra": {
            "example": {
                "title": "Уборка торгового зала",
                "description": "Влажная уборка пола, протереть витрины, вынести мусор",
                "category": "cleaning",
                "store_id": "550e8400-e29b-41d4-a716-446655440000",
                "store_address": "Москва, ул. Ленина, 10, ТЦ Мега",
                "store_latitude": 55.7558,
                "store_longitude": 37.6176,
                "price": 1500.00,
                "scheduled_date": "2025-12-01",
                "scheduled_time_start": "09:00:00",
                "scheduled_time_end": "12:00:00",
                "required_photo_count": 2,
                "photo_instructions": "Сфотографируйте чистый пол и витрины",
            }
        }
    }


class UpdateTaskRequest(BaseModel):
    """Редактирование задания (только в статусе DRAFT)."""
    title:                Optional[str]   = None
    description:          Optional[str]   = None
    price:                Optional[float] = None
    scheduled_date:       Optional[date]  = None
    scheduled_time_start: Optional[time]  = None
    scheduled_time_end:   Optional[time]  = None
    required_photo_count: Optional[int]   = None
    photo_instructions:   Optional[str]   = None


class RejectTaskRequest(BaseModel):
    """Отклонение задания директором магазина."""
    reason: str

    model_config = {
        "json_schema_extra": {
            "example": {"reason": "Пол не домыт до конца, у стеллажей грязь осталась"}
        }
    }


class CreateTemplateRequest(BaseModel):
    """Создание шаблона задания."""
    title:                str
    description:          str
    category:             str
    store_id:             Optional[str]   = None
    region_id:            Optional[str]   = None
    default_price:        float
    required_photo_count: int             = 1
    photo_instructions:   Optional[str]   = None

    @field_validator("default_price")
    @classmethod
    def validate_price(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Стоимость должна быть больше нуля")
        return round(v, 2)


# =============================================================================
# ОТВЕТЫ
# =============================================================================

class TaskPhotoResponse(BaseModel):
    """Данные одного фотоотчёта."""
    id:                       str
    sequence_number:          int
    file_path:                str
    file_size_mb:             Optional[float] = None
    image_width:              Optional[int]   = None
    image_height:             Optional[int]   = None
    photo_latitude:           Optional[float] = None
    photo_longitude:          Optional[float] = None
    distance_from_store_meters: Optional[float] = None
    geo_verification:         str              # pending / verified / failed
    taken_at:                 Optional[str]   = None
    resolution_ok:            Optional[bool]  = None

    model_config = {"from_attributes": True}


class TaskResponse(BaseModel):
    """Полные данные задания."""
    id:                   str
    number:               Optional[str]  = None
    title:                str
    description:          str
    category:             str
    status:               str
    store_id:             str
    store_address:        str
    store_latitude:       Optional[float] = None
    store_longitude:      Optional[float] = None
    created_by_id:        str
    executor_id:          Optional[str]  = None
    price:                float
    price_includes_tax:   bool
    price_tax_amount:     float
    scheduled_date:       str
    scheduled_time_start: Optional[str]  = None
    scheduled_time_end:   Optional[str]  = None
    actual_start_at:      Optional[str]  = None
    actual_end_at:        Optional[str]  = None
    duration_minutes:     Optional[int]  = None
    required_photo_count: int
    photo_instructions:   Optional[str]  = None
    photos_verified:      bool
    rejection_reason:     Optional[str]  = None
    rejection_count:      int
    photos:               list[TaskPhotoResponse] = []
    created_at:           str
    published_at:         Optional[str]  = None
    taken_at:             Optional[str]  = None
    submitted_at:         Optional[str]  = None
    completed_at:         Optional[str]  = None

    model_config = {"from_attributes": True}


class TaskListResponse(BaseModel):
    """Постраничный список заданий."""
    items: list[TaskResponse]
    total: int
    page:  int
    size:  int
    pages: int


class TaskTemplateResponse(BaseModel):
    """Данные шаблона задания."""
    id:                   str
    title:                str
    description:          str
    category:             str
    default_price:        float
    required_photo_count: int
    photo_instructions:   Optional[str] = None
    usage_count:          int
    is_active:            bool

    model_config = {"from_attributes": True}
