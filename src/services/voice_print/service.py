from pathlib import Path
from typing import Optional, List
import uuid

from sqlalchemy.orm import Session
import numpy as np

from src.models.database import VoicePrintProfile, VoicePrintSample, VoicePrintMatch, get_session_local
from src.services.voice_print.extractor import get_voice_print_extractor
from src.services.voice_print.matcher import cosine_similarity
from src.core import settings


class VoicePrintService:
    def __init__(self, db: Optional[Session] = None):
        self.db = db or get_session_local()()
        self.extractor = None

    def _get_extractor(self):
        if self.extractor is None:
            self.extractor = get_voice_print_extractor()
        return self.extractor

    def create_profile(self, name: str, description: Optional[str] = None) -> VoicePrintProfile:
        profile = VoicePrintProfile(
            id=str(uuid.uuid4()),
            name=name,
            description=description,
            status="pending",
        )
        self.db.add(profile)
        self.db.commit()
        self.db.refresh(profile)
        return profile

    def list_profiles(self, skip: int = 0, limit: int = 20) -> List[VoicePrintProfile]:
        return self.db.query(VoicePrintProfile).order_by(VoicePrintProfile.created_at.desc()).offset(skip).limit(limit).all()

    def get_profile(self, profile_id: str) -> Optional[VoicePrintProfile]:
        return self.db.query(VoicePrintProfile).filter(VoicePrintProfile.id == profile_id).first()

    def update_profile(self, profile_id: str, name: Optional[str] = None, description: Optional[str] = None) -> Optional[VoicePrintProfile]:
        profile = self.get_profile(profile_id)
        if profile is None:
            return None
        if name is not None:
            profile.name = name
        if description is not None:
            profile.description = description
        self.db.commit()
        self.db.refresh(profile)
        return profile

    def delete_profile(self, profile_id: str) -> bool:
        profile = self.get_profile(profile_id)
        if profile is None:
            return False
        self.db.delete(profile)
        self.db.commit()
        return True

    def add_sample(
        self,
        profile_id: str,
        audio_path: str,
        extract_embedding: bool = True,
    ) -> Optional[VoicePrintSample]:
        profile = self.get_profile(profile_id)
        if profile is None:
            return None

        from src.services.audio.processor import get_audio_processor
        processor = get_audio_processor()
        duration = processor.get_duration(audio_path)

        sample = VoicePrintSample(
            id=str(uuid.uuid4()),
            profile_id=profile_id,
            audio_path=audio_path,
            duration=duration,
            status="pending" if extract_embedding else "skipped",
        )
        self.db.add(sample)

        if extract_embedding:
            try:
                extractor = self._get_extractor()
                embedding = extractor.extract_embedding(audio_path)
                sample.embedding = embedding.tolist()
                sample.status = "completed"
            except Exception as e:
                sample.status = "failed"
                sample.error_message = str(e)

        self.db.commit()
        self.db.refresh(sample)

        self._update_profile_embedding(profile_id)
        return sample

    def _update_profile_embedding(self, profile_id: str) -> None:
        profile = self.get_profile(profile_id)
        if profile is None:
            return

        samples = self.db.query(VoicePrintSample).filter(
            VoicePrintSample.profile_id == profile_id,
            VoicePrintSample.status == "completed",
            VoicePrintSample.embedding.isnot(None),
        ).all()

        if not samples:
            profile.embedding = None
            profile.sample_count = len(samples)
            profile.status = "pending"
        else:
            embeddings = [np.array(s.embedding) for s in samples]
            avg_embedding = np.mean(embeddings, axis=0).tolist()
            profile.embedding = avg_embedding
            profile.sample_count = len(samples)
            profile.status = "ready"
            if len(samples) >= 3:
                profile.status = "trained"

        profile.updated_at = __import__("datetime").datetime.utcnow()
        self.db.commit()

    def list_samples(self, profile_id: str) -> List[VoicePrintSample]:
        return self.db.query(VoicePrintSample).filter(
            VoicePrintSample.profile_id == profile_id
        ).order_by(VoicePrintSample.created_at.desc()).all()

    def delete_sample(self, sample_id: str) -> bool:
        sample = self.db.query(VoicePrintSample).filter(VoicePrintSample.id == sample_id).first()
        if sample is None:
            return False
        profile_id = sample.profile_id
        self.db.delete(sample)
        self.db.commit()
        self._update_profile_embedding(profile_id)
        return True

    def match_speaker(
        self,
        speaker_embedding: np.ndarray,
        threshold: float = 0.7,
    ) -> Optional[tuple[str, float]]:
        profiles = self.db.query(VoicePrintProfile).filter(
            VoicePrintProfile.status.in_(["ready", "trained"]),
            VoicePrintProfile.embedding.isnot(None),
        ).all()

        best_match = None
        best_score = threshold

        for profile in profiles:
            profile_embedding = np.array(profile.embedding)
            score = cosine_similarity(speaker_embedding, profile_embedding)
            if score > best_score:
                best_score = score
                best_match = profile.id

        if best_match:
            return best_match, best_score
        return None

    def record_match(
        self,
        profile_id: str,
        interview_id: Optional[str] = None,
        speaker_id: Optional[str] = None,
        speaker_label: Optional[str] = None,
        confidence: float = 0.0,
    ) -> VoicePrintMatch:
        match = VoicePrintMatch(
            id=str(uuid.uuid4()),
            profile_id=profile_id,
            interview_id=interview_id,
            speaker_id=speaker_id,
            speaker_label=speaker_label,
            confidence=confidence,
        )
        self.db.add(match)
        self.db.commit()
        self.db.refresh(match)
        return match

    def get_matches(self, profile_id: Optional[str] = None, interview_id: Optional[str] = None, limit: int = 50) -> List[VoicePrintMatch]:
        query = self.db.query(VoicePrintMatch)
        if profile_id:
            query = query.filter(VoicePrintMatch.profile_id == profile_id)
        if interview_id:
            query = query.filter(VoicePrintMatch.interview_id == interview_id)
        return query.order_by(VoicePrintMatch.matched_at.desc()).limit(limit).all()