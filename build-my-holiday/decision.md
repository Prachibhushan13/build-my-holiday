# Design decisions and trade-offs

Each decision uses the same five fields: **Decision** (what we chose), **Alternative** (what we didn't), **Why** (tied to the hackathon constraints), **Cost** (what we gave up) and **At scale** (what we'd change in production).

Hackathon constraints referenced throughout: ~9–10 hours to build, a team of 2, correctness on unseen judge requests (25%), live code changes explained by each member (20%), "backend holds the logic", state survives restart, no AI in the app, start in 1–2 commands, read-only catalog.

---

## 1. Store the traveler's choices (a "spec"), re-derive the package every time

- **Decision:** What is saved and edited is a small spec: cities and nights, hotel + room per city, two flights, optional forced transfers, attraction placements. The full trip (times, prices, items) is rebuilt from it on every read and every change (`package_builder.assemble`).
- **Alternative:** Save the finished package and patch it in place when something changes.
- **Why:** Judges change hotels, flights and attractions and check that "other parts still fit". Rebuilding from choices makes it impossible for a stale transfer time or price to survive a change. One code path builds every package, so there is one place to explain and debug.
- **Cost:** Every change re-runs the build and validation (a few milliseconds). Past versions of a package are overwritten, not kept.
- **At scale:** Keep the spec model but cache derived trips, add an append-only change history table, and version the spec schema so old saved specs can be migrated.

## 2. One independent validator that only reads the finished trip

- **Decision:** `package_validator.validate_trip` checks every rule from the problem statement using only the exported trip items and the catalog. It runs on generated packages, every change, confirmation, and can run on exported JSON.
- **Alternative:** Enforce rules inside the builder as it constructs the package, with no separate check.
- **Why:** "A package that breaks one rule is wrong." The judges run their own checker on our JSON, so we want an independent check that catches builder bugs the same way theirs would. It also made the 800-request randomized test meaningful.
- **Cost:** Some rules (opening hours, service windows, buffers) exist twice: once to build, once to check. A rule change must be made in both places.
- **At scale:** Share rule definitions as data (a rule registry) used by both builder and validator, and run the validator as a gate in CI against generated sample packages.

## 3. Exact search over all city plans with Pareto pruning

- **Decision:** `package_generator` enumerates every valid city plan, and for each finds the cheapest flights × hotels × transfers exactly. A hotel that costs more and has fewer stars than another is dropped (Pareto pruning). The cheapest result matched a brute-force search in development.
- **Alternative:** A greedy builder (pick the cheapest of everything in order), or a generic solver (ILP/constraint programming).
- **Why:** Greedy can miss the true cheapest when transfer availability couples a flight to a hotel. A solver library adds a dependency and is hard to explain in a live code review. The explicit loops are short and the problem is small enough to solve exactly.
- **Cost:** Correct only because components are independent given the plan. If a new rule linked, say, hotel choice to attraction prices, the pruning would no longer be safe and would need revisiting.
- **At scale:** With many cities and thousands of hotels, move to a pre-indexed or solver-based approach (e.g. OR-tools), precompute per-city cheapest tables, and cache searches by request.

## 4. "Fastest" and "Best rated" use a smaller search than "Cheapest"

- **Decision:** Cheapest is exact. Fastest and best-rated pick the best option within budget, with the remaining components filled in at their cheapest.
- **Alternative:** Exact multi-objective optimization (full Pareto front over price, time and stars).
- **Why:** The problem asks for one fastest and one best-rated package and says "on a tie, show either". Within the time budget, correctness of the cheapest and zero rule violations mattered more than provable optimality of the other two.
- **Cost:** The fastest or best-rated package is not guaranteed to be the globally optimal combination.
- **At scale:** Compute a proper Pareto frontier, let the traveler weight price vs time vs comfort, and show the trade-off curve.

## 5. Deterministic rules, no AI anywhere in the app

- **Decision:** Every choice is a loop, formula or rule over the catalog. Same request, same package.
- **Alternative:** An LLM to "plan" the holiday or parse requests.
- **Why:** It is a hard constraint ("no AI inside the app"), and determinism also lets judges re-run requests and get the same answer.
- **Cost:** No natural-language request (stretch S1) and less "creative" itineraries. Attraction choice is simply cheapest-first.
- **At scale:** Keep the rule engine as the source of truth. Any ML would only rank already-valid packages, never decide validity.

## 6. Backend holds all logic; the frontend only displays

