"""
Correction / Editing API Routes
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.api.deps import get_db
from src.models.database import (
    Interview,
    Speaker,
    AudioSegment,
    PendingChange,
    ChangeType,
)
from src.services.pipeline.cascade_engine import (
    add_pending_change,
    get_pending_changes_summary,
    apply_all_pending_changes,
    discard_all_pending_changes,
)


router = APIRouter(prefix="/interviews", tags=["corrections"])


class SpeakerRenameRequest(BaseModel):
    speaker_id: str
    new_label: str
    chunk_id: str


class SpeakerMergeRequest(BaseModel):
    target_speaker_id: str
    merged_speaker_ids: list[str]
    chunk_id: str


class SpeakerReassignRequest(BaseModel):
    segment_ids: list[str]
    new_speaker_id: str


class SegmentEditRequest(BaseModel):
    segment_id: str
    changes: dict


class SegmentSplitRequest(BaseModel):
    segment_id: str
    split_time: float
    speaker_id_1: str | None = None
    speaker_id_2: str | None = None
    text_1: str | None = None
    text_2: str | None = None


class SegmentSplitByTextRequest(BaseModel):
    segment_id: str
    split_text_position: int
    speaker_id_1: str
    speaker_id_2: str
    time_ratio: float | None = None
    text_1: str | None = None
    text_2: str | None = None


class SegmentMergeRequest(BaseModel):
    segment_ids: list[str]


# ---------- Speaker Corrections ----------

@router.post("/{interview_id}/corrections/rename-speaker")
def rename_speaker(
    interview_id: str,
    req: SpeakerRenameRequest,
    db: Session = Depends(get_db),
):
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    speaker = db.query(Speaker).filter(
        Speaker.id == req.speaker_id,
        Speaker.interview_id == interview_id,
    ).first()
    if not speaker:
        raise HTTPException(status_code=404, detail="Speaker not found")

    change = add_pending_change(
        db, interview_id,
        ChangeType.SPEAKER_RENAME,
        {"speaker_id": req.speaker_id, "new_label": req.new_label},
        f"重命名说话人 '{speaker.label}' → '{req.new_label}'",
        chunk_id=req.chunk_id,
    )

    summary = get_pending_changes_summary(db, interview_id)
    return {"change_id": change.id, "pending_summary": summary}


@router.post("/{interview_id}/corrections/merge-speakers")
def merge_speakers(
    interview_id: str,
    req: SpeakerMergeRequest,
    db: Session = Depends(get_db),
):
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    target = db.query(Speaker).filter(
        Speaker.id == req.target_speaker_id,
        Speaker.interview_id == interview_id,
    ).first()
    if not target:
        raise HTTPException(status_code=404, detail="Target speaker not found")

    other_labels = []
    for sp_id in req.merged_speaker_ids:
        if sp_id == req.target_speaker_id:
            continue
        sp = db.query(Speaker).filter(
            Speaker.id == sp_id,
            Speaker.interview_id == interview_id,
        ).first()
        if sp:
            other_labels.append(sp.label)

    desc = f"合并说话人 [{', '.join(other_labels)}] → [{target.label}]"
    change = add_pending_change(
        db, interview_id,
        ChangeType.SPEAKER_MERGE,
        {"target_speaker_id": req.target_speaker_id, "merged_speaker_ids": req.merged_speaker_ids},
        desc,
        chunk_id=req.chunk_id,
    )

    summary = get_pending_changes_summary(db, interview_id)
    return {"change_id": change.id, "pending_summary": summary}


@router.post("/{interview_id}/corrections/reassign-speaker")
def reassign_segments(
    interview_id: str,
    req: SpeakerReassignRequest,
    db: Session = Depends(get_db),
):
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    segments = db.query(AudioSegment).filter(
        AudioSegment.id.in_(req.segment_ids),
        AudioSegment.interview_id == interview_id,
    ).all()
    if not segments:
        raise HTTPException(status_code=404, detail="No segments found")

    speaker = db.query(Speaker).filter(
        Speaker.id == req.new_speaker_id,
        Speaker.interview_id == interview_id,
    ).first()

    old_sp = db.query(Speaker).filter(
        Speaker.id == segments[0].speaker_id,
        Speaker.interview_id == interview_id,
    ).first()
    old_label = old_sp.label if old_sp else "未知"
    new_label = speaker.label if speaker else "未知"

    change = add_pending_change(
        db, interview_id,
        ChangeType.SPEAKER_REASSIGN,
        {"segment_ids": req.segment_ids, "new_speaker_id": req.new_speaker_id},
        f"将 {len(segments)} 个段落从 [{old_label}] 改到 [{new_label}]",
    )

    summary = get_pending_changes_summary(db, interview_id)
    return {"change_id": change.id, "pending_summary": summary}


# ---------- Segment Corrections ----------

@router.post("/{interview_id}/corrections/edit-segment")
def edit_segment(
    interview_id: str,
    req: SegmentEditRequest,
    db: Session = Depends(get_db),
):
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    segment = db.query(AudioSegment).filter(
        AudioSegment.id == req.segment_id,
        AudioSegment.interview_id == interview_id,
    ).first()
    if not segment:
        raise HTTPException(status_code=404, detail="Segment not found")

    changed_fields = ", ".join(req.changes.keys())
    change = add_pending_change(
        db, interview_id,
        ChangeType.SEGMENT_EDIT,
        {"segment_id": req.segment_id, "changes": req.changes},
        f"编辑段落: 修改 {changed_fields}",
    )

    summary = get_pending_changes_summary(db, interview_id)
    return {"change_id": change.id, "pending_summary": summary}


@router.post("/{interview_id}/corrections/split-segment")
def split_segment(
    interview_id: str,
    req: SegmentSplitRequest,
    db: Session = Depends(get_db),
):
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    segment = db.query(AudioSegment).filter(
        AudioSegment.id == req.segment_id,
        AudioSegment.interview_id == interview_id,
    ).first()
    if not segment:
        raise HTTPException(status_code=404, detail="Segment not found")

    from src.services.pipeline.cascade_engine import apply_segment_split

    segments = apply_segment_split(
        db,
        req.segment_id,
        req.split_time,
        speaker_id_1=req.speaker_id_1,
        speaker_id_2=req.speaker_id_2,
        text_1=req.text_1,
        text_2=req.text_2,
    )

    change = add_pending_change(
        db, interview_id,
        ChangeType.SEGMENT_EDIT,
        {
            "segment_id": req.segment_id,
            "split_time": req.split_time,
            "speaker_id_1": req.speaker_id_1,
            "speaker_id_2": req.speaker_id_2,
            "text_1": req.text_1,
            "text_2": req.text_2,
        },
        f"分裂段落于 {req.split_time:.1f}s",
    )

    summary = get_pending_changes_summary(db, interview_id)
    return {
        "change_id": change.id,
        "pending_summary": summary,
        "new_segment_id": segments[1].id if len(segments) > 1 else None,
    }


@router.post("/{interview_id}/corrections/split-segment-by-text")
def split_segment_by_text(
    interview_id: str,
    req: SegmentSplitByTextRequest,
    db: Session = Depends(get_db),
):
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    segment = db.query(AudioSegment).filter(
        AudioSegment.id == req.segment_id,
        AudioSegment.interview_id == interview_id,
    ).first()
    if not segment:
        raise HTTPException(status_code=404, detail="Segment not found")

    from src.services.pipeline.cascade_engine import (
        estimate_split_time_hybrid,
        split_text_at_position,
    )

    text_1, text_2 = split_text_at_position(
        segment.transcript or "",
        req.split_text_position
    )

    if req.text_1:
        text_1 = req.text_1
    if req.text_2:
        text_2 = req.text_2

    if req.time_ratio is not None:
        duration = segment.end_time - segment.start_time
        split_time = segment.start_time + duration * req.time_ratio
    else:
        split_time = estimate_split_time_hybrid(segment, req.split_text_position)

    change = add_pending_change(
        db, interview_id,
        ChangeType.SEGMENT_EDIT,
        {
            "segment_id": req.segment_id,
            "split_time": split_time,
            "speaker_id_1": req.speaker_id_1,
            "speaker_id_2": req.speaker_id_2,
            "text_1": text_1,
            "text_2": text_2,
        },
        f"基于文本分割段落: {text_1[:20]}... | {text_2[:20]}...",
    )

    summary = get_pending_changes_summary(db, interview_id)
    return {
        "change_id": change.id,
        "pending_summary": summary,
        "estimated_split_time": split_time,
        "text_1": text_1,
        "text_2": text_2,
    }


@router.post("/{interview_id}/corrections/merge-segments")
def merge_segments(
    interview_id: str,
    req: SegmentMergeRequest,
    db: Session = Depends(get_db),
):
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    if len(req.segment_ids) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 segments to merge")

    change = add_pending_change(
        db, interview_id,
        ChangeType.SEGMENT_MERGE,
        {"segment_ids": req.segment_ids},
        f"合并 {len(req.segment_ids)} 个段落",
    )

    summary = get_pending_changes_summary(db, interview_id)
    return {"change_id": change.id, "pending_summary": summary}


# ---------- Batch Operations ----------

@router.get("/{interview_id}/corrections/pending")
def get_pending_corrections(interview_id: str, db: Session = Depends(get_db)):
    summary = get_pending_changes_summary(db, interview_id)
    return summary


@router.post("/{interview_id}/corrections/apply")
def apply_corrections(interview_id: str, db: Session = Depends(get_db)):
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    result = apply_all_pending_changes(db, interview_id)
    return result


@router.post("/{interview_id}/corrections/discard")
def discard_corrections(interview_id: str, db: Session = Depends(get_db)):
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    count = discard_all_pending_changes(db, interview_id)
    return {"discarded": count}


@router.delete("/{interview_id}/corrections/{change_id}")
def delete_pending_correction(
    interview_id: str,
    change_id: str,
    db: Session = Depends(get_db),
):
    change = db.query(PendingChange).filter(
        PendingChange.id == change_id,
        PendingChange.interview_id == interview_id,
        PendingChange.applied == False,
    ).first()
    if not change:
        raise HTTPException(status_code=404, detail="Pending change not found")

    db.delete(change)
    db.commit()
    summary = get_pending_changes_summary(db, interview_id)
    return {"deleted": change_id, "pending_summary": summary}
