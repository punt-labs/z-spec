# LaTeX Style Guidelines for Z Specifications

> **Critical**: Never use `\t1` through `\t9` for indentation — fuzz does not support them and will error. Use `\quad~` for nested continuation lines (inside parentheses, after `\LET`/`\IF`). Top-level `\land`/`\lor` continuations align at the left margin without `\quad~`. Keep all schema lines under 80 characters to avoid PDF margin overflow.

Consistent LaTeX formatting improves readability of Z specifications. This guide covers formatting conventions for Z notation documents.

## Document Structure

### Required Packages

Always include these packages in order:

```latex
\documentclass[a4paper,10pt,fleqn]{article}
\usepackage[margin=1in]{geometry}
\usepackage{fuzz}
\usepackage[colorlinks=true,linkcolor=blue,citecolor=blue,urlcolor=blue]{hyperref}
```

Load `hyperref` after `fuzz` following standard LaTeX convention (hyperref should be one of the last packages loaded).

### Document Metadata

Include hypersetup for PDF metadata:

```latex
\hypersetup{
  pdftitle={System Name: A Z Specification},
  pdfauthor={Author Name},
  pdfsubject={Z Specification},
  pdfcreator={fuzz/probcli}
}
```

### Table of Contents

Include `\tableofcontents` and `\newpage` after `\maketitle` for navigable documents.

## Line Width Guidelines

### Maximum Line Length

Schema predicates and declarations should not exceed **80 characters** to avoid horizontal overflow in PDF output.

### Breaking Long Lines

#### Schema Declarations

Break after type declarations:

```latex
% BAD - too long
\begin{schema}{State}
receiveLevel, sendLevel, currentStreak, longestStreak : \nat
\end{schema}

% GOOD - split across lines
\begin{schema}{State}
receiveLevel : \nat \\
sendLevel : \nat \\
currentStreak : \nat \\
longestStreak : \nat
\end{schema}
```

#### Schema Predicates

Break at logical operators (`\land`, `\lor`, `\implies`):

```latex
% BAD - single long line
accuracy? \geq 90 \land level < maxLevel \land daysSinceStart \geq minDaysAtLevel

% GOOD - break at logical operators
accuracy? \geq 90 \\
\land level < maxLevel \\
\land daysSinceStart \geq minDaysAtLevel
```

#### Set Comprehensions

Break after `|` and before closing brace:

```latex
% BAD - too long
completedLevels = \{ l : 1 \upto 26 | l < currentLevel \land stats(l).accuracy \geq 90 \}

% GOOD - break for readability
completedLevels = \{ l : 1 \upto 26 | \\
\quad~ l < currentLevel \\
\quad~ \land stats(l).accuracy \geq 90 \}
```

#### Function Definitions

Break enumerated mappings across lines:

```latex
% BAD - single line
kochOrder = \{ 1 \mapsto K, 2 \mapsto M, 3 \mapsto R, 4 \mapsto S, 5 \mapsto U, ... \}

% GOOD - grouped by 5
kochOrder = \{ \\
\quad~ 1 \mapsto K, 2 \mapsto M, 3 \mapsto R, 4 \mapsto S, 5 \mapsto U, \\
\quad~ 6 \mapsto A, 7 \mapsto P, 8 \mapsto T, 9 \mapsto L, 10 \mapsto O, \\
\quad~ ... \}
```

### Indentation in Z Schemas

Use `\quad~` for indentation within predicates (`\t1` through `\t9` do **not** work with fuzz):

```latex
\begin{schema}{ComplexOperation}
\Delta State \\
input? : \nat
\where
input? > 0 \\
\land (condition1 \\
\quad~ \implies effect1 \\
\quad~ \land effect2) \\
\land condition2 \implies effect3
\end{schema}
```

## Common Patterns

### Conditional Effects

Use `\implies` with aligned predicates:

```latex
accuracy? \geq threshold \implies level' = level + 1 \\
accuracy? < threshold \implies level' = level
```

### Frame Conditions

Group unchanged variables:

```latex
% Explicit preservation
receiveLevel' = receiveLevel \\
sendLevel' = sendLevel \\
currentStreak' = currentStreak
```

Or use schema notation for unchanged state:

```latex
\Xi OtherState  % OtherState unchanged
```

## Detecting and Fixing Typeset Overflows

**Important**: Source line breaks (for `.tex` readability) are different from typeset line breaks (what appears in the PDF). A line under 80 characters in your source can still overflow in the typeset output.

### Detecting Overflows

After running pdflatex, check for "Overfull hbox" warnings:

```bash
pdflatex -interaction=nonstopmode spec.tex
grep -i "overfull" spec.log
```

Example output:
```
Overfull \hbox (279.5776pt too wide) in alignment at lines 837--854
```

The line numbers refer to the `.tex` source. Any overflow means content is cut off in the PDF—readers cannot see it.

### Fixing Overflows

Add explicit line breaks with `\\` followed by `\quad~` for indentation:

```latex
% BAD - typeset overflow even though source is multi-line
(condition1 \land result1) \lor
(condition2 \land result2)

% GOOD - explicit typeset breaks with indentation
(condition1 \\
\quad~ \land result1) \\
\lor (condition2 \\
\quad~ \land result2)
```

### Common Overflow Patterns

| Pattern | Solution |
|---------|----------|
| Long `\LET` bindings | Break after `==`, indent body with `\quad~` |
| `\IF-\THEN-\ELSE` | Each clause on its own line with `\quad~` |
| Chained `\land` predicates | Break before each `\land`, indent with `\quad~` |
| Chained `\lor` alternatives | Break before `\lor`, keep `(` on same line |
| Long comparisons | Break after operator, indent continuation |

### Example: Breaking a Complex Schema

```latex
% Before - causes overflow
\LET minAttempts == \IF base > perChar * count \THEN base \ELSE perChar * count @
(attempts \geq minAttempts \land accuracy \geq threshold \land met! = ztrue) \lor
(attempts < minAttempts \land met! = zfalse)

% After - no overflow
\LET minAttempts == \\
\quad~ \IF base > perChar * count \\
\quad~ \THEN base \\
\quad~ \ELSE perChar * count @
(attempts \geq minAttempts \\
\quad~ \land accuracy \geq threshold \\
\quad~ \land met! = ztrue) \\
\lor (attempts < minAttempts \\
\quad~ \land met! = zfalse)
```

### Iterative Fix Process

1. Run `pdflatex` and check for overflows
2. Find the schema at the reported line numbers
3. Add `\\` and `\quad~` breaks at logical operators
4. Re-run `pdflatex` and verify no overflows remain
5. Repeat until `grep -i "overfull" spec.log` returns nothing

## Formatting Tools

### tex-fmt

If available, use `tex-fmt` to auto-format LaTeX:

```bash
tex-fmt docs/spec.tex
```

This handles:
- Consistent indentation
- Brace alignment
- Blank line normalization

### Manual Verification

After formatting, verify:
1. No horizontal overflow in PDF
2. Schema predicates align logically
3. Line breaks preserve mathematical meaning

## Checklist Before Commit

- [ ] `hyperref` package included
- [ ] `\tableofcontents` present
- [ ] No lines exceed 80 characters in schemas
- [ ] Long predicates broken at logical operators
- [ ] `tex-fmt` run (if available)
- [ ] PDF generated without overflow warnings
