import uuid
import os
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from src.models import get_db
from src.models.database import VoicePrintProfile, VoicePrintSample, VoicePrintMatch
from src.services.voice_print.service import VoicePrintService
from src.core import settings


router = APIRouter(prefix="/voice-prints", tags=["voice-prints"])


class ProfileCreate(BaseModel):
    name: str
    description: Optional[str] = None


class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class ProfileResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    embedding: Optional[dict]
    sample_count: int
    status: str
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class SampleResponse(BaseModel):
    id: str
    profile_id: str
    audio_path: str
    duration: Optional[float]
    embedding: Optional[dict]
    status: str
    error_message: Optional[str]
    created_at: str

    class Config:
        from_attributes = True


class MatchResponse(BaseModel):
    id: str
    profile_id: str
    interview_id: Optional[str]
    speaker_id: Optional[str]
    speaker_label: Optional[str]
    confidence: float
    matched_at: str

    class Config:
        from_attributes = True


@router.post("", response_model=ProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_profile(
    data: ProfileCreate,
    db: Session = Depends(get_db),
):
    service = VoicePrintService(db)
    profile = service.create_profile(data.name, data.description)
    return profile


@router.get("", response_model=List[ProfileResponse])
async def list_profiles(
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
):
    service = VoicePrintService(db)
    profiles = service.list_profiles(skip, limit)
    return profiles


@router.get("/{profile_id}", response_model=ProfileResponse)
async def get_profile(
    profile_id: str,
    db: Session = Depends(get_db),
):
    service = VoicePrintService(db)
    profile = service.get_profile(profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@router.patch("/{profile_id}", response_model=ProfileResponse)
async def update_profile(
    profile_id: str,
    data: ProfileUpdate,
    db: Session = Depends(get_db),
):
    service = VoicePrintService(db)
    profile = service.update_profile(profile_id, data.name, data.description)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_profile(
    profile_id: str,
    db: Session = Depends(get_db),
):
    service = VoicePrintService(db)
    if not service.delete_profile(profile_id):
        raise HTTPException(status_code=404, detail="Profile not found")


@router.post("/{profile_id}/samples", response_model=SampleResponse, status_code=status.HTTP_201_CREATED)
async def add_sample(
    profile_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    settings.ensure_directories()
    
    file_id = str(uuid.uuid4())
    file_ext = Path(file.filename).suffix or ".wav"
    file_path = settings.voice_print_dir / f"{file_id}{file_ext}"

    try:
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save file: {str(e)}",
        )

    service = VoicePrintService(db)
    sample = service.add_sample(profile_id, str(file_path))
    if sample is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return sample


@router.get("/{profile_id}/samples", response_model=List[SampleResponse])
async def list_samples(
    profile_id: str,
    db: Session = Depends(get_db),
):
    service = VoicePrintService(db)
    samples = service.list_samples(profile_id)
    return samples


@router.delete("/samples/{sample_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sample(
    sample_id: str,
    db: Session = Depends(get_db),
):
    service = VoicePrintService(db)
    if not service.delete_sample(sample_id):
        raise HTTPException(status_code=404, detail="Sample not found")


@router.get("/{profile_id}/matches", response_model=List[MatchResponse])
async def get_profile_matches(
    profile_id: str,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    service = VoicePrintService(db)
    matches = service.get_matches(profile_id=profile_id, limit=limit)
    return matches


@router.get("/matches", response_model=List[MatchResponse])
async def get_all_matches(
    interview_id: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    service = VoicePrintService(db)
    matches = service.get_matches(interview_id=interview_id, limit=limit)
    return matches


@router.post("/match")
async def match_embedding(
    embedding: dict,
    threshold: float = 0.7,
    db: Session = Depends(get_db),
):
    import numpy as np
    service = VoicePrintService(db)
    emb = np.array(embedding.get("embedding"))
    result = service.match_speaker(emb, threshold)
    if result:
        profile_id, score = result
        profile = service.get_profile(profile_id)
        return {"profile_id": profile_id, "profile_name": profile.name if profile else None, "confidence": score}
    return {"profile_id": None, "profile_name": None, "confidence": 0.0}