import json
import time
import pytest
from starlette.testclient import TestClient

from app.main import app
from app.services.room_manager import room_manager


def test_three_participants_lifecycle_and_disconnection():
    """Verify that when 3 participants join in sequence:
    1. Every participant receives the correct room participant count at connection time via room_welcome.
    2. All existing participants receive peer_joined with the updated count.
    3. When a participant disconnects, all remaining participants receive peer_left with updated count.
    4. When all participants leave, the room is completely purged from memory.
    """
    client = TestClient(app)
    room_id = "LIFECYCLE1"

    # Step 1: Participant 1 (Alice) connects
    with client.websocket_connect(f"/ws/{room_id}") as ws_alice:
        alice_welcome = json.loads(ws_alice.receive_text())
        assert alice_welcome["type"] == "room_welcome"
        assert alice_welcome["room_id"] == room_id
        assert alice_welcome["participant_count"] == 1
        alice_id = alice_welcome["peer_id"]

        assert room_manager.get_participant_count(room_id) == 1

        # Step 2: Participant 2 (Bob) connects
        with client.websocket_connect(f"/ws/{room_id}") as ws_bob:
            bob_welcome = json.loads(ws_bob.receive_text())
            assert bob_welcome["type"] == "room_welcome"
            assert bob_welcome["room_id"] == room_id
            assert bob_welcome["participant_count"] == 2
            bob_id = bob_welcome["peer_id"]

            # Alice must receive peer_joined notification with count 2
            alice_saw_bob_join = json.loads(ws_alice.receive_text())
            assert alice_saw_bob_join["type"] == "peer_joined"
            assert alice_saw_bob_join["peer_id"] == bob_id
            assert alice_saw_bob_join["participant_count"] == 2

            assert room_manager.get_participant_count(room_id) == 2

            # Step 3: Participant 3 (Charlie) connects
            with client.websocket_connect(f"/ws/{room_id}") as ws_charlie:
                charlie_welcome = json.loads(ws_charlie.receive_text())
                assert charlie_welcome["type"] == "room_welcome"
                assert charlie_welcome["room_id"] == room_id
                assert charlie_welcome["participant_count"] == 3
                charlie_id = charlie_welcome["peer_id"]

                # Alice receives peer_joined for Charlie with count 3
                alice_saw_charlie_join = json.loads(ws_alice.receive_text())
                assert alice_saw_charlie_join["type"] == "peer_joined"
                assert alice_saw_charlie_join["peer_id"] == charlie_id
                assert alice_saw_charlie_join["participant_count"] == 3

                # Bob receives peer_joined for Charlie with count 3
                bob_saw_charlie_join = json.loads(ws_bob.receive_text())
                assert bob_saw_charlie_join["type"] == "peer_joined"
                assert bob_saw_charlie_join["peer_id"] == charlie_id
                assert bob_saw_charlie_join["participant_count"] == 3

                assert room_manager.get_participant_count(room_id) == 3

                # Charlie disconnects (sends close frame)
                ws_charlie.close(1000)
                time.sleep(0.05)

            # Step 4: Both Alice and Bob must receive peer_left for Charlie with count 2
            alice_saw_charlie_leave = json.loads(ws_alice.receive_text())
            assert alice_saw_charlie_leave["type"] == "peer_left"
            assert alice_saw_charlie_leave["peer_id"] == charlie_id
            assert alice_saw_charlie_leave["participant_count"] == 2

            bob_saw_charlie_leave = json.loads(ws_bob.receive_text())
            assert bob_saw_charlie_leave["type"] == "peer_left"
            assert bob_saw_charlie_leave["peer_id"] == charlie_id
            assert bob_saw_charlie_leave["participant_count"] == 2

            assert room_manager.get_participant_count(room_id) == 2

            # Bob disconnects (sends close frame)
            ws_bob.close(1000)
            time.sleep(0.05)

        # Step 5: Alice must receive peer_left for Bob with count 1
        alice_saw_bob_leave = json.loads(ws_alice.receive_text())
        assert alice_saw_bob_leave["type"] == "peer_left"
        assert alice_saw_bob_leave["peer_id"] == bob_id
        assert alice_saw_bob_leave["participant_count"] == 1

        assert room_manager.get_participant_count(room_id) == 1

    # Step 6: Alice disconnects
    # The room has 0 participants and must be purged from memory immediately
    assert room_manager.has_room(room_id) is False
    assert room_id not in room_manager._rooms
