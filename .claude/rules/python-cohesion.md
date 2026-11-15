---
paths:
  - "**/*.py"
---

# Class Cohesion Standards

## PL-CO-1: LCOM — Lack of Cohesion of Methods

**Statement**: Every class should have high cohesion — its methods should
operate on shared instance state. LCOM measures the fraction of method
pairs that share no `self._*` attributes. A class where most methods
touch disjoint data is doing multiple jobs and should be split.

**Computation**: For each pair of instance methods (excluding static and
class methods), check whether their `self._*` attribute sets intersect.
LCOM = (pairs with empty intersection) / (total pairs). Range 0.0
(perfectly cohesive) to 1.0 (no methods share any data). Classes with
0 or 1 instance methods have LCOM 0.0 (trivially cohesive).

**Criterion**:
- Pass: max LCOM across classes in a module <= 0.8
- Fail: any class has LCOM > 0.8

**Tooling**:
- `tools/oo_coupling.py` — `max_lcom` and `avg_lcom` metrics
- LLM review: classes with LCOM > 0.5 are candidates for splitting even
  if they pass the threshold

## PL-CO-2: Responsibility Count

**Statement**: A class should have at most two disjoint groups of methods
that operate on non-overlapping state. More than two groups means the
class has multiple responsibilities and should be decomposed.

**Symptoms of violation**:
- Provider classes with `synthesize()`, `health_check()`, and
  `resolve_voice()` touching completely different attributes
- Manager classes with creation, monitoring, and cleanup methods
  that share no instance data

**Criterion**:
- Pass: methods cluster into <= 2 groups by shared attribute access
- Fail: 3+ disjoint method clusters in a single class

**Tooling**:
- LLM review: examine LCOM > 0.5 classes and identify disjoint clusters
- Future: automated cluster detection in `oo_coupling.py`

## PL-CO-3: Module Cohesion

**Statement**: Classes in the same module must be related — they should
reference each other, share types, or collaborate on a single domain
concept. A module containing unrelated classes is a filing cabinet,
not a cohesive unit.

**Criterion**:
- Pass: every class in the module imports from, inherits from, or
  references at least one other class in the same module (or the module
  has only one class)
- Fail: classes in the module have no import/reference edges between them

**Tooling**:
- `tools/oo_coupling.py` — `pkg_cohesion` metric at the package level
- LLM review: modules with 3+ classes that don't reference each other
