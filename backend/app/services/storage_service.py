# =============================================================================
# KARI.Самозанятые — Сервис хранения файлов (MinIO)
# Файл: app/services/storage_service.py
# =============================================================================
# MinIO — это наше собственное S3-хранилище на сервере KARI.
# Туда загружаем: фотоотчёты к заданиям, акты, договоры.
#
# Фотоотчёты хранятся 3 года (требование ТЗ 3.10).
# Путь к файлу: kari-photos/2025/12/01/<task_id>/<номер>.jpg
# =============================================================================

import io
import math
import logging
from datetime import datetime, timezone
from typing import Optional

from minio import Minio
from minio.error import S3Error

from app.config import settings

logger = logging.getLogger(__name__)

# Клиент MinIO — создаётся один раз при старте
_minio_client: Optional[Minio] = None


def get_minio_client() -> Minio:
    """Возвращает клиент MinIO (создаёт при первом вызове)."""
    global _minio_client
    if _minio_client is None:
        _minio_client = Minio(
            endpoint=settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
        )
        # Создаём бакеты если не существуют
        for bucket in [settings.MINIO_BUCKET_PHOTOS, settings.MINIO_BUCKET_DOCS]:
            try:
                if not _minio_client.bucket_exists(bucket):
                    _minio_client.make_bucket(bucket)
                    logger.info(f"Создан бакет MinIO: {bucket}")
            except S3Error as e:
                logger.error(f"Ошибка создания бакета {bucket}: {e}")
    return _minio_client


# =============================================================================
# ЗАГРУЗКА ФОТОГРАФИИ
# =============================================================================

async def upload_photo(
    file_data: bytes,
    task_id: str,
    sequence_number: int,
    content_type: str = "image/jpeg",
) -> str:
    """
    Загружает фотографию в MinIO и возвращает путь к файлу.

    Путь формата: 2025/12/01/<task_id>/1.jpg
    """
    now = datetime.now(timezone.utc)
    ext = "jpg" if "jpeg" in content_type else content_type.split("/")[-1]

    # Формируем путь: год/месяц/день/task_id/номер.расширение
    file_path = f"{now.year}/{now.month:02d}/{now.day:02d}/{task_id}/{sequence_number}.{ext}"

    try:
        client = get_minio_client()
        client.put_object(
            bucket_name=settings.MINIO_BUCKET_PHOTOS,
            object_name=file_path,
            data=io.BytesIO(file_data),
            length=len(file_data),
            content_type=content_type,
        )
        logger.info(f"Фото загружено в MinIO: {file_path}")
        return file_path

    except S3Error as e:
        logger.error(f"Ошибка загрузки фото в MinIO: {e}")
        raise RuntimeError(f"Не удалось сохранить фото: {e}")


async def delete_photo(file_path: str) -> bool:
    """Удаляет файл из MinIO (при отклонении задания)."""
    try:
        client = get_minio_client()
        client.remove_object(settings.MINIO_BUCKET_PHOTOS, file_path)
        return True
    except S3Error as e:
        logger.error(f"Ошибка удаления фото {file_path}: {e}")
        return False


def get_photo_url(file_path: str, expires_hours: int = 24) -> str:
    """
    Генерирует временную ссылку на фото (действует expires_hours часов).
    Используется для показа фото в интерфейсе.
    """
    from datetime import timedelta
    try:
        client = get_minio_client()
        url = client.presigned_get_object(
            bucket_name=settings.MINIO_BUCKET_PHOTOS,
            object_name=file_path,
            expires=timedelta(hours=expires_hours),
        )
        return url
    except S3Error as e:
        logger.error(f"Ошибка генерации ссылки для {file_path}: {e}")
        return ""


# =============================================================================
# РАБОТА С ИЗОБРАЖЕНИЯМИ
# =============================================================================

