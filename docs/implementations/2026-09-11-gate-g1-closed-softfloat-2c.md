# 2026-09-11 — Gate G1 closed: SoftFloat 2c runs on MVS 3.8j

| Field | Value |
|---|---|
| Date | 2026-09-11 |
| Author | Claude (senior engineer), with owner decisions by Mert |
| Phase / gate | **Gate G1 — CLOSED (D-119)**; part of Gate G0 (TBD-14) |
| Owner decisions relied on | D-105 … D-120 |
| Requirements touched | NR-02, NR-03, NR-04, NR-14 (amended), C-01, C-04, NFR-MEM-01, TT-01/32, TT-02 |
| Open items closed | **TBD-14 closed at 8M (D-116).** Gate G1 closed (D-119) |

This note continues `2026-09-11-gccmvs-64bit-matrix.md`, which established
*why* Release 3e cannot be used on MVS. This one is what replaced it.

## 1. Problem / motivation

Gate G1 asks whether GCCMVS can build and run a SoftFloat release. The
previous note answered that for Release 3e: **no**, for four independent
reasons (VL-19, VL-21) — internal compiler errors at four distinct points, a
silently wrong variable 64-bit left shift, no 64-bit runtime helpers in
PDPCLIB, and a code-generation bug asking for them the wrong way.

NR-03 has always prescribed the response: fall back to Release 2c, which
implements binary64 in 32-bit integers only. D-105 invoked it. Everything
below is what invoking it actually cost, and what it bought.

## 2. What changed

| File | Change |
|---|---|
| `third_party/SoftFloat-2c/` | New. Release 2c vendored whole and verbatim, 37 files. |
| `third_party/MANIFEST.md` | Provenance, SHA-256, and the fact that 2c's licence is **not** BSD. |
| `softfloat/derive2c.py`, `softfloat/c2c/` | ONFLY's 2c configuration, generated from upstream's templates. |
| `softfloat/c89/stdint.h`, `stdbool.h` | The NR-04 shims. PDPCLIB has neither. |
| `softfloat/derive3e.py`, `softfloat/onfprim.c` | Five 3e primitives under C-04 compliant names. |
| `tools/gen2cnm.py`, `gen3enm.py` | Generated C-04 rename prologues for both releases. |
| `tools/gen2cv.py`, `gentf2.py`, `gen32v.py` | Vector generators: Python-oracle, TestFloat, and 32-bit integer. |
| `tools/mvsbld.py` | The GCCMVS deck shape, factored out; amalgamation; per-source flags; region. |
| `tools/mvs2c.py`, `mvstf2.py`, `mvs32.py` | The three MVS jobs. |
| `tools/mvsub.py` | Refuses to submit on the wrong codepage (D-103). |
| `tools/lint_c04.py` | `--enforce-all`, global symbols only, `__`-prefixed exempt. |
| `tests/tst2c.c`, `tsttf2.c`, `tst32.c` | The three drivers, each run on both x86 and MVS. |
| `Makefile` | `c2c`, `tf2`, `tt0132`, `c04mvs`, `sfs`, `shim`, all wired into `test`. |
| `docs/ONFLY-SRS.md` | D-105…D-120; VL-22…VL-30; NR-14 and the G1 criterion amended; TBD-14 closed; G1 closed. |

## 3. Implementation approach

### 3.1 Prove it agrees before porting it (D-106)

Every ACC-5 fingerprint was computed with 3e. If 2c disagreed anywhere, every
fingerprint would change — a far larger decision than choosing a library. So
that was settled first, on x86, against TestFloat rather than against 3e
directly: two libraries agreeing with an independent oracle says more than two
agreeing with each other.

```
run_c2c: 6 of 6 operations passed, 260376 cases checked,
         18408 NaN cases skipped (VL-11)
```

`make tt02` runs 3e through the same generator and the same vectors, so
agreement between the two releases follows from both passing (VL-22).

### 3.2 Three obstacles, each measured rather than assumed

**The include names collide (VL-23).** GCCMVS resolves `#include "name"` to
the PDS member given by the first **eight** characters. 2c's `softfloat.h`,
`softfloat-macros` and `softfloat-specialize` therefore all name `SOFTFLOA`,
and three files cannot occupy one member. D-109 read the compiler's own
option list rather than guessing, and tested `-remap` — GCC's mechanism for
filesystems with very short names, which is exactly this situation. It is
accepted and **inert** on this port (VL-24). D-110 amalgamates instead: the
includes are inlined in order, at submit time, never to disk, so there is no
second copy of the source to drift from the first.

