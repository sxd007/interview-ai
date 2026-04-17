import pytest
import numpy as np
from unittest.mock import Mock, patch, MagicMock

from src.inference.face.engine import (
    FaceAnalysisEngine,
    AU_INDICES,
    FACE_EMOTION_KEY_LANDMARKS,
    get_face_engine,
)


class TestFaceAnalysisEngineInit:
    def test_init_default_params(self):
        engine = FaceAnalysisEngine()
        assert engine.num_faces == 1
        assert engine.min_detection_confidence == 0.5
        assert engine.min_tracking_confidence == 0.5
        assert engine.model is None

    def test_init_custom_params(self):
        engine = FaceAnalysisEngine(
            num_faces=2,
            min_detection_confidence=0.7,
            min_tracking_confidence=0.8,
        )
        assert engine.num_faces == 2
        assert engine.min_detection_confidence == 0.7
        assert engine.min_tracking_confidence == 0.8

    def test_init_custom_model_path(self):
        engine = FaceAnalysisEngine(model_path="/nonexistent/path/model.task")
        assert engine.model_path is None


class TestFaceAnalysisEngineNormalize:
    def test_normalize_within_range(self):
        engine = FaceAnalysisEngine()
        result = engine._normalize(0.5, 0.0, 1.0)
        assert result == 0.5

    def test_normalize_below_min(self):
        engine = FaceAnalysisEngine()
        result = engine._normalize(-0.5, 0.0, 1.0)
        assert result == 0.0

    def test_normalize_above_max(self):
        engine = FaceAnalysisEngine()
        result = engine._normalize(1.5, 0.0, 1.0)
        assert result == 1.0

    def test_normalize_invalid_range(self):
        engine = FaceAnalysisEngine()
        result = engine._normalize(0.5, 1.0, 1.0)
        assert result == 0.0

    def test_normalize_exact_min(self):
        engine = FaceAnalysisEngine()
        result = engine._normalize(0.0, 0.0, 1.0)
        assert result == 0.0

    def test_normalize_exact_max(self):
        engine = FaceAnalysisEngine()
        result = engine._normalize(1.0, 0.0, 1.0)
        assert result == 1.0


class TestFaceAnalysisEngineComputeBbox:
    def test_compute_bbox_basic(self):
        engine = FaceAnalysisEngine()
        landmarks = np.array([
            [0.3, 0.3, 0.0],
            [0.7, 0.3, 0.0],
            [0.5, 0.7, 0.0],
        ])
        image_shape = (480, 640, 3)
        
        bbox = engine._compute_bbox(landmarks, image_shape)
        
        assert len(bbox) == 4
        assert all(isinstance(v, float) for v in bbox)

    def test_compute_bbox_with_margin(self):
        engine = FaceAnalysisEngine()
        landmarks = np.array([
            [0.4, 0.4, 0.0],
            [0.6, 0.4, 0.0],
            [0.5, 0.6, 0.0],
        ])
        image_shape = (480, 640, 3)
        
        bbox = engine._compute_bbox(landmarks, image_shape)
        
        x_min, y_min, x_max, y_max = bbox
        assert x_min >= 0
        assert y_min >= 0
        assert x_max <= 640
        assert y_max <= 480

    def test_compute_bbox_full_face(self):
        engine = FaceAnalysisEngine()
        landmarks = np.array([
            [0.1, 0.1, 0.0],
            [0.9, 0.1, 0.0],
            [0.1, 0.9, 0.0],
            [0.9, 0.9, 0.0],
        ])
        image_shape = (480, 640, 3)
        
        bbox = engine._compute_bbox(landmarks, image_shape)
        
        assert len(bbox) == 4


class TestFaceAnalysisEngineComputeActionUnits:
    def test_compute_action_units_basic(self):
        engine = FaceAnalysisEngine()
        landmarks = np.zeros((468, 3), dtype=np.float32)
        landmarks[:, 0] = 0.5
        landmarks[:, 1] = 0.5
        
        aus = engine._compute_action_units(landmarks)
        
        assert isinstance(aus, dict)
        assert "AU1" in aus
        assert "AU12" in aus

    def test_compute_action_units_values_in_range(self):
        engine = FaceAnalysisEngine()
        landmarks = np.random.rand(468, 3).astype(np.float32) * 0.2 + 0.4
        
        aus = engine._compute_action_units(landmarks)
        
        for au_name, au_value in aus.items():
            assert 0.0 <= au_value <= 1.0, f"{au_name} = {au_value}"


