from pydantic import BaseModel


class ReservationRef(BaseModel):
    reference: str
