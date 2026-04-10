"""File upload endpoint — multipart upload to AWS S3 (Part 2 ready)."""

import uuid
import boto3
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel

from app.core.config import settings
from app.core.dependencies import get_current_user
from app.models.user import User

router = APIRouter(prefix="/upload", tags=["upload"])

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_FILE_SIZE_MB = 5


class UploadResponse(BaseModel):
    """URL of the uploaded file."""
    url: str


@router.post("/avatar", response_model=UploadResponse)
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
) -> UploadResponse:
    """
    Upload a profile avatar image to S3.
    Returns the CloudFront URL of the uploaded file.
    Requires AWS credentials in .env (Part 2 activation).
    """
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type not allowed. Use: {', '.join(ALLOWED_IMAGE_TYPES)}",
        )

    contents = await file.read()
    size_mb = len(contents) / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Max size is {MAX_FILE_SIZE_MB}MB.",
        )

    if not settings.aws_s3_bucket:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="File storage not configured. Set AWS_S3_BUCKET in .env.",
        )

    ext = file.filename.rsplit(".", 1)[-1] if file.filename else "jpg"
    key = f"avatars/{current_user.id}/{uuid.uuid4()}.{ext}"

    s3 = boto3.client(
        "s3",
        region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
    )
    s3.put_object(
        Bucket=settings.aws_s3_bucket,
        Key=key,
        Body=contents,
        ContentType=file.content_type,
        ACL="public-read",
    )

    base = settings.aws_cloudfront_url.rstrip("/") if settings.aws_cloudfront_url else \
        f"https://{settings.aws_s3_bucket}.s3.amazonaws.com"
    url = f"{base}/{key}"

    return UploadResponse(url=url)
