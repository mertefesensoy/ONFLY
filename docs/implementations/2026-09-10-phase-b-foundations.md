# 2026-09-10 — Phase B foundations: layout generator, engine primitives, float layer

| Field | Value |
|---|---|
| Date | 2026-09-10 |
| Author | ONFLY engineering session |
| Phase / gate | Phase B — Engine and oracle (x86), scope set by D-25 |
| Owner decisions relied on | D-18, D-24 … D-36 |
| Requirements touched | IR-COM-01, IR-COM-02, IR-COM-03, IR-COM-04, IR-NET-06, IR-NET-07, NR-01, NR-02, NR-04, NR-05, NR-07, NR-08, NR-10, NR-11, NR-12, NR-13, NFR-MNT-01, NFR-MNT-02, NFR-PRT-01, FR-SIM-01, FR-SIM-02, FR-SIM-03, FR-SIM-04, FR-SIM-05, FR-SIM-07, FR-SIM-08, FR-LOD-05, SR-MOD-01, SR-MOD-03, SR-MOD-05 |
| Open items closed | TBD-11, TBD-15, TBD-16. TBD-06 remains **open**; D-37 sets a provisional value for x86 Phase B only |

## 1. Problem / motivation

Before this session the repository held the SRS and nothing else — no source, no
tests, not even a git repository. Phase B could not begin, because three of the
things it depends on were still undecided: the phase ordering itself was marked
PROPOSED and awaiting sign-off (TBD-15), the PRNG had no seed-zero constant
(TBD-11), and the SoftFloat NaN specialization was unchosen (TBD-16).

The gap this closes is the foundation every later phase stands on. Concretely:

- **Layout drift.** The same 412 bytes are read by a COBOL driver compiled by a
  1968-era compiler, a C engine compiled by GCCMVS, and a Python oracle. Three
  hand-maintained copies of one layout drift silently, and the drift surfaces as
  a wrong answer rather than a build error.
- **Silent hexadecimal floating point.** S/370 has no IEEE floating point
  (C-02). A stray `double` compiles perfectly under GCCMVS and quietly becomes
  HFP. Nothing fails; the numbers are simply different on MVS. This is the exact
  failure ONFLY exists to rule out, so the guard against it has to exist before
  the kernel does, not after.
- **Unverifiable primitives.** The CRC, the PRNG and the stimulus draws feed
  every later result. If they are not bit-exact against an independent oracle
  now, every determinism claim later rests on sand.

## 2. What changed

