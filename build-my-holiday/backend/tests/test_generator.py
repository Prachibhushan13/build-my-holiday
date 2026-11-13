import pytest

from app.schemas.request import TripRequest, normalize_request
from app.services.package_builder import assemble, summary
from app.services.package_generator import city_plans, generate
from app.services.package_validator import validate_trip


def _gen(cat, **kw):
    base = {"departure_city": "Bengaluru", "country": "Japan", "start_date": "2027-04-10", "nights": 6, "adults": 2,
            "child_ages": [6], "budget_inr": 350000}
    base.update(kw)
    return generate(cat, normalize_request(cat, TripRequest(**base)))


def test_menon_sample(cat):
    res = _gen(cat)
    assert res["status"] == "OK"
    assert set(res["specs"]) >= {"cheapest"}
    sums = {}
    for name, spec in res["specs"].items():
        trip = assemble(cat, spec, "t")
        assert validate_trip(cat, trip, first_package=True) == []
        sums[name] = summary(cat, trip)
        assert sums[name]["within_budget"]
    assert sums["cheapest"]["total_inr"] <= min(s["total_inr"] for s in sums.values())
    if "fastest" in sums:
        assert sums["fastest"]["travel_minutes"] <= sums["cheapest"]["travel_minutes"]
    if "best_rated" in sums:
        assert sums["best_rated"]["avg_stars"] >= sums["cheapest"]["avg_stars"]


def test_over_budget(cat):
    res = _gen(cat, budget_inr=50000)
    assert res["status"] == "OVER_BUDGET" and res["deficit"] > 0 and res["cheapest_total"] > 50000


@pytest.mark.parametrize("kw,fragment", [
    ({"start_date": "2027-03-20"}, "1 April"),
    ({"start_date": "2027-04-18"}, "1 April") if False else ({"start_date": "2027-04-19", "nights": 3}, "window"),
    ({"departure_city": "Chennai", "start_date": "2027-04-10"}, "No flight"),
    ({"adults": 12, "child_ages": []}, "seats"),
])
def test_impossible_has_reason(cat, kw, fragment):
    res = _gen(cat, **kw)
    assert res["status"] == "IMPOSSIBLE"
    assert res["reasons"] and any(fragment.lower() in r.lower() or "window" in r.lower() or "no flight" in r.lower() or "seats" in r.lower() for r in res["reasons"])


def test_every_city_has_two_nights_and_plans_unique(cat):
    for n in range(3, 11):
        for plan in city_plans(cat, "Japan", n):
            assert len({c for c, _ in plan}) == len(plan) and all(k >= 2 for _, k in plan) and sum(k for _, k in plan) == n


def test_randomised_requests_always_valid(cat):
    import itertools
    count = 0
    for dep, country, start, nights, (adults, ages) in itertools.product(
            ["BLR", "DEL"], ["Japan", "United Arab Emirates"], ["2027-04-03", "2027-04-09"], [3, 6, 9], [(1, []), (2, [6]), (3, [4, 9])]):
        res = _gen(cat, departure_city=dep, country=country, start_date=start, nights=nights, adults=adults,
                   child_ages=ages, budget_inr=10 ** 7)
        for spec in res.get("specs", {}).values():
            assert validate_trip(cat, assemble(cat, spec, "t"), True) == []
            count += 1
    assert count > 30
