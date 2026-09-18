import re
import secrets
import time
from fastapi import APIRouter, HTTPException, Request, status
from app.config import RATE_LIMIT_ROOM_CREATION_PER_MINUTE
from app.models.api_schemas import CreateRoomResponse
from app.security.rate_limiter import get_client_ip, rate_limiter
from app.services.room_manager import room_manager

router = APIRouter(prefix="/api/rooms", tags=["Rooms"])

# Character set excluding visually ambiguous characters (0, O, I, 1, L)
ROOM_ID_CHARS = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
ROOM_ID_REGEX = re.compile(r"^[A-Za-z0-9_-]{4,16}$")


def generate_room_id(length: int = 6) -> str:
    """Generate a high-entropy, human-readable room code."""
    return "".join(secrets.choice(ROOM_ID_CHARS) for _ in range(length))


@router.post("/create", response_model=CreateRoomResponse)
async def create_room(request: Request):
    """Create a new ephemeral room code with rate limiting."""
    client_ip = get_client_ip(request)
    if not rate_limiter.is_allowed(client_ip, "room_create", RATE_LIMIT_ROOM_CREATION_PER_MINUTE):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Room creation limit exceeded. Please wait before creating another room.",
        )

    room_id = generate_room_id(6)
    return CreateRoomResponse(
        room_id=room_id,
        created_at=int(time.time()),
        ttl_seconds=86400,
    )


@router.get("/{room_id}/status")
async def get_room_status(room_id: str):
    """Query whether a room is currently active and participant count."""
    if not ROOM_ID_REGEX.match(room_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid room ID format",
        )

    exists = room_manager.has_room(room_id)
    participants = room_manager.get_participant_count(room_id)
    return {
        "room_id": room_id,
        "is_active": exists,
        "participant_count": participants,
    }
