import pytest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

from src.services.pipeline.cascade_engine import (
    PIPELINE_STAGE_ORDER,
    get_stage_index,
    invalidate_stages_for_change,
    apply_speaker_merge,
    apply_speaker_rename,
    apply_segment_edit,
    apply_segment_merge,
    apply_segment_split,
    apply_speaker_reassign,
    apply_all_pending_changes,
    discard_all_pending_changes,
    add_pending_change,
    get_pending_changes_summary,
    merge_speakers_by_label,
)
from src.models.database import (
    Speaker,
    AudioSegment,
    PipelineStage,
    PendingChange,
    StageStatus,
    ChangeType,
)


class TestPipelineStageOrder:
    def test_stage_order_length(self):
        assert len(PIPELINE_STAGE_ORDER) == 9

    def test_stage_order_sequence(self):
        assert PIPELINE_STAGE_ORDER[0] == "audio_extract"
        assert PIPELINE_STAGE_ORDER[-1] == "fusion"
        assert "stt" in PIPELINE_STAGE_ORDER
        assert "emotion" in PIPELINE_STAGE_ORDER


class TestGetStageIndex:
    def test_get_stage_index_valid(self):
        assert get_stage_index("audio_extract") == 0
        assert get_stage_index("fusion") == 8
        assert get_stage_index("stt") == 3

    def test_get_stage_index_invalid(self):
        assert get_stage_index("nonexistent") == -1

    def test_get_stage_order_correct(self):
        assert get_stage_index("denoise") < get_stage_index("stt")
        assert get_stage_index("stt") < get_stage_index("emotion")


class TestInvalidateStagesForChange:
    def test_invalidate_speaker_merge(self, db_session):
        interview_id = "test-interview"
        
        stage = PipelineStage(
            id="stage-1",
            interview_id=interview_id,
            stage_name="prosody",
            status=StageStatus.COMPLETED.value,
            progress=1.0,
        )
        db_session.add(stage)
        db_session.commit()
        
        invalidated = invalidate_stages_for_change(
            db_session,
            interview_id,
            ChangeType.SPEAKER_MERGE,
            {},
        )
        
        assert "prosody" in invalidated
        assert "emotion" in invalidated
        assert "fusion" in invalidated

    def test_invalidate_speaker_reassign(self, db_session):
        interview_id = "test-interview"
        
        invalidated = invalidate_stages_for_change(
            db_session,
            interview_id,
            ChangeType.SPEAKER_REASSIGN,
            {},
        )
        
        assert "prosody" in invalidated

    def test_invalidate_segment_edit(self, db_session):
        interview_id = "test-interview"
        
        invalidated = invalidate_stages_for_change(
            db_session,
            interview_id,
            ChangeType.SEGMENT_EDIT,
            {},
        )
        
        assert "prosody" in invalidated
        assert "emotion" in invalidated


class TestApplySpeakerRename:
    def test_apply_speaker_rename_success(self, db_session):
        speaker = Speaker(
            id="speaker-1",
            interview_id="test-interview",
            label="Speaker A",
            color="#1890ff",
        )
        db_session.add(speaker)
        db_session.commit()
        
        result = apply_speaker_rename(db_session, "speaker-1", "New Name")
        
        assert result["old_label"] == "Speaker A"
        assert result["new_label"] == "New Name"
        
        db_session.refresh(speaker)
        assert speaker.label == "New Name"

    def test_apply_speaker_rename_not_found(self, db_session):
        with pytest.raises(ValueError, match="not found"):
            apply_speaker_rename(db_session, "nonexistent", "New Name")


