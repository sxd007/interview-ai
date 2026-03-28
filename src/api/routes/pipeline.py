"""
Pipeline Management API Routes
"""

import uuid
import os
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.api.deps import get_db
from src.models.database import (
    Interview,
    PipelineStage,
    PendingChange,
    Speaker,
    AudioSegment,
    StageStatus,
    ChangeType,
    Interview,
    VideoChunk,
    ChunkStatus,
    AnnotationLog,
    AnnotationType,
    ApprovalStatus,
    EmotionNode,
)
from src.services.pipeline.stage_executor import (
    get_all_stages,
    get_stage_status,
    can_run_stage,
    reset_stage,
    STAGE_DEFINITIONS,
)
from src.services.pipeline.cascade_engine import (
    add_pending_change,
    get_pending_changes_summary,
    apply_all_pending_changes,
    discard_all_pending_changes,
    apply_speaker_merge,
    apply_speaker_rename,
    apply_segment_edit,
    apply_segment_merge,
    apply_segment_split,
    apply_speaker_reassign,
)
from src.services.audio.processor import AudioProcessor
from src.inference.diarization.engine import DiarizationEngine
from src.inference.stt.sensevoice import SenseVoiceEngine


router = APIRouter(prefix="/interviews", tags=["pipeline"])


@router.get("/{interview_id}/pipeline")
def get_pipeline(interview_id: str, db: Session = Depends(get_db)):
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    stages = get_all_stages(db, interview_id)
    pending_summary = get_pending_changes_summary(db, interview_id)

    stage_infos = []
    for s in stages:
        stage_def = next((d for d in STAGE_DEFINITIONS if d["name"] == s.stage_name), None)
        info = {
            "id": s.id,
            "name": s.stage_name,
            "label": stage_def["label"] if stage_def else s.stage_name,
            "label_en": stage_def["label_en"] if stage_def else s.stage_name,
            "description": stage_def["description"] if stage_def else "",
            "depends_on": stage_def["depends_on"] if stage_def else [],
            "affects": stage_def["affects"] if stage_def else [],
            "status": s.status,
            "progress": s.progress,
            "error_message": s.error_message,
            "result_summary": s.result_summary,
            "approved_by": s.approved_by,
            "approved_at": s.approved_at.isoformat() if s.approved_at else None,
            "started_at": s.started_at.isoformat() if s.started_at else None,
            "completed_at": s.completed_at.isoformat() if s.completed_at else None,
        }
        if s.status == StageStatus.PENDING.value:
            can_run, reason = can_run_stage(db, interview_id, s.stage_name)
            info["can_run"] = can_run
            info["blocked_reason"] = reason if not can_run else None
        else:
            info["can_run"] = False
            info["blocked_reason"] = None
        stage_infos.append(info)

    return {
        "interview_id": interview_id,
        "interview_status": interview.status,
        "stages": stage_infos,
        "pending_changes": pending_summary,
    }


@router.post("/{interview_id}/pipeline/{stage_name}/run")
def run_pipeline_stage(
    interview_id: str,
    stage_name: str,
    db: Session = Depends(get_db),
):
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    can_run_, reason = can_run_stage(db, interview_id, stage_name)
    if not can_run_:
        raise HTTPException(status_code=400, detail=reason)

    hf_token = os.getenv("HF_TOKEN")

    try:
        if stage_name == "audio_extract":
            result = _run_audio_extract(db, interview, hf_token)
        elif stage_name == "denoise":
            result = _run_denoise(db, interview, hf_token)
        elif stage_name == "diarization":
            result = _run_diarization(db, interview, hf_token)
        elif stage_name == "stt":
            result = _run_stt(db, interview, hf_token)
        elif stage_name == "face_analysis":
            result = _run_face_analysis(db, interview)
        elif stage_name == "keyframes":
            result = _run_keyframes(db, interview)
        elif stage_name == "prosody":
            result = _run_prosody(db, interview)
        else:
            raise HTTPException(status_code=400, detail=f"Stage '{stage_name}' not yet implemented")

        return {"status": "completed", "stage": stage_name, "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{interview_id}/pipeline/{stage_name}/approve")
