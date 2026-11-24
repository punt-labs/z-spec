"""Validate quarantine metadata before pytest deselects test cases."""

from __future__ import annotations

import re
from datetime import UTC, date, datetime, timedelta

import pytest


def _expiry(value: object) -> date | None:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def quarantine_is_valid(mark: pytest.Mark, today: date) -> bool:
    """Check that the quarantine has an issue, an owner and an active deadline."""
    issue = mark.kwargs.get("issue")
    owner = mark.kwargs.get("owner")
    reason = mark.kwargs.get("reason")
    expiry = _expiry(mark.kwargs.get("expires"))
    return (
        not mark.args
        and isinstance(issue, str)
        and re.fullmatch(r"PL-[1-9][0-9]*", issue) is not None
        and isinstance(owner, str)
        and bool(owner.strip())
        and isinstance(reason, str)
        and bool(reason.strip())
        and expiry is not None
        and today <= expiry <= today + timedelta(days=14)
    )


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Reject invalid or expired quarantines, even outside the selected suite."""
    today = datetime.now(UTC).date()
    for item in items:
        for mark in item.iter_markers("quarantine"):
            if not quarantine_is_valid(mark, today):
                msg = (
                    f"{item.nodeid}: quarantine requires a Linear issue, named "
                    "owner, reason, and an unexpired YYYY-MM-DD deadline within 14 days"
                )
                raise pytest.UsageError(msg)
