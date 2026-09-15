# 2026-09-15 — D-302: calibrating for a variant stimulus set, to answer VL-65

| Field | Value |
|---|---|
| Date | 2026-09-15 |
| Author | ONFLY senior engineer |
| Phase / gate | Phase E — MVS MVP (D-296) |
| Owner decisions relied on | D-300, D-302, D-303, D-305; and D-52, D-73, D-165, D-176, D-177, D-209 as constraints |
| Requirements touched | ACC-4, ACC-3, SR-CAL-02, SR-CAL-05; risk R-03 |
| Open items closed | none |

## 1. Problem / motivation

ACC-4 fails. The full-brain MaleCNS model matches Shiu at 60, 120 and
200 Hz and passes both shape clauses, but its MN9 fires at 10 and 40 Hz
where the reference is silent or nearly so (VL-64). That is Phase E's
only failing exit criterion.

The obvious investigation has already been done. D-174 ordered it, D-176
ran three stimulus-set variants at full ACC-4 grade, and VL-65 recorded
the numbers. D-177 then decided the disposition: keep the D-52/D-73
stimulus set and W_syn 0.2969 mV, and record the mismatch as a finding.

So the cause is understood. What is **not** answered is the sentence
VL-65 ends on:

> **Not proven:** that a W_syn recalibrated for the taste-peg-only or the
> unilateral set would pass ACC-4 in full (no recalibration was run).

Every variant in D-176 was measured at the *shipped* W_syn. That is not a
fair test of the variant: W_syn was calibrated for the 14-neuron bilateral
set, so driving 10 neurons or 7 through it under-drives the network by
construction. The dorsal_tpGRN-only variant came within tolerance at four
of five validation rates anyway — failing only at 40 Hz — which is exactly
the shape of a result that a recalibration might close.

This matters because of **risk R-03**, which attributes the ACC-4 gap to
dataset differences between a male connectome and a model calibrated on a
female one. If no W_syn lets MaleCNS reproduce Shiu, R-03's reading is
supported and the finding is a fact about the data. If some W_syn does,
the mismatch is partly a calibration artefact and D-177 is worth
revisiting *on evidence*. Nothing in the repository could tell those
apart, because `prep/calibrate.py` had no way to calibrate for anything
but the shipped set.

## 2. What changed

| File | Change |
|---|---|
| `prep/calibrate.py` | Adds `--variant`, a module-level `VARIANT`, and `select_stim()`; variant runs get their own search log and candidate filenames. |
| `prep/acc4.py` | Adds the `RUNNET` guard `calibrate.py` already had. |
| `tests/test_varnt.py` | New. Pins the variant selection against VL-65's literal counts and pins the baseline-isolation properties. |
| `Makefile` | Runs `tests/test_varnt.py` in the `prep` target. |

## 3. Implementation approach

### 3.1 The selection rule is reused, never copied

`select_stim(stim, name)` returns `(bodies, desc)` — an int64 array of
MaleCNS body ids and acc4's description dict — or `(stim, None)` when no
variant is asked for. No side effects.

It delegates to `prep/acc4.py`'s `select_variant()` rather than
reimplementing it. The reason is specific: a calibration run and the
ACC-4 evaluation that judges it must agree on which neurons the variant
means. Two copies of that rule reading the same annotation file is
exactly how they drift apart — and the drift would be **invisible**,
because both would still produce plausible numbers. One function, one
answer.

The import is lazy, inside the function body. `acc4` imports `calibrate`
and reads `cal.CAL_DIR` at module scope, so a top-level `import acc4` in
`calibrate.py` would be a circular import resolved against a
half-initialised module. Called from `main()`, both modules are complete.

### 3.2 The baseline must be unwritable from a variant run

This is the part that needed care, and the danger is not that the
calibration is wrong.

`evaluate()` returns a cached candidate rather than measuring it when the
W_syn label is already in the log. So a variant entry filed in the
baseline log under the same label would be **served in place of the real
one, indefinitely, with nothing to show it had happened**. D-209 already
hit that failure from a different direction — a re-run that read the old
log ran nothing — which is why `--log` exists.

Two separations, not one:

- **The log.** With `--variant X` and no explicit `--log`, the log
  becomes `search-log-X.json`. The shipped `search-log.json` is never
  opened.
- **The candidate filename.** `net-X-<w>.bin` rather than `net-<w>.bin`.
  This is not redundant with the log: `evaluate()` *deletes* the network
  after its runs unless `--keep`, so two runs racing on one host could
  otherwise read each other's bytes.

### 3.3 Nothing that ships can move

`prep/emit.py` reads the D-52 mapping directly and never consults
`VARIANT`. Every emitted network, every golden fingerprint and the
calibrated 0.2969 mV are untouched by any run that sets it. A variant run
also prints that fact, so the operator sees it:

    variant tpgrn: 10 stimulus neurons ['dorsal_tpGRN'] sides ['L', 'R']
      investigation only (D-302): no emitted network, no golden
      fingerprint and no shipped W_syn is affected by this run

### 3.4 The `acc4.py` guard

