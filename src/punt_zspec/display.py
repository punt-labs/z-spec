"""LuxDisplay — the one module that renders opaque scenes through punt_lux."""

from __future__ import annotations

import logging
from typing import Any, Protocol, Self, final

from punt_zspec.commands.show import DisplayError

logger = logging.getLogger(__name__)


class ClientProvider(Protocol):
    """Return a connected lux client, or raise on connection failure."""

    # Any (PY-TS-9): punt_lux.client.LuxClient ships no type stubs.
    def __call__(self) -> Any: ...


class ClientReset(Protocol):
    """Drop any cached client so the next provider call reconnects fresh."""

    def __call__(self) -> None: ...


@final
class LuxDisplay:
    """Render a scene on a lux client, reconnecting once on socket failure.

    With no provider, each render constructs and connects its own client — the
    CLI path. The MCP server injects a provider/reset pair bound to its single
    persistent menu client so the process keeps one connection.
    """

    # ClientProvider | None (PY-TS-14): None = "build a fresh self-connecting
    # client per render" — the CLI default, a real mode, not a missing value.
    _provide: ClientProvider | None
    # ClientReset | None (PY-TS-14): None = "nothing to reset" — a self-built
    # client is discarded after each render, so there is no cache to drop.
    _reset: ClientReset | None
    __slots__ = ("_provide", "_reset")

    def __new__(
        cls,
        provide: ClientProvider | None = None,
        reset: ClientReset | None = None,
    ) -> Self:
        self = super().__new__(cls)
        self._provide = provide
        self._reset = reset
        return self

    def show(self, scene: object, *, frame_id: str, frame_title: str) -> None:
        """Render ``scene``; reconnect once on failure, then raise DisplayError."""
        try:  # PY-EH-5 exception: lux socket I/O is a genuine boundary
            self._render(scene, frame_id=frame_id, frame_title=frame_title)
        except (ConnectionError, OSError):
            if self._reset is not None:
                self._reset()
            try:
                self._render(scene, frame_id=frame_id, frame_title=frame_title)
            except (ConnectionError, OSError) as exc:
                logger.warning("Lux reconnect failed: %s", exc)
                raise DisplayError(str(exc)) from exc

    def _render(self, scene: object, *, frame_id: str, frame_title: str) -> None:
        client = self._provide() if self._provide is not None else self._connect()
        client.show(frame_id, [scene], frame_id=frame_id, frame_title=frame_title)

    @staticmethod
    def _connect() -> Any:  # Any (PY-TS-9): untyped LuxClient
        from punt_lux.client import LuxClient

        client = LuxClient(name="z-spec")
        if not client.is_connected:
            client.connect()
        if not client.listener_active:
            client.start_listener()
        return client
