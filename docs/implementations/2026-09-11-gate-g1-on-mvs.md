# 2026-09-11 — Gate G1 on real MVS: the lab, and why G1 failed

| Field | Value |
|---|---|
| Date | 2026-09-11 |
| Author | Claude (senior engineer), with owner decisions by Mert |
| Phase / gate | Gate G0 (environment), Gate G1 (SoftFloat/toolchain), part of Gate G2 (transport) |
| Owner decisions relied on | D-88, D-89, D-90, D-92, D-93, D-94, D-95 |
| Requirements touched | A-05, NR-02, NR-04, NR-14, C-06, IR-TRN-01, IR-JCL-01, TT-01 |
| Open items closed | P-07 closed by D-93. **A-05 disproved.** Gate G1: **FAILED** |

## 1. Problem / motivation

Gate G1's exit criterion is "TT-01 and TT-02 pass under GCCMVS". Everything
above L0 in Section 8.1 rests on it, and assumption A-05 — "GCCMVS synthesizes
correct 64-bit integer arithmetic for `long long` on S/370" — was recorded
**Unverified** from the beginning, with risk R-01 saying it might not.

No Hercules, no TK5 and no MVS existed on the development host, so the
criterion could not be evaluated at all. D-88 authorised standing the lab up.

## 2. What changed

| File | Change |
|---|---|
| `tools/lint_col80.py` | New. Fails any ONFLY-owned source over 80 columns (D-93). |
| `tools/mvsub.py` | New. Submits a deck to TK5's card reader and collects the job's printer output; refuses an over-length card. |
| `tools/mvstt01.py` | New. Generates the TT-01 job from the repository sources and submits it. |
| `tools/genint.py` | Emits each vector across two lines, and splits its own sha256 banner. |
| `layout/generate.py`, `softfloat/derive.py` | Banner and long-line wrapping so generated output stays within 80 columns. |
| six hand-written sources | Comment and argument rewrapping only. |
| `Makefile` | `col80` target, wired into `test`. |
| `docs/ONFLY-SRS.md` | D-88…D-95; VL-15, VL-16; A-05 marked disproved; P-07 closed. |

Nothing under `C:\hercules-lab` is in the repository (D-89).

## 3. Implementation approach

### 3.1 The lab

SDL Hercules 4.9.1.11612-SDL-gee86c4de and TK5 with Update 5, unpacked outside
the repository. TK5 bundles the *same* Hercules build, so the separate download
was redundant — recorded because it cost bandwidth and proves the version.

TK5 IPLs unattended: `scripts/ipl.rc` uses Hercules' automatic operator to
answer the console prompts, so no terminal is needed. This matters, because the
host has no 3270 client at all. The whole cycle is instead:

| Direction | Mechanism |
|---|---|
| in | `000C 3505 ... sockdev ascii trunc eof` — a deck sent to TCP 3505 |
| out | `000E 1403 prt/prt00e.txt` — a plain file |
| control | `/command` through the Hercules HTTP console on 8038 |

### 3.2 Three MVS traps, each found by being bitten

**Cards truncate at column 80, silently.** An 85-character card was submitted
to the running system to find out what `trunc` does. It arrived as exactly 80
characters, columns 81–85 discarded, with no error, no warning and no message;
the job ended normally. Eleven ONFLY sources were over the limit. D-93 closes
this with the `col80` lint — the wraps fix today, the lint fixes tomorrow.

**`/*` in column 1 ends an inline data stream.** Every C source opens with a
comment block, so `//SYSIN DD *` was terminated by the first card of the first
header and IEBUPDTE reported `IEB823I SYSIN HAS NO RECORDS`. The compile then
failed three steps later with `013-18`, member not found, where the cause was
no longer visible. `DD DATA,DLM='ZZ'` fixes it.

**A missing REGION makes JCC hang rather than fail.** Two probe jobs spun at
100% of a core and had to be cancelled before JCC's own JCL was read, where
every job carries `REGION=8M,TIME=1440`. With the region, the same job ran in
about a second.

### 3.3 A correction

I reported to the owner that GCCMVS "is not installed at all" because no
`GCC.*` dataset exists on any volume. That was wrong. GCCMVS on TK5 is the
`GCC` load module in `SYS2.LINKLIB` with `PDPCLIB.INCLUDE`, `PDPCLIB.MACLIB`
and `PDPCLIB.NCALIB`; the ZIP dataset is only the distribution archive. D-92
was decided on that wrong premise. It did no harm — JCC proved the transport
path — but the decision log should show the premise was mine and it was wrong.

## 4. Numerical / mechanical details

### 4.1 What JCC does

JCC compiled, linked and ran ONFLY-style C and returned, for
`v = (u64)0xFFFFFFFF; v = v + 1;` and `v * v`:

```
PROBEC 2p32hi=00000001 lo=00000000      (2**32, correct)
PROBEC sqhi=00000000 lo=00000000        ((2**32)**2 mod 2**64 = 0, correct)
```

