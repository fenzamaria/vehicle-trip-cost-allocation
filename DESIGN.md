# Design Document — Vehicle Trip Cost Allocation

## 1. Architecture Overview

```
┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│  trips.json  │   │   fuel.json  │   │   tolls.json │   │ expenses.json │
│ (trip logs)  │   │(fuel purchase)│  │(toll transact)│  │(driver expense)│
└──────┬───────┘   └──────┬───────┘   └──────┬───────┘   └──────┬───────┘
       │                  │                  │                  │
       ▼                  ▼                  ▼                  ▼
       └──────────────────┴────────┬─────────┴──────────────────┘
                             Ingestion Layer
                    (reads + validates against schemas/)
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │  Allocation Engine   │
                         │ (one policy per      │
                         │  cost-source type)   │
                         └──────────┬───────────┘
                                    ▼
                    ┌───────────────────────────────┐
                    │        Allocations Table        │
                    │  (source, amount, level,        │
                    │   trip_id / vehicle_id,          │
                    │   reason_code, run_id)           │
                    └───────────────┬───────────────┘
                                    ▼
                 ┌──────────────────────────────────────┐
                 │  Query API: cost-per-trip,            │
                 │  cost-per-vehicle, unattributed pool  │
                 └──────────────────────────────────────┘
```

**Stack:** Python, FastAPI, SQLite (via SQLAlchemy), pytest.

**Why this shape:** each cost-source type gets its own, independently reasoned
allocation policy function — rather than one generic "try to match a trip" routine.
This is deliberate: the four sources have genuinely different reliability
characteristics (a toll timestamp is a strong signal; a driver expense with no
reference is a weak one), and collapsing them into one generic matcher would hide
that difference and encourage exactly the kind of forced, uniform attribution the
brief warns against.

## 2. The Core Design Decision: Three Attribution Levels, Not Two

The brief's central tension is: *attribute confidently, or admit you can't — never
guess a fake middle ground.* A naive binary model ("attributed to a trip" vs.
"unattributed") forces bad choices: either you invent a trip-level split you can't
justify (e.g., spreading a fuel purchase evenly across trips), or you dump genuinely
resolvable costs (like "this vehicle definitely bought this fuel") into a pool meant
for costs we can't explain at all — losing real information either way.

**Resolution: three levels of attribution confidence:**

| Level | Meaning | Example |
|---|---|---|
| **TRIP** | Confidently tied to one specific trip | Toll timestamp falls cleanly inside a trip's time window |
| **VEHICLE** | Confidently tied to a known vehicle, not a single trip | Fuel purchase spanning a multi-trip fill period |
| **UNATTRIBUTED** | Cannot confidently tie to even a known vehicle | Driver expense with no trip/vehicle reference and an unmapped driver |

`cost-per-vehicle` sums both TRIP-level and VEHICLE-level costs for that vehicle.
`cost-per-trip` sums only TRIP-level costs for that trip. This means a vehicle's
total cost is always ≥ the sum of its trips' costs — an intentional, documented
property, not a bug: it reflects that some real costs (like fuel) are genuinely
vehicle-scoped, not trip-scoped, and forcing them down to trip level would be
false precision.

## 3. Allocation Policy Per Cost Type, With Rationale

### Fuel Purchases → VEHICLE level (never split across trips)
**Rationale:** a tank spans several trips; without per-trip odometer/fuel-consumption
data, any split across trips is a fabricated number that merely *looks* precise.
Attributing at VEHICLE level, scoped to the fill period (bounded by the next fuel
purchase for that vehicle), is the most granular attribution the data actually
supports.

### Toll Transactions → TRIP level (with a bounded tolerance), else VEHICLE level
**Rationale:** a toll timestamp is a strong, specific temporal signal — if it falls
within `[trip.start_time, trip.end_time]` (extended by a small, explicitly documented
tolerance for timing drift), attributing it to that trip is well-justified. If it
falls in a genuine gap between two trips for the same vehicle, we do **not** guess
which of the two trips it belongs to — we fall back to VEHICLE level. We never split
a toll between two candidate trips.

