import uuid
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from src.api.schemas import (
    HealthResponse,
    InterviewCreate,
    InterviewListResponse,
    InterviewResponse,
    StatusResponse,
)
from src.models import Interview, ProcessingStatus, get_db
from src.core import settings


router = APIRouter(prefix="/interviews", tags=["interviews"])


def get_video_duration(path: str) -> float:
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            capture_output=True, text=True, check=True, timeout=30,
        )
        return float(result.stdout.strip())
    except Exception:
        return 0.0


@router.get("/health", response_model=HealthResponse, tags=["health"])
async def health_check():
    return HealthResponse(
        status="healthy",
        version=settings.api_version,
        environment=settings.environment,
    )


@router.post("", response_model=InterviewResponse, status_code=status.HTTP_201_CREATED, tags=["interviews"])
async def create_interview(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    if file.size and file.size > settings.max_upload_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds maximum of {settings.max_upload_size / 1024 / 1024 / 1024:.1f}GB",
        )

    settings.ensure_directories()

    file_id = str(uuid.uuid4())
    file_ext = Path(file.filename).suffix or ".mp4"
    file_path = settings.upload_dir / f"{file_id}{file_ext}"

    try:
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save file: {str(e)}",
        )

    duration = get_video_duration(str(file_path))

    interview = Interview(
        id=file_id,
        filename=file.filename or "unknown",
        file_path=str(file_path),
        duration=duration,
        status=ProcessingStatus.PENDING.value,
    )
    db.add(interview)
    db.commit()
    db.refresh(interview)

    return interview


@router.get("", response_model=InterviewListResponse, tags=["interviews"])
async def list_interviews(
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
):
    total = db.query(Interview).count()
    interviews = db.query(Interview).order_by(Interview.created_at.desc()).offset(skip).limit(limit).all()

    return InterviewListResponse(total=total, interviews=interviews)


@router.get("/{interview_id}", response_model=InterviewResponse, tags=["interviews"])
async def get_interview(interview_id: str, db: Session = Depends(get_db)):
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Interview not found: {interview_id}",
        )
    return interview


@router.delete("/{interview_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["interviews"])
async def delete_interview(interview_id: str, db: Session = Depends(get_db)):
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Interview not found: {interview_id}",
        )

    if Path(interview.file_path).exists():
        Path(interview.file_path).unlink()

    db.delete(interview)
    db.commit()


@router.post("/{interview_id}/status", response_model=StatusResponse, tags=["interviews"])
async def get_status(interview_id: str, db: Session = Depends(get_db)):
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Interview not found: {interview_id}",
        )

    return StatusResponse(
        status=interview.status,
        message=interview.error_message or f"Interview status: {interview.status}",
    )
