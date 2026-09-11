# 2026-09-11 — TT-01, the Gate G1 gap, and the minimal ONFLYENG

| Field | Value |
|---|---|
| Date | 2026-09-11 |
| Author | Claude (senior engineer), with owner decisions by Mert |
| Phase / gate | Gate G1 preparation, plus the IR-TRN-03 and NFR-OBS-01 engine items |
| Owner decisions relied on | D-76, D-77, D-78, D-79, D-80, D-81, D-82, D-83, D-84, D-85, D-86 |
| Requirements touched | NR-04, NR-11, NR-14, A-05, C-04, IR-TRN-03, IR-MSG-01, IR-JCL-04, FR-LOD-01…FR-LOD-05, NFR-OBS-01, NFR-REL-01, NFR-MNT-02, TT-01, TE-09 |
| Open items closed | none. TBC-06 was deliberately left open by D-77; VL-14 was added |

## 1. Problem / motivation

Three separate gaps, each of which would have failed quietly rather than loudly.

**TT-01 did not exist.** Gate G1's exit criterion in SRS Section 9.1 is "TT-01
and TT-02 pass under GCCMVS". TT-02 had been built (D-44). TT-01 had not — there
was no integer self-test anywhere in `tests/`. It had been deferred three times,
by D-48, D-53 and D-61, each time for good reasons, and each time on the
observation that its value is only realised when a GCCMVS build runs it. The
result was that the *earliest* unmet criterion in the whole D-24 ordering sat
unbuilt while Phase C work went ahead above it.

What TT-01 guards against is specific. S/370 has 32-bit registers and no 64-bit
integer instructions, so GCCMVS and JCC must synthesise every 64-bit multiply,
divide, shift and carry out of 32-bit pieces. Assumption A-05 asserts they do
this correctly and records itself **Unverified**; risk R-01 is that they do not.
SoftFloat's binary64 significand arithmetic is 64-bit, so a wrong shift would not
crash anything. It would produce a slightly different number, and a slightly
different number is a different fly.

**TT-02 was not reproducible from the repository.** `.gitignore`'s `build/` rule
also matched `third_party/**/build/`. Upstream ships a `build/<target>/Makefile`
and, for TestFloat, a `build/<target>/platform.h`; those are vendored *source*,
not build output, and `make testfloat` reads them. The count was unambiguous: 622
files tracked under `third_party/`, none of them under a `build/` directory. So
`mingw32-make testfloat` failed in any fresh clone, and TT-02 could only ever
have been run in the single checkout where the archive was first extracted. Half
of Gate G1's exit criterion was therefore not reproducible by anyone else.

**IR-TRN-03 and NFR-OBS-01 named a program that did not exist.** Both say
"ONFLYENG shall…", but `engine/src/` held only a library; the only `main()`
functions in the repository were test harnesses and `tools/runnet.c`. Verify-only
mode matters operationally: IR-TRN-02 asks Spike S2 to run at least ten transfers
per transport method and check each one, and without this mode "check" means
running a simulation, which on TK5 costs minutes per attempt.

## 2. What changed

| File | Change |
|---|---|
| `tools/genint.py` | New. Generates the TT-01 known-answer table: 149 vectors in nine operation groups, every expectation computed from exact Python integers on x86. |
| `generated/onfivec.h` | New, generated. The table, plus the `ONFI_OP_*` and `ONFI_CMP_*` constants. Never to be edited by hand (IR-COM-01). |
| `softfloat/onfint.h` | New. Declares `onfitst`, `onfirun`, `onfignm`, `onfignc` and the `ONFI_*` result codes; states why the file sits beside SoftFloat yet depends on none of it. |
| `softfloat/onfint.c` | New. Runs the vectors. Builds operands by multiply and extracts results by shift *and* by divide, so the two extraction paths cannot conspire with a broken one. |
| `tests/tstint.c` | New. The TT-01 binary: prints what the compiler actually computed for every vector, then runs the engine's own startup check. |
| `tests/run_tt01.py` | New. Recomputes every vector in Python from the operands in the generated header, so the table is checked rather than trusted. |
| `engine/src/onflyeng.c` | New. The minimal ONFLYENG of D-78: startup self-test, load and verify, run manifest, `PARM='VERIFY'`. |
| `tests/run_eng.py` | New. TE-09. Replays `run_dec.py`'s corruption cases through the program, checks every NFR-OBS-01 manifest field, and proves structurally that no simulation happens. |
| `tools/lint_c04.py` | Skips symbols containing a dot — the optimiser's own clones, which are not C identifiers (D-83). |
| `.gitignore` | Narrow negation tracking upstream's four vendored `build/<target>` source files while leaving `.o`, `.a` and `.exe` ignored (D-80). |
| `third_party/{SoftFloat,TestFloat}-3e/build/Win32-MinGW/{Makefile,platform.h}` | Added, byte-identical to upstream. |
| `Makefile` | New `tt01` and `eng` targets; `test` now runs L0 before L1 per Section 8.1; `c04` now covers `onfint.c`. |
| `docs/ONFLY-SRS.md` | D-76…D-86 in Appendix A.1; VL-14 in Appendix D; ONF905S and ONF108E in Appendix E; TBC-06's row annotated as deliberately still open. |

