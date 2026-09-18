import re
from starlette.testclient import TestClient
from app.routers.rooms import ROOM_ID_CHARS


def test_create_room_endpoint(client: TestClient):
    response = client.post("/api/rooms/create")
    assert response.status_code == 200
    data = response.json()
    assert "room_id" in data
    assert len(data["room_id"]) == 6
    assert all(c in ROOM_ID_CHARS for c in data["room_id"])
    assert data["ttl_seconds"] == 86400
    assert "created_at" in data


def test_room_status_endpoint(client: TestClient):
    # Empty / nonexistent room
    res = client.get("/api/rooms/ROOM99/status")
    assert res.status_code == 200
    assert res.json()["is_active"] is False
    assert res.json()["participant_count"] == 0

    # Invalid room format
    res_bad = client.get("/api/rooms/!invalid!/status")
    assert res_bad.status_code == 400


def test_create_room_rate_limit(client: TestClient):
    # Send requests until rate limit is triggered
    for _ in range(10):
        res = client.post("/api/rooms/create")
        assert res.status_code == 200

    # 11th request should be rate-limited (HTTP 429)
    res_limited = client.post("/api/rooms/create")
    assert res_limited.status_code == 429
