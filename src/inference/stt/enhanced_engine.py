from typing import Optional, Dict, List, Any
from dataclasses import dataclass
import numpy as np

from src.inference.stt.engine import STTEngine


@dataclass
class STTConfig:
    min_silence_duration_ms: int = 300
    speech_pad_ms: int = 200
    min_speech_duration_ms: int = 200
    temperature: float = 0.2
    compression_ratio_threshold: float = 2.4
    log_prob_threshold: float = -1.0
    no_speech_threshold: float = 0.6
    beam_size: int = 5
    best_of: int = 5


class EnhancedSTTEngine(STTEngine):
    def __init__(
        self,
        model_size: str = "large-v3-turbo",
        device: str = "auto",
        compute_type: str = "auto",
        cache_dir: Optional[str] = None,
        engine_type: str = "faster-whisper",
        config: Optional[STTConfig] = None,
    ):
        super().__init__(model_size, device, compute_type, cache_dir, engine_type)
        self.config = config or STTConfig()

    def _transcribe_whisper(
        self,
        audio_path: str,
        language: str,
        task: str,
        vad_filter: bool,
        vad_parameters: Optional[Dict],
        word_timestamps: bool,
    ) -> Dict[str, Any]:
        vad_params = vad_parameters or {
            "min_silence_duration_ms": self.config.min_silence_duration_ms,
            "speech_pad_ms": self.config.speech_pad_ms,
            "min_speech_duration_ms": self.config.min_speech_duration_ms,
        }

        if self.model is None:
            self.load()

        segments, info = self.model.transcribe(
            audio_path,
            language=language,
            task=task,
            vad_filter=vad_filter,
            vad_parameters=vad_params,
            word_timestamps=word_timestamps,
            beam_size=self.config.beam_size,
            best_of=self.config.best_of,
            temperature=self.config.temperature,
            compression_ratio_threshold=self.config.compression_ratio_threshold,
            log_prob_threshold=self.config.log_prob_threshold,
            no_speech_threshold=self.config.no_speech_threshold,
        )

        result_segments = []
        full_text = []

        for segment in segments:
            text = segment.text.strip()
            if self._is_valid_text(text):
                seg_dict = {
                    "start": segment.start,
                    "end": segment.end,
                    "text": text,
                }
                if word_timestamps and segment.words:
                    seg_dict["words"] = [
                        {
                            "word": w.word.strip(),
                            "start": w.start,
                            "end": w.end,
                            "probability": w.probability,
                        }
                        for w in segment.words
                    ]
                result_segments.append(seg_dict)
                full_text.append(text)

        return {
            "text": "".join(full_text),
            "segments": result_segments,
            "language": info.language,
            "language_probability": info.language_probability,
            "duration": info.duration,
        }

    def _is_valid_text(self, text: str) -> bool:
        if not text:
            return False
        punctuation_only = set("。", "，", "、", "！", "？", "...", "…", ".", ",", "!")
        cleaned = text.strip()
        return cleaned in punctuation_only or len(cleaned) == 0

    def _post_process_segments(
        self,
        segments: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        return [s for s in segments if self._is_valid_text(s.get("text", ""))]

    def transcribe_with_retry(
        self,
        audio_path: str,
        language: str = "zh",
        max_retries: int = 3,
    ) -> Dict[str, Any]:
        for attempt in range(max_retries):
            try:
                result = self.transcribe(
                    audio_path,
                    language=language,
                    temperature=self.config.temperature + attempt * 0.1,
                )
                if result["segments"]:
                    return result
            except Exception:
                if attempt == max_retries - 1:
                    raise
        return {"text": "", "segments": [], "language": language, "duration": 0}


def get_enhanced_stt_engine(
    model_size: str = "large-v3-turbo",
    device: str = "auto",
    config: Optional[STTConfig] = None,
) -> EnhancedSTTEngine:
    return EnhancedSTTEngine(
        model_size=model_size,
        device=device,
        config=config,
    )
