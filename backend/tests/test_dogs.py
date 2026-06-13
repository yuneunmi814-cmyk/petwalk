from tests.conftest import auth_headers, make_dog


def test_dog_crud_with_soft_delete(ctx):
    client, _ = ctx
    headers = auth_headers(client, email="owner@example.com")

    dog = make_dog(client, headers, name="콩이", size="small", temperament="calm")
    dog_id = dog["id"]

    assert len(client.get("/api/v1/dogs", headers=headers).json()) == 1

    patched = client.patch(
        f"/api/v1/dogs/{dog_id}", headers=headers, json={"temperament": "playful"}
    )
    assert patched.status_code == 200 and patched.json()["temperament"] == "playful"

    assert client.delete(f"/api/v1/dogs/{dog_id}", headers=headers).status_code == 204
    # Soft-deleted: gone from list and 404 on fetch.
    assert client.get("/api/v1/dogs", headers=headers).json() == []
    assert client.get(f"/api/v1/dogs/{dog_id}", headers=headers).status_code == 404


def test_cannot_touch_another_users_dog(ctx):
    client, _ = ctx
    a = auth_headers(client, email="a@example.com")
    b = auth_headers(client, email="b@example.com")
    dog = make_dog(client, a)
    assert client.get(f"/api/v1/dogs/{dog['id']}", headers=b).status_code == 404


def test_invalid_size_is_rejected(ctx):
    client, _ = ctx
    headers = auth_headers(client, email="c@example.com")
    res = client.post(
        "/api/v1/dogs",
        headers=headers,
        json={"name": "X", "breed": "Y", "size": "huge", "temperament": "calm"},
    )
    assert res.status_code == 400  # normalised validation error
    assert res.json()["error"]["code"] == "validation_error"
