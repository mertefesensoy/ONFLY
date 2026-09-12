# 2026-09-12 — Phase C: TBD-07..10 closed, the Shiu reference re-run, W_syn calibration

| Field | Value |
|---|---|
| Date | 2026-09-12 |
| Author | ONFLY engineering session (third session of the day) |
| Phase / gate | Phase C — Science (x86); scope set by D-162 |
| Owner decisions relied on | D-162 … D-172 |
| Requirements touched | SR-CAL-01, SR-CAL-02, SR-CAL-03, SR-CAL-04, SR-CAL-05, SR-MOD-05, FR-PRP-05, FR-PRP-06, IR-NET-03, IR-MSG-02, ACC-3, ACC-4 |
| Open items closed | TBC-06, TBD-07, TBD-08, TBD-09, TBD-10 |

## 1. Problem / motivation

Calibration (SR-CAL) was blocked on four open items and one missing input.
SR-CAL-02 needs the rate split fixed before the first run (TBD-07), ACC-3 and
ACC-4 need their floors (TBD-08), and SR-CAL-04 needs the Shiu reference curve
(TBC-06), which D-77 had held open because neither the paper's figure nor a
re-run of the published code was reachable from the host on 2026-09-11. TBD-09
and TBD-10 were format v1.0 gates that D-65 had deliberately deferred.

Without calibration, `W_syn` stays the FlyWire value 0.275 mV applied to a
different connectome. The 2026-09-11 full-brain run showed what that costs:
the MN9 pathway responds monotonically, but global activity flips between two
regimes unrelated to the stimulus (see the full-brain run note), which is what
an uncalibrated synaptic scale looks like. SR-EXT-01's subcircuit is defined
by activity in a *calibrated* run, so nothing downstream in Phase C, D or E can
be final until this is done.

## 2. What changed

| File | Change |
|---|---|
| `docs/ONFLY-SRS.md` | D-162 … D-171 recorded; TBC-06, TBD-07, TBD-08, TBD-09, TBD-10 closed; SR-CAL-02, ACC-3, ACC-4, IR-NET-03, IR-MSG-02 text updated under D-165/D-166/D-167; proposals P-09 and P-10 added; verification limits added (Section 6 below). |
| `reference/shiu/rerun.py` | New. Drives Shiu et al.'s vendored `model.py` through the Figure 1D protocol at the eight TBD-07 rates, seeded per trial, and writes the MN9 reference table and a manifest. |
| `reference/shiu/utils.py` | New, vendored verbatim from github.com/philshiu/Drosophila_brain_model (MIT): `load_exps` and `get_rate`, the exact rate computation of `figures.ipynb`. |
| `reference/shiu/MANIFEST.json` | New. SHA-256 and sizes of the vendored code and of the two FlyWire 630 data files (not committed). |
| `prep/calibrate.py` | New. SR-CAL-03 search: signed-count cache, one full-network emission per candidate, nine engine runs per candidate, the objective, the D-171 scan and golden-section, the kept search log. |
| `prep/emit.py` | `build_network` takes `w_syn` and `max_ms` parameters (defaults unchanged in meaning); `MAX_MS` is now 1300 per D-138 instead of D-37's provisional 5000. |
| `.gitignore` | FlyWire inputs, re-run spike outputs, candidate networks and the signed cache are ignored; digests and logs are committed. |

## 3. Implementation approach

**Reference (SR-CAL-04, D-164).** `rerun.py` calls Shiu's own `run_trial`
(`create_model`, `poi`, `Network.run`) unchanged, on the FlyWire 630 files the
paper used, with the 21 right-hemisphere labellar sugar GRNs of `figures.ipynb`
cell 4 as Poisson inputs. It differs from Shiu's `run_exp` in two documented
ways: every trial is seeded (`brian2.seed(trial + 1)`) so the result is
reproducible, and only the TBD-07 rates are run. The MN9 rate is computed by
Shiu's `utils.get_rate` (spikes / `t_run`, mean over `n_run` = 30 trials),
then reduced to the D-170 quantity, the mean of the left and right MN9.

Contract of `rerun.py`: inputs are the vendored code and the two data files;
outputs are `results/data/sugarR_<r>Hz.parquet` (spike times, ignored by git),
`results/mn9-reference.csv` (committed) and `results/MANIFEST.json`
(environment, digests, timings). No side effects outside `results/`.

**Calibration (SR-CAL-01..03).** `calibrate.py` caches the signed pair counts
once (`signed.npz`, the output of `prep/signs.py`, so D-54/D-55/D-56 are
applied exactly once), then for each candidate `W_syn` builds the **full**
184,099-neuron network through `emit.build_network` — the same code that builds
the shipped network, now parameterised — and runs `build/runnet.exe` at the
three calibration rates for seeds 1, 2, 3. ONFLY's MN9 rate at a rate is the
mean over both readouts and all seeds of `spikes / 1 s`. Every candidate's
network digest, all nine raw run results, the derived rates, the error and the
timings go into `data/calibration/search-log.json`, which is written after
every candidate so an interrupted search resumes without recomputation.

