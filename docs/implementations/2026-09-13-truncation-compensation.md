# 2026-09-13 — Weight-compensated truncation, and why no truncation works

| Field | Value |
|---|---|
| Date | 2026-09-13 |
| Author | ONFLY senior engineer |
| Phase / gate | Phase C (Science, x86) — the SR-EXT-03 escalation D-183 deferred |
| Owner decisions relied on | D-184, D-185, D-186, D-187, D-188, D-189 (and D-135, D-165, D-166, D-170, D-173, D-175 for the protocol) |
| Requirements touched | SR-EXT-01, SR-EXT-02, SR-EXT-03, ACC-3, NFR-MEM-01, IR-NET-01 |
| Open items closed | none — SR-EXT-03's escalation remains the owner's to close |

## 1. Problem / motivation

SR-EXT-03 says N shall be the smallest value in {250, 500, 1000, 2000, 4000}
satisfying ACC-3, NFR-MEM-01 and NFR-PERF-01, **and that if none does, the
conflict shall be escalated to the owner**. That escalation happened on
2026-09-12: VL-66 measured that no N under SR-EXT-01's activity rule meets
ACC-3, and VL-67, VL-68 and VL-69 then refuted a one-hop partner patch, a
pathway fixture, the whole two-hop neighbourhood and an inhibitory closure.
D-183 closed that session by recording the finding and deferring three
decisions — SR-EXT-01's rule, ACC-3's role as an MVP completion criterion,
and which network goes to MVS — to a dedicated session.

The gap this work fills is that the evidence was incomplete in one specific
way. VL-69 named the untried mechanism: "a rule that trims weights rather
than neurons (not attempted)". Every construction so far removed neurons and
kept the surviving weights untouched, which SR-EXT-02 requires. Nobody had
asked whether the truncation could be made to work by *restoring the drive
the dropped neurons used to supply*. Deciding the escalation without that
answer would mean choosing between an SRS amendment and a recorded failure
while one plausible engineering fix was still unexamined.

The risk of not doing it: Section 6.4 makes ACC-3 an MVP completion
criterion, so whatever the owner decides here changes what "the MVP is
complete" means. That decision deserves to be made on a closed evidence set.

## 2. What changed

| File | Change |
|---|---|
| `prep/emit.py` | `build_network` grows optional `gain_exc` / `gain_inh` arrays — one multiplier per kept neuron, in ascending body-id order — applied to retained edges by target neuron and edge sign. |
| `prep/extract.py` | New `--compensate` stage building constructions A, B1 and B2 and putting each through the VL-66 ACC-3 comparison into `data/calibration/acc3-compensated.json`. |
| `tests/test_gain.py` | TP-07: four unit tests pinning the gain hook's contract on a hand-built six-neuron fixture. |
| `Makefile` | TP-07 joins the `prep` target, so it runs in `make test`. |
| `docs/ONFLY-SRS.md` | D-184…D-189 in Appendix A.1; VL-70 in Appendix D; Phase C status line in Section 9.2. |

## 3. Implementation approach

### 3.1 The gain hook, and why it is the dangerous part

`emit.build_network` is the single place that turns signed synapse counts
into the f64 weight section of an ONFNET file (SR-MOD-05: weight = count ×
sign × W_syn). Everything in the repository that has a network — the golden
`path` fixture whose thirteen ACC-5 fingerprints are reference values, the
calibration candidates, the subcircuits — comes out of this function.

Adding an optional multiplier there creates exactly one serious hazard: if
the hook were ever *not* a perfect no-op when no caller supplies a gain,
every network file would change and every ACC-5 fingerprint with it, silently
and everywhere at once. The contract is therefore pinned by test rather than
by care:

* absent gain and an all-ones gain produce **byte-identical** files;
* a gain applies only to edges whose **target** is that neuron and whose
  **sign** matches, and to no other edge;
* a wrong-length array raises `ValueError` instead of being broadcast.

`tests/test_gain.py` builds its expectation from the fixture literally rather
than by calling the code under test, so a test that agreed with a broken
implementation would have to be wrong in the same way twice. Its fixture is
hand-built, so unlike the MaleCNS half of TP-01 it needs no retrieved data
and runs on a bare checkout.

No file-format change was needed: IR-NET-01 already specifies the weight
section as f64.

