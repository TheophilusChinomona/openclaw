"""Tests for the ChannelAdapter abstract base class."""

import pytest

from openclaw.channels.base import ChannelAdapter
from openclaw.models.core import ChatType, PlatformMessage, RoutePeer


class DummyChannel(ChannelAdapter):
    channel_id = "dummy"

    async def start(self) -> None:
        self._running = True

    async def stop(self) -> None:
        self._running = False

    async def send_text(self, peer_id: str, text: str, thread_id: str | None = None) -> None:
        self._last_sent = (peer_id, text, thread_id)

    def normalize_event(self, raw_event: object) -> PlatformMessage | None:
        if not isinstance(raw_event, dict):
            return None
        return PlatformMessage(
            channel=self.channel_id,
            account_id="bot",
            peer=RoutePeer(kind=ChatType.DIRECT, id=str(raw_event.get("from_id", ""))),
            text=str(raw_event.get("text", "")),
            message_id=str(raw_event.get("id", "")),
        )


def test_cannot_instantiate_abstract():
    with pytest.raises(TypeError):
        ChannelAdapter()  # type: ignore[abstract]


@pytest.mark.asyncio
async def test_dummy_channel_lifecycle():
    ch = DummyChannel()
    await ch.start()
    assert ch._running is True
    await ch.stop()
    assert ch._running is False


def test_normalize_event_returns_platform_message():
    ch = DummyChannel()
    msg = ch.normalize_event({"from_id": "123", "text": "hello", "id": "42"})
    assert msg is not None
    assert msg.text == "hello"
    assert msg.peer.kind == ChatType.DIRECT
    assert msg.peer.id == "123"
    assert msg.channel == "dummy"


def test_normalize_event_returns_none_for_invalid():
    ch = DummyChannel()
    assert ch.normalize_event("not a dict") is None


@pytest.mark.asyncio
async def test_send_text():
    ch = DummyChannel()
    await ch.send_text("user1", "hi there", thread_id="t1")
    assert ch._last_sent == ("user1", "hi there", "t1")
