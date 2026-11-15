---
paths:
  - "**/*.py"
---

# Design Pattern Standards

These patterns are explicitly taught and named in the course. Apply the correct
pattern when the situation matches. Do not invent patterns not listed here.

## PY-DP-1: Flyweight (Object Caching)

**When**: Immutable value objects where identity can equal equality.
**Implementation**: Class-level `WeakValueDictionary` cache in `__new__`. Check
cache before creating a new instance. Always pair with `@final`.
**Required**: `from weakref import WeakValueDictionary` (not plain `dict`, which
causes memory leaks by holding strong references).

**Tooling**:
- Grep: `WeakValueDictionary` usage paired with `@final`
- AST: classes with `__instances` must use `WeakValueDictionary`, not `dict`

## PY-DP-2: Factory Pattern

**When**: One class owns data (e.g., UIDs) required for constructing another.
**Implementation**: Factory class has a creation method; created class refuses
direct construction via guard check (see PY-CC-3, PY-CC-4).

**Tooling**:
- Test: direct construction raises `TypeError`
- LLM review: classes with UID/ID allocation use factory pattern

## PY-DP-3: State Pattern

**When**: A class behaves differently depending on internal state, with explicit
transition methods.
**Implementation**: `Literal` type for state values. Protocol interfaces per
state. Transition methods validate current state, update it, fire events, and
delete stale attributes. Use `cast()` to narrow the return type after transition.

**Tooling**:
- mypy: Protocol satisfaction verified statically
- Test: attempt invalid transitions, verify `ValueError`
- AST: state transition methods must check `self.__state` before modifying it

## PY-DP-4: Builder Pattern

**When**: An object's data can be set in arbitrary order, at different times.
**Implementation**: Setter methods on draft/incomplete objects. Fluent API
(`-> Self`) for chaining. Validation on transition (not on each set).

**Tooling**:
- mypy: return type `Self` on setter methods
- LLM review: draft objects allow partial construction

## PY-DP-5: Memento Pattern

**When**: Undo/restore functionality is needed for object state.
**Implementation**: `memento()` returns a snapshot (shallow copy of internal
dict). `restore()` accepts a snapshot and replaces current state.

**Tooling**:
- Test: snapshot → modify → restore → verify original values

## PY-DP-6: Prototype Pattern

**When**: Creating new objects from existing blueprints with different identity.
**Implementation**: `clone()` creates a new instance via the factory, then
restores a memento from the original.

**Tooling**:
- Test: clone produces a distinct object with same data but different ID

## PY-DP-7: Singleton Pattern

**When**: Exactly one global instance should exist (e.g., TimeServer).
**Implementation**: `__new__` checks for and returns an existing class-level
instance.

**Tooling**:
- Test: `ClassName() is ClassName()` must be `True`

## PY-DP-8: PubSub (Publish-Subscribe) Pattern

**When**: Objects need to react to events in other objects without tight coupling.
**Implementation**: Registration methods (`on_event(callback)`), unregistration
methods, and private trigger methods (`__trigger_event()`). Callbacks stored in
`set`. Clear callback sets after one-shot events as optimization.

**Naming**: Registration: `on_<event>()`. Callback type: `<Event>Callback`.
Trigger: `__trigger_<event>()`. Notification handler: `_notify_<event>()`.

**Tooling**:
- LLM review: verify callbacks are registered and unregistered correctly
- Test: register callback, trigger event, verify callback invoked

## PY-DP-9: Null Object Pattern

**When**: A subsystem needs a "do nothing" stand-in that satisfies an interface
without performing real work (e.g., `NullPort` that raises or returns empty
values for every `Port` method).
**Implementation**: Subclass the real class (or implement the same Protocol).
Override every method with a no-op, empty return, or error raise. Methods will
not access `self` — this is correct and expected.

**Known tooling false positive**: `ruff PLR6301` flags every method in a Null
Object because none use `self`. Suppress with `# noqa: PLR6301` on the class
or exclude Null Object classes in ruff config. An agent must not "fix" these
by removing `self` or converting to static methods — that would break the
interface contract.

**Tooling**:
- LLM review: Null Object classes must implement the full parent interface
- ruff PLR6301: suppress findings on Null Object classes (known false positive)

## PY-DP-10: Facade Pattern

**When**: A library/subsystem needs a single entry point.
**Implementation**: One class (`Marketplace`) that delegates to internal classes.
`__init__.py` re-exports only the facade via `__all__`.

**Tooling**:
- Check `__init__.py` has `__all__` listing only the facade class
- Test: `from package import Facade` is the primary API

## PY-DP-11: Single-Method Interfaces (Strategy, Observer, Callable ABCs)

**When**: An interface defines exactly one abstract method — common for Strategy,
Observer, Visitor, and callback protocols.
**Implementation**: ABC or Protocol with a single `@abstractmethod`. This is a
legitimate design, not a "data holder missing methods."

**Known tooling false positive**: `pylint R0903` (too-few-public-methods) flags
any class with fewer than 2 public methods. Single-method ABCs and Protocols
are correct by design — the interface IS one method.

**Suppress**: Add `# pylint: disable=too-few-public-methods` on the class, or
configure pylint with `min-public-methods=1` for the project.

**How to distinguish from a real R0903 problem**:
- Class is an ABC/Protocol with 1 abstract method → **legitimate**, suppress
- Class is a concrete class with 1 method and stored data → **data holder**,
  consider replacing with a function or dataclass
- Class has 0 public methods → **always a problem** unless it's a mixin

**Tooling**:
- pylint R0903: suppress on ABC/Protocol classes with exactly 1 abstract method
- LLM review: concrete classes with < 2 methods still need scrutiny
