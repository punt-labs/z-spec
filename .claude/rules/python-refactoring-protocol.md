---
paths:
  - "**/*.py"
---

# Refactoring Protocol

Refactoring means small, incremental, behavior-preserving transformations.
Each step must leave the system running identically. Each step must improve
a measurable score. No big-bang rewrites.

## PY-RF-1: The Refactoring Loop

Every refactoring session follows this loop. No exceptions.

```text
1. MEASURE  → run `make report SRC=<module>` → record baseline scores
2. IDENTIFY → pick the single worst-scoring metric
3. PLAN     → choose exactly one transformation (see PY-RF-3 catalog)
4. APPLY    → make the change (one logical change, one commit)
5. TEST     → run the test suite; if tests fail, revert immediately
6. CHECK    → run `make check SRC=<module>` → must exit 0
7. MEASURE  → run `make report SRC=<module>` again
8. COMPARE  → at least one score must improve; no score may worsen by > 5%
9. COMMIT   → if pass, commit with message citing the metric improved
10. REPEAT  → go to step 2
```

**Hard rules**:

- Never combine two transformations in one step.
- Never skip the test step (if a module somehow lacks formal tests, create and
  run a behavioral snapshot per PY-RF-2; identical output means behavior is
  preserved).
- If a score worsens, revert the change entirely. Do not "fix forward."
- If no single transformation improves any score, stop and report.
- Every extraction deletes the old code and wires all callers in the same
  commit. A new class with zero callers is dead code, not a refactoring.

## PY-RF-2: What "Behavior Preserving" Means

A transformation is behavior-preserving if and only if:

1. All existing tests and behavioral snapshots produce identical output (diff
   the output).
2. The public API of every module remains unchanged (same function/class names,
   same parameter signatures, same return types).
3. `mypy --strict` passes before and after.
4. The old code path is deleted in the same commit as the new one. Every caller
   is updated to use the new path. Zero dead code — if you create a class, all
   callers use it before the commit lands. "Create now, wire later" is not
   refactoring — it is code duplication.

**Integration direction**: When you find a new class or module with zero callers
that was created as part of a refactoring, the fix is always **forward** — wire
callers to use the new code, then delete the old code path. Never **backward** —
deleting the new class and keeping the old functions undoes the structural
improvement and wastes the extraction work. The new code exists because the old
structure was wrong. The old structure is what gets deleted.

How to tell the difference between dead code and an unwired extraction:

- **Truly dead**: function/class that serves no purpose, was never part of a
  planned refactoring, has no design rationale → delete it
- **Unwired extraction**: new class created to replace old functions, but callers
  still point to the old path → wire callers forward, delete old path
- **Test**: does the new code implement the same behavior as an existing old code
  path? If yes, it's an unwired extraction — integrate forward. If no, it's
  genuinely dead — delete it.

**How to verify**:

```bash
# Before the change:
uv run <entry-point> > .tmp/before.txt 2>&1
# After the change:
uv run <entry-point> > .tmp/after.txt 2>&1
# Compare:
diff .tmp/before.txt .tmp/after.txt  # must produce no output
```

If there are no tests covering the code, the agent must create a behavioral
snapshot first (run all entry points, capture output) before starting any
refactoring.

## PY-RF-3: Transformation Catalog

Each transformation is one atomic step. Apply one at a time.

### Extract Class (procedural → OO)

**Trigger**: 3+ top-level functions share a parameter (operate on same data).
**Action**: Create a class. Move the shared parameter to `__new__`. Convert
functions to methods. Update all call sites. Delete the old functions.
**Completion test**: grep for the old function names — zero hits outside tests.
**Metric improved**: method_ratio (% of functions that are methods)

### Extract Method

**Trigger**: Function > 30 lines with identifiable sub-responsibilities.
**Action**: Extract a block into a new private method on the same class.
**Metric improved**: avg_complexity (radon CC)

### Introduce Property

**Trigger**: Public attribute accessed directly from outside the class.
**Action**: Prefix attribute with `_`, add `@property` getter.
**Metric improved**: encapsulation_ratio

### Push Down State

**Trigger**: Function takes 5+ parameters.
**Action**: Group related parameters into a class or dataclass.
**Metric improved**: avg_params

### Replace Dict with Class

**Trigger**: A `dict` or `TypedDict` is passed through 3+ functions and
accessed by string keys.
**Action**: Convert to a class with typed attributes and methods.
**Metric improved**: method_ratio, encapsulation_ratio

### Seal Leaf Class

**Trigger**: Concrete class at bottom of hierarchy without `@final`.
**Action**: Add `@final` decorator.
**Metric improved**: (compliance score, not a radon metric)

### Introduce Factory

**Trigger**: Constructor requires data owned by another class.
**Action**: Add factory method on the owning class; guard the constructor.
**Metric improved**: (compliance score)

### Split Module

**Trigger**: Module > 300 lines or > 3 classes.
**Action**: Extract one class and its helpers into a new module. Update imports.
**Metric improved**: module_size, classes_per_module

### Internalize Attribute

**Trigger**: Public attribute (`self.name`) without underscore.
**Action**: Rename to `self._name`, add property if external read needed.
**Metric improved**: encapsulation_ratio

## PY-RF-4: Prioritization Order

When multiple metrics are bad, fix in this order (each unlocks the next):

1. **Missing test coverage** → create behavioral snapshot first
2. **Public attributes** → internalize (PY-EN-1 violations block other refactors)
3. **God modules** → split (can't reason about 1000-line files)
4. **Procedural functions** → extract class (the core OO transformation)
5. **High complexity** → extract method
6. **Parameter bloat** → push down state into classes
7. **Missing patterns** → apply Factory/State/PubSub as identified

## PY-RF-5: Agent Reporting

After each refactoring step, the agent must report:

```text
STEP: <transformation name>
FILE: <file changed>
METRIC: <which score improved>
BEFORE: <score value>
AFTER: <score value>
TESTS: PASS | FAIL (reverted)
```

After a refactoring session (multiple steps), summarize:

```text
TOTAL STEPS: N
SCORES BEFORE: { method_ratio: X, encapsulation: Y, complexity: Z, ... }
SCORES AFTER:  { method_ratio: X, encapsulation: Y, complexity: Z, ... }
REVERTED: M steps (list which and why)
```

## PY-RF-6: Fixing Incomplete Extractions

When you inherit code where a prior refactoring created new classes/modules
but did not wire callers or delete old code:

1. **Identify the pairs.** For each new class, find the old function(s) it
   replaces. They will have the same behavior — same inputs, same outputs,
   same side effects.
2. **Wire callers.** Update every caller of the old function to use the new
   class. This is the hard part and the part that was skipped.
3. **Delete the old path.** Remove the old function. Remove any re-exports
   or shims that kept it alive.
4. **Update tests.** Tests that called the old function now call the new class.
   Tests that mocked the old function now mock the new class.
5. **Verify behavior.** `make check` must pass. Diff test output before/after
   — identical.

**Never delete the new code to "fix" the duplication.** The new code is the
target architecture. The old code is what gets removed. Deleting the new code
is a revert — it undoes structural improvement and returns to the state that
was already identified as needing change.

## PY-RF-7: When to Stop

Stop refactoring when any of these hold:

- All OO scores are above their thresholds (see oo_score.py)
- No single transformation improves any score
- The only remaining fix would break the public API, change invocation
  semantics, or add architectural complexity disproportionate to the metric
  improvement — document the reason and the remaining score
- The user says stop
- 10 consecutive steps have been applied (check in with the user)
