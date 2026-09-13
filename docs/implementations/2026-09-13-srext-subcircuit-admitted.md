# 2026-09-13 — The SR-EXT subcircuit: fitted compensation, and N = 500 admitted

| Field | Value |
|---|---|
| Date | 2026-09-13 |
| Author | ONFLY senior engineer |
| Phase / gate | Phase C (Science, x86) — closing the SR-EXT-03 escalation |
| Owner decisions relied on | D-197 … D-205 |
| Requirements touched | SR-EXT-01, SR-EXT-02, SR-EXT-03, **ACC-3 (amended)**, ACC-1, ACC-2, IR-NET-09, NFR-MEM-01, NFR-PERF-01 |
| Open items closed | **SR-EXT-03's escalation**, open since D-183 across twenty-one constructions |

## 1. Problem / motivation

SR-EXT-03 requires N to be the smallest of {250, 500, 1000} (narrowed from
{…, 2000, 4000} by Gate G3) satisfying ACC-3, NFR-MEM-01 and NFR-PERF-01,
and escalates to the owner if none does. That escalation had stood since
2026-09-13 morning. Twenty-one constructions had been measured — activity
ranking, partner patches, path and two-hop neighbourhoods, inhibitory
closure, balance-matched selection, two families of weight compensation, and
the format v1.1 compensating input at three estimators — and none satisfied
ACC-3. The best agreement was 62% at the worst rate, where ACC-3 allows 10%.

Without a chosen network, **Phase E cannot start**: it is the phase that
ships a network to MVS, and there was nothing to ship.

## 2. What changed

| File | Change |
|---|---|
| `docs/ONFLY-SRS.md` | D-197…D-205; VL-73…VL-78; **ACC-3 amended** (D-202); **SR-EXT-02 amended** and SR-EXT-01/SR-EXT-03 annotated (D-205). |
| `prep/extract.py` | `--fitbias` (F1/F2), `--constbias` (F3), `--acc1`, `--admit`; `edges_within`; `acc3_excluded`; the multiplier search rewritten from bisection to scan-then-refine. |
| `tools/cmpback3.py` | New: run one network on every float backend and require bit-exact agreement; check ACC-2 on each. |
| `Makefile` | New `runners` target building `runnet` against SOFT3E and SOFT2C. |
| `data/networks/onfnet-malecns-v1.0-srext.bin` | The admitted MVP subcircuit. |
| `data/networks/MANIFEST.json` | `srext` entry with selection rule, estimator, fitted constant and every acceptance verdict; `mvp_subcircuit` names it. |

## 3. Implementation approach

### 3.1 The construction

SR-EXT-01's selection rule is **unchanged**: the 500 most active neurons by
total spike count over the 240-run full-brain ranking, ties by ascending body
id, plus every stimulus and readout neuron — 501 neurons, 10,783 edges.

SR-EXT-02's "unchanged weights" clause also **survives intact**. The
compensation is a *separate per-neuron input*, not a rescaling of any edge.
That distinction is not cosmetic: the twenty-one constructions that did alter
selection or weights were all measured first, and all of them failed.

What D-205 added to SR-EXT-02 is the format v1.1 compensating-input table
(IR-NET-09), built in two steps:

1. **The shape** — for each kept neuron, the mean per-step drive its dropped
   presynaptic neurons used to supply, with their firing estimated as the
   per-neuron **median** over 15 seeds (D-193; the median rather than the mean
   because full-brain activity is bimodal — a run either ignites ~191
   hyperactive neurons or does not).
2. **The scale** — a single constant, fitted on the SR-CAL-02 calibration
   rates {20, 80, 160} against SR-CAL-03's own objective, then judged out of
   sample on the validation rates. Its value is **0.6468**.

### 3.2 Why the search had to be rewritten

The first fit used bisection, on the assumption that more compensating drive
means more firing. **That assumption is false**, and the run exposed it: the
search reported 0.00 Hz at a 20× multiplier at 40 Hz, where the multiplier
1.0 network had measured 9.55 Hz.

Mapping the curve showed why (VL-73). At N = 500, 40 Hz:

| multiplier | 0 | 0.25 | **0.5** | 0.75 | 1.0 | 2.0 | 3.0 | 5.0 | 20 |
|---|---|---|---|---|---|---|---|---|---|
| MN9 Hz | 8.50 | 12.15 | **15.80** | 11.80 | 9.30 | 6.00 | 2.15 | 0.00 | 0.00 |

