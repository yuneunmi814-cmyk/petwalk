"""Test harness: a temp **file** SQLite per test + per-request sessions.

Why a file, not in-memory: the async matcher opens its OWN session/connection
(like production). A file DB gives each connection real isolation and makes
cross-connection commits visible — the same guarantees Postgres would. The
matcher's step delay and the demo seed are turned off for deterministic, fast
runs; each test sets up exactly the data it needs.
"""

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core import database, ratelimit
from app.core.config import get_settings
from app.core.database import Base, get_db
from app.core.ratelimit import InMemoryRateLimiter
from app.main import app


@pytest.fixture()
def ctx(tmp_path):
    os.environ["PETWALK_MATCH_STEP_DELAY_S"] = "0"
    os.environ["PETWALK_SEED_ON_STARTUP"] = "0"
    get_settings.cache_clear()

    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}",
        connect_args={"check_same_thread": False},
        future=True,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    # The worker resolves the session factory through the module at call time.
    database.engine = engine
    database.SessionLocal = TestingSessionLocal

    def _override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    ratelimit.set_rate_limiter(InMemoryRateLimiter(per_min=1_000_000))

    with TestClient(app) as client:
        yield client, TestingSessionLocal

    app.dependency_overrides.clear()
    ratelimit.set_rate_limiter(None)
    Base.metadata.drop_all(bind=engine)
    for key in ("PETWALK_MATCH_STEP_DELAY_S", "PETWALK_SEED_ON_STARTUP"):
        os.environ.pop(key, None)
    get_settings.cache_clear()


# --- helpers ------------------------------------------------------------


def signup(client, email="a@example.com", password="password123", name="테스터", lat=None, lng=None):
    body = {"email": email, "password": password, "displayName": name}
    if lat is not None and lng is not None:
        body["lat"], body["lng"] = lat, lng
    return client.post("/api/v1/auth/signup", json=body)


def auth_headers(client, **kwargs):
    res = signup(client, **kwargs)
    assert res.status_code == 201, res.text
    return {"Authorization": f"Bearer {res.json()['accessToken']}"}


def make_dog(client, headers, name="몽이", breed="믹스", size="medium", temperament="playful"):
    res = client.post(
        "/api/v1/dogs",
        headers=headers,
        json={"name": name, "breed": breed, "size": size, "temperament": temperament},
    )
    assert res.status_code == 201, res.text
    return res.json()
