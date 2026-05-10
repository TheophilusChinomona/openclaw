"""YAML config loader with environment variable injection."""

from __future__ import annotations

import os
import re
from pathlib import Path

import yaml

from .schema import GatewayConfig

_ENV_VAR_RE = re.compile(r"\$\{([^}]+)\}")

DEFAULT_CONFIG_PATH = "~/.claw/config.yaml"


def _expand_env_vars(value: object) -> object:
    """Recursively replace ${VAR} placeholders in strings with env var values."""
    if isinstance(value, str):
        def replacer(m: re.Match[str]) -> str:
            return os.environ.get(m.group(1), m.group(0))
        return _ENV_VAR_RE.sub(replacer, value)
    if isinstance(value, dict):
        return {k: _expand_env_vars(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand_env_vars(item) for item in value]
    return value


def load_config(path: str | None = None) -> GatewayConfig:
    """Load GatewayConfig from a YAML file, expanding ${ENV_VAR} references."""
    config_path = Path(path or DEFAULT_CONFIG_PATH).expanduser()
    if not config_path.exists():
        return GatewayConfig()
    with config_path.open() as f:
        raw = yaml.safe_load(f) or {}
    expanded = _expand_env_vars(raw)
    return GatewayConfig.model_validate(expanded)
