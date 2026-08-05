"""Operator-only user management endpoints.

Provides user listing, detail, and update operations for operator accounts
(React Rescue Dashboard / admin console).
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.core.deps import get_current_operator
from app.models.user import User, UserRole
from app.schemas.user import UserOut
from app.schemas.admin import PaginatedUsers

router = APIRouter(prefix="/api/v1/admin/users", tags=["admin-users"])


@router.get("/", response_model=PaginatedUsers)
def list_users(
    role: str | None = Query(default=None),
    q: str | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    _: User = Depends(get_current_operator),
    db: Session = Depends(get_db),
):
    query = db.query(User)
    if role:
        try:
            query = query.filter(User.role == UserRole(role))
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role filter")
    if q:
        q_like = f"%{q}%"
        query = query.filter((User.full_name.ilike(q_like)) | (User.phone_number.ilike(q_like)))
    total = query.count()
    users = query.order_by(User.full_name.asc()).offset(skip).limit(limit).all()

    # Reuse PaginatedFishermen schema to avoid creating a separate admin user schema —
    # the rescue dashboard expects user lists with similar fields (name, phone, harbor, etc.).
    items = []
    for u in users:
        items.append(
            UserOut.model_validate(u)
        )
    return PaginatedUsers(items=items, total=total, skip=skip, limit=limit)


@router.get("/{user_id}", response_model=UserOut)
def get_user_detail(
    user_id: int,
    _: User = Depends(get_current_operator),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return UserOut.model_validate(user)


@router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    payload: dict,
    _: User = Depends(get_current_operator),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Allowed operator updates
    allowed = {"full_name", "preferred_language", "home_harbor", "emergency_contact_name", "emergency_contact_phone", "is_active", "role"}
    updated = False
    for k, v in payload.items():
        if k not in allowed:
            continue
        if k == "role":
            try:
                v = UserRole(v)
            except ValueError:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role")
        setattr(user, k, v)
        updated = True

    if updated:
        db.add(user)
        db.commit()
        db.refresh(user)

    return UserOut.model_validate(user)
