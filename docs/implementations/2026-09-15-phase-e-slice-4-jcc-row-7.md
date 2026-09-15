# 2026-09-15 — Phase E slice 4: a second compiler, and what it found

| Field | Value |
|---|---|
| Date | 2026-09-15 |
| Author | ONFLY senior engineer |
| Phase / gate | Phase E — MVS MVP |
| Owner decisions relied on | D-279, D-281, D-282, D-283, D-284, D-285, D-286, D-291 |
| Requirements touched | ACC-5, ACC-2, TX-01, TX-02, IR-COM-05, FR-LOD-02, FR-LOD-03, NR-02, NR-03, NR-09, NFR-OBS-01, C-04, A-04, A-05 |
| Open items closed | none |

## 1. Problem / motivation

Row 7 of the SRS Section 8.3 determinism matrix has been empty since the
matrix was written:

| Row | Platform | Backend | Compiler |
|---|---|---|---|
| 6 | TK5 MVS 3.8j | SOFT2C | GCCMVS — filled 2026-09-15 (D-255, VL-91) |
| 7 | TK5 MVS 3.8j | SOFT2C | **JCC** (engine-only if JCC cannot build the soft backend, VL-03) |

ACC-5 is satisfied only when every golden request produces the same
fingerprint in **every** row, and ACC-5 is a Phase E exit criterion. So
for as long as row 7 is empty, Phase E cannot exit — and, more
importantly, the project has no evidence separating two very different
propositions:

* the fingerprints are a property of **the source**, which is what
  IR-COM-05 and ACC-5 are for; and
* the fingerprints are a property of **one code generator** that every
  mainframe result so far happens to share.

Row 7 is the only check ONFLY has that distinguishes them. The engine
does integer work over a software float library, so a code-generation
difference could not appear as a small rounding difference. It would
appear as a wrong answer, or not at all.

What the project knew before this slice: JCC 1.50.00 is installed
(A-04, 12 datasets on TK5002, reached by STEPLIB rather than the
linklist) and it compiled, prelinked, linked and ran a 20-line probe at
Gate G0. What it did not know: whether JCC could compile SoftFloat 2c,
whether it could compile ONFLY's own C89, and whether its PRELINK stage
would accept a concatenated object input — `tools/mvstt01.py` records in
its own source that it could not be made to, with **two** objects. This
link has thirteen.

## 2. What changed

| File | Change |
|---|---|
| `tools/mvsjcc.py` | New. The whole JCC path: six probes that answer one question each, and the thirteen-unit build, run and comparison for row 7. |
| `tools/mvsrun.py` | `--install-net` copies the network off the card reader into a catalogued FB/80 dataset (D-286); row 6's `ONFNET` DD now reads that dataset instead of the reader; `NETS` gains a per-network dataset and job name. |
| `softfloat/derive2c.py` | The `(bits32 *)` cast on `float64_rem`'s `add64` call, as an `EDITS_C` entry with an expected count of 1 (D-285). |
| `softfloat/c2c/softfloat.c` | Regenerated from it. **Not edited by hand** — see §3.4. |
| `tests/run_mvsjcc.py` | New. Twenty-four cases: the link order, the shared installed network, D-284's PARM, the recorded run, and that every generated probe source is well-formed C. |
| `tools/mvstt01.py` | A note this session contradicted, corrected forward rather than deleted. |
| `Makefile` | `mvsjcc` added to the `test` target. |
| `docs/ONFLY-SRS.md` | D-279…D-286 and D-291 in Appendix A.1; Section 8.3 rows 6 and 7; VL-93 in Appendix D. |

## 3. Implementation approach

### 3.1 The toolchain was read off the machine, not guessed

`SYS2.PROCLIB(JCCCL)` was printed with IEBPTPCH before a single deck was
written. It is four steps, and two of them have no counterpart in the
GCCMVS path `tools/mvsbld.py` owns:

