import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.modules.auth.router import router as auth_router
from app.modules.auth.firebase_admin_client import initialize_firebase_admin
from app.modules.create_test.router import router as create_test_router
from app.db.session import init_db
from app.core.logging import configure_logging


configure_logging()


def _normalize_origin(origin: str) -> str:
    return origin.strip().rstrip("/")


def _load_allowed_origins() -> list[str]:
    raw_origins = os.getenv("FRONTEND_ORIGINS", "")
    origins = [
        _normalize_origin(origin)
        for origin in raw_origins.split(",")
        if origin.strip()
    ]

    fallback_origin = _normalize_origin(os.getenv("FRONTEND_ORIGIN", "http://localhost:3000"))
    if fallback_origin not in origins:
        origins.append(fallback_origin)

    return origins

app = FastAPI(
    title="JD Agentic Test System",
    version="0.1.0",
    description="Generate interview tests from a job description using LangGraph agents.",
)

frontend_origin = os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")
allowed_origins = _load_allowed_origins()

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/v1")
app.include_router(create_test_router, prefix="/api/v1")


@app.on_event("startup")
def on_startup() -> None:
    initialize_firebase_admin()
    init_db()


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "JD Agentic Test System is running"}
