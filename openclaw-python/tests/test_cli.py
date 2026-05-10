"""Tests for the CLI entry point."""

from click.testing import CliRunner

from openclaw.main import cli


def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Usage" in result.output


def test_cli_run_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["run", "--help"])
    assert result.exit_code == 0


def test_cli_status_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["status", "--help"])
    assert result.exit_code == 0


def test_cli_channels_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["channels", "--help"])
    assert result.exit_code == 0


def test_cli_agents_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["agents", "--help"])
    assert result.exit_code == 0
