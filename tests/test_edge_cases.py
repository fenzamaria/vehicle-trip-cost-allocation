"""
One test per edge case named in the brief, using the exact seed records
documented in schemas/seed_data_mapping.md. Each test asserts both the
attribution_level AND (where relevant) the specific trip/vehicle/reason
— not just "it didn't crash."
"""
from app.models import Allocation
from app.services.allocation import run_allocation


def _get(db, run_id, source_id):
    return (
        db.query(Allocation)
        .filter(Allocation.run_id == run_id, Allocation.source_id == source_id)
        .first()
    )


def test_case1_fuel_purchase_spans_multiple_trips_goes_to_vehicle_level(db):
    """F1 covers both T1 and T2 — must NOT be split, must land at VEHICLE level."""
    run_id = run_allocation(db)
    a = _get(db, run_id, "F1")
    assert a.attribution_level == "VEHICLE"
    assert a.vehicle_id == "V1"
    assert a.trip_id is None


def test_case2_toll_in_genuine_gap_falls_back_to_vehicle_level(db):
    """TL3 (13:00) is hours from any trip — a genuine gap, not ambiguity."""
    run_id = run_allocation(db)
    a = _get(db, run_id, "TL3")
    assert a.attribution_level == "VEHICLE"
    assert a.vehicle_id == "V1"
    assert a.trip_id is None
    assert a.reason_code is None  # vehicle IS known, this isn't unattributed


def test_case3_toll_cleanly_inside_trip_gets_trip_level(db):
    """TL1 (08:30) falls cleanly inside T1's 08:00-09:00 window."""
    run_id = run_allocation(db)
    a = _get(db, run_id, "TL1")
    assert a.attribution_level == "TRIP"
    assert a.trip_id == "T1"
    assert a.vehicle_id == "V1"


def test_case4_driver_expense_vehicle_and_date_only_not_inferred_to_trip(db):
    """DE2 has vehicle_id + date but no trip_id — must stay at VEHICLE level,
    never guessed down to a specific trip even if only one trip that day."""
    run_id = run_allocation(db)
    a = _get(db, run_id, "DE2")
    assert a.attribution_level == "VEHICLE"
    assert a.vehicle_id == "V1"
    assert a.trip_id is None


def test_case5_fully_unresolvable_expense_goes_unattributed(db):
    """DE3: driver D2 has no vehicle_id, no trip_id -> UNATTRIBUTED."""
    run_id = run_allocation(db)
    a = _get(db, run_id, "DE3")
    assert a.attribution_level == "UNATTRIBUTED"
    assert a.reason_code == "UNMAPPED_DRIVER"
    assert a.trip_id is None
    assert a.vehicle_id is None


def test_case6_fuel_purchase_no_trip_that_day_still_vehicle_level(db):
    """F3: V2 has zero trips anywhere in the dataset, but the vehicle IS
    known -> VEHICLE level, NOT unattributed."""
    run_id = run_allocation(db)
    a = _get(db, run_id, "F3")
    assert a.attribution_level == "VEHICLE"
    assert a.vehicle_id == "V2"
    assert a.reason_code is None


def test_case7_unknown_vehicle_goes_unattributed(db):
    """TL4 references vehicle V9, which does not exist in vehicles.json."""
    run_id = run_allocation(db)
    a = _get(db, run_id, "TL4")
    assert a.attribution_level == "UNATTRIBUTED"
    assert a.reason_code == "UNKNOWN_VEHICLE"
    assert a.vehicle_id is None


def test_case8_ambiguous_toll_between_two_trips_falls_back_to_vehicle(db):
    """TL2 (09:02) is within 5-min tolerance of BOTH T1's end (09:00) and
    T2's start (09:05) -> must NOT arbitrarily pick either -> VEHICLE level."""
    run_id = run_allocation(db)
    a = _get(db, run_id, "TL2")
    assert a.attribution_level == "VEHICLE"
    assert a.vehicle_id == "V1"
    assert a.trip_id is None  # confirms neither T1 nor T2 was arbitrarily chosen


def test_bonus_explicit_trip_reference_trusted_directly(db):
    """DE1 has an explicit, valid trip_id -> trusted directly, TRIP level."""
    run_id = run_allocation(db)
    a = _get(db, run_id, "DE1")
    assert a.attribution_level == "TRIP"
    assert a.trip_id == "T1"
    assert a.vehicle_id == "V1"
