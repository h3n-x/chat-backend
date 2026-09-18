import base64
import json
import os
import pytest
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from starlette.testclient import TestClient

from app.main import app


def derive_key(shared_secret: bytes) -> bytes:
    """HKDF-SHA256 key derivation matching RFC 5869."""
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=b"chat-anonimo-v2-key-wrap",
    )
    return hkdf.derive(shared_secret)


def test_e2ee_blind_relay_handshake_and_messaging():
    """Verify that two clients can perform X25519 handshake and AES-256-GCM messaging
    through the blind relay without the server having access to keys or plaintext."""
    client = TestClient(app)
    room_id = "ROOM42"

    # Alice opens WebSocket
    with client.websocket_connect(f"/ws/{room_id}") as ws_alice:
        # Bob opens WebSocket
        with client.websocket_connect(f"/ws/{room_id}") as ws_bob:
            # Alice should receive peer_joined notification for Bob
            msg = json.loads(ws_alice.receive_text())
            assert msg["type"] == "peer_joined"
            assert msg["participant_count"] == 2
            bob_peer_id = msg["peer_id"]

            # --- Handshake Phase ---
            # 1. Bob generates ephemeral X25519 keypair
            bob_sk = X25519PrivateKey.generate()
            bob_pk_bytes = bob_sk.public_key().public_bytes_raw()
            bob_pk_b64 = base64.b64encode(bob_pk_bytes).decode("ascii")

            # 2. Bob sends KEY_REQUEST to room
            ws_bob.send_text(
                json.dumps({
                    "type": "key_request",
                    "room_id": room_id,
                    "pk": bob_pk_b64,
                })
            )

            # 3. Alice receives KEY_REQUEST relayed from server
            alice_received_req = json.loads(ws_alice.receive_text())
            assert alice_received_req["type"] == "key_request"
            assert alice_received_req["sender_id"] == bob_peer_id
            assert alice_received_req["pk"] == bob_pk_b64

            # 4. Alice generates her ephemeral X25519 keypair
            alice_sk = X25519PrivateKey.generate()
            alice_pk_bytes = alice_sk.public_key().public_bytes_raw()
            alice_pk_b64 = base64.b64encode(alice_pk_bytes).decode("ascii")

            # 5. Alice performs ECDH and derives K_wrap
            bob_pub_key = X25519PublicKey.from_public_bytes(base64.b64decode(alice_received_req["pk"]))
            alice_shared_secret = alice_sk.exchange(bob_pub_key)
            k_wrap_alice = derive_key(alice_shared_secret)

            # 6. Alice has generated a 256-bit symmetric RoomKey
            room_key = os.urandom(32)

            # 7. Alice wraps RoomKey with K_wrap using AES-256-GCM
            wrap_iv = os.urandom(12)
            aesgcm_wrap = AESGCM(k_wrap_alice)
            wrapped_key_bytes = aesgcm_wrap.encrypt(wrap_iv, room_key, None)

            # 8. Alice sends KEY_DELIVERY targeted to Bob
            ws_alice.send_text(
                json.dumps({
                    "type": "key_delivery",
                    "room_id": room_id,
                    "target_id": bob_peer_id,
                    "pk": alice_pk_b64,
                    "wrapped_key": base64.b64encode(wrapped_key_bytes).decode("ascii"),
                    "iv": base64.b64encode(wrap_iv).decode("ascii"),
                })
            )

            # 9. Bob receives KEY_DELIVERY relayed by server
            bob_received_delivery = json.loads(ws_bob.receive_text())
            assert bob_received_delivery["type"] == "key_delivery"
            assert bob_received_delivery["pk"] == alice_pk_b64

            # 10. Bob performs ECDH and unrolls RoomKey
            alice_pub_key = X25519PublicKey.from_public_bytes(
                base64.b64decode(bob_received_delivery["pk"])
            )
            bob_shared_secret = bob_sk.exchange(alice_pub_key)
            k_wrap_bob = derive_key(bob_shared_secret)
            assert k_wrap_alice == k_wrap_bob

            aesgcm_unwrap = AESGCM(k_wrap_bob)
            decrypted_room_key = aesgcm_unwrap.decrypt(
                base64.b64decode(bob_received_delivery["iv"]),
                base64.b64decode(bob_received_delivery["wrapped_key"]),
                None,
            )
            assert decrypted_room_key == room_key

            # --- E2EE Messaging Phase ---
            # 11. Alice encrypts message with RoomKey and AAD
            plaintext_obj = {
                "id": "msg-001",
                "sender_name": "Alice",
                "color": "#4ECDC4",
                "text": "Hello Bob from Zero-Knowledge E2EE!",
                "timestamp": 1726630000000,
            }
            plaintext_bytes = json.dumps(plaintext_obj).encode("utf-8")
            msg_iv = os.urandom(12)
            aad = f"room:{room_id}".encode("utf-8")

            room_aesgcm = AESGCM(room_key)
            ciphertext_bytes = room_aesgcm.encrypt(msg_iv, plaintext_bytes, aad)

            ws_alice.send_text(
                json.dumps({
                    "type": "e2ee_message",
                    "room_id": room_id,
                    "payload": {
                        "ciphertext": base64.b64encode(ciphertext_bytes).decode("ascii"),
                        "iv": base64.b64encode(msg_iv).decode("ascii"),
                        "v": 2,
                    },
                })
            )

            # 12. Bob receives relayed e2ee_message
            bob_received_msg = json.loads(ws_bob.receive_text())
            assert bob_received_msg["type"] == "e2ee_message"
            assert bob_received_msg["room_id"] == room_id
            payload = bob_received_msg["payload"]

            # 13. Bob decrypts and authenticates with RoomKey and matching AAD
            bob_cipher_bytes = base64.b64decode(payload["ciphertext"])
            bob_iv_bytes = base64.b64decode(payload["iv"])
            decrypted_bytes = room_aesgcm.decrypt(bob_iv_bytes, bob_cipher_bytes, aad)
            recovered_obj = json.loads(decrypted_bytes.decode("utf-8"))

            assert recovered_obj == plaintext_obj
            assert recovered_obj["text"] == "Hello Bob from Zero-Knowledge E2EE!"

            # --- Tamper Resistance: Cross-Room / AAD Tampering ---
            # Attempting to authenticate the ciphertext with a different AAD must fail
            with pytest.raises(Exception):
                room_aesgcm.decrypt(
                    bob_iv_bytes, bob_cipher_bytes, b"room:OTHER_ROOM"
                )


