# YYYY-MM-DD — <Title>

| Field | Value |
|---|---|
| Date | YYYY-MM-DD |
| Author | |
| Phase / gate | <SRS Section 9 phase or gate this belongs to> |
| Owner decisions relied on | <D-nn, D-nn> |
| Requirements touched | <FR-, IR-, NR-, SR-, ACC-, NFR- IDs> |
| Open items closed | <TBC-nn, TBD-nn, or "none"> |

## 1. Problem / motivation

Why was this change needed? What risk or gap did it address? State the failure
that would occur without it, not just the feature that is missing.

## 2. What changed

| File | Change |
|---|---|
| `path/to/file` | One sentence. |

## 3. Implementation approach

The "how": the pattern, algorithm or strategy chosen, and the contract of any
function introduced — inputs, outputs, side effects, invariants relied on.

## 4. Mathematical / numerical details

Any formula, statistical test or numeric algorithm, described in plain English
with notation, so a future reader can audit the mathematics without reading the
code. Omit this section only for purely structural changes.

## 5. Design decisions

What alternatives were considered and why this approach was chosen. Where the
owner made the choice, cite the decision ID; where the architect chose, say so.

## 6. Verification

Concrete, runnable steps, with the exact command and what a pass looks like.
State the platform, compiler and float backend for every result, and state what
the result does **not** prove (SRS Appendix D).

## 7. Related docs

Links to the SRS sections and any other implementation notes.
