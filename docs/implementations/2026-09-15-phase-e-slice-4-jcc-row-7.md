# 2026-09-15 — Phase E slice 4: a second compiler, and what it found

| Field | Value |
|---|---|
| Date | 2026-09-15 |
| Author | ONFLY senior engineer |
| Phase / gate | Phase E — MVS MVP |
| Owner decisions relied on | D-279, D-281, D-282, D-283, D-284, D-285, D-286 |
| Requirements touched | ACC-5, IR-COM-05, FR-LOD-02, FR-LOD-03, NR-02, NR-03, NR-09, C-04, A-04, A-05 |
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
| `tools/mvsjcc.py` | New. The whole JCC path: five probes that answer one question each, and the thirteen-unit build, run and comparison for row 7. |
| `tools/mvsrun.py` | `--install-net` copies the network off the card reader into a catalogued FB/80 dataset (D-286); row 6's `ONFNET` DD now reads that dataset instead of the reader; `NETS` gains a per-network dataset and job name. |
| `softfloat/c2c/softfloat.c` | One `(bits32 *)` cast on `float64_rem`'s `add64` call (D-285), with the reason in place. |
| `docs/ONFLY-SRS.md` | D-279…D-286 in Appendix A.1; Section 8.3 row 7; Appendix D. |

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

### 3.4 Five probes, each answering one question

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
| `--run` | Row 7 itself | 8,390 cards |

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

*(Filled in below as each result lands; every figure is from this
session.)*

## 7. Related docs

- SRS Section 8.3 (determinism matrix), 8.5 (TX-01, TX-02), 6.4 (ACC-5),
  3.2 (FR-LOD-02, FR-LOD-03), Appendix A.1 (D-279…D-286), Appendix D
- [2026-09-15 — Phase E slice 1](2026-09-15-phase-e-slice-1-mvs-simulation.md)
- [2026-09-15 — Phase E slice 3](2026-09-15-phase-e-slice-3-buzz.md)
- [2026-09-11 — Gate G1 on MVS](2026-09-11-gate-g1-on-mvs.md)