The response peaks and collapses. The cause is that **the sign of the
readout's own compensating value changes with rate**: at 40 Hz the left MN9's
bias is −0.45 while the sum over all 501 kept neurons is +50.68, so a large
multiplier suppresses the readout directly even while driving everything else
harder. At 120 Hz that same value is +0.45 and the response rises
monotonically to 242.75 Hz.

A bisection assuming monotonicity returned the 20× cap — the worst
multiplier available at that rate. The search was replaced with the coarse
scan plus refinement **D-171 had already chosen for the W_syn calibration,
for this exact hazard**. Following an existing decision's method rather than
inventing one is why this did not need a new owner decision.

### 3.3 A correctness-preserving speedup

Each probe emits a network, and `emit.build_network`'s first act is to select
the kept edges out of 24.7 million. `edges_within` does that selection once
per node set instead of once per probe. It is provably equivalent —
`build_network` re-runs the same test, which is then a no-op, and the
surviving edges arrive in the same order — and it was verified by digest
before being trusted: **5.99 s → 0.022 s, byte-identical output.**

### 3.4 The ACC-3 amendment, and why it is not special pleading

ACC-3 now tests a validation rate only where the full-brain reference mean
exceeds its own standard deviation over the same seeds. The wording states
the **condition**, not the rate (the owner chose this form over naming 10 Hz),
so it is auditable from data the suite already records and re-protects the
criterion automatically if a later W_syn destabilises a different rate.

On the D-135 seeds it excludes exactly one rate:

| rate | reference | sd | excluded? |
|---|---|---|---|
| 10 Hz | 3.67 | **4.22** | **yes** |
| 40 Hz | 14.35 | 8.45 | no |
| 60 Hz | 28.38 | 7.85 | no |
| 120 Hz | 68.38 | 8.19 | no |
| 200 Hz | 88.80 | 5.07 | no |

Two independent measurements justify it. At N = 500, **no multiplier between
0 and 20 produces more than 0.10 Hz** of MN9 firing at a 10 Hz stimulus
(VL-73); and **no N between 500 and 1000 recovers it either** (VL-75, giving
0.02, 0.53, 0.67, 0.60, 0.43 Hz at N = 500…1000 against a 3.67 Hz target).
The criterion was asking a 500-neuron subcircuit to reproduce the frequency
of a rare stochastic ignition in a 184,099-neuron network to within 1 Hz.

**The amendment did not weaken the criterion.** Under the amended ACC-3 and
the same construction, N = 250, 600, 700, 800 and 1000 all still fail. One
size of six passes. And tolerances were untouched — ±10% and the ±1 Hz floor
stand — so SR-CAL-05's bar on widening after the fact holds.

### 3.5 Admission is guarded

`--admit` refuses to emit unless `F3-n500` actually passes ACC-3 in the
recorded results, and it compares the emitted bytes against the artifact the
criteria were measured on, refusing on any difference. The run reported
`digest matches the measured artifact diag-F3-n500.bin`. Without that check
the manifest could claim verdicts for a file nothing had been measured on.

## 4. Mathematical / numerical details

**The compensating input.** For a kept neuron *i* and stimulus rate *R*,

> bias[R][i] = m · Σ<sub>j ∉ S, j→i</sub> w<sub>ji</sub> · S̃<sub>j</sub>(R) / T

where *w<sub>ji</sub>* is the signed synapse count × W_syn, *S̃<sub>j</sub>(R)*
is the **median** over 15 seeds of *j*'s spike count in a *T* = 10,000-step
full-brain run, and *m* = 0.6468 is the fitted constant. Dividing by *T*
makes it a per-step expectation, so a request of any duration receives the
same input per step. Rate 0's row is zero by construction (IR-NET-09), which
is what keeps ACC-2 exact.

**The objective.** *m* minimises the mean over {20, 80, 160} Hz of
|measured − reference| / reference — SR-CAL-03's own form. No rate is
excluded from it; D-172's exclusion applies to a zero reference and none of
the three has one (5.63, 46.20, 76.57 Hz). The scan had a clean single
minimum: 0.6705 at *m* = 0, falling to 0.3492 at 0.6, rising to 2.0125 at 20.
The residual 0.34 is almost entirely the 20 Hz rate, which VL-73 showed
cannot be matched at this size.

**Why one parameter and not two.** F1 fitted *a* + *b*·*R* on the same three
rates and reached 14% worst deviation above the 10 Hz floor; the constant
reached **5.4%**. F1's line was tilted by the 20 Hz calibration point wanting
0.257 while every rate from 60 Hz up wants ≈0.58. Fewer parameters fitted the
data better — and a pass on one parameter carries more evidence than a pass
on two.

## 5. Design decisions

