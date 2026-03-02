---
description: Create a Z specification for stateful entities in a system
argument-hint: "[focus area or system description]"
allowed-tools: Bash(fuzz:*), Bash(probcli:*), Bash($PROBCLI:*), Bash(which:*), Bash(pdflatex:*), Read, Glob, Grep
---

# /z-spec:code2model - Code to Model

You are creating a formal Z specification for the key stateful entities in a system. The specification will be type-checked with fuzz and should be compatible with probcli for animation and model checking.

## Input

Focus hint: $ARGUMENTS

## Process

### 0. Check Prerequisites

Before proceeding, verify fuzz is installed:

```bash
which fuzz >/dev/null 2>&1 || echo "FUZZ_NOT_FOUND"
```

**If fuzz not found**: Stop and tell the user:
> fuzz is not installed. Run `/z-spec:setup` first to install the Z specification tools.

Do not proceed with specification creation until fuzz is available.

### 1. Ensure TeX Files Available

Before creating a specification, ensure the required TeX files are in the project's `docs/` directory.

**Check and copy if missing:**

```bash
mkdir -p docs

# Check for fuzz.sty
if [ ! -f docs/fuzz.sty ]; then
    # Try local install first
    if [ -f /usr/local/share/texmf/tex/latex/fuzz.sty ]; then
        cp /usr/local/share/texmf/tex/latex/fuzz.sty docs/
        cp /usr/local/share/texmf/fonts/source/public/oxsz/*.mf docs/
    else
        # Download from GitHub
        curl -sL -o docs/fuzz.sty "https://raw.githubusercontent.com/Spivoxity/fuzz/master/tex/fuzz.sty"
        for mf in oxsz.mf oxsz10.mf oxsz5.mf oxsz6.mf oxsz7.mf oxsz8.mf oxsz9.mf zarrow.mf zletter.mf zsymbol.mf; do
            curl -sL -o "docs/$mf" "https://raw.githubusercontent.com/Spivoxity/fuzz/master/tex/$mf"
        done
    fi
fi
```

**Update .gitignore** (add if not present):

```bash
# Ensure .gitignore has Z tooling patterns
for pattern in "docs/fuzz.sty" "docs/*.mf" "docs/*.pk" "docs/*.tfm" "docs/*.aux" "docs/*.log" "docs/*.fuzz" "docs/*.toc"; do
    grep -qxF "$pattern" .gitignore 2>/dev/null || echo "$pattern" >> .gitignore
done
```

### 2. Analyze the System

If in a codebase:
- Search for model files, data structures, entities, and state management
- Focus on the area specified in the hint (if provided)
- Identify: entities, their attributes, relationships, invariants, and operations

If working from description:
- Extract entities, attributes, and operations from the description
- Ask clarifying questions if the description is ambiguous

### 3. Identify Stateful Components

For each entity, determine:
- **Basic types**: Identifiers, timestamps, external references (use given sets)
- **Enumerations**: Status values, modes, phases (use free types)
- **State variables**: Attributes that change over time
- **Invariants**: Constraints that must always hold
- **Operations**: State transitions with preconditions and effects

### 4. Generate the Specification

Create a LaTeX file with this structure:

```latex
%
% <system_name>.tex
%
% Z Specification for <System Name>
% Formal model of <brief description>
%

\documentclass[a4paper,10pt,fleqn]{article}
\usepackage[margin=1in]{geometry}
\usepackage{fuzz}
\usepackage[colorlinks=true,linkcolor=blue,citecolor=blue,urlcolor=blue]{hyperref}

\begin{document}

\title{<System Name>: A Z Specification}
\author{Formal Model of <System Description>}
\date{<Month Year>}
\hypersetup{
  pdftitle={<System Name>: A Z Specification},
  pdfauthor={<Author or Organization>},
  pdfsubject={Z Specification},
  pdfcreator={fuzz/probcli}
}
\maketitle

\tableofcontents
\newpage

\section{Introduction}
% Brief description of what the system does

\section{Basic Types}
% Given sets for entities with no internal structure
\begin{zed}
[TYPEA, TYPEB, ...]
\end{zed}

\section{Free Types}
% Enumerations
\begin{zed}
Status ::= value1 | value2 | ...
\end{zed}

% Boolean type (fuzz doesn't have built-in boolean)
% Use ZBOOL to avoid ProB/B keyword conflicts with BOOL/true/false
\begin{zed}
ZBOOL ::= ztrue | zfalse
\end{zed}

\section{Global Constants}
% System-wide configuration
\begin{axdef}
maxValue : \nat
\where
maxValue = 100
\end{axdef}

\section{<Entity Name>}
% State schema with invariants
\begin{schema}{EntityName}
attribute1 : Type1 \\
attribute2 : Type2
\where
% invariants
attribute1 \leq maxValue
\end{schema}

% Initialization
\begin{schema}{InitEntityName}
EntityName'
\where
attribute1' = 0 \\
attribute2' = defaultValue
\end{schema}

\section{Operations}

\subsection{Operation Name}
\begin{schema}{OperationName}
\Delta EntityName \\
input? : InputType
\where
% preconditions
attribute1 < maxValue \\
% effects
attribute1' = attribute1 + input? \\
attribute2' = attribute2
\end{schema}

\section{System Invariants}
% Summary of key properties

\end{document}
```

