from fastapi import APIRouter, HTTPException

from ..services import booking_service as booking
from ..services.package_service import NotFound

router = APIRouter(prefix="/api/reservations", tags=["reservations"])


@router.get("/{reference}")
def get_reservation(reference: str):
    try:
        return booking.lookup(reference)
    except NotFound:
        raise HTTPException(404, "Reservation not found")
