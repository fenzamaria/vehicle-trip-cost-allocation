# Skills.md — Skills Demonstrated, Mapped to Evaluation Areas

A direct map from each evaluation area to where it's evidenced in this project,
so it's easy to verify coverage rather than searching for it.

## 1. System Design & Architecture
- Monolithic, layered structure (Routes → Controllers → Services → ORM) —
  `Architecture.md` Section 1
- ER Diagram (Mermaid) — `Architecture.md` Section 2
- State Flow Diagram (Mermaid) — `Architecture.md` Section 3
- Relationships & dependencies between components — `Architecture.md` Section 4
- AI-assisted / agentic development workflow — `Agents.md`

## 2. Backend Development
- API routes: `POST /allocations/run`, `GET /costs/trip/{id}`,
  `GET /costs/vehicle/{id}`, `GET /unattributed`, `GET /reconciliation` —
  `app/routes/allocation_routes.py`
- Controllers kept thin (no business logic) — same file, delegates to services
- Services (business logic): `app/services/allocation.py` (the allocation
  engine), `app/services/query.py` (cost queries, reconciliation)
- Database code / ORM: `app/models/` (SQLAlchemy models), `app/database.py`
  (connection/session setup)
- Role-based login: designed (`Architecture.md` Section 6) but **not
  implemented** — see `DESIGN.md` Future Improvements for the honest reason
  (deprioritized in favor of core correctness given time constraints)

## 3. Database & ORM
- SQLAlchemy ORM used throughout `app/models/`
- SQLite as the database backend
- Schema documented via the ER diagram (`Architecture.md`) and the seed data
  schema mapping (`schemas/seed_data_mapping.md`)
- Relationships: one-to-many (Vehicle→Trip, Vehicle→FuelPurchase, etc.),
  nullable foreign keys where the domain genuinely requires it
  (`DriverExpense.vehicle_id`, `DriverExpense.trip_id`)
- Real DBMS-level bug found and fixed: SQLite's lack of reliable datetime
  arithmetic at the SQL level — see `Agents.md` for the full story

## 4. Security
- Password hashing (bcrypt) and JWT sessions — designed, documented in
  `Architecture.md` Section 6, not yet implemented (honest scope note, not
  hidden)
- Secrets management: `.env` / `.env.example` pattern in place regardless of
  auth status, since secrets hygiene was treated as cost-free to set up early

## 5. Technologies Used
Python, FastAPI, SQLAlchemy, SQLite, Pytest, JSON (for the simulated data
feeds) — see `README.md` "Technologies Used"

## 6. Software Engineering Practices
- **Testing:** 18 Pytest tests — conservation invariant (3), all 8 named edge
  cases plus a baseline case (9), re-runnability (3), 404/not-found handling
  (3) — `tests/`
- **Error handling & validation:** `NotFoundError` raised at the service layer,
  translated to HTTP 404 at the route layer — a deliberate layering decision,
  not just a try/except bolted on; documented in `API.md`
- **Code review equivalent:** mentor feedback incorporated as a real revision
  pass (conservation invariant scope, toll ambiguity, decimal vs float) —
  changes traceable in `DESIGN.md` and `Architecture.md`

## 7. Object-Oriented Programming
- Each SQLAlchemy model (`Vehicle`, `Trip`, `FuelPurchase`, `Allocation`, etc.)
  is a class encapsulating its own fields and relationships —
  `app/models/*.py`
- Services (`AllocationService`-equivalent functions in `allocation.py`,
  `QueryService`-equivalent functions in `query.py`) are organized around
  single, clear responsibilities, favoring composition (services calling into
  models) over deep inheritance hierarchies — appropriate for this domain,
  where the entities don't have meaningful "is-a" relationships to model
  through inheritance
- Abstract-class-style question, honestly answered: this project doesn't force
  an abstract base class where the domain doesn't call for one (e.g., the
  three cost-bearing sources are structurally similar but have distinct
  columns and distinct allocation policies — modeling them as separate
  classes with separate, explicit `allocate_*` functions was a deliberate
  choice over a forced shared abstraction, since the brief's whole point is
  that these three sources should NOT be treated uniformly)

## 8. CSS / Frontend
- Minimal static dashboard (`app/static/index.html`, served at `/ui`) — vanilla
  HTML/CSS/JS, no framework, calling the live API directly via `fetch`.
- Deliberate design choices, not a generic template: dark fleet-instrumentation
  theme, monospace type specifically for financial figures so digits align
  like a real ledger, and the reconciliation ledger positioned as the visual
  centerpiece since it's the single most important number in the system (the
  conservation invariant).
