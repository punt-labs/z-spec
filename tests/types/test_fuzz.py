"""Tests for punt_zspec.types.fuzz."""

from __future__ import annotations

from punt_zspec.types import FuzzError, FuzzResult


def test_to_dict_serializes_each_error() -> None:
    result = FuzzResult(ok=False, errors=[FuzzError(3, 7, "type clash")])
    assert result.to_dict() == {
        "ok": False,
        "errors": [{"line": 3, "column": 7, "message": "type clash"}],
    }


def test_to_dict_empty_errors_is_empty_list() -> None:
    assert FuzzResult(ok=True).to_dict() == {"ok": True, "errors": []}


def test_raw_output_is_not_serialized() -> None:
    result = FuzzResult(ok=True, raw_output="lots of noise")
    assert "raw_output" not in result.to_dict()
