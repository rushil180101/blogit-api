import os
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from tests.conftest import auth_header, create_test_user, login_test_user


@pytest.mark.anyio
async def test_create_user_validation_error(client: AsyncClient):
    response = await client.post(
        "/api/users",
        json={"username": "test_user"},
    )

    assert response.status_code == 422
    assert "email" in response.text
    assert "password" in response.text


@pytest.mark.anyio
async def test_create_user_bad_request(client: AsyncClient):
    await create_test_user(client)

    response = await client.post(
        "/api/users",
        json={
            "username": "test_user_new",
            "email": "test_user@example.com",  # This email already exists
            "password": "test_password",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "user with this email already exists"


@pytest.mark.anyio
async def test_create_user_success(client: AsyncClient):
    response = await client.post(
        "/api/users",
        json={
            "username": "testing_user",
            "email": "testing_user@gmail.com",
            "password": "testing_password",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert "image_path" in data
    assert "password" not in data
    assert "password_hash" not in data
    assert data["username"] == "testing_user"
    assert data["email"] == "testing_user@gmail.com"


@pytest.mark.anyio
async def test_update_profile_pic(client: AsyncClient, mocked_aws_s3_client):
    user = await create_test_user(client)
    access_token = await login_test_user(client)

    test_image_path = Path(__file__).parent / "test_image.png"
    image_bytes = test_image_path.read_bytes()

    response = await client.patch(
        f"/api/users/{user['id']}/profile_pic",
        files={"file": ("test_image.png", BytesIO(image_bytes), "image/jpeg")},
        headers=auth_header(access_token),
    )

    assert response.status_code == 200
    data = response.json()
    assert "image_file" in data
    assert "image_path" in data
    assert data["image_file"].endswith(".jpg")
    assert data["image_path"].endswith(".jpg")

    assert data["image_path"] == (
        "https://{bucket}.s3.{region}.amazonaws.com/profile_pics/{file}".format(
            bucket=os.environ["S3_BUCKET_NAME"],
            region=os.environ["S3_REGION"],
            file=data["image_file"],
        )
    )

    s3_objects = mocked_aws_s3_client.list_objects_v2(
        Bucket=os.environ["S3_BUCKET_NAME"]
    )
    assert "Contents" in s3_objects
    assert len(s3_objects["Contents"]) == 1
    assert s3_objects["Contents"][0]["Key"].endswith(data["image_file"])


@pytest.mark.anyio
async def test_forgot_password_sends_email(client: AsyncClient):
    await create_test_user(client)

    with patch(
        "routers.users.send_password_reset_email",
        new_callable=AsyncMock,
    ) as mock_send:
        response = await client.post(
            "/api/users/forgot_password",
            json={"email": "test_user@example.com"},
        )

    assert response.status_code == 202
    mock_send.assert_awaited_once()
    call_kwargs = mock_send.call_args.kwargs
    assert call_kwargs["to"] == "test_user@example.com"
    assert call_kwargs["username"] == "test_user"
    assert "token" in call_kwargs