Owner's, each recorded in Appendix A.1 before dependent code was written:

* **D-197** scope; **D-198** push policy; **D-199** the fitted-bias plan;
  **D-200** the constant multiplier; **D-201** the N sweep; **D-202** the
  ACC-3 amendment *and its wording*; **D-203** evaluate ACC-1 first;
  **D-204** run every float backend first; **D-205** amend SR-EXT-02 and
  admit.

The owner asked for four separate verification steps before admitting
anything — ACC-3, then ACC-1/ACC-2, then the backends, then admission. Each
one found something the previous had not covered.

Architect's (engineer's) choices, stated so they are not mistaken for the
owner's: the scan grid and refinement count; 10 seeds for fit candidates and
30 for verdicts; N ∈ {500, 1000} for the first fit; `edges_within`; running
ACC-2 alongside ACC-1; and the digest guard in `--admit`.

## 6. Verification

All results below ran **in this session** on x86-64 Windows 11, mingw32 gcc
6.3.0, Python 3.13.14.

**The admitted network** — `onfnet-malecns-v1.0-srext.bin`, 501 neurons,
10,783 edges, 171,768 bytes, 9 bias rows, multiplier 0.6468, SHA-256
`bf09a3ad18a8…`.

**ACC-3** (`python prep/extract.py --constbias --fit-n 500 --jobs 14`):

```
F3-n500  ACC-3 PASS   excluded rates: [10]
   10 Hz sub   0.02 full 3.67 +-4.22  EXCLUDED (D-202: sd 4.22 >= mean 3.67)
   40 Hz sub  13.77 full  14.35 tol  1.44  PASS
   60 Hz sub  28.88 full  28.38 tol  2.84  PASS
  120 Hz sub  72.07 full  68.38 tol  6.84  PASS
  200 Hz sub  91.35 full  88.80 tol  8.88  PASS
```

**SR-EXT-03's determination**: 250 FAIL, **500 PASS** (need 255,688 B against
8M; inside Gate G3), 1000 FAIL.

**ACC-1 and ACC-2** (`--acc1 data/calibration/diag-F3-n500.bin`):

```
    40  ref  4.73  mean 13.77  30/30 seeds  PASS
    60  ref 32.07  mean 28.88  30/30 seeds  PASS
   120  ref 64.43  mean 72.07  30/30 seeds  PASS
   200  ref 77.57  mean 91.35  30/30 seeds  PASS
ACC-1 PASS over the rates it applies to: [40, 60, 120, 200]
ACC-2 PASS: rate 0 produced 0 spikes across all 501 neurons
```

**All three float backends** (`mingw32-make runners`, then
`python tools/cmpback3.py …`):

```
EXACT AGREEMENT: NATIVE, SOFT3E, SOFT2C agree bit-for-bit on all 300
comparisons (150 rate/seed pairs, readout spike counts and first-spike
latencies)
NATIVE / SOFT3E / SOFT2C  rate 0: 0 spikes, all neurons — ACC-2 PASS
```

**What these results do NOT prove** (recorded as VL-76, VL-77, VL-78):

* **Every result is x86-64.** Nothing is proven for Linux s390x, MVS 3.8j or
  z/OS, and **the v1.1 header has never been decoded by GCCMVS**. ACC-2's
  text claims "every platform and backend"; this discharges the backend half
  on one platform.
* **ACC-4 still fails** (VL-64, VL-65) and no extraction result can move it:
  it compares the full brain against the Shiu reference, not a subcircuit
  against the full brain. D-177 recorded it as a finding under SR-CAL-05.
* ACC-5, ACC-6 and ACC-7 are unevaluated on this network. It has no golden
  request, so its determinism has no standing fingerprint for a later MVS
  comparison.
* The fitted multiplier was not tested on seeds outside 1…30, at a different
  W_syn, or at durations other than 1000 ms.
* F2's four-of-five agreement (VL-73) was in sample by construction and is
  labelled so everywhere; only F1 and F3 are out-of-sample results.

## 7. Related docs

* `docs/ONFLY-SRS.md` §6.3 (SR-EXT-01…03), §6.4 (ACC-1…ACC-3), Appendix A.1
  D-197…D-205, Appendix D VL-73…VL-78.
* `docs/implementations/2026-09-13-network-format-v11-compensating-input.md`
  — the format and kernel work this builds on.
* `docs/implementations/2026-09-13-truncation-compensation.md` — the eleven
  network-level constructions that failed first.
* `data/calibration/acc3-constbias.json`, `acc3-fitbias.json`,
  `acc1-candidate.json`, `backends-F3-n500.json`.
