# =============================================================================
# KARI.Самозанятые v2 — Сервис шифрования персональных данных
# Файл: app/services/crypto_service.py
# =============================================================================
#
# Персональные данные исполнителей хранятся в зашифрованном виде:
#   - Серия и номер паспорта
#   - Место рождения
#   - Адрес регистрации
#   - Номер банковской карты (последние 4 цифры в открытом виде для UI)
#   - Номер расчётного счёта
#   - БИК банка
#
# Что НЕ шифруем (нужно для поиска и проверок):
#   - Телефон (ключ авторизации)
#   - ИНН (нужен для поиска в стоп-листе и запросов в ФНС)
#   - ФИО (нужно для документов)
#   - UUID записей
#
# Алгоритм: AES-256-GCM (симметричное шифрование)
#   - Ключ берётся из переменной окружения ENCRYPTION_KEY (32 байта, base64)
#   - Для каждого значения генерируется уникальный nonce (96 бит)
#   - Результат: base64(nonce + ciphertext + tag)
#
# Генерация ключа (в терминале):
#   python -c "import secrets, base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"
#
# =============================================================================

import base64
import logging
import os
import secrets
from typing import Optional

logger = logging.getLogger(__name__)

# Пробуем импортировать cryptography (pip install cryptography)
try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    logger.warning(
        "Библиотека cryptography не установлена. "
        "Шифрование персональных данных ОТКЛЮЧЕНО. "
        "Выполните: pip install cryptography"
    )


# =============================================================================
# ЗАГРУЗКА КЛЮЧА ШИФРОВАНИЯ
# =============================================================================

def _load_encryption_key() -> Optional[bytes]:
    """
    Загружает ключ шифрования из переменной окружения ENCRYPTION_KEY.
    Ключ должен быть 32 байта в формате base64.

    В production: ключ хранится в vault (HashiCorp Vault / Yandex Lockbox).
    В разработке: в .env файле.
    """
    key_b64 = os.getenv("ENCRYPTION_KEY")
    if not key_b64:
        logger.warning(
            "ENCRYPTION_KEY не задан в .env. "
            "Персональные данные не будут зашифрованы!"
        )
        return None

    try:
        key = base64.b64decode(key_b64)
        if len(key) != 32:
            logger.error(
                "ENCRYPTION_KEY должен быть 32 байта (AES-256). "
                "Текущий размер: %d байт", len(key)
            )
            return None
        return key
    except Exception as e:
        logger.error("Ошибка декодирования ENCRYPTION_KEY: %s", e)
        return None


# Ключ загружается один раз при старте сервиса
_ENCRYPTION_KEY: Optional[bytes] = _load_encryption_key()


# =============================================================================
# ОСНОВНЫЕ ФУНКЦИИ
# =============================================================================

def encrypt(plaintext: str) -> str:
    """
    Зашифровать строку.

    Если ключ не настроен или cryptography не установлена — возвращает исходную
    строку (режим разработки, не для production).

    Args:
        plaintext: Строка для шифрования

    Returns:
        Зашифрованная строка в формате base64
    """
    if not plaintext:
        return plaintext

    if not CRYPTO_AVAILABLE or not _ENCRYPTION_KEY:
        logger.debug("Шифрование отключено, возвращаем plaintext")
        return plaintext

    try:
        aesgcm = AESGCM(_ENCRYPTION_KEY)
        nonce = secrets.token_bytes(12)  # 96 бит — оптимально для GCM
        ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
        # Упаковываем: nonce (12 байт) + ciphertext + tag (16 байт встроен)
        return base64.b64encode(nonce + ciphertext).decode("utf-8")
    except Exception as e:
        logger.error("Ошибка шифрования: %s", e)
        return plaintext  # Fallback — лучше сохранить, чем потерять


def decrypt(ciphertext_b64: str) -> str:
    """
    Расшифровать строку.

    Args:
        ciphertext_b64: Зашифрованная строка (base64)

    Returns:
        Расшифрованная строка

    Raises:
        ValueError: Если расшифровка не удалась (повреждённые данные)
    """
    if not ciphertext_b64:
        return ciphertext_b64

    if not CRYPTO_AVAILABLE or not _ENCRYPTION_KEY:
        logger.debug("Шифрование отключено, возвращаем как есть")
        return ciphertext_b64

    try:
        data = base64.b64decode(ciphertext_b64)
        nonce = data[:12]
        ciphertext = data[12:]
        aesgcm = AESGCM(_ENCRYPTION_KEY)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext.decode("utf-8")
    except Exception as e:
        logger.error("Ошибка расшифровки: %s", e)
        raise ValueError(f"Не удалось расшифровать данные: {e}")


def encrypt_passport(series: str, number: str) -> str:
    """
    Зашифровать паспортные данные.
    Серия и номер хранятся вместе в одной зашифрованной строке.

    Args:
        series: Серия паспорта (4 цифры)
        number: Номер паспорта (6 цифр)

    Returns:
        Зашифрованная строка "СЕРИЯ НОМЕР"
    """
    combined = f"{series} {number}"
    return encrypt(combined)


def decrypt_passport(encrypted: str) -> tuple[str, str]:
    """
    Расшифровать паспортные данные.

    Returns:
        Tuple (series, number)
    """
    decrypted = decrypt(encrypted)
    parts = decrypted.split(" ", 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return decrypted, ""


def mask_card_number(card_number: str) -> str:
    """
    Маскировать номер карты для отображения в UI.
    Например: "4111111111111111" → "**** **** **** 1111"

    Настоящий номер хранится только в зашифрованном виде.
    В UI всегда показываем только маску.
    """
    # Убираем пробелы и дефисы
    clean = card_number.replace(" ", "").replace("-", "")
    if len(clean) >= 4:
        return f"**** **** **** {clean[-4:]}"
    return "****"


def mask_account_number(account: str) -> str:
    """
    Маскировать номер расчётного счёта.
    Например: "40817810123456789012" → "408178**********9012"
    """
    if len(account) >= 8:
        return f"{account[:6]}{'*' * (len(account) - 10)}{account[-4:]}"
    return "****"


def mask_inn(inn: str) -> str:
    """
    Маскировать ИНН для публичного отображения.
    Например: "381012345678" → "3810****5678"
    """
    if len(inn) >= 8:
        return f"{inn[:4]}{'*' * (len(inn) - 8)}{inn[-4:]}"
    return "****"


# =============================================================================
# УТИЛИТА: ГЕНЕРАЦИЯ КЛЮЧА
# =============================================================================

def generate_encryption_key() -> str:
    """
    Сгенерировать новый ключ шифрования.
    Используется один раз при первоначальной настройке.

    Добавьте результат в .env:
        ENCRYPTION_KEY=<результат>
    """
    key = secrets.token_bytes(32)
    return base64.b64encode(key).decode("utf-8")


# При запуске в режиме разработки — подсказка
if __name__ == "__main__":
    print("Генерация ключа шифрования для .env:")
    print(f"ENCRYPTION_KEY={generate_encryption_key()}")
    print()
    print("Тест шифрования:")
    test = "4111 1111 1111 1111"
    enc = encrypt(test)
    dec = decrypt(enc) if enc != test else "(шифрование отключено)"
    print(f"  Исходное: {test}")
    print(f"  Зашифровано: {enc[:40]}...")
    print(f"  Расшифровано: {dec}")
    print(f"  Маска карты: {mask_card_number(test)}")
