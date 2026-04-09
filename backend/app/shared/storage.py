import io
import logging

from minio import Minio
from minio.error import S3Error

from app.config import settings

logger = logging.getLogger(__name__)

_client: Minio | None = None
_presign_client: Minio | None = None


def get_minio_client() -> Minio:
    global _client
    if _client is None:
        _client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_USE_SSL,
        )
        _ensure_bucket()
    return _client


def _get_presign_client() -> Minio:
    """Return a MinIO client whose endpoint matches what the browser will use.

    Inside Docker the internal client talks to ``minio:9000`` but presigned
    URLs must be signed for the host the browser will hit
    (``localhost:9000``).  S3-V4 signatures include the ``Host`` header, so a
    post-hoc string-replace on the URL invalidates the signature.

    We create a second client pointing at the external endpoint and
    pre-populate its region cache so it never needs to actually connect.
    """
    external = settings.MINIO_EXTERNAL_ENDPOINT
    if not external or external == settings.MINIO_ENDPOINT:
        return get_minio_client()

    global _presign_client
    if _presign_client is None:
        # Resolve the real region from the internal client first
        internal = get_minio_client()
        region = internal._get_region(settings.MINIO_BUCKET)

        _presign_client = Minio(
            external,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_EXTERNAL_USE_SSL,
            region=region,
        )
        # Pre-populate so presigned_get_object skips the network lookup
        _presign_client._region_map[settings.MINIO_BUCKET] = region
    return _presign_client


def _ensure_bucket() -> None:
    client = _client
    if client is None:
        return
    bucket = settings.MINIO_BUCKET
    try:
        if not client.bucket_exists(bucket):
            client.make_bucket(bucket)
            logger.info("Created MinIO bucket: %s", bucket)
    except S3Error as e:
        logger.error("Failed to ensure MinIO bucket: %s", e)
        raise


def upload_file(
    object_key: str,
    data: bytes,
    content_type: str = "application/octet-stream",
) -> None:
    client = get_minio_client()
    client.put_object(
        settings.MINIO_BUCKET,
        object_key,
        io.BytesIO(data),
        length=len(data),
        content_type=content_type,
    )


def get_file_url(
    object_key: str,
    tenant_id: str | None = None,
    expires_minutes: int = 10,
) -> str:
    from datetime import timedelta

    if tenant_id and not object_key.startswith(f"{tenant_id}/"):
        logger.warning(
            "Tenant mismatch on presigned URL: tenant=%s, key=%s",
            tenant_id, object_key,
        )
        raise ValueError("Access denied")

    client = _get_presign_client()
    return client.presigned_get_object(
        settings.MINIO_BUCKET,
        object_key,
        expires=timedelta(minutes=expires_minutes),
    )


def delete_file(object_key: str) -> None:
    client = get_minio_client()
    try:
        client.remove_object(settings.MINIO_BUCKET, object_key)
    except S3Error as e:
        logger.error("Failed to delete object %s: %s", object_key, e)
        raise


def get_file_bytes(object_key: str) -> bytes:
    client = get_minio_client()
    response = None
    try:
        response = client.get_object(settings.MINIO_BUCKET, object_key)
        return response.read()
    finally:
        if response is not None:
            response.close()
            response.release_conn()
