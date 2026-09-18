from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(default="ok")
    version: str = Field(default="2.0.0")
    active_rooms: int = Field(default=0)


class CreateRoomResponse(BaseModel):
    room_id: str
    created_at: int
    ttl_seconds: int = 86400  # Ephemeral room lifecycle


class FileUploadResponse(BaseModel):
    file_id: str
    size_bytes: int
    expires_in_seconds: int
