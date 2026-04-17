from typing import Optional, Dict, List, Any, Tuple
from dataclasses import dataclass
import numpy as np

import torch

from src.inference.diarization.engine import DiarizationEngine
from src.utils.pipeline_logger import get_pipeline_logger, pipeline_context

pipeline_log = get_pipeline_logger(__name__)


@dataclass
class DiarizationConfig:
    segmentation_onset: float = 0.3
    segmentation_duration: float = 5.0
    min_duration_off: float = 0.3
    min_duration_on: float = 0.3
    clustering_threshold: float = 0.715
    min_cluster_size: int = 15
    gap_threshold: float = 0.5
    min_segment_duration: float = 0.5


class EnhancedDiarizationEngine(DiarizationEngine):
    def __init__(
        self,
        model_name: str = "pyannote/speaker-diarization-3.1",
        auth_token: Optional[str] = None,
        device: Optional[str] = None,
        cache_dir: Optional[str] = None,
        config: Optional[DiarizationConfig] = None,
    ):
        super().__init__(model_name, auth_token, device, cache_dir)
        self.config = config or DiarizationConfig()
        self._speaker_embeddings: Dict[str, np.ndarray] = {}

    def load(self) -> None:
        if self.pipeline is None:
            super().load()
            self._apply_config()

    def _apply_config(self) -> None:
        if self.pipeline is None:
            return
        
        try:
            params = self.pipeline.parameters(instantiated=False)
            
            if hasattr(params, 'segmentation') and hasattr(params.segmentation, 'onset'):
                params.segmentation.onset.value = self.config.segmentation_onset
            
            if hasattr(params, 'segmentation') and hasattr(params.segmentation, 'duration'):
                params.segmentation.duration.value = self.config.segmentation_duration
            
            if hasattr(params, 'clustering') and hasattr(params.clustering, 'threshold'):
                params.clustering.threshold.value = self.config.clustering_threshold
            
            if hasattr(params, 'clustering') and hasattr(params.clustering, 'min_cluster_size'):
                params.clustering.min_cluster_size.value = self.config.min_cluster_size
            
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Could not apply all diarization parameters: {e}")

    def diarize(
        self,
        audio_path: str,
        min_speakers: Optional[int] = None,
        max_speakers: Optional[int] = None,
        short_segment_mode: bool = True,
    ) -> List[Dict[str, Any]]:
        with pipeline_context("diarization", "人声识别", device=self.device, logger=pipeline_log):
            try:
                if self.pipeline is None:
                    pipeline_log.log_model_load(self.model_name, self.device)
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

            merged_results = self._merge_segments_enhanced(results)
            
            unique_speakers = len(set(r["speaker"] for r in merged_results))
            pipeline_log.log_stage_end(
                "diarization", "人声识别", 0,
                extra_info={
                    "识别到的说话人数量": unique_speakers,
                    "音频片段数量": len(merged_results)
                }
            )
            
            return merged_results

    def _merge_segments_enhanced(
        self,
        segments: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        if not segments:
            return []

        merged = []
        current = segments[0].copy()

        for seg in segments[1:]:
            is_same_speaker = seg["speaker"] == current["speaker"]
            gap = seg["start"] - current["end"]

            if is_same_speaker and gap < self.config.gap_threshold:
                current["end"] = seg["end"]
            else:
                if self._is_valid_segment(current):
                    merged.append(current)
                current = seg.copy()

        if self._is_valid_segment(current):
            merged.append(current)

        return merged

    def _is_valid_segment(self, segment: Dict[str, Any]) -> bool:
        duration = segment["end"] - segment["start"]
        return duration >= self.config.min_segment_duration

    def diarize_with_embeddings(
        self,
        audio_path: str,
        min_speakers: Optional[int] = None,
        max_speakers: Optional[int] = None,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, np.ndarray]]:
        segments = self.diarize(audio_path, min_speakers, max_speakers)
        return segments, self._speaker_embeddings.copy()

    def match_speaker(
        self,
        embedding: np.ndarray,
        threshold: float = 0.7,
    ) -> Optional[str]:
        if not self._speaker_embeddings:
            return None

        best_match = None
        best_similarity = -1

        for speaker_id, stored_emb in self._speaker_embeddings.items():
            similarity = self._cosine_similarity(embedding, stored_emb)
            if similarity > best_similarity:
                best_similarity = similarity
                best_match = speaker_id

        if best_similarity >= threshold:
            return best_match
        return None

    def register_speaker(self, speaker_id: str, embedding: np.ndarray):
        self._speaker_embeddings[speaker_id] = embedding

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        if a.shape != b.shape:
            return 0.0
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))


def get_enhanced_diarization_engine(
    auth_token: Optional[str] = None,
    device: Optional[str] = None,
    config: Optional[DiarizationConfig] = None,
) -> EnhancedDiarizationEngine:
    return EnhancedDiarizationEngine(
        auth_token=auth_token,
        device=device,
        config=config,
    )
