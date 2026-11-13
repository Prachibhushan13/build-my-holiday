"""All price formulas in one place (INR, whole rupees)."""
import math
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass(frozen=True)
class Party:
    adults: int
    child_ages: tuple = field(default_factory=tuple)

    @property
    def children(self) -> int:
        return len(self.child_ages)

    @property
    def travellers(self) -> int:
        return self.adults + self.children


def flight_price(flight: dict, travellers: int) -> int:
    return flight["price_per_seat"]["amount"] * travellers


def rooms_needed(room: dict, adults: int, children: int) -> Optional[int]:
    """Smallest k such that k rooms of this type fit the party, or None.
    adults <= k*max_adults, adults+children <= k*(max_adults+max_children), adults >= k."""
    ma, mc = room["max_adults"], room["max_children"]
    if ma <= 0:
        return None
    for k in range(1, adults + 1):
        if adults <= k * ma and adults + children <= k * (ma + mc):
            return k
    return None


def room_fits(room: dict, k: int, adults: int, children: int) -> bool:
    ma, mc = room["max_adults"], room["max_children"]
    return k >= 1 and adults <= k * ma and adults + children <= k * (ma + mc) and adults >= k


def hotel_price(room: dict, k: int, nights: int) -> int:
    return room["price_per_night"]["amount"] * k * nights


def vehicles(transfer: dict, travellers: int) -> int:
    return math.ceil(travellers / transfer["max_passengers"])


def transfer_quantity(transfer: dict, party: Party) -> int:
    if transfer["pricing"] == "PER_VEHICLE":
        return vehicles(transfer, party.travellers)
    return party.travellers


def transfer_price(transfer: dict, party: Party) -> int:
    if transfer["pricing"] == "PER_VEHICLE":
        return transfer["price"]["amount"] * vehicles(transfer, party.travellers)
    adult = transfer["price"]["amount"]
    child = (transfer.get("child_price") or transfer["price"])["amount"]
    return party.adults * adult + party.children * child


def attraction_price(att: dict, party: Party) -> int:
    adult = att["price_per_person"]["amount"]
    child = (att.get("child_price") or att["price_per_person"])["amount"]
    return party.adults * adult + party.children * child


def breakdown(items: List[dict]) -> dict:
    out = {"flights": 0, "hotels": 0, "transfers": 0, "attractions": 0}
    key = {"flight": "flights", "hotel": "hotels", "transfer": "transfers", "attraction": "attractions"}
    for it in items:
        out[key[it["type"]]] += it["price_inr"]
    out["total"] = sum(out.values())
    return out
