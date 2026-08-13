"""
API Routes — deliberately thin (per Architecture.md Section 1): each
route just validates the request, calls the right service, and shapes
the response. No business logic lives here.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import query as query_service
from app.services.allocation import run_allocation

router = APIRouter()


@router.post("/allocations/run")
def trigger_allocation_run(db: Session = Depends(get_db)):
    """Runs a fresh, complete allocation over all current source data."""
    run_id = run_allocation(db)
    return {"run_id": run_id, "status": "completed"}


@router.get("/costs/trip/{trip_id}")
def cost_per_trip(trip_id: str, db: Session = Depends(get_db)):
    try:
        return query_service.get_cost_for_trip(db, trip_id)
    except query_service.NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/costs/vehicle/{vehicle_id}")
def cost_per_vehicle(vehicle_id: str, db: Session = Depends(get_db)):
    try:
        return query_service.get_cost_for_vehicle(db, vehicle_id)
    except query_service.NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/unattributed")
def unattributed_pool(db: Session = Depends(get_db)):
    return query_service.get_unattributed_pool(db)


@router.get("/reconciliation")
def reconciliation_summary(db: Session = Depends(get_db)):
    """Shows the conservation invariant directly: attributed + unattributed
    totals for the latest run, so it's visibly inspectable, not just
    something proven in a test."""
    return query_service.get_reconciliation_summary(db)
