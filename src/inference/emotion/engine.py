import os
from typing import Dict, Any, Optional, List
import numpy as np

import torch
import librosa


EMOTION_LABELS = [
    "neutral", "happy", "sad", "angry",
    "fearful", "disgust", "surprised", "anxious"
]

STRESS_KEY_EMOTIONS = {"anxious", "fearful", "angry", "sad"}
CONFIDENCE_KEY_EMOTIONS = {"happy", "surprised", "neutral"}


class VoiceEmotionEngine:
    def __init__(
        self,
        model_name: str = "ehcalabres/wav2vec2-lg-xlsr-53-chinese-zh-arctic-emotion-detection",
        device: Optional[str] = None,
        cache_dir: Optional[str] = None,
    ):
        self.model_name = model_name
        self.device = self._get_device(device)
        self.cache_dir = cache_dir
        self.model = None
        self.processor = None

    def _get_device(self, device: Optional[str]) -> str:
        if device:
            return device
        if torch.cuda.is_available():
            return "cuda"
        elif torch.backends.mps.is_available():
            return "mps"
        return "cpu"

    def load(self) -> None:
        if self.model is not None:
            return

        try:
            from transformers import Wav2Vec2ForSequenceClassification, Wav2Vec2Processor
            self.processor = Wav2Vec2Processor.from_pretrained(
                self.model_name, cache_dir=self.cache_dir
            )
            self.model = Wav2Vec2ForSequenceClassification.from_pretrained(
                self.model_name, cache_dir=self.cache_dir
            )
            self.model.to(self.device)
            self.model.eval()
        except Exception as e:
            self.model = None
            self.processor = None

    def unload(self) -> None:
        if self.model is not None:
            del self.model
            self.model = None
            self.processor = None
            if self.device in ("cuda", "mps"):
                torch.cuda.empty_cache() if self.device == "cuda" else torch.mps.empty_cache()

    def predict(self, audio_path: str) -> Dict[str, Any]:
        if self.model is None:
            self.load()

        if self.model is None:
            return self._fallback_analysis(audio_path)

        audio, sr = librosa.load(audio_path, sr=16000)
        return self._predict_audio(audio, sr)

    def predict_array(
        self, audio: np.ndarray, sample_rate: int = 16000
    ) -> Dict[str, Any]:
        if self.model is None:
            self.load()

        if self.model is None:
            return self._fallback_analysis_array(audio, sample_rate)

        if sample_rate != 16000:
            audio = librosa.resample(audio, orig_sr=sample_rate, target_sr=16000)

        return self._predict_audio(audio, 16000)

    def _predict_audio(self, audio: np.ndarray, sr: int) -> Dict[str, Any]:
        try:
            inputs = self.processor(
                audio, sampling_rate=sr, return_tensors="pt", padding=True
            )
            inputs = {k: v.to(self.device) for k, v in inputs.items()}

            with torch.no_grad():
                logits = self.model(**inputs).logits

            probs = torch.softmax(logits, dim=-1).cpu().numpy()[0]
            scores = {label: float(probs[i]) for i, label in enumerate(EMOTION_LABELS)}

            dominant = max(scores, key=scores.get)
            confidence = float(max(probs))

            stress_score = self._compute_stress(scores)
            confidence_score = self._compute_confidence(scores)

            return {
                "dominant_emotion": dominant,
                "confidence": confidence,
                "emotion_scores": scores,
                "stress_score": stress_score,
                "confidence_score": confidence_score,
                "is_stress": stress_score > 0.4,
            }
        except Exception:
            return self._fallback_analysis_array(audio, sr)

    def _fallback_analysis(self, audio_path: str) -> Dict[str, Any]:
        audio, sr = librosa.load(audio_path, sr=16000)
        return self._fallback_analysis_array(audio, sr)

    def _fallback_analysis_array(
        self, audio: np.ndarray, sr: int
    ) -> Dict[str, Any]:
        energy = np.sqrt(np.mean(audio**2))
        energy_normalized = min(float(energy) * 5, 1.0)

        try:
            f0, _, _ = librosa.pyin(
                audio,
                fmin=librosa.note_to_hz("C2"),
                fmax=librosa.note_to_hz("C7"),
                sr=sr,
            )
            f0 = f0[~np.isnan(f0)]
            pitch_variation = float(np.std(f0) / np.mean(f0)) if len(f0) > 0 and np.mean(f0) > 0 else 0.0
        except Exception:
            pitch_variation = 0.0

        is_stress = pitch_variation > 0.15 or energy_normalized < 0.3
        scores = {
            "neutral": 0.5 + (0.3 if not is_stress else 0.0),
            "happy": 0.1,
            "sad": 0.1,
            "angry": 0.1 + (0.2 if is_stress else 0.0),
            "fearful": 0.0 + (0.2 if is_stress else 0.0),
            "disgust": 0.0,
            "surprised": 0.1,
            "anxious": 0.0 + (0.2 if is_stress else 0.0),
        }
        total = sum(scores.values())
        scores = {k: v / total for k, v in scores.items()}

        return {
            "dominant_emotion": "neutral" if not is_stress else "anxious",
            "confidence": 0.4,
            "emotion_scores": scores,
            "stress_score": float(pitch_variation * 2),
            "confidence_score": 0.5,
            "is_stress": is_stress,
        }

    def predict_segments(
        self, audio: np.ndarray, sample_rate: int, segments: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        results = []
        for seg in segments:
            start_sample = int(seg["start"] * sample_rate)
            end_sample = int(seg["end"] * sample_rate)
            seg_audio = audio[start_sample:end_sample]
            if len(seg_audio) > 1600:
                result = self.predict_array(seg_audio, sample_rate)
            else:
                result = self._fallback_analysis_array(seg_audio, sample_rate)
            result["start"] = seg["start"]
            result["end"] = seg["end"]
            results.append(result)
        return results

    def _compute_stress(self, scores: Dict[str, float]) -> float:
        stress_emotions = ["anxious", "fearful", "angry", "sad"]
        return sum(scores.get(e, 0.0) for e in stress_emotions)

    def _compute_confidence(self, scores: Dict[str, float]) -> float:
        neutral = scores.get("neutral", 0.0)
        happy = scores.get("happy", 0.0)
        return float(neutral * 0.5 + happy * 0.5)


def get_voice_emotion_engine(
    model_name: Optional[str] = None, device: Optional[str] = None
) -> VoiceEmotionEngine:
    return VoiceEmotionEngine(model_name=model_name, device=device)