## 3. Implementation approach

### 3.1 The circularity problem in TT-01, and how it is broken

A self-test for a compiler's 64-bit arithmetic has to be written in that same
compiler's 64-bit arithmetic. The obvious trap is a test that agrees with the bug
it is meant to find.

Every operand and expectation in the generated table is stored as a pair of
32-bit halves, so the header contains no 64-bit literal at all — which also means
it needs no `LL` suffix and no `UINT64_C`, neither of which C89 has and neither
of which PDPCLIB provides (C-06). But turning a pair into a 64-bit value, and a
64-bit value back into a pair, are themselves 64-bit operations. If both used
shifts, a compiler whose 64-bit shift were wrong could build a wrong operand,
read the wrong result back with the same wrong shift, and agree with itself.

The three paths therefore lean on deliberately different instructions:

| Path | Operation used |
|---|---|
| building a value from halves | multiply by 2³², then add the low half |
| extracting the high half | shift right by 32 |
| extracting it a second time | divide by 2³² |

A vector passes only when the shift path and the divide path produce the same
high half *and* that half matches the table. For the two to conspire, a
compiler's synthesised shift and its synthesised divide would have to be wrong in
exactly matching ways, and those are the two least alike routines in 64-bit
synthesis. 2³² itself is built without a shift, a multiply, or a 64-bit literal:
it is `0xFFFFFFFF` widened and incremented.

### 3.2 Contracts

`int onfitst(void)` — runs every vector against the table. Returns 0 on success,
otherwise `op * 1000 + (idx + 1)`, identifying the first failing vector; the
1-based index keeps the code non-zero for vector 0 of group 0. No I/O, no
allocation, no writable static data, so it is reentrant for the future CICS path
(NFR-MNT-02). This is the function ONFLYENG calls at startup.

`int onfirun(int op, int idx, onf_u32 *rhi, onf_u32 *rlo)` — computes one vector
and reports what the compiler produced. Returns `ONFI_OK`, `ONFI_RANGE`,
`ONFI_SPLIT` (the two high-half extractions disagreed) or `ONFI_SIGNED` (the
unsigned-to-signed round trip was not faithful). `*rhi` and `*rlo` are written
whenever `op` and `idx` are in range, including on a cross-check failure, so a
caller can print what was produced rather than only that something was wrong.

`const char *onfignm(int op)` / `int onfignc(int op)` — the group's name (eight
characters or fewer, so an ONF901S message needs no continuation line under
IR-MSG-01) and its vector count.

### 3.3 ONFLYENG's flow

1. Parse `argv[1]` as the PARM and `argv[2]` as the dataset; absent, the dataset
   is `DD:ONFNET`, PDPCLIB's spelling of the DD IR-JCL-01 allocates (D-86).
2. `onfitst()`. On failure, ONF901S naming the group and vector, return code 16.
   Section 8.1's rule that L0 passes first is enforced *by the program*, not only
   by the test suite.
3. Read the dataset. Unreadable, absent or empty gives ONF108E and return code 12
   (D-85).
4. `onfdec` performs FR-LOD-02's checks in order. The first failure gives its
   ONF1xxE and return code 12. The memory limit is passed as 0 — unlimited —
   because TBD-14 has not fixed the TK5 region and inventing a number here would
   pre-empt it.
5. ONF001I, then the ONF002I manifest.
6. Under VERIFY: ONF003I, return code 0. Otherwise ONF905S, return code 16.

One reading of NFR-OBS-01 deserves stating, because a reviewer will notice it.
The requirement says the manifest is printed "at the start of every run", but
four of the fields it demands — both network CRCs, N and E — do not exist until
the network has been read and verified. The manifest is therefore printed
immediately after the load succeeds and before any other work, and a run whose
load fails produces its ONF1xxE or ONF108E instead. That is the only order in
which the requirement can be satisfied at all; it is recorded here rather than
left for someone to rediscover as an apparent defect.

### 3.4 What "without simulating" is proved by

IR-TRN-03's phrase is checked structurally rather than by timing: `run_eng.py`
requires the linked program to contain no `onfrun` symbol at all. A program that
does not contain the kernel cannot have called it, which is a stronger and far
more stable statement than any measurement of elapsed time. The check reports
itself as skipped, rather than passing, where `nm` is unavailable.

