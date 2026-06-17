import secrets
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import RequestResponseEndpoint

from iceyard_api.api.v1.router import router as api_router
from iceyard_api.auth.service import AuthService
from iceyard_api.core.config import get_settings
from iceyard_api.core.logging import configure_logging
from iceyard_api.db.base import Base
from iceyard_api.db.schema_sync import reconcile_schema
from iceyard_api.db.session import SessionLocal, engine

settings = get_settings()
configure_logging(settings.log_level)
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    Base.metadata.create_all(bind=engine)
    reconcile_schema(engine)
    with SessionLocal() as session:
        default_admin = AuthService(session, settings).ensure_default_admin()
        session.commit()
        if default_admin:
            logger.info("auth.default_admin.ready", username=default_admin.username)
    yield


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=settings.effective_cors_origin_regex(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
# Pre-session endpoints cannot carry a CSRF token yet.
CSRF_EXEMPT_PATHS = {
    "/api/v1/auth/login",
    "/api/v1/auth/bootstrap",
    "/api/v1/auth/csrf",
}
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
}


def _csrf_blocked(request: Request) -> bool:
    """Double-submit CSRF check for cookie-authenticated, state-changing requests.

    Bearer-token requests (SPA/CLI/Terraform) are inherently CSRF-safe because the
    Authorization header cannot be set cross-site, so they are exempt. Only requests
    that authenticate via the session cookie must present a matching CSRF token.
    """
    if request.method not in UNSAFE_METHODS:
        return False
    if request.url.path in CSRF_EXEMPT_PATHS or not request.url.path.startswith("/api/"):
        return False
    authorization = request.headers.get("authorization", "")
    if authorization.lower().startswith("bearer "):
        return False
    session_cookie = request.cookies.get("iceyard_session")
    if not session_cookie:
        return False  # unauthenticated; the route will return 401
    csrf_cookie = request.cookies.get("iceyard_csrf")
    csrf_header = request.headers.get("x-csrf-token")
    return not (csrf_cookie and csrf_header and secrets.compare_digest(csrf_cookie, csrf_header))


@app.middleware("http")
async def request_context(request: Request, call_next: RequestResponseEndpoint) -> Response:
    correlation_id = (
        request.headers.get("x-correlation-id")
        or request.headers.get("x-request-id")
        or str(uuid.uuid4())
    )
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=correlation_id)
    start = time.perf_counter()
    try:
        if _csrf_blocked(request):
            logger.warning("request.csrf_blocked", path=request.url.path, method=request.method)
            response: Response = JSONResponse(
                status_code=403, content={"detail": "Missing or invalid CSRF token."}
            )
        else:
            response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        response.headers["x-request-id"] = correlation_id
        response.headers["x-correlation-id"] = correlation_id
        for header, value in SECURITY_HEADERS.items():
            response.headers.setdefault(header, value)
        if settings.secure_cookies:
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        logger.info(
            "request.complete",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=duration_ms,
        )
        return response
    finally:
        structlog.contextvars.clear_contextvars()


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz")
def readyz() -> dict[str, str]:
    return {"status": "ready"}


@app.get("/metrics")
def metrics() -> dict[str, str]:
    return {"status": "not_configured"}


app.include_router(api_router)
