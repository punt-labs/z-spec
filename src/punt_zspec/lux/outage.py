"""``ZSpecLegOutage`` — one Lux receive-leg outage, logged once, not per retry.

A luxd that stays down makes the receive leg retry every few seconds for as long
as the outage lasts. Logging each attempt at WARNING buries the one actionable
fact under noise, so the outage opens with one WARNING, repeats go to DEBUG,
and its end is one INFO summary naming the outcome and how many attempts
failed. The first unexpected fault in an outage is logged at ERROR with its
traceback, whether it opens the outage or arrives after luxd went down.
"""

from __future__ import annotations

import logging
from typing import Self, final

__all__ = ["ZSpecLegOutage"]

logger = logging.getLogger(__name__)


@final
class ZSpecLegOutage:
    """Count one receive-leg outage from its first failure to its end."""

    _failures: int
    _faulted: bool
    __slots__ = ("_failures", "_faulted")

    def __new__(cls) -> Self:
        """Start with no outage open."""
        self = super().__new__(cls)
        self._failures = 0
        self._faulted = False
        return self

    def failed(self, why: str, retry_seconds: float, *, fault: bool = False) -> None:
        """Report one failed attempt: loudly if it opens the outage, else at DEBUG.

        Args:
            why: What went wrong, in fixed words safe to log.
            retry_seconds: How long the leg waits before its next attempt.
            fault: The failure is an unexpected exception, logged at ERROR with
                its traceback the first time one occurs in this outage, even
                when a WARNING already opened it.
        """
        self._failures += 1
        first_fault = fault and not self._faulted
        self._faulted = self._faulted or fault
        if self._failures == 1 or first_fault:
            logger.log(
                logging.ERROR if fault else logging.WARNING,
                "[lux] %s; retrying the z-spec menu leg every %.1fs "
                "(repeats logged at DEBUG)",
                why,
                retry_seconds,
                exc_info=fault,
            )
            return
        logger.debug(
            "[lux] %s (attempt %d); reconnecting the z-spec menu leg in %.1fs",
            why,
            self._failures,
            retry_seconds,
            exc_info=fault,
        )

    def close(self, outcome: str) -> None:
        """Summarize an open outage once with its ``outcome``, then forget it."""
        if self._failures:
            logger.info(
                "[lux] z-spec menu leg outcome=%s failures=%d",
                outcome,
                self._failures,
            )
        self._failures = 0
        self._faulted = False
