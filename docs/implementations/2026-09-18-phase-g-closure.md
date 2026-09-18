# 2026-09-18 — Phase G closed: the three components re-verified, then marked

| Field | Value |
|---|---|
| Date | 2026-09-18 |
| Phase / gate | Phase G (second MVP) — closure |
| Owner decisions | D-437 (scope), D-438 (TK5 use), D-439 (plan of record), D-440 (carried-forward items), D-441 (this run is a confirmation), D-442 (the marker), D-443 (fast-forward main) |
| Proposals | P-33 (the plan, approved), P-34 (the marker text, authorised) |
| Verification limits | VL-136 (new) |
| Platforms exercised | x86-64 Windows 11 and MVS 3.8j TK5 under Hercules 4.9.1 |

---

## 1. Problem / motivation

Phase G's three components were all built by 2026-09-17:

- the `EXEC CICS` transaction, verified in process against Raincode (D-391…D-402, VL-117);
- the live view, x86 and MVS halves, byte-identical streams (D-403…D-423, VL-118…VL-127, VL-135);
- the 3270 flow under INTERCOMM on TK5 (D-424…D-436, VL-129…VL-133).

Section 9.2's Phase G row described all three in prose and gave **no verdict**.
Every other finished phase carries a marker of the form
`COMPLETE <date> (D-nn)`; Phase G did not. The 2026-09-16 status snapshot had
named exactly this shape of defect a **record gap** when Phase E had it, and
D-348 closed that one the same day.

The gap was not cosmetic. D-126 makes the IBM Z Xplore permissions request
**with Phase G in hand**, and Phase F's dependency column reads
"E; permissions granted". A reader consulting Section 9.2 to decide whether
Phase G was in hand found three paragraphs of evidence and no conclusion.

The obvious fix — write the verdict from the records already in the document —
was rejected. Section 3 of the engineering protocol requires every reported
result to name the platform, compiler and float backend it was measured on **in
the reporting session**, and forbids reporting a result for a platform it was
not run on. A phase verdict assembled from yesterday's documents is precisely
that. So the marker was earned by re-running each component.

## 2. What changed

No source file changed. This is a record change backed by four measurement runs.

| File | Change |
|---|---|
| `docs/ONFLY-SRS.md` | Appendix A.1 gains D-437…D-443, seven owner decisions. Appendix A.2 gains P-33 (the plan, then struck as approved) and P-34 (the marker text, then struck as authorised). Appendix D gains VL-136. Section 9.2's Phase G row gains the `COMPLETE 2026-09-18 (D-442)` label and the closure note. |
| `docs/plan/2026-09-18-phase-g-closure.md` | New. The six-slice plan, drafted for approval before any command was run; approved as drafted by D-439. |
| `docs/implementations/2026-09-18-phase-g-closure.md` | New. This document. |

## 3. Implementation approach

The plan's ordering was chosen around one constraint: exactly one component is
slow, and it runs on a machine that is idle while the others do not need it.

1. **Baseline first.** `mingw32-make test` establishes that the tree is green on
   SOFT3E, SOFT2C and NATIVE before any component claim is made. If it had not
   exited 0, the session would have become a repair and been reported as one.
2. **The long TK5 job started next and left to run.** `tools/mvsstm.py --run`
   submits 9,244 cards, compiles thirteen translation units under GCCMVS,
   links, and simulates five requests while punching the chunk stream to the
   `10D` device. Eighteen minutes of guest wall clock.
3. **The Raincode component built on x86 while that ran.** Different machine,
   no contention on the thing that matters (byte-identity), and the two figures
   the TK5 job produces that *are* timing-sensitive were already settled as a
   confirmation rather than a reported figure by D-441.
4. **The stream comparison and the picture when the job landed**, then the 3270
   flow, which brings the INTERCOMM region up itself and takes it down again.
5. **Only then the record**: VL-136, the marker text as a proposal, this
   document, the commit and the push.

