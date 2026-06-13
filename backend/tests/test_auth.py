from tests.conftest import auth_headers, signup


def test_signup_returns_tokens_and_first_user_is_admin(ctx):
    client, _ = ctx
    res = signup(client, email="first@example.com", name="첫유저")
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["accessToken"] and body["refreshToken"]
    assert body["user"]["role"] == "admin"  # first account bootstraps to admin
    assert body["user"]["isVerified"] is True


def test_second_user_is_plain_user(ctx):
    client, _ = ctx
    signup(client, email="first@example.com")
    res = signup(client, email="second@example.com")
    assert res.json()["user"]["role"] == "user"


def test_duplicate_email_conflicts(ctx):
    client, _ = ctx
    signup(client, email="dup@example.com")
    res = signup(client, email="dup@example.com")
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "email_taken"


def test_login_and_wrong_password(ctx):
    client, _ = ctx
    signup(client, email="u@example.com", password="password123")
    ok = client.post("/api/v1/auth/login", json={"email": "u@example.com", "password": "password123"})
    assert ok.status_code == 200 and ok.json()["accessToken"]

    bad = client.post("/api/v1/auth/login", json={"email": "u@example.com", "password": "nope"})
    assert bad.status_code == 401
    assert bad.json()["error"]["code"] == "invalid_credentials"


def test_refresh_issues_new_access_token(ctx):
    client, _ = ctx
    tokens = signup(client, email="r@example.com").json()
    res = client.post("/api/v1/auth/refresh", json={"refreshToken": tokens["refreshToken"]})
    assert res.status_code == 200 and res.json()["accessToken"]


def test_access_token_cannot_be_used_as_refresh(ctx):
    client, _ = ctx
    tokens = signup(client, email="x@example.com").json()
    res = client.post("/api/v1/auth/refresh", json={"refreshToken": tokens["accessToken"]})
    assert res.status_code == 401  # type claim mismatch


def test_me_requires_bearer(ctx):
    client, _ = ctx
    assert client.get("/api/v1/auth/me").status_code == 401
    headers = auth_headers(client, email="me@example.com")
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 200
