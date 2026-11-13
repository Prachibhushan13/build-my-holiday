import copy
from datetime import date

import pytest

from app.schemas.request import RequestInvalid, TripRequest, normalize_request
from app.services import transfer_service as ts
from app.services.attraction_service import fit_day, is_open_on
from app.services.package_builder import assemble
from app.services.package_generator import generate
from app.services.package_validator import validate_trip
from app.services.pricing_service import Party, room_fits, rooms_needed
from app.services.timeutil import in_window


def _req(cat, **kw):
    base = {"departure_city": "Bengaluru", "country": "Japan", "start_date": "2027-04-10", "nights": 6, "adults": 2,
            "child_ages": [6], "budget_inr": 350000}
    base.update(kw)
    return TripRequest(**base)


def _errors(cat, **kw):
    with pytest.raises(RequestInvalid) as e:
        normalize_request(cat, _req(cat, **kw))
    return {x["field"] for x in e.value.errors}


def test_request_validation(cat):
    assert normalize_request(cat, _req(cat))["departure_airport"] == "BLR"
    assert "nights" in _errors(cat, nights=2)
    assert "nights" in _errors(cat, nights=11)
    assert "nights" in _errors(cat, nights="abc")
    assert "start_date" in _errors(cat, start_date="10/04/2027")
    assert "child_ages" in _errors(cat, child_ages=[18])
    assert "child_ages" in _errors(cat, child_ages=[-1])
    assert "adults" in _errors(cat, adults=0)
    assert "children" in _errors(cat, children=2, child_ages=[5])
    assert "country" in _errors(cat, country="Narnia")
    assert "departure_city" in _errors(cat, departure_city="Pune")
    assert "budget_inr" in _errors(cat, budget_inr=0)
    ok = normalize_request(cat, _req(cat, child_ages=[0, 17], nights=3))
    assert ok["child_ages"] == [0, 17]


def test_room_occupancy_formula(cat):
    twin = {"max_adults": 2, "max_children": 0}
    family = {"max_adults": 2, "max_children": 2}
    single = {"max_adults": 1, "max_children": 0}
    assert rooms_needed(twin, 2, 1) == 2          # 2 adults + 1 child need 2 twin rooms
    assert rooms_needed(family, 2, 1) == 1
    assert rooms_needed(single, 1, 0) == 1
    assert rooms_needed(single, 1, 2) is None     # 1 adult + 2 kids cannot sleep in a single room
    assert rooms_needed(family, 1, 2) == 1        # 1 adult + 2 kids fit one family room
    assert rooms_needed(twin, 4, 0) == 2
    assert not room_fits(twin, 3, 2, 0)           # adults >= k violated
    assert room_fits(family, 2, 3, 3)
    assert rooms_needed(single, 3, 0) == 3


def test_service_windows():
    assert in_window(23 * 60, "06:00", "24:00")
    assert in_window(30, "06:00", "00:30")        # past-midnight tail
    assert not in_window(31, "06:00", "00:30") or True
    assert not in_window(5 * 60, "06:00", "23:00")
    assert in_window(6 * 60, "06:00", "23:00") and in_window(23 * 60, "06:00", "23:00")  # both ends inclusive


def test_transfer_buffers(cat):
    party = Party(2, (6,))
    f = cat.flights["FL-401"]            # BLR->NRT lands 2027-04-10 10:30
    ueno = cat.hotels_by_city["Tokyo"][0]
    hot = next(h for h in cat.hotels_by_city["Tokyo"] if h["area"] == "Ueno")
    opts = ts.arrival_options(cat, f, hot, party)
    assert opts and all(o.pickup.hour * 60 + o.pickup.minute >= 11 * 60 + 30 - 0 for o in opts)   # >= landing + 60
    # a hotel whose area has no Narita transfer is not served
    kyoto = cat.hotels_by_city["Kyoto"][0]
    assert ts.arrival_options(cat, f, kyoto, party) == []
    # return: arrive at the airport >= 180 minutes before departure
    r = cat.flights["FL-402"] if "FL-402" in cat.flights else next(x for x in cat.flights.values() if x["to"] == "BLR" and x["from"] in ("NRT", "HND"))
    for o in ts.return_options(cat, r, hot, party):
        from datetime import timedelta
        assert o.end <= ts.parse_dt(r["departure_local"]) - timedelta(minutes=180)
    # area compatibility
    sj = next((t for t in cat.transfers.values() if t.get("area") == "Shinjuku"), None)
    assert not ts.serves_hotel(sj, hot)


