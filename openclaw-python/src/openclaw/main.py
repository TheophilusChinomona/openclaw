"""CLI entry point for the OpenClaw Python gateway."""

from __future__ import annotations

import click
from rich.console import Console

console = Console()


@click.group()
@click.version_option(package_name="openclaw")
def cli() -> None:
    """OpenClaw gateway — multi-channel AI agent gateway."""


@cli.command()
@click.option("--config", "-c", default=None, help="Path to config.yaml")
@click.option("--dry-run", is_flag=True, help="Validate config and exit without starting")
def run(config: str | None, dry_run: bool) -> None:
    """Start the gateway server."""
    from openclaw.config.loader import load_config

    cfg = load_config(config)
    if dry_run:
        console.print("[green]Config valid.[/green]")
        console.print(cfg.model_dump())
        return
    from openclaw.server.gateway import GatewayServer

    GatewayServer(cfg).run()


@cli.command()
def setup() -> None:
    """Interactive setup wizard."""
    from openclaw.server.wizard import run_setup_wizard

    run_setup_wizard()


@cli.command()
@click.option("--from", "source", default=None, metavar="PATH",
              help="Path to existing Hermes config.yaml (auto-detected if omitted)")
@click.option("--to", "output", default=None, metavar="PATH",
              help="Output path (default: ~/.claw/config.yaml)")
def migrate(source: str | None, output: str | None) -> None:
    """Migrate a Hermes gateway config to OpenClaw format."""
    from openclaw.migration.hermes import run_migration_wizard

    run_migration_wizard(source=source, output=output)


@cli.command()
@click.option("--config", "-c", default=None, help="Path to config.yaml")
def status(config: str | None) -> None:
    """Show gateway status and diagnostics."""
    from openclaw.config.loader import load_config
    from openclaw.server.wizard import show_status

    cfg = load_config(config)
    show_status(cfg)


@cli.command()
@click.option("--config", "-c", default=None, help="Path to config.yaml")
def channels(config: str | None) -> None:
    """List configured channels."""
    from openclaw.config.loader import load_config

    cfg = load_config(config)
    if not cfg.channels:
        console.print("No channels configured.")
        return
    for ch in cfg.channels:
        console.print(f"  [cyan]{ch.id}[/cyan]  type={ch.type}  dm_scope={ch.dm_scope}")


@cli.command()
@click.option("--config", "-c", default=None, help="Path to config.yaml")
def agents(config: str | None) -> None:
    """List configured agents."""
    from openclaw.config.loader import load_config

    cfg = load_config(config)
    if not cfg.agents:
        console.print("No agents configured.")
        return
    for ag in cfg.agents:
        default_marker = " [default]" if ag.default else ""
        console.print(f"  [cyan]{ag.id}[/cyan]{default_marker}")
