"""Gateway router — 8-tier binding resolution matching src/routing/resolve-route.ts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from openclaw.config.schema import AgentConfig, BindingConfig, GatewayConfig
from openclaw.models.core import ChatType, RoutePeer
from openclaw.routing.session_key import (
    DEFAULT_ACCOUNT_ID,
    DEFAULT_AGENT_ID,
    build_agent_main_session_key,
    build_agent_peer_session_key,
    normalize_agent_id,
    normalize_account_id,
)

MatchedBy = Literal[
    "binding.peer",
    "binding.peer.parent",
    "binding.peer.wildcard",
    "binding.guild+roles",
    "binding.guild",
    "binding.team",
    "binding.account",
    "binding.channel",
    "default",
]


@dataclass
class ResolvedRoute:
    agent_id: str
    channel: str
    account_id: str
    session_key: str
    main_session_key: str
    matched_by: MatchedBy
    last_route_policy: Literal["main", "session"]


class GatewayRouter:
    def __init__(self, config: GatewayConfig) -> None:
        self._config = config
        self._agents: dict[str, AgentConfig] = {a.id: a for a in config.agents}
        self._default_agent_id = self._resolve_default_agent_id()

    def _resolve_default_agent_id(self) -> str:
        for agent in self._config.agents:
            if agent.default:
                return agent.id
        if self._config.agents:
            return self._config.agents[0].id
        return DEFAULT_AGENT_ID

    def resolve(
        self,
        channel: str,
        peer: RoutePeer,
        account_id: str | None = None,
        guild_id: str | None = None,
        team_id: str | None = None,
        member_role_ids: list[str] | None = None,
        thread_id: str | None = None,
        parent_peer: RoutePeer | None = None,
    ) -> ResolvedRoute:
        """Run 8-tier binding resolution and return a ResolvedRoute."""
        ch = channel.lower()
        roles = set(member_role_ids or [])

        matched_agent_id: str | None = None
        matched_by: MatchedBy = "default"

        for binding in self._config.bindings:
            m = binding.match
            if m.channel.lower() != ch:
                continue

            # Tier 1: exact peer match
            if m.peer_kind and m.peer_id and m.peer_id != "*":
                if m.peer_kind == peer.kind and m.peer_id == peer.id:
                    matched_agent_id = binding.agent_id
                    matched_by = "binding.peer"
                    break

        if matched_agent_id is None:
            for binding in self._config.bindings:
                m = binding.match
                if m.channel.lower() != ch:
                    continue

                # Tier 2: parent peer match (threads)
                if m.peer_kind and m.peer_id and m.peer_id != "*" and parent_peer:
                    if m.peer_kind == parent_peer.kind and m.peer_id == parent_peer.id:
                        matched_agent_id = binding.agent_id
                        matched_by = "binding.peer.parent"
                        break

        if matched_agent_id is None:
            for binding in self._config.bindings:
                m = binding.match
                if m.channel.lower() != ch:
                    continue

                # Tier 3: peer kind wildcard
                if m.peer_kind and m.peer_id == "*":
                    if m.peer_kind == peer.kind:
                        matched_agent_id = binding.agent_id
                        matched_by = "binding.peer.wildcard"
                        break

                # Tier 4: guild + roles
                if m.guild_id and m.roles and guild_id == m.guild_id:
                    if roles.intersection(m.roles):
                        matched_agent_id = binding.agent_id
                        matched_by = "binding.guild+roles"
                        break

                # Tier 5: guild only
                if m.guild_id and not m.roles and guild_id == m.guild_id:
                    matched_agent_id = binding.agent_id
                    matched_by = "binding.guild"
                    break

                # Tier 6: team
                if m.team_id and team_id == m.team_id:
                    matched_agent_id = binding.agent_id
                    matched_by = "binding.team"
                    break

                # Tier 7: specific account
                if m.account_id and m.account_id != "*" and m.account_id == account_id:
                    matched_agent_id = binding.agent_id
                    matched_by = "binding.account"
                    break

                # Tier 8: channel catch-all
                if m.account_id == "*" and not any(
                    [m.peer_kind, m.guild_id, m.team_id]
                ):
                    matched_agent_id = binding.agent_id
                    matched_by = "binding.channel"
                    break

        agent_id = normalize_agent_id(matched_agent_id or self._default_agent_id)
        acct = normalize_account_id(account_id)

        # Determine the dm_scope from the matched agent's channel config
        dm_scope = "main"
        for ch_cfg in self._config.channels:
            if ch_cfg.id.lower() == ch:
                dm_scope = ch_cfg.dm_scope
                break

        session_key = build_agent_peer_session_key(
            agent_id=agent_id,
            channel=channel,
            peer_kind=peer.kind,
            peer_id=peer.id,
            account_id=acct,
            dm_scope=dm_scope,
        )
        main_session_key = build_agent_main_session_key(agent_id)
        last_route_policy: Literal["main", "session"] = (
            "main" if session_key == main_session_key else "session"
        )

        return ResolvedRoute(
            agent_id=agent_id,
            channel=channel,
            account_id=acct,
            session_key=session_key,
            main_session_key=main_session_key,
            matched_by=matched_by,
            last_route_policy=last_route_policy,
        )
