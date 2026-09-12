# 2026-09-12 — Phase C: TBD-07..10 closed, the Shiu reference re-run, W_syn calibration

| Field | Value |
|---|---|
| Date | 2026-09-12 |
| Author | ONFLY engineering session (third session of the day) |
| Phase / gate | Phase C — Science (x86); scope set by D-162 |
| Owner decisions relied on | D-162 … D-171 |
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

**Objective (SR-CAL-03).** With calibration rates `R = {20, 80, 160}` Hz, ONFLY
rate `o(r)` and Shiu reference `t(r)`:

    E(W_syn) = (1/|R|) · Σ_{r∈R} |o(r) − t(r)| / max(t(r), 2 Hz)

The 2 Hz divisor floor is ACC-4's D-166 floor and is proposal P-10; the log
records the rates at which it was applied, if any.

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
- **P-10** for the zero-reference divisor, flagged rather than decided.

## 6. Verification

*(Filled from this session's output; see the GOAL REPORT in the transcript for
the same excerpts.)*

### 6.1 Environment probe

```
.venv/Scripts/python reference/shiu/rerun.py --probe --target numpy
```

### 6.2 Reference curve

```
.venv/Scripts/python reference/shiu/rerun.py --n-proc 3 --target numpy
```

### 6.3 Calibration

```
mingw32-make runner
python prep/calibrate.py --cache
python prep/calibrate.py --scan
python prep/calibrate.py --refine
python prep/calibrate.py --status
```

### 6.4 Regression

```
mingw32-make test
```

### What these results do not prove

Stated per claim in Appendix D (VL-61 onward) and in the GOAL REPORT.

## 7. Related docs

- `docs/ONFLY-SRS.md` — Sections 6.2 (SR-CAL), 6.4 (ACC), 4.1 (IR-NET-03),
  4.5 (IR-MSG-02), Appendix A.1 (D-162 … D-171), A.2 (P-09, P-10), Appendix B.
- `docs/implementations/2026-09-11-full-brain-run.md` — the uncalibrated run.
- `docs/implementations/2026-09-11-shiu-reconciliation.md` — TBC-01/02/05.
- `reference/shiu/MANIFEST.json`, `reference/shiu/results/MANIFEST.json`.
