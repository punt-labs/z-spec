# Test Assertion Patterns by Language

Reference for matching Z specification constraints to unit test assertions across different languages and frameworks.

## Swift / XCTest

### Directory Detection

| Pattern | Description |
|---------|-------------|
| `*Tests/` | Standard XCTest target directory |
| `*UITests/` | UI test target directory |
| `*IntegrationTests/` | Integration test directory |

### File Patterns

| Pattern | Description |
|---------|-------------|
| `*Tests.swift` | Standard test file naming |
| `*Spec.swift` | BDD-style naming |
| `Test*.swift` | Prefix naming |

### Assertion Patterns

| Constraint Type | XCTest Assertion | Example |
|-----------------|------------------|---------|
| Upper bound (`x <= N`) | `XCTAssertLessThanOrEqual` | `XCTAssertLessThanOrEqual(interval, 30.0)` |
| Lower bound (`x >= N`) | `XCTAssertGreaterThanOrEqual` | `XCTAssertGreaterThanOrEqual(level, 1)` |
| Strict upper (`x < N`) | `XCTAssertLessThan` | `XCTAssertLessThan(index, array.count)` |
| Strict lower (`x > N`) | `XCTAssertGreaterThan` | `XCTAssertGreaterThan(count, 0)` |
| Equality (`x = N`) | `XCTAssertEqual` | `XCTAssertEqual(result.level, 2)` |
| Inequality (`x != N`) | `XCTAssertNotEqual` | `XCTAssertNotEqual(status, .invalid)` |
| Boolean true | `XCTAssertTrue` | `XCTAssertTrue(account.isValid)` |
| Boolean false | `XCTAssertFalse` | `XCTAssertFalse(result.isEmpty)` |
| Nil check | `XCTAssertNil`, `XCTAssertNotNil` | `XCTAssertNotNil(session)` |
| Optional unwrap | `XCTUnwrap` | `let value = try XCTUnwrap(optional)` |

### Keyword Patterns

Test methods often encode constraint intent in their names:

| Constraint Type | Common Keywords |
|-----------------|-----------------|
| Bounds | `max`, `min`, `cap`, `limit`, `threshold`, `boundary`, `clamp` |
| Preconditions | `when`, `given`, `requires`, `guard`, `prerequisite`, `if` |
| Effects | `doubles`, `increments`, `resets`, `maintains`, `advances`, `updates` |
| Invariants | `always`, `never`, `ensures`, `preserves`, `valid`, `invalid` |

### Example Test Structure

```swift
final class IntervalCalculatorTests: XCTestCase {

    // Testing upper bound: interval <= 30
    func testMaxIntervalCapped30Days() {
        let result = IntervalCalculator.calculateNextInterval(
            currentInterval: 20.0,
            accuracy: 0.95,
            daysSinceStart: 30
        )
        XCTAssertLessThanOrEqual(result, 30.0)  // Upper bound assertion
    }

    // Testing precondition: accuracy >= 90%
    func testExactly90PercentDoublesInterval() {
        let result = IntervalCalculator.calculateNextInterval(
            currentInterval: 2.0,
            accuracy: 0.90,  // Exactly at threshold
            daysSinceStart: 30
        )
        XCTAssertEqual(result, 4.0)  // Effect: interval doubles
    }

    // Testing effect: interval' = 1 (reset)
    func testLowAccuracyResetsToDaily() {
        let result = IntervalCalculator.calculateNextInterval(
            currentInterval: 8.0,
            accuracy: 0.65,
            daysSinceStart: 30
        )
        XCTAssertEqual(result, 1.0)  // Reset effect
    }
}
```

---

## TypeScript / Jest

### Directory Detection

| Pattern | Description |
|---------|-------------|
| `__tests__/` | Jest default test directory |
| `test/`, `tests/` | Common alternatives |
| `src/**/*.test.ts` | Co-located test files |
| `src/**/*.spec.ts` | BDD-style co-located |

### File Patterns

| Pattern | Description |
|---------|-------------|
| `*.test.ts` | Jest standard |
| `*.spec.ts` | BDD-style |
| `*.test.tsx` | React component tests |

### Assertion Patterns

| Constraint Type | Jest Assertion | Example |
|-----------------|----------------|---------|
| Upper bound | `expect(...).toBeLessThanOrEqual` | `expect(interval).toBeLessThanOrEqual(30)` |
| Lower bound | `expect(...).toBeGreaterThanOrEqual` | `expect(level).toBeGreaterThanOrEqual(1)` |
| Strict upper | `expect(...).toBeLessThan` | `expect(index).toBeLessThan(length)` |
| Strict lower | `expect(...).toBeGreaterThan` | `expect(count).toBeGreaterThan(0)` |
| Equality | `expect(...).toBe`, `expect(...).toEqual` | `expect(result).toBe(2)` |
| Inequality | `expect(...).not.toBe` | `expect(status).not.toBe('invalid')` |
| Truthy | `expect(...).toBeTruthy` | `expect(isValid).toBeTruthy()` |
| Falsy | `expect(...).toBeFalsy` | `expect(isEmpty).toBeFalsy()` |
| Defined | `expect(...).toBeDefined` | `expect(session).toBeDefined()` |
| Undefined | `expect(...).toBeUndefined` | `expect(error).toBeUndefined()` |

