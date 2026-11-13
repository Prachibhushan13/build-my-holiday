"""Request model + semantic validation with traveler-friendly messages (M1)."""
from datetime import date
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict


class TripRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: Optional[str] = "Traveler"
    departure_city: Any = None
    country: Any = None
    start_date: Any = None
    nights: Any = None
    adults: Any = None
    children: Any = None
    child_ages: Any = None
    budget_inr: Any = None


class RequestInvalid(Exception):
    def __init__(self, errors: List[dict]):
        self.errors = errors
        super().__init__("; ".join(e["message"] for e in errors))


def _int(v) -> Optional[int]:
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, float) and v == int(v):
        return int(v)
    if isinstance(v, str) and v.strip().lstrip("-").isdigit():
        return int(v.strip())
    return None


def normalize_request(cat, r: TripRequest) -> dict:
    """Returns the normalised request dict used everywhere, or raises RequestInvalid."""
    errs: List[dict] = []

    def err(field, msg):
        errs.append({"field": field, "message": msg})

    rules = cat.rules
    dep_airport = dep_city = None
    if not r.departure_city or not isinstance(r.departure_city, str):
        err("departure_city", "Choose a departure city.")
    else:
        dep_airport = cat.departure_airport(r.departure_city)
        if not dep_airport:
            names = ", ".join(c["city"] for c in cat.departure_cities)
            err("departure_city", f"'{r.departure_city}' is not a departure city. Choose one of: {names}.")
        else:
            dep_city = next(c["city"] for c in cat.departure_cities if c["airport"] == dep_airport)
    country = None
    if not r.country or not isinstance(r.country, str):
        err("country", "Choose a destination country.")
    else:
        country = cat.country_name(r.country)
        if not country:
            err("country", f"'{r.country}' is not available. Choose one of: {', '.join(cat.countries)}.")
    start = None
    if not r.start_date:
        err("start_date", "Enter the holiday start date.")
    else:
        try:
            start = date.fromisoformat(str(r.start_date)[:10])
        except ValueError:
            err("start_date", "Holiday start date must be a valid date (YYYY-MM-DD).")
    nights = _int(r.nights)
    if nights is None:
        err("nights", "Number of nights must be a whole number.")
    elif not rules["min_nights"] <= nights <= rules["max_nights"]:
        err("nights", f"Nights must be between {rules['min_nights']} and {rules['max_nights']}.")
    adults = _int(r.adults)
    if adults is None or adults < 1:
        err("adults", "At least 1 adult is required.")
    elif adults > 30:
        err("adults", "Please enter 30 adults or fewer.")
    ages_raw = r.child_ages if r.child_ages is not None else []
    ages: List[int] = []
    if not isinstance(ages_raw, list):
        err("child_ages", "Child ages must be a list of numbers.")
    else:
        for i, a in enumerate(ages_raw):
            ai = _int(a)
            if ai is None or not 0 <= ai <= 17:
                err("child_ages", f"Child {i + 1}: age must be a whole number from 0 to 17 (a traveller aged 18 or more is an adult).")
            else:
                ages.append(ai)
        if len(ages) > 30:
            err("child_ages", "Please enter 30 children or fewer.")
    if r.children is not None:
        c = _int(r.children)
        if c is None or c < 0:
            err("children", "Number of children must be 0 or more.")
        elif isinstance(ages_raw, list) and c != len(ages_raw):
            err("children", f"You entered {c} child(ren) but {len(ages_raw)} age(s). Give one age (0–17) per child.")
    budget = None
    try:
        budget = float(r.budget_inr) if r.budget_inr not in (None, "") and not isinstance(r.budget_inr, bool) else None
    except (TypeError, ValueError):
        budget = None
    if budget is None or budget <= 0:
        err("budget_inr", "Budget must be a positive amount in INR.")
    if errs:
        raise RequestInvalid(errs)
    return {
        "name": (r.name or "Traveler").strip()[:60] or "Traveler",
        "departure_city": dep_city, "departure_airport": dep_airport, "country": country,
        "start_date": start.isoformat(), "nights": nights, "adults": adults, "child_ages": ages,
        "budget_inr": int(round(budget)),
    }