```
COMPILE  PGM=JCC      PARM='-I//DDN:JCCINCL //DDN:SYSIN -o -list=//DDN:SYSPRINT'
         STEPLIB JCC.LINKLIB; includes on JCCINCL/JCCINCS; object out
         on JCCOASM as FB/80; work file on JCCOUTPT
PRELINK  PGM=PRELINK  PARM='-r //DDN:L //DDN:O //DDN:I'
         L = JCC.OBJ (the C runtime), I = input, O = output
LKED     PGM=IEWL     PARM='NCAL,MAP,LIST,XREF,NORENT'
GO       PGM=GO       STEPLIB &&GOSET
```

Two consequences matter.

**JCC emits an object deck directly.** There is no assembly step, so
IFOX00 — the assembler that rejected GCCMVS's 64-bit output and is how
assumption A-05 was disproved — is not in this path at all.

**IEWL is given NCAL here and deliberately is not in the GCCMVS path.**
PRELINK has already resolved the C runtime out of `JCC.OBJ`, so there is
nothing left for the linkage editor to search. In the GCCMVS path the
linkage editor is what searches `PDPCLIB.NCALIB`, so NCAL there would
break it.

### 3.2 The link order is taken from row 6, not copied

`mvsjcc.run_deck()` calls `mvsrun._sources()` and asserts the resulting
member sequence equals `mvsrun.UNIT_MEMBERS`. Row 7 is only evidence if
it links what row 6 linked, and two copies of a link order is two link
orders. The GCCMVS flags in each entry's third field are ignored — they
are GCC spellings — and nothing else about the entries is changed: the
same `ONF_FP_SOFT2C` define, the same `generated/onf2cnm.h` prologue,
the same D-110 amalgamation of SoftFloat.

### 3.3 Column 71, and why the DD names are ONFH and LST

JCC's include path must name ONFLY's header library as well as its own,
and the whole PARM has to fit on one JCL card. With `INCLUDE` and
`SYSPRINT` the card is 78 columns. A quoted JCL string *can* be
continued — but only by taking every column through 71 as part of the
string, which makes the position of the break part of the compiler's
command line. That is precisely the class of silent, position-dependent
corruption D-93 exists to refuse, so the DD names were shortened and the
card is 70 columns.

### 3.4 Why the vendor cast went into the generator

`softfloat/c2c/softfloat.c` is **generated** — `softfloat/derive2c.py`
derives it from `third_party/SoftFloat-2c/softfloat/bits32/softfloat.c`
by a list of substitutions, each carrying the number of occurrences it
expects so that an upstream change is a failure rather than a partial
edit (D-123). The 2026-09-11 implementation note says of it, in the
file table: *New (generated). The derived library the builds compile.
Never edited by hand.*

D-285's cast was first written straight into the generated file, which
was wrong twice over: `make` regenerates that file from
`softfloat/derive2c.py`, so the cast would have vanished at the next
build with no message; and the *reason* for the cast would have lived
nowhere a future reader of the generator would find it. It is now an
`EDITS_C` entry with an expected count of 1, and
`python softfloat/derive2c.py --check` is what says the committed file
and the generator agree.

The same mistake was almost repeated at the level of evidence: the first
ONFJRUN ran from the hand-edited text. Its fingerprints were right, and
it is cited nowhere — see §6.4.

### 3.5 Six probes, each answering one question

The full link is 8,391 cards. Submitting it to learn "does JCC compile
SoftFloat at all" would spend a long compile on something three units
can say. Each probe below was written after the previous one's answer,
and each is still in `tools/mvsjcc.py` so the findings are reproducible.

| Probe | Question | Cost |
|---|---|---|
| `--probe` | Does JCC compile the SoftFloat 2c amalgamation, plain ONFLY C89, and will PRELINK take a concatenation? | 5,874 cards |
| `--ddprobe` | Which `fopen` spelling does JCC's libc honour, and does it split a PARM into argv? | 100 cards |
| `--mini warn|typebad|type` | Does JCC's RC 1 mean "warning" or "no object"? | 3 × ~95 cards |
| `--rdrprobe` | Can JCC open a unit-record DD in any mode? | 95 cards |
| `--ccprobe` | Which predefined macros does JCC define? (D-291) | 186 cards |
| `--run` | Row 7 itself | 8,383 cards |

## 4. Numerical details

