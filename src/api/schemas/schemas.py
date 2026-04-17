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


class DiarizationAdvancedConfig(BaseModel):
    """
    说话人分离高级参数配置
    
    这些参数影响 pyannote 说话人分离引擎的行为，用于控制如何将音频分割成不同说话人的片段。
    """
    segmentation_onset: float = Field(
        default=0.3,
        ge=0.1,
        le=0.9,
        description="语音起始检测阈值。值越低越容易检测到语音开始，但可能误检噪音。",
        json_schema_extra={
            "impact": {
                "increase": "减少噪音误检，但可能漏检短句",
                "decrease": "更容易检测到语音，但可能将噪音识别为说话人",
                "recommended_range": "0.2-0.5",
                "scenarios": {
                    "noisy_environment": "建议提高到 0.4-0.5",
                    "quiet_environment": "可降低到 0.2-0.3",
                    "short_sentences": "建议降低到 0.2"
                }
            }
        }
    )
    
    segmentation_duration: float = Field(
        default=5.0,
        ge=2.0,
        le=10.0,
        description="分段窗口长度(秒)。较长窗口可捕捉更完整的说话段落。",
        json_schema_extra={
            "impact": {
                "increase": "捕捉更完整的说话段落，但可能错过快速切换",
                "decrease": "更精确捕捉说话人切换点",
                "recommended_range": "3.0-8.0",
                "scenarios": {
                    "fast_conversation": "建议降低到 3.0-4.0",
                    "long_monologue": "可提高到 6.0-8.0"
                }
            }
        }
    )
    
    min_duration_off: float = Field(
        default=0.3,
        ge=0.1,
        le=1.0,
        description="说话人间隙最小长度(秒)。小于此值的间隙会被合并到相邻片段。",
        json_schema_extra={
            "impact": {
                "increase": "更多片段被合并，减少碎片化",
                "decrease": "保留更多说话人切换点",
                "recommended_range": "0.2-0.5",
                "scenarios": {
                    "fragmented_speech": "建议提高到 0.4-0.5",
                    "precise_switching": "建议降低到 0.15-0.2"
                }
            }
        }
    )
    
    min_duration_on: float = Field(
        default=0.3,
        ge=0.1,
        le=1.0,
        description="说话片段最小长度(秒)。小于此值的片段会被过滤掉。",
        json_schema_extra={
            "impact": {
                "increase": "过滤掉短促的噪音片段",
                "decrease": "保留更多短句",
                "recommended_range": "0.15-0.5",
                "scenarios": {
                    "missing_short_sentences": "建议降低到 0.15-0.2",
                    "too_many_false_positives": "建议提高到 0.4-0.5"
                }
            }
        }
    )
    
    clustering_threshold: float = Field(
        default=0.715,
        ge=0.5,
        le=0.9,
        description="说话人聚类阈值。值越高，越不容易将同一人分成多个说话人。",
        json_schema_extra={
            "impact": {
                "increase": "减少同一人被拆分成多个说话人的情况",
                "decrease": "更容易区分相似的说话人",
                "recommended_range": "0.65-0.85",
                "scenarios": {
                    "same_person_split": "建议提高到 0.75-0.85",
                    "different_persons_merged": "建议降低到 0.6-0.7",
                    "similar_voices": "建议降低到 0.55-0.65"
                }
            }
        }
    )
    
    min_cluster_size: int = Field(
        default=15,
        ge=5,
        le=50,
        description="最小聚类样本数。值越大，越不容易产生虚假说话人。",
        json_schema_extra={
            "impact": {
                "increase": "减少虚假说话人，但可能漏掉说话较少的人",
                "decrease": "更容易识别说话较少的人",
                "recommended_range": "10-30",
                "scenarios": {
                    "too_many_speakers": "建议提高到 20-30",
                    "missing_quiet_speaker": "建议降低到 8-12"
                }
            }
        }
    )
    
    gap_threshold: float = Field(
        default=0.5,
        ge=0.1,
        le=2.0,
        description="后处理合并间隙阈值(秒)。同一说话人间隙小于此值会被合并。",
        json_schema_extra={
            "impact": {
                "increase": "更多片段被合并，减少碎片化",
                "decrease": "保留更多独立片段",
                "recommended_range": "0.3-1.0"
            }
        }
    )
    
    min_segment_duration: float = Field(
        default=0.5,
        ge=0.1,
        le=2.0,
        description="最小有效片段长度(秒)。后处理阶段过滤短片段。",
        json_schema_extra={
            "impact": {
                "increase": "过滤更多短片段",
                "decrease": "保留更多短片段",
                "recommended_range": "0.3-1.0"
            }
        }
    )