**The external names collide (VL-25).** With that fixed, 2c **compiled**
(RC 0) and Assembler XF rejected it:

```
IFO196  FLOAT64@ HAS BEEN PREVIOUSLY DEFINED
IFO196  FLOAT32@ HAS BEEN PREVIOUSLY DEFINED
IFO196  INT32@TO HAS BEEN PREVIOUSLY DEFINED
IFO189  INVALID ENTRY OPERAND, LINKAGE CANNOT BE PERFORMED
```

That is C-04 — external names at most eight characters, unique ignoring case
— meeting a library never written for it: 38 of 2c's 42 externals fall into
three colliding groups. D-111 renames them by a generated `#define` prologue,
applied on x86 too so the mechanism is exercised by the ordinary suite.

**Five of 3e's names are feature tests (VL-27).** Extending the same
treatment to 3e could not be done as instructed. Five of its thirteen
colliding names are written `#ifndef <name>` in both `primitives.h` and their
own `s_*.c` — upstream's extension point, where defining the name says "the
platform supplies this" and upstream omits **both** declaration and
definition. A `#define` meant as a rename would have *deleted* them. D-114
uses the extension point as designed: `softfloat/onfprim.c` carries
upstream's own bodies under compliant names, derived mechanically.

### 3.3 The lint is the part that lasts

The C-04 lint had reported SoftFloat's collisions since it was written and
enforced on nothing. That is exactly how 2c reached Assembler XF before
anyone noticed. It now enforces (D-111, D-113), and run against the
unrenamed object it reproduces the three groups the assembler found — so the
class is caught before a job is ever submitted.

Two boundaries are drawn deliberately, both from measurement:

- **Global symbols only.** 2c's file-local `addFloat64Sigs` and
  `roundAndPackFloat64` also collide at eight characters and Assembler XF
  accepted them without a word, because they are never ENTRY.
- **`__`-prefixed names exempt.** `__udivdi3` and `__umoddi3` are libgcc's,
  reserved to the implementation, not names this project chooses.

### 3.4 Sizing by measurement (D-115)

Every table size on offer was an estimate resting on one timing data point.
The real ceiling turned out to be below the smallest of them. By bisection:

| Vectors | Cards | Result |
|---|---|---|
| 3,000 | 10,187 | PASS |
| **4,500** | **13,187** | **PASS** |
| 5,250 | 14,687 | FAIL, `ABEND S878` |
| 12,000 | 28,187 | FAIL, `ABEND S878` |

Raising the JCL region does not lift it — 12,000 still ends S878 at
`REGION=16M` — so the binding constraint is GCCMVS's own storage inside a
24-bit address space, not the job's region.

That produced TBD-14's number as a by-product, measured with a bare IEFBR14
job per value: TK5 **accepts 8M and 16M** and **rejects 9M, 10M, 11M and 12M
with `ABEND S822`**. The installation limit refuses an explicit intermediate
request, while 16M is taken as asking for the whole address space.

### 3.5 What TT-01 had to become (D-118)

NR-14 required a **64-bit** integer self-test on every platform. Under NR-03
the MVS engine uses no 64-bit integer at all, so on MVS that asked for proof
about arithmetic the engine never performs — while the arithmetic it does
perform had no L0 check whatever. Both requirement texts were amended under
explicit authorisation, and TT-01/32 was written.

Its carry and borrow groups are the point. SoftFloat 2c never asks the
machine for a carry flag; it writes

```c
z1 = a1 + b1;  z0 = a0 + b0 + (z1 < a1);
```

so the carry is a **comparison**. A compiler wrong about either the wrapping
addition or that comparison would corrupt every wide value the library
builds, and a float test would report it far from its cause.

## 4. Numerical details

2c's `bits32` build carries a `float64` as two 32-bit halves and forms no
64-bit integer anywhere. That was verified by inspection before anything was
built on it: `bits32/softfloat.c`, `bits32/softfloat-macros` and the two
templates contain no occurrence of `bits64`, `sbits64`, `long long` or
`LIT64`.

Two configuration values are worth recording because both look like defects
and are not:

- **`float_detect_tininess` is left at upstream's `after_rounding`.** It
  gates only `float_raise(float_flag_underflow)` and never the returned
  value, and ONFLY discards flags (D-34, NR-10). Changing it would change
  nothing and would misrepresent the build.
- **NaN results are excluded from the Python-oracle vectors, not just NaN
  operands.** Python returns a NaN carrying the sign of its operands, so
  `-inf * -0.0` is `0xFFF8000000000000`, while ARM-VFPv2 default NaN (D-31,
  D-107) returns `0x7FF8000000000000` regardless. Neither is wrong. The first
  cut of the generator missed this and x86 caught it — six vectors of 1,860.

## 5. Design decisions

D-105 (invoke NR-03, vendor 2c), D-106 (prove agreement before porting),
D-107 (match D-31's NaN convention), D-108 (MVS before the backend),
D-109 (probe for another include mechanism), D-110 (amalgamate),
D-111 (rename, and make the lint enforce), D-112 (TT-02 with a shipped
table), D-113 and D-114 (3e too, using the extension point),
D-115 (measure the size), D-116 (TBD-14 at 8M), D-117 and D-118 (re-scope
TT-01), D-119 (close G1, note S1 separately), D-120 (finish on the report).

D-110 sets aside D-94's reasoning, which had rejected amalgamation for TT-01.
The distinction the owner authorised: this is a vendored library rather than
the engine source NFR-PRT-01 governs, and it is forced by a measured compiler
limit rather than chosen for convenience. Generating in memory rather than
into a file is what keeps D-94's actual worry — two forms of one source —
from arising at all.

## 6. Verification

**Platform for every MVS result:** MVS 3.8j TK5 with Update 5 under SDL
Hercules 4.9.1.11612-SDL-gee86c4de on x86-64 Windows 11; GCCMVS (GCC 3.2.3)
at `-O1`; Hercules codepage `819/1047`; float backend **SoftFloat 2c
bits32**. Every figure came from a job submitted in this session.

```bash
python tools/mvs32.py     # TT-01/32   -> 0 of 1068 vectors wrong
python tools/mvstf2.py --per-op 750   # TT-02 -> 0 of 4500 wrong
python tools/mvs2c.py     # known answers -> 0 of 1854 wrong
```

**Platform for every x86 result:** x86-64 Windows 11, MinGW gcc, backends as
named by each target.

```bash
mingw32-make test
```

### What these results do not prove

- **No ONFLY engine code has been compiled on MVS.** What runs there is the
  float library and three test drivers. The engine, the kernel, the decoder
  and ONFLYENG have never been built on MVS.
- **TT-02 on MVS is 4,500 cases against x86's 260,376** — 1.7%. Stratified
  across testfloat_gen's stream rather than a prefix, but a sample.
- **Four workarounds are load-bearing and none is in the repository:** the
  `-O1` pin (VL-17), the `819/1047` codepage (VL-18), the D-110 amalgamation
  and the D-111 renames. A Hercules restart silently reverts the codepage;
  `tools/mvsub.py` refuses to submit when it has (D-103).
- **SoftFloat 3e still fails on MVS** for the reasons in VL-21. C-04
  compliance removed one obstacle and touched none of the others.
- **2c and 3e are proven to agree on TestFloat's level-1 vectors, not
  universally.** 260,376 cases is very strong evidence, not a theorem.
- **No golden-suite fingerprint has been computed with 2c.** That needs an
  `onf_fp` backend, which does not exist; 2c's `float64` is a two-word struct
  rather than a scalar, so it is real work.
- **8M is what a job may request, not what a program can obtain.** A compile
  hit its own S878 ceiling well below it with `REGION=16M` in force.
- **Nothing here concerns s390x, z/OS or real IBM Z.** VL-01 and VL-04 stand.

## 7. Related docs

- `docs/ONFLY-SRS.md` — Section 9.1 (Gate G1, closed), NR-02…NR-04, NR-14
  (amended), C-04, Appendix A.1 (D-105…D-120), Appendix B (TBD-14, closed),
  Appendix D (VL-22…VL-30).
- `docs/implementations/2026-09-11-gccmvs-64bit-matrix.md` — why 3e cannot be
  used on MVS, which is what made all of this necessary.
- `docs/implementations/2026-09-11-gate-g1-on-mvs.md` — the lab itself.
- `third_party/MANIFEST.md` — provenance and the two different licences.
