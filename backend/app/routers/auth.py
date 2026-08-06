"""
Auth: register, login, refresh, current-user profile.

Both fishermen and family members register through the same endpoint with
a different `role`; the mobile app picks the right onboarding flow in the
UI, but the API surface stays uniform.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token, decode_token
from fastapi.security import OAuth2PasswordBearer
from app.core.deps import get_current_user, oauth2_scheme
from app.core.rate_limit import rate_limit
from app.models.user import User, UserRole, TokenBlocklist, PasswordResetToken
from app.schemas.user import (
    UserRegister,
    UserLogin,
    UserOut,
    TokenPair,
    RefreshRequest,
    PasswordResetRequest,
    PasswordResetConfirm,
    UserUpdate,
    PasswordChangeRequest,
)
import hashlib
from datetime import datetime, timezone, timedelta
import uuid
import logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _issue_tokens(user: User) -> TokenPair:
    return TokenPair(
        access_token=create_access_token(subject=str(user.id)),
        refresh_token=create_refresh_token(subject=str(user.id)),
        user=UserOut.model_validate(user),
    )


@router.post("/register", response_model=TokenPair, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(rate_limit("register", limit=10))])
def register(payload: UserRegister, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.phone_number == payload.phone_number).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Phone number already registered")

    # Defense in depth: UserRegister.role already restricts this to
    # fisherman/family, but never allow this public endpoint to mint an
    # operator account even if that constraint is loosened later.
    role = UserRole(payload.role)
    if role == UserRole.operator:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Operator accounts cannot self-register")

    user = User(
        phone_number=payload.phone_number,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        role=role,
        preferred_language=payload.preferred_language,
        boat_name=payload.boat_name,
        boat_registration_number=payload.boat_registration_number,
        home_harbor=payload.home_harbor,
        emergency_contact_name=payload.emergency_contact_name,
        emergency_contact_phone=payload.emergency_contact_phone,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _issue_tokens(user)


@router.post("/login", response_model=TokenPair,
             dependencies=[Depends(rate_limit("login", limit=20))])
def login(payload: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.phone_number == payload.phone_number).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid phone number or password")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")
    return _issue_tokens(user)


@router.post("/refresh", response_model=TokenPair)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    data = decode_token(payload.refresh_token)
    if not data or data.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    jti = data.get("jti")
    if not jti:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    # Reject already-used or revoked refresh tokens
    if db.query(TokenBlocklist).filter(TokenBlocklist.jti == jti).first():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    user = db.query(User).filter(User.id == int(data["sub"])) .first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    # Invalidate refresh tokens issued before the user's last password change.
    try:
        token_iat = float(data.get("iat", 0))
    except (TypeError, ValueError):
        token_iat = 0.0
    if user.password_changed_at is not None and token_iat:
        password_changed_at = user.password_changed_at
        if password_changed_at.tzinfo is None:
            password_changed_at = password_changed_at.replace(tzinfo=timezone.utc)
        if datetime.fromtimestamp(token_iat, timezone.utc) < password_changed_at:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    # Token rotation: mark the presented refresh token as used so it cannot be replayed.
    blocklist = TokenBlocklist(jti=jti)
    db.add(blocklist)
    db.commit()

    # Issue a fresh token pair
    return _issue_tokens(user)


@router.post("/forgot", status_code=status.HTTP_202_ACCEPTED)
def forgot_password(payload: PasswordResetRequest, db: Session = Depends(get_db)):
    # Don't reveal whether a phone number is registered — return 202 regardless.
    user = db.query(User).filter(User.phone_number == payload.phone_number).first()
    if not user:
        # Still return 202 to avoid user enumeration
        return {"status": "ok"}

    # Create a one-time token and persist only a hash of it
    raw_token = uuid.uuid4().hex
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    prt = PasswordResetToken(user_id=user.id, token_hash=token_hash, expires_at=expires_at)
    db.add(prt)
    db.commit()

    # Do not log reset secrets. Emit a non-sensitive audit message so
    # operators can trace issuance without leaking the one-time token.
    logger.info("Password reset token created for user %s", user.phone_number)

    return {"status": "ok"}


@router.post("/reset", status_code=status.HTTP_200_OK)
def reset_password(payload: PasswordResetConfirm, db: Session = Depends(get_db)):
    token_hash = hashlib.sha256(payload.token.encode("utf-8")).hexdigest()
    now = datetime.now(timezone.utc)
    prt = (
        db.query(PasswordResetToken)
        .filter(PasswordResetToken.token_hash == token_hash, PasswordResetToken.used == False)
        .first()
    )
    if prt is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired token")

    expires_at = prt.expires_at
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at is None or expires_at < now:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired token")

    user = db.query(User).filter(User.id == prt.user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token")

    # Update password and mark token used. Also update password_changed_at to invalidate old tokens.
    user.password_hash = hash_password(payload.new_password)
    user.password_changed_at = now
    prt.used = True
    db.add(user)
    db.add(prt)
    db.commit()

    return {"status": "ok"}


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    current_user: User = Depends(get_current_user),
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    payload = decode_token(token)
    if payload and "jti" in payload:
        blocklist = TokenBlocklist(jti=payload["jti"])
        db.add(blocklist)
        db.commit()


@router.post("/logout_all", status_code=status.HTTP_204_NO_CONTENT)
def logout_all(
    payload: dict,
    current_user: User = Depends(get_current_user),
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    """Revoke current access token and optional refresh token provided in the body.

    Body: { "refresh_token": "..." }  (refresh_token optional)
    """
    # Block the presented access token
    access_payload = decode_token(token)
    if access_payload and "jti" in access_payload:
        db.add(TokenBlocklist(jti=access_payload["jti"]))

    # Block the provided refresh token (if any)
    provided_refresh = payload.get("refresh_token") if isinstance(payload, dict) else None
    if provided_refresh:
        refresh_payload = decode_token(provided_refresh)
        if refresh_payload and refresh_payload.get("type") == "refresh" and "jti" in refresh_payload:
            db.add(TokenBlocklist(jti=refresh_payload["jti"]))

    db.commit()


@router.patch("/me", response_model=UserOut)
def update_profile(
    payload: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    updated_fields = payload.model_dump(exclude_unset=True)
    if updated_fields:
        for key, value in updated_fields.items():
            setattr(current_user, key, value)
        db.add(current_user)
        db.commit()
        db.refresh(current_user)
    return current_user


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    payload: PasswordChangeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid current password")
    if payload.current_password == payload.new_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="New password must differ from the current password")

    now = datetime.now(timezone.utc)
    current_user.password_hash = hash_password(payload.new_password)
    current_user.password_changed_at = now
    db.add(current_user)
    db.commit()


@router.get("/me", response_model=UserOut)
def read_profile(current_user: User = Depends(get_current_user)):
    return current_user
