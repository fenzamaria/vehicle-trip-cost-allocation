# PRD.md — Vehicle Trip Cost Allocation

## Problem Statement

A fleet client wants a **true cost per trip and per vehicle**, drawn from four
data sources — trip logs, fuel purchases, toll transactions, and driver-reported
expenses — none of which reference each other reliably. Costs need to be
allocated to the trip or vehicle they belong to, and anything that can't be
confidently attributed must be flagged honestly rather than forced into a
plausible-looking but fabricated split.

## Goals

1. **Accurate allocation** — every cost-bearing record ends up attributed at the
   most granular level the underlying data actually supports.
2. **Honesty over false precision** — never invent an attribution just to make
   totals balance neatly; fall back to a coarser (but defensible) level, or the
   unattributed pool, instead.
3. **Provable correctness** — the conservation invariant (allocated + unattributed
   = total recorded spend) must be exact and verifiable, not just claimed.
4. **Re-runnability** — running the allocation process again must never corrupt,
   duplicate, or drift from a previous run's correctness.

## Non-Goals (Explicitly Out of Scope)

- Live/external data ingestion — all data is simulated, per team clarification.
- Distance-proportional fuel splitting within a fill period (see DESIGN.md
  Section 3 for the reasoning).
- Full user account management (signup, password reset) — only a minimal
  role-based access pattern was designed (not yet implemented — see DESIGN.md
  Future Improvements).
- Multi-currency support.

## Users / Stakeholders

- **Fleet operations / finance teams** — the ultimate consumers of accurate
  cost-per-trip and cost-per-vehicle figures, for budgeting and reporting.
- **An evaluator/reviewer** (in the context of this exercise) — needs to be able
  to verify the allocation policy is sound, the conservation invariant holds, and
  the system is re-runnable and testable.

## Functional Requirements

| # | Requirement | Status |
|---|---|---|
| 1 | Ingest all four data sources | ✅ Implemented (`ingest.py`) |
| 2 | Allocate each cost-bearing record to TRIP, VEHICLE, or UNATTRIBUTED | ✅ Implemented (`app/services/allocation.py`) |
| 3 | Cost-per-trip query API | ✅ Implemented (`GET /costs/trip/{trip_id}`) |
| 4 | Cost-per-vehicle query API | ✅ Implemented (`GET /costs/vehicle/{vehicle_id}`) |
| 5 | Unattributed pool with reason codes | ✅ Implemented (`GET /unattributed`) |
| 6 | Re-runnable allocation | ✅ Implemented and tested (`tests/test_rerunnability.py`) |
| 7 | Conservation invariant provable | ✅ Implemented and tested (3 tests + live `/reconciliation` endpoint) |
| 8 | Role-based access control | ⏸ Deferred (designed, not built — see Future Improvements) |

## Success Criteria

- All 8 edge cases named in the brief produce the correct, predicted attribution
  (verified — see `tests/test_edge_cases.py`, all passing).
- The conservation invariant holds exactly on the seed dataset: total allocated
  (7675.00) + unattributed (170.00) = total recorded spend (7845.00).
- Re-running the allocation engine produces identical per-record results across
  runs (verified — `tests/test_rerunnability.py`).
- Every design decision that trades off precision for honesty (e.g., fuel never
  split across trips, ambiguous tolls falling back to VEHICLE level) is explicitly
  documented with its rationale, not left implicit in code.

## Key Design Trade-off (the core of the exercise)

The central tension this project resolves: a naive system could force every cost
down to TRIP-level attribution to make reporting look complete, but that requires
guessing in scenarios the data doesn't support (e.g., splitting a fuel purchase
across multiple trips with no odometer data to justify the split). This system
instead uses a **three-level attribution model** (TRIP → VEHICLE → UNATTRIBUTED),
so precision is never claimed beyond what the source data actually justifies —
see DESIGN.md Section 6 for the full argument.
