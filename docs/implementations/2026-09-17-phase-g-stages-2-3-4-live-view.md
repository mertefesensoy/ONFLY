# 2026-09-17 — Phase G Stages 2, 3 and 4: the live view

| Field | Value |
|---|---|
| Date | 2026-09-17 (session opened 2026-09-16; D-374…D-383 were taken before midnight, D-384…D-389 after) |
| Author | Senior engineer |
| Phase / gate | Phase G — transaction demonstrator (second MVP), live-view half |
| Owner decisions relied on | D-128, D-139, D-140, D-344, D-345, D-346, D-366…D-368; taken this session: **D-374 … D-389** |
| Requirements touched | **IR-STM-01…04 (new)**, FR-SIM-07, FR-SIM-10, FR-SIM-05, FR-SIM-08, IR-COM-05, IR-NAM-01, NR-05, NR-13, C-04, ACC-2, ACC-5, FR-PRP-09, NFR-OBS-01 |
| Open items closed | none. TBD-19 was already closed by D-139/D-140; this builds what it closed on |

## 1. Problem / motivation

Phase G's third component is *"a live view of the network rendered on x86 from
streamed engine output"* (Section 9.2). Stage 1 (D-366) made the kernel
resumable — `onfinit`, `onfcont`, and `onfrun` defined as their composition —
but nothing yet **looked** between the chunks, and nothing knew **where** any
neuron was.

Without those two pieces the requirement cannot be met at all: D-128 fixed
"live" as the engine emitting intermediate state *during a single run*, and
explicitly ruled out the two cheap substitutes — one request per frame, and a
recorded trace replayed afterwards.

The failure this prevents is subtler than "no picture". A visualisation that
is *not* tied to the computation is worse than none: it looks like evidence
and is not. Section 6 below is mostly about making that impossible.

## 2. What changed

| File | Change |
|---|---|
| `engine/include/onfreq.h` | Declares `onfrqb`, `onfrqc`, `onfrqe` and states why the request sequence was split rather than duplicated or made to take a callback (D-383). |
| `engine/src/onfreq.c` | The split itself; `onfrq1k` is redefined as exactly their composition, so a streaming driver runs the same code path. |
| `engine/src/onflyeng.c` | `PARM='STREAM=nnn'` parsing (`onfestk`), the ONFSTM dataset, and the two emitters `onfesh` and `onfesc`. Messages ONF907S and ONF908S. |
| `tests/test_strm.py` | **TU-11**: inertness, agreement with the response, form, the membrane against the oracle, the two failure paths. |
| `prep/geom.py` | Joins the 501 `srext` bodies to `somaLocation`; measures the projection axes; emits the sidecar and the backdrop. |
| `tests/test_geom.py` | Guards the **committed** sidecar against the shipped network, without needing the gitignored feather. |
| `tools/liveview.py` | The three-panel viewer (D-345), consuming ONFSTM as it is written. |
| `Makefile` | `test_strm.py` in `req`, `test_geom.py` in `prep`, and a new `clips` target. |
| `docs/ONFLY-SRS.md` | D-374…D-389; P-21 in A.2; **Section 4.7 IR-STM-01…04**; TU-11 in 8.5; ONF907S and ONF908S in Appendix E. |
| `data/geom/*`, `docs/media/*` | The committed sidecar, backdrop and the two recorded clips (D-385, D-389). |
| `tests/test_varnt.py` | **D-390**, a defect this work exposed: its skip guard named the annotations feather while the test reads the 1.05 GB weights feather. Provisioning annotations for `prep/geom.py` therefore turned a clean skip into a `FileNotFoundError` that failed `make test` at `prep`. The guard now names every feather it reaches. |

## 3. Implementation approach

### 3.1 Why the request sequence was split (D-383)

`onfrq1k` owns the chunk loop, so a driver that wants to emit *between* chunks
cannot use it. Three ways out were possible and two were rejected:

- **A callback.** Smallest API change. Rejected because function pointers
  appear nowhere in this engine and have never been compiled by GCCMVS or
  JCC, and no MVS run was available this session to prove they can be.
- **Let the driver repeat the work.** No API change at all — and it puts a
  second implementation of the validation order, the step count and the
  fingerprint outside `onfreq.c`. That is the exact condition that produced
  D-289 and then D-360, silently both times. D-224 put the sequence in one
  place deliberately.
- **Split it**, which is what happened.

The contract:

```
int  onfrqb(net, st, maxms, q, z)   validate; onfinit if there is work.
                                    Returns non-zero when the caller should
                                    now drive chunks.  z is final except for
                                    the fingerprint in every other case.
int  onfrqc(net, st, z, k)          advance one chunk of up to k steps
                                    (k <= 0 = the whole remainder).  1 while
                                    steps remain, 0 when complete, -1 on
                                    non-finite state (FR-SIM-08).
void onfrqe(net, st, paycrc, q, z)  fill the readout entries if it ran, and
                                    fingerprint either way.  Exactly once per
                                    request, rejected ones included.
```

