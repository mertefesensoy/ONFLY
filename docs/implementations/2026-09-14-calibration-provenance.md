# 2026-09-14 — Calibration provenance: the search replays, the shipped W_syn does not match it

| Field | Value |
|---|---|
| Date | 2026-09-14 |
| Author | ONFLY senior engineer |
| Phase / gate | Phase C (Science, x86) — verification of Phase C's own record |
| Owner decisions relied on | D-207, D-208, D-209, D-210, D-211 |
| Requirements touched | SR-MOD-02 (W_syn row, amended), SR-CAL-01…03, ACC-4 |
| Open items closed | none |

## 1. Problem / motivation

D-206 declared Phase C complete. The `/goal` under which this session ran
asks for every exit criterion to be evidenced by a command run **in this
session**, and three Phase C items had only earlier-session evidence: data
retrieval, the SR-CAL search, and ACC-4. The owner chose (D-207) to re-run
ACC-4 and to spot-check the calibration rather than cite the old output.

The spot-check **failed**, and chasing that failure is what this document is
about. It turned into three findings, one of which corrects an earlier one of
mine.

## 2. What changed

| File | Change |
|---|---|
| `prep/calibrate.py` | `key()` documented as a label not a value; each candidate now records `w_syn` (exact float), `w_syn_label` and `w_syn_hex`; new `--log` option. |
| `prep/extract.py` | New `--calcheck`; it asserts the manifest's W_syn and digest and **reports** the VL-63 comparison rather than asserting it. |
| `docs/ONFLY-SRS.md` | D-207…D-211; VL-79, VL-80, VL-81; **SR-MOD-02's W_syn row amended** (D-211); VL-79's over-broad claim corrected. |
| `data/calibration/search-log-rerun.json` | The replayed search, 16 candidates, with exact floats. |

## 3. What happened, in order

### 3.1 ACC-4 re-run: the format change is provably neutral

`python prep/acc4.py --jobs 8` — 151 full-brain runs, 7,723 s. VL-64 had
measured ACC-4 on the **v1.0** network (`ea605b865c52…`); this ran on the
**v1.1** network (`aaa825c2d025…`). Every number agreed exactly: 3.67 /
14.35 / 28.38 / 68.38 / 88.80 Hz, standard deviations 4.22 / 8.45 / 7.85 /
8.19 / 5.07, same per-rate verdicts, same shape verdict.

That is D-192's requirement — a network with `nbias` = 0 reproduces version
1.0's arithmetic exactly — **confirmed on the reference network over 151
runs**, not merely on fixtures. ACC-4 remains FAIL at 10 and 40 Hz.

### 3.2 The calibration spot-check failed

`--calcheck` re-ran the shipped full network at the SR-CAL-02 calibration
rates with D-169's seeds and measured **3.67 / 48.83 / 75.17 Hz** where VL-63
recorded **3.83 / 46.17 / 77.33**.

