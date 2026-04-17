import pytest
import numpy as np
from unittest.mock import patch, Mock

from src.services.audio.prosody import (
    ProsodyAnalyzer,
    ProsodyFeatures,
    get_prosody_analyzer,
)


class TestProsodyFeatures:
    def test_prosody_features_creation(self):
        features = ProsodyFeatures(
            pitch_mean=150.0,
            pitch_std=30.0,
            pitch_min=80.0,
            pitch_max=300.0,
            energy_mean=0.5,
            energy_std=0.1,
            speech_rate=4.5,
            pause_ratio=0.2,
            filler_count=3,
            pitch_range=220.0,
            energy_range=0.4,
        )
        
        assert features.pitch_mean == 150.0
        assert features.pitch_std == 30.0
        assert features.speech_rate == 4.5

    def test_prosody_features_to_dict(self):
        features = ProsodyFeatures(
            pitch_mean=150.0,
            pitch_std=30.0,
            pitch_min=80.0,
            pitch_max=300.0,
            energy_mean=0.5,
            energy_std=0.1,
            speech_rate=4.5,
            pause_ratio=0.2,
            filler_count=3,
            pitch_range=220.0,
            energy_range=0.4,
        )
        
        result = features.to_dict()
        
        assert isinstance(result, dict)
        assert result["pitch_mean"] == 150.0
        assert result["speech_rate"] == 4.5
        assert result["filler_count"] == 3


class TestProsodyAnalyzerInit:
    def test_init_default_sample_rate(self):
        analyzer = ProsodyAnalyzer()
        assert analyzer.sample_rate == 16000

    def test_init_custom_sample_rate(self):
        analyzer = ProsodyAnalyzer(sample_rate=22050)
        assert analyzer.sample_rate == 22050


class TestProsodyAnalyzerEmptyResult:
    def test_empty_result(self):
        analyzer = ProsodyAnalyzer()
        result = analyzer._empty_result()
        
        assert result["pitch_mean"] == 0.0
        assert result["pitch_std"] == 0.0
        assert result["energy_mean"] == 0.0
        assert result["speech_rate"] == 0.0
        assert result["pause_ratio"] == 0.0
        assert result["filler_count"] == 0


class TestProsodyAnalyzerComputeEnergy:
    def test_compute_energy_silent(self):
        analyzer = ProsodyAnalyzer()
        audio = np.zeros(16000, dtype=np.float32)
        energy = analyzer._compute_energy(audio, 16000)
        
        assert len(energy) > 0
        assert np.allclose(energy, 0.0, atol=1e-6)

    def test_compute_energy_loud(self):
        analyzer = ProsodyAnalyzer()
        audio = np.ones(16000, dtype=np.float32) * 0.5
        energy = analyzer._compute_energy(audio, 16000)
        
        assert len(energy) > 0
        assert np.all(energy > 0)

    def test_compute_energy_empty(self):
        analyzer = ProsodyAnalyzer()
        audio = np.array([], dtype=np.float32)
        energy = analyzer._compute_energy(audio, 16000)
        
        assert len(energy) == 0

    def test_compute_energy_short(self):
        analyzer = ProsodyAnalyzer()
        audio = np.random.randn(100).astype(np.float32)
        energy = analyzer._compute_energy(audio, 16000)
        
        assert len(energy) >= 0


class TestProsodyAnalyzerComputePitch:
    def test_compute_pitch_silent(self):
        analyzer = ProsodyAnalyzer()
        audio = np.zeros(16000, dtype=np.float32)
        f0, voiced, probs = analyzer._compute_pitch(audio, 16000)
        
        assert len(f0) > 0

    def test_compute_pitch_short_audio(self):
        analyzer = ProsodyAnalyzer()
        audio = np.random.randn(1000).astype(np.float32)
        f0, voiced, probs = analyzer._compute_pitch(audio, 16000)
        
        assert len(f0) == 0

    def test_compute_pitch_returns_tuple(self):
        analyzer = ProsodyAnalyzer()
        audio = np.random.randn(16000).astype(np.float32) * 0.3
        result = analyzer._compute_pitch(audio, 16000)
        
        assert isinstance(result, tuple)
        assert len(result) == 3


class TestProsodyAnalyzerComputeSpeechRate:
    def test_compute_speech_rate_silent(self):
        analyzer = ProsodyAnalyzer()
        audio = np.zeros(16000, dtype=np.float32)
        rate, pause = analyzer._compute_speech_rate(audio, 16000)
        
        assert rate >= 0.0
        assert pause >= 0.0

    def test_compute_speech_rate_empty(self):
        analyzer = ProsodyAnalyzer()
        audio = np.array([], dtype=np.float32)
        rate, pause = analyzer._compute_speech_rate(audio, 16000)
        
        assert rate == 0.0
        assert pause == 0.0

    def test_compute_speech_rate_with_speech(self):
        analyzer = ProsodyAnalyzer()
        audio = np.random.randn(48000).astype(np.float32) * 0.5
        rate, pause = analyzer._compute_speech_rate(audio, 16000)
        
        assert isinstance(rate, float)
        assert isinstance(pause, float)
        assert rate >= 0.0
        assert 0.0 <= pause <= 1.0


