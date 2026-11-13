from fastapi import APIRouter, HTTPException

from ..catalog.catalog_loader import get_catalog

router = APIRouter(prefix="/api/catalog", tags=["catalog"])


@router.get("")
def catalog():
    return get_catalog().public()


@router.get("/hotels")
def hotels(city: str):
    cat = get_catalog()
    return [{**h, "rooms": cat.rooms_by_hotel[h["hotel_id"]]} for h in cat.hotels_by_city.get(city, [])]


@router.get("/attractions")
def attractions(city: str):
    return get_catalog().attractions_by_city.get(city, [])
