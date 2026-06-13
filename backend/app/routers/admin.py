"""Admin surface (design §1.3): operational metrics + moderation actions.
All endpoints require role=admin."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_admin
from app.core.errors import AppError
from app.models import Report, Review, User, WalkRequest
from app.schemas import AdminMetricsOut

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.get("/metrics", response_model=AdminMetricsOut)
def metrics(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> AdminMetricsOut:
    total_users = db.scalar(
        select(func.count(User.id)).where(User.deleted_at.is_(None))
    ) or 0
    total_requests = db.scalar(
        select(func.count(WalkRequest.id)).where(WalkRequest.deleted_at.is_(None))
    ) or 0
    matched = db.scalar(
        select(func.count(WalkRequest.id)).where(WalkRequest.status == "matched")
    ) or 0
    open_reports = db.scalar(
        select(func.count(Report.id)).where(Report.status.in_(("queued", "reviewing")))
    ) or 0
    reviews_total = db.scalar(select(func.count(Review.id))) or 0
    no_shows = db.scalar(select(func.count(Review.id)).where(Review.no_show.is_(True))) or 0

    return AdminMetricsOut(
        total_users=total_users,
        total_requests=total_requests,
        matched_requests=matched,
        match_success_rate=round(matched / total_requests, 3) if total_requests else 0.0,
        open_reports=open_reports,
        no_show_rate=round(no_shows / reviews_total, 3) if reviews_total else 0.0,
    )


@router.post("/users/{user_id}/disable", status_code=204)
def disable_user(
    user_id: int, _: User = Depends(require_admin), db: Session = Depends(get_db)
):
    user = db.get(User, user_id)
    if user is None:
        raise AppError("not_found", "User not found", 404)
    user.status = "disabled"
    db.commit()


@router.post("/users/{user_id}/verify", status_code=204)
def verify_user(
    user_id: int, _: User = Depends(require_admin), db: Session = Depends(get_db)
):
    user = db.get(User, user_id)
    if user is None:
        raise AppError("not_found", "User not found", 404)
    user.is_verified = True
    db.commit()


@router.post("/reports/{report_id}/resolve", status_code=204)
def resolve_report(
    report_id: int, _: User = Depends(require_admin), db: Session = Depends(get_db)
):
    report = db.get(Report, report_id)
    if report is None:
        raise AppError("not_found", "Report not found", 404)
    report.status = "actioned"
    db.commit()
