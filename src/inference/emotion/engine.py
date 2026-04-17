import os
import logging
from typing import Dict, Any, Optional, List
import numpy as np

import torch
import librosa

logger = logging.getLogger(__name__)


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

STRESS_KEY_EMOTIONS = {"fearful", "angry", "sad"}
CONFIDENCE_KEY_EMOTIONS = {"happy", "surprised", "neutral"}


class VoiceEmotionEngine:
    def __init__(
        self,
        model_name: str = "FunAudioLLM/SenseVoiceSmall",
        device: Optional[str] = None,
        cache_dir: Optional[str] = None,
    ):
        self.model_name = model_name
        self.device = self._get_device(device)
        self.cache_dir = cache_dir
        self.model = None
        self.processor = None

    def _get_device(self, device: Optional[str]) -> str:
        logger.info("[Emotion] 情绪识别引擎设备检测...")
        
        if device:
            logger.info(f"[Emotion] 使用指定设备: {device}")
            return device
        
        if torch.cuda.is_available():
            device_str = "cuda:0"
            gpu_name = torch.cuda.get_device_name(0)
            logger.info(f"[Emotion] ✓ 检测到CUDA GPU: {gpu_name}")
            logger.info(f"[Emotion] ✓ 选择设备: {device_str}")
            return device_str
        elif torch.backends.mps.is_available():
            device_str = "mps"
            logger.info("[Emotion] ✓ 检测到MPS设备 (Apple Silicon)")
            logger.info(f"[Emotion] ✓ 选择设备: {device_str}")
            return device_str
        else:
            logger.info("[Emotion] ✗ 未检测到GPU，使用CPU")
            logger.info("[Emotion] ✓ 选择设备: cpu")
            return "cpu"

    def load(self) -> None:
        if self.model is not None:
            logger.info("[Emotion] 模型已加载，跳过重复加载")
            return

        logger.info(f"[Emotion] 开始加载情绪识别模型...")
        logger.info(f"[Emotion] 模型名称: {self.model_name}")
        logger.info(f"[Emotion] 目标设备: {self.device}")

        try:
            from funasr import AutoModel
            
            logger.info("[Emotion] 加载 SenseVoiceSmall 模型...")
            self.model = AutoModel(
                model=self.model_name,
                device=self.device,
                hub="hf",
                disable_update=True,
            )
            self.processor = True  # 标记为已加载
            
            logger.info(f"[Emotion] ✓ 模型加载完成，设备: {self.device}")
            
        except Exception as e:
            logger.error(f"[Emotion] ✗ 模型加载失败: {e}")
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
        if self.model is None:
            self.load()

        if self.model is None:
            return self._fallback_analysis(audio_path)

        audio, sr = librosa.load(audio_path, sr=16000)
        return self._predict_audio(audio, sr, audio_path)

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

    def _predict_audio(self, audio: np.ndarray, sr: int, audio_path: Optional[str] = None) -> Dict[str, Any]:
        try:
            from funasr.utils.postprocess_utils import rich_transcription_postprocess
            
            res = self.model.generate(
                input=audio if audio_path is None else audio_path,
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
        except Exception as e:
            logger.error(f"[Emotion] 推理失败: {e}")
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
            "disgusted": 0.0,
            "surprised": 0.1,
        }
        total = sum(scores.values())
        scores = {k: v / total for k, v in scores.items()}

        return {
            "dominant_emotion": "neutral" if not is_stress else "fearful",
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
        stress_emotions = ["fearful", "angry", "sad"]
        return sum(scores.get(e, 0.0) for e in stress_emotions)

    def _compute_confidence(self, scores: Dict[str, float]) -> float:
        neutral = scores.get("neutral", 0.0)
        happy = scores.get("happy", 0.0)
        return float(neutral * 0.5 + happy * 0.5)


def get_voice_emotion_engine(
    model_name: Optional[str] = None, device: Optional[str] = None
) -> VoiceEmotionEngine:
    return VoiceEmotionEngine(model_name=model_name, device=device)
