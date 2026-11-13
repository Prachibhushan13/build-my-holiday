"""Build My Holiday API (FastAPI). Also serves the built React app and photos when present."""
import logging
import os
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .api import catalog as catalog_api
from .api import packages as packages_api
from .api import reservations as reservations_api
from .catalog.catalog_loader import get_catalog
from .db.database import db_path, init_db

ROOT = Path(__file__).resolve().parents[2]

app = FastAPI(title="Build My Holiday", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


log = logging.getLogger("bmh")


def setup_logging():
    """Console + rotating file (backend/var/app.log, next to the database). Safe to call repeatedly."""
    if getattr(log, "_bmh_ready", False):
        return
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(message)s", "%H:%M:%S")
    log.setLevel(logging.INFO)
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    log.addHandler(console)
    try:
        path = db_path().parent
        path.mkdir(parents=True, exist_ok=True)
        fh = RotatingFileHandler(path / "app.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
        fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(message)s"))
        log.addHandler(fh)
    except OSError:
        pass
    log._bmh_ready = True


@app.on_event("startup")
def startup():
    setup_logging()
    cat = get_catalog()   # load + index the catalog once
    init_db()
    log.info("started: %d flights, %d hotels, %d attractions loaded; db=%s",
             len(cat.flights), len(cat.hotels), len(cat.attractions), db_path())


@app.middleware("http")
async def log_requests(request: Request, call_next):
    t0 = time.time()
    try:
        response = await call_next(request)
    except Exception:
        log.exception("UNHANDLED ERROR %s %s", request.method, request.url.path)
        raise
    if request.url.path.startswith("/api") and request.url.path != "/api/health":
        level = logging.INFO if response.status_code < 400 else logging.WARNING
        if response.status_code >= 500:
            level = logging.ERROR
        log.log(level, "%s %s -> %s (%d ms)", request.method, request.url.path, response.status_code, (time.time() - t0) * 1000)
    return response


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    errs = [{"field": ".".join(str(x) for x in e["loc"][1:]) or "body", "message": e["msg"]} for e in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": {"message": "Invalid request", "errors": errs}})


@app.get("/api/health")
def health():
    return {"ok": True}


app.include_router(catalog_api.router)
app.include_router(packages_api.router)
app.include_router(reservations_api.router)

images = ROOT / "images"
if images.is_dir():
    app.mount("/images", StaticFiles(directory=images), name="images")

dist = ROOT / "frontend" / "dist"
if dist.is_dir():
    app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        f = dist / path
        if path and f.is_file():
            return FileResponse(f)
        return FileResponse(dist / "index.html")