None of this slice changes any arithmetic. The one source change,
D-285's `(bits32 *)` cast, is semantically null: `sigMean0` is declared
`sbits32` and `add64`'s fifth parameter is `bits32 *`, the two types
have the same width and the same representation on a two's-complement
host, the cast changes the pointer's type and not its value, and the
datum is read back through the signed lvalue two lines later exactly as
before. A compiler that accepted the line before the cast cannot
generate different code after it — which is a claim the re-run of row 6
and the x86 suite test rather than assert.

## 5. Design decisions

Four owner decisions were needed, each taken through AskUserQuestion
after the relevant fact had been **measured** rather than estimated.

**D-284 — the DD spelling.** The engine opens `DD:ONFNET`, PDPCLIB's
spelling (D-86). JCC's libc returns NULL for it. Rather than guess, the
probe tried four spellings and reported what each did; only
`//DDN:ONFNET` opened, and it read `7B899583` — EBCDIC `#inc` — proving
a real open of a real dataset rather than a handle that reads nothing.
The owner chose to pass the three names as arguments, which D-86 and
D-223 already allow, so **no engine source changed at all** and row 7
runs byte-identical source to row 6. The engineer flagged that JCC's
PARM-to-argv splitting was unmeasured; it was then measured, and gives
`argc=5` with `argv[2..4]` holding the three names.

**D-285 — one line of vendor SoftFloat.** The first full link left
F64LT, F64LE, F64MUL, F64SUB and F64ADD unresolved, and PRELINK's map
showed no `SF2C` CSECT at all: the SoftFloat unit had contributed
nothing. JCC had reported RC 1 on it — seven warnings and one "type
error" — and the remedy's size depended entirely on which of those
suppressed the object. Three four-line programs settled it:

| probe | diagnostic | JCC RC | object? | result |
|---|---|---|---|---|
| `warn` | `warning: unsigned operand of unary -` | 0 | yes | ran, `negu=4294967293` |
| `typebad` | `type error in argument 1 to 'put'` | **1** | **no** | LKED RC 4, `main` unresolved, GO flushed |
| `type` | the same with a cast | 0 | yes | ran, `v=7` |

So warnings are harmless and one dead vendor function — ONFLY's float
API never calls `float64_rem` — was suppressing the entire translation
unit. The owner chose the cast in the repository copy over a JCC-only
patch, so that every platform compiles the same text and row 7 is a
claim about identical source.

**D-286 — where the network comes from.** Row 7 then built clean and
answered `ONF108E NETWORK DATASET UNREADABLE: //DDN:ONFNET`, with the
step accounting showing `10C.......0`. `--rdrprobe` established that
JCC's `fopen` returns NULL on the unit-record device in **every** mode
tried: `rb`, `r` and `rb,type=record`. The owner chose to install the
network as a catalogued FB/80 dataset and have **both** rows read it,
so the compiler stays the only difference between them. This is not a
retreat from Gate G2: the raw card reader is still the transport that
brings the network onto the system (D-150), and what changed is that
jobs read an installed copy, exactly as slice 3 already installs ONFNAM
and both load modules. The transport also cannot corrupt the claim,
because FR-LOD-02 has the engine verify magic, sentinel, version, header
CRC, declared length and payload CRC before it simulates: a wrong byte
ends the step at ONF104E or ONF107E rather than producing a wrong
fingerprint quietly.

**D-283 — serialization.** The x86 science and the lab work do not
overlap, so ACC-6's timing is measured on an otherwise quiet host.

## 6. Verification

Every figure below was produced on 2026-09-15, in the session that wrote
this document.

### 6.1 Off-MVS, before anything was submitted

```
$ python tests/run_mvsjcc.py
  ok   ONFJRUN passes mvsub.check_cards                     8383 cards, longest 80
  ok   every JCL card is inside column 71                   0 over
  ok   ONFJRUN compiles UNIT_MEMBERS, in order              13 units, last ONFLYENG
  ok   member names are <=8 and unique ignoring case (C-04) 13 members
  ok   one JCC compile step per unit                        13 COMP steps
  ok   PRELINK reads every object as one concatenation      13 objects on the I DD
  ok   IEWL is given NCAL (PRELINK resolved the runtime)    SYS2.PROCLIB(JCCCL)'s own PARM
  ok   row 7 ONFNET is the installed dataset                HERC01.ONFLY.ENET
  ok   row 6 ONFNET is the same dataset                     HERC01.ONFLY.ENET
  ok   neither row names the reader unit                    no unit-record DD in either GO step
  ok   GO carries D-284's three names, in argv order        //   PARM='RUN //DDN:ONFNET //DDN:ONFREQ //DDN:ONFRSP'
  ...
run_mvsjcc: 21 passed, 0 failed
```

