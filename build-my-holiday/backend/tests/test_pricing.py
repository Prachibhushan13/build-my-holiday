import math

from app.services.package_builder import assemble
from app.services.package_generator import generate
from app.services.pricing_service import (Party, attraction_price, breakdown, flight_price, hotel_price,
                                          transfer_price, transfer_quantity)
from app.schemas.request import TripRequest, normalize_request


def test_pricing_accuracy(cat):
    party = Party(2, (6,))
    taxi = cat.transfers["TR-NRT-ASA-TAXI"]               # PER_VEHICLE 13440, 4 pax
    assert transfer_price(taxi, party) == 13440 * math.ceil(3 / 4)
    assert transfer_price(taxi, Party(3, (1, 2))) == 13440 * 2      # 5 travellers -> 2 vehicles
    van = cat.transfers["TR-NRT-SJK-VAN"]
    assert transfer_quantity(van, Party(4, (3, 4, 5))) == 1       # 7 pax in an 8-seat van
    bus = cat.transfers["TR-NRT-ASA-BUS"]                 # PER_PERSON 1792 / child 896
    assert transfer_price(bus, party) == 2 * 1792 + 896
    train = cat.transfers["TR-TYO-KYO-01"]
    assert transfer_price(train, party) == 2 * 7935 + 3968
    no_child_price = {"pricing": "PER_PERSON", "price": {"amount": 100}}
    assert transfer_price(no_child_price, party) == 300     # child falls back to adult price
    att = cat.attractions["ATT-KYO-001"]                    # 280 / child 112
    assert attraction_price(att, party) == 2 * 280 + 112
    nochild = {"price_per_person": {"amount": 500}}
    assert attraction_price(nochild, party) == 1500
    f = cat.flights["FL-401"]
    assert flight_price(f, 3) == 25200 * 3 == 75600
    room = cat.rooms["RM-TYO-001-A"]
    assert hotel_price(room, 2, 5) == 6440 * 2 * 5


def test_total_equals_sum_of_items(cat):
    req = normalize_request(cat, TripRequest(departure_city="Bengaluru", country="Japan", start_date="2027-04-10", nights=6,
                                             adults=2, child_ages=[6], budget_inr=350000))
    for spec in generate(cat, req)["specs"].values():
        trip = assemble(cat, spec, "t")
        assert trip["total_inr"] == sum(i["price_inr"] for i in trip["items"]) == breakdown(trip["items"])["total"]
