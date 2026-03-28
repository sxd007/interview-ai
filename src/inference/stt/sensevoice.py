import re
import logging
from typing import Optional, Dict, Any, List, Tuple
import numpy as np

import torch

from funasr import AutoModel

logger = logging.getLogger(__name__)


EMOTION_TAG_MAP = {
    "NEUTRAL": "neutral",
    "HAPPY": "happy",
    "SAD": "sad",
    "ANGRY": "angry",
    "FEAR": "fearful",
    "DISGUST": "disgust",
    "SURPRISE": "surprised",
    "EMO_UNKNOWN": "unknown",
    "EMO_OTHER": "unknown",
}

LANG_TAG_MAP = {
    "zh": "zh",
    "en": "en",
    "ja": "ja",
    "ko": "ko",
    "yue": "yue",
    "nospeech": "nospeech",
}

EVENT_TAG_MAP = {
    "Speech": "speech",
    "BGM": "bgm",
    "Laughter": "laughter",
    "Applause": "applause",
    "Crying": "crying",
    "Shout": "shout",
    "Noise": "noise",
}


def clean_text(text: str) -> str:
    """Remove all <|tag|> markers from text."""
    return re.sub(r"<\|[^|]+\|>", "", text)


def parse_sentence_tags(text: str) -> List[Dict[str, Any]]:
    """Parse text with embedded <|tag|> markers into sentences with metadata.

    Tags appear BEFORE each sentence: <|lang|><|emotion|><|event|><|itn|>sentence_text
    Returns list of {text, lang, emotion, event, itn}.
    """
    tag_pattern = r"(<\|[^|>]+\|>)"
    parts = re.split(tag_pattern, text)

    sentences = []
    current_meta = {"lang": "unknown", "emotion": "neutral", "event": "speech", "itn": False}

    for part in parts:
        if not part:
            continue
        if part.startswith("<|") and part.endswith("|>"):
            tag = part[2:-2]
            if tag in LANG_TAG_MAP:
                current_meta = current_meta.copy()
                current_meta["lang"] = LANG_TAG_MAP[tag]
            elif tag in EMOTION_TAG_MAP:
                current_meta = current_meta.copy()
                current_meta["emotion"] = EMOTION_TAG_MAP[tag]
            elif tag in EVENT_TAG_MAP:
                current_meta = current_meta.copy()
                current_meta["event"] = EVENT_TAG_MAP[tag]
            elif tag == "withitn":
                current_meta = current_meta.copy()
                current_meta["itn"] = True
            elif tag == "noitn":
                current_meta = current_meta.copy()
                current_meta["itn"] = False
        else:
            cleaned = part.strip()
            if cleaned:
                sentences.append({
                    "text": cleaned,
                    "lang": current_meta["lang"],
                    "emotion": current_meta["emotion"],
                    "event": current_meta["event"],
                })

    return sentences


def split_sentences(text: str) -> List[str]:
    """Split raw text into sentences using punctuation."""
    text = clean_text(text)
    sentences = re.split(r"(?<=[。！？!?\.])", text)
    result = []
    for s in sentences:
        s = s.strip()
        if s:
            result.append(s)
    return result


def estimate_sentence_timestamps(
    sentences: List[str],
    total_duration: float,
) -> List[Tuple[float, float]]:
    """Estimate timestamps for sentences proportionally by character count.

    Accounts for Chinese characters being ~2x the visual width of ASCII.
    """
    def char_weight(s: str) -> float:
        chinese = len(re.findall(r"[\u4e00-\u9fff]", s))
        other = len(s) - chinese
        return chinese * 2 + other

    total_weight = sum(char_weight(s) for s in sentences)
    if total_weight == 0 or total_duration == 0:
        return [(0.0, total_duration)]

    timestamps = []
    cursor = 0.0
    for s in sentences:
        weight = char_weight(s)
        duration = (weight / total_weight) * total_duration
        start = cursor
        end = min(cursor + duration, total_duration)
        timestamps.append((start, end))
        cursor = end

    if len(timestamps) > 1:
        timestamps[-1] = (timestamps[-1][0], total_duration)

    return timestamps


