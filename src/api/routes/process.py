import io
import os
import uuid
import subprocess
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from src.services.audio.processor import AudioProcessor
from src.inference.diarization.engine import DiarizationEngine
from src.inference.stt.sensevoice import SenseVoiceEngine
from sqlalchemy.orm import Session

from src.api.schemas import (
    ProcessConfig,
    TaskResponse,
    ProgressResponse,
    TranscriptResponse,
    SpeakerResponse,
    SegmentResponse,
    ProsodyResponse,
    EmotionAnalysisResponse,
    EmotionNodeResponse,
    EmotionSummary,
    SignalItem,
    TimelineResponse,
    FaceFrameResponse,
    KeyframeResponse,
    ReportResponse,
    DiarizationAdvancedConfig,
    STTAdvancedConfig,
    AdvancedConfigDefaults,
)
from src.models import (
    Interview, Speaker, AudioSegment, FaceFrame, Keyframe, EmotionNode,
    VideoChunk, PipelineStage, PendingChange, get_db, ProcessingStatus, StageStatus, ChunkStatus,
)
from src.services.interview import process_interview, ProcessingProgress
from src.services.report.generator import generate_report
from src.core import settings
from src.utils.logging import get_logger
from src.utils.pipeline_logger import get_pipeline_logger, pipeline_context

logger = get_logger(__name__)
pipeline_log = get_pipeline_logger(__name__)

router = APIRouter(prefix="/interviews", tags=["processing"])


def get_video_duration(video_path: str) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", video_path],
        capture_output=True, text=True, check=True
    )
    return float(result.stdout.strip())


def _extract_speakers_from_funasr(words_data: List) -> List[Dict[str, Any]]:
    """Extract speaker segments from FunASR words data.
    
    words_data format: [{"text": "word", "start": 0.0, "end": 0.5, "speaker": "SPEAKER_00"}, ...]
    Returns: [{"start": 0.0, "end": 5.0, "speaker": "SPEAKER_00"}, ...]
    """
    if not words_data:
        return []
    
    segments = []
    current_speaker = None
    current_start = None
    current_end = None
    
    for word in words_data:
        try:
            word_text = word.get("text", "")
            word_start = word.get("start", 0)
            word_end = word.get("end", 0)
            speaker = word.get("speaker", "")
            
            if not speaker:
                continue
            
            if speaker != current_speaker:
                if current_speaker is not None and current_start is not None:
                    segments.append({
                        "start": current_start,
                        "end": current_end,
                        "speaker": current_speaker,
                    })
                current_speaker = speaker
                current_start = word_start
                current_end = word_end
            else:
                current_end = word_end
        except Exception:
            continue
    
    if current_speaker is not None and current_start is not None:
        segments.append({
            "start": current_start,
            "end": current_end,
            "speaker": current_speaker,
        })
    
    return segments


def _extract_timestamps_from_list(
    timestamp_list: Optional[List],
    sentences: List[str],
    total_duration: float,
):
    """Extract timestamps for sentences using FunASR real timestamps or fallback to estimation."""
    from src.inference.stt.sensevoice import estimate_sentence_timestamps
    
    if not timestamp_list:
        logger.warning("No timestamp_list from FunASR, using estimation")
        return estimate_sentence_timestamps(sentences, total_duration)

    timestamps_ms = []
    for ts in timestamp_list:
        if isinstance(ts, list) and len(ts) >= 2:
            start_ms, end_ms = ts[0], ts[1]
            if start_ms is not None and end_ms is not None:
                timestamps_ms.append((start_ms / 1000.0, end_ms / 1000.0))

    if not timestamps_ms:
        logger.warning("Failed to parse timestamps from FunASR, using estimation")
        return estimate_sentence_timestamps(sentences, total_duration)

    num_timestamps = len(timestamps_ms)
    num_sentences = len(sentences)

    if num_timestamps == num_sentences:
        logger.info(f"Timestamp count matches sentence count: {num_sentences}")
        return timestamps_ms

    if num_timestamps > num_sentences:
        merged = _merge_timestamps_to_sentences(sentences, timestamps_ms)
        if merged and len(merged) == num_sentences:
            logger.info(f"Merged {num_timestamps} timestamps to {num_sentences} sentences")
            return merged

    logger.warning(f"Timestamp count ({num_timestamps}) != sentence count ({num_sentences}), using estimation")
    return estimate_sentence_timestamps(sentences, total_duration)


def _merge_timestamps_to_sentences(
    sentences: List[str],
    word_timestamps: List[tuple],
):
    """Merge word-level timestamps into sentence-level timestamps."""
    if not sentences or not word_timestamps:
        return []

    timestamps = []
    cursor = 0

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


def _create_segments_from_whisper(
    db: Session,
    interview_id: str,
    chunk_id: str,
    whisper_result: dict,
    diarization_data: Optional[dict] = None,
    chunk_global_start: float = 0.0,
) -> int:
    """
    Create Speaker + AudioSegment records from Whisper output.
    
    Whisper output format:
    {
        "text": "full text",
        "segments": [
            {"start": 0.0, "end": 5.0, "text": "segment text", "words": [...]},
            ...
        ],
        "language": "zh",
        "duration": 100.0
    }
    """
    segments = whisper_result.get("segments", [])
    if not segments:
        logger.warning(f"No segments in Whisper result for chunk {chunk_id}")
        return 0
    
    detected_lang = whisper_result.get("language", "zh")
    
    colors = ["#1890ff", "#52c41a", "#faad14", "#f5222d", "#722ed1", "#13c2c2"]
    existing_speakers = {sp.label: sp for sp in db.query(Speaker).filter(
        Speaker.interview_id == interview_id,
        Speaker.chunk_id == chunk_id,
    ).all()}
    
    if diarization_data and "speakers" in diarization_data:
        speaker_order = list(dict.fromkeys(d["speaker"] for d in diarization_data["speakers"]))
        speaker_map = {}
        for i, sp_label in enumerate(speaker_order):
            display_label = f"说话人 {chr(65 + i)}"
            if display_label not in existing_speakers:
                sp = Speaker(
                    id=str(uuid.uuid4()),
                    interview_id=interview_id,
                    chunk_id=chunk_id,
                    label=display_label,
                    color=colors[i % len(colors)],
                )
                db.add(sp)
                db.flush()
                existing_speakers[display_label] = sp
            speaker_map[sp_label] = existing_speakers[display_label].id
        diarization_entries = diarization_data["speakers"]
    else:
        speaker_map = {}
        diarization_entries = []
        if not existing_speakers:
            display_label = "说话人 A"
            sp = Speaker(
                id=str(uuid.uuid4()),
                interview_id=interview_id,
                chunk_id=chunk_id,
                label=display_label,
                color=colors[0],
            )
            db.add(sp)
            db.flush()
            existing_speakers[display_label] = sp
    
    created = 0
    for seg in segments:
        seg_start = seg.get("start", 0.0)
        seg_end = seg.get("end", 0.0)
        seg_text = seg.get("text", "").strip()
        
        if not seg_text:
            continue
        
        abs_start = chunk_global_start + seg_start
        abs_end = chunk_global_start + seg_end
        
        speaker_id = None
        if diarization_entries:
            best_speaker = None
            best_overlap = 0.0
            
            for entry in diarization_entries:
                entry_start = chunk_global_start + entry["start"]
                entry_end = chunk_global_start + entry["end"]
                
                overlap_start = max(abs_start, entry_start)
                overlap_end = min(abs_end, entry_end)
                overlap = max(0, overlap_end - overlap_start)
                
                if overlap > best_overlap:
                    best_overlap = overlap
                    best_speaker = entry["speaker"]
            
            if best_speaker:
                speaker_id = speaker_map.get(best_speaker)
        
        if not speaker_id:
            sp_list = list(existing_speakers.values())
            speaker_id = sp_list[created % len(sp_list)].id if sp_list else None
        
        audio_seg = AudioSegment(
            id=str(uuid.uuid4()),
            interview_id=interview_id,
            chunk_id=chunk_id,
            speaker_id=speaker_id,
            start_time=abs_start,
            end_time=abs_end,
            transcript=seg_text,
            confidence=0.9,
            lang=detected_lang,
            event="speech",
            emotion_scores={"emotion": "neutral"},
        )
        db.add(audio_seg)
        created += 1
    
    db.commit()
    logger.info(f"Created {created} segments from Whisper for chunk {chunk_id}")
    return created


