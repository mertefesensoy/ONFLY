# 2026-09-17 — Phase G Stage 5: the live view's MVS half

| Field | Value |
|---|---|
| Date | 2026-09-17 |
| Author | Senior engineer |
| Phase / gate | Phase G — transaction demonstrator (second MVP), live-view component |
| Owner decisions relied on | D-128, D-139, D-140, D-344…D-346, D-366, D-377; taken this session: **D-403 … D-423** |
| Requirements touched | **IR-STM-01…04**, FR-SIM-10, IR-COM-05, ACC-5 row 6, **NR-06**, NR-05, NR-08, C-04, NFR-OBS-01 |
| Open items closed | none. TBD-19 was closed by D-139/D-140; this builds on it |

## 1. Problem / motivation

P-17 (approved as D-366) laid the live view out in five stages and said of the
last:

> **Stage 5 — the MVS half.** The same chunked driver on TK5, and a fingerprint
> panel showing the x86 and MVS runs agreeing. Deliberately last: it is the
> highest-risk piece, because MVS spools job output rather than streaming it,
> and the transport for mid-job output is unproven.

Stages 1 to 4 landed the same morning (D-374…D-389) and left the component
working on x86-64 and nowhere else. Three things were unknown, and the third
was the one the plan called the risk:

1. **Does the chunked engine build on MVS?** `onfrqb`/`onfrqc`/`onfrqe`, the
   split request sequence Stage 1 introduced, and the ONFSTM emitter had never
   been seen by GCCMVS.
2. **Does chunking move an answer there?** FR-SIM-10 requires the response to
   be independent of K. That is tested on x86 and on no other platform.
3. **Can output leave MVS while the job is still running?** Without this an MVS
   "live view" is a recording played afterwards — which D-128 explicitly ruled
   out as one of the two cheap substitutes.

The failure this prevents is not "no picture". It is a picture that *looks*
like evidence: an animation produced from a finished spool file, shown beside a
mainframe, implying something about the mainframe that was never true.

## 2. What changed

| File | Change |
|---|---|
| `engine/src/onflyeng.c` | `ONF_STMCOL`/`ONF_STMBUF`, and the three emitters rewritten to fill lines by measurement: `ONFSC` continuing on `ONFSD` (D-406), `ONFSU` and `ONFSR` continuing by repeating their own tag (D-412, D-413). |
| `tools/goldfp.py` | **New.** The Section 8.4 `srext` fingerprints in one place, now that three callers need them as data. |
| `tools/mvsstm.py` | **New.** The streaming engine job on TK5: `PARM='STREAM=nnn'`, the ONFSTM DD on the `10D` punch, an incremental harvest of the punch file, and the liveness, width and fingerprint measurements. |
| `tools/liveview.py` | `--follow` (render a stream someone else is writing), the fingerprint panel, `ONFSD` and the repeated-tag continuations, and per-request reset so a five-request stream draws five pictures. |
| `tests/test_strm.py` | TU-11 gains the width clause, the reassembly clause, and `check_wide` — a synthetic nr=30 network built for the sole purpose of making the `ONFSU` and `ONFSR` wrap branches execute. |
| `docs/ONFLY-SRS.md` | D-403…D-423; P-25…P-29 in A.2; **IR-STM-02 and IR-STM-03 amended** (D-409, D-412, D-413); TU-11 amended; Section 9.2's Phase G row (D-417, then D-422); **VL-118…VL-128** in Appendix D. |
| `tools/mvsjcc.py` run | ACC-5 row 7 refilled from corrected source (D-423); no file changed, the row's provenance did. |
| `engine/include/onffp.h`, `engine/src/onffpc.c`, `engine/src/onfker.c` | **`onffzer()` removed (D-420).** GCCMVS miscompiled it; its callers use `onffbit(0UL, 0UL)`, measured correct on the same build. |
| `tests/tstfp.c`, `tests/run_fp.py` | **D-421.** The zero constant's bit pattern is printed and checked, so this defect class fails where it happens. |
| `tools/mvsfp.py` | **New.** Builds and runs `tests/tstfp.c` under GCCMVS on TK5 — the first time ONFLY's float self-test has run on MVS at all. |
| `docs/media/onfly-mvs-live.gif` | The MVS run recorded as it happened (D-411, D-416). |
| `docs/plan/2026-09-17-phase-g-stage5-mvs-live-view.md` | The plan of record (P-25, approved as D-408). |

## 3. Implementation approach

### 3.1 The carrier, and how it was chosen

Not by reasoning. Four measurements on the running TK5, before a line of the
plan was written.

