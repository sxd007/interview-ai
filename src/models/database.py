from datetime import datetime
from enum import Enum
from typing import Optional, List

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey,
    Integer, JSON, String, Text, create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker


class Base(DeclarativeBase):
    pass


class ProcessingStatus(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class StageStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    AWAITING_REVIEW = "awaiting_review"
    SKIPPED = "skipped"


class ChunkStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    REVIEW_PENDING = "review_pending"
    REVIEW_COMPLETED = "review_completed"
    FAILED = "failed"


class ChangeType(str, Enum):
    SPEAKER_MERGE = "speaker_merge"
    SPEAKER_SPLIT = "speaker_split"
    SPEAKER_RENAME = "speaker_rename"
    SEGMENT_EDIT = "segment_edit"
    SEGMENT_DELETE = "segment_delete"
    SEGMENT_MERGE = "segment_merge"
    SPEAKER_REASSIGN = "speaker_reassign"


class AnnotationType(str, Enum):
    MANUAL_CORRECTION = "manual_correction"
    HUMAN_APPROVED = "human_approved"


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DISCARDED = "discarded"


class Interview(Base):
    __tablename__ = "interviews"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    duration: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    fps: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    resolution: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default=ProcessingStatus.PENDING.value)
    error_message: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    chunk_duration: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    chunk_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_chunked: Mapped[bool] = mapped_column(Boolean, default=False)

    speakers: Mapped[List["Speaker"]] = relationship(back_populates="interview", cascade="all, delete-orphan")
    segments: Mapped[List["AudioSegment"]] = relationship(back_populates="interview", cascade="all, delete-orphan")
    face_frames: Mapped[List["FaceFrame"]] = relationship(back_populates="interview", cascade="all, delete-orphan")
    keyframes: Mapped[List["Keyframe"]] = relationship(back_populates="interview", cascade="all, delete-orphan")
    emotion_nodes: Mapped[List["EmotionNode"]] = relationship(back_populates="interview", cascade="all, delete-orphan")
    pipeline_stages: Mapped[List["PipelineStage"]] = relationship(back_populates="interview", cascade="all, delete-orphan")
    pending_changes: Mapped[List["PendingChange"]] = relationship(back_populates="interview", cascade="all, delete-orphan")
    video_chunks: Mapped[List["VideoChunk"]] = relationship(back_populates="interview", cascade="all, delete-orphan")
    annotation_logs: Mapped[List["AnnotationLog"]] = relationship(back_populates="interview", cascade="all, delete-orphan")


class VideoChunk(Base):
    __tablename__ = "video_chunks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    interview_id: Mapped[str] = mapped_column(String(36), ForeignKey("interviews.id"), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    global_start: Mapped[float] = mapped_column(Float, nullable=False)
    global_end: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default=ChunkStatus.PENDING.value)
    audio_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    stt_raw_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    stt_raw_output: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    diarization_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    diarization_engine_used: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    processing_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    review_pending_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    approved_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    interview: Mapped["Interview"] = relationship(back_populates="video_chunks")
    segments: Mapped[List["AudioSegment"]] = relationship(
        back_populates="chunk", cascade="all, delete-orphan"
    )
    face_frames: Mapped[List["FaceFrame"]] = relationship(
        back_populates="chunk", cascade="all, delete-orphan"
    )
    keyframes: Mapped[List["Keyframe"]] = relationship(
        back_populates="chunk", cascade="all, delete-orphan"
    )
    emotion_nodes: Mapped[List["EmotionNode"]] = relationship(
        back_populates="chunk", cascade="all, delete-orphan"
    )
    speakers: Mapped[List["Speaker"]] = relationship(
        back_populates="chunk", cascade="all, delete-orphan"
    )


class Speaker(Base):
    __tablename__ = "speakers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    interview_id: Mapped[str] = mapped_column(String(36), ForeignKey("interviews.id"), nullable=False)
    chunk_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("video_chunks.id"), nullable=True)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    voice_embedding: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    color: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    merged_into: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("speakers.id"), nullable=True)

    interview: Mapped["Interview"] = relationship(back_populates="speakers")
    chunk: Mapped[Optional["VideoChunk"]] = relationship(back_populates="speakers")
    segments: Mapped[List["AudioSegment"]] = relationship(back_populates="speaker")


class AudioSegment(Base):
    __tablename__ = "audio_segments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    interview_id: Mapped[str] = mapped_column(String(36), ForeignKey("interviews.id"), nullable=False)
    chunk_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("video_chunks.id"), nullable=True)
    speaker_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("speakers.id"), nullable=True)

    start_time: Mapped[float] = mapped_column(Float, nullable=False)
    end_time: Mapped[float] = mapped_column(Float, nullable=False)
    transcript: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    prosody: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    emotion_scores: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    lang: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    event: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    is_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    corrected_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    interview: Mapped["Interview"] = relationship(back_populates="segments")
    speaker: Mapped[Optional["Speaker"]] = relationship(back_populates="segments")
    chunk: Mapped[Optional["VideoChunk"]] = relationship(back_populates="segments")


