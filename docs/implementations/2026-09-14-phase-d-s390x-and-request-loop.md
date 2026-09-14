# 2026-09-14 — Phase D: Linux s390x, and the FR-BAT-01 STEP2 request loop

| Field | Value |
|---|---|
| Date | 2026-09-14 |
| Author | ONFLY engineering session |
| Phase / gate | **Phase D — Big-endian** (SRS Section 9.2) |
| Owner decisions relied on | D-214 … D-233 |
| Requirements touched | FR-LNX-01, FR-LNX-02, FR-BAT-01, FR-BAT-02, FR-BAT-05, FR-LOD-04, FR-LOD-05, IR-COM-01, IR-COM-04, IR-COM-05, IR-JCL-02, IR-JCL-03, IR-JCL-04, IR-TRN-03, NR-09, NR-11, NR-12, NR-14, NFR-OBS-01, NFR-PRT-01, ACC-5 |
| Open items closed | none |

## 1. Problem / motivation

Every result in this repository up to 2026-09-13 is **x86-64 little-endian**.
The whole design rests on a hypothesis about a machine nobody had run:
IR-NET-01 puts the network file in big-endian byte order; FR-LOD-05 forbids
pointer casts over the buffer and requires explicit byte shifts; `onfdec.c`
deliberately leaves the payload arrays big-endian and unconverted on the
grounds that a big-endian host could then use them directly; `onffpn.c`
assembles a binary64 bit pattern big-endian first and swaps it only on a
little-endian host.

None of that had been executed on a big-endian machine. If any of it were
wrong, the failure would surface for the first time inside Hercules during
Phase E — the slowest and least observable environment in the project. Phase
D exists to find those defects on a machine where a rebuild takes seconds.

A second gap emerged while planning the phase. TX-01 requires that "Linux
s390x and MVS response records are identical", but `engine/src/onflyeng.c`
states in its own header that the request/response loop is not there: D-78
built only IR-TRN-03's verify-only mode, leaving FR-BAT-01's STEP2 to Phase
E. **No build on any platform emitted a response record**, so TX-01 had no
comparand of any kind, not even an x86 one. The owner authorised bringing
STEP2 forward (D-221).

## 2. What changed

| File | Change |
|---|---|
| `Makefile` | `ONFPLAT` selects the one platform-specific line, `NATFLAGS` (D-218); out-of-tree `testfloat_gen` build for non-x86 platforms (D-225); `req` target; `eng` builds the `-DONF_NOREQ` variant; `golden` links the new module |
| `engine/include/onfreq.h` | Contract for the single copy of the request sequence: `struct onfrq`, `struct onfrz`, `onfsid`, `onfrqg`, `onfrqp`, `onfrq1` |
| `engine/src/onfreq.c` | The validation ordering, simulation and IR-COM-05 fingerprint; record encode and decode through the generated big-endian accessors |
| `engine/src/onflyeng.c` | FR-BAT-01 STEP2: streams ONFREQ into ONFRSP, ONF301I per request, ONF302I summary, IR-JCL-04 step return code; ONF906S; `-DONF_NOREQ` variant for TE-09 |
| `tests/tstgld.c` | Calls `onfrq1` instead of keeping its own copy of the sequence (D-224) |
| `tests/run_eng.py` | TE-09 proved twice: structurally on the variant, observationally on the shipped engine (D-228) |
| `tests/run_req.py` | New: the Section 8.4 suite through the loop, against the oracle, on every backend |
| `tests/run_tx.py` | New: records TX-01 and TX-02 evidence per platform and compares two recordings |
| `tools/mkreq.py` | New: IR-JCL-02 control cards into an ONFREQ dataset |
| `tools/tfgprep.py` | New: prepares out-of-tree build directories for `testfloat_gen` |
| `softfloat/tfgen/platform.h` | New: ONFLY-owned platform header for the stock SoftFloat/TestFloat reference build |
| `docs/ONFLY-SRS.md` | D-214 … D-228 in Appendix A.1; ONF906S added to Appendix E; ONF905S annotated |

## 3. Implementation approach

### 3.1 One build file, one platform-specific line

