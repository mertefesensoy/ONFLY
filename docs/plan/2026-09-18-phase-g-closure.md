# Phase G closure — re-verify the three components, then draft the marker

**Drafted for owner approval before any verification work is done.** Nothing in
here is acted on until the owner approves it; this file is the proposal P-33
records.

| Field | Value |
|---|---|
| Date | 2026-09-18 |
| Phase | G (second MVP) — closure, not construction |
| Authorising decisions | D-437 (this is the session's scope), D-438 (TK5 jobs may be submitted freely) |
| Standing decisions it obeys | D-126 (the order is A,B,C,D,E,**G**,F,H and the permissions request is made with Phase G in hand), D-130/D-131 (which surface each component is), D-132 (nothing INTERCOMM-derived is committed), D-348 (the precedent for how a phase marker is added) |
| Platforms | x86-64 Windows (Raincode, MinGW, Python) and MVS 3.8j TK5 under Hercules 4.9.1 |

---

## 1. Problem / motivation

Phase G has three components and all three are built:

- the `EXEC CICS` transaction, verified in process against Raincode on x86-64
  (D-391…D-402, VL-117);
- the live view, x86 and MVS halves, byte-identical streams (D-403…D-423,
  VL-118…VL-127, VL-135);
- the 3270 flow under INTERCOMM on TK5 (D-424…D-436, VL-129…VL-133).

Section 9.2's Phase G row says so in prose. What it does **not** carry is a
completion marker of the form every other finished phase has — "**A —
Foundations — COMPLETE 2026-09-14 (D-252)**", "**E — MVS MVP — COMPLETE
2026-09-16 (D-348)**". Phase E carried exactly this gap for a day, and the
2026-09-16 status snapshot named it a *record gap* before D-348 closed it.

A record gap is not a cosmetic problem here. Phase F is blocked on the IBM Z
access request, and D-126 says the permissions request is made **with
Phase G in hand**. A reviewer reading Section 9.2 to decide whether Phase G is
in hand finds three paragraphs of evidence and no verdict.

**The gap is a record problem, so the fix is a record — but the protocol
forbids writing a verdict from documents alone.** Section 3 of the engineering
protocol requires every reported result to name the platform, compiler and
backend it was measured on **in this session**, and forbids reporting a result
for a platform it was not run on. So the marker is earned by re-running each
component, not by re-reading it.

## 2. What "closed" means for this phase

Section 9.1 defines exit criteria for gates G0–G4. Phase G is a **phase**, not
a gate, so its exit criteria are its Section 9.2 *Content* column, which names
exactly three things:

| # | Phase G content, as Section 9.2 states it | The component |
|---|---|---|
| C1 | "ONFLY as a transaction written in real `EXEC CICS`, verified against Raincode on the development host (D-130, VL-37)" | `cics/ONFCSUG.cbl`, `cics/ONFCBUZ.cbl`, the `[RainCodeExport]` module |
| C2 | "the flow shown on a real 3270 driven by INTERCOMM on TK5 (D-131)" | `tools/mvstx.py`, the SUGR/BUZZ verbs, the INTERCOMM subsystem (out of tree, D-132) |
| C3 | "a live view of the network rendered on x86 from streamed engine output (D-126, D-127, D-128)" | `tools/mvsstm.py`, `tools/liveview.py`, the `ONFSTM` chunk stream |

Closure means: each of C1, C2, C3 PASSES a command run in this session, the
tree is green, and the marker text is authorised by the owner.

## 3. Slices

Each slice ends with its command's real output printed in the transcript.

### Slice 0 — baseline

`mingw32-make test` on x86-64. Establishes that the tree is green on SOFT3E,
SOFT2C and NATIVE before any component claim is made. About 7 minutes. If this
is not 0, nothing else in this plan means anything and the session becomes a
repair, reported as such.

### Slice 1 — C3's long MVS half, started first

`python tools/mvsstm.py --run` submits the chunked engine to TK5 with
`PARM='STREAM=50'`, writing to the `10D` punch. The two valid prior runs took
about 1,010 s and 1,150 s to the END banner. **Started first and left to run**,
because it is the only long job in the plan and slice 2 needs a different
machine.

### Slice 2 — C1, on x86 while slice 1 runs on TK5

`python tools/cicsbld.py build/cics` — seven steps: the column check, the
engine shared library, the `[RainCodeExport]` module, `tests/tstcics.c`, the
BMS mapset, the COBOL compiles, and the `rclrun` run. TX-06's two assertions:
the adapter's 412-byte response records byte-identical to the batch engine's,
and the transaction reporting G-16's `BAF81D91` with MN9 at 27 spikes and
25800 µs. Raincode is installed on this host at `C:\Program Files\Raincode`;
`cicsbld.py` locates it through `RCBIN`/`RCDIR` and **skips with exit 0** if it
cannot, which would turn C1 into a not-run and must be reported as one.

### Slice 3 — C3 finished

When slice 1's job lands: `python tools/mvsstm.py --compare` against the x86
stream (D-414's CRLF rule), then `python tools/liveview.py --follow` to draw
the picture from the MVS stream rather than a local engine. C3 passes when the
streams are byte-identical and the five `srext` fingerprints are Section 8.4's.

### Slice 4 — C2

`python tools/mvstx.py`. It starts the INTERCOMM region if it is not up,
claims a free local 3270, logs on to `INTERCOM`, types `SUGR,…`, polls `BUZZ,`
until the run lands, asserts G-16's `BAF81D91`, and cross-checks every readout
row against FR-BAT-04's printed report of the same job. It stops the region
again if it started it. This is TX-07.

### Slice 5 — the record

Only if C1, C2 and C3 all pass:

1. A **VL entry** (VL-136) registering this session's measurements — every
   figure with its platform, compiler and backend, and everything the re-run
   does *not* cover.
2. The **Section 9.2 marker text**, drafted into Appendix A.2 as a proposal
   and put to the owner through AskUserQuestion. The SRS's requirement and
   phase text is not changed without an owner answer authorising that change.
3. An implementation doc at `docs/implementations/2026-09-18-phase-g-closure.md`.
4. Commit and push to `origin`.

## 4. What this will not prove

Stated now, so the closure report cannot quietly grow claims:

- **C1 is x86-64 Windows only.** `ONFCBUZ` has never been EXECUTED: `SEND MAP`
  and `RECEIVE` return `INVREQ` with no licence present (VL-37). Section 3.7's
  `CONCURRENCY(REQUIRED)` obligation is addressed by design and untested,
  because one `rclrun` run unit is one task. On z/OS the LINK target would be a
  C program from IBM's compiler, not this .NET module.
- **C2 is not reproducible from a clone**, by construction: D-132 keeps the
  INTERCOMM subsystem out of this MIT tree. It is TK5 only, and the monitor is
  not CICS.
- **C3's MVS half is `srext` only.** The GCCMVS code-generation fault behind
  D-420 is not characterised beyond `onffzer` being the only no-argument
  struct-returning function in ONFLY (VL-127).
- **Nothing here touches Phase F.** Row 8 of Section 8.3 stays empty, and
  ACC-5 row 7 still covers 5 of the 19 golden requests.
- Hercules and QEMU are emulators; VL-01's argument applies unchanged.

## 5. Open questions for the owner

Both are put with this plan.

1. **Do the four carried-forward items above block the marker, or carry into
   the row?** Phase E's marker was added with its own carried-forward list
   intact (D-348), which is the precedent; the alternative is to discharge one
   or more of them first, which is new construction, not closure.
2. **Does slice 1's run become a reported liveness figure?** D-436 settled, on
   2026-09-17, that Section 9.2 reports run 1 (JOB 320) and run 4 (JOB 328) and
   names each. A fifth run produces a fifth set of timings. Either it is added
   and the row reports three runs, or the re-run is a confirmation whose
   figures are recorded in the new VL entry but do not displace or join the two
   in Section 9.2.

## 6. Related docs

- `docs/ONFLY-SRS.md` §9.2 (phases), §8.3 (determinism matrix), §8.5 (TX-06,
  TX-07, TU-11), Appendix A.1 (D-437, D-438), Appendix D (VL-117…VL-135)
- `docs/implementations/2026-09-17-phase-g-cics-transaction.md`
- `docs/implementations/2026-09-17-phase-g-stage5-mvs-live-view.md`
- `docs/implementations/2026-09-17-phase-g-3270-intercomm.md`
- `docs/implementations/2026-09-17-phase-g-liveness-figure-reconciliation.md`