`python softfloat/derive2c.py --check` reports *4 generated files match
the templates*, which is what says D-285's cast reached
`softfloat/c2c/softfloat.c` **through the generator**. That file is
generated and is never edited by hand; the cast was first written into
it directly and that was wrong — it would have been silently reverted by
the next `make`.

### 6.2 The four measurements, each on TK5, each a separate job

**JCC's fopen spelling and its PARM handling** — `python
tools/mvsjcc.py --ddprobe`:

```
DDPROBE DD:ONFNET      FOPEN-NULL
DDPROBE //DDN:ONFNET   OPEN read=4 7B899583
DDPROBE DDN:ONFNET     FOPEN-NULL
DDPROBE dd:onfnet      FOPEN-NULL
ARGVPROBE argc=5
ARGVPROBE argv[0]=<GO>       argv[1]=<RUN>
ARGVPROBE argv[2]=<//DDN:ONFNET>
ARGVPROBE argv[3]=<//DDN:ONFREQ>
ARGVPROBE argv[4]=<//DDN:ONFRSP>
```

`7B899583` is EBCDIC `#inc`: the open was real and so was the read.

**What JCC's RC 1 means** — `python tools/mvsjcc.py --mini
warn|typebad|type`, three four-line programs:

| probe | diagnostic | JCC RC | object? | GO |
|---|---|---|---|---|
| `warn` | `warning: unsigned operand of unary -` | 0 | yes | ran, `negu=4294967293` |
| `typebad` | `type error in argument 1 to 'put'` | **1** | **no** | LKED RC 4, `main` unresolved, flushed |
| `type` | the same with `(unsigned int *)` | 0 | yes | ran, `v=7` |

**Whether JCC can read a unit-record DD** — `python tools/mvsjcc.py
--rdrprobe`, with the reader loaded with the network:

```
RDRPROBE mode=rb               fopen-NULL
RDRPROBE mode=r                fopen-NULL
RDRPROBE mode=rb,type=record   fopen-NULL
RDRPROBE no mode opened the reader
```

**That PRELINK takes a concatenation** — `python tools/mvsjcc.py
--probe` put three objects on one `I` DD and PRELINK ended `COND CODE
0000`; the full run then did the same with thirteen.

### 6.3 What the failures looked like before the fixes

Both are recorded because each was a *silent* failure mode — a job that
ends with a return code saying nothing about the cause.

Before D-285, the link ended `LKED RC 0004` with five `IEW0461`
warnings, and PRELINK's map contained **no `SF2C` CSECT at all**:

```
Mapping ONFFP2C   ST000054
Mapping F64LT     ST000055     <- references, never definitions
Mapping F64LE     ST000056
Mapping F64MUL    ST000057
Mapping F64SUB    ST000058
Mapping F64ADD    ST000059
```

Before D-286, the link was clean at `LKED RC 0000` and the engine
answered:

```
ONF108E NETWORK DATASET UNREADABLE: //DDN:ONFNET
```

with the step accounting showing `10C.......0` — nothing read from the
card reader — and `GO ... COND CODE 0012`.

### 6.4 Row 7 itself

`python tools/mvsjcc.py --run --out data/phase-e/jcc`, job ONFJRUN,
8,383 cards, thirteen translation units. **Every one of its 22 steps
ended `COND CODE 0000`:**

```
 8.52.51 ONFJRUN SCRATCH  IEFBR14  RC= 0000     8.52.55 COMP9    JCC  RC= 0000
 8.52.51 ONFJRUN ALLOC    IEFBR14  RC= 0000     8.52.55 COMP10   JCC  RC= 0000
 8.52.51 ONFJRUN WRITEH   IEBUPDTE RC= 0000     8.52.56 COMP11   JCC  RC= 0000
 8.52.51 ONFJRUN WRITEC   IEBUPDTE RC= 0000     8.52.56 COMP12   JCC  RC= 0000
 8.52.53 ONFJRUN COMP1    JCC      RC= 0000     8.52.56 COMP13   JCC  RC= 0000
 8.52.53 ONFJRUN COMP2    JCC      RC= 0000     8.52.57 PRELINK       RC= 0000
 8.52.54 ONFJRUN COMP3..8 JCC      RC= 0000     8.52.57 LKED     IEWL RC= 0000
                                                 8.52.57 SCRATCH2     RC= 0000
                                                 9.11.09 GO           RC= 0000
                                                 9.11.09 DUMP  IDCAMS RC= 0000