class TestApplySegmentEdit:
    def test_apply_segment_edit_time(self, db_session):
        segment = AudioSegment(
            id="segment-1",
            interview_id="test-interview",
            speaker_id=None,
            start_time=0.0,
            end_time=5.0,
            transcript="Hello",
        )
        db_session.add(segment)
        db_session.commit()
        
        result = apply_segment_edit(
            db_session,
            "segment-1",
            {"start_time": 1.0, "end_time": 6.0},
        )
        
        assert result.start_time == 1.0
        assert result.end_time == 6.0
        assert result.is_locked is True

    def test_apply_segment_edit_transcript(self, db_session):
        segment = AudioSegment(
            id="segment-1",
            interview_id="test-interview",
            speaker_id=None,
            start_time=0.0,
            end_time=5.0,
            transcript="Hello",
        )
        db_session.add(segment)
        db_session.commit()
        
        result = apply_segment_edit(
            db_session,
            "segment-1",
            {"transcript": "Hello World"},
        )
        
        assert result.transcript == "Hello World"

    def test_apply_segment_edit_not_found(self, db_session):
        with pytest.raises(ValueError, match="not found"):
            apply_segment_edit(db_session, "nonexistent", {})


class TestApplySegmentMerge:
    def test_apply_segment_merge_success(self, db_session):
        seg1 = AudioSegment(
            id="segment-1",
            interview_id="test-interview",
            speaker_id=None,
            start_time=0.0,
            end_time=5.0,
            transcript="Hello",
        )
        seg2 = AudioSegment(
            id="segment-2",
            interview_id="test-interview",
            speaker_id=None,
            start_time=5.0,
            end_time=10.0,
            transcript="World",
        )
        db_session.add_all([seg1, seg2])
        db_session.commit()
        
        result = apply_segment_merge(db_session, ["segment-1", "segment-2"])
        
        assert result.end_time == 10.0
        assert result.is_locked is True

    def test_apply_segment_merge_single_segment(self, db_session):
        with pytest.raises(ValueError, match="Need at least 2"):
            apply_segment_merge(db_session, ["segment-1"])

    def test_apply_segment_merge_not_found(self, db_session):
        with pytest.raises(ValueError, match="Only found"):
            apply_segment_merge(db_session, ["nonexistent-1", "nonexistent-2"])


class TestApplySegmentSplit:
    def test_apply_segment_split_success(self, db_session):
        segment = AudioSegment(
            id="segment-1",
            interview_id="test-interview",
            speaker_id=None,
            start_time=0.0,
            end_time=10.0,
            transcript="Hello World",
        )
        db_session.add(segment)
        db_session.commit()
        
        result = apply_segment_split(db_session, "segment-1", 5.0)
        
        assert len(result) == 2
        assert result[0].end_time == 5.0
        assert result[1].start_time == 5.0

    def test_apply_segment_split_invalid_time(self, db_session):
        segment = AudioSegment(
            id="segment-1",
            interview_id="test-interview",
            speaker_id=None,
            start_time=0.0,
            end_time=10.0,
            transcript="Hello",
        )
        db_session.add(segment)
        db_session.commit()
        
        with pytest.raises(ValueError, match="must be between"):
            apply_segment_split(db_session, "segment-1", 15.0)

    def test_apply_segment_split_not_found(self, db_session):
        with pytest.raises(ValueError, match="not found"):
            apply_segment_split(db_session, "nonexistent", 5.0)


class TestApplySpeakerReassign:
    def test_apply_speaker_reassign_success(self, db_session):
        seg1 = AudioSegment(
            id="segment-1",
            interview_id="test-interview",
            speaker_id="speaker-1",
            start_time=0.0,
            end_time=5.0,
        )
        seg2 = AudioSegment(
            id="segment-2",
            interview_id="test-interview",
            speaker_id="speaker-1",
            start_time=5.0,
            end_time=10.0,
        )
        db_session.add_all([seg1, seg2])
        db_session.commit()
        
        result = apply_speaker_reassign(
            db_session,
            ["segment-1", "segment-2"],
            "speaker-2",
        )
        
        assert result["count"] == 2
        assert "speaker-2" in result["new_speaker_id"]

    def test_apply_speaker_reassign_empty(self, db_session):
        result = apply_speaker_reassign(db_session, [], "speaker-2")
        
        assert result["count"] == 0


