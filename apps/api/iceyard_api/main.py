import time
import uuid
from collections.abc import Callable
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from iceyard_api.api.v1.router import router as api_router
from iceyard_api.auth.service import AuthService
from iceyard_api.core.config import get_settings
from iceyard_api.core.logging import configure_logging
from iceyard_api.db.base import Base
from iceyard_api.db.session import SessionLocal, engine

settings = get_settings()
configure_logging(settings.log_level)
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
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
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_context(request: Request, call_next: Callable[[Request], object]) -> Response:
    request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = round((time.perf_counter() - start) * 1000, 2)
    response.headers["x-request-id"] = request_id
    logger.info(
        "request.complete",
        request_id=request_id,
        method=request.method,
        path=request.url.path,
        status=response.status_code,
        duration_ms=duration_ms,
    )
    return response


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
