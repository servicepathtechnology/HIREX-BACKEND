"""Presigned URL endpoint for direct S3 uploads from client."""

import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.core.config import settings
from app.core.dependencies import get_current_user
from app.models.user import User

router = APIRouter(prefix="/upload", tags=["upload"])

ALLOWED_CONTENT_TYPES = {
    "application/pdf", "application/zip",
    "image/png", "image/jpeg", "image/webp",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain", "application/octet-stream",
}


class PresignedUrlResponse(BaseModel):
    upload_url: str
    file_url: str
    key: str


@router.get("/presigned-url", response_model=PresignedUrlResponse)
async def get_presigned_url(
    filename: str = Query(...),
    content_type: str = Query(...),
    current_user: User = Depends(get_current_user),
) -> PresignedUrlResponse:
    if not settings.aws_s3_bucket:
        raise HTTPException(
            status_code=503,
            detail="File storage not configured. Set AWS_S3_BUCKET in .env.",
        )

    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Content type not allowed: {content_type}",
        )

    ext = filename.rsplit(".", 1)[-1] if "." in filename else "bin"
    key = f"submissions/{current_user.id}/{uuid.uuid4()}.{ext}"

    import boto3
    s3 = boto3.client(
        "s3",
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        region_name="us-east-1",
    )

    upload_url = s3.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": settings.aws_s3_bucket,
            "Key": key,
            "ContentType": content_type,
        },
        ExpiresIn=3600,
    )

    base = (
        settings.aws_cloudfront_url.rstrip("/")
        if settings.aws_cloudfront_url
        else f"https://{settings.aws_s3_bucket}.s3.amazonaws.com"
    )
    file_url = f"{base}/{key}"

    return PresignedUrlResponse(upload_url=upload_url, file_url=file_url, key=key)
