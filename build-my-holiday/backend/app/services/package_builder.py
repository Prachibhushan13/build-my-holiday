"""Turns a package *spec* (the choices) into a full trip: items with times and prices.
The spec is what we persist and what modifications edit; the trip is always re-derived from it
and re-validated by package_validator."""
from datetime import date, timedelta
from typing import Dict, List, Optional

from . import transfer_service as ts
from .attraction_service import is_open_on
from .flight_service import flight_label
from .hotel_service import stay_available
from .pricing_service import (Party, attraction_price, breakdown, flight_price, hotel_price,
                              rooms_needed, transfer_price, transfer_quantity)
from .timeutil import at, fmt_dt, hhmm, hm, parse_dt, window


class BuildError(Exception):
    """A spec that cannot be turned into a coherent package; the message is shown to the traveler."""


def party_of(req: dict) -> Party:
    return Party(req["adults"], tuple(req["child_ages"]))


def city_dates(spec: dict):
    start = date.fromisoformat(spec["request"]["start_date"])
    out, cur = [], start
    for c in spec["cities"]:
        out.append((cur, cur + timedelta(days=c["nights"])))
        cur += timedelta(days=c["nights"])
    return out


def end_date_of(spec: dict) -> date:
    return date.fromisoformat(spec["request"]["start_date"]) + timedelta(days=sum(c["nights"] for c in spec["cities"]))


def _windows(ts_list):
    return ", ".join(sorted({f"{t['service_from']}-{t['service_until']}" for t in ts_list}))


def explain_arrival(cat, flight, hotel) -> str:
    cands = ts.airport_candidates(cat, flight["to"], hotel)
    arr = parse_dt(flight["arrival_local"])
    if not cands:
        return (f"No airport transfer from {flight['to']} serves {hotel['name']} ({hotel['area']}, {hotel['city']}).")
    earliest = arr + timedelta(minutes=ts.ARRIVAL_BUFFER_MIN)
    return (f"Flight {flight['flight_number']} lands at {arr:%H:%M}, so the earliest pickup is {earliest:%H:%M} "
            f"(60 minutes after landing), which is outside the service hours of every {flight['to']} airport transfer "
            f"to {hotel['area']} ({_windows(cands)}).")


def explain_return(cat, flight, hotel) -> str:
    cands = ts.airport_candidates(cat, flight["from"], hotel)
    dep = parse_dt(flight["departure_local"])
    if not cands:
        return (f"No airport transfer to {flight['from']} serves {hotel['name']} ({hotel['area']}, {hotel['city']}).")
    return (f"Flight {flight['flight_number']} departs at {dep:%H:%M}; you must be at {flight['from']} 180 minutes "
            f"earlier, so the transfer would have to leave outside its service hours ({_windows(cands)}).")


