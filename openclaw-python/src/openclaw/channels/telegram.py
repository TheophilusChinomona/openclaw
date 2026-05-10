"""Telegram channel adapter using python-telegram-bot."""

from __future__ import annotations

import re
from typing import Any

from openclaw.channels.base import ChannelAdapter
from openclaw.models.core import ChatType, PlatformMessage, RoutePeer

_PRIVATE_TYPES = {"private"}
_GROUP_TYPES = {"group", "supergroup", "channel"}


class TelegramChannelAdapter(ChannelAdapter):
    def __init__(
        self,
        channel_id: str,
        token: str,
        dm_scope: str = "main",
        bot_username: str = "",
    ) -> None:
        self.channel_id = channel_id
        self._token = token
        self._dm_scope = dm_scope
        self._bot_username = bot_username.lstrip("@").lower()
        self._app: Any = None
        self._on_message: Any = None

    async def start(self) -> None:
        from telegram.ext import Application, MessageHandler, filters

        self._app = Application.builder().token(self._token).build()
        if self._on_message:
            self._app.add_handler(MessageHandler(filters.TEXT, self._on_message))
        await self._app.initialize()
        await self._app.start()

    async def stop(self) -> None:
        if self._app:
            await self._app.stop()
            await self._app.shutdown()

    async def send_text(
        self,
        peer_id: str,
        text: str,
        thread_id: str | None = None,
    ) -> None:
        if self._app is None:
            return
        kwargs: dict[str, Any] = {"chat_id": int(peer_id), "text": text, "parse_mode": "Markdown"}
        if thread_id:
            try:
                kwargs["message_thread_id"] = int(thread_id)
            except ValueError:
                pass
        await self._app.bot.send_message(**kwargs)

    def normalize_event(self, raw_event: object) -> PlatformMessage | None:
        try:
            msg = raw_event.message  # type: ignore[union-attr]
        except AttributeError:
            return None
        if msg is None:
            return None

        text: str = getattr(msg, "text", "") or ""
        chat_type: str = getattr(getattr(msg, "chat", None), "type", "") or ""
        chat_id: int = getattr(getattr(msg, "chat", None), "id", 0) or 0
        from_id: int = getattr(getattr(msg, "from_user", None), "id", 0) or 0
        message_id: int = getattr(msg, "message_id", 0) or 0

        is_private = chat_type in _PRIVATE_TYPES
        is_group = chat_type in _GROUP_TYPES

        if is_group:
            # Only process if the bot is @mentioned
            mention = f"@{self._bot_username}" if self._bot_username else ""
            if mention and mention.lower() not in text.lower():
                return None
            # Strip the mention from the text
            if mention:
                text = re.sub(re.escape(mention), "", text, flags=re.IGNORECASE).strip()

        peer: RoutePeer
        thread_id: str | None = None

        if is_private:
            peer = RoutePeer(kind=ChatType.DIRECT, id=str(from_id))
        elif is_group:
            peer = RoutePeer(kind=ChatType.GROUP, id=str(chat_id))
            reply = getattr(msg, "reply_to_message", None)
            if reply is not None:
                thread_id = str(getattr(reply, "message_id", ""))
        else:
            peer = RoutePeer(kind=ChatType.CHANNEL, id=str(chat_id))

        return PlatformMessage(
            channel=self.channel_id,
            account_id="bot",
            peer=peer,
            text=text,
            message_id=str(message_id),
            thread_id=thread_id,
        )
