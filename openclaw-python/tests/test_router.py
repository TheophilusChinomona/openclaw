"""Tests for GatewayRouter — 8-tier binding resolution."""

import pytest

from openclaw.config.schema import AgentConfig, BindingConfig, BindingMatch, GatewayConfig
from openclaw.models.core import ChatType, RoutePeer
from openclaw.routing.router import GatewayRouter


def make_config(**kwargs: object) -> GatewayConfig:
    defaults = dict(
        agents=[AgentConfig(id="main", default=True)],
        bindings=[],
    )
    defaults.update(kwargs)
    return GatewayConfig(**defaults)  # type: ignore[arg-type]


def test_default_fallback_when_no_bindings():
    cfg = make_config()
    router = GatewayRouter(cfg)
    route = router.resolve("telegram-main", RoutePeer(kind=ChatType.DIRECT, id="123"))
    assert route.agent_id == "main"
    assert route.matched_by == "default"


def test_binding_channel_catchall():
    cfg = make_config(
        agents=[AgentConfig(id="main", default=True), AgentConfig(id="support")],
        bindings=[
            BindingConfig(
                agent_id="support",
                match=BindingMatch(channel="discord-main", account_id="*"),
            )
        ],
    )
    router = GatewayRouter(cfg)
    route = router.resolve("discord-main", RoutePeer(kind=ChatType.GROUP, id="ch1"))
    assert route.agent_id == "support"
    assert route.matched_by == "binding.channel"


def test_binding_peer_exact():
    cfg = make_config(
        agents=[AgentConfig(id="main", default=True), AgentConfig(id="vip")],
        bindings=[
            BindingConfig(
                agent_id="vip",
                match=BindingMatch(channel="telegram-main", peer_kind="direct", peer_id="999"),
            )
        ],
    )
    router = GatewayRouter(cfg)
    route = router.resolve("telegram-main", RoutePeer(kind=ChatType.DIRECT, id="999"))
    assert route.agent_id == "vip"
    assert route.matched_by == "binding.peer"


def test_binding_peer_wildcard():
    cfg = make_config(
        agents=[AgentConfig(id="main", default=True), AgentConfig(id="groupbot")],
        bindings=[
            BindingConfig(
                agent_id="groupbot",
                match=BindingMatch(channel="telegram-main", peer_kind="group", peer_id="*"),
            )
        ],
    )
    router = GatewayRouter(cfg)
    route = router.resolve("telegram-main", RoutePeer(kind=ChatType.GROUP, id="any_group"))
    assert route.agent_id == "groupbot"
    assert route.matched_by == "binding.peer.wildcard"


def test_binding_guild():
    cfg = make_config(
        agents=[AgentConfig(id="main", default=True), AgentConfig(id="guildbot")],
        bindings=[
            BindingConfig(
                agent_id="guildbot",
                match=BindingMatch(channel="discord-main", guild_id="guild123"),
            )
        ],
    )
    router = GatewayRouter(cfg)
    route = router.resolve(
        "discord-main",
        RoutePeer(kind=ChatType.GROUP, id="ch1"),
        guild_id="guild123",
    )
    assert route.agent_id == "guildbot"
    assert route.matched_by == "binding.guild"


def test_binding_guild_roles():
    cfg = make_config(
        agents=[AgentConfig(id="main", default=True), AgentConfig(id="adminbot")],
        bindings=[
            BindingConfig(
                agent_id="adminbot",
                match=BindingMatch(
                    channel="discord-main", guild_id="guild123", roles=["admin"]
                ),
            )
        ],
    )
    router = GatewayRouter(cfg)
    route = router.resolve(
        "discord-main",
        RoutePeer(kind=ChatType.GROUP, id="ch1"),
        guild_id="guild123",
        member_role_ids=["admin", "member"],
    )
    assert route.agent_id == "adminbot"
    assert route.matched_by == "binding.guild+roles"


def test_binding_team():
    cfg = make_config(
        agents=[AgentConfig(id="main", default=True), AgentConfig(id="teambot")],
        bindings=[
            BindingConfig(
                agent_id="teambot",
                match=BindingMatch(channel="slack-main", team_id="T123"),
            )
        ],
    )
    router = GatewayRouter(cfg)
    route = router.resolve(
        "slack-main",
        RoutePeer(kind=ChatType.CHANNEL, id="C1"),
        team_id="T123",
    )
    assert route.agent_id == "teambot"
    assert route.matched_by == "binding.team"


def test_session_key_included_in_route():
    cfg = make_config()
    router = GatewayRouter(cfg)
    route = router.resolve("telegram-main", RoutePeer(kind=ChatType.DIRECT, id="42"))
    assert route.session_key.startswith("agent:main:")
    assert route.main_session_key.startswith("agent:main:")


def test_last_route_policy_main_when_keys_equal():
    cfg = make_config()
    router = GatewayRouter(cfg)
    route = router.resolve("telegram-main", RoutePeer(kind=ChatType.DIRECT, id="42"))
    if route.session_key == route.main_session_key:
        assert route.last_route_policy == "main"
    else:
        assert route.last_route_policy == "session"