- **Decision:** Pricing, city choice, validation, alternatives and refusals all run in the FastAPI backend. The React app calls the API and renders results.
- **Alternative:** Check rules and compute prices in the browser for instant feedback.
- **Why:** Required by the problem ("backend holds the logic") and it guarantees the UI cannot show a package the rules would reject.
- **Cost:** More API calls and a loading state. Opening the "Change hotel" dialog asks the server to check every option (about 30 quick checks).
- **At scale:** Add caching and pagination for alternatives, debounce requests, and consider server-sent updates. Keep rules server-side regardless.

## 7. SQLite with JSON columns for persistence

- **Decision:** Two tables (`packages`, `reservations`) in one SQLite file in WAL mode. Request, spec and trip are stored as JSON text.
- **Alternative:** Postgres, or a fully normalized schema (items, hotels, bookings as separate tables).
- **Why:** Zero setup keeps start-up to one command, survives restarts, and runs on a judge's laptop. JSON columns avoided a schema migration every time the trip format grew.
- **Cost:** You cannot easily query across bookings ("all Tokyo bookings"), and there are no foreign keys between items and the catalog. One writer at a time.
- **At scale:** Postgres with normalized item tables and JSONB for the spec, an index on reference, and a proper migration tool.

## 8. Catalog loaded into memory once at start-up

- **Decision:** `catalog_loader` reads all JSON files at start and builds lookups (flights by route, rooms left by night, transfers by airport).
- **Alternative:** Read files per request, or load the catalog into the database.
- **Why:** The data is small (about 530 KB) and read-only, so memory lookups are instant and the loader is simple to explain. The data files are never modified, as required.
- **Cost:** Changing the data needs a server restart. There is no live inventory.
- **At scale:** Move to a database or search service with live inventory, cache invalidation, and a separate pricing/availability service.

## 9. Confirmed bookings do not consume seats or rooms (stretch S2 skipped)

- **Decision:** Confirm saves the reservation but leaves catalog availability unchanged.
- **Alternative:** Keep an inventory table and subtract seats and rooms on confirm, refusing a booking that needs the last ones.
- **Why:** S2 earns credit only after all Must-haves work, and the judges validate packages against the original files, so adjusted inventory could make later requests look wrong.
- **Cost:** Two people can book the same last seat or room.
- **At scale:** Maintain a reservation ledger, check and decrement availability inside the same transaction as confirm, and add holds with expiry before payment.

## 10. Attractions: 1 per day for Cheapest, up to 2 for the others, none auto-planned on arrival or city-change days

- **Decision:** The cheapest package uses the cheapest open attraction each full day. Fastest and best-rated use two per day when the budget allows. Arrival and city-change days get none automatically but can be added manually.
- **Alternative:** Always two per day, or fill arrival and change days too.
- **Why:** Keeps "Cheapest" truly the lowest price while still meeting the "1–2 per full day" rule. Arrival and change days are optional in the spec and have the most timing risk.
- **Cost:** The default itinerary can feel thin, with empty half-days on travel days.
- **At scale:** Rank attractions by proximity, theme, family-friendliness and traveler preferences, and plan routes to minimize walking between sights.

## 11. Over-budget packages can be edited; confirming needs an explicit override

- **Decision:** Changes are never refused just because they exceed the budget (the budget bar turns red). Confirm is blocked with a message unless the traveler chooses "Confirm anyway".
- **Alternative:** Hard-refuse any change that goes over budget.
- **Why:** The budget is not one of the travel rules the judges check. Letting the traveler see the price impact of an expensive option is more useful than a blunt refusal.
- **Cost:** A judge expecting a hard refusal on over-budget changes may see this as lenient.
- **At scale:** Make the behavior a product setting, add price alerts and "fits your budget" filters in every option list.

## 12. "Change cities" rebuilds the package from scratch

- **Decision:** Picking another city plan regenerates the cheapest package for that plan and replaces the old one.
- **Alternative:** Carry over earlier hotel, flight and attraction choices where still valid.
- **Why:** Always produces a fully valid package with minimal code, and city changes invalidate almost every hotel and transfer anyway.
- **Cost:** The traveler's earlier customizations are lost.
- **At scale:** Diff old and new plans, keep compatible choices (same flights, same hotel in a retained city), and offer undo.

## 13. Dependent bookings are fixed automatically where possible, otherwise the change is refused

