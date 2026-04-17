import os
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
import tempfile
import logging

import numpy as np
import soundfile as sf
import torch

from src.utils.system_check import SystemChecker
from src.utils.pipeline_logger import get_pipeline_logger, pipeline_context

logger = logging.getLogger(__name__)
pipeline_log = get_pipeline_logger(__name__)


class AudioProcessor:
    def __init__(self, device: Optional[str] = None):
        self.device = self._get_device(device)
        self._check_ffmpeg()
    
    def _check_ffmpeg(self) -> None:
        """Check if ffmpeg is available."""
        available, message = SystemChecker.check_ffmpeg()
        if not available:
            raise RuntimeError(
                f"ffmpeg is required for audio processing.\n{message}"
            )

    def _get_device(self, device: Optional[str]) -> str:
        logger.info("[AudioProcessor] 音频处理器设备检测...")
        
        if device:
            logger.info(f"[AudioProcessor] 使用指定设备: {device}")
            return device
        
        if torch.cuda.is_available():
            device_str = "cuda"
            gpu_name = torch.cuda.get_device_name(0)
            logger.info(f"[AudioProcessor] ✓ 检测到CUDA GPU: {gpu_name}")
            logger.info(f"[AudioProcessor] ✓ 选择设备: {device_str}")
            return device_str
        elif torch.backends.mps.is_available():
            device_str = "mps"
            logger.info("[AudioProcessor] ✓ 检测到MPS设备 (Apple Silicon)")
            logger.info(f"[AudioProcessor] ✓ 选择设备: {device_str}")
            return device_str
        else:
            logger.info("[AudioProcessor] ✗ 未检测到GPU，使用CPU")
            logger.info("[AudioProcessor] ✓ 选择设备: cpu")
            return "cpu"

    def extract_audio(
        self,
        video_path: str,
        output_path: Optional[str] = None,
        sample_rate: int = 16000,
        channels: int = 1,
    ) -> Tuple[str, int]:
        with pipeline_context("audio_extract", "音频提取", device="cpu", logger=pipeline_log):
            if output_path is None:
                output_path = tempfile.mktemp(suffix=".wav")

            cmd = [
                "ffmpeg",
                "-i", video_path,
                "-vn",
                "-acodec", "pcm_s16le",
                "-ar", str(sample_rate),
                "-ac", str(channels),
                "-y",
                output_path,
            ]

            subprocess.run(cmd, check=True, capture_output=True)
            return output_path, sample_rate

    def denoise(
        self,
        audio_path: str,
        output_path: Optional[str] = None,
        model_name: str = "htdemucs_ft",
    ) -> str:
        import torch
        from demucs.pretrained import get_model
        from demucs.separate import apply_model

        with pipeline_context("audio_denoise", "音频降噪", device=self.device, logger=pipeline_log):
            if output_path is None:
                output_path = tempfile.mktemp(suffix=".wav")

            pipeline_log.log_model_load(f"demucs/{model_name}", self.device)
            
            model = get_model(model_name)
            device = torch.device(self.device)

            audio, sr = sf.read(audio_path, dtype="float32")
            if audio.ndim == 1:
                audio = np.stack([audio, audio], axis=-1)
            audio_tensor = torch.from_numpy(audio).float()
            if audio_tensor.shape[-1] == 2:
                audio_tensor = audio_tensor.T

            audio_tensor = audio_tensor.to(device)
            wav = audio_tensor.unsqueeze(0)

            with torch.no_grad():
                sources = apply_model(model, wav, shifts=0, split=True, overlap=0.25, progress=False, device=device)

            source_names = ["drums", "bass", "other", "vocals"]
            if sources.shape[2] > 0 and len(source_names) <= sources.shape[1]:
                vocals = sources[0, source_names.index("vocals"), :, :]
                vocals = vocals.cpu().numpy()
                if vocals.ndim == 2:
                    vocals = vocals.mean(axis=0)
            else:
                vocals = audio_tensor.cpu().numpy()
                if vocals.ndim == 2:
                    vocals = vocals.mean(axis=1)

            sf.write(output_path, vocals, sr)
            
            pipeline_log.log_model_unload(f"demucs/{model_name}", self.device)
            return output_path

    def load_audio(self, audio_path: str) -> Tuple[np.ndarray, int]:
        audio, sample_rate = sf.read(audio_path, dtype="float32")
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        return audio, sample_rate

    def save_audio(
        self,
        audio: np.ndarray,
        output_path: str,
        sample_rate: int = 16000,
    ) -> None:
        sf.write(output_path, audio, sample_rate)

    def get_duration(self, audio_path: str) -> float:
        audio, sr = self.load_audio(audio_path)
        return len(audio) / sr

    def resample(
        self,
        audio: np.ndarray,
        orig_sr: int,
        target_sr: int,
    ) -> np.ndarray:
        import librosa
        return librosa.resample(audio, orig_sr=orig_sr, target_sr=target_sr)


def get_audio_processor(device: Optional[str] = None) -> AudioProcessor:
    return AudioProcessor(device=device)
