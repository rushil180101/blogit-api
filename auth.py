from datetime import UTC, datetime, timedelta
from typing import Optional

import jwt
from fastapi.security import OAuth2PasswordBearer
from pwdlib import PasswordHash

from config import settings

password_hasher = PasswordHash.recommended()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/users/token")


def hash_password(password: str) -> str:
    """Creates and returns a password hash"""
    return password_hasher.hash(password)


def verify_password(plain_text_password: str, hashed_password: str) -> bool:
    """Compares plain text and hashed passwords and returns a boolean result"""
    return password_hasher.verify(
        password=plain_text_password,
        hash=hashed_password,
    )


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
