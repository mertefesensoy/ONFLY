# 2026-09-11 — Gate G1: what GCCMVS actually does with 64-bit integers

| Field | Value |
|---|---|
| Date | 2026-09-11 |
| Author | Claude (senior engineer), with owner decisions by Mert |
| Phase / gate | Gate G1 (SoftFloat port / toolchain), part of Gate G2 (transport) |
| Owner decisions relied on | D-97, D-98, D-99, D-100, D-101, D-102, D-103, D-104 |
| Requirements touched | NR-02, NR-03, NR-04, NR-14, A-05, C-06, IR-TRN-01, TT-01 |
| Open items closed | none. **Gate G1: still FAILED**, with a different and much sharper answer |

## 1. Problem / motivation

The previous session left Gate G1 failed and D-96 deferred the response. The
recorded failure was that GCCMVS could not compile a 64-bit addition at all:
`unable to generate reloads`, an internal compiler error, and nothing else
known. Three responses were on the table — rewrite TT-01 in 32-bit halves,
make JCC primary, or fetch a newer GCCMVS — and each of them commits either
an SRS text change or a fresh toolchain install.

Before choosing among them, one variable turned out never to have been moved.
**Every GCCMVS job in that session compiled with**

```
PARM='-S -ansi -pedantic-errors -Wno-long-long -o dd:out -'
```

with no `-O` flag at all, so at GCC 3.2.3's default. "Unable to generate
reloads" is a failure in GCC's *reload* pass, and on old back ends that pass
behaves very differently per optimisation level. Every figure in VL-15 and
VL-16 was therefore a statement about `-O0`, not about GCCMVS. D-97 chose to
measure that first.

## 2. What changed

| File | Change |
|---|---|
| `tools/mvsgcc.py` | New. Reproduces every measurement below against a running TK5: `--chars`, `--levels`, `--ops`, `--shifts`. |
| `tools/mvsub.py` | Refuses to submit unless Hercules is on codepage 819/1047 (D-103); `current_codepage()` and `check_codepage()` added. |
| `tools/mvstt01.py` | `--opt=` parameter, defaulting to `-O1` (D-100); the continued PARM card moved to column 5; an `a()` wrapper enforcing JCL's column-71 limit; header rewritten around the two host-configuration preconditions. |
| `tools/mvsbld.py` | New. The GCCMVS compile-assemble-link-go deck shape, factored out of mvstt01.py so D-104's job does not copy it. Adds the VB/255 include library and an assembler-listing knob. |
| `tools/mvssfs.py` | New. Submits tests/tstsfs.c with the two vendored SoftFloat units (D-104). |
| `softfloat/c89/stdint.h` | New. The NR-04 C89 shim; PDPCLIB has none. |
| `softfloat/c89/stdbool.h` | New. The NR-04 C89 shim; PDPCLIB has none. |
| `tests/tstsfs.c` | New. Drives SoftFloat's two jam functions so that every result must be 1. |
| `Makefile` | `sfs` and `shim` targets, both wired into `test`. |
| `docs/ONFLY-SRS.md` | D-97…D-104 in Appendix A.1; VL-17…VL-21 in Appendix D; VL-14 and VL-20 annotated as answered. |

Nothing under `C:\hercules-lab` is in the repository (D-89). The Hercules
codepage change (D-101) is host configuration and is **not** carried here.

## 3. Implementation approach

### 3.1 Three findings, each reached by being bitten

**The optimisation level is decisive (VL-17).** One job per level, on the
identical twelve-line addition that failed before:

| Level | Result |
|---|---|
| `-O0` | ICE, `unable to generate reloads`, at 3590 |
| **`-O1`** | **compiles, assembles, links, runs, returns 2^32 correctly** |
| `-O2` | ICE at 447 |
| `-O3` | ICE at 447 |
| `-Os` | ICE at 447 |

Two *different* defects, and `-O1` threads between them. That is also its
cost: ONFLY's MVS builds are now pinned to a level chosen to dodge compiler
bugs, not for code quality (D-100).

**The card reader mangles `|` (VL-18).** With `-O1` in place, TT-01's compile
walked past the old failure at line 67 and died at line 110 with

```
<stdin>:110: stray '\152' in program
```

