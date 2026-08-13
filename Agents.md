# Agents.md — AI-Assisted Development Workflow

This project was built with AI assistance (Claude), following a deliberate
**plan-then-execute** pattern rather than generating code first and retrofitting
a rationale afterward. This document is an honest account of where AI tooling
accelerated the work, and where the actual thinking had to be done manually.

## Workflow Pattern

1. **Plan Mode (design before code):** the allocation policy — the three-level
   TRIP/VEHICLE/UNATTRIBUTED attribution model, the reasoning for never
   splitting fuel across trips, the toll tolerance/ambiguity handling — was
   reasoned through explicitly and documented in `DESIGN.md` *before* any
   implementation code was written. This was a deliberate choice: the brief's
   core test is the allocation policy and its rationale, not the code itself,
   so getting the reasoning right first mattered more than moving fast into code.

2. **Mentor review as a checkpoint:** after the initial design docs were
   submitted, mentor feedback identified three real issues — the conservation
   invariant incorrectly including trip logs (which carry no monetary amount),
   missing handling for a toll matching two trips within tolerance, and using
   `float` instead of `decimal` for monetary fields. All three were genuine
   design gaps, not documentation polish — fixing them changed both the docs
   and the eventual implementation.

3. **Agent Mode (implementation):** once the design was settled, AI tooling was
   used to scaffold the SQLAlchemy models, the ingestion pipeline, the
   allocation engine, the query service, the FastAPI routes, and the Pytest
   suite — each piece built incrementally and verified by actually running it
   against the seed data before moving to the next piece, rather than
   generating the whole system at once and debugging at the end.

## Where AI Accelerated the Work

- Boilerplate: SQLAlchemy model definitions, FastAPI route wiring, Pytest
  fixture setup.
- Translating an already-decided policy into code (e.g., once "ambiguous toll →
  VEHICLE level" was decided, writing the match-count logic was mechanical).
- Generating the seed data JSON files once the edge-case table (which records
  need to exist, and why) was already specified.

## Where Manual Reasoning Was Required (Not Just AI Output)

- **The core three-level attribution model itself** — deciding TRIP vs VEHICLE
  vs UNATTRIBUTED wasn't a coding decision, it was the actual answer to the
  brief's central question ("why not spread costs evenly to force a balance").
- **Catching and fixing a real bug during testing:** the toll-tolerance query
  was initially written as SQL-level datetime arithmetic
  (`Trip.start_time - TOLL_TOLERANCE <= toll.timestamp`), which silently
  returned zero matches against SQLite (which stores datetimes as text and
  doesn't reliably support this arithmetic at the SQL level). This wasn't
  caught by inspection — it was caught by actually running the engine against
  known seed data and noticing `TL1` (which should have matched T1 directly)
  came back as an ambiguous VEHICLE-level result instead of TRIP-level. The
  fix (moving the comparison into Python) required understanding *why* the
  original approach failed, not just applying a suggested patch.
- **Incorporating mentor feedback correctly** — e.g., recognizing that "trip
  logs are reference data" meant fixing the invariant definition in three
  separate places (DESIGN.md, the test's expected-total calculation, and the
  reconciliation endpoint's documentation) consistently, not just in the one
  place it was first flagged.
- **The 404 vs. zero-cost fix** — recognizing that "total_cost: 0" for a fake
  trip ID and "total_cost: 0" for a real trip with no attributed cost look
  identical in a response but mean genuinely different things, and that this
  needed a real distinction (a `NotFoundError` raised at the service layer,
  translated to HTTP 404 at the route layer) rather than a documentation note
  alone.

## Honest Note

Given prior experience where AI-generated project code wasn't fully understood
at defense time, this project was deliberately built with a habit of tracing
through actual results against hand-predicted expected values at every step
(the `schemas/seed_data_mapping.md` table exists specifically for this reason)
— rather than trusting that code "looks right" without independently verifying it.
