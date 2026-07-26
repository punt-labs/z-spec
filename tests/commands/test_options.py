"""Unit tests for the command parameter bundles."""

from __future__ import annotations

import pytest

from punt_zspec.commands.options import AnimateOptions, ProbOptions


def test_prob_options_defaults() -> None:
    opts = ProbOptions()

    assert opts.setsize == 2
    assert opts.max_ops == 1000
    assert opts.timeout_ms == 30000


def test_animate_options_defaults() -> None:
    opts = AnimateOptions()

    assert opts.steps == 20
    assert opts.setsize == 2


def test_prob_options_is_frozen() -> None:
    opts = ProbOptions()

    with pytest.raises(AttributeError):
        opts.setsize = 5  # type: ignore[misc]
