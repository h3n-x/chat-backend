import json
import logging
import secrets
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from pydantic import ValidationError, TypeAdapter

from app.config import (
    RATE_LIMIT_WS_CONNECTIONS_PER_IP,
    RATE_LIMIT_WS_MESSAGES_PER_MINUTE,
    WS_MAX_MESSAGE_SIZE,
)
from app.models.ws_messages import (
    InboundWSMessage,
    WSInboundE2EEMessage,
    WSInboundKeyDelivery,
    WSInboundKeyRequest,
    WSInboundPing,
    WSInboundTyping,
    WSOutboundE2EEMessage,
    WSOutboundError,
    WSOutboundKeyDelivery,
    WSOutboundKeyRequest,
    WSOutboundPong,
    WSOutboundTyping,
)
from app.routers.rooms import ROOM_ID_REGEX
from app.security.rate_limiter import get_client_ip, rate_limiter
from app.services.room_manager import room_manager

logger = logging.getLogger("chat.websocket")
router = APIRouter(tags=["WebSocket"])

# Type adapter for inbound discriminated union
inbound_adapter = TypeAdapter(InboundWSMessage)


@router.websocket("/ws/{room_id}")
async def websocket_relay_endpoint(websocket: WebSocket, room_id: str):
    """Zero-Knowledge WebSocket Blind Relay.
    
    Relays opaque encrypted envelopes and X25519 handshake frames without
    inspecting or storing any keys, ciphertexts, or message contents.
    """
    client_ip = get_client_ip(websocket)

    # 1. Validate room_id format
    if not ROOM_ID_REGEX.match(room_id):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid room ID format")
        return

    # 2. Check active connection rate limits per IP
    if not rate_limiter.acquire_connection(client_ip, RATE_LIMIT_WS_CONNECTIONS_PER_IP):
        logger.warning(f"Connection rejected for {client_ip}: max connections reached.")
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Maximum concurrent connections per IP reached",
        )
        return

    await websocket.accept()
    client_id = secrets.token_hex(4)

    # 3. Register with room manager
    connected = await room_manager.connect(room_id, client_id, websocket)
    if not connected:
        rate_limiter.release_connection(client_ip)
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Room reached maximum participant capacity",
        )
        return

    try:
        while True:
            raw_text = await websocket.receive_text()

            # 4. Check message rate limit
            if not rate_limiter.is_allowed(client_ip, "ws_msg", RATE_LIMIT_WS_MESSAGES_PER_MINUTE):
                err = WSOutboundError(
                    code="RATE_LIMIT_EXCEEDED",
                    message="Message rate limit exceeded. Please slow down.",
                ).model_dump_json()
                await websocket.send_text(err)
                continue

            # 5. Check frame size cutoff (64 KB)
            if len(raw_text.encode("utf-8")) > WS_MAX_MESSAGE_SIZE:
                err = WSOutboundError(
                    code="FRAME_TOO_LARGE",
                    message=f"Frame exceeds maximum limit of {WS_MAX_MESSAGE_SIZE} bytes",
                ).model_dump_json()
                await websocket.send_text(err)
                continue

            # 6. Parse JSON and validate frame schema
            try:
                msg_data = json.loads(raw_text)
                parsed_msg = inbound_adapter.validate_python(msg_data)
            except (json.JSONDecodeError, ValidationError) as e:
                err = WSOutboundError(
                    code="INVALID_FRAME",
                    message="Invalid frame structure or missing required fields",
                ).model_dump_json()
                await websocket.send_text(err)
                continue

            # 7. Route according to frame type
            if isinstance(parsed_msg, WSInboundPing):
                await websocket.send_text(WSOutboundPong().model_dump_json())

            elif isinstance(parsed_msg, WSInboundTyping):
                if parsed_msg.room_id != room_id:
                    continue
                outbound = WSOutboundTyping(
                    room_id=room_id,
                    sender_id=client_id,
                    is_typing=parsed_msg.is_typing,
                ).model_dump_json()
                await room_manager.broadcast_to_room(room_id, outbound, exclude_client_id=client_id)

            elif isinstance(parsed_msg, WSInboundE2EEMessage):
                if parsed_msg.room_id != room_id:
                    continue  # Discard mismatched room frames
                outbound = WSOutboundE2EEMessage(
                    room_id=room_id,
                    sender_id=client_id,
                    payload=parsed_msg.payload,
                ).model_dump_json()
                await room_manager.broadcast_to_room(room_id, outbound, exclude_client_id=client_id)

            elif isinstance(parsed_msg, WSInboundKeyRequest):
                if parsed_msg.room_id != room_id:
                    continue
                outbound = WSOutboundKeyRequest(
                    room_id=room_id,
                    sender_id=client_id,
                    pk=parsed_msg.pk,
                ).model_dump_json()
                await room_manager.broadcast_to_room(room_id, outbound, exclude_client_id=client_id)

            elif isinstance(parsed_msg, WSInboundKeyDelivery):
                if parsed_msg.room_id != room_id:
                    continue
                outbound = WSOutboundKeyDelivery(
                    room_id=room_id,
                    sender_id=client_id,
                    target_id=parsed_msg.target_id,
                    pk=parsed_msg.pk,
                    wrapped_key=parsed_msg.wrapped_key,
                    iv=parsed_msg.iv,
                ).model_dump_json()

                if parsed_msg.target_id:
                    await room_manager.send_to_client(room_id, parsed_msg.target_id, outbound)
                else:
                    await room_manager.broadcast_to_room(
                        room_id, outbound, exclude_client_id=client_id
                    )

    except WebSocketDisconnect:
        logger.info(f"WebSocket client {client_id} disconnected from room {room_id}")
    except Exception as e:
        logger.error(f"Unexpected error in WebSocket loop for {client_id}: {e}")
    finally:
        rate_limiter.release_connection(client_ip)
        await room_manager.disconnect(room_id, client_id)
