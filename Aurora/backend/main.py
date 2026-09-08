"""
AURA — AI English Speaking Coach
FastAPI application entry point.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import ENVIRONMENT
from backend.database import engine, Base
from backend.routers import health


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Runs at startup and shutdown.
    Creates all database tables on first run (development convenience).
    In production, use Alembic migrations instead.
    """
    # Create tables if they don't exist (idempotent — safe to run repeatedly)
    Base.metadata.create_all(bind=engine)
    print("✅  Database tables verified / created")
    yield
    # (cleanup on shutdown goes here if needed)


app = FastAPI(
    title="AURA — AI English Speaking Coach",
    description="Real-time conversational English practice with personalized feedback.",
    version="0.1.0",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
# Allow the Next.js dev server (localhost:3000) to call the API.
# Tighten this for production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",   # Next.js dev server
        "http://localhost:5173",   # Vite dev server (if used)
    ] if ENVIRONMENT == "development" else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(health.router)

# Phase 1 routers will be added here:
# app.include_router(conversation.router, prefix="/api")
