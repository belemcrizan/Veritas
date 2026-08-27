"""Optional Redis nonce store.

Redis is not used as a generic database. Nonce consumption is SET NX because it is
ephemeral single-use coordination. Rolling budgets remain in SQLite/PostgreSQL:
those need durable committed+prepared sums, not TTL keys.
"""

from __future__ import annotations

from datetime import datetime


def redis_available() -> bool:
    try:
        import redis  # noqa: F401
    except ImportError:
        return False
    return True


class RedisNonceStore:
    def __init__(self, url: str, *, ttl_seconds: int = 86400) -> None:
        if not redis_available():
            raise RuntimeError("redis package is not installed")
        import redis

        self._client = redis.Redis.from_url(url, decode_responses=True)
        self.ttl_seconds = ttl_seconds
        self.path = url

    def consume(self, nonce: str, cap_id: str, now: datetime) -> bool:
        del now
        key = f"veritas:nonce:{nonce}"
        return bool(self._client.set(key, cap_id, nx=True, ex=self.ttl_seconds))
