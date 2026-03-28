import uuid
import os
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass

import numpy as np
from sqlalchemy.orm import Session

from src.models import Interview, Speaker, AudioSegment, FaceFrame, EmotionNode, Keyframe, ProcessingStatus
from src.services.audio.processor import AudioProcessor
from src.services.audio.prosody import ProsodyAnalyzer
from src.services.video.keyframe import KeyframeExtractor
from src.inference.stt.engine import STTEngine
from src.inference.diarization.engine import DiarizationEngine
from src.inference.emotion.engine import VoiceEmotionEngine
from src.inference.face.engine import FaceAnalysisEngine
from src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ProcessingProgress:
    interview_id: str
    stage: str
    progress: float
    message: str


class InterviewProcessor:
    def __init__(
        self,
        db: Session,
        interview_id: str,
        hf_token: Optional[str] = None,
        stt_model: str = "large-v3-turbo",
        language: str = "zh",
        stt_engine_type: str = "faster-whisper",
        enable_denoise: bool = True,
        enable_diarization: bool = True,
        enable_prosody: bool = True,
        enable_emotion: bool = True,
        enable_face: bool = True,
        enable_keyframes: bool = True,
        face_sample_rate: float = 2.0,
        callback: Optional[Callable[[ProcessingProgress], None]] = None,
    ):
        self.db = db
        self.interview_id = interview_id
        self.hf_token = hf_token
        self.stt_model = stt_model
        self.language = language
        self.enable_denoise = enable_denoise
        self.enable_diarization = enable_diarization
        self.enable_prosody = enable_prosody
        self.enable_emotion = enable_emotion
        self.enable_face = enable_face
        self.enable_keyframes = enable_keyframes
        self.face_sample_rate = face_sample_rate
        self.callback = callback

        self.audio_processor = AudioProcessor()
        self.stt_engine = STTEngine(
            model_size=stt_model,
            engine_type=stt_engine_type,
        )
        self.diarization_engine = DiarizationEngine(auth_token=hf_token)
        self.prosody_analyzer = ProsodyAnalyzer()
        self.emotion_engine = VoiceEmotionEngine()
        self.face_engine = FaceAnalysisEngine()
        self.keyframe_extractor = KeyframeExtractor()

        self.temp_files: List[str] = []
        self.raw_audio: Optional[np.ndarray] = None
        self.raw_audio_sr: Optional[int] = None

    def _update_status(self, status: str, error_message: Optional[str] = None):
        interview = self.db.query(Interview).filter(Interview.id == self.interview_id).first()
        if interview:
            interview.status = status
            if error_message:
                interview.error_message = error_message
            self.db.commit()

    def _report_progress(self, stage: str, progress: float, message: str):
        if self.callback:
            self.callback(ProcessingProgress(
                interview_id=self.interview_id,
                stage=stage,
                progress=progress,
                message=message,
            ))

    def process(self) -> Dict[str, Any]:
        interview = self.db.query(Interview).filter(Interview.id == self.interview_id).first()
        if not interview:
            raise ValueError(f"Interview not found: {self.interview_id}")

        logger.info(f"[{self.interview_id}] Starting processing pipeline")
        logger.info(f"[{self.interview_id}] Video: {interview.file_path}")

        self._update_status(ProcessingStatus.PROCESSING.value)
        self._report_progress("init", 0.0, "开始处理...")

        try:
            audio_path = self._extract_audio(interview.file_path)
            logger.info(f"[{self.interview_id}] Audio extracted: {audio_path}")
            self._report_progress("audio_extraction", 0.05, "音频提取完成")

            if self.enable_denoise:
                logger.info(f"[{self.interview_id}] Starting denoising...")
                audio_path = self._denoise_audio(audio_path)
                logger.info(f"[{self.interview_id}] Denoising complete")
                self._report_progress("denoising", 0.1, "降噪完成")

            duration = self.audio_processor.get_duration(audio_path)
            interview.duration = duration
            self.db.commit()

            self.raw_audio, self.raw_audio_sr = self.audio_processor.load_audio(audio_path)

            speakers = []
            if self.enable_diarization:
                logger.info(f"[{self.interview_id}] Starting diarization...")
                speakers = self._diarize_speakers(audio_path)
                logger.info(f"[{self.interview_id}] Diarization complete: {len(speakers)} segments")
                self._report_progress("diarization", 0.2, "说话人分离完成")

            self._report_progress("stt", 0.25, "开始语音转文字...")
            logger.info(f"[{self.interview_id}] Starting STT ({self.stt_engine.engine_type})...")
            transcript_result = self._transcribe(audio_path)
            logger.info(f"[{self.interview_id}] STT complete: {len(transcript_result.get('segments', []))} segments")
            self._report_progress("stt", 0.4, "转录完成")

            segments = transcript_result.get("segments", [])

            if self.enable_prosody:
                self._report_progress("prosody", 0.45, "开始韵律分析...")
                logger.info(f"[{self.interview_id}] Starting prosody analysis...")
                segments = self._analyze_prosody(segments)
                logger.info(f"[{self.interview_id}] Prosody analysis complete")
                self._report_progress("prosody", 0.5, "韵律分析完成")

            if self.enable_emotion:
                self._report_progress("emotion", 0.52, "开始情绪识别...")
                logger.info(f"[{self.interview_id}] Starting emotion recognition...")
                segments = self._analyze_emotion(segments)
                logger.info(f"[{self.interview_id}] Emotion recognition complete")
                self._report_progress("emotion", 0.57, "情绪识别完成")

            if self.enable_face:
                self._report_progress("face_analysis", 0.6, "开始人脸分析...")
                logger.info(f"[{self.interview_id}] Starting face analysis...")
                try:
                    self._analyze_faces(interview)
                    logger.info(f"[{self.interview_id}] Face analysis complete")
                    self._report_progress("face_analysis", 0.75, "人脸分析完成")
                except Exception as e:
                    logger.warning(f"[{self.interview_id}] Face analysis skipped: {e}")
                    self._report_progress("face_analysis", 0.75, f"人脸分析跳过: {str(e)}")

            if self.enable_keyframes:
                self._report_progress("keyframes", 0.78, "开始关键帧提取...")
                logger.info(f"[{self.interview_id}] Starting keyframe extraction...")
                try:
                    self._extract_keyframes(interview)
                    logger.info(f"[{self.interview_id}] Keyframe extraction complete")
                    self._report_progress("keyframes", 0.83, "关键帧提取完成")
                except Exception as e:
                    logger.warning(f"[{self.interview_id}] Keyframe extraction skipped: {e}")
                    self._report_progress("keyframes", 0.83, f"关键帧提取跳过: {str(e)}")

            if self.enable_emotion:
                self._report_progress("emotion_fusion", 0.85, "开始情绪融合...")
                logger.info(f"[{self.interview_id}] Starting emotion fusion...")
                self._fuse_emotions(interview)
                logger.info(f"[{self.interview_id}] Emotion fusion complete")
                self._report_progress("emotion_fusion", 0.92, "情绪融合完成")

            self._save_results(interview, speakers, segments, audio_path)
            self._report_progress("complete", 1.0, "处理完成")
            logger.info(f"[{self.interview_id}] Processing COMPLETED")

            self._update_status(ProcessingStatus.COMPLETED.value)
            self._cleanup()

            return {
                "status": "completed",
                "duration": duration,
                "speakers": len(speakers),
                "segments": len(segments),
            }

        except Exception as e:
            import traceback
            logger.error(f"[{self.interview_id}] Processing FAILED: {e}")
            logger.error(traceback.format_exc())
            self._update_status(ProcessingStatus.FAILED.value, str(e))
            self._cleanup()
            raise

    def _extract_audio(self, video_path: str) -> str:
        audio_path, _ = self.audio_processor.extract_audio(video_path)
        self.temp_files.append(audio_path)
        return audio_path

    def _denoise_audio(self, audio_path: str) -> str:
        denoised_path = self.audio_processor.denoise(audio_path)
        self.temp_files.append(denoised_path)
        return denoised_path

    def _diarize_speakers(self, audio_path: str) -> List[Dict[str, Any]]:
        return self.diarization_engine.diarize(audio_path)

    def _transcribe(self, audio_path: str) -> Dict[str, Any]:
        return self.stt_engine.transcribe(
            audio_path,
            language=self.language,
            word_timestamps=True,
        )

    def _save_results(
        self,
        interview: Interview,
        speakers_data: List[Dict[str, Any]],
        segments: List[Dict[str, Any]],
        audio_path: str,
    ):
        speaker_order = list(dict.fromkeys(s["speaker"] for s in speakers_data))
        speaker_map = {}
        for i, speaker_label in enumerate(speaker_order):
            speaker = Speaker(
                id=str(uuid.uuid4()),
                interview_id=interview.id,
                label=f"说话人 {chr(65 + i)}",
                color=self._get_speaker_color(i),
            )
            self.db.add(speaker)
            self.db.flush()
            speaker_map[speaker_label] = speaker.id

        for segment in segments:
            speaker_label = self._find_speaker(segment["start"], segment["end"], speakers_data)
            speaker_id = speaker_map.get(speaker_label) if speaker_label else None

            audio_segment = AudioSegment(
                id=str(uuid.uuid4()),
                interview_id=interview.id,
                speaker_id=speaker_id,
                start_time=segment["start"],
                end_time=segment["end"],
                transcript=segment.get("text", ""),
                confidence=0.9,
                prosody=segment.get("prosody"),
                emotion_scores=segment.get("emotion", {}).get("emotion_scores"),
                lang=segment.get("lang"),
                event=segment.get("event"),
            )
            self.db.add(audio_segment)

        self.db.commit()

    def _find_speaker(
        self,
        start: float,
        end: float,
        speakers_data: List[Dict[str, Any]],
    ) -> Optional[str]:
        mid = (start + end) / 2
        for seg in speakers_data:
            if seg["start"] <= mid <= seg["end"]:
                return seg["speaker"]
        return None

    def _get_speaker_color(self, index: int) -> str:
        colors = ["#1890ff", "#52c41a", "#faad14", "#f5222d", "#722ed1", "#13c2c2"]
        return colors[index % len(colors)]

    def _analyze_prosody(self, segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if self.raw_audio is None or len(self.raw_audio) == 0:
            return segments
        sr = self.raw_audio_sr or 16000
        results = self.prosody_analyzer.analyze_segments(
            self.raw_audio, sr, segments
        )
        for i, seg in enumerate(segments):
            seg["prosody"] = results[i]
        return segments

    def _analyze_emotion(self, segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if self.raw_audio is None or len(self.raw_audio) == 0:
            return segments
        sr = self.raw_audio_sr or 16000
        results = self.emotion_engine.predict_segments(
            self.raw_audio, sr, segments
        )
        for i, seg in enumerate(segments):
            seg["emotion"] = results[i]
        return segments

    def _analyze_faces(self, interview: Interview) -> None:
        face_results = self.face_engine.detect_from_video(
            interview.file_path, sample_rate=self.face_sample_rate
        )
        for face_data in face_results:
            face_frame = FaceFrame(
                id=str(uuid.uuid4()),
                interview_id=interview.id,
                timestamp=face_data["timestamp"],
                landmarks=face_data.get("landmarks"),
                face_bbox=face_data.get("bbox"),
                action_units=face_data.get("action_units"),
                emotion_scores=face_data.get("emotion_scores"),
            )
            self.db.add(face_frame)
        self.db.commit()

    def _extract_keyframes(self, interview: Interview) -> None:
        keyframes = self.keyframe_extractor.detect_scenes(
            interview.file_path,
            save_frames=True,
            output_dir=None,
        )
        for kf in keyframes:
            keyframe_record = Keyframe(
                id=str(uuid.uuid4()),
                interview_id=interview.id,
                timestamp=kf.timestamp,
                frame_idx=kf.frame_idx,
                scene_len=kf.scene_len,
                frame_path=kf.frame_path,
            )
            self.db.add(keyframe_record)
        self.db.commit()

    def _fuse_emotions(self, interview: Interview) -> None:
        segments = self.db.query(AudioSegment).filter(
            AudioSegment.interview_id == interview.id
        ).all()
        face_frames = self.db.query(FaceFrame).filter(
            FaceFrame.interview_id == interview.id
        ).order_by(FaceFrame.timestamp).all()

        for seg in segments:
            if seg.emotion_scores:
                self._create_emotion_node(
                    interview.id,
                    (seg.start_time + seg.end_time) / 2,
                    "audio",
                    seg.emotion_scores,
                )

        for frame in face_frames:
            if frame.emotion_scores:
                self._create_emotion_node(
                    interview.id,
                    frame.timestamp,
                    "video",
                    frame.emotion_scores,
                )

    def _create_emotion_node(
        self, interview_id: str, timestamp: float, source: str, emotion_scores: Dict[str, float]
    ) -> None:
        if not emotion_scores:
            return
        if "emotion" in emotion_scores and len(emotion_scores) == 1:
            dominant = emotion_scores["emotion"]
            confidence = 1.0
        else:
            dominant = max(emotion_scores.keys(), key=lambda k: emotion_scores.get(k, 0))  # type: ignore
            confidence = float(emotion_scores.get(dominant, 0))
        node = EmotionNode(
            id=str(uuid.uuid4()),
            interview_id=interview_id,
            timestamp=timestamp,
            source=source,
            label=dominant,
            intensity=confidence,
            confidence=confidence,
        )
        if source == "audio":
            node.audio_emotion = emotion_scores
        else:
            node.video_emotion = emotion_scores
        self.db.add(node)

    def _cleanup(self):
        for f in self.temp_files:
            try:
                if os.path.exists(f):
                    os.unlink(f)
            except Exception:
                pass
        self.temp_files.clear()


def process_interview(
    db: Session,
    interview_id: str,
    hf_token: Optional[str] = None,
    language: str = "zh",
    stt_engine_type: str = "faster-whisper",
    enable_denoise: bool = True,
    enable_diarization: bool = True,
    enable_prosody: bool = True,
    enable_emotion: bool = True,
    enable_face: bool = True,
    enable_keyframes: bool = True,
    face_sample_rate: float = 2.0,
    callback: Optional[Callable[[ProcessingProgress], None]] = None,
) -> Dict[str, Any]:
    processor = InterviewProcessor(
        db=db,
        interview_id=interview_id,
        hf_token=hf_token,
        language=language,
        stt_engine_type=stt_engine_type,
        enable_denoise=enable_denoise,
        enable_diarization=enable_diarization,
        enable_prosody=enable_prosody,
        enable_emotion=enable_emotion,
        enable_face=enable_face,
        enable_keyframes=enable_keyframes,
        face_sample_rate=face_sample_rate,
        callback=callback,
    )
    return processor.process()
