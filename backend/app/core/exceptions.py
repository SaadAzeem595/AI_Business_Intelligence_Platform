import logging
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class ServiceException(Exception):
    """Base exception class for business logic domain services errors."""

    def __init__(
        self,
        message: str,
        status_code: int = 400,
        code: str = "BAD_REQUEST",
        module: str = "core",
        details: dict = None
    ):
        self.message = message
        self.status_code = status_code
        self.code = code
        self.module = module
        self.details = details or {}
        super().__init__(message)


class NoDataInPeriodException(ServiceException):
    """Raised when the requested reporting period contains no observations."""

    def __init__(
        self,
        message: str = "The selected reporting period contains no data.",
        dataset_min_date: str = "",
        dataset_max_date: str = "",
        requested_start: str = "",
        requested_end: str = "",
    ):
        details = {
            "dataset_min_date": dataset_min_date,
            "dataset_max_date": dataset_max_date,
            "requested_start": requested_start,
            "requested_end": requested_end,
        }
        super().__init__(
            message=message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="NO_DATA_IN_PERIOD",
            module="reports",
            details=details
        )


def setup_exception_handlers(app: FastAPI) -> None:
    """Configures global error interception responses returning clean API envelopes."""

    @app.exception_handler(ServiceException)
    async def service_exception_handler(
        request: Request, exc: ServiceException
    ) -> JSONResponse:
        logger.warning(f"Business logic failure [{exc.code}] in module '{exc.module}': {exc.message}")
        content = {
            "error": {
                "code": exc.code,
                "message": exc.message,
                "module": exc.module,
                "details": exc.details,
            },
            "detail": exc.message,
        }
        # Also expose top-level fields for convenience
        if exc.details:
            content.update(exc.details)
        return JSONResponse(
            status_code=exc.status_code,
            content=content,
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        detail_msg = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": f"HTTP_{exc.status_code}",
                    "message": detail_msg,
                    "module": "api",
                    "details": {},
                },
                "detail": exc.detail,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        err_details = jsonable_encoder(exc.errors())
        logger.info(f"Invalid parameters submitted: {err_details}")
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Invalid request parameters.",
                    "module": "validation",
                    "details": err_details,
                },
                "detail": err_details,
            },
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        err_msg = str(exc)
        logger.error(f"Unhandled system fault occurred: {err_msg}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": f"An internal server error occurred: {err_msg}",
                    "module": "system",
                    "details": {"exception_type": type(exc).__name__},
                },
                "detail": f"An internal server error occurred: {err_msg}",
            },
        )