The one thing the plan did not anticipate: `--compare` needs an x86 comparand
stream that is not committed (`build/` is gitignored), so the native engine was
run once to produce `build/x86-stream.txt` from the same
`data/phase-d/x86w/req-srext.bin` the MVS job's `HERC01.ONFLY.EREQ` is built
from. That is a rebuild of a fixture, not a change to one.

## 4. Mathematical / numerical details

None. No formula, tolerance, statistical test or numeric algorithm was added,
removed or altered. The numerical content of this session is entirely
*comparison*: 19,909 stream lines matched byte for byte across two
architectures under D-414's CRLF rule, and five 32-bit fingerprints matched
Section 8.4's golden values on each of three independent paths (the MVS engine
under GCCMVS/SOFT2C, the x86 engine under gcc/NATIVE, and the CICS adapter).
The fingerprint itself is IR-COM-05's CRC over the canonical response string
and is unchanged.

## 5. Design decisions

**Re-run rather than re-read (D-437).** The alternative was ten minutes of
editing. It was rejected because the protocol's honesty rule is not satisfiable
by citation: a marker written from documents would be a claim about MVS made in
a session that touched no MVS.

**Carried forward rather than discharged (D-440).** Four items remain
undischarged: `ONFCBUZ` has never been executed, `CONCURRENCY(REQUIRED)` is
untested, the 3270 demonstration is not clone-reproducible, and the live view's
MVS half is `srext` only. The first two are blocked on a Raincode licence ONFLY
does not have (VL-37); the third is deliberate (D-132 keeps INTERCOMM-derived
material out of this MIT tree); the fourth is a cost question, not a defect.
The precedent is D-348, which marked Phase E complete with its own
carried-forward list intact — a phase closes on what it undertook, and the
carried-forward list is the record of what it did not.

**The confirmation does not become a reported figure (D-441).** D-436, one day
old, had settled which streaming runs Section 9.2 reports and named each. A
fifth run entering the row the following day would re-open the question D-436
answered. This session's figures live in VL-136 instead, where they do the job
that matters — making C3 a result measured now rather than a record read back —
without displacing figures that are candidates for external publication.

## 6. Verification

Four commands, all run on 2026-09-18, all exit 0. Reproduce with:

```
mingw32-make test
python tools/cicsbld.py build/cics
python tools/mvsstm.py --run
build/onflyeng_nat.exe STREAM=50 data/networks/onfnet-malecns-v1.0-srext.bin \
    data/phase-d/x86w/req-srext.bin build/x86-rsp.bin build/x86-stream.txt
python tools/mvsstm.py --compare
python tools/liveview.py --follow build/mvs-stream.txt --requests 5 --save out.gif
python tools/mvstx.py
```

