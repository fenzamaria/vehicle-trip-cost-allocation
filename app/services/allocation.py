"""
The Allocation Engine — the heart of the whole project.

For each cost-bearing record (fuel, toll, driver expense), this decides
whether it can be attributed to a specific TRIP, falls back to VEHICLE
level, or must go to the UNATTRIBUTED pool with a reason code.

Every function here returns a plain dict describing the allocation
decision — the caller (run_allocation) is responsible for actually
writing it to the database. Keeping these functions pure (no direct
DB writes) makes them easy to test in isolation.
"""
import uuid
from datetime import timedelta, datetime, timezone

from sqlalchemy.orm import Session

from app.models import (
    Vehicle, Trip, FuelPurchase, TollTransaction, DriverExpense,
    AllocationRun, Allocation,
)

# The toll tolerance window — documented explicitly in README.md assumption 3.
# A toll timestamp within this many minutes of a trip's start/end still
# counts as "inside" that trip for TRIP-level attribution purposes.
TOLL_TOLERANCE = timedelta(minutes=5)


def _vehicle_exists(db: Session, vehicle_id: str) -> bool:
    return db.query(Vehicle).filter(Vehicle.vehicle_id == vehicle_id).first() is not None


def allocate_fuel(fuel: FuelPurchase, db: Session) -> dict:
    """
    Fuel purchases are NEVER split across trips (see DESIGN.md Section 3) —
    a tank spans multiple trips and we have no reliable way to divide it.
    The only decision here is: do we even recognize the vehicle?
    """
    if not _vehicle_exists(db, fuel.vehicle_id):
        return {
            "source_type": "FUEL",
            "source_id": fuel.fuel_id,
            "amount": fuel.amount,
            "attribution_level": "UNATTRIBUTED",
            "trip_id": None,
            "vehicle_id": None,
            "reason_code": "UNKNOWN_VEHICLE",
        }

    return {
        "source_type": "FUEL",
        "source_id": fuel.fuel_id,
        "amount": fuel.amount,
        "attribution_level": "VEHICLE",
        "trip_id": None,
        "vehicle_id": fuel.vehicle_id,
        "reason_code": None,
    }


def allocate_toll(toll: TollTransaction, db: Session) -> dict:
    """
    Tolls try for TRIP-level attribution first (a timestamp is a strong
    signal), but only when exactly one trip matches within tolerance.
    Zero matches (a gap) or 2+ matches (ambiguous overlap) both fall back
    to VEHICLE level — see DESIGN.md Section 3 for the full rationale.
    """
    if not _vehicle_exists(db, toll.vehicle_id):
        return {
            "source_type": "TOLL",
            "source_id": toll.toll_id,
            "amount": toll.amount,
            "attribution_level": "UNATTRIBUTED",
            "trip_id": None,
            "vehicle_id": None,
            "reason_code": "UNKNOWN_VEHICLE",
        }

    # Find every trip for this vehicle whose [start - tolerance, end + tolerance]
    # window contains the toll's timestamp.
    #
    # NOTE: this comparison is done in Python, not as SQL arithmetic
    # (e.g. `Trip.start_time - TOLL_TOLERANCE <= toll.timestamp`), because
    # SQLite stores datetimes as plain text and does not reliably support
    # datetime-minus-interval arithmetic at the SQL level the way a
    # database like PostgreSQL would. Fetching a vehicle's (small) trip
    # list and comparing real Python datetime objects is both correct
    # and portable across database backends.
    vehicle_trips = db.query(Trip).filter(Trip.vehicle_id == toll.vehicle_id).all()
    candidate_trips = [
        t for t in vehicle_trips
        if (t.start_time - TOLL_TOLERANCE) <= toll.timestamp <= (t.end_time + TOLL_TOLERANCE)
    ]

    if len(candidate_trips) == 1:
        # Exactly one confident match -> TRIP level.
        matched_trip = candidate_trips[0]
        return {
            "source_type": "TOLL",
            "source_id": toll.toll_id,
            "amount": toll.amount,
            "attribution_level": "TRIP",
            "trip_id": matched_trip.trip_id,
            "vehicle_id": toll.vehicle_id,
            "reason_code": None,
        }

    # 0 matches (a gap) or 2+ matches (ambiguous overlap) -> VEHICLE level.
    # We never guess between two equally-plausible trips, and we never
    # split a toll between them.
    return {
        "source_type": "TOLL",
        "source_id": toll.toll_id,
        "amount": toll.amount,
        "attribution_level": "VEHICLE",
        "trip_id": None,
        "vehicle_id": toll.vehicle_id,
        "reason_code": None,
    }


