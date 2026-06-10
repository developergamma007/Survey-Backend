"""AWS S3 helpers for survey audio."""

from __future__ import annotations

import base64
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Tuple

import boto3
from botocore.exceptions import BotoCoreError, ClientError

_DATA_URL_RE = re.compile(r"^data:([^;]+);base64,(.+)$", re.DOTALL | re.IGNORECASE)

_CONTENT_TYPE_EXT = {
    "audio/webm": "webm",
    "audio/m4a": "m4a",
    "audio/mp4": "m4a",
    "audio/mpeg": "mp3",
    "audio/ogg": "ogg",
    "audio/wav": "wav",
}


def is_configured() -> bool:
    return bool(
        os.getenv("AWS_ACCESS_KEY_ID")
        and os.getenv("AWS_SECRET_ACCESS_KEY")
        and os.getenv("S3_BUCKET_NAME")
    )


def _region() -> str:
    return os.getenv("AWS_REGION", "ap-south-1")


def _client():
    return boto3.client(
        "s3",
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        region_name=_region(),
    )


def _bucket() -> str:
    bucket = os.getenv("S3_BUCKET_NAME")
    if not bucket:
        raise RuntimeError("S3_BUCKET_NAME is not set")
    return bucket


def parse_audio_base64(value: str) -> Tuple[bytes, str]:
    trimmed = value.strip()
    if not trimmed:
        raise ValueError("Empty audio payload")

    match = _DATA_URL_RE.match(trimmed)
    if match:
        content_type = match.group(1).lower()
        payload = match.group(2).strip()
        return base64.b64decode(payload), content_type

    return base64.b64decode(trimmed), "audio/webm"


def to_data_url(value: str) -> str:
    trimmed = value.strip()
    if trimmed.startswith("data:"):
        return trimmed
    return f"data:audio/webm;base64,{trimmed}"


def _extension_for_content_type(content_type: str) -> str:
    return _CONTENT_TYPE_EXT.get(content_type.lower(), "webm")


def upload_survey_audio(audio_base64: str) -> str:
    """Upload audio bytes to S3. Returns the object key."""
    if not is_configured():
        raise RuntimeError("S3 is not configured")

    audio_bytes, content_type = parse_audio_base64(audio_base64)
    if len(audio_bytes) < 50:
        raise ValueError("Audio payload is too small")

    now = datetime.now(timezone.utc)
    ext = _extension_for_content_type(content_type)
    object_key = f"surveys/{now:%Y/%m}/{uuid.uuid4().hex}.{ext}"

    try:
        _client().put_object(
            Bucket=_bucket(),
            Key=object_key,
            Body=audio_bytes,
            ContentType=content_type,
        )
    except (BotoCoreError, ClientError) as exc:
        raise RuntimeError(f"S3 upload failed: {exc}") from exc

    return object_key


def get_playback_url(object_key: str, expires_in: int = 3600) -> str:
    """Return a public or presigned URL for playback."""
    public_base = os.getenv("S3_PUBLIC_BASE_URL", "").strip()
    if public_base:
        return f"{public_base.rstrip('/')}/{object_key.lstrip('/')}"

    return _client().generate_presigned_url(
        "get_object",
        Params={"Bucket": _bucket(), "Key": object_key},
        ExpiresIn=expires_in,
    )
