"""PetWalk API entrypoint.

Tables are created and demo data seeded inside the lifespan against whatever
SessionLocal currently points at (tests repoint it), so a clean clone boots with
a populated map and no migration step. Use Alembic + PostGIS in production.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core import database
from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.routers import (
    admin,
    auth,
    dogs,
    matches,
    mates,
    places,
    reports,
    reviews,
    walk_requests,
)
from app.services.seed import seed_all


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    bind = database.SessionLocal().get_bind()
    database.Base.metadata.create_all(bind=bind)
    if settings.seed_on_startup:
        db = database.SessionLocal()
        try:
            seed_all(db)
        finally:
            db.close()
    yield


app = FastAPI(
    title="PetWalk — 동네 반려견 산책 메이트 매칭",
    version="0.1.0",
    description="반경 2km 내 검증된 견주를 매칭하는 위치 기반 산책 메이트 앱.",
    lifespan=lifespan,
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_error_handlers(app)

for module in (auth, dogs, mates, walk_requests, matches, reviews, reports, places, admin):
    app.include_router(module.router)


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}
