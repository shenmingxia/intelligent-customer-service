from __future__ import annotations

import json
import os
import time
from dataclasses import asdict
from typing import Protocol


class SessionOwnershipError(Exception):
    """Raised when a session is reused by a different user."""


class ConversationStateProtocol(Protocol):
    session_id: str
    user_id: str
    pending_intent: str | None
    slots: dict[str, str] | None
    turns: list[dict[str, str]] | None


class SessionStore(Protocol):
    def get(self, session_id: str) -> dict | None:
        ...

    def save(self, state: ConversationStateProtocol) -> None:
        ...

    def clear(self) -> None:
        ...


class InMemorySessionStore:
    def __init__(self, ttl_seconds: int) -> None:
        self.ttl_seconds = ttl_seconds
        self.sessions: dict[str, ConversationStateProtocol] = {}
        self.expires_at: dict[str, float] = {}

    def get(self, session_id: str) -> dict | None:
        self._delete_if_expired(session_id)
        state = self.sessions.get(session_id)
        if state is None:
            return None
        self._touch(session_id)
        return asdict(state)

    def save(self, state: ConversationStateProtocol) -> None:
        if self.ttl_seconds <= 0:
            self.delete(state.session_id)
            return
        self.sessions[state.session_id] = state
        self._touch(state.session_id)

    def delete(self, session_id: str) -> None:
        self.sessions.pop(session_id, None)
        self.expires_at.pop(session_id, None)

    def clear(self) -> None:
        self.sessions.clear()
        self.expires_at.clear()

    def _touch(self, session_id: str) -> None:
        self.expires_at[session_id] = time.time() + self.ttl_seconds

    def _delete_if_expired(self, session_id: str) -> None:
        expires_at = self.expires_at.get(session_id)
        if expires_at is not None and expires_at <= time.time():
            self.delete(session_id)


class RedisSessionStore:
    def __init__(self, redis_url: str, ttl_seconds: int, key_prefix: str = "support:session") -> None:
        from redis import Redis

        self.client = Redis.from_url(redis_url, decode_responses=True)
        self.ttl_seconds = ttl_seconds
        self.key_prefix = key_prefix

    def get(self, session_id: str) -> dict | None:
        raw = self.client.get(self._key(session_id))
        if raw is None:
            return None
        if self.ttl_seconds > 0:
            self.client.expire(self._key(session_id), self.ttl_seconds)
        return json.loads(raw)

    def save(self, state: ConversationStateProtocol) -> None:
        payload = json.dumps(asdict(state), ensure_ascii=False)
        if self.ttl_seconds > 0:
            self.client.setex(self._key(state.session_id), self.ttl_seconds, payload)
        else:
            self.client.delete(self._key(state.session_id))

    def clear(self) -> None:
        for key in self.client.scan_iter(match=f"{self.key_prefix}:*"):
            self.client.delete(key)

    def _key(self, session_id: str) -> str:
        return f"{self.key_prefix}:{session_id}"


def build_session_store() -> SessionStore:
    ttl_seconds = int(os.getenv("SESSION_TTL_SECONDS", "86400"))
    redis_url = os.getenv("REDIS_URL")
    if redis_url:
        return RedisSessionStore(redis_url=redis_url, ttl_seconds=ttl_seconds)
    return InMemorySessionStore(ttl_seconds=ttl_seconds)
