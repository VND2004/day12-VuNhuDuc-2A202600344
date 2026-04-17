from datetime import datetime

import redis
from fastapi import HTTPException

from app.config import settings

r = redis.from_url(settings.redis_url, decode_responses=True)


def check_budget(user_id: str, estimated_cost: float) -> None:
    """Monthly budget check in Redis. Raises 402 when exceeded."""
    month_key = datetime.now().strftime("%Y-%m")
    key = f"budget:{user_id}:{month_key}"

    current = float(r.get(key) or 0.0)
    if current + estimated_cost > settings.monthly_budget_usd:
        raise HTTPException(
            status_code=402,
            detail=(
                f"Monthly budget exceeded for {user_id}. "
                f"Limit: ${settings.monthly_budget_usd:.2f}"
            ),
        )

    pipe = r.pipeline()
    pipe.incrbyfloat(key, estimated_cost)
    pipe.expire(key, 35 * 24 * 3600)
    pipe.execute()


def estimate_cost(question: str, answer: str = "") -> float:
    """Very rough token-to-cost approximation for lab/demo."""
    input_tokens = max(1, len(question.split()) * 2)
    output_tokens = max(1, len(answer.split()) * 2) if answer else 0

    # Demo pricing, not real provider billing.
    input_cost = (input_tokens / 1000.0) * 0.00015
    output_cost = (output_tokens / 1000.0) * 0.00060
    return input_cost + output_cost
