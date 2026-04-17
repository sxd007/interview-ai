from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum
import numpy as np

import torch
import librosa

from src.utils.pipeline_logger import get_pipeline_logger, pipeline_context

pipeline_log = get_pipeline_logger(__name__)


class EmotionModelType(str, Enum):
    WAV2VEC2 = "wav2vec2"
    EMOTION2VEC = "emotion2vec"
    AUTO = "auto"


EMOTION_LABELS = [
    "neutral", "happy", "sad", "angry",
    "fearful", "disgusted", "surprised"
]

EMOTION_LABEL_MAP = {
    "NEUTRAL": "neutral",
    "HAPPY": "happy",
    "SAD": "sad",
    "ANGRY": "angry",
    "FEARFUL": "fearful",
    "DISGUSTED": "disgusted",
    "SURPRISED": "surprised",
}

STRESS_EMOTION_WEIGHTS = {
    "fearful": 1.0,
    "angry": 0.8,
    "sad": 0.6,
}

CONFIDENCE_EMOTION_WEIGHTS = {
    "happy": 0.6,
    "neutral": 0.4,
    "surprised": 0.2,
}


@dataclass
class EmotionResult:
    dominant_emotion: str
    confidence: float
    emotion_scores: Dict[str, float]
    stress_score: float
    confidence_score: float
    is_stress: bool
    arousal: float
    valence: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "dominant_emotion": self.dominant_emotion,
            "confidence": self.confidence,
            "emotion_scores": self.emotion_scores,
            "stress_score": self.stress_score,
            "confidence_score": self.confidence_score,
            "is_stress": self.is_stress,
            "arousal": self.arousal,
            "valence": self.valence,
        }


