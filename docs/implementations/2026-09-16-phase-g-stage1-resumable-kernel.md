# 2026-09-16 — Phase G Stage 1: the resumable kernel, and FR-SIM-10 against the engine

| Field | Value |
|---|---|
| Date | 2026-09-16 |
| Author | Senior engineer |
| Phase / gate | Phase G — transaction demonstrator (second MVP), Stage 1 of P-17 |
| Owner decisions relied on | D-364, D-365, D-366, D-367, D-368, D-369, D-370, D-371; and, inherited, D-140, D-224, D-318, D-344…D-346 |
| Requirements touched | FR-SIM-10 (discharged against the engine), FR-SIM-04, FR-SIM-05, FR-SIM-07, FR-SIM-08, IR-COM-05, NR-05, NR-07, NR-08, NR-12, NR-13, C-04, ACC-5 (guarded, not re-claimed) |
| Open items closed | none. FR-SIM-10's engine half is discharged; TBD-13 and TBD-06's seed clause are untouched |

## 1. Problem / motivation

Phase G's third component is *"a live view of the network rendered on x86 from
streamed engine output"* (Section 9.2). Nothing could be streamed, because
nothing could be paused.

`engine/src/onfker.c` had one entry point, `onfrun`, which initialised every
array, looped to completion and returned. The PRNG, the step counter and the
request's rate were **locals**: they existed only while that call was on the
stack. A caller could therefore have the whole answer or none of it, and D-128
had already ruled out both alternatives to real streaming — one request per
frame, and replaying a recorded trace.

The contract already named the gap precisely. FR-SIM-10, added 2026-09-16 by
D-318, requires a chunked run to produce the identical response, and its own
status note said:

> **Met by the oracle and open against the engine**: `engine/src/onfker.c` has
> no chunked entry point, so Phase G must show this against the Section 8.4
> golden suite — VL-107.

So the requirement existed, the catalogue entry existed (TU-10), and the
oracle-level proof existed. The engine implementation did not.

**The failure this prevents is not a missing feature.** ACC-5 is the project's
spine: nineteen fingerprints reproduced across the rows of Section 8.3, two
independent compilers on MVS among them. If the fingerprint depended on where
a chunk boundary fell, Phase G would be built on a determinism claim that
Phase E had already published as evidence. The whole shape of this change is
chosen so that outcome is impossible by construction rather than unlikely.

## 2. What changed

| File | Change |
|---|---|
| `engine/include/onfker.h` | `struct onfsta` gains `gen`, `step`, `steps`, `thresh`, `brow` — the five things that were locals of `onfrun`; declares `onfinit` and `onfcont`; documents why each carried value is what a naive chunked driver gets wrong. |
| `engine/src/onfker.c` | Split into `onfinit` (initialisation and the D-190/D-191 bias-row choice) and `onfcont` (the step loop), with `onfrun` redefined as their composition. No arithmetic changed. |
| `engine/include/onfreq.h` | Declares `onfrq1k`, the chunked form of the shared request sequence, and states the FR-SIM-10 obligation on it. |
| `engine/src/onfreq.c` | `onfrq1` becomes `onfrq1k(..., 0)`; `onfrq1k` holds the one implementation and drives the kernel through `onfinit` plus repeated `onfcont`. |
| `tests/tstgld.c` | Optional third argument, the chunk size K, passed to `onfrq1k`; K echoed in the banner so a comparison across K can say which run made which lines. |
| `tools/cmpchk.py` | **New.** Runs the Section 8.4 suite at a swept set of K and requires every GOLD and GOUT line to be byte-identical to the unchunked reference run. |
| `Makefile` | The `golden` target invokes `cmpchk` on all three backends at K ∈ {1, 7, 250, 100000} (D-369). |
| `tests/run_eng.py` | `kernel_absent()` now looks for every kernel entry point, not only `onfrun`; a `KERNEL_ENTRIES` tuple makes the omission visible if another is added. |
| `tests/test_chunk.py` | Docstring only. It claimed *"Nothing in the tree can currently run in chunks"*, which stopped being true; it now says it is the oracle half and names `cmpchk` as the engine half. |
| `docs/ONFLY-SRS.md` | D-364…D-371 in A.1; P-17, P-19, P-20 struck as adopted in A.2; FR-SIM-10's status note and Section 8.5's TU-10 row replaced under D-371; VL-115 and VL-116 in Appendix D. |

