---
description: Audit test coverage for Z specification constraints
argument-hint: "[spec.tex] [--json] [--test-dir=DIR]"
allowed-tools: Read, Glob, Grep
---

# /z-spec:audit - Test Coverage Audit

Audit unit test coverage against constraints defined in a Z specification. Extracts invariants, preconditions, effects, and bounds from the spec, then searches the test suite for coverage.

## Input

Arguments: $ARGUMENTS

Parse arguments:
- First positional argument: Z specification file (default: search `docs/*.tex`)
- `--json`: Output JSON instead of markdown table
- `--test-dir=DIR`: Override test directory detection

## Process

### 0. Prerequisites

This command does not require fuzz or probcli. It reads existing Z specifications and searches test files using pattern matching. The specification should already exist (created via `/z-spec:code2model`).

### 1. Locate the Specification

If a file path is provided, use it directly.

If no file specified:
- Look in `docs/` for `.tex` files containing Z specifications
- If multiple found, ask user to specify

Read the specification file.

### 2. Detect Language and Test Directory

If `--test-dir` specified, use it.

Otherwise, auto-detect from project files:

| Indicator | Language | Test Directory Pattern |
|-----------|----------|------------------------|
| `Package.swift`, `*.xcodeproj`, `project.yml` | Swift | `*Tests/` |
| `package.json`, `tsconfig.json` | TypeScript | `__tests__/`, `*.test.ts`, `*.spec.ts` |
| `pyproject.toml`, `setup.py`, `requirements.txt` | Python | `tests/`, `test_*.py`, `*_test.py` |
| `build.gradle.kts`, `pom.xml` | Kotlin | `src/test/` |

Use Glob to find test files matching the detected pattern.

### 3. Extract Constraints from Z Specification

Parse the specification and extract constraints into 4 categories:

#### Category 1: Schema Invariants

Location: `\where` clauses in state schemas (non-operation schemas without `\Delta` or `\Xi`)

Examples:
```latex
\begin{schema}{State}
level : \nat
\where
level \geq 1 \\
level \leq 26
\end{schema}
```

Extracts: `level >= 1`, `level <= 26`

#### Category 2: Operation Preconditions

Location: Predicates in operation schemas (`\Delta` or `\Xi`) that reference only unprimed state variables and inputs.

Examples:
```latex
\begin{schema}{AdvanceLevel}
\Delta State \\
accuracy? : \nat
\where
accuracy? \geq 90 \\      % Precondition
level < 26 \\             % Precondition
level' = level + 1        % Effect (has prime)
\end{schema}
```

Extracts: `accuracy >= 90`, `level < 26`

#### Category 3: Operation Effects

Location: Predicates in operation schemas containing primed variables (`x'`).

Examples:
```latex
level' = level + 1
interval' = interval * 2
streak' = 0
```

Extracts: `level increments by 1`, `interval doubles`, `streak resets to 0`

#### Category 4: Upper/Lower Bounds

Location: Any predicate with explicit numeric limits using `\leq`, `\geq`, `<`, `>`, or `\in ... \upto ...`

Examples:
```latex
attempts \leq 10000
interval \in 1 \upto 30
```

Extracts: `attempts <= 10000`, `interval in 1..30`

**Category Priority**: When a constraint could fit multiple categories, use this priority:
1. **Preconditions** (in `\where` clause of operation with inputs)
2. **Effects** (assignments to primed variables)
3. **Bounds** (explicit numeric limits like max/min values)
4. **Invariants** (remaining state constraints)

For example, `level <= 26` in a State schema is an **invariant** (domain constraint), while `interval <= maxInterval` in an axdef is a **bound** (system limit).

### 4. Build Constraint List

For each extracted constraint, record:
- **Category**: invariant, precondition, effect, or bound
- **Source**: Schema name where it appears
- **Text**: Original Z notation (simplified)
- **Keywords**: Extracted variable names and values for matching

### 5. Search Tests for Coverage

For each constraint, search test files using two strategies:

#### Strategy A: Keyword Matching

Generate keywords from the constraint:
- Variable names: `level`, `interval`, `streak`, `accuracy`
- Numeric values: `26`, `90`, `1`, `30`
- Operation hints: `advance`, `reset`, `double`, `increment`

Use Grep to find test files containing these keywords.

#### Strategy B: Assertion Pattern Matching

Consult `reference/test-patterns.md` for language-specific assertion patterns. For each keyword match, check if nearby lines contain assertion patterns that match the constraint type (e.g., `XCTAssertLessThanOrEqual` for upper bounds, `expect(...).toBeGreaterThanOrEqual` for lower bounds).

