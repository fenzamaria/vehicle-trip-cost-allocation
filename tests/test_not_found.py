"""
Tests for the NotFoundError fix: querying a nonexistent trip/vehicle
should raise, distinct from a real trip/vehicle with legitimately zero
attributed cost.
"""
import pytest

from app.services import query as query_service
from app.services.allocation import run_allocation


def test_unknown_trip_id_raises_not_found(db):
    run_allocation(db)
    with pytest.raises(query_service.NotFoundError):
        query_service.get_cost_for_trip(db, "T_DOES_NOT_EXIST")


def test_unknown_vehicle_id_raises_not_found(db):
    run_allocation(db)
    with pytest.raises(query_service.NotFoundError):
        query_service.get_cost_for_vehicle(db, "V_DOES_NOT_EXIST")


def test_real_trip_with_zero_cost_does_not_raise(db):
    """T3 exists but has no toll/expense allocations tied to it in the
    seed data -> should return a valid 0, not raise."""
    run_allocation(db)
    result = query_service.get_cost_for_trip(db, "T3")
    assert result["total_cost"] == 0