| File | Change |
|---|---|
| `docs/ONFLY-SRS.md` | Moved from repo root (D-27); recorded owner decisions D-24…D-36; closed TBD-11, TBD-15, TBD-16; promoted D-18 and P-07 from proposals to decisions. |
| `docs/implementations/_TEMPLATE.md` | New implementation-note template. |
| `layout/master.py` | The single master definition of the COMMAREA layout, with self-validating invariants. |
| `layout/generate.py` | Generates the COBOL copybook, C header, C accessors and Python struct formats from the master. |
| `generated/ONFCOM.cpy` | Generated COBOL copybook, MVT column discipline. **Do not edit.** |
| `generated/onfcom.h` | Generated C header: offsets, struct, compile-time assertions. **Do not edit.** |
| `generated/onfcom.c` | Generated big-endian accessors. **Do not edit.** |
| `generated/onfcom_py.py` | Generated Python struct formats and ranges. **Do not edit.** |
| `engine/include/onfplat.h` | Platform configuration header: integer typedefs and compile-time width checks. |
| `engine/include/onfcrc.h`, `engine/src/onfcrc.c` | CRC-32/ISO-HDLC, bit at a time, no static state. |
| `engine/include/onfrnd.h`, `engine/src/onfrnd.c` | xorshift32 PRNG per D-32. |
| `engine/include/onfstm.h`, `engine/src/onfstm.c` | Integer-only stimulus draws with rejection sampling. |
| `engine/include/onffp.h` | The binary64 float API every FP operation goes through. |
| `engine/src/onffpc.c` | Backend-independent bit operations: abs, non-finite test, +0.0, bit construction. |
| `engine/src/onffps.c` | SOFT backend over SoftFloat 3e. |
| `engine/src/onffpn.c` | NATIVE backend over host binary64. The only ONFLY file allowed to name `double`. |
| `softfloat/platform.h` | ONFLY's SoftFloat build configuration; selects the non-FAST_INT64 build. |
| `softfloat/onfflag.c` | No-op `softfloat_raiseFlags`, replacing upstream's flag accumulator. |
| `softfloat/onfrpk.c` | Hand-derived flags-free `softfloat_roundPackToF64`. |
| `softfloat/derive.py` | Mechanically derives `onfsub.c` from upstream with asserted substitutions. |
| `softfloat/onfsub.c` | Generated derived file. **Do not edit.** |
| `tools/lint_nr05.py` | The NR-05 build-time lint. |
| `tools/cmpback.py` | Byte-for-byte comparison of the two float backends. |
| `tests/tstcom.c` | TU-01, TU-07: layout geometry and accessor round-trips. |
| `tests/tstunit.c`, `tests/run_units.py` | TU-03, TU-04, TU-05 against the oracle. |
| `tests/tstfp.c`, `tests/run_fp.py` | TU-02 float API against the oracle. |
| `oracle/onfly_oracle/crc32.py`, `prng.py`, `stimulus.py` | Reference oracle primitives. |
| `oracle/onfly_oracle/kernel.py` | Reference kernel: SRS Appendix C in plain Python floats. |
| `engine/include/onfker.h`, `engine/src/onfker.c` | The simulation kernel, Appendix C, operation by operation. |
| `tests/tstker.c`, `tests/run_ker.py` | Kernel comparison against the oracle on a synthetic network. |
| `layout/master.py` (extended) | Now also defines the 164-byte network file header (IR-NET-01), with its own alignment invariants. |
| `generated/onfnhd.h` | Generated network header offsets and constants. **Do not edit.** |
| `layout/netwrite.py` | Writes a network file: sections 8-byte aligned, both CRCs, all binary64 as bit patterns. |
| `engine/include/onfdec.h`, `engine/src/onfdec.c` | Integrity checks in FR-LOD-02's order, plus header decode. |
| `tests/tstdec.c`, `tests/run_dec.py` | TE-01..TE-08 against deliberately corrupted files. |
| `tools/lint_nr05.py` | Gained `--exclude` so whole directories are scanned by default. |
| `Makefile` | x86 build and test driver (D-29). |
| `.gitattributes` | Pins `eol=lf` and marks binary types so git cannot rewrite artifact bytes. |

## 3. Implementation approach

### 3.1 Generated layouts (IR-COM-01, D-18)

`layout/master.py` is the only place the record layout is written. It validates
itself at import: fields must tile the record with no gaps or overlaps, 2-byte
fields must sit at even offsets and 4-byte fields at multiples of 4 (IR-COM-03),
and every declared value range must fit its COBOL PIC digit count so the TRUNC
option can never alter a stored value (IR-COM-02).

`layout/generate.py` emits four artifacts, each carrying the SHA-256 of
`master.py` so a stale regeneration is visible by inspection.

The COBOL emitter enforces MVT column discipline (C-03) and asserts that no line
passes column 72. That assertion fired on the first run — the SHA-256 banner is
64 characters and overflowed Area B — which is exactly the class of defect it
exists to catch.

### 3.2 Big-endian accessors (IR-COM-04, FR-LOD-05)

Every multi-byte field is decoded by explicit byte shifts; no pointer cast is
ever taken over a record buffer. The contract of `onfg32`/`onfp32` is that the
result depends on neither host byte order nor alignment.

The signed conversions avoid relying on signed overflow (NR-11). For an
unsigned value `u ≥ 2³¹` the decoder computes `-(int32)(0xFFFFFFFF - u) - 1`;
`0xFFFFFFFF - u` is at most `0x7FFFFFFF`, so every intermediate stays inside the
signed range and the result reaches exactly INT32_MIN without overflow.