def approve_stage(
    interview_id: str,
    stage_name: str,
    approved_by: str = "user",
    db: Session = Depends(get_db),
):
    stage = db.query(PipelineStage).filter(
        PipelineStage.interview_id == interview_id,
        PipelineStage.stage_name == stage_name,
    ).first()
    if not stage:
        raise HTTPException(status_code=404, detail="Stage not found")
    if stage.status not in (StageStatus.COMPLETED.value, StageStatus.AWAITING_REVIEW.value):
        raise HTTPException(status_code=400, detail=f"Stage status is '{stage.status}', cannot approve")

    stage.status = StageStatus.COMPLETED.value
    stage.approved_by = approved_by
    stage.approved_at = uuid.uuid4()
    db.commit()
    return {"status": "approved", "stage": stage_name}


@router.post("/{interview_id}/pipeline/{stage_name}/reset")
def reset_pipeline_stage(
    interview_id: str,
    stage_name: str,
    db: Session = Depends(get_db),
):
    try:
        reset_stage(db, interview_id, stage_name)
        return {"status": "reset", "stage": stage_name}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{interview_id}/chunks")
def get_chunks(interview_id: str, db: Session = Depends(get_db)):
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    chunks = db.query(VideoChunk).filter(
        VideoChunk.interview_id == interview_id
    ).order_by(VideoChunk.chunk_index).all()

    return {
        "interview_id": interview_id,
        "is_chunked": interview.is_chunked,
        "chunk_duration": interview.chunk_duration,
        "chunk_count": interview.chunk_count,
        "chunks": [
            {
                "id": c.id,
                "chunk_index": c.chunk_index,
                "global_start": c.global_start,
                "global_end": c.global_end,
                "status": c.status,
                "file_path": c.file_path,
                "error_message": c.error_message,
                "created_at": c.created_at.isoformat() if c.created_at else None,
                "review_pending_at": c.review_pending_at.isoformat() if c.review_pending_at else None,
                "reviewed_at": c.reviewed_at.isoformat() if c.reviewed_at else None,
            }
            for c in chunks
        ],
    }