class TestFaceAnalysisEngineComputeEmotionFromAus:
    def test_compute_emotion_basic(self):
        engine = FaceAnalysisEngine()
        aus = {
            "AU1": 0.0,
            "AU2": 0.0,
            "AU4": 0.0,
            "AU6": 0.0,
            "AU7": 0.0,
            "AU9": 0.0,
            "AU10": 0.0,
            "AU12": 0.0,
            "AU15": 0.0,
            "AU17": 0.0,
            "AU20": 0.0,
        }
        
        scores = engine._compute_emotion_from_aus(aus)
        
        assert isinstance(scores, dict)
        assert "happy" in scores
        assert "sad" in scores
        assert "angry" in scores

    def test_compute_emotion_happy(self):
        engine = FaceAnalysisEngine()
        aus = {
            "AU6": 0.8,
            "AU12": 0.9,
        }
        
        scores = engine._compute_emotion_from_aus(aus)
        
        assert scores["happy"] > 0.3

    def test_compute_emotion_sad(self):
        engine = FaceAnalysisEngine()
        aus = {
            "AU4": 0.8,
            "AU15": 0.7,
            "AU17": 0.6,
        }
        
        scores = engine._compute_emotion_from_aus(aus)
        
        assert scores["sad"] > 0.2

    def test_compute_emotion_angry(self):
        engine = FaceAnalysisEngine()
        aus = {
            "AU4": 0.7,
            "AU9": 0.8,
            "AU17": 0.5,
        }
        
        scores = engine._compute_emotion_from_aus(aus)
        
        assert scores["angry"] > 0.2

    def test_compute_emotion_scores_sum_to_one(self):
        engine = FaceAnalysisEngine()
        aus = {
            "AU6": 0.5,
            "AU12": 0.6,
            "AU4": 0.3,
        }
        
        scores = engine._compute_emotion_from_aus(aus)
        
        total = sum(scores.values())
        assert total == pytest.approx(1.0, rel=0.01)


class TestFaceAnalysisEngineDetect:
    def test_detect_no_face(self):
        engine = FaceAnalysisEngine()
        engine.model = Mock()
        engine.model.detect.return_value = Mock(
            face_landmarks=[],
            face_blendshapes=[],
        )
        
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        result = engine.detect(frame)
        
        assert result is None

    def test_detect_with_face(self):
        engine = FaceAnalysisEngine()
        
        mock_landmark = Mock()
        mock_landmark.x = 0.5
        mock_landmark.y = 0.5
        mock_landmark.z = 0.0
        
        mock_result = Mock()
        mock_result.face_landmarks = [[mock_landmark] * 468]
        mock_result.face_blendshapes = []
        
        engine.model = Mock()
        engine.model.detect.return_value = mock_result
        
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        result = engine.detect(frame)
        
        assert result is not None
        assert "landmarks" in result
        assert "action_units" in result
        assert "emotion_scores" in result
        assert "bbox" in result


class TestFaceAnalysisEngineDetectFromVideo:
    def test_detect_from_video_file_not_found(self):
        engine = FaceAnalysisEngine()
        results = engine.detect_from_video("/nonexistent/video.mp4")
        assert results == []

    @patch("cv2.VideoCapture")
    def test_detect_from_video_empty(self, mock_cap_class):
        engine = FaceAnalysisEngine()
        
        mock_cap = Mock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.side_effect = [30.0, 0]
        mock_cap.read.return_value = (False, None)
        mock_cap_class.return_value = mock_cap
        
        results = engine.detect_from_video("/fake/video.mp4")
        assert results == []


class TestAUIndices:
    def test_au_indices_defined(self):
        assert "AU1_inner" in AU_INDICES
        assert "AU12_l" in AU_INDICES
        assert "AU25_l" in AU_INDICES

    def test_au_indices_values(self):
        assert isinstance(AU_INDICES["AU1_inner"], list)
        assert isinstance(AU_INDICES["AU12_l"], int)


class TestFaceEmotionKeyLandmarks:
    def test_key_landmarks_defined(self):
        assert "inner_brow" in FACE_EMOTION_KEY_LANDMARKS
        assert "eye_l" in FACE_EMOTION_KEY_LANDMARKS
        assert "mouth_outer_l" in FACE_EMOTION_KEY_LANDMARKS

    def test_key_landmarks_values(self):
        assert isinstance(FACE_EMOTION_KEY_LANDMARKS["inner_brow"], list)


class TestGetFaceEngine:
    def test_get_engine_default(self):
        engine = get_face_engine()
        assert isinstance(engine, FaceAnalysisEngine)

    def test_get_engine_custom_params(self):
        engine = get_face_engine(model_path="/custom/path", num_faces=2)
        assert engine.num_faces == 2
