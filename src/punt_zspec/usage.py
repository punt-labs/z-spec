"""Record privacy-safe usage of each capability through ``punt-observe``.

Every CLI verb and MCP tool call emits one ``z-spec.<surface>.<capability>``
event, version 1, carrying only closed enums and a duration: the outcome, the
``CommandFailure`` kind when the command failed, and the wall time. Paths,
spec text and report JSON never enter a signal. Capture is local SQLite under
``~/.punt-labs/z-spec/`` by default and stops entirely under
``PUNT_TELEMETRY=off`` or ``Z_SPEC_TELEMETRY=off``; the exporter is
configuration, so instrumentation here never names one.
"""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import TYPE_CHECKING, Literal, Self, final

from punt_observe.telemetry import (
    DurationAttr,
    EnumAttr,
    SignalSchema,
    TelemetryConfig,
    open_telemetry,
)

from punt_zspec.commands.result import CommandFailure
from punt_zspec.logging_config import TOOL

if TYPE_CHECKING:
    from collections.abc import Generator

    from punt_observe.telemetry import Telemetry

    from punt_zspec.commands.result import CommandResult, JsonObject

__all__ = [
    "SCHEMA_VERSION",
    "Observation",
    "Surface",
    "Usage",
    "schemas",
    "signal_name",
]

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1
_SHUTDOWN_TIMEOUT_S = 2.0

type Surface = Literal["cli", "mcp"]
type Outcome = Literal["ok", "failed", "error"]

_SURFACES: tuple[Surface, ...] = ("cli", "mcp")
_OUTCOMES: tuple[Outcome, ...] = ("ok", "failed", "error")


def signal_name(surface: Surface, capability: str) -> str:
    """Return the ``<tool>.<surface>.<action>`` name of one capability's event.

    Args:
        surface: The client surface the call arrived on.
        capability: The canonical capability name from the registry.

    Returns:
        The signal name, with ``-`` spelled ``_`` as the schema grammar requires.
    """
    return f"{TOOL}.{surface}.{capability.replace('-', '_')}"


def schemas() -> tuple[SignalSchema, ...]:
    """Return the versioned event schema of every capability on both surfaces.

    Returns:
        One event schema per (surface, capability) pair.
    """
    from punt_zspec.commands.registry import CAPABILITIES

    attributes: dict[str, EnumAttr | DurationAttr] = {
        "outcome": EnumAttr(_OUTCOMES),
        "failure": EnumAttr(tuple(kind.value for kind in CommandFailure)),
        "duration_ms": DurationAttr(),
    }
    return tuple(
        SignalSchema(
            signal_name(surface, capability.name), SCHEMA_VERSION, "event", attributes
        )
        for surface in _SURFACES
        for capability in CAPABILITIES
    )


@final
class Observation:
    """The outcome of one capability call, filled in by the call site."""

    _outcome: Outcome
    _failure: CommandFailure | None
    __slots__ = ("_failure", "_outcome")

    def __new__(cls) -> Self:
        """Start an observation that succeeds unless told otherwise."""
        self = super().__new__(cls)
        self._outcome = "ok"
        self._failure = None
        return self

    def result[T: JsonObject](self, result: CommandResult[T]) -> CommandResult[T]:
        """Note *result*'s outcome and hand it back unchanged.

        Args:
            result: The command's result.

        Returns:
            The same result, so a call site can wrap its ``run`` call inline.
        """
        err = result.error
        if err is not None:
            self._outcome = "failed"
            self._failure = err.kind
        return result

    def fail(self, kind: CommandFailure) -> None:
        """Note an expected failure the surface met before the command ran.

        Args:
            kind: The failure mode, as a command would have reported it.
        """
        self._outcome = "failed"
        self._failure = kind

    def raised(self) -> None:
        """Note an unexpected exception, unless the failure was already noted."""
        if self._outcome == "ok":
            self._outcome = "error"

    @property
    def outcome(self) -> Outcome:
        """Return the call's outcome."""
        return self._outcome

    @property
    def failure(self) -> CommandFailure | None:
        """Return the failure kind of a failed call, or ``None``."""
        return self._failure


@final
class Usage:
    """Record one usage event per capability call on one surface.

    Disabled until the surface's entry point calls :meth:`start`, so importing
    a client module never opens a store.
    """

    _surface: Surface
    _telemetry: Telemetry
    __slots__ = ("_surface", "_telemetry")

    def __new__(cls, surface: Surface) -> Self:
        """Bind *surface* with capture disabled until :meth:`start`."""
        self = super().__new__(cls)
        self._surface = surface
        self._telemetry = open_telemetry(TOOL, (), TelemetryConfig(enabled=False))
        return self

    def start(self, config: TelemetryConfig | None = None) -> None:
        """Open capture for this process; the off switches always win.

        Args:
            config: Telemetry settings; the shared defaults when omitted.
        """
        self._telemetry = open_telemetry(
            TOOL, schemas(), config if config is not None else TelemetryConfig()
        )

    def stop(self) -> None:
        """Stop capture, bounding the wait for the store to flush."""
        self._telemetry.shutdown(timeout_s=_SHUTDOWN_TIMEOUT_S)

    @contextmanager
    def observe(self, capability: str) -> Generator[Observation]:
        """Time one capability call and record its outcome when it ends.

        Exceptions propagate unchanged; recording never raises.

        Args:
            capability: The canonical capability name from the registry.

        Yields:
            The observation the call site reports its result through.
        """
        observation = Observation()
        started = time.monotonic()
        try:
            yield observation
        except BaseException:
            observation.raised()
            raise
        finally:
            self._record(capability, observation, time.monotonic() - started)

    def _record(
        self, capability: str, observation: Observation, elapsed_s: float
    ) -> None:
        duration_ms = elapsed_s * 1000
        failure = observation.failure
        logger.info(
            "Completed %s via %s: outcome=%s failure=%s duration_ms=%.0f",
            capability,
            self._surface,
            observation.outcome,
            failure.value if failure is not None else "none",
            duration_ms,
        )
        attrs: dict[str, object] = {
            "outcome": observation.outcome,
            "duration_ms": duration_ms,
        }
        if failure is not None:
            attrs["failure"] = failure.value
        self._telemetry.event(
            signal_name(self._surface, capability), SCHEMA_VERSION, **attrs
        )