The Makefile's header said "the Linux s390x build has its own configuration",
implying a second build file. Measurement before writing any of it showed
that of 585 lines **exactly one** was x86-specific: `NATFLAGS`, carrying
`-msse2 -mfpmath=sse` for D-30's 32-bit mingw x87 problem and
`-DONF_FP_LITTLE` for the byte swap in `onffpn.c`. The 70 `.exe` suffixes are
cosmetic on Linux and no Python tool contains a Windows-ism.

So `ONFPLAT` selects a block and everything else is shared (D-218). The
default, `x86w`, reproduces the previous build exactly; `s390x` drops
`-msse2 -mfpmath=sse`, which has no meaning on z/Architecture, keeps
`-ffp-contract=off`, which s390x needs because it has a fused multiply-add
(MADBR) gcc will contract into, and **omits `-DONF_FP_LITTLE`** so that the
big-endian byte array `onffpn.c` builds is already in host order. An
unrecognised `ONFPLAT` is a hard `$(error)`.

### 3.2 The request sequence, in one place

`onfrq1` is the only copy of an **ordering**:

```
unknown stimulus → reserved stimulus → rate range → NR-12's
rate × dt ≤ 1,000,000 bound → duration range → simulate
```

followed by an IR-COM-05 fingerprint over whatever that ordering produced.
Two copies of an ordering do not diverge loudly — a drift shows up as a
changed fingerprint on one path only, which is the class of defect the
golden suite exists to catch and would instead be the cause of. D-224
therefore had `tests/tstgld.c` call this module rather than keep its own
copy.

**Contract.** `onfrq1` is a pure function of `(net, paycrc, maxms, request)`
except that it uses `*st` as scratch. `onfrun` resets the state at the start
of every run (FR-SIM-02), so one `st` may be reused across requests and the
results do not depend on processing order. That invariant is what lets
ONFLYENG loop over a dataset with one allocation, and ACC-5 depends on it: a
fingerprint must not depend on what ran before it. `onfrq1` never fails —
every rejection is a return code in the result, because a rejected request
still has to produce a response record and a fingerprint (G-13 is exactly
such a request).

`ms` arrives **already resolved**. Section 8.4's G-09 asks for "the header
maximum" and the C driver's table spells that as a negative sentinel;
resolving it is the caller's business, because a negative duration arriving
in a real ONFREQ record is a malformed request that must be rejected, not
reinterpreted as the maximum. Keeping the sentinel out of the module is what
keeps those two readings apart.

### 3.3 Streaming records

ONFLYENG reads one 412-byte record, processes it and writes one, rather than
loading the dataset. On MVS that is not a style preference: C-01 gives the
region single-digit megabytes and the network already consumes most of it, so
a design that read the whole request dataset first would work on x86 and fail
on the platform the MVP targets.

`onfrqp` writes **only** the response portion (IR-JCL-03) — offsets 0 to 15,
the request echo, arrive and leave untouched — and writes all 32 readout
entries, zeroing those at or above `outcount`. That last point matters for
TX-01: the bytes of a response record are then a function of the result and
nothing else, which is what makes a byte-for-byte comparison across platforms
mean something.

### 3.4 TestFloat on a platform with no vendored build

NR-14 requires the TestFloat suite to pass on every platform, but
`third_party/` ships only a Win32-MinGW build of `testfloat_gen`, and D-28
and D-35 commit `third_party/` to byte-identity with the published archives.

Both vendored Makefiles declare `SOURCE_DIR`, `SPECIALIZE_TYPE` and
`PLATFORM` with `?=` and put `-I.` — the build directory — first on the
include path. That is upstream's own mechanism for a new platform: a build
directory containing nothing but a `platform.h`. ONFLY supplies that
directory under `$(BUILD)`, outside `third_party/`, and drives the vendored
Makefiles from it with `-C` and command-line variable overrides. No source
list is copied, so none can drift.

`softfloat/tfgen/platform.h` is deliberately **not** `softfloat/platform.h`.
The latter configures the library ONFLY *ships* — flags discarded (D-34),
`INLINE` forced to `static` for GCCMVS and JCC. The former configures the
stock library that acts as TestFloat's **reference**. A reference modified to
match the implementation under test would prove nothing, so the two must stay
separate.

