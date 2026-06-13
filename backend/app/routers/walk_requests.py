"""Walk requests — the async heart of the product (design §1.2 step 3).

POST returns 202 + a jobId immediately; the suitability computation runs in the
background (FastAPI BackgroundTasks -> matching.process_match_job). The client
polls the job endpoint, shows progress, then renders the ranked matches.
"""

from datetime import timezone

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.errors import AppError
from app.models import Dog, Match, MatchJob, User, WalkRequest
from app.schemas import JobAcceptedOut, JobStatusOut, MatchOut, WalkRequestIn
from app.services.matching import process_match_job

router = APIRouter(prefix="/api/v1/walk-requests", tags=["walk-requests"])


@router.post("", status_code=202, response_model=JobAcceptedOut)
def create_walk_request(
    body: WalkRequestIn,
    background: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> JobAcceptedOut:
    if user.grid_cell is None:
        raise AppError("location_required", "Set your location before requesting", 400)
    dog = db.get(Dog, body.dog_id)
    if dog is None or dog.deleted_at is not None or dog.owner_id != user.id:
        raise AppError("not_found", "Dog not found", 404)

    # SQLite has no native tz: store a canonical naive-UTC instant.
    slot = body.time_slot
    if slot.tzinfo is not None:
        slot = slot.astimezone(timezone.utc).replace(tzinfo=None)

    req = WalkRequest(
        requester_id=user.id,
        dog_id=dog.id,
        grid_cell=user.grid_cell,
        time_slot=slot,
        radius_km=body.radius_km,
        status="open",
    )
    db.add(req)
    db.commit()
    db.refresh(req)

    job = MatchJob(request_id=req.id, user_id=user.id, status="queued", progress=0)
    db.add(job)
    db.commit()
    db.refresh(job)

    # Heavy suitability calc is async (design §1.2: 비동기 202 + jobId).
    background.add_task(process_match_job, job.id)
    return JobAcceptedOut(
        job_id=job.id, status_url=f"/api/v1/walk-requests/{req.id}/jobs/{job.id}"
    )


@router.get("/{request_id}/jobs/{job_id}", response_model=JobStatusOut)
def job_status(
    request_id: int,
    job_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> JobStatusOut:
    job = db.get(MatchJob, job_id)
    if job is None or job.request_id != request_id:
        raise AppError("not_found", "Job not found", 404)
    if job.user_id != user.id:
        raise AppError("forbidden", "Not your job", 403)

    matches: list[MatchOut] = []
    if job.status == "success":
        rows = (
            db.execute(
                select(Match)
                .where(Match.request_id == request_id, Match.state != "declined")
                .order_by(Match.score.desc())
            )
            .scalars()
            .all()
        )
        for m in rows:
            cand = db.get(User, m.candidate_user_id)
            dog = db.get(Dog, m.candidate_dog_id)
            if cand is None or dog is None:
                continue
            matches.append(
                MatchOut(
                    match_id=m.id,
                    mate_user_id=cand.id,
                    mate_name=cand.display_name,
                    is_verified=cand.is_verified,
                    dog_name=dog.name,
                    breed=dog.breed,
                    size=dog.size,
                    temperament=dog.temperament,
                    score=m.score,
                    approx_distance_m=m.distance_m,
                    state=m.state,
                )
            )

    return JobStatusOut(
        job_id=job.id,
        request_id=request_id,
        status=job.status,
        progress=job.progress,
        matches=matches,
        error=job.error_message,
    )