ONF302I STEP SUMMARY: 5 OK, 0 WARN, 0 ERROR
ONF301I request 1 FP=6C3F7272   2 FP=BAF81D91   3 FP=F9C7EE77
        request 4 FP=4FD0ED1E   5 FP=C4C320BC
```

COMP1 is the SoftFloat 2c amalgamation, and RC 0000 is D-285 working:
the same step read `COND CODE 0001` before the cast, and wrote no
object.

`python tools/mvsjcc.py --compare data/phase-e/jcc data/phase-d/x86w`:

```
=== ACC-5 row 7: TK5 MVS 3.8j / SOFT2C / JCC ===
  note record 1..5: raw NO   binary(8..411) yes  translated yes
         chr[0:8] got e2e4c7d940404040 ('SUGR    ' as EBCDIC), want 5355475220202020
  raw=False  binary=True  translated=True

=== ACC-5 row 7 vs the Section 8.4 fingerprints ===
  ok   G-15  fp=6C3F7272  golden=6C3F7272
  ok   G-16  fp=BAF81D91  golden=BAF81D91
  ok   G-17  fp=F9C7EE77  golden=F9C7EE77
  ok   G-18  fp=4FD0ED1E  golden=4FD0ED1E
  ok   G-19  fp=C4C320BC  golden=C4C320BC
mvsjcc: ACC-5 row 7 PASS
```

`raw=False` is expected and is not a weakening: the response record's
one code-page-dependent field is `ONF-STIM-CODE`, and D-261 fixed how
identity is judged across an EBCDIC and an ASCII host. Every other byte
matches with no translation at all.

**Two runs, not one.** The first ONFJRUN produced these same five
fingerprints from a `softfloat/c2c/softfloat.c` that had been edited by
hand. That file is generated, so the cast was moved into
`softfloat/derive2c.py` and the job was submitted again from the
regenerated text. The figures above are the second run's. The first is
not cited anywhere, because a result from source the repository does not
hold is not a result about the repository.

### 6.5 What row 7 found that no single-compiler row could

The whole argument for row 7 is that a second code generator can
disagree where one cannot. It did not disagree about any number — but
it did expose an NFR-OBS-01 shortfall that had been latent since the
manifest was written. Under JCC:

```
ONF001I NETWORK LOADED N=501 E=10783 CRC=4577D74E
ONF002I RUN MANIFEST
ONF002I   ENGINE VERSION  0.5.0
ONF002I   FLOAT BACKEND   SOFT2C
ONF002I   COMPILER        UNKNOWN      <-- NFR-OBS-01 requires this
ONF002I   PLATFORM        UNKNOWN      <--
ONF002I   MODE            SIMULATE
ONF002I   NET FORMAT      1.1
ONF002I   HEADER CRC      B05B9E6A
ONF002I   PAYLOAD CRC     4577D74E
ONF002I   N               501
ONF002I   E               10783
ONF002I   NS NR           14 2
ONF002I   DT              100 US
ONF002I   DT BITS         3FB999999999999A
ONF002I   DELAY REFRACT   18 22 STEPS
ONF002I   BIAS ROWS       9
ONF002I   BYTES NEED      171768 255688
```

**Exactly two fields are wrong, and the rest are right.** The format
version, both CRCs, the neuron and edge counts, the stimulus and readout
counts, the timestep in microseconds and as its binary64 bit pattern,
the delay and refractory step counts, the compensating table's row count
and both byte figures are all correct. `ONF_CCID` keys off `__GNUC__`,
`__IBMC__` and `__MVS__`; `ONF_PLATID` off `__MVS__`, `__s390x__` and
`_WIN32`; JCC defines none of the six.

NFR-OBS-01 says the manifest *shall* carry compiler identification, and
the comment above `ONF_CCID` says why: *the same source produces
different object code under GCCMVS, JCC, gcc and clang … a result that
does not name its compiler cannot be compared with another.* The row
whose purpose is to be a different compiler is therefore the row that
could not say so. D-291 resolves it by asking JCC which macros it does
define, rather than asserting an answer from the deck.

### 6.6 D-285 measured, not merely argued

Section 4 argues the cast cannot change generated code. Arguments of
that shape are how silent numerical regressions get in, so it was also
measured on x86-64 Windows 11, mingw32 gcc, after the regeneration:

```
$ mingw32-make c2c
run_c2c: SoftFloat 2c bits32 vs TestFloat -- 6 of 6 operations passed,
         260376 cases checked, 18408 NaN cases skipped (VL-11)
