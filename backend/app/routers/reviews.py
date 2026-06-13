"""Post-walk mutual reviews. One per (match, rater) — the DB unique constraint
turns a duplicate into a 409. A no-show flag feeds the admin no-show metric
(design §1.3 / §8)."""

from fastapi import APIRouter, Depends
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.errors import AppError
from app.models import Match, Review, User, WalkRequest
from app.schemas import ReviewIn, ReviewOut

router = APIRouter(prefix="/api/v1/reviews", tags=["reviews"])


@router.post("", status_code=201, response_model=ReviewOut)
def create_review(
    body: ReviewIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Review:
    match = db.get(Match, body.match_id)
    if match is None or match.state != "confirmed":
        raise AppError("not_found", "Confirmed match not found", 404)
    req = db.get(WalkRequest, match.request_id)
    if req is None or user.id not in (req.requester_id, match.candidate_user_id):
        raise AppError("forbidden", "Not your match", 403)

    ratee_id = match.candidate_user_id if user.id == req.requester_id else req.requester_id
    review = Review(
        match_id=match.id,
        rater_id=user.id,
        ratee_id=ratee_id,
        score=body.score,
        comment=body.comment,
        no_show=body.no_show,
    )
    db.add(review)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise AppError("conflict", "You already reviewed this walk", 409)
    db.refresh(review)
    return review