def assemble(cat, spec: dict, package_id: str, status: str = "PLANNED", reference: Optional[str] = None) -> dict:
    req = spec["request"]
    party = party_of(req)
    T = party.travellers
    country = req["country"]
    start = date.fromisoformat(req["start_date"])
    cities = spec["cities"]
    dates = city_dates(spec)
    end = dates[-1][1]

    arr_f = cat.flights.get(spec["arrival_flight"])
    ret_f = cat.flights.get(spec["return_flight"])
    if not arr_f or not ret_f:
        raise BuildError("Unknown flight selected.")
    counters: Dict[str, int] = {}

    def nid(prefix):
        counters[prefix] = counters.get(prefix, 0) + 1
        return f"{prefix}-{counters[prefix]}"

    items: List[dict] = []
    hotels = []
    for c, (ci, co) in zip(cities, dates):
        h = cat.hotels.get(c["hotel_id"])
        r = cat.rooms.get(c["room_id"])
        if not h or not r or r["hotel_id"] != h["hotel_id"] or h["city"] != c["city"]:
            raise BuildError(f"Invalid hotel/room selection for {c['city']}.")
        k = rooms_needed(r, party.adults, party.children)
        if k is None:
            raise BuildError(f"{r['name']} at {h['name']} cannot accommodate {party.adults} adult(s) and {party.children} child(ren).")
        if not stay_available(cat, r["room_id"], ci, c["nights"], k):
            raise BuildError(f"{h['name']} ({r['name']}) does not have {k} room(s) free for all of {ci:%d %b}–{co:%d %b}.")
        hotels.append((h, r, k, ci, co, c["nights"]))
        items.append({
            "item_id": nid("htl"), "type": "hotel", "name": h["name"], "city": h["city"], "status": status,
            "catalog_id": h["hotel_id"], "room_id": r["room_id"], "start": ci.isoformat(), "end": co.isoformat(),
            "quantity": k, "price_inr": hotel_price(r, k, c["nights"]), "booking": None, "sources": [], "warnings": [],
            "meta": {"area": h["area"], "stars": h["stars"], "rating": h["rating"], "room_name": r["name"],
                     "room_type": r["room_type"], "nights": c["nights"], "price_per_night": r["price_per_night"]["amount"],
                     "check_in_from": h["check_in_from"], "check_out_until": h["check_out_until"],
                     "image": h.get("image"), "family_friendly": h.get("family_friendly"), "refundable": r.get("refundable")},
        })

    # ---- flights -------------------------------------------------------
    def flight_item(f, role, city):
        return {
            "item_id": nid("fl"), "type": "flight", "name": flight_label(f), "city": city, "status": status,
            "catalog_id": f["flight_id"], "room_id": None, "start": f["departure_local"][:16], "end": f["arrival_local"][:16],
            "quantity": T, "price_inr": flight_price(f, T), "booking": None, "sources": [], "warnings": [],
            "meta": {"role": role, "airline": f["airline"], "flight_number": f["flight_number"], "from": f["from"],
                     "to": f["to"], "stops": f["stops"], "duration_minutes": f["duration_minutes"], "seats_left": f["seats_left"]},
        }

    items.append(flight_item(arr_f, "ARRIVAL", cities[0]["city"]))
    items.append(flight_item(ret_f, "RETURN", cities[-1]["city"]))

    # ---- airport transfers ----------------------------------------------
    def transfer_item(t, opt, city, direction, extra=None):
        meta = {"direction": direction, "transfer_type": t["type"], "from_point": t.get("from_point"),
                "to_point": t.get("to_point"), "duration_minutes": t["duration_minutes"], "pricing": t["pricing"],
                "service_from": t.get("service_from"), "service_until": t.get("service_until")}
        meta.update(extra or {})
        return {
            "item_id": nid("tr"), "type": "transfer", "name": t["name"], "city": city, "status": status,
            "catalog_id": t["transfer_id"], "room_id": None, "start": fmt_dt(opt.pickup), "end": fmt_dt(opt.end),
            "quantity": opt.quantity, "price_inr": opt.price, "booking": None, "sources": [], "warnings": [], "meta": meta,
        }

    h0, hN = hotels[0][0], hotels[-1][0]
    opts = ts.arrival_options(cat, arr_f, h0, party, spec.get("arrival_transfer"))
    if not opts:
        raise BuildError(explain_arrival(cat, arr_f, h0))
    arr_opt = opts[0]
    items.append(transfer_item(cat.transfers[arr_opt.transfer_id], arr_opt, h0["city"], "ARRIVAL"))
    opts = ts.return_options(cat, ret_f, hN, party, spec.get("return_transfer"))
    if not opts:
        raise BuildError(explain_return(cat, ret_f, hN))
    ret_opt = opts[0]
    items.append(transfer_item(cat.transfers[ret_opt.transfer_id], ret_opt, hN["city"], "RETURN"))

    # ---- intercity ------------------------------------------------------
    forced = list(spec.get("intercity") or [])
    change_end: Dict[date, "datetime"] = {}
    for i in range(len(cities) - 1):
        day = dates[i][1]
        f = forced[i] if i < len(forced) else None
        opts = ts.intercity_options(cat, country, cities[i]["city"], cities[i + 1]["city"], day, party, f)
        if not opts:
            raise BuildError(f"No {cities[i]['city']} → {cities[i + 1]['city']} transfer is available on {day:%d %b}.")
        o = opts[0]
        t = cat.transfers[o.transfer_id]
        change_end[day] = o.end
        items.append(transfer_item(t, o, cities[i + 1]["city"], "INTERCITY",
                                   {"from_city": cities[i]["city"], "to_city": cities[i + 1]["city"]}))

    # ---- attractions ------------------------------------------------------
    for a in sorted(spec.get("attractions", []), key=lambda x: (x["date"], x["start"])):
        att = cat.attractions.get(a["attraction_id"])
        if not att:
            raise BuildError(f"Unknown attraction {a['attraction_id']}.")
        d = date.fromisoformat(a["date"])
        s = at(d, a["start"])
        items.append({
            "item_id": nid("att"), "type": "attraction", "name": att["name"], "city": att["city"], "status": status,
            "catalog_id": att["attraction_id"], "room_id": None, "start": fmt_dt(s),
            "end": fmt_dt(s + timedelta(minutes=att["visit_minutes"])), "quantity": T,
            "price_inr": attraction_price(att, party), "booking": None, "sources": [], "warnings": [],
            "meta": {"category": att["category"], "visit_minutes": att["visit_minutes"], "image": att.get("image"),
                     "open_from": att["open_from"], "open_until": att["open_until"], "name_ja": att.get("name_ja"),
                     "child_friendly": att.get("child_friendly")},
        })

    # ---- advisory warnings (G1) ---------------------------------------------
    h_items = [i for i in items if i["type"] == "hotel"]
    arr_end = arr_opt.end
    if hm(h0["check_in_from"]) > arr_end.hour * 60 + arr_end.minute:
        h_items[0]["warnings"].append(
            f"You reach the hotel around {arr_end:%H:%M}, before check-in opens at {h0['check_in_from']}. "
            f"Ask for early check-in or luggage storage.")
    for idx in range(1, len(hotels)):
        e = change_end[dates[idx - 1][1]]
        hh = hotels[idx][0]
        if hm(hh["check_in_from"]) > e.hour * 60 + e.minute:
            h_items[idx]["warnings"].append(
                f"The {cities[idx - 1]['city']} → {cities[idx]['city']} transfer arrives around {e:%H:%M}, before "
                f"check-in at {hh['check_in_from']}. Ask for luggage storage.")
    ret_pick = ret_opt.pickup
    if ret_pick.hour * 60 + ret_pick.minute < hm("06:00"):
        h_items[-1]["warnings"].append(f"Very early start: you leave the hotel at {ret_pick:%H:%M} on {end:%d %b}.")

    order = {"flight": 0, "transfer": 1, "hotel": 2, "attraction": 3}
    items.sort(key=lambda i: (i["start"], order[i["type"]], i["item_id"]))
    total = sum(i["price_inr"] for i in items)
    if reference:
        for i in items:
            i["status"] = "BOOKED"
            i["booking"] = {"reference": reference}
    return {
        "trip_id": package_id,
        "traveler": {"name": req.get("name") or "Traveler", "home_airport": req["departure_airport"],
                     "adults": party.adults, "children": party.children, "child_ages": list(party.child_ages)},
        "start_date": start.isoformat(), "end_date": end.isoformat(), "country": country,
        "budget_inr": req["budget_inr"], "total_inr": total, "items": items,
    }