### 3.3 The float layer (NR-01, NR-05)

`onf_f64` carries a binary64 value as two unsigned 32-bit halves rather than one
64-bit integer or a `double`. Two requirements drive that: NR-04 confines 64-bit
integers to SoftFloat and the float layer, and the engine holds this type as
simulation state; and NR-05 forbids floating-point types in the engine, where a
struct of two unsigned ints cannot be accidentally used as a number because no
operator does anything useful to it.

### 3.4 Flags-free SoftFloat (D-34, NFR-MNT-02)

SoftFloat 3e keeps three mutable globals — `softfloat_roundingMode`,
`softfloat_detectTininess`, `softfloat_exceptionFlags` — and `THREAD_LOCAL` is
`#define`d to nothing, so they are plain writable globals. NFR-MNT-02 forbids
writable static data so the engine is reentrant for the CICS path.

They were removed in three steps:

1. `softfloat/onfflag.c` supplies a no-op `softfloat_raiseFlags`; upstream's is
   not compiled. This removes every `raiseFlags` call site.
2. `softfloat/onfrpk.c` replaces `s_roundPackToF64.c`, hard-wiring
   round-to-nearest-ties-to-even and dropping the flag write.
3. `softfloat/onfsub.c` is derived mechanically from `s_subMagsF64.c`, replacing
   the one remaining rounding-mode read.

A macro cannot do this job: `softfloat.h` declares these as extern variables and
`softfloat_raiseFlags` as a function, so a same-named macro mangles the
declaration into a syntax error. The removal has to happen at link time and by
derivation, which is why it is structured this way.

### 3.5 The kernel (FR-SIM-01, Appendix C)

`engine/src/onfker.c` implements Appendix C's step algorithm operation by
operation. It is written as separate statements rather than compound
expressions because NR-07 makes the *sequence* of floating-point operations
normative: a compound expression invites the compiler to contract or reassociate,
and both are forbidden.

Three details in the algorithm are easy to get wrong and are worth naming:

- **The ring slot.** Appendix C writes arrivals into slot `(t + D) mod D`, which
  is the same slot consumed and zeroed at the start of step `t`. It is next read
  at the start of step `t + D`, which is exactly the synaptic delay. Writing to
  the slot just emptied looks like a bug and is not one.
- **Draws are unconditional.** Every stimulus neuron consumes exactly one
  *accepted* draw per step whether or not it is refractory. If refractory
  neurons skipped their draw, two hosts whose network state had diverged would
  consume different numbers of draws and the PRNG streams would separate — which
  would turn a small numerical difference into a completely different run
  (FR-SIM-04).
- **CSR order is normative.** Targets within a row are visited in ascending CSR
  order because IR-NET-06 says so, and IR-NET-06 says so because floating-point
  addition is not associative. Accumulating a row's weights in a different order
  is a different number, not the same number computed differently.

The kernel never allocates, performs no I/O and holds no static data
(FR-SIM-07, NFR-MNT-02); all state is caller-owned so one allocation can serve
many requests.

## 4. Mathematical / numerical details

### 4.1 CRC-32/ISO-HDLC (IR-NET-07)

Parameters: width 32; polynomial 0x04C11DB7, reflected to 0xEDB88320 for the
LSB-first form; initial register all ones; input and output reflected; final XOR
all ones. Implemented bit at a time: for each input byte, XOR it into the low
byte of the register, then eight times shift the register right one bit and XOR
the reflected polynomial back in whenever the bit shifted out was 1.

Bitwise rather than a 256-entry table because NFR-MNT-02 forbids building a
table lazily, and a `const` table costs 1 KB in a 24-bit region (C-01) while
adding a second thing to keep in step with the polynomial. The cost is roughly
eight times more work per byte, paid once per job step over the network file and
over about forty bytes per fingerprint — neither is in the simulation inner
loop, so it does not bear on NFR-PERF-01. If Spike S3 shows otherwise, a
generated `const` table is the answer.

