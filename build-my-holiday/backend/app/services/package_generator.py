"""Deterministic constraint-search engine (no AI).

City rule: every ordered selection of distinct country cities whose consecutive pairs are linked in
destinations.json, with >= 2 nights per city summing to the requested nights, is a candidate plan.
For each plan the cheapest-feasible component choices are found exactly (flights x hotel/transfer
combinations, Pareto-pruned on price vs stars), then three winners are picked across all plans:
cheapest (min total), fastest (min flight + intercity minutes within budget) and best rated
(max night-weighted hotel stars within budget)."""
from dataclasses import dataclass, field
from datetime import date, timedelta
from itertools import permutations, product
from typing import Dict, List, Optional, Tuple

from . import transfer_service as ts
from .attraction_service import schedule_days
from .flight_service import arrival_flights, return_flights
from .hotel_service import HotelOpt, hotel_options, why_no_hotel
from .pricing_service import Party, attraction_price, flight_price


def compositions(total: int, parts: int, minimum: int):
    if parts == 1:
        if total >= minimum:
            yield (total,)
        return
    for first in range(minimum, total - minimum * (parts - 1) + 1):
        for rest in compositions(total - first, parts - 1, minimum):
            yield (first,) + rest


def city_plans(cat, country: str, nights: int) -> List[Tuple[Tuple[str, int], ...]]:
    cities = cat.country_cities(country)
    minimum = cat.rules["min_nights_per_city"]
    plans = []
    for k in range(1, min(len(cities), nights // minimum) + 1):
        for seq in permutations(cities, k):
            if any((country, a, b) not in cat.links for a, b in zip(seq, seq[1:])):
                continue
            for comp in compositions(nights, k, minimum):
                plans.append(tuple(zip(seq, comp)))
    return plans


def pareto(cands):
    """cands: (price, stars, payload). Keep options not beaten on both price and stars."""
    cands = sorted(cands, key=lambda c: (c[0], -c[1]))
    out, best = [], -1
    for c in cands:
        if c[1] > best:
            out.append(c)
            best = c[1]
    return out


class Ctx:
    def __init__(self, cat, req: dict):
        self.cat, self.req = cat, req
        self.party = Party(req["adults"], tuple(req["child_ages"]))
        self.start = date.fromisoformat(req["start_date"])
        self.nights = req["nights"]
        self.end = self.start + timedelta(days=self.nights)
        self.dep = req["departure_airport"]
        self.country = req["country"]
        self._ho, self._att, self._ar, self._rt = {}, {}, {}, {}
        self.blockers: Dict[str, int] = {}

    def block(self, msg):
        self.blockers[msg] = self.blockers.get(msg, 0) + 1

    def hotels(self, city, ci, nights):
        k = (city, ci, nights)
        if k not in self._ho:
            self._ho[k] = hotel_options(self.cat, city, ci, nights, self.party.adults, self.party.children)
        return self._ho[k]

    def arr_opts(self, flight, hotel_id):
        k = (flight["flight_id"], hotel_id)
        if k not in self._ar:
            self._ar[k] = ts.arrival_options(self.cat, flight, self.cat.hotels[hotel_id], self.party)
        return self._ar[k]

    def ret_opts(self, flight, hotel_id):
        k = (flight["flight_id"], hotel_id)
        if k not in self._rt:
            self._rt[k] = ts.return_options(self.cat, flight, self.cat.hotels[hotel_id], self.party)
        return self._rt[k]

    def attractions(self, plan, per_day):
        """(placements, cost) for every full day of the plan, or None when a day cannot be filled."""
        k = (plan, per_day)
        if k not in self._att:
            res, cost, cur = [], 0, self.start
            for city, n in plan:
                days = [cur + timedelta(days=i) for i in range(1, n)]
                sched = schedule_days(self.cat, city, days, self.party, per_day)
                if sched is None:
                    self._att[k] = None
                    break
                for d, lst in sched.items():
                    for a, s in lst:
                        res.append({"attraction_id": a["attraction_id"], "date": d.isoformat(), "start": s})
                        cost += attraction_price(a, self.party)
                cur += timedelta(days=n)
            else:
                self._att[k] = (sorted(res, key=lambda x: (x["date"], x["start"])), cost)
        return self._att[k]


@dataclass
class Selection:
    plan: tuple
    arrival: dict
    ret: dict
    hotels: List[HotelOpt]
    arr_tr: str
    ret_tr: str
    intercity: List[str]
    total: int = 0
    minutes: int = 0
    stars: int = 0


def intercity_combos(ctx, plan):
    """[(price, minutes, [transfer ids])] for all link choices on the city-change days."""
    per = []
    cur = ctx.start
    for i in range(len(plan) - 1):
        cur += timedelta(days=plan[i][1])
        opts = ts.intercity_options(ctx.cat, ctx.country, plan[i][0], plan[i + 1][0], cur, ctx.party)
        if not opts:
            return None
        per.append(opts)
    combos = []
    for pick in product(*per):
        combos.append((sum(o.price for o in pick), sum(o.duration for o in pick), [o.transfer_id for o in pick]))
    return combos or [(0, 0, [])]


def search(ctx: Ctx, plans, budget: int, fast: bool = False) -> Dict[str, Optional[Selection]]:
    """Scan all plans; return the best Selection per objective (keys: cheapest, fastest, best_rated)."""
    cat, party = ctx.cat, ctx.party
    T = party.travellers
    best = {"cheapest": (None, None), "fastest": (None, None), "best_rated": (None, None)}

    def offer(total, minutes, stars, make):
        key = (total, minutes, -stars)
        if best["cheapest"][0] is None or key < best["cheapest"][0]:
            best["cheapest"] = (key, make)
        if fast or total > budget:
            return
        key = (minutes, total, -stars)
        if best["fastest"][0] is None or key < best["fastest"][0]:
            best["fastest"] = (key, make)
        key = (-stars, total, minutes)
        if best["best_rated"][0] is None or key < best["best_rated"][0]:
            best["best_rated"] = (key, make)

    for plan in plans:
        att = ctx.attractions(plan, 1)
        if att is None:
            ctx.block("not enough open attractions to fill every full day with 1–2 visits")
            continue
        att_cost = att[1]
        first_city, last_city = plan[0][0], plan[-1][0]
        arrivals = arrival_flights(cat, ctx.dep, first_city, ctx.start, T)
        returns = return_flights(cat, ctx.dep, last_city, ctx.end, T)
        if not arrivals:
            ctx.block(f"no arrival flight on {ctx.start:%d %b %Y} into an airport serving {first_city} with {T} seats")
            continue
        if not returns:
            ctx.block(f"no return flight on {ctx.end:%d %b %Y} from an airport serving {last_city} with {T} seats")
            continue
        cur, ho, ok = ctx.start, [], True
        for city, n in plan:
            opts = ctx.hotels(city, cur, n)
            if not opts:
                ctx.block(why_no_hotel(cat, city, cur, n, party.adults, party.children))
                ok = False
                break
            ho.append((n, opts))
            cur += timedelta(days=n)
        if not ok:
            continue
        ic = intercity_combos(ctx, plan)
        if ic is None:
            ctx.block("no city-to-city transfer is available for this plan")
            continue
        if fast:
            ic = [min(ic)]

        if len(plan) == 1:
            n, opts = ho[0]
            for a in arrivals:
                for r in returns:
                    cands = []
                    for h in opts:
                        ao, ro = ctx.arr_opts(a, h.hotel_id), ctx.ret_opts(r, h.hotel_id)
                        if ao and ro:
                            cands.append((h.price + ao[0].price + ro[0].price, h.stars, (h, ao[0], ro[0])))
                    if not cands:
                        ctx.block(f"no airport transfer fits flights {a['flight_number']} / {r['flight_number']} (service hours or hotel area)")
                        continue
                    for price, stars, (h, ao, ro) in (cands[:1] if fast else pareto(cands)):
                        total = flight_price(a, T) + flight_price(r, T) + att_cost + price
                        offer(total, a["duration_minutes"] + r["duration_minutes"], stars * n,
                              lambda a=a, r=r, h=h, ao=ao, ro=ro, plan=plan: Selection(plan, a, r, [h], ao.transfer_id, ro.transfer_id, []))
            continue

        n0, opts0 = ho[0]
        nN, optsN = ho[-1]
        mids = []
        for n, opts in ho[1:-1]:
            fr = [(h.price, h.stars, h) for h in opts]
            mids.append([(p, s, h, n) for p, s, h in (fr[:1] if fast else pareto(fr))])
        firsts = {}
        for a in arrivals:
            c = []
            for h in opts0:
                ao = ctx.arr_opts(a, h.hotel_id)
                if ao:
                    c.append((h.price + ao[0].price, h.stars, (h, ao[0])))
            firsts[a["flight_id"]] = c[:1] if fast else pareto(c)
        lasts = {}
        for r in returns:
            c = []
            for h in optsN:
                ro = ctx.ret_opts(r, h.hotel_id)
                if ro:
                    c.append((h.price + ro[0].price, h.stars, (h, ro[0])))
            lasts[r["flight_id"]] = c[:1] if fast else pareto(c)
        for a in arrivals:
            F1 = firsts[a["flight_id"]]
            if not F1:
                ctx.block(f"no {a['to']} airport transfer fits flight {a['flight_number']} (arrival time vs service hours)")
                continue
            for r in returns:
                FN = lasts[r["flight_id"]]
                if not FN:
                    ctx.block(f"no {r['from']} airport transfer fits flight {r['flight_number']} (departure time vs service hours)")
                    continue
                base = flight_price(a, T) + flight_price(r, T) + att_cost
                fmin = a["duration_minutes"] + r["duration_minutes"]
                for p1, s1, (h1, ao) in F1:
                    for pN, sN, (hN, ro) in FN:
                        for mid in product(*mids):
                            mp = sum(m[0] for m in mid)
                            ms = sum(m[1] * m[3] for m in mid)
                            for icp, icm, ids in ic:
                                offer(base + p1 + pN + mp + icp, fmin + icm, s1 * n0 + sN * nN + ms,
                                      lambda a=a, r=r, h1=h1, hN=hN, ao=ao, ro=ro, mid=mid, ids=ids, plan=plan:
                                      Selection(plan, a, r, [h1] + [m[2] for m in mid] + [hN], ao.transfer_id, ro.transfer_id, ids))
    out = {}
    for k, (key, make) in best.items():
        if make is None:
            out[k] = None
        else:
            sel = make()
            sel.total, sel.minutes, sel.stars = key[0], key[1], -key[2]
            if k == "fastest":
                sel.total, sel.minutes, sel.stars = key[1], key[0], -key[2]
            if k == "best_rated":
                sel.total, sel.minutes, sel.stars = key[1], key[2], -key[0]
            out[k] = sel
    return out


def to_spec(ctx: Ctx, sel: Selection, per_day: int = 1) -> dict:
    att = ctx.attractions(sel.plan, per_day) or ctx.attractions(sel.plan, 1)
    return {
        "request": ctx.req,
        "cities": [{"city": c, "nights": n, "hotel_id": h.hotel_id, "room_id": h.room_id}
                   for (c, n), h in zip(sel.plan, sel.hotels)],
        "arrival_flight": sel.arrival["flight_id"], "return_flight": sel.ret["flight_id"],
        "arrival_transfer": sel.arr_tr, "return_transfer": sel.ret_tr, "intercity": list(sel.intercity),
        "attractions": att[0],
    }


def diagnose(ctx: Ctx) -> List[str]:
    """Why is no package possible? Ordered from the most fundamental blocker."""
    cat, req = ctx.cat, ctx.req
    T = ctx.party.travellers
    win = cat.rules["data_window"]
    reasons = []
    if ctx.start < date.fromisoformat(win["first_night"]) or ctx.end > date.fromisoformat(win["last_departure"]):
        reasons.append(f"Flights and rooms exist only from {win['first_night']} to {win['last_departure']}. "
                       f"Your trip ({ctx.start:%d %b %Y} – {ctx.end:%d %b %Y}) is outside that window.")
        return reasons
    airports = {ap for c in cat.country_cities(ctx.country) for ap in cat.city_airports.get(c, [])}
    arr_any = [f for ap in airports for f in cat.flights_by_route.get((ctx.dep, ap), []) if f["arr_date"] == ctx.start.isoformat()]
    ret_any = [f for ap in airports for f in cat.flights_by_route.get((ap, ctx.dep), []) if f["dep_date"] == ctx.end.isoformat()]
    if not arr_any:
        reasons.append(f"No flight from {req['departure_city']} to {ctx.country} lands on {ctx.start:%d %b %Y}.")
    elif not [f for f in arr_any if f["seats_left"] >= T]:
        reasons.append(f"Flights to {ctx.country} on {ctx.start:%d %b %Y} exist, but none has {T} free seats (the most is "
                       f"{max(f['seats_left'] for f in arr_any)}).")
    if not ret_any:
        reasons.append(f"No flight from {ctx.country} to {req['departure_city']} leaves on {ctx.end:%d %b %Y}.")
    elif not [f for f in ret_any if f["seats_left"] >= T]:
        reasons.append(f"Return flights on {ctx.end:%d %b %Y} exist, but none has {T} free seats.")
    for msg, n in sorted(ctx.blockers.items(), key=lambda x: -x[1]):
        reasons.append(msg[0].upper() + msg[1:] + ".")
    if not reasons:
        reasons.append("No combination of flights, hotels and transfers satisfies every travel rule for this request.")
    seen, out = set(), []
    for r in reasons:
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out[:6]


def generate(cat, req: dict, plans=None, fast: bool = False) -> dict:
    ctx = Ctx(cat, req)
    budget = req["budget_inr"]
    plans = plans if plans is not None else city_plans(cat, ctx.country, ctx.nights)
    win = cat.rules["data_window"]
    if ctx.start < date.fromisoformat(win["first_night"]) or ctx.end > date.fromisoformat(win["last_departure"]):
        return {"status": "IMPOSSIBLE", "reasons": diagnose(ctx), "ctx": ctx}
    best = search(ctx, plans, budget, fast=fast)
    cheapest = best["cheapest"]
    if cheapest is None:
        return {"status": "IMPOSSIBLE", "reasons": diagnose(ctx), "ctx": ctx}
    res = {"ctx": ctx, "cheapest_total": cheapest.total, "plans_considered": len(plans)}
    if cheapest.total > budget:
        res.update(status="OVER_BUDGET", deficit=cheapest.total - budget, specs={"cheapest": to_spec(ctx, cheapest, 1)})
        return res
    specs = {"cheapest": to_spec(ctx, cheapest, 1)}
    for name in ("fastest", "best_rated"):
        sel = best[name]
        if sel is None or fast:
            continue
        rich = ctx.attractions(sel.plan, 2)
        base = ctx.attractions(sel.plan, 1)
        per_day = 2 if rich and base and sel.total - base[1] + rich[1] <= budget else 1
        specs[name] = to_spec(ctx, sel, per_day)
    res.update(status="OK", specs=specs)
    return res
