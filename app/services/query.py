"""
QueryService — reads from the Allocation table only (never recomputes
live), so query performance is independent of how complex the
allocation logic is. See Architecture.md Section 4.

All queries operate against the LATEST allocation run by default —
"latest" is determined by the most recent run_at timestamp.
"""
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models import Allocation, AllocationRun


def get_latest_run_id(db: Session) -> str | None:
    latest = db.query(AllocationRun).order_by(AllocationRun.run_at.desc()).first()
    return latest.run_id if latest else None


def get_cost_for_trip(db: Session, trip_id: str, run_id: str | None = None) -> dict:
    """
    Cost for a specific trip = sum of only TRIP-level allocations tied to
    it. Deliberately does NOT include VEHICLE-level costs, even ones for
    the same vehicle — see DESIGN.md Section 2: a vehicle's total cost is
    allowed to exceed the sum of its trips' costs, by design.
    """
    run_id = run_id or get_latest_run_id(db)
    total = (
        db.query(func.coalesce(func.sum(Allocation.amount), 0))
        .filter(
            Allocation.run_id == run_id,
            Allocation.attribution_level == "TRIP",
            Allocation.trip_id == trip_id,
        )
        .scalar()
    )
    return {"trip_id": trip_id, "run_id": run_id, "total_cost": total}


def get_cost_for_vehicle(db: Session, vehicle_id: str, run_id: str | None = None) -> dict:
    """
    Cost for a vehicle = sum of BOTH TRIP-level AND VEHICLE-level
    allocations for that vehicle — a vehicle's cost includes everything
    confidently tied to it, whether or not it was narrowed down to a
    specific trip. See DESIGN.md Section 2.
    """
    run_id = run_id or get_latest_run_id(db)
    total = (
        db.query(func.coalesce(func.sum(Allocation.amount), 0))
        .filter(
            Allocation.run_id == run_id,
            Allocation.attribution_level.in_(["TRIP", "VEHICLE"]),
            Allocation.vehicle_id == vehicle_id,
        )
        .scalar()
    )
    return {"vehicle_id": vehicle_id, "run_id": run_id, "total_cost": total}


def get_unattributed_pool(db: Session, run_id: str | None = None) -> list[dict]:
    """
    Every record that couldn't be confidently attributed even to a known
    vehicle, with its reason code — queryable, never silently dropped.
    See DESIGN.md Section 5 for the reason code taxonomy.
    """
    run_id = run_id or get_latest_run_id(db)
    records = (
        db.query(Allocation)
        .filter(Allocation.run_id == run_id, Allocation.attribution_level == "UNATTRIBUTED")
        .all()
    )
    return [
        {
            "source_type": r.source_type,
            "source_id": r.source_id,
            "amount": r.amount,
            "reason_code": r.reason_code,
        }
        for r in records
    ]


def get_reconciliation_summary(db: Session, run_id: str | None = None) -> dict:
    """
    A direct, queryable proof of the conservation invariant for a given
    run — total allocated (TRIP + VEHICLE) + unattributed pool, broken
    out explicitly so it's visible, not just asserted in a test.
    """
    run_id = run_id or get_latest_run_id(db)

    trip_and_vehicle_total = (
        db.query(func.coalesce(func.sum(Allocation.amount), 0))
        .filter(Allocation.run_id == run_id, Allocation.attribution_level.in_(["TRIP", "VEHICLE"]))
        .scalar()
    )
    unattributed_total = (
        db.query(func.coalesce(func.sum(Allocation.amount), 0))
        .filter(Allocation.run_id == run_id, Allocation.attribution_level == "UNATTRIBUTED")
        .scalar()
    )

    return {
        "run_id": run_id,
        "attributed_total": trip_and_vehicle_total,
        "unattributed_total": unattributed_total,
        "grand_total": trip_and_vehicle_total + unattributed_total,
    }
