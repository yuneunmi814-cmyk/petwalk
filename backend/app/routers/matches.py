"""Match acceptance + chat.

Accepting a suggested candidate confirms the match, pins a PUBLIC meeting place
(first-meeting safety, design §1.2/§1.5), and declines the request's other
suggestions. Chat opens only after confirmation. Message bodies are stored raw
and escaped at render time (React escapes by default); the API never reflects
them as HTML.
"""

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.core import database
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.errors import AppError
from app.core.security import decode_token
from app.models import Dog, Match, MeetingPlace, Message, User, WalkRequest
from app.schemas import (
    AcceptIn,
    MatchConfirmedOut,
    MatchOut,
    MeetingPlaceOut,
    MessageIn,
    MessageOut,
)
from app.services.ws import manager

router = APIRouter(prefix="/api/v1/matches", tags=["matches"])


def _match_for_participant(db: Session, user: User, match_id: int) -> tuple[Match, WalkRequest]:
    match = db.get(Match, match_id)
    if match is None:
        raise AppError("not_found", "Match not found", 404)
    req = db.get(WalkRequest, match.request_id)
    if req is None or user.id not in (req.requester_id, match.candidate_user_id):
        raise AppError("forbidden", "Not your match", 403)
    return match, req


@router.post("/{match_id}/accept", response_model=MatchConfirmedOut)
def accept_match(
    match_id: int,
    body: AcceptIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MatchConfirmedOut:
    match, req = _match_for_participant(db, user, match_id)
    # The requester chose the mate, so only they confirm.
    if user.id != req.requester_id:
        raise AppError("forbidden", "Only the requester can accept", 403)
    if match.state == "declined":
        raise AppError("conflict", "This candidate was already declined", 409)

    place = db.get(MeetingPlace, body.meeting_place_id)
    if place is None or not place.is_public:
        raise AppError("not_found", "Public meeting place not found", 404)

    match.state = "confirmed"
    match.meeting_place_id = place.id
    req.status = "matched"
    # Decline the request's other suggestions — one confirmed mate per request.
    db.execute(
        update(Match)
        .where(Match.request_id == req.id, Match.id != match.id, Match.state == "suggested")
        .values(state="declined")
    )
    db.commit()
    return MatchConfirmedOut(
        match_id=match.id, state=match.state, meeting_place=MeetingPlaceOut.model_validate(place)
    )


@router.get("", response_model=list[MatchOut])
def my_matches(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[MatchOut]:
    """Confirmed matches the caller is part of, counterpart shown as the mate."""
    rows = (
        db.execute(
            select(Match)
            .join(WalkRequest, Match.request_id == WalkRequest.id)
            .where(
                Match.state == "confirmed",
                or_(
                    WalkRequest.requester_id == user.id,
                    Match.candidate_user_id == user.id,
                ),
            )
            .order_by(Match.created_at.desc())
        )
        .scalars()
        .all()
    )
    out: list[MatchOut] = []
    for m in rows:
        req = db.get(WalkRequest, m.request_id)
        if user.id == req.requester_id:
            other, other_dog = db.get(User, m.candidate_user_id), db.get(Dog, m.candidate_dog_id)
        else:
            other, other_dog = db.get(User, req.requester_id), db.get(Dog, req.dog_id)
        if other is None or other_dog is None:
            continue
        out.append(
            MatchOut(
                match_id=m.id,
                mate_user_id=other.id,
                mate_name=other.display_name,
                is_verified=other.is_verified,
                dog_name=other_dog.name,
                breed=other_dog.breed,
                size=other_dog.size,
                temperament=other_dog.temperament,
                score=m.score,
                approx_distance_m=m.distance_m,
                state=m.state,
            )
        )
    return out


@router.get("/{match_id}/messages", response_model=list[MessageOut])
def list_messages(
    match_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Message]:
    match, _ = _match_for_participant(db, user, match_id)
    return list(
        db.execute(
            select(Message).where(Message.match_id == match.id).order_by(Message.created_at)
        ).scalars()
    )


@router.post("/{match_id}/messages", status_code=201, response_model=MessageOut)
def send_message(
    match_id: int,
    body: MessageIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Message:
    match, _ = _match_for_participant(db, user, match_id)
    if match.state != "confirmed":
        raise AppError("conflict", "Chat opens after the match is confirmed", 409)
    msg = Message(match_id=match.id, sender_id=user.id, body=body.body)
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


# --- Real-time chat over WebSocket (design §1.2 step 4 / §5: 채팅 p95 < 1s) -----
#
# The browser WebSocket API can't send an Authorization header, so the access
# token is passed as a query param and verified at handshake. DB work is sync,
# so it's pushed off the event loop via run_in_threadpool.


def _authorize_socket(token: str | None, match_id: int) -> int | None:
    """Return the participant's user id, or None to reject. All failure reasons
    collapse to None so we don't leak which check failed."""
    if not token:
        return None
    db = database.SessionLocal()
    try:
        try:
            payload = decode_token(token, "access")
        except Exception:
            return None
        user = db.get(User, int(payload["sub"]))
        if user is None or user.deleted_at is not None or user.status == "disabled":
            return None
        match = db.get(Match, match_id)
        if match is None or match.state != "confirmed":
            return None
        req = db.get(WalkRequest, match.request_id)
        if req is None or user.id not in (req.requester_id, match.candidate_user_id):
            return None
        return user.id
    finally:
        db.close()


def _persist_message(match_id: int, sender_id: int, body: str) -> dict:
    db = database.SessionLocal()
    try:
        msg = Message(match_id=match_id, sender_id=sender_id, body=body)
        db.add(msg)
        db.commit()
        db.refresh(msg)
        return MessageOut.model_validate(msg).model_dump(by_alias=True, mode="json")
    finally:
        db.close()


@router.websocket("/{match_id}/ws")
async def chat_socket(
    websocket: WebSocket, match_id: int, token: str | None = Query(default=None)
):
    user_id = await run_in_threadpool(_authorize_socket, token, match_id)
    if user_id is None:
        await websocket.close(code=1008)  # policy violation
        return

    await manager.connect(match_id, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            body = (data.get("body", "") if isinstance(data, dict) else "").strip()
            if not body:
                continue
            payload = await run_in_threadpool(_persist_message, match_id, user_id, body[:2000])
            await manager.broadcast(match_id, payload)
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(match_id, websocket)
