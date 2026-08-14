"""
Boundary tests for the toll tolerance window. The seed data's edge cases
(TL1, TL2, TL3) test the general behavior, but none of them test the
EXACT boundary of the 5-minute tolerance itself — this file does.

Uses T3 (2026-01-02, isolated — no adjacent trip) specifically so a
boundary match/non-match isn't confused with the ambiguous-overlap case.
T3 window: 08:00-09:00. With 5-min tolerance: [07:55, 09:05].
"""
from datetime import datetime

from app.models import TollTransaction
from app.services.allocation import allocate_toll, TOLL_TOLERANCE


def test_toll_exactly_at_tolerance_boundary_matches(db):
    """A toll at EXACTLY end_time + tolerance (09:05:00) should still
    count as a match — the boundary itself is inclusive (<=)."""
    toll = TollTransaction(
        toll_id="TL_BOUNDARY_IN",
        vehicle_id="V1",
        timestamp=datetime(2026, 1, 2, 9, 5, 0),  # exactly T3.end + 5min
        amount=100.00,
    )
    result = allocate_toll(toll, db)
    assert result["attribution_level"] == "TRIP"
    assert result["trip_id"] == "T3"


def test_toll_one_second_past_tolerance_boundary_does_not_match(db):
    """A toll just ONE SECOND past the boundary should NOT match —
    proves the tolerance is a real, enforced limit, not accidentally
    unbounded."""
    toll = TollTransaction(
        toll_id="TL_BOUNDARY_OUT",
        vehicle_id="V1",
        timestamp=datetime(2026, 1, 2, 9, 5, 1),  # 1 second past the boundary
        amount=100.00,
    )
    result = allocate_toll(toll, db)
    assert result["attribution_level"] == "VEHICLE"
    assert result["trip_id"] is None


def test_toll_exactly_at_start_boundary_matches(db):
    """Same check on the START side of the window: T3 starts at 08:00,
    so 07:55:00 (exactly start - tolerance) should match."""
    toll = TollTransaction(
        toll_id="TL_BOUNDARY_START",
        vehicle_id="V1",
        timestamp=datetime(2026, 1, 2, 7, 55, 0),
        amount=100.00,
    )
    result = allocate_toll(toll, db)
    assert result["attribution_level"] == "TRIP"
    assert result["trip_id"] == "T3"


def test_tolerance_constant_is_five_minutes():
    """A simple guard: if someone changes TOLL_TOLERANCE without updating
    the documentation (README assumption 3, DESIGN.md), this test fails
    loudly rather than the discrepancy going unnoticed."""
    assert TOLL_TOLERANCE.total_seconds() == 5 * 60
