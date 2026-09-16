# 2026-09-16 — Phase G Stages 2, 3 and 4: the live view

| Field | Value |
|---|---|
| Date | 2026-09-16 |
| Author | Senior engineer, for owner approval |
| Phase / gate | Phase G — transaction demonstrator (second MVP), live-view half |
| Owner decisions relied on | D-126, D-127, D-128, D-139, D-140, D-344, D-345, D-346, D-366, D-374, D-375, D-376 |
| Requirements touched | FR-SIM-07, FR-SIM-10, FR-SIM-05, NR-05, NR-07, C-04, IR-COM-05, NFR-OBS-01, ACC-5 |
| Open items closed | none — this is a plan |
| Status | **PROPOSED (P-21). Not approved. No code written until it is.** |

This refines Stages 2, 3 and 4 of P-17, which D-366 left as proposals to be
approved individually when reached. D-374 selected them as this session's scope;
D-375 chose matplotlib; D-376 fixed the demo chunk size at K = 50.

## 1. Problem / motivation

Stage 1 gave the engine a resumable kernel: `onfinit`, `onfcont`, and `onfrun`
defined as their composition (D-366, D-367), driven per request by `onfrq1k`
(D-368). Nothing yet *looks* between the chunks. D-128 fixed what "live" means —
the engine emits intermediate state during a single run, not one request per
frame and not a replayed recording — and D-139 fixed what it emits: spike events
for every neuron, plus membrane snapshots for the readout set only.

So the three missing pieces are: something that emits (Stage 2), something that
says where each neuron is (Stage 3), and something that draws it (Stage 4).

## 2. Measured facts this plan rests on

All read on x86-64 in this session, not assumed.

| Fact | Value | How it was obtained |
|---|---|---|
| `srext` header | `n=501, e=10783, dt_us=100, delay=18, refract=22, max_ms=1300, u_th=7.0, w_syn=0.2969` | `layout/netread.read()` on `data/networks/onfnet-malecns-v1.0-srext.bin` |
| Bias table | `bias_rates = [0,10,20,40,60,80,120,160,200]`, 9 rows | same |
| Standard run | 1000 ms ÷ 100 µs = **10,000 steps**; at K=50 that is **200 chunks** | arithmetic on the above |
| Readout indices | `[9, 88]` — the two MN9 | same header |
| Stimulus indices | 14 entries, `[128,136,140,141,142,145,147,148,150,155,156,446,496,497]` | same header |
| matplotlib | 3.10.7 installed; **imported nowhere in the repository** | `import matplotlib`; `grep` over `prep/ tools/ tests/ layout/ oracle/` |
| Annotations feather | 14,483,314 bytes, CRC-32 `DC81FB64`, SHA-256 recorded | `data/malecns/MANIFEST.json` |
| The feather is absent from this worktree | `prep.names.ANNOT` does not exist here | `os.path.exists` |
| The request record has **no** chunk field | `HEAD` is 28 bytes over 8 fields, record 412 | `layout/master.py` |

That last row is the one with teeth, and Section 4 turns it into a question.

## 3. Stage 2 — the stream, emitted entirely in the driver

### 3.1 Where the code goes

`engine/src/onflyeng.c` — the batch adapter — gains a stream path that is inert
unless asked for. **The kernel is not touched.** `st->spikes[]` is a cumulative
per-neuron count and `st->u[]` is the membrane array; both are readable from the
caller's own `struct onfsta` between `onfcont` calls, so the driver differences
`spikes[]` across a chunk and reads `u[]` directly. That is what keeps FR-SIM-07
("no I/O and no dynamic allocation after initialization") true of the core, and
it is why D-140 chose caller-driven chunking over a kernel callback.

