# OpenClaw Gateway — Python

A standalone Python 3.11+ implementation of the [OpenClaw](https://openclaw.ai) multi-channel AI agent gateway. Receives messages from messaging platforms, routes them to AI agents via any OpenAI-compatible LLM API, manages per-user session history, executes tools, and returns responses.

Built for compatibility with **Hermes Agent's** architecture: `config.yaml`, `SKILL.md` skills, toolsets, and multi-agent delegation all work without modification.

---

## Quick start

```bash
pip install openclaw

# Interactive setup (creates ~/.claw/config.yaml)
claw setup

# Start the gateway
claw run
```

Or point at an existing config:

```bash
claw run --config /path/to/config.yaml
```

---

## Configuration (`config.yaml`)

```yaml
model_provider:
  type: openai            # openai | anthropic | ollama
  api_key: ${OPENAI_API_KEY}
  model: gpt-4o

channels:
  - id: discord-main
    type: discord
    token: ${DISCORD_TOKEN}
    dm_scope: per-peer    # main | per-peer | per-channel-peer | per-account-channel-peer

agents:
  - id: main
    default: true
    system_prompt: "You are a helpful assistant."
    workspace: ~/.openclaw/workspaces/main
    skills:
      - researcher
      - coder

bindings:
  - agent_id: main
    match:
      channel: discord-main

session:
  store: ~/.openclaw/sessions
  max_context_tokens: 8192

security:
  auth_mode: token
  token: ${GATEWAY_TOKEN}

server:
  port: 18789
  bind: loopback          # loopback | lan | custom
```

---

## Hermes Plugin Compatibility

All Hermes agent concepts map directly to this gateway. Existing Hermes skills, tools, and configs work without changes.

| Hermes concept | This gateway | Notes |
|---|---|---|
| `config.yaml` | `GatewayConfig` (Pydantic) | Same file, extended with `channels`, `bindings`, `server` sections |
| `SKILL.md` skills | `skills/loader.py` | YAML frontmatter + body — identical format |
| Toolsets | `tools/registry.py` | `register_tool(name, handler, description, parameters)` |
| Agent delegation | `routing/router.py` | 8-tier binding rules route messages to the right agent |
| Agent loop | `agent/loop.py` | LLM call → tool loop → response, same as Hermes |
| Session / memory | `session/manager.py` | Per-user JSONL store, same scoping semantics |
| Context engine | `context/engine.py` | Assembles system prompt + skills + history + tools |
| CLI | Click: `claw run/setup/status/channels/agents` | Hermes uses similar command names |
| Security | `SecurityConfig` (`none` / `token`) | Token auth via `Authorization: Bearer <token>` |

### Skills (`SKILL.md`)

Skills work identically — place them in the agent's `workspace/skills/` directory or reference them by name in `config.yaml`:

```markdown
---
name: researcher
description: Deep research and source citation
---

## Researcher

You excel at finding accurate, well-sourced information. Always cite your sources.
When uncertain, say so explicitly rather than guessing.
```

```yaml
agents:
  - id: main
    skills:
      - researcher   # loads workspace/skills/researcher.md
```

### Tools / Toolsets

Register tools the same way as Hermes toolsets:

```python
from openclaw.tools.registry import register_tool

register_tool(
    "get_weather",
    get_weather_handler,
    description="Get current weather for a location.",
    parameters={
        "type": "object",
        "properties": {
            "location": {"type": "string", "description": "City name or coordinates"},
        },
        "required": ["location"],
    },
)
```

Five tools are built in: `search_web`, `exec_command`, `read_file`, `write_file`, `search_files`.

---

## Migrating from a Hermes Gateway

### 1. Install and initialise

```bash
pip install openclaw
claw setup   # or copy your existing config (see section 2)
```

### 2. Translate your config

Most Hermes config keys carry over directly. Add the `channels`, `bindings`, and `server` blocks:

```yaml
# Hermes config (before)               # OpenClaw config (after)
model_provider:                         model_provider:
  type: openai                            type: openai
  api_key: ${OPENAI_API_KEY}              api_key: ${OPENAI_API_KEY}
  model: gpt-4o                           model: gpt-4o

agents:                                 agents:
  - id: main                              - id: main
    default: true                           default: true
    system_prompt: "..."                    system_prompt: "..."
    skills: [researcher]                    skills: [researcher]

                                        # New: add your messaging channels
                                        channels:
                                          - id: discord-main
                                            type: discord
                                            token: ${DISCORD_TOKEN}

                                        # New: route all discord messages to main agent
                                        bindings:
                                          - agent_id: main
                                            match:
                                              channel: discord-main

session:                                session:
  max_context_tokens: 8192               max_context_tokens: 8192

security:                               security:
  auth_mode: token                        auth_mode: token
  token: ${GATEWAY_TOKEN}                 token: ${GATEWAY_TOKEN}
```

### 3. Move skills — no changes needed

Skills in `SKILL.md` format work as-is. Copy them to your agent workspace:

```bash
cp -r ~/.hermes/skills ~/.openclaw/workspaces/main/skills
```

### 4. Port custom tools

Wrap each Hermes toolset handler with `register_tool` and call it at startup:

```python
# Before (Hermes toolset)
def my_tool(query: str) -> str:
    return do_something(query)

# After (OpenClaw tool registration)
from openclaw.tools.registry import register_tool

register_tool(
    "my_tool",
    my_tool,
    description="Does something with a query.",
    parameters={
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
    },
)
```

Call `register_all_builtin_tools()` to also load the five built-ins, then add your custom registrations before starting the server.

### 5. Start the gateway

```bash
claw run --config ~/.claw/config.yaml
```

Verify everything is connected:

```bash
claw status
claw channels
claw agents
```

---

## CLI reference

| Command | Description |
|---|---|
| `claw run` | Start the gateway server |
| `claw run --dry-run` | Validate config and exit |
| `claw setup` | Interactive setup wizard |
| `claw status` | Show config summary and diagnostics |
| `claw channels` | List configured channels |
| `claw agents` | List configured agents |

---

## Session scoping (`dm_scope`)

Controls how DM conversations are grouped into sessions:

| `dm_scope` | Session key | Use case |
|---|---|---|
| `main` | `agent:main:main` | All DMs share one context (Hermes default) |
| `per-peer` | `agent:main:direct:{userId}` | Each user gets their own session |
| `per-channel-peer` | `agent:main:{channel}:direct:{userId}` | Per-user per-channel isolation |
| `per-account-channel-peer` | `agent:main:{channel}:{account}:direct:{userId}` | Full multi-account isolation |

---

## Agent routing (bindings)

Messages are routed to agents via priority-ordered binding rules:

```yaml
bindings:
  # Exact user → VIP agent
  - agent_id: vip-support
    match:
      channel: discord-main
      peer_kind: direct
      peer_id: "123456789"

  # Guild role → specialised agent
  - agent_id: admin-agent
    match:
      channel: discord-main
      guild_id: "987654321"
      roles: ["admin", "moderator"]

  # Entire server → catch-all
  - agent_id: main
    match:
      channel: discord-main
      account_id: "*"
```

Resolution order: exact peer → parent peer (threads) → kind wildcard → guild+roles → guild → team → account → channel catch-all → default agent.

---

## Running tests

```bash
# Unit tests (no tokens needed)
pytest tests/ --ignore=tests/channels/test_discord_live.py

# Discord live tests (requires DISCORD_TEST_TOKEN)
DISCORD_TEST_TOKEN=<token> DISCORD_TEST_BOT_ID=<id> pytest tests/channels/test_discord_live.py -v
```

Set `DISCORD_TEST_TOKEN`, `DISCORD_TEST_BOT_ID`, and optionally `DISCORD_TEST_GUILD_ID` as repository secrets to run live tests in CI automatically.

---

## Requirements

- Python 3.11+
- An OpenAI-compatible LLM API (OpenAI, Anthropic via compatible endpoint, Ollama)
- A Discord bot token (see [Discord Developer Portal](https://discord.com/developers/applications))
