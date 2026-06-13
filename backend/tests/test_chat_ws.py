"""Real-time chat over WebSocket: roundtrip + authorization."""

import pytest
from starlette.websockets import WebSocketDisconnect

from app.services import seed
from tests.conftest import make_dog, signup


def _confirmed_match(client, SessionLocal) -> tuple[str, int]:
    """Set up a confirmed match and return (requester_token, match_id)."""
    db = SessionLocal()
    try:
        seed.seed_all(db)
    finally:
        db.close()

    token = signup(client, email="host@example.com", lat=seed.BASE_LAT, lng=seed.BASE_LNG).json()[
        "accessToken"
    ]
    h = {"Authorization": f"Bearer {token}"}
    dog = make_dog(client, h)
    job = client.post(
        "/api/v1/walk-requests",
        headers=h,
        json={"dogId": dog["id"], "timeSlot": "2026-06-14T18:00:00+09:00", "radiusKm": 2},
    ).json()
    match_id = client.get(job["statusUrl"], headers=h).json()["matches"][0]["matchId"]
    places = client.get("/api/v1/meeting-places", headers=h).json()
    client.post(
        f"/api/v1/matches/{match_id}/accept", headers=h, json={"meetingPlaceId": places[0]["id"]}
    )
    return token, match_id


def test_ws_chat_roundtrip_and_persist(ctx):
    client, SessionLocal = ctx
    token, match_id = _confirmed_match(client, SessionLocal)

    with client.websocket_connect(f"/api/v1/matches/{match_id}/ws?token={token}") as ws:
        ws.send_json({"body": "실시간 안녕!"})
        echo = ws.receive_json()
        assert echo["body"] == "실시간 안녕!"
        assert echo["matchId"] == match_id

    # Delivered over WS AND persisted — REST history shows it.
    h = {"Authorization": f"Bearer {token}"}
    history = client.get(f"/api/v1/matches/{match_id}/messages", headers=h).json()
    assert any(m["body"] == "실시간 안녕!" for m in history)


def test_ws_rejects_without_token(ctx):
    client, SessionLocal = ctx
    _, match_id = _confirmed_match(client, SessionLocal)
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/api/v1/matches/{match_id}/ws") as ws:
            ws.receive_json()


def test_ws_rejects_non_participant(ctx):
    client, SessionLocal = ctx
    _, match_id = _confirmed_match(client, SessionLocal)
    stranger = signup(client, email="stranger@example.com").json()["accessToken"]
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/api/v1/matches/{match_id}/ws?token={stranger}") as ws:
            ws.receive_json()
