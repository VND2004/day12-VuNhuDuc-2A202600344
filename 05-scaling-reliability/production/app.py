"""
ADVANCED — Stateless Agent với Redis Session

Stateless = agent không giữ state trong memory.
Mọi state (session, conversation history) lưu trong Redis.

Tại sao stateless quan trọng khi scale?
  Instance 1: User A gửi request 1 → lưu session trong memory
  Instance 2: User A gửi request 2 → KHÔNG có session! Bug!

  ✅ Giải pháp: Lưu session trong Redis
  Bất kỳ instance nào cũng đọc được session của user.

Demo:
  docker compose up
  # Sau đó test multi-turn conversation
  python test_stateless.py
"""
import os
import time
import json
import logging
import uuid
from datetime import datetime, timezone
from contextlib import asynccontextmanager


from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import redis
import uvicorn
from utils.mock_llm import ask

# Stateless mode: Redis là bắt buộc, không fallback in-memory
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
_redis = redis.from_url(REDIS_URL, decode_responses=True)


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

START_TIME = time.time()
INSTANCE_ID = os.getenv("INSTANCE_ID", f"instance-{uuid.uuid4().hex[:6]}")


# ──────────────────────────────────────────────────────────
# Session Storage (Redis-backed, Stateless-compatible)
# ──────────────────────────────────────────────────────────

def save_session(session_id: str, data: dict, ttl_seconds: int = 3600):
    """Lưu session vào Redis với TTL."""
    serialized = json.dumps(data)
    _redis.setex(f"session:{session_id}", ttl_seconds, serialized)


def load_session(session_id: str) -> dict:
    """Load session từ Redis."""
    data = _redis.get(f"session:{session_id}")
    return json.loads(data) if data else {}


def append_to_history(session_id: str, role: str, content: str):
    """Thêm message vào conversation history."""
    session = load_session(session_id)
    history = session.get("history", [])
    history.append({
        "role": role,
        "content": content,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    # Giữ tối đa 20 messages (10 turns)
    if len(history) > 20:
        history = history[-20:]
    session["history"] = history
    save_session(session_id, session)
    return history


def get_user_history(user_id: str) -> list[dict]:
    """Đọc conversation history theo user_id từ Redis list."""
    rows = _redis.lrange(f"history:{user_id}", 0, -1)
    history: list[dict] = []
    for item in rows:
        try:
            history.append(json.loads(item))
        except json.JSONDecodeError:
            continue
    return history


def append_user_history(user_id: str, role: str, content: str, ttl_seconds: int = 7 * 24 * 3600):
    """Append message vào Redis list, giới hạn 20 messages và set TTL."""
    key = f"history:{user_id}"
    message = {
        "role": role,
        "content": content,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    _redis.rpush(key, json.dumps(message))
    _redis.ltrim(key, -20, -1)
    _redis.expire(key, ttl_seconds)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        _redis.ping()
    except redis.RedisError as exc:
        logger.exception("Redis unavailable at startup. Stateless mode requires Redis.")
        raise RuntimeError("Redis unavailable. Cannot run in stateless mode.") from exc

    logger.info(f"Starting instance {INSTANCE_ID}")
    logger.info("Storage: Redis")
    yield
    logger.info(f"Instance {INSTANCE_ID} shutting down")


app = FastAPI(
    title="Stateless Agent",
    version="4.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ──────────────────────────────────────────────────────────
# Models
# ──────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    question: str
    session_id: str | None = None  # None = tạo session mới


class AskRequest(BaseModel):
    user_id: str
    question: str


# ──────────────────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────────────────

@app.post("/chat")
async def chat(body: ChatRequest):
    """
    Multi-turn conversation với session management.

    Gửi session_id trong các request tiếp theo để tiếp tục cuộc trò chuyện.
    Agent có thể chạy trên bất kỳ instance nào — state trong Redis.
    """
    # Tạo hoặc dùng session hiện có
    session_id = body.session_id or str(uuid.uuid4())

    # Thêm câu hỏi vào history
    append_to_history(session_id, "user", body.question)

    # Gọi LLM với context (trong mock, ta chỉ dùng câu hỏi hiện tại)
    session = load_session(session_id)
    history = session.get("history", [])
    answer = ask(body.question)

    # Lưu response vào history
    append_to_history(session_id, "assistant", answer)

    return {
        "session_id": session_id,
        "question": body.question,
        "answer": answer,
        "turn": len([m for m in history if m["role"] == "user"]) + 1,
        "served_by": INSTANCE_ID,  # ← thấy rõ bất kỳ instance nào cũng serve được
        "storage": "redis",
    }


@app.post("/ask")
async def ask_agent(body: AskRequest):
    """
    Stateless endpoint theo user_id.

    History được lưu trong Redis key: history:{user_id}
    nên bất kỳ instance nào cũng đọc/ghi được.
    """
    history = get_user_history(body.user_id)
    answer = ask(body.question)

    append_user_history(body.user_id, "user", body.question)
    append_user_history(body.user_id, "assistant", answer)

    return {
        "user_id": body.user_id,
        "question": body.question,
        "answer": answer,
        "history_messages_before": len(history),
        "served_by": INSTANCE_ID,
        "storage": "redis",
    }


@app.get("/chat/{session_id}/history")
def get_history(session_id: str):
    """Xem conversation history của một session."""
    session = load_session(session_id)
    if not session:
        raise HTTPException(404, f"Session {session_id} not found or expired")
    return {
        "session_id": session_id,
        "messages": session.get("history", []),
        "count": len(session.get("history", [])),
    }


@app.delete("/chat/{session_id}")
def delete_session(session_id: str):
    """Xóa session (user logout)."""
    _redis.delete(f"session:{session_id}")
    return {"deleted": session_id}


# ──────────────────────────────────────────────────────────
# Health / Metrics
# ──────────────────────────────────────────────────────────

@app.get("/health")
def health():
    try:
        _redis.ping()
        redis_ok = True
    except redis.RedisError:
        redis_ok = False

    status = "ok" if redis_ok else "degraded"

    return {
        "status": status,
        "instance_id": INSTANCE_ID,
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "storage": "redis",
        "redis_connected": redis_ok,
    }


@app.get("/ready")
def ready():
    try:
        _redis.ping()
    except redis.RedisError:
        raise HTTPException(503, "Redis not available")
    return {"ready": True, "instance": INSTANCE_ID}


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=True)
