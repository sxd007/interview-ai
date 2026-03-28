from typing import Dict, Any, Optional, List
from dataclasses import dataclass

import numpy as np
import librosa
from scipy.signal import find_peaks


@dataclass
class ProsodyFeatures:
    pitch_mean: float
    pitch_std: float
    pitch_min: float
    pitch_max: float
    energy_mean: float
    energy_std: float
    speech_rate: float
    pause_ratio: float
    filler_count: int
    pitch_range: float
    energy_range: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pitch_mean": float(self.pitch_mean),
            "pitch_std": float(self.pitch_std),
            "pitch_min": float(self.pitch_min),
            "pitch_max": float(self.pitch_max),
            "pitch_range": float(self.pitch_range),
            "energy_mean": float(self.energy_mean),
            "energy_std": float(self.energy_std),
            "energy_range": float(self.energy_range),
            "speech_rate": float(self.speech_rate),
            "pause_ratio": float(self.pause_ratio),
            "filler_count": int(self.filler_count),
        }


class ProsodyAnalyzer:
    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate

    def analyze(self, audio_path: str) -> Dict[str, Any]:
        audio, sr = librosa.load(audio_path, sr=self.sample_rate)
        return self.analyze_array(audio, sr)

    def analyze_array(self, audio: np.ndarray, sample_rate: Optional[int] = None) -> Dict[str, Any]:
        sr = sample_rate or self.sample_rate
        if len(audio) == 0:
            return self._empty_result()

        energy = self._compute_energy(audio, sr)
        pitch, voiced_flag, voiced_probs = self._compute_pitch(audio, sr)
        speech_rate, pause_ratio = self._compute_speech_rate(audio, sr)
        filler_count = self._detect_fillers(audio, sr)

        features = ProsodyFeatures(
            pitch_mean=float(np.mean(pitch[pitch > 0])) if np.any(pitch > 0) else 0.0,
            pitch_std=float(np.std(pitch[pitch > 0])) if np.any(pitch > 0) else 0.0,
            pitch_min=float(np.min(pitch[pitch > 0])) if np.any(pitch > 0) else 0.0,
            pitch_max=float(np.max(pitch[pitch > 0])) if np.any(pitch > 0) else 0.0,
            pitch_range=float(np.max(pitch) - np.min(pitch)) if len(pitch) > 0 else 0.0,
            energy_mean=float(np.mean(energy)),
            energy_std=float(np.std(energy)),
            energy_range=float(np.max(energy) - np.min(energy)),
            speech_rate=speech_rate,
            pause_ratio=pause_ratio,
            filler_count=filler_count,
        )
        return features.to_dict()

    def analyze_segments(
        self, audio: np.ndarray, sample_rate: int, segments: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        results = []
        for seg in segments:
            start_sample = int(seg["start"] * sample_rate)
            end_sample = int(seg["end"] * sample_rate)
            seg_audio = audio[start_sample:end_sample]
            if len(seg_audio) > 0:
                result = self.analyze_array(seg_audio, sample_rate)
            else:
                result = self._empty_result()
            result["start"] = seg["start"]
            result["end"] = seg["end"]
            results.append(result)
        return results

    def _compute_energy(self, audio: np.ndarray, sr: int) -> np.ndarray:
        frame_length = int(0.025 * sr)
        hop_length = int(0.010 * sr)
        energy = np.array([
            np.sqrt(np.mean(audio[i:i+frame_length]**2))
            for i in range(0, len(audio) - frame_length, hop_length)
        ])
        return energy

    def _compute_pitch(
        self, audio: np.ndarray, sr: int
    ):
        f0, voiced_flag, voiced_probs = librosa.pyin(
            audio,
            fmin=librosa.note_to_hz("C2"),
            fmax=librosa.note_to_hz("C7"),
            sr=sr,
            frame_length=2048,
            hop_length=512,
            center=True,
        )
        f0 = np.nan_to_num(f0, nan=0.0)
        return f0, voiced_flag, voiced_probs

    def _compute_speech_rate(
        self, audio: np.ndarray, sr: int
    ) -> tuple:
        frame_length = int(0.025 * sr)
        hop_length = int(0.010 * sr)
        energy = np.array([
            np.sqrt(np.mean(audio[i:i+frame_length]**2))
            for i in range(0, len(audio) - frame_length, hop_length)
        ])
        
        energy_threshold = np.mean(energy) * 0.2
        speech_frames = energy > energy_threshold
        speech_duration = np.sum(speech_frames) * hop_length / sr
        total_duration = len(audio) / sr
        
        pause_ratio = 1.0 - (speech_duration / total_duration) if total_duration > 0 else 0.0
        
        peaks, _ = find_peaks(energy, height=energy_threshold, distance=int(0.3 * sr / hop_length))
        speech_rate = len(peaks) / total_duration if total_duration > 0 else 0.0
        
        return speech_rate, pause_ratio

    def _detect_fillers(self, audio: np.ndarray, sr: int) -> int:
        try:
            onset_env = librosa.onset.onset_strength(y=audio, sr=sr)
            onset_frames = librosa.onset.onset_detect(
                onset_envelope=onset_env, sr=sr,
                backtrack=False,
            )
            durations = []
            for i in range(len(onset_frames) - 1):
                dur = (onset_frames[i+1] - onset_frames[i]) * librosa.get_samplerate() / sr / 2
                durations.append(dur)
            fillers = [d for d in durations if 0.03 < d < 0.15]
            return len(fillers)
        except Exception:
            return 0

    def _empty_result(self) -> Dict[str, Any]:
        return {
            "pitch_mean": 0.0,
            "pitch_std": 0.0,
            "pitch_min": 0.0,
            "pitch_max": 0.0,
            "pitch_range": 0.0,
            "energy_mean": 0.0,
            "energy_std": 0.0,
            "energy_range": 0.0,
            "speech_rate": 0.0,
            "pause_ratio": 0.0,
            "filler_count": 0,
        }


def get_prosody_analyzer(sample_rate: int = 16000) -> ProsodyAnalyzer:
    return ProsodyAnalyzer(sample_rate=sample_rate)
