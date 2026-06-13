"""Curated public meeting places for confirmed first walks."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import MeetingPlace, User
from app.schemas import MeetingPlaceOut

router = APIRouter(prefix="/api/v1/meeting-places", tags=["meeting-places"])


@router.get("", response_model=list[MeetingPlaceOut])
def list_meeting_places(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[MeetingPlace]:
    return list(
        db.execute(
            select(MeetingPlace).where(MeetingPlace.is_public.is_(True)).order_by(MeetingPlace.name)
        ).scalars()
    )
