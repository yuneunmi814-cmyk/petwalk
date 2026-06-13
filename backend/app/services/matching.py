"""Async suitability matcher (design §1.2 step 3, §3 worker).

A WalkRequest spawns a MatchJob; this runs off the request lifecycle in its own
SessionLocal (threadpool-scheduled by FastAPI BackgroundTasks). It scores nearby
candidates on distance + dog size/temperament compatibility + time-slot overlap,
writes the top matches as `suggested` Match rows, and walks the job
queued -> running -> success while bumping `progress` so the UI can show it.

Scoring is intentionally explicit and tunable (admins adjust weights, design
§1.3): distance 0-40, size 0-20, temperament 0-25, verified +5, time overlap
0-15. Candidates below 30 are dropped; top 10 kept.
"""

import time
from datetime import datetime, timezone

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from app.core import database
from app.core.config import get_settings
from app.core.security import grid_center, haversine_m, neighbor_cells
from app.models import Block, Dog, Match, MatchJob, User, WalkRequest

_SIZE_RANK = {"small": 0, "medium": 1, "large": 2}

# Symmetric dog-temperament compatibility (frozenset key handles either order;
# a same-temperament pair collapses to a 1-element set).
_TEMPERAMENT = {
    frozenset(["calm"]): 22,
    frozenset(["playful"]): 25,
    frozenset(["energetic"]): 22,
    frozenset(["shy"]): 18,
    frozenset(["calm", "playful"]): 18,
    frozenset(["calm", "energetic"]): 12,
    frozenset(["calm", "shy"]): 20,
    frozenset(["playful", "energetic"]): 18,
    frozenset(["playful", "shy"]): 10,
    frozenset(["energetic", "shy"]): 6,
}

SCORE_THRESHOLD = 30.0
MAX_MATCHES = 10


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _to_naive_utc(dt: datetime) -> datetime:
    """SQLite hands back naive datetimes; normalise so arithmetic never mixes
    aware/naive."""
    return dt.astimezone(timezone.utc).replace(tzinfo=None) if dt.tzinfo else dt


def _size_score(a: str, b: str) -> int:
    return {0: 20, 1: 12, 2: 4}[abs(_SIZE_RANK[a] - _SIZE_RANK[b])]


def _temperament_score(a: str, b: str) -> int:
    return _TEMPERAMENT.get(frozenset([a, b]), 12)


def _distance_m(cell_a: str, cell_b: str, size_deg: float) -> float:
    la, lna = grid_center(cell_a, size_deg)
    lb, lnb = grid_center(cell_b, size_deg)
    d = haversine_m(la, lna, lb, lnb)
    # Same cell -> identical centre -> 0; floor at half a cell so we never claim
    # "0 m away" for an approximate location.
    return max(d, size_deg * 111_000 / 2)


def _time_overlap_bonus(db: Session, candidate_id: int, slot: datetime) -> int:
    """+15 if the candidate has their own open request within 90 min, +8 within
    3 h — a weak signal that they're actually free then."""
    rows = (
        db.execute(
            select(WalkRequest.time_slot).where(
                WalkRequest.requester_id == candidate_id,
                WalkRequest.status == "open",
                WalkRequest.deleted_at.is_(None),
            )
        )
        .scalars()
        .all()
    )
    target = _to_naive_utc(slot)
    best = 0
    for ts in rows:
        diff_min = abs((_to_naive_utc(ts) - target).total_seconds()) / 60.0
        if diff_min <= 90:
            best = max(best, 15)
        elif diff_min <= 180:
            best = max(best, 8)
    return best


def score_pair(
    req_dog: Dog, cand_dog: Dog, distance_m: float, radius_km: float,
    verified: bool, time_bonus: int,
) -> float:
    radius_m = radius_km * 1000
    distance = 40.0 * max(0.0, 1.0 - distance_m / radius_m)
    size = _size_score(req_dog.size, cand_dog.size)
    temperament = _temperament_score(req_dog.temperament, cand_dog.temperament)
    return distance + size + temperament + (5 if verified else 0) + time_bonus


def _blocked_ids(db: Session, user_id: int) -> set[int]:
    rows = db.execute(
        select(Block).where(or_(Block.user_id == user_id, Block.blocked_user_id == user_id))
    ).scalars().all()
    return {b.blocked_user_id if b.user_id == user_id else b.user_id for b in rows}


def _delay() -> None:
    d = get_settings().match_step_delay_s
    if d > 0:
        time.sleep(d)


def process_match_job(job_id: int) -> None:
    """Entry point scheduled via BackgroundTasks. Owns its own DB session."""
    settings = get_settings()
    db = database.SessionLocal()
    try:
        job = db.get(MatchJob, job_id)
        if job is None:
            return
        job.status, job.progress = "running", 10
        db.commit()

        req = db.get(WalkRequest, job.request_id)
        req_dog = db.get(Dog, req.dog_id) if req else None
        if req is None or req.deleted_at is not None or req_dog is None:
            job.status, job.error_message = "failed", "request or dog not found"
            job.finished_at = _utcnow()
            db.commit()
            return

        _delay()
        job.progress = 35
        db.commit()

        blocked = _blocked_ids(db, req.requester_id)
        cells = neighbor_cells(req.grid_cell)
        candidates = (
            db.execute(
                select(User).where(
                    User.grid_cell.in_(cells),
                    User.id != req.requester_id,
                    User.status == "active",
                    User.deleted_at.is_(None),
                )
            )
            .scalars()
            .all()
        )

        _delay()
        job.progress = 70
        db.commit()

        scored: list[tuple[User, Dog, float, float]] = []
        for cand in candidates:
            if cand.id in blocked or cand.grid_cell is None:
                continue
            dogs = [d for d in cand.dogs if d.deleted_at is None]
            if not dogs:
                continue
            dist = _distance_m(req.grid_cell, cand.grid_cell, settings.grid_size_deg)
            if dist > req.radius_km * 1000:
                continue
            bonus = _time_overlap_bonus(db, cand.id, req.time_slot)
            best_dog, best_score = None, -1.0
            for d in dogs:
                sc = score_pair(req_dog, d, dist, req.radius_km, cand.is_verified, bonus)
                if sc > best_score:
                    best_dog, best_score = d, sc
            scored.append((cand, best_dog, best_score, dist))

        scored.sort(key=lambda r: r[2], reverse=True)
        top = [r for r in scored if r[2] >= SCORE_THRESHOLD][:MAX_MATCHES]

        # Idempotent re-run: clear prior suggestions, keep any confirmed match.
        db.execute(
            delete(Match).where(Match.request_id == req.id, Match.state == "suggested")
        )
        for cand, dog, sc, dist in top:
            db.add(
                Match(
                    request_id=req.id,
                    candidate_user_id=cand.id,
                    candidate_dog_id=dog.id,
                    score=round(sc, 1),
                    distance_m=int(dist),
                    state="suggested",
                )
            )

        _delay()
        job.progress, job.status = 100, "success"
        job.finished_at = _utcnow()
        db.commit()
    except Exception as exc:  # noqa: BLE001 - record failure, never crash the worker
        db.rollback()
        job = db.get(MatchJob, job_id)
        if job is not None:
            job.status, job.error_message = "failed", str(exc)[:200]
            job.finished_at = _utcnow()
            db.commit()
    finally:
        db.close()
