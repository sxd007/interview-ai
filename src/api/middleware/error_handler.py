import traceback
from typing import Callable
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from src.core.exceptions import InterviewAIException, ErrorCode
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        try:
            return await call_next(request)
        except InterviewAIException as e:
            logger.error(
                f"InterviewAIException: {e.error_code.value} - {e.message}",
                extra={
                    "error_code": e.error_code.value,
                    "detail": e.detail,
                    "path": request.url.path,
                },
            )
            return JSONResponse(
                status_code=e.status_code,
                content=e.to_dict(),
                headers={
                    "X-Error-Code": e.error_code.value,
                    "X-Request-Id": request.headers.get("X-Request-Id", ""),
                },
            )
        except Exception as e:
            logger.exception(
                f"Unhandled exception: {type(e).__name__}: {str(e)}",
                extra={
                    "path": request.url.path,
                    "method": request.method,
                },
            )
            error_response = {
                "error_code": ErrorCode.INTERNAL_ERROR.value,
                "message": "An unexpected error occurred",
                "detail": {
                    "type": type(e).__name__,
                    "message": str(e),
                },
            }
            return JSONResponse(
                status_code=500,
                content=error_response,
                headers={
                    "X-Error-Code": ErrorCode.INTERNAL_ERROR.value,
                    "X-Request-Id": request.headers.get("X-Request-Id", ""),
                },
            )


def register_exception_handlers(app):
    from fastapi import HTTPException
    from fastapi.exceptions import RequestValidationError
    
    @app.exception_handler(InterviewAIException)
    async def interview_ai_exception_handler(request: Request, exc: InterviewAIException):
        logger.error(
            f"InterviewAIException: {exc.error_code.value} - {exc.message}",
            extra={
                "error_code": exc.error_code.value,
                "detail": exc.detail,
                "path": request.url.path,
            },
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.to_dict(),
            headers={
                "X-Error-Code": exc.error_code.value,
            },
        )
    
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        error_code = ErrorCode.INTERNAL_ERROR
        if exc.status_code == 404:
            error_code = ErrorCode.FILE_NOT_FOUND
        elif exc.status_code == 400:
            error_code = ErrorCode.VALIDATION_ERROR
        
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error_code": error_code.value,
                "message": str(exc.detail),
                "detail": {},
            },
            headers={
                "X-Error-Code": error_code.value,
            },
        )
    
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        errors = []
        for error in exc.errors():
            errors.append({
                "field": ".".join(str(loc) for loc in error["loc"]),
                "message": error["msg"],
                "type": error["type"],
            })
        
        return JSONResponse(
            status_code=422,
            content={
                "error_code": ErrorCode.VALIDATION_ERROR.value,
                "message": "Request validation failed",
                "detail": {"errors": errors},
            },
            headers={
                "X-Error-Code": ErrorCode.VALIDATION_ERROR.value,
            },
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        logger.exception(
            f"Unhandled exception: {type(exc).__name__}: {str(exc)}",
            extra={
                "path": request.url.path,
                "method": request.method,
            },
        )
        
        return JSONResponse(
            status_code=500,
            content={
                "error_code": ErrorCode.INTERNAL_ERROR.value,
                "message": "An unexpected error occurred",
                "detail": {
                    "type": type(exc).__name__,
                },
            },
            headers={
                "X-Error-Code": ErrorCode.INTERNAL_ERROR.value,
            },
        )
