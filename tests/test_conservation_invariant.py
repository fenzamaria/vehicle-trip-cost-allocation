"""
The conservation invariant is the single non-negotiable rule from the
brief: total allocated cost + unattributed pool must equal total
recorded spend across the three cost-bearing sources, exactly.

This test doesn't just check a plausible-looking number — it computes
the expected total independently, from the source tables directly, and
compares it against what the allocation engine actually produced.
"""
from decimal import Decimal

from app.models import FuelPurchase, TollTransaction, DriverExpense, Allocation
from app.services.allocation import run_allocation


def test_conservation_invariant_holds(db):
    # Compute the expected total the SAME way DESIGN.md Section 4 defines
    # it: sum of the three cost-bearing sources only (trip logs excluded,
    # since they carry no `amount` field).
    expected_total = (
        sum(f.amount for f in db.query(FuelPurchase).all())
        + sum(t.amount for t in db.query(TollTransaction).all())
        + sum(e.amount for e in db.query(DriverExpense).all())
    )

    run_id = run_allocation(db)

    allocations = db.query(Allocation).filter(Allocation.run_id == run_id).all()
    actual_total = sum(a.amount for a in allocations)

    assert actual_total == expected_total, (
        f"Conservation invariant violated: allocated {actual_total}, "
        f"but total recorded spend was {expected_total}"
    )


def test_conservation_invariant_matches_known_seed_total(db):
    """
    A second, independent check against the hand-computed total documented
    in schemas/seed_data_mapping.md — catches the case where BOTH the
    engine and the "expected_total" computation above share the same bug.
    """
    run_id = run_allocation(db)
    allocations = db.query(Allocation).filter(Allocation.run_id == run_id).all()
    total = sum(a.amount for a in allocations)

    assert total == Decimal("7845.00")


def test_every_source_record_allocated_exactly_once(db):
    """
    Verifies the rule that makes the conservation invariant provable:
    every source record produces exactly one Allocation row, never zero,
    never more than one.
    """
    run_id = run_allocation(db)
    allocations = db.query(Allocation).filter(Allocation.run_id == run_id).all()

    fuel_count = db.query(FuelPurchase).count()
    toll_count = db.query(TollTransaction).count()
    expense_count = db.query(DriverExpense).count()
    expected_allocation_count = fuel_count + toll_count + expense_count

    assert len(allocations) == expected_allocation_count

    # Also check for true duplicates: no (source_type, source_id) pair
    # should appear more than once within a single run.
    seen = set()
    for a in allocations:
        key = (a.source_type, a.source_id)
        assert key not in seen, f"Duplicate allocation found for {key}"
        seen.add(key)
