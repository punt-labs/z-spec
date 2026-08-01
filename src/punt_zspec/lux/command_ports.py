"""Receive-leg command ports: the guarded menu registrar and the click command.

``MenuRegistrar`` is the failure-tolerant ``register_callback`` the subscription
drives from ``on_connect``. ``ClickCommand`` is the one method a menu click runs —
``BrowseCommand``/``PickerCommand`` satisfy it structurally — and
``ClickCommandFactory`` binds one to the server-owned ``Display``. Protocols
(PY-TS-6) so the subscription routes clicks with fakes in tests.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from punt_zspec.commands.show import Display

__all__ = ["ClickCommand", "ClickCommandFactory", "MenuRegistrar"]


@runtime_checkable
class MenuRegistrar(Protocol):
    """The guarded registration of one menu callback the subscription drives."""

    async def register(self, callback_id: str, label: str) -> None:
        """Register the menu callback, swallowing a down or refusing luxd."""
        ...


@runtime_checkable
class ClickCommand(Protocol):
    """One render a menu click runs — a second caller of a shipped command."""

    # object return (PY-TS-14): the command's typed CommandResult, forwarded
    # uninspected — a click is best-effort, so the subscription discards it.
    def run(self, target: Path, /, *, frame_id: str) -> object:
        """Render ``target`` into ``frame_id`` (the raised Hub scene id)."""
        ...


# A factory binding a ClickCommand to the server-owned Display (PY-TS-8 alias).
type ClickCommandFactory = Callable[[Display], ClickCommand]
