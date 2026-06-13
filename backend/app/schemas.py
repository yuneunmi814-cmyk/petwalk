"""Pydantic v2 request/response models.

All wire fields are camelCase (matching the design doc's JSON samples) via an
alias generator; internally we still use snake_case. `from_attributes` lets us
return ORM objects directly. Crucially, NO response model exposes home_lat /
home_lng — exact coordinates never cross the wire (design §1.5).
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, from_attributes=True
    )


# --- Auth ---------------------------------------------------------------


class SignupIn(CamelModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=80)
    phone: str | None = Field(default=None, max_length=32)
    # Home location for proximity matching. Optional at signup; stored exactly
    # server-side, exposed only as a grid cell.
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)


class LoginIn(CamelModel):
    email: EmailStr
    password: str


class TokenPair(CamelModel):
    access_token: str
    refresh_token: str


class RefreshIn(CamelModel):
    refresh_token: str


class AccessOut(CamelModel):
    access_token: str


class LocationIn(CamelModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class MeOut(CamelModel):
    id: int
    email: EmailStr
    display_name: str
    role: str
    status: str
    is_verified: bool
    grid_cell: str | None
    # The cell centre — the only location ever shown to clients.
    grid_center: list[float] | None = None


class SignupOut(TokenPair):
    user: MeOut


# --- Dogs ---------------------------------------------------------------


class DogIn(CamelModel):
    name: str = Field(min_length=1, max_length=80)
    breed: str = Field(min_length=1, max_length=80)
    size: Literal["small", "medium", "large"]
    temperament: Literal["calm", "playful", "energetic", "shy"]
    photo_url: str | None = Field(default=None, max_length=512)


class DogUpdate(CamelModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    breed: str | None = Field(default=None, min_length=1, max_length=80)
    size: Literal["small", "medium", "large"] | None = None
    temperament: Literal["calm", "playful", "energetic", "shy"] | None = None
    photo_url: str | None = Field(default=None, max_length=512)


class DogOut(CamelModel):
    id: int
    owner_id: int
    name: str
    breed: str
    size: str
    temperament: str
    photo_url: str | None


# --- Mates / search -----------------------------------------------------


class MateOut(CamelModel):
    user_id: int
    display_name: str
    is_verified: bool
    dog_id: int
    dog_name: str
    breed: str
    size: str
    temperament: str
    approx_distance_m: int
    grid_center: list[float]


class MateListOut(CamelModel):
    items: list[MateOut]
    total: int
    page: int


# --- Walk requests / async job -----------------------------------------


class WalkRequestIn(CamelModel):
    dog_id: int
    time_slot: datetime
    radius_km: float = Field(default=2.0, gt=0, le=10)


class JobAcceptedOut(CamelModel):
    job_id: int
    status_url: str


class MatchOut(CamelModel):
    match_id: int
    mate_user_id: int
    mate_name: str
    is_verified: bool
    dog_name: str
    breed: str
    size: str
    temperament: str
    score: float
    approx_distance_m: int
    state: str


class JobStatusOut(CamelModel):
    job_id: int
    request_id: int
    status: str
    progress: int
    matches: list[MatchOut] = []
    error: str | None = None


# --- Match accept / chat ------------------------------------------------


class AcceptIn(CamelModel):
    meeting_place_id: int


class MeetingPlaceOut(CamelModel):
    id: int
    name: str
    address: str
    lat: float
    lng: float


class MatchConfirmedOut(CamelModel):
    match_id: int
    state: str
    meeting_place: MeetingPlaceOut


class MessageIn(CamelModel):
    body: str = Field(min_length=1, max_length=2000)


class MessageOut(CamelModel):
    id: int
    match_id: int
    sender_id: int
    body: str
    created_at: datetime


# --- Reviews / reports --------------------------------------------------


class ReviewIn(CamelModel):
    match_id: int
    score: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=1000)
    no_show: bool = False


class ReviewOut(CamelModel):
    id: int
    match_id: int
    rater_id: int
    ratee_id: int
    score: int
    comment: str | None
    no_show: bool


class ReportIn(CamelModel):
    target_user_id: int
    reason: str = Field(min_length=1, max_length=255)


class ReportOut(CamelModel):
    id: int
    target_user_id: int
    reason: str
    status: str


# --- Admin --------------------------------------------------------------


class AdminMetricsOut(CamelModel):
    total_users: int
    total_requests: int
    matched_requests: int
    match_success_rate: float
    open_reports: int
    no_show_rate: float
