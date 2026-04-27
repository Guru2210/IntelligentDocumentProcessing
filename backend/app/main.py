"""
FastAPI main application — registers all routers, CORS, startup events.
"""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import create_tables
from app.routers import projects, documents, labels, training, extraction, models, review


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: create database tables and MinIO bucket."""
    create_tables()
    try:
        from app.services.storage_service import ensure_bucket_exists
        ensure_bucket_exists()
    except Exception as e:
        print(f"Warning: Could not connect to MinIO on startup: {e}")

    os.makedirs(settings.models_dir, exist_ok=True)
    os.makedirs(settings.temp_dir, exist_ok=True)

    print("IDP Backend started successfully")
    yield
    print("IDP Backend shutting down")


app = FastAPI(
    title="Intelligent Document Processing API",
    description="Self-hosted document intelligence platform equivalent to Azure Document Intelligence",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(projects.router)
app.include_router(documents.router)
app.include_router(labels.router)
app.include_router(training.router)
app.include_router(extraction.router)
app.include_router(models.router)
app.include_router(review.router)


@app.get("/")
def root():
    return {"message": "IDP API running", "docs": "/docs", "version": "1.0.0"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/v1/prebuilt-schemas")
def prebuilt_schemas():
    return list(projects.PREBUILT_SCHEMAS.keys())
