"""LuxDisplay — the one module that publishes opaque scenes to the lux Hub."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Protocol, Self, cast, final

from punt_lux import HubUnavailableError, LuxClient
from punt_lux.operations import OpError, RenderRequest, SceneShown
from punt_lux.operations.models.render import FrameSpec

from punt_zspec.commands.show import DisplayError

if TYPE_CHECKING:
    from punt_lux.operations import Scope
    from punt_lux.protocol import Element

logger = logging.getLogger(__name__)


class HubRenderer(Protocol):
    """Publish a whole scene to the lux Hub, returning a typed result."""

    def render(
        self, request: RenderRequest, *, scope: Scope
    ) -> SceneShown | OpError: ...


class HubConnector(Protocol):
    """Locate luxd and return a ``LuxClient``, raising when luxd is unreachable."""

    def __call__(self) -> LuxClient: ...


@final
class LuxDisplay:
    """Publish a scene to the lux Hub over its REST surface."""

    _connect: HubConnector
    __slots__ = ("_connect",)

    def __new__(cls, connect: HubConnector | None = None) -> Self:
        # None (PY-TS-14): use the real LuxClient connector — a concrete default.
        self = super().__new__(cls)
        self._connect = connect if connect is not None else LuxDisplay._default_connect
        return self

    @staticmethod
    def _default_connect() -> LuxClient:
        """Connect to luxd, raising HubUnavailableError if it is down."""
        return LuxClient.connect()

    def show(self, scene: object, *, frame_id: str, frame_title: str) -> None:
        """Publish ``scene`` to the Hub; raise DisplayError if it cannot land."""
        # cast (PY-TS-12): the injected builder always returns a punt_lux Element;
        # the Display protocol keeps it opaque so callers stay punt_lux-free.
        element = cast("Element", scene)
        request = RenderRequest(
            scene_id=frame_id,
            elements=[element.to_dict()],
            title=frame_title,
            frame=FrameSpec(frame_id=frame_id, frame_title=frame_title),
        )
        try:  # PY-EH-5 exception: locating and reaching luxd is an I/O boundary
            client = self._connect()
            result = client.sync.render(request, scope=client.scope)
        except (HubUnavailableError, OSError) as exc:
            logger.warning("Lux Hub unreachable: %s", exc)
            raise DisplayError(str(exc)) from exc
        if isinstance(result, OpError):
            logger.warning("Lux Hub rejected scene %s: %s", frame_id, result.reason)
            raise DisplayError(result.reason)
