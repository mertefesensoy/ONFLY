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

### 3.1 What "re-run" means for each criterion

The seven criteria are not the same kind of thing, and saying "re-run
them" hides that. What each one actually needs:

| ID | What it is measured on | What re-running it costs |
|---|---|---|
| ACC-1 | The shipped `srext` network, x86, 5 rates × 30 seeds | `prep/extract.py --acc1`, about a minute |
| ACC-2 | The same pass; rate 0 must give zero spikes everywhere | included in ACC-1's pass, plus every MVS and s390x run |
| ACC-3 | `srext` against the **full-brain** reference in `acc4.json` | `prep/extract.py --acc3-file`, a few minutes |
| ACC-4 | The **full brain** against Shiu's reference, 151 runs | `prep/acc4.py`, about 90 minutes |
| ACC-5 | Every row of Section 8.3 — rows 6 and 7 are the MVS ones | two TK5 jobs, about 15 minutes each, plus `path` |
| ACC-6 | One request, timed on TK5 | the TX-04 job, about 4 minutes |
| ACC-7 | BUZZ end to end on TK5 | about 15 minutes |

ACC-2 is the one worth noticing: it is not a separate run at all. It is
a property every other run either has or does not — *a request with rate
0 produces zero spikes in every neuron, on every platform and backend* —
so it is evaluated wherever G-15 and G-01 appear, which is the x86
suite, the s390x suite, row 6 and row 7.

### 3.2 The order, and why the lab goes first

D-283 serializes the lab work ahead of the x86 science. The reason is
ACC-6: NFR-PERF-01 bounds wall-clock time on the TK5 reference host, and
§6.2c of the slice 1 document measured the same MVS work 23% apart
under load. A figure taken while 151 full-brain runs saturate the host
is not a measurement of the bound, it is a measurement of the
contention. Everything else in the sweep is insensitive to load —
return codes and fingerprints do not change with CPU pressure — so only
ACC-6 actually constrains the order, and it constrains it completely.

### 3.3 Why row 6 is run again at all

D-285 changed the text every platform compiles. Row 6's nineteen
fingerprints, ACC-6's 166 s and ACC-7's BUZZ run were all recorded
earlier on 2026-09-15, from before that change. The cast is neutral by
construction and now also by measurement on x86 (§6), but "we re-ran the
x86 suite and it was fine, so the MVS result still stands" is an
inference across platforms, and this project does not make those. The
MVS results are produced again on MVS.

## 4. Mathematical / numerical details

Four of the seven criteria are statistical, and they compare three
different things. Getting them confused is easy, so they are set out
here in plain English with their notation.

### 4.1 The three quantities being compared

Let *R* be a validation rate, one of {10, 40, 60, 120, 200} Hz (D-165),
and let each measurement be over seeds *s* = 1…30 (D-135) at the
standard duration of 1000 ms (D-73). For each rate there are three
numbers:

| Symbol | What it is |
|---|---|
| **F(R)** | the **full MaleCNS brain's** mean MN9 firing rate, 184,099 neurons, x86 NATIVE |
| **S(R)** | the **shipped subcircuit's** mean MN9 rate, 501 neurons, the `srext` network |
| **K(R)** | **Shiu et al.'s reference** MN9 rate, from the D-164 re-run of their published code on FlyWire |

The mean is over both MN9 neurons and all 30 seeds; the rate in Hz is
spikes ÷ 1 s, so at 1000 ms the count and the rate are numerically
equal.

### 4.2 ACC-3 compares S against F — "did truncation lose anything?"

ACC-3 asks whether cutting 184,099 neurons down to 501 changed the
answer. It is satisfied at rate *R* when

    |S(R) − F(R)|  ≤  max( 0.10 × F(R),  1 Hz )

The 1 Hz floor (D-166) exists because a relative tolerance is
meaningless near zero: 10% of 0.02 Hz is not a tolerance, it is a
rounding error.

D-202 added an **exclusion rule**, and it is not a loosening. A rate
whose reference satisfies sd(F) ≥ mean(F) is excluded from the
criterion and *reported* instead of tested. At such a rate the
full-brain reference is not a reproducible quantity at all — it is the
frequency of a rare event, and requiring a 501-neuron truncation to
match it would be requiring it to reproduce a coin toss. On the D-135
seeds this excludes exactly one rate, 10 Hz, where F = 3.67 ± 4.22 Hz.
At the other four, F is 14.35 ± 8.45, 28.38 ± 7.85, 68.38 ± 8.19 and
88.80 ± 5.07 — every one with sd well below its mean.