## 4. Numerical details

TT-01 contains no floating-point arithmetic; the numerics are exact integer
identities, evaluated in Python over the unbounded integers and reduced modulo
2⁶⁴, which is what an unsigned 64-bit type must do. Writing `M = 2⁶⁴`:

| Group | Identity checked | Vectors |
|---|---|---|
| MUL | `(a · b) mod M` | 14 |
| DIV | `⌊a / b⌋`, b ≠ 0 | 12 |
| MOD | `a − b·⌊a / b⌋` | 12 |
| SHL | `(a · 2ⁿ) mod M`, 0 ≤ n ≤ 63 | 42 |
| SHR | `⌊a / 2ⁿ⌋`, 0 ≤ n ≤ 63 | 42 |
| ADD | `(a + b) mod M` | 7 |
| SUB | `(a − b) mod M` | 6 |
| CMPU | the six relational operators on a, b ∈ [0, M) | 8 |
| CMPS | the same on their two's-complement readings, a, b ∈ [−M/2, M/2) | 6 |

**Why these particular operands.** The cases are not random; each targets a
documented synthesis failure.

- *Multiply.* A 64×64 product is assembled from four 32×32 partial products whose
  carries must cross the word boundary. The cases drive each partial product
  alone, then all four together, then the wrapping cases (2³²·2³², 2⁶³·2).
- *Divide.* The 64/32 path and the 64/64 path are different routines; divisors
  above 2³² exercise the harder one. Divisor 1, a dividend below the divisor, and
  exact division are included because each is usually a special case in the
  synthesised routine.
- *Shifts.* Counts of 0, 1, 7, 31, 32, 33 and 63. A synthesised shift often
  implements a count below 32 as a pair of shifts by n and 32−n, which is wrong
  for n = 0, and treats 32 and above as a word exchange. Count 64 is never tested:
  C leaves a shift by the operand width undefined, and the generator enforces
  0 ≤ n ≤ 63.
- *Comparisons.* Both directions of the classic confusion. `CMPU` includes pairs
  where bit 63 is set, which is the only place an unsigned comparison performed as
  a signed one differs; `CMPS` includes pairs that straddle the 32-bit boundary.
  All six relational operators are evaluated rather than three and their
  negations, because a compiler that gets `<` right and `>=` wrong as its
  negation is a real failure mode that checking half the operators would miss.

**NR-11 compliance.** Every arithmetic vector is unsigned, so no result depends
on signed overflow and nothing negative is ever shifted or divided. Signed
64-bit values appear only in CMPS, and only under comparison, which cannot
overflow. C89 leaves the unsigned-to-signed conversion of a value above the
signed maximum *implementation-defined* rather than undefined; `onfirun` converts
back and requires the round trip to be exact, which turns that assumption into a
tested condition.

**The mutation evidence.** The bound worth stating is not "149 vectors pass" but
"these vectors detect these faults". Three faults were injected into scratch
copies — the committed source was never modified:

| Injected fault | Detected on |
|---|---|
| shift count masked to 5 bits (the S/370 word-boundary bug) | exactly the SHL vectors with count ≥ 32, and no others |
| unsigned comparison performed as signed | exactly the CMPU pairs with bit 63 set |
| multiply off by one | the MUL group broadly |

In every case both callers caught it and named the failing group and vector.

## 5. Design decisions

Every decision below was made by the owner through a question, not by the
engineer; the engineer's recommendation is noted where it differed or where the
reasoning is worth recording.

- **D-76, scope.** Gate G1's gap over Phase C calibration, SR-EXT extraction, or
  Phase D. Calibration is blocked behind TBC-06, extraction behind calibration,
  and Phase D behind a QEMU toolchain this host does not have.
- **D-77, TBC-06 stays open.** Shiu's `model.py` is vendored at `reference/shiu/`
  but their connectome data is not, `brian2` is not installed, and the published
  figure is not reachable offline. SR-CAL-05 forbids widening tolerances after the
  fact, so the reference curve must be real before it is used; a number invented
  from any of those gaps would be a guess wearing the word "reference".
- **D-78, minimal ONFLYENG.** A full main including the request loop was offered
  and declined: Section 9.2 makes Phase E depend on Phase C and Phase D, neither
  finished. Library entry points alone were also declined, because TE-09 must
  exercise the *mode* IR-TRN-03 names, not a function standing in for it.
- **D-79, one vector table with two callers.** NR-14 describes an L0 test suite
  and Appendix E describes a startup known-answer check; the SRS never says
  whether they are the same vectors. One table answers both and makes drift
  impossible. A startup-only check was declined for inverting Section 8.1.
