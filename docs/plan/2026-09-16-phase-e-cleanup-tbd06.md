# 2026-09-16 — Phase E cleanup and TBD-06: plan for owner approval

| Field | Value |
|---|---|
| Date | 2026-09-16 |
| Author | Senior engineer, for owner approval |
| Phase / gate | Phase E — MVS MVP, record closure; and TBD-06 (seeds per rate) |
| Scope chosen by | The owner, through AskUserQuestion, 2026-09-16: *"Phase E cleanup + TBD-06"*, *"first E then we talk G"*, *"clean E"* |
| Owner decisions relied on | D-73, D-135, D-165, D-166, D-170, D-202, D-246, D-340, D-341 |
| Requirements touched | Section 6.4 (ACC-1…ACC-7 preamble), ACC-1, ACC-3, ACC-4, FR-SIM-06, NFR-PERF-01, SR-EXT-03, Section 9.2 Phase E row, Appendix B TBD-06 |
| Open items this closes | **TBD-06**, on its last remaining item (seeds per rate) |
| Status | **PROPOSED. Not approved. No code written until the owner answers.** |

Phase G is explicitly out of scope for this session by the owner's answer. P-17 stays a
proposal and its open questions stay unasked.

## 1. Problem / motivation

Two things are unfinished in Phase E, and neither is a capability gap.

**(a) The record gap.** Section 6.4 says *"The MVP is complete when ACC-1 through ACC-7
all pass."* All seven carry PASS records (VL-105, VL-76, VL-112, VL-91/93/101, VL-102/106,
VL-104). Section 9.2's Phase E row carries no completion marker, so the contract does not
say what the evidence says. Phase B had the same gap and D-246 closed it retroactively on
2026-09-14; this is the same operation on the same grounds. The owner authorised it
through AskUserQuestion on 2026-09-16.

**(b) TBD-06, seeds per rate.** This is the last open item on TBD-06; duration was fixed
by D-73 and D-138. D-135 (2026-09-12) is explicit about why it stayed open:

> Seeds per rate stays at 30, and the question is deliberately deferred **until the first
> full acceptance run has been executed**. TBD-06 therefore remains open on this item alone.

That run has now happened. The condition D-135 set is satisfied, so the item is answerable
on measurement rather than judgement — which is the only reason it was left open.

### Why the answer is not obvious, and why it is not merely a cost question

D-135's alternatives framed this as compute time: 30 seeds or 15, halving a 5.2-hour suite.
Reading the criteria as they now stand shows the seed count is **also a bar height**, in two
places, and in opposite directions:

- **ACC-4's shape clause** (the criterion itself since D-341) allows a decrease between
  successive rates of at most **one standard error of the earlier point** — and
  SE = sd/√n. **More seeds is a stricter test.** Raising the seed count could fail a
  criterion that currently passes. This is recorded as interpretation P-11 and is visible
  in `prep/acc4.py:344`.
- **ACC-1** requires a spike in **at least 90% of seeds**. At n = 30 that is 27 of 30;
  at n = 10 it is 9 of 10, so a single unlucky seed carries ten times the weight.
- **ACC-3's exclusion rule (D-202)** — a rate whose reference sd is at or above its mean is
  excluded — is a property of the **distribution**, not of the sample size: sd does not
  shrink with n. So this clause should be insensitive to the seed count, and the plan
  predicts that and then checks it rather than assuming it.

A seed count chosen without knowing which clauses move would be a guess about the height of
the bar, not just about compute.

## 2. What is already measured, and what is missing

Read from `data/calibration/acc4.json` (30 seeds, 1000 ms, full MaleCNS brain, x86-64
NATIVE) — these are recorded figures, not run this session:

| Rate | mean (Hz) | sd (Hz) | se at n=30 | seeds with an MN9 spike |
|---|---|---|---|---|
| 10 | 3.667 | 4.225 | 0.771 | 29 / 30 |
| 40 | 14.350 | 8.449 | 1.543 | 30 / 30 |
| 60 | 28.383 | 7.848 | 1.433 | 30 / 30 |
| 120 | 68.383 | 8.194 | 1.496 | 30 / 30 |
| 200 | 88.800 | 5.068 | 0.925 | 30 / 30 |

