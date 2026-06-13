"""Unit layer: crypto + grid approximation primitives (design §6 단위)."""

import math

from app.core import security


def test_password_hash_roundtrip():
    h = security.hash_password("password123")
    assert h != "password123"
    assert security.verify_password("password123", h)
    assert not security.verify_password("wrong", h)


def test_aes_pii_roundtrip_and_nondeterministic():
    a = security.encrypt_pii("010-1234-5678")
    b = security.encrypt_pii("010-1234-5678")
    assert a != b  # random nonce
    assert security.decrypt_pii(a) == "010-1234-5678"
    assert security.encrypt_pii(None) is None


def test_grid_cell_is_deterministic_and_coarse():
    # Two points ~50m apart fall in the same cell; the cell never reveals them.
    c1 = security.grid_cell(37.51720, 127.04730)
    c2 = security.grid_cell(37.51725, 127.04735)
    assert c1 == c2
    cx, cy = security.grid_center(c1)
    # centre is within half a cell of the inputs, never the exact point
    assert abs(cx - 37.51720) < security.get_settings().grid_size_deg
    assert (cx, cy) != (37.51720, 127.04730)


def test_neighbor_cells_covers_3x3():
    cells = security.neighbor_cells("100_200")
    assert len(cells) == 9
    assert "100_200" in cells


def test_haversine_known_distance():
    # ~111 km per degree of latitude near the equator-ish; allow generous slack.
    d = security.haversine_m(37.5, 127.0, 37.51, 127.0)
    assert 1000 < d < 1200
    assert math.isclose(security.haversine_m(37.5, 127.0, 37.5, 127.0), 0.0, abs_tol=1e-6)
