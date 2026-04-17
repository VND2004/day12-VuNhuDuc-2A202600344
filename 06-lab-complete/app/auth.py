from fastapi import HTTPException, Security
from fastapi.security.api_key import APIKeyHeader

from app.config import settings

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(api_key: str = Security(_api_key_header)) -> str:
    """Validate API key and return a stable user identifier."""
    if not api_key or api_key != settings.agent_api_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key. Include header: X-API-Key",
        )

    # Simple deterministic user id for demo labs.
    return f"user:{api_key[:8]}"
