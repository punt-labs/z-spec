---
paths:
  - "**/*.py"
---

# Inheritance and Composition Standards

## PY-IC-1: Composition over Inheritance When Behavior Differs

**Statement**: If a subclass would violate the Liskov Substitution Principle
(i.e., its behavior is not substitutable for the parent), use composition
instead of inheritance.

**Canonical example**: a ranked stack composes a general-purpose stack rather
than inheriting from it, because its placement semantics differ from plain
push — an override would not be substitutable.

**Criterion**:

- Pass: subclass can be used anywhere the parent is expected without surprises
- Fail: subclass overrides a method with incompatible behavior

**Tooling**:

- LLM review: check that every override preserves parent contract
- mypy: catches signature incompatibilities but not behavioral violations

## PY-IC-2: @final on Leaf Classes

**Statement**: Mark concrete classes that should not be subclassed with `@final`
from `typing`. This is required when the class uses patterns (flyweight, sealed
hierarchy) that break under subclassing.

**Criterion**:

- Pass: leaf classes in sealed hierarchies have `@final`; `@final` classes with
  flyweight caches always have it
- Fail: flyweight class without `@final`; concrete class in sealed hierarchy
  without `@final`

**Tooling**:

- mypy: enforces `@final` (error if someone subclasses a final class)
- Grep: `grep -n "@final"` to audit coverage
- AST check: classes with `__instances` cache must have `@final`

## PY-IC-3: Mixins Must Have No Constructor and No Instance Data

**Statement**: A mixin provides abstract method declarations plus default
implementations built on those abstractions. Mixins must not define `__new__`
or `__init__` and must not store instance data.

**Required**: `__slots__ = ()` on every mixin class.

**Criterion**:

- Pass: mixin has `__slots__ = ()`, no constructor, no `self._attr =` assignments
- Fail: mixin stores instance data or defines a constructor

**Tooling**:

- AST check: classes inheriting from multiple parents where any parent has
  `__slots__ = ()` → verify mixin rules
- Grep: `grep -A2 "class.*Mixin"` for `__slots__`

## PY-IC-4: **slots** as Tuples on Mixins and Interfaces

**Statement**: When declaring `__slots__`, always use a tuple literal. Never
use a list (mutable after class creation, misleading) or a dict (cursed).

**Criterion**:

- Pass: `__slots__ = ("field_a", "field_b")` or `__slots__ = ()`
- Fail: `__slots__ = ["field_a"]` or `__slots__ = {"field_a": ""}`

**Tooling**:

- AST check: `__slots__` assignment RHS must be `ast.Tuple`
- Grep: `grep -n "__slots__"` and visually verify tuple syntax

## PY-IC-5: super() by Default; Explicit Dispatch for Diamond

**Statement**: Always use `super()` for method calls up the hierarchy. Resort to
explicit `ClassName.method(self)` only when resolving diamond inheritance
conflicts where you need a specific parent's version.

**Rationale**: `super()` respects MRO and is resilient to hierarchy refactoring.
Explicit `ParentClass.method(self)` bypasses intermediate classes and breaks if
the hierarchy changes.

**Criterion**:

- Pass: `super().__new__(cls)`, `super().method()` as default
- Fail: `ParentClass.__new__(cls, ...)` without diamond justification

**Tooling**:

- Grep: `grep -Pn "\b[A-Z]\w+\.__new__\(cls"` to find explicit parent calls
- LLM review: verify diamond justification when explicit dispatch found

## PY-IC-6: Single Responsibility Principle

**Statement**: Every component — module, class, method, function — should have a
single well-defined responsibility at its level of abstraction.

**Application**:

- One concept per module (orders in `orders.py`, invoices in `invoices.py`)
- Constructor delegates to methods (`__new__` → `update()` → `add()`)
- Methods delegate to other methods (`__sub__` → `__add__` + `__neg__`)

**Criterion**:

- Pass: each class has one reason to change; methods do one thing
- Fail: god class with mixed responsibilities; method that validates, transforms,
  persists, and notifies in a single block

**Tooling**:

- Heuristic: class > 300 lines or method > 50 lines → review
- LLM review for semantic responsibility assessment

## PY-IC-7: Open-Closed Principle

**Statement**: Parent class logic should not need modification to support derived
class needs. Use inheritance/delegation to extend behavior.

**Criterion**:

- Pass: new subclass works without modifying parent
- Fail: adding a subclass requires changes to the parent class

**Tooling**:

- LLM review: check that parent classes are closed for modification
- Git diff: new subclass PR should not modify parent class files

## PY-IC-8: Dependency Direction — Core Never Imports Presentation

**Statement**: The dependency arrow always points inward. Core/domain modules
must never import from presentation modules (CLI, server, UI). Presentation
imports core, never the reverse.

**Layers** (inner → outer):

1. **Types/Protocols** — importable with zero heavy dependencies
2. **Core/Domain** — business logic, data access
3. **Commands** — orchestration (optional layer, see PL-PA-3)
4. **Presentation** — CLI, MCP server, REST API

A module in layer N may import from layers 1..N-1, never from N+1.

**Criterion**:

- Pass: `core.py` has no `from .cli import` or `from .server import`
- Fail: core module imports from CLI, server, or UI module

**Tooling**:

- Grep: `grep -rn "from.*cli import\|from.*server import" --include="*.py" src/core*`
  — should return zero hits
- AST check: build import graph, verify no edges from core → presentation
- LLM review: audit import headers of core modules

## PY-IC-9: Types and Protocols in Their Own Modules

**Statement**: Dataclasses, Protocol classes, type aliases, and TypedDicts belong
in dedicated modules (`types.py` or a `types/` package). These must be
importable without pulling in heavy dependencies or triggering side effects.

**Rationale**: Separating type definitions allows other packages and tools to
import the type contracts without importing the implementation. This is
especially important for avoiding circular imports and for keeping
`TYPE_CHECKING` guards clean.

**Criterion**:

- Pass: Protocol/dataclass definitions in `types.py` or dedicated module
- Fail: Protocol defined inline in the same module as its implementation

**Tooling**:

- LLM review: Protocol and dataclass definitions in core modules → suggest extraction
- Grep: `grep -rn "class.*Protocol" --include="*.py"` — verify location