class TestAddPendingChange:
    def test_add_pending_change(self, db_session):
        change = add_pending_change(
            db_session,
            "test-interview",
            ChangeType.SPEAKER_RENAME,
            {"speaker_id": "speaker-1", "new_label": "New Name"},
            "Rename speaker",
        )
        
        assert change.id is not None
        assert change.interview_id == "test-interview"
        assert change.change_type == ChangeType.SPEAKER_RENAME.value
        assert change.applied is False


class TestGetPendingChangesSummary:
    def test_get_pending_changes_summary_empty(self, db_session):
        result = get_pending_changes_summary(db_session, "test-interview")
        
        assert result["total"] == 0
        assert result["by_type"] == {}
        assert result["changes"] == []

    def test_get_pending_changes_summary_with_changes(self, db_session):
        add_pending_change(
            db_session,
            "test-interview",
            ChangeType.SPEAKER_RENAME,
            {"speaker_id": "s1"},
            "Rename",
        )
        add_pending_change(
            db_session,
            "test-interview",
            ChangeType.SEGMENT_EDIT,
            {"segment_id": "seg1"},
            "Edit",
        )
        
        result = get_pending_changes_summary(db_session, "test-interview")
        
        assert result["total"] == 2
        assert "speaker_rename" in result["by_type"]
        assert "segment_edit" in result["by_type"]


class TestDiscardAllPendingChanges:
    def test_discard_all_pending_changes(self, db_session):
        add_pending_change(
            db_session,
            "test-interview",
            ChangeType.SPEAKER_RENAME,
            {"speaker_id": "s1"},
            "Rename",
        )
        
        count = discard_all_pending_changes(db_session, "test-interview")
        
        assert count == 1
        
        result = get_pending_changes_summary(db_session, "test-interview")
        assert result["total"] == 0


class TestApplyAllPendingChanges:
    def test_apply_all_pending_changes_empty(self, db_session):
        result = apply_all_pending_changes(db_session, "test-interview")
        
        assert result["applied"] == 0
        assert result["changes"] == []

    def test_apply_all_pending_changes_with_rename(self, db_session):
        speaker = Speaker(
            id="speaker-1",
            interview_id="test-interview",
            label="Old Name",
            color="#1890ff",
        )
        db_session.add(speaker)
        db_session.commit()
        
        add_pending_change(
            db_session,
            "test-interview",
            ChangeType.SPEAKER_RENAME,
            {"speaker_id": "speaker-1", "new_label": "New Name"},
            "Rename speaker",
        )
        
        result = apply_all_pending_changes(db_session, "test-interview")
        
        assert result["applied"] == 1
        
        db_session.refresh(speaker)
        assert speaker.label == "New Name"


class TestMergeSpeakersByLabel:
    def test_merge_speakers_by_label_empty(self, db_session):
        result = merge_speakers_by_label(db_session, "test-interview")
        
        assert result["merged_groups"] == 0
        assert result["speakers_merged"] == 0

    def test_merge_speakers_by_label_no_duplicates(self, db_session):
        sp1 = Speaker(
            id="speaker-1",
            interview_id="test-interview",
            label="Speaker A",
            color="#1890ff",
        )
        sp2 = Speaker(
            id="speaker-2",
            interview_id="test-interview",
            label="Speaker B",
            color="#52c41a",
        )
        db_session.add_all([sp1, sp2])
        db_session.commit()
        
        result = merge_speakers_by_label(db_session, "test-interview")
        
        assert result["merged_groups"] == 0

    def test_merge_speakers_by_label_with_duplicates(self, db_session):
        sp1 = Speaker(
            id="speaker-1",
            interview_id="test-interview",
            label="Speaker A",
            color="#1890ff",
        )
        sp2 = Speaker(
            id="speaker-2",
            interview_id="test-interview",
            label="Speaker A",
            color="#52c41a",
        )
        seg1 = AudioSegment(
            id="segment-1",
            interview_id="test-interview",
            speaker_id="speaker-2",
            start_time=0.0,
            end_time=5.0,
        )
        db_session.add_all([sp1, sp2, seg1])
        db_session.commit()
        
        result = merge_speakers_by_label(db_session, "test-interview")
        
        assert result["merged_groups"] == 1
        assert result["speakers_merged"] == 1
