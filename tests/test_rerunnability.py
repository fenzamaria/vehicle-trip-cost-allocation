"""
"Re-runnable allocation" is a distinct requirement from correctness — even
if the allocation logic is perfect, the SYSTEM could still be broken if
running it twice corrupts or duplicates results. These tests check that
specifically.
"""
from app.models import Allocation, AllocationRun
from app.services.allocation import run_allocation


def test_running_twice_creates_two_separate_runs(db):
    run_id_1 = run_allocation(db)
    run_id_2 = run_allocation(db)

    assert run_id_1 != run_id_2
    assert db.query(AllocationRun).count() == 2


def test_running_twice_gives_identical_results_per_run(db):
    """Each run, independently, should allocate every record the same way —
    re-running isn't supposed to change the OUTCOME, just produce a fresh
    copy of it under a new run_id."""
    run_id_1 = run_allocation(db)
    run_id_2 = run_allocation(db)

    run_1_allocations = {
        a.source_id: (a.attribution_level, a.trip_id, a.vehicle_id, a.reason_code)
        for a in db.query(Allocation).filter(Allocation.run_id == run_id_1).all()
    }
    run_2_allocations = {
        a.source_id: (a.attribution_level, a.trip_id, a.vehicle_id, a.reason_code)
        for a in db.query(Allocation).filter(Allocation.run_id == run_id_2).all()
    }

    assert run_1_allocations == run_2_allocations


def test_running_twice_does_not_double_count_within_a_single_run(db):
    """Each individual run's total should still match expected spend —
    re-running shouldn't cause amounts to accumulate across runs."""
    from app.models import FuelPurchase, TollTransaction, DriverExpense

    expected_total = (
        sum(f.amount for f in db.query(FuelPurchase).all())
        + sum(t.amount for t in db.query(TollTransaction).all())
        + sum(e.amount for e in db.query(DriverExpense).all())
    )

    run_id_1 = run_allocation(db)
    run_allocation(db)  # run again, discard the id — just checking run 1 is unaffected

    run_1_total = sum(
        a.amount for a in db.query(Allocation).filter(Allocation.run_id == run_id_1).all()
    )
    assert run_1_total == expected_total