Ruled out in turn: the network file (byte-identical to the candidate `acc4.py`
emits), the header fields (identical), the seeds and duration (identical),
and the summary arithmetic (`onfly_rates` pools six values, equivalent to the
check's per-seed mean).

### 3.3 The cause, and a measurement of how much it matters

`prep/calibrate.py` had `key(w) = "%.4f" % w`, used for the candidate's
filename *and* its log key, and stored `float(k)` — the **label** — as the
candidate's `w_syn`. The network, though, was emitted from the unrounded
golden-section value.

How much a difference that small matters was measured directly, on the full
brain at 80 Hz seed 1:

| W_syn | MN9 readouts | network total spikes |
|---|---|---|
| 0.29685 | [62, 2] | 92,476 |
| **0.29690** | **[80, 4]** | 92,322 |
| 0.29695 | [61, 1] | 90,309 |

**A 0.017% change in W_syn swings the readout 25%, while the whole-network
total moves about 2%.** The model is chaotic at the readout and stable in
aggregate.

### 3.4 A correction I had to make to my own finding

On that evidence I wrote VL-79, claiming the search "cannot be replayed".
**That was wrong**, and the re-run the owner then authorised (D-209) proved
it: all 16 candidates reproduce VL-63 to the digit — the eight scan points,
the scan minimum and bracket, and the eight golden-section refinement values,
which are *computed*, not literals. The final objective matches to sixteen
significant digits (0.06909687990972463).

VL-80 withdrew the claim and replaced it with the accurate one: **the search
replays exactly; what differs from it is the network the project ships.**

### 3.5 The real defect, and the surprise

The search chose **`0.2968847050625473`** (hex `0x1.30028b4bb479fp-2`),
filed under the label `0.2969`. `prep/emit.py`'s `W_SYN` and SR-MOD-02 carry
the **literal** `0.2969` — 1.529×10⁻⁵ higher, 0.00515%.

So the shipped network was never the network the search selected. But against
the D-164 reference (`mn9_mean_hz` 48.95 at 80 Hz, 71.52 at 160):

| W_syn | 80 Hz error | 160 Hz error | **SR-CAL-03 objective** |
|---|---|---|---|
| search-chosen `0.29688470…` | 5.68% | 8.13% | **0.0691** |
| shipped literal `0.2969` | 0.25% | 5.11% | **0.0268** |

**The rounding landed 2.6× better than the minimum golden-section reported.**
That is not luck to rely on; it is evidence that SR-CAL-03's objective is
noise-dominated at the resolution the search refines to — golden-section
converged to 0.005 mV on a surface where a 0.000015 mV step moves the answer
further than the convergence interval does.

## 4. Mathematical / numerical details

SR-CAL-03's objective is the mean relative error over the calibration rates
whose reference is non-zero (D-172 excludes 20 Hz, whose reference is 0.00):

> E(W) = ½ · ( |m₈₀(W) − r₈₀| / r₈₀ + |m₁₆₀(W) − r₁₆₀| / r₁₆₀ )

with *m* the mean MN9 rate over both readouts and D-169's three seeds, and
*r* the D-164 Shiu reference means. Reproducing VL-63's 0.069 from the
re-run's rates confirms the objective is computed identically.

The sensitivity is the interesting quantity. Writing δ = ΔW/W, the measured
response is |Δm/m| ≈ 25% for δ ≈ 1.7×10⁻⁴ at the readout, against ≈ 2% for
the network total — a gain of order 10³ at the readout and order 10² in
aggregate. A readout two synaptic hops from a stimulus whose own drive is
Poisson is not a smooth function of W in any usable sense at this scale; it
is a threshold crossing counted over a finite window.

This is why the last digit of a calibrated W_syn carries no information, and
why VL-63's own caveat needed extending from "the last digit is not
physically meaningful" to "**the search minimum itself is not meaningful at
that resolution**".

## 5. Design decisions

Owner's: **D-207** re-run ACC-4 and spot-check the calibration; **D-209**
re-run the search into a separate log; **D-210** park at 13 candidates for
travel, then resume; **D-211** keep 0.2969 as a deliberately adopted value.

The engineer's, recorded as **D-208** and flagged to the owner rather than
decided for him: storing the exact float and hex beside the label, and making
`--calcheck` assert only the manifest facts that are checkable.

Two alternatives the owner was offered and declined at D-211, with the costs
stated: adopting the exact chosen float (faithful to the search, but the
worse-calibrated of the two, and it would invalidate the activity ranking,
ACC-4, the compensating input and the admitted subcircuit); and re-running
with more seeds to resolve the minimum (a protocol change, roughly five times
four hours, same invalidation risk).

## 6. Verification

All of the following ran **in this session** on x86-64 Windows 11, mingw32
gcc 6.3.0, NATIVE backend.

```
python prep/acc4.py --jobs 8
  rate  onfly  sd  se  reference  tol  mag
    10   3.67 4.22 0.77  0.00  2.00  FAIL
    40  14.35 8.45 1.54  4.73  2.00  FAIL
    60  28.38 7.85 1.43 32.07  8.02  PASS
   120  68.38 8.19 1.50 64.43 16.11  PASS
   200  88.80 5.07 0.93 77.57 19.39  PASS
  ACC-4 shape PASS; magnitude FAIL; ACC-4 FAIL          (7,723 s)
```

Identical to VL-64 in every field, on a different format version.

```
python prep/calibrate.py --scan --refine --log search-log-rerun.json --jobs 8
  scan minimum at 0.3000 mV (error 0.1397); bracket [0.2750, 0.3500]
  chosen: W_syn = 0.2969 mV, error 0.0691                (16 candidates)
```

All 16 candidates identical to `search-log.json`; chosen error
`0.06909687990972463` bit-identical; chosen float now recorded as
`0.2968847050625473`.

```
python prep/extract.py --calcheck --jobs 8
    20      3.67      3.83    -4.2%
    80     48.83     46.17    +5.8%
   160     75.17     77.33    -2.8%
  manifest W_syn and network digest: VERIFIED
```

**What these results do NOT prove:**

* Everything here is **x86-64 NATIVE**. Nothing is proven for Linux s390x,
  MVS 3.8j or z/OS.
* The objective was evaluated at **three seeds per rate** throughout (D-169).
  No seed count large enough to resolve the minimum was attempted, so the
  location of the true minimum remains unknown — that is the finding, not an
  omission.
* **Data retrieval was not re-run and cannot be**: the MaleCNS source data is
  not present in this worktree, only `data/malecns/MANIFEST.json`. It is
  cited by digest.
* ACC-4's failure is unchanged and is a property of the protocol difference
  (VL-64, VL-65), not of the calibration.

## 7. Related docs

* `docs/ONFLY-SRS.md` SR-MOD-02 (W_syn row), SR-CAL-01…05, Appendix A.1
  D-207…D-211, Appendix D VL-63, VL-79, VL-80, VL-81.
* `docs/implementations/2026-09-13-srext-subcircuit-admitted.md` — the
  extraction work whose results this verifies were built on a consistent
  W_syn.
* `data/calibration/search-log.json`, `search-log-rerun.json`, `acc4.json`,
  `calcheck.json`.
