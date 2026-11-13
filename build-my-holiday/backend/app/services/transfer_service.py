"""Airport and intercity transfers: compatibility, service windows, buffers, pricing."""
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import List, Optional

from .pricing_service import Party, transfer_price, transfer_quantity
from .timeutil import at, hm, in_window, parse_dt, window

ARRIVAL_BUFFER_MIN = 60     # pickup >= landing + 60
RETURN_BUFFER_MIN = 180     # at the airport >= 180 min before departure
INTERCITY_EARLIEST = 10 * 60 #10am


@dataclass(frozen=True)
class TransferOpt:
    transfer_id: str
    pickup: datetime
    end: datetime
    price: int
    quantity: int
    duration: int


def serves_hotel(t: dict, hotel: dict) -> bool:
    return t.get("city") == hotel["city"] and (t.get("area") is None or t.get("area") == hotel["area"])


def airport_candidates(cat, airport: str, hotel: dict) -> List[dict]:
    return [t for t in cat.airport_transfers.get((airport, hotel["city"]), []) if serves_hotel(t, hotel)]


def _sort(opts):
    return sorted(opts, key=lambda o: (o.price, o.duration, o.transfer_id))


def arrival_options(cat, flight: dict, hotel: dict, party: Party, forced: Optional[str] = None) -> List[TransferOpt]:
    arr = parse_dt(flight["arrival_local"])
    earliest = arr + timedelta(minutes=ARRIVAL_BUFFER_MIN)
    out = []
    for t in airport_candidates(cat, flight["to"], hotel):
        if forced and t["transfer_id"] != forced:
            continue
        a, b = window(t["service_from"], t["service_until"])
        m = earliest.hour * 60 + earliest.minute
        if earliest.date() != arr.date():
            continue  # pickup must stay on the landing day
        if m < a:
            m = a
        m5 = -(-m // 5) * 5  # tidy: round up to the next 5 minutes when still valid
        if m5 < 1440 and in_window(m5, t["service_from"], t["service_until"]):
            m = m5
        if m > 1439 or not in_window(m, t["service_from"], t["service_until"]):
            continue
        pick = at(arr.date(), m)
        out.append(TransferOpt(t["transfer_id"], pick, pick + timedelta(minutes=t["duration_minutes"]),
                               transfer_price(t, party), transfer_quantity(t, party), t["duration_minutes"]))
    return _sort(out)


def return_options(cat, flight: dict, hotel: dict, party: Party, forced: Optional[str] = None) -> List[TransferOpt]:
    dep = parse_dt(flight["departure_local"])
    out = []
    for t in airport_candidates(cat, flight["from"], hotel):
        if forced and t["transfer_id"] != forced:
            continue
        a, b = window(t["service_from"], t["service_until"])
        latest = dep - timedelta(minutes=RETURN_BUFFER_MIN + t["duration_minutes"])
        if latest.date() != dep.date():
            continue  # leave the hotel on the day of departure
        m = min(latest.hour * 60 + latest.minute, b, 1439)
        if m < a:
            continue
        m5 = (m // 5) * 5
        if m5 >= a:
            m = m5
        if not in_window(m, t["service_from"], t["service_until"]):
            continue
        pick = at(dep.date(), m)
        out.append(TransferOpt(t["transfer_id"], pick, pick + timedelta(minutes=t["duration_minutes"]),
                               transfer_price(t, party), transfer_quantity(t, party), t["duration_minutes"]))
    return _sort(out)


def intercity_options(cat, country: str, from_city: str, to_city: str, day: date, party: Party,
                      forced: Optional[str] = None) -> List[TransferOpt]:
    out = []
    for tid in cat.links.get((country, from_city, to_city), []):
        if forced and tid != forced:
            continue
        t = cat.transfers[tid]
        a, b = window(t["service_from"], t["service_until"])
        last = min(b, 1439)
        freq = t.get("frequency_minutes")
        deps = list(range(a, last + 1, freq)) if freq else list(range(a, last + 1, 30))
        deps = [m for m in deps if m + t["duration_minutes"] <= 1439]
        if not deps:
            continue
        later = [m for m in deps if m >= INTERCITY_EARLIEST]
        m = later[0] if later else deps[0]
        pick = at(day, m)
        out.append(TransferOpt(tid, pick, pick + timedelta(minutes=t["duration_minutes"]),
                               transfer_price(t, party), transfer_quantity(t, party), t["duration_minutes"]))
    return _sort(out)