#### Scoring Matches

Assign confidence based on match quality:

| Match Type | Confidence |
|------------|------------|
| Exact variable name + correct assertion type | High |
| Variable name + any assertion | Medium |
| Related keyword only | Low |
| No match | Uncovered |

### 6. Generate Report

#### Markdown Output (default)

```markdown
## Z Specification Test Coverage Audit

**Specification**: docs/example.tex
**Test Directory**: ExampleTests/
**Coverage**: 15/19 constraints (79%)

### Summary by Category

| Category | Covered | Total | Coverage |
|----------|---------|-------|----------|
| Schema invariants | 8 | 10 | 80% |
| Operation preconditions | 4 | 4 | 100% |
| Operation effects | 3 | 4 | 75% |
| Upper/lower bounds | 0 | 1 | 0% |

### Detailed Coverage

| Constraint | Category | Source | Covered By | Confidence |
|------------|----------|--------|------------|------------|
| `level >= 1` | invariant | State | StudentProgressTests.swift:89 | High |
| `level <= 26` | invariant | State | StudentProgressTests.swift:95 | High |
| `accuracy >= 90` | precondition | AdvanceLevel | IntervalCalculatorTests.swift:42 | High |
| `level' = level + 1` | effect | AdvanceLevel | StudentProgressTests.swift:145 | Medium |
| `interval <= 30` | bound | State | **UNCOVERED** | - |

### Uncovered Constraints

The following constraints have no detected test coverage:

1. **`interval <= 30`** (bound, State schema)
   - Suggested test: Verify interval never exceeds maximum bound
   - Pattern: `XCTAssertLessThanOrEqual(interval, 30)`

2. **`correct <= attempts`** (invariant, CharacterStat schema)
   - Suggested test: Verify correct count never exceeds attempt count
   - Pattern: `XCTAssertLessThanOrEqual(stat.correct, stat.attempts)`
```

#### JSON Output (--json flag)

```json
{
  "specification": "docs/example.tex",
  "testDirectory": "ExampleTests/",
  "summary": {
    "covered": 15,
    "total": 19,
    "percentage": 79
  },
  "byCategory": {
    "invariant": { "covered": 8, "total": 10 },
    "precondition": { "covered": 4, "total": 4 },
    "effect": { "covered": 3, "total": 4 },
    "bound": { "covered": 0, "total": 1 }
  },
  "constraints": [
    {
      "text": "level >= 1",
      "category": "invariant",
      "source": "State",
      "coveredBy": "StudentProgressTests.swift:89",
      "confidence": "high"
    }
  ],
  "uncovered": [
    {
      "text": "interval <= 30",
      "category": "bound",
      "source": "State",
      "suggestion": "Verify interval never exceeds maximum bound",
      "testPattern": "XCTAssertLessThanOrEqual(interval, 30)"
    }
  ]
}
```

### 7. Generate Test Suggestions

For each uncovered constraint, generate a specific test suggestion:

| Constraint Pattern | Suggestion Template |
|--------------------|---------------------|
| `x >= N` (lower bound) | "Test that {x} is never less than {N}" |
| `x <= N` (upper bound) | "Test that {x} never exceeds {N}" |
| `x <= y` (relation) | "Test that {x} never exceeds {y}" |
| `x' = x + 1` (increment) | "Test that {operation} increments {x} by 1" |
| `x' = 0` (reset) | "Test that {operation} resets {x} to 0" |
| `cond => effect` (implication) | "Test that when {cond}, then {effect}" |

Include framework-specific assertion patterns from `reference/test-patterns.md`.

## Error Handling

| Error | Response |
|-------|----------|
| Specification not found | "Error: No Z specification found. Specify path or create one with `/z-spec:code2model`." |
| No tests found | "Warning: No test files detected. Coverage: 0%. Use `--test-dir` to specify test location." |
| Unsupported language | "Warning: Could not detect supported test framework. Use `--test-dir` to specify. Supported: Swift, TypeScript, Python, Kotlin." |
| Parse error in spec | "Warning: Could not parse schema {name}. Skipping." (continue with others) |
| Empty constraint extraction | "Warning: No constraints extracted. Check that specification contains schemas with predicates." |

## Reference

- Test assertion patterns: `reference/test-patterns.md`
- Z notation: `reference/z-notation.md`
- Schema patterns: `reference/schema-patterns.md`
