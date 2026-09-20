from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import User
from app.schemas.user import UserOut, UserCreate, UserUpdate
from app.core.rbac import require_permission, Role
from app.core.security import hash_password

router = APIRouter(prefix="/users", tags=["users"])


def _to_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        officialId=user.official_id,
        fullName=user.full_name,
        role=user.role,
        jurisdiction=user.jurisdiction,
        isActive=user.is_active,
    )


@router.get("", response_model=list[UserOut])
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("MANAGE_USERS")),
):
    return [_to_out(u) for u in db.query(User).order_by(User.created_at.desc()).all()]


@router.post("", response_model=UserOut, status_code=201)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("MANAGE_USERS")),
):
    if payload.role not in {r.value for r in Role}:
        raise HTTPException(status_code=400, detail=f"Unknown role '{payload.role}'.")
    if db.query(User).filter_by(official_id=payload.officialId).first():
        raise HTTPException(status_code=409, detail="An account with this official ID already exists.")

    user = User(
        official_id=payload.officialId,
        full_name=payload.fullName,
        role=payload.role,
        jurisdiction=payload.jurisdiction,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _to_out(user)


@router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: str,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("MANAGE_USERS")),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if payload.role is not None:
        if payload.role not in {r.value for r in Role}:
            raise HTTPException(status_code=400, detail=f"Unknown role '{payload.role}'.")
        user.role = payload.role
    if payload.fullName is not None:
        user.full_name = payload.fullName
    if payload.jurisdiction is not None:
        user.jurisdiction = payload.jurisdiction
    if payload.isActive is not None:
        if user.id == current_user.id and not payload.isActive:
            raise HTTPException(status_code=400, detail="You cannot deactivate your own account.")
        user.is_active = payload.isActive
    if payload.password:
        user.hashed_password = hash_password(payload.password)

    db.commit()
    db.refresh(user)
    return _to_out(user)
