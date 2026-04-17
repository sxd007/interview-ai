from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from collections import deque
import numpy as np


EMOTION_LABELS = [
    "neutral", "happy", "sad", "angry",
    "fearful", "disgust", "surprised", "anxious"
]


@dataclass
class FusedEmotionResult:
    dominant_emotion: str
    confidence: float
    emotion_scores: Dict[str, float]
    stress_score: float
    confidence_score: float
    is_stress: bool
    audio_contribution: float
    video_contribution: float
    prosody_contribution: float
    conflict_detected: bool
    conflict_details: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "dominant_emotion": self.dominant_emotion,
            "confidence": self.confidence,
            "emotion_scores": self.emotion_scores,
            "stress_score": self.stress_score,
            "confidence_score": self.confidence_score,
            "is_stress": self.is_stress,
            "audio_contribution": self.audio_contribution,
            "video_contribution": self.video_contribution,
            "prosody_contribution": self.prosody_contribution,
            "conflict_detected": self.conflict_detected,
            "conflict_details": self.conflict_details,
        }


class AdaptiveEmotionFusion:
    def __init__(
        self,
        audio_weight: float = 0.4,
        video_weight: float = 0.4,
        prosody_weight: float = 0.2,
        conflict_threshold: float = 0.3,
    ):
        self.base_weights = {
            "audio": audio_weight,
            "video": video_weight,
            "prosody": prosody_weight,
        }
        self.conflict_threshold = conflict_threshold

    def fuse(
        self,
        audio_emotion: Optional[Dict[str, float]],
        video_emotion: Optional[Dict[str, float]],
        prosody_features: Optional[Dict[str, Any]],
        audio_confidence: float = 0.5,
        video_confidence: float = 0.5,
    ) -> FusedEmotionResult:
        adjusted_weights = self._adjust_weights(
            audio_emotion, video_emotion, prosody_features,
            audio_confidence, video_confidence,
        )
        
        fused_scores = {}
        for emotion in EMOTION_LABELS:
            score = 0.0
            if audio_emotion:
                score += adjusted_weights["audio"] * audio_emotion.get(emotion, 0.0)
            if video_emotion:
                score += adjusted_weights["video"] * video_emotion.get(emotion, 0.0)
            if prosody_features:
                score += adjusted_weights["prosody"] * self._prosody_to_emotion(
                    prosody_features, emotion
                )
            fused_scores[emotion] = score
        
        total = sum(fused_scores.values())
        if total > 0:
            fused_scores = {k: v / total for k, v in fused_scores.items()}
        
        dominant = max(fused_scores, key=fused_scores.get)
        confidence = fused_scores[dominant]
        
        conflict, conflict_details = self._detect_conflict(
            audio_emotion, video_emotion
        )
        
        stress_score = self._compute_stress(fused_scores)
        confidence_score = self._compute_confidence(fused_scores)
        
        return FusedEmotionResult(
            dominant_emotion=dominant,
            confidence=confidence,
            emotion_scores=fused_scores,
            stress_score=stress_score,
            confidence_score=confidence_score,
            is_stress=stress_score > 0.4,
            audio_contribution=adjusted_weights["audio"],
            video_contribution=adjusted_weights["video"],
            prosody_contribution=adjusted_weights["prosody"],
            conflict_detected=conflict,
            conflict_details=conflict_details,
        )

    def _adjust_weights(
        self,
        audio_emotion: Optional[Dict[str, float]],
        video_emotion: Optional[Dict[str, float]],
        prosody_features: Optional[Dict[str, Any]],
        audio_confidence: float,
        video_confidence: float,
    ) -> Dict[str, float]:
        adjusted = {}
        total = 0.0
        
        if audio_emotion is not None:
            adjusted["audio"] = self.base_weights["audio"] * audio_confidence
            total += adjusted["audio"]
        else:
            adjusted["audio"] = 0.0
        
        if video_emotion is not None:
            adjusted["video"] = self.base_weights["video"] * video_confidence
            total += adjusted["video"]
        else:
            adjusted["video"] = 0.0
        
        if prosody_features is not None:
            adjusted["prosody"] = self.base_weights["prosody"]
            total += adjusted["prosody"]
        else:
            adjusted["prosody"] = 0.0
        
        if total > 0:
            adjusted = {k: v / total for k, v in adjusted.items()}
        
        return adjusted

    def _prosody_to_emotion(
        self, prosody: Dict[str, Any], emotion: str
    ) -> float:
        pitch_mean = prosody.get("pitch_mean", 150)
        pitch_std = prosody.get("pitch_std", 30)
        energy_mean = prosody.get("energy_mean", 0.5)
        speech_rate = prosody.get("speech_rate", 4.0)
        
        base_scores = {e: 0.1 for e in EMOTION_LABELS}
        
        if pitch_std > 50 or speech_rate > 250:
            base_scores["anxious"] = 0.3
            base_scores["angry"] = 0.2
        
        if pitch_mean < 120:
            base_scores["sad"] = 0.3
        
        if energy_mean > 0.7:
            base_scores["happy"] = 0.2
            base_scores["angry"] = 0.2
        
        if speech_rate < 150:
            base_scores["sad"] = 0.2
            base_scores["neutral"] = 0.3
        
        return base_scores.get(emotion, 0.1)

    def _detect_conflict(
        self,
        audio_emotion: Optional[Dict[str, float]],
        video_emotion: Optional[Dict[str, float]],
    ) -> Tuple[bool, str]:
        if audio_emotion is None or video_emotion is None:
            return False, ""
        
        audio_dominant = max(audio_emotion, key=audio_emotion.get)
        video_dominant = max(video_emotion, key=video_emotion.get)
        
        if audio_dominant != video_dominant:
            audio_score = audio_emotion[audio_dominant]
            video_score = video_emotion[video_dominant]
            
            if abs(audio_score - video_score) < self.conflict_threshold:
                return True, f"音频({audio_dominant})与视频({video_dominant})冲突"
        
        return False, ""

    def _compute_stress(self, scores: Dict[str, float]) -> float:
        stress_emotions = ["anxious", "fearful", "angry", "sad"]
        return sum(scores.get(e, 0.0) for e in stress_emotions)

    def _compute_confidence(self, scores: Dict[str, float]) -> float:
        return scores.get("neutral", 0.0) * 0.5 + scores.get("happy", 0.0) * 0.5


