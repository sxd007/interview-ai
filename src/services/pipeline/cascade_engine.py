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


def merge_speakers_by_label(db: Session, interview_id: str) -> Dict[str, Any]:
    """
    Merge speakers across all chunks that have the same label.
    This is called when all chunks are reviewed to consolidate duplicate speaker names.
    """
    all_speakers = db.query(Speaker).filter(
        Speaker.interview_id == interview_id,
    ).all()
    
    if not all_speakers:
        return {"merged_groups": 0, "speakers_merged": 0}
    
    from src.utils.logging import get_logger
    logger = get_logger(__name__)
    print(f"[merge_speakers_by_label] ========== START for interview {interview_id} ==========")
    print(f"[merge_speakers_by_label] Found {len(all_speakers)} speakers")
    logger.info(f"[merge_speakers_by_label] Found {len(all_speakers)} speakers for interview {interview_id}")
    
    if not all_speakers:
        print("[merge_speakers_by_label] No speakers found, returning early")
        return {"merged_groups": 0, "speakers_merged": 0}
    
    # Debug: print all speaker labels
    all_labels = set(sp.label for sp in all_speakers if sp.label)
    print(f"[merge_speakers_by_label] All unique labels: {all_labels}")
    logger.info(f"[merge_speakers_by_label] All labels: {all_labels}")
    
    # Debug: print speakers grouped by label
    for label in all_labels:
        speakers_with_label = [sp for sp in all_speakers if sp.label == label]
        if len(speakers_with_label) > 1:
            print(f"[merge_speakers_by_label] Label '{label}' has {len(speakers_with_label)} speakers: {[sp.id for sp in speakers_with_label]}")
            logger.info(f"[merge_speakers_by_label] Label '{label}' has {len(speakers_with_label)} speakers")
    
    # Don't skip merged_into, we need to re-merge if needed
    label_to_speakers: Dict[str, List[Speaker]] = {}
    for sp in all_speakers:
        label = sp.label or "Unknown"
        if label not in label_to_speakers:
            label_to_speakers[label] = []
        label_to_speakers[label].append(sp)
    
    # Reset merged_into for speakers that will be re-merged
    for label, speakers in label_to_speakers.items():
        if len(speakers) > 1:
            print(f"[merge_speakers_by_label] Will re-merge label '{label}' with {len(speakers)} speakers")
            for sp in speakers:
                sp.merged_into = None  # Reset previous merge
    
    print(f"[merge_speakers_by_label] label_to_speakers counts: {[(k, len(v)) for k, v in label_to_speakers.items()]}")
    
    logger.info(f"[merge_speakers_by_label] label_to_speakers: {[(k, len(v)) for k, v in label_to_speakers.items()]}")
    
    speakers_merged = 0
    merged_groups = 0
    
    for label, speakers in label_to_speakers.items():
        if len(speakers) <= 1:
            continue
        
        merged_groups += 1
        target_speaker = speakers[0]
        print(f"[merge_speakers_by_label] >>> MERGING {len(speakers)} speakers with label '{label}' into {target_speaker.id}")
        logger.info(f"[merge_speakers_by_label] Merging {len(speakers)} speakers with label '{label}' into {target_speaker.id}")
        
        for speaker in speakers[1:]:
            segments = db.query(AudioSegment).filter(
                AudioSegment.speaker_id == speaker.id,
            ).all()
            print(f"[merge_speakers_by_label] Reassigning {len(segments)} segments from {speaker.id[:8]} to {target_speaker.id[:8]}")
            logger.info(f"[merge_speakers_by_label] Reassigning {len(segments)} segments from {speaker.id} to {target_speaker.id}")
            
            for seg in segments:
                seg.speaker_id = target_speaker.id
            
            speaker.merged_into = target_speaker.id
            speakers_merged += 1
    
    db.commit()
    
    print(f"[merge_speakers_by_label] <<< Result: merged_groups={merged_groups}, speakers_merged={speakers_merged}")
    logger.info(f"[merge_speakers_by_label] Result: merged_groups={merged_groups}, speakers_merged={speakers_merged}")
    return {
        "merged_groups": merged_groups,
        "speakers_merged": speakers_merged,
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


def estimate_by_char_ratio(
    segment: AudioSegment,
    split_position: int,
) -> float:
    """
    基于字符比例估算时间分割点
    
    Args:
        segment: 音频片段
        split_position: 文本分割位置（字符索引）
    
    Returns:
        估算的时间分割点
    """
    total_chars = len(segment.transcript or "")
    if total_chars == 0:
        return (segment.start_time + segment.end_time) / 2
    
    ratio = split_position / total_chars
    duration = segment.end_time - segment.start_time
    split_time = segment.start_time + duration * ratio
    
    epsilon = 0.001
    split_time = max(segment.start_time + epsilon, min(split_time, segment.end_time - epsilon))
    
    return split_time


def estimate_by_word_timestamps(
    segment: AudioSegment,
    split_position: int,
    word_timestamps: List[Dict[str, Any]],
) -> float:
    """
    基于词级时间戳估算时间分割点
    
    Args:
        segment: 音频片段
        split_position: 文本分割位置（字符索引）
        word_timestamps: 词级时间戳列表
    
    Returns:
        精确的时间分割点
    """
    if not word_timestamps:
        return estimate_by_char_ratio(segment, split_position)
    
    char_count = 0
    for word_info in word_timestamps:
        word = word_info.get('word', '')
        char_count += len(word)
        if char_count >= split_position:
            return word_info.get('start', segment.start_time)
    
    return segment.end_time


def estimate_split_time_hybrid(
    segment: AudioSegment,
    split_position: int,
    word_timestamps: Optional[List[Dict[str, Any]]] = None,
) -> float:
    """
    混合方法估算时间分割点
    
    优先使用词级时间戳，否则使用字符比例法
    
    Args:
        segment: 音频片段
        split_position: 文本分割位置（字符索引）
        word_timestamps: 可选的词级时间戳列表
    
    Returns:
        时间分割点
    """
    if word_timestamps:
        return estimate_by_word_timestamps(segment, split_position, word_timestamps)
    else:
        return estimate_by_char_ratio(segment, split_position)


def split_text_at_position(
    transcript: str,
    position: int,
) -> tuple[str, str]:
    """
    在指定位置分割文本，智能处理边界情况
    
    Args:
        transcript: 原始文本
        position: 分割位置
    
    Returns:
        (text1, text2): 分割后的两段文本
    """
    if not transcript:
        return "", ""
    
    position = max(0, min(position, len(transcript)))
    
    for offset in range(0, min(10, position)):
        if position - offset > 0 and transcript[position - offset - 1] in '，。！？；：':
            position = position - offset
            break
    
    text1 = transcript[:position].strip()
    text2 = transcript[position:].strip()
    
    return text1, text2


def apply_segment_split(
    db: Session,
    segment_id: str,
    split_time: float,
    speaker_id_1: Optional[str] = None,
    speaker_id_2: Optional[str] = None,
    text_1: Optional[str] = None,
    text_2: Optional[str] = None,
) -> List[AudioSegment]:
    """
    Split one segment into two at split_time.
    
    Args:
        db: 数据库会话
        segment_id: 要分割的片段ID
        split_time: 分割时间点
        speaker_id_1: 第一部分的说话人ID（可选）
        speaker_id_2: 第二部分的说话人ID（可选）
        text_1: 第一部分的文本（可选）
        text_2: 第二部分的文本（可选）
    
    Returns:
        分割后的两个片段列表
    """
    segment = db.query(AudioSegment).filter(AudioSegment.id == segment_id).first()
    if not segment:
        raise ValueError(f"Segment {segment_id} not found")

    epsilon = 0.001
    split_time = max(segment.start_time + epsilon, min(split_time, segment.end_time - epsilon))
    
    if not (segment.start_time < split_time < segment.end_time):
        raise ValueError(f"Split time {split_time} must be between {segment.start_time} and {segment.end_time}")

    segment.is_locked = True
    segment.corrected_at = datetime.utcnow()

    if text_1 is None:
        text_1 = segment.transcript
    if text_2 is None:
        text_2 = None

    new_segment = AudioSegment(
        id=str(uuid.uuid4()),
        interview_id=segment.interview_id,
        chunk_id=segment.chunk_id,
        speaker_id=speaker_id_2 if speaker_id_2 else segment.speaker_id,
        start_time=split_time,
        end_time=segment.end_time,
        transcript=text_2,
        lang=segment.lang,
        event=segment.event,
        is_locked=True,
        corrected_at=datetime.utcnow(),
    )
    
    segment.end_time = split_time
    if speaker_id_1:
        segment.speaker_id = speaker_id_1
    if text_1 is not None:
        segment.transcript = text_1

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
            if "split_time" in change_data:
                result = {"segments": [s.id for s in apply_segment_split(
                    db,
                    change_data["segment_id"],
                    change_data["split_time"],
                    speaker_id_1=change_data.get("speaker_id_1"),
                    speaker_id_2=change_data.get("speaker_id_2"),
                    text_1=change_data.get("text_1"),
                    text_2=change_data.get("text_2"),
                )]}
            else:
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
                "chunk_id": c.chunk_id,
                "change_type": c.change_type,
                "description": c.description,
                "target_id": c.target_id,
                "created_at": c.created_at.isoformat(),
            }
            for c in pending
        ],
    }