class TestProsodyAnalyzerDetectFillers:
    def test_detect_fillers_silent(self):
        analyzer = ProsodyAnalyzer()
        audio = np.zeros(16000, dtype=np.float32)
        count = analyzer._detect_fillers(audio, 16000)
        
        assert count == 0

    def test_detect_fillers_empty(self):
        analyzer = ProsodyAnalyzer()
        audio = np.array([], dtype=np.float32)
        count = analyzer._detect_fillers(audio, 16000)
        
        assert count == 0

    def test_detect_fillers_with_audio(self):
        analyzer = ProsodyAnalyzer()
        audio = np.random.randn(16000).astype(np.float32) * 0.3
        count = analyzer._detect_fillers(audio, 16000)
        
        assert isinstance(count, int)
        assert count >= 0


class TestProsodyAnalyzerAnalyzeArray:
    def test_analyze_array_silent(self):
        analyzer = ProsodyAnalyzer()
        audio = np.zeros(16000, dtype=np.float32)
        result = analyzer.analyze_array(audio, 16000)
        
        assert "pitch_mean" in result
        assert "energy_mean" in result
        assert "speech_rate" in result

    def test_analyze_array_with_audio(self):
        analyzer = ProsodyAnalyzer()
        audio = np.random.randn(48000).astype(np.float32) * 0.3
        result = analyzer.analyze_array(audio, 16000)
        
        assert "pitch_mean" in result
        assert "pitch_std" in result
        assert "energy_mean" in result
        assert "speech_rate" in result
        assert "pause_ratio" in result

    def test_analyze_array_empty(self):
        analyzer = ProsodyAnalyzer()
        audio = np.array([], dtype=np.float32)
        result = analyzer.analyze_array(audio, 16000)
        
        assert result == analyzer._empty_result()

    def test_analyze_array_none(self):
        analyzer = ProsodyAnalyzer()
        result = analyzer.analyze_array(None, 16000)
        
        assert result == analyzer._empty_result()


class TestProsodyAnalyzerAnalyzeSegments:
    def test_analyze_segments_empty(self):
        analyzer = ProsodyAnalyzer()
        audio = np.zeros(16000, dtype=np.float32)
        segments = []
        
        results = analyzer.analyze_segments(audio, 16000, segments)
        assert results == []

    def test_analyze_segments_single(self):
        analyzer = ProsodyAnalyzer()
        audio = np.random.randn(48000).astype(np.float32) * 0.3
        segments = [{"start": 0.0, "end": 1.0}]
        
        results = analyzer.analyze_segments(audio, 16000, segments)
        assert len(results) == 1
        assert "start" in results[0]
        assert "end" in results[0]
        assert "pitch_mean" in results[0]

    def test_analyze_segments_multiple(self):
        analyzer = ProsodyAnalyzer()
        audio = np.random.randn(160000).astype(np.float32) * 0.3
        segments = [
            {"start": 0.0, "end": 2.0},
            {"start": 2.0, "end": 4.0},
            {"start": 4.0, "end": 6.0},
        ]
        
        results = analyzer.analyze_segments(audio, 16000, segments)
        assert len(results) == 3

    def test_analyze_segments_out_of_bounds(self):
        analyzer = ProsodyAnalyzer()
        audio = np.random.randn(16000).astype(np.float32) * 0.3
        segments = [{"start": 0.0, "end": 10.0}]
        
        results = analyzer.analyze_segments(audio, 16000, segments)
        assert len(results) == 1
        assert "pitch_mean" in results[0]

    def test_analyze_segments_empty_segment(self):
        analyzer = ProsodyAnalyzer()
        audio = np.random.randn(16000).astype(np.float32) * 0.3
        segments = [{"start": 5.0, "end": 5.0}]
        
        results = analyzer.analyze_segments(audio, 16000, segments)
        assert len(results) == 1
        assert results[0]["pitch_mean"] == 0.0


class TestGetProsodyAnalyzer:
    def test_get_analyzer_default(self):
        analyzer = get_prosody_analyzer()
        assert isinstance(analyzer, ProsodyAnalyzer)
        assert analyzer.sample_rate == 16000

    def test_get_analyzer_custom_sample_rate(self):
        analyzer = get_prosody_analyzer(sample_rate=22050)
        assert isinstance(analyzer, ProsodyAnalyzer)
        assert analyzer.sample_rate == 22050
