import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..catalog.catalog_loader import get_catalog
from ..schemas.export_format import ExportTrip
from ..schemas.package import AddAttraction, ChangeCities, ChangeFlight, ChangeHotel
from ..schemas.request import RequestInvalid, TripRequest
from ..services import booking_service as booking
from ..services import package_service as ps
from ..services.package_builder import to_export

log = logging.getLogger("bmh")
router = APIRouter(prefix="/api/packages", tags=["packages"])


class ConfirmBody(BaseModel):
    allow_over_budget: bool = False


def _wrap(fn):
    try:
        return fn()
    except ps.NotFound as e:
        raise HTTPException(404, str(e))
    except ps.ChangeRejected as e:
        log.warning("REFUSED: %s | rules: %s", e.message, [v["code"] for v in e.violations] or "-")
        raise HTTPException(409, {"message": e.message, "violations": e.violations})
    except RequestInvalid as e:
        log.warning("INVALID REQUEST: %s", [(x["field"], x["message"]) for x in e.errors])
        raise HTTPException(422, {"message": str(e), "errors": e.errors})


@router.post("/generate")
def generate(req: TripRequest):
    return _wrap(lambda: ps.generate_packages(get_catalog(), req))


@router.get("/{package_id}")
def get_package(package_id: str):
    return _wrap(lambda: ps.get_payload(get_catalog(), package_id))


@router.get("/{package_id}/options")
def options(package_id: str):
    return _wrap(lambda: ps.group_options(get_catalog(), package_id))


@router.get("/{package_id}/export", response_model=ExportTrip)
def export(package_id: str):
    p = _wrap(lambda: ps.get_payload(get_catalog(), package_id))
    return to_export(p["trip"])


@router.get("/{package_id}/alternatives/flights")
def flight_alts(package_id: str, direction: str):
    return _wrap(lambda: ps.flight_alternatives(get_catalog(), package_id, direction))


@router.get("/{package_id}/alternatives/hotels")
def hotel_alts(package_id: str, city: str):
    return _wrap(lambda: ps.hotel_alternatives(get_catalog(), package_id, city))


@router.get("/{package_id}/attractions")
def attraction_list(package_id: str):
    return _wrap(lambda: ps.attraction_catalog(get_catalog(), package_id))


@router.get("/{package_id}/city-plans")
def city_plans(package_id: str):
    return _wrap(lambda: ps.city_plan_options(get_catalog(), package_id))


@router.patch("/{package_id}/flight")
def change_flight(package_id: str, body: ChangeFlight):
    cat = get_catalog()
    return _wrap(lambda: ps.modify(cat, package_id, ps.change_flight_mutator(cat, body.direction, body.flight_id)))


@router.patch("/{package_id}/hotel")
def change_hotel(package_id: str, body: ChangeHotel):
    cat = get_catalog()
    return _wrap(lambda: ps.modify(cat, package_id, ps.change_hotel_mutator(cat, body.city, body.hotel_id, body.room_id)))


@router.post("/{package_id}/attractions")
def add_attraction(package_id: str, body: AddAttraction):
    cat = get_catalog()
    return _wrap(lambda: ps.modify(cat, package_id, ps.add_attraction_mutator(cat, None, body.attraction_id, body.date, body.start)))


@router.delete("/{package_id}/attractions/{attraction_id}")
def remove_attraction(package_id: str, attraction_id: str):
    cat = get_catalog()
    return _wrap(lambda: ps.modify(cat, package_id, ps.remove_attraction_mutator(cat, attraction_id)))


@router.post("/{package_id}/cities")
def change_cities(package_id: str, body: ChangeCities):
    cat = get_catalog()
    return _wrap(lambda: ps.change_cities(cat, package_id, [(p.city, p.nights) for p in body.plan]))


@router.post("/{package_id}/confirm")
def confirm(package_id: str, body: Optional[ConfirmBody] = None):
    cat = get_catalog()
    return _wrap(lambda: booking.confirm(cat, package_id, bool(body and body.allow_over_budget)))
