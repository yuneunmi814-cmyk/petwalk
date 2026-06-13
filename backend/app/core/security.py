"""Crypto + location-privacy primitives.

- Passwords: bcrypt cost 12, never stored in plaintext.
- Tokens: short-lived access JWT + long-lived refresh JWT, distinguished by a
  `type` claim so a refresh token can't be replayed as an access token.
- PII (phone): AES-256-GCM authenticated encryption, nonce prepended.
- Location: exact lat/lng is reduced to a coarse grid cell (~300m). The exact
  point is kept server-side for distance math; clients only ever get the cell
  centre. This is the product's signature privacy guarantee (design §1.5).
"""

import base64
import math
import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import get_settings

# --- Passwords ----------------------------------------------------------


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# --- JWT ----------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _encode(user_id: int, token_type: str, ttl: timedelta) -> str:
    s = get_settings()
    payload = {
        "sub": str(user_id),
        "type": token_type,
        "iat": _now(),
        "exp": _now() + ttl,
    }
    return jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm)


def create_access_token(user_id: int) -> str:
    s = get_settings()
    return _encode(user_id, "access", timedelta(minutes=s.access_token_ttl_min))


def create_refresh_token(user_id: int) -> str:
    s = get_settings()
    return _encode(user_id, "refresh", timedelta(days=s.refresh_token_ttl_days))


def decode_token(token: str, expected_type: str) -> dict:
    """Decode + verify a JWT. Raises jwt.PyJWTError or ValueError on any problem."""
    s = get_settings()
    payload = jwt.decode(token, s.jwt_secret, algorithms=[s.jwt_algorithm])
    if payload.get("type") != expected_type:
        raise ValueError("unexpected token type")
    return payload


# --- PII encryption (AES-256-GCM) --------------------------------------


def _aes_key() -> bytes:
    key = bytes.fromhex(get_settings().aes_key_hex)
    if len(key) != 32:
        raise RuntimeError("PETWALK_AES_KEY_HEX must be 64 hex chars (32 bytes)")
    return key


def encrypt_pii(plaintext: str | None) -> str | None:
    if plaintext is None:
        return None
    nonce = os.urandom(12)
    ct = AESGCM(_aes_key()).encrypt(nonce, plaintext.encode("utf-8"), None)
    return base64.b64encode(nonce + ct).decode("ascii")


def decrypt_pii(token: str | None) -> str | None:
    if token is None:
        return None
    raw = base64.b64decode(token)
    return AESGCM(_aes_key()).decrypt(raw[:12], raw[12:], None).decode("utf-8")


# --- Location grid approximation ---------------------------------------


def grid_cell(lat: float, lng: float, size: float | None = None) -> str:
    """Reduce an exact point to a coarse cell id, e.g. "12506_42349"."""
    size = size or get_settings().grid_size_deg
    return f"{math.floor(lat / size)}_{math.floor(lng / size)}"


def grid_center(cell: str, size: float | None = None) -> tuple[float, float]:
    """Centre of a cell — the only location a client is ever shown."""
    size = size or get_settings().grid_size_deg
    gx, gy = (int(p) for p in cell.split("_"))
    return ((gx + 0.5) * size, (gy + 0.5) * size)


def neighbor_cells(cell: str) -> list[str]:
    """The cell plus its 8 neighbours — the candidate search window."""
    gx, gy = (int(p) for p in cell.split("_"))
    return [f"{gx + dx}_{gy + dy}" for dx in (-1, 0, 1) for dy in (-1, 0, 1)]


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in metres."""
    r = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))
