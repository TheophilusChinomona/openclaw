"""Discord channel adapter using discord.py."""

from __future__ import annotations

import re
from typing import Any

from openclaw.channels.base import ChannelAdapter
from openclaw.models.core import ChatType, PlatformMessage, RoutePeer

_THREAD_TYPES = {"public_thread", "private_thread", "news_thread"}


class DiscordChannelAdapter(ChannelAdapter):
    def __init__(
        self,
        channel_id: str,
        token: str,
        dm_scope: str = "per-peer",
        bot_id: int = 0,
    ) -> None:
        self.channel_id = channel_id
        self._token = token
        self._dm_scope = dm_scope
        self._bot_id = bot_id
        self._client: Any = None

    async def start(self) -> None:
        import discord

        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        self._client = discord.Client(intents=intents)

        @self._client.event
        async def on_message(message: Any) -> None:  # type: ignore[misc]
            pass  # Router wires this up externally

        await self._client.start(self._token)

    async def stop(self) -> None:
        if self._client:
            await self._client.close()

    async def send_text(
        self,
        peer_id: str,
        text: str,
        thread_id: str | None = None,
    ) -> None:
        if self._client is None:
            return
        target_id = int(thread_id) if thread_id else int(peer_id)
        channel = self._client.get_channel(target_id)
        if channel:
            await channel.send(text)

    def normalize_event(self, raw_event: object) -> PlatformMessage | None:
        msg = raw_event
        author = getattr(msg, "author", None)
        if author is None:
            return None

        # Skip own messages
        if getattr(author, "id", None) == self._bot_id:
            return None

        # Skip other bots
        if getattr(author, "bot", False):
            return None

        content: str = getattr(msg, "content", "") or ""
        guild = getattr(msg, "guild", None)
        channel_obj = getattr(msg, "channel", None)
        channel_id_val = getattr(channel_obj, "id", 0)
        channel_type = getattr(getattr(channel_obj, "type", None), "name", "") or ""
        author_id: int = getattr(author, "id", 0)
        message_id: int = getattr(msg, "id", 0)
        guild_id: str | None = str(getattr(guild, "id", "")) if guild else None
        thread_id: str | None = None

        bot_mention = f"<@{self._bot_id}>"
        alt_mention = f"<@!{self._bot_id}>"

        is_dm = guild is None
        is_thread = channel_type in _THREAD_TYPES

        if not is_dm:
            # In guilds, require a mention
            if bot_mention not in content and alt_mention not in content:
                return None
            # Strip mention patterns
            content = re.sub(rf"<@!?{re.escape(str(self._bot_id))}>", "", content).strip()

        if is_thread:
            thread_id = str(channel_id_val)
            parent_id = getattr(channel_obj, "parent_id", None)
            peer_id_val = str(parent_id) if parent_id else str(channel_id_val)
        else:
            peer_id_val = str(author_id) if is_dm else str(channel_id_val)

        peer = RoutePeer(
            kind=ChatType.DIRECT if is_dm else ChatType.GROUP,
            id=peer_id_val,
        )

        return PlatformMessage(
            channel=self.channel_id,
            account_id=str(self._bot_id),
            peer=peer,
            text=content,
            message_id=str(message_id),
            thread_id=thread_id,
            guild_id=guild_id,
        )
