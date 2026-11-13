"""Small helpers for local-time arithmetic. All catalog times are local, no time zones needed."""
from datetime import date, datetime, timedelta, time

WEEKDAYS = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]


def hm(s: str) -> int:
    """'HH:MM' -> minutes since midnight ('24:00' -> 1440)."""
    h, m = s.split(":")[:2]
    return int(h) * 60 + int(m)


def hhmm(minutes: int) -> str:
    minutes = int(minutes)
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def window(frm: str, until: str):
    """Service window in minutes; a window that ends before it starts runs past midnight."""
    a, b = hm(frm), hm(until)
    if b < a:
        b += 1440
    return a, b


def in_window(minute: int, frm: str, until: str) -> bool:
    """Is a pickup at `minute` (0..1439 of its own calendar day) inside the service window?
    Both ends are inclusive. Post-midnight tails (06:00-00:30) cover 00:00-00:30 of the next day."""
    a, b = window(frm, until)
    if a <= minute <= b:
        return True
    return b > 1440 and minute + 1440 <= b


def weekday(d: date) -> str:
    return WEEKDAYS[d.weekday()]


def fmt_dt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M")


def parse_dt(s: str) -> datetime:
    return datetime.fromisoformat(s)


def at(d: date, minute: int) -> datetime:
    return datetime.combine(d, time(0)) + timedelta(minutes=minute)


def iso(d: date) -> str:
    return d.isoformat()