def _create_segments_from_raw_text(
    db: Session,
    interview_id: str,
    chunk_id: str,
    raw_text: str,
    duration: float,
    diarization_data: Optional[dict] = None,
    chunk_global_start: float = 0.0,
    timestamp_list: Optional[List] = None,
) -> int:
    """
    Parse SenseVoice raw output (with tags) and create Speaker + AudioSegment records.
    Tags like <|zh|>, <|neutral|> are preserved because use_itn=False was used.
    Diarization data maps time ranges to speaker labels for accurate speaker assignment.
    Uses FunASR timestamps if available, otherwise falls back to estimation.
    """
    from src.inference.stt.sensevoice import (
        parse_sentence_tags, split_sentences, estimate_sentence_timestamps,
    )

    if not raw_text or not raw_text.strip():
        logger.warning(f"Empty raw_text for chunk {chunk_id}, creating no segments")
        return 0

    parsed = parse_sentence_tags(raw_text)
    if not parsed:
        logger.warning(f"No parsed sentences from raw_text for chunk {chunk_id}")
        return 0

    sentences_with_meta = []
    for item_meta in parsed:
        parts = split_sentences(item_meta["text"])
        for part in parts:
            if part.strip():
                sentences_with_meta.append({
                    "text": part.strip(),
                    "lang": item_meta.get("lang", "unknown"),
                    "emotion": item_meta.get("emotion", "neutral"),
                    "event": item_meta.get("event", "speech"),
                })

    if not sentences_with_meta:
        return 0

    timestamps = _extract_timestamps_from_list(
        timestamp_list, [s["text"] for s in sentences_with_meta], duration
    )

    colors = ["#1890ff", "#52c41a", "#faad14", "#f5222d", "#722ed1", "#13c2c2"]
    existing_speakers = {sp.label: sp for sp in db.query(Speaker).filter(
        Speaker.interview_id == interview_id,
        Speaker.chunk_id == chunk_id,
    ).all()}

    if diarization_data and "speakers" in diarization_data:
        speaker_order = list(dict.fromkeys(d["speaker"] for d in diarization_data["speakers"]))
        speaker_map = {}
        for i, sp_label in enumerate(speaker_order):
            display_label = f"说话人 {chr(65 + i)}"
            if display_label not in existing_speakers:
                sp = Speaker(
                    id=str(uuid.uuid4()),
                    interview_id=interview_id,
                    chunk_id=chunk_id,
                    label=display_label,
                    color=colors[i % len(colors)],
                )
                db.add(sp)
                db.flush()
                existing_speakers[display_label] = sp
            speaker_map[sp_label] = existing_speakers[display_label].id
        diarization_entries = diarization_data["speakers"]
    else:
        speaker_map = {}
        diarization_entries = []
        if not existing_speakers:
            display_label = "说话人 A"
            sp = Speaker(
                id=str(uuid.uuid4()),
                interview_id=interview_id,
                chunk_id=chunk_id,
                label=display_label,
                color=colors[0],
            )
            db.add(sp)
            db.flush()
            existing_speakers[display_label] = sp

    created = 0
    for i, sent in enumerate(sentences_with_meta):
        ts = timestamps[i] if i < len(timestamps) else (0.0, 0.0)
        abs_start = chunk_global_start + ts[0]
        abs_end = chunk_global_start + ts[1]
        
        speaker_id = None
        if diarization_entries:
            best_speaker = None
            best_overlap = 0.0
            
            for entry in diarization_entries:
                entry_start = chunk_global_start + entry["start"]
                entry_end = chunk_global_start + entry["end"]
                
                overlap_start = max(abs_start, entry_start)
                overlap_end = min(abs_end, entry_end)
                overlap = max(0, overlap_end - overlap_start)
                
                if overlap > best_overlap:
                    best_overlap = overlap
                    best_speaker = entry["speaker"]
            
            if best_speaker:
                speaker_id = speaker_map.get(best_speaker)
        
        if not speaker_id:
            sp_list = list(existing_speakers.values())
            speaker_id = sp_list[i % len(sp_list)].id if sp_list else None

        seg = AudioSegment(
            id=str(uuid.uuid4()),
            interview_id=interview_id,
            chunk_id=chunk_id,
            speaker_id=speaker_id,
            start_time=abs_start,
            end_time=abs_end,
            transcript=sent["text"],
            confidence=0.9,
            lang=sent["lang"],
            event=sent["event"],
            emotion_scores={"emotion": sent["emotion"]},
        )
        db.add(seg)
        created += 1

    db.commit()
    logger.info(f"Created {created} segments for chunk {chunk_id}")
    return created


def split_video_chunks(video_path: str, chunk_duration: float, output_dir: str, interview_hash: str):
    """Split video into chunks with H.264 transcoding for browser compatibility.
    Returns list of (file_path, global_start, global_end).
    """
    from src.utils.video_transcoder import get_optimal_encoder
    
    os.makedirs(output_dir, exist_ok=True)
    total = get_video_duration(video_path)
    chunks = []
    start = 0.0
    idx = 0
    step = chunk_duration
    
    encoder, encoder_params = get_optimal_encoder(force_cpu=True)
    logger.info(f"[split_video_chunks] Using encoder: {encoder}, preset: {encoder_params.get('preset', 'default')}")
    
    while start < total:
        end = min(start + chunk_duration, total)
        chunk_name = f"chunk_{idx:03d}.mp4"
        chunk_path = os.path.join(output_dir, chunk_name)
        
        cmd = [
            "ffmpeg", "-v", "error", "-y",
            "-ss", str(start), "-i", video_path,
            "-t", str(end - start),
        ]
        
        if encoder == "h264_nvenc":
            cmd.extend([
                "-c:v", encoder,
                "-preset", encoder_params.get("preset", "hq"),
                "-cq", encoder_params.get("cq", "23"),
            ])
        elif encoder == "h264_videotoolbox":
            cmd.extend([
                "-c:v", encoder,
                "-q:v", encoder_params.get("q:v", "65"),
            ])
        else:
            cmd.extend([
                "-c:v", encoder,
                "-preset", encoder_params.get("preset", "fast"),
                "-crf", encoder_params.get("crf", "23"),
            ])
        
        cmd.extend([
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart",
            chunk_path,
        ])
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"Chunk {idx} split failed: {result.stderr}")
            if os.path.exists(chunk_path):
                os.remove(chunk_path)
            raise RuntimeError(f"Failed to split video chunk {idx}: {result.stderr}")
        
        if not os.path.exists(chunk_path) or os.path.getsize(chunk_path) == 0:
            raise RuntimeError(f"Chunk {idx} output file is empty or missing")
        
        chunks.append((chunk_path, start, end))
        start += step
        idx += 1
    return chunks


