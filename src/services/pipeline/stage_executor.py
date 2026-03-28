"""
Pipeline Stage Executor

Runs individual pipeline stages with proper status tracking,
dependencies, and rollback on failure.
"""

import uuid
import os
from datetime import datetime
from typing import Optional, Callable, Dict, Any, List
from dataclasses import dataclass

from sqlalchemy.orm import Session

from src.models.database import (
    Interview,
    PipelineStage,
    Speaker,
    AudioSegment,
    EmotionNode,
    StageStatus,
)


STAGE_DEFINITIONS = [
    {
        "name": "audio_extract",
        "label": "音频提取",
        "label_en": "Audio Extraction",
        "description": "从视频中提取音频流",
        "depends_on": [],
        "affects": ["denoise", "diarization", "stt"],
    },
    {
        "name": "denoise",
        "label": "音频降噪",
        "label_en": "Audio Denoising",
        "description": "降低背景噪声",
        "depends_on": ["audio_extract"],
        "affects": ["diarization", "stt"],
    },
    {
        "name": "diarization",
        "label": "人声识别",
        "label_en": "Speaker Diarization",
        "description": "识别不同说话人并分割时间范围",
        "depends_on": ["denoise"],
        "affects": ["stt", "prosody", "emotion"],
    },
    {
        "name": "stt",
        "label": "文字提取",
        "label_en": "Speech-to-Text",
        "description": "将语音转录为文字（审核后生效）",
        "depends_on": ["denoise"],
        "affects": ["prosody", "emotion"],
    },
    {
        "name": "face_analysis",
        "label": "人脸分析",
        "label_en": "Face Analysis",
        "description": "检测人脸和表情（独立运行）",
        "depends_on": [],
        "affects": ["fusion"],
    },
    {
        "name": "keyframes",
        "label": "关键帧提取",
        "label_en": "Keyframe Extraction",
        "description": "提取视频关键帧",
        "depends_on": [],
        "affects": [],
    },
    {
        "name": "prosody",
        "label": "韵律分析",
        "label_en": "Prosody Analysis",
        "description": "分析语调、语速、停顿等韵律特征（纠错后执行）",
        "depends_on": ["stt", "diarization"],
        "affects": ["emotion", "fusion"],
    },
    {
        "name": "emotion",
        "label": "情绪识别",
        "label_en": "Emotion Recognition",
        "description": "基于音频的情绪识别（纠错后执行）",
        "depends_on": ["prosody"],
        "affects": ["fusion"],
    },
    {
        "name": "fusion",
        "label": "情绪融合",
        "label_en": "Emotion Fusion",
        "description": "融合音频与视频情绪数据，生成报告",
        "depends_on": ["emotion", "face_analysis"],
        "affects": [],
    },
]


def get_stage_def(name: str) -> Optional[Dict[str, Any]]:
    for s in STAGE_DEFINITIONS:
        if s["name"] == name:
            return s
    return None


def ensure_stage_exists(
    db: Session,
    interview_id: str,
    stage_name: str,
) -> PipelineStage:
    stage = db.query(PipelineStage).filter(
        PipelineStage.interview_id == interview_id,
        PipelineStage.stage_name == stage_name,
    ).first()
    if not stage:
        stage = PipelineStage(
            id=str(uuid.uuid4()),
            interview_id=interview_id,
            stage_name=stage_name,
            status=StageStatus.PENDING.value,
        )
        db.add(stage)
        db.commit()
    return stage


def get_stage_status(
    db: Session,
    interview_id: str,
    stage_name: str,
) -> str:
    stage = db.query(PipelineStage).filter(
        PipelineStage.interview_id == interview_id,
        PipelineStage.stage_name == stage_name,
    ).first()
    return stage.status if stage else StageStatus.PENDING.value


def update_stage_status(
    db: Session,
    interview_id: str,
    stage_name: str,
    status: str,
    progress: float = 1.0,
    result_summary: Optional[Dict[str, Any]] = None,
    error_message: Optional[str] = None,
) -> PipelineStage:
    stage = db.query(PipelineStage).filter(
        PipelineStage.interview_id == interview_id,
        PipelineStage.stage_name == stage_name,
    ).first()
    if not stage:
        stage = ensure_stage_exists(db, interview_id, stage_name)

    stage.status = status
    stage.progress = progress

    if status == StageStatus.RUNNING.value:
        stage.started_at = datetime.utcnow()
    elif status in (StageStatus.COMPLETED.value, StageStatus.FAILED.value):
        stage.completed_at = datetime.utcnow()

    if error_message:
        stage.error_message = error_message
    if result_summary:
        stage.result_summary = result_summary

    db.commit()
    return stage