## 3. Implementation approach

### 3.1 The split, and why it is structural

`onfrun` is now **defined** as its two halves:

```c
int onfrun(const struct onfnet *net, struct onfsta *st,
           onf_u32 seed, onf_i32 rate, onf_i32 steps)
{
    int rc;

    rc = onfinit(net, st, seed, rate, steps);
    if (rc != ONFK_OK) {
        return rc;
    }
    return onfcont(net, st, steps);
}
```

There is exactly one step loop in the program. A whole run and a chunked run
are therefore not two implementations that ought to agree — they are the same
code reached two ways, and bit-identity is a consequence of that rather than a
property to be hoped for and tested afterwards.

**Contract of `onfinit`** — inputs `net`, `seed`, `rate`, `steps`; output: `st`
fully initialised with `st->step == 0`; returns `ONFK_OK`. Side effects:
writes only through `st`; no I/O, no allocation, no static data (FR-SIM-07).
It cannot fail today — there is no arithmetic before the first step that could
go non-finite — but it returns `int` so `onfrun` needs no special case and a
future check here changes no caller.

**Contract of `onfcont`** — inputs `net`, `st`, `k`; advances
`min(k, st->steps - st->step)` steps (D-367) and returns `ONFK_OK`, or
`ONFK_NONFIN` exactly as `onfrun` did. `k <= 0` advances nothing.
Invariant relied on: `st` was initialised by `onfinit` against this same
`net`. On `ONFK_NONFIN` the state is left mid-step deliberately — FR-SIM-08
requires the request to be abandoned (ONF903S), so there is nothing to resume.

**`onfcont` takes neither `rate` nor `seed`.** That is not an omission. A
caller cannot change the stimulus rate part-way through a run because there is
no parameter through which to do it, which removes a class of driver bug by
construction rather than by review.

### 3.2 The three carried values, and why each matters

| State | What a naive chunked driver does to it | Consequence |
|---|---|---|
| `gen` | re-seeds per chunk | the stimulus stream restarts; FR-SIM-04 requires one stream per request |
| `step` | restarts at 0 per chunk | `step % delay` rotates the delay ring, so synaptic input is misdelivered, and `(step + 1) * dtus` mis-dates every first-spike latency (FR-SIM-05) |
| `steps` | — | without it `onfcont` could not clamp, and a K that does not divide the step count would overrun |

`thresh` and `brow` are derived from the rate once in `onfinit` and are
read-only thereafter, so a chunk boundary cannot reselect the D-191 bias row.

### 3.3 Transcription risk, and how it was eliminated rather than reviewed

Moving a normative loop is where this change could have gone wrong silently.
Two things were done about it.

**First, a mechanical diff.** The step-loop body was extracted from the
pre-split file and from the new one, comments and blank lines stripped, and
the declared substitutions applied to the old text (`&gen` → `&st->gen`,
`thresh` → `st->thresh`, and the inner CSR index `k` → `e`, since `k` is now
the chunk-size parameter). The two then compare **equal at 53 statements
each**, with exactly two lines added that the old body had no need for:
`t = st->step;` at the top and `st->step = t + 1;` at the bottom.

**Second, a real error was caught this way.** The first transcription reused
the outer neuron index `i` for the CSR emission loop, because the original's
inner variable `k` collided with the new parameter name. That would have
destroyed the outer loop counter. It was found before any build.

### 3.4 The request level

D-368 put the chunk loop in `engine/src/onfreq.c` rather than in the test,
because D-224 made `onfrq1` the single shared request sequence — ONFLYENG, the
MVS driver and `tstgld` all run it. A chunk loop written inside `tstgld` would
have re-implemented validation, readout extraction and fingerprinting, so the
test would have proved a copy of the path rather than the path itself.