def process_single_chunk(
    db: Session,
    chunk_id: str,
    interview_id: str,
    hf_token: Optional[str],
    config: ProcessConfig,
    global_diarization_data: Optional[dict] = None,
):
    logger.info(f"[PROCESS] process_single_chunk STARTED for chunk {chunk_id}")
    """
    Process a single chunk: audio extract → denoise → diarization → STT.
    Updates VideoChunk.status to 'review_pending' when complete.
    The db session is passed in so all updates are committed together atomically.
    """
    import soundfile as sf

    try:
        chunk = db.query(VideoChunk).filter(VideoChunk.id == chunk_id).first()
        if not chunk:
            logger.error(f"[PROCESS] Chunk {chunk_id} not found")
            return

        chunk.status = ChunkStatus.PROCESSING.value
        chunk.processing_started_at = datetime.utcnow()
        db.commit()
        logger.info(f"[PROCESS] Chunk {chunk_id} status set to PROCESSING")

        processor = AudioProcessor()
        audio_path, _ = processor.extract_audio(chunk.file_path)
        chunk.audio_path = audio_path
        db.commit()
        logger.info(f"[PROCESS] Chunk {chunk_id}: audio extracted")

        info = sf.info(audio_path)
        duration = float(info.frames) / float(info.samplerate)

        interview = db.query(Interview).filter(Interview.id == interview_id).first()
        interview.status = ProcessingStatus.PROCESSING.value
        if interview.duration is None:
            interview.duration = duration
        if chunk.global_end == 0.0:
            chunk.global_end = duration
        db.commit()

        if config.audio_denoise:
            audio_path = processor.denoise(audio_path)
            db.commit()
            logger.info(f"[PROCESS] Chunk {chunk_id}: audio denoised")

        diarization_engine_used = config.diarization_engine if config.diarization_engine else "pyannote"
        chunk.diarization_engine_used = diarization_engine_used

        funasr_spk_enabled = (diarization_engine_used == "funasr")
        
        stt_cfg = config.stt_config or STTAdvancedConfig()
        diar_cfg = config.diarization_config or DiarizationAdvancedConfig()

        if config.speaker_diarization and global_diarization_data:
            chunk.diarization_data = global_diarization_data
            logger.info(f"[PROCESS] Chunk {chunk_id}: using global diarization data")
        elif diarization_engine_used == "pyannote":
            logger.info(f"[PROCESS] Chunk {chunk_id}: running pyannote speaker diarization...")
            from src.inference.diarization.enhanced_engine import EnhancedDiarizationEngine, DiarizationConfig as DiarConfig
            diar_config = DiarConfig(
                segmentation_onset=diar_cfg.segmentation_onset,
                segmentation_duration=diar_cfg.segmentation_duration,
                min_duration_off=diar_cfg.min_duration_off,
                min_duration_on=diar_cfg.min_duration_on,
                clustering_threshold=diar_cfg.clustering_threshold,
                min_cluster_size=diar_cfg.min_cluster_size,
                gap_threshold=diar_cfg.gap_threshold,
                min_segment_duration=diar_cfg.min_segment_duration,
            )
            diarization_engine = EnhancedDiarizationEngine(
                auth_token=hf_token, 
                cache_dir=str(settings.model_cache_dir),
                config=diar_config,
            )
            speakers_data = diarization_engine.diarize(audio_path)
            chunk.diarization_data = {"speakers": speakers_data}
            logger.info(f"[PROCESS] Chunk {chunk_id}: pyannote diarization done, {len(speakers_data)} segments")
        else:
            logger.info(f"[PROCESS] Chunk {chunk_id}: FunASR speaker diarization will be done during STT")

        stt_engine_type = config.stt_engine if config.stt_engine else "faster-whisper"
        chunk.stt_engine_used = stt_engine_type
        logger.info(f"[PROCESS] Chunk {chunk_id}: using STT engine: {stt_engine_type}")
        
        raw_text = ""
        timestamp_list = []
        stt_raw_output = None
        
        if stt_engine_type == "sensevoice":
            stt = SenseVoiceEngine(
                device=None,
                cache_dir=str(settings.model_cache_dir),
                language=stt_cfg.language,
                vad_enabled=stt_cfg.vad_enabled,
                spk_enabled=funasr_spk_enabled or stt_cfg.spk_enabled,
            )
            logger.info(f"[PROCESS] Chunk {chunk_id}: loading SenseVoice model on device={stt.device} (spk_enabled={funasr_spk_enabled or stt_cfg.spk_enabled})...")
            stt.load()
            try:
                logger.info(f"[PROCESS] Chunk {chunk_id}: running SenseVoice STT...")
                
                stt_params = {
                    "input": audio_path,
                    "cache": {},
                    "language": stt_cfg.language,
                    "use_itn": stt_cfg.use_itn,
                    "batch_size_s": stt_cfg.batch_size_s,
                    "merge_vad": stt_cfg.merge_vad,
                    "merge_length_s": stt_cfg.merge_length_s,
                    "output_timestamp": True,
                }
                
                if diarization_engine_used == "funasr":
                    stt_params["spk_model"] = "cam++"
                
                res = stt.model.generate(**stt_params)
                
                if res:
                    stt_raw_output = res[0]
                    raw_text = res[0].get("text", "")
                    timestamp_list = res[0].get("timestamp", [])
                    words_data = res[0].get("words", [])
                    
                    if diarization_engine_used == "funasr" and words_data:
                        speakers_from_funasr = _extract_speakers_from_funasr(words_data)
                        if speakers_from_funasr:
                            chunk.diarization_data = {"speakers": speakers_from_funasr}
                            logger.info(f"[PROCESS] Chunk {chunk_id}: FunASR speaker diarization done, {len(speakers_from_funasr)} segments")
                
                logger.info(f"[PROCESS] Chunk {chunk_id}: SenseVoice STT done, text length: {len(raw_text)}, timestamps: {len(timestamp_list)}")
            finally:
                stt.unload()
                logger.info(f"[PROCESS] Chunk {chunk_id}: SenseVoice model unloaded")
        else:
            from src.inference.stt.engine import STTEngine
            stt = STTEngine(
                model_size=config.stt_model if config.stt_model else "large-v3-turbo",
                device="auto",
                compute_type="auto",
                cache_dir=str(settings.model_cache_dir),
                engine_type="faster-whisper",
            )
            logger.info(f"[PROCESS] Chunk {chunk_id}: loading Whisper model...")
            stt.load()
            try:
                logger.info(f"[PROCESS] Chunk {chunk_id}: running Whisper STT...")
                
                language = stt_cfg.language if stt_cfg.language != "auto" else None
                
                result = stt.transcribe(
                    audio_path,
                    language=language,
                    task="transcribe",
                    vad_filter=stt_cfg.vad_enabled,
                    word_timestamps=True,
                )
                
                raw_text = result.get("text", "")
                stt_raw_output = result
                
                segments = result.get("segments", [])
                timestamp_list = []
                for seg in segments:
                    timestamp_list.append([int(seg["start"] * 1000), int(seg["end"] * 1000)])
                
                logger.info(f"[PROCESS] Chunk {chunk_id}: Whisper STT done, text length: {len(raw_text)}, segments: {len(segments)}")
            finally:
                stt.unload()
                logger.info(f"[PROCESS] Chunk {chunk_id}: Whisper model unloaded")

        chunk.stt_raw_text = raw_text
        chunk.stt_raw_output = stt_raw_output
        db.commit()

        logger.info(f"[PROCESS] Chunk {chunk_id}: creating segments...")
        
        if stt_engine_type == "sensevoice":
            _create_segments_from_raw_text(
                db, interview_id, chunk_id, raw_text, duration,
                diarization_data=chunk.diarization_data,
                chunk_global_start=chunk.global_start,
                timestamp_list=timestamp_list,
            )
        else:
            _create_segments_from_whisper(
                db, interview_id, chunk_id, stt_raw_output,
                diarization_data=chunk.diarization_data,
                chunk_global_start=chunk.global_start,
            )
        
        logger.info(f"[PROCESS] Chunk {chunk_id}: segments created")

        chunk.status = ChunkStatus.REVIEW_PENDING.value
        chunk.review_pending_at = datetime.utcnow()

        db.commit()
        logger.info(f"[PROCESS] Chunk {chunk.chunk_index} ({chunk_id}) COMPLETED, status=review_pending")

    except Exception as e:
        logger.error(f"[PROCESS] Chunk {chunk_id} processing FAILED: {e}")
        import traceback; logger.error(traceback.format_exc())
        chunk = db.query(VideoChunk).filter(VideoChunk.id == chunk_id).first()
        if chunk:
            chunk.status = ChunkStatus.FAILED.value
            chunk.error_message = str(e)
        interview = db.query(Interview).filter(Interview.id == interview_id).first()
        if interview:
            interview.status = ProcessingStatus.FAILED.value
        db.commit()
        logger.error(f"[PROCESS] Chunk {chunk_id} marked as FAILED")