### 5. Write the File

Save to `docs/<system_name>.tex` where `<system_name>` is derived from the focus hint or codebase name.

### 6. Format with tex-fmt (if available)

If tex-fmt is installed, format the LaTeX for consistent style:

```bash
if command -v tex-fmt >/dev/null 2>&1; then
    tex-fmt docs/<system_name>.tex
fi
```

This ensures consistent indentation and line breaks. See `reference/latex-style.md` for formatting guidelines.

### 7. Type-Check with Fuzz

Run:
```bash
fuzz -t docs/<system_name>.tex
```

If errors occur:
- Fix type errors iteratively
- Common issues: missing BOOL free type, tuple projection (use schema fields), cardinality on complex expressions

### 8. Report Results

Summarize:
- Entities modeled
- Key invariants captured
- Operations defined
- Any limitations or areas for future expansion

## Key Principles

1. **Invariants over code duplication**: Express constraints once in the schema predicate
2. **Use partial injection (`\pinj`) for unique mappings**
3. **Frame all state changes**: Explicitly state what doesn't change in operations
4. **Prefer simple types**: Use given sets for IDs, free types for enums
5. **Test with fuzz**: The specification must type-check

## ProB Compatibility

Specifications that pass fuzz may still fail in probcli. Follow these guidelines to create **animatable** specifications:

### 1. Avoid B Keyword Conflicts

**Don't use**: `BOOL`, `TRUE`, `FALSE`, `true`, `false`, `bool`

**Do use**: `ZBOOL ::= ztrue | zfalse`

### 2. Provide Concrete Values for Functions

Abstract functions can't be animated. If you define:
```latex
% ABSTRACT (fuzz OK, probcli FAILS)
\begin{axdef}
kochOrder : \nat_1 \pinj CHAR
\where
\dom kochOrder = 1 \upto 26
\end{axdef}
```

Also provide concrete instantiation:
```latex
% CONCRETE (probcli can animate)
\begin{axdef}
kochOrder : \nat_1 \pinj CHAR
\where
kochOrder = \{ 1 \mapsto K, 2 \mapsto M, 3 \mapsto R, ... \}
\end{axdef}
```

Or use a simpler model that doesn't require function enumeration.

### 3. Add Bounds to Numeric Variables

Unbounded integers cause "Unbounded enumeration" warnings and slow/failed animation.

**Don't**:
```latex
attempts : \nat
```

**Do** (add reasonable upper bounds in invariants):
```latex
attempts : \nat
\where
attempts \leq 10000
```

### 4. Create a Unified Init Schema

probcli expects a single initialization schema named `Init`. Create one that composes all entity inits:

```latex
\begin{schema}{Init}
InitEntity1 \\
InitEntity2
\end{schema}
```

Or define all initial values in one schema:
```latex
\begin{schema}{Init}
State'
\where
attr1' = 0 \\
attr2' = \emptyset \\
...
\end{schema}
```

### 5. Constrain Given Set Cardinality

For model checking, given sets need finite sizes. Design invariants that work with small cardinalities (2-5 elements).

### 6. Flatten Nested Schema Types

**Avoid nested schema types in state**. ProB cannot initialize nested schemas:

```latex
% BAD - probcli fails to initialize
\begin{schema}{StudentProgress}
schedule : PracticeSchedule  % Nested schema type
...
\end{schema}

\begin{schema}{Init}
StudentProgress'
\where
schedule'.receiveInterval = 1  % ProB can't resolve this
\end{schema}
```

