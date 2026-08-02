import logging
import time
import uuid
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Intercepts and logs execution latency index and binds custom UUID tracing tags."""

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id
        start_time = time.perf_counter()

        logger.info(
            f"Request started: {request.method} {request.url.path} [ID: {request_id}]"
        )

        try:
            response = await call_next(request)
            process_time = time.perf_counter() - start_time
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time"] = f"{process_time:.4f}s"

            logger.info(
                f"Request finished: {request.method} {request.url.path} "
                f"Status: {response.status_code} in {process_time:.4f}s [ID: {request_id}]"
            )
            return response
        except Exception as exc:
            process_time = time.perf_counter() - start_time
            logger.error(
                f"Request failed: {request.method} {request.url.path} "
                f"Error: {str(exc)} in {process_time:.4f}s [ID: {request_id}]",
                exc_info=True,
            )
            raise
