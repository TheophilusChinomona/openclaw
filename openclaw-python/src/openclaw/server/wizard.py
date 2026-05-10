"""Interactive setup wizard and status diagnostics."""

from __future__ import annotations

from rich.console import Console
from rich.table import Table

from openclaw.config.schema import GatewayConfig

console = Console()


def run_setup_wizard() -> None:
    """Interactive prompts to create ~/.claw/config.yaml."""
    from pathlib import Path

    console.print("[bold cyan]OpenClaw Gateway Setup[/bold cyan]\n")

    provider = console.input("Model provider [openai/anthropic/ollama] (default: openai): ").strip() or "openai"
    model = console.input("Model name (default: gpt-4o): ").strip() or "gpt-4o"
    api_key = console.input("API key (leave blank to use env var): ").strip() or None

    channels_yaml = ""
    add_telegram = console.input("\nAdd Telegram channel? [y/N]: ").strip().lower() == "y"
    if add_telegram:
        tg_token = console.input("  Telegram bot token: ").strip()
        channels_yaml += f"  - id: telegram-main\n    type: telegram\n    token: \"{tg_token}\"\n"

    add_discord = console.input("Add Discord channel? [y/N]: ").strip().lower() == "y"
    if add_discord:
        dc_token = console.input("  Discord bot token: ").strip()
        channels_yaml += f"  - id: discord-main\n    type: discord\n    token: \"{dc_token}\"\n"

    config_path = Path("~/.claw/config.yaml").expanduser()
    config_path.parent.mkdir(parents=True, exist_ok=True)

    api_key_line = f'  api_key: "{api_key}"' if api_key else "  # api_key: set OPENAI_API_KEY env var"

    config_yaml = f"""\
model_provider:
  type: {provider}
  model: {model}
{api_key_line}

channels:
{channels_yaml or "  []"}
agents:
  - id: main
    default: true
    system_prompt: "You are a helpful assistant."
"""
    config_path.write_text(config_yaml)
    console.print(f"\n[green]Config saved to {config_path}[/green]")
    console.print("Run [bold]claw run[/bold] to start the gateway.")


def show_status(cfg: GatewayConfig) -> None:
    """Display gateway config summary as a Rich table."""
    console.print("[bold cyan]OpenClaw Gateway Status[/bold cyan]\n")

    table = Table(show_header=True, header_style="bold")
    table.add_column("Setting")
    table.add_column("Value")
    table.add_row("Provider", f"{cfg.model_provider.type} / {cfg.model_provider.model}")
    table.add_row("Server", f"{cfg.server.bind}:{cfg.server.port}")
    table.add_row("Auth mode", cfg.security.auth_mode)
    table.add_row("Channels", str(len(cfg.channels)))
    table.add_row("Agents", str(len(cfg.agents)))
    console.print(table)

    if cfg.channels:
        console.print("\n[bold]Channels:[/bold]")
        for ch in cfg.channels:
            console.print(f"  • {ch.id} ({ch.type})")

    if cfg.agents:
        console.print("\n[bold]Agents:[/bold]")
        for ag in cfg.agents:
            marker = " [default]" if ag.default else ""
            console.print(f"  • {ag.id}{marker}")