### 4.3 ACC-4 compares F against K — "is this still the fly?"

ACC-4 asks whether the MaleCNS model reproduces Shiu's published
behaviour. It has two clauses.

**Magnitude**, at each validation rate:

    |F(R) − K(R)|  ≤  max( 0.25 × K(R),  2 Hz )

**Shape**, across rates: F must not *decrease* from one validation rate
to the next by more than one standard error of its own mean at the lower
rate — se = sd/√30, the interpretation recorded as proposal P-11 because
the SRS does not say whose standard error — and the onset rate, the
lowest rate at which F exceeds 1 Hz, must be within one sampled rate of
K's onset.

**Where it fails, and why the failure is structural.** From
`data/calibration/acc4.json`, measured 2026-09-12:

| R (Hz) | F(R) ± sd | K(R) | tolerance | magnitude |
|---|---|---|---|---|
| 10 | 3.67 ± 4.22 | **0.00** | ±2.0 | **fail** |
| 40 | 14.35 ± 8.45 | **4.73** | ±2.0 | **fail** |
| 60 | 28.38 ± 7.85 | 32.07 | ±8.02 | pass |
| 120 | 68.38 ± 8.19 | 64.43 | ±16.11 | pass |
| 200 | 88.80 ± 5.07 | 77.57 | ±19.39 | pass |

Shape passes (`shape_pass: true`, no decrease beyond one standard
error), and the onset clause passes even though ONFLY's onset is 10 Hz
against the reference's 40 Hz, because 10 Hz is within one *sampled*
rate of 40 Hz on the {10, 40, 60, …} grid.

So the failure is confined to the two lowest rates, and it is one-sided:
**the MaleCNS fly responds to sugar where Shiu's FlyWire fly does not.**
Note what the tolerance does at those rates. Where K = 0, the relative
term 0.25 × K is also 0, so the entire tolerance is the 2 Hz floor —
there is no rate at all at which a model that fires when the reference
is silent can pass. That is by design (SR-CAL-05, R-03): the criterion
is meant to detect exactly this, and D-177 chose to report it as a
finding about two connectomes rather than to tune the stimulus set until
it went away.

## 5. Design decisions

**D-280 — ACC-4 is re-run, and its failure reported.** The alternative
offered was to cite VL-64's 2026-09-12 measurement and say plainly it
was not re-run, which would have saved about 90 minutes of host time.
The owner chose the re-run. The verdict is not in question — SR-CAL-05
forbids widening tolerances after the fact, D-177 kept the stimulus set
and D-195 and D-206 refused to relabel the criterion — so what the
re-run buys is that Phase E's one failing criterion fails *on evidence
from the session that reports it*, which is the same standard D-207 set
for Phase C.

**D-283 — serialization.** See §3.2. The engineer proposed overlapping
at reduced `--jobs` to save about 90 minutes of wall clock, with ACC-6
then cited rather than re-measured; the owner chose the clean figure
over the saved time.

**D-287 — both `path` jobs.** ONFPRUN re-establishes ACC-5 row 6's
fourteen `path` fingerprints against the post-D-285 source; SUGR is the
only job that prints ONF201W, ONF203E and ONF202E through **ONFLYDRV**
on MVS. The engineer stated before the choice that neither substitutes
for the other: SUGR has no IDCAMS dump step — `tests/run_mvsrun.py`
pins it to FR-BAT-01's exactly three EXEC steps — so it recovers no
records to compare, and ONFPRUN runs the engine alone, so it prints no
report. About 130 minutes between them, which the owner accepted.

**Engineer's call, recorded not decided: ACC-2 is not given a run of its
own.** Section 6.4 defines it as a property holding *on every platform
and backend*, and G-01 and G-15 are rate-0 requests already present in
the x86 suite, the s390x suite, row 6 and row 7. A dedicated ACC-2 run
would test one platform where the suite tests four.

## 6. Verification

*(filled in)*

## 7. Related docs

- SRS Section 6.4 (ACC-1 … ACC-7), 6.2 (SR-CAL-05), 7 (NFR-PERF-01),
  8.3, 8.4, Appendix A.1 (D-279…D-287), Appendix D
- [2026-09-15 — Phase E slice 4](2026-09-15-phase-e-slice-4-jcc-row-7.md)
- [2026-09-13 — the srext subcircuit admitted](2026-09-13-srext-subcircuit-admitted.md)
- [2026-09-12 — Phase C calibration](2026-09-12-phase-c-calibration.md)