def get_all_stages(
    db: Session,
    interview_id: str,
) -> List[PipelineStage]:
    stages = db.query(PipelineStage).filter(
        PipelineStage.interview_id == interview_id,
    ).order_by(PipelineStage.created_at).all()

    result = []
    for s in STAGE_DEFINITIONS:
        existing = next((st for st in stages if st.stage_name == s["name"]), None)
        if existing:
            result.append(existing)
        else:
            ps = PipelineStage(
                id=str(uuid.uuid4()),
                interview_id=interview_id,
                stage_name=s["name"],
                status=StageStatus.PENDING.value,
            )
            db.add(ps)
            result.append(ps)
    db.commit()
    return result


def can_run_stage(
    db: Session,
    interview_id: str,
    stage_name: str,
) -> tuple[bool, str]:
    """
    Check if a stage can run (dependencies are completed).
    Returns (can_run, reason).
    """
    stage_def = get_stage_def(stage_name)
    if not stage_def:
        return False, f"Unknown stage: {stage_name}"

    if not stage_def["depends_on"]:
        return True, ""

    dep_statuses = []
    for dep in stage_def["depends_on"]:
        dep_status = get_stage_status(db, interview_id, dep)
        dep_statuses.append(f"{dep}={dep_status}")
        if dep_status == StageStatus.FAILED.value:
            return False, f"Dependency '{dep}' failed"
        if dep_status not in (StageStatus.COMPLETED.value, StageStatus.AWAITING_REVIEW.value):
            return False, f"Dependency '{dep}' not completed (status: {dep_status}). Required: {', '.join(dep_statuses)}"

    return True, ""


def run_stage(
    db: Session,
    interview_id: str,
    stage_name: str,
    runner: Callable[[Session, Interview, Callable], Dict[str, Any]],
    progress_callback: Optional[Callable[[str, float, str], None]] = None,
) -> Dict[str, Any]:
    """
    Run a pipeline stage with proper status tracking.
    runner: function(interview_id, interview, callback) -> result_dict
    """
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise ValueError(f"Interview {interview_id} not found")

    can_run_, reason = can_run_stage(db, interview_id, stage_name)
    if not can_run_:
        raise RuntimeError(f"Cannot run stage '{stage_name}': {reason}")

    def progress_handler(message: str, progress: float = 0.0):
        update_stage_status(db, interview_id, stage_name, StageStatus.RUNNING.value, progress)
        if progress_callback:
            progress_callback(stage_name, progress, message)

    update_stage_status(db, interview_id, stage_name, StageStatus.RUNNING.value, 0.0)
    progress_handler(f"开始执行 {stage_name}", 0.0)

    try:
        result = runner(db, interview, progress_handler)
        update_stage_status(
            db, interview_id, stage_name,
            StageStatus.COMPLETED.value, 1.0,
            result_summary=result,
        )
        return result
    except Exception as e:
        update_stage_status(
            db, interview_id, stage_name,
            StageStatus.FAILED.value, 0.0,
            error_message=str(e),
        )
        raise


def reset_stage(
    db: Session,
    interview_id: str,
    stage_name: str,
) -> PipelineStage:
    """
    Reset a stage to pending (allows re-running).
    Also invalidates all downstream stages.
    """
    stage = db.query(PipelineStage).filter(
        PipelineStage.interview_id == interview_id,
        PipelineStage.stage_name == stage_name,
    ).first()
    if not stage:
        raise ValueError(f"Stage {stage_name} not found for interview {interview_id}")

    stage.status = StageStatus.PENDING.value
    stage.completed_at = None
    stage.progress = 0.0
    stage.error_message = None
    stage.result_summary = None

    stage_def = get_stage_def(stage_name)
    if stage_def:
        for downstream in stage_def["affects"]:
            dep_stage = db.query(PipelineStage).filter(
                PipelineStage.interview_id == interview_id,
                PipelineStage.stage_name == downstream,
            ).first()
            if dep_stage and dep_stage.status != StageStatus.PENDING.value:
                dep_stage.status = StageStatus.PENDING.value
                dep_stage.completed_at = None
                dep_stage.progress = 0.0

    db.commit()
    return stage
