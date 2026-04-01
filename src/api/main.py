from contextlib import asynccontextmanager
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.core import settings
from src.models import init_db
from src.api.routes import interviews_router, process_router, pipeline_router, corrections_router
from src.services.voice_print.api import router as voice_print_router
from src.utils.logging import setup_logging
from src.utils.system_check import SystemChecker

setup_logging(level=settings.log_level)
logger = setup_logging(level=settings.log_level)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Interview AI API...")
    
    system_check = SystemChecker.full_check()
    logger.info(f"Platform: {system_check['platform']}")
    logger.info(f"Python: {system_check['python']['version']}")
    
    if not system_check['ffmpeg']['available']:
        logger.warning(f"ffmpeg: {system_check['ffmpeg']['message']}")
    else:
        logger.info("ffmpeg: available")
    
    gpu = system_check['gpu']
    if gpu['cuda_available']:
        logger.info(f"GPU: CUDA {gpu['cuda_version']} - {gpu['gpu_name']}")
    elif gpu['mps_available']:
        logger.info("GPU: MPS (Apple Silicon)")
    else:
        logger.info("GPU: CPU mode")
    
    fonts = system_check['fonts']
    if not fonts.get('cn_font'):
        logger.warning("Chinese font not available. PDF generation may fail.")
        logger.warning("Install with: sudo apt install fonts-noto-cjk (Ubuntu)")
    
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
app.include_router(voice_print_router, prefix="/api")


@app.get("/")
async def root():
    return {
        "name": settings.api_title,
        "version": settings.api_version,
        "docs": "/docs",
    }