Two gaps stand between this and an answer:

1. **`prep/acc4.py` computes the per-seed values and keeps only the summary.** The `means`
   list at `prep/acc4.py:323` is discarded after mean/sd/se are taken. Same in
   `prep/extract.py:366` for the subcircuit. So no bootstrap over real seeds is possible
   from the stored artefacts alone.
2. **The subcircuit's across-seed sd was never recorded at all** — `acc3-srext.json` stores
   `sub_mean_hz` and no dispersion. ACC-3 compares that mean against the full-brain mean, so
   half of the quantity whose stability we are judging is unmeasured.

The subcircuit half is cheap: 501 neurons, and the recorded run of 5 rates × 30 seeds took
**80 s** (`acc3-srext.json:elapsed_s`). The full-brain half is not: 184,099 neurons, and
`acc4.json:elapsed_s` is **6971 s** for 151 runs. That asymmetry is what Question 3 below is
about.

## 3. Plan

### Stage 0 — records before code

1. Recover the three owner decisions taken on 2026-09-16 that were left uncommitted in a
   sibling worktree — **D-344, D-345, D-346** (Phase G: x86 stream first; three-panel
   viewer; `srext` network) — into Appendix A.1, and **P-17** into A.2 with its plan file.
   These are owner answers already given; recording them is required before any later
   session writes code on them, and leaving them unrecorded would let this session's new
   decisions collide with their numbers. *Subject to Question 2 below.*
2. Record this session's answers as the next D-numbers: the scope choice, and the
   authorisation to mark Phase E complete.

### Stage 1 — close the Phase E record gap

Re-read each of the seven acceptance records **before** writing the marker, and cite in it
only what the document actually supports, including the two live caveats: ACC-4 passes on
D-341's amended bar, and ACC-5 row 7 covers 5 of the 19 golden requests. Mirror D-246's
wording for Phase B so the two retroactive markers read alike.

No code. Document change only, authorised.

### Stage 2 — measure the seed sensitivity (`prep/seeds.py`, new)

A new tool, in the style of the existing `prep/` tools and reusing `calibrate.py`'s runner
pool, that:

1. Runs the shipped `srext` network (`data/networks/onfnet-malecns-v1.0-srext.bin`, the
   network every Phase E criterion was evaluated on) at the five D-165 validation rates with
   **S seeds** and **retains the per-seed MN9 rate**, writing them to
   `data/calibration/seeds.json`. S is Question 4 below; 200 is proposed, about 9 minutes by
   the 80-second-for-150-runs figure above.
2. **Bootstraps** each seed-dependent clause at candidate n ∈ {5, 10, 15, 20, 30, 50, 100}:
   resample n seeds with replacement from the S measured values, B = 10,000 times, and
   report the fraction of resamples in which the clause's verdict differs from the verdict
   on the full sample. That fraction is the probability the criterion flips on a reseed —
   the quantity a seed count should be chosen to control.
3. Reports the three clauses separately, because they move differently:
   **ACC-1** (≥90% of seeds spike), **ACC-3** (subcircuit mean within tolerance of the
   full-brain mean), **ACC-4 shape** (no decrease beyond one SE of the earlier point).
4. States for ACC-3 which half is measured and which is cited, and does not present a paired
   figure unless Question 3 is answered in favour of re-running the full brain.

The tool changes no criterion and no existing artefact. It only measures.

### Stage 3 — the owner closes TBD-06

Present the measured table through AskUserQuestion. The owner fixes the seed count. Record
as a new D-nn, update Appendix B's TBD-06 row to CLOSED, and amend Section 6.4's
parenthetical *"(seed count TBD-06)"* to name the decision — an authorised SRS text change,
authorised by that same answer.

If the measurement shows a criterion currently passing would fail at a higher seed count,
that is reported as a finding and put to the owner; it is not quietly avoided by choosing a
lower count.

### Stage 4 — verify, document, push

