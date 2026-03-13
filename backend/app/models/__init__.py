# =============================================================================
# Импортируем все модели здесь — это нужно для Alembic (миграции БД)
# Alembic сканирует этот файл чтобы понять какие таблицы создавать
# =============================================================================

# =============================================================================
# Модели v1 (основной проект)
# =============================================================================
from app.models.user import User, SmsCode, UserRole, FnsStatus, UserStatus
from app.models.task import Task, TaskPhoto, TaskTemplate, TaskStatus, TaskCategory
from app.models.payment import (
    Payment, PaymentRegistry, PaymentRegistryItem, FnsReceipt,
    PaymentStatus, RegistryStatus, FnsReceiptStatus,
)
from app.models.document import Document, DocumentType, DocumentStatus
from app.models.stop_list import StopList, StopListReason

# =============================================================================
# Модели v2 — объединение с проектом коллеги (Март 2026)
# Новые таблицы создаются миграцией: alembic/versions/20260310_0004_new_features.py
# =============================================================================
from app.models.rating import Rating
from app.models.chat import ChatMessage
from app.models.penalty import Penalty, PenaltyType
from app.models.store_blacklist import StoreBlacklist
from app.models.audit_log import AuditLog
