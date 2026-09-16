# 2026-09-16 — Phase E record closure, and TBD-06 measured

| Field | Value |
|---|---|
| Date | 2026-09-16 |
| Author | Senior engineer |
| Phase / gate | Phase E — MVS MVP (record closure); TBD-06 (seeds per rate) |
| Owner decisions relied on | D-135, D-165, D-166, D-202, D-246, D-341, and D-347…D-352 taken this session |
| Requirements touched | Section 6.4 preamble, ACC-1, ACC-3, ACC-4, Section 9.2 Phase E row, Appendix B TBD-06 |
| Open items closed | **TBD-06** on its last item (seeds per rate); the Phase E §9.2 record gap |

## 1. Problem / motivation

Two gaps, neither of them a missing capability.

**The Phase E record gap.** Section 6.4 says *"The MVP is complete when ACC-1
through ACC-7 all pass."* All seven carry PASS records — VL-105 (ACC-1, ACC-2),
VL-98 (ACC-3), VL-112 (ACC-4), VL-91/93/95/96/99/101 (ACC-5 rows 1–7), VL-102 and
VL-106 (ACC-6), VL-104 (ACC-7) — while Section 9.2's Phase E row carried no
completion marker. The document lagged its own evidence. Phase B had the identical
gap and D-246 closed it retroactively on 2026-09-14; the owner authorised the same
operation here as D-348.

The failure this prevents is not cosmetic. Phase G's row lists **E** as its
dependency. A dependency that the contract does not record as satisfied is one that
a later reader — or a later session — has to re-derive from seven scattered
verification records, and re-derivation is where a caveat gets dropped.

**TBD-06.** The seed count was the last open item. D-135 did not leave it open for
lack of an opinion; it left it open for lack of a measurement:

> Seeds per rate stays at 30, and the question is deliberately deferred **until the
> first full acceptance run has been executed**. TBD-06 therefore remains open on
> this item alone.

That run has happened. The condition D-135 set is satisfied, so the item became
answerable on evidence rather than judgement.

### Why it was not simply a compute-time question

D-135 framed the alternatives as cost: 30 seeds or 15, halving a suite. Reading
Section 6.4 as it now stands shows the seed count is also **a bar height**, and it
moves the bar in more than one direction:

- **ACC-4's shape clause** — the criterion itself since D-341 — allows a decrease
  between successive rates of at most **one standard error**, and SE = sd/√n. Taken
  alone, more seeds is a stricter test.
- **ACC-1** requires a spike in at least 90% of seeds. At n = 30 that is 27 of 30;
  at n = 10 a single unlucky seed carries ten times the weight.
- **ACC-3's exclusion rule (D-202)** compares sd against the mean. A sample sd
  estimates something that does not shrink with n, so the excluded set should not
  systematically move — a prediction worth checking rather than assuming.

A count chosen without knowing which clauses move would have been a guess about how
high the bar is, not only about how long the suite takes.

### Two gaps in the stored evidence

Two things stood between the recorded acceptance run and an answer, and both are
the same omission:

1. **`prep/acc4.py:323` computes the per-seed values and keeps only the summary.**
   The `means` list is reduced to mean/sd/se and discarded.
   `prep/extract.py:366` does the same for the subcircuit.
2. **The subcircuit's across-seed sd was never recorded at all.**
   `data/calibration/acc3-srext.json` stores `sub_mean_hz` and no dispersion — so
   half of the quantity whose stability was in question was unmeasured.

The subcircuit half was cheap to fix: 501 neurons, and the recorded 5 rates × 30
seeds took 80 s. The full-brain half was not: 184,099 neurons and 6971 s for 151
runs. D-351 settled that asymmetry by declining the re-run and accepting a bound.

## 2. What changed

| File | Change |
|---|---|
| `docs/ONFLY-SRS.md` | §9.2 Phase E row marked COMPLETE with its evidence and its carried-forward caveats (D-348); Appendix A.1 gains D-344…D-352; A.2 gains P-17; Appendix B's TBD-06 row and §6.4's seed-count parenthetical updated |
| `prep/seeds.py` | **New.** Measures the per-seed MN9 rate the other tools discard, then reports how each seed-dependent clause responds to the seed count |
| `tests/test_seeds.py` | **New.** Pins the tool's clause implementations against the recorded acceptance artefacts, so a second implementation of ACC-1 and ACC-3 cannot drift from the first |
| `data/calibration/seeds.json` | **New.** The measured per-seed rates and the analysis derived from them |
| `docs/plan/2026-09-16-phase-e-cleanup-tbd06.md` | The approved plan (D-349) |
| `docs/plan/2026-09-16-phase-g-live-view.md` | Recovered from an uncommitted sibling worktree (D-350); Phase G content, out of scope this session |

## 3. Implementation approach

### The measurement

