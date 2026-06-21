import uuid
from io import BytesIO
from typing import Any, Optional, Tuple

import boto3
from PIL import Image, ImageOps
from starlette.concurrency import run_in_threadpool

from config import settings


def _get_s3_client() -> Any:
    return boto3.client(
        "s3",
        region_name=settings.s3_region,
        aws_access_key_id=(
            settings.s3_access_key_id.get_secret_value()
            if settings.s3_access_key_id
            else None
        ),
        aws_secret_access_key=(
            settings.s3_secret_access_key.get_secret_value()
            if settings.s3_secret_access_key
            else None
        ),
        endpoint_url=settings.s3_endpoint_url,
    )


def process_image(content: bytes) -> Tuple[bytes, str]:
    with Image.open(BytesIO(content)) as original:
        img = ImageOps.exif_transpose(original)
        img = ImageOps.fit(img, (300, 300), method=Image.Resampling.LANCZOS)
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGB")

        filename = f"{uuid.uuid4().hex}.jpg"
        output = BytesIO()
        img.save(output, "JPEG", quality=85, optimize=True)
        output.seek(0)
        processed_image_bytes = output.read()

    return processed_image_bytes, filename


def _upload_to_s3(file_bytes: bytes, key: str) -> None:
    s3_client = _get_s3_client()
    # Blocking call, hence, it should run in a separate threadpool
    s3_client.upload_fileobj(
        BytesIO(file_bytes),
        settings.s3_bucket_name,
        key,
        ExtraArgs={"ContentType": "image/jpeg"},
    )


def _delete_from_s3(key: str) -> None:
    s3_client = _get_s3_client()
    # Blocking call, hence, it should run in a separate threadpool
    s3_client.delete_object(
        Bucket=settings.s3_bucket_name,
        Key=key,
    )


async def upload_profile_image(file_bytes: bytes, filename: str) -> None:
    key = f"profile_pics/{filename}"
    await run_in_threadpool(_upload_to_s3, file_bytes, key)


async def delete_profile_image(filename: Optional[str] = None) -> None:
    if filename is None:
        return
    key = f"profile_pics/{filename}"
    await run_in_threadpool(_delete_from_s3, key)