import traceback as _traceback

def start_chunk_queue(
    interview_id: str,
    config: Optional[ProcessConfig] = None,
    hf_token: Optional[str] = None,
):
    import traceback
    import sys
    import threading
    import time
    
    print(f"[QUEUE] === THREAD STARTED === interview_id={interview_id}", flush=True)
    print(f"[QUEUE] Python version: {sys.version}", flush=True)
    print(f"[QUEUE] Current thread: {threading.current_thread().name}", flush=True)
    
    logger.info(f"[QUEUE] start_chunk_queue STARTED for {interview_id}")
    
    pipeline_start_time = time.time()
    
    try:
        print("[QUEUE] Getting database session...", flush=True)
        db_gen = get_db()
        db = next(db_gen)
        print("[QUEUE] Database session obtained", flush=True)
        logger.info(f"[QUEUE] db session obtained")
    except Exception as e:
        print(f"[QUEUE] ERROR getting db session: {e}", flush=True)
        logger.error(f"[QUEUE] ERROR getting db session: {e}")
        return
    
    try:
        interview = db.query(Interview).filter(Interview.id == interview_id).first()
        if not interview:
            logger.error(f"[QUEUE] Interview {interview_id} not found")
            return
        
        saved_config = interview.processing_config
        if saved_config:
            logger.info(f"[QUEUE] Using saved config from database")
            config = ProcessConfig(**saved_config)
        elif config is None:
            config = ProcessConfig()
        
        logger.info(f"[QUEUE] config: chunk_enabled={config.chunk_enabled}, speaker_diarization={config.speaker_diarization}, audio_denoise={config.audio_denoise}")
        
        chunks = db.query(VideoChunk).filter(
            VideoChunk.interview_id == interview_id
        ).order_by(VideoChunk.chunk_index).all()
        logger.info(f"[QUEUE] Found {len(chunks)} chunks")

        global_diarization_data = None
        if config.speaker_diarization and interview and interview.file_path:
            logger.info(f"[QUEUE] Starting global diarization...")
            try:
                processor = AudioProcessor()
                full_audio, _ = processor.extract_audio(interview.file_path)
                if config.audio_denoise:
                    full_audio = processor.denoise(full_audio)
                
                diar_cfg = config.diarization_config or DiarizationAdvancedConfig()
                from src.inference.diarization.enhanced_engine import EnhancedDiarizationEngine, DiarizationConfig as DiarConfig
                diar_config = DiarConfig(
                    segmentation_onset=diar_cfg.segmentation_onset,
                    segmentation_duration=diar_cfg.segmentation_duration,
                    min_duration_off=diar_cfg.min_duration_off,
                    min_duration_on=diar_cfg.min_duration_on,
                    clustering_threshold=diar_cfg.clustering_threshold,
                    min_cluster_size=diar_cfg.min_cluster_size,
                    gap_threshold=diar_cfg.gap_threshold,
                    min_segment_duration=diar_cfg.min_segment_duration,
                )
                diarization_engine = EnhancedDiarizationEngine(
                    auth_token=hf_token, 
                    cache_dir=str(settings.model_cache_dir),
                    config=diar_config,
                )
                speakers_data = diarization_engine.diarize(full_audio)
                global_diarization_data = {"speakers": speakers_data}
                logger.info(f"Global diarization: {len(speakers_data)} entries, {len(set(s['speaker'] for s in speakers_data))} unique speakers")
            except Exception as e:
                logger.error(f"Global diarization failed: {e}")
                logger.error(traceback.format_exc())

        logger.info(f"[QUEUE] Starting chunk loop. global_diarization_data present: {global_diarization_data is not None}")

        for chunk in chunks:
            try:
                if chunk.status in (ChunkStatus.REVIEW_PENDING.value, ChunkStatus.REVIEW_COMPLETED.value):
                    logger.info(f"Chunk {chunk.chunk_index} already {chunk.status}, skipping")
                    continue
                logger.info(f"[QUEUE] Calling process_single_chunk for chunk {chunk.id}")
                process_single_chunk(db, chunk.id, interview_id, hf_token, config, global_diarization_data)
                logger.info(f"[QUEUE] process_single_chunk returned for chunk {chunk.id}")
            except Exception as e:
                logger.error(f"[QUEUE] Exception processing chunk {chunk.id}: {e}")
                logger.error(traceback.format_exc())

        interview = db.query(Interview).filter(Interview.id == interview_id).first()
        if interview:
            interview.status = ProcessingStatus.QUEUED.value
            logger.info(f"All chunks processed for interview {interview_id}, waiting for review")
        db.commit()
        
        pipeline_duration = time.time() - pipeline_start_time
        pipeline_log.log_stage_end(
            "pipeline", "整体处理流程", pipeline_duration,
            extra_info={
                "处理的块数": len(chunks),
                "总耗时": pipeline_log.format_duration(pipeline_duration)
            }
        )
    except Exception as e:
        logger.error(f"[QUEUE] start_chunk_queue failed: {e}")
        logger.error(traceback.format_exc())
    finally:
        try:
            next(db_gen)
        except StopIteration:
            pass


