import os
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent.parent
TEMP_UPLOAD_DIR = Path(os.getenv("TEMP_UPLOAD_DIR", BASE_DIR / "temp_uploads"))

# Server Config
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))

# CORS Config
# Stored as comma-separated origins in env var
DEFAULT_ORIGINS = "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173,http://127.0.0.1:3000,https://chat-zk.netlify.app"
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", DEFAULT_ORIGINS).split(",")
    if origin.strip()
]

# File Transfer Limits (Zero-Knowledge Streaming)
MAX_FILE_SIZE_BYTES = 15 * 1024 * 1024  # 15 MB
CHUNK_SIZE_BYTES = 64 * 1024            # 64 KB per stream chunk
FILE_TTL_SECONDS = 600                  # 10 minutes auto-delete

# WebSocket Limits
WS_MAX_MESSAGE_SIZE = 64 * 1024         # 64 KB maximum frame size
MAX_PARTICIPANTS_PER_ROOM = 50          # Guard against unbounded memory consumption

# Rate Limits (Token Bucket / Sliding Window per Client IP)
RATE_LIMIT_WS_MESSAGES_PER_MINUTE = int(os.getenv("RATE_LIMIT_WS_MESSAGES", "30"))
RATE_LIMIT_WS_CONNECTIONS_PER_IP = int(os.getenv("RATE_LIMIT_WS_CONNECTIONS", "5"))
RATE_LIMIT_FILE_UPLOADS_PER_MINUTE = int(os.getenv("RATE_LIMIT_FILE_UPLOADS", "3"))
RATE_LIMIT_ROOM_CREATION_PER_MINUTE = int(os.getenv("RATE_LIMIT_ROOM_CREATION", "10"))