### 4.2 What GCCMVS does

One operation per job, so that an ICE in one could not hide the others:

| Operation | Result |
|---|---|
| `a + b` | **Internal compiler error**, "unable to generate reloads" |
| `a - b` | compiles, links, runs |
| `a * b` | compiles; Assembler XF rejects the output (IFOX00 RC 8) |
| `a / b` | compiles; Assembler XF rejects the output (IFOX00 RC 8) |
| `a << 3`, `a >> 3` | compile, link, run |
| `a & b` | compiles, links, runs |
| assignment | compiles, links, runs |

Addition was then tested in four shapes, in case the register-allocation
failure was pattern-specific:

| Shape | Result |
|---|---|
| `return a + b;` | ICE |
| `r = a; r += b;` | ICE |
| `return a + (u64)1U;` | ICE |
| `r = a; r = r + b;` | ICE |
| 32-bit halves, carry propagated by hand | **compiles, links, runs, correct** |

The last row returned `ADDH1 hi=00000001 lo=00000000` for 0xFFFFFFFF + 1.

### 4.3 What that means

Two conclusions, and they point in opposite directions.

**A-05 is disproved and R-01 has materialised.** GCCMVS does not produce a
wrong 64-bit answer; it cannot compile 64-bit addition at all, in any form
tried, and its multiply and divide output is rejected by the assembler. The
failure is louder than the one the project feared, which is the better kind.

**The engine's chosen mitigation survives.** SoftFloat's not-FAST_INT64 build
carries values as 32-bit halves and propagates carries by hand, and that
pattern compiles and runs correctly. NR-02 and D-06 chose that build because
"S/370 has no 64-bit integers and GCCMVS must synthesise them". This
measurement shows the choice is load-bearing rather than merely prudent.

**And the irony worth recording:** TT-01 as written cannot be built by GCCMVS,
because `onfi2p32` adds. The test designed to detect bad 64-bit code generation
cannot be compiled by the compiler it was written to test. Whether TT-01 should
be rewritten in 32-bit halves — which would make it test the thing the engine
actually does, at the cost of no longer testing `long long` directly — is an
owner decision and is deliberately not taken here.

## 5. Design decisions

D-88 (stand the lab up), D-89 (outside the repository; the approved downloads),
D-90 (TT-01 before TT-02), D-92 (JCC first to prove the path — decided on my
incorrect premise, §3.3), D-93 (80 columns and the lint), D-94 (separate PDS
members and a real include path, with a probe first), D-95 (move to GCCMVS once
JCC had served its purpose).

D-94's two-translation-unit shape was not achieved under JCC. `JCCC`, `JCCCL`
and `JCCCLG` each build exactly one unit, and its prelink stage left the same
four runtime symbols unresolved whichever order the two objects were given in,
because independent prelinks build independent long-name mapping tables. The
owner chose to move to GCCMVS rather than continue, since Gate G1 names GCCMVS
and no JCC result can close it.

## 6. Verification

**Platform for every MVS result below:** MVS 3.8j TK5 with Update 5, under SDL
Hercules 4.9.1.11612-SDL-gee86c4de, on x86-64 Windows 11. Compilers as named.
Every figure was produced by a job submitted in this session and read back from
`prt/prt00e.txt`.

```bash
mingw32-make test
```
x86-64, MinGW gcc, SOFT and NATIVE backends: exits 0, including the new `col80`
lint, TT-01's 149 vectors and TE-01…TE-09.

Lab, reproducible by re-running the same tools:

```bash
python tools/mvstt01.py --print      # the generated deck, 997 cards
python tools/mvstt01.py              # submit it and read the result
```

### What these results do not prove

- **SoftFloat 3e has not been compiled under GCCMVS.** That is Spike S1 and was
  not attempted. VL-16 shows the *pattern* it relies on compiles; it does not
  show the library does. NR-04 also promises `stdint.h` and `stdbool.h` shims
  for SoftFloat and none exist in the repository yet.
- **TT-01 has not run on MVS under any compiler.** Under GCCMVS it cannot be
  compiled; under JCC the two units could not be linked.
- **TT-02 has not been attempted on MVS.**
- **No engine source has been compiled on MVS.** The claim in §4.3 that the
  engine's mitigation survives is about a code *pattern*, measured in isolation,
  not about the engine.
- **Nothing here concerns s390x or z/OS.** VL-01 and VL-04 still stand: Hercules
  timings are lab figures and say nothing about real IBM Z.
- The JCC results are JCC's. D-03 makes GCCMVS primary, and a JCC pass has never
  been able to close Gate G1.

## 7. Related docs

- `docs/ONFLY-SRS.md` — Section 9.1 (Gate G0, G1, G2), Appendix A.1 (D-88…D-95),
  Appendix D (VL-15, VL-16), the A-05 row in Section 2.6.
- `docs/implementations/2026-09-11-tt01-and-onflyeng.md` — TT-01 itself and the
  minimal ONFLYENG, both on x86.