class FaceFrame(Base):
    __tablename__ = "face_frames"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    interview_id: Mapped[str] = mapped_column(String(36), ForeignKey("interviews.id"), nullable=False)
    chunk_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("video_chunks.id"), nullable=True)

    timestamp: Mapped[float] = mapped_column(Float, nullable=False)
    frame_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    face_bbox: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    landmarks: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    action_units: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    emotion_scores: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    interview: Mapped["Interview"] = relationship(back_populates="face_frames")
    chunk: Mapped[Optional["VideoChunk"]] = relationship(back_populates="face_frames")


class Keyframe(Base):
    __tablename__ = "keyframes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    interview_id: Mapped[str] = mapped_column(String(36), ForeignKey("interviews.id"), nullable=False)
    chunk_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("video_chunks.id"), nullable=True)

    timestamp: Mapped[float] = mapped_column(Float, nullable=False)
    frame_idx: Mapped[int] = mapped_column(Integer, nullable=False)
    scene_len: Mapped[int] = mapped_column(Integer, nullable=True)
    frame_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    interview: Mapped["Interview"] = relationship(back_populates="keyframes")
    chunk: Mapped[Optional["VideoChunk"]] = relationship(back_populates="keyframes")


class EmotionNode(Base):
    __tablename__ = "emotion_nodes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    interview_id: Mapped[str] = mapped_column(String(36), ForeignKey("interviews.id"), nullable=False)
    chunk_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("video_chunks.id"), nullable=True)

    timestamp: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    label: Mapped[str] = mapped_column(String(50), nullable=False)
    intensity: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)

    audio_emotion: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    video_emotion: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    interview: Mapped["Interview"] = relationship(back_populates="emotion_nodes")
    chunk: Mapped[Optional["VideoChunk"]] = relationship(back_populates="emotion_nodes")


class PipelineStage(Base):
    __tablename__ = "pipeline_stages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    interview_id: Mapped[str] = mapped_column(String(36), ForeignKey("interviews.id"), nullable=False)
    stage_name: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default=StageStatus.PENDING.value)
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    result_summary: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    approved_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    interview: Mapped["Interview"] = relationship(back_populates="pipeline_stages")


class PendingChange(Base):
    __tablename__ = "pending_changes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    interview_id: Mapped[str] = mapped_column(String(36), ForeignKey("interviews.id"), nullable=False)
    chunk_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("video_chunks.id"), nullable=True)
    change_type: Mapped[str] = mapped_column(String(30), nullable=False)
    target_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    change_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    applied: Mapped[bool] = mapped_column(Boolean, default=False)
    applied_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    interview: Mapped["Interview"] = relationship(back_populates="pending_changes")


class AnnotationLog(Base):
    __tablename__ = "annotation_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    interview_id: Mapped[str] = mapped_column(String(36), ForeignKey("interviews.id"), nullable=False)
    chunk_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("video_chunks.id"), nullable=True)
    annotation_type: Mapped[str] = mapped_column(String(30), nullable=False)
    change_type: Mapped[str] = mapped_column(String(30), nullable=True)
    change_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    corrected_by: Mapped[str] = mapped_column(String(100), default="user")
    session_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    approval_status: Mapped[str] = mapped_column(String(20), default=ApprovalStatus.APPROVED.value)
    reprocess_triggered: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    interview: Mapped["Interview"] = relationship(back_populates="annotation_logs")


class VoicePrintProfile(Base):
    __tablename__ = "voice_print_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    embedding: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    sample_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    samples: Mapped[List["VoicePrintSample"]] = relationship(back_populates="profile", cascade="all, delete-orphan")
    matches: Mapped[List["VoicePrintMatch"]] = relationship(back_populates="profile", cascade="all, delete-orphan")


class VoicePrintSample(Base):
    __tablename__ = "voice_print_samples"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    profile_id: Mapped[str] = mapped_column(String(36), ForeignKey("voice_print_profiles.id"), nullable=False)
    audio_path: Mapped[str] = mapped_column(String(512), nullable=False)
    duration: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    embedding: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    profile: Mapped["VoicePrintProfile"] = relationship(back_populates="samples")


class VoicePrintMatch(Base):
    __tablename__ = "voice_print_matches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    profile_id: Mapped[str] = mapped_column(String(36), ForeignKey("voice_print_profiles.id"), nullable=False)
    interview_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("interviews.id"), nullable=True)
    speaker_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    speaker_label: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    matched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    profile: Mapped["VoicePrintProfile"] = relationship(back_populates="matches")


_engine = None
_session_local = None


def get_engine():
    global _engine
    if _engine is None:
        from src.core import settings
        _engine = create_engine(
            settings.database_url,
            echo=settings.database_echo,
            connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
        )
    return _engine


def get_session_local():
    global _session_local
    if _session_local is None:
        _session_local = sessionmaker(autocommit=False, autoflush=False, bind=get_engine())
    return _session_local


engine = property(lambda self: get_engine())


def init_db() -> None:
    Base.metadata.create_all(bind=get_engine())


def get_db():
    db = get_session_local()()
    try:
        yield db
    finally:
        db.close()