**Every SYSOUT device belongs to JES2.** `$DU` names READER1 `00C`, PRINTER1
`00E`, PRINTER2 `00F`, PRINTER3 `002` and PUNCH1 `00D`; `D U,,,00C,8` reports
all four unit-record devices as status **A**, allocated. JES2 spools, so
anything written through `SYSOUT=` reaches the host when the job *ends*. The
obvious answer cannot be live, and that is measured rather than assumed.

**`10D` is a punch JES2 does not own.** `D U,,,10C,4` gives `10C 2540 O` and
`10D 2540 O` — online and unallocated. `tools/mvseng.py` already reads `10C` as
a *device* for the reader transport; `10D` is its punch counterpart, configured
as `010D 3525 pch/pch10d.txt ascii`, so Hercules translates EBCDIC to ASCII and
appends to a plain host file.

**It is live.** A probe job wrote twelve cards with a CPU burn between them
while the host sampled the file every 250 ms: twelve size changes, one per
~1.25 s, all before the END banner at t=16.8 s.

**It truncates silently over 80 columns.** The same job wrote lines of 79, 80,
81 and 200 columns. They arrived as 79, 80, **80** and **80** bytes — one card
per line, no split, no message, `COND CODE 0000`. The D-93 failure class.

### 3.2 Why the format changed, and how far

`ONFSC` is the only line type that reaches the bound in practice. Measured on
x86 at K=50 over the five `srext` golden requests:

```
  ONFSC  n=1000  longest=1976   over80=797
  ONFSE  n=5     longest=20     over80=0
  ONFSH  n=5     longest=42     over80=0
  ONFSR  n=5     longest=10     over80=0
  ONFSU  n=1000  longest=49     over80=0
```

797 of 1,000 `ONFSC` lines would have lost their tail on MVS. So D-406
introduced `ONFSD`: continuation lines repeating the chunk and step, with
`nfired` **unchanged** — still the count for the whole chunk. That last point
is the design, not a detail. A consumer reads pairs across the `ONFSC` and its
`ONFSD` lines until it has `nfired` of them, so a line that went missing is
*detectable*. The rejected alternative — repeating `ONFSC` with a per-line
count — would have made a truncated chunk indistinguishable from a complete
one, which is the exact failure the 80-column limit creates.

`ONFSU` and `ONFSR` cannot overflow on any shipped network: `nr` is 2 on all
four. The owner declined to leave them (D-410, D-413) on the ground that a
bound holding for one line type and not another is not a bound, and both now
continue by **repeating their own tag**. The asymmetry with `ONFSD` is
principled: `ONFSC` could not repeat because `nfired` sits on it, while `ONFSU`
and `ONFSR` carry no count and `nr` from the `ONFSH` line already plays
`nfired`'s part.

### 3.3 The fill is by measurement, not by a constant

Each emitter formats the next item into a small buffer, measures it, and starts
a new line when it would not fit. A pairs-per-line constant would have to be
sized for a 10-digit index beside a 10-digit count and would then waste three
quarters of every line in the common case.

The bound is arithmetic, and the arithmetic is in the source: `chunk`, `step`
and `nfired` print from `long`s that IR-NET and FR-SIM hold below 2^31, so each
costs at most 11 columns; the `ONFSC` header is therefore at most 38 columns
and a pair at most 22, and 38 + 22 = 60 ≤ 80. **Every line can always hold its
header and at least one item**, so neither fill loop can fail to make progress,
neither needs an error path, and neither can loop forever.

### 3.4 Separation between the driver and the viewer

`tools/mvsstm.py` drives TK5 and knows nothing about drawing.
`tools/liveview.py --follow` draws and knows nothing about TK5. The stream file
is the only thing between them. In particular **the liveness claim is
`mvsstm.py`'s alone** — it is the only process that can see both the punch file
and the job's END banner — and `liveview.py` says so in its own output rather
than claiming something it cannot know.

The harvest is incremental. A harvest that ran once when the job finished would
hand the viewer a finished recording, which is what D-128 ruled out, while the
mechanism that made a live view possible sat unused.

### 3.5 The defect this work found, and how

The stream comparison is what found it, and nothing that existed before could
have. The sequence is worth recording because each step eliminated a
hypothesis rather than confirming one.

**The symptom.** With the MVS stream and the x86 stream side by side, 200 of
19,910 lines differed. Every one was an `ONFSU` line of **G-15, the rate 0
silent request**. x86 wrote `0000000000000000`; MVS wrote subnormals around
1e-318 that rose for 34 chunks and then held bit-identical for 166. Requests
G-16 to G-19 were byte-identical and all five fingerprints agreed.

