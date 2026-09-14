# 2026-09-14 — Gate G3's row stated a superseded maximum duration

| Field | Value |
|---|---|
| Date | 2026-09-14 |
| Author | Claude (ONFLY senior engineer session) |
| Phase / gate | Gate G3 record only; no phase work |
| Owner decisions relied on | **D-245** (this correction), authorised by the owner on 2026-09-14 |
| Requirements touched | FR-SIM-06 (read, unchanged), NFR-PERF-01 (read, unchanged) |
| Open items | None closed. TBD-06 remains open on seeds per rate (D-135) |

## 1. Problem / motivation

**The SRS contradicted itself on a number the engine enforces.**

| Where | What it said |
|---|---|
| Gate G3 row, §9.1 | maximum fixed at **2000 ms (D-134)** |
| FR-SIM-06 | bounded by the header's maximum of **1300 ms (D-138)** |
| Appendix B, TBD-06 | Maximum duration: **CLOSED at 1300 ms by D-138** |

This is not cosmetic. FR-SIM-06 makes ONFLYENG return **ONF202E** for an
out-of-range duration. An implementer sizing that check from the gate row
would accept everything between 1300 and 2000 ms, silently admitting requests
that measurement says do not fit inside NFR-PERF-01's bound. Two sources said
1300; the gate row said 2000; the gate row was the wrong one.

**How it arose:** the G3 row was written while D-134 stood, and was never
revisited when D-136 and then D-138 overturned it. D-134 and D-136 are both
correctly marked SUPERSEDED in Appendix A.1 — only the §9.1 summary was left
behind. Nothing was hidden; a summary simply outlived the decision it quoted.

**How it was found:** not by reading the document, but by reading it *against
itself* — comparing the gate table's claims to the requirement text and the
open-items appendix. Three earlier passes over this same SRS, including one
that produced a full status report, did not catch it.

## 2. What changed

| File | Change |
|---|---|
| `docs/ONFLY-SRS.md` | §9.1 G3 row: maximum corrected to 1300 ms (D-138), with the refutation history stated inline. Appendix A.1: **D-245** added. |
| `docs/implementations/2026-09-14-g3-row-maximum-duration-correction.md` | This note. |

No code, no tests, no generated files. The engine already enforced 1300 ms,
because it is built against FR-SIM-06, not against the gate table.

## 3. Numerical basis

The three candidate maxima, all at N=1000 against D-133's 600 s bound:

| Decision | Value | How it was set | Measured | Verdict |
|---|---|---|---|---|
| D-134 | 2000 ms | estimate | **770 s** | refuted, 170 s over |
| D-136 | 1500 ms | estimate | **658 s** | refuted, 58 s over (VL-42) |
| **D-138** | **1300 ms** | **measured** | **507 s** | **fits, 93 s margin (15.5%)** |

D-137 is the decision that stopped the pattern: settle it by measuring where
the bound is actually crossed rather than by a third estimate. 1400 ms was
then declined on evidence — interpolation puts it near 581 s, a 19 s margin,
in exactly the region where cost per millisecond steepens from 0.407 s/ms to
0.755 s/ms, so interpolating upward there is unsafe.

## 4. Design decisions

**Corrected the row rather than leaving it.** The alternative — rely on
FR-SIM-06 and Appendix B already being right — was rejected because §9.1 is
where a reader goes to learn what a gate concluded, and a summary that
contradicts the requirement it summarises is a trap rather than a shortcut.

**Kept the history in the row rather than silently swapping the number.** The
row now names D-134's and D-136's refuted values. A reader who remembers
"2000 ms" should find out what happened to it, not quietly see a different
number and assume they misremembered.

**Did not touch the gate's result.** G3 stays **MEASURED**, not closed; seeds
per rate stay open under D-135. Only the quoted value was wrong.

## 5. Verification

```bash
grep -o "maximum fixed at [0-9]* ms ([^)]*)" docs/ONFLY-SRS.md   # 1300 ms (D-138)
grep -o "maximum of \*\*[0-9]* ms ([^)]*)\*\*" docs/ONFLY-SRS.md  # 1300 ms (D-138)
grep -o "CLOSED at [0-9]* ms by D-[0-9]*" docs/ONFLY-SRS.md      # 1300 ms by D-138
```

All three now agree. Remaining `2000 ms` occurrences are the historical
records in D-37, D-134, D-136, D-137, TBD-06 and D-245 itself, each
explicitly marked as superseded or as history. Markdown table structure was
checked: both edited rows carry five column separators, matching their
neighbours.

**Not run:** `make test` was not executed for this change. It is a
documentation-only edit that touches no compiled source, no generated file and
no lint input — `lint_col80` covers `engine generated softfloat tests tools
cobol`, not `docs`. Saying so explicitly rather than implying a green suite.

## 6. Not proven

- **Whether other §9.1 or §9.2 summaries quote superseded values.** This
  correction was found by comparing one gate row against its requirement; the
  same comparison has not been run across every gate and phase row.
- **Phase B still has no completion marker** in §9.2, while C and D both do,
  even though D-47 states plainly that Phase B was exited on 2026-09-10. Noticed
  in the same pass and deliberately left alone: it is a separate record gap and
  changing §9.2 needs its own owner answer.
- Two further gaps noticed in that pass were closed the same day by a parallel
  session and are **not** outstanding: Gate G0's missing closure marker
  (**D-241**) and A-03/A-04 still reading "TBC at Gate G0" (**D-242**, VL-86,
  VL-87).
- **Where between 1300 and 1500 ms the bound is actually crossed** remains
  unmeasured, and §3 above says not to interpolate it.

## 7. A note on concurrency

This correction was first written as **D-235**. While it sat uncommitted, a
parallel session pushed D-235 through D-244, so it was renumbered to **D-245**
and rebased. Appendix A.1's decision ids are a single global counter and every
recent commit touches this file, so two sessions writing decisions at the same
time will collide by construction. Worth knowing before scheduling parallel
work on the SRS.

## 8. Related docs

- `docs/ONFLY-SRS.md` — §9.1 Gate G3, FR-SIM-06, Appendix A.1 D-245, Appendix B TBD-06.
- `docs/implementations/2026-09-12-tbd06-maximum-and-tbd19-streaming.md` — where 1300 ms was measured and D-134/D-136 refuted.
- `docs/implementations/2026-09-11-gate-g3-measured.md` — the G3 measurement itself.
