"""Production-ready stateless agent for Day 12 Part 6."""
import json
import logging
import os
import signal
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import redis
import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.auth import verify_api_key
from app.config import settings
from app.cost_guard import check_budget, estimate_cost
from app.rate_limiter import check_rate_limit
from utils.mock_llm import ask as llm_ask


logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format='{"ts":"%(asctime)s","lvl":"%(levelname)s","msg":"%(message)s"}',
)
logger = logging.getLogger(__name__)

START_TIME = time.time()
IN_FLIGHT_REQUESTS = 0
IS_READY = False
IS_DRAINING = False
TOTAL_REQUESTS = 0
TOTAL_ERRORS = 0

r = redis.from_url(settings.redis_url, decode_responses=True)


def _json_log(event: str, **kwargs) -> None:
    payload = {"event": event, **kwargs}
    logger.info(json.dumps(payload, ensure_ascii=True))


def load_history(user_id: str) -> list[dict]:
    rows = r.lrange(f"history:{user_id}", 0, -1)
    history: list[dict] = []
    for row in rows:
        try:
            history.append(json.loads(row))
        except json.JSONDecodeError:
            continue
    return history


def append_history(user_id: str, role: str, content: str) -> None:
    key = f"history:{user_id}"
    message = {
        "role": role,
        "content": content,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    r.rpush(key, json.dumps(message, ensure_ascii=True))
    r.ltrim(key, -settings.max_history_messages, -1)
    r.expire(key, settings.history_ttl_seconds)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global IS_READY
    try:
        r.ping()
    except redis.RedisError as exc:
        logger.exception("Redis unavailable at startup")
        raise RuntimeError("Redis is required for stateless mode") from exc

    _json_log(
        "startup",
        app=settings.app_name,
        version=settings.app_version,
        env=settings.environment,
    )
    IS_READY = True
    yield
    IS_READY = False
    _json_log("shutdown")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "X-API-Key"],
)


@app.middleware("http")
async def request_middleware(request: Request, call_next):
    global IN_FLIGHT_REQUESTS, TOTAL_ERRORS, TOTAL_REQUESTS
    TOTAL_REQUESTS += 1

    if IS_DRAINING and request.url.path not in {"/health", "/ready"}:
        raise HTTPException(status_code=503, detail="Server is draining")

    start = time.time()
    IN_FLIGHT_REQUESTS += 1
    try:
        response: Response = await call_next(request)
    except Exception:
        TOTAL_ERRORS += 1
        raise
    finally:
        IN_FLIGHT_REQUESTS -= 1

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    elapsed_ms = round((time.time() - start) * 1000, 1)

    _json_log(
        "request",
        method=request.method,
        path=request.url.path,
        status=response.status_code,
        ms=elapsed_ms,
    )
    return response


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    user_id: str | None = Field(default=None, min_length=3, max_length=128)


class AskResponse(BaseModel):
    user_id: str
    question: str
    answer: str
    model: str
    history_messages: int
    timestamp: str


@app.get("/")
def root():
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "endpoints": ["/ask", "/health", "/ready", "/metrics"],
    }


@app.post("/ask", response_model=AskResponse)
async def ask_agent(body: AskRequest, user_from_key: str = Depends(verify_api_key)):
    user_id = body.user_id or user_from_key

    check_rate_limit(user_id)
    check_budget(user_id, estimate_cost(body.question))

    history = load_history(user_id)
    append_history(user_id, "user", body.question)

    answer = llm_ask(body.question)

    check_budget(user_id, estimate_cost("", answer))
    append_history(user_id, "assistant", answer)

    return AskResponse(
        user_id=user_id,
        question=body.question,
        answer=answer,
        model=settings.llm_model,
        history_messages=len(history) + 2,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@app.get("/history/{user_id}")
def get_history(user_id: str, _user_from_key: str = Depends(verify_api_key)):
    history = load_history(user_id)
    return {"user_id": user_id, "messages": history, "count": len(history)}


@app.delete("/history/{user_id}")
def clear_history(user_id: str, _user_from_key: str = Depends(verify_api_key)):
    r.delete(f"history:{user_id}")
    return {"deleted": user_id}


@app.get("/health")
def health():
    return {
        "status": "ok",
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "instance_pid": os.getpid(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/ready")
def ready():
    if not IS_READY or IS_DRAINING:
        raise HTTPException(status_code=503, detail="Not ready")

    try:
        r.ping()
    except redis.RedisError:
        raise HTTPException(status_code=503, detail="Redis unavailable")

    return {"ready": True}


@app.get("/metrics")
def metrics(_user_from_key: str = Depends(verify_api_key)):
    return {
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "in_flight_requests": IN_FLIGHT_REQUESTS,
        "total_requests": TOTAL_REQUESTS,
        "total_errors": TOTAL_ERRORS,
    }


def shutdown_handler(signum, _frame):
    global IS_DRAINING, IS_READY
    IS_DRAINING = True
    IS_READY = False
    _json_log("signal_received", signum=signum)


signal.signal(signal.SIGTERM, shutdown_handler)
signal.signal(signal.SIGINT, shutdown_handler)


if __name__ == "__main__":
    _json_log("boot", host=settings.host, port=settings.port)
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        timeout_graceful_shutdown=30,
    )