```c
krc = onfinit(net, st, (onf_u32)q->seed, q->rate, z->steps);
if (krc == ONFK_OK) {
    if (k <= 0) {
        krc = onfcont(net, st, z->steps);
    } else {
        while (st->step < z->steps) {
            krc = onfcont(net, st, k);
            if (krc != ONFK_OK) {
                break;
            }
        }
    }
}
```

The loop carries nothing across iterations except `st`. It computes no
`min()`, because `onfcont` clamps its own final chunk. It terminates because
`onfcont` with `k >= 1` strictly increases `st->step` while any steps remain.

A **rejected** request never reaches the kernel, so K is irrelevant to it —
and that is worth having in the sweep, because FR-BAT-04 fingerprints rejected
requests too and ACC-5 compares those fingerprints. G-11, G-12 and G-13 are
the three in the suite.

## 4. Numerical details

**No mathematics changed, and that is the claim being made.** The update order
of Appendix C, the propagator constants P11, P12 and P22, the NR-08 subnormal
clamp at G_EPS, the strict threshold of D-69, the D-67 freeze-and-reset of `g`
and the accumulation order over strictly ascending CSR target indices
(IR-NET-06) are all untouched. Section 3.3's mechanical diff is the evidence
for that, and the fingerprint comparison in Section 6 is the consequence.

The one new quantity is the chunk size **K**, a count of timesteps. It enters
no arithmetic. FR-SIM-10 requires the response to be independent of it.

Why the sweep is the set it is (D-369). Floating-point addition is not
associative, so the question is never "does the arithmetic commute" but "does
any per-chunk state leak into it". The values probe the ways a boundary can
fall:

- **K = 1** — a boundary between every pair of steps: the maximum number of
  opportunities for state to be lost.
- **K = 7** — divides neither 10,000 (the standard 1000 ms at dt = 0.1 ms) nor
  13,000 (G-09 at the 1300 ms maximum, D-138), so boundaries land at unaligned
  positions and the final chunk is short. 10,000 = 7·1428 + 4 and
  13,000 = 7·1857 + 1.
- **K = 250** — divides 10,000 exactly but not 13,000, so most requests see
  only whole chunks and G-09 alone sees a short one.
- **K = 100,000** — larger than every request in the suite, so `onfcont`
  clamps on the very first call (D-367) and the driver loop ends after one
  iteration.

## 5. Design decisions

| Decision | Choice | Alternatives declined |
|---|---|---|
| D-366 | P-17 approved as the plan of record; Stage 1 exactly as drafted | Approve Stage 1 only; change the design; discuss first |
| D-367 | `onfcont` clamps to what is left, in the kernel | Exact `k` with the caller clamping (the oracle's division of labour); exact `k` with a new overrun return code — declined because a new code enters a header ACC-5's fingerprints depend on |
| D-368 | `onfrq1k` beside `onfrq1` in the shared request module | Chunk loop inside `tstgld`; a separate kernel-only `tstchk.c`, which would have exercised no fingerprint and no validation and so would not have met FR-SIM-10's own wording |
| D-369 | Sweep all three backends at four K in `make test` (+4.6 min measured) | NATIVE only (+2 min) — declined because ACC-5 is claimed on all three, and "the backend cannot matter" is an argument, not evidence; eight K (+8.3 min); keep out of `make test` |
| D-370 | Negative controls stay a one-off, recorded here and in VL-116 | A permanent `make chknp` target compiling deliberately wrong source |
| D-371 | P-19 and P-20 written in | Drop P-19's platform sentence; leave both texts stale |

The engineer's own choices inside those: `e` as the CSR index name (the
original `k` now names the chunk size); `KERNEL_ENTRIES` as a named tuple in
`run_eng.py` rather than three inline comparisons, so that adding a fourth
entry point has one obvious place to be recorded.

## 6. Verification

**Everything below was run on x86-64 in this session.** Platform: Windows 11,
build 10.0.26200.9457, under MSYS2/MinGW64. Compiler: `gcc.exe (MinGW.org
GCC-6.3.0-1) 6.3.0`. `GNU Make 3.82.90` (`mingw32-make`). `Python 3.13.14`.
Float backends: SOFT3E, SOFT2C and NATIVE.

### 6.1 The gate: the nineteen fingerprints did not move