on every line containing `|`. Octal 152 is 0x6A: Hercules' `default` codepage
delivers ASCII `|` as EBCDIC 0x6A, which GCCMVS will not lex. It is the only
character of ``| ! ^ [ ] { } ~ # @ $ \ ` `` it rejects, and ASCII `!` arrives
at its normal 0x5A so it is no substitute. `|=` builds the comparison mask in
`onficmu` and `onficms` and `||` guards every range check, so **no ONFLY
source could reach the compiler intact.**

`819/037` was tried first and traded one broken character for three: `|`
became acceptable while `^`, `[` and `]` moved to 0xB0, 0xBA and 0xBB and
were rejected. Array subscripts are everywhere, so CP037 is unusable. Those
two failures together pin GCCMVS's source character set to IBM-1047 by
measurement: it takes `|` at 0x4F and `[`, `]`, `^` where `default` puts them,
which are 0xAD, 0xBD and 0x5F. Under `819/1047` all thirteen lex (D-101).

**The real defect is silence, and it is the variable shift (VL-19).** With
both preconditions in place, `tests/tstint.c` compiled and assembled on MVS —
COMP1 and ASM1 both RC 0, the first ONFLY source ever to do so — and
`softfloat/onfint.c` died with a *third* distinct ICE, at 902, on the closing
brace of `onfirun`, the function whose switch holds every 64-bit operation at
once. Taking the operations one job each:

| Op | Result at `-O1` |
|---|---|
| MUL (64×64) | correct |
| DIV | assembler rejects the generated code (IFOX00 RC 8) |
| MOD | assembler rejects the generated code (IFOX00 RC 8) |
| SHL, constant count | correct, including 0, 1, 7, 9, 10, 11, 31, 32, 33, 63 |
| **SHL, variable count** | **WRONG in 32 of 64 counts** |
| SHR | correct |
| ADD | ICE at 6970 in this shape, though the minimal shape passes |
| SUB, AND, OR | correct |
| 32×32→64 multiply | correct |

The variable-shift failure is complete and clean: sweeping `a << n` for
n = 0…63 with `n` a variable, the wrong counts are exactly the 32 for which
the result's bit 63 should be set, and `a` has exactly 32 bits set.
**GCCMVS's variable 64-bit left shift always writes zero into bit 63.**

### 3.3 A probe that produced a false positive

The first version of that matrix reported two further defects that do not
exist: that MUL returns zero, and that `a << 7` drops bit 63. Both were the
probe's fault. It built its operand with

```c
a = (u64)0x01234567UL;
a = (a << 32) + (u64)0x89ABCDEFUL;   /* 64-bit '+' is itself defective */
```

so the scaffolding shared a defect with the subject, and there was no way to
tell which one had failed. Rebuilt with `|` — one of the operations measured
correct — and printing `a` back for checking inside the job, MUL and constant
SHL are both right.

This is recorded rather than quietly corrected. A probe that can manufacture
a false positive of exactly the kind it is hunting is the same failure class
as the blind golden fixture D-70 had to fix, and `_mk_a()` now carries the
reasoning so the next person does not rebuild the trap.

### 3.4 What that means for SoftFloat 3e (VL-20)

Every variable-count 64-bit left shift in the build ONFLY actually compiles:

| Site | Expression |
|---|---|
| `s_normSubnormalF64Sig.c:48` | `sig<<shiftDist` |
| `s_normRoundPackToF64.c:51` | `sig<<(shiftDist - 10)` |
| `s_normRoundPackToF64.c:54` | `sig<<shiftDist` |
| `s_shiftRightJam64.c:46` | `a<<(-dist & 63)`, feeding the sticky bit |
| `s_shortShiftRightJam64.c:45` | `((uint_fast64_t) 1<<dist) - 1` |
| `softfloat/onfsub.c:120` | `sigDiff<<shiftDist` |

These are the normalisation, rounding and sticky-bit paths: the places where
a dropped top bit changes a *result*, not merely a flag. At `dist = 63` the
`shortShiftRightJam64` mask turns from 0x7FFF…F into 0xFFFF…F, which is not a
rounding nuance but a different number.

So the prediction was that SoftFloat 3e built by GCCMVS computes wrong
binary64 values silently. **D-104 then measured it, and the prediction was
wrong in the direction that matters — see §3.6.**