@router.post("/{interview_id}/chunks/{chunk_id}/approve")
def approve_chunk(
    interview_id: str,
    chunk_id: str,
    approved_by: str = "user",
    session_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    chunk = db.query(VideoChunk).filter(
        VideoChunk.id == chunk_id,
        VideoChunk.interview_id == interview_id,
    ).first()
    if not chunk:
        raise HTTPException(status_code=404, detail="Chunk not found")

    if chunk.status not in (ChunkStatus.REVIEW_PENDING.value,):
        raise HTTPException(
            status_code=400,
            detail=f"Chunk status is '{chunk.status}', can only approve 'review_pending' chunks",
        )

    pending = db.query(PendingChange).filter(
        PendingChange.interview_id == interview_id,
        PendingChange.applied == False,
    ).all()

    for change in pending:
        change_type = ChangeType(change.change_type)
        log = AnnotationLog(
            id=str(uuid.uuid4()),
            interview_id=interview_id,
            chunk_id=chunk_id,
            annotation_type=AnnotationType.MANUAL_CORRECTION.value,
            change_type=change.change_type,
            change_data=change.change_data,
            corrected_by=approved_by,
            session_id=session_id,
            approval_status=ApprovalStatus.APPROVED.value,
            reprocess_triggered=True,
        )
        db.add(log)

    if pending:
        apply_all_pending_changes(db, interview_id)

    chunk.status = ChunkStatus.REVIEW_COMPLETED.value
    chunk.reviewed_at = datetime.utcnow()
    chunk.approved_by = approved_by

    all_chunks = db.query(VideoChunk).filter(
        VideoChunk.interview_id == interview_id
    ).all()
    all_reviewed = all(c.status == ChunkStatus.REVIEW_COMPLETED.value for c in all_chunks)

    if all_reviewed:
        # Update stt stage status
        stt_stage = db.query(PipelineStage).filter(
            PipelineStage.interview_id == interview_id,
            PipelineStage.stage_name == "stt",
        ).first()
        if stt_stage and stt_stage.status != StageStatus.COMPLETED.value:
            stt_stage.status = StageStatus.COMPLETED.value
            stt_stage.completed_at = datetime.utcnow()
            stt_stage.result_summary = {"all_chunks_reviewed": True}

        # Also update diarization stage status
        diarization_stage = db.query(PipelineStage).filter(
            PipelineStage.interview_id == interview_id,
            PipelineStage.stage_name == "diarization",
        ).first()
        if diarization_stage and diarization_stage.status != StageStatus.COMPLETED.value:
            diarization_stage.status = StageStatus.COMPLETED.value
            diarization_stage.completed_at = datetime.utcnow()
            diarization_stage.result_summary = {"all_chunks_reviewed": True}

        _unlock_deep_analysis_stages(db, interview_id)

    db.commit()

    return {
        "status": "approved",
        "chunk_id": chunk_id,
        "changes_applied": len(pending),
        "all_chunks_reviewed": all_reviewed,
    }


@router.post("/{interview_id}/pipeline/run-all")
def run_all_stages(
    interview_id: str,
    db: Session = Depends(get_db),
):
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    results = {}
    for stage_def in STAGE_DEFINITIONS:
        name = stage_def["name"]
        can_run_, _ = can_run_stage(db, interview_id, name)
        if not can_run_:
            continue
        try:
            results[name] = {"status": "skipped", "reason": "unimplemented"}
        except Exception as e:
            results[name] = {"status": "error", "error": str(e)}

    return {"results": results}


def _run_audio_extract(db, interview, hf_token):
    import soundfile as sf
    processor = AudioProcessor()
    audio_path, sr = processor.extract_audio(interview.file_path)
    info = sf.info(audio_path)
    interview.duration = float(info.frames) / float(info.samplerate)
    db.commit()
    return {"audio_path": audio_path, "duration": interview.duration}


def _run_denoise(db, interview, hf_token):
    processor = AudioProcessor()
    audio_path = processor.extract_audio(interview.file_path)[0]
    denoised_path = processor.denoise(audio_path)
    return {"denoised_path": denoised_path}


def _run_diarization(db, interview, hf_token):
    processor = AudioProcessor()
    audio_path = processor.extract_audio(interview.file_path)[0]
    diarization_engine = DiarizationEngine(auth_token=hf_token)
    speakers_data = diarization_engine.diarize(audio_path)

    speaker_order = list(dict.fromkeys(s["speaker"] for s in speakers_data))
    speaker_map = {}
    colors = ["#1890ff", "#52c41a", "#faad14", "#f5222d", "#722ed1", "#13c2c2"]

    for i, sp_label in enumerate(speaker_order):
        sp = Speaker(
            id=str(uuid.uuid4()),
            interview_id=interview.id,
            label=f"说话人 {chr(65 + i)}",
            color=colors[i % len(colors)],
        )
        db.add(sp)
        db.flush()
        speaker_map[sp_label] = sp.id

    segments = db.query(AudioSegment).filter(
        AudioSegment.interview_id == interview.id
    ).all()
    for seg in segments:
        mid = (seg.start_time + seg.end_time) / 2
        for sd in speakers_data:
            if sd["start"] <= mid <= sd["end"]:
                seg.speaker_id = speaker_map.get(sd["speaker"])
                break

    db.commit()
    return {"speaker_count": len(speaker_order), "segments_affected": len(segments)}


def _run_stt(db, interview, hf_token):
    processor = AudioProcessor()
    audio_path = processor.extract_audio(interview.file_path)[0]
    stt = SenseVoiceEngine(device="cpu")
    stt.load()
    result = stt.transcribe(audio_path, language="auto", use_itn=True)

    from src.inference.stt.sensevoice import (
        clean_text, parse_sentence_tags, split_sentences, estimate_sentence_timestamps,
    )

    raw_text = result.get("text", "")
    parsed_sentences = parse_sentence_tags(raw_text)
    if not parsed_sentences:
        clean = clean_text(raw_text)
        sentences_raw = split_sentences(clean)
        parsed_sentences = [{"text": t, "lang": "unknown", "emotion": "neutral", "event": "speech"} for t in sentences_raw]

    sentences_with_meta = []
    for item_meta in parsed_sentences:
        parts = split_sentences(item_meta["text"])
        for part in parts:
            if part.strip():
                sentences_with_meta.append({
                    "text": part.strip(),
                    "lang": item_meta.get("lang", "unknown"),
                    "emotion": item_meta.get("emotion", "neutral"),
                    "event": item_meta.get("event", "speech"),
                })

    duration = interview.duration or 1.0
    timestamps = estimate_sentence_timestamps(
        [s["text"] for s in sentences_with_meta], duration
    )

    db.query(AudioSegment).filter(
        AudioSegment.interview_id == interview.id
    ).delete()

    speakers = db.query(Speaker).filter(Speaker.interview_id == interview.id).all()
    speaker_map = {sp.id: sp.id for sp in speakers}

    for i, sent in enumerate(sentences_with_meta):
        start, end = timestamps[i] if i < len(timestamps) else (0.0, 0.0)
        db.add(AudioSegment(
            id=str(uuid.uuid4()),
            interview_id=interview.id,
            speaker_id=None,
            start_time=start,
            end_time=end,
            transcript=sent["text"],
            confidence=0.9,
            lang=sent["lang"],
            event=sent["event"],
            emotion_scores={"emotion": sent["emotion"]},
        ))

    db.commit()
    stt.unload()
    os.unlink(audio_path)
    return {"segments_created": len(sentences_with_meta), "text_length": len(raw_text)}


def _run_face_analysis(db, interview):
    from src.inference.face.engine import get_face_engine
    face_engine = get_face_engine()
    results = face_engine.detect_from_video(interview.file_path, sample_rate=2.0)
    from src.models.database import FaceFrame
    for face_data in results:
        db.add(FaceFrame(
            id=str(uuid.uuid4()),
            interview_id=interview.id,
            timestamp=face_data["timestamp"],
            frame_path=face_data.get("frame_path"),
            face_bbox=face_data.get("bbox"),
            landmarks=face_data.get("landmarks"),
            action_units=face_data.get("action_units"),
            emotion_scores=face_data.get("emotion_scores"),
        ))
    db.commit()
    return {"face_frames": len(results)}


def _run_keyframes(db, interview):
    from src.services.video.keyframe import KeyframeExtractor
    extractor = KeyframeExtractor()
    keyframes = extractor.detect_scenes(interview.file_path, save_frames=True, output_dir=None)
    from src.models.database import Keyframe as KB
    for kf in keyframes:
        db.add(KB(
            id=str(uuid.uuid4()),
            interview_id=interview.id,
            timestamp=kf.timestamp,
            frame_idx=kf.frame_idx,
            scene_len=kf.scene_len,
            frame_path=kf.frame_path,
        ))
    db.commit()
    return {"keyframes": len(keyframes)}


def _run_prosody(db: Session, interview):
    from src.services.audio.processor import AudioProcessor
    from src.services.audio.prosody import ProsodyAnalyzer
    from src.models.database import AudioSegment, VideoChunk
    
    processor = AudioProcessor()
    
    # 尝试复用已有的音频（STT 阶段已提取）
    audio_path = None
    chunks = db.query(VideoChunk).filter(VideoChunk.interview_id == interview.id).all()
    for chunk in chunks:
        if chunk.audio_path:
            audio_path = chunk.audio_path
            break
    
    # 如果没有已提取的音频，才需要重新提取
    if not audio_path:
        audio_path, _ = processor.extract_audio(interview.file_path)
    
    raw_audio, sr = processor.load_audio(audio_path)
    
    prosody_analyzer = ProsodyAnalyzer()
    
    segments = db.query(AudioSegment).filter(
        AudioSegment.interview_id == interview.id
    ).order_by(AudioSegment.start_time).all()
    
    segments_data = []
    for seg in segments:
        segments_data.append({
            "start": seg.start_time,
            "end": seg.end_time,
            "text": seg.transcript,
        })
    
    if not segments_data:
        return {"error": "No segments found"}
    
    results = prosody_analyzer.analyze_segments(raw_audio, sr, segments_data)
    
    for i, seg in enumerate(segments):
        if i < len(results):
            seg.prosody = results[i]
    
    db.commit()
    return {"segments_analyzed": len(segments)}


def _unlock_deep_analysis_stages(db: Session, interview_id: str):
    """
    When all chunks are reviewed, unlock prosody/emotion/fusion stages.
    Also delete existing audio EmotionNodes so they can be regenerated.
    """
    deep_stages = ["prosody", "emotion", "fusion"]
    for stage_name in deep_stages:
        stage = db.query(PipelineStage).filter(
            PipelineStage.interview_id == interview_id,
            PipelineStage.stage_name == stage_name,
        ).first()
        if stage:
            stage.status = StageStatus.PENDING.value
            stage.completed_at = None
            stage.progress = 0.0

    db.query(EmotionNode).filter(
        EmotionNode.interview_id == interview_id,
        EmotionNode.source == "audio",
    ).delete(synchronize_session=False)

    db.query(AudioSegment).filter(
        AudioSegment.interview_id == interview_id,
    ).update({"prosody": None, "emotion_scores": {"emotion": "neutral"}}, synchronize_session=False)

    db.commit()