- **D-80, fix the TT-02 reproducibility defect now** rather than record it as a
  follow-up.
- **D-81, ONF905S.** A non-VERIFY run could have ended at return code 0 having
  simulated nothing; NFR-REL-01 forbids exactly that silence. Reusing ONF904S was
  declined because it means "integer width check failed" and would have told an
  operator something untrue.
- **D-83, the C-04 lint skips dotted names.** `onfirun.part.0` is GCC's
  partial-inlining clone. A dot cannot appear in a C identifier, so no such name
  reaches the MVS linkage editor, and measuring it against C-04 reported a defect
  that did not exist. Suppressing the clone with `-fno-partial-inlining` was
  declined because the lint would then inspect a build that differs from the one
  that ships.
- **D-84, keep the libgcc dependency.** `softfloat/onfint.o` is the only object in
  the engine that references `__udivdi3` and `__umoddi3` — SoftFloat's
  not-FAST_INT64 build genuinely avoids 64-bit division, and D-79's startup call
  is what pulls them in. Splitting the callers would have undone the single-table
  property D-79 chose. Recorded as VL-14.
- **D-85, ONF108E**, and **D-86, `DD:ONFNET` fallback.** The fallback is already
  correct against IR-JCL-01, so Phase E inherits a working path rather than a
  rewrite, while the argument form is what makes TE-09 verifiable on this host.

The naming of the generated tables (`onfvmul`…`onfvcms`) was an engineer's choice
forced by C-04: names built as `onfi_` + group label give `onfi_cmpu` and
`onfi_cmps`, nine characters and identical for the first eight, which is one
symbol to the MVS linkage editor.

## 6. Verification

All results below are from **x86-64 Windows 11, MinGW gcc (`-std=c89 -pedantic
-Wall -Wextra -Werror`), both the SOFT and NATIVE float backends**, in this
session.

```bash
mingw32-make test
```

Expect exit 0 and the closing line naming TT-01, TT-02, TU-01…TU-07, the kernel,
TE-01…TE-09, the ACC-5 golden suite and TP-01.

Individually:

```bash
mingw32-make tt01
```
Expect `run_tt01: ok   table, compiler and oracle agree on all 149 vectors` and
`run_tt01: ok   onfitst returned 0; no cross-check failure`.

```bash
mingw32-make eng
```
Expect `run_eng: 25 passed, 0 failed` on the soft backend and again on the
native one, including `IR-TRN-03 contains no kernel entry point  onfrun is
absent`.

```bash
mingw32-make testfloat
```
Expect `testfloat_gen.exe` to build **from a clean clone**, which is what D-80
restored; this was verified in a worktree that had none.

### What these results do not prove

- **Nothing here is an MVS, s390x or z/OS result.** TT-01's whole purpose is to
  run under GCCMVS and JCC at Gate G1; an x86 pass says only that the vectors and
  the oracle agree with each other on a compiler nobody doubted. Assumption A-05
  remains Unverified.
- **VL-14.** On MVS the engine's startup self-test references `__udivdi3` and
  `__umoddi3`. Whether GCCMVS and PDPCLIB supply them is unverified, so a TT-01
  pass on x86 says nothing about whether ONFLYENG will even link on MVS.
- **VL-11 still applies to TT-02**, which is unchanged by this work: its reference
  is built against the 8086 specialisation and excludes NaN cases.
- **TE-09's corruption cases run against `run_dec.py`'s synthetic 16-neuron
  network**, not the real MaleCNS data. That is appropriate — each case corrupts
  one header field — but it means the verify-only mode has been exercised on real
  data only in the single clean case reported by hand against
  `data/networks/onfnet-malecns-v1.0-path.bin`.
- **TE-08's memory-limit cases are skipped** by TE-09, because ONFLYENG passes an
  unlimited budget while TBD-14 is open. `make decode` still covers them at the
  decoder level.
- **No performance claim is made.** Verify-only mode is argued to be cheap because
  it allocates nothing proportional to E and links no kernel, not because it was
  timed on TK5.

## 7. Related docs

- `docs/ONFLY-SRS.md` — Section 8.1 (verification levels), Section 8.5 (TT-01,
  TE-09), Section 9.1 (Gate G1), Appendix A.1 (D-76…D-86), Appendix D (VL-14),
  Appendix E (ONF905S, ONF108E).
- `docs/implementations/2026-09-10-phase-b-foundations.md` — the float layer and
  decoder this builds on.
- `docs/implementations/2026-09-11-tt02-and-c04-lint.md` — TT-02 and the C-04
  lint as originally built.
- `third_party/MANIFEST.md` — provenance of the vendored SoftFloat and TestFloat
  trees whose build sources D-80 restored.
