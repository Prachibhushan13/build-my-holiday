from dataclasses import dataclass
from datetime import date, timedelta
from functools import lru_cache
from typing import List

from .pricing_service import rooms_needed, hotel_price


@dataclass(frozen=True)
class HotelOpt:
    hotel_id: str
    room_id: str
    city: str
    area: str
    stars: int
    k: int
    price: int
    nights: int

    @property
    def key(self):
        return (self.hotel_id, self.room_id)


def stay_available(cat, room_id: str, check_in: date, nights: int, k: int) -> bool:
    return all(cat.rooms_left(room_id, check_in + timedelta(days=i)) >= k for i in range(nights))


def hotel_options(cat, city: str, check_in: date, nights: int, adults: int, children: int) -> List[HotelOpt]:
    """Every (hotel, room type) in the city that fits the party and is free on all nights."""
    out = []
    for h in cat.hotels_by_city.get(city, []):
        for r in cat.rooms_by_hotel.get(h["hotel_id"], []):
            k = rooms_needed(r, adults, children)
            if k is None or not stay_available(cat, r["room_id"], check_in, nights, k):
                continue
            out.append(HotelOpt(h["hotel_id"], r["room_id"], city, h["area"], h["stars"], k,
                                hotel_price(r, k, nights), nights))
    return sorted(out, key=lambda o: (o.price, -o.stars, o.hotel_id, o.room_id))


def why_no_hotel(cat, city: str, check_in: date, nights: int, adults: int, children: int) -> str:
    hs = cat.hotels_by_city.get(city, [])
    if not hs:
        return f"there are no hotels in {city}"
    fit = [r for h in hs for r in cat.rooms_by_hotel[h["hotel_id"]] if rooms_needed(r, adults, children)]
    if not fit:
        return f"no room type in {city} can accommodate {adults} adult(s) and {children} child(ren)"
    return f"no room that fits your group is free for every night in {city} ({check_in} for {nights} nights)"
