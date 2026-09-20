from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import User
from app.core.security import verify_password, create_access_token, create_refresh_token, decode_token
from app.schemas.auth import LoginRequest, LoginResponse, AuthUserOut, TokenPair, RefreshRequest
from app.api.deps import get_current_user
from app.core.config import get_settings

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


def _to_auth_user_out(user: User) -> AuthUserOut:
    # AuthUserOut's fields are camelCase (matching the frontend's AuthUser
    # type) while the ORM model's columns are snake_case, so this maps them
    # explicitly rather than relying on AuthUserOut.model_validate(user),
    # which fails because from_attributes reads attributes by field name.
    return AuthUserOut(
        id=user.id,
        fullName=user.full_name,
        officialId=user.official_id,
        role=user.role,
        jurisdiction=user.jurisdiction,
    )


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """
    `payload.role` is the role the frontend's login screen was showing when
    the form was submitted — a UX hint only. We look the account up purely by
    officialId, verify the password, and issue a token carrying THAT
    account's real role. If payload.role disagrees with the account's actual
    role we still log them in (their account may simply differ from what
    they clicked) but the token — and therefore every permission check
    downstream — reflects the database, never the request body.
    """
    user = db.query(User).filter_by(official_id=payload.officialId).first()
    if not user or not user.is_active or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid official ID or password.")

    access_token = create_access_token(user.id, user.role)
    refresh_token = create_refresh_token(user.id)

    return LoginResponse(
        user=_to_auth_user_out(user),
        tokens=TokenPair(
            accessToken=access_token,
            refreshToken=refresh_token,
            expiresIn=settings.access_token_expire_minutes * 60,
        ),
    )


@router.post("/refresh", response_model=TokenPair)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    try:
        claims = decode_token(payload.refreshToken)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    if claims.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Wrong token type")

    user = db.get(User, claims["sub"])
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    return TokenPair(
        accessToken=create_access_token(user.id, user.role),
        refreshToken=create_refresh_token(user.id),
        expiresIn=settings.access_token_expire_minutes * 60,
    )


@router.post("/logout")
def logout(current_user: User = Depends(get_current_user)):
    # Stateless JWTs: logout is enforced client-side by discarding tokens.
    # A production deployment should additionally maintain a short-lived
    # revocation list in Redis keyed by token jti for immediate server-side
    # invalidation — left as a documented extension point rather than a
    # fabricated "logged out" side effect with no real enforcement.
    return {"detail": "Logged out."}


@router.get("/me", response_model=AuthUserOut)
def me(current_user: User = Depends(get_current_user)):
    return _to_auth_user_out(current_user)
