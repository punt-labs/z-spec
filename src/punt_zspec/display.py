"""LuxDisplay — the one module that publishes opaque scenes to the lux Hub."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Protocol, Self, cast, final

from punt_lux.operations import OpError, RenderRequest, SceneShown
from punt_lux.operations.models.render import FrameSpec
from punt_lux.rest_client import LuxRestClient
from punt_lux.rest_transport import HubUnavailableError

from punt_zspec.commands.show import DisplayError

if TYPE_CHECKING:
    from punt_lux.protocol import Element

logger = logging.getLogger(__name__)


class HubRenderer(Protocol):
    """Publish a whole scene to the lux Hub, returning a typed result."""

    def render(self, request: RenderRequest) -> SceneShown | OpError: ...


class HubConnector(Protocol):
    """Locate luxd and return a Hub renderer, raising when luxd is unreachable."""

    def __call__(self) -> HubRenderer: ...


@final
class LuxDisplay:
    """Publish a scene to the 0.21 lux Hub over its REST surface.

    Each render locates luxd's port and PUTs the scene to ``/scenes/{id}``; the
    Hub becomes the scene's authority and replicates it to the display. In 0.21
    the display socket is Hub-internal — a scene reaches the window only through
    the Hub, never a direct socket send — so this is the sole publishing path.
    """

    _connect: HubConnector
    __slots__ = ("_connect",)

    def __new__(cls, connect: HubConnector | None = None) -> Self:
        # HubConnector | None (PY-TS-14): None = "use the real LuxRestClient
        # connector" — the CLI/server default; a concrete mode, not a missing value.
        self = super().__new__(cls)
        self._connect = connect if connect is not None else LuxDisplay._default_connect
        return self

    @staticmethod
    def _default_connect() -> HubRenderer:
        """Connect to luxd over REST, raising HubUnavailableError if it is down."""
        return LuxRestClient.connect()

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
            result = self._connect().render(request)
        except (HubUnavailableError, OSError) as exc:
            logger.warning("Lux Hub unreachable: %s", exc)
            raise DisplayError(str(exc)) from exc
        if isinstance(result, OpError):
            logger.warning("Lux Hub rejected scene %s: %s", frame_id, result.reason)
            raise DisplayError(result.reason)