### 3.2 The three constructions

All three are diagnostic (D-189): their networks are written to
`data/calibration/`, never to `data/networks/`, and nothing here amends
SR-EXT-01 or SR-EXT-02.

**A — selection only, SR-EXT-02 intact.** Keeps weights untouched and changes
only which neurons are kept. Starting from stimulus ∪ readouts, spend the
smallest k of the N slots on the readouts' inhibitory presynaptic partners
(heaviest rate-weighted mass first, ties by ascending body id) such that
inhibition onto every readout is retained at least as well as excitation, and
give the remaining N − k slots to the activity ranking. This is the control
that separates "SR-EXT-01's rule is wrong" from "truncation itself needs
compensation".

**B1 — one-shot mean-field compensation, SR-EXT-02 amended.** Takes exactly
SR-EXT-01's top-N sets and scales the retained edges onto each kept neuron so
that neuron's *expected* synaptic drive matches the full brain's.

**B2 — self-consistent rate matching, SR-EXT-02 amended.** Starts from B1's
gains, measures each kept neuron's actual firing inside the subcircuit with
`runnet --all`, and damps its excitatory gain toward the rate that neuron has
in the full brain. B1 corrects expected *input*; only B2 closes the loop on
realised *output*.

**The readouts and the stimulus neurons are never updated by B2.** Tuning
MN9's own gain toward MN9's full-brain rate would be fitting the very
quantity ACC-3 measures, and would make a passing ACC-3 meaningless. Leaving
them frozen keeps ACC-3 an out-of-sample check of whether matching *interior*
rates reproduces the readout. The stimulus neurons are driven externally and
have no synaptic input to scale.

### 3.3 Contracts of the functions introduced

* `drive_model(arrays, totals) -> dict` — pure. Builds the rate-weighted
  drive tables for the whole brain. Raises `SystemExit` if the totals array
  and the connectivity disagree on neuron count.
* `retained_drive(dm, arrays, nodes) -> (E_sub, I_sub)` — pure; drive counting
  only edges with both endpoints in `nodes`.
* `meanfield_gains(dm, arrays, nodes) -> (ge, gi)` — pure; gains clipped to
  [1/20, 20]. A neuron with no retained excitatory (or inhibitory) input keeps
  a gain of **1**: there is no edge left to scale, and inventing one would be
  a different construction.
* `balanced_nodes(...) -> (nodes, k, fractions)` — pure; deterministic,
  because the candidate order is by descending mass with ties broken by
  ascending body id.
* `rate_match(...) -> (ge, gi, history)` — side effects: emits one network per
  iteration under `data/calibration/` and runs the engine. Invariant: entries
  of `ge` for stimulus and readout neurons are never modified.
* `acc3_eval(cases, full, jobs) -> cases` — side effect: runs the engine.
  Mutates each case in place with `per_rate`, `acc3_pass`, `need_bytes`,
  `nfr_mem_01_pass`.

## 4. Mathematical / numerical details

### 4.1 Rate-weighted drive

For a neuron *j*, let *w<sub>ij</sub>* be the number of synapses from *i* to
*j* (unsigned) and *r<sub>i</sub>* be neuron *i*'s total spike count over the
240-run SR-EXT-01 ranking — all eight TBD-07 rates, seeds 1…30. Define

* excitatory drive  **E<sub>j</sub> = Σ<sub>i excitatory→j</sub> w<sub>ij</sub> · r<sub>i</sub>**
* inhibitory drive  **I<sub>j</sub> = Σ<sub>i inhibitory→j</sub> w<sub>ij</sub> · r<sub>i</sub>**

This is the expected total synaptic input *j* receives per unit time, under
the approximation that each presynaptic neuron fires at its full-brain
average rate. Only ratios of *r* ever enter a gain, so no conversion to Hz is
needed. One number per neuron rather than one per rate is deliberate (D-188):
a per-rate gain would mean a different network file per rate, and MVS ships
one file.

Restricting the sums to edges inside a kept set *S* gives
E<sub>j</sub><sup>S</sup> and I<sub>j</sub><sup>S</sup>.

### 4.2 B1's gains

