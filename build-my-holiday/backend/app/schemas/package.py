from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class ChangeFlight(BaseModel):
    direction: str  # "arrival" | "return"
    flight_id: str


class ChangeHotel(BaseModel):
    city: str
    hotel_id: str
    room_id: Optional[str] = None


class AddAttraction(BaseModel):
    attraction_id: str
    date: Optional[str] = None
    start: Optional[str] = None  # HH:MM


class CityPlanItem(BaseModel):
    city: str
    nights: int


class ChangeCities(BaseModel):
    plan: List[CityPlanItem]
