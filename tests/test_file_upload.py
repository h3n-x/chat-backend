import os
import time
from pathlib import Path
from starlette.testclient import TestClient

from app.config import MAX_FILE_SIZE_BYTES
from app.main import app
from app.services.file_storage import file_storage


def test_file_upload_and_download_success(client: TestClient):
    """Test standard streaming encrypted blob upload and download."""
    content = os.urandom(1024 * 128)  # 128 KB opaque binary payload

    # Upload
    response = client.post(
        "/api/files/upload",
        content=content,
        headers={"Content-Type": "application/octet-stream"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "file_id" in data
    assert data["size_bytes"] == len(content)
    assert data["expires_in_seconds"] == 600
    file_id = data["file_id"]

    # Download
    dl_response = client.get(f"/api/files/download/{file_id}")
    assert dl_response.status_code == 200
    assert dl_response.content == content
    assert dl_response.headers["Content-Type"] == "application/octet-stream"
    assert "no-store" in dl_response.headers["Cache-Control"]
    assert dl_response.headers["Content-Length"] == str(len(content))


def test_file_upload_exceeds_15mb_aborts_with_413(client: TestClient):
    """Test streaming upload aborts with HTTP 413 when exceeding 15MB cutoff."""
    # Create generator that produces slightly over 15MB
    chunk_size = 1024 * 1024  # 1 MB chunk
    total_chunks = 16  # 16 MB total

    def stream_over_15mb():
        for _ in range(total_chunks):
            yield b"X" * chunk_size

    response = client.post(
        "/api/files/upload",
        content=stream_over_15mb(),
        headers={"Content-Type": "application/octet-stream"},
    )
    assert response.status_code == 413
    assert "15MB" in response.json()["detail"]

    # Ensure no partial file was left in the upload directory
    assert len(list(file_storage.upload_dir.glob("*.enc"))) == 0


def test_file_upload_empty_fails_with_400(client: TestClient):
    """Uploading zero bytes should fail with 400."""
    response = client.post(
        "/api/files/upload",
        content=b"",
        headers={"Content-Type": "application/octet-stream"},
    )
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


def test_file_download_invalid_uuid_rejected(client: TestClient):
    """Path traversal or invalid UUID formats must be rejected with 400."""
    response = client.get("/api/files/download/../../etc/passwd")
    # URL path normalization might yield 404 or our regex returns 400/404
    assert response.status_code in [400, 404]

    response_non_uuid = client.get("/api/files/download/some-invalid-id")
    assert response_non_uuid.status_code == 400


def test_file_download_nonexistent_returns_404(client: TestClient):
    """Valid UUID that does not exist returns 404."""
    response = client.get("/api/files/download/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


def test_file_ttl_expiration_and_cleanup(client: TestClient):
    """Test that files older than TTL return 404 and are purged during cleanup."""
    content = b"temporary secret"
    res = client.post("/api/files/upload", content=content)
    assert res.status_code == 200
    file_id = res.json()["file_id"]

    file_path = file_storage._get_file_path(file_id)
    assert file_path.exists()

    # Artificially age the file past 600s TTL (e.g. 15 minutes ago)
    past_time = time.time() - 900
    os.utime(file_path, (past_time, past_time))

    # Download request should detect expiration, delete the file, and return 404
    dl_res = client.get(f"/api/files/download/{file_id}")
    assert dl_res.status_code == 404
    assert not file_path.exists()

    # Verify batch cleanup
    res2 = client.post("/api/files/upload", content=content)
    file_id2 = res2.json()["file_id"]
    file_path2 = file_storage._get_file_path(file_id2)
    os.utime(file_path2, (past_time, past_time))

    purged = file_storage.cleanup_expired_files()
    assert purged == 1
    assert not file_path2.exists()


def test_file_upload_rate_limit(client: TestClient):
    """Verify that exceeding RATE_LIMIT_FILE_UPLOADS_PER_MINUTE triggers 429."""
    for _ in range(3):
        res = client.post("/api/files/upload", content=b"data")
        assert res.status_code == 200

    # 4th upload from same IP should be blocked
    res_blocked = client.post("/api/files/upload", content=b"data")
    assert res_blocked.status_code == 429

