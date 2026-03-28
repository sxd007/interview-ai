import pytest


class TestInterviewValidation:
    def test_filename_required(self):
        from src.api.schemas import InterviewCreate
        with pytest.raises(ValueError):
            InterviewCreate(filename="")

    def test_process_config_defaults(self):
        from src.api.schemas import ProcessConfig
        config = ProcessConfig()
        assert config.video_analysis is True
        assert config.face_analysis is True
        assert config.speech_to_text is True


class TestEmotionNodeValidation:
    def test_intensity_range(self):
        from src.api.schemas import EmotionNodeResponse
        node = EmotionNodeResponse(
            id="test",
            timestamp=0.0,
            source="audio",
            label="happy",
            intensity=1.5,
            confidence=0.9,
        )
        assert node.intensity == 1.5


class TestSegmentValidation:
    def test_segment_times(self):
        from src.api.schemas import SegmentResponse
        segment = SegmentResponse(
            id="test",
            start_time=5.0,
            end_time=10.0,
        )
        assert segment.start_time < segment.end_time
