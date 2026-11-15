---
paths:
  - "**/*.py"
---

# OO Standards Adoption

## PL-OA-1: Ratchet — Every Commit Improves OO Quality

**Statement**: The OO Python rules (PY-CC, PY-EN, PY-TS, PY-IC, PY-OP, PY-DP,
PY-EH, PY-OO, PY-CS) represent the target standard. Existing code does not yet
fully comply. The rule is: every commit must improve compliance, never regress.

When you touch a file:
1. Run `python tools/oo_score.py <file>` before your change — record the baseline
2. Make your change
3. Run `python tools/oo_score.py <file>` after — no metric may worsen
4. If you can improve a metric while making your change, do so

You are not required to fix an entire file in one pass. You are required to
leave every file better than you found it.

**Criterion**:
- Pass: OO score does not regress on any touched file; at least one metric improves
- Fail: OO score worsens on a touched file; or opportunity to improve was ignored

**Tooling**:
- `python tools/oo_score.py <file>` — before and after every change
- `python tools/oo_score.py <directory> --threshold` — per-file breakdown

## PL-OA-2: The oo_score.py Tool Is Required

**Statement**: Every Python project must have `tools/oo_score.py` available.
This is a zero-dependency AST analysis script (stdlib only) that produces
numeric OO quality metrics. Copy it from the canonical source at
`~/Coding/oop-course-python/tools/oo_score.py`.

**Metrics and thresholds**:

| Metric | Target | What it catches |
|--------|--------|----------------|
| method_ratio | >= 0.80 | Procedural modules (functions not in classes) |
| encapsulation_ratio | == 1.0 | Public attributes (missing _ prefix) |
| avg_params | <= 4.0 | Parameter bloat (should be an object) |
| max_complexity | <= 10 | God functions (worst single function) |
| avg_complexity | <= 5.0 | Sustained complexity (many moderately-complex functions) |
| module_size | <= 300 | God modules |
| classes_per_module | <= 3 | Unfocused modules |
| class_to_func_ratio | >= 0.5 | Procedural code disguised as a module |
| init_violations | == 0 | __init__ used instead of __new__ |
| public_attr_violations | == 0 | self.name without underscore |
| future_annotations | == 1 | Missing from __future__ import annotations |

**Criterion**:
- Pass: `tools/oo_score.py` exists in the project and runs without error
- Fail: tool missing or broken

## PL-OA-3: Apply the Refactoring Protocol for Legacy Code

**Statement**: When working on a file that violates OO standards, follow
the refactoring protocol in `python-refactoring-protocol.md`. Key principle:
one transformation per step, tests pass at each step, score improves at
each step. Never big-bang rewrite.

The refactoring protocol applies when:
- You are asked to improve OO quality of existing code
- You touch a file with low OO scores and have scope to improve it
- A code review flags OO violations in code you changed

The refactoring protocol does NOT apply when:
- You are writing new code (write it correctly from the start)
- The change is a one-line bug fix with no reasonable OO improvement nearby