### 3.6 What SoftFloat 3e actually does under GCCMVS (VL-21)

The NR-04 shims were written and the vendored sources submitted unmodified.

| Unit | Result |
|---|---|
| `tests/tstsfs.c` | **compiled and assembled, RC 0** — the shims work on MVS |
| `s_shortShiftRightJam64.c` | **ICE at 6970** |
| `s_shiftRightJam64.c` | compiled, then `IFO188 @@UCMPDI IS AN UNDEFINED SYMBOL` |

SoftFloat never reaches the point of computing anything, so the failure is
loud. Behind that one assembler message are two separate defects.

**PDPCLIB has no 64-bit runtime helpers.** A minimal assembly declaring
`@@UCMPDI` (`__ucmpdi2`, unsigned 64-bit compare), `@@UDIVDI` (`__udivdi3`)
and `@@UMODDI` (`__umoddi3`) EXTRN, linked against `PDPCLIB.NCALIB`, left all
three unresolved:

```
@@UCMPDI       $UNRESOLVED
@@UDIVDI       $UNRESOLVED
@@UMODDI       $UNRESOLVED
IEW0132 ERROR - SYMBOL PRINTED IS AN UNRESOLVED EXTERNAL REFERENCE.
```

That answers VL-14 and D-84 definitively. It also explains VL-19's DIV and
MOD rejections: the same defect with the other two names.

**GCCMVS asks for them the wrong way.** The generated assembler contains

```
         L     15,=A(@@UCMPDI)
               =A(@@UCMPDI)
```

An A-type address constant must resolve inside the assembly; an external
routine needs `=V(...)` or an `EXTRN`. So the failure surfaces at *assembly*
time as an undefined symbol rather than cleanly at link time as an
unresolved reference, which is why VL-19 recorded "the assembler rejects the
output" without knowing what it was rejecting.

The consequence is decisive for Gate G1: `a != 0` on a `uint64_t` compiles
to a call to `@@UCMPDI`, that expression is pervasive in SoftFloat, and
there is nothing on the system to link it to.

NR-03 and D-06 anticipate exactly this case.

### 3.5 A JCL limit that is not the card limit

Adding ` -O1` to the PARM pushed the closing apostrophe to column 74. The
card was still inside the reader's 80-column limit, so D-93's `col80` lint
could not see it, but a JCL *field* must end by column 71 because column 72
is the continuation indicator. MVS read an unterminated string and rejected
the job with `IEF629I INCORRECT USE OF APOSTROPHE IN THE PARM FIELD`.

`mvstt01.py` now builds cards through a wrapper that raises on any card
beginning `//` longer than 71 columns. Data cards written into an inline
stream are not JCL and keep the full 80.

## 4. Numerical details

The operand pair is `a = 0x0123456789ABCDEF`, `b = 0x00000000FEDCBA98`, chosen
so every nibble of `a` is distinct and a dropped or duplicated half shows up
in the printed value instead of being hidden by symmetry.

The variable left-shift defect is exact, and the sweep characterises it
completely rather than sampling it. Write `s(n) = a << n` evaluated with `n`
a variable. For every n in 0…63, GCCMVS returns

```
  s_mvs(n) = (a · 2^n  mod 2^64)  with bit 63 forced to 0
```

so `s_mvs(n)` differs from the true value in **bit 63 alone**, and only when
that bit should have been 1. Bit 63 of the true result is bit 63−n of `a`, so
the count n fails exactly when `a` has bit 63−n set. The operand
`a = 0x0123456789ABCDEF` has popcount 32, and **32 of the 64 counts failed** —
the observed failure set is precisely the predicted one, which is what makes
this a characterisation rather than a list of symptoms.

Two consequences follow directly, and both matter more than the arithmetic:

- A test using a small operand, or checking only the low 32 bits, passes. The
  defect is invisible unless a set bit is driven into position 63.
- The same counts written as **compile-time constants** are all correct, so
  reading the source for `<<` is not enough to find the exposure. Only the
  variable-count sites are affected, which is why VL-20 enumerates those
  specifically instead of all shifts.

## 5. Design decisions