### Driver-Reported Expenses → TRIP level (only if explicit trip_id given), else
VEHICLE level (if vehicle/date resolvable), else UNATTRIBUTED
**Rationale:** these carry the weakest signal of the four sources. An explicit
`trip_id` on the record is trusted directly. A vehicle + date alone is NOT treated
as equivalent to an explicit trip reference, even if only one trip happened that day
— because "happened to be the only trip that day" is a coincidence of the seed data,
not a real link the source data asserts. Attributing it to VEHICLE level is the
honest granularity; forcing it down to TRIP level would be an inference, not a fact
present in the source.

### Fuel Swipe, No Recorded Trip That Day → VEHICLE level (not unattributed)
**Rationale:** the vehicle is known and the cost is real (e.g., pre-trip refueling,
idle-day top-up) — the absence of a same-day trip doesn't make the *vehicle*
unknown, so this does not belong in the unattributed pool. It's correctly captured
in `cost-per-vehicle`, just absent from any specific `cost-per-trip`.

## 4. The Conservation Invariant

**Invariant:** `SUM(all TRIP-level allocations) + SUM(all VEHICLE-level allocations)
+ SUM(unattributed pool) == SUM(total recorded spend across all four sources)`,
exactly, per allocation run.

**How it's asserted:**
- Every source record is allocated **exactly once** per run — the allocation engine
  processes each source record independently and assigns it to precisely one
  destination (a trip, a vehicle, or the unattributed pool), never zero, never more
  than one.
- After each run, a reconciliation check sums all `Allocations` rows for that
  `run_id` and compares it against the sum of all four source tables' amounts. This
  is implemented as an automated test (`test_conservation_invariant`), not just a
  manual spot-check — it runs against the seed data on every test execution and
  fails loudly if the totals diverge by even a rounding unit.
- **Re-runnability:** each allocation run is tagged with a `run_id`. Re-running the
  engine does not append to prior results — it computes a fresh, complete allocation
  from the four source tables (a pure function of the source data), and the API
  serves the latest run. This guarantees re-running never double-counts or drifts,
  since nothing is incrementally mutated.

## 5. Unattributed Pool — Reason Code Taxonomy

| Reason Code | Meaning |
|---|---|
| `UNKNOWN_VEHICLE` | Source record references a vehicle ID not present in the vehicle registry |
| `UNMAPPED_DRIVER` | Driver expense references a driver with no vehicle assignment for that date, and no trip/vehicle reference given |
| `NO_TEMPORAL_ANCHOR` | Source record lacks any timestamp/date to anchor attribution at all |

Each unattributed record retains its original source type, amount, and reason code
— it is queryable via the API (`GET /unattributed`), never silently dropped, exactly
per the brief's requirement that the books balance without discarding anything.

## 6. Why Costs Are Not Spread Evenly to Force a Balance

Spreading a cost evenly across candidate trips (e.g., dividing a fuel purchase by
the number of trips in its fill period) would make the books arithmetically balance
— but it would be **false precision presented as fact**. It implies "this is what
each trip actually cost," when in reality it's a fabricated average with no basis in
the source data (trips vary in distance and duration; fuel consumption isn't
uniform). This exercise's stated goal is a *true* cost per trip/vehicle — an evenly
spread number isn't true, it's merely convenient. The three-level attribution model
achieves the same conservation invariant (the books still balance exactly) without
ever inventing a number the data doesn't support — the "cost" of that honesty is
that `cost-per-trip` is sometimes incomplete by design, with the gap visible and
explained (at VEHICLE level or in the unattributed pool) rather than hidden inside
a falsely precise trip-level figure.

## 7. Known Trade-offs

- Distance-proportional fuel splitting within a fill period was considered and
  rejected — see README scope limits for the full reasoning.
- Toll tolerance window (5 min) is a fixed constant, not currently configurable
  per data source — flagged as a future improvement.
