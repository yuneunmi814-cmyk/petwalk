"""End-to-end async pipeline: request -> background match -> accept -> chat -> review."""

from app.services import seed
from tests.conftest import auth_headers, make_dog


def _seed_pool(SessionLocal):
    db = SessionLocal()
    try:
        seed.seed_all(db)
    finally:
        db.close()


def test_full_walk_flow(ctx):
    client, SessionLocal = ctx
    _seed_pool(SessionLocal)  # nearby owners + public meeting places

    headers = auth_headers(
        client, email="me@example.com", name="나", lat=seed.BASE_LAT, lng=seed.BASE_LNG
    )
    dog = make_dog(client, headers, name="몽이", size="medium", temperament="playful")

    # 1) async request -> 202 + jobId
    res = client.post(
        "/api/v1/walk-requests",
        headers=headers,
        json={"dogId": dog["id"], "timeSlot": "2026-06-14T18:00:00+09:00", "radiusKm": 2},
    )
    assert res.status_code == 202, res.text
    job = res.json()
    assert job["jobId"] and job["statusUrl"]

    # 2) poll -> success with ranked matches
    status = client.get(job["statusUrl"], headers=headers).json()
    assert status["status"] == "success"
    assert status["progress"] == 100
    matches = status["matches"]
    assert len(matches) > 0
    scores = [m["score"] for m in matches]
    assert scores == sorted(scores, reverse=True)  # ranked best-first
    assert all(m["approxDistanceM"] > 0 for m in matches)

    # 3) accept the top candidate at a public place -> confirmed
    top = matches[0]
    places = client.get("/api/v1/meeting-places", headers=headers).json()
    assert places, "seed should provide public meeting places"
    acc = client.post(
        f"/api/v1/matches/{top['matchId']}/accept",
        headers=headers,
        json={"meetingPlaceId": places[0]["id"]},
    )
    assert acc.status_code == 200, acc.text
    assert acc.json()["state"] == "confirmed"
    assert acc.json()["meetingPlace"]["id"] == places[0]["id"]

    # other suggestions for the request are now declined
    after = client.get(job["statusUrl"], headers=headers).json()
    confirmed = [m for m in after["matches"] if m["state"] == "confirmed"]
    assert len(confirmed) == 1

    # 4) confirmed match shows up in /matches
    mine = client.get("/api/v1/matches", headers=headers).json()
    assert any(m["matchId"] == top["matchId"] for m in mine)

    # 5) chat opens after confirmation
    msg = client.post(
        f"/api/v1/matches/{top['matchId']}/messages", headers=headers, json={"body": "안녕하세요!"}
    )
    assert msg.status_code == 201
    assert len(client.get(f"/api/v1/matches/{top['matchId']}/messages", headers=headers).json()) == 1

    # 6) review once; duplicate is rejected
    rv = client.post(
        "/api/v1/reviews",
        headers=headers,
        json={"matchId": top["matchId"], "score": 5, "comment": "좋았어요"},
    )
    assert rv.status_code == 201
    dup = client.post(
        "/api/v1/reviews", headers=headers, json={"matchId": top["matchId"], "score": 4}
    )
    assert dup.status_code == 409


def test_request_requires_location(ctx):
    client, _ = ctx
    headers = auth_headers(client, email="noloc@example.com")  # no lat/lng
    dog = make_dog(client, headers)
    res = client.post(
        "/api/v1/walk-requests",
        headers=headers,
        json={"dogId": dog["id"], "timeSlot": "2026-06-14T18:00:00+09:00", "radiusKm": 2},
    )
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "location_required"


def test_chat_blocked_before_confirmation(ctx):
    client, SessionLocal = ctx
    _seed_pool(SessionLocal)
    headers = auth_headers(client, email="me2@example.com", lat=seed.BASE_LAT, lng=seed.BASE_LNG)
    dog = make_dog(client, headers)
    job = client.post(
        "/api/v1/walk-requests",
        headers=headers,
        json={"dogId": dog["id"], "timeSlot": "2026-06-14T18:00:00+09:00", "radiusKm": 2},
    ).json()
    match = client.get(job["statusUrl"], headers=headers).json()["matches"][0]
    # not yet accepted -> chat is 409
    res = client.post(
        f"/api/v1/matches/{match['matchId']}/messages", headers=headers, json={"body": "hi"}
    )
    assert res.status_code == 409
