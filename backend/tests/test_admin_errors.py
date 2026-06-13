"""Admin authorization + the unified error contract."""

from tests.conftest import auth_headers


def test_admin_metrics_for_admin_only(ctx):
    client, _ = ctx
    admin = auth_headers(client, email="admin@example.com")  # first -> admin
    plain = auth_headers(client, email="plain@example.com")  # second -> user

    ok = client.get("/api/v1/admin/metrics", headers=admin)
    assert ok.status_code == 200
    body = ok.json()
    for key in ("totalUsers", "totalRequests", "matchSuccessRate", "openReports", "noShowRate"):
        assert key in body

    forbidden = client.get("/api/v1/admin/metrics", headers=plain)
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "forbidden"


def test_unknown_route_uses_error_contract(ctx):
    client, _ = ctx
    res = client.get("/api/v1/nope")
    assert res.status_code == 404
    assert set(res.json()["error"].keys()) == {"code", "message"}


def test_unauthorized_uses_error_contract(ctx):
    client, _ = ctx
    res = client.get("/api/v1/dogs")
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "unauthorized"


def test_health(ctx):
    client, _ = ctx
    assert client.get("/health").json() == {"status": "ok"}