Putting it in `onflyeng.c` rather than in an x86-only test driver is deliberate:
Stage 5 (D-344's second step) then needs no new program on MVS.

### 3.2 The record

Line-oriented, newline-delimited, fixed field order, one tag per line type, and
**no text in the numeric path**. Shaped to map onto an MVS record later.

```
ONFSH <ver> <n> <nr> <dtus> <k> <steps> <seed> <rate> <paycrc-hex>
ONFSR <idx> <idx> ...
ONFSC <chunk> <step> <nfired> <idx> <delta> <idx> <delta> ...
ONFSU <chunk> <step> <u-hex> <u-hex>
ONFSE <chunk> <rc> <fp-hex>
```

`ONFSH` once per request, `ONFSR` once (the readout indices, so the viewer needs
no second file to know which neurons the `ONFSU` columns are), then `ONFSC` and
`ONFSU` per chunk, then `ONFSE`.

**Membrane potentials are emitted as 16 hexadecimal digits of the binary64 bit
pattern, never as decimal.** NR-05 forbids `onflyeng.c` from holding a binary64
as a number at all, and the file already prints header floats this way in the
NFR-OBS-01 manifest. The viewer reconstructs the value with
`struct.unpack('>d', bytes.fromhex(...))`. A bit pattern is also the only form in
which two platforms can be compared exactly, which is what Stage 5 will need.

`ONFSC` is **sparse**: only neurons whose count changed during the chunk appear.
D-139 requires coverage of every neuron, not a row per neuron per chunk. At 501
neurons and 200 chunks a dense encoding would be 100,200 rows for a run in which
most neurons are silent most of the time.

The stream is **flushed after every chunk**. Without that, C stdio buffering
would deliver the run in 4 KB blocks and the view would not be live in any
meaningful sense — it would be a replay with extra steps, which is what D-128
rejected.

### 3.3 What it must not do

The stream must not change the answer. The guard is the same one Stage 1 used:
run the Section 8.4 golden suite with streaming on and compare all nineteen
fingerprints against the recorded values. A stream that perturbs a fingerprint
is not a feature that failed, it is the determinism claim of Phase E failing.

## 4. Stage 2's two open design questions

### 4.1 How does K reach the driver?

D-140 says K "travels in the request rather than being fixed in the SRS". The
request record has no field for it: `HEAD` is eight fields over 28 bytes, and the
record is 412. Three ways out, and this is the owner's to choose:

| Option | Cost |
|---|---|
| **(a) PARM keyword**, `PARM='STREAM=50'` | No layout change. K is per *run* rather than per *record*, which is a narrower reading of D-140 than its words |
| **(b) A new positional argument** | Same as (a), but invisible to MVS JCL, which passes PARM and DDs, not argv |
| **(c) A field in the request record** | Literally what D-140 says. Costs: the record grows past 412 bytes, so the generated COBOL copybook, C header and Python struct all move, every recorded MVS artifact is stale, and TX-01's measured 412-byte identity (D-261) must be re-established on TK5 — a Stage 5 cost paid in Stage 2 |

### 4.2 Where does the stream go?

| Option | Cost |
|---|---|
| **(a) A separate file / DD**, `argv[5]`, default `DD:ONFSTM` | Keeps the numeric stream out of the operator message path; maps onto an MVS DD directly; the viewer tails the file as it grows |
| **(b) stdout, interleaved with ONF messages** | One fewer file to allocate; but the report and the stream share a channel, and on MVS SYSPRINT is the report |

Tailing a file **that is still being written** is not the replay D-128 rejected:
the viewer follows the writer, frame by frame, and stops when `ONFSE` arrives.

## 5. Stage 3 — the geometry sidecar (`prep/geom.py`, new)

### 5.1 Provisioning

`tools/fixtures.py` is extended to provision `data/malecns/` artifacts the same
way it already provisions `data/networks/`: search `$ONFLY_FIXTURES`, the main
checkout, then sibling worktrees; verify byte count, CRC-32 **and** SHA-256
against `data/malecns/MANIFEST.json`; copy, never link (D-249's rule, and the
reason for it is recorded there). Only the 14.5 MB annotations file is needed —
not the 43 MB neurotransmitters file and not the 1.05 GB weights file.

### 5.2 Output

Per neuron, in network index order: `index, bodyId, x, y, z, somaSide,
somaNeuromere, class, type, placed`.

The 19 of 501 bodies with no `somaLocation` are placed at the centroid of their
`type` group and flagged **`placed: true`**. If a type group has no measured
member at all, the fallback is the centroid of the whole subcircuit, still
flagged. They are never silently given an invented position: a viewer that
cannot tell measured from imputed is a viewer that lies, and the flag is what
lets the drawing mark them.

The backdrop — soma positions for the full annotated set — is downsampled by a
**deterministic stride over bodyId-sorted order**, not a random sample, so two
runs produce byte-identical files (the property FR-PRP-09 demands of the prep
pipeline generally).

Both files are committed, so the viewer runs from a clean checkout without the
feather: the 501-row sidecar as JSON, the backdrop as CSV of integers.

### 5.3 The axis question

The axis order inside `somaLocation` has **not** been confirmed against anatomy
and this plan does not assume it. `geom.py` computes the bounding box and reports,
per axis, the mean coordinate of the bodies labelled with a brain neuromere
against those labelled with a nerve-cord neuromere (`T1,T2,T3,A1..A8`). The axis
that separates them is the one the viewer treats as the long body axis, and the
sign that puts brain above nerve cord is read off the same comparison rather than
guessed. The measurement is printed so it can be disagreed with.

## 6. Stage 4 — the viewer (`tools/liveview.py`, new)

matplotlib (D-375), three coupled panels on one clock (D-345), consuming the
stream as it is produced:

- **Anatomy.** 501 neurons at real soma positions inside a faint point cloud of
  the full annotated set (D-346). A spike lights a neuron which then decays.
  Stimulus neurons and MN9 carry distinct **markers and labels** — colour is
  never the only encoding. Imputed positions are drawn hollow.
- **Raster.** Neuron index against time, filling left to right.
- **MN9 trace.** Membrane potential against time with `u_th = 7.0` drawn, so the
  panel shows *why* a spike happens and not only that it did.

It launches `onflyeng` itself, tails the stream file, and renders each chunk as
it lands. `--save` writes a GIF through matplotlib's Pillow writer (Pillow ships
with matplotlib; no new dependency), so the clip is recordable without a screen
recorder.

