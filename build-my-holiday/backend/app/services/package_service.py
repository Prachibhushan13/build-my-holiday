"""Orchestration: generate packages, persist them, and apply traveler changes atomically.
Every change = copy spec -> mutate -> rebuild -> full re-validation -> commit, or reject with a reason."""
import copy
import json
import logging
import uuid
from datetime import date, timedelta
from typing import Callable, Dict, List, Optional

from ..db import database as db
from ..schemas.request import TripRequest, normalize_request
from . import package_generator as gen
from .attraction_service import DAY_START, GAP, earliest_start, is_open_on
from .flight_service import arrival_flights, flight_view, return_flights
from .hotel_service import hotel_options
from .package_builder import (BuildError, assemble, avg_stars, city_dates, itinerary, party_of, summary,
                              to_export, travel_minutes)
from .package_validator import explain, validate_trip
from .pricing_service import attraction_price, flight_price, rooms_needed
from .timeutil import hhmm, hm, parse_dt, weekday

log = logging.getLogger("bmh")
OPTION_TITLES = {"cheapest": "Cheapest", "fastest": "Fastest", "best_rated": "Best rated"}


class ChangeRejected(Exception):
    def __init__(self, message: str, violations: Optional[list] = None):
        self.message = message
        self.violations = violations or []
        super().__init__(message)


class NotFound(Exception):
    pass


def new_id() -> str:
    return "BMH-" + uuid.uuid4().hex[:8].upper()