and then, literally:

```c
void onfrq1k(net, st, paycrc, maxms, q, z, k)
{
    if (onfrqb(net, st, maxms, q, z)) {
        while (onfrqc(net, st, z, k) > 0) { }
    }
    onfrqe(net, st, paycrc, q, z);
}
```

This is D-366's pattern one level up. **Bit-identity is structural, not
tested for afterwards** — the streaming path is the same statements with
emission interleaved.

### 3.2 The stream stays out of the kernel

All mutable state already lives in caller-allocated `struct onfsta`. The
driver keeps a snapshot of `st->spikes[]` and differences it after each
`onfcont`; `st->u[]` is read directly. The kernel is handed nothing and told
nothing, so:

- **FR-SIM-07 stands.** The simulation core still performs no I/O and no
  allocation after initialisation.
- **Stage 5 is cheap.** The MVS engine needs no kernel change to stream.
- **A stream cannot change an answer**, because nothing in the emission path
  flows back into the simulation. IR-STM-04 then only has to be *checked*,
  not *engineered*.

### 3.3 The record (IR-STM-02, IR-STM-03)

```
ONFSH ver n nr dtus k steps seed rate paycrc   once per simulated request
ONFSR idx ...                                  the readout columns' neurons
ONFSC chunk step nfired idx delta ...          sparse; only what moved
ONFSU chunk step u-hex ...                     16 hex digits each
ONFSE chunk rc fp                              once, rejected requests too
```

Two properties are load-bearing rather than cosmetic:

**Membrane values are bit patterns, never decimals.** NR-05 forbids
`onflyeng.c` from holding a binary64 *as a number at all*; the file already
prints header floats this way in the NFR-OBS-01 manifest. It is also the only
form in which two platforms can be compared exactly, which is what Stage 5
will need.

**`ONFSC` is sparse.** At 501 neurons and 200 chunks a dense encoding would be
100,200 rows. Measured: even at 40 Hz only about 209 neurons move per chunk,
and at rate 0 none do.

**Flushed after every chunk.** Without it stdio would deliver the run in 4 KB
blocks and the view would be a recording arriving late — the thing D-128
rejected.

### 3.4 Geometry (Stage 3)

`prep/geom.py` joins `SUBCIRCUIT.json`'s 501 bodies to the annotations and
emits one row per neuron **in network index order**, because that is what the
stream's neuron numbers are.

Two things are measured rather than assumed, and both are described in
Section 4.

## 4. Numerical and measurement details

No new arithmetic enters the simulation. The kernel's update order, the
propagator constants and the accumulation order are untouched — that is the
point of the structural split, and the fingerprint check is what proves it.

Three quantities are *measured* here, and each is reported so it can be
audited:

### 4.1 Which coordinate axis is which

`somaLocation` is a bare triple `(c0, c1, c2)`. Nothing in the dataset says
which entry runs down the body. Guessing would produce a picture wrong in a
way no test could catch — it would simply look like a different animal.

So for each axis *a* two separations are computed over all 141,781 annotated
somata, using labels that are **independent of the coordinates**:

- `Dbody(a) = |mean(a | somaNeuromere ∈ brain) − mean(a | somaNeuromere ∈ VNC)|`
  where VNC = {T1..T3, A1..A9}
- `Dside(a) = |mean(a | somaSide = L) − mean(a | somaSide = R)|`

The body axis is `argmax Dbody`, the side axis is `argmax Dside`, and the
remaining axis is depth. The build fails if those two are the same axis.
The brain's end of the body axis is read from the sign of the same difference.

Measured on MaleCNS v1.0 this session:

| axis | Dbody | Dside | role |
|---|---|---|---|
| x | 1,751 | **47,712** | left–right |
| y | 24,296 | 1,407 | depth |
| z | **73,713** | 912 | brain → nerve cord, brain at the **low** end |

The margins are not marginal: the chosen axis wins by 3× on the body test and
by 34× on the side test. The whole block is written into the sidecar under
`projection`.

### 4.2 Imputed positions (D-384)

19 of 501 bodies carry no `somaLocation`, and **14 of those are the entire
stimulus set**. That is biology: sugar-sensing GRNs (PhG9, dorsal_tpGRN —
D-52) have peripheral cell bodies in the proboscis, outside the imaged volume.

Fallbacks, in order, each computed over **measured positions only** so that an
imputed position can never feed another:

1. the centroid of the neuron's own postsynaptic targets in this network
2. the centroid of its `type` group
3. the centroid of the whole subcircuit

For the 14 GRNs, rule 1 applies with 15 to 23 measured targets each, putting
them in the SEZ (dorsal_tpGRN at z ≈ 19,000, PhG9 at z ≈ 26,000–30,000, split
left and right on x) beside the MN9 readouts at z ≈ 15,500 — where GRN axon
terminals are. The previous fallback put all 14 on one point at z = 90,408,
deep in the nerve cord.

Every such row keeps `placed: true` and records its `basis`.

### 4.3 How active the network actually is

Measured from the stream, per 5 ms chunk, over the `srext` golden requests:

| rate | mean neurons firing per chunk | max | distinct over the run |
|---|---|---|---|
| 0 Hz | 0.0 | 0 | 0 |
| 40 Hz | 209.5 | 256 | 419 |
| 100 Hz | 257.4 | 297 | 446 |
| 200 Hz | 260.6 | 292 | 438 |
| 9999 Hz | 304.0 | 337 | 449 |

This is why the full-duration raster reads as a solid block, and why D-388
records a short window as well: MN9's 27 spikes at 40 Hz are a rare event
inside a great deal of chatter. The block is the truth about this subcircuit,
not a drawing defect.

## 5. Design decisions

| Decision | Owner or architect |
|---|---|
| Scope = Stages 2, 3, 4 | Owner, **D-374** |
| matplotlib, accepted as a repository dependency | Owner, **D-375** |
| K = 50 for the demo | Owner, **D-376** |
| P-21 approved as the plan of record | Owner, **D-377** |
| K by PARM keyword, not in the request record | Owner, **D-378** — a **narrower reading of D-140** than its words, recorded as such |
| Stream to its own ONFSTM DD | Owner, **D-379** |
| Both guards in `make test` | Owner, **D-380** |
| ONF907S and ONF908S added | Owner, **D-381** |
| IR-STM-01…04 and TU-11 added — new requirement text | Owner, **D-382** |
| `onfreq.c` split rather than callback or duplication | Owner, **D-383** |
| GRNs at their target centroid | Owner, **D-384** |
| Sidecar and backdrop committed at ~620 KB | Owner, **D-385** |
| Commit per stage, push at the end | Owner, **D-386** |
| Raster ordered down the body axis — **a deviation from P-21** | Owner, **D-387** |
| Two clips, short and standard | Owner, **D-388** |
| Clips committed under `docs/media/` | Owner, **D-389** |
| `tests/test_varnt.py`'s skip guard corrected | Owner, **D-390** — found outside scope and asked rather than fixed, as D-360 was |

Architect's choices, not the owner's, and therefore open to correction: the
exact ONFSH/ONFSR/ONFSC/ONFSU/ONFSE field order; the sparse encoding; the
glow decay constant; the backdrop stride; and the three-level imputation
fallback order (the owner chose *that targets come first*, not the rest).

One drafting error is worth recording because it was caught by an existing
test rather than by review: the first draft of ONF908S said a PARM that was
"neither empty, nor VERIFY, nor a well-formed STREAM=nnn" was an error, which
would have silently changed behaviour `tests/run_eng.py` has asserted since
D-226 (`PARM='XYZZY'` means SIMULATE). The requirement was narrowed to PARMs
that *begin with* `STREAM=` before any code was written.

## 6. Verification

Everything below was run in this session on **x86-64 Windows, gcc (MinGW)**,
with the float backend named per line. Commands are as invoked.

### 6.1 The stream does not change the answer

```
mingw32-make golden
```
→ `cmpgld: SOFT3E, NATIVE, SOFT2C agree on all 19 golden requests across 2
networks`, and `cmpchk [FR-SIM-10 chunk invariance]: 24 passed, 0 failed`
over K ∈ {1, 7, 250, 100000} on all three backends.

```
python tests/test_strm.py build/onflyeng_soft.exe build/onflyeng_nat.exe \
    build/onflyeng_2c.exe
```
→ `test_strm: 292 passed, 0 failed`, about 40 s. Fifteen of those checks are the
`srext` fingerprints against the values TK5 recorded under **GCCMVS and JCC**
(VL-91, VL-93): `6C3F7272`, `BAF81D91`, `F9C7EE77`, `4FD0ED1E`, `C4C320BC`,
each reproduced on each backend with streaming on.

### 6.2 The stream describes the same run

Per readout neuron, the `ONFSC` counts sum to `ONF-OUT-SPIKES` and the chunk
in which they first rise brackets `ONF-OUT-LAT-US`. For example at 40 Hz:
27 spikes on neuron 9, latency 25,800 µs, bracketed by (25,000, 30,000].