Unrelated to the variant work but found by it. `calibrate.py`'s `main()`
checks `RUNNET` exists and says `build the runner first: mingw32-make
runner`. `acc4.py` had no such check, so on a fresh worktree a missing
`build/runnet.exe` surfaced 150 lines later inside `run_many()`'s `Popen`
as a bare `FileNotFoundError: [WinError 2] The system cannot find the
file specified`, naming neither the file nor the fix — and only *after*
`load_cache()` had spent minutes building the 594 MB signed cache. The
same guard, in the same place, before the cache work.

## 4. Mathematical / numerical details

The variant switch introduces **no new arithmetic**. It changes which
body ids are marked as stimulus neurons in the emitted network; the
kernel, the propagator coefficients, the objective and the scoring are
untouched.

For the reader auditing what a variant calibration will mean: the
objective is unchanged from SR-CAL-03. W_syn is searched over the D-171
scan points and refined by golden-section search to the D-171 resolution
of 0.005 mV, scoring each candidate by its error against the Shiu
reference at the **calibration** rates {20, 80, 160} Hz (D-165). ACC-4 is
then evaluated separately at the **validation** rates {10, 40, 60, 120,
200} Hz (D-165), 30 seeds each (D-135), 1000 ms (D-73), with tolerance
`max(25% of reference, 2 Hz)` (D-166). Calibrating on one rate set and
judging on a disjoint one is what stops the answer from being fitted to
its own test.

One property of the search is worth restating because it bounds how much
a recalibration can be trusted: **the model is sensitive to W_syn far
below the fourth decimal.** VL-79 measured, on the full brain at 80 Hz
seed 1, that W_syn 0.29685 / 0.29690 / 0.29695 give MN9 readouts
[62, 2] / [80, 4] / [61, 1] — a 25% swing in the readout for a 0.017%
change in W_syn, while the whole-network total moves about 2%. So a
variant W_syn that lands ACC-4 inside tolerance should be read as "a
W_syn exists that does this", not as a precisely determined constant.

## 5. Design decisions

| Choice | Made by | Note |
|---|---|---|
| Aim D-300's investigation at VL-65's open question rather than re-running D-176's | **Owner, D-302** | Asked after the engineer surfaced that D-174/D-176/D-177 had already settled the stimulus-set hypothesis |
| Nothing shipped changes | **Owner, D-302** | The stimulus set stays as D-177 left it; this is measurement, not a protocol change |
| ACC-4 re-run scheduled after `make test`, at `--jobs 14` | **Owner, D-303** | |
| ONFPRUN started under contention | **Owner, D-304** | |
| Reuse `select_variant` instead of copying it | Architect | Silent drift between "calibrated for" and "evaluated on" is the failure mode |
| Separate log **and** separate candidate filename | Architect | The log alone is insufficient — `evaluate()` deletes the network, so names can collide |
| Add the `RUNNET` guard to `acc4.py` | Architect | A tool defect found in passing; not an SRS matter |

## 6. Verification

### 6.1 The selection reproduces VL-65's populations

Platform x86-64 Windows, CPython 3.13, no engine involved:

    python tests/test_varnt.py

    Ran 11 tests in 1.103s
    OK

The counts are asserted against literals written into the test, not
derived from the selection code:

| Variant | Neurons | Types | Sides |
|---|---|---|---|
| baseline | 14 | PhG9 + dorsal_tpGRN | L, R |
| `right` | 7 | PhG9, dorsal_tpGRN | R |
| `phg9` | 4 | PhG9 | L, R |
| `tpgrn` | 10 | dorsal_tpGRN | L, R |

These are the same figures VL-65 records for D-176's runs.

### 6.2 Baseline isolation

Asserted by `BaselineIsolation` in the same run: the default log still
ends `data/calibration/search-log.json`; every variant log name differs
from it; `net-tpgrn-0.2969.bin` differs from `net-0.2969.bin`.

### 6.3 D-289 and D-292 verified complete (D-305)

Neither needed work. `prep/extract.py`'s `acc3_file()` carries D-289's
comment and calls `acc3_excluded()`, the same function `acc3_eval()`
uses, so one criterion has one implementation. For D-292, a scan of every
table row in the SRS by **GFM's real escaping rule** — only a
backslash-escaped pipe is literal; a pipe inside a code span is *not*
protected, which is the whole reason D-292 existed — reports:

    rows a renderer would mis-split: 0

A first version of that scan honoured code spans and wrongly reported two
survivors. The verdict rests on the corrected one.

### 6.4 ACC-4 re-run and the variant calibration

*(Pending — see §6.5.)*

### 6.5 What this does **not** prove

To be completed with the runs.

## 7. Related docs

- SRS Section 6.2 (SR-CAL), 6.4 (ACC-3, ACC-4), Section 10 (R-03),
  Appendix A.1 (D-176, D-177, D-209, D-300, D-302…D-305), Appendix D
  (VL-63, VL-64, VL-65, VL-79)
- `docs/implementations/2026-09-12-phase-c-calibration.md`
- `docs/implementations/2026-09-15-d291-jcc-compiler-identification.md`
