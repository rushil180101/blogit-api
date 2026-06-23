import pytest
from httpx import AsyncClient

from tests.conftest import auth_header, create_test_user, login_test_user


# Pytest fixture injection
# We don't need to explicitly import "client" fixture from conftest.
# Pytest automatically searches a fixture with same name and injects it.
@pytest.mark.anyio
async def test_get_posts_empty(client: AsyncClient):
    response = await client.get("/api/posts")
    assert response.status_code == 200
    data = response.json()
    assert data["posts"] == []
    assert data["total"] == 0
    assert data["has_more"] is False


@pytest.mark.anyio
async def test_get_post_not_found(client: AsyncClient):
    response = await client.get("/api/posts/100")
    assert response.status_code == 404
    assert response.json()["detail"] == "post not found"


@pytest.mark.anyio
async def test_create_post_success(client: AsyncClient):
    user = await create_test_user(client)
    access_token = await login_test_user(client)
    headers = auth_header(access_token)

    response = await client.post(
        "/api/posts",
        json={"title": "test title", "content": "test content"},
        headers=headers,
    )

    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "test title"
    assert data["content"] == "test content"
    assert data["user_id"] == user["id"]
    assert data["author"]["username"] == "test_user"


@pytest.mark.anyio
async def test_create_post_unauthorized(client: AsyncClient):

    response = await client.post(
        "/api/posts",
        json={"title": "test title", "content": "test content"},
    )

    assert response.status_code == 401
    data = response.json()
    assert data["detail"] == "Not authenticated"


@pytest.mark.anyio
async def test_update_post_success(client: AsyncClient):
    _ = await create_test_user(client)
    access_token = await login_test_user(client)
    headers = auth_header(access_token)

    response = await client.post(
        "/api/posts",
        json={"title": "test title", "content": "test content"},
        headers=headers,
    )
    post_id = response.json()["id"]

    response = await client.patch(
        f"/api/posts/{post_id}",
        json={"title": "updated test title"},
        headers=headers,
    )

    assert response.status_code == 200
    updated_post = response.json()
    assert updated_post["title"] == "updated test title"
    assert updated_post["content"] == "test content"


@pytest.mark.anyio
async def test_update_post_wrong_user(client: AsyncClient):
    await create_test_user(
        client=client,
        username="user1",
        email="user1@example.com",
        password="password1",
    )
    token1 = await login_test_user(
        client=client,
        username="user1",
        password="password1",
    )
    headers1 = auth_header(token=token1)
    response = await client.post(
        "/api/posts",
        json={"title": "test title", "content": "test content"},
        headers=headers1,
    )
    user1_post_id = response.json()["id"]

    await create_test_user(
        client=client,
        username="user2",
        email="user2@example.com",
        password="password2",
    )
    token2 = await login_test_user(
        client=client,
        username="user2",
        password="password2",
    )
    headers2 = auth_header(token=token2)
    response = await client.patch(
        f"/api/posts/{user1_post_id}",
        json={"title": "updated test title"},
        headers=headers2,
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "not authorized to update this post"