def validate_and_get_image_info(file_data: bytes) -> dict:
    """
    Проверяет изображение и возвращает его параметры.

    Проверяет:
    - Размер файла (макс 10 МБ)
    - Разрешение (мин 1280×720)
    - Извлекает GPS-координаты из EXIF

    Возвращает словарь: {width, height, latitude, longitude, taken_at}
    """
    from PIL import Image
    from PIL.ExifTags import TAGS, GPSTAGS
    import io as stdlib_io

    MAX_SIZE_BYTES = 10 * 1024 * 1024  # 10 МБ
    MIN_WIDTH  = 1280
    MIN_HEIGHT = 720

    # Проверка размера файла
    if len(file_data) > MAX_SIZE_BYTES:
        raise ValueError(
            f"Файл слишком большой: {len(file_data) / 1_048_576:.1f} МБ. "
            f"Максимум: 10 МБ"
        )

    try:
        image = Image.open(stdlib_io.BytesIO(file_data))
    except Exception:
        raise ValueError("Файл не является изображением или повреждён")

    width, height = image.size

    # Проверка разрешения
    if width < MIN_WIDTH or height < MIN_HEIGHT:
        raise ValueError(
            f"Разрешение {width}×{height} слишком маленькое. "
            f"Минимум: {MIN_WIDTH}×{MIN_HEIGHT}"
        )

    result = {
        "width":     width,
        "height":    height,
        "latitude":  None,
        "longitude": None,
        "taken_at":  None,
    }

    # Извлечение EXIF данных (GPS + дата съёмки)
    try:
        exif_data = image._getexif()
        if exif_data:
            for tag_id, value in exif_data.items():
                tag = TAGS.get(tag_id, tag_id)

                # Дата и время съёмки
                if tag == "DateTimeOriginal":
                    try:
                        result["taken_at"] = datetime.strptime(value, "%Y:%m:%d %H:%M:%S")
                    except Exception:
                        pass

                # GPS координаты
                if tag == "GPSInfo":
                    gps = {GPSTAGS.get(t, t): v for t, v in value.items()}

                    lat = _gps_to_decimal(
                        gps.get("GPSLatitude"),
                        gps.get("GPSLatitudeRef", "N"),
                    )
                    lon = _gps_to_decimal(
                        gps.get("GPSLongitude"),
                        gps.get("GPSLongitudeRef", "E"),
                    )
                    if lat and lon:
                        result["latitude"]  = lat
                        result["longitude"] = lon
    except Exception as e:
        logger.warning(f"Не удалось прочитать EXIF: {e}")

    return result


def _gps_to_decimal(coords, ref: str) -> Optional[float]:
    """Переводит GPS координаты из формата EXIF (градусы/минуты/секунды) в десятичные."""
    if not coords:
        return None
    try:
        d = float(coords[0])
        m = float(coords[1])
        s = float(coords[2])
        decimal = d + m / 60 + s / 3600
        if ref in ("S", "W"):
            decimal = -decimal
        return round(decimal, 6)
    except Exception:
        return None


# =============================================================================
# ГЕОПРОВЕРКА ФОТОГРАФИИ (ТЗ 3.10 — радиус 300 метров)
# =============================================================================

def calculate_distance_meters(
    lat1: float, lon1: float,
    lat2: float, lon2: float,
) -> float:
    """
    Вычисляет расстояние между двумя точками по формуле Гаверсинуса.
    Возвращает расстояние в метрах.
    """
    R = 6_371_000  # Радиус Земли в метрах

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return round(R * c, 1)


def verify_photo_location(
    photo_lat: float,
    photo_lon: float,
    store_lat: float,
    store_lon: float,
    max_distance_meters: float = 300.0,
) -> tuple[str, float]:
    """
    Проверяет что фото сделано рядом с магазином (в радиусе 300м).

    Возвращает: (статус: 'verified'|'failed', расстояние_в_метрах)
    """
    distance = calculate_distance_meters(photo_lat, photo_lon, store_lat, store_lon)

    if distance <= max_distance_meters:
        return "verified", distance
    else:
        return "failed", distance


# =============================================================================
# КЛАСС StorageService — обёртка для работы с MinIO (загрузка/скачивание PDF)
# =============================================================================

class StorageService:
    """
    Сервис для работы с MinIO: загрузка и скачивание файлов (PDF договоров, актов).
    Используется в api/documents.py.
    """

    async def upload_bytes(
        self,
        bucket: str,
        path: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> None:
        """
        Загружает байты в MinIO.
        bucket — имя бакета (например 'kari-documents')
        path   — путь внутри бакета
        data   — содержимое файла
        """
        import asyncio
        from functools import partial

        client = get_minio_client()

        # Убеждаемся что бакет существует
        try:
            if not client.bucket_exists(bucket):
                client.make_bucket(bucket)
        except S3Error:
            pass

        # MinIO SDK синхронный — выполняем в executor чтобы не блокировать event loop
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            partial(
                client.put_object,
                bucket,
                path,
                io.BytesIO(data),
                len(data),
                content_type=content_type,
            )
        )
        logger.info(f"Файл загружен в MinIO: {bucket}/{path} ({len(data)} байт)")

    async def download_bytes(
        self,
        bucket: str,
        path: str,
    ) -> bytes:
        """
        Скачивает файл из MinIO и возвращает байты.
        """
        import asyncio
        from functools import partial

        client = get_minio_client()

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            partial(client.get_object, bucket, path)
        )
        try:
            data = response.read()
        finally:
            response.close()
            response.release_conn()

        logger.info(f"Файл скачан из MinIO: {bucket}/{path} ({len(data)} байт)")
        return data
