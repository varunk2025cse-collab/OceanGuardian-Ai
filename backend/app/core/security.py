"""
Password hashing and JWT token helpers.

Kept isolated from the rest of the app so the crypto/JWT approach can be
swapped or hardened later (e.g. moving to short-lived access + refresh
token rotation) without touching route handlers.
"""
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import jwt, JWTError

from app.config import settings

# Using the `bcrypt` library directly rather than passlib's CryptContext
# wrapper: passlib 1.7.x reads a `__about__.__version__` attribute that
# bcrypt >=4.1 no longer exposes, which breaks hashing at runtime. Calling
# bcrypt directly avoids that fragile dependency entirely.
_BCRYPT_MAX_BYTES = 72  # bcrypt silently ignores anything past this


def hash_password(plain_password: str) -> str:
    truncated = plain_password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
    return bcrypt.hashpw(truncated, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    truncated = plain_password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
    return bcrypt.checkpw(truncated, hashed_password.encode("utf-8"))


def get_password_hash(plain_password: str) -> str:
    return hash_password(plain_password)


def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode = {"sub": subject, "exp": expire, "type": "access"}
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
    to_encode = {"sub": subject, "exp": expire, "type": "refresh"}
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None
