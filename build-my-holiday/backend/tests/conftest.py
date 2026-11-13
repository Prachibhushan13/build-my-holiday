import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("BMH_DB_PATH", str(Path(tempfile.mkdtemp()) / "test.sqlite3"))

import pytest

from app.catalog.catalog_loader import Catalog


@pytest.fixture(scope="session")
def cat():
    return Catalog()


MENON = {"name": "Menon family", "departure_city": "Bengaluru", "country": "Japan", "start_date": "2027-04-10",
         "nights": 6, "adults": 2, "child_ages": [6], "budget_inr": 350000}


@pytest.fixture()
def menon():
    return dict(MENON)
