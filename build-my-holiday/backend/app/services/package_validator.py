"""Central rule checker: the single source of truth for "is this package correct?".
It works only from the exported trip (items + catalog), never from builder internals, so the same
checks run on generated packages, on every modification, at confirmation, and on re-imported JSON."""
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

from . import transfer_service as ts
from .attraction_service import is_open_on
from .hotel_service import stay_available
from .pricing_service import (Party, attraction_price, flight_price, hotel_price, room_fits,
                              transfer_price)
from .timeutil import hm, in_window, parse_dt, weekday

TOL = 0.01


def _close(a, b) -> bool:
    return abs(a - b) <= max(1, TOL * max(abs(a), abs(b)))


def validate_trip(cat, trip: dict, first_package: bool = False) -> List[dict]:
    v: List[dict] = []

    def bad(code: str, message: str, item: Optional[dict] = None):
        v.append({"code": code, "message": message, "item_id": item["item_id"] if item else None})

    rules = cat.rules
    tr = trip.get("traveler") or {}
    adults = tr.get("adults", 0)
    ages = tr.get("child_ages") or []
    if tr.get("children", len(ages)) != len(ages):
        bad("TRAVELERS", "children count does not match the number of child ages")
    if adults < 1:
        bad("TRAVELERS", "At least one adult is required")
    if any((not isinstance(a, int)) or a < 0 or a > 17 for a in ages):
        bad("TRAVELERS", "Child ages must be between 0 and 17")
    party = Party(adults, tuple(ages))
    T = party.travellers

    try:
        start = date.fromisoformat(trip["start_date"])
        end = date.fromisoformat(trip["end_date"])
    except Exception:
        bad("DATES", "start_date / end_date are not valid dates")
        return v
    nights = (end - start).days
    if not (rules["min_nights"] <= nights <= rules["max_nights"]):
        bad("NIGHTS", f"Trip is {nights} nights; it must be {rules['min_nights']}–{rules['max_nights']}")
    win = rules["data_window"]
    if start < date.fromisoformat(win["first_night"]):
        bad("DATES", f"Holiday start {start} is before {win['first_night']}")
    if end > date.fromisoformat(win["last_departure"]):
        bad("DATES", f"Return day {end} is after {win['last_departure']}")

    country = trip.get("country")
    if country not in cat.countries:
        bad("COUNTRY", f"Unknown country {country!r}")
        return v
    country_cities = set(cat.country_cities(country))
    items = trip.get("items") or []
    by_type: Dict[str, List[dict]] = {"flight": [], "hotel": [], "transfer": [], "attraction": []}
    for it in items:
        if it.get("type") not in by_type:
            bad("ITEM", f"Unknown item type {it.get('type')!r}", it)
            continue
        by_type[it["type"]].append(it)

    # ---------------- hotels -------------------------------------------------
    hotels = sorted(by_type["hotel"], key=lambda i: i["start"])
    hinfo = []  # (item, hotel, room, ci, co)
    if not hotels:
        bad("HOTEL", "The package has no hotel")
    seen_cities = set()
    for h in hotels:
        hot = cat.hotels.get(h["catalog_id"])
        room = cat.rooms.get(h.get("room_id") or "")
        if not hot:
            bad("HOTEL", f"Unknown hotel {h['catalog_id']}", h)
            continue
        if not room or room["hotel_id"] != hot["hotel_id"]:
            bad("ROOM", f"Room {h.get('room_id')} does not belong to {hot['name']}", h)
            continue
        ci, co = date.fromisoformat(h["start"][:10]), date.fromisoformat(h["end"][:10])
        n = (co - ci).days
        k = h["quantity"]
        if hot["city"] not in country_cities:
            bad("CITY", f"{hot['city']} is not in {country}", h)
        if hot["city"] in seen_cities:
            bad("CITY_REPEAT", f"{hot['city']} appears more than once in the plan", h)
        seen_cities.add(hot["city"])
        if n < rules["min_nights_per_city"]:
            bad("CITY_NIGHTS", f"{hot['city']} has only {n} night(s); each city needs at least {rules['min_nights_per_city']}", h)
        if not room_fits(room, k, adults, party.children):
            bad("OCCUPANCY", f"{k} × {room['name']} cannot house {adults} adult(s) and {party.children} child(ren) "
                             f"(rules: adults ≤ k×max_adults, guests ≤ k×(max_adults+max_children), adults ≥ k)", h)
        if n > 0 and not stay_available(cat, room["room_id"], ci, n, k):
            bad("AVAILABILITY", f"{hot['name']} has fewer than {k} {room['name']} room(s) free on some night of {ci}–{co}", h)
        if not _close(h["price_inr"], hotel_price(room, k, n)):
            bad("PRICE", f"Hotel price {h['price_inr']} should be {hotel_price(room, k, n)}", h)
        hinfo.append((h, hot, room, ci, co))
    if hinfo:
        if hinfo[0][3] != start:
            bad("HOTEL_DATES", f"First hotel night must be the holiday start date {start}")
        for a, b in zip(hinfo, hinfo[1:]):
            if a[4] != b[3]:
                bad("HOTEL_DATES", f"Hotel nights are not continuous between {a[1]['city']} and {b[1]['city']}")
        if hinfo[-1][4] != end:
            bad("HOTEL_DATES", "The last hotel must check out on the final day (no hotel night on the final day)")
        if sum((x[4] - x[3]).days for x in hinfo) != nights:
            bad("NIGHTS", "Nights across cities do not add up to the trip length")

    # ---------------- flights --------------------------------------------------
    home = tr.get("home_airport")
    flights = by_type["flight"]
    arr_item = ret_item = None
    arrs = [f for f in flights if (cat.flights.get(f["catalog_id"]) or {}).get("from") == home]
    rets = [f for f in flights if (cat.flights.get(f["catalog_id"]) or {}).get("to") == home]
    if len(flights) != 2 or len(arrs) != 1 or len(rets) != 1:
        bad("FLIGHTS", "The package needs exactly one arrival flight from your home airport and one return flight back")
    arr_f = ret_f = None
    if len(arrs) == 1:
        arr_item, arr_f = arrs[0], cat.flights[arrs[0]["catalog_id"]]
        if arr_f["arr_date"] != start.isoformat():
            bad("ARRIVAL_DATE", f"Arrival flight lands on {arr_f['arr_date']}, not the holiday start date {start}", arr_item)
        if hinfo and hinfo[0][1]["city"] not in (cat.airports.get(arr_f["to"], {}).get("serves_cities") or []):
            bad("ARRIVAL_AIRPORT", f"{arr_f['to']} does not serve {hinfo[0][1]['city']}", arr_item)
        if arr_f["seats_left"] < T:
            bad("SEATS", f"{arr_f['flight_number']} has {arr_f['seats_left']} seat(s) left for {T} traveller(s)", arr_item)
        if not _close(arr_item["price_inr"], flight_price(arr_f, T)):
            bad("PRICE", f"Flight price {arr_item['price_inr']} should be {flight_price(arr_f, T)}", arr_item)
    if len(rets) == 1:
        ret_item, ret_f = rets[0], cat.flights[rets[0]["catalog_id"]]
        if ret_f["dep_date"] != end.isoformat():
            bad("RETURN_DATE", f"Return flight departs on {ret_f['dep_date']}, not the last day {end}", ret_item)
        if hinfo and hinfo[-1][1]["city"] not in (cat.airports.get(ret_f["from"], {}).get("serves_cities") or []):
            bad("RETURN_AIRPORT", f"{ret_f['from']} does not serve {hinfo[-1][1]['city']}", ret_item)
        if ret_f["seats_left"] < T:
            bad("SEATS", f"{ret_f['flight_number']} has {ret_f['seats_left']} seat(s) left for {T} traveller(s)", ret_item)
        if not _close(ret_item["price_inr"], flight_price(ret_f, T)):
            bad("PRICE", f"Flight price {ret_item['price_inr']} should be {flight_price(ret_f, T)}", ret_item)

    # ---------------- transfers ---------------------------------------------------
    party_ = party
    arr_end: Optional[datetime] = None
    change_end: Dict[date, datetime] = {}
    arr_trs, ret_trs, ic_trs = [], [], []
    for t in by_type["transfer"]:
        rec = cat.transfers.get(t["catalog_id"])
        if not rec:
            bad("TRANSFER", f"Unknown transfer {t['catalog_id']}", t)
            continue
        s = parse_dt(t["start"])
        if not in_window(s.hour * 60 + s.minute, rec["service_from"], rec["service_until"]):
            bad("SERVICE_HOURS", f"{rec['name']} pickup {s:%H:%M} is outside its service hours {rec['service_from']}–{rec['service_until']}", t)
        if not _close(t["price_inr"], transfer_price(rec, party_)):
            bad("PRICE", f"Transfer price {t['price_inr']} should be {transfer_price(rec, party_)}", t)
        if rec.get("airport"):
            if arr_f and rec["airport"] == arr_f["to"] and s.date() == start:
                arr_trs.append((t, rec, s))
            elif ret_f and rec["airport"] == ret_f["from"] and s.date() == end:
                ret_trs.append((t, rec, s))
            else:
                bad("TRANSFER", f"{rec['name']} does not match the arrival or return airport/date", t)
        elif rec.get("from_city"):
            ic_trs.append((t, rec, s))
        else:
            if rec["city"] not in country_cities:
                bad("TRANSFER", f"City transfer {rec['name']} is outside {country}", t)
    if hinfo and arr_f:
        if len(arr_trs) != 1:
            bad("ARRIVAL_TRANSFER", "Exactly one airport → hotel transfer is required")
        for t, rec, s in arr_trs:
            hot = hinfo[0][1]
            if not ts.serves_hotel(rec, hot):
                bad("TRANSFER_AREA", f"{rec['name']} does not serve {hot['name']} ({hot['area']}, {hot['city']})", t)
            landing = parse_dt(arr_f["arrival_local"])
            if s < landing + timedelta(minutes=ts.ARRIVAL_BUFFER_MIN):
                bad("ARRIVAL_BUFFER", f"Pickup {s:%H:%M} is less than 60 minutes after landing at {landing:%H:%M}", t)
            arr_end = s + timedelta(minutes=rec["duration_minutes"])
    if hinfo and ret_f:
        if len(ret_trs) != 1:
            bad("RETURN_TRANSFER", "Exactly one hotel → airport transfer is required")
        for t, rec, s in ret_trs:
            hot = hinfo[-1][1]
            if not ts.serves_hotel(rec, hot):
                bad("TRANSFER_AREA", f"{rec['name']} does not serve {hot['name']} ({hot['area']}, {hot['city']})", t)
            dep = parse_dt(ret_f["departure_local"])
            if s + timedelta(minutes=rec["duration_minutes"]) > dep - timedelta(minutes=ts.RETURN_BUFFER_MIN):
                bad("RETURN_BUFFER", f"You would reach the airport at {(s + timedelta(minutes=rec['duration_minutes'])):%H:%M}, "
                                     f"less than 180 minutes before the {dep:%H:%M} departure", t)
    used = set()
    for a, b in zip(hinfo, hinfo[1:]):
        day = a[4]
        match = [x for x in ic_trs if x[1].get("from_city") == a[1]["city"] and x[1].get("to_city") == b[1]["city"] and x[2].date() == day]
        if len(match) != 1:
            bad("INTERCITY", f"Exactly one {a[1]['city']} → {b[1]['city']} transfer is required on {day}")
            continue
        t, rec, s = match[0]
        used.add(t["item_id"])
        if rec["transfer_id"] not in cat.links.get((country, a[1]["city"], b[1]["city"]), []):
            bad("INTERCITY", f"{rec['name']} is not a valid link {a[1]['city']} → {b[1]['city']}", t)
        change_end[day] = s + timedelta(minutes=rec["duration_minutes"])
    for t, rec, s in ic_trs:
        if t["item_id"] not in used:
            bad("INTERCITY", f"Unexpected city-to-city transfer {rec['name']} on {s.date()}", t)

    # ---------------- attractions ----------------------------------------------------
    atts = by_type["attraction"]
    seen_att = set()
    per_day: Dict[date, List[tuple]] = {}
    night_city = {}
    for h, hot, room, ci, co in hinfo:
        d = ci
        while d < co:
            night_city[d] = hot["city"]
            d += timedelta(days=1)
    for a in atts:
        rec = cat.attractions.get(a["catalog_id"])
        if not rec:
            bad("ATTRACTION", f"Unknown attraction {a['catalog_id']}", a)
            continue
        s = parse_dt(a["start"])
        d = s.date()
        sm = s.hour * 60 + s.minute
        em = sm + rec["visit_minutes"]
        if rec["attraction_id"] in seen_att:
            bad("ATTRACTION_REPEAT", f"{rec['name']} is scheduled more than once", a)
        seen_att.add(rec["attraction_id"])
        if d == end:
            bad("FINAL_DAY", f"{rec['name']}: no attractions on the final day", a)
        elif d not in night_city:
            bad("ATTRACTION_DATE", f"{rec['name']} is scheduled outside the holiday", a)
        elif night_city[d] != rec["city"]:
            bad("ATTRACTION_CITY", f"{rec['name']} is in {rec['city']} but you sleep in {night_city[d]} that night", a)
        if weekday(d) not in rec["open_days"]:
            bad("CLOSED_DAY", f"{rec['name']} is closed on {weekday(d)}", a)
        if d.isoformat() in (rec.get("closed_dates") or []):
            bad("CLOSED_DATE", f"{rec['name']} is closed on {d}", a)
        if sm < hm(rec["open_from"]) or em > hm(rec["open_until"]):
            bad("OPENING_HOURS", f"{rec['name']} visit {sm // 60:02d}:{sm % 60:02d}–{em // 60:02d}:{em % 60:02d} does not fit opening hours {rec['open_from']}–{rec['open_until']}", a)
        if em > 1440:
            bad("OPENING_HOURS", f"{rec['name']} visit runs past midnight", a)
        if d == start and arr_end and s < arr_end:
            bad("BEFORE_ARRIVAL", f"{rec['name']} starts at {s:%H:%M} before you reach the hotel ({arr_end:%H:%M})", a)
        if d in change_end and s < change_end[d]:
            bad("BEFORE_ARRIVAL", f"{rec['name']} starts at {s:%H:%M} before you arrive in the new city ({change_end[d]:%H:%M})", a)
        if not _close(a["price_inr"], attraction_price(rec, party_)):
            bad("PRICE", f"Attraction price {a['price_inr']} should be {attraction_price(rec, party_)}", a)
        per_day.setdefault(d, []).append((sm, em, a, rec))
    for d, lst in per_day.items():
        lst.sort(key=lambda x: x[0])
        for x, y in zip(lst, lst[1:]):
            if y[0] < x[1]:
                bad("OVERLAP", f"{x[3]['name']} and {y[3]['name']} overlap on {d}", y[2])
    if first_package:
        full_days = []
        for h, hot, room, ci, co in hinfo:
            d = ci + timedelta(days=1)
            while d < co:
                full_days.append(d)
                d += timedelta(days=1)
        for d in full_days:
            n = len(per_day.get(d, []))
            if not 1 <= n <= 2:
                bad("DAILY_COUNT", f"{d} has {n} attractions; a full day needs 1–2")

    # ---------------- totals ---------------------------------------------------------
    total = sum(i.get("price_inr", 0) for i in items)
    if not _close(total, trip.get("total_inr", -1)):
        bad("TOTAL", f"total_inr {trip.get('total_inr')} does not equal the sum of item prices {total}")
    return v


def explain(violations: List[dict]) -> str:
    return "; ".join(x["message"] for x in violations[:4]) if violations else ""
