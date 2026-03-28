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
)
from src.models import (
    Interview, Speaker, AudioSegment, FaceFrame, Keyframe, EmotionNode,
    VideoChunk, PipelineStage, PendingChange, get_db, ProcessingStatus, StageStatus, ChunkStatus,
)
from src.services.interview import process_interview, ProcessingProgress
from src.services.report.generator import generate_report
from src.core import settings
from src.utils.logging import get_logger

logger = get_logger(__name__)

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
    """Split video into chunks. Returns list of (file_path, global_start, global_end)."""
    os.makedirs(output_dir, exist_ok=True)
    total = get_video_duration(video_path)
    chunks = []
    start = 0.0
    idx = 0
    step = chunk_duration
    while start < total:
        end = min(start + chunk_duration, total)
        chunk_name = f"chunk_{idx:03d}.mp4"
        chunk_path = os.path.join(output_dir, chunk_name)
        cmd = [
            "ffmpeg", "-v", "error", "-y",
            "-ss", str(start), "-i", video_path,
            "-t", str(end - start), "-c", "copy",
            "-avoid_negative_ts", "make_zero", chunk_path,
        ]
        subprocess.run(cmd, check=True, capture_output=True)
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

        if config.speaker_diarization and global_diarization_data:
            chunk.diarization_data = global_diarization_data
            logger.info(f"[PROCESS] Chunk {chunk_id}: using global diarization data")
        else:
            if diarization_engine_used == "pyannote":
                logger.info(f"[PROCESS] Chunk {chunk_id}: running pyannote speaker diarization...")
                diarization_engine = DiarizationEngine(auth_token=hf_token, cache_dir=str(settings.model_cache_dir))
                speakers_data = diarization_engine.diarize(audio_path)
                chunk.diarization_data = {"speakers": speakers_data}
                logger.info(f"[PROCESS] Chunk {chunk_id}: pyannote diarization done, {len(speakers_data)} segments")
            else:
                logger.info(f"[PROCESS] Chunk {chunk_id}: FunASR speaker diarization will be done during STT")

        stt = SenseVoiceEngine(
            device="cpu", 
            cache_dir=str(settings.model_cache_dir),
            spk_enabled=funasr_spk_enabled,
        )
        logger.info(f"[PROCESS] Chunk {chunk_id}: loading STT model (spk_enabled={funasr_spk_enabled})...")
        stt.load()
        raw_text = ""
        timestamp_list = []
        funasr_output = None
        try:
            logger.info(f"[PROCESS] Chunk {chunk_id}: running STT...")
            
            stt_params = {
                "input": audio_path,
                "cache": {},
                "language": "auto",
                "use_itn": True,
                "batch_size_s": 300,
                "merge_vad": True,
                "merge_length_s": 15,
                "output_timestamp": True,
            }
            
            if diarization_engine_used == "funasr":
                stt_params["spk_model"] = "cam++"
            
            res = stt.model.generate(**stt_params)
            
            if res:
                funasr_output = res[0]
                raw_text = res[0].get("text", "")
                timestamp_list = res[0].get("timestamp", [])
                words_data = res[0].get("words", [])
                
                if diarization_engine_used == "funasr" and words_data:
                    speakers_from_funasr = _extract_speakers_from_funasr(words_data)
                    if speakers_from_funasr:
                        chunk.diarization_data = {"speakers": speakers_from_funasr}
                        logger.info(f"[PROCESS] Chunk {chunk_id}: FunASR speaker diarization done, {len(speakers_from_funasr)} segments")
            
            logger.info(f"[PROCESS] Chunk {chunk_id}: STT done, text length: {len(raw_text)}, timestamps: {len(timestamp_list)}")
        finally:
            stt.unload()
            logger.info(f"[PROCESS] Chunk {chunk_id}: STT model unloaded")

        chunk.stt_raw_text = raw_text
        chunk.stt_raw_output = funasr_output
        db.commit()

        logger.info(f"[PROCESS] Chunk {chunk_id}: creating segments...")
        _create_segments_from_raw_text(
            db, interview_id, chunk_id, raw_text, duration,
            diarization_data=chunk.diarization_data,
            chunk_global_start=chunk.global_start,
            timestamp_list=timestamp_list,
        )
        logger.info(f"[PROCESS] Chunk {chunk_id}: segments created")

        chunk.status = ChunkStatus.REVIEW_PENDING.value
        chunk.review_pending_at = datetime.utcnow()

        interview = db.query(Interview).filter(Interview.id == interview_id).first()
        if interview:
            interview.status = ProcessingStatus.COMPLETED.value

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
    config: ProcessConfig,
    hf_token: Optional[str],
):
    """Background task: process chunks one by one in order."""
    import traceback
    logger.info(f"[QUEUE] start_chunk_queue STARTED for {interview_id}")
    logger.info(f"[QUEUE] config: chunk_enabled={config.chunk_enabled}, speaker_diarization={config.speaker_diarization}, audio_denoise={config.audio_denoise}")
    db_gen = get_db()
    db = next(db_gen)
    logger.info(f"[QUEUE] db session obtained")
    try:
        chunks = db.query(VideoChunk).filter(
            VideoChunk.interview_id == interview_id
        ).order_by(VideoChunk.chunk_index).all()
        logger.info(f"[QUEUE] Found {len(chunks)} chunks")

        interview = db.query(Interview).filter(Interview.id == interview_id).first()
        logger.info(f"[QUEUE] interview status={interview.status if interview else 'NOT FOUND'}, file_path={interview.file_path if interview else 'N/A'}")
        global_diarization_data = None

        if config.speaker_diarization and interview and interview.file_path:
            logger.info(f"[QUEUE] Starting global diarization...")
            try:
                processor = AudioProcessor()
                full_audio, _ = processor.extract_audio(interview.file_path)
                if config.audio_denoise:
                    full_audio = processor.denoise(full_audio)
                diarization_engine = DiarizationEngine(auth_token=hf_token, cache_dir=str(settings.model_cache_dir))
                speakers_data = diarization_engine.diarize(full_audio)
                global_diarization_data = {"speakers": speakers_data}
                logger.info(f"Global diarization: {len(speakers_data)} entries, {len(set(s['speaker'] for s in speakers_data))} unique speakers")
            except Exception as e:
                logger.error(f"Global diarization failed: {e}")
                import traceback; logger.error(traceback.format_exc())

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
            interview.status = ProcessingStatus.COMPLETED.value
            db.commit()
        logger.info(f"All chunks processed for interview {interview_id}")
    except Exception as e:
        logger.error(f"[QUEUE] start_chunk_queue failed: {e}")
        logger.error(traceback.format_exc())
    finally:
        try:
            next(db_gen)
        except StopIteration:
            pass


@router.post("/{interview_id}/process", response_model=TaskResponse, tags=["processing"])
async def start_processing(
    interview_id: str,
    config: Optional[ProcessConfig] = None,
    db: Session = Depends(get_db),
):
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail=f"Interview not found")

    if config is None:
        config = ProcessConfig()
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
            subprocess.run([
                "ffmpeg", "-v", "error", "-y",
                "-i", interview.file_path, "-c", "copy", single_path,
            ], check=True)

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
    completed_chunk_ids = [c.id for c in chunks if c.status == ChunkStatus.REVIEW_PENDING.value]

    if not completed_chunk_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No chunk has completed processing yet",
        )

    speakers = db.query(Speaker).filter(
        Speaker.interview_id == interview_id,
        Speaker.chunk_id.in_(completed_chunk_ids)
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
