from pathlib import Path
from typing import Optional, List
import numpy as np

import torch
from pyannote.audio import Pipeline
import soundfile as sf


class VoicePrintExtractor:
    def __init__(
        self,
        diarization_model: str = "pyannote/speaker-diarization-3.1",
        auth_token: Optional[str] = None,
        device: Optional[str] = None,
        cache_dir: Optional[str] = None,
    ):
        self.diarization_model = diarization_model
        self.auth_token = auth_token or __import__("os").getenv("HF_TOKEN")
        self.device = self._get_device(device)
        self.cache_dir = cache_dir
        self._pipeline = None

    def _get_device(self, device: Optional[str]) -> str:
        if device:
            return device
        if torch.cuda.is_available():
            return "cuda"
        elif torch.backends.mps.is_available():
            return "mps"
        return "cpu"

    def load_pipeline(self) -> None:
        if self._pipeline is None:
            import os
            if self.cache_dir:
                import huggingface_hub
                huggingface_hub.constants.HF_HOME = self.cache_dir
            self._pipeline = Pipeline.from_pretrained(
                self.diarization_model,
                use_auth_token=self.auth_token,
            )
            if self.device != "cpu":
                self._pipeline = self._pipeline.to(torch.device(self.device))

    def unload(self) -> None:
        if self._pipeline is not None:
            del self._pipeline
            self._pipeline = None
            if self.device == "cuda":
                torch.cuda.empty_cache()
            elif self.device == "mps":
                torch.mps.empty_cache()

    def extract_embedding(
        self,
        audio_path: str,
        return_all_segments: bool = False,
    ) -> np.ndarray:
        self.load_pipeline()

        diarization = self._pipeline(audio_path, min_speakers=1, max_speakers=1)

        from pyannote.audio import Audio
        from pyannote.core import Segment

        audio = Audio()
        embeddings = []

        for segment, track, label in diarization.itertracks(yield_label=True):
            waveform, sample_rate = audio.crop(audio_path, Segment(segment.start, segment.end))
            embedding = self._pipeline.speaker_embedding(waveform)
            embeddings.append(embedding.squeeze().cpu().numpy())

        if not embeddings:
            waveform, sample_rate = audio.load(audio_path)
            embedding = self._pipeline.speaker_embedding(waveform)
            embeddings.append(embedding.squeeze().cpu().numpy())

        if return_all_segments:
            return np.array(embeddings)

        return np.mean(embeddings, axis=0)

    def extract_from_array(
        self,
        audio_array: np.ndarray,
        sample_rate: int = 16000,
    ) -> np.ndarray:
        import tempfile
        import soundfile as sf

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            sf.write(f.name, audio_array, sample_rate)
            embedding = self.extract_embedding(f.name)
            import os
            os.unlink(f.name)

        return embedding


def get_voice_print_extractor(
    auth_token: Optional[str] = None,
    device: Optional[str] = None,
) -> VoicePrintExtractor:
    return VoicePrintExtractor(auth_token=auth_token, device=device)