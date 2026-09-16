# 2026-09-16 — Phase G live view: plan for the next session

| Field | Value |
|---|---|
| Date | 2026-09-16 |
| Author | Senior engineer, for owner approval |
| Phase / gate | Phase G — transaction demonstrator (second MVP), live-view half |
| Owner decisions relied on | D-126, D-127, D-128, D-139, D-140, D-318; D-344, D-345, D-346 (this session) |
| Requirements touched | FR-SIM-10, FR-SIM-04, FR-SIM-07, IR-COM-05, NR-05, NR-07, NR-13, C-04, ACC-5 |
| Open items closed | none — this is a plan, not an implementation |
| Status | **PROPOSED (P-17). Not approved. No code written this session.** |

This file is a plan, so it is not in `docs/implementations/`; that directory records
what was done. The implementation document is written when the work lands.

## 1. Problem / motivation

Phase G became ready on 2026-09-16: every dependency (Phase E in substance, TBD-17,
TBC-18, TBD-19) is satisfied. Its third component, in Section 9.2's own words, is
*"a live view of the network rendered on x86 from streamed engine output (D-126,
D-127, D-128)"*.

The owner's requirement for this session was a demo that is **valuable and legible to
other people** — something recordable that makes sense to someone who has never heard
of this project.

The gap is precise and is already named in the contract. FR-SIM-10 says a chunked run
must produce the identical response, and its own note states the position exactly:

> **Met by the oracle and open against the engine**: `engine/src/onfker.c` has no
> chunked entry point, so Phase G must show this against the Section 8.4 golden
> suite — VL-107.

So: the requirement exists (D-318), the test catalogue entry exists (TU-10), the
oracle-level proof exists (VL-107, 16 tests OK). **The engine implementation does
not.** `onfrun` initialises state and loops to completion with no way to resume.
Without it there is nothing to stream, and D-128 ruled out both alternatives — one
request per frame, and replaying a recorded trace — as not being "live".

### What makes this worth watching

The risk with a visualisation is that it becomes a screensaver: pretty motion that
proves nothing. Two things stop that here, and the plan is shaped around both.

1. **There is a real story in the data.** The shipped `srext` network is the sugar
   pathway: 14 sugar-sensing neurons (PhG9 + dorsal_tpGRN, D-52) and the MN9 motor
   neurons that drive proboscis extension. Stimulus arrives at the mouthparts,
   propagates through the nerve cord, and MN9 fires — the fly deciding to eat. With
   real soma coordinates that is a legible anatomical event, not an abstract graph.
2. **There is a claim only this project can show.** The same C source, on MVS 3.8j
   under Hercules, produces bit-identical fingerprints (ACC-5 rows 6 and 7, two
   independent compilers). A viewer that shows the fly firing *and* the two platforms
   agreeing is evidence, not decoration.

## 2. Owner decisions taken this session

Recorded in SRS Appendix A.1 as D-344, D-345, D-346.

| ID | Decision |
|---|---|
| D-344 | The stream comes from the **x86 native build first**, with the MVS streaming path as a second step. |
| D-345 | The viewer shows **three coupled panels**: anatomy, spike raster, MN9 membrane trace. |
| D-346 | The simulated network is **`srext` (501 neurons)**, drawn inside a faint point cloud of all MaleCNS soma positions. |

## 3. What the data actually supports (verified this session, on x86 only)

| Fact | Evidence | Limit |
|---|---|---|
| Soma coordinates exist for the shipped network | `somaLocation` in `body-annotations-male-cns-v1.0-minconf-0.5.feather`; 482 of 501 `srext` bodies carry one (96.2%) | Read on x86 with pandas this session. Coordinates are soma positions only, not neurites — the drawing is cell bodies, not morphology |
| The network spans brain and nerve cord | `somaNeuromere` over the 501: A8 43, T3 41, T2 41, T1 30, A5 29, None 108 | `None` for 108 means the neuromere label is absent, not that the neuron is absent |
| Index to bodyId mapping exists | `data/networks/SUBCIRCUIT.json` then `subcircuits.500.bodies`, 501 entries in network index order | Not independently re-verified against the `.bin` this session |
| The full-brain backdrop is available | 141,782 distinct `somaLocation` values over 211,577 annotated bodies | Includes bodies outside any ONFLY network, which is the point of a backdrop |
| Nothing in the tree runs in chunks | `tests/test_chunk.py` header; `onfker.h` contract | Confirmed by reading, not by running |

**The 13.1 GB `syn-points` file is not needed and should not be fetched.** It was
deliberately not retrieved (`MANIFEST.json`, `not_retrieved`) and the annotations file
already carries what the view needs.

## 4. Implementation approach

