"""
AllocationRun and Allocation — these are the OUTPUT of the allocation engine,
not raw input data. Every time the engine runs, it creates one AllocationRun
row, and one Allocation row PER source record it processed (fuel purchase,
toll, or driver expense) — this "exactly one row per source record" rule is
what makes the conservation invariant provable rather than just hoped-for.
"""
from sqlalchemy import Column, String, DateTime, Numeric, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class AllocationRun(Base):
    __tablename__ = "allocation_runs"

    run_id = Column(String, primary_key=True)
    run_at = Column(DateTime, nullable=False)

    allocations = relationship("Allocation", back_populates="run")


class Allocation(Base):
    __tablename__ = "allocations"

    allocation_id = Column(String, primary_key=True)
    run_id = Column(String, ForeignKey("allocation_runs.run_id"), nullable=False)

    # Which original record this allocation came from, and what type it was.
    source_type = Column(String, nullable=False)  # "FUEL" / "TOLL" / "DRIVER_EXPENSE"
    source_id = Column(String, nullable=False)     # the original fuel_id/toll_id/expense_id

    amount = Column(Numeric(10, 2), nullable=False)

    # TRIP, VEHICLE, or UNATTRIBUTED — see DESIGN.md Section 2 for the full
    # rationale behind these three levels.
    attribution_level = Column(String, nullable=False)

    trip_id = Column(String, ForeignKey("trips.trip_id"), nullable=True)
    vehicle_id = Column(String, ForeignKey("vehicles.vehicle_id"), nullable=True)

    # Only set when attribution_level == "UNATTRIBUTED" — the taxonomy from
    # DESIGN.md Section 5 (UNKNOWN_VEHICLE, UNMAPPED_DRIVER, NO_TEMPORAL_ANCHOR)
    reason_code = Column(String, nullable=True)

    run = relationship("AllocationRun", back_populates="allocations")
