from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse

from app.api.routes.auth import router as auth_router
from app.api.routes.videos import router as video_router
from app.core.config import settings
from app.db import Base, engine

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(video_router)


def _resolve_frontend_asset(relative_path: str) -> Path | None:
    candidates = (
        settings.frontend_dist_dir / relative_path,
        settings.backend_root.parent / "public" / relative_path,
    )
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", include_in_schema=False, response_model=None)
def serve_root():
    if (settings.frontend_dist_dir / "index.html").exists():
        return FileResponse(settings.frontend_dist_dir / "index.html")
    return {"service": settings.app_name, "docs": "/docs"}


@app.get("/api-access-guide.html", include_in_schema=False, response_model=None)
def redirect_legacy_api_guide():
    return RedirectResponse(url="/developer-api-guide", status_code=307)


@app.get("/developer-api-guide.html", include_in_schema=False, response_model=None)
def redirect_static_api_guide():
    return RedirectResponse(url="/developer-api-guide", status_code=307)


@app.get("/{full_path:path}", include_in_schema=False, response_model=None)
def serve_frontend(full_path: str):
    if full_path.startswith("api") or full_path in {"docs", "openapi.json", "health"}:
        raise HTTPException(status_code=404, detail="Not found")

    candidate = _resolve_frontend_asset(full_path)
    if candidate:
        return FileResponse(candidate)
    index_path = settings.frontend_dist_dir / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    raise HTTPException(status_code=404, detail="Not found")
