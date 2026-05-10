"""Hermes → OpenClaw gateway migration helpers.

`migrate_hermes_config` is the pure transformation layer (testable, no I/O side effects).
`run_migration_wizard` is the interactive CLI wizard that calls it.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from openclaw.config.schema import (
    AgentConfig,
    BindingConfig,
    ChannelConfig,
    GatewayConfig,
    ModelProviderConfig,
    SecurityConfig,
    ServerConfig,
    SessionConfig,
)


# ---------------------------------------------------------------------------
# Pure transformation layer
# ---------------------------------------------------------------------------

@dataclass
class MigrationResult:
    config: GatewayConfig
    skill_workspace_hints: list[str] = field(default_factory=list)

    def write(self, path: str) -> None:
        """Serialise the migrated config to YAML at *path*."""
        out = Path(path).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(_config_to_yaml(self.config))


def migrate_hermes_config(
    source_path: str,
    channels: list[ChannelConfig],
    bindings: list[BindingConfig],
    server: ServerConfig | None = None,
) -> MigrationResult:
    """Read a Hermes config.yaml and produce a GatewayConfig with channels/bindings injected.

    Preserves all compatible Hermes sections (model_provider, agents, session, security)
    and merges in the supplied channels and bindings.

    Raises FileNotFoundError if *source_path* does not exist.
    """
    src = Path(source_path).expanduser()
    if not src.exists():
        raise FileNotFoundError(f"Hermes config not found: {src}")

    raw: dict[str, Any] = yaml.safe_load(src.read_text()) or {}

    model_provider = _parse_model_provider(raw.get("model_provider") or {})
    agents, workspace_hints = _parse_agents(raw.get("agents") or [])
    session = _parse_session(raw.get("session") or {})
    security = _parse_security(raw.get("security") or {})

    cfg = GatewayConfig(
        model_provider=model_provider,
        agents=agents,
        channels=channels,
        bindings=bindings,
        session=session,
        security=security,
        server=server or ServerConfig(),
    )
    return MigrationResult(config=cfg, skill_workspace_hints=workspace_hints)


# ---------------------------------------------------------------------------
# Section parsers
# ---------------------------------------------------------------------------

def _parse_model_provider(raw: dict[str, Any]) -> ModelProviderConfig:
    return ModelProviderConfig(
        type=raw.get("type", "openai"),
        api_key=raw.get("api_key") or None,
        model=raw.get("model", "gpt-4o"),
        base_url=raw.get("base_url") or None,
    )


def _parse_agents(raw: list[dict[str, Any]]) -> tuple[list[AgentConfig], list[str]]:
    agents: list[AgentConfig] = []
    hints: list[str] = []
    for entry in raw:
        agent = AgentConfig(
            id=entry.get("id", "main"),
            default=bool(entry.get("default", False)),
            system_prompt=entry.get("system_prompt", ""),
            workspace=entry.get("workspace") or None,
            skills=list(entry.get("skills") or []),
        )
        agents.append(agent)
        if agent.workspace:
            hints.append(agent.workspace)
    return agents, hints


def _parse_session(raw: dict[str, Any]) -> SessionConfig:
    return SessionConfig(
        store=raw.get("store", "~/.openclaw/sessions"),
        max_context_tokens=int(raw.get("max_context_tokens", 8192)),
        prune_after=str(raw.get("prune_after", "30d")),
    )


def _parse_security(raw: dict[str, Any]) -> SecurityConfig:
    return SecurityConfig(
        auth_mode=raw.get("auth_mode", "token"),
        token=raw.get("token") or None,
    )


# ---------------------------------------------------------------------------
# YAML serialisation
# ---------------------------------------------------------------------------

def _config_to_yaml(cfg: GatewayConfig) -> str:
    data: dict[str, Any] = {
        "model_provider": {
            "type": cfg.model_provider.type,
            "model": cfg.model_provider.model,
            **( {"api_key": cfg.model_provider.api_key} if cfg.model_provider.api_key else {}),
            **( {"base_url": cfg.model_provider.base_url} if cfg.model_provider.base_url else {}),
        },
        "channels": [
            {
                "id": ch.id,
                "type": ch.type,
                "token": ch.token,
                "dm_scope": ch.dm_scope,
            }
            for ch in cfg.channels
        ],
        "agents": [
            {
                "id": ag.id,
                **({"default": True} if ag.default else {}),
                **({"system_prompt": ag.system_prompt} if ag.system_prompt else {}),
                **({"workspace": ag.workspace} if ag.workspace else {}),
                **({"skills": ag.skills} if ag.skills else {}),
            }
            for ag in cfg.agents
        ],
        "bindings": [
            {
                "agent_id": b.agent_id,
                "match": {k: v for k, v in {
                    "channel": b.match.channel,
                    "account_id": b.match.account_id,
                    "peer_kind": b.match.peer_kind,
                    "peer_id": b.match.peer_id,
                    "guild_id": b.match.guild_id,
                    "team_id": b.match.team_id,
                    **({"roles": b.match.roles} if b.match.roles else {}),
                }.items() if v is not None},
            }
            for b in cfg.bindings
        ],
        "session": {
            "store": cfg.session.store,
            "max_context_tokens": cfg.session.max_context_tokens,
            "prune_after": cfg.session.prune_after,
        },
        "security": {
            "auth_mode": cfg.security.auth_mode,
            **({"token": cfg.security.token} if cfg.security.token else {}),
        },
        "server": {
            "port": cfg.server.port,
            "bind": cfg.server.bind,
            **({"custom_bind_host": cfg.server.custom_bind_host}
               if cfg.server.custom_bind_host else {}),
        },
    }
    return yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True)


# ---------------------------------------------------------------------------
# Interactive wizard
# ---------------------------------------------------------------------------

def run_migration_wizard(source: str | None, output: str | None) -> None:
    """Interactive Hermes → OpenClaw migration wizard."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    from openclaw.config.schema import BindingConfig, BindingMatch, ChannelConfig, ServerConfig

    console = Console()
    console.print(Panel.fit(
        "[bold cyan]OpenClaw Migration Wizard[/bold cyan]\n"
        "Migrate your Hermes gateway config to OpenClaw format.",
        border_style="cyan",
    ))

    # --- Locate source config ---
    if not source:
        candidates = [
            "~/.hermes/config.yaml",
            "~/.config/hermes/config.yaml",
            "./config.yaml",
        ]
        for candidate in candidates:
            if Path(candidate).expanduser().exists():
                source = candidate
                break
        if not source:
            source = console.input("\n[bold]Path to your Hermes config.yaml:[/bold] ").strip()

    src_path = Path(source).expanduser()
    if not src_path.exists():
        console.print(f"[red]File not found:[/red] {src_path}")
        sys.exit(1)

    console.print(f"\n[green]✓[/green] Reading: [bold]{src_path}[/bold]")

    # Preview what will be imported
    raw: dict[str, Any] = yaml.safe_load(src_path.read_text()) or {}
    _preview_hermes_config(console, raw)

    # --- Channels ---
    console.print("\n[bold]Channel setup[/bold]")
    channels: list[ChannelConfig] = []
    bindings: list[BindingConfig] = []

    agent_ids = [a.get("id", "main") for a in (raw.get("agents") or [{"id": "main"}])]

    if console.input("Add a [bold]Discord[/bold] channel? [y/N]: ").strip().lower() == "y":
        ch = _wizard_discord_channel(console)
        channels.append(ch)
        agent_id = _pick_agent(console, agent_ids, ch.id)
        bindings.append(BindingConfig(
            agent_id=agent_id,
            match=BindingMatch(channel=ch.id, account_id="*"),
        ))

    if console.input("Add a [bold]Telegram[/bold] channel? [y/N]: ").strip().lower() == "y":
        ch = _wizard_telegram_channel(console)
        channels.append(ch)
        agent_id = _pick_agent(console, agent_ids, ch.id)
        bindings.append(BindingConfig(
            agent_id=agent_id,
            match=BindingMatch(channel=ch.id, account_id="*"),
        ))

    # --- Server settings ---
    console.print("\n[bold]Server settings[/bold]")
    port_raw = console.input(f"  Port [bold](default 18789)[/bold]: ").strip()
    port = int(port_raw) if port_raw.isdigit() else 18789
    bind_raw = console.input("  Bind mode — loopback / lan / custom [bold](default loopback)[/bold]: ").strip().lower()
    bind = bind_raw if bind_raw in ("loopback", "lan", "custom") else "loopback"
    custom_host: str | None = None
    if bind == "custom":
        custom_host = console.input("  Custom bind host: ").strip() or None
    server = ServerConfig(port=port, bind=bind, custom_bind_host=custom_host)  # type: ignore[arg-type]

    # --- Output path ---
    if not output:
        default_out = "~/.claw/config.yaml"
        out_raw = console.input(f"\n  Output path [bold](default {default_out})[/bold]: ").strip()
        output = out_raw or default_out

    # --- Run migration ---
    result = migrate_hermes_config(
        source_path=str(src_path),
        channels=channels,
        bindings=bindings,
        server=server,
    )
    result.write(output)

    out_path = Path(output).expanduser()
    console.print(f"\n[green]✓[/green] Config written to [bold]{out_path}[/bold]")

    # --- Skill workspace hints ---
    if result.skill_workspace_hints:
        console.print("\n[bold]Skills[/bold] — copy your Hermes skill files to the agent workspace:")
        for ws in result.skill_workspace_hints:
            openclaw_ws = ws.replace(".hermes", ".openclaw")
            console.print(f"  cp -r {ws}/skills {openclaw_ws}/skills")

    console.print("\n[bold]Next steps:[/bold]")
    console.print(f"  1. Review [bold]{out_path}[/bold]")
    console.print("  2. Add any missing secrets (tokens, API keys)")
    console.print("  3. [bold]claw run[/bold] — start the gateway")
    console.print("  4. [bold]claw status[/bold] — verify everything is connected\n")


