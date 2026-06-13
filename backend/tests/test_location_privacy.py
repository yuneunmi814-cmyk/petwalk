"""The signature guarantee (design §1.5): exact coordinates never cross the wire.
Clients only ever see a coarse grid cell + its centre."""

from app.services import seed
from tests.conftest import auth_headers, make_dog

EXACT_LAT = 37.51720
EXACT_LNG = 127.04730


def test_me_never_returns_exact_coordinates(ctx):
    client, _ = ctx
    headers = auth_headers(client, email="priv@example.com", lat=EXACT_LAT, lng=EXACT_LNG)
    res = client.get("/api/v1/auth/me", headers=headers)
    body = res.json()
    text = res.text

    assert body["gridCell"] is not None
    assert body["gridCenter"] is not None  # coarse centre is OK to expose
    # No exact-coordinate keys or values anywhere in the payload.
    assert "homeLat" not in text and "home_lat" not in text
    assert str(EXACT_LAT) not in text and str(EXACT_LNG) not in text


def test_mate_search_exposes_only_grid_center(ctx):
    client, SessionLocal = ctx
    db = SessionLocal()
    try:
        seed.seed_all(db)
    finally:
        db.close()

    headers = auth_headers(client, email="searcher@example.com", lat=seed.BASE_LAT, lng=seed.BASE_LNG)
    make_dog(client, headers)
    res = client.get("/api/v1/mates", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total"] > 0
    for mate in data["items"]:
        assert "gridCenter" in mate and len(mate["gridCenter"]) == 2
        assert mate["approxDistanceM"] >= 0
        # exact owner coordinate fields must not be present
        assert "homeLat" not in mate and "lat" not in mate
