"""Session key builders — mirrors src/routing/session-key.ts exactly."""

from __future__ import annotations

import re

DEFAULT_AGENT_ID = "main"
DEFAULT_MAIN_KEY = "main"
DEFAULT_ACCOUNT_ID = "default"

_VALID_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$", re.IGNORECASE)
_INVALID_CHARS_RE = re.compile(r"[^a-z0-9_-]+")


def normalize_agent_id(value: str | None) -> str:
    trimmed = (value or "").strip()
    if not trimmed:
        return DEFAULT_AGENT_ID
    lower = trimmed.lower()
    if _VALID_ID_RE.match(lower):
        return lower
    cleaned = _INVALID_CHARS_RE.sub("-", lower).strip("-")[:64]
    return cleaned or DEFAULT_AGENT_ID


def normalize_account_id(value: str | None) -> str:
    v = (value or "").strip().lower()
    return v or DEFAULT_ACCOUNT_ID


def normalize_main_key(value: str | None) -> str:
    trimmed = (value or "").strip()
    return trimmed.lower() if trimmed else DEFAULT_MAIN_KEY


def build_agent_main_session_key(
    agent_id: str,
    main_key: str | None = None,
) -> str:
    aid = normalize_agent_id(agent_id)
    mk = normalize_main_key(main_key)
    return f"agent:{aid}:{mk}"


def build_agent_peer_session_key(
    agent_id: str,
    channel: str,
    peer_kind: str = "direct",
    peer_id: str | None = None,
    account_id: str | None = None,
    dm_scope: str = "main",
    main_key: str | None = None,
) -> str:
    """Build a session key matching the TypeScript buildAgentPeerSessionKey logic."""
    aid = normalize_agent_id(agent_id)
    ch = (channel or "unknown").strip().lower()
    pid = (peer_id or "").strip().lower()
    mk = normalize_main_key(main_key)

    if peer_kind == "direct":
        if dm_scope == "per-account-channel-peer" and pid:
            acct = normalize_account_id(account_id)
            return f"agent:{aid}:{ch}:{acct}:direct:{pid}"
        if dm_scope == "per-channel-peer" and pid:
            return f"agent:{aid}:{ch}:direct:{pid}"
        if dm_scope == "per-peer" and pid:
            return f"agent:{aid}:direct:{pid}"
        # "main" scope or missing peer_id → collapse to main session
        return f"agent:{aid}:{mk}"

    pid = pid or "unknown"
    return f"agent:{aid}:{ch}:{peer_kind}:{pid}"


def resolve_thread_session_key(base_key: str, thread_id: str | None) -> str:
    """Append :thread:{id} suffix, matching TS resolveThreadSessionKeys."""
    if not thread_id or not thread_id.strip():
        return base_key
    return f"{base_key}:thread:{thread_id.strip().lower()}"