class EnhancedVoiceEmotionEngine:
    SUPPORTED_MODELS = {
        "sensevoice": "FunAudioLLM/SenseVoiceSmall",
    }
    
    EMOTION_VALENCE = {
        "happy": 0.8,
        "surprised": 0.3,
        "neutral": 0.0,
        "sad": -0.6,
        "angry": -0.5,
        "fearful": -0.7,
        "disgusted": -0.8,
    }
    
    EMOTION_AROUSAL = {
        "angry": 0.8,
        "fearful": 0.7,
        "surprised": 0.6,
        "happy": 0.4,
        "sad": 0.2,
        "disgusted": 0.3,
        "neutral": 0.0,
    }

    def __init__(
        self,
        model_type: str = "sensevoice",
        device: Optional[str] = None,
        cache_dir: Optional[str] = None,
        context_window: float = 0.5,
    ):
        self.model_type = model_type
        self.device = self._get_device(device)
        self.cache_dir = cache_dir
        self.context_window = context_window
        self.model = None
        self.processor = None

    def _get_device(self, device: Optional[str]) -> str:
        if device:
            return device
        if torch.cuda.is_available():
            return "cuda:0"
        elif torch.backends.mps.is_available():
            return "mps"
        return "cpu"

    def load(self) -> None:
        if self.model is not None:
            return

        try:
            from funasr import AutoModel
            model_name = self.SUPPORTED_MODELS.get(self.model_type, self.SUPPORTED_MODELS["sensevoice"])
            self.model = AutoModel(
                model=model_name,
                device=self.device,
                hub="hf",
                disable_update=True,
            )
            self.processor = True
        except Exception as e:
            pipeline_log.logger.error(f"[Emotion] 模型加载失败: {e}")
            import traceback
            traceback.print_exc()
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
        with pipeline_context("emotion", "情绪识别", device=self.device, logger=pipeline_log):
            if self.model is None:
                pipeline_log.log_model_load(
                    self.SUPPORTED_MODELS.get(self.model_type, "wav2vec2"),
                    self.device
                )
                self.load()

            if self.model is None:
                return self._fallback_analysis(audio_path)

            audio, sr = librosa.load(audio_path, sr=16000)
            result = self._predict_audio(audio, sr).to_dict()
            
            pipeline_log.log_stage_end(
                "emotion", "情绪识别", 0,
                extra_info={
                    "主要情绪": result.get("dominant_emotion", "unknown"),
                    "置信度": f"{result.get('confidence', 0):.2f}",
                    "压力分数": f"{result.get('stress_score', 0):.2f}"
                }
            )
            
            return result

    def predict_array(
        self, audio: np.ndarray, sample_rate: int = 16000
    ) -> Dict[str, Any]:
        if self.model is None:
            self.load()

        if self.model is None:
            return self._fallback_analysis_array(audio, sample_rate).to_dict()

        if sample_rate != 16000:
            audio = librosa.resample(audio, orig_sr=sample_rate, target_sr=16000)

        return self._predict_audio(audio, 16000).to_dict()

    def predict_with_context(
        self,
        audio: np.ndarray,
        sample_rate: int,
        start: float,
        end: float,
        full_audio: Optional[np.ndarray] = None,
    ) -> EmotionResult:
        if full_audio is not None and self.context_window > 0:
            context_samples = int(self.context_window * sample_rate)
            start_sample = max(0, int(start * sample_rate) - context_samples)
            end_sample = min(len(full_audio), int(end * sample_rate) + context_samples)
            extended_audio = full_audio[start_sample:end_sample]
        else:
            extended_audio = audio

        if self.model is None:
            self.load()

        if self.model is None:
            return self._fallback_analysis_array(audio, sample_rate)

        if sample_rate != 16000:
            extended_audio = librosa.resample(extended_audio, orig_sr=sample_rate, target_sr=16000)

        return self._predict_audio(extended_audio, 16000)

    def _predict_audio(self, audio: np.ndarray, sr: int) -> EmotionResult:
        try:
            from funasr.utils.postprocess_utils import rich_transcription_postprocess
            
            res = self.model.generate(
                input=audio,
                cache={},
                language="auto",
                use_itn=True,
                batch_size_s=60,
            )
            
            if not res or len(res) == 0:
                return self._fallback_analysis_array(audio, sr)
            
            text = res[0]["text"]
            
            emotion_label = self._extract_emotion(text)
            
            if emotion_label is None:
                return self._fallback_analysis_array(audio, sr)
            
            scores = self._create_emotion_scores(emotion_label)
            
            dominant = emotion_label
            confidence = scores[dominant]
            
            stress_score = self._compute_stress_advanced(scores)
            confidence_score = self._compute_confidence_advanced(scores)
            arousal = self._compute_arousal(scores)
            valence = self._compute_valence(scores)

            return EmotionResult(
                dominant_emotion=dominant,
                confidence=confidence,
                emotion_scores=scores,
                stress_score=stress_score,
                confidence_score=confidence_score,
                is_stress=stress_score > 0.4,
                arousal=arousal,
                valence=valence,
            )
        except Exception as e:
            pipeline_log.logger.error(f"[Emotion] 推理失败: {e}")
            return self._fallback_analysis_array(audio, sr)
    
    def _extract_emotion(self, text: str) -> Optional[str]:
        """从 SenseVoiceSmall 输出中提取情绪标签"""
        import re
        emotion_pattern = r'<\|([A-Z]+)\|>'
        matches = re.findall(emotion_pattern, text)
        
        for match in matches:
            if match in EMOTION_LABEL_MAP:
                return EMOTION_LABEL_MAP[match]
        
        return None
    
    def _create_emotion_scores(self, dominant_emotion: str) -> Dict[str, float]:
        """创建情绪分数字典"""
        scores = {label: 0.1 for label in EMOTION_LABELS}
        scores[dominant_emotion] = 0.7
        
        total = sum(scores.values())
        scores = {k: v / total for k, v in scores.items()}
        
        return scores

    def _fallback_analysis(self, audio_path: str) -> EmotionResult:
        audio, sr = librosa.load(audio_path, sr=16000)
        return self._fallback_analysis_array(audio, sr)

    def _fallback_analysis_array(
        self, audio: np.ndarray, sr: int
    ) -> EmotionResult:
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
            "disgusted": 0.0,
            "surprised": 0.1,
        }
        total = sum(scores.values())
        scores = {k: v / total for k, v in scores.items()}

        return EmotionResult(
            dominant_emotion="neutral" if not is_stress else "fearful",
            confidence=0.4,
            emotion_scores=scores,
            stress_score=float(pitch_variation * 2),
            confidence_score=0.5,
            is_stress=is_stress,
            arousal=0.3 if is_stress else 0.1,
            valence=-0.3 if is_stress else 0.0,
        )

    def predict_segments(
        self,
        audio: np.ndarray,
        sample_rate: int,
        segments: List[Dict[str, Any]],
        use_context: bool = True,
    ) -> List[Dict[str, Any]]:
        results = []
        for seg in segments:
            start_sample = int(seg["start"] * sample_rate)
            end_sample = int(seg["end"] * sample_rate)
            seg_audio = audio[start_sample:end_sample]
            
            if len(seg_audio) > 1600:
                if use_context:
                    result = self.predict_with_context(
                        seg_audio, sample_rate,
                        seg["start"], seg["end"],
                        full_audio=audio,
                    )
                else:
                    result = self._predict_audio(seg_audio, sample_rate)
            else:
                result = self._fallback_analysis_array(seg_audio, sample_rate)
            
            result_dict = result.to_dict()
            result_dict["start"] = seg["start"]
            result_dict["end"] = seg["end"]
            results.append(result_dict)
        return results

    def _compute_stress_advanced(self, scores: Dict[str, float]) -> float:
        weighted_sum = sum(
            scores.get(emotion, 0.0) * weight
            for emotion, weight in STRESS_EMOTION_WEIGHTS.items()
        )
        return min(1.0, weighted_sum)

    def _compute_confidence_advanced(self, scores: Dict[str, float]) -> float:
        weighted_sum = sum(
            scores.get(emotion, 0.0) * weight
            for emotion, weight in CONFIDENCE_EMOTION_WEIGHTS.items()
        )
        return min(1.0, weighted_sum)

    def _compute_arousal(self, scores: Dict[str, float]) -> float:
        return sum(
            scores.get(emotion, 0.0) * arousal
            for emotion, arousal in self.EMOTION_AROUSAL.items()
        )

    def _compute_valence(self, scores: Dict[str, float]) -> float:
        return sum(
            scores.get(emotion, 0.0) * valence
            for emotion, valence in self.EMOTION_VALENCE.items()
        )


def get_enhanced_voice_emotion_engine(
    model_type: str = "wav2vec2",
    device: Optional[str] = None,
    context_window: float = 0.5,
) -> EnhancedVoiceEmotionEngine:
    return EnhancedVoiceEmotionEngine(
        model_type=model_type,
        device=device,
        context_window=context_window,
    )
