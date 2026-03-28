from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, ConfigDict, Field


class ProcessingStatus(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ProcessConfig(BaseModel):
    video_analysis: bool = True
    face_analysis: bool = True
    micro_expression: bool = False
    audio_denoise: bool = True
    speaker_diarization: bool = False  # 全局说话人分离模式（跨 Chunk 一致）
    speech_to_text: bool = True
    prosody_analysis: bool = True
    emotion_recognition: bool = True
    multimodal_fusion: bool = True

    stt_model: str = "large-v3-turbo"
    stt_engine: Optional[str] = None
    diarization_model: str = "pyannote-3.1"
    diarization_engine: str = "pyannote"  # 说话人分离引擎: "pyannote" 或 "funasr"
    keyframe_interval: float = 5.0
    face_sample_rate: float = 2.0

    chunk_enabled: bool = False
    chunk_duration: float = 600.0


class InterviewBase(BaseModel):
    filename: str


class InterviewCreate(InterviewBase):
    pass


class InterviewResponse(InterviewBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    duration: Optional[float] = None
    fps: Optional[float] = None
    resolution: Optional[str] = None
    status: ProcessingStatus
    error_message: Optional[str] = None
    created_at: datetime
    chunk_duration: Optional[float] = None
    chunk_count: Optional[int] = None
    is_chunked: bool = False
    updated_at: datetime
    video_url: Optional[str] = None


class InterviewListResponse(BaseModel):
    total: int
    interviews: List[InterviewResponse]


class SpeakerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    label: str
    color: Optional[str] = None
    chunk_id: Optional[str] = None


class ProsodyResponse(BaseModel):
    pitch_mean: Optional[float] = None
    pitch_std: Optional[float] = None
    energy_mean: Optional[float] = None
    speech_rate: Optional[float] = None
    pause_ratio: Optional[float] = None


class SegmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    speaker_id: Optional[str] = None
    speaker_label: Optional[str] = None
    start_time: float
    end_time: float
    transcript: Optional[str] = None
    confidence: Optional[float] = None
    prosody: Optional[ProsodyResponse] = None
    emotion_scores: Optional[Dict[str, Any]] = None
    lang: Optional[str] = None
    event: Optional[str] = None
    chunk_id: Optional[str] = None


class KeyframeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    timestamp: float
    frame_idx: int
    scene_len: Optional[int] = None
    frame_path: Optional[str] = None


class FaceFrameResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    timestamp: float
    frame_path: Optional[str] = None
    face_bbox: Optional[List[float]] = None
    action_units: Optional[Dict[str, float]] = None
    emotion_scores: Optional[Dict[str, float]] = None


class EmotionNodeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    timestamp: float
    source: str
    label: str
    intensity: float
    confidence: float


class EmotionSummary(BaseModel):
    dominant_emotion: str
    emotion_distribution: Dict[str, float]
    stress_signals: int
    avoidance_signals: int
    confidence_score: float


class SignalItem(BaseModel):
    timestamp: float
    type: str
    intensity: float
    indicator: str


class TranscriptResponse(BaseModel):
    interview_id: str
    speakers: List[SpeakerResponse]
    segments: List[SegmentResponse]
    full_text: str


class EmotionAnalysisResponse(BaseModel):
    interview_id: str
    emotion_nodes: List[EmotionNodeResponse]
    summary: EmotionSummary
    signals: List[SignalItem]


class TimelineResponse(BaseModel):
    interview_id: str
    duration: float
    speakers: List[SpeakerResponse]
    segments: List[SegmentResponse]
    keyframes: List[KeyframeResponse]
    face_frames: List[FaceFrameResponse]
    emotion_nodes: List[EmotionNodeResponse]


class ReportResponse(BaseModel):
    interview_id: str
    metadata: Dict[str, Any]
    transcript: str
    emotion_summary: Dict[str, Any]
    signals: List[Dict[str, Any]]
    key_moments: List[Dict[str, Any]]


class TaskResponse(BaseModel):
    task_id: str
    status: str
    message: str


class ProgressResponse(BaseModel):
    interview_id: str
    status: ProcessingStatus
    progress: float
    current_stage: Optional[str] = None
    message: Optional[str] = None


class StatusResponse(BaseModel):
    status: str
    message: str


class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str
