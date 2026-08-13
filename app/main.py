"""
Main FastAPI application entry point.
Run with: uvicorn app.main:app --reload
"""
from fastapi import FastAPI

from app.database import Base, engine
from app.routes.allocation_routes import router as allocation_router

# Ensure all tables exist on startup (safe no-op if they already do).
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Vehicle Trip Cost Allocation",
    description=(
        "Allocates recorded costs (fuel, tolls, driver expenses) to the "
        "trip or vehicle they belong to, and honestly flags anything it "
        "cannot confidently attribute."
    ),
)

app.include_router(allocation_router)


@app.get("/")
def root():
    return {"message": "Vehicle Trip Cost Allocation API. See /docs for the interactive API explorer."}