# tst2c 0 of 1854 vectors wrong

$ mingw32-make tt02
run_tt02: 18 of 18 operation runs passed, 781128 cases checked,
          55224 NaN cases skipped (VL-11)

$ mingw32-make lint liclint col80 c04 c04mvs sub mvsrun mvsjcc names
lint_nr05: 64 files scanned, 1 excluded, 0 violations
lint_col80: 73 files scanned, all within 80 columns (D-93)
lint_c04: every external satisfies C-04 (both object sets)
run_sub: 16 passed   run_mvsrun: 47 passed   run_mvsjcc: 24 passed
run_names: 21 passed
```

`python softfloat/derive2c.py --check` reports *4 generated files match
the templates*, which is what makes the first three lines a statement
about the committed tree rather than about a working copy.

### 6.7 What is NOT proven

- **Row 7 is one backend, one network and five requests.** It is
  SOFT2C only — NR-03 puts SoftFloat 2c on MVS and there is no 3e or
  native MVS build to compare — on `srext` only, over G-15 … G-19.
  The fourteen `path` requests of row 6 have no JCC counterpart.
- **JCC has no TT-01 or TT-02 result.** Gate G1 closed on GCCMVS
  (VL-29, VL-30). What row 7 shows is that the *engine* agrees; the
  float library's own conformance under JCC was not measured, and
  VL-03's caveat about JCC's scope stands for that.
- **A-05 was never tested for JCC.** GCCMVS's 64-bit failure was found
  through IFOX00, which is not in JCC's path at all. Nothing here says
  whether JCC's `long long` is correct — the MVS build uses SoftFloat
  2c precisely so that it need not be.
- **The transport differs from row 6's original.** Both rows now read
  an installed dataset (D-286). What Gate G2 measured — the raw card
  reader moving the network onto the system — is upstream of that and
  unchanged, and FR-LOD-02's CRC gate stands between the copy and any
  claim, but no ONFLY job now reads the reader directly except the
  demonstrations.
- **Hercules is an emulator.** VL-01's argument about QEMU applies in
  the same form: nothing here is a real-hardware, z/OS or Enterprise
  COBOL result.
- **D-285's cast is argued, not exhaustively proven, to be neutral.**
  The argument is that it changes a pointer's type and not its value,
  between two types of the same width; the evidence is that every
  platform's results are unchanged after it. That is strong for the
  platforms re-run in this session and silent about any that were not.

## 7. Related docs

- SRS Section 8.3 (determinism matrix), 8.5 (TX-01, TX-02), 6.4 (ACC-5),
  3.2 (FR-LOD-02, FR-LOD-03), Appendix A.1 (D-279…D-286), Appendix D
- [2026-09-15 — Phase E slice 1](2026-09-15-phase-e-slice-1-mvs-simulation.md)
- [2026-09-15 — Phase E slice 3](2026-09-15-phase-e-slice-3-buzz.md)
- [2026-09-11 — Gate G1 on MVS](2026-09-11-gate-g1-on-mvs.md)
