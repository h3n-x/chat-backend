import re
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from app.config import (
    FILE_TTL_SECONDS,
    RATE_LIMIT_FILE_UPLOADS_PER_MINUTE,
)
from app.models.api_schemas import FileUploadResponse
from app.security.rate_limiter import get_client_ip, rate_limiter
from app.services.file_storage import file_storage

router = APIRouter(prefix="/api/files", tags=["Files"])

UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


@router.post("/upload", response_model=FileUploadResponse)
async def upload_encrypted_file(request: Request):
    """Receive an opaque encrypted file stream with streaming 15MB cutoff."""
    client_ip = get_client_ip(request)
    if not rate_limiter.is_allowed(
        client_ip, "file_upload", RATE_LIMIT_FILE_UPLOADS_PER_MINUTE
    ):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="File upload rate limit exceeded. Please wait before uploading another file.",
        )

    file_id, size_bytes = await file_storage.save_stream(request)

    return FileUploadResponse(
        file_id=file_id,
        size_bytes=size_bytes,
        expires_in_seconds=FILE_TTL_SECONDS,
    )


@router.get("/download/{file_id}")
async def download_encrypted_file(file_id: str):
    """Download an opaque encrypted blob by its UUID before TTL expiration."""
    if not UUID_PATTERN.match(file_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file identifier format",
        )

    file_path = file_storage.get_file_path_if_valid(file_id)
    if not file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found or expired",
        )

    headers = {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Content-Disposition": 'attachment; filename="payload.enc"',
        "Content-Length": str(file_path.stat().st_size),
    }

    return StreamingResponse(
        file_storage.stream_file(file_path),
        media_type="application/octet-stream",
        headers=headers,
    )
