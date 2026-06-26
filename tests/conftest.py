# flake8: noqa
import os

TEST_AWS_ACCESS_KEY_ID = "test-aws-access-key-id"
TEST_AWS_SECRET_ACCESS_KEY = "test-aws-secret-access-key"
TEST_AWS_REGION = "us-east-1"

# We don't want actual prod settings to be used in test environment.
# Thus, we set them here first so that they are not brought in from
# actual settings (.env).

os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["POOLED_DATABASE_URL"] = (
    "postgresql+psycopg://bloguser:blogpass@localhost/test_blog"
)
os.environ["S3_BUCKET_NAME"] = "test-bucket"
os.environ["S3_REGION"] = TEST_AWS_REGION
os.environ["S3_ACCESS_KEY_ID"] = TEST_AWS_ACCESS_KEY_ID
os.environ["S3_SECRET_ACCESS_KEY"] = TEST_AWS_SECRET_ACCESS_KEY
os.environ["AWS_ACCESS_KEY_ID"] = TEST_AWS_ACCESS_KEY_ID
os.environ["AWS_SECRET_ACCESS_KEY"] = TEST_AWS_SECRET_ACCESS_KEY
os.environ["AWS_DEFAULT_REGION"] = TEST_AWS_REGION

from collections.abc import AsyncGenerator

import boto3
import pytest
from httpx import ASGITransport, AsyncClient
from moto import mock_aws
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from database import get_db
from main import app
from models import Base

pytest_plugins = ["anyio"]  # "anyio" plugin lets us write async test functions


@pytest.fixture(scope="session")
def anyio_backend():
    # "anyio" uses multiple variations of backends, so
    # we specify it to use "asyncio" type of backend
    return "asyncio"


@pytest.fixture(scope="session")
def test_engine():
    engine = create_async_engine(
        url=os.environ["POOLED_DATABASE_URL"],
        poolclass=NullPool,
        # NullPool disables connection pooling entirely,
        # because without it, multiple tests can cause
        # problems like stale connections, or connection
        # already closed errors.
    )
    return engine


@pytest.fixture(scope="session")
async def handle_database(test_engine):
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await test_engine.dispose()


# Create a database session fixture for each test
@pytest.fixture
async def db_session(test_engine, handle_database) -> AsyncGenerator[AsyncSession]:
    conn = await test_engine.connect()
    transaction = await conn.begin()

    # We create an async db session which is bound to this
    # particular test connection instead of the engine.
    test_async_session = async_sessionmaker(
        bind=conn,
        class_=AsyncSession,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    # "create_savepoint" allows sqlalchemy to intercept db commit calls
    # and save a checkpoint instead of performing actual db writes

    async with test_async_session() as session:
        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()
            await conn.close()


# Mock AWS boto3 calls using moto
@pytest.fixture
def mocked_aws_s3_client():
    with mock_aws():
        s3_client = boto3.client("s3", region_name=os.environ["S3_REGION"])
        s3_client.create_bucket(Bucket=os.environ["S3_BUCKET_NAME"])
        yield s3_client


@pytest.fixture
async def client(db_session, mocked_aws_s3_client) -> AsyncGenerator[AsyncClient]:
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        # With ASGI transport, call happens in memory without any network call
        base_url="http://test",
    ) as async_client:
        yield async_client

    app.dependency_overrides.clear()


async def create_test_user(
    client: AsyncClient,
    username: str = "test_user",
    email: str = "test_user@example.com",
    password: str = "test_password",
) -> dict:
    response = await client.post(
        "/api/users",
        json={
            "username": username,
            "email": email,
            "password": password,
        },
    )
    assert response.status_code == 201, f"Failed to create user: {response.text}"
    return response.json()


async def login_test_user(
    client: AsyncClient,
    username: str = "test_user",
    password: str = "test_password",
) -> str:
    response = await client.post(
        "/api/users/token",
        data={  # Use "data" instead of "json" because it uses OAuth2 form data
            "username": username,
            "password": password,
        },
    )
    assert (
        response.status_code == 200
    ), f"Failed to get access token for login: {response.text}"
    return response.json()["access_token"]


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
