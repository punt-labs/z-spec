"""Metric thresholds and the direction-aware comparison semantics."""

from __future__ import annotations

from typing import ClassVar


class Thresholds:
    """OO metric thresholds plus the ordering semantics each metric obeys.

    A metric's operator (``>=``, ``<=``, ``==``) defines both its absolute
    target and what "better" means: for ``==`` metrics, closer to the target
    is better; for the others, the operator direction is the ordering.
    """

    TABLE: ClassVar[dict[str, tuple[str, float]]] = {
        "method_ratio": (">=", 0.80),
        "encapsulation_ratio": (">=", 1.0),
        "avg_params": ("<=", 4.0),
        "max_complexity": ("<=", 10),
        "avg_complexity": ("<=", 5.0),
        "module_size": ("<=", 300),
        "classes_per_module": ("<=", 3),
        "class_to_func_ratio": (">=", 0.5),
        "init_violations": ("==", 0),
        "public_attr_violations": ("==", 0),
        "future_annotations": ("==", 1),
    }

    @classmethod
    def names(cls) -> tuple[str, ...]:
        """Return the tracked metric names in table order."""
        return tuple(cls.TABLE)

    @classmethod
    def describe(cls, metric: str) -> str:
        """Return a human-readable ``op target`` label for a metric."""
        op, target = cls.TABLE[metric]
        return f"{op} {target}"

    @classmethod
    def meets(cls, metric: str, value: float) -> bool:
        """Return whether value satisfies the metric's absolute threshold."""
        op, target = cls.TABLE[metric]
        if op == ">=":
            return value >= target
        if op == "<=":
            return value <= target
        return value == target

    @classmethod
    def better_or_equal(cls, metric: str, current: float, baseline: float) -> bool:
        """Return whether current is at least as good as baseline."""
        op, target = cls.TABLE[metric]
        if op == ">=":
            return current >= baseline
        if op == "<=":
            return current <= baseline
        return abs(current - target) <= abs(baseline - target)

    @classmethod
    def strictly_better(cls, metric: str, current: float, baseline: float) -> bool:
        """Return whether current is strictly better than baseline."""
        op, target = cls.TABLE[metric]
        if op == ">=":
            return current > baseline
        if op == "<=":
            return current < baseline
        return abs(current - target) < abs(baseline - target)
