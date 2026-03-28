from typing import Optional, Union

from fastapi import HTTPException, status


class InterviewAIException(Exception):
    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail: Optional[Union[dict, list]] = None,
    ):
        self.message = message
        self.status_code = status_code
        self.detail = detail or {"message": message}
        super().__init__(self.message)


class NotFoundError(InterviewAIException):
    def __init__(self, resource: str, identifier: str):
        super().__init__(
            message=f"{resource} not found: {identifier}",
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"resource": resource, "identifier": identifier},
        )


class ProcessingError(InterviewAIException):
    def __init__(self, message: str, stage: Optional[str] = None):
        super().__init__(
            message=f"Processing error: {message}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"stage": stage} if stage else None,
        )


class ValidationError(InterviewAIException):
    def __init__(self, message: str, field: Optional[str] = None):
        super().__init__(
            message=f"Validation error: {message}",
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"field": field} if field else None,
        )


class FileSizeError(InterviewAIException):
    def __init__(self, size: int, max_size: int):
        super().__init__(
            message=f"File size {size} exceeds maximum {max_size}",
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={"size": size, "max_size": max_size},
        )


class ModelNotFoundError(InterviewAIException):
    def __init__(self, model_name: str):
        super().__init__(
            message=f"Model not found: {model_name}",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"model": model_name},
        )


class ModelDownloadError(InterviewAIException):
    def __init__(self, model_name: str, reason: str):
        super().__init__(
            message=f"Failed to download model {model_name}: {reason}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"model": model_name, "reason": reason},
        )


def raise_http_exception(error: InterviewAIException) -> None:
    raise HTTPException(
        status_code=error.status_code,
        detail=error.detail,
        headers={"X-Error": error.message},
    )
