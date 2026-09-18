from typing import Annotated, Literal, Optional, Union
from pydantic import BaseModel, Field, constr


class EncryptedPayload(BaseModel):
    """Encrypted envelope. The server NEVER decrypts or inspects this."""
    ciphertext: str = Field(..., description="Base64-encoded AES-256-GCM ciphertext + tag")
    iv: str = Field(..., description="Base64-encoded 12-byte initialization vector")
    v: int = Field(default=2, description="Protocol version number")


# --- Inbound Messages (Client -> Server) ---

class WSInboundE2EEMessage(BaseModel):
    type: Literal["e2ee_message"]
    room_id: str = Field(..., min_length=4, max_length=16)
    payload: EncryptedPayload


class WSInboundKeyRequest(BaseModel):
    type: Literal["key_request"]
    room_id: str = Field(..., min_length=4, max_length=16)
    pk: str = Field(..., description="Base64-encoded ephemeral X25519 public key")


class WSInboundKeyDelivery(BaseModel):
    type: Literal["key_delivery"]
    room_id: str = Field(..., min_length=4, max_length=16)
    target_id: Optional[str] = Field(None, description="Optional recipient peer ID")
    pk: str = Field(..., description="Base64-encoded ephemeral X25519 public key of sender")
    wrapped_key: str = Field(..., description="Base64-encoded AES-GCM wrapped room key")
    iv: str = Field(..., description="Base64-encoded 12-byte IV for key wrap")


class WSInboundPing(BaseModel):
    type: Literal["ping"]


class WSInboundTyping(BaseModel):
    type: Literal["typing"]
    room_id: str = Field(..., min_length=4, max_length=16)
    is_typing: bool = True


InboundWSMessage = Annotated[
    Union[WSInboundE2EEMessage, WSInboundKeyRequest, WSInboundKeyDelivery, WSInboundPing, WSInboundTyping],
    Field(discriminator="type"),
]


# --- Outbound Messages (Server -> Client) ---

class WSOutboundE2EEMessage(BaseModel):
    type: Literal["e2ee_message"] = "e2ee_message"
    room_id: str
    sender_id: str
    payload: EncryptedPayload


class WSOutboundKeyRequest(BaseModel):
    type: Literal["key_request"] = "key_request"
    room_id: str
    sender_id: str
    pk: str


class WSOutboundKeyDelivery(BaseModel):
    type: Literal["key_delivery"] = "key_delivery"
    room_id: str
    sender_id: str
    target_id: Optional[str] = None
    pk: str
    wrapped_key: str
    iv: str


class WSOutboundRoomWelcome(BaseModel):
    type: Literal["room_welcome"] = "room_welcome"
    room_id: str
    peer_id: str
    participant_count: int


class WSOutboundPeerJoined(BaseModel):
    type: Literal["peer_joined"] = "peer_joined"
    room_id: str
    peer_id: str
    participant_count: int


class WSOutboundPeerLeft(BaseModel):
    type: Literal["peer_left"] = "peer_left"
    room_id: str
    peer_id: str
    participant_count: int


class WSOutboundTyping(BaseModel):
    type: Literal["typing"] = "typing"
    room_id: str
    sender_id: str
    is_typing: bool = True


class WSOutboundPong(BaseModel):
    type: Literal["pong"] = "pong"


class WSOutboundError(BaseModel):
    type: Literal["error"] = "error"
    code: str
    message: str
