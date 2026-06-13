"""Auth dependencies: resolve the bearer token to a live user, enforce rate limit."""

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import AppError
from app.core.ratelimit import get_rate_limiter
from app.core.security import decode_token
from app.models import User


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise AppError("unauthorized", "Missing bearer token", 401)
    token = authorization.split(" ", 1)[1]
    try:
        payload = decode_token(token, "access")
    except Exception:
        raise AppError("unauthorized", "Invalid or expired token", 401)

    user = db.get(User, int(payload["sub"]))
    if user is None or user.deleted_at is not None:
        raise AppError("unauthorized", "Account not found", 401)
    if user.status == "disabled":
        raise AppError("forbidden", "Account disabled", 403)

    # Rate limit authenticated traffic per user (sliding 1-min window).
    if not get_rate_limiter().check(f"user:{user.id}"):
        raise AppError("rate_limited", "Too many requests, slow down", 429)
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise AppError("forbidden", "Admin privileges required", 403)
    return user
