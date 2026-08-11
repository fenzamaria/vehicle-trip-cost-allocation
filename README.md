# Vehicle Trip Cost Allocation

A service that allocates recorded costs (trip logs, fuel purchases, toll transactions,
driver-reported expenses) to the trip or vehicle they belong to — and honestly flags
what it cannot confidently attribute, rather than guessing.

## Key Assumptions

1. **Vehicles and trips are the anchor entities.** Every allocation attempt resolves
   toward a known `vehicle_id`; trips are windows in time bounded by `start_time` and
   `end_time` for a specific vehicle.
2. **Attribution has three levels of confidence, not two.** A cost can be attributed
   to a specific TRIP (highest confidence), to a VEHICLE only (medium confidence — we
   know who, not which trip), or land in the UNATTRIBUTED pool (we cannot confidently
   tie it to a known vehicle at all). See `DESIGN.md` for the full rationale.
3. **A toll timestamp is matched to a trip if it falls within `[trip.start_time,
   trip.end_time]`, extended by a small fixed tolerance window (default: 5 minutes)**
   to account for minor timestamp drift between systems. This tolerance is an explicit,
   documented assumption — not a silent guess. If a toll timestamp falls in a genuine
   gap between two trips for the same vehicle, it is attributed at the VEHICLE level
   (we know the vehicle, not the trip), never split or guessed between the two trips.
4. **Fuel purchases are never split across trips.** A single fuel purchase is attributed
   to the VEHICLE level, scoped to the fill period it falls within (the window between
   this purchase and the vehicle's next fuel purchase, or its last known trip, if
   no distance/odometer data exists to justify a more granular, defensible split).
5. **Driver-reported expenses** are attributed to a TRIP only if the expense record
   references a `trip_id` directly. If it references only a `vehicle_id` and date, and
   exactly one trip exists for that vehicle on that date, it's attributed at VEHICLE
   level for that date (not guessed down to the single trip, since date-level matching
   isn't the same confidence as an explicit trip reference). If no vehicle can be
   resolved at all (e.g., unmapped driver, no trip/vehicle reference), it goes to the
   UNATTRIBUTED pool.
6. **A fuel swipe for a vehicle with no recorded trip that day** is still a legitimate
   VEHICLE-level cost (the vehicle existed and incurred a cost, even if idle or
   pre-trip) — it is NOT pushed to the unattributed pool merely for lacking a same-day
   trip. Unattributed is reserved for cases where the *vehicle itself* can't be resolved.

## Technologies Used

- **Python 3.11+**
- **FastAPI** — API routes and request/response validation
- **SQLAlchemy** — ORM layer over SQLite
- **SQLite** — embedded database, zero infra setup, ideal for a known/seeded test dataset
- **Pytest** — unit and integration tests, including the conservation-invariant check

## Setup & Run Instructions

```bash
# 1. Clone and enter the project
git clone <repo-url>
cd vehicle-trip-cost-allocation

# 2. Create a virtual environment and install dependencies
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 3. Set up environment secrets (JWT signing key, etc.)
cp .env.example .env            # then fill in values

# 4. Ingest the four source files into the database
python ingest.py --data-dir ./data/seed
# (swap --data-dir to point at any other folder matching the schemas
#  in schemas/ to test against different data)

# 5. Run the allocation engine
python run_allocation.py

# 6. Run the test suite (includes the conservation-invariant assertion)
pytest

# 7. Start the API server
uvicorn app.main:app --reload

# 8. API available at http://localhost:8000/docs (interactive Swagger UI)
#    Log in with a seeded Admin or Viewer account (see data/seed/users.json)
#    to obtain a token for protected endpoints.
```

## Scope Limits (Intentionally Left Out, and Why)

- **No proportional distance-based fuel splitting**, even though trip `distance_km`
  is present in the seed data. I considered allocating fuel proportionally to distance
  within a fill period, but decided against it for this submission: it would require
  assuming uniform fuel efficiency across trips, which isn't demonstrated by the data
  — a plausible-looking number that isn't actually justified. Flagged as a genuine,
  reasoned trade-off in `DESIGN.md`, not an oversight.
- **No multi-currency handling** — all costs assumed to be in a single currency.
- **Authentication is intentionally minimal (role-based, not full account
  management)** — the problem brief itself doesn't specify a user model, but since
  the API exposes real financial data (cost-per-vehicle, cost-per-trip), I added a
  lightweight Admin/Viewer role distinction rather than leaving the API fully open.
  Full account management (signup flows, password reset, etc.) is out of scope as
  unrelated to the core allocation problem.

## Data Simulation

Per clarification from the evaluators, all four feeds are simulated/generated —
no live or external data sources are used. The four sources (trip logs, fuel
purchases, toll transactions, driver expenses) are represented as structured JSON
files (one per source type, schema documented in `schemas/`), loaded via a real
ingestion layer rather than hardcoded directly in application code.

The simulated data is deliberately constructed to include every edge case named in
the brief, so each allocation policy path is actually exercised and verifiable, not
just theoretically correct:

| Edge case | Included in simulated data |
|---|---|
| Fuel purchase spanning multiple trips | ✓ at least one multi-trip fill period |
| Toll timestamp falling in a genuine gap between trips | ✓ |
| Toll timestamp falling cleanly inside a trip (positive case) | ✓ |
| Driver expense with vehicle+date only, no trip_id | ✓ |
| Driver expense fully unresolvable (no vehicle/trip reference) | ✓ |
| Fuel purchase for a vehicle with no recorded trip that day | ✓ |
| Cost record referencing an unknown/nonexistent vehicle | ✓ |
| Toll timestamp ambiguous between two trips (within tolerance of both) | ✓ |

This table doubles as the foundation of the test plan: each row corresponds to a
concrete test case with a known, verifiable expected outcome.