@router.get("/advanced-config-defaults", tags=["processing"])
async def get_advanced_config_defaults():
    """
    获取高级配置的默认值和参数说明。
    
    返回说话人分离和语音转文字的默认参数配置，以及每个参数的详细说明和影响指导。
    前端可使用此接口获取参数元数据，用于构建高级配置 UI。
    """
    from pydantic import TypeAdapter
    
    diar_schema = DiarizationAdvancedConfig.model_json_schema()
    stt_schema = STTAdvancedConfig.model_json_schema()
    
    return {
        "diarization": {
            "defaults": DiarizationAdvancedConfig().model_dump(),
            "schema": diar_schema,
        },
        "stt": {
            "defaults": STTAdvancedConfig().model_dump(),
            "schema": stt_schema,
        },
    }


@router.post("/{interview_id}/reprocess-all", response_model=TaskResponse, tags=["processing"])
async def reprocess_all_chunks(
    interview_id: str,
    db: Session = Depends(get_db),
):
    """
    重新处理所有 chunks，即使它们已经处理完毕。
    会重置所有 chunks 的状态为 pending，然后重新处理。
    """
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail=f"Interview not found")
    
    logger.info(f"[REPROCESS] Reprocessing all chunks for interview {interview_id}")
    
    if interview.status == ProcessingStatus.PROCESSING.value:
        raise HTTPException(status_code=400, detail=f"Interview is already processing")
    
    hf_token = settings.hf_token or None
    
    chunks = db.query(VideoChunk).filter(VideoChunk.interview_id == interview_id).all()
    if not chunks:
        raise HTTPException(status_code=400, detail=f"No chunks found for interview")
    
    logger.info(f"[REPROCESS] Found {len(chunks)} chunks, resetting status...")
    
    for chunk in chunks:
        chunk.status = ChunkStatus.PENDING.value
        chunk.processing_started_at = None
        chunk.review_pending_at = None
        chunk.reviewed_at = None
        chunk.error_message = None
    
    db.query(AudioSegment).filter(AudioSegment.interview_id == interview_id).delete(synchronize_session=False)
    db.query(Speaker).filter(Speaker.interview_id == interview_id).delete(synchronize_session=False)
    db.query(PendingChange).filter(PendingChange.interview_id == interview_id).delete(synchronize_session=False)
    
    interview.status = ProcessingStatus.QUEUED.value
    db.commit()
    
    logger.info(f"[REPROCESS] All chunks reset to pending, starting processing...")
    
    saved_config = interview.processing_config
    if saved_config:
        config = ProcessConfig(**saved_config)
    else:
        config = ProcessConfig()
    
    import threading
    t = threading.Thread(target=start_chunk_queue, args=(interview_id, config, hf_token))
    t.daemon = True
    t.start()
    
    return TaskResponse(
        task_id=interview_id,
        status="processing",
        message=f"Reprocessing started for {len(chunks)} chunks",
    )


@router.post("/{interview_id}/process", response_model=TaskResponse, tags=["processing"])
async def start_processing(
    interview_id: str,
    config: Optional[ProcessConfig] = None,
    db: Session = Depends(get_db),
):
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail=f"Interview not found")
    logger.info(f"[QUEUE] Start processing interview {interview_id}")
    
    if config is None:
        config = ProcessConfig()
    
    if config.diarization_config or config.stt_config:
        config_dict = config.model_dump(mode='json')
        interview.processing_config = config_dict
        db.commit()
        logger.info(f"Saved advanced config to database")
    elif not interview.processing_config:
        config_dict = config.model_dump(mode='json')
        interview.processing_config = config_dict
        db.commit()
        logger.info(f"Saved initial config to database")
    
    hf_token = settings.hf_token or None

    existing_chunks = db.query(VideoChunk).filter(VideoChunk.interview_id == interview_id).count()
    if interview.status == ProcessingStatus.PROCESSING.value:
        raise HTTPException(status_code=400, detail=f"Interview is already processing")
    if interview.status == ProcessingStatus.QUEUED.value and existing_chunks > 0:
        logger.info(f"[QUEUE] Calling start_chunk_queue directly for {interview_id}")
        import threading
        t = threading.Thread(target=start_chunk_queue, args=(interview_id, config, hf_token))
        t.daemon = True
        t.start()
        return TaskResponse(
            task_id=interview_id,
            status="processing",
            message=f"Processing started for {existing_chunks} chunks",
        )
    if interview.status == ProcessingStatus.COMPLETED.value and existing_chunks > 0:
        db.query(AudioSegment).filter(AudioSegment.interview_id == interview_id).delete(synchronize_session=False)
        db.query(VideoChunk).filter(VideoChunk.interview_id == interview_id).delete(synchronize_session=False)
        db.query(Speaker).filter(Speaker.interview_id == interview_id).delete(synchronize_session=False)
        db.query(PendingChange).filter(PendingChange.interview_id == interview_id).delete(synchronize_session=False)
        db.commit()
        logger.info(f"Cleared {existing_chunks} chunks and all related data for re-processing")
        existing_chunks = 0

    if config.chunk_enabled and interview.duration and interview.duration > config.chunk_duration:
        interview_hash = interview.id[:36]
        chunk_dir = f"data/chunks/{interview_hash}"
        os.makedirs(chunk_dir, exist_ok=True)

        chunks_info = split_video_chunks(
            interview.file_path,
            config.chunk_duration,
            chunk_dir,
            interview_hash,
        )

        interview.is_chunked = True
        interview.chunk_duration = config.chunk_duration
        interview.chunk_count = len(chunks_info)
        interview.status = ProcessingStatus.QUEUED.value
        db.commit()

        for idx, (file_path, global_start, global_end) in enumerate(chunks_info):
            chunk = VideoChunk(
                id=str(uuid.uuid4()),
                interview_id=interview_id,
                chunk_index=idx,
                file_path=file_path,
                global_start=global_start,
                global_end=global_end,
                status=ChunkStatus.PENDING.value,
            )
            db.add(chunk)
        db.commit()

        import threading
        t = threading.Thread(target=start_chunk_queue, args=(interview_id, config, hf_token))
        t.daemon = True
        t.start()
        logger.info(f"[QUEUE] Started thread for {interview_id}")

        return TaskResponse(
            task_id=interview_id,
            status="processing",
            message=f"Video split into {len(chunks_info)} chunks, processing started",
        )
    else:
        interview_hash = interview.id[:36]
        chunk_dir = f"data/chunks/{interview_hash}"
        os.makedirs(chunk_dir, exist_ok=True)

        single_path = os.path.join(chunk_dir, "chunk_000.mp4")
        if not os.path.exists(single_path):
            from src.utils.video_transcoder import transcode_video
            
            logger.info(f"Transcoding video to H.264: {single_path}")
            
            success, message = transcode_video(
                interview.file_path,
                single_path,
                use_gpu=False
            )
            
            if not success:
                logger.error(f"Transcode failed: {message}")
                raise RuntimeError(f"Video transcoding failed: {message}")
            
            logger.info(f"Transcoding complete: {single_path}")

        interview.is_chunked = False
        interview.chunk_duration = None
        interview.chunk_count = 1
        interview.status = ProcessingStatus.PROCESSING.value

        chunk = VideoChunk(
            id=str(uuid.uuid4()),
            interview_id=interview_id,
            chunk_index=0,
            file_path=single_path,
            global_start=0.0,
            global_end=interview.duration or 0.0,
            status=ChunkStatus.PENDING.value,
        )
        db.add(chunk)
        db.commit()

        import threading
        t = threading.Thread(target=start_chunk_queue, args=(interview_id, config, hf_token))
        t.daemon = True
        t.start()
        logger.info(f"[QUEUE] Started thread for {interview_id} (non-chunk)")

        return TaskResponse(
            task_id=interview_id,
            status="processing",
            message=f"Processing started for interview {interview_id}",
        )