# --------------------------------------------------------------------------------------
def travel_minutes(cat, trip) -> int:
    n = 0
    for i in trip["items"]:
        if i["type"] == "flight":
            n += cat.flights[i["catalog_id"]]["duration_minutes"]
        elif i["type"] == "transfer" and (i["meta"] or {}).get("direction") == "INTERCITY":
            n += cat.transfers[i["catalog_id"]]["duration_minutes"]
    return n


def avg_stars(trip) -> float:
    hs = [i for i in trip["items"] if i["type"] == "hotel"]
    nights = sum(i["meta"]["nights"] for i in hs)
    return round(sum(i["meta"]["stars"] * i["meta"]["nights"] for i in hs) / nights, 2) if nights else 0


def summary(cat, trip) -> dict:
    b = breakdown(trip["items"])
    budget = trip["budget_inr"]
    return {
        "total_inr": b["total"], "budget_inr": budget, "remaining_inr": budget - b["total"],
        "within_budget": b["total"] <= budget, "breakdown": {k: v for k, v in b.items() if k != "total"},
        "travel_minutes": travel_minutes(cat, trip), "avg_stars": avg_stars(trip),
        "nights": (date.fromisoformat(trip["end_date"]) - date.fromisoformat(trip["start_date"])).days,
        "cities": [i["city"] for i in trip["items"] if i["type"] == "hotel"],
    }