`mingw32-make test` on this host, an implementation document under `docs/implementations/`,
`git diff --stat`, commit and push to `origin`.

## 4. Mathematical detail

**Standard error and the ACC-4 bar.** For a sample of n seeds with sample standard deviation
s, the standard error of the mean is s/√n. ACC-4's shape clause compares the drop between
successive rates against the earlier rate's standard error, so the allowed drop scales as
n^(−1/2): going from 30 seeds to 120 halves it. The measured curve is monotonically
increasing (3.67 → 14.35 → 28.38 → 68.38 → 88.80 Hz), so every drop is negative and the
clause is expected to hold at any n — but that is a prediction from the recorded means, and
Stage 2 tests it on resampled data rather than asserting it.

**The bootstrap.** For each candidate n, draw n values with replacement from the S measured
per-seed rates, B times, evaluate the clause on each draw, and report the flip fraction.
This makes no normality assumption, which matters at 10 Hz where the distribution is
strongly skewed — sd 4.225 exceeds mean 3.667, which is exactly the condition D-202 tests.

**Paired versus unpaired difference (ACC-3).** ACC-3's quantity is d = mean_sub − mean_full,
and `prep/extract.py` evaluates both halves **on the same seeds**. If per-seed values existed
for both, the honest estimate is the sd of the per-seed differences, which is smaller than
√(s_sub² + s_full²) whenever the two are positively correlated across seeds — and they
should be, since the same stimulus draws drive both. With only the subcircuit's per-seed
values, the unpaired form is the available bound and it is **conservative**: it overstates
the variability, so it can only recommend more seeds than are truly needed. The report will
label it as a bound, not as the measured paired figure.

**What none of this establishes.** The bootstrap estimates the sampling variability of the
verdict under the model as implemented. It says nothing about whether the model matches the
fly, which is ACC-3's and ACC-4's separate business.

## 5. Verification plan

| Stage | Command | Pass looks like | Will not prove |
|---|---|---|---|
| 0, 1 | `git diff docs/ONFLY-SRS.md` | the four rows change and nothing else | Nothing technical |
| 2 | `make fixtures` then `python prep/seeds.py` | 5 rates × S seeds, `seeds.json` written, flip table printed | x86-64 NATIVE only; nothing about MVS or s390x |
| 3 | `git diff docs/ONFLY-SRS.md` | TBD-06 CLOSED, §6.4 names the decision | Nothing technical |
| 4 | `mingw32-make test` | exit 0 | x86-64 only, this host's gcc, all three backends |

Every figure will be reported with platform, compiler and float backend, and with what it
does not prove.

## 6. Risks

| Risk | Mitigation |
|---|---|
| The bootstrap says the current 30 seeds is too few, and an existing PASS is unstable | Report it as a finding to the owner and let him decide; do not choose a seed count to preserve a verdict |
| Re-running `srext` gives means differing from `acc3-srext.json` | The engine is deterministic given (network, rate, seed); the first S = 30 seeds must reproduce the recorded means exactly, and the tool checks that and stops if not |
| `make fixtures` reaches outside the worktree | It is the sanctioned mechanism and copies rather than links; `--check` first |
| Scope creep into Phase G | The owner said "first E then we talk G"; P-17 stays a proposal and Phase G code is not written |

## 7. Questions for the owner

Asked through AskUserQuestion with this plan, not answered here.

1. Approve this plan, change it, or discuss it first.
2. Whether to recover D-344…D-346 and P-17 onto `main` now.
3. Whether to re-run the full brain (~2 h) so ACC-3's difference can be measured paired, or
   to use the recorded 30-seed sd as a conservative unpaired bound.
4. How many seeds S the subcircuit sweep should measure.

## 8. Related docs

- `docs/ONFLY-SRS.md` §6.4, §9.2, Appendix A.1 (D-135, D-202, D-246, D-341), Appendix B (TBD-06), Appendix D
- `docs/implementations/2026-09-15-phase-e-slice-5-acceptance.md`
- `docs/plan/2026-09-16-phase-g-live-view.md` — P-17, out of scope this session
