# 2026-09-15 — Phase E slice 5: the acceptance sweep, and the one that fails

| Field | Value |
|---|---|
| Date | 2026-09-15 |
| Author | ONFLY senior engineer |
| Phase / gate | Phase E — MVS MVP |
| Owner decisions relied on | D-279, D-280, D-282, D-283, D-285, D-286, D-287 |
| Requirements touched | ACC-1 … ACC-7, SR-CAL-05, NFR-PERF-01, FR-BAT-01, FR-BAT-04, FR-BAT-05, FR-BAT-06, IR-JCL-04, TX-01, TX-04 |
| Open items closed | none |

## 1. Problem / motivation

Phase E's exit content is *GCCMVS build; ONFLYDRV; JCL; BUZZ
demonstration; ACC-1 … ACC-7*. The first four were done earlier on
2026-09-15 (slices 1–3) and row 7 of the determinism matrix was filled
in slice 4. What remained was the acceptance criteria themselves — and
two problems with the evidence that existed for them.

**The first is date.** ACC-1, ACC-2 and ACC-3 passed in Phase C
(VL-76, VL-77, VL-78), but against `data/calibration/diag-F3-n500.bin`,
the *candidate* that D-205 later admitted and emitted as
`data/networks/onfnet-malecns-v1.0-srext.bin`. Nothing had ever
evaluated them against the shipped file under its shipped name. D-207
established the principle for Phase C — that a phase's completion should
rest on evidence produced now rather than cited from an earlier session
— and D-280 extends it to Phase E.

**The second is that the source moved underneath them.** D-285 added a
cast to the vendor SoftFloat library so that JCC would emit an object at
all. It is a null change by construction, but "by construction" is an
argument and this project measures. Every MVS result recorded earlier
on 2026-09-15 — row 6's nineteen fingerprints, ACC-6's 166 s, ACC-7's
BUZZ run — was produced from the text before that cast. Each has to be
produced again or reported as standing on superseded source.

**And one criterion cannot be made to pass.** ACC-4 compares the full
MaleCNS brain against Shiu et al.'s FlyWire-based reference. VL-64
recorded it failing at 10 and 40 Hz, where MN9 fires and the reference
is silent. The owner has already declined to change the stimulus set
(D-177) and declined to relabel the criterion (D-195, D-206), and
SR-CAL-05 forbids widening tolerances after the fact. D-280's
instruction is to re-run it and report the finding — so the re-run
changes the date on the evidence, not the verdict, and Phase E ends
PARTIAL on this one criterion however well everything else goes.

## 2. What changed

| File | Change |
|---|---|
| *(filled in as the sweep proceeds)* | |

## 3. Implementation approach

*(filled in)*

## 4. Mathematical / numerical details

*(filled in)*

## 5. Design decisions

*(filled in)*

## 6. Verification

*(filled in)*

## 7. Related docs

- SRS Section 6.4 (ACC-1 … ACC-7), 6.2 (SR-CAL-05), 7 (NFR-PERF-01),
  8.3, 8.4, Appendix A.1 (D-279…D-287), Appendix D
- [2026-09-15 — Phase E slice 4](2026-09-15-phase-e-slice-4-jcc-row-7.md)
- [2026-09-13 — the srext subcircuit admitted](2026-09-13-srext-subcircuit-admitted.md)
- [2026-09-12 — Phase C calibration](2026-09-12-phase-c-calibration.md)
