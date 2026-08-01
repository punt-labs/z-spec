"""``ZSpecMenuRegistrar`` — register a z-spec menu callback, best-effort.

A thin, guarded transport over the REST client: :meth:`register` builds the
client and calls ``register_callback`` off-thread (both block), swallowing a down
or refusing luxd into a log line — a missing menu entry must never crash the
receive leg. The lux lease keeps the entry alive once registered; ``on_connect``
re-registers it after every handshake (register-fresh).
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Self, final

from punt_lux import HubUnavailableError
from punt_lux.operations import OpError

if TYPE_CHECKING:
    from collections.abc import Callable

    from punt_zspec.lux.ports import MenuClient

__all__ = ["ZSpecMenuRegistrar"]

logger = logging.getLogger(__name__)


@final
class ZSpecMenuRegistrar:
    """Register one menu callback over the REST client, failure-tolerant."""

    _connect: Callable[[], MenuClient]
    __slots__ = ("_connect",)

    def __new__(cls, connect: Callable[[], MenuClient]) -> Self:
        self = super().__new__(cls)
        self._connect = connect
        return self

    async def register(self, callback_id: str, label: str) -> None:
        """Register the ``label`` menu entry off-thread, dropping any lux failure.

        A best-effort REST I/O boundary (PY-EH-6): a down luxd logs a warning; any
        other transport fault is logged with its traceback and swallowed. Nothing
        is raised, so a failed registration can never escape into the receive
        leg's guarded restart and turn a missing menu into a dropped connection.
        """
        try:
            client = await asyncio.to_thread(self._connect)
            result = await asyncio.to_thread(
                client.register_callback, callback_id, label
            )
        except HubUnavailableError:
            logger.warning("luxd unavailable; %r menu entry not registered", label)
            return
        except Exception:
            logger.exception("[lux] %r menu registration failed", label)
            return
        if isinstance(result, OpError):
            logger.error(
                "luxd rejected the %r menu registration: %s", label, result.reason
            )
