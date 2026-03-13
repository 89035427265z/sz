# =============================================================================
# KARI.Самозанятые — Схемы данных выплат
# Файл: app/schemas/payment.py
# =============================================================================

from typing import Optional
from pydantic import BaseModel


# =============================================================================
# ОТВЕТЫ — ВЫПЛАТЫ
# =============================================================================

class PaymentResponse(BaseModel):
    """Данные одной выплаты."""
    id:                        str
    task_id:                   str
    executor_id:               str
    executor_name:             Optional[str]  = None
    executor_phone:            Optional[str]  = None
    amount:                    float
    tax_amount:                float
    total_amount:              float
    status:                    str
    bank_card_masked:          Optional[str]  = None
    bank_name:                 Optional[str]  = None
    sovcombank_transaction_id: Optional[str]  = None
    error_message:             Optional[str]  = None
    retry_count:               int            = 0
    fns_receipt_id:            Optional[str]  = None
    created_at:                str
    processing_at:             Optional[str]  = None
    completed_at:              Optional[str]  = None

    model_config = {"from_attributes": True}


class PaymentListResponse(BaseModel):
    """Постраничный список выплат."""
    items: list[PaymentResponse]
    total: int
    page:  int
    size:  int
    pages: int


# =============================================================================
# ОТВЕТЫ — РЕЕСТРЫ МАССОВЫХ ВЫПЛАТ (ТЗ 3.12)
# =============================================================================

class RegistryItemResponse(BaseModel):
    """Одна строка реестра массовых выплат."""
    id:               str
    row_number:       int
    executor_inn:     str
    executor_name:    Optional[str]  = None
    service_description: str
    amount:           float
    work_date:        str
    status:           str

    # Результаты 5 проверок
    check_fns_status:   Optional[bool] = None
    check_income_limit: Optional[bool] = None
    check_duplicate:    Optional[bool] = None
    check_amount:       Optional[bool] = None
    check_budget:       Optional[bool] = None
    all_checks_passed:  bool           = False

    validation_errors:  Optional[list] = None
    error_message:      Optional[str]  = None
    payment_id:         Optional[str]  = None

    model_config = {"from_attributes": True}


class RegistryResponse(BaseModel):
    """Данные реестра массовых выплат."""
    id:                  str
    name:                str
    number:              Optional[str] = None
    status:              str
    file_name_original:  str
    total_rows:          int
    valid_rows:          int
    invalid_rows:        int
    paid_rows:           int
    failed_rows:         int
    total_amount:        float
    paid_amount:         float
    validation_summary:  Optional[dict] = None
    xml_export_path:     Optional[str]  = None
    created_at:          str
    validated_at:        Optional[str]  = None
    approved_at:         Optional[str]  = None
    completed_at:        Optional[str]  = None

    model_config = {"from_attributes": True}


class RegistryListResponse(BaseModel):
    """Постраничный список реестров."""
    items: list[RegistryResponse]
    total: int
    page:  int
    size:  int
    pages: int


# =============================================================================
# ОТВЕТЫ — ЧЕКИ ФНС (ТЗ 3.11)
# =============================================================================

class FnsReceiptResponse(BaseModel):
    """Данные чека ФНС."""
    id:                        str
    payment_id:                str
    executor_id:               str
    fns_receipt_uuid:          Optional[str]  = None
    fns_receipt_link:          Optional[str]  = None
    amount:                    float
    service_name:              str
    service_date:              str
    status:                    str
    cancelled_at:              Optional[str]  = None
    cancel_reason:             Optional[str]  = None
    last_check_at:             Optional[str]  = None
    director_notified_at:      Optional[str]  = None
    accounting_notified_at:    Optional[str]  = None
    accounting_notified_in_time: Optional[bool] = None
    issued_at:                 Optional[str]  = None

    model_config = {"from_attributes": True}
