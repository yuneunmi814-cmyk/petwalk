"""Auth: signup / login / refresh / me / location.

First account bootstraps to an approved admin (PlanForge convention). Tokens are
a short access JWT + long refresh JWT; the refresh endpoint mints a fresh access
token. (Production: deliver the refresh token as an HttpOnly+Secure cookie —
design §1.5; the body form here keeps the local build simple.)
"""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.errors import AppError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    encrypt_pii,
    grid_cell,
    grid_center,
    hash_password,
    verify_password,
)
from app.models import User
from app.schemas import (
    AccessOut,
    LocationIn,
    LoginIn,
    MeOut,
    RefreshIn,
    SignupIn,
    SignupOut,
    TokenPair,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def me_out(user: User) -> MeOut:
    center = list(grid_center(user.grid_cell)) if user.grid_cell else None
    return MeOut(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        status=user.status,
        is_verified=user.is_verified,
        grid_cell=user.grid_cell,
        grid_center=center,
    )


@router.post("/signup", status_code=201, response_model=SignupOut)
def signup(body: SignupIn, db: Session = Depends(get_db)) -> SignupOut:
    if db.execute(select(User.id).where(User.email == body.email)).first() is not None:
        raise AppError("email_taken", "Email already registered", 409)

    is_first = db.execute(select(User.id).limit(1)).first() is None
    cell = (
        grid_cell(body.lat, body.lng)
        if body.lat is not None and body.lng is not None
        else None
    )
    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        display_name=body.display_name,
        phone_enc=encrypt_pii(body.phone),
        role="admin" if is_first else "user",
        status="active",
        is_verified=is_first,
        home_lat=body.lat,
        home_lng=body.lng,
        grid_cell=cell,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return SignupOut(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
        user=me_out(user),
    )


@router.post("/login", response_model=TokenPair)
def login(body: LoginIn, db: Session = Depends(get_db)) -> TokenPair:
    user = db.execute(
        select(User).where(User.email == body.email, User.deleted_at.is_(None))
    ).scalar_one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        raise AppError("invalid_credentials", "Invalid email or password", 401)
    if user.status == "disabled":
        raise AppError("forbidden", "Account disabled", 403)
    return TokenPair(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/refresh", response_model=AccessOut)
def refresh(body: RefreshIn, db: Session = Depends(get_db)) -> AccessOut:
    try:
        payload = decode_token(body.refresh_token, "refresh")
    except Exception:
        raise AppError("unauthorized", "Invalid or expired refresh token", 401)
    user = db.get(User, int(payload["sub"]))
    if user is None or user.deleted_at is not None:
        raise AppError("unauthorized", "Account not found", 401)
    return AccessOut(access_token=create_access_token(user.id))


@router.get("/me", response_model=MeOut)
def me(user: User = Depends(get_current_user)) -> MeOut:
    return me_out(user)


@router.patch("/me/location", response_model=MeOut)
def set_location(
    body: LocationIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MeOut:
    # Store the exact point server-side; expose only the cell.
    user.home_lat, user.home_lng = body.lat, body.lng
    user.grid_cell = grid_cell(body.lat, body.lng)
    db.commit()
    db.refresh(user)
    return me_out(user)
