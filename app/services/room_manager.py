import logging
from typing import Dict, Optional, Set
from starlette.websockets import WebSocket, WebSocketState
from app.config import MAX_PARTICIPANTS_PER_ROOM
from app.models.ws_messages import (
    WSOutboundPeerJoined,
    WSOutboundPeerLeft,
    WSOutboundRoomWelcome,
)

logger = logging.getLogger("chat.room_manager")


class RoomManager:
    """Zero-Knowledge Blind Relay Room Manager.
    
    Routes opaque encrypted frames between peers without inspecting,
    storing, or persisting message content or keys.
    """

    def __init__(self):
        # Maps room_id -> {client_id: WebSocket}
        self._rooms: Dict[str, Dict[str, WebSocket]] = {}

    def get_active_room_count(self) -> int:
        return len(self._rooms)

    def get_participant_count(self, room_id: str) -> int:
        return len(self._rooms.get(room_id, {}))

    def has_room(self, room_id: str) -> bool:
        return room_id in self._rooms and len(self._rooms[room_id]) > 0

    async def connect(self, room_id: str, client_id: str, websocket: WebSocket) -> bool:
        """Register a client websocket in a room."""
        if room_id not in self._rooms:
            self._rooms[room_id] = {}

        if len(self._rooms[room_id]) >= MAX_PARTICIPANTS_PER_ROOM:
            logger.warning(f"Room {room_id} reached capacity ({MAX_PARTICIPANTS_PER_ROOM}). Rejecting {client_id}.")
            return False

        self._rooms[room_id][client_id] = websocket
        participant_count = len(self._rooms[room_id])
        logger.info(f"Client {client_id} connected to room {room_id}. Total: {participant_count}")

        # 1. Send welcome status frame directly to the connecting client with current room state
        welcome_msg = WSOutboundRoomWelcome(
            room_id=room_id,
            peer_id=client_id,
            participant_count=participant_count,
        ).model_dump_json()
        await websocket.send_text(welcome_msg)

        # 2. Notify peers about new participant
        join_msg = WSOutboundPeerJoined(
            room_id=room_id,
            peer_id=client_id,
            participant_count=participant_count,
        ).model_dump_json()

        await self.broadcast_to_room(room_id, join_msg, exclude_client_id=client_id)
        return True

    async def disconnect(self, room_id: str, client_id: str) -> None:
        """Remove a client from a room and clean up empty rooms."""
        if room_id not in self._rooms:
            return

        if client_id in self._rooms[room_id]:
            del self._rooms[room_id][client_id]
            participant_count = len(self._rooms[room_id])
            logger.info(f"Client {client_id} left room {room_id}. Remaining: {participant_count}")

            if participant_count == 0:
                # Zero-persistence: purge empty room completely from memory
                del self._rooms[room_id]
                logger.info(f"Room {room_id} has no participants and was purged from memory.")
            else:
                # Notify remaining peers
                leave_msg = WSOutboundPeerLeft(
                    room_id=room_id,
                    peer_id=client_id,
                    participant_count=participant_count,
                ).model_dump_json()
                await self.broadcast_to_room(room_id, leave_msg)

    async def broadcast_to_room(
        self,
        room_id: str,
        message_json: str,
        exclude_client_id: Optional[str] = None,
    ) -> int:
        """Blindly relay an opaque frame to all participants in a room."""
        if room_id not in self._rooms:
            return 0

        dead_clients: Set[str] = set()
        delivered_count = 0

        for cid, ws in list(self._rooms[room_id].items()):
            if exclude_client_id and cid == exclude_client_id:
                continue

            try:
                if ws.client_state == WebSocketState.CONNECTED:
                    await ws.send_text(message_json)
                    delivered_count += 1
                else:
                    dead_clients.add(cid)
            except Exception as e:
                logger.debug(f"Failed to relay frame to client {cid}: {e}")
                dead_clients.add(cid)

        # Clean up any stale sockets encountered during broadcast
        for cid in dead_clients:
            await self.disconnect(room_id, cid)

        return delivered_count

    async def send_to_client(
        self,
        room_id: str,
        target_client_id: str,
        message_json: str,
    ) -> bool:
        """Directly relay an opaque frame to a specific client in the room."""
        if room_id not in self._rooms:
            return False

        ws = self._rooms[room_id].get(target_client_id)
        if not ws:
            return False

        try:
            if ws.client_state == WebSocketState.CONNECTED:
                await ws.send_text(message_json)
                return True
            else:
                await self.disconnect(room_id, target_client_id)
                return False
        except Exception as e:
            logger.debug(f"Failed to direct-relay frame to {target_client_id}: {e}")
            await self.disconnect(room_id, target_client_id)
            return False


# Global singleton instance
room_manager = RoomManager()