Contract of `calibrate.py evaluate(w)`: input a `W_syn` in mV; output the log
entry; side effects are one 300 MB network written and (unless `--keep`)
deleted, nine engine processes, and the log file. Invariant relied on: the
engine is deterministic for a given (network, rate, seed), so re-evaluating a
candidate returns the cached entry rather than re-running.

## 4. Mathematical / numerical details

**Objective (SR-CAL-03, D-172).** With calibration rates `R = {20, 80, 160}`
Hz, ONFLY rate `o(r)`, Shiu reference `t(r)`, and `R⁺ = {r ∈ R : t(r) > 0}`:

    E(W_syn) = (1/|R⁺|) · Σ_{r∈R⁺} |o(r) − t(r)| / t(r)

The re-run measured `t(20) = 0` (no MN9 spike in 30 trials), so `R⁺ = {80,
160}` and 20 Hz is excluded from the objective and reported as a finding
(D-172; the earlier proposal P-10 of a 2 Hz divisor floor was withdrawn).

**ONFLY rate at one calibration rate (D-169, D-170).**

    o(r) = (1/6) · Σ_{seed∈{1,2,3}} Σ_{k∈{MN9_L, MN9_R}} spikes(k, r, seed) / 1.0 s

**Reference rate (D-164, D-170).** Shiu's `get_rate` computes, per neuron and
rate, the mean over 30 trials of `spikes / t_run` with `t_run` = 1 s; the
reference is the mean of that value over the two MN9 neurons.

**Search (D-171).** Evaluate `E` on the scan grid
`{0.10, 0.15, 0.20, 0.25, 0.275, 0.30, 0.35, 0.40}` mV; let `k` be the index of
the smallest value (ties to the lower index). The bracket is
`[W_{k−1}, W_{k+1}]`, clamped at the grid ends. Golden-section search then
keeps two interior points `c = b − φ(b − a)` and `d = a + φ(b − a)`,
`φ = (√5 − 1)/2`, discards the worse end, and stops when `b − a < 0.005` mV.
Every evaluated point is a full candidate in the log; the chosen `W_syn` is the
evaluated point with the smallest `E` (ties to the smaller `W_syn`), not an
interpolation. Candidates are keyed at 0.0001 mV.

**Weights (SR-MOD-05, FR-PRP-06).** `weight = signed_count × W_syn` is computed
in binary64 on x86 by `emit.build_network` and serialised as bit patterns; the
engine never sees `W_syn` itself except as header provenance.

## 5. Design decisions

Owner decisions: D-162 (scope), D-163 (push policy), D-164 (re-run rather than
the Edmond archive), D-165 (rate split with 60 Hz added), D-166 (floors),
D-167 (magic and prefix), D-168 (plan), D-169 (3 seeds), D-170 (mean of both
MN9), D-171 (scan then golden-section).

Mine within them:

- **Seeding the Shiu trials.** Shiu's `run_exp` does not seed; his published
  numbers are one draw. Seeding costs nothing physical and makes the reference
  a fixed artifact with a digest. Recorded in the manifest.
- **Re-using `emit.build_network` instead of a calibration-only emitter.** One
  code path builds calibration and shipped networks, so a calibrated `W_syn`
  cannot be lost between the search and v1.0 emission.
- **Full-network emission per candidate rather than scaling weights at load.**
  `count × W_new` computed directly is not bit-identical to
  `(count × 0.275) ⊗ (W_new / 0.275)`; SR-MOD-05 and FR-PRP-06 want the former.
- **Not reusing D-63's runs.** Those were one seed at the uncalibrated value;
  the scan re-evaluates 0.275 mV under D-169's three seeds so every candidate
  is comparable.
- **P-10** (a divisor floor) was proposed for the zero-reference case and
  withdrawn once the reference at 20 Hz measured exactly zero; the owner chose
  exclusion (D-172).

## 6. Verification

All results below: x86-64 Windows 11 host (Intel i7-13650HX, 20 logical
cores, 15.6 GB RAM), 2026-09-12. Engine runs use the 32-bit mingw32 gcc 6.3.0
build with the NATIVE backend and D-30's SSE2 flags. The Shiu re-run uses
Python 3.13.14, brian2 2.10.1, numpy 2.5.3, pandas 3.0.5, numpy codegen target.

### 6.1 Environment probe

```
.venv/Scripts/python reference/shiu/rerun.py --probe --target numpy
PROBE 200 Hz 1 trial: 35.1 s, 404 spiking neurons, 17078 spikes, MN9 {'left': 97, 'right': 71}
```

### 6.2 Reference curve (VL-61)

