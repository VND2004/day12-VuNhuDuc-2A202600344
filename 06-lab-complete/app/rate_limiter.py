import time

import redis
from fastapi import HTTPException

from app.config import settings

r = redis.from_url(settings.redis_url, decode_responses=True)


def check_rate_limit(user_id: str) -> None:
    """Sliding-window limit in Redis: N requests per minute per user."""
    now = time.time()
    window_start = now - 60
    key = f"rate:{user_id}"

    pipe = r.pipeline()
    pipe.zremrangebyscore(key, 0, window_start)
    pipe.zcard(key)
    _, request_count = pipe.execute()

    if int(request_count) >= settings.rate_limit_per_minute:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded ({settings.rate_limit_per_minute}/min)",
            headers={"Retry-After": "60"},
        )

    pipe = r.pipeline()
    pipe.zadd(key, {str(now): now})
    pipe.expire(key, 120)
    pipe.execute()
