"""Build My Holiday API (FastAPI). Also serves the built React app and photos when present."""
import os
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
from .db.database import init_db

ROOT = Path(__file__).resolve().parents[2]

app = FastAPI(title="Build My Holiday", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
def startup():
    get_catalog()   # load + index the catalog once
    init_db()


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