@router.get("/{interview_id}/transcript", response_model=TranscriptResponse, tags=["processing"])
async def get_transcript(interview_id: str, db: Session = Depends(get_db)):
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Interview not found: {interview_id}",
        )

    chunks = db.query(VideoChunk).filter(VideoChunk.interview_id == interview_id).all()
    completed_chunk_ids = [c.id for c in chunks if c.status in (ChunkStatus.REVIEW_PENDING.value, ChunkStatus.REVIEW_COMPLETED.value)]

    if not completed_chunk_ids:
        return TranscriptResponse(
            interview_id=interview_id,
            speakers=[],
            segments=[],
            full_text="",
        )

    # Only return speakers that haven't been merged into another speaker
    speakers = db.query(Speaker).filter(
        Speaker.interview_id == interview_id,
        Speaker.chunk_id.in_(completed_chunk_ids),
        Speaker.merged_into == None  # Exclude merged speakers
    ).all()
    segments = (
        db.query(AudioSegment)
        .filter(
            AudioSegment.interview_id == interview_id,
            AudioSegment.chunk_id.in_(completed_chunk_ids)
        )
        .order_by(AudioSegment.start_time)
        .all()
    )

    speaker_responses = [
        SpeakerResponse(id=s.id, label=s.label, color=s.color, chunk_id=s.chunk_id)
        for s in speakers
    ]

    speaker_map = {s.id: s.label for s in speakers}

    segment_responses = []
    full_text_parts = []

    for seg in segments:
        prosody = None
        if seg.prosody:
            prosody = ProsodyResponse(**seg.prosody)

        segment_responses.append(
            SegmentResponse(
                id=seg.id,
                speaker_id=seg.speaker_id,
                speaker_label=speaker_map.get(seg.speaker_id),
                start_time=seg.start_time,
                end_time=seg.end_time,
                transcript=seg.transcript,
                confidence=seg.confidence,
                prosody=prosody,
                emotion_scores=seg.emotion_scores,
                lang=seg.lang,
                event=seg.event,
                chunk_id=seg.chunk_id,
            )
        )
        if seg.transcript:
            full_text_parts.append(seg.transcript)

    return TranscriptResponse(
        interview_id=interview_id,
        speakers=speaker_responses,
        segments=segment_responses,
        full_text="".join(full_text_parts),
    )


@router.post("/{interview_id}/process-one/{chunk_idx}", tags=["debug"])
async def process_one_chunk(
    interview_id: str,
    chunk_idx: int,
    db: Session = Depends(get_db),
):
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    
    from src.core import settings
    config = ProcessConfig()
    hf_token = settings.hf_token or None
    
    chunk = db.query(VideoChunk).filter(
        VideoChunk.interview_id == interview_id,
        VideoChunk.chunk_index == chunk_idx
    ).first()
    
    if not chunk:
        raise HTTPException(status_code=404, detail="Chunk not found")
    
    try:
        process_single_chunk(db, chunk.id, interview_id, hf_token, config, None)
        db.commit()
        return {"success": True, "chunk_id": chunk.id, "chunk_status": chunk.status, "interview_status": interview.status}
    except Exception as e:
        import traceback
        return {"success": False, "error": str(e), "trace": traceback.format_exc()}


@router.post("/{interview_id}/process-sync", tags=["debug"])
async def start_processing_sync(
    interview_id: str,
    db: Session = Depends(get_db),
):
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    
    from src.services.pipeline.stage_executor import can_run_stage
    from src.models import ChunkStatus, ProcessingStatus
    from src.core import settings
    
    config = ProcessConfig()
    hf_token = settings.hf_token or None
    
    chunks = db.query(VideoChunk).filter(
        VideoChunk.interview_id == interview_id
    ).order_by(VideoChunk.chunk_index).all()
    
    result = {"interview_status": interview.status, "chunk_count": len(chunks), "chunks": []}
    for c in chunks:
        result["chunks"].append({"id": c.id, "index": c.chunk_index, "status": c.status, "file_exists": os.path.exists(c.file_path)})
    
    try:
        import soundfile as sf
        test_chunk = chunks[0]
        processor = AudioProcessor()
        audio_path, _ = processor.extract_audio(test_chunk.file_path)
        info = sf.info(audio_path)
        result["audio_test"] = {"success": True, "duration": float(info.frames) / float(info.samplerate), "audio_path": audio_path}
    except Exception as e:
        result["audio_test"] = {"success": False, "error": str(e)}
        import traceback; result["audio_test"]["trace"] = traceback.format_exc()
    
    return result


@router.post("/{interview_id}/process-sync-all", tags=["debug"])
async def start_processing_sync_all(
    interview_id: str,
    db: Session = Depends(get_db),
):
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    from src.core import settings
    config = ProcessConfig()
    hf_token = settings.hf_token or None

    try:
        chunks = db.query(VideoChunk).filter(
            VideoChunk.interview_id == interview_id
        ).order_by(VideoChunk.chunk_index).all()

        for chunk in chunks:
            if chunk.status in (ChunkStatus.REVIEW_PENDING.value, ChunkStatus.REVIEW_COMPLETED.value):
                continue
            process_single_chunk(db, chunk.id, interview_id, hf_token, config, None)

        interview = db.query(Interview).filter(Interview.id == interview_id).first()
        if interview:
            interview.status = ProcessingStatus.COMPLETED.value
        db.commit()

        final_chunks = db.query(VideoChunk).filter(
            VideoChunk.interview_id == interview_id
        ).all()

        return {"success": True, "chunks": [{"index": c.chunk_index, "status": c.status} for c in final_chunks]}
    except Exception as e:
        import traceback
        return {"success": False, "error": str(e), "trace": traceback.format_exc()}