Verified against the standard check value: CRC of `"123456789"` is `0xCBF43926`.

### 4.2 xorshift32 (NR-13, D-32)

State is a non-zero unsigned 32-bit word. One draw is

```
x ← x XOR (x << 13)      (mod 2³²)
x ← x XOR (x >> 17)
x ← x XOR (x << 5)       (mod 2³²)
```

and the **new** state is returned. The map is linear over GF(2), so the
all-zeros state is a fixed point: once zero, always zero. Seed 0 is a legal
request value and golden request G-10 uses it, so D-32 maps it to 2463534242
(0x92D68CA2), Marsaglia's own published seed.

### 4.3 Stimulus draws (NR-12)

Per stimulus neuron per step: draw a 32-bit `r`; if `r ≥ 4,294,000,000` discard
and redraw; the neuron spikes if `r mod 1,000,000 < rate_hz × dt_us`.

The rejection removes modulo bias. 2³² = 4,294,967,296 is not a multiple of
10⁶, so reducing the whole range would make the low residues slightly more
likely. Discarding the top 967,296 values leaves exactly 4,294 complete cycles
of 10⁶, so every residue is equiprobable. The rejection probability is
967,296 / 2³² ≈ 2.25 × 10⁻⁴, about one draw in 4,440.

`rate_hz × dt_us / 10⁶ = rate_hz × dt_seconds` is the expected spikes per step.
NR-12's bound `rate_hz × dt_us ≤ 10⁶` is therefore the statement that the
per-step probability must not exceed 1. **This is tighter than it looks:** golden
request G-07 uses the maximum rate 9,999 Hz, and at dt = 0.1 ms (100 µs) that
gives 999,900 — inside the bound by 100 parts per million. Any increase in dt
above 0.1 ms breaks G-07.

Measured against the prediction: over 200,000 steps the expected rejection count
is 200,000 × 2.25 × 10⁻⁴ ≈ 45. Observed: 39 (seed 1) and 44 (seed 0).

### 4.4 Round-to-nearest-ties-to-even, and why the derivation is result-preserving

`softfloat_roundPackToF64` adds a rounding increment to the significand and
shifts right by 10. Under round-to-nearest the increment is 0x200, exactly half
of the 0x400 discarded. Ties are broken to even by the mask
`sig &= ~(uint64)(!(roundBits ^ 0x200))`: when the discarded bits are exactly
one half, this clears the significand's low bit.

The derived version is bit-identical to upstream under this mode because every
removed element is a pure side effect:

- `isTiny` is computed only to decide whether to raise the underflow flag; it
  enters no arithmetic. With flags discarded it is dead, and removing it also
  removes the `softfloat_detectTininess` read.
- The overflow branch computes `packToF64UI(sign, 0x7FF, 0) - !roundIncrement`.
  With `roundIncrement = 0x200`, `!roundIncrement` is 0, so the result is
  infinity either way.
- The `exceptionFlags |= inexact` write changes no returned value.

For `s_subMagsF64`, the `x − x` case selects the sign of zero by
`softfloat_roundingMode == softfloat_round_min`. IEEE 754 makes `x − x` equal to
+0 in every rounding mode except round-toward-negative-infinity. NR-01 fixes the
mode to nearest-even, so the comparison is false by construction and becomes the
constant 0. `tests/tstfp.c` checks this specifically by comparing **bit
patterns**, because `-0.0 == +0.0` is true and a value comparison would pass
even with the sign wrong.

## 5. Design decisions

Owner decisions D-24 … D-36 are recorded in SRS Appendix A.1 with their
alternatives and rationale, and are not repeated here. Choices made by the
architect within those decisions:

- **Bitwise CRC over a const table.** Reasoning in §4.1. Reversible; revisit at
  Spike S3.
- **`onf_f64` as two 32-bit halves.** Reasoning in §3.3.
- **`INLINE` defined as `static`.** C89 has no `inline`, and GCCMVS is an old
  GCC whose `extern inline` follows GNU rather than C99 semantics. `static` is
  the one spelling that behaves identically on every ONFLY target. The cost is
  unused-function warnings, silenced narrowly.
