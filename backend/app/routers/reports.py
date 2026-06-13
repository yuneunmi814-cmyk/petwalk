"""Reporting. A report immediately blocks the pair both ways (design §1.5: 신고
1회로 즉시 차단 큐) so the matcher can never surface them to each other again,
and queues the report for admin review."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.errors import AppError
from app.models import Block, Report, User
from app.schemas import ReportIn, ReportOut

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


def _block(db: Session, user_id: int, blocked_user_id: int) -> None:
    exists = db.execute(
        select(Block.id).where(
            Block.user_id == user_id, Block.blocked_user_id == blocked_user_id
        )
    ).first()
    if exists is None:
        db.add(Block(user_id=user_id, blocked_user_id=blocked_user_id))


@router.post("", status_code=201, response_model=ReportOut)
def create_report(
    body: ReportIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Report:
    if body.target_user_id == user.id:
        raise AppError("bad_request", "You cannot report yourself", 400)
    target = db.get(User, body.target_user_id)
    if target is None or target.deleted_at is not None:
        raise AppError("not_found", "Target user not found", 404)

    report = Report(
        reporter_id=user.id,
        target_user_id=target.id,
        reason=body.reason,
        status="queued",
    )
    db.add(report)
    # Immediate, symmetric block.
    _block(db, user.id, target.id)
    _block(db, target.id, user.id)
    db.commit()
    db.refresh(report)
    return report