@router.get("/{interview_id}/progress", response_model=ProgressResponse, tags=["processing"])
async def get_progress(interview_id: str, db: Session = Depends(get_db)):
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Interview not found: {interview_id}",
        )

    progress_map = {
        ProcessingStatus.PENDING.value: 0.0,
        ProcessingStatus.PROCESSING.value: 0.5,
        ProcessingStatus.COMPLETED.value: 1.0,
        ProcessingStatus.FAILED.value: 0.0,
    }

    return ProgressResponse(
        interview_id=interview_id,
        status=ProcessingStatus(interview.status),
        progress=progress_map.get(interview.status, 0.0),
        current_stage=interview.status,
        message=interview.error_message or f"Status: {interview.status}",
    )


@router.get("/{interview_id}/emotion", response_model=EmotionAnalysisResponse, tags=["processing"])
async def get_emotion_analysis(interview_id: str, db: Session = Depends(get_db)):
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Interview not found: {interview_id}",
        )

    if interview.status != ProcessingStatus.COMPLETED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Interview processing is not completed yet",
        )

    emotion_nodes = (
        db.query(EmotionNode)
        .filter(EmotionNode.interview_id == interview_id)
        .order_by(EmotionNode.timestamp)
        .all()
    )

    emotion_labels = [n.label for n in emotion_nodes]
    emotion_dist = dict(Counter(emotion_labels))
    total = sum(emotion_dist.values()) if emotion_dist else 1
    emotion_distribution = {k: v / total for k, v in emotion_dist.items()}

    dominant_emotion = max(emotion_distribution.keys(), key=lambda k: emotion_distribution.get(k, 0)) if emotion_distribution else "neutral"  # type: ignore

    stress_signals = sum(
        1 for n in emotion_nodes if n.label in {"anxious", "fearful", "angry"}
    )
    avoidance_signals = sum(
        1 for n in emotion_nodes if n.label in {"sad", "neutral"} and n.confidence > 0.6
    )

    segments = db.query(AudioSegment).filter(AudioSegment.interview_id == interview_id).all()
    total_confidence = 0.0
    count = 0
    for seg in segments:
        if seg.emotion_scores:
            total_confidence += max(seg.emotion_scores.values())
            count += 1
    avg_confidence = total_confidence / count if count > 0 else 0.5
    confidence_score = avg_confidence

    signals: List[SignalItem] = []
    for node in emotion_nodes:
        if node.label in {"anxious", "fearful", "angry"}:
            signals.append(SignalItem(
                timestamp=node.timestamp,
                type="stress",
                intensity=node.intensity,
                indicator=f"High {node.label} emotion detected",
            ))
        if node.label == "sad" and node.intensity > 0.5:
            signals.append(SignalItem(
                timestamp=node.timestamp,
                type="avoidance",
                intensity=node.intensity,
                indicator="Low engagement signal",
            ))

    node_responses = [
        EmotionNodeResponse(
            id=n.id,
            timestamp=n.timestamp,
            source=n.source,
            label=n.label,
            intensity=n.intensity,
            confidence=n.confidence,
        )
        for n in emotion_nodes
    ]

    return EmotionAnalysisResponse(
        interview_id=interview_id,
        emotion_nodes=node_responses,
        summary=EmotionSummary(
            dominant_emotion=dominant_emotion,
            emotion_distribution=emotion_distribution,
            stress_signals=stress_signals,
            avoidance_signals=avoidance_signals,
            confidence_score=confidence_score,
        ),
        signals=signals,
    )


@router.get("/{interview_id}/timeline", response_model=TimelineResponse, tags=["processing"])
async def get_timeline(interview_id: str, db: Session = Depends(get_db)):
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Interview not found: {interview_id}",
        )

    speakers = db.query(Speaker).filter(Speaker.interview_id == interview_id).all()
    segments = (
        db.query(AudioSegment)
        .filter(AudioSegment.interview_id == interview_id)
        .order_by(AudioSegment.start_time)
        .all()
    )
    keyframes = (
        db.query(Keyframe)
        .filter(Keyframe.interview_id == interview_id)
        .order_by(Keyframe.timestamp)
        .all()
    )
    face_frames = (
        db.query(FaceFrame)
        .filter(FaceFrame.interview_id == interview_id)
        .order_by(FaceFrame.timestamp)
        .all()
    )
    emotion_nodes = (
        db.query(EmotionNode)
        .filter(EmotionNode.interview_id == interview_id)
        .order_by(EmotionNode.timestamp)
        .all()
    )

    speaker_responses = [
        SpeakerResponse(id=s.id, label=s.label, color=s.color, chunk_id=s.chunk_id)
        for s in speakers
    ]

    segment_responses = []
    for seg in segments:
        prosody = None
        if seg.prosody:
            prosody = ProsodyResponse(**seg.prosody)
        segment_responses.append(
            SegmentResponse(
                id=seg.id,
                speaker_id=seg.speaker_id,
                start_time=seg.start_time,
                end_time=seg.end_time,
                transcript=seg.transcript,
                confidence=seg.confidence,
                prosody=prosody,
                emotion_scores=seg.emotion_scores,
                chunk_id=seg.chunk_id,
            )
        )

    face_responses = [
        FaceFrameResponse(
            id=f.id,
            timestamp=f.timestamp,
            frame_path=f.frame_path,
            face_bbox=f.face_bbox,
            action_units=f.action_units,
            emotion_scores=f.emotion_scores,
        )
        for f in face_frames
    ]

    emotion_responses = [
        EmotionNodeResponse(
            id=n.id,
            timestamp=n.timestamp,
            source=n.source,
            label=n.label,
            intensity=n.intensity,
            confidence=n.confidence,
        )
        for n in emotion_nodes
    ]

    return TimelineResponse(
        interview_id=interview_id,
        duration=interview.duration or 0.0,
        speakers=speaker_responses,
        segments=segment_responses,
        keyframes=[KeyframeResponse.model_validate(kf) for kf in keyframes],
        face_frames=face_responses,
        emotion_nodes=emotion_responses,
    )


@router.get("/{interview_id}/keyframes", response_model=List[KeyframeResponse], tags=["processing"])
async def get_keyframes(interview_id: str, db: Session = Depends(get_db)):
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Interview not found: {interview_id}",
        )

    keyframes = (
        db.query(Keyframe)
        .filter(Keyframe.interview_id == interview_id)
        .order_by(Keyframe.timestamp)
        .all()
    )

    return [KeyframeResponse.model_validate(kf) for kf in keyframes]


