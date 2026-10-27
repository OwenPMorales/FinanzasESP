import io
import logging
from collections.abc import Iterator
from datetime import timedelta
from functools import lru_cache

from fastapi import HTTPException, status
from minio import Minio
from minio.deleteobjects import DeleteObject
from minio.error import MinioException

from core.config import settings

logger = logging.getLogger(__name__)

# Firmas binarias ("magic bytes"): se valida el contenido real del archivo,
# no el Content-Type que manda el cliente (que se puede falsificar).
FILE_SIGNATURES: dict[str, tuple[bytes, ...]] = {
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/webp": (b"RIFF",),
    "application/pdf": (b"%PDF-",),
}
EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "application/pdf": ".pdf",
}
IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
# Los tickets también pueden ser facturas PDF (CFDI).
TICKET_TYPES = IMAGE_TYPES | {"application/pdf"}


def detect_content_type(data: bytes) -> str | None:
    for content_type, signatures in FILE_SIGNATURES.items():
        if any(data.startswith(sig) for sig in signatures):
            if content_type == "image/webp" and data[8:12] != b"WEBP":
                continue
            return content_type
    return None


def validate_file(data: bytes, allowed: set[str]) -> str:
    """Valida tamaño y tipo real. Devuelve el content-type detectado."""
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El archivo está vacío.")
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"El archivo supera el límite de {settings.MAX_UPLOAD_MB} MB.",
        )
    content_type = detect_content_type(data)
    if content_type not in allowed:
        permitidos = ", ".join(sorted(EXTENSIONS[t] for t in allowed))
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Tipo de archivo no permitido. Formatos aceptados: {permitidos}",
        )
    return content_type


def storage_unavailable(exc: Exception) -> HTTPException:
    logger.error("Error de MinIO: %s", exc)
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="El almacenamiento de archivos no está disponible.",
    )


class StorageService:
    """Envoltura del SDK de MinIO: el resto de la API no conoce detalles de S3."""

    def __init__(self) -> None:
        self.bucket = settings.MINIO_BUCKET
        self.client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
            region=settings.MINIO_REGION,
        )
        # Las URLs prefirmadas se firman con el host que verá el cliente
        # (navegador o ESP32), que puede ser distinto al host interno.
        self.public_client = Minio(
            settings.MINIO_PUBLIC_ENDPOINT or settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
            region=settings.MINIO_REGION,  # con región fija no hace llamadas de red al firmar
        )

    def ensure_bucket(self) -> None:
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)
            logger.info("Bucket '%s' creado", self.bucket)

    def is_available(self) -> bool:
        try:
            self.client.bucket_exists(self.bucket)
            return True
        except Exception:  # noqa: BLE001 - cualquier fallo = no disponible
            return False

    def upload(self, key: str, data: bytes, content_type: str) -> None:
        try:
            self.client.put_object(
                self.bucket, key, io.BytesIO(data), length=len(data), content_type=content_type
            )
        except MinioException as exc:
            raise storage_unavailable(exc) from exc

    def presigned_url(self, key: str) -> str:
        try:
            return self.public_client.presigned_get_object(
                self.bucket,
                key,
                expires=timedelta(minutes=settings.PRESIGNED_URL_EXPIRE_MINUTES),
            )
        except MinioException as exc:
            raise storage_unavailable(exc) from exc

    def stream(self, key: str) -> Iterator[bytes]:
        try:
            response = self.client.get_object(self.bucket, key)
        except MinioException as exc:
            raise storage_unavailable(exc) from exc

        def iterator() -> Iterator[bytes]:
            try:
                yield from response.stream(32 * 1024)
            finally:
                response.close()
                response.release_conn()

        return iterator()

    def delete(self, key: str) -> None:
        # Si falla, solo se registra: un objeto huérfano es preferible a un error al usuario.
        try:
            self.client.remove_object(self.bucket, key)
        except MinioException as exc:
            logger.warning("No se pudo borrar %s de MinIO: %s", key, exc)

    def delete_prefix(self, prefix: str) -> None:
        """Borra todos los objetos bajo un prefijo (ej. todo lo de un usuario)."""
        try:
            objects = self.client.list_objects(self.bucket, prefix=prefix, recursive=True)
            to_delete = [DeleteObject(obj.object_name) for obj in objects]
            for error in self.client.remove_objects(self.bucket, to_delete):
                logger.warning("No se pudo borrar %s: %s", error.name, error)
        except MinioException as exc:
            logger.warning("No se pudo limpiar el prefijo %s: %s", prefix, exc)


@lru_cache
def get_storage() -> StorageService:
    """Dependencia de FastAPI: una sola instancia (el cliente MinIO reutiliza conexiones)."""
    return StorageService()


# === Convención de llaves: todo lo de un usuario cuelga de users/<id>/ ===

def user_prefix(user_id) -> str:
    return f"users/{user_id}/"


def avatar_key(user_id, content_type: str) -> str:
    return f"{user_prefix(user_id)}avatar/avatar{EXTENSIONS[content_type]}"


def ticket_key(user_id, ticket_id, created_at, content_type: str) -> str:
    return (
        f"{user_prefix(user_id)}tickets/{created_at:%Y/%m}/"
        f"{ticket_id}{EXTENSIONS[content_type]}"
    )
