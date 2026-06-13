"""PetWalk ORM models (design §1.4 db_schema).

The matching pipeline: a User posts a WalkRequest, which spawns a MatchJob the
worker processes asynchronously, writing Match rows (suggested -> confirmed).
Confirmed matches carry a chat (Message) and, after the walk, mutual Reviews.
Reports drop the target into a Block (immediate block queue, design §1.5).

Soft Delete (deleted_at) on user-owned rows that must survive for dispute/audit
history; hard FKs everywhere with explicit ondelete.
"""

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

DOG_SIZES = ("small", "medium", "large")
DOG_TEMPERAMENTS = ("calm", "playful", "energetic", "shy")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(80))
    # AES-256-GCM ciphertext (design §1.5). Never serialised.
    phone_enc: Mapped[str | None] = mapped_column(Text, nullable=True)

    role: Mapped[str] = mapped_column(String(16), default="user")  # user | admin
    status: Mapped[str] = mapped_column(String(16), default="active")  # active | disabled
    # Owner verification badge (design v1). MVP signs everyone up unverified.
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)

    # Exact home point — SERVER ONLY, never returned in any response. Clients
    # only ever see grid_cell / its centre (design §1.5 location privacy).
    home_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    home_lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    grid_cell: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    dogs: Mapped[list["Dog"]] = relationship(back_populates="owner", cascade="all, delete-orphan")


class Dog(Base):
    __tablename__ = "dogs"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    breed: Mapped[str] = mapped_column(String(80))
    size: Mapped[str] = mapped_column(String(16))  # one of DOG_SIZES
    temperament: Mapped[str] = mapped_column(String(16))  # one of DOG_TEMPERAMENTS
    photo_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    owner: Mapped["User"] = relationship(back_populates="dogs")


class WalkRequest(Base):
    __tablename__ = "walk_requests"
    # Hot path: "open requests in these cells around this time" (design §1.4 idx).
    __table_args__ = (Index("ix_walk_requests_cell_slot", "grid_cell", "time_slot"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    requester_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    dog_id: Mapped[int] = mapped_column(ForeignKey("dogs.id", ondelete="CASCADE"))
    grid_cell: Mapped[str] = mapped_column(String(32))
    time_slot: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    radius_km: Mapped[float] = mapped_column(Float, default=2.0)
    status: Mapped[str] = mapped_column(String(16), default="open")  # open|matched|closed|canceled
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MatchJob(Base):
    """One async suitability run for a WalkRequest. The worker drives status."""

    __tablename__ = "match_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(
        ForeignKey("walk_requests.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(16), default="queued", index=True)
    # queued | running | success | failed
    progress: Mapped[int] = mapped_column(Integer, default=0)  # 0..100
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Match(Base):
    __tablename__ = "matches"
    __table_args__ = (
        UniqueConstraint("request_id", "candidate_user_id", name="uq_match_request_candidate"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(
        ForeignKey("walk_requests.id", ondelete="CASCADE"), index=True
    )
    candidate_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    candidate_dog_id: Mapped[int] = mapped_column(ForeignKey("dogs.id", ondelete="CASCADE"))
    score: Mapped[float] = mapped_column(Float, default=0.0)
    distance_m: Mapped[int] = mapped_column(Integer, default=0)  # approximate, grid-derived
    state: Mapped[str] = mapped_column(String(16), default="suggested")  # suggested|confirmed|declined
    meeting_place_id: Mapped[int | None] = mapped_column(
        ForeignKey("meeting_places.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (Index("ix_messages_match_created", "match_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"), index=True)
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Review(Base):
    __tablename__ = "reviews"
    # One review per (match, rater) — blocks duplicate ratings (design §1.4).
    __table_args__ = (UniqueConstraint("match_id", "rater_id", name="uq_review_match_rater"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"), index=True)
    rater_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    ratee_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    score: Mapped[int] = mapped_column(Integer)  # 1..5
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    no_show: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    reporter_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    target_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    reason: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(16), default="queued")  # queued|reviewing|actioned|dismissed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Block(Base):
    """Immediate block queue: a report blocks the pair both ways, and the
    matcher excludes blocked users so a re-request can't reach them."""

    __tablename__ = "blocks"
    __table_args__ = (UniqueConstraint("user_id", "blocked_user_id", name="uq_block_pair"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    blocked_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class MeetingPlace(Base):
    """Curated public first-meeting locations (design §1.2: 첫 만남 공개 장소 강제)."""

    __tablename__ = "meeting_places"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    address: Mapped[str] = mapped_column(String(255))
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    is_public: Mapped[bool] = mapped_column(Boolean, default=True)