def itinerary(cat, trip) -> List[dict]:
    """Chronological day-by-day view built from the trip items."""
    start = date.fromisoformat(trip["start_date"])
    end = date.fromisoformat(trip["end_date"])
    days: Dict[date, List[dict]] = {}

    def add(d, minute_key, ev):
        days.setdefault(d, []).append((minute_key, ev))

    for it in trip["items"]:
        s = parse_dt(it["start"]) if "T" in it["start"] else None
        meta = it.get("meta") or {}
        base = {"item_id": it["item_id"], "city": it["city"], "price_inr": it["price_inr"], "type": it["type"], "meta": meta,
                "warnings": it["warnings"], "catalog_id": it["catalog_id"]}
        if it["type"] == "flight":
            e = parse_dt(it["end"])
            add(s.date(), s, {**base, "time": f"{s:%H:%M}", "end_time": f"{e:%H:%M}", "end_date": e.date().isoformat(),
                              "title": it["name"], "subtitle": f"{meta['airline']} · {'Direct' if meta['stops'] == 0 else '1 stop'} · "
                              f"{meta['duration_minutes'] // 60}h {meta['duration_minutes'] % 60:02d}m · lands {e:%d %b %H:%M}"})
        elif it["type"] == "transfer":
            e = parse_dt(it["end"])
            label = {"ARRIVAL": "Airport → hotel", "RETURN": "Hotel → airport", "INTERCITY": f"{meta.get('from_city')} → {meta.get('to_city')}"}.get(meta.get("direction"), "Transfer")
            add(s.date(), s, {**base, "time": f"{s:%H:%M}", "end_time": f"{e:%H:%M}", "title": it["name"],
                              "subtitle": f"{label} · {meta['duration_minutes']} min · {it['quantity']} {'vehicle(s)' if meta['pricing'] == 'PER_VEHICLE' else 'passenger(s)'}"})
        elif it["type"] == "hotel":
            ci, co = date.fromisoformat(it["start"]), date.fromisoformat(it["end"])
            add(ci, parse_dt(ci.isoformat() + "T" + meta["check_in_from"]), {**base, "time": meta["check_in_from"], "kind": "check-in",
                "title": f"Check in · {it['name']}", "subtitle": f"{meta['room_name']} × {it['quantity']} · {meta['nights']} nights · {'★' * meta['stars']} · {meta['area']}"})
            add(co, parse_dt(co.isoformat() + "T" + meta["check_out_until"]), {**base, "time": meta["check_out_until"], "kind": "check-out", "price_inr": 0,
                "title": f"Check out · {it['name']}", "subtitle": f"by {meta['check_out_until']}", "warnings": []})
        else:
            e = parse_dt(it["end"])
            add(s.date(), s, {**base, "time": f"{s:%H:%M}", "end_time": f"{e:%H:%M}", "title": it["name"],
                              "subtitle": f"{meta['category'].replace('_', ' ').title()} · {meta['visit_minutes']} min"})
    first = min(days)
    out = []
    d = first
    hotel_items = [i for i in trip["items"] if i["type"] == "hotel"]
    while d <= end:
        evs = [ev for _, ev in sorted(days.get(d, []), key=lambda x: x[0])]
        city = None
        for h in hotel_items:
            if date.fromisoformat(h["start"]) <= d < date.fromisoformat(h["end"]):
                city = h["city"]
        if city is None and hotel_items:
            city = hotel_items[-1]["city"] if d >= end else hotel_items[0]["city"]
        out.append({"date": d.isoformat(), "day_number": (d - start).days + 1, "city": city,
                    "label": "Departure from home" if d < start else ("Return home" if d == end else None), "events": evs})
        d += timedelta(days=1)
    return out


def to_export(trip: dict) -> dict:
    """Strict shared trip format (DATA_DICTIONARY section 4) without UI-only fields."""
    keys = ["item_id", "type", "name", "city", "status", "catalog_id", "room_id", "start", "end", "quantity",
            "price_inr", "booking", "sources", "warnings"]
    out = {k: trip[k] for k in ["trip_id", "traveler", "start_date", "end_date", "country", "budget_inr", "total_inr"]}
    out["items"] = [{k: it[k] for k in keys} for it in trip["items"]]
    return out
