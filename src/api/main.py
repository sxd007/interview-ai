from contextlib import asynccontextmanager
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.core import settings
from src.models import init_db
from src.api.routes import interviews_router, process_router, pipeline_router, corrections_router
from src.utils.logging import setup_logging

setup_logging(level=settings.log_level)
logger = setup_logging(level=settings.log_level)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Interview AI API...")
    settings.ensure_directories()
    init_db()
    logger.info("Database initialized")
    logger.info(f"Upload dir: {settings.upload_dir}")

    data_root = os.path.abspath("data")
    if os.path.exists(data_root):
        app.mount("/data", StaticFiles(directory=data_root), name="data")

    yield
    logger.info("Shutting down Interview AI API...")


app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    description="Interview Video Intelligence System - Multi-modal analysis for psychological research",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(interviews_router, prefix="/api")
app.include_router(process_router, prefix="/api")
app.include_router(pipeline_router, prefix="/api")
app.include_router(corrections_router, prefix="/api")


@app.get("/")
async def root():
    return {
        "name": settings.api_title,
        "version": settings.api_version,
        "docs": "/docs",
    }