α<sub>j</sub> = E<sub>j</sub> / E<sub>j</sub><sup>S</sup> and
β<sub>j</sub> = I<sub>j</sub> / I<sub>j</sub><sup>S</sup>, each clipped to
[1/20, 20], and 1 where the denominator is zero. Multiplying every retained
excitatory weight into *j* by α<sub>j</sub> and every retained inhibitory one
by β<sub>j</sub> makes *j*'s expected drive equal the full brain's **exactly**
in mean field, at the single operating point of §4.1. It preserves the
excitation-to-inhibition ratio at *j* as well as the magnitude, because the
two are corrected independently.

### 4.3 B2's update

Let *f<sub>j</sub>* be neuron *j*'s mean spike count per (rate, seed) in the
full brain — totals divided by 8 × 30 — and *s<sub>j</sub>* the same quantity
measured in the subcircuit over 8 rates × 3 seeds. With ε = ½ spike,

**ρ<sub>j</sub> = clip( (f<sub>j</sub> + ε) / (s<sub>j</sub> + ε), 0.1, 10 )**,
then **α<sub>j</sub> ← clip( α<sub>j</sub> · ρ<sub>j</sub><sup>0.5</sup>, 1/20, 20 )**

for interior *j* only; α is left alone for stimulus and readout neurons. The
exponent 0.5 is the damping: it moves the gain halfway (in log space) toward
the value that would fix the rate if the response were proportional. ε keeps
a zero count from producing a division by zero, and the clip at 10 keeps one
iteration from jumping more than a decade.

**Why this cannot converge here, from the measurement.** §6 records that all
501 and all 1,001 kept neurons fire in the full brain, but only 153 and 456 of
them fire inside their subcircuit. For a neuron with *f<sub>j</sub>* > 0 and
*s<sub>j</sub>* = 0 the relative error |s − f| / max(f, ε) is exactly 1 — which
is why the median interior error sits at exactly 1.000 through every
iteration — and ρ<sub>j</sub> = (f + ½)/½, which clips to 10 every round. After
four rounds α<sub>j</sub> has run to the 20× cap. The gain is being asked to
make a neuron fire that has **no retained edge carrying any input at all**,
which no multiplier can do; meanwhile the neurons that *can* fire are
amplified twentyfold. The measured consequence is a rate curve nearly
independent of the stimulus: B2-n1000 fires 51.50 Hz at a 10 Hz stimulus and
45.23 Hz at 200 Hz.

### 4.4 The ACC-3 statistic

Unchanged from VL-66 and D-170: for each validation rate, the mean over both
MN9 neurons of their spike counts, converted to Hz by × 1000 / 1000 ms, then
averaged over seeds 1…30; compared against `acc4.json`'s full-brain mean at
the same rate with tolerance max(10% × full, 1 Hz) (ACC-3, D-166).

## 5. Design decisions

Owner's, all through AskUserQuestion and recorded in Appendix A.1 before any
code depended on them:

* **D-186** — answer the escalation with one more construction, weight
  compensation, before any SRS text changes. The alternatives were to decide
  immediately by making ACC-3 a reported measurement, or by widening its
  tolerance. The engineer measured and reported, before the choice, that
  widening would need **at least 126%** relative tolerance for the best
  construction ever measured, 153% for `hop2`, 395% for top-500 + partners
  and 560% for the `path` fixture.
* **D-187** — build **both** a selection-only and a weight-rescaling
  construction and compare them, rather than only the compensated one the
  engineer recommended. This is what makes A's result interpretable.
* **D-188** — the plan as presented. The gain cap (20×), damping (0.5),
  iteration count (4) and B2's restriction to N ∈ {500, 1000} are the
  engineer's choices for a diagnostic and bind nothing, on the D-182
  precedent.
* **D-189** — a construction that passes ACC-3 does **not** amend the SRS in
  the same step.

Architect's (engineer's) choices, stated so they are not mistaken for the
owner's:

* Freezing readouts and stimulus neurons in B2 (§3.2). Not a free parameter:
  the alternative makes ACC-3 self-fulfilling.
* Gain 1 rather than an invented edge where a neuron has lost all input of one
  sign.
* The single-operating-point rate proxy of §4.1, forced by D-188's
  one-file-for-MVS constraint.