## 4. Numerical details

No arithmetic changed. `onfrq1` performs exactly the operations `tstgld.c`
performed before it, in the same order, and the golden fingerprints are
byte-identical before and after the refactor — that identity is the evidence
that the extraction was behaviour-preserving, and it was checked on all three
x86 backends and both networks before anything else was built on top.

### 4.1 Why the full network's duration is not arbitrary

D-230 left `full`'s short duration open and D-232 fixed it at 100 ms, on a
measurement that changed the question. The first recording used 1 ms and was
**vacuous**: both readout entries came back `(id, −1, 0)`, never firing, so
the three fingerprints differed only because the rate is a field of the
request. That is the D-70 trap — a suite whose readouts never fire cannot
detect a kernel change — reappearing in a new place.

Let *L(k)* be the first-spike latency of readout *k* and *S(k, T)* its spike
count over a run of duration *T*. Measured at 200 Hz, seed 1, x86-64 NATIVE:

| *T* | *S*(306, *T*) | *S*(6394, *T*) | wall clock |
|---|---|---|---|
| 1 ms | 0 | 0 | — |
| 50 ms | 4 | 1 | 18.5 s |
| 100 ms | 11 | 2 | 35.9 s |
| 200 ms | 28 | 5 | 74.3 s |

with *L*(306) = 26.0 ms and *L*(6394) = 39.0 ms, both independent of *T*.
Any *T* below about 40 ms leaves the second readout silent, and *T* = 50 ms
leaves it firing exactly once — the same single-spike margin D-213 rejected
when it moved G-19 off 30 Hz. 100 ms is the smallest tested duration at
which both readouts fire more than once.

### 4.2 Two integer relations

These are re-stated because the loop now enforces them on data that arrives
from a file rather than from a compiled-in table:

- **NR-12's draw bound.** A request is rejected unless
  `rate_hz × dt_us ≤ 1,000,000`. Below that bound the rejection-sampling
  draw in `onfstm.c` is exactly uniform; above it, it cannot be.
- **Step count.** `steps = ms × 1000 / dt_us`, computed in integers on
  non-negative values only (NR-11), after `ms` has been range-checked against
  the header's maximum, so the division cannot be reached with a negative
  numerator.

## 5. Design decisions

Every choice below was the owner's, taken through AskUserQuestion and
recorded in SRS Appendix A.1 before the code that depends on it was written.

| Decision | Alternatives rejected |
|---|---|
| D-214 Phase D is the session's scope | D-140's chunk-fingerprint obligation; TBD-06's seeds; ruling on P-08/P-11 |
| D-215 full s390x system VM, Ubuntu 24.04 under `qemu-system-s390x` | x86 cross-compiler with `qemu-s390x` user mode; Alpine netboot; hand-rolled cloud-init seed |
| D-216 TX-01/TX-02 against synthetic plus all four networks | the two networks Section 8.4 names; `srext` alone |
| D-217 worktree exported read-write over 9p | read-only share with console results; tar on a virtio disk |
| D-218 parameterise the one Makefile | `build/linux.mk` overlay; standalone `Makefile.s390x` |
| D-219 TX-01 compared against x86, reported PARTIAL | NOT RUN until Phase E; amend TX-01's text |
| D-220 all three backends on s390x, SOFT2C included | only the two rows Section 8.3 names |
| D-221 build the request loop now | report TX-01 NOT RUN; narrow it to the record layout |
| D-222 the full plan, not a reduced one | golden-request records only, no cards, no messages |
| D-223 ONFREQ/ONFRSP as `argv[3]`/`argv[4]` | environment variables; fixed filenames |
| D-224 extract and share the sequence | duplicate it, leaving `tstgld.c` untouched |
| D-225 build `testfloat_gen` out of tree | carry x86 vectors in; extend the baked-in header; vendor a build dir |
| D-226 ONF906S at RC 16 | ONF204E at RC 8; reuse ONF108E |
| D-227 keep ONF905S, annotated | remove it; re-purpose it |
| D-228 TE-09 proved structurally **and** observationally | observational only; structural only |
| D-229 three requests on `hop2` and `full`: 0, 40, 200 Hz | one request each; the same five `srext` carries |
| D-230 `hop2` at 1000 ms, `full` short | 1000 ms for both; short for both |
| D-231 the payload bound moves to `onfplat.h` | raise it globally; use `runnet` for `full`; drop `full` |
| D-232 `full` runs at 100 ms | 50 ms; 200 ms; the 1000 ms standard duration |
| D-233 `liclint` and `prep` skip with a printed line | a reduced target list; install the dependencies in the guest |

