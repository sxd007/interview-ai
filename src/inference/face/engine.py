import os
from typing import Dict, Any, Optional, List, Tuple
import numpy as np

import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

from src.utils.pipeline_logger import get_pipeline_logger, pipeline_context

pipeline_log = get_pipeline_logger(__name__)


FACE_LANDMARKS = list(range(468))


AU_INDICES = {
    "AU1_inner": [33, 133],
    "AU1_outer_l": 133,
    "AU1_outer_r": 362,
    "AU2_inner": [33, 133],
    "AU2_outer_l": 133,
    "AU2_outer_r": 362,
    "AU4_inner": [33, 133],
    "AU4_l": 160,
    "AU4_r": 384,
    "AU6_l": 50,
    "AU6_r": 280,
    "AU7_l": 21,
    "AU7_r": 251,
    "AU9_inner": [33, 133],
    "AU9_l": 123,
    "AU9_r": 352,
    "AU10_l": 13,
    "AU10_r": 302,
    "AU12_l": 61,
    "AU12_r": 291,
    "AU14_l": 43,
    "AU14_r": 269,
    "AU15_l": 37,
    "AU15_r": 267,
    "AU17_l": 50,
    "AU17_r": 280,
    "AU20_l": 62,
    "AU20_r": 292,
    "AU23_l": 73,
    "AU23_r": 303,
    "AU25_l": 61,
    "AU25_r": 291,
    "AU26_l": 50,
    "AU26_r": 280,
    "AU28_l": 13,
    "AU28_r": 302,
    "AU43_l": 33,
    "AU43_r": 263,
}

FACE_EMOTION_KEY_LANDMARKS = {
    "inner_brow": [107, 336],
    "outer_brow_l": [336, 296, 334, 293, 300],
    "outer_brow_r": [107, 151, 117, 118, 119],
    "eye_l": [33, 160, 158, 133, 153, 144],
    "eye_r": [362, 385, 387, 263, 373, 380],
    "nose_bridge": [168, 6],
    "nose_tip": [1, 2, 98, 327, 4],
    "mouth_outer_l": [61, 291, 62, 292, 306, 308, 409, 415],
    "mouth_outer_r": [61, 291, 62, 292, 306, 308, 409, 415],
    "mouth_inner": [78, 80, 81, 82, 13, 312, 311, 310, 415, 308],
}


