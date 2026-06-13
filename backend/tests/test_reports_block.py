"""A single report blocks the pair both ways and removes them from each other's
search (design §1.5: 신고 1회로 즉시 차단, 동일인 재요청 차단)."""

from tests.conftest import auth_headers, make_dog


def _user_ids_in_mates(client, headers):
    return {m["userId"] for m in client.get("/api/v1/mates", headers=headers).json()["items"]}


def test_report_blocks_both_directions(ctx):
    client, _ = ctx
    a = auth_headers(client, email="a@example.com", name="A", lat=37.5172, lng=127.0473)
    b = auth_headers(client, email="b@example.com", name="B", lat=37.5174, lng=127.0475)
    make_dog(client, a)
    make_dog(client, b)

    a_id = client.get("/api/v1/auth/me", headers=a).json()["id"]
    b_id = client.get("/api/v1/auth/me", headers=b).json()["id"]

    # Before: each can see the other.
    assert b_id in _user_ids_in_mates(client, a)
    assert a_id in _user_ids_in_mates(client, b)

    res = client.post("/api/v1/reports", headers=a, json={"targetUserId": b_id, "reason": "노쇼"})
    assert res.status_code == 201
    assert res.json()["status"] == "queued"

    # After: symmetric block — neither sees the other.
    assert b_id not in _user_ids_in_mates(client, a)
    assert a_id not in _user_ids_in_mates(client, b)


def test_cannot_report_self(ctx):
    client, _ = ctx
    a = auth_headers(client, email="self@example.com", lat=37.5172, lng=127.0473)
    a_id = client.get("/api/v1/auth/me", headers=a).json()["id"]
    res = client.post("/api/v1/reports", headers=a, json={"targetUserId": a_id, "reason": "x"})
    assert res.status_code == 400
