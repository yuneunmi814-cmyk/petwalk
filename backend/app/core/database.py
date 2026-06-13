"""SQLAlchemy engine/session wiring.

`SessionLocal` is module-level so background workers (the async matcher) can open
their own session off the request lifecycle — the same pattern PlanForge's worker
uses. Tests repoint `SessionLocal` at an in-memory engine.
"""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

# check_same_thread=False: the matcher runs in a threadpool thread but shares the
# SQLite connection (fine — we never write concurrently to the same row).
connect_args = (
    {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
)
engine = create_engine(settings.database_url, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
