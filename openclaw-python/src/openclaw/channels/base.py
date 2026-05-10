"""Abstract base class for all channel adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod

from openclaw.models.core import PlatformMessage


class ChannelAdapter(ABC):
    """Common interface every channel adapter must implement."""

    channel_id: str

    @abstractmethod
    async def start(self) -> None:
        """Connect and begin receiving events."""

    @abstractmethod
    async def stop(self) -> None:
        """Disconnect and release resources."""

    @abstractmethod
    async def send_text(
        self,
        peer_id: str,
        text: str,
        thread_id: str | None = None,
    ) -> None:
        """Send a text reply to a peer (optionally in a thread)."""

    @abstractmethod
    def normalize_event(self, raw_event: object) -> PlatformMessage | None:
        """Convert a platform-specific event into a PlatformMessage.

        Return None to skip (bot's own message, non-text events, etc.).
        """