- **No GCC builtins in the SoftFloat configuration.** Upstream's Win32 config
  sets `SOFTFLOAT_BUILTIN_CLZ`; ONFLY does not, because one configuration must
  also serve GCCMVS and JCC (D-03, NFR-PRT-01).
- **`memcpy` for bit reinterpretation in the native backend.** Union punning is
  unspecified in C89 and pointer casts violate aliasing rules compilers exploit.
- **`.gitattributes` pinning `eol=lf`.** Git's autocrlf would rewrite bytes,
  which FR-PRP-09, IR-NET-01 and ACC-5 forbid. This enforces existing
  requirements rather than adding one.
- **Absolute paths in the test runners.** Windows `CreateProcess` fails on a
  relative path when the working directory contains non-ASCII characters, which
  this project's does (`Masaüstü`).

## 6. Verification

One command runs everything:

```
mingw32-make test
```

Observed on 2026-09-10, exit status 0:

```
lint_nr05: EXCLUDED engine/src/onffpn.c (native backend, NR-05 does not apply)
lint_nr05: 22 files scanned, 1 excluded, 0 violations
tstcom: TU-01/TU-07 on platform WIN32
tstcom: 170 checks, 0 failures
run_units: 19 passed, 0 failed
run_fp [SOFT backend]: 2426 passed, 0 failed
run_fp [NATIVE backend]: 2426 passed, 0 failed
cmpback: soft and native agree bit-for-bit on 2018 result lines
run_ker [SOFT backend]: 449 passed, 0 failed
run_ker [NATIVE backend]: 449 passed, 0 failed
cmpback: soft and native agree bit-for-bit on 778 result lines
run_dec: 10 passed, 0 failed
  ok   TE-01 corrupt magic                  rc=101
  ok   TE-02 corrupt sentinel               rc=102
  ok   TE-03 wrong version                  rc=103
  ok   TE-04 header CRC mismatch            rc=104
  ok   TE-06 payload length inconsistent    rc=106
  ok   TE-05 payload CRC mismatch           rc=107
  ok   TE-08 exceeds memory limit           rc=105
  ok   TE-07 FB zero padding tolerated      rc=0
```

Every TE case corrupts exactly one thing and requires the **specific** Appendix
E condition, not merely a rejection. That distinction is the operational point:
ONF102E tells an operator to re-send in binary mode, ONF107E that the transfer
was corrupted, ONF106E that it was truncated. A decoder returning one generic
"bad file" would help nobody at 3 a.m.

TE-07 is worth singling out. The valid file is 976 bytes; padded to an FB-80
dataset it becomes 1040. The engine accepts it and reads exactly 976, because
FR-LOD-03 and IR-NET-08 make the header's declared length authoritative and the
dataset size irrelevant.

Kernel behaviour across the seven cases, identical under both backends and the
oracle. The monotone rise with stimulus rate is the qualitative shape ACC-1 and
ACC-4 will later test against the Shiu reference; here it only demonstrates the
kernel responds sensibly, on a synthetic network with uncalibrated weights.

| Case | Seed | Rate (Hz) | Steps | Total spikes |
|---|---|---|---|---|
| 0 | 1 | 0 | 200 | **0** — exact silence, ACC-2 in miniature |
| 1 | 1 | 40 | 500 | 16 |
| 2 | 1 | 120 | 500 | 39 |
| 3 | 1 | 200 | 500 | 56 |
| 4 | 0 | 120 | 500 | 33 — seed-zero remapping (G-10) |
| 5 | 999999999 | 200 | 300 | 36 — maximum seed (G-06) |
| 6 | 7 | 9999 | 100 | 40 — NR-12 upper bound (G-07) |

Guards were checked against deliberate faults rather than assumed to work:

| Guard | Injected fault | Result |
|---|---|---|
| `onfcom.h` compile-time assertions | `ONF_OUTLEN` 12 → 16 in a scratch copy | build fails: "size of array 'onfcom_len_assert' is negative" |
| `master.py` invariants | `ONF-SEED` offset 8 → 9 | `AssertionError: gap/overlap at seed: expected 8 got 9` |
| NR-05 lint | `static double leak;` and `return 1.5e3;` | both flagged; "double" in a comment, in a string, and `arr[0].field` correctly not flagged |
| COBOL column discipline | SHA-256 banner line | assertion fired on first run, fixed by wrapping |
| Derived `onfsub.c` | — | `x − x` bit pattern asserted to be `00000000:00000000`, not `80000000:...` |
| Kernel vs oracle | first-spike latency `(t+1)*dt` → `t*dt` | 47 of 449 comparisons fail, exit 1. Spike **counts** were unchanged, so a count-only check would have missed it entirely |
| NR-05 lint coverage | `static double` added to `onfker.c` | flagged, exit 1, while `onffpn.c` stayed correctly excluded |

NFR-MNT-02 was verified structurally, not by inspection: `size` reports **0
bytes** of `data` and `bss` in every SoftFloat object, and `nm` shows all three
SoftFloat globals **absent** from the linked binary.

### What these results do not prove

Everything above ran on **one** configuration: x86, 32-bit mingw32 (`gcc
6.3.0`, target `mingw32`), Windows 11. Specifically:

- Nothing here was run under **GCCMVS, JCC, MVS 3.8j, Linux s390x or QEMU**.
  None of those is installed on this host. Gates G1, G2, G3 and G4 remain
  entirely unrun, and D-25 records that this session's work does not discharge
  Spike S1.
- The SoftFloat build proves nothing about **A-05** (whether GCCMVS synthesises
  correct 64-bit integer arithmetic) or **A-06**. Those are Gate G1's job.
- **NR-09 native-backend admission is NOT complete.** Soft/native bit-identity
  was demonstrated on the operand set `tstfp.c` exercises, which is one of
  several conditions. TestFloat vectors (TT-02) and golden-suite fingerprints
  have not been run — the golden suite does not exist yet.
- The host is **32-bit i686**, which SRS Section 2.3 does not list as a
  platform; the matrix names x86-64. D-30 authorised pursuing native admission
  here with SSE2 forced but explicitly did **not** authorise amending Section
  2.3, so this host remains unlisted.
- The network **file format, writer, decoder and integrity checks** now
  exist, but the decoder populates only the header scalars: it leaves the
  CSR array pointers null, because the payload is big-endian and the kernel
  needs host-order arrays, and that conversion is not yet written. So **no
  end-to-end path from a network file to a simulation exists**, and the
  kernel is still exercised only on a synthetic in-memory network.
- No **response fingerprint** (IR-COM-05), **golden-suite harness**, COBOL
  driver or JCL exists. No ACC-n criterion has been evaluated and **Phase B
  is not complete**.
- Appendix C is still marked **draft**. The kernel implements it faithfully,
  but TBC-01 and TBC-02 remain open until Phase C, so agreement with the
  oracle proves the code matches the specification, not that the
  specification matches Shiu et al. (VL-05, VL-07).
- **C-04 is unaddressed for SoftFloat.** Every SoftFloat external name
  (`softfloat_roundPackToF64`, `softfloat_shiftRightJam64`, …) far exceeds the
  8-character limit the MVS linkage editor accepts. ONFLY's own names are 6–7
  characters, but how GCCMVS handles the vendored names is unknown and is a
  material risk for Gate G1.

## 7. Related docs

- `docs/ONFLY-SRS.md` — Sections 4.3 (COMMAREA), 5 (numerical requirements),
  8 (verification), 9 (gates and phases), Appendix A.1 (decisions D-24…D-36),
  Appendix B (open items), Appendix C (normative kernel), Appendix D (limits).
- `third_party/SoftFloat-3e/COPYING.txt` — BSD 3-clause licence covering the
  vendored library and the derived files (NFR-LIC-01).
