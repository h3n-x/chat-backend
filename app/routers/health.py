from fastapi import APIRouter
from app.models.api_schemas import HealthResponse
from app.services.room_manager import room_manager

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint exposing version and active ephemeral room count."""
    return HealthResponse(
        status="ok",
        version="2.0.0",
        active_rooms=room_manager.get_active_room_count(),
    )
