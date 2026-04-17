from typing import Optional, Union, Dict, Any
from datetime import datetime
from enum import Enum

from fastapi import HTTPException, status


class ErrorCode(str, Enum):
    INTERVIEW_NOT_FOUND = "INTERVIEW_NOT_FOUND"
    SPEAKER_NOT_FOUND = "SPEAKER_NOT_FOUND"
    SEGMENT_NOT_FOUND = "SEGMENT_NOT_FOUND"
    VIDEO_NOT_FOUND = "VIDEO_NOT_FOUND"
    FILE_NOT_FOUND = "FILE_NOT_FOUND"
    
    MODEL_LOAD_ERROR = "MODEL_LOAD_ERROR"
    MODEL_NOT_FOUND = "MODEL_NOT_FOUND"
    MODEL_DOWNLOAD_ERROR = "MODEL_DOWNLOAD_ERROR"
    
    VIDEO_PROCESSING_ERROR = "VIDEO_PROCESSING_ERROR"
    AUDIO_PROCESSING_ERROR = "AUDIO_PROCESSING_ERROR"
    STT_PROCESSING_ERROR = "STT_PROCESSING_ERROR"
    DIARIZATION_ERROR = "DIARIZATION_ERROR"
    EMOTION_ANALYSIS_ERROR = "EMOTION_ANALYSIS_ERROR"
    FACE_ANALYSIS_ERROR = "FACE_ANALYSIS_ERROR"
    
    VALIDATION_ERROR = "VALIDATION_ERROR"
    FILE_SIZE_ERROR = "FILE_SIZE_ERROR"
    FILE_TYPE_ERROR = "FILE_TYPE_ERROR"
    
    GPU_ERROR = "GPU_ERROR"
    GPU_OUT_OF_MEMORY = "GPU_OUT_OF_MEMORY"
    
    PIPELINE_ERROR = "PIPELINE_ERROR"
    STAGE_ERROR = "STAGE_ERROR"
    
    INTERNAL_ERROR = "INTERNAL_ERROR"


class InterviewAIException(Exception):
    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.INTERNAL_ERROR,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail: Optional[Union[Dict[str, Any], list]] = None,
    ):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.detail = detail or {}
        self.timestamp = datetime.utcnow().isoformat()
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error_code": self.error_code.value,
            "message": self.message,
            "detail": self.detail,
            "timestamp": self.timestamp,
        }


class NotFoundError(InterviewAIException):
    def __init__(self, resource: str, identifier: str):
        super().__init__(
            message=f"{resource} not found: {identifier}",
            error_code=ErrorCode.INTERVIEW_NOT_FOUND,
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"resource": resource, "identifier": identifier},
        )


class VideoNotFoundError(InterviewAIException):
    def __init__(self, interview_id: str):
        super().__init__(
            message=f"Video file not found for interview: {interview_id}",
            error_code=ErrorCode.VIDEO_NOT_FOUND,
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"interview_id": interview_id},
        )


class ProcessingError(InterviewAIException):
    def __init__(
        self,
        message: str,
        stage: Optional[str] = None,
        error_code: ErrorCode = ErrorCode.PIPELINE_ERROR,
    ):
        super().__init__(
            message=f"Processing error: {message}",
            error_code=error_code,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"stage": stage} if stage else {},
        )


class VideoProcessingError(ProcessingError):
    def __init__(self, message: str, interview_id: Optional[str] = None):
        super().__init__(
            message=message,
            stage="video_processing",
            error_code=ErrorCode.VIDEO_PROCESSING_ERROR,
        )
        self.detail["interview_id"] = interview_id


class AudioProcessingError(ProcessingError):
    def __init__(self, message: str, interview_id: Optional[str] = None):
        super().__init__(
            message=message,
            stage="audio_processing",
            error_code=ErrorCode.AUDIO_PROCESSING_ERROR,
        )
        self.detail["interview_id"] = interview_id