## 7. Verification

Every claim states platform, compiler and backend. Everything below is x86-64,
gcc (MinGW) on this host; **nothing here says anything about s390x or MVS.**

| # | Check | Command | Pass looks like |
|---|---|---|---|
| V1 | The stream does not move a fingerprint | `mingw32-make test` | exit 0; all 19 Section 8.4 fingerprints unchanged on NATIVE, SOFT3E, SOFT2C |
| V2 | The stream agrees with the response | `python tests/test_strm.py` | per request: summed `ONFSC` deltas per readout neuron equal `ONF-OUT-SPIKES`; the first chunk in which a readout neuron's count rises brackets `ONF-OUT-LAT-US` |
| V3 | Streaming is inert when not asked for | byte-compare response datasets with and without `STREAM=` | identical |
| V4 | Chunking still invariant with the stream on | `python tools/cmpchk.py` | unchanged from D-369's sweep |
| V5 | Geometry | `python prep/geom.py` | 501 rows, 482 measured, 19 flagged `placed`; two runs byte-identical |
| V6 | The viewer draws what the engine sent | `python tools/liveview.py --save` | a GIF whose frame count equals the chunk count |

**V2 is the test that matters.** V1 proves the response did not change; only V2
proves the *stream* is the same run — that what is drawn is what was computed,
rather than a plausible animation beside it.

## 8. What this will not prove

- Every result is **x86-64, gcc (MinGW), on this development host**. Neither lab
  is started: no TK5 under Hercules, no QEMU s390x guest.
- Stage 5 is out of scope by D-374, so nothing here shows MVS streaming, and
  the claim that this design makes Stage 5 cheap is an argument, not a measurement.
- Soma coordinate accuracy is the dataset's; this plan verifies the join and the
  imputation flag, not the anatomy.
- The projection axis is measured from neuromere labels, which is evidence about
  the labels as much as about the axes.

## 9. Related docs

- `docs/plan/2026-09-16-phase-g-live-view.md` — P-17, of which this is Stages 2–4
- `docs/implementations/2026-09-16-phase-g-stage1-resumable-kernel.md` — Stage 1
- `docs/ONFLY-SRS.md` — FR-SIM-07, FR-SIM-10 (Section 3.3), Section 8.3, 8.4,
  8.5 (TU-10), Section 9.2 (Phase G), Appendix A.1 (D-126…D-140, D-344…D-346,
  D-366…D-376), Appendix D (VL-107, VL-115)
