"""Exact shape of the shared trip format (DATA_DICTIONARY section 4)."""
from typing import List, Optional

from pydantic import BaseModel


class Booking(BaseModel):
    reference: str


class ExportItem(BaseModel):
    item_id: str
    type: str
    name: str
    city: str
    status: str
    catalog_id: str
    room_id: Optional[str] = None
    start: str
    end: Optional[str] = None
    quantity: int
    price_inr: int
    booking: Optional[Booking] = None
    sources: List[str] = []
    warnings: List[str] = []


class Traveler(BaseModel):
    name: str
    home_airport: str
    adults: int
    children: int
    child_ages: List[int]


class ExportTrip(BaseModel):
    trip_id: str
    traveler: Traveler
    start_date: str
    end_date: str
    country: str
    budget_inr: int
    total_inr: int
    items: List[ExportItem]
