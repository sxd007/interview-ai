import os
from pathlib import Path
from typing import Optional, Dict, List, Any, Union
import numpy as np

import torch

from faster_whisper import WhisperModel

from src.inference.stt.sensevoice import SenseVoiceEngine


class STTEngine:
    ENGINE_FASTERWHISPER = "faster-whisper"
    ENGINE_SENSEVOICE = "sensevoice"

    def __init__(
        self,
        model_size: str = "large-v3-turbo",
        device: str = "auto",
        compute_type: str = "auto",
        cache_dir: Optional[str] = None,
        engine_type: str = "faster-whisper",
    ):
        self.model_size = model_size
        self.device = self._get_device(device)
        self.compute_type = self._get_compute_type(compute_type)
        self.cache_dir = cache_dir
        self.engine_type = engine_type
        self.model = None
        self._whisper_engine = None
        self._sensevoice_engine = None

    def _get_engine(self):
        if self.engine_type == self.ENGINE_SENSEVOICE:
            if self._sensevoice_engine is None:
                self._sensevoice_engine = SenseVoiceEngine(
                    model_name="FunAudioLLM/SenseVoiceSmall",
                    device=self.device,
                    cache_dir=self.cache_dir,
                )
                self._sensevoice_engine.load()
            return self._sensevoice_engine
        else:
            if self._whisper_engine is None:
                whisper_device = self.device
                whisper_compute = self.compute_type
                if whisper_device == "mps":
                    whisper_device = "cpu"
                    whisper_compute = "int8"
                self._whisper_engine = WhisperModel(
                    self.model_size,
                    device=whisper_device,
                    compute_type=whisper_compute,
                    download_root=self.cache_dir,
                )
            return self._whisper_engine

    def _get_device(self, device: str) -> str:
        if device == "auto":
            if torch.cuda.is_available():
                return "cuda"
            elif torch.backends.mps.is_available():
                return "mps"
            return "cpu"
        return device

    def _get_compute_type(self, compute_type: str) -> str:
        if compute_type == "auto":
            if self.device == "cuda":
                return "float16"
            elif self.device == "mps":
                return "int8"
            return "int8"
        return compute_type

    def load(self) -> None:
        if self.engine_type == self.ENGINE_SENSEVOICE:
            self._get_engine()
        else:
            if self.model is None:
                self.model = WhisperModel(
                    self.model_size,
                    device=self.device,
                    compute_type=self.compute_type,
                    download_root=self.cache_dir,
                )

    def unload(self) -> None:
        if self.engine_type == self.ENGINE_SENSEVOICE:
            if self._sensevoice_engine:
                self._sensevoice_engine.unload()
                self._sensevoice_engine = None
        else:
            if self.model is not None:
                del self.model
                self.model = None
                if self.device == "cuda":
                    torch.cuda.empty_cache()
                elif self.device == "mps":
                    torch.mps.empty_cache()

    def transcribe(
        self,
        audio_path: str,
        language: str = "zh",
        task: str = "transcribe",
        vad_filter: bool = True,
        vad_parameters: Optional[Dict] = None,
        word_timestamps: bool = True,
    ) -> Dict[str, Any]:
        if self.engine_type == self.ENGINE_SENSEVOICE:
            return self._transcribe_sensevoice(audio_path, language)
        else:
            return self._transcribe_whisper(
                audio_path, language, task, vad_filter, vad_parameters, word_timestamps
            )

    def _transcribe_sensevoice(
        self, audio_path: str, language: str
    ) -> Dict[str, Any]:
        engine = self._get_engine()
        result = engine.transcribe(audio_path, language=language, use_itn=True)
        return result

    def _transcribe_whisper(
        self,
        audio_path: str,
        language: str,
        task: str,
        vad_filter: bool,
        vad_parameters: Optional[Dict],
        word_timestamps: bool,
    ) -> Dict[str, Any]:
        if self.model is None:
            self.load()

        vad_params = vad_parameters or {
            "min_silence_duration_ms": 500,
            "speech_pad_ms": 400,
        }

        segments, info = self.model.transcribe(
            audio_path,
            language=language,
            task=task,
            vad_filter=vad_filter,
            vad_parameters=vad_params,
            word_timestamps=word_timestamps,
            beam_size=5,
            best_of=5,
            temperature=0.0,
        )

        result_segments = []
        full_text = []

        for segment in segments:
            seg_dict = {
                "start": segment.start,
                "end": segment.end,
                "text": segment.text.strip(),
            }
            if word_timestamps and segment.words:
                seg_dict["words"] = [
                    {
                        "word": word.word.strip(),
                        "start": word.start,
                        "end": word.end,
                        "probability": word.probability,
                    }
                    for word in segment.words
                ]
            result_segments.append(seg_dict)
            full_text.append(seg_dict["text"])

        return {
            "text": "".join(full_text),
            "segments": result_segments,
            "language": info.language,
            "language_probability": info.language_probability,
            "duration": info.duration,
        }

    def transcribe_array(
        self,
        audio_array: np.ndarray,
        sample_rate: int = 16000,
        language: str = "zh",
        **kwargs,
    ) -> Dict[str, Any]:
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            import soundfile as sf
            sf.write(f.name, audio_array, sample_rate)
            result = self.transcribe(f.name, language=language, **kwargs)
            os.unlink(f.name)

        return result


def get_stt_engine(
    model_size: str = "large-v3-turbo",
    device: str = "auto",
    cache_dir: Optional[str] = None,
) -> STTEngine:
    return STTEngine(
        model_size=model_size,
        device=device,
        cache_dir=cache_dir,
    )
