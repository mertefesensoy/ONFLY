# 2026-09-14 — Phase B's completion marker, and the ruling it reverses

| Field | Value |
|---|---|
| Date | 2026-09-14 |
| Author | Claude (ONFLY senior engineer session) |
| Phase / gate | Section 9.2 record only; no phase work |
| Owner decisions relied on | **D-246**, authorised by the owner on 2026-09-14 |
| Requirements touched | None |
| Open items | None closed. D-47's ambiguity about what "exit" means for a phase stays open |

## 1. Problem / motivation

Section 9.2 was internally inconsistent: **three phases were complete, two were
marked.** Phase C carried `COMPLETE 2026-09-13 (D-206)` and Phase D carried
`COMPLETE 2026-09-14 (D-234)`, while Phase B — the earliest and least doubtful
of the three — carried nothing. A reader scanning the phase table would
reasonably conclude Phase B was unfinished.

**This is the part that makes it interesting: the missing marker was not an
oversight.** D-47 exited Phase B for x86, and its rationale records why no
marker followed:

> Section 9 states exit criteria for gates only and gives phases content lists,
> so "exit" needed an owner ruling. The owner did **not** authorise amending
> Section 9, so its text is unchanged and this ambiguity persists for later
> phases.

So the blank was deliberate. What made it wrong was **practice overtaking the
ruling without anyone revisiting it**: C and D were later given markers, and
the position D-47 recorded quietly stopped being the one the document follows.
The inconsistency is the residue of a rule that was abandoned in fact but never
in writing.

This is a different defect from D-245's. There, a summary quoted a superseded
number and nobody noticed. Here, everybody followed a newer convention and
nobody went back for the first row.

## 2. What changed

| File | Change |
|---|---|
| `docs/ONFLY-SRS.md` | §9.2 Phase B row: `COMPLETE 2026-09-10 (D-47)` marker added, with S1's disposition stated. Appendix A.1: **D-246** added. |
| `docs/implementations/2026-09-14-phase-b-completion-marker.md` | This note. |

One row and one decision. No code, no generated files.

## 3. How the date was established

D-47 carries no date, so 2026-09-10 is evidenced rather than assumed:

- `docs/implementations/2026-09-10-fingerprint-golden-suite.md` is dated
  2026-09-10, names its phase as "Phase B — Engine and oracle (x86)", and was
  committed that day. **D-40** identifies the golden-suite harness as the last
  outstanding item of Phase B's §9.2 content, so that doc records the last
  Phase B work.
- **D-47** sits immediately before **D-48**, "Next work is Phase C data
  retrieval", which is the shape of an end-of-phase session.

An earlier draft of this correction cited a 2026-09-10 date that traced back to
a document written in this same session — circular, and discarded. The two
sources above are independent of it.

## 4. Design decisions

**Marked the row rather than leaving it.** Leaving it would preserve D-47's
letter at the cost of a phase table that misreports its own project.

**Did not add exit criteria to every phase.** That was D-47's explicitly
rejected alternative, and rejecting it again is the conservative reading of an
authorisation to "fix the Phase B marker". D-47's underlying ambiguity — what
"exit" formally means for a phase, as opposed to a gate — is untouched and
still open.

**Stated S1's disposition in the row.** D-47's whole difficulty was that Phase
B looked incomplete while Spike S1 was outstanding. The row now says S1 stayed
a Phase A / Gate G1 obligation and was met when G1 closed (D-119), so the
question that made the marker contentious is answered in place.

**Named the reversal in D-246 rather than silently amending.** A future reader
comparing D-47 against §9.2 would otherwise find a contradiction with no
explanation of which way it was resolved.

## 5. Verification

```bash
grep -c "COMPLETE 2026-09-10 (D-47)" docs/ONFLY-SRS.md   # 2 (phase row + D-246)
```

All three complete phases now carry a marker in §9.2. Markdown table structure
checked: the Phase B row carries four column separators like its neighbours,
and D-246 carries five like D-245.

**Not run:** `make test`. Documentation only — no compiled source, no generated
file, and nothing `lint_col80` covers (`engine generated softfloat tests tools
cobol`, not `docs`).

## 6. Not proven

- **Whether §9.2's other rows carry stale or missing status.** Phases E, G, F
  and H are all unstarted, so there is nothing yet to mark, but that is a
  reading rather than a systematic check.
- **What "exit" means for a phase** remains undefined, exactly as D-47 left it.
  This change marks one phase complete; it does not define the criterion by
  which any phase is judged complete.

## 7. Related docs

- `docs/ONFLY-SRS.md` — §9.2 Phase B, Appendix A.1 D-47, D-206, D-234, D-246.
- `docs/implementations/2026-09-14-g3-row-maximum-duration-correction.md` — the other record defect found in the same pass.
- `docs/implementations/2026-09-10-fingerprint-golden-suite.md` — Phase B's last content item.