**First hypothesis, wrong.** A value that stops changing under repeated
multiplication by P11 ≈ 0.995 suggests subnormal multiplication is a no-op in
the MVS build. That was recorded as a hypothesis (VL-120) and it was refuted.

**The measurement that refuted it.** Three MVS runs of the same five requests.
Runs 2 and 3, from the same binary, produced **byte-identical** streams; run 1,
from a binary differing only by D-412's and D-413's continuations — byte-inert
on x86 — differed in exactly those 200 lines. A deterministic arithmetic fault
reproduces. This did not. The values depend on **code layout**, which means
something is reading storage it did not write.

**The probe.** A job linking the engine's own SoftFloat units, so that a
correct result could not exonerate a library the engine does not have. Its
first line was the answer:

```
FPP ZERO   00000000000AE782        onffzer()          <-- not +0.0
FPP HAND   0000000000000000        z.hi = 0; z.lo = 0
FPP BIT00  0000000000000000        onffbit(0UL, 0UL)
FPP PRESET DEADBEEFCAFEBABE        a variable, before
FPP AFTERZ 00000000000AE782        the same variable, after a = onffzer()
FPP U50    0000000000000000        Appendix C, 50 steps from the HAND zero
```

`onffzer()` did not return `+0.0`, from source that reads exactly
`z.hi = 0UL; z.lo = 0UL; return z;`. `AFTERZ` shows the call *does* write — it
writes the wrong bytes. `onffbit(0UL, 0UL)`, the same return type with two
arguments, is correct in the same program, and the Appendix C recurrence run
from a correctly-built zero gives `0000000000000000`, which is what x86 and the
oracle give. `onffzer` was the **only** no-argument struct-returning function
in ONFLY, and it is the one that failed.

**Why it mattered more than the symptom suggested.** `onfinit` seeded every
`u`, every `g` and the whole ring from it; NR-08's clamp re-seeded `g` from it;
and the reset after a spike set `u` and `g` from it. Every `+0.0` in the MVS
kernel was that subnormal.

**Why nothing caught it.** IR-COM-05's fingerprint covers spike counts and
latencies, and 1e-318 against a 7.0 mV threshold changes neither. TU-11's
oracle comparison of the membrane runs on x86. `tests/tstfp.c` *used* the zero
constant and never checked what it was. And ONFLY's float self-test had never
run on MVS at all — Gate G1 ran SoftFloat's own tests there, not ONFLY's layer
over them. D-420 removed the function; D-421 closed the coverage gap, and
`tools/mvsfp.py` is the runner that had been missing.

**An honest note on the luck.** No fingerprint ever moved because of this, on
any platform, in any run. That is not because the engine was protected from it
— it is because a subnormal of 1e-318 is swamped by every normal-magnitude
value it meets. It survived three MVS runs and every suite ONFLY has.

## 4. Mathematical / numerical details

**None, and that is the claim.** No arithmetic changed: not the kernel's update
order, the propagators P11/P12/P22, the subnormal clamp `G_EPS`, nor the
accumulation order over ascending target indices (IR-NET-06). `ONF_STMCOL` is a
count of text columns and enters no computation.

The claim is *checked* rather than asserted, three ways:

- The response dataset is byte-identical before and after the format change —
  2,060 bytes, `cmp` clean.
- All five `srext` fingerprints are unchanged: `6C3F7272`, `BAF81D91`,
  `F9C7EE77`, `4FD0ED1E`, `C4C320BC`.
- The x86 stream is byte-identical before and after D-412/D-413, confirming
  those two branches are inert at `nr` = 2.

## 5. Design decisions

