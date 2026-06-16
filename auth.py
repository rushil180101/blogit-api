import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated, Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database import get_db
from models import User

password_hasher = PasswordHash.recommended()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/users/token")

# Create a "bearer token extractor from header" dependency
OAuth2TokenDependency = Annotated[str, Depends(oauth2_scheme)]

# Create a session dependency typehint
DbSessionDependency = Annotated[AsyncSession, Depends(get_db)]


def hash_password(password: str) -> str:
    """Creates and returns a password hash"""
    return password_hasher.hash(password)


def verify_password(plain_text_password: str, hashed_password: str) -> bool:
    """Compares plain text and hashed passwords and returns a boolean result"""
    return password_hasher.verify(
        password=plain_text_password,
        hash=hashed_password,
    )


def generate_reset_token() -> str:
    return secrets.token_urlsafe(32)


def hash_reset_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_access_token(
    data: dict, expiration_timedelta_in_minutes: Optional[int] = None
) -> str:
    """Create a jwt access token"""
    to_encode = data.copy()
    expiration_timedelta_in_minutes = (
        expiration_timedelta_in_minutes
        or settings.access_token_expiration_timedelta_in_minutes
    )
    expiration_time = datetime.now(UTC) + timedelta(
        minutes=expiration_timedelta_in_minutes
    )
    to_encode.update({"exp": expiration_time})
    encoded_jwt = jwt.encode(
        payload=to_encode,
        key=settings.secret_key.get_secret_value(),
        algorithm=settings.algorithm,
    )
    return encoded_jwt


def verify_access_token(token: str) -> str | None:
    """Decodes jwt token and returns user id if token is valid"""
    try:
        payload = jwt.decode(
            jwt=token,
            key=settings.secret_key.get_secret_value(),
            algorithms=[settings.algorithm],
            options={"require": ["exp", "sub"]},
        )
    except jwt.InvalidTokenError:
        return None
    return payload.get("sub")


async def get_current_user(
    token: OAuth2TokenDependency, db: DbSessionDependency
) -> User:
    try:
        user_id = int(verify_access_token(token))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    result = await db.execute(select(User).where(User.id == user_id))
    existing_user = result.scalars().first()
    if not existing_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return existing_user


# Create the current user dependency
CurrentUser = Annotated[User, Depends(get_current_user)]
