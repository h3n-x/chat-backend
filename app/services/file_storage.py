import asyncio
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Optional, AsyncGenerator

import aiofiles
from fastapi import HTTPException, status
from starlette.requests import Request

from app.config import (
    CHUNK_SIZE_BYTES,
    FILE_TTL_SECONDS,
    MAX_FILE_SIZE_BYTES,
    TEMP_UPLOAD_DIR,
)

logger = logging.getLogger("chat.file_storage")


class FileStorageService:
    """Manages ephemeral encrypted file blobs on disk with strict size caps and TTL."""

    def __init__(self, upload_dir: Path = TEMP_UPLOAD_DIR):
        self.upload_dir = upload_dir
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    def _get_file_path(self, file_id: str) -> Path:
        # Sanitize UUID to prevent path traversal
        clean_id = Path(file_id).name
        return self.upload_dir / f"{clean_id}.enc"

    async def save_stream(self, request: Request) -> tuple[str, int]:
        """Stream request body directly to disk in 64KB chunks.
        
        Enforces a hard 15MB limit; aborts with HTTP 413 immediately if exceeded,
        ensuring bounded RAM consumption.
        """
        file_id = str(uuid.uuid4())
        file_path = self._get_file_path(file_id)
        total_bytes = 0

        try:
            async with aiofiles.open(file_path, "wb") as f:
                async for chunk in request.stream():
                    total_bytes += len(chunk)
                    if total_bytes > MAX_FILE_SIZE_BYTES:
                        # Hard cutoff reached
                        logger.warning(
                            f"Upload rejected: exceeded {MAX_FILE_SIZE_BYTES} bytes. Aborting."
                        )
                        # Close and delete the partially written file
                        break
                    await f.write(chunk)

            if total_bytes > MAX_FILE_SIZE_BYTES:
                if file_path.exists():
                    file_path.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                    detail=f"File exceeds maximum allowed limit of {MAX_FILE_SIZE_BYTES // (1024 * 1024)}MB",
                )

            if total_bytes == 0:
                if file_path.exists():
                    file_path.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot upload empty file payload",
                )

            logger.info(f"Encrypted blob saved: {file_id}.enc ({total_bytes} bytes)")
            return file_id, total_bytes

        except HTTPException:
            raise
        except Exception as e:
            if file_path.exists():
                file_path.unlink(missing_ok=True)
            logger.error(f"Error saving stream: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to process file stream",
            )

    def get_file_path_if_valid(self, file_id: str) -> Optional[Path]:
        """Return Path if file exists and has not exceeded TTL, otherwise remove and return None."""
        file_path = self._get_file_path(file_id)
        if not file_path.is_file():
            return None

        # Check TTL
        file_mtime = file_path.stat().st_mtime
        if time.time() - file_mtime > FILE_TTL_SECONDS:
            file_path.unlink(missing_ok=True)
            logger.info(f"File {file_id}.enc expired and was deleted upon request.")
            return None

        return file_path

    async def stream_file(self, file_path: Path) -> AsyncGenerator[bytes, None]:
        """Stream an encrypted file from disk in 64KB chunks."""
        async with aiofiles.open(file_path, "rb") as f:
            while chunk := await f.read(CHUNK_SIZE_BYTES):
                yield chunk

    def cleanup_expired_files(self) -> int:
        """Purge all encrypted files older than FILE_TTL_SECONDS."""
        deleted_count = 0
        now = time.time()
        for f in self.upload_dir.glob("*.enc"):
            try:
                if now - f.stat().st_mtime > FILE_TTL_SECONDS:
                    f.unlink(missing_ok=True)
                    deleted_count += 1
            except Exception as e:
                logger.debug(f"Failed to delete expired file {f}: {e}")
        
        if deleted_count > 0:
            logger.info(f"Purged {deleted_count} expired encrypted files.")
        return deleted_count


# Global singleton instance
file_storage = FileStorageService()
