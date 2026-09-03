"""Redis client factory."""

import os
from typing import Optional

from redis import Redis


def get_redis_client() -> Optional[Redis]:
    """Get Redis client from environment."""
    redis_url = os.getenv("REDIS_URL")
    if redis_url:
        return Redis.from_url(redis_url, decode_responses=True)
    return None