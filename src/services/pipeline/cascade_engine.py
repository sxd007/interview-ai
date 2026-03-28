"""
Cascade Reprocessing Engine

Applies pending corrections and determines which downstream pipeline stages
need to be re-run based on what changed.
"""

import uuid
import os
from datetime import datetime
from typing import Optional, Dict, Any, List, Callable

from sqlalchemy.orm import Session

from src.models.database import (
    Interview,
    Speaker,
    AudioSegment,
    EmotionNode,
    PipelineStage,
    PendingChange,
    StageStatus,
    ChangeType,
)


PIPELINE_STAGE_ORDER = [
    "audio_extract",
    "denoise",
    "diarization",
    "stt",
    "face_analysis",
    "keyframes",
    "prosody",
    "emotion",
    "fusion",
]


def get_stage_index(name: str) -> int:
    try:
        return PIPELINE_STAGE_ORDER.index(name)
    except ValueError:
        return -1


def invalidate_stages_for_change(
    db: Session,
    interview_id: str,
    change_type: ChangeType,
    change_data: Dict[str, Any],
) -> List[str]:
    """
    Determine which pipeline stages need to be invalidated based on a correction.
    Returns list of stage names to invalidate.
    """
    stages_to_invalidate = []

    if change_type in (
        ChangeType.SPEAKER_MERGE,
        ChangeType.SPEAKER_SPLIT,
        ChangeType.SPEAKER_REASSIGN,
        ChangeType.SPEAKER_RENAME,
        ChangeType.SEGMENT_MERGE,
        ChangeType.SEGMENT_EDIT,
        ChangeType.SEGMENT_DELETE,
    ):
        stages_to_invalidate = ["prosody", "emotion", "fusion"]

    for stage_name in stages_to_invalidate:
        stage = db.query(PipelineStage).filter(
            PipelineStage.interview_id == interview_id,
            PipelineStage.stage_name == stage_name,
        ).first()
        if stage and stage.status == StageStatus.COMPLETED.value:
            stage.status = StageStatus.PENDING.value
            stage.completed_at = None
            stage.progress = 0.0

    return stages_to_invalidate


