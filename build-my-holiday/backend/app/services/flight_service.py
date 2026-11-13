from datetime import date, timedelta
from typing import List

from .pricing_service import flight_price


def arrival_flights(cat, dep_airport: str, first_city: str, start: date, travellers: int) -> List[dict]:
    out = []
    for ap in cat.city_airports.get(first_city, []):
        for f in cat.flights_by_route.get((dep_airport, ap), []):
            if f["arr_date"] == start.isoformat() and f["seats_left"] >= travellers:
                out.append(f)
    return sorted(out, key=lambda f: (f["price_per_seat"]["amount"], f["flight_id"]))


def return_flights(cat, dep_airport: str, last_city: str, end: date, travellers: int) -> List[dict]:
    out = []
    for ap in cat.city_airports.get(last_city, []):
        for f in cat.flights_by_route.get((ap, dep_airport), []):
            if f["dep_date"] == end.isoformat() and f["seats_left"] >= travellers:
                out.append(f)
    return sorted(out, key=lambda f: (f["price_per_seat"]["amount"], f["flight_id"]))


def flight_label(f: dict) -> str:
    return f"{f['flight_number']} {f['from']} to {f['to']}"


def flight_view(f: dict, travellers: int) -> dict:
    return {
        "flight_id": f["flight_id"], "airline": f["airline"], "flight_number": f["flight_number"],
        "from": f["from"], "to": f["to"], "departure_local": f["departure_local"][:16],
        "arrival_local": f["arrival_local"][:16], "stops": f["stops"],
        "duration_minutes": f["duration_minutes"], "seats_left": f["seats_left"],
        "price_per_seat": f["price_per_seat"]["amount"], "price_inr": flight_price(f, travellers),
    }