Alternatives considered and rejected before proposing the plan: running the
full brain on MVS, which is arithmetically impossible — 299,515,256 bytes
decoded against TBD-14's 8M region, and at Gate G3's measured 36.6–40.8 µs
per neuron-step, 184,099 neurons × 10,000 steps is ≈ 19 hours per request
against NFR-PERF-01's 10 minutes.

## 6. Verification

All results below were produced **on this host in this session**: x86-64
Windows 11, mingw32 gcc 6.3.0, **NATIVE** float backend (D-30 flags), Python
3.13.14.

**The gain hook (TP-07).**

```
python tests/test_gain.py
```

Pass looks like `Ran 4 tests ... OK`. It is also reached by `mingw32-make
test` through the `prep` target.

**The three constructions.**

```
mingw32-make runner
python prep/extract.py --compensate --jobs 14
```

Needs `data/networks/onfnet-malecns-v1.0-full.bin` (SHA-256 `ea605b86…`),
`data/calibration/activity-ranking.json`, `activity-totals.npy`, `signed.npz`
and `acc4.json`. 8 networks emitted, 192 rate-matching runs and 1,200 ACC-3
runs in 609 s. Result — mean MN9 rate over seeds 1…30, full brain
3.67 / 14.35 / 28.38 / 68.38 / 88.80 Hz:

| case | neurons | 10 Hz | 40 Hz | 60 Hz | 120 Hz | 200 Hz | ACC-3 | worst-rate tolerance needed |
|---|---|---|---|---|---|---|---|---|
| A-n250 | 257 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | FAIL | 100% |
| A-n500 | 500 | 0.00 | 5.58 | 10.97 | 16.78 | 20.63 | FAIL | 100% |
| A-n1000 | 988 | 0.43 | 32.48 | 50.88 | 81.88 | 101.53 | FAIL | 126% |
| B1-n250 | 256 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | FAIL | 100% |
| B1-n500 | 501 | 1.40 | 17.97 | 23.35 | 34.65 | 47.15 | FAIL | 62% |
| B1-n1000 | 1001 | 0.62 | 34.60 | 54.23 | 88.77 | 113.97 | FAIL | 141% |
| B2-n500 | 501 | 13.05 | 17.12 | 19.38 | 28.67 | 51.73 | FAIL | 256% |
| B2-n1000 | 1001 | 51.50 | 40.42 | 37.42 | 40.00 | 45.23 | FAIL | 1305% |

All forty comparisons fail. Decoded need 88–562 KB, every one inside TBD-14's
8M, so NFR-MEM-01 passes throughout and is not the constraint.

**The mechanism.** One `runnet --all` per subcircuit at 80 Hz, seed 1,
against the full-brain totals:

```
N=500   kept=501   fire in full brain: 501   fire in subcircuit: 153
N=1000  kept=1001  fire in full brain: 1001  fire in subcircuit: 456
```

Every kept neuron fires in the full brain — SR-EXT-01 selects them for
exactly that — and 70% (N=500) and 54% (N=1000) of them are silent inside
their own subcircuit.

**What these results do NOT prove** (SRS Appendix D; recorded as VL-70):

* Nothing here ran on MVS 3.8j, Linux s390x or z/OS, and nothing ran on the
  SOFT3E or SOFT2C backends. Every number above is x86-64 NATIVE only.
* ACC-1 was not evaluated on any of these eight constructions.
* A construction that changes the **model** rather than the network — a
  compensating bias current, a per-neuron threshold or leak adjustment — was
  not attempted. Each would deviate from Appendix C, which is normative,
  rather than from SR-EXT-02.
* N above 4,456 was not attempted; Gate G3 and TBD-14 exclude it regardless.
* B2 was run with one damping value, one cap and four iterations. It is not
  proven that no schedule converges — only that this one diverges, and §4.3
  gives the structural reason it must.

## 7. Related docs

* `docs/ONFLY-SRS.md` §6.3 (SR-EXT), §6.4 (ACC-3), §9.2 Phase C, Appendix A.1
  D-184…D-189, Appendix D VL-63…VL-70.
* `docs/implementations/2026-09-12-phase-c-calibration.md` — W_syn 0.2969 mV
  and the ACC-4 finding this builds on.
* `data/calibration/acc3-compensated.json` — the full result, per rate and
  per seed-mean, with every gain summary and B2's iteration history.