class FaceAnalysisEngine:
    DEFAULT_MODEL_PATH = os.path.expanduser("~/.cache/mediapipe/face_landmarker.task")
    MODEL_DOWNLOAD_URL = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"

    def __init__(
        self,
        model_path: Optional[str] = None,
        num_faces: int = 1,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
        auto_download: bool = True,
    ):
        self.num_faces = num_faces
        self.min_detection_confidence = min_detection_confidence
        self.min_tracking_confidence = min_tracking_confidence
        self.model_path = model_path or self.DEFAULT_MODEL_PATH
        self.auto_download = auto_download
        
        if self.model_path and not os.path.exists(self.model_path):
            if self.auto_download:
                self._download_model()
            else:
                self.model_path = None
        self.model = None
    
    def _download_model(self):
        import urllib.request
        import logging
        
        logger = logging.getLogger(__name__)
        logger.info(f"MediaPipe model not found at {self.model_path}")
        logger.info(f"Downloading from {self.MODEL_DOWNLOAD_URL}...")
        
        try:
            os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
            urllib.request.urlretrieve(self.MODEL_DOWNLOAD_URL, self.model_path)
            logger.info(f"Successfully downloaded MediaPipe model to {self.model_path}")
        except Exception as e:
            logger.error(f"Failed to download MediaPipe model: {e}")
            self.model_path = None
            raise RuntimeError(
                f"Failed to download MediaPipe face_landmarker.task model. "
                f"Please download manually from:\n  {self.MODEL_DOWNLOAD_URL}\n"
                f"And save it to:\n  {self.model_path}\n"
                f"Or run: python scripts/download_models.py"
            ) from e

    def _ensure_model(self):
        if self.model is None:
            if not self.model_path:
                raise RuntimeError(
                    "MediaPipe face_landmarker.task model not found!\n"
                    "The model file is required for face analysis.\n\n"
                    "To fix this issue:\n"
                    "1. Run: python scripts/download_models.py\n"
                    "2. Or download manually from:\n"
                    f"   {self.MODEL_DOWNLOAD_URL}\n"
                    f"   And save to: {self.DEFAULT_MODEL_PATH}\n"
                    "3. Or set auto_download=True when creating FaceAnalysisEngine"
                )
            
            base_options = python.BaseOptions(model_asset_path=self.model_path)
            options = vision.FaceLandmarkerOptions(
                base_options=base_options,
                num_faces=self.num_faces,
                min_face_detection_confidence=self.min_detection_confidence,
                min_face_presence_confidence=self.min_tracking_confidence,
                min_tracking_confidence=self.min_tracking_confidence,
                output_face_blendshapes=False,
                output_facial_transformation_matrixes=False,
            )
            self.model = vision.FaceLandmarker.create_from_options(options)

    def detect(self, frame: np.ndarray) -> Optional[Dict[str, Any]]:
        self._ensure_model()
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame)
        result = self.model.detect(image)

        if not result.face_landmarks or len(result.face_landmarks) == 0:
            return None

        face_landmarks = result.face_landmarks[0]
        blendshapes = result.face_blendshapes[0] if result.face_blendshapes else []

        landmarks = np.array([
            [lm.x, lm.y, lm.z] for lm in face_landmarks
        ])

        action_units = self._compute_action_units(landmarks)
        emotion_scores = self._compute_emotion_from_aus(action_units)

        bbox = self._compute_bbox(landmarks, frame.shape)

        return {
            "landmarks": landmarks.tolist(),
            "action_units": action_units,
            "emotion_scores": emotion_scores,
            "bbox": bbox,
            "blendshapes": {bs.name: float(bs.score) for bs in blendshapes},
        }

    def detect_from_video(
        self, video_path: str, sample_rate: float = 2.0
    ) -> List[Dict[str, Any]]:
        with pipeline_context("face_analysis", "人脸分析", device="cpu", logger=pipeline_log):
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                return []

            fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            interval = max(1, int(fps / sample_rate))

            results = []
            frame_idx = 0

            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                if frame_idx % interval == 0:
                    timestamp = frame_idx / fps
                    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    face_data = self.detect(rgb_frame)
                    if face_data:
                        face_data["timestamp"] = timestamp
                        face_data["frame_idx"] = frame_idx
                        results.append(face_data)

                frame_idx += 1

            cap.release()
            
            pipeline_log.log_stage_end(
                "face_analysis", "人脸分析", 0,
                extra_info={
                    "检测到的帧数": len(results),
                    "采样率": f"{sample_rate} fps"
                }
            )
            
            return results

    def _compute_action_units(
        self, landmarks: np.ndarray
    ) -> Dict[str, float]:
        aus = {}

        brow_inner_l = landmarks[33]
        brow_inner_r = landmarks[263]
        brow_outer_l = landmarks[133]
        brow_outer_r = landmarks[362]
        brow_mid_l = landmarks[55]
        brow_mid_r = landmarks[285]

        brow_height_l = brow_mid_l[1] - brow_inner_l[1]
        brow_height_r = brow_mid_r[1] - brow_inner_r[1]
        brow_inner_dist = abs(brow_inner_l[0] - brow_inner_r[0])
        aus["AU1"] = self._normalize(
            max(0, brow_height_l + brow_height_r) / brow_inner_dist, 0, 0.08
        )

        aus["AU2"] = self._normalize(
            abs(brow_outer_l[0] - brow_inner_l[0]) + abs(brow_outer_r[0] - brow_inner_r[0]),
            0, 0.15
        )

        cheek_l = landmarks[50]
        cheek_r = landmarks[280]
        mouth_l = landmarks[61]
        mouth_r = landmarks[291]
        nose_tip = landmarks[4]
        nose_bridge = landmarks[168]

        au4_l_dist = abs(cheek_l[0] - landmarks[33][0])
        au4_r_dist = abs(cheek_r[0] - landmarks[263][0])
        aus["AU4"] = self._normalize(
            (au4_l_dist + au4_r_dist) / 2, 0, 0.1
        )

        eye_l_center = (landmarks[33] + landmarks[133]) / 2
        eye_r_center = (landmarks[362] + landmarks[263]) / 2
        eye_open_l = abs(landmarks[159][1] - landmarks[145][1])
        eye_open_r = abs(landmarks[386][1] - landmarks[374][1])
        eye_width_l = abs(landmarks[133][0] - landmarks[33][0])
        eye_width_r = abs(landmarks[362][0] - landmarks[263][0])
        aus["AU6"] = self._normalize(
            (eye_open_l + eye_open_r) / 2, 0, 0.08
        )
        aus["AU7"] = self._normalize(
            (eye_width_l + eye_width_r) / 2, 0, 0.15
        )

        nose_lift = landmarks[4][1] - landmarks[6][1]
        aus["AU9"] = self._normalize(max(0, nose_lift), 0, 0.06)

        mouth_open = abs(landmarks[13][1] - landmarks[14][1])
        aus["AU10"] = self._normalize(mouth_open, 0, 0.08)

        mouth_corner_l = landmarks[61]
        mouth_corner_r = landmarks[291]
        mouth_width = abs(mouth_corner_r[0] - mouth_corner_l[0])
        aus["AU12"] = self._normalize(
            (mouth_corner_r[1] - mouth_corner_l[1] + 0.01) / (mouth_width + 0.01),
            0.2, 0.5
        )
        aus["AU15"] = self._normalize(
            max(0, -(mouth_corner_r[1] - mouth_corner_l[1])) / (mouth_width + 0.01),
            0, 0.05
        )

        aus["AU20"] = self._normalize(
            abs(landmarks[62][0] - landmarks[292][0]) / mouth_width, 0.8, 1.2
        )

        chin_lift = landmarks[152][1] - landmarks[6][1]
        aus["AU17"] = self._normalize(max(0, chin_lift), 0.1, 0.15)

        mouth_vert = abs(landmarks[13][1] - landmarks[14][1])
        aus["AU25"] = self._normalize(mouth_vert, 0, 0.1)
        aus["AU26"] = self._normalize(mouth_vert, 0, 0.08)

        return aus

    def _compute_emotion_from_aus(
        self, aus: Dict[str, float]
    ) -> Dict[str, float]:
        scores = {
            "neutral": 0.3,
            "happy": 0.0,
            "sad": 0.0,
            "angry": 0.0,
            "fearful": 0.0,
            "disgust": 0.0,
            "surprised": 0.0,
        }

        au6 = aus.get("AU6", 0)
        au12 = aus.get("AU12", 0)
        au17 = aus.get("AU17", 0)

        scores["happy"] = min(1.0, au6 * 3 + au12 * 2)
        scores["neutral"] = max(0.0, 0.3 - scores["happy"] * 0.5)

        au4 = aus.get("AU4", 0)
        au15 = aus.get("AU15", 0)
        au17_sad = au17
        scores["sad"] = min(1.0, au4 * 2 + au15 * 3 + au17_sad * 2)
        scores["neutral"] = max(0.0, scores["neutral"] - scores["sad"] * 0.3)

        au4_angry = au4
        au9 = aus.get("AU9", 0)
        au17_angry = au17
        scores["angry"] = min(1.0, au4_angry * 2 + au9 * 3 + au17_angry * 2)

        au1 = aus.get("AU1", 0)
        au2 = aus.get("AU2", 0)
        au5 = aus.get("AU7", 0)
        scores["fearful"] = min(1.0, au1 * 2 + au2 * 2 + au5 * 2)
        scores["surprised"] = min(
            1.0, au1 * 2 + au2 * 2 + au5 + au6
        ) if au6 > 0.3 else 0.0

        au10 = aus.get("AU10", 0)
        au9_disgust = au9
        scores["disgust"] = min(1.0, au10 * 2 + au9_disgust * 2)

        au20 = aus.get("AU20", 0)
        if au20 > 0.8 and scores["happy"] < 0.2:
            scores["fearful"] += 0.1

        total = sum(scores.values())
        if total > 0:
            scores = {k: v / total for k, v in scores.items()}

        return scores

    def _compute_bbox(
        self, landmarks: np.ndarray, image_shape: Tuple[int, ...]
    ) -> List[float]:
        h, w = image_shape[:2]
        x_coords = landmarks[:, 0]
        y_coords = landmarks[:, 1]
        x_min, x_max = x_coords.min(), x_coords.max()
        y_min, y_max = y_coords.min(), y_coords.max()
        margin = 0.1
        x_margin = (x_max - x_min) * margin
        y_margin = (y_max - y_min) * margin
        return [
            float(max(0, (x_min - x_margin) * w)),
            float(max(0, (y_min - y_margin) * h)),
            float(min(1, (x_max + x_margin) * w)),
            float(min(1, (y_max + y_margin) * h)),
        ]

    def _normalize(
        self, value: float, min_val: float, max_val: float
    ) -> float:
        if max_val <= min_val:
            return 0.0
        return min(1.0, max(0.0, (value - min_val) / (max_val - min_val)))


def get_face_engine(
    model_path: Optional[str] = None, 
    num_faces: int = 1,
    auto_download: bool = True,
) -> FaceAnalysisEngine:
    return FaceAnalysisEngine(
        model_path=model_path, 
        num_faces=num_faces,
        auto_download=auto_download,
    )