def allocate_expense(expense: DriverExpense, db: Session) -> dict:
    """
    Driver expenses carry the weakest signal of the three cost sources.
    Priority: explicit trip_id (if valid) > vehicle_id alone > unattributed.
    See DESIGN.md Section 3 and README.md assumption 5.
    """
    # 1. Explicit trip_id given — validate it actually exists.
    if expense.trip_id:
        trip = db.query(Trip).filter(Trip.trip_id == expense.trip_id).first()
        if trip is not None:
            return {
                "source_type": "DRIVER_EXPENSE",
                "source_id": expense.expense_id,
                "amount": expense.amount,
                "attribution_level": "TRIP",
                "trip_id": trip.trip_id,
                "vehicle_id": trip.vehicle_id,
                "reason_code": None,
            }
        # trip_id given but doesn't reference a real trip -> treat as if it
        # weren't given at all (never trust a broken reference), fall through.

    # 2. No (valid) trip_id — try vehicle_id alone.
    if expense.vehicle_id:
        if _vehicle_exists(db, expense.vehicle_id):
            return {
                "source_type": "DRIVER_EXPENSE",
                "source_id": expense.expense_id,
                "amount": expense.amount,
                "attribution_level": "VEHICLE",
                "trip_id": None,
                "vehicle_id": expense.vehicle_id,
                "reason_code": None,
            }
        else:
            return {
                "source_type": "DRIVER_EXPENSE",
                "source_id": expense.expense_id,
                "amount": expense.amount,
                "attribution_level": "UNATTRIBUTED",
                "trip_id": None,
                "vehicle_id": None,
                "reason_code": "UNKNOWN_VEHICLE",
            }

    # 3. No trip_id, no vehicle_id at all -> cannot resolve.
    # NOTE (documented simplification, see README): we don't currently
    # implement a driver-to-vehicle date-based assignment lookup — if a
    # future iteration adds one, this is where it would be checked before
    # falling back to UNMAPPED_DRIVER.
    return {
        "source_type": "DRIVER_EXPENSE",
        "source_id": expense.expense_id,
        "amount": expense.amount,
        "attribution_level": "UNATTRIBUTED",
        "trip_id": None,
        "vehicle_id": None,
        "reason_code": "UNMAPPED_DRIVER",
    }


def run_allocation(db: Session) -> str:
    """
    Runs a full, fresh allocation over every cost-bearing record in the
    database, and writes the results as a new AllocationRun. Re-running
    this creates a NEW run_id and a full new set of Allocation rows —
    it never mutates or appends to a previous run, which is what makes
    the allocation genuinely re-runnable (see DESIGN.md Section 4).
    """
    run_id = str(uuid.uuid4())
    run = AllocationRun(run_id=run_id, run_at=datetime.now(timezone.utc))
    db.add(run)

    decisions = []

    for fuel in db.query(FuelPurchase).all():
        decisions.append(allocate_fuel(fuel, db))

    for toll in db.query(TollTransaction).all():
        decisions.append(allocate_toll(toll, db))

    for expense in db.query(DriverExpense).all():
        decisions.append(allocate_expense(expense, db))

    for decision in decisions:
        db.add(Allocation(
            allocation_id=str(uuid.uuid4()),
            run_id=run_id,
            **decision,
        ))

    db.commit()
    return run_id
