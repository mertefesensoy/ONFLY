# 2026-09-17 — Phase G, live view Stage 5: the MVS half

| Field | Value |
|---|---|
| Status | **Draft for owner approval.** No ONFLY code is written until it is approved |
| Phase | Phase G — transaction demonstrator (second MVP), live-view component |
| Owner decisions relied on | D-128 (what "live" means), D-139 (what is emitted), D-140 (caller-driven chunking), D-344…D-346, D-366 (P-17 approved; Stages 2–5 to be approved individually), D-377 (P-21, Stages 2–4), **D-403** (this session's scope), **D-404** (TK5 may be started) |
| Requirements touched | IR-STM-01…04, FR-SIM-10, IR-COM-05, ACC-5 row 6, NR-05, C-04, NFR-OBS-01 |
| Open items | none opened or closed. TBD-19 was closed by D-139/D-140; this builds on it |
| Proposal ID | **P-25** (Appendix A.2) |

---

## 1. Problem / motivation

P-17, approved as D-366, laid out the live view in five stages and said of the
last one:

> **Stage 5 — the MVS half.** The same chunked driver on TK5, and a fingerprint
> panel showing the x86 and MVS runs agreeing. Deliberately last: it is the
> highest-risk piece, because MVS spools job output rather than streaming it,
> and the transport for mid-job output is unproven.

Stages 1 to 4 landed on 2026-09-17 (D-374…D-389) and the component now works
end to end **on x86-64 only**. The live view is the third of Phase G's three
components and the only one whose mainframe half is missing; the other two are
the `EXEC CICS` transaction (built 2026-09-17, D-391…D-402) and the 3270 flow
under INTERCOMM (unbuilt).

What Stage 5 has to establish is narrower than "MVS can draw a picture". It is:

1. **The engine streams on MVS at all.** `onfrqb`/`onfrqc`/`onfrqe` — the split
   request sequence Stage 1 introduced — has never been compiled by GCCMVS, and
   neither has the ONFSTM emitter. Whether the chunked path builds and runs
   there is unknown until it is tried.
2. **Chunking does not move an answer on MVS.** FR-SIM-10 requires the response
   to be identical for every K. It is tested on x86 (TU-10, TU-11) and on no
   other platform.
3. **The output can leave MVS while the job is still running.** Without this,
   an MVS "live view" is a recording played back afterwards — exactly what D-128
   ruled out.

Point 3 was the unmeasured risk. It is now measured; see Section 2.

---

## 2. What the probe measured (this session, TK5 MVS 3.8j under Hercules)

Nothing in this section is inferred. Every line is from a run in this session,
after the owner authorised starting the lab (D-404). The probe lives in the
session scratchpad, not the repository, following the precedent VL-117 set.

### 2.1 Every SYSOUT device belongs to JES2

From the Hercules HTTP console, before any job was submitted:

```
$DU
$HASP000 READER1   00C INACTIVE      $HASP000 PRINTER1  00E INACTIVE
$HASP000 PRINTER2  00F INACTIVE      $HASP000 PRINTER3  002 INACTIVE
$HASP000 PUNCH1    00D INACTIVE

D U,,,00C,8
UNIT TYPE STATUS       UNIT TYPE STATUS
00C  2540 A            00D  2540 A
00E  1403 A            00F  1403 A
```

All four unit-record devices are **A — allocated**, to JES2. So every route
through `SYSOUT=` is spooled, and spooled output does not reach the host until
the job ends. That eliminates the obvious answer.

### 2.2 `10D` is a punch that JES2 does not own

```
D U,,,10C,4
UNIT TYPE STATUS       UNIT TYPE STATUS
10C  2540 O            10D  2540 O
```

Online, unallocated, named by no JES2 device. `tools/mvseng.py` already reads
`10C` as a **device** for the reader transport, for exactly this reason. `10D`
is its punch counterpart, configured in `conf/tk5.cnf` as

```
010D 3525 pch/pch10d.txt ascii
```

— Hercules translates EBCDIC to ASCII on the way out and appends to a plain
host file.

### 2.3 A batch job can allocate it, and the host file grows mid-job

A GCCMVS compile-link-go job with

```
//ONFSTM   DD UNIT=10D,
//            DCB=(RECFM=F,LRECL=80,BLKSIZE=80)
```

wrote twelve cards with a CPU burn between them. Every step ended `COND CODE
0000`, GO included. The host sampled `pch/pch10d.txt` every 250 ms:

```
probe: job END banner at t=16.8s
probe: 12 size changes
   t=  1.51s     331 bytes      t=  9.53s     379 bytes
   t=  3.01s     339 bytes      t= 10.78s     387 bytes
   t=  4.51s     347 bytes      t= 11.79s     395 bytes
   t=  5.52s     355 bytes      t= 13.29s     403 bytes
   t=  7.02s     363 bytes      t= 14.54s     412 bytes
   t=  8.28s     371 bytes      t= 15.55s     421 bytes
probe: VERDICT LIVE -- 12 of 12 size changes happened before the job ended
```

One card every ~1.25 s, tracking the burn loop, all of it before the job
ended. **This is a live channel off MVS.** P-17's risk row "MVS cannot stream
mid-job" is refuted for this device.

### 2.4 A line over 80 columns is silently truncated

The same job wrote four lines of 79, 80, 81 and 200 characters. What arrived:

```
card 0 len= 79 b'0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ01234...0123456'
card 1 len= 80 b'0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ01234...01234567'
card 2 len= 80 b'0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ01234...01234567'
card 3 len= 80 b'0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ01234...01234567'
```

One card per `fprintf`, no split, no message, `COND CODE 0000`. The 81st and
the 120 bytes past column 80 are **gone**. This is the D-93 failure class —
silent truncation of a record — and D-93 is why ONFLY sources are linted to 80
columns in the first place.

Hercules strips trailing blanks, so a short card arrives at its true length:
the 79-character line came back as 79 bytes, not padded to 80. That matters
for Section 6's byte comparison.

### 2.5 Only one line type is affected

Measured on x86-64 in this session — `build/onflyeng_nat.exe` with
`PARM='STREAM=50'` over the five `srext` golden requests:

```
  ONFSC  n=1000  longest=1976   over80=797
  ONFSE  n=5     longest=20     over80=0
  ONFSH  n=5     longest=42     over80=0
  ONFSR  n=5     longest=10     over80=0
  ONFSU  n=1000  longest=49     over80=0
```

`ONFSU` carries `nr` membrane values and `nr` is 2, so it is 49 characters and
will stay short. `ONFSC` carries up to `n` sparse pairs and `n` is 501, so it
reaches 1,976 characters and **797 of its 1,000 lines would be truncated on
MVS**. Everything else fits with room to spare.

### 2.6 One finding about the probe itself, worth keeping

The probe's first version built its test string with `'A' + (j % 26)` and
produced `ABCDEFGHI` followed by seven junk bytes. In EBCDIC the letters are
not contiguous — A–I are 0xC1–0xC9, J–R 0xD1–0xD9, S–Z 0xE2–0xE9 — so `'A' + 9`
is not `'J'`. The garbage was the probe's arithmetic, not the transport's
translation. The same mistake inside a real emitter would present as a
transport fault and be debugged in the wrong place.

---

## 3. What is built

### 3.1 The `ONFSC` continuation (`engine/src/onflyeng.c`)

The one format change. `onfesc` emits at most `ONF_STMPAIR` sparse pairs on an
`ONFSC` line; any remaining pairs continue on `ONFSD` lines carrying the same
`chunk` and `step`:

```
ONFSC chunk step nfired idx delta idx delta ...
ONFSD chunk step idx delta idx delta ...
ONFSD chunk step idx delta idx delta ...
ONFSU chunk step u-hex ...
```

Three properties are deliberate:

- **`nfired` keeps its present meaning** — the total for the chunk, not the
  count on its own line. A consumer reads pairs across `ONFSC` and its `ONFSD`
  continuations until it has `nfired` of them, so a lost or truncated line is
  *detectable* rather than silently absorbed. This is the whole reason for a
  separate tag rather than repeated `ONFSC` lines.
- **Both platforms emit it.** x86 wraps identically, so the two streams are
  byte-comparable and Section 6's strongest check is available at no cost. One
  format, not a mainframe dialect.
- **The bound is 80 columns, for everyone.** Not because x86 needs it, but
  because a second width is a second format. 80 is already the number D-93
  fixed for ONFLY source and the number the card reader enforces.

`ONF_STMPAIR` is chosen so the longest possible `ONFSC`/`ONFSD` line is ≤ 80:
the tag, chunk, step and `nfired` cost at most `5 + 1 + 6 + 1 + 6 + 1 + 4 = 24`
columns at the sizes IR-NET/FR-SIM permit, and a pair costs at most
`1 + 3 + 1 + 6 = 11`, so five pairs per line is safe with margin. The emitter
asserts the bound rather than trusting the arithmetic.

### 3.2 `tools/mvsstm.py` — the streaming job on TK5

Builds `tools/mvsrun.py`'s `run_deck` with two additions and nothing else
changed, so the engine under test is the same engine ACC-5 row 6 was filled
with:

```
go_parm = "STREAM=nnn"
//ONFSTM   DD UNIT=10D,
//            DCB=(RECFM=F,LRECL=80,BLKSIZE=80)
```

It submits, follows `pch/pch10d.txt` from the byte offset it recorded before
submitting, writes what arrives to `$(BUILD)/mvs-stream.txt`, and reports the
two timings that make the liveness claim checkable: **when the first `ONFSC`
arrived** and **when the job's END banner appeared**. The first must be smaller.

It does not truncate the lab's punch file. It records the offset and reads
forward, the way `mvsub.py` reads the printer.

### 3.3 `tools/liveview.py --follow FILE`

A second source for the viewer. Today it spawns `onflyeng_nat.exe` and follows
the ONFSTM it writes; `--follow` makes it follow a file **someone else** is
writing and never spawn anything. That is the smaller change and it keeps the
viewer blind to who produced the stream — `tools/mvsstm.py` does not have to
know how to draw, and `liveview.py` does not have to know how to drive TK5.

### 3.4 The fingerprint panel

P-17 names it: "a fingerprint panel showing the x86 and MVS runs agreeing".
It is a fourth panel — a text panel, not a plot — carrying, per request:

```
        request  x86-64/NATIVE   TK5/GCCMVS/SOFT2C   verdict
        G-16     BAF81D91        BAF81D91            AGREE
```

The x86 column is the Section 8.4 golden value, read from the golden suite, not
recomputed at draw time. The MVS column is the `ONFSE` fingerprint out of the
stream being followed. A disagreement is drawn in the panel, not hidden: this
panel is the only part of the picture that is evidence rather than
illustration.

### 3.5 `tests/test_strm.py` — two clauses added to TU-11

- **No line exceeds 80 columns**, for every K in a small sweep, on both the
  `path` and `srext` networks.
- **The continuation round-trips**: reassembling `ONFSC` plus its `ONFSD` lines
  yields exactly the pairs the unwrapped emitter produced, and the count
  reaches `nfired` exactly.

---

## 4. Numerical detail

None. No arithmetic changes, no constant changes, no change to the kernel's
update order, the propagators, the subnormal clamp or the accumulation order.
`ONF_STMPAIR` is a count of text fields on a line and enters no computation.

That is the claim, and Section 6 is arranged so that it is *checked* rather
than asserted: the five `srext` fingerprints must come out of this work
unchanged from `6C3F7272`, `BAF81D91`, `F9C7EE77`, `4FD0ED1E`, `C4C320BC`, on
all three x86 backends and on MVS. If any one of them moves, the change was not
numerically inert and nothing else in this plan proceeds.

---

## 5. Design decisions and the alternatives rejected

| Decision | Alternatives rejected, and why |
|---|---|
| Carrier is the `10D` punch | **SYSOUT**: every unit-record device is JES2's and JES2 spools (§2.1), so it cannot be live. **Tape 0480**: supports long records and would need no format change, but its liveness is unmeasured, it needs AWS block parsing on the host, and it is the network transport's own drive. **Console WTO**: genuinely live, but 126 characters per message and ~14,000 messages would swamp the operator console. **A new Hercules device**: MVS 3.8j has a static UCB table, so a device Hercules attaches at runtime that MVS was not sysgen'd for is unusable; 10E/10F have UCBs but no Hercules device, and at 132 columns would not solve §2.5 anyway |
| A new `ONFSD` tag | **Repeated `ONFSC` lines** with `nfired` redefined as the per-line count: no new tag, but it destroys the only consistency check the format has — a consumer could not tell a complete chunk from a truncated one. **Platform-specific wrapping** (MVS wraps, x86 does not): two formats, and the byte comparison in §6 becomes impossible |
| Both platforms wrap | Keeping x86 unwrapped would leave the MVS stream comparable to nothing |
| The viewer gains `--follow`, not `--mvs` | A `--mvs` mode would put TK5 submission inside the viewer and couple two tools that have no reason to know about each other |

---

## 6. Verification plan

Every row states platform, compiler and float backend, and what it does not
prove. Nothing is reported for a platform it was not run on.

| # | Claim | Command | Pass looks like | Will not prove |
|---|---|---|---|---|
| V1 | The format change is numerically inert | `mingw32-make test` | exit 0; the five `srext` and fourteen `path` golden fingerprints unchanged | x86-64 only, gcc/MinGW, NATIVE + SOFT3E + SOFT2C |
| V2 | No stream line exceeds 80 columns | `python tests/test_strm.py` | TU-11 passes including the two new clauses | x86-64; the bound is arithmetic, MVS is V5 |
| V3 | The engine builds on MVS with the chunked path | `python tools/mvsstm.py --build` | every step `COND CODE 0000` under GCCMVS | GCCMVS only; JCC is not attempted here |
| V4 | Chunking does not move the answer on MVS | `python tools/mvsstm.py --run --k 50` then `tests/run_tx.py --compare` | ONFRSP byte-identical to the x86-64 recording | one network, one K, SOFT2C |
| V5 | The MVS stream equals the x86 stream | `python tools/mvsstm.py --compare` | byte-identical after Hercules' trailing-blank strip | `srext` only |
| V6 | The MVS half is live | the same run | first `ONFSC` arrives strictly before the job's END banner, both timestamps printed | that MVS *spooled* output is not live; only that this device is |
| V7 | The picture draws from the MVS stream | `python tools/liveview.py --follow …` | frames drawn, fingerprint panel reads AGREE | a picture is not evidence; V1–V6 are |

V4 is the gate. If the MVS response is not byte-identical to x86's, this is not
a feature that failed — it is ACC-5 row 6 failing — and nothing else is drawn
or claimed until it holds.

---

## 7. Open questions for the owner

Asked with this plan, through AskUserQuestion, before any code is written.

1. **The `ONFSC` continuation form.** §3.1 proposes a new `ONFSD` tag with
   `nfired` unchanged. This is **new requirement text** in IR-STM-02 and
   IR-STM-03, which needs authorising in its own right — the same footing D-382
   put Section 4.7 on and D-401 put TX-06 on.
2. **Chunk size K, and which requests the MVS demo runs.** K is a request field
   under D-140, so a demo value is not a specification change, but the default
   is the owner's. K = 50 on the 1000 ms standard duration gives 200 chunks,
   about 2,800 cards for one request and about 14,000 for all five.
3. **Approval of this plan as the plan of record**, or changes to it first.

---

## 8. Related docs

- `docs/plan/2026-09-16-phase-g-live-view.md` — P-17, the five-stage plan
- `docs/plan/2026-09-16-phase-g-stages-2-3-4.md` — P-21, Stages 2–4
- `docs/implementations/2026-09-17-phase-g-stages-2-3-4-live-view.md`
- `docs/implementations/2026-09-15-phase-e-slice-1-mvs-simulation.md` — ACC-5 row 6
- `docs/ONFLY-SRS.md` §4.7 (IR-STM-01…04), §8.3 row 6, §8.4, §9.2 Phase G
