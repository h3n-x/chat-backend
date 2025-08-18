from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime
import re

class ChatMessage(BaseModel):
    type: str = "chat_message"
    message: str = Field(..., min_length=1, max_length=500)
    user_id: Optional[str] = None
    username: Optional[str] = None
    timestamp: Optional[str] = None
    
    @validator('message')
    def validate_message(cls, v):
        if not v.strip():
            raise ValueError('El mensaje no puede estar vacío')
        return v.strip()

class FileMessage(BaseModel):
    type: str = "file_message"
    file_id: str = Field(..., min_length=1)
    filename: str = Field(..., min_length=1, max_length=255)
    file_size: int = Field(..., gt=0)
    mime_type: str = Field(..., min_length=1)
    file_url: str = Field(..., min_length=1)
    user_id: Optional[str] = None
    username: Optional[str] = None
    timestamp: Optional[str] = None
    room_id: Optional[str] = None
    
    @validator('filename')
    def validate_filename(cls, v):
        # Sanitizar nombre de archivo
        import re
        sanitized = re.sub(r'[<>:"/\\|?*]', '', v)
        return sanitized[:255]

class SystemMessage(BaseModel):
    type: str = "system_message"
    message: str = Field(..., min_length=1)
    timestamp: Optional[str] = None

class UserInfo(BaseModel):
    id: str = Field(..., min_length=1)
    username: str = Field(..., min_length=1, max_length=30)
    connected_at: str
    color: str = Field(..., pattern=r'^#[0-9A-Fa-f]{6}$')
    message_count: int = Field(default=0, ge=0)

class WebSocketMessage(BaseModel):
    type: str = Field(..., min_length=1)
    message: Optional[str] = Field(None, max_length=500)
    room_id: Optional[str] = Field(None, max_length=10)
    data: Optional[dict] = None
    
    @validator('type')
    def validate_type(cls, v):
        allowed_types = ['chat_message', 'ping', 'pong', 'typing', 'join_room', 'leave_room', 'file_message']
        if v not in allowed_types:
            raise ValueError(f'Tipo de mensaje debe ser uno de: {allowed_types}')
        return v

class RoomMessage(BaseModel):
    type: str = "room_message"
    room_id: str = Field(..., min_length=1, max_length=10)
    message: str = Field(..., min_length=1, max_length=500)
    user_id: str
    username: str
    timestamp: str
    color: str
    
    @validator('message')
    def validate_message(cls, v):
        if not v.strip():
            raise ValueError('El mensaje no puede estar vacío')
        return v.strip()

class RoomInfo(BaseModel):
    room_id: str = Field(..., min_length=1, max_length=10)
    created_at: str
    user_count: int = Field(ge=0)
    users: List[dict] = []

class JoinRoomRequest(BaseModel):
    room_id: str = Field(..., min_length=1, max_length=10)
    
    @validator('room_id')
    def validate_room_id(cls, v):
        # Validar formato del ID de sala
        if not re.match(r'^[A-Z0-9]{6}$', v):
            raise ValueError('ID de sala debe tener 6 caracteres alfanuméricos en mayúsculas')
        return v

class AdminBroadcast(BaseModel):
    message: str = Field(..., min_length=1, max_length=200)
    
    @validator('message')
    def validate_admin_message(cls, v):
        # Sanitizar mensaje de admin
        clean_message = re.sub(r'[<>\"&]', '', v.strip())
        if not clean_message:
            raise ValueError('Mensaje de admin inválido')
        return clean_message

class ConnectionStats(BaseModel):
    active_connections: int = Field(..., ge=0)
    total_messages: int = Field(..., ge=0)
    banned_users: int = Field(..., ge=0)
    anonymous_counter: int = Field(..., ge=0)

class HealthResponse(BaseModel):
    status: str
    timestamp: str
    metrics: ConnectionStats
    limits: dict