The golden suite was run and recorded **before** the kernel was touched, then
again after, on all three backends and both networks:

```
for b in soft nat 2c; do
  ./build/tstgld_$b.exe data/networks/onfnet-malecns-v1.0-path.bin  0
  ./build/tstgld_$b.exe data/networks/onfnet-malecns-v1.0-srext.bin 1
done
```

**153 GOLD and GOUT lines byte-identical**, 19 requests × 3 backends. The
fingerprints: G-01 `6C143127`, G-02 `5CAB2AA0`, G-03 `A54BAAC7`, G-04
`82808C5F`, G-05 `CBEB5C0B`, G-06 `4F98279A`, G-07 `C4CABE4D`, G-08
`F37639B8`, G-09 `5E07D024`, G-10 `461A343E`, G-11 `025CBFDB`, G-12
`740E6A92`, G-13 `A30B1F03`, G-14 `8EC69ADE`, G-15 `6C3F7272`, G-16
`BAF81D91`, G-17 `F9C7EE77`, G-18 `4FD0ED1E`, G-19 `C4C320BC`.

### 6.2 FR-SIM-10 against the engine

```
python tools/cmpchk.py build/tstgld_soft.exe build/tstgld_nat.exe \
  build/tstgld_2c.exe --chunks 1,7,250,100000
```

See VL-115 for the recorded result and its limits.

### 6.3 The negative control: would the test have caught the defect?

A passing test cannot answer that, so two deliberately wrong kernels were
built from copies of `onfker.c` in the scratchpad — the tree was never
modified — each realising one of TU-10's two named threats. Both were caught;
the figures are in VL-116.

The first attempt at the step-index control is itself worth recording. Setting
`t = c` alone left `st->step = t + 1` pinning `st->step` at `k`, so the
driver loop in `onfrq1k` never terminated and the run **hung** rather than
producing a wrong fingerprint. That is a true statement about the carry being
load-bearing, but it is not the thing `cmpchk` has to catch, so the control
was corrected to advance `st->step` independently and then it produced the
moved fingerprints that were wanted.

### 6.4 How to reproduce

```bash
mingw32-make fixtures && mingw32-make testfloat && mingw32-make test
```

`make testfloat` is needed once in a fresh worktree: `testfloat_gen.exe` is a
gitignored build output, and `tt02` fails with a clear message rather than a
make error when it is absent.

## 7. Not proven

- **x86-64 only.** No chunked run has been made on Linux s390x, MVS 3.8j or
  z/OS. Chunk invariance is a property of state handling and the C is the same
  on every target, but that is an argument; the evidence is x86.
- The `onfrun` path is unchanged and re-measured, so ACC-5 rows 6 and 7 are
  **guarded** by this work, not re-established by it. No MVS or s390x run was
  made in this session.
- Stages 2 to 5 of P-17 are untouched: there is no stream, no geometry
  sidecar, no viewer and no MVS chunked driver. Nothing here draws anything.
- `onfinit`'s `int` return is never non-`ONFK_OK` today, so the `rc` check in
  `onfrun` is unexercised.
- The sweep covers four K. Every K was checked against the same reference, not
  against each other pairwise; that is a weaker statement than all-pairs, and
  equal to it only because equality is transitive, which it is here because
  the comparison is byte equality.

## 8. Follow-ups (out of scope)

- Stage 2: the D-139 stream, by differencing `st->spikes[]` between chunks in
  the driver. The kernel needs no further change for it.
- Stage 5: the same chunked driver on TK5, which would turn VL-115's x86-only
  limit into an ACC-5-row-6 result.
- `tools/cmpchk.py` has no s390x invocation. When the guest is next up,
  `make ONFPLAT=s390x ... golden` would produce the big-endian row cheaply.

## 9. Related docs

- `docs/plan/2026-09-16-phase-g-live-view.md` — P-17, of which this is Stage 1
- `docs/implementations/2026-09-16-d316-chunk-invariance.md` — the oracle half
- `docs/ONFLY-SRS.md` Section 3.3 (FR-SIM-10), Section 8.4, Section 8.5
  (TU-10), Appendix A.1 (D-364…D-371), Appendix D (VL-107, VL-115, VL-116)