class STTAdvancedConfig(BaseModel):
    """
    语音转文字高级参数配置
    
    这些参数影响 SenseVoice/FunASR 语音识别引擎的行为。
    """
    language: str = Field(
        default="auto",
        description="识别语言。指定语言可提高准确率。",
        json_schema_extra={
            "options": ["auto", "zh", "en", "ja", "ko", "yue"],
            "impact": {
                "auto": "自动检测语言，适合多语言场景",
                "zh": "中文，提高中文识别准确率",
                "en": "英文，提高英文识别准确率",
                "scenarios": {
                    "chinese_interview": "建议设置为 'zh'",
                    "english_interview": "建议设置为 'en'",
                    "mixed_language": "建议设置为 'auto'"
                }
            }
        }
    )
    
    use_itn: bool = Field(
        default=True,
        description="逆文本标准化。将'一百二十三'转为'123'等。",
        json_schema_extra={
            "impact": {
                "true": "数字、日期等会转换为标准格式",
                "false": "保持原始文本形式",
                "scenarios": {
                    "formal_report": "建议开启",
                    "verbatim_transcript": "建议关闭"
                }
            }
        }
    )
    
    vad_enabled: bool = Field(
        default=True,
        description="语音活动检测。过滤静音段，提高识别效率。",
        json_schema_extra={
            "impact": {
                "true": "自动过滤静音段，提高效率",
                "false": "处理全部音频，可能包含静音",
                "scenarios": {
                    "long_silence_periods": "建议开启",
                    "subtle_speech": "可尝试关闭"
                }
            }
        }
    )
    
    spk_enabled: bool = Field(
        default=False,
        description="使用 FunASR 内置说话人识别。开启后使用 cam++ 模型进行说话人分离。",
        json_schema_extra={
            "impact": {
                "true": "使用 FunASR 内置说话人分离，替代 pyannote",
                "false": "使用 pyannote 进行说话人分离",
                "scenarios": {
                    "funasr_pipeline": "建议开启，与 STT 一体化",
                    "pyannote_pipeline": "建议关闭，使用独立的 pyannote"
                }
            }
        }
    )
    
    batch_size_s: int = Field(
        default=300,
        ge=60,
        le=600,
        description="批处理时长(秒)。影响内存占用和处理速度。",
        json_schema_extra={
            "impact": {
                "increase": "提高处理速度，但增加内存占用",
                "decrease": "降低内存占用，适合低配机器",
                "recommended_range": "180-450",
                "scenarios": {
                    "low_memory": "建议降低到 120-180",
                    "high_performance": "可提高到 400-500"
                }
            }
        }
    )
    
    merge_vad: bool = Field(
        default=True,
        description="合并 VAD 片段。减少碎片化，提高时间戳准确性。",
        json_schema_extra={
            "impact": {
                "true": "合并相邻的语音片段",
                "false": "保留原始 VAD 分割",
                "scenarios": {
                    "fragmented_transcript": "建议开启",
                    "precise_timestamps": "可尝试关闭"
                }
            }
        }
    )
    
    merge_length_s: int = Field(
        default=15,
        ge=5,
        le=30,
        description="合并最大长度(秒)。控制合并后片段的最大时长。",
        json_schema_extra={
            "impact": {
                "increase": "允许更长的合并片段",
                "decrease": "限制片段长度，更精细的分割",
                "recommended_range": "10-25"
            }
        }
    )


class ProcessConfig(BaseModel):
    video_analysis: bool = True
    face_analysis: bool = True
    micro_expression: bool = False
    audio_denoise: bool = True
    speaker_diarization: bool = False
    speech_to_text: bool = True
    prosody_analysis: bool = True
    emotion_recognition: bool = True
    multimodal_fusion: bool = True

    stt_model: str = "large-v3-turbo"
    stt_engine: str = "faster-whisper"
    diarization_model: str = "pyannote-3.1"
    diarization_engine: str = "pyannote"
    keyframe_interval: float = 5.0
    face_sample_rate: float = 2.0

    chunk_enabled: bool = False
    chunk_duration: float = 600.0

    diarization_config: Optional[DiarizationAdvancedConfig] = None
    stt_config: Optional[STTAdvancedConfig] = None


class AdvancedConfigDefaults(BaseModel):
    """返回给前端的默认配置和参数说明"""
    diarization: DiarizationAdvancedConfig = DiarizationAdvancedConfig()
    stt: STTAdvancedConfig = STTAdvancedConfig()


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