### Stage 1 — a resumable kernel (the load-bearing change)

This is the only change to the engine's simulation contract, and it touches ACC-5's
spine. It is designed so that `onfrun` cannot change behaviour, rather than tested
afterwards to see whether it did.

All mutable simulation state already lives in caller-allocated `struct onfsta` — `u`,
`g`, `rfr`, `spikes`, `first`, `force`, `isstim`, `ring`. Only three things are
trapped inside `onfrun`: the PRNG state, the step counter, and the request's rate.
Move those into `struct onfsta` and split the function:

    int onfinit(const struct onfnet *net, struct onfsta *st,
                onf_u32 seed, onf_i32 rate, onf_i32 steps);
    int onfcont(const struct onfnet *net, struct onfsta *st, onf_i32 k);

with the existing entry point redefined as exactly:

    int onfrun(net, st, seed, rate, steps)
    {
        int rc = onfinit(net, st, seed, rate, steps);
        if (rc != ONFK_OK) return rc;
        return onfcont(net, st, steps);
    }

`onfrun` is then the same code path it always was, so bit-identity is structural
rather than hoped for.

`onfcont` takes only `k`, never `rate` or `seed`: a caller cannot change the rate
mid-run, because there is no parameter through which to do it. That removes a whole
class of driver bug by construction.

**Three pieces of state make chunk boundaries observable, and each is preserved by
moving it into `st`:**

| State | Why a naive chunked driver breaks it |
|---|---|
| `rng` (xorshift32, NR-13) | Re-seeding per chunk restarts the stimulus stream; FR-SIM-04 requires one stream per request |
| `step` | First-spike latency is `step * dtus`; restarting the index per chunk reports wrong latencies |
| `step % delay` into `ring` | The delay ring is indexed by absolute step; restarting rotates the ring and misdelivers synaptic input |

TU-10 already names the driver that "re-seeds or restarts the step index per chunk"
as the thing to catch, so the test and the design agree about the threat.

**Constraints that are easy to violate by habit:** C89 plus `long long`; no `float`,
`double` or floating-point literals (NR-05); every floating-point operation through
the `onf_fp` API in Appendix C's exact order (NR-07); external names at most 8
characters, unique ignoring case (C-04) — `onfinit` and `onfcont` are 7 each, but
`tools/lint_c04.py` must confirm no collision with existing symbols before the bodies
are written; no I/O, no allocation, no static data (FR-SIM-07).

**Stage 1 gate — nothing is drawn until all of this passes:**

1. `mingw32-make test` green on NATIVE, SOFT3E and SOFT2C.
2. The 19 Section 8.4 golden fingerprints **unchanged**, compared against the values
   recorded in Section 8.3 rows 6 and 7.
3. `tests/test_chunk.py` extended from oracle level to the engine: the same request at
   K in {1, 7, 250, full} yields one fingerprint. This is what discharges FR-SIM-10
   against the engine and clears its "open against the engine" note.

If a fingerprint moves, stop and report. A chunk-dependent fingerprint would not cost
a feature, it would cost the determinism claim Phase E just established.

### Stage 2 — the stream (D-139), entirely in the driver

D-139 requires spike events for every neuron plus membrane snapshots for the readout
set. Both are already readable from `st` after each `onfcont` call:

- **Spikes:** `st->spikes[]` is a cumulative per-neuron count. The driver snapshots it
  before and after each chunk and emits the delta — which neurons fired during this
  chunk, and how often.
- **Membrane:** `st->u[]` read directly for the readout indices.

**The kernel therefore does no I/O and needs no callback.** That keeps FR-SIM-07
intact and means the MVS engine needs no kernel change for streaming either, which is
what makes Stage 5 cheap. It is also why D-140 chose caller-driven chunking over a
kernel callback.

Resolution is per chunk, not per step. At K=1 it is per step exactly.

Record: newline-delimited, one per chunk, fields in a fixed order, no text in the
numeric path. Shaped to map onto an MVS record later rather than to be convenient now.

### Stage 3 — geometry sidecar (`prep/geom.py`, new)

Joins `SUBCIRCUIT.json` bodies against the annotations feather on `bodyId`. Emits per
neuron: index, bodyId, x, y, z, somaSide, somaNeuromere, class, type, and a `placed`
flag.

The 19 neurons with no `somaLocation` are placed at the centroid of their `type` group
and **flagged `placed: true`**, so the viewer can draw them differently. They are never
silently given an invented position — a viewer that cannot tell measured from imputed
is a viewer that lies.

Also emits the backdrop: soma positions for the full annotated set, downsampled, as a
separate compact file.

