import shutil
import tempfile
from pathlib import Path
import pytest
from starlette.testclient import TestClient

from app.main import app
from app.services.file_storage import file_storage
from app.services.room_manager import room_manager
from app.security.rate_limiter import rate_limiter


@pytest.fixture(autouse=True)
def reset_state():
    """Reset singleton state and use a temporary directory for file uploads between tests."""
    # Create temp dir for uploads
    temp_dir = Path(tempfile.mkdtemp())
    orig_dir = file_storage.upload_dir
    file_storage.upload_dir = temp_dir

    # Reset room manager & rate limiter
    room_manager._rooms.clear()
    rate_limiter._history.clear()
    rate_limiter._active_connections.clear()

    yield

    # Cleanup
    file_storage.upload_dir = orig_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def client():
    """Synchronous test client for REST endpoints and WebSockets."""
    with TestClient(app) as test_client:
        yield test_client