D-97 (measure the optimisation level before choosing a structural response),
D-98 (NR-04 shims next), D-99 (authorise the codepage change), D-101 (amend it
to `819/1047` once `819/037` was measured and found to break three characters),
D-100 (`-O1` becomes the committed level), D-102 (measure the shift behaviour
before writing the shims, so NR-03 would be invoked on a measurement rather
than a prediction), D-103 (the transport refuses a wrong codepage).

D-103 follows D-93's shape deliberately. A wrong codepage does not announce
itself: the deck is accepted, the job runs, and the compile fails on a source
line, so the time goes into reading C rather than into reading configuration.
A warning was rejected for the same reason D-70 exists — a warning that can be
scrolled past is not a check. An unreachable console is refused rather than
assumed good, since every lab operation here already depends on it.

D-99 is kept in the log rather than rewritten, because its premise — that 0x4F
is GCCMVS's `|` — was the thing that needed measuring and proved right. Only
the table chosen to deliver it was wrong.

The character fix was taken as a lab configuration change rather than as a
source change, and the alternative of removing `|` from ONFLY's C was rejected
by the owner as hiding a transport fault inside the engine. A `cp_updt` user
table was rejected as non-persistent.

## 6. Verification

**Platform for every MVS result:** MVS 3.8j TK5 with Update 5 under SDL
Hercules 4.9.1.11612-SDL-gee86c4de on x86-64 Windows 11, compiler GCCMVS
(GCC 3.2.3) at `-O1`, Hercules codepage `819/1047`. Every figure came from a
job submitted in this session and read back from `prt/prt00e.txt`.

```bash
python tools/mvsgcc.py
```

reproduces all four measurements: the character set, the optimisation-level
table, the 64-bit operation matrix and the shift sweep. Individual parts run
as `--chars`, `--levels`, `--ops`, `--shifts`. `python tools/mvstt01.py`
submits TT-01 itself, and `python tools/mvssfs.py` submits the SoftFloat
units of D-104. Every one of these refuses to run if Hercules is not on
codepage 819/1047 (D-103).

```bash
mingw32-make test
```

x86-64, MinGW gcc, SOFT and NATIVE backends.

### What these results do not prove

- **Gate G1 is not passed.** TT-01 has still never run on MVS: `onfirun` ICEs.
  TT-02 has not been attempted. Both halves of the exit criterion are open.
- **No SoftFloat object exists on MVS, so nothing about SoftFloat's numerical
  behaviour there has been measured.** Two of its source files were submitted;
  one ICEd and one was rejected by the assembler. `tests/tstint.c` and
  `tests/tstsfs.c` compiled and assembled, but neither was linked or run,
  because the units they depend on did not build.
- **The variable-shift defect has not been observed inside SoftFloat.** It was
  measured in isolated probes (VL-19) and the affected call sites were read
  from the source (VL-20). Whether it would change a rounding decision in
  practice is unknown and now unknowable on this compiler, since the code
  containing those sites cannot be built.
- **The NR-04 shims are proven on x86 and, for `stdint.h` only, on MVS.**
  `make shim` forces the whole x86 SoftFloat build through them with
  bit-identical results; on MVS only `tests/tstsfs.c` consumed `<stdint.h>`,
  and `stdbool.h` was transported into the library but never included by
  anything.
- **The `-O1` results are `-O1` results.** VL-15's and VL-16's findings were
  taken at the default level and are not superseded except where VL-19 says so.
- **Every MVS result here is conditional on host configuration the repository
  does not carry.** A Hercules restart returns the codepage to `default` and
  silently reintroduces the `|` fault.
- **Nothing here concerns s390x, z/OS or real IBM Z.** VL-01 and VL-04 stand.
- The x86 suite proves x86 behaviour. It says nothing about MVS, which is the
  entire reason Gate G1 exists.

## 7. Related docs

- `docs/ONFLY-SRS.md` — Section 9.1 (Gate G1), Appendix A.1 (D-97…D-101),
  Appendix D (VL-17, VL-18, VL-19), NR-02/NR-03/NR-04/NR-14, risk R-01.
- `docs/implementations/2026-09-11-gate-g1-on-mvs.md` — the lab itself, and the
  default-level measurements this note builds on.
- `docs/implementations/2026-09-11-tt01-and-onflyeng.md` — TT-01 on x86.