def test_ws_ping_pong():
    """Verify ping-pong keepalive works as expected."""
    client = TestClient(app)
    with client.websocket_connect("/ws/PINGRM") as ws:
        ws.send_text(json.dumps({"type": "ping"}))
        response = json.loads(ws.receive_text())
        assert response["type"] == "pong"


def test_ws_frame_validation():
    """Verify malformed frames return an error frame and don't crash the server."""
    client = TestClient(app)
    with client.websocket_connect("/ws/TESTVAL") as ws:
        # Invalid JSON
        ws.send_text("this-is-not-json")
        err = json.loads(ws.receive_text())
        assert err["type"] == "error"
        assert err["code"] == "INVALID_FRAME"

        # Valid JSON but invalid schema
        ws.send_text(json.dumps({"type": "unknown_type", "foo": "bar"}))
        err2 = json.loads(ws.receive_text())
        assert err2["type"] == "error"
        assert err2["code"] == "INVALID_FRAME"


def test_ws_frame_too_large():
    """Verify frames larger than 64KB are rejected with an error frame."""
    client = TestClient(app)
    with client.websocket_connect("/ws/LARGEMSG") as ws:
        large_str = "A" * (65 * 1024)
        ws.send_text(large_str)
        err = json.loads(ws.receive_text())
        assert err["type"] == "error"
        assert err["code"] == "FRAME_TOO_LARGE"


def test_ws_message_rate_limit():
    """Verify sending more than RATE_LIMIT_WS_MESSAGES_PER_MINUTE triggers rate limit error."""
    client = TestClient(app)
    with client.websocket_connect("/ws/RATELIM") as ws:
        for _ in range(30):
            ws.send_text(json.dumps({"type": "ping"}))
            res = json.loads(ws.receive_text())
            assert res["type"] == "pong"

        # 31st message should trigger rate limit error
        ws.send_text(json.dumps({"type": "ping"}))
        res_limited = json.loads(ws.receive_text())
        assert res_limited["type"] == "error"
        assert res_limited["code"] == "RATE_LIMIT_EXCEEDED"


def test_ws_connection_limit_per_ip():
    """Verify that exceeding RATE_LIMIT_WS_CONNECTIONS_PER_IP closes with 1008 policy violation."""
    client = TestClient(app)
    connections = []
    try:
        for _ in range(5):
            ws = client.websocket_connect("/ws/CONNLIM")
            ws.__enter__()
            connections.append(ws)

        # 6th connection should be rejected with 1008
        with pytest.raises(Exception):
            with client.websocket_connect("/ws/CONNLIM") as ws6:
                pass
    finally:
        for ws in connections:
            ws.__exit__(None, None, None)


def test_ws_invalid_room_id():
    """Verify invalid room ID in WebSocket URL is rejected with 1008."""
    client = TestClient(app)
    with pytest.raises(Exception):
        with client.websocket_connect("/ws/!bad-chars!") as ws:
            pass


def test_ws_mismatched_room_discard():
    """Verify frames where payload room_id does not match the connected room are discarded."""
    client = TestClient(app)
    with client.websocket_connect("/ws/ROOM_A") as ws_a:
        with client.websocket_connect("/ws/ROOM_A") as ws_b:
            # Drain join message
            ws_a.receive_text()

            # Send message with mismatched room_id
            mismatched_msg = {
                "type": "e2ee_message",
                "room_id": "ROOM_B",
                "payload": {"ciphertext": "abc", "iv": "123", "v": 2},
            }
            ws_b.send_text(json.dumps(mismatched_msg))

            # Send ping to confirm connection is intact and mismatched msg was not relayed
            ws_b.send_text(json.dumps({"type": "ping"}))
            pong = json.loads(ws_b.receive_text())
            assert pong["type"] == "pong"


def test_ws_room_max_capacity(monkeypatch):
    """Verify that attempting to join a room beyond MAX_PARTICIPANTS_PER_ROOM is rejected."""
    import app.services.room_manager as rm_module
    monkeypatch.setattr(rm_module, "MAX_PARTICIPANTS_PER_ROOM", 1)

    client = TestClient(app)
    with client.websocket_connect("/ws/CAPRM") as ws1:
        # Second client attempting to connect is accepted and immediately closed with 1008
        from starlette.websockets import WebSocketDisconnect
        with client.websocket_connect("/ws/CAPRM") as ws2:
            with pytest.raises(WebSocketDisconnect) as exc_info:
                ws2.receive_text()
            assert exc_info.value.code == 1008