class SenseVoiceEngine:
    def __init__(
        self,
        model_name: str = "FunAudioLLM/SenseVoiceSmall",
        device: Optional[str] = None,
        cache_dir: Optional[str] = None,
        language: str = "auto",
        vad_enabled: bool = True,
        spk_enabled: bool = False,
    ):
        self.model_name = model_name
        self.device = self._get_device(device)
        self.cache_dir = cache_dir
        self.language = language
        self.vad_enabled = vad_enabled
        self.spk_enabled = spk_enabled
        self.model = None
        self._total_duration: float = 0.0

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

        device = self.device

        vad_kwargs = {}
        if self.vad_enabled:
            vad_kwargs = {
                "vad_model": "fsmn-vad",
                "vad_kwargs": {"max_single_segment_time": 30000},
            }

        spk_kwargs = {}
        if self.spk_enabled:
            spk_kwargs = {
                "spk_model": "cam++",
                "punc_model": "ct-punc-c",
            }

        self.model = AutoModel(
            model=self.model_name,
            device=device,
            cache_dir=self.cache_dir,
            hub="hf",
            trust_remote_code=True,
            disable_update=True,
            **vad_kwargs,
            **spk_kwargs,
        )

        if device == "cpu" and self.device == "mps":
            self._use_mps_fallback = True
        else:
            self._use_mps_fallback = False

    def unload(self) -> None:
        if self.model is not None:
            del self.model
            self.model = None
            if self.device in ("cuda", "mps"):
                torch.mps.empty_cache() if self.device == "mps" else torch.cuda.empty_cache()

    def transcribe(
        self,
        audio_path: str,
        language: str = "auto",
        use_itn: bool = True,
        word_timestamps: bool = False,
    ) -> Dict[str, Any]:
        if self.model is None:
            self.load()

        lang = language if language != "auto" else self.language

        self._total_duration = self._get_audio_duration(audio_path)

        res = self.model.generate(
            input=audio_path,
            cache={},
            language=lang,
            use_itn=use_itn,
            batch_size_s=300,
            merge_vad=True,
            merge_length_s=15,
            output_timestamp=True,
        )

        result = self._parse_result(res)
        return result

    def _get_audio_duration(self, audio_path: str) -> float:
        try:
            import soundfile as sf
            info = sf.info(audio_path)
            return float(info.frames) / float(info.samplerate)
        except Exception:
            try:
                import librosa
                duration = librosa.get_duration(path=audio_path)
                return duration
            except Exception:
                return 0.0

    def transcribe_array(
        self,
        audio_array: np.ndarray,
        sample_rate: int = 16000,
        **kwargs,
    ) -> Dict[str, Any]:
        import tempfile
        import soundfile as sf

        self._total_duration = float(len(audio_array)) / float(sample_rate)

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            sf.write(f.name, audio_array, sample_rate)
            result = self.transcribe(f.name, **kwargs)
            import os
            os.unlink(f.name)

        return result

    def _parse_result(self, res: List[Dict[str, Any]], include_spk: bool = False) -> Dict[str, Any]:
        if not res:
            return {"text": "", "segments": [], "language": "unknown"}

        item = res[0]
        raw_text = item.get("text", "")
        total_duration = self._total_duration

        timestamp_list = item.get("timestamp", [])
        
        words_data = item.get("words", [])

        parsed_sentences = parse_sentence_tags(raw_text)

        if not parsed_sentences:
            clean = clean_text(raw_text)
            sentences_raw = split_sentences(clean)
            parsed_sentences = [
                {"text": t, "lang": "unknown", "emotion": "neutral", "event": "speech"}
                for t in sentences_raw
            ]

        sentences_with_meta = []
        for item_meta in parsed_sentences:
            parts = split_sentences(item_meta["text"])
            for part in parts:
                if part.strip():
                    sentences_with_meta.append({
                        "text": part.strip(),
                        "lang": item_meta.get("lang", "unknown"),
                        "emotion": item_meta.get("emotion", "neutral"),
                        "event": item_meta.get("event", "speech"),
                    })

        timestamps = self._extract_sentence_timestamps(sentences_with_meta, timestamp_list, total_duration)
        
        spk_segments = []
        if include_spk and words_data:
            spk_segments = self._extract_speaker_from_words(words_data, sentences_with_meta, timestamps)

        segments = []
        lang_counts: Dict[str, int] = {}
        emotion_counts: Dict[str, int] = {}
        event_counts: Dict[str, int] = {}

        for i, sent in enumerate(sentences_with_meta):
            start, end = timestamps[i] if i < len(timestamps) else (0.0, 0.0)
            lang = sent["lang"]
            emotion = sent["emotion"]
            event = sent["event"]

            lang_counts[lang] = lang_counts.get(lang, 0) + 1
            emotion_counts[emotion] = emotion_counts.get(emotion, 0) + 1
            event_counts[event] = event_counts.get(event, 0) + 1

            segments.append({
                "start": start,
                "end": end,
                "text": sent["text"],
                "duration": end - start,
                "lang": lang,
                "emotion": emotion,
                "event": event,
            })

        dominant_lang = max(lang_counts, key=lang_counts.get) if lang_counts else "zh"
        clean_text_output = clean_text(raw_text)

        return {
            "text": clean_text_output,
            "segments": segments,
            "language": dominant_lang,
            "lang_distribution": lang_counts,
            "emotion_distribution": emotion_counts,
            "event_distribution": event_counts,
            "duration": total_duration,
        }

    def _extract_sentence_timestamps(
        self,
        sentences: List[Dict[str, Any]],
        timestamp_list: List[List],
        total_duration: float,
    ) -> List[Tuple[float, float]]:
        """Extract timestamps for sentences using FunASR real timestamps or fallback to estimation."""
        if not timestamp_list:
            logger.warning("No timestamp_list from FunASR, using estimation")
            return estimate_sentence_timestamps(
                [s["text"] for s in sentences], total_duration
            )

        timestamps_ms = []
        for ts in timestamp_list:
            if isinstance(ts, list) and len(ts) >= 2:
                start_ms, end_ms = ts[0], ts[1]
                if start_ms is not None and end_ms is not None:
                    timestamps_ms.append((start_ms / 1000.0, end_ms / 1000.0))

        if not timestamps_ms:
            logger.warning("Failed to parse timestamps from FunASR, using estimation")
            return estimate_sentence_timestamps(
                [s["text"] for s in sentences], total_duration
            )

        num_timestamps = len(timestamps_ms)
        num_sentences = len(sentences)

        if num_timestamps == num_sentences:
            logger.info(f"Timestamp count matches sentence count: {num_sentences}")
            return timestamps_ms

        if num_timestamps > num_sentences:
            merged_timestamps = self._merge_timestamps_to_sentences(
                [s["text"] for s in sentences], timestamps_ms
            )
            if merged_timestamps and len(merged_timestamps) == num_sentences:
                logger.info(f"Merged {num_timestamps} timestamps to {num_sentences} sentences")
                return merged_timestamps

        logger.warning(f"Timestamp count ({num_timestamps}) != sentence count ({num_sentences}), using estimation")
        return estimate_sentence_timestamps(
            [s["text"] for s in sentences], total_duration
        )

    def _merge_timestamps_to_sentences(
        self,
        sentences: List[str],
        word_timestamps: List[Tuple[float, float]],
    ) -> List[Tuple[float, float]]:
        """Merge word-level timestamps into sentence-level timestamps."""
        if not sentences or not word_timestamps:
            return []

        timestamps = []
        cursor = 0
        current_start = word_timestamps[0][0] if word_timestamps else 0.0

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                timestamps.append((0.0, 0.0))
                continue

            sentence_start = None
            sentence_end = None
            char_count = 0

            while cursor < len(word_timestamps):
                word_ts = word_timestamps[cursor]
                if sentence_start is None:
                    sentence_start = word_ts[0]
                    sentence_end = word_ts[1]
                else:
                    sentence_end = word_ts[1]

                char_count += 1
                cursor += 1

                if char_count >= len(sentence):
                    break

            if sentence_start is not None:
                timestamps.append((sentence_start, sentence_end or sentence_start))
            else:
                timestamps.append((0.0, 0.0))

        return timestamps

    def _extract_speaker_from_words(
        self,
        words_data: List,
        sentences: List[Dict[str, Any]],
        timestamps: List[Tuple[float, float]],
    ) -> List[Dict[str, Any]]:
        """Extract speaker information from FunASR words data.
        
        words_data format: [{"text": "word", "start": 0.0, "end": 0.5, "speaker": "SPEAKER_00"}, ...]
        """
        if not words_data:
            return []
        
        spk_segments = []
        
        for i, sentence in enumerate(sentences):
            if i >= len(timestamps):
                break
            
            sent_start, sent_end = timestamps[i]
            
            sent_speakers = []
            for word in words_data:
                try:
                    word_start = word.get("start", 0)
                    word_end = word.get("end", 0)
                    
                    if word_start >= sent_start and word_end <= sent_end:
                        speaker = word.get("speaker", "")
                        if speaker:
                            sent_speakers.append(speaker)
                except:
                    continue
            
            if sent_speakers:
                from collections import Counter
                most_common = Counter(sent_speakers).most_common(1)
                if most_common:
                    spk_segments.append({
                        "start": sent_start,
                        "end": sent_end,
                        "speaker": most_common[0][0],
                    })
        
        return spk_segments


def get_sensevoice_engine(
    model_name: str = "FunAudioLLM/SenseVoiceSmall",
    device: Optional[str] = None,
) -> SenseVoiceEngine:
    return SenseVoiceEngine(model_name=model_name, device=device)