### Example Test Structure

```typescript
describe('IntervalCalculator', () => {

  // Testing upper bound: interval <= 30
  it('caps interval at 30 days maximum', () => {
    const result = calculateNextInterval({
      currentInterval: 20,
      accuracy: 0.95,
      daysSinceStart: 30
    });
    expect(result).toBeLessThanOrEqual(30);
  });

  // Testing precondition: accuracy >= 90%
  it('doubles interval at exactly 90% accuracy', () => {
    const result = calculateNextInterval({
      currentInterval: 2,
      accuracy: 0.90,
      daysSinceStart: 30
    });
    expect(result).toBe(4);
  });
});
```

---

## Python / pytest

### Directory Detection

| Pattern | Description |
|---------|-------------|
| `tests/` | Standard test directory |
| `test/` | Alternative |
| `src/**/test_*.py` | Co-located tests |

### File Patterns

| Pattern | Description |
|---------|-------------|
| `test_*.py` | pytest standard (prefix) |
| `*_test.py` | pytest alternative (suffix) |

**Note**: `conftest.py` contains fixtures and configuration, not test cases. Don't count it as a test file.

### Assertion Patterns

| Constraint Type | pytest Assertion | Example |
|-----------------|------------------|---------|
| Upper bound | `assert x <= N` | `assert interval <= 30` |
| Lower bound | `assert x >= N` | `assert level >= 1` |
| Strict upper | `assert x < N` | `assert index < len(items)` |
| Strict lower | `assert x > N` | `assert count > 0` |
| Equality | `assert x == N` | `assert result == 2` |
| Inequality | `assert x != N` | `assert status != 'invalid'` |
| Truthy | `assert x` | `assert is_valid` |
| Falsy | `assert not x` | `assert not is_empty` |
| None | `assert x is None`, `assert x is not None` | `assert session is not None` |
| In range | `assert N <= x <= M` | `assert 1 <= level <= 26` |

### Example Test Structure

```python
class TestIntervalCalculator:

    # Testing upper bound: interval <= 30
    def test_max_interval_capped_30_days(self):
        result = calculate_next_interval(
            current_interval=20,
            accuracy=0.95,
            days_since_start=30
        )
        assert result <= 30

    # Testing precondition: accuracy >= 90%
    def test_exactly_90_percent_doubles_interval(self):
        result = calculate_next_interval(
            current_interval=2,
            accuracy=0.90,
            days_since_start=30
        )
        assert result == 4

    # Testing effect: interval resets to 1
    def test_low_accuracy_resets_to_daily(self):
        result = calculate_next_interval(
            current_interval=8,
            accuracy=0.65,
            days_since_start=30
        )
        assert result == 1
```

---

## Kotlin / JUnit 5

### Directory Detection

| Pattern | Description |
|---------|-------------|
| `src/test/kotlin/` | Gradle/Maven standard |
| `src/test/java/` | Java-style (Kotlin compatible) |

### File Patterns

| Pattern | Description |
|---------|-------------|
| `*Test.kt` | JUnit standard |
| `*Tests.kt` | Plural naming |
| `*Spec.kt` | BDD-style |

### Assertion Patterns

| Constraint Type | JUnit 5 Assertion | Example |
|-----------------|-------------------|---------|
| Upper bound | `assertTrue(x <= N)` | `assertTrue(interval <= 30)` |
| Lower bound | `assertTrue(x >= N)` | `assertTrue(level >= 1)` |
| Equality | `assertEquals(expected, actual)` | `assertEquals(2, result)` |
| Boolean | `assertTrue(...)`, `assertFalse(...)` | `assertTrue(isValid)` |
| Null | `assertNull(...)`, `assertNotNull(...)` | `assertNotNull(session)` |

---

## Adding New Languages

To add support for a new language or framework:

1. **Add Directory Detection section** with patterns for test directories
2. **Add File Patterns section** with test file naming conventions
3. **Add Assertion Patterns table** mapping constraint types to framework assertions
4. **Add Example Test Structure** showing typical test organization

### Constraint Type Reference

This table shows logical categories of Z constraints. For how to extract these structurally from Z specifications (schema invariants vs operation preconditions vs effects), see `commands/audit.md` section 3.

| Category | Z Pattern | Description |
|----------|-----------|-------------|
| Upper bound | `x \leq N` | Value must not exceed N |
| Lower bound | `x \geq N` | Value must be at least N |
| Strict upper | `x < N` | Value must be less than N |
| Strict lower | `x > N` | Value must be greater than N |
| Equality | `x = N` | Value must equal N |
| Relation | `x \leq y` | One value bounded by another |
| Membership | `x \in S` | Value must be in set |
| Non-membership | `x \notin S` | Value must not be in set |
| Subset | `A \subseteq B` | All elements of A are in B |
| Implication | `P \implies Q` | If P holds, then Q must hold |
