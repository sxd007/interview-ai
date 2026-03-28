#!/usr/bin/env python3
"""
Migration script: Re-parse SenseVoice transcript with corrected tag parsing,
split into sentence-level segments with timestamps, and link speakers.

Usage:
    python scripts/migrate_segments.py [--interview-id ID]
"""

import sys
import os
import re
import uuid
import tempfile
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("HF_TOKEN", "")  # Set your HuggingFace token here
os.environ.setdefault("PYTHONPATH", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import soundfile as sf

from src.models.database import get_session_local, init_db, AudioSegment, Speaker, EmotionNode
from src.services.audio.processor import AudioProcessor
from src.inference.diarization.engine import DiarizationEngine
from src.inference.stt.sensevoice import (
    clean_text,
    parse_sentence_tags,
    split_sentences,
    estimate_sentence_timestamps,
)


EMOTION_TAG_MAP = {
    "NEUTRAL": "neutral", "HAPPY": "happy", "SAD": "sad", "ANGRY": "angry",
    "FEAR": "fearful", "DISGUST": "disgust", "SURPRISE": "surprised",
    "EMO_UNKNOWN": "unknown", "EMO_OTHER": "unknown",
}
LANG_TAG_MAP = {
    "zh": "zh", "en": "en", "ja": "ja", "ko": "ko", "yue": "yue", "nospeech": "nospeech",
}
EVENT_TAG_MAP = {
    "Speech": "speech", "BGM": "bgm", "Laughter": "laughter",
    "Applause": "applause", "Crying": "crying", "Shout": "shout", "Noise": "noise",
}


def get_audio_duration(audio_path: str) -> float:
    try:
        info = sf.info(audio_path)
        return float(info.frames) / float(info.samplerate)
    except Exception:
        import librosa
        return librosa.get_duration(path=audio_path)


def parse_transcript(raw_text: str, total_duration: float):
    parsed_sentences = parse_sentence_tags(raw_text)

    if not parsed_sentences:
        clean = clean_text(raw_text)
        sentences_raw = split_sentences(clean)
        parsed_sentences = [{"text": t, "lang": "unknown", "emotion": "neutral", "event": "speech"} for t in sentences_raw]

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

    timestamps = estimate_sentence_timestamps([s["text"] for s in sentences_with_meta], total_duration)

    segments = []
    for i, sent in enumerate(sentences_with_meta):
        start, end = timestamps[i] if i < len(timestamps) else (0.0, 0.0)
        segments.append({
            "text": sent["text"],
            "start": start,
            "end": end,
            "duration": end - start,
            "lang": sent["lang"],
            "emotion": sent["emotion"],
            "event": sent["event"],
        })
    return segments


def find_speaker(start: float, end: float, speakers_data: list):
    mid = (start + end) / 2
    for seg in speakers_data:
        if seg["start"] <= mid <= seg["end"]:
            return seg["speaker"]
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--interview-id", default="bf16962e-f085-40e8-af35-82369c3ae8db")
    parser.add_argument("--hf-token", default=os.getenv("HF_TOKEN"))
    parser.add_argument("--rerun-stt", action="store_true", help="Re-run STT to get fresh raw transcript")
    args = parser.parse_args()

    db = get_session_local()()
    try:
        from src.models.database import Interview
        interview = db.query(Interview).filter(Interview.id == args.interview_id).first()
        if not interview:
            print(f"Interview not found: {args.interview_id}")
            return

        print(f"Processing interview: {interview.id}")
        print(f"  Duration: {interview.duration}s")
        print(f"  File: {interview.file_path}")

        if args.rerun_stt:
            print("\nRe-running STT (SenseVoice) to get fresh raw transcript...")
            processor = AudioProcessor()
            audio_path, _ = processor.extract_audio(interview.file_path)
            try:
                from src.inference.stt.sensevoice import SenseVoiceEngine
                stt = SenseVoiceEngine(device="cpu")
                stt.load()
                res = stt.model.generate(
                    input=audio_path,
                    cache={},
                    language="auto",
                    use_itn=False,
                    batch_size_s=300,
                    merge_vad=True,
                    merge_length_s=15,
                )
                raw_text = res[0].get("text", "")
                print(f"  -> STT raw text length: {len(raw_text)} chars")
                print(f"  -> First 100 chars: {repr(raw_text[:100])}")
                stt.unload()
            finally:
                os.unlink(audio_path)
        else:
            raw_segment = db.query(AudioSegment).filter(
                AudioSegment.interview_id == interview.id
            ).first()
            if not raw_segment or not raw_segment.transcript:
                print("No raw transcript found. Use --rerun-stt to re-generate.")
                return
            raw_text = raw_segment.transcript
        total_duration = interview.duration or 1.0

        print(f"\nParsing transcript ({len(raw_text)} chars)...")
        parsed = parse_transcript(raw_text, total_duration)
        print(f"  -> {len(parsed)} sentence segments")

        lang_counts = {}
        event_counts = {}
        emotion_counts = {}
        for seg in parsed:
            lang_counts[seg["lang"]] = lang_counts.get(seg["lang"], 0) + 1
            event_counts[seg["event"]] = event_counts.get(seg["event"], 0) + 1
            emotion_counts[seg["emotion"]] = emotion_counts.get(seg["emotion"], 0) + 1
        print(f"  Languages: {lang_counts}")
        print(f"  Events: {event_counts}")
        print(f"  Emotions: {emotion_counts}")

        video_path = interview.file_path
        if not os.path.exists(video_path):
            print(f"Video file not found: {video_path}")
            return

        print("\nExtracting audio for diarization...")
        processor = AudioProcessor()
        audio_path, _ = processor.extract_audio(video_path)

        print("Running speaker diarization (pyannote)...")
        diarization_engine = DiarizationEngine(auth_token=args.hf_token)
        speakers_data = diarization_engine.diarize(audio_path)
        print(f"  -> {len(speakers_data)} speaker segments from pyannote")
        unique_speakers = list(dict.fromkeys(s["speaker"] for s in speakers_data))
        print(f"  -> {len(unique_speakers)} unique speakers: {unique_speakers}")

        speaker_label_map = {}
        existing_speakers = db.query(Speaker).filter(Speaker.interview_id == interview.id).all()
        existing_label_map = {sp.label: sp for sp in existing_speakers}
        for i, sp_label in enumerate(unique_speakers):
            db_label = f"说话人 {chr(65 + i)}"
            if db_label in existing_label_map:
                speaker_label_map[sp_label] = existing_label_map[db_label].id
            else:
                new_sp = Speaker(
                    id=str(uuid.uuid4()),
                    interview_id=interview.id,
                    label=db_label,
                    color=["#1890ff", "#52c41a", "#faad14", "#f5222d", "#722ed1", "#13c2c2"][i % 6],
                )
                db.add(new_sp)
                db.flush()
                speaker_label_map[sp_label] = new_sp.id

        print("\nReplacing old segments...")
        db.query(AudioSegment).filter(AudioSegment.interview_id == interview.id).delete()
        db.query(EmotionNode).filter(
            EmotionNode.interview_id == interview.id,
            EmotionNode.source == "audio"
        ).delete()

        print(f"Creating {len(parsed)} new segments...")
        for seg in parsed:
            speaker_label = find_speaker(seg["start"], seg["end"], speakers_data)
            speaker_id = speaker_label_map.get(speaker_label) if speaker_label else None

            audio_seg = AudioSegment(
                id=str(uuid.uuid4()),
                interview_id=interview.id,
                speaker_id=speaker_id,
                start_time=seg["start"],
                end_time=seg["end"],
                transcript=seg["text"],
                confidence=0.9,
                lang=seg["lang"],
                event=seg["event"],
                emotion_scores={"emotion": seg["emotion"]},
            )
            db.add(audio_seg)

        db.commit()
        print("Done! Segments saved.")

        linked = db.query(AudioSegment).filter(
            AudioSegment.interview_id == interview.id,
            AudioSegment.speaker_id.isnot(None)
        ).count()
        total = db.query(AudioSegment).filter(
            AudioSegment.interview_id == interview.id
        ).count()
        print(f"\nSpeaker linking: {linked}/{total} segments have speaker assigned.")

        lang_summary = {}
        for seg in db.query(AudioSegment).filter(AudioSegment.interview_id == interview.id).all():
            lang_summary[seg.lang] = lang_summary.get(seg.lang, 0) + 1
        print(f"Language distribution: {lang_summary}")

        os.unlink(audio_path)

    finally:
        db.close()


if __name__ == "__main__":
    main()