def inr(n: int) -> str:
    s = f"{abs(int(n)):,}"
    # Indian digit grouping
    d = str(abs(int(n)))
    if len(d) > 3:
        head, tail = d[:-3], d[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        s = ",".join(parts + [tail])
    return ("-" if n < 0 else "") + "₹" + s


# ---------------------------------------------------------------------------------------
def build_payload(cat, pid, status, reference, option, request, spec, trip, group_id=None, extra=None) -> dict:
    warnings = [{"item_id": i["item_id"], "item": i["name"], "message": w} for i in trip["items"] for w in i["warnings"]]
    out = {
        "package_id": pid, "group_id": group_id, "option": option, "status": status, "reference": reference,
        "request": request, "plan": [{"city": c["city"], "nights": c["nights"]} for c in spec["cities"]],
        "summary": summary(cat, trip), "itinerary": itinerary(cat, trip), "trip": trip, "warnings": warnings,
    }
    out.update(extra or {})
    return out


def payload_from_row(cat, row) -> dict:
    return build_payload(cat, row["package_id"], row["status"], row["reference"], row["option_label"],
                         json.loads(row["request_json"]), json.loads(row["spec_json"]), json.loads(row["trip_json"]),
                         row["group_id"])


def get_payload(cat, pid: str) -> dict:
    row = db.get_package(pid)
    if not row:
        raise NotFound("Package not found")
    return payload_from_row(cat, row)


# ---------------------------------------------------------------------------------------
def rebuild(cat, spec: dict, pid: str, first_package: bool = False, notes: Optional[list] = None) -> dict:
    """Assemble + validate, auto-resolving dependent bookings (G1). Mutates spec when it auto-fixes."""
    notes = notes if notes is not None else []
    before = json.dumps([spec.get("arrival_transfer"), spec.get("return_transfer"), spec.get("intercity")])
    try:
        trip = assemble(cat, spec, pid)
    except BuildError as first:
        spec.update(arrival_transfer=None, return_transfer=None, intercity=[])
        try:
            trip = assemble(cat, spec, pid)
        except BuildError as e:
            raise ChangeRejected(str(e))
    for _ in range(12):
        v = validate_trip(cat, trip, first_package)
        fix = [x for x in v if x["code"] == "BEFORE_ARRIVAL"]
        if not fix or len(fix) != len(v):
            break
        gone = {next(i for i in trip["items"] if i["item_id"] == x["item_id"])["catalog_id"] for x in fix}
        for g in gone:
            notes.append(f"Removed {cat.attractions[g]['name']}: it would now start before you reach the hotel/city.")
        spec["attractions"] = [a for a in spec["attractions"] if a["attraction_id"] not in gone]
        trip = assemble(cat, spec, pid)
    v = validate_trip(cat, trip, first_package)
    if v:
        raise ChangeRejected(explain(v), v)
    return trip


def _transfer_signature(trip) -> list:
    return [(i["meta"]["direction"], i["catalog_id"], i["name"]) for i in trip["items"]
            if i["type"] == "transfer" and i["meta"].get("direction") in ("ARRIVAL", "RETURN", "INTERCITY")]


def _transfer_notes(old_trip, new_trip, notes):
    old = {(d, ) + (n,) for d, c, n in _transfer_signature(old_trip)}
    for d, c, n in _transfer_signature(new_trip):
        if (d, n) not in old:
            label = {"ARRIVAL": "Airport pickup", "RETURN": "Airport drop-off", "INTERCITY": "City-to-city transfer"}[d]
            notes.append(f"{label} automatically changed to “{n}” so it fits the new selection.")


# ---------------------------------------------------------------------------------------
def over_budget_suggestions(cat, req: dict, cheapest_total: int, spec_trip: dict) -> List[str]:
    budget = req["budget_inr"]
    sugs: List[str] = []
    for n in range(req["nights"] - 1, cat.rules["min_nights"] - 1, -1):
        r = gen.generate(cat, {**req, "nights": n}, fast=True)
        if r["status"] in ("OK",):
            sugs.append(f"Shorten the trip to {n} nights: the cheapest package would be {inr(r['cheapest_total'])}, within your budget.")
            break
    best = None
    start = date.fromisoformat(req["start_date"])
    for delta in (-3, -2, -1, 1, 2, 3):
        d = start + timedelta(days=delta)
        r = gen.generate(cat, {**req, "start_date": d.isoformat()}, fast=True)
        if r["status"] == "OK" and (best is None or r["cheapest_total"] < best[0]):
            best = (r["cheapest_total"], d)
    if best:
        sugs.append(f"Travel starting {best[1]:%d %b %Y} instead: the cheapest package would be {inr(best[0])}, within your budget.")
    b = summary(cat, spec_trip)["breakdown"]
    top = max(b, key=b.get)
    sugs.append(f"Increase your budget to at least {inr(cheapest_total)}. Most of the cost is {top} ({inr(b[top])}).")
    if req["adults"] + len(req["child_ages"]) > 2:
        sugs.append("Fewer travellers or a smaller room count would reduce the flight and hotel cost.")
    return sugs


def generate_packages(cat, raw: TripRequest) -> dict:
    req = normalize_request(cat, raw)
    res = gen.generate(cat, req)
    if res["status"] == "IMPOSSIBLE":
        return {"status": "IMPOSSIBLE", "request": req, "reasons": res["reasons"],
                "message": "No holiday package is possible for this request.", "options": [], "package": None}
    group = new_id()
    seen: Dict[str, str] = {}
    options, payloads = [], {}
    with db.transaction() as conn:
        for name, spec in res["specs"].items():
            key = json.dumps({k: v for k, v in spec.items() if k != "attractions"}, sort_keys=True) + json.dumps(spec["attractions"])
            if key in seen:
                continue
            pid = new_id()
            trip = assemble(cat, spec, pid)
            v = validate_trip(cat, trip, first_package=True)
            if v:
                log.error("generated package failed validation: %s", v)
                if name == "cheapest":
                    raise RuntimeError("internal: generated package invalid: " + explain(v))
                continue
            db.save_package(conn, pid, "PLANNED", req, spec, trip, group_id=group, option=name)
            seen[key] = pid
            payloads[name] = build_payload(cat, pid, "PLANNED", None, name, req, spec, trip, group)
    for name, p in payloads.items():
        s = p["summary"]
        options.append({"option": name, "title": OPTION_TITLES[name], "package_id": p["package_id"], "total_inr": s["total_inr"],
                        "travel_minutes": s["travel_minutes"], "avg_stars": s["avg_stars"], "cities": s["cities"],
                        "within_budget": s["within_budget"]})
    primary = payloads["cheapest"]
    out = {"status": res["status"], "request": req, "options": options, "package": primary, "group_id": group,
           "plans_considered": res.get("plans_considered")}
    if res["status"] == "OVER_BUDGET":
        out.update(
            message=f"No package fits your budget of {inr(req['budget_inr'])}. The cheapest valid package costs "
                    f"{inr(res['cheapest_total'])}, which is {inr(res['deficit'])} over.",
            cheapest_total_inr=res["cheapest_total"], deficit_inr=res["deficit"],
            suggestions=over_budget_suggestions(cat, req, res["cheapest_total"], primary["trip"]))
    else:
        out["message"] = "Here are your holiday packages."
    out["packages"] = {p["package_id"]: p for p in payloads.values()}
    return out


# ---------------------------------------------------------------------------------------
def modify(cat, pid: str, mutate: Callable[[dict, dict, list], None]) -> dict:
    with db.transaction() as conn:
        row = conn.execute("SELECT * FROM packages WHERE package_id=?", (pid,)).fetchone()
        if not row:
            raise NotFound("Package not found")
        if row["status"] == "BOOKED":
            raise ChangeRejected("This package is already booked and can no longer be changed.")
        spec = json.loads(row["spec_json"])
        old_trip = json.loads(row["trip_json"])
        new_spec = copy.deepcopy(spec)
        notes: List[str] = []
        mutate(new_spec, old_trip, notes)
        trip = rebuild(cat, new_spec, pid, notes=notes)
        _transfer_notes(old_trip, trip, notes)
        db.save_package(conn, pid, "PLANNED", json.loads(row["request_json"]), new_spec, trip)
        out = build_payload(cat, pid, "PLANNED", None, row["option_label"], json.loads(row["request_json"]),
                            new_spec, trip, row["group_id"])
    out["change"] = {"previous_total_inr": old_trip["total_inr"], "new_total_inr": trip["total_inr"],
                     "price_diff_inr": trip["total_inr"] - old_trip["total_inr"], "notes": notes}
    return out


def _evaluate(cat, pid, spec, old_trip, mutate):
    s = copy.deepcopy(spec)
    notes: List[str] = []
    try:
        mutate(s, old_trip, notes)
        trip = rebuild(cat, s, pid, notes=notes)
        _transfer_notes(old_trip, trip, notes)
        return trip, notes, None
    except ChangeRejected as e:
        return None, [], e.message


def _row(pid):
    row = db.get_package(pid)
    if not row:
        raise NotFound("Package not found")
    return row


# ---- flights ----------------------------------------------------------------------------
def _flight_problem(cat, spec, direction, f) -> Optional[str]:
    req = spec["request"]
    party = party_of(req)
    start = date.fromisoformat(req["start_date"])
    end = city_dates(spec)[-1][1]
    if direction == "arrival":
        city = spec["cities"][0]["city"]
        if f["from"] != req["departure_airport"] or f["to"] not in cat.city_airports.get(city, []):
            return f"{f['flight_number']} does not fly {req['departure_airport']} → an airport serving {city}."
        if f["arr_date"] != start.isoformat():
            return f"{f['flight_number']} lands on {f['arr_date']}, but your holiday starts on {start.isoformat()}."
    else:
        city = spec["cities"][-1]["city"]
        if f["to"] != req["departure_airport"] or f["from"] not in cat.city_airports.get(city, []):
            return f"{f['flight_number']} does not fly an airport serving {city} → {req['departure_airport']}."
        if f["dep_date"] != end.isoformat():
            return f"{f['flight_number']} departs on {f['dep_date']}, but your last day is {end.isoformat()}."
    if f["seats_left"] < party.travellers:
        return f"{f['flight_number']} has only {f['seats_left']} seat(s) left; you need {party.travellers}."
    return None


def change_flight_mutator(cat, direction: str, flight_id: str):
    def mut(spec, old, notes):
        if direction not in ("arrival", "return"):
            raise ChangeRejected("direction must be 'arrival' or 'return'.")
        f = cat.flights.get(flight_id)
        if not f:
            raise ChangeRejected("Unknown flight.")
        problem = _flight_problem(cat, spec, direction, f)
        if problem:
            raise ChangeRejected(problem)
        if direction == "arrival":
            spec["arrival_flight"], spec["arrival_transfer"] = flight_id, None
        else:
            spec["return_flight"], spec["return_transfer"] = flight_id, None
    return mut


def flight_alternatives(cat, pid: str, direction: str) -> dict:
    row = _row(pid)
    spec, trip = json.loads(row["spec_json"]), json.loads(row["trip_json"])
    req = spec["request"]
    end = city_dates(spec)[-1][1]
    start = date.fromisoformat(req["start_date"])
    T = party_of(req).travellers
    cur_id = spec["arrival_flight"] if direction == "arrival" else spec["return_flight"]
    cands = []
    if direction == "arrival":
        for ap in cat.city_airports.get(spec["cities"][0]["city"], []):
            cands += [f for f in cat.flights_by_route.get((req["departure_airport"], ap), []) if f["arr_date"] == start.isoformat()]
    else:
        for ap in cat.city_airports.get(spec["cities"][-1]["city"], []):
            cands += [f for f in cat.flights_by_route.get((ap, req["departure_airport"]), []) if f["dep_date"] == end.isoformat()]
    out = []
    for f in sorted(cands, key=lambda f: (flight_price(f, T), f["flight_id"])):
        if f["flight_id"] == cur_id:
            out.append({**flight_view(f, T), "is_current": True, "valid": True, "reason": None, "price_diff_inr": 0,
                        "new_total_inr": trip["total_inr"], "notes": []})
            continue
        t2, notes, reason = _evaluate(cat, pid, spec, trip, change_flight_mutator(cat, direction, f["flight_id"]))
        out.append({**flight_view(f, T), "is_current": False, "valid": t2 is not None, "reason": reason,
                    "price_diff_inr": (t2["total_inr"] - trip["total_inr"]) if t2 else None,
                    "new_total_inr": t2["total_inr"] if t2 else None, "notes": notes})
    return {"direction": direction, "current_total_inr": trip["total_inr"], "alternatives": out}


# ---- hotels -----------------------------------------------------------------------------
def change_hotel_mutator(cat, city: str, hotel_id: str, room_id: Optional[str]):
    def mut(spec, old, notes):
        idx = next((i for i, c in enumerate(spec["cities"]) if c["city"] == city), None)
        if idx is None:
            raise ChangeRejected(f"{city} is not part of this package.")
        h = cat.hotels.get(hotel_id)
        if not h or h["city"] != city:
            raise ChangeRejected(f"That hotel is not in {city}.")
        party = party_of(spec["request"])
        ci = city_dates(spec)[idx][0]
        n = spec["cities"][idx]["nights"]
        rid = room_id
        if rid is None:
            opts = [o for o in hotel_options(cat, city, ci, n, party.adults, party.children) if o.hotel_id == hotel_id]
            if not opts:
                raise ChangeRejected(f"{h['name']} has no room type that fits {party.adults} adult(s) + {party.children} child(ren) "
                                     f"and is free for all {n} nights.")
            rid = opts[0].room_id
        spec["cities"][idx]["hotel_id"], spec["cities"][idx]["room_id"] = hotel_id, rid
        if idx == 0:
            spec["arrival_transfer"] = None
        if idx == len(spec["cities"]) - 1:
            spec["return_transfer"] = None
    return mut


def hotel_alternatives(cat, pid: str, city: str) -> dict:
    row = _row(pid)
    spec, trip = json.loads(row["spec_json"]), json.loads(row["trip_json"])
    idx = next((i for i, c in enumerate(spec["cities"]) if c["city"] == city), None)
    if idx is None:
        raise NotFound(f"{city} is not part of this package")
    cur = spec["cities"][idx]
    out = []
    for h in cat.hotels_by_city.get(city, []):
        for r in cat.rooms_by_hotel[h["hotel_id"]]:
            is_cur = (h["hotel_id"], r["room_id"]) == (cur["hotel_id"], cur["room_id"])
            base = {"hotel_id": h["hotel_id"], "room_id": r["room_id"], "name": h["name"], "area": h["area"], "stars": h["stars"],
                    "rating": h["rating"], "room_name": r["name"], "room_type": r["room_type"], "image": h.get("image"),
                    "price_per_night": r["price_per_night"]["amount"], "family_friendly": h.get("family_friendly"),
                    "refundable": r.get("refundable"), "is_current": is_cur}
            if is_cur:
                out.append({**base, "valid": True, "reason": None, "price_diff_inr": 0, "new_total_inr": trip["total_inr"], "notes": [],
                            "rooms": next(i["quantity"] for i in trip["items"] if i["type"] == "hotel" and i["city"] == city)})
                continue
            t2, notes, reason = _evaluate(cat, pid, spec, trip, change_hotel_mutator(cat, city, h["hotel_id"], r["room_id"]))
            rooms = next((i["quantity"] for i in t2["items"] if i["type"] == "hotel" and i["city"] == city), None) if t2 else None
            out.append({**base, "valid": t2 is not None, "reason": reason, "rooms": rooms,
                        "price_diff_inr": (t2["total_inr"] - trip["total_inr"]) if t2 else None,
                        "new_total_inr": t2["total_inr"] if t2 else None, "notes": notes})
    out.sort(key=lambda a: (not a["is_current"], not a["valid"], a["price_diff_inr"] if a["valid"] else 0, a["name"]))
    return {"city": city, "current_total_inr": trip["total_inr"], "alternatives": out}


# ---- attractions ------------------------------------------------------------------------
def _day_info(cat, trip):
    """night city per date, earliest allowed start per date (arrival / city change), existing visits per date."""
    night_city, floor, busy = {}, {}, {}
    start = date.fromisoformat(trip["start_date"])
    for h in (i for i in trip["items"] if i["type"] == "hotel"):
        d = date.fromisoformat(h["start"])
        while d < date.fromisoformat(h["end"]):
            night_city[d] = h["city"]
            d += timedelta(days=1)
    for i in trip["items"]:
        if i["type"] == "transfer" and i["meta"].get("direction") in ("ARRIVAL", "INTERCITY"):
            e = parse_dt(i["end"])
            if e.date() in night_city:
                floor[e.date()] = max(floor.get(e.date(), 0), e.hour * 60 + e.minute)
        if i["type"] == "attraction":
            s, e = parse_dt(i["start"]), parse_dt(i["end"])
            busy.setdefault(s.date(), []).append((s.hour * 60 + s.minute, e.hour * 60 + e.minute))
    return night_city, floor, busy


def find_slot(cat, trip, att: dict, date_str: Optional[str] = None):
    night_city, floor, busy = _day_info(cat, trip)
    days = sorted(d for d, c in night_city.items() if c == att["city"])
    if date_str:
        days = [d for d in days if d.isoformat() == date_str]
    if not days:
        if att["city"] not in set(night_city.values()):
            if att["city"] not in {c["name"] for co in cat.countries.values() for c in co["cities"]}:
                return None, f"{att['name']} is in {att['city']}, which has no hotels, so there is no night there to plan it around."
            return None, f"{att['name']} is in {att['city']}, which is not part of this package."
        return None, f"You do not sleep in {att['city']} on {date_str}."
    closed = 0
    for d in sorted(days, key=lambda d: (len(busy.get(d, [])), d)):
        if not is_open_on(att, d):
            closed += 1
            continue
        cur = max(DAY_START, floor.get(d, 0) + (30 if d in floor else 0))
        cur = -(-cur // 5) * 5
        for _ in range(10):
            s = earliest_start(att, d, cur)
            if s is None:
                break
            e = s + att["visit_minutes"]
            clash = [b for b in busy.get(d, []) if b[0] < e + 0 and s < b[1]]
            if not clash:
                return (d, s), None
            cur = -(-(max(b[1] for b in clash) + 15) // 5) * 5
    if closed == len(days):
        return None, f"{att['name']} is closed on every day you are in {att['city']} (open {', '.join(att['open_days'])})."
    return None, f"{att['name']} does not fit between your other plans or its opening hours ({att['open_from']}–{att['open_until']}) on the days you are in {att['city']}."


def add_attraction_mutator(cat, trip_for_slot, attraction_id, date_str, start_str):
    def mut(spec, old, notes):
        att = cat.attractions.get(attraction_id)
        if not att:
            raise ChangeRejected("Unknown attraction.")
        if any(a["attraction_id"] == attraction_id for a in spec["attractions"]):
            raise ChangeRejected(f"{att['name']} is already in your package.")
        if start_str and date_str:
            d, s = date.fromisoformat(date_str), hm(start_str)
        else:
            slot, why = find_slot(cat, old, att, date_str)
            if not slot:
                raise ChangeRejected(why)
            d, s = slot
        spec["attractions"].append({"attraction_id": attraction_id, "date": d.isoformat(), "start": s})
        notes.append(f"Added {att['name']} on {d:%a %d %b} at {hhmm(s)}.")
    return mut


def remove_attraction_mutator(cat, attraction_id):
    def mut(spec, old, notes):
        hit = next((a for a in spec["attractions"] if a["attraction_id"] == attraction_id), None)
        if not hit:
            raise ChangeRejected("That attraction is not in your package.")
        spec["attractions"] = [a for a in spec["attractions"] if a["attraction_id"] != attraction_id]
        d = date.fromisoformat(hit["date"])
        full = any(ci < d < co or (ci + timedelta(days=1) <= d < co) for ci, co in city_dates(spec))
        if full and not any(a["date"] == hit["date"] for a in spec["attractions"]):
            notes.append(f"{d:%a %d %b} now has no attractions planned.")
    return mut


def attraction_catalog(cat, pid: str) -> dict:
    row = _row(pid)
    spec, trip = json.loads(row["spec_json"]), json.loads(row["trip_json"])
    party = party_of(spec["request"])
    have = {a["attraction_id"] for a in spec["attractions"]}
    out = []
    for c in spec["cities"]:
        for a in sorted(cat.attractions_by_city.get(c["city"], []), key=lambda a: a["attraction_id"]):
            slot, why = (None, "Already in your package") if a["attraction_id"] in have else find_slot(cat, trip, a)
            out.append({"attraction_id": a["attraction_id"], "name": a["name"], "city": a["city"], "category": a["category"],
                        "visit_minutes": a["visit_minutes"], "open_days": a["open_days"], "open_from": a["open_from"],
                        "open_until": a["open_until"], "closed_dates": a.get("closed_dates") or [], "image": a.get("image"),
                        "child_friendly": a.get("child_friendly"), "price_inr": attraction_price(a, party),
                        "in_package": a["attraction_id"] in have,
                        "can_add": slot is not None, "reason": why,
                        "suggested": {"date": slot[0].isoformat(), "start": hhmm(slot[1])} if slot else None})
    return {"attractions": out}


# ---- cities (G3) ------------------------------------------------------------------------------
def city_plan_options(cat, pid: str) -> dict:
    row = _row(pid)
    spec, trip = json.loads(row["spec_json"]), json.loads(row["trip_json"])
    req = spec["request"]
    cur = tuple((c["city"], c["nights"]) for c in spec["cities"])
    out = []
    for plan in gen.city_plans(cat, req["country"], req["nights"]):
        r = gen.generate(cat, req, plans=[plan], fast=True)
        entry = {"plan": [{"city": c, "nights": n} for c, n in plan], "is_current": plan == cur}
        if r["status"] == "IMPOSSIBLE":
            entry.update(feasible=False, reason=r["reasons"][0])
        else:
            entry.update(feasible=True, total_inr=r["cheapest_total"], diff_inr=r["cheapest_total"] - trip["total_inr"],
                         within_budget=r["cheapest_total"] <= req["budget_inr"])
        out.append(entry)
    out.sort(key=lambda e: (not e["feasible"], e.get("total_inr", 0)))
    return {"current_total_inr": trip["total_inr"], "plans": out}


def change_cities(cat, pid: str, plan: List[tuple]) -> dict:
    def mut(spec, old, notes):
        req = spec["request"]
        valid = gen.city_plans(cat, req["country"], req["nights"])
        plan_t = tuple((c, n) for c, n in plan)
        if plan_t not in valid:
            raise ChangeRejected("That city plan is not valid: each city needs at least 2 nights, nights must add up to "
                                 f"{req['nights']}, cities must be in {req['country']} and linked by a transfer, and a city can appear only once.")
        r = gen.generate(cat, req, plans=[plan_t], fast=True)
        if r["status"] == "IMPOSSIBLE":
            raise ChangeRejected("No package is possible with that plan: " + " ".join(r["reasons"][:2]))
        spec.clear()
        spec.update(r["specs"]["cheapest"])
        notes.append("Hotels, transfers and attractions were rebuilt for the new city plan.")
    return modify(cat, pid, mut)


# ---- options of one search (the three tabs) ---------------------------------------------------
def group_options(cat, pid: str) -> dict:
    row = _row(pid)
    conn = db.connect()
    try:
        rows = conn.execute("SELECT * FROM packages WHERE group_id=? ORDER BY created_at, package_id", (row["group_id"],)).fetchall() \
            if row["group_id"] else [row]
    finally:
        conn.close()
    order = {"cheapest": 0, "fastest": 1, "best_rated": 2}
    rows = sorted(rows, key=lambda r: order.get(r["option_label"], 9))
    options, labels = [], {}
    for r in rows:
        trip = json.loads(r["trip_json"])
        s = summary(cat, trip)
        options.append({"option": r["option_label"], "title": OPTION_TITLES.get(r["option_label"], r["option_label"]),
                        "package_id": r["package_id"], "total_inr": s["total_inr"], "travel_minutes": s["travel_minutes"],
                        "avg_stars": s["avg_stars"], "cities": s["cities"], "within_budget": s["within_budget"],
                        "status": r["status"]})
    req = json.loads(row["request_json"])
    out = {"options": options, "request": req, "status": "OK"}
    cheapest = next((o for o in options if o["option"] == "cheapest"), None)
    if cheapest and not cheapest["within_budget"]:
        crow = next(r for r in rows if r["package_id"] == cheapest["package_id"])
        out["status"] = "OVER_BUDGET"
        out["cheapest_total_inr"] = cheapest["total_inr"]
        out["deficit_inr"] = cheapest["total_inr"] - req["budget_inr"]
        out["suggestions"] = over_budget_suggestions(cat, req, cheapest["total_inr"], json.loads(crow["trip_json"]))
    return out