class STTError(ProcessingError):
    def __init__(self, message: str, interview_id: Optional[str] = None):
        super().__init__(
            message=message,
            stage="stt",
            error_code=ErrorCode.STT_PROCESSING_ERROR,
        )
        self.detail["interview_id"] = interview_id


class DiarizationError(ProcessingError):
    def __init__(self, message: str, interview_id: Optional[str] = None):
        super().__init__(
            message=message,
            stage="diarization",
            error_code=ErrorCode.DIARIZATION_ERROR,
        )
        self.detail["interview_id"] = interview_id


class EmotionAnalysisError(ProcessingError):
    def __init__(self, message: str, interview_id: Optional[str] = None):
        super().__init__(
            message=message,
            stage="emotion_analysis",
            error_code=ErrorCode.EMOTION_ANALYSIS_ERROR,
        )
        self.detail["interview_id"] = interview_id


class FaceAnalysisError(ProcessingError):
    def __init__(self, message: str, interview_id: Optional[str] = None):
        super().__init__(
            message=message,
            stage="face_analysis",
            error_code=ErrorCode.FACE_ANALYSIS_ERROR,
        )
        self.detail["interview_id"] = interview_id


class ValidationError(InterviewAIException):
    def __init__(self, message: str, field: Optional[str] = None):
        super().__init__(
            message=f"Validation error: {message}",
            error_code=ErrorCode.VALIDATION_ERROR,
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"field": field} if field else {},
        )


class FileSizeError(InterviewAIException):
    def __init__(self, size: int, max_size: int):
        super().__init__(
            message=f"File size {size} exceeds maximum {max_size}",
            error_code=ErrorCode.FILE_SIZE_ERROR,
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={"size": size, "max_size": max_size},
        )


class FileTypeError(InterviewAIException):
    def __init__(self, file_type: str, allowed_types: list):
        super().__init__(
            message=f"File type '{file_type}' not allowed",
            error_code=ErrorCode.FILE_TYPE_ERROR,
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"file_type": file_type, "allowed_types": allowed_types},
        )


class ModelNotFoundError(InterviewAIException):
    def __init__(self, model_name: str):
        super().__init__(
            message=f"Model not found: {model_name}",
            error_code=ErrorCode.MODEL_NOT_FOUND,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"model": model_name},
        )


class ModelLoadError(InterviewAIException):
    def __init__(self, model_name: str, reason: str):
        super().__init__(
            message=f"Failed to load model {model_name}: {reason}",
            error_code=ErrorCode.MODEL_LOAD_ERROR,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"model": model_name, "reason": reason},
        )


class ModelDownloadError(InterviewAIException):
    def __init__(self, model_name: str, reason: str):
        super().__init__(
            message=f"Failed to download model {model_name}: {reason}",
            error_code=ErrorCode.MODEL_DOWNLOAD_ERROR,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"model": model_name, "reason": reason},
        )


class GPUError(InterviewAIException):
    def __init__(self, message: str, gpu_id: Optional[int] = None):
        super().__init__(
            message=f"GPU error: {message}",
            error_code=ErrorCode.GPU_ERROR,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"gpu_id": gpu_id} if gpu_id is not None else {},
        )


class GPUOutOfMemoryError(InterviewAIException):
    def __init__(self, requested: Optional[int] = None, available: Optional[int] = None):
        super().__init__(
            message="GPU out of memory",
            error_code=ErrorCode.GPU_OUT_OF_MEMORY,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"requested_mb": requested, "available_mb": available},
        )


class StageError(InterviewAIException):
    def __init__(
        self,
        stage_name: str,
        message: str,
        interview_id: Optional[str] = None,
    ):
        super().__init__(
            message=f"Stage '{stage_name}' error: {message}",
            error_code=ErrorCode.STAGE_ERROR,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "stage": stage_name,
                "interview_id": interview_id,
            },
        )


def raise_http_exception(error: InterviewAIException) -> None:
    raise HTTPException(
        status_code=error.status_code,
        detail=error.to_dict(),
        headers={
            "X-Error-Code": error.error_code.value,
            "X-Error": error.message,
        },
    )
