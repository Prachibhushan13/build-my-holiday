"""Confirmation and reservation lookup (M7). One SQLite transaction: re-validate, mint a unique
10-digit reference, mark the package BOOKED and store an immutable snapshot."""
import json
import logging
import re
import secrets

from ..db import database as db
from .package_builder import BuildError, assemble
from .package_service import ChangeRejected, NotFound, build_payload, inr
from .package_validator import explain, validate_trip

log = logging.getLogger("bmh")
REF_RE = re.compile(r"^\d{10}$")


def confirm(cat, pid: str, allow_over_budget: bool = False) -> dict:
    with db.transaction() as conn:
        row = conn.execute("SELECT * FROM packages WHERE package_id=?", (pid,)).fetchone()
        if not row:
            raise NotFound("Package not found")
        request, spec = json.loads(row["request_json"]), json.loads(row["spec_json"])
        if row["status"] == "BOOKED":  # idempotent: same package, same reference
            snap = conn.execute("SELECT snapshot_json FROM reservations WHERE reference=?", (row["reference"],)).fetchone()
            return json.loads(snap["snapshot_json"])
        try:
            trip = assemble(cat, spec, pid)
        except BuildError as e:
            raise ChangeRejected(str(e))
        violations = validate_trip(cat, trip)
        if violations:
            raise ChangeRejected("The package no longer satisfies the travel rules: " + explain(violations), violations)
        if trip["total_inr"] > request["budget_inr"] and not allow_over_budget:
            raise ChangeRejected(f"This package costs {inr(trip['total_inr'])}, which is {inr(trip['total_inr'] - request['budget_inr'])} "
                                 f"over your budget of {inr(request['budget_inr'])}. Adjust the package or confirm anyway.")
        while True:
            ref = f"{secrets.randbelow(10 ** 10):010d}"
            if not conn.execute("SELECT 1 FROM reservations WHERE reference=?", (ref,)).fetchone():
                break
        booked = assemble(cat, spec, pid, status="BOOKED", reference=ref)
        db.save_package(conn, pid, "BOOKED", request, spec, booked, reference=ref)
        payload = build_payload(cat, pid, "BOOKED", ref, row["option_label"], request, spec, booked, row["group_id"])
        log.info("CONFIRMED %s as reservation %s, total %d", pid, ref, booked["total_inr"])
        payload["confirmed_at"] = db.now()
        conn.execute("INSERT INTO reservations(reference, package_id, snapshot_json, confirmed_at) VALUES (?,?,?,?)",
                     (ref, pid, json.dumps(payload), payload["confirmed_at"]))
    return payload


def lookup(reference: str) -> dict:
    ref = (reference or "").strip()
    if not REF_RE.match(ref):
        raise NotFound("Reservation not found")
    row = db.get_reservation(ref)
    if not row:
        raise NotFound("Reservation not found")
    return json.loads(row["snapshot_json"])
