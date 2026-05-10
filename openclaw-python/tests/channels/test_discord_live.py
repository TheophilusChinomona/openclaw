"""Live Discord tests — require DISCORD_TEST_TOKEN (set as CI secret or env var).

These tests call the real Discord REST API to verify:
  1. The bot token authenticates correctly
  2. The bot's identity can be fetched (catches scope/intent misconfigs)
  3. DiscordChannelAdapter normalises a Discord-shaped payload correctly

Run locally:
    DISCORD_TEST_TOKEN=<token> DISCORD_TEST_BOT_ID=<id> pytest tests/channels/test_discord_live.py -v

In CI: set DISCORD_TEST_TOKEN and DISCORD_TEST_BOT_ID as repository secrets.
Optional: DISCORD_TEST_GUILD_ID to also verify guild membership.
"""

from __future__ import annotations

import os

import httpx
import pytest

DISCORD_API = "https://discord.com/api/v10"
TOKEN = os.getenv("DISCORD_TEST_TOKEN", "")
BOT_ID = int(os.getenv("DISCORD_TEST_BOT_ID", "0") or "0")
GUILD_ID = os.getenv("DISCORD_TEST_GUILD_ID", "")

skip_no_token = pytest.mark.skipif(not TOKEN, reason="DISCORD_TEST_TOKEN not set")


def _auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bot {TOKEN}"}


@skip_no_token
@pytest.mark.asyncio
async def test_bot_token_authenticates():
    """Token must be valid — catches expired/revoked secrets early."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{DISCORD_API}/users/@me", headers=_auth_headers())
    assert resp.status_code == 200, f"Discord auth failed: {resp.status_code} {resp.text}"
    data = resp.json()
    assert "id" in data
    assert data.get("bot") is True


@skip_no_token
@pytest.mark.asyncio
async def test_bot_identity_matches_configured_id():
    """Bot ID from the API must match DISCORD_TEST_BOT_ID when set."""
    if not BOT_ID:
        pytest.skip("DISCORD_TEST_BOT_ID not set")
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{DISCORD_API}/users/@me", headers=_auth_headers())
    assert resp.status_code == 200
    data = resp.json()
    assert int(data["id"]) == BOT_ID, (
        f"Bot ID mismatch: API returned {data['id']}, expected {BOT_ID}. "
        "Update DISCORD_TEST_BOT_ID to match the token."
    )


@skip_no_token
@pytest.mark.asyncio
async def test_guild_membership():
    """Bot must be a member of the configured test guild."""
    if not GUILD_ID:
        pytest.skip("DISCORD_TEST_GUILD_ID not set")
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{DISCORD_API}/guilds/{GUILD_ID}",
            headers=_auth_headers(),
            params={"with_counts": "false"},
        )
    assert resp.status_code == 200, (
        f"Cannot access guild {GUILD_ID}: {resp.status_code}. "
        "Invite the test bot to the server and enable the SERVER MEMBERS intent."
    )


@skip_no_token
def test_adapter_normalises_realistic_dm_payload():
    """Adapter must handle the exact shape Discord sends for a DM."""
    from unittest.mock import MagicMock

    from openclaw.channels.discord import DiscordChannelAdapter
    from openclaw.models.core import ChatType

    bot_id = BOT_ID or 99999
    adapter = DiscordChannelAdapter(
        channel_id="discord-live",
        token=TOKEN,
        dm_scope="per-peer",
        bot_id=bot_id,
    )

    # Replicate Discord.py's message object shape for a DM
    msg = MagicMock()
    msg.content = "Hello bot!"
    msg.id = 1234567890
    msg.author.id = 888
    msg.author.bot = False
    msg.guild = None  # DM → no guild
    msg.channel.id = 777
    msg.channel.type.name = "private"
    msg.channel.recipient.id = 888

    result = adapter.normalize_event(msg)
    assert result is not None
    assert result.peer.kind == ChatType.DIRECT
    assert result.text == "Hello bot!"
    assert result.guild_id is None


@skip_no_token
def test_adapter_normalises_realistic_guild_message():
    """Adapter must handle the exact shape Discord sends for a guild message with @mention."""
    from unittest.mock import MagicMock

    from openclaw.channels.discord import DiscordChannelAdapter
    from openclaw.models.core import ChatType

    bot_id = BOT_ID or 99999
    adapter = DiscordChannelAdapter(
        channel_id="discord-live",
        token=TOKEN,
        dm_scope="per-peer",
        bot_id=bot_id,
    )

    msg = MagicMock()
    msg.content = f"<@{bot_id}> help me please"
    msg.id = 9999
    msg.author.id = 111
    msg.author.bot = False
    msg.guild = MagicMock()
    msg.guild.id = int(GUILD_ID) if GUILD_ID else 555
    msg.channel.id = 333
    msg.channel.type.name = "text"

    result = adapter.normalize_event(msg)
    assert result is not None
    assert result.peer.kind == ChatType.GROUP
    assert f"<@{bot_id}>" not in result.text
    assert "help me please" in result.text
    assert result.guild_id == str(msg.guild.id)
