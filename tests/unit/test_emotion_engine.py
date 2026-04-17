import pytest
import numpy as np
from unittest.mock import Mock, patch, MagicMock

from src.inference.emotion.engine import (
    VoiceEmotionEngine,
    EMOTION_LABELS,
    STRESS_KEY_EMOTIONS,
    CONFIDENCE_KEY_EMOTIONS,
    get_voice_emotion_engine,
)


class TestVoiceEmotionEngineInit:
    def test_init_default_params(self):
        engine = VoiceEmotionEngine()
        assert engine.model_name is not None
        assert engine.model is None
        assert engine.processor is None

    def test_init_custom_device(self):
        engine = VoiceEmotionEngine(device="cpu")
        assert engine.device == "cpu"

    def test_init_custom_model_name(self):
        engine = VoiceEmotionEngine(model_name="custom-model")
        assert engine.model_name == "custom-model"


class TestVoiceEmotionEngineDevice:
    def test_get_device_cuda(self):
        with patch("torch.cuda.is_available", return_value=True):
            engine = VoiceEmotionEngine()
            assert engine.device == "cuda"

    def test_get_device_mps(self):
        with patch("torch.cuda.is_available", return_value=False):
            with patch("torch.backends.mps.is_available", return_value=True):
                engine = VoiceEmotionEngine()
                assert engine.device == "mps"

    def test_get_device_cpu(self):
        with patch("torch.cuda.is_available", return_value=False):
            with patch("torch.backends.mps.is_available", return_value=False):
                engine = VoiceEmotionEngine()
                assert engine.device == "cpu"


class TestVoiceEmotionEngineComputeScores:
    def test_compute_stress(self):
        engine = VoiceEmotionEngine()
        scores = {
            "anxious": 0.3,
            "fearful": 0.2,
            "angry": 0.1,
            "sad": 0.1,
            "neutral": 0.2,
            "happy": 0.1,
        }
        stress = engine._compute_stress(scores)
        assert stress == pytest.approx(0.7, rel=0.01)

    def test_compute_stress_zero(self):
        engine = VoiceEmotionEngine()
        scores = {label: 0.0 for label in EMOTION_LABELS}
        stress = engine._compute_stress(scores)
        assert stress == 0.0

    def test_compute_confidence(self):
        engine = VoiceEmotionEngine()
        scores = {
            "neutral": 0.6,
            "happy": 0.4,
            "sad": 0.0,
        }
        confidence = engine._compute_confidence(scores)
        assert confidence == pytest.approx(0.5, rel=0.01)

    def test_compute_confidence_zero(self):
        engine = VoiceEmotionEngine()
        scores = {label: 0.0 for label in EMOTION_LABELS}
        confidence = engine._compute_confidence(scores)
        assert confidence == 0.0


class TestVoiceEmotionEngineFallback:
    def test_fallback_analysis_array_silent(self):
        engine = VoiceEmotionEngine()
        audio = np.zeros(16000, dtype=np.float32)
        result = engine._fallback_analysis_array(audio, 16000)
        
        assert "dominant_emotion" in result
        assert "confidence" in result
        assert "emotion_scores" in result
        assert "stress_score" in result
        assert "is_stress" in result
        assert result["confidence"] == 0.4

    def test_fallback_analysis_array_loud(self):
        engine = VoiceEmotionEngine()
        audio = np.random.randn(16000).astype(np.float32) * 0.5
        result = engine._fallback_analysis_array(audio, 16000)
        
        assert "dominant_emotion" in result
        assert "emotion_scores" in result
        assert sum(result["emotion_scores"].values()) == pytest.approx(1.0, rel=0.01)

    def test_fallback_emotion_scores_sum_to_one(self):
        engine = VoiceEmotionEngine()
        audio = np.random.randn(16000).astype(np.float32) * 0.3
        result = engine._fallback_analysis_array(audio, 16000)
        
        total = sum(result["emotion_scores"].values())
        assert total == pytest.approx(1.0, rel=0.01)


class TestVoiceEmotionEnginePredictArray:
    def test_predict_array_without_model(self):
        engine = VoiceEmotionEngine()
        engine.model = None
        engine.processor = None
        
        audio = np.random.randn(16000).astype(np.float32) * 0.3
        result = engine.predict_array(audio, 16000)
        
        assert "dominant_emotion" in result
        assert "emotion_scores" in result

    def test_predict_array_resample(self):
        engine = VoiceEmotionEngine()
        engine.model = None
        
        audio = np.random.randn(22050).astype(np.float32) * 0.3
        result = engine.predict_array(audio, 22050)
        
        assert "dominant_emotion" in result


class TestVoiceEmotionEnginePredictSegments:
    def test_predict_segments_empty(self):
        engine = VoiceEmotionEngine()
        audio = np.zeros(16000, dtype=np.float32)
        segments = []
        
        results = engine.predict_segments(audio, 16000, segments)
        assert results == []

    def test_predict_segments_single(self):
        engine = VoiceEmotionEngine()
        engine.model = None
        
        audio = np.random.randn(48000).astype(np.float32) * 0.3
        segments = [{"start": 0.0, "end": 1.0}]
        
        results = engine.predict_segments(audio, 16000, segments)
        assert len(results) == 1
        assert "start" in results[0]
        assert "end" in results[0]
        assert results[0]["start"] == 0.0
        assert results[0]["end"] == 1.0

    def test_predict_segments_short_segment(self):
        engine = VoiceEmotionEngine()
        engine.model = None
        
        audio = np.random.randn(16000).astype(np.float32) * 0.3
        segments = [{"start": 0.0, "end": 0.05}]
        
        results = engine.predict_segments(audio, 16000, segments)
        assert len(results) == 1
        assert "emotion_scores" in results[0]


class TestVoiceEmotionEngineLoad:
    def test_load_skip_if_already_loaded(self):
        engine = VoiceEmotionEngine()
        engine.model = Mock()
        engine.processor = Mock()
        
        engine.load()
        
        assert engine.model is not None

    def test_unload(self):
        engine = VoiceEmotionEngine()
        engine.model = Mock()
        engine.processor = Mock()
        
        engine.unload()
        
        assert engine.model is None
        assert engine.processor is None


class TestEmotionLabels:
    def test_emotion_labels_count(self):
        assert len(EMOTION_LABELS) == 8

    def test_stress_key_emotions(self):
        assert "anxious" in STRESS_KEY_EMOTIONS
        assert "fearful" in STRESS_KEY_EMOTIONS
        assert "angry" in STRESS_KEY_EMOTIONS
        assert "sad" in STRESS_KEY_EMOTIONS

    def test_confidence_key_emotions(self):
        assert "happy" in CONFIDENCE_KEY_EMOTIONS
        assert "surprised" in CONFIDENCE_KEY_EMOTIONS
        assert "neutral" in CONFIDENCE_KEY_EMOTIONS


class TestGetVoiceEmotionEngine:
    def test_get_engine_default(self):
        engine = get_voice_emotion_engine()
        assert isinstance(engine, VoiceEmotionEngine)

    def test_get_engine_custom_params(self):
        engine = get_voice_emotion_engine(model_name="custom", device="cpu")
        assert engine.model_name == "custom"
        assert engine.device == "cpu"
