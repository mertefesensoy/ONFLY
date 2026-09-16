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

### 6.4 ACC-4 re-run, and what the investigation actually cost

Platform x86-64 Windows 11, mingw32 gcc, **NATIVE** backend throughout.

    python prep/acc4.py --jobs 14                    # 6,971 s

    rate      onfly       sd       se  reference      tol    mag
      10       3.67     4.22     0.77       0.00     2.00   FAIL
      40      14.35     8.45     1.54       4.73     2.00   FAIL
      60      28.38     7.85     1.43      32.07     8.02   PASS
     120      68.38     8.19     1.50      64.43    16.11   PASS
     200      88.80     5.07     0.93      77.57    19.39   PASS
    ACC-4 shape PASS ...; magnitude FAIL; ACC-4 FAIL

This reproduces VL-64's 2026-09-12 measurement **bit-for-bit**: a `git
diff` of `data/calibration/acc4.json` against the committed record shows
**one changed field, `elapsed_s`**. That is a determinism result as well
as a finding, and it re-confirms D-285's cast neutral on this platform.

The full D-302 programme was never run, and did not need to be. D-306
redirected it to the question the answer actually turns on, and D-309
then repeated that at ACC-4's own seed count:

    python prep/wsens.py --variant tpgrn \
        --w-syn 0.26,0.28,0.2969,0.32 --rates 40,60,120 \
        --seeds 30 --jobs 16            # 360 runs, 11,047 s

       W_syn          40 Hz         60 Hz        120 Hz
      0.2600     5.60+-0.50   10.28+-0.77   28.80+-0.62
      0.2800     6.97+-0.63   17.53+-0.86   38.42+-0.70
      0.2969     7.78+-0.78   24.55+-1.24   49.10+-1.00
      0.3200    11.82+-1.44   34.37+-1.16   63.02+-1.22

Every rate is monotonic in W_syn, so each ACC-4 band becomes a one-sided
constraint on it:

       40 Hz is ABOVE its band at 0.2969 (7.78 > 6.73): W_syn <= 0.2766
       60 Hz is INSIDE its band  (24.55 in [24.05, 40.08]): W_syn >= 0.2957
      120 Hz is INSIDE its band  (49.10 in [48.32, 80.54]): W_syn >= 0.2957

      feasible W_syn window: 0.2957 .. 0.2766
      EMPTY -- disjoint by 0.0191 mV (6.9% of W_syn).

**No W_syn satisfies ACC-4 for this variant** (VL-103). The failure is
not a mis-set gain: W_syn is a single scalar, and the variant's
dose-response curve has the wrong *shape* against Shiu's — too much
response at 40 Hz for the amount it delivers at 60 and 120 Hz. A scalar
cannot change a shape. This is the evidence risk R-03 asserts and which
D-177 had to decide without.

**A correction, and the reason D-307 was right.** A first pass at four
seeds (VL-100) reported the 40 Hz column as non-monotonic — 3.88, 8.50,
7.00, 8.75 — and read that as 40 Hz being insensitive to W_syn. At thirty
seeds it is 5.60, 6.97, 7.78, 11.82 and cleanly monotonic. **The verdict
was right and the mechanism was wrong**, and the owner's decision under
D-307 not to settle ACC-4's disposition on the weaker evidence is what
caught it. Cross-check: the 30-seed 0.2969 row reproduces VL-65's
independently measured values (7.78 / 24.55 / 49.10) exactly.

### 6.5 What this does **not** prove

- **Four W_syn points with linear interpolation between them, not a
  search.** The crossings 0.2766 and 0.2957 locate the window; they do
  not bound it to four decimal places, and VL-79 measured this model
  swinging sharply below the fourth decimal. The disjointness, at 6.9%,
  is far larger than that uncertainty — which is why the conclusion holds
  even though the crossings are approximate.
- **No recalibrated W_syn was produced.** D-302's `--variant` switch
  makes a variant calibration possible; this investigation deliberately
  did not run one, because the sensitivity measurement answered the
  question at about a tenth of the cost.
- **Only the `tpgrn` variant was probed.** VL-65's other candidate, the
  unilateral `right` set, was not, and its half of that sentence is still
  open. It fails at 60, 120 and 200 Hz by four- to sixfold at the shipped
  W_syn, so it is unlikely — but unlikely is not measured.
- **x86-64 NATIVE only.** Nothing here was run on MVS, s390x or either
  soft backend, and nothing here bears on them.
- **Three rates, not five.** The probe ran 40, 60 and 120 Hz, the three
  that bound the window. 10 and 200 Hz were not measured across W_syn.
- **Nothing shipped was touched.** The stimulus set is still D-52's
  fourteen neurons on both hemispheres and W_syn is still 0.2969 mV in
  every emitted network; the probe writes only
  `data/calibration/wsens-tpgrn-s4.json` and `-s30.json`.

## 7. Related docs

- SRS Section 6.2 (SR-CAL), 6.4 (ACC-3, ACC-4), Section 10 (R-03),
  Appendix A.1 (D-176, D-177, D-209, D-300, D-302…D-305), Appendix D
  (VL-63, VL-64, VL-65, VL-79)
- `docs/implementations/2026-09-12-phase-c-calibration.md`
- `docs/implementations/2026-09-15-d291-jcc-compiler-identification.md`
