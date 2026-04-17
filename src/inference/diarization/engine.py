import os
import logging
from pathlib import Path
from typing import Optional, Dict, List, Any, Tuple
import numpy as np

import torch

import huggingface_hub
_original_hf_hub_download = huggingface_hub.hf_hub_download

def _patched_hf_hub_download(*args, **kwargs):
    if 'use_auth_token' in kwargs:
        kwargs['token'] = kwargs.pop('use_auth_token')
    return _original_hf_hub_download(*args, **kwargs)

huggingface_hub.hf_hub_download = _patched_hf_hub_download

from pyannote.audio import Pipeline

logger = logging.getLogger(__name__)


class DiarizationEngine:
    def __init__(
        self,
        model_name: str = "pyannote/speaker-diarization-3.1",
        auth_token: Optional[str] = None,
        device: Optional[str] = None,
        cache_dir: Optional[str] = None,
    ):
        self.model_name = model_name
        self.auth_token = auth_token or os.getenv("HF_TOKEN")
        self.device = self._get_device(device)
        self.cache_dir = cache_dir
        self.pipeline = None

    def _get_device(self, device: Optional[str]) -> str:
        logger.info("[Diarization] 说话人分离引擎设备检测...")
        
        if device:
            logger.info(f"[Diarization] 使用指定设备: {device}")
            return device
        
        if torch.cuda.is_available():
            device_str = "cuda"
            gpu_name = torch.cuda.get_device_name(0)
            logger.info(f"[Diarization] ✓ 检测到CUDA GPU: {gpu_name}")
            logger.info(f"[Diarization] ✓ 选择设备: {device_str}")
            return device_str
        elif torch.backends.mps.is_available():
            device_str = "mps"
            logger.info("[Diarization] ✓ 检测到MPS设备 (Apple Silicon)")
            logger.info(f"[Diarization] ✓ 选择设备: {device_str}")
            return device_str
        else:
            logger.info("[Diarization] ✗ 未检测到GPU，使用CPU")
            logger.info("[Diarization] ✓ 选择设备: cpu")
            return "cpu"

    def load(self) -> None:
        if self.pipeline is None:
            logger.info(f"[Diarization] 开始加载说话人分离模型...")
            logger.info(f"[Diarization] 模型名称: {self.model_name}")
            logger.info(f"[Diarization] 目标设备: {self.device}")
            
            try:
                if self.cache_dir:
                    import huggingface_hub
                    huggingface_hub.constants.HF_HOME = self.cache_dir
                    logger.info(f"[Diarization] 缓存目录: {self.cache_dir}")
                
                if self.auth_token:
                    os.environ["HF_TOKEN"] = self.auth_token
                    logger.info("[Diarization] ✓ HF_TOKEN已设置")
                
                logger.info("[Diarization] 加载pyannote Pipeline...")
                self.pipeline = Pipeline.from_pretrained(
                    self.model_name,
                )
                logger.info("[Diarization] ✓ Pipeline加载完成")
                
            except Exception as e:
                logger.error(f"[Diarization] ✗ Pipeline加载失败: {e}")
                if "401" in str(e) or "Unauthorized" in str(e) or "authentication" in str(e).lower():
                    raise RuntimeError(
                        "pyannote.audio authentication failed. "
                        "Please set a valid HF_TOKEN in your .env file. "
                        "Get a token at: https://huggingface.co/settings/tokens"
                    )
                raise
            
            if self.device != "cpu":
                logger.info(f"[Diarization] 将Pipeline移动到设备: {self.device}")
                self.pipeline = self.pipeline.to(torch.device(self.device))
                logger.info(f"[Diarization] ✓ Pipeline已移动到: {self.device}")
            else:
                logger.info("[Diarization] 使用CPU设备，无需移动Pipeline")
            
            logger.info(f"[Diarization] ✓ 模型加载完成，设备: {self.device}")

    def unload(self) -> None:
        if self.pipeline is not None:
            del self.pipeline
            self.pipeline = None
            if self.device == "cuda":
                torch.cuda.empty_cache()
            elif self.device == "mps":
                torch.mps.empty_cache()

    def diarize(
        self,
        audio_path: str,
        min_speakers: Optional[int] = None,
        max_speakers: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        try:
            if self.pipeline is None:
                self.load()
        except RuntimeError:
            raise
        except Exception as e:
            raise RuntimeError(f"Failed to load diarization model: {e}")

        diarization = self.pipeline(
            audio_path,
            min_speakers=min_speakers,
            max_speakers=max_speakers,
        )

        results = []
        for segment, track, label in diarization.itertracks(yield_label=True):
            results.append({
                "start": segment.start,
                "end": segment.end,
                "speaker": label,
                "track": track,
            })

        return self._merge_segments(results)

    def diarize_array(
        self,
        audio_array: np.ndarray,
        sample_rate: int = 16000,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        import tempfile
        import soundfile as sf

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            sf.write(f.name, audio_array, sample_rate)
            result = self.diarize(f.name, **kwargs)
            os.unlink(f.name)

        return result

    def _merge_segments(
        self,
        segments: List[Dict[str, Any]],
        gap_threshold: float = 0.5,
        same_speaker_threshold: float = 0.1,
    ) -> List[Dict[str, Any]]:
        if not segments:
            return []

        merged = []
        current = segments[0].copy()

        for seg in segments[1:]:
            is_same_speaker = seg["speaker"] == current["speaker"]
            gap = seg["start"] - current["end"]

            if is_same_speaker and gap < gap_threshold:
                current["end"] = seg["end"]
            else:
                merged.append(current)
                current = seg.copy()

        merged.append(current)
        return merged

    def get_speaker_count(self, segments: List[Dict[str, Any]]) -> int:
        speakers = set(seg["speaker"] for seg in segments)
        return len(speakers)


def get_diarization_engine(
    auth_token: Optional[str] = None,
    device: Optional[str] = None,
) -> DiarizationEngine:
    return DiarizationEngine(
        auth_token=auth_token,
        device=device,
    )
