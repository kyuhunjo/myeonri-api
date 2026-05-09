from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import saju, user, consult, calendar, logs
from app.core.config import settings
from app.core.database import close_pool
from app.core.auth import APIKeyMiddleware

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/docs",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Key Authentication
app.add_middleware(APIKeyMiddleware)

# Routers
app.include_router(saju.router)
app.include_router(user.router)
app.include_router(consult.router)
app.include_router(calendar.router)
app.include_router(logs.router)


@app.on_event("shutdown")
async def shutdown():
    await close_pool()


@app.get("/health")
async def health():
    return {"status": "ok", "version": settings.APP_VERSION}
