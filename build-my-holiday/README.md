# Build My Holiday

A deterministic, constraint-based holiday package builder: **request → complete package → change → confirm → 10-digit reservation**.
No AI/LLM is used anywhere in the app — cities, flights, hotels, transfers and attractions are chosen by a rule engine over the read-only catalog in `data/catalog/`.

## Start it (1 command)

```bash
./run.sh            # first run creates .venv, installs deps, serves API + UI on http://localhost:8000
```

Other modes: `./run.sh dev` (API with reload on :8000 + Vite on :5173), `./run.sh test` (backend tests).
Requirements: Python 3.10+. Node is only needed to rebuild the UI — a prebuilt bundle is in `frontend/dist`.

The Menon family request (Bengaluru → Japan, 10 Apr 2027, 6 nights, 2 adults + 1 child aged 6, ₹3,50,000) can be filled with the **"Use the Menon example"** button.
Packages and reservations live in `backend/var/bmh.sqlite3` (SQLite, WAL) and survive restarts.

## Architecture

```
backend/app
  catalog/catalog_loader.py     loads + indexes data/catalog/*.json once at start-up (read-only)
  services/
    pricing_service.py          every price formula + the k-room occupancy rule
    flight_service.py hotel_service.py transfer_service.py attraction_service.py
                                component search: seats, availability, service windows, buffers, opening hours
    package_generator.py        deterministic constraint search (city plans → components → 3 objectives)
    package_builder.py          spec (the choices) → full trip (items, times, prices, advisory warnings, day plan)
    package_validator.py        THE single source of truth for every rule; works only from the exported trip + catalog
    package_service.py          generate / persist / atomic change engine / alternatives with price diff
    booking_service.py          confirm (one SQLite transaction) + reservation lookup
  api/                          FastAPI routers: catalog, packages, reservations
  db/                           SQLite (WAL): packages + reservations tables
frontend/src                    React + TS + Tailwind: RequestForm, ItineraryTimeline, PriceBreakdown, Change*Modal, ...
```

**Spec vs. trip.** What is stored and edited is a small *spec* (cities+nights, hotel/room per city, two flights, optional forced transfers, attraction placements).
The full trip is always *re-derived* from the spec and then *re-validated* — nothing is patched in place, so the package can never drift out of sync.

**Change protocol (M6/G1/G2).** copy spec → apply change → rebuild (auto-picks a compatible airport transfer, drops attractions that would now start before you reach the hotel) → run the full validator → commit in one SQLite transaction and report the price difference, **or** refuse with a human-readable reason and leave the package untouched.
Every alternative in the "Change flight/hotel" dialogs is pre-checked this way, so each shows its exact price delta and, if impossible, why.

**Confirmation (M7).** Re-validates, mints a unique random 10-digit string (leading zeros kept), marks all items `BOOKED` with `booking.reference`, and stores an immutable snapshot — all in one `BEGIN IMMEDIATE` transaction. Confirm is idempotent.

## City rule (how the app chooses cities)

All ordered selections of distinct cities of the country such that consecutive cities are linked in `destinations.json`, every city gets ≥ 2 nights, and nights sum to the request, form the candidate **plans** (e.g. Japan, 10 nights: 1, 2 or 3 cities → 100+ plans).
For each plan the cheapest valid components are found exactly (Pareto-pruned search over flights × hotels × transfers; verified against brute force in development). Across all plans:

* **Cheapest** – minimum total price (1 attraction per full day, cheapest open ones).
* **Fastest** – minimum `sum(flight duration_minutes) + sum(intercity transfer duration_minutes)` among packages within budget (up to 2 attractions/day if budget allows).
* **Best rated** – maximum night-weighted average hotel `stars` among packages within budget (guest `rating` is ignored).

If valid packages exist but all exceed the budget → status `OVER_BUDGET` (cheapest package, deficit, concrete suggestions: fewer nights, shifted dates, raise budget). If none exist → `IMPOSSIBLE` with the blocking reasons (no flight that day, not enough seats, no room for the group, outside the 1–20 April window, no transfer within service hours…).

## What is implemented

| | |
|---|---|
| M1–M8 | request form with catalog dropdowns + inline validation (client **and** server), package builder, all rules via one validator, day-by-day plan, total/budget/remaining + JSON export, change hotel/flight/attractions with re-validation, confirm + 10-digit reservation that survives restarts, "not found", over-budget handling |
| G1 | dependent changes: transfers auto-switch to a compatible one, now-impossible attractions are removed with a note, early-arrival/check-in warnings |
| G2 | price difference on every flight/hotel/city-plan option and after every change |
| G3 | **Change cities** dialog: every valid city plan with its total; choosing one rebuilds the package |
| G4 | Cheapest / Fastest / Best-rated tabs |
| Tests | `./run.sh test` – 21 pytest tests (request validation, room occupancy, transfer buffers/windows, attraction rules incl. Nara, pricing, generator, SQLite persistence across a simulated restart, change/reject flow) |

## API (all under `/api`)

`GET /catalog` · `POST /packages/generate` · `GET /packages/{id}` · `GET /packages/{id}/options` · `GET /packages/{id}/export` ·
`GET /packages/{id}/alternatives/flights?direction=arrival|return` · `GET /packages/{id}/alternatives/hotels?city=` ·
`PATCH /packages/{id}/flight` · `PATCH /packages/{id}/hotel` · `GET|POST /packages/{id}/attractions` · `DELETE /packages/{id}/attractions/{attraction_id}` ·
`GET /packages/{id}/city-plans` · `POST /packages/{id}/cities` · `POST /packages/{id}/confirm` · `GET /reservations/{reference}`.
Interactive docs: `http://localhost:8000/docs`.

## Conventions worth knowing

* Times are local at the place; overnight flights show the departure on the previous day. Pickups stay on the landing day; return pickups on the departure day.
* Airport pickup = landing + 60 min (or the service start); hotel departure leaves the airport ≥ 180 min before the flight; both must be inside the transfer's service window (windows like `06:00–00:30` and `24:00` handled).
* City-change day: one transfer from the `links` list, departing from 10:00 (first departure in the window). Optional station taxis are not added.
* Export adds nothing beyond the shared trip format; the UI-only `meta` block is stripped.
* Return flight `city` is the destination city the traveller leaves from.

## Known limitations

* Stretch features not built: S1 quick text request, S2 booking consuming seats/rooms (confirmed bookings do not reduce catalog inventory), S3.
* Attractions on arrival / city-change days are optional and never auto-planned (they can be added manually and are checked against arrival times).
* Hotel check-in/out times are display-only (advisory warnings, never blocking), as specified.
* Search covers every valid city plan; Pareto pruning keeps a full 10-night, 3-city search to well under a second.