```
.venv/Scripts/python reference/shiu/rerun.py --n-proc 3 --target numpy   # died at 120 Hz, WinError 1450
.venv/Scripts/python reference/shiu/rerun.py --n-proc 2 --target numpy   # resumed from the five saved rates
 rate_hz  mn9_left_hz  mn9_left_sd  mn9_right_hz  mn9_right_sd  mn9_mean_hz
      10     0.000000     0.000000      0.000000      0.000000     0.000000
      20     0.000000     0.000000      0.000000      0.000000     0.000000
      40     5.266667     4.304520      4.200000      3.409790     4.733333
      60    36.566667     4.208589     27.566667      3.921593    32.066667
      80    56.400000     4.834598     41.500000      4.349329    48.950000
     120    75.033333     4.430826     53.833333      5.329686    64.433333
     160    84.800000     4.230051     58.233333      4.730633    71.516667
     200    92.900000     5.539856     62.233333      4.287061    77.566667
```

Per-rate wall time: 550 to 725 s with three workers (10 to 80 Hz), 767 to
868 s with two (120 to 200 Hz).

### 6.3 Calibration (VL-63)

```
mingw32-make runner
python prep/calibrate.py --cache            # 24775486 pairs, 121581733 synapses, 242 s
python prep/calibrate.py --scan --jobs 9    # eight candidates, about 10 min each
python prep/calibrate.py --refine --jobs 9  # scan minimum at 0.3000 mV (error 0.1397); bracket [0.2750, 0.3500]
python prep/calibrate.py --status
W_syn        20Hz     80Hz    160Hz    error
0.1000       0.00     0.00     0.00   1.0000
0.1500       0.00     1.00     6.67   0.9432
0.2000       0.00    11.17    42.67   0.5876
0.2500       3.83    24.67    48.17   0.4113
0.2750       6.33    31.17    68.33   0.2039
0.2927       6.17    33.83    78.33   0.2021
0.2953       5.50    41.33    77.67   0.1208
0.2969       3.83    46.17    77.33   0.0691
0.2979       3.83    44.67    79.67   0.1007
0.2995       3.00    46.33    83.67   0.1117
0.3000       5.17    42.33    81.83   0.1397
0.3036       5.33    40.33    78.67   0.1380
0.3104       4.17    54.67    88.67   0.1783
0.3214       4.83    44.00    97.67   0.2334
0.3500      11.00    67.67   109.67   0.4579
0.4000       4.50    79.00   135.00   0.7508
ref          0.00    48.95    71.52   (Shiu reference, D-170 mean)
chosen: W_syn = 0.2969 mV, error 0.0691
```

The first scan candidate ran with `--jobs 3` (1212 s of runs); the rest with
nine parallel engine processes (420 to 514 s per candidate, 60 to 123 s per
emission).

### 6.4 Cross-check of the emission path (VL-62)

```
./build/runnet.exe data/networks/onfnet-malecns-v1.0-full.bin 160 1000 1
READOUT k=0 n=306 spikes=102 first=28700
READOUT k=1 n=6394 spikes=7 first=43400
```

identical to the 0.275 mV candidate's `160/1` entry in the search log.

### 6.5 ACC-4 at the chosen W_syn

*(filled in below once `prep/acc4.py` completes)*

### 6.6 Regression

```
mingw32-make testfloat && mingw32-make test
run_gld [SOFT2C backend]: 14 passed, 0 failed
cmpgld: SOFT3E, NATIVE, SOFT2C agree on all 13 golden requests (33 output lines)
Ran 15 tests in 0.660s
OK
ONFLY: NR-05 + licence + col80 + C-04 + C-04/MVS lints, TT-01, TT-02, ... ACC-5 golden suite and TP-01 all passed on SOFT3E, SOFT2C and NATIVE
make test exit=0
```

### What these results do not prove

- **x86 NATIVE only.** No calibration or acceptance run has executed on MVS
  3.8j, Linux s390x, or either SOFT backend. ACC-5 (determinism) is untouched
  by this work and still holds on x86 only.
- **The reference is a re-run, not the paper's numbers** (VL-61): a newer
  brian2, seeded trials, eight rates. Shiu's own `fig_1d_rate.csv` was not
  fetched.
- **The objective is noisy at the search's resolution** (VL-63): the chosen
  0.2969 mV is the best evaluated point, its neighbours 0.004 mV away score
  0.10 to 0.12, and the last digit reflects seed variance, not physics.
- **20 Hz is excluded from the objective** (D-172) and ONFLY's MN9 fires there
  where Shiu's does not.
- **ACC-3 is unevaluated**: no SR-EXT subcircuit exists yet. ACC-1 is defined on
  the MVS subcircuit; anything reported here for it is a full-brain x86 preview.
- **VL-06, VL-12, VL-13** (female FlyWire reference versus male MaleCNS,
  labellar versus pharyngeal stimulus sets, 40.2% of synapses) apply in full.

## 7. Related docs

- `docs/ONFLY-SRS.md` — Sections 6.2 (SR-CAL), 6.4 (ACC), 4.1 (IR-NET-03),
  4.5 (IR-MSG-02), Appendix A.1 (D-162 … D-171), A.2 (P-09, P-10), Appendix B.
- `docs/implementations/2026-09-11-full-brain-run.md` — the uncalibrated run.
- `docs/implementations/2026-09-11-shiu-reconciliation.md` — TBC-01/02/05.
- `reference/shiu/MANIFEST.json`, `reference/shiu/results/MANIFEST.json`.
