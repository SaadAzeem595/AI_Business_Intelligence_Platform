import logging
import time
import uuid
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.config import settings
from app.core.cache import cache_client

logger = logging.getLogger(__name__)

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Intercepts and logs execution latency index, applies secure headers, and checks rate limits."""

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id
        start_time = time.perf_counter()

        # 1. Rate Limiting Check (bypass health/metrics probes)
        if not any(probe in request.url.path for probe in ["/health", "/ready", "/live", "/metrics"]):
            try:
                # Use client IP as identifier
                client_ip = request.client.host if request.client else "unknown"
                rate_limit_key = f"rate_limit:{client_ip}"
                
                # Check current request count in window
                current_requests = await cache_client.get(rate_limit_key)
                limit = settings.RATE_LIMIT_PER_MINUTE
                
                if current_requests is None:
                    await cache_client.set(rate_limit_key, 1, ttl=60)
                else:
                    count = int(current_requests)
                    if count >= limit:
                        logger.warning(f"Rate limit exceeded for client: {client_ip} [Path: {request.url.path}]")
                        return Response(
                            content='{"detail": "Too many requests. Rate limit exceeded."}',
                            status_code=429,
                            media_type="application/json"
                        )
                    await cache_client.set(rate_limit_key, count + 1, ttl=60)
            except Exception as e:
                logger.warning(f"Rate limiter encountered check error: {str(e)}. Proceeding (fail-open).")

        # Read and restore request body to log payload details without hanging ASGI downstream
        body_str = ""
        content_type = request.headers.get("content-type", "").lower()
        is_upload = (
            "multipart/form-data" in content_type
            or "application/octet-stream" in content_type
            or any(path in request.url.path for path in ["/datasets", "/upload", "/ingest"])
        )
        if request.method in ["POST", "PUT", "PATCH"]:
            if is_upload:
                body_str = "<Multipart file upload payload>"
            else:
                try:
                    body = await request.body()
                    async def receive():
                        return {"type": "http.request", "body": body, "more_body": False}
                    request._receive = receive
                    body_str = body.decode("utf-8", errors="ignore")
                except Exception as e:
                    body_str = f"<Could not read body: {str(e)}>"

        log_payload = f"\nRequest Payload: {body_str[:1500]}" if body_str else ""
        logger.info(
            f"Request started: {request.method} {request.url.path} [ID: {request_id}]{log_payload}"
        )

        try:
            response = await call_next(request)
            process_time = time.perf_counter() - start_time
            
            # 2. Bind response headers
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time"] = f"{process_time:.4f}s"
            
            # 3. Apply Secure Enterprise Headers
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["Content-Security-Policy"] = "frame-ancestors 'none';"
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
            response.headers["X-XSS-Protection"] = "1; mode=block"
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

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

