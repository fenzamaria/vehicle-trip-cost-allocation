# Seed Data — Edge Case Mapping

This maps every record in `data/seed/` to the specific edge case it's designed to
exercise, per the brief and the table in README.md.

## Vehicles & Drivers (reference)
- `V1` — has trips, fuel, tolls, expenses (the "normal" vehicle)
- `V2` — has a fuel purchase but zero recorded trips (edge case 6)
- `V9` — referenced by a toll transaction but does NOT exist in `vehicles.json`
  (edge case 7 — deliberately not added here)
- `D1` — has expenses linked to `V1`
- `D2` — never linked to any vehicle (edge case 5)

## Trips
- `T1`: 2026-01-01 08:00–09:00 (V1)
- `T2`: 2026-01-01 09:05–10:00 (V1) — starts only 5 minutes after T1 ends,
  **deliberately close**, to create the ambiguous-toll overlap case
- `T3`: 2026-01-02 08:00–09:00 (V1)

## Edge Case → Record Mapping

| # | Edge case | Record(s) | Expected result |
|---|---|---|---|
| 1 | Fuel purchase spans multiple trips | `F1` (2026-01-01 07:30, before both T1 and T2, next fuel purchase is F2 the following day) | VEHICLE-level, fill period covers T1 + T2 |
| 2 | Toll falls in a genuine gap | `TL3` (13:00, hours away from any trip) | VEHICLE-level, no reason code (vehicle known) |
| 3 | Toll falls cleanly inside a trip (positive case) | `TL1` (08:30, inside T1's 08:00–09:00 window) | TRIP-level, attributed to T1 |
| 4 | Driver expense: vehicle+date only, no trip_id | `DE2` (V1, 2026-01-01, trip_id null) | VEHICLE-level, not inferred down to T1 or T2 |
| 5 | Driver expense fully unresolvable | `DE3` (D2 is unmapped, no vehicle_id, no trip_id) | UNATTRIBUTED, reason_code = `UNMAPPED_DRIVER` |
| 6 | Fuel purchase, vehicle has no trip that day | `F3` (V2, 2026-01-05 — V2 has zero trips in the dataset) | VEHICLE-level, not unattributed |
| 7 | Cost references an unknown vehicle | `TL4` (vehicle_id `V9`, not present in `vehicles.json`) | UNATTRIBUTED, reason_code = `UNKNOWN_VEHICLE` |
| 8 | Toll ambiguous between two trips | `TL2` (09:02 — within 5-min tolerance of both T1's end at 09:00 and T2's start at 09:05) | VEHICLE-level, not arbitrarily assigned to either |

## Bonus: explicit trip reference (baseline correctness check)
- `DE1` (D1, V1, trip_id explicitly `T1`) → TRIP-level, attributed to T1 directly,
  no inference needed. This is the simplest possible case and a good first test
  to get passing before tackling the harder ones above.

## Verifying the conservation invariant with this dataset
Total recorded spend (fuel + tolls + driver expenses only, per DESIGN.md Section 4):
- Fuel: 3200.00 + 1800.00 + 2100.00 = **7100.00**
- Tolls: 90.00 + 60.00 + 75.00 + 50.00 = **275.00**
- Driver expenses: 150.00 + 200.00 + 120.00 = **470.00**
- **Total: 7845.00**

After running the allocation engine, `SUM(all Allocation.amount rows for the run)`
must equal exactly `7845.00` — this is the number your conservation-invariant test
should assert against.
