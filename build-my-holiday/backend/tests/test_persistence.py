import importlib
import os

import pytest
from fastapi.testclient import TestClient

MENON = {"name": "Menon family", "departure_city": "Bengaluru", "country": "Japan", "start_date": "2027-04-10",
         "nights": 6, "adults": 2, "child_ages": [6], "budget_inr": 350000}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("BMH_DB_PATH", str(tmp_path / "t.sqlite3"))
    from app.main import app
    with TestClient(app) as c:
        yield c


def test_sqlite_persistence_survives_restart(client, tmp_path):
    r = client.post("/api/packages/generate", json=MENON)
    assert r.status_code == 200 and r.json()["status"] == "OK"
    pid = r.json()["package"]["package_id"]
    ref = client.post(f"/api/packages/{pid}/confirm").json()["reference"]
    assert len(ref) == 10 and ref.isdigit()
    before = client.get(f"/api/reservations/{ref}").json()
    # "restart": a brand-new app/client reading the same SQLite file
    from app.main import app
    with TestClient(app) as c2:
        after = c2.get(f"/api/reservations/{ref}").json()
        assert after == before and after["status"] == "BOOKED"
        assert all(i["status"] == "BOOKED" and i["booking"]["reference"] == ref for i in after["trip"]["items"])
        assert c2.get("/api/reservations/0000000000").status_code == 404
        assert c2.get("/api/reservations/abc").status_code == 404
        exp = c2.get(f"/api/packages/{pid}/export").json()
        assert exp["items"][0]["booking"] == {"reference": ref}
        assert c2.patch(f"/api/packages/{pid}/hotel", json={"city": "Tokyo", "hotel_id": "x"}).status_code == 409


def test_unique_references_and_idempotent_confirm(client):
    refs = set()
    for _ in range(3):
        pid = client.post("/api/packages/generate", json=MENON).json()["package"]["package_id"]
        a = client.post(f"/api/packages/{pid}/confirm").json()["reference"]
        assert client.post(f"/api/packages/{pid}/confirm").json()["reference"] == a
        refs.add(a)
    assert len(refs) == 3


def test_change_flow_and_rejection(client):
    p = client.post("/api/packages/generate", json=MENON).json()["package"]
    pid, total = p["package_id"], p["summary"]["total_inr"]
    alts = client.get(f"/api/packages/{pid}/alternatives/flights", params={"direction": "arrival"}).json()["alternatives"]
    bad = next(a for a in alts if not a["valid"])
    r = client.patch(f"/api/packages/{pid}/flight", json={"direction": "arrival", "flight_id": bad["flight_id"]})
    assert r.status_code == 409 and r.json()["detail"]["message"]
    assert client.get(f"/api/packages/{pid}").json()["summary"]["total_inr"] == total      # unchanged after rejection
    good = next(a for a in alts if a["valid"] and not a["is_current"])
    r = client.patch(f"/api/packages/{pid}/flight", json={"direction": "arrival", "flight_id": good["flight_id"]})
    assert r.status_code == 200 and r.json()["change"]["price_diff_inr"] == good["price_diff_inr"]
    assert client.get(f"/api/packages/{pid}").json()["summary"]["total_inr"] == r.json()["summary"]["total_inr"]


def test_bad_requests(client):
    r = client.post("/api/packages/generate", json={**MENON, "nights": 2})
    assert r.status_code == 422 and r.json()["detail"]["errors"][0]["field"] == "nights"
    r = client.post("/api/packages/generate", json={**MENON, "start_date": "2027-05-30"})
    assert r.status_code == 200 and r.json()["status"] == "IMPOSSIBLE" and r.json()["reasons"]