def _preview_hermes_config(console: Any, raw: dict[str, Any]) -> None:
    from rich.table import Table

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("key", style="dim")
    table.add_column("value")

    mp = raw.get("model_provider") or {}
    table.add_row("Provider", f"{mp.get('type', '?')} / {mp.get('model', '?')}")

    agents = raw.get("agents") or []
    table.add_row("Agents", ", ".join(a.get("id", "?") for a in agents) or "(none)")

    sess = raw.get("session") or {}
    if sess.get("max_context_tokens"):
        table.add_row("Context window", str(sess["max_context_tokens"]) + " tokens")

    sec = raw.get("security") or {}
    if sec.get("auth_mode"):
        table.add_row("Auth mode", sec["auth_mode"])

    console.print("\n[dim]Importing from Hermes config:[/dim]")
    console.print(table)


def _wizard_discord_channel(console: Any) -> "ChannelConfig":
    from openclaw.config.schema import ChannelConfig

    chan_id = console.input("  Channel id [bold](default discord-main)[/bold]: ").strip() or "discord-main"
    token = console.input("  Bot token (or env var like ${DISCORD_TOKEN}): ").strip() or "${DISCORD_TOKEN}"
    scope_raw = console.input(
        "  DM scope — main / per-peer / per-channel-peer / per-account-channel-peer "
        "[bold](default per-peer)[/bold]: "
    ).strip()
    dm_scope = scope_raw if scope_raw in (
        "main", "per-peer", "per-channel-peer", "per-account-channel-peer"
    ) else "per-peer"
    return ChannelConfig(id=chan_id, type="discord", token=token, dm_scope=dm_scope)  # type: ignore[arg-type]