`prep/seeds.py` re-runs the shipped `srext` subcircuit — the network every Phase E
criterion was evaluated on — at the five D-165 validation rates, keeping the
per-seed MN9 rate. The rate is the D-170 quantity: spikes summed over the two
readout neurons, divided by the simulated second, averaged over readouts.

**Contract of `sweep(path, seeds, jobs)`:** takes a network path, a seed list and a
pool width; returns `{rate: [Hz per seed]}` and the elapsed wall time. Side effects
are the engine runs themselves, through `extract.run_pool`, which writes each run's
stdout to a file rather than a pipe (a `--all` run would otherwise deadlock — the
2026-09-12 measurement recorded in that function's docstring). It relies on the
engine being deterministic in `(network, rate, seed)`, which is the invariant the
next paragraph exploits.

**The reproduction check is the load-bearing safety property.** Because the engine
is deterministic given `(network, rate, seed)`, seeds 1…30 of this sweep are *the
same thirty runs* that produced VL-105. `reproduction_check()` requires them to
agree to within 1e-12 on the mean and exactly on the count of seeds that spiked, at
every rate, and stops the tool otherwise. Without it, a tool that silently analysed
a changed engine would produce a seed-count recommendation for a model nobody had.

### Separating what is measured from what is modelled

The report is split because the two halves have different epistemic status, and
collapsing them would have produced one confident-looking table resting half on
measurement and half on an assumption.

- **Measured, non-parametric.** ACC-1 is defined on the MVS subcircuit, so its
  clause is bootstrapped from real seeds. For each candidate n, draw n seeds with
  replacement from the S measured seeds, B = 10,000 times, evaluate the clause, and
  report the fraction whose verdict differs from the verdict on the full sample.
  No distribution is assumed — which matters at 10 Hz, where the distribution is
  strongly skewed.
- **Bounded.** ACC-3 compares the subcircuit against the full brain. Its
  re-evaluation form (reference held at its recorded value) is measured; its
  re-measurement form (reference re-run too) is bracketed. See §4.
- **Modelled.** ACC-4 is evaluated on the full brain, so its clauses are treated
  analytically from the recorded means and sds, and every ACC-4 figure is labelled
  a normal-theory estimate.

### Why a second implementation of the criteria needed a test

`seeds.py` must evaluate ACC-1 and ACC-3 thousands of times over resampled arrays,
which the existing list-shaped implementations in `prep/extract.py` cannot do. That
creates a second implementation of criteria that already had one — exactly the
condition that produced D-289, where `--acc3-file` predated D-202's amendment and
printed FAIL while every rate ACC-3 actually tests passed.

Two defences. Where sharing is possible, `seeds.py` shares: D-202's exclusion is
asked of `extract.acc3_excluded()`, and `ACC1_SEED_FRACTION`, `REL_TOL` and
`ABS_FLOOR` are imported rather than retyped. Where it is not, `tests/test_seeds.py`
pins the array form against the recorded artefacts the list form produced — ACC-1
against `acc1-candidate.json` (VL-105) and ACC-3, per rate and overall including the
exclusion, against `acc3-srext.json` (VL-98). A negative control is included:
silencing a fifth of the seeds at 40 Hz must make ACC-1 fail, so the test cannot
pass by evaluating nothing.

## 4. Mathematical / numerical details

### The bootstrap

For candidate n, resample n of the S measured per-seed values with replacement,
B = 10,000 times, evaluate the clause on each replicate, and report the fraction of
replicates disagreeing with the full-sample verdict. This estimates the probability
that the criterion's verdict would change if the campaign were re-seeded. The
resampling generator is seeded from a constant recorded in the output, so the table
is reproducible; that seed governs the analysis only and has nothing to do with
NR-13's xorshift32 in the engine.

### ACC-3's two stabilities

ACC-3's statistic is d = mean_sub − mean_full, against a tolerance of
max(0.10 · mean_full, 1 Hz). Two different questions hide inside "is it stable":

**(a) Re-evaluation.** `prep/extract.py --acc3-file` reads the reference from the
recorded `acc4.json` and re-runs only the subcircuit. The reference is then a
constant and the only sampling noise is the subcircuit's, which this work measures
directly. This is what re-running the criterion does today.

**(b) Re-measurement.** If the full brain were re-run too, the reference moves as
well. Then

    var(d) = s_sub² + s_full² − 2ρ · s_sub · s_full

with ρ the across-seed correlation between the two halves — a quantity nobody
measured, because the full brain's per-seed values were never kept (D-351). Three
points on that curve:

| ρ | sd(d) | |
|---|---|---|
| +1 | \|s_full − s_sub\| | the minimum |
| 0 | √(s_sub² + s_full²) | D-351's bound |
| −1 | s_full + s_sub | the maximum |

The tool reports the first two. That is a bracket over ρ ∈ [0, 1], **not** over
every arithmetically possible ρ, and the restriction is the content of D-351: the
same seed drives the same fourteen stimulus neurons in both networks, because
SR-EXT-01 keeps every stimulus and readout neuron inside the subcircuit, so a seed
that delivers a strong stimulus burst raises both means. A negative ρ would mean a
seed that excites the full brain quietens its own subcircuit, which the construction
makes implausible. Reported as a bracket, the conclusion does not rest on the
unmeasured number: where s_full is several times s_sub the two ends sit close
together and the verdict is the same anywhere between them.

Given sd(d), the pass probability at seed count n is

    P(|d| ≤ tol) = Φ((tol − μ_d)/SE) − Φ((−tol − μ_d)/SE),   SE = sd(d)/√n

with μ_d the measured difference. The tolerance is held at 10% of the recorded
reference rather than following the draw; its own sampling wobble is an order below
the difference's and folding it in would obscure the bracket.

### ACC-4's shape clause gets *easier* with more seeds

This is the counter-intuitive result, and the reason the clause needed analysis
rather than assertion. The clause allows drop_i = m_i − m_{i+1} to be at most
SE_i(n) = sd_i/√n. Treating the two sample means as normal, the drop's own standard
error is √(sd_i² + sd_{i+1}²)/√n, so the failure probability is 1 − Φ(z) with

    z = (SE_i(n) − drop_i) / SE(drop_i)(n)
      = (sd_i + |drop_i|·√n) / √(sd_i² + sd_{i+1}²)     when drop_i < 0

Both the bar and the noise shrink as n^(−1/2), but the **true** drop does not move
at all. On a rising curve — which the measured curve is — z therefore grows as √n
and the clause becomes easier to satisfy, not harder, even though the bar itself is
falling. `tests/test_seeds.py` asserts this direction, and asserts the rising-curve
premise it depends on rather than assuming it.

### D-202's exclusion, and what rides on it

The rule compares the reference's sd with its mean. Since sd estimates a population
quantity that does not shrink with n, the excluded set should not systematically
move with the seed count — only the reliability of the classification changes.

That matters more than it first appears, because the exclusion is **load-bearing**:
at 10 Hz the subcircuit produces about 0.02 Hz against a reference of 3.67 Hz and a
tolerance of 1.0 Hz, so if that rate were ever *tested* rather than excluded, ACC-3
would fail outright. So the honest statement is not "the exclusion is stable" but
"ACC-3's PASS rests on a classification made from a ratio near 1, and more seeds
**resolves** that classification rather than improving it" — if the population ratio
is truly above 1, more seeds makes the exclusion certain; if it is below 1, more
seeds makes ACC-3 fail with certainty. A seed count cannot choose which.

For a normal sample the mean and sample sd are independent, with m ~ N(μ, σ²/n) and
s concentrating about σ with relative standard deviation 1/√(2(n−1)), so to first
order

    log(s/m) ~ N( log(σ/μ),  1/(2(n−1)) + (σ/μ)²/n )

and P(not excluded) = P(s/m < 1) follows by plugging in the measured ratio. Normality
is a poor fit at exactly the rate this matters for — 10 Hz is skewed, which is what
makes its sd exceed its mean in the first place — so this figure indicates where the
risk lies rather than calibrating it. The structural point above does not depend on
it.

## 5. Design decisions

| Choice | Made by | Why |
|---|---|---|
| Phase E's §9.2 row marked COMPLETE with caveats inside the marker | Owner, D-348 | The evidence exists; D-246 set the precedent on Phase B. Caveats inside rather than beside so no reader can take one without the other |
| No full-brain re-run; the unpaired figure used as a bound | Owner, D-351 | Two hours against a figure that can only recommend more seeds than needed, never fewer |
| 200 seeds measured on the subcircuit | Owner, D-352 | Estimates each rate's sd to about ±5%, so the estimate is not itself the dominant uncertainty |
| Report re-evaluation and re-measurement separately | Engineer | They differ by an order of magnitude; one combined number would have been true of neither question |
| Bracket ρ rather than assume it | Engineer | The unmeasured correlation cannot change the conclusion if both ends give the same verdict; assuming a value would have hidden that |
| Pin the clause implementations with a test | Engineer | D-289's lesson: one criterion, one implementation — and where a second is unavoidable, a test that ties it to the first |
| Stop rather than analyse if seeds 1…30 do not reproduce | Engineer | A recommendation computed from a changed engine would be worse than no recommendation |

## 6. Verification

Filled in from this session's runs — see the session's goal report for the command
output excerpts.

## 7. Related docs

- `docs/ONFLY-SRS.md` §6.4 (acceptance criteria), §8.3 (determinism matrix), §9.2
  (phases), Appendix A.1 (D-135, D-202, D-246, D-341, D-347…D-352), Appendix B
  (TBD-06), Appendix D (VL-98, VL-105, VL-112)
- `docs/plan/2026-09-16-phase-e-cleanup-tbd06.md` — the approved plan
- `docs/implementations/2026-09-15-phase-e-slice-5-acceptance.md` — the acceptance
  records this closure rests on