**Flatten all fields into one state schema**:

```latex
% GOOD - probcli can animate
\begin{schema}{State}
receiveLevel : \nat \\
sendLevel : \nat \\
receiveInterval : \nat \\  % Flattened from PracticeSchedule
sendInterval : \nat \\
currentStreak : \nat \\
longestStreak : \nat
\where
...
\end{schema}

\begin{schema}{Init}
State'
\where
receiveLevel' = 1 \\
receiveInterval' = 1 \\
...
\end{schema}
```

### 7. Bound All Input Variables

Unbounded inputs cause infinite enumeration during animation:

```latex
% BAD - probcli enumerates 90..infinity
accuracy? : \nat
\where
accuracy? \geq 90

% GOOD - finite range for animation
accuracy? : \nat
\where
accuracy? \geq 90 \\
accuracy? \leq 100
```

### 8. Separate vs Shared State Schemas

If you have multiple entity types (e.g., `CharacterStat` and `State`), operations on one type won't automatically frame the other. Either:

1. **Combine into single state schema** (recommended for animation)
2. **Accept that sub-entity operations work independently** (operations on `CharacterStat` won't affect `State` variables)

## Updating Existing Specifications

When updating an existing `.tex` file (rather than creating new):

### 1. Read Existing Specification

Load the current `.tex` file and understand:
- Current basic types and free types
- Existing schemas and their structure
- Operations defined
- Invariants in place

### 2. Analyze Requested Changes

Common change types:

| Change Type | Actions Required |
|-------------|------------------|
| Add new entity | Add schema, init schema, basic operations |
| Add attribute | Update schema, update init, update operations that should reference it |
| Add operation | Add operation schema, ensure frame conditions |
| Add invariant | Add predicate to schema, verify existing ops maintain it |
| Modify operation | Update preconditions/effects, check consistency |
| Remove element | Remove definition, check for dangling references |
| Rename | Update all references consistently |

### 3. Apply Changes

When modifying:

1. **Maintain consistency**: If adding an attribute, ensure all `\Delta` operations either update it or explicitly preserve it (`attr' = attr`)

2. **Preserve invariants**: New operations must maintain existing invariants

3. **Update dependencies**: If a type changes, update all schemas and operations using it

4. **Add needed types**: If the change requires new enumerations or basic types, add them

### Example Updates

**Adding a new attribute** ("Add email to User schema"):
1. If needed, add basic type: `[EMAIL]`
2. Add to schema declaration: `email : EMAIL`
3. Add to init: `email' = defaultEmail` (or leave unconstrained)
4. Update all `\Delta User` operations to preserve: `email' = email`

**Adding a new operation** ("Add a delete operation for sessions"):
```latex
\begin{schema}{DeleteSession}
\Delta SessionStore \\
sessionId? : SESSIONID
\where
sessionId? \in \dom sessions \\
sessions' = \{ sessionId? \} \ndres sessions
\end{schema}
```

**Adding an invariant** ("Ensure balance is never negative"):
1. Add to schema predicate: `balance \geq 0`
2. Review all operations that modify `balance` to ensure they maintain this
3. May need to add preconditions to prevent violations

**Strengthening a type** ("Make usernames unique"):
- Change from `\pfun` to `\pinj`:
  - Before: `users : USERNAME \pfun UserData`
  - After: `users : USERNAME \pinj UserData`
- This automatically enforces uniqueness via the injection constraint

### 4. Format and Regenerate PDF

After any changes to the `.tex` file:

1. **Format with tex-fmt** (if available):
```bash
if command -v tex-fmt >/dev/null 2>&1; then
    tex-fmt docs/<file>.tex
fi
```

2. **Regenerate PDF** (run twice for TOC/references):
```bash
cd docs && pdflatex <file>.tex && pdflatex <file>.tex
```

3. **Check for typeset overflows**:
```bash
grep -i "overfull" docs/<file>.log
```

If any overflows are reported, fix them by adding `\\` and `\t1` breaks at logical operators. See `reference/latex-style.md` for the overflow fix process. Repeat until no overflows remain.

## Reference

Consult the reference files for:
- Z notation syntax: `reference/z-notation.md`
- Common schema patterns: `reference/schema-patterns.md`
- probcli options: `reference/probcli-guide.md`
- LaTeX formatting: `reference/latex-style.md`