Open sub-task: compute the bounding box and choose the projection that puts brain
above nerve cord. The axis order in `somaLocation` has not been confirmed against
anatomy and must not be assumed.

### Stage 4 — the viewer (D-345)

Three coupled panels sharing one clock:

- **Anatomy.** 501 neurons at real soma positions inside the faint full-brain cloud. A
  spike lights a neuron, which then decays. Stimulus neurons and MN9 are marked and
  labelled — colour is never the only encoding.
- **Raster.** Neuron index against time, filling left to right as the run proceeds.
- **MN9 trace.** Membrane potential climbing toward threshold, with the threshold
  drawn. This is the panel that shows *why* a spike happens rather than only that it
  did.

It consumes the stream as it is produced. It must not read a completed file — that
would be the replay D-128 rejected.

### Stage 5 — the MVS half (D-344's second step)

The same chunked driver on TK5, and a fingerprint panel showing the x86 and MVS runs
agreeing. Deliberately last: it is the highest-risk piece, because MVS spools job
output rather than streaming it, and the transport for mid-job output is unproven.
Stages 1 to 4 must stand on their own without it.

## 5. Numerical detail

No new mathematics. The kernel's update order, the propagator constants P11, P12, P22,
the subnormal clamp G_EPS and the accumulation order over strictly ascending target
indices (IR-NET-06) are all unchanged. That is the point of the structural split: **the
arithmetic must be untouched, and the fingerprint check is what proves it was.**

The only new numeric quantity is the chunk size K, which is a count of timesteps and
enters no arithmetic. FR-SIM-10 requires the response to be independent of it.

Frame budget, to be confirmed against the network header's `dt_us` rather than assumed:
a 1000 ms run at dt = 0.1 ms is 10,000 steps, so K = 100 gives 100 frames and K = 33
gives about 300. A recordable clip wants roughly 100 to 300 frames.

## 6. Verification plan

Every claim must state platform, compiler and float backend, and what it does not prove.

| Stage | Command | Pass looks like | Will not prove |
|---|---|---|---|
| 1 | `mingw32-make test` | exit 0 on NATIVE, SOFT3E, SOFT2C | Nothing about s390x or MVS |
| 1 | golden-suite fingerprint compare | all 19 identical to Section 8.3 rows 6 and 7 | Only that x86 is unchanged; MVS must be re-run in Stage 5 |
| 1 | `python tests/test_chunk.py` (extended) | K in {1, 7, 250, full} give one fingerprint | Oracle plus x86 engine only |
| 3 | `python prep/geom.py` | 501 rows, 482 measured, 19 flagged `placed` | Coordinate accuracy is the dataset's, not verified here |
| 4 | record a run | video shows stimulus, propagation, MN9 spiking | An x86 result; says nothing about MVS |
| 5 | MVS run | fingerprints equal to x86 | One network, one duration, one seed unless swept |

## 7. Risks

| Risk | Mitigation |
|---|---|
| The kernel split moves a fingerprint | `onfrun` redefined as init plus cont so it is the same path; fingerprints compared before anything else proceeds |
| `onfinit` or `onfcont` collides under C-04 | Run `tools/lint_c04.py` first; rename before writing the body |
| MVS cannot stream mid-job | Stage 5 is last and separable; Stages 1 to 4 deliver the demo without it |
| The projection axis is guessed wrong | Compute the bounding box and check brain-above-VNC before rendering |
| The viewer needs a new dependency | **Open question below — must be answered before Stage 4** |

## 8. Open questions for the owner

1. **Viewer technology, and whether a dependency is allowed.** A Python viewer using
   matplotlib is zero new dependency *if* matplotlib is already in the environment —
   unverified. A self-contained HTML/canvas viewer fed by a local file needs no Python
   package but does need a way to stream to the page. The engineering protocol requires
   asking before adding any dependency, so this is the first question next session opens
   with.
2. **Chunk size K for the demo**, once `dt_us` is read from the header. K is a request
   field under D-140, so a demo value is not a specification change, but the default
   belongs to the owner.
3. **Whether Stage 5 is in scope for the next session at all**, or whether the session
   ends at a recordable x86 demo and MVS becomes its own session.

## 9. Related docs

- `docs/ONFLY-SRS.md` Section 3.3 (FR-SIM-10), Section 8.3 (determinism matrix),
  Section 8.4 (golden suite), Section 8.5 (TU-10), Section 9.2 (Phase G row),
  Appendix A.1 (D-126, D-127, D-128, D-139, D-140, D-318, D-344 to D-346), Appendix D
  (VL-107)
- `docs/implementations/2026-09-16-d316-chunk-invariance.md` — the oracle-level proof
- `docs/status/2026-09-16-status.md` — the state Phase G starts from
