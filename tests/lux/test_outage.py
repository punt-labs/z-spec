"""Tests for ``ZSpecLegOutage``: one loud record per outage, plus each new fault."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from punt_zspec.lux.outage import ZSpecLegOutage

if TYPE_CHECKING:
    from pytest import LogCaptureFixture

_LOGGER = "punt_zspec.lux.outage"


def _levels(caplog: LogCaptureFixture) -> list[int]:
    return [r.levelno for r in caplog.records if r.name == _LOGGER]


def test_a_fault_after_luxd_went_down_logs_at_error_once(
    caplog: LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger=_LOGGER)
    outage = ZSpecLegOutage()
    try:
        raise RuntimeError("boom")
    except RuntimeError:
        outage.failed("luxd is down", 5.0)
        outage.failed("the menu leg failed", 5.0, fault=True)
        outage.failed("the menu leg failed", 5.0, fault=True)
    outage.close("terminated")

    assert _levels(caplog) == [
        logging.WARNING,
        logging.ERROR,
        logging.DEBUG,
        logging.INFO,
    ]
    error = next(r for r in caplog.records if r.levelno == logging.ERROR)
    assert error.exc_info is not None


def test_a_closed_outage_reopens_loudly(caplog: LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, logger=_LOGGER)
    outage = ZSpecLegOutage()
    outage.failed("luxd is down", 5.0)
    outage.close("recovered")
    outage.failed("luxd is down", 5.0)

    assert _levels(caplog) == [logging.WARNING, logging.INFO, logging.WARNING]