| Decision | Alternatives, and why they were rejected |
|---|---|
| **D-403** scope | The `path` half of ACC-5 row 7; Phase G's 3270/INTERCOMM component; the CICS transaction's concurrency obligation |
| **D-406** `ONFSD` | Repeated `ONFSC` with a per-line count (destroys the completeness check); tape 0480 (liveness unmeasured, AWS parsing, and it is the network transport's drive); capping the pairs (makes the stream a sample) |
| **D-407** all five requests at K=50 | G-16 alone, or K=100. The owner chose the fuller run against the engineer's recommendation, so the panel shows five rows and the whole `srext` half is re-proved through the chunked path |
| **D-410, D-412, D-413** | The engineer recommended recording the `ONFSU` residual; the owner declined, and `ONFSR` was then found to have the same hole and closed the same way. A third option — narrowing IR-STM-03 — was offered and declined; it would have been the first requirement text this session weakened |
| **D-411** commit the clip | Evidence without a picture, or a shorter clip |
| **D-414** judge V5 after CRLF→LF | Drop the cross-platform byte comparison, or make x86 write LF with a platform conditional. Text mode is what makes each newline a *record* on MVS, so binary mode is not available there. The allowance is checkable: the files differ by exactly one byte per line |
| **D-415 → D-419** record, then diagnose | D-415 said record only; the evidence then changed — from "MVS differs from x86" to "two MVS runs differ from each other" — and the owner reversed it. The reversal was right: the diagnosis found a real defect and the engineer's stated hypothesis was wrong |
| **D-420** remove `onffzer` | Give it a dummy argument (an inference from `onffbit`, not a measurement of the function); build the zero at the call sites (measured correct, but puts the representation into the kernel that `onffp.h` exists to keep it out of); record and do not fix |
| **D-421** assert the bit pattern on MVS | Assert it on x86 only, leaving it unproven where it has ever failed; no test at all. `tests/tstfp.c` *used* the constant and never checked it, which is the whole reason the defect survived |
| **D-423** refill ACC-5 row 7 | Record the gap and leave the row; run only the float self-test under JCC. The owner chose the fuller job against the engineer's recommendation, so no shipped determinism row rests on a binary known to contain a defect |

## 6. Verification

Every row below was run in this session. Platform, compiler and float backend
are stated for each, and Section 6.2 says what each does **not** prove.

### 6.1 P-25's seven rows

| # | Claim | Command | Result |
|---|---|---|---|
| V1 | The format change is numerically inert | `mingw32-make test` | **PASS** — exits 0; the Makefile's all-passed banner for SOFT3E, SOFT2C and NATIVE. The response dataset is byte-identical before and after the change (`cmp`, 2,060 bytes) and all five `srext` fingerprints are unchanged |
| V2 | No stream line exceeds 80 columns | `python tests/test_strm.py build/onflyeng_nat.exe` | **PASS** — `test_strm: 122 passed, 0 failed`, including `D-406 K=50 no line exceeds 80 columns / longest is 80 columns at line 442` and the same at K=7 |
| V3 | The engine builds on MVS with the chunked path | `python tools/mvsstm.py --run` | **PASS** — 9,244 cards, every step `COND CODE 0000` through 13 compiles, 13 assembles, LKED and GO |
| V4 | Chunking does not move the answer on MVS | the same run | **PASS** — `ONF302I STEP SUMMARY: 5 OK, 0 WARN, 0 ERROR`, and all five fingerprints equal Section 8.4: `6C3F7272`, `BAF81D91`, `F9C7EE77`, `4FD0ED1E`, `C4C320BC` |
| V5 | The MVS stream equals the x86 stream | `python tools/mvsstm.py --compare` | **PASS**, after the D-420 fix — `streams are BYTE-IDENTICAL under D-414's rule (1523612 bytes)`, 19,909 lines. **It FAILED before the fix**, which is how the defect was found |
| V6 | The MVS half is live | the same run | **PASS** — **run 4, JOB 328**: `first ONFSC at +31.3 s, job END banner at +1011.3 s`, `1020 of 1020 punch writes landed before the job ended`. Run 1 (JOB 320) measured the same claim independently at +28.3 s against +1148.1 s, 1,027 of 1,028; **both runs are reported in SRS Section 9.2 and registered with their limits in VL-135** (D-436). They are two measurements on different binaries, not a repeatability figure |
| V7 | The picture draws from the MVS stream | `python tools/liveview.py --follow …` | **PASS** — 5 of 5 requests followed as the job wrote them, fingerprint panel `AGREE` on every row, `docs/media/onfly-mvs-live.gif` |

### 6.1b The two rows the defect added

| # | Claim | Command | Result |
|---|---|---|---|
| V8 | The zero constant is `+0.0` **on MVS** (D-421) | `python tools/mvsfp.py` | **PASS** — every step `COND CODE 0000`; `FPZERO z=00000000:00000000`; and the **2,019 self-test lines are identical, line for line, to the x86-64 SOFT2C build's**. The first time ONFLY's float self-test has ever run on MVS |
| V9 | ACC-5 row 7 no longer rests on a defective binary (D-423) | `python tools/mvsjcc.py --run` | **PASS** — rebuilt and re-run under **JCC 1.50.00**, 13 compiles + PRELINK + LKED + GO + DUMP all `COND CODE 0000`, `5 OK, 0 WARN, 0 ERROR`, and the five fingerprints **unchanged** from the values row 7 already carried |

### 6.2 What none of it proves

- **Platform.** V3 to V7 are **TK5 MVS 3.8j under Hercules, GCCMVS 3.2.3, SOFT2C**, on the `srext` network at K = 50, and nothing else. V1 and V2 are **x86-64, MinGW gcc**, on SOFT3E, SOFT2C and NATIVE. Linux s390x was not re-run in this session at all.
- **JCC's exposure is unmeasured.** V9 rebuilt row 7 from corrected source and its fingerprints did not move, which is what VL-125 predicted; it does **not** establish whether JCC miscompiled `onffzer` in the same way GCCMVS did. Nothing measured that.
- **The compiler fault is not characterised.** What is established is that a no-argument struct-returning function returned wrong bytes and the same type from a two-argument function did not (VL-123). No GCCMVS assembler listing was read and no reproducer outside ONFLY was built. `onffzer` was the only such function in ONFLY, so the rule has nothing else to be tested against (VL-127).
- **Liveness is device-specific.** It is proven for a batch job writing to a directly-allocated `10D` punch. It says nothing about MVS spooled output, which §3.1 measured to be the opposite.
- **One K, one network, one seed set.** FR-SIM-10 is swept on x86 (K ∈ {7, 50}); on MVS only K = 50 was run.
- **Wall clock.** The timings above are from the third and fourth runs: V6's liveness figures from **run 4 (JOB 328)**, V7's clip recorded during **run 3 (JOB 322)** under D-418. The second run's timings are void: the development host was suspended mid-job and its clock jumped two hours. That is recorded rather than quietly dropped. **Run 1's liveness figures are valid too** and are reported beside run 4's in SRS Section 9.2 under D-436; VL-135 holds both and says why the difference between them measures nothing: different binaries, a host under different load, and a punch-write count that counts observed file growth rather than channel programs, so it tracks how long the job ran.

### 6.3 The MVS runs, and why there were four

| Run | Job | Binary | MVS clock, `IEF403I` to `IEF404I` | Outcome |
|---|---|---|---|---|
| 1 | JOB 320 | before D-412/D-413 | 07.23.56 → 07.43.04, 1,148 s | complete; the first liveness measurement, `+28.3 s` / `+1148.1 s` / 1,027 of 1,028 (VL-135); stream differed from x86 in 200 lines |
| 2 | JOB 321 | after D-412/D-413 | 08.16.11 → 13.10.18, **void** | host suspended mid-job; timings void, harvest short. The job itself completed and its bytes were recovered from the punch. The banner gap is the suspension, not the job |
| 3 | JOB 322 | same as run 2 | 13.12.59 → 13.33.50, 1,251 s | complete and clean. **Byte-identical to run 2**, which is what established build-sensitivity rather than run-to-run nondeterminism (VL-124). V7's clip was recorded here; its liveness timings appear in no document |
| 4 | JOB 328 | after the D-420 fix | 13.41.07 → 13.57.56, 1,009 s | complete and clean; the one the results above are from. V5 passes; `+31.3 s` / `+1011.3 s` / 1020 of 1020 (VL-135) |

**The job numbers and the MVS clock were added on 2026-09-17 under D-436**, after
the liveness figures in this table's run 1 row were found standing unattributed
in SRS Section 9.2 while row V6 above carried run 4's. They are recovered
evidence, not a new run: `pch/pch10d.txt` appends, so it still held all four
streams, and `prt/prt00e.txt` still held every JES2 banner. The MVS clock column
is the guest's own and is independent of the host-side figures in V6 and VL-135,
which is what makes it a check on them rather than a restatement: 1,148 s
against `+1148.1 s` on run 1, and 1,009 s against `+1011.3 s` on run 4, the
excess in each being submission latency plus the two-second printer poll.

## 7. Related docs

- `docs/plan/2026-09-17-phase-g-stage5-mvs-live-view.md` — P-25, the plan of record
- `docs/plan/2026-09-16-phase-g-live-view.md` — P-17, the five-stage plan
- `docs/implementations/2026-09-17-phase-g-stages-2-3-4-live-view.md` — Stages 2–4
- `docs/implementations/2026-09-15-phase-e-slice-1-mvs-simulation.md` — ACC-5 row 6
- `docs/implementations/2026-09-17-phase-g-liveness-figure-reconciliation.md` — D-436, which reconciled §6.1's V6 figures with SRS §9.2's
- `docs/ONFLY-SRS.md` §4.7, §8.3 row 6, §8.4, §8.5 TU-11, §9.2 Phase G, A.1 D-436, Appendix D VL-135
