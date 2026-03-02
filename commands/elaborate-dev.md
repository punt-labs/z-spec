---
description: Elaborate a Z specification with narrative from design documentation
argument-hint: "[spec file] [design doc]"
---

# Elaborate Z Specification

You are enhancing a formal Z specification by combining it with design documentation to create a polished, readable artifact that serves both as formal specification and design documentation.

## Input

Arguments: $ARGUMENTS

Parse arguments as:
- First argument: path to Z specification (`.tex` file)
- Second argument (optional): path to design documentation (defaults to `DESIGN.md`)

## Process

### 1. Read the Specification

Read the Z specification file. Identify:
- Basic types and their intended meaning
- Free types (enumerations)
- State schemas and their fields
- Operations and their purpose
- Any existing narrative text

### 2. Read Design Documentation

Search for design documentation in order:
1. Explicit path from arguments
2. `DESIGN.md` in project root
3. `docs/DESIGN.md`
4. `README.md` (extract design sections)

Extract relevant content:
- System overview and purpose
- Design philosophy and principles
- Feature descriptions
- Algorithm explanations
- Domain terminology
- Architectural decisions

### 3. Enhance the Specification

Transform the specification by adding:

#### Document Structure
```latex
\tableofcontents
\newpage
```

#### Introduction Section
- System purpose from design docs
- Design philosophy (bullet points)
- Scope of specification (what is/isn't modeled)

#### Section Narratives
For each major section, add explanatory text:
- **Basic Types**: Why these given sets? What do they represent?
- **Free Types**: Domain meaning of each enumeration value
- **Constants**: Why these values? What do they configure?
- **State Schemas**:
  - What does each field represent?
  - Why these invariants matter?
  - Semantic meaning (not just type)
- **Operations**:
  - When is this operation used?
  - What triggers it?
  - Connection to user actions or system events

#### Algorithm Explanations
Where operations implement algorithms from design docs:
- Add tables summarizing rules (e.g., spaced repetition thresholds)
- Note implementation details not captured in formal model
- Reference design doc sections

#### Properties Not Modeled
Add a section listing aspects intentionally omitted:
- UI state
- Real-time behavior
- External integrations
- Implementation details

#### Validation Section
Document verification status:
```latex
\section{Validation}

This specification has been validated with:
\begin{itemize}
\item \textbf{fuzz}: Type-checking passes with no errors
\item \textbf{probcli -init}: Initialization succeeds
\item \textbf{probcli -animate}: All operations covered
\end{itemize}
```

### 4. Writing Style

Follow these guidelines:

**Clarity over formality**: The narrative should help readers understand the formal notation, not duplicate it.

**Connect to domain**: Use domain terminology from design docs consistently.

**Explain "why"**: Formal specs show "what"—narrative explains "why" choices were made.

**Cross-reference**: Link schema fields to design concepts.

**Subsections for semantics**: Under state schemas, add subsections like:
```latex
\subsection{Level Semantics}
Each level $n$ unlocks the first $n$ characters...

\subsection{Interval Semantics}
The interval represents days until next scheduled practice...
```

**Tables for algorithms**: Present decision rules in tabular form:
```latex
\begin{center}
\begin{tabular}{ll}
\hline
Condition & Effect \\
\hline
$accuracy \geq 90\%$ & Double interval \\
...
\end{tabular}
\end{center}
```

**Implementation notes**: Where the formal model simplifies:
```latex
Note: The implementation includes additional rules not modeled here:
\begin{itemize}
\item First 14 days: intervals capped at 2 days
\item ...
\end{itemize}
```

### 5. Verify

After enhancement:
1. Run `fuzz -t <file>` to ensure type-checking still passes
2. Format with tex-fmt if available: `tex-fmt <file>` (see `reference/latex-style.md`)
3. Run `pdflatex` twice to generate PDF with table of contents
4. Review for consistency between narrative and formal content

### 6. Report

Summarize:
- Sections enhanced
- Key narratives added
- Page count of final document
- Any design concepts that could benefit from additional formal modeling

## Example Output Structure

```latex
\documentclass[a4paper,10pt,fleqn]{article}
\usepackage[margin=1in]{geometry}
\usepackage{fuzz}
\usepackage[colorlinks=true,linkcolor=blue,citecolor=blue,urlcolor=blue]{hyperref}

\begin{document}

\title{System Name: A Z Specification}
\author{Formal Model of System Description}
\date{Month Year}
\hypersetup{
  pdftitle={System Name: A Z Specification},
  pdfauthor={Author},
  pdfsubject={Z Specification},
  pdfcreator={fuzz/probcli}
}
\maketitle

\tableofcontents
\newpage

%==============================================================================
\section{Introduction}
%==============================================================================

[System overview from design docs]

\subsection{Design Philosophy}
[Bullet points of core principles]

\subsection{Scope of This Specification}
[What is modeled, what is not]

%==============================================================================
\section{Basic Types}
%==============================================================================

[Explanation of why these given sets]

\begin{zed}
[TYPEA, TYPEB]
\end{zed}

[What each type represents]

%==============================================================================
\section{Free Types}
%==============================================================================

\subsection{Type Name}

[Domain meaning and usage]

\begin{zed}
TypeName ::= value1 | value2
\end{zed}

[Explanation of each value]

... [continue pattern for all sections]

%==============================================================================
\section{System Invariants}
%==============================================================================

[Numbered list of key properties with explanations]

%==============================================================================
\section{Properties Not Modeled}
%==============================================================================

[Bullet list of intentionally omitted aspects]

%==============================================================================
\section{Validation}
%==============================================================================

[Verification status]

\end{document}
```

## Tips

1. **Preserve formal content**: Don't modify schemas—add narrative around them
2. **Match terminology**: Use the same terms as design docs
3. **Keep invariant explanations close**: Explain constraints right after stating them
4. **Use LaTeX features**: `\emph{}`, `\textbf{}`, tables, itemize/enumerate
5. **Section separators**: Use `%===` comment lines for visual structure