def apply_speaker_merge(
    db: Session,
    interview_id: str,
    merged_speaker_ids: List[str],
    target_speaker_id: str,
    chunk_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Merge multiple speakers into one (within a specific chunk).
    All segments from merged speakers get reassigned to target_speaker.
    Merged speakers are marked as merged_into.
    """
    target_speaker = db.query(Speaker).filter(
        Speaker.id == target_speaker_id,
        Speaker.interview_id == interview_id,
    ).first()
    if not target_speaker:
        raise ValueError(f"Target speaker {target_speaker_id} not found")

    affected_segments = []
    for sp_id in merged_speaker_ids:
        if sp_id == target_speaker_id:
            continue
        speaker = db.query(Speaker).filter(
            Speaker.id == sp_id,
            Speaker.interview_id == interview_id,
            Speaker.chunk_id == chunk_id,
        ).first()
        if speaker:
            speaker.merged_into = target_speaker_id

        seg_query = db.query(AudioSegment).filter(
            AudioSegment.interview_id == interview_id,
            AudioSegment.speaker_id == sp_id,
        )
        if chunk_id:
            seg_query = seg_query.filter(AudioSegment.chunk_id == chunk_id)
        segments = seg_query.all()
        for seg in segments:
            seg.speaker_id = target_speaker_id
            affected_segments.append(seg.id)

    db.commit()
    return {
        "affected_segments": affected_segments,
        "target_speaker": target_speaker.label,
        "merged_count": len(merged_speaker_ids) - 1,
    }


def apply_speaker_rename(
    db: Session,
    speaker_id: str,
    new_label: str,
) -> Dict[str, Any]:
    speaker = db.query(Speaker).filter(Speaker.id == speaker_id).first()
    if not speaker:
        raise ValueError(f"Speaker {speaker_id} not found")
    old_label = speaker.label
    speaker.label = new_label
    db.commit()
    return {"old_label": old_label, "new_label": new_label}


def apply_segment_edit(
    db: Session,
    segment_id: str,
    changes: Dict[str, Any],
) -> AudioSegment:
    """
    Apply edits to a segment (time, speaker, text).
    Marks the segment as corrected and locked.
    """
    segment = db.query(AudioSegment).filter(AudioSegment.id == segment_id).first()
    if not segment:
        raise ValueError(f"Segment {segment_id} not found")

    if "start_time" in changes:
        segment.start_time = changes["start_time"]
    if "end_time" in changes:
        segment.end_time = changes["end_time"]
    if "speaker_id" in changes:
        segment.speaker_id = changes["speaker_id"]
    if "transcript" in changes:
        segment.transcript = changes["transcript"]

    segment.is_locked = True
    segment.corrected_at = datetime.utcnow()

    db.commit()
    return segment


def apply_segment_merge(
    db: Session,
    segment_ids: List[str],
) -> AudioSegment:
    """
    Merge multiple adjacent segments into one.
    Keeps the first segment, extends its end_time, deletes others.
    """
    if len(segment_ids) < 2:
        raise ValueError("Need at least 2 segments to merge")

    segments = db.query(AudioSegment).filter(
        AudioSegment.id.in_(segment_ids)
    ).order_by(AudioSegment.start_time).all()

    if len(segments) < 2:
        raise ValueError(f"Only found {len(segments)} segments")

    main_seg = segments[0]
    main_seg.end_time = max(s. end_time for s in segments)
    main_seg.is_locked = True
    main_seg.corrected_at = datetime.utcnow()

    for seg in segments[1:]:
        db.delete(seg)

    db.commit()
    return main_seg


def apply_segment_split(
    db: Session,
    segment_id: str,
    split_time: float,
) -> List[AudioSegment]:
    """
    Split one segment into two at split_time.
    """
    segment = db.query(AudioSegment).filter(AudioSegment.id == segment_id).first()
    if not segment:
        raise ValueError(f"Segment {segment_id} not found")

    if not (segment.start_time < split_time < segment.end_time):
        raise ValueError(f"Split time {split_time} must be between {segment.start_time} and {segment.end_time}")

    segment.is_locked = True
    segment.corrected_at = datetime.utcnow()

    new_segment = AudioSegment(
        id=str(uuid.uuid4()),
        interview_id=segment.interview_id,
        speaker_id=segment.speaker_id,
        start_time=split_time,
        end_time=segment.end_time,
        transcript=None,
        lang=segment.lang,
        event=segment.event,
    )
    segment.end_time = split_time

    db.add(new_segment)
    db.commit()
    return [segment, new_segment]


def apply_speaker_reassign(
    db: Session,
    segment_ids: List[str],
    new_speaker_id: str,
) -> Dict[str, Any]:
    """
    Reassign a list of segments to a different speaker.
    """
    affected = db.query(AudioSegment).filter(
        AudioSegment.id.in_(segment_ids)
    ).all()

    old_speaker_id = affected[0].speaker_id if affected else None
    for seg in affected:
        seg.speaker_id = new_speaker_id
        seg.is_locked = True
        seg.corrected_at = datetime.utcnow()

    db.commit()
    return {
        "affected_segments": [s.id for s in affected],
        "old_speaker_id": old_speaker_id,
        "new_speaker_id": new_speaker_id,
        "count": len(affected),
    }


def apply_all_pending_changes(
    db: Session,
    interview_id: str,
    hf_token: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Apply all pending changes for an interview and invalidate downstream stages.
    Returns summary of what was done.
    """
    pending = db.query(PendingChange).filter(
        PendingChange.interview_id == interview_id,
        PendingChange.applied == False,
    ).order_by(PendingChange.created_at).all()

    if not pending:
        return {"applied": 0, "changes": [], "stages_invalidated": []}

    stages_invalidated = set()
    applied_changes = []

    for change in pending:
        change_type = ChangeType(change.change_type)
        change_data = change.change_data
        result = {}

        if change_type == ChangeType.SPEAKER_MERGE:
            result = apply_speaker_merge(
                db, interview_id,
                change_data["merged_speaker_ids"],
                change_data["target_speaker_id"],
                chunk_id=change.chunk_id,
            )
        elif change_type == ChangeType.SPEAKER_RENAME:
            result = apply_speaker_rename(
                db, change_data["speaker_id"],
                change_data["new_label"],
            )
        elif change_type == ChangeType.SEGMENT_EDIT:
            result = {"segment_id": change_data["segment_id"]}
            apply_segment_edit(db, change_data["segment_id"], change_data["changes"])
        elif change_type == ChangeType.SEGMENT_MERGE:
            result = apply_segment_merge(db, change_data["segment_ids"])
        elif change_type == ChangeType.SEGMENT_DELETE:
            seg = db.query(AudioSegment).filter(AudioSegment.id == change_data["segment_id"]).first()
            if seg:
                db.delete(seg)
            result = {"segment_id": change_data["segment_id"]}
        elif change_type == ChangeType.SPEAKER_REASSIGN:
            result = apply_speaker_reassign(
                db, change_data["segment_ids"],
                change_data["new_speaker_id"],
            )
        elif change_type == ChangeType.SPEAKER_SPLIT:
            result = {"segments": [s.id for s in apply_segment_split(
                db, change_data["segment_id"], change_data["split_time"]
            )]}
        else:
            result = {"skipped": f"Unknown change type: {change_type}"}

        invalidated = invalidate_stages_for_change(db, interview_id, change_type, change_data)
        stages_invalidated.update(invalidated)

        change.applied = True
        change.applied_at = datetime.utcnow()

        applied_changes.append({
            "id": change.id,
            "type": change.change_type,
            "result": result,
            "stages_invalidated": list(invalidated),
        })

    db.commit()

    deleted_nodes = db.query(EmotionNode).filter(
        EmotionNode.interview_id == interview_id,
        EmotionNode.source == "audio",
    ).delete()
    db.commit()

    return {
        "applied": len(applied_changes),
        "changes": applied_changes,
        "stages_invalidated": list(stages_invalidated),
        "emotion_nodes_deleted": deleted_nodes,
    }


def discard_all_pending_changes(
    db: Session,
    interview_id: str,
) -> int:
    """
    Delete all pending (unapplied) changes for an interview.
    Returns count of deleted changes.
    """
    count = db.query(PendingChange).filter(
        PendingChange.interview_id == interview_id,
        PendingChange.applied == False,
    ).delete()
    db.commit()
    return count


def add_pending_change(
    db: Session,
    interview_id: str,
    change_type: ChangeType,
    change_data: Dict[str, Any],
    description: str,
    chunk_id: Optional[str] = None,
) -> PendingChange:
    """
    Queue a pending change without applying it immediately.
    """
    change = PendingChange(
        id=str(uuid.uuid4()),
        interview_id=interview_id,
        chunk_id=chunk_id,
        change_type=change_type.value,
        target_id=change_data.get("target_id"),
        change_data=change_data,
        description=description,
    )
    db.add(change)
    db.commit()
    return change


def get_pending_changes_summary(
    db: Session,
    interview_id: str,
) -> Dict[str, Any]:
    """
    Get a summary of all pending (unapplied) changes.
    """
    pending = db.query(PendingChange).filter(
        PendingChange.interview_id == interview_id,
        PendingChange.applied == False,
    ).all()

    by_type: Dict[str, int] = {}
    for c in pending:
        by_type[c.change_type] = by_type.get(c.change_type, 0) + 1

    return {
        "total": len(pending),
        "by_type": by_type,
        "changes": [
            {
                "id": c.id,
                "type": c.change_type,
                "description": c.description,
                "target_id": c.target_id,
                "created_at": c.created_at.isoformat(),
            }
            for c in pending
        ],
    }