@router.get("/{interview_id}/report", response_model=ReportResponse, tags=["processing"])
async def get_report(interview_id: str, db: Session = Depends(get_db)):
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Interview not found: {interview_id}",
        )

    if interview.status != ProcessingStatus.COMPLETED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Interview processing is not completed yet",
        )

    keyframes = (
        db.query(Keyframe)
        .filter(Keyframe.interview_id == interview_id)
        .order_by(Keyframe.timestamp)
        .all()
    )
    segments = (
        db.query(AudioSegment)
        .filter(AudioSegment.interview_id == interview_id)
        .order_by(AudioSegment.start_time)
        .all()
    )
    emotion_nodes = (
        db.query(EmotionNode)
        .filter(EmotionNode.interview_id == interview_id)
        .order_by(EmotionNode.timestamp)
        .all()
    )
    face_frames = db.query(FaceFrame).filter(FaceFrame.interview_id == interview_id).all()

    full_text_parts = [s.transcript for s in segments if s.transcript]
    transcript_text = "".join(full_text_parts)

    emotion_labels = [n.label for n in emotion_nodes]
    emotion_dist = dict(Counter(emotion_labels))
    total = sum(emotion_dist.values()) if emotion_dist else 1
    emotion_distribution = {k: round(v / total, 4) for k, v in emotion_dist.items()}

    stress_signals = [
        {"timestamp": n.timestamp, "type": "stress", "label": n.label, "intensity": n.intensity}
        for n in emotion_nodes if n.label in {"anxious", "fearful", "angry"}
    ]

    key_moments = []
    for node in emotion_nodes:
        if node.intensity > 0.6:
            key_moments.append({
                "timestamp": node.timestamp,
                "type": "high_intensity",
                "label": node.label,
                "intensity": node.intensity,
                "source": node.source,
            })

    prosody_issues = []
    for seg in segments:
        if seg.prosody:
            if seg.prosody.get("pause_ratio", 0) > 0.4:
                prosody_issues.append({
                    "timestamp": (seg.start_time + seg.end_time) / 2,
                    "type": "long_pause",
                    "value": seg.prosody["pause_ratio"],
                })
            if seg.prosody.get("filler_count", 0) > 3:
                prosody_issues.append({
                    "timestamp": (seg.start_time + seg.end_time) / 2,
                    "type": "high_filler",
                    "value": seg.prosody["filler_count"],
                })

    for issue in prosody_issues:
        key_moments.append(issue)

    key_moments.sort(key=lambda x: x["timestamp"])

    stress_count = sum(1 for n in emotion_nodes if n.label in {"anxious", "fearful", "angry"})
    avoidance_count = sum(1 for n in emotion_nodes if n.label in {"sad", "neutral"} and n.confidence > 0.6)

    return ReportResponse(
        interview_id=interview_id,
        metadata={
            "filename": interview.filename,
            "duration": interview.duration,
            "segment_count": len(segments),
            "speaker_count": db.query(Speaker).filter(Speaker.interview_id == interview_id).count(),
            "keyframe_count": len(keyframes),
            "face_frame_count": len(face_frames),
            "emotion_node_count": len(emotion_nodes),
        },
        transcript=transcript_text,
        emotion_summary={
            "dominant_emotion": max(emotion_distribution.keys(), key=lambda k: emotion_distribution.get(k, 0)) if emotion_distribution else "neutral",  # type: ignore
            "distribution": emotion_distribution,
            "stress_signal_count": stress_count,
            "avoidance_signal_count": avoidance_count,
        },
        signals=stress_signals,
        key_moments=key_moments,
    )


@router.get("/{interview_id}/report/download", tags=["processing"])
async def download_report(interview_id: str, db: Session = Depends(get_db)):
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Interview not found: {interview_id}",
        )

    if interview.status != ProcessingStatus.COMPLETED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Interview processing is not completed yet",
        )

    keyframes = (
        db.query(Keyframe)
        .filter(Keyframe.interview_id == interview_id)
        .order_by(Keyframe.timestamp)
        .all()
    )
    segments = (
        db.query(AudioSegment)
        .filter(AudioSegment.interview_id == interview_id)
        .order_by(AudioSegment.start_time)
        .all()
    )
    emotion_nodes = (
        db.query(EmotionNode)
        .filter(EmotionNode.interview_id == interview_id)
        .order_by(EmotionNode.timestamp)
        .all()
    )
    face_frames = db.query(FaceFrame).filter(FaceFrame.interview_id == interview_id).all()

    full_text_parts = [s.transcript for s in segments if s.transcript]
    transcript_text = "".join(full_text_parts)

    emotion_labels = [n.label for n in emotion_nodes]
    emotion_dist = dict(Counter(emotion_labels))
    total = sum(emotion_dist.values()) if emotion_dist else 1
    emotion_distribution = {k: round(v / total, 4) for k, v in emotion_dist.items()}

    stress_signals = [
        {"timestamp": n.timestamp, "type": "stress", "label": n.label, "intensity": n.intensity}
        for n in emotion_nodes if n.label in {"anxious", "fearful", "angry"}
    ]

    key_moments = []
    for node in emotion_nodes:
        if node.intensity > 0.6:
            key_moments.append({
                "timestamp": node.timestamp,
                "type": "high_intensity",
                "label": node.label,
                "intensity": node.intensity,
                "source": node.source,
            })

    prosody_issues = []
    for seg in segments:
        if seg.prosody:
            if seg.prosody.get("pause_ratio", 0) > 0.4:
                prosody_issues.append({
                    "timestamp": (seg.start_time + seg.end_time) / 2,
                    "type": "long_pause",
                    "value": seg.prosody["pause_ratio"],
                })
            if seg.prosody.get("filler_count", 0) > 3:
                prosody_issues.append({
                    "timestamp": (seg.start_time + seg.end_time) / 2,
                    "type": "high_filler",
                    "value": seg.prosody["filler_count"],
                })

    for issue in prosody_issues:
        key_moments.append(issue)
    key_moments.sort(key=lambda x: x["timestamp"])

    stress_count = sum(1 for n in emotion_nodes if n.label in {"anxious", "fearful", "angry"})
    avoidance_count = sum(1 for n in emotion_nodes if n.label in {"sad", "neutral"} and n.confidence > 0.6)

    report_data = {
        "metadata": {
            "filename": interview.filename,
            "duration": interview.duration,
            "segment_count": len(segments),
            "speaker_count": db.query(Speaker).filter(Speaker.interview_id == interview_id).count(),
            "keyframe_count": len(keyframes),
            "face_frame_count": len(face_frames),
            "emotion_node_count": len(emotion_nodes),
        },
        "transcript": transcript_text,
        "emotion_summary": {
            "dominant_emotion": max(emotion_distribution.keys(), key=lambda k: emotion_distribution.get(k, 0)) if emotion_distribution else "neutral",  # type: ignore
            "distribution": emotion_distribution,
            "stress_signal_count": stress_count,
            "avoidance_signal_count": avoidance_count,
        },
        "signals": stress_signals,
        "key_moments": key_moments,
    }

    pdf_bytes = generate_report(report_data)

    filename = f"report_{interview_id[:8]}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