### 6.3 Negative controls — would this have caught it?

Three deliberately-wrong emitters were built and run (a one-off experiment in
the spirit of D-370; nothing in the tree compiles them). Each changes **only**
the emitter, so the response and its fingerprint stay correct — a control that
also broke the fingerprint would be caught by `make golden` and would prove
nothing about TU-11.

| Control | What it does | Result |
|---|---|---|
| `cumul` | emits cumulative counts instead of deltas | **caught** — 11 failures; sums wrong by ~100× |
| `late` | holds each neuron's first event back one chunk | **caught** — 10 failures; every latency bracket wrong |
| `umem` | replaces the membrane column with the spike count | **passed every check at first** — 90 of 90 |

The third is the reason TU-11 now compares the membrane against the oracle
bit for bit: a small integer read as a binary64 is a subnormal, so it is
finite, it varies, and in the silent request it is zero — it satisfied every
*shape* check. With the oracle comparison added it fails at chunk 1:
`stream 0000000000000000, oracle 3FBD0F700A663AEF`. **A shape check cannot
tell a membrane from something shaped like one.**

All three controls were rebuilt from the final source and re-run against the
final test: `cumul` 11 failures, `late` 10, `umem` 1 — the oracle comparison.

### 6.6 A defect the golden suite could not have caught

Found by re-reading the streaming loop rather than by a test: a **warned or
rejected** request emitted `ONFSE` with no preceding `ONFSH`, so a consumer
met an end line for a request it had never been told about — and this file's
own parser raised on it. It contradicted IR-STM-02, and `onfesh`'s contract
comment asserted the wrong thing.

The `srext` half of Section 8.4 is five *valid* requests, so nothing in the
golden suite reaches that path. TU-11 now carries a deck that does — the
`srext` counterparts of G-11, G-12 and G-13 — and checks that such a request
streams a complete envelope with `steps` 0, no `ONFSC`, and its own return
code and fingerprint in `ONFSE`, all against the response record.

The lesson is the same one Section 6.3 draws: a suite that only exercises the
happy path cannot report on the paths it does not take.

### 6.4 Geometry

```
python prep/geom.py
```
→ `501 neurons, 482 measured, 19 placed`; `body axis z (brain-VNC separation
73713, brain at low end), side axis x (L-R separation 47712), depth axis y`;
`backdrop 20255 of 141781 somata (every 7th)`.

Two consecutive runs produce **byte-identical** sidecar and backdrop
(FR-PRP-09), verified with `cmp`.

```
python tests/test_geom.py
```
→ `12 passed, 0 failed`, including the index-mapping witnesses: every index
the network header calls readout is an MN9, every index it calls stimulus is
PhG9 or dorsal_tpGRN, and every ONFNAM row names the same neuron the sidecar
does. This is the check the Phase G plan recorded as outstanding.

### 6.5 The view is live, not a replay

```
mingw32-make clips
```
→ `120 chunks received, 120 frames drawn, 120 recorded`;
`first frame at +0.14 s, engine exited at +8.57 s (rc 0)`.

The first frame is drawn **eight seconds before the engine exits**. That is a
measurement of the property D-128 requires, not an assertion about it. Both
the `--save` writer path and the interactive `plt.pause` path were exercised.

## 7. What this does NOT prove

- **Every result here is x86-64, Windows, gcc (MinGW)**, on the backends
  named per line. Neither lab was started this session: no TK5 under
  Hercules, no QEMU s390x guest.
- **No MVS or s390x engine has ever written a stream.** IR-STM-01…04 are
  verified on one platform only. Stage 5 is out of scope under D-374, and the
  claim that this design makes Stage 5 cheap is an argument, not a
  measurement.
- **The interactive window was never seen.** The `plt.pause` branch was
  exercised under the Agg backend, which draws no window; that it renders
  correctly on a real display is untested.
- **Soma coordinate accuracy is the dataset's.** What was verified is the
  join, the axis measurement, the index mapping and the imputation flag.
- **The positions are somata, not neurites** — where cells sit, not their
  morphology. 19 of 501 are imputed.
- The axis measurement is evidence about `somaNeuromere` and `somaSide` as
  much as about the axes: it assumes those labels are right.

## 8. Related docs

- `docs/plan/2026-09-16-phase-g-stages-2-3-4.md` — P-21, the approved plan
- `docs/plan/2026-09-16-phase-g-live-view.md` — P-17, of which this is 2–4
- `docs/implementations/2026-09-16-phase-g-stage1-resumable-kernel.md`
- `docs/ONFLY-SRS.md` — Section 4.7, Section 8.3, 8.4, 8.5 (TU-10, TU-11),
  Section 9.2, Appendix A.1 (D-374…D-389), Appendix E