| ID | Claim | Command | Result |
|---|---|---|---|
| V0 | The tree is green before any component claim | `mingw32-make test` | **PASS** — exit 0. `run_fp` 2427 passed on each of SOFT3E, NATIVE and SOFT2C; `run_ker` 449 on each; `run_units` 19; `run_req` 79; `cmpgld: SOFT3E, NATIVE, SOFT2C agree on all 19 golden requests across 2 networks`; `cmpchk [FR-SIM-10 chunk invariance]: 24 passed, 0 failed` |
| V1 | **C1** — the `EXEC CICS` transaction equals the batch engine (TX-06) | `python tools/cicsbld.py build/cics` | **PASS** — `run_cics: 3 checks, 0 failed`; `V4 PASS 2060 bytes, 5 records, byte-identical`; `V3 PASS transaction FP=BAF81D91 RC=0, equal to the batch response`; `V3 PASS 2 readout entries agree`. Raincode Crossbow net8.0, .NET 10.0.400, gcc 16.2.0, NATIVE backend |
| V2 | **C3a** — the MVS engine builds and streams live | `python tools/mvsstm.py --run` | **PASS** — job `ONFERUN` JOB 394, 9,244 cards, `K=50`; every step `COND CODE 0000` through 13 compiles, 13 assemblies, LKED and GO; `ONF302I STEP SUMMARY: 5 OK, 0 WARN, 0 ERROR`; 19,909 stream lines, longest 80 columns at line 442; `1026 of 1026 punch writes landed before the job ended`; `LIVE`; all five `srext` fingerprints Section 8.4's |
| V3 | **C3b** — the MVS and x86 streams agree | `python tools/mvsstm.py --compare` | **PASS** — `MVS 1523612 bytes / 19909 lines, x86 1543521 bytes / 19909 lines`; `19909 CRLF on the x86 side, 19909 bytes of difference accounted for by them`; `streams are BYTE-IDENTICAL under D-414's rule` |
| V4 | **C3c** — the picture draws from the MVS stream | `python tools/liveview.py --follow …` | **PASS** — `1000 chunks received, 1000 frames drawn`; `5 of 5 requests seen in 73.4 s`; every fingerprint matches Section 8.4 |
| V5 | **C2** — the 3270 transaction starts a run and shows its result (TX-07) | `python tools/mvstx.py` | **PASS** — region `ONFICOM` JOB 395, `INTERCOMM VERSION 9.0 STARTING`, device `0C1` as a 3279-2; `SUGR,0040,1000,000000001` → `ONF410I RUN STARTED`; result after 301 s as `ONF420I SUGR RATE= 40 MS=1000 SEED= 1 RC= 0 FP=BAF81D91`, `READOUT 1 ID=9 LAT-US=25800 SPIKES=27`, `READOUT 2 ID=88 LAT-US=-1 SPIKES=0`; screen fingerprint `== BAF81D91 (G-16)`; printed report fingerprint matches the screen's; both readout rows agree; `mvstx: PASS` |

### What these runs do not prove

Restated here because a closure document is where a reader looks for it.

- **C1 is x86-64 Windows only.** `ONFCBUZ` compiled but never executed;
  `SEND MAP` and `RECEIVE` return `INVREQ` with no licence (VL-37).
  `CONCURRENCY(REQUIRED)` is addressed by design and untested, one `rclrun` run
  unit being one task. On z/OS the LINK target would be a C program from IBM's
  compiler, not this .NET module.
- **C2 is TK5 only, is not CICS, and is not reproducible from a clone** (D-132).
- **C3's MVS half is `srext` only**, and the GCCMVS code-generation fault behind
  D-420 is still uncharacterised beyond `onffzer` being the only no-argument
  struct-returning function in ONFLY (VL-127).
- **Phase F is untouched.** Section 8.3 row 8 is empty; ACC-5 row 7 still covers
  5 of the 19 golden requests.
- Hercules is an emulator. VL-01's argument applies unchanged.

### One finding, recorded because it removes an audit route

`mvsstm` reported `punch file at 0 bytes before submission`. The Hercules
restart at 00:37 on 2026-09-18 truncated `pch/pch10d.txt`, so the four earlier
streaming runs that D-436 re-derived **from that file** are no longer
recoverable from it. No figure D-436 recorded changes. What is gone is the
means by which those figures were checked, which is an argument for D-441's
choice to leave them exactly as recorded rather than reopen the row.

## 7. Related docs

- `docs/ONFLY-SRS.md` §9.2 (phases), §8.3 (determinism matrix), §8.5 (TX-06, TX-07, TU-11), Appendix A.1 (D-437…D-443), Appendix A.2 (P-33, P-34), Appendix D (VL-136)
- `docs/plan/2026-09-18-phase-g-closure.md` — the approved plan
- `docs/implementations/2026-09-17-phase-g-cics-transaction.md` — C1 as built
- `docs/implementations/2026-09-17-phase-g-stage5-mvs-live-view.md` — C3 as built
- `docs/implementations/2026-09-17-phase-g-3270-intercomm.md` — C2 as built
- `docs/implementations/2026-09-17-phase-g-liveness-figure-reconciliation.md` — D-436, the figures this session deliberately did not disturb
