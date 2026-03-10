from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

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


@app.get("/{full_path:path}", include_in_schema=False, response_model=None)
def serve_frontend(full_path: str):
    if full_path.startswith("api") or full_path in {"docs", "openapi.json", "health"}:
        raise HTTPException(status_code=404, detail="Not found")

    candidate = settings.frontend_dist_dir / full_path
    if candidate.exists() and candidate.is_file():
        return FileResponse(candidate)
    index_path = settings.frontend_dist_dir / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    raise HTTPException(status_code=404, detail="Not found")