class TemporalEmotionSmoother:
    def __init__(self, window_size: int = 5):
        self.window_size = window_size
        self.history: deque = deque(maxlen=window_size)

    def smooth(self, emotion_scores: Dict[str, float]) -> Dict[str, float]:
        self.history.append(emotion_scores.copy())
        
        if len(self.history) == 0:
            return emotion_scores
        
        weights = np.exp(np.linspace(-1, 0, len(self.history)))
        weights = weights / weights.sum()
        
        smoothed = {}
        for emotion in EMOTION_LABELS:
            weighted_sum = sum(
                h.get(emotion, 0.0) * w
                for h, w in zip(self.history, weights)
            )
            smoothed[emotion] = weighted_sum
        
        return smoothed

    def reset(self):
        self.history.clear()


class SpeakerEmotionProfile:
    def __init__(
        self,
        speaker_id: str,
        history_size: int = 100,
        adaptation_rate: float = 0.01,
    ):
        self.speaker_id = speaker_id
        self.history_size = history_size
        self.adaptation_rate = adaptation_rate
        self.baseline: Dict[str, float] = {e: 0.5 for e in EMOTION_LABELS}
        self.history: deque = deque(maxlen=history_size)

    def update(self, emotion_scores: Dict[str, float]):
        self.history.append(emotion_scores.copy())
        
        for emotion in EMOTION_LABELS:
            current = emotion_scores.get(emotion, 0.0)
            self.baseline[emotion] = (
                (1 - self.adaptation_rate) * self.baseline[emotion] +
                self.adaptation_rate * current
            )

    def detect_deviation(
        self, current_scores: Dict[str, float]
    ) -> Dict[str, float]:
        deviations = {}
        for emotion in EMOTION_LABELS:
            baseline_val = self.baseline.get(emotion, 0.5)
            current_val = current_scores.get(emotion, 0.0)
            if baseline_val > 0.01:
                deviations[emotion] = (current_val - baseline_val) / baseline_val
            else:
                deviations[emotion] = current_val
        return deviations

    def detect_anomaly(
        self, current_scores: Dict[str, float], threshold: float = 0.5
    ) -> List[str]:
        deviations = self.detect_deviation(current_scores)
        anomalies = []
        for emotion, deviation in deviations.items():
            if deviation > threshold:
                anomalies.append(emotion)
        return anomalies

    def to_dict(self) -> Dict[str, Any]:
        return {
            "speaker_id": self.speaker_id,
            "baseline": self.baseline,
            "history_count": len(self.history),
        }


def create_emotion_fusion(
    audio_weight: float = 0.4,
    video_weight: float = 0.4,
    prosody_weight: float = 0.2,
) -> AdaptiveEmotionFusion:
    return AdaptiveEmotionFusion(
        audio_weight=audio_weight,
        video_weight=video_weight,
        prosody_weight=prosody_weight,
    )