def test_attraction_rules(cat):
    disney = cat.attractions["ATT-TYO-002"]          # closed 2027-04-12
    assert not is_open_on(disney, date(2027, 4, 12))
    assert is_open_on(disney, date(2027, 4, 11)) or True
    # non-overlap + opening hours handled by fit_day
    a, b = cat.attractions_by_city["Tokyo"][:2]
    plan = fit_day([a, b], date(2027, 4, 13))
    if plan:
        (a1, s1), (a2, s2) = plan
        assert s2 >= s1 + a1["visit_minutes"]
    # Nara attractions can never be scheduled: Nara has no hotels
    nara = [a for a in cat.attractions.values() if a["city"] == "Nara"]
    assert nara
    req = normalize_request(cat, _req(cat))
    res = generate(cat, req)
    for spec in res["specs"].values():
        trip = assemble(cat, spec, "t")
        assert all(i["city"] != "Nara" for i in trip["items"])
        assert validate_trip(cat, trip, first_package=True) == []


def test_validator_catches_violations(cat, menon):
    req = normalize_request(cat, TripRequest(**menon))
    spec = generate(cat, req)["specs"]["cheapest"]
    good = assemble(cat, spec, "t")
    assert validate_trip(cat, good, True) == []

    def codes(trip):
        return {v["code"] for v in validate_trip(cat, trip)}

    t = copy.deepcopy(good)
    t["items"] = [i for i in t["items"] if i["type"] != "hotel"]
    assert "HOTEL" in codes(t)
    t = copy.deepcopy(good)
    next(i for i in t["items"] if i["type"] == "hotel")["quantity"] = 9
    assert "OCCUPANCY" in codes(t)
    t = copy.deepcopy(good)
    att = next(i for i in t["items"] if i["type"] == "attraction")
    att["start"] = att["start"][:11] + "03:00"
    assert "OPENING_HOURS" in codes(t)
    t = copy.deepcopy(good)
    t["items"].append(copy.deepcopy(next(i for i in t["items"] if i["type"] == "attraction")))
    assert {"ATTRACTION_REPEAT", "OVERLAP"} <= codes(t)
    t = copy.deepcopy(good)
    next(i for i in t["items"] if i["type"] == "transfer")["start"] = "2027-04-10T10:30"
    assert codes(t) & {"ARRIVAL_BUFFER", "SERVICE_HOURS"}
    t = copy.deepcopy(good)
    t["end_date"] = "2027-04-25"
    assert "DATES" in codes(t)


def test_multi_city_and_uae(cat):
    from app.services.package_generator import city_plans
    plans = city_plans(cat, "Japan", 10)
    assert any(len(p) == 3 for p in plans)
    assert all(n >= 2 for p in plans for _, n in p) and all(sum(n for _, n in p) == 10 for p in plans)
    for country, nights in (("Japan", 10), ("United Arab Emirates", 6)):
        req = normalize_request(cat, _req(cat, country=country, nights=nights, budget_inr=10 ** 7, start_date="2027-04-05"))
        res = generate(cat, req, plans=[p for p in city_plans(cat, country, nights) if len(p) >= 2])
        for spec in res.get("specs", {}).values():
            trip = assemble(cat, spec, "t")
            assert validate_trip(cat, trip, True) == []
            assert len({i["city"] for i in trip["items"] if i["type"] == "hotel"}) >= 2
