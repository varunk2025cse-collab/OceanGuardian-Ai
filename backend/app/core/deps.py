"""
FastAPI dependency layer.

Three authenticated identities:
  get_current_user       - any active account (fisherman, family, operator)
  get_current_operator   - requires operator role (Rescue Dashboard only)
  get_current_fisherman  - requires fisherman role (SOS trigger, GPS sync, etc.)

The fisherman guard exists to prevent an operator account accidentally
tagging GPS pings or triggering SOS on behalf of a fisherman.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.database import get_db
from app.models.user import User, UserRole, TokenBlocklist

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_token(token)
    if payload is None or payload.get("type") != "access":
        raise credentials_error

    user_id = payload.get("sub")
    jti = payload.get("jti")
    if user_id is None or jti is None:
        raise credentials_error

    if db.query(TokenBlocklist).filter(TokenBlocklist.jti == jti).first():
        raise credentials_error

    user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None or not user.is_active:
        raise credentials_error

    # Invalidate tokens issued before the user's last password change.
    try:
        token_iat = float(payload.get("iat", 0))
    except (TypeError, ValueError):
        token_iat = 0
    if user.password_changed_at is not None and token_iat:
        if token_iat < float(user.password_changed_at.timestamp()):
            raise credentials_error

    return user


def get_current_operator(current_user: User = Depends(get_current_user)) -> User:
    """Restricts endpoint to operator-role accounts only."""
    if current_user.role != UserRole.operator:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operator account required",
        )
    return current_user


def get_current_fisherman(current_user: User = Depends(get_current_user)) -> User:
    """Restricts endpoint to fisherman-role accounts only."""
    if current_user.role != UserRole.fisherman:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Fisherman account required",
        )
    return current_user