def _wizard_telegram_channel(console: Any) -> "ChannelConfig":
    from openclaw.config.schema import ChannelConfig

    chan_id = console.input("  Channel id [bold](default telegram-main)[/bold]: ").strip() or "telegram-main"
    token = console.input("  Bot token (or env var like ${TELEGRAM_TOKEN}): ").strip() or "${TELEGRAM_TOKEN}"
    scope_raw = console.input(
        "  DM scope — main / per-peer / per-channel-peer / per-account-channel-peer "
        "[bold](default main)[/bold]: "
    ).strip()
    dm_scope = scope_raw if scope_raw in (
        "main", "per-peer", "per-channel-peer", "per-account-channel-peer"
    ) else "main"
    return ChannelConfig(id=chan_id, type="telegram", token=token, dm_scope=dm_scope)  # type: ignore[arg-type]


def _pick_agent(console: Any, agent_ids: list[str], channel_id: str) -> str:
    if len(agent_ids) == 1:
        return agent_ids[0]
    options = " / ".join(agent_ids)
    default = agent_ids[0]
    choice = console.input(
        f"  Route [bold]{channel_id}[/bold] messages to which agent? [{options}] "
        f"[bold](default {default})[/bold]: "
    ).strip()
    return choice if choice in agent_ids else default