Two engineer errors are recorded rather than quietly fixed, because both
changed what the owner was told:

- The cost stated for D-225 was wrong. `testfloat_gen` **does** link the
  SoftFloat library; the list read was `OBJS_COMMON`, the contents of
  `testfloat.a`, not the link line. The decision was unaffected and the
  correction is in D-225's own row.
- D-219 was asked on a false premise — that x86 response records existed to
  compare against. Discovering they did not is what produced D-221.

## 6. Verification

Every command below was run in this session. **Platform and backend are
stated for each; nothing is generalised across rows.**

### 6.1 x86-64 Windows 11, mingw32 gcc 6.3.0

```
mingw32-make test
```

Exit 0. Covers the NR-05, licence, 80-column, C-04 and C-04/MVS lints,
TT-01, TT-02, the SoftFloat 2c checks, TU-01…TU-07, the kernel, the
embedded-network engine path, TE-01…TE-13, the new STEP2 request loop and the
ACC-5 golden suite, on SOFT3E, SOFT2C and NATIVE.

```
mingw32-make req
  run_req: 67 passed, 0 failed
  path  step RC 8 (IR-JCL-04); srext step RC 0
  ONFRSP byte-identical across SOFT3E, SOFT2C and NATIVE on both networks
mingw32-make golden
  cmpgld: SOFT3E, NATIVE, SOFT2C agree on all 19 golden requests
          across 2 networks
```

### 6.2 Linux s390x, Ubuntu 24.04, gcc 13.3.0, under qemu-system-s390x (TCG)

Results are recorded in Section 6.3 of this document as they were measured.

### 6.3 What these results do **not** prove

- **QEMU is not hardware.** VL-01 applies: `qemu-system-s390x` emulates
  z/Architecture floating point in software. An s390x result under TCG is a
  statement about Linux on z/Architecture as QEMU implements it, not about a
  real IBM Z machine.
- **Nothing here ran under GCCMVS, JCC, MVS 3.8j or z/OS.** Rows 6, 7 and 8
  of the Section 8.3 determinism matrix remain unrun. TX-01 stays **PARTIAL**
  for exactly this reason (D-219): its MVS half cannot exist until Phase E.
- **The x86 native backend is 32-bit mingw gcc 6.3.0 with SSE2 forced**
  (D-30). The s390x native backend is gcc 13.3.0 with no such flag because
  z/Architecture has no x87. These are different admissibility arguments for
  NR-09, not one argument applied twice.
- **ONFLYDRV, the JCL and the report are still Phase E.** D-221 brought
  STEP2 forward and nothing else; `tools/mkreq.py` stands in for STEP1's
  card parsing and is *not* a replacement for the COBOL program. When Phase E
  builds ONFLYDRV's request mode, the two must be shown to agree byte for
  byte on the same cards, and that comparison has not been made.

## 7. Related docs

- `docs/ONFLY-SRS.md` — Section 3.4 (FR-BAT), Section 3.5 (FR-LNX),
  Section 4.3 (COMMAREA), Section 4.4 (JCL step contracts), Section 8.3
  (determinism matrix), Section 8.4 (golden suite), Section 9.2 (phases),
  Appendix A.1 (D-214 … D-228), Appendix D (verification limits),
  Appendix E (message catalog)
- `docs/implementations/2026-09-11-soft2c-backend-and-engine-on-mvs.md` —
  where SOFT2C came from and why MVS needs it
- `docs/implementations/2026-09-13-network-format-v11-compensating-input.md`
  — the v1.1 table the srext network carries
