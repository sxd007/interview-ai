import pytest
import numpy as np
from unittest.mock import Mock, patch, MagicMock

from src.inference.diarization.engine import (
    DiarizationEngine,
    get_diarization_engine,
)


class TestDiarizationEngineInit:
    def test_init_default_params(self):
        engine = DiarizationEngine()
        assert engine.device in ["cuda", "mps", "cpu"]
        assert engine.pipeline is None

    def test_init_custom_device(self):
        engine = DiarizationEngine(device="cpu")
        assert engine.device == "cpu"


class TestDiarizationEngineDevice:
    def test_get_device_cuda(self):
        with patch("torch.cuda.is_available", return_value=True):
            engine = DiarizationEngine()
            assert engine.device == "cuda"

    def test_get_device_mps(self):
        with patch("torch.cuda.is_available", return_value=False):
            with patch("torch.backends.mps.is_available", return_value=True):
                engine = DiarizationEngine()
                assert engine.device == "mps"

    def test_get_device_cpu(self):
        with patch("torch.cuda.is_available", return_value=False):
            with patch("torch.backends.mps.is_available", return_value=False):
                engine = DiarizationEngine()
                assert engine.device == "cpu"


class TestDiarizationEngineMergeSegments:
    def test_merge_segments_empty(self):
        engine = DiarizationEngine()
        result = engine._merge_segments([])
        assert result == []

    def test_merge_segments_single(self):
        engine = DiarizationEngine()
        segments = [{"start": 0.0, "end": 5.0, "speaker": "SPEAKER_00"}]
        result = engine._merge_segments(segments)
        assert len(result) == 1
        assert result[0]["start"] == 0.0
        assert result[0]["end"] == 5.0

    def test_merge_segments_same_speaker_small_gap(self):
        engine = DiarizationEngine()
        segments = [
            {"start": 0.0, "end": 5.0, "speaker": "SPEAKER_00"},
            {"start": 5.1, "end": 10.0, "speaker": "SPEAKER_00"},
        ]
        result = engine._merge_segments(segments, gap_threshold=0.5)
        
        assert len(result) == 1
        assert result[0]["start"] == 0.0
        assert result[0]["end"] == 10.0

    def test_merge_segments_same_speaker_large_gap(self):
        engine = DiarizationEngine()
        segments = [
            {"start": 0.0, "end": 5.0, "speaker": "SPEAKER_00"},
            {"start": 10.0, "end": 15.0, "speaker": "SPEAKER_00"},
        ]
        result = engine._merge_segments(segments, gap_threshold=0.5)
        
        assert len(result) == 2

    def test_merge_segments_different_speakers(self):
        engine = DiarizationEngine()
        segments = [
            {"start": 0.0, "end": 5.0, "speaker": "SPEAKER_00"},
            {"start": 5.1, "end": 10.0, "speaker": "SPEAKER_01"},
        ]
        result = engine._merge_segments(segments, gap_threshold=0.5)
        
        assert len(result) == 2

    def test_merge_segments_multiple_same_speaker(self):
        engine = DiarizationEngine()
        segments = [
            {"start": 0.0, "end": 5.0, "speaker": "SPEAKER_00"},
            {"start": 5.2, "end": 10.0, "speaker": "SPEAKER_00"},
            {"start": 10.3, "end": 15.0, "speaker": "SPEAKER_00"},
        ]
        result = engine._merge_segments(segments, gap_threshold=0.5)
        
        assert len(result) == 1
        assert result[0]["start"] == 0.0
        assert result[0]["end"] == 15.0


class TestDiarizationEngineGetSpeakerCount:
    def test_get_speaker_count_empty(self):
        engine = DiarizationEngine()
        count = engine.get_speaker_count([])
        assert count == 0

    def test_get_speaker_count_single(self):
        engine = DiarizationEngine()
        segments = [
            {"start": 0.0, "end": 5.0, "speaker": "SPEAKER_00"},
        ]
        count = engine.get_speaker_count(segments)
        assert count == 1

    def test_get_speaker_count_multiple(self):
        engine = DiarizationEngine()
        segments = [
            {"start": 0.0, "end": 5.0, "speaker": "SPEAKER_00"},
            {"start": 5.0, "end": 10.0, "speaker": "SPEAKER_01"},
            {"start": 10.0, "end": 15.0, "speaker": "SPEAKER_02"},
        ]
        count = engine.get_speaker_count(segments)
        assert count == 3

    def test_get_speaker_count_repeated(self):
        engine = DiarizationEngine()
        segments = [
            {"start": 0.0, "end": 5.0, "speaker": "SPEAKER_00"},
            {"start": 5.0, "end": 10.0, "speaker": "SPEAKER_00"},
            {"start": 10.0, "end": 15.0, "speaker": "SPEAKER_01"},
        ]
        count = engine.get_speaker_count(segments)
        assert count == 2


class TestDiarizationEngineUnload:
    def test_unload(self):
        engine = DiarizationEngine()
        engine.pipeline = Mock()
        
        engine.unload()
        
        assert engine.pipeline is None


class TestGetDiarizationEngine:
    def test_get_engine_default(self):
        engine = get_diarization_engine()
        assert isinstance(engine, DiarizationEngine)

    def test_get_engine_custom_device(self):
        engine = get_diarization_engine(device="cpu")
        assert engine.device == "cpu"
