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
from app.models.user import User, UserRole, TokenBlocklist
from app.schemas.user import UserRegister, UserLogin, UserOut, TokenPair, RefreshRequest

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
    if not jti or db.query(TokenBlocklist).filter(TokenBlocklist.jti == jti).first():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
        
    user = db.query(User).filter(User.id == int(data["sub"])).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    return _issue_tokens(user)


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


@router.get("/me", response_model=UserOut)
def read_profile(current_user: User = Depends(get_current_user)):
    return current_user
