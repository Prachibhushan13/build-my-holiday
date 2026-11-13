"""Loads and indexes the read-only JSON catalog once at start-up."""
import json
import os
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Optional

DEFAULT_DIR = Path(__file__).resolve().parents[3] / "data" / "catalog"


def _load(path: Path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


class Catalog:
    def __init__(self, directory: Optional[Path] = None):
        d = Path(directory or os.environ.get("BMH_CATALOG_DIR") or DEFAULT_DIR)
        self.directory = d
        self.destinations = _load(d / "destinations.json")
        self.rules = self.destinations["rules"]
        self.departure_cities = self.destinations["departure_cities"]
        self.countries = {c["name"]: c for c in self.destinations["countries"]}
        self.countries_by_code = {c["code"]: c for c in self.destinations["countries"]}
        self.city_country = {}
        for c in self.destinations["countries"]:
            for city in c["cities"]:
                self.city_country[city["name"]] = c["name"]
        # links[(country, from_city, to_city)] -> [transfer ids]
        self.links = {}
        for c in self.destinations["countries"]:
            for ln in c["links"]:
                self.links[(c["name"], ln["from_city"], ln["to_city"])] = ln["transfer_ids"]

        self.airports = {a["code"]: a for a in _load(d / "airports.json")}
        self.city_airports = defaultdict(list)  # city -> airports serving it
        for code, a in self.airports.items():
            for city in a.get("serves_cities") or []:
                self.city_airports[city].append(code)

        self.flights = {}
        self.flights_by_route = defaultdict(list)
        for f in _load(d / "flights.json"):
            f["dep_date"] = f["departure_local"][:10]
            f["arr_date"] = f["arrival_local"][:10]
            self.flights[f["flight_id"]] = f
            self.flights_by_route[(f["from"], f["to"])].append(f)

        self.hotels = {h["hotel_id"]: h for h in _load(d / "hotels.json")}
        self.hotels_by_city = defaultdict(list)
        for h in self.hotels.values():
            self.hotels_by_city[h["city"]].append(h)
        self.rooms = {r["room_id"]: r for r in _load(d / "rooms.json")}
        self.rooms_by_hotel = defaultdict(list)
        for r in self.rooms.values():
            self.rooms_by_hotel[r["hotel_id"]].append(r)
        self.avail = {(a["room_id"], a["date"]): a["rooms_left"] for a in _load(d / "availability.json")}

        self.transfers = {t["transfer_id"]: t for t in _load(d / "transfers.json")}
        self.airport_transfers = defaultdict(list)  # (airport, city) -> transfers
        for t in self.transfers.values():
            if t.get("airport"):
                self.airport_transfers[(t["airport"], t["city"])].append(t)

        self.attractions = {a["attraction_id"]: a for a in _load(d / "attractions.json")}
        self.attractions_by_city = defaultdict(list)
        for a in self.attractions.values():
            self.attractions_by_city[a["city"]].append(a)

    # ---- convenience -------------------------------------------------
    def departure_airport(self, value: str) -> Optional[str]:
        for dc in self.departure_cities:
            if value.strip().lower() in (dc["city"].lower(), dc["airport"].lower()):
                return dc["airport"]
        return None

    def country_name(self, value: str) -> Optional[str]:
        v = value.strip().lower()
        for c in self.destinations["countries"]:
            if v in (c["name"].lower(), c["code"].lower()):
                return c["name"]
        if v in ("uae", "emirates"):
            return "United Arab Emirates"
        return None

    def country_cities(self, country: str):
        return [c["name"] for c in self.countries[country]["cities"]]

    def rooms_left(self, room_id: str, d: date) -> int:
        return self.avail.get((room_id, d.isoformat()), 0)

    def public(self) -> dict:
        return {
            "departure_cities": self.departure_cities,
            "countries": [
                {"code": c["code"], "name": c["name"], "cities": [x["name"] for x in c["cities"]]}
                for c in self.destinations["countries"]
            ],
            "rules": self.rules,
        }


_catalog: Optional[Catalog] = None


def get_catalog() -> Catalog:
    global _catalog
    if _catalog is None:
        _catalog = Catalog()
    return _catalog