- **Decision:** After a change, the app picks a compatible airport transfer itself, drops attractions that would now start before arrival, and adds notes and warnings. Anything that still breaks a rule is refused with a reason, and the saved package stays untouched.
- **Alternative:** Ask the traveler to choose a replacement transfer each time, or allow temporarily invalid packages with warnings.
- **Why:** Meets G1 and the rule "the app checks the whole package again and updates the total, or refuses". There is no UI for choosing transfers, and an invalid saved package would be a wrong answer to a judge.
- **Cost:** The traveler cannot pick a specific transfer (such as bus vs taxi). The app always chooses the cheapest feasible one.
- **At scale:** Offer transfer choices (comfort vs price), show a clear before-and-after diff for every automatic fix, and ask for confirmation on larger side effects.

## 14. Intercity transfer fixed at the first departure at or after 10:00

- **Decision:** On a city-change day the transfer departs at the first scheduled time at or after 10:00 in its service window.
- **Alternative:** Let the traveler choose a departure, or optimize for attractions in the morning.
- **Why:** Gives a predictable, valid time inside service hours with minimal UI. Keeps arrival after typical hotel checkout.
- **Cost:** No control over travel time of day. Optional station taxis are not added.
- **At scale:** Show the real timetable, allow selecting a departure, and add station taxis with their prices.

## 15. Reservation number: random 10 digits, uniqueness checked inside the transaction

- **Decision:** `secrets.randbelow(10**10)` formatted with leading zeros, regenerated if it already exists, inside one `BEGIN IMMEDIATE` transaction. Confirming twice returns the same number.
- **Alternative:** A sequential counter, or a UUID.
- **Why:** The spec requires a unique 10-digit string with leading zeros preserved. Random numbers are not guessable and need no counter table.
- **Cost:** A tiny chance of retrying on collision, and the number carries no meaning.
- **At scale:** Use a sequence plus a check digit (so typos are caught), and rate-limit lookups so references cannot be enumerated.

## 16. Local times as plain strings, no time-zone library

- **Decision:** All times are local at the place, as in the catalog. Flight duration comes from `duration_minutes`, never from subtracting local times.
- **Alternative:** Convert everything to UTC with a time-zone library.
- **Why:** The data dictionary states all times are local with no daylight-saving changes, so converting would add risk without benefit.
- **Cost:** Correct only because the data has no DST and compares times at one place at a time.
- **At scale:** Store timestamps with zones in UTC, convert at the edges, and handle DST and multi-zone itineraries.

## 17. Smallest room count only

- **Decision:** For each room type we use the smallest number of rooms that fits the group.
- **Alternative:** Also consider more rooms than necessary (for example, extra space).
- **Why:** More rooms always cost more and need more availability, so the minimum is both the cheapest and the most likely to be available.
- **Cost:** The traveler cannot choose extra rooms for comfort.
- **At scale:** Let the traveler pick room count and bed configuration, and price family splits across room types.

## 18. FastAPI + React, with the built UI committed in `frontend/dist`

- **Decision:** Python backend, React + TypeScript + Tailwind frontend. A prebuilt bundle is included and served by the backend.
- **Alternative:** A single-stack app, or requiring `npm install` and a build on first run.
- **Why:** A familiar stack that is quick to build and easy to explain. The prebuilt bundle keeps "start in 1–2 commands" working on a machine with no Node.
- **Cost:** The bundle must be rebuilt after UI edits. Submission rules say no build output in the zip, so judges need Node to rebuild.
- **At scale:** Build in CI, serve the UI from a CDN, and deploy the API as a separate container.

## 19. Test the backend only

- **Decision:** 21 pytest tests cover validation, occupancy, transfer buffers, attractions, pricing, search, persistence across a restart, and the change flow.
- **Alternative:** Also write browser tests and tests for every endpoint.
- **Why:** The rules and the money are in the backend and are what judges score. A browser test setup would have cost hours.
- **Cost:** No automated UI tests. The change-cities, change-hotel and add and remove attraction endpoints were checked by hand, not by tests.
- **At scale:** Add API tests for every endpoint, browser end-to-end tests of the demo path, property-based tests for the validator, and CI on every push.

## 20. Logging to the console and a rotating file

- **Decision:** Each API call, search, change, refusal (with rule codes) and confirmation is logged to the terminal and to `backend/var/app.log`.
- **Alternative:** No logging, or a full tracing and metrics stack.
- **Why:** The fastest way to debug a failed change during the demo is to see which rule refused it.
- **Cost:** Plain text lines, not structured, with no request ids and no log search.
- **At scale:** Structured JSON logs with request ids, centralized log storage, metrics on search time and refusal rates, and alerting.
