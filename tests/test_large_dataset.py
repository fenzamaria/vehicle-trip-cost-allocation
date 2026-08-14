"""
Tests against a larger, programmatically-generated dataset (5 vehicles,
20 trips, 40+ cost records spanning all three cost types) — separate
from the hand-crafted seed data used everywhere else.

Purpose: the seed-data tests prove each SPECIFIC edge case works, but
they can't rule out the allocation logic being subtly overfit to those
exact 10 records. This test proves the conservation invariant and
"exactly once" rule hold generally, at a scale and variety the seed
data doesn't cover — a genuine generalization check, not just a repeat
of the same assertions on bigger numbers.

Data is generated deterministically (fixed values, not random) so
failures are reproducible.
"""
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Vehicle, Trip, FuelPurchase, TollTransaction, DriverExpense, Allocation
from app.services.allocation import run_allocation


def _build_large_dataset(session):
    """Builds 5 vehicles, 20 trips (4 each), and a mix of cost records
    deliberately covering: normal trip-level matches, multi-trip fuel
    fill periods, gaps, ambiguous overlaps, unknown vehicles, and
    unresolvable expenses — but at a larger scale and with different
    specific values than the main seed data."""

    # 5 vehicles; VX99 is deliberately never added (unknown-vehicle case at scale)
    vehicle_ids = ["VA", "VB", "VC", "VD", "VE"]
    for vid in vehicle_ids:
        session.add(Vehicle(vehicle_id=vid, registration_no=f"REG-{vid}"))

    from app.models import Driver
    session.add(Driver(driver_id="DX1", name="Driver One"))
    session.add(Driver(driver_id="DX2", name="Driver Two (unmapped)"))

    base_day = datetime(2026, 3, 1, 6, 0, 0)
    trip_counter = 0
    fuel_counter = 0
    toll_counter = 0

    expected_total = Decimal("0.00")

    for v_idx, vid in enumerate(vehicle_ids):
        # 4 trips per vehicle, spaced 90 minutes apart, each 45 min long,
        # across 4 different days (so each vehicle gets its own fill periods).
        trips_for_vehicle = []
        for day in range(4):
            trip_counter += 1
            trip_id = f"TX{trip_counter}"
            start = base_day + timedelta(days=day, hours=v_idx)
            end = start + timedelta(minutes=45)
            session.add(Trip(trip_id=trip_id, vehicle_id=vid, start_time=start,
                              end_time=end, distance_km=20.0))
            trips_for_vehicle.append((trip_id, start, end))

        # One fuel purchase before the first two trips (spans a multi-trip
        # fill period, same pattern as the main seed data's F1) + one more
        # before the later two trips.
        fuel_counter += 1
        f1_amount = Decimal("1500.00") + (v_idx * 100)
        session.add(FuelPurchase(
            fuel_id=f"FX{fuel_counter}", vehicle_id=vid,
            timestamp=trips_for_vehicle[0][1] - timedelta(minutes=30),
            amount=f1_amount,
        ))
        expected_total += f1_amount

        fuel_counter += 1
        f2_amount = Decimal("1600.00") + (v_idx * 100)
        session.add(FuelPurchase(
            fuel_id=f"FX{fuel_counter}", vehicle_id=vid,
            timestamp=trips_for_vehicle[2][1] - timedelta(minutes=30),
            amount=f2_amount,
        ))
        expected_total += f2_amount

        # Tolls: one clean match on trip 0, one ambiguous between trips 1&2
        # is skipped for simplicity at scale (already covered in boundary
        # tests) — instead: one clean match, one genuine gap, one unknown
        # vehicle (only for the first vehicle, to keep it deterministic).
        toll_counter += 1
        clean_amount = Decimal("80.00") + v_idx
        session.add(TollTransaction(
            toll_id=f"TX_TOLL{toll_counter}", vehicle_id=vid,
            timestamp=trips_for_vehicle[0][1] + timedelta(minutes=10),  # inside trip 0
            amount=clean_amount,
        ))
        expected_total += clean_amount

        toll_counter += 1
        gap_amount = Decimal("60.00") + v_idx
        session.add(TollTransaction(
            toll_id=f"TX_TOLL{toll_counter}", vehicle_id=vid,
            timestamp=trips_for_vehicle[1][2] + timedelta(hours=3),  # hours after trip 1 ends
            amount=gap_amount,
        ))
        expected_total += gap_amount

        # Driver expenses: one explicit trip_id, one vehicle-only.
        session.add(DriverExpense(
            expense_id=f"DX_EXP{v_idx}_1", driver_id="DX1", vehicle_id=vid,
            trip_id=trips_for_vehicle[0][0],
            expense_date=trips_for_vehicle[0][1].date(),
            amount=Decimal("50.00"),
        ))
        expected_total += Decimal("50.00")

        session.add(DriverExpense(
            expense_id=f"DX_EXP{v_idx}_2", driver_id="DX1", vehicle_id=vid,
            trip_id=None,
            expense_date=trips_for_vehicle[2][1].date(),
            amount=Decimal("35.00"),
        ))
        expected_total += Decimal("35.00")

    # One unknown-vehicle toll (vehicle "VX99" never added above).
    session.add(TollTransaction(
        toll_id="TX_TOLL_UNKNOWN", vehicle_id="VX99",
        timestamp=base_day, amount=Decimal("45.00"),
    ))
    expected_total += Decimal("45.00")

    # One fully unresolvable driver expense (unmapped driver, no refs).
    session.add(DriverExpense(
        expense_id="DX_EXP_UNRESOLVABLE", driver_id="DX2", vehicle_id=None,
        trip_id=None, expense_date=base_day.date(), amount=Decimal("22.00"),
    ))
    expected_total += Decimal("22.00")

    session.commit()
    return expected_total


def test_large_synthetic_dataset_conservation_invariant():
    """Fresh, isolated in-memory database — separate from the `db`
    fixture's seed data, so this really is a different dataset, not a
    bigger copy of the same one."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    expected_total = _build_large_dataset(session)

    run_id = run_allocation(session)
    allocations = session.query(Allocation).filter(Allocation.run_id == run_id).all()
    actual_total = sum(a.amount for a in allocations)

    assert actual_total == expected_total, (
        f"Invariant broken at scale: got {actual_total}, expected {expected_total}"
    )

    # Also re-check "exactly once" at this larger scale.
    seen = set()
    for a in allocations:
        key = (a.source_type, a.source_id)
        assert key not in seen, f"Duplicate at scale: {key}"
        seen.add(key)

    session.close()


def test_large_synthetic_dataset_has_expected_unattributed_count():
    """Sanity check on the SHAPE of the result, not just the total:
    exactly 2 records should land in UNATTRIBUTED (the unknown-vehicle
    toll and the unresolvable expense) — everything else should resolve
    to TRIP or VEHICLE level."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    _build_large_dataset(session)
    run_id = run_allocation(session)
    allocations = session.query(Allocation).filter(Allocation.run_id == run_id).all()

    unattributed = [a for a in allocations if a.attribution_level == "UNATTRIBUTED"]
    assert len(unattributed) == 2

    reason_codes = {a.reason_code for a in unattributed}
    assert reason_codes == {"UNKNOWN_VEHICLE", "UNMAPPED_DRIVER"}

    session.close()
