"""Attraction opening rules and a deterministic day scheduler."""
from datetime import date
from itertools import combinations, permutations
from typing import Dict, List, Optional, Tuple

from .pricing_service import Party, attraction_price
from .timeutil import hm, weekday

DAY_START = 9 * 60
GAP = 30
DAY_LIMIT = 23 * 60


def is_open_on(att: dict, d: date) -> bool:
    return weekday(d) in att["open_days"] and d.isoformat() not in (att.get("closed_dates") or [])


def earliest_start(att: dict, d: date, cursor: int) -> Optional[int]:
    """Earliest start >= cursor so the whole visit fits in the opening window, else None."""
    if not is_open_on(att, d):
        return None
    start = max(cursor, hm(att["open_from"]))
    end = start + att["visit_minutes"]
    if end > hm(att["open_until"]) or end > 1440:
        return None
    return start


def fit_day(atts: List[dict], d: date, cursor0: int = DAY_START, limit: int = DAY_LIMIT) -> Optional[List[Tuple[dict, int]]]:
    """Order and time a set of attractions on one day without overlaps (30 min gap)."""
    for order in permutations(atts):
        cursor, plan, ok = cursor0, [], True
        for a in order:
            s = earliest_start(a, d, cursor)
            if s is None or s + a["visit_minutes"] > limit:
                ok = False
                break
            plan.append((a, s))
            cursor = s + a["visit_minutes"] + GAP
        if ok:
            return plan
    return None


def schedule_days(cat, city: str, days: List[date], party: Party, per_day: int = 1,
                  taken: Optional[set] = None, node_cap: int = 30000) -> Optional[Dict[date, List[Tuple[dict, int]]]]:
    """Give every day 1..per_day attractions (cheapest first), no repeats. Backtracking, deterministic."""
    cands = sorted(cat.attractions_by_city.get(city, []), key=lambda a: (attraction_price(a, party), a["attraction_id"]))
    used0 = set(taken or ())
    nodes = [0]

    def day_choices(d, used):
        singles = []
        for a in cands:
            if a["attraction_id"] in used:
                continue
            p = fit_day([a], d)
            if p:
                singles.append((attraction_price(a, party), a["attraction_id"], p))
        pairs = []
        if per_day >= 2:
            for (pa, ia, _), (pb, ib, _) in combinations(singles, 2):
                a, b = cat.attractions[ia], cat.attractions[ib]
                p = fit_day([a, b], d)
                if p:
                    pairs.append((pa + pb, ia + ib, p))
        return sorted(pairs, key=lambda x: (x[0], x[1])) + sorted(singles, key=lambda x: (x[0], x[1]))

    def rec(i, used):
        if i == len(days):
            return {}
        nodes[0] += 1
        if nodes[0] > node_cap:
            return None
        for _, _, plan in day_choices(days[i], used):
            ids = {a["attraction_id"] for a, _ in plan}
            rest = rec(i + 1, used | ids)
            if rest is not None:
                rest[days[i]] = plan
                return rest
        return None

    return rec(0, used0)
