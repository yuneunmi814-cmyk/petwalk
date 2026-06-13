"""Nearby-mate discovery (design §1.2 step 2).

Synchronous, grid-scoped read: returns owners whose cell is in the caller's 3x3
cell window, never their exact coordinates — only the cell centre + an
approximate distance. Blocked users are excluded. (Production caches this per
cell with a 60s TTL — design §1.2.)
"""

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.errors import AppError
from app.core.security import grid_center, neighbor_cells
from app.models import User
from app.schemas import MateListOut, MateOut
from app.services.matching import _blocked_ids, _distance_m

router = APIRouter(prefix="/api/v1/mates", tags=["mates"])


@router.get("", response_model=MateListOut)
def list_mates(
    radius_km: float = Query(default=2.0, gt=0, le=10, alias="radiusKm"),
    slot: datetime | None = None,
    page: int = Query(default=1, ge=1),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MateListOut:
    if user.grid_cell is None:
        raise AppError("location_required", "Set your location before searching", 400)

    size_deg = get_settings().grid_size_deg
    cells = neighbor_cells(user.grid_cell)
    blocked = _blocked_ids(db, user.id)
    candidates = (
        db.execute(
            select(User).where(
                User.grid_cell.in_(cells),
                User.id != user.id,
                User.status == "active",
                User.deleted_at.is_(None),
            )
        )
        .scalars()
        .all()
    )

    items: list[MateOut] = []
    for cand in candidates:
        if cand.id in blocked or cand.grid_cell is None:
            continue
        dogs = [d for d in cand.dogs if d.deleted_at is None]
        if not dogs:
            continue
        dist = _distance_m(user.grid_cell, cand.grid_cell, size_deg)
        if dist > radius_km * 1000:
            continue
        center = list(grid_center(cand.grid_cell))
        for dog in dogs:
            items.append(
                MateOut(
                    user_id=cand.id,
                    display_name=cand.display_name,
                    is_verified=cand.is_verified,
                    dog_id=dog.id,
                    dog_name=dog.name,
                    breed=dog.breed,
                    size=dog.size,
                    temperament=dog.temperament,
                    approx_distance_m=int(dist),
                    grid_center=center,
                )
            )

    items.sort(key=lambda m: m.approx_distance_m)
    return MateListOut(items=items, total=len(items), page=page)
