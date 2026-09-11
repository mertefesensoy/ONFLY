# 2026-09-11 — The SOFT2C backend, and the first ONFLY engine code on MVS

| Field | Value |
|---|---|
| Date | 2026-09-11 |
| Author | Claude (senior engineer), for owner Mert Efe Şensoy |
| Phase / gate | Phase B (x86 engine and oracle), completing the float layer; first reconnaissance into Phase E |
| Owner decisions relied on | D-121, D-122, D-123, D-124; standing: D-04, D-26, D-31, D-34, D-35, D-105, D-110, D-111, D-118 |
| Requirements touched | NR-01, NR-02, NR-03, NR-04, NR-05, NR-07, NR-10, NR-12, NR-13, NR-14, NFR-MNT-02, NFR-OBS-01, NFR-PRT-01, C-04, IR-NET-07, IR-COM-05, FR-SIM-01, FR-SIM-03, FR-SIM-04, FR-LOD-02, ACC-2, ACC-5 |
| Open items closed | none |

## 1. Problem / motivation

Gate G1 closed on 2026-09-11 with SoftFloat 2c proven to build and run
correctly on MVS 3.8j under GCCMVS (VL-26, VL-29, VL-30). Two things were
left standing at the end of that session, and both were load-bearing.

**There was no `onf_fp` backend for 2c.** Every golden-suite fingerprint
ONFLY had ever produced came from Release 3e or from the host's native
hardware — and Release 3e *cannot be built by GCCMVS* (VL-21). So the
determinism the project exists to demonstrate had never been exercised
with the library MVS actually uses. Had 2c and 3e disagreed anywhere the
arithmetic matters, nothing built so far would have detected it.

**No ONFLY engine code had ever been compiled on MVS at all.** Everything
that had run there — the TT-01/32 self-test, the TT-02 TestFloat vectors,
the 2c known answers — was the float library and its test drivers. Whether
`onfcrc.c`, `onfrnd.c`, `onfstm.c`, `onfker.c` or `onffp2.c` would even
compile under GCCMVS was unknown, and the project had already been
surprised four times by that compiler (VL-15, VL-17, VL-19, VL-23).

A third gap surfaced while closing the first two, and it was the most
valuable finding of the session: SoftFloat 2c keeps **writable static
state** and writes to it on essentially every operation. The 3e backend has
none, because D-34 and D-35 removed it. A 2c backend built as-is would have
given MVS — the platform whose whole future is a CICS transaction
(Section 3.7) — the one property NFR-MNT-02 forbids.

## 2. What changed

| File | Change |
|---|---|
| `docs/ONFLY-SRS.md` | D-121…D-124 in Appendix A.1; P-08 in A.2; NFR-OBS-01 and the Section 8.3 backend column amended under D-124; VL-31, VL-33 and VL-35 in Appendix D |
| `engine/src/onffp2.c` | **New.** The SOFT2C backend: the `onf_fp` API over SoftFloat 2c |
| `engine/include/onffp.h` | Three backend identities instead of two; `ONF_FP_SOFT2C` selects 2c; mutually-exclusive selection enforced at compile time |
| `softfloat/derive2c.py` | Derives a modified `softfloat.c` with 2c's writable static state removed (D-123); edits now carry an expected occurrence count |
| `softfloat/c2c/softfloat.c` | **New (generated).** The derived library the builds compile. Never edited by hand |
| `softfloat/c2c/softfloat.h`, `softfloat-specialize` | The three globals' declarations and the tininess definition removed |
| `tools/gen2cnm.py` | The three removed globals dropped from the C-04 rename map |
| `tools/mvs2c.py` | Amalgamates the derived `softfloat.c`, not upstream's |
| `Makefile` | `SF2CSRC`, `SF2CFLAGS`; 2c columns in `fp`, `kernel`, `golden`, `tt02`; `c04mvs` widened to the whole MVS-bound object set |
| `tools/cmpback.py`, `tools/cmpgld.py` | Compare N builds, each labelled by the backend it declares, not two positional ones |
| `tests/run_tt02.py` | Same generalisation; the last argument is `testfloat_gen` |
| `tests/run_units.py` | `compare(text)` split out of `main()`; CRC vector note |
| `tests/run_ker.py` | `compare(text)` split out of `main()`, returning a `Result` |
| `tests/tstunit.c` | TU-03's three named CRC vectors written as byte arrays, not C character literals |
| `tools/mvsunit.py` | **New.** Runs TU-03, TU-04 and TU-05 on MVS |
| `tools/mvsker.py` | **New.** Runs the kernel on MVS through the SOFT2C backend |
| `tools/gensyn.py` | **New.** Serialises a complete ONFNET image as a C array |
| `generated/onfsynt.h` | **New (generated).** That image, plus the requests to run |
| `tests/tstsyn.c` | **New.** Decode, integrity-check, load, simulate, fingerprint, over the embedded image |
| `tests/run_syn.py` | **New.** Judges it against the oracle; `compare(text)` serves both platforms |
| `tools/mvssyn.py` | **New.** Runs that whole path on MVS |

## 3. Implementation approach

### 3.1 The backend is almost nothing, and that is the point

SoftFloat 2c's `bits32` build carries a binary64 as

```c
typedef struct { bits32 high, low; } float64;
```

and ONFLY carries one as

```c
struct onff64 { onf_u32 hi; onf_u32 lo; };
```

These are the same shape, so `onffp2.c` converts by copying two fields. The
3e backend has to reassemble the halves into the single `uint64_t` that
3e's `float64_t` wraps and split it again on return; 2c needs no 64-bit
type anywhere, which is exactly the property that makes it survivable under
a compiler whose 64-bit addition ends in an internal compiler error
(VL-15) and whose variable-count 64-bit left shift silently drops bit 63
(VL-19).

The copy is field by field rather than a cast: a cast between two
structurally identical structs is not legal C89, and it would be a pointer
pun over a buffer besides, which FR-LOD-05 rules out as a technique.

**Contract of each function.** `onffadd`, `onffsub`, `onffmul` take two
`onf_f64` by value and return the correctly rounded binary64 result,
round-to-nearest-ties-to-even (NR-01). `onfflt` and `onffle` return 1 or 0
and return 0 if either operand is NaN. None allocates, performs I/O, or
touches static data (FR-SIM-07, NFR-MNT-02). None reads or reports IEEE
exception flags (NR-10).

The **signalling** comparisons `float64_lt` and `float64_le` are used
rather than the `_quiet` forms, for two reasons: they are what the 3e
backend calls, and they are the two functions VL-22's identity check
actually exercises (`tests/tstc2c.c` calls them by name). A backend built
on functions the verification does not cover would be verified by
association. The choice cannot change a result — both forms return 0 for
any NaN and differ only in whether a flag is raised, and after §3.2 there
is nowhere to raise one.

### 3.2 Removing 2c's writable static state (D-123)

**The measurement, taken before the decision was put to the owner.**
Upstream `third_party/SoftFloat-2c/softfloat/bits32/softfloat.c` defines
`float_rounding_mode` and `float_exception_flags` at lines 32–33, and the
binary64 add/subtract/multiply path ONFLY calls reaches all three globals:

| Line | What it does | Where |
|---|---|---|
| 407 | `float_exception_flags \|= float_flag_inexact;` | `roundAndPackFloat64` |
| 386 | reads `float_detect_tininess` | `roundAndPackFloat64`, underflow test |
| 1337 | reads `float_rounding_mode` | `roundAndPackFloat64` |
| 1668 | reads `float_rounding_mode` | `subFloat64Sigs`, the x − x sign rule |

with 27 references in total across the file.

`softfloat/derive2c.py` now emits a modified `softfloat.c`. Each
substitution replaces a global with a constant the specification already
fixes, so **no result can change**:

- `roundingMode = float_rounding_mode;` → `float_round_nearest_even`.
  NR-01 fixes the mode and NR-10 forbids changing it, so the global held
  that value by construction. This is verbatim the argument D-35 made for
  Release 3e.
- `float_detect_tininess == float_tininess_before_rounding` → `0`. Upstream's
  own specialize file statically initialises the mode to
  `float_tininess_after_rounding`, so the comparison was already false.
- `float_exception_flags |= float_flag_inexact;` → `float_raise(...)`, which
  D-34 already made a no-op. The call sites keep upstream's shape; what
  disappears is the storage behind them.
- `float_rounding_mode == float_round_down` → `0`. The difference of two
  equal finite values is −0 only when rounding toward negative infinity,
  which NR-01 excludes.

The definitions and the `extern` declarations go too, so a future
reference is a compile error rather than a link-time reintroduction.

Every edit carries an **expected occurrence count** that the script
asserts. Upstream changing the shape of the file is then a loud failure
rather than a partial substitution — the same discipline `derive2c.py`
already applied to the `!!!` placeholders.

`third_party/` is not edited (D-28, D-35). Upstream's file is the *input*
to the script.

### 3.3 Naming three backends (D-124)

`ONF_FPID` is now `SOFT3E`, `SOFT2C` or `NATIVE`, and `onffp.h` rejects a
build that asks for two at once. NFR-OBS-01's text and the Section 8.3
backend column were amended under D-124's authorisation.

The comparison tools follow: `cmpback.py`, `cmpgld.py` and `run_tt02.py`
take two **or more** builds and label each by the backend it declares in
its own banner, rather than by its position on the command line. Three
pairwise comparisons would have reported one disagreement three times
without saying which backend was the odd one out.

### 3.4 Getting engine code onto MVS without shipping answers

`tools/mvs32.py` and `tools/mvstf2.py` both carry a generated vector table
to MVS, because their subjects are arithmetic primitives whose inputs must
be enumerated. The engine units need no such table, because ONFLY's test
drivers already print what they computed and let Python judge:

- `tests/tstunit.c` prints CRCs, PRNG draws and stimulus outcomes;
  `tests/run_units.py` recomputes all of them in the oracle.
- `tests/tstker.c` prints the synthetic network it built *and* the kernel's
  results; `tests/run_ker.py` parses the network, runs the independent
  Python oracle (O-1) on that very network, and compares.

So `tools/mvsunit.py` and `tools/mvsker.py` submit the job, harvest the
program's own output from the job listing, and hand it to the **same**
comparison that judges the x86 build. `compare(text)` was split out of each
script's `main()` for exactly this; nothing else about either changed.

This is stronger than a shipped table. A table proves MVS agrees with
values x86 computed earlier. This proves MVS agrees with an oracle that
shares no code with either build — and because the network travels back in
the listing, the oracle simulates precisely what MVS simulated.

For the kernel job the 2c library reaches GCCMVS as the D-110 amalgamation
with the D-111 rename prologue, and `engine/src/onffp2.c` carries the same
prologue, so caller and callee agree by construction rather than by care.

### 3.5 A network compiled into the program

`tstdec.c` and `tstgld.c` both open a *file*. On MVS that is a dead end
until Gate G2 chooses and proves a binary-transparent transport
(IR-TRN-01, IR-TRN-02) — so `onfdec.c`, the FR-LOD-02 integrity checks,
the big-endian payload load and the IR-COM-05 fingerprint had never run on
the one platform whose byte order and code page could break them.

`tools/gensyn.py` serialises a complete ONFNET image — the full 164-byte
header of Section 4.1, big-endian throughout, both CRCs from zlib,
8-byte-aligned payload sections — into `generated/onfsynt.h` as a C array.
Nothing about it is simplified for being small. It travels through the
same card reader as every other ONFLY source.

**This does not stand in for Gate G2 and does not weaken it.** It answers a
different question. Risk R-07 is "silent corruption in transport", and it
has two halves: *can a file be moved onto MVS intact* (Gate G2), and *is
the code that would detect the corruption correct on that host* (this).
Only the first is Gate G2's, and until now neither had been answered.

The image is generated from `tests/run_dec.py`'s `sample_network()` — the
network that already drives TE-01…TE-08 on x86 — so the C side, the oracle
and the x86 decode tests cannot drift apart.

**The integrity cases split in two, and the split is the point.** A field
inside the header CRC's coverage (bytes 0–159, IR-NET-07) cannot be tested
on its own by flipping a bit: FR-LOD-02 checks the header CRC before the
length and payload CRC, so the header check would catch it and the case
would prove only that *something* was wrong. TE-01, TE-02, TE-03 and TE-06
therefore patch the field and **reseal** the header CRC, modelling a
producer that wrote an inconsistent file; TE-04 and TE-05 leave the damage
unrepaired, modelling a transport that damaged a good one. An operator has
to be told which happened — rebuild the network, or re-send it in binary
(NFR-REL-01). My first draft got this wrong and expected `ONFD_PLEN` and
`ONFD_PCRC` where the header CRC correctly fired first; the run said so,
and the expectation was what changed.

Two of the cases are ones only MVS is placed to test properly.
**IR-NET-04's byte-order sentinel** exists to catch a text-mode transfer,
and **IR-NET-08's zero-padded FB dataset** — where the file is *longer*
than the payload and the header's declared length is authoritative
(FR-LOD-03) — is what every MVS dataset looks like and what no other
platform produces.

## 4. Mathematical / numerical details

No new numerics. The kernel, the propagator coefficients and the operation
order are unchanged and remain Appendix C's, which is normative (NR-07).

What this work adds is a third *implementation* of the same binary64
operations, and the claim being tested is **bit-identity**, not
approximation. Two libraries agreeing to within a tolerance would be
worthless here: a single differing bit in a membrane potential changes
which timestep a neuron crosses `U_th`, which changes the spike train, and
a different spike train is a different fly. So every comparison in §6 is an
equality on exact bit patterns, never a tolerance.

One numerical fact does the work of the whole of §3.2. IEEE 754 makes
`x − x` equal `+0` in every rounding mode **except** round-toward-negative-
infinity, where it is `−0`. NR-01 fixes the mode to round-to-nearest-ties-
to-even and NR-10 forbids changing it, so the sign expression at
`softfloat.c:1668` is false by construction and the constant `0` is not an
approximation of it — it is the same value, always.

The EBCDIC finding in §6.3 is likewise arithmetic rather than opinion. CRC-32
is computed over **bytes**. The nine characters `123456789` are the bytes
`31…39` in ASCII and `F1…F9` in EBCDIC, and CRC-32/ISO-HDLC of those two
byte strings is `CBF43926` and `8A097905` respectively. Both engines
computed their input's CRC correctly; the inputs were different objects.

## 5. Design decisions

Every decision below was put to the owner through AskUserQuestion and
answered by the owner before the code that depends on it was written.

| ID | Decision | Alternatives offered |
|---|---|---|
| D-121 | Session scope: the 2c backend, then the first engine build on MVS | 2c backend on x86 only; Gate G4 (COBOL spike); Gate G2 (transport spike) |
| D-122 | The plan above, approved as written | Approve Stage 1 and re-ask; approve but drop the synthetic-network step; discuss first |
| D-123 | Remove 2c's writable static state by derivation | Accept the globals and carry NFR-MNT-02 as an open item due before Phase G; measure the derivation cost first |
| D-124 | Three backend identifiers, amending NFR-OBS-01 and the Section 8.3 column | Keep SOFT/NATIVE and add a release field; keep SOFT alone and caveat every report |

**P-08 is a proposal, not a decision.** D-124 renamed the determinism
matrix's backend values; it did not add rows, so ACC-5's row set is
unchanged. An x86/SOFT2C row is proposed in Appendix A.2 and stays there
until the owner rules on it. The x86 SOFT2C fingerprints in §6.1 are
therefore reported as evidence, not as an ACC-5 row.

**The architect's own choices**, which the SRS already determines and which
were not put to the owner:

- Writing TU-03's three named CRC vectors as byte arrays. This makes the
  test hash the same bytes on every host, which is what a known-answer test
  must do; it is the same reasoning IR-COM-05 applies to the response
  fingerprint. It preserves `CBF43926`, the standard CRC-32/ISO-HDLC check
  value, as a genuine cross-platform assertion.
- Source member names on MVS gaining a trailing `C`. Only the *header*
  member names are forced — they are what `#include` resolves to (VL-23) —
  and `mvsbld` keeps member names unique across both libraries.

## 6. Verification

Every figure below was produced in this session. Nothing is remembered.

### 6.1 x86-64

**Platform:** x86-64, Windows 11, MinGW gcc 6.3.0 (32-bit, SSE2 forced for
the native backend per D-30). **Backends:** as each line names.

```bash
mingw32-make test
```

| What | Result |
|---|---|
| `run_c2c` — VL-22 re-run on the **derived** library | 6 of 6 operations, **260,376 cases, 0 mismatches** |
| `tst2c` known answers | `# tst2c 0 of 1854 vectors wrong` |
| `run_tt02` — TestFloat through `onf_fp` | 18 of 18 operation runs, **781,128 cases, 0 mismatches**, over SOFT3E, NATIVE **and SOFT2C** |
| `run_fp` (TU-02) | 2,426 passed on each of the three backends |
| `cmpback` (TU-02) | `SOFT3E, NATIVE, SOFT2C agree bit-for-bit on 2018 result lines` |
| `run_ker` | 449 passed on each of the three backends |
| `cmpback` (kernel) | `agree bit-for-bit on 778 result lines` |
| `run_gld` | 14 passed on each of the three backends |
| `cmpgld` | `SOFT3E, NATIVE, SOFT2C agree on all 13 golden requests (33 output lines)` |
| `lint_c04 --enforce-all` (MVS-bound set) | 70 externals over 9 objects, all compliant |
| `lint_nr05` | 54 files, 1 excluded (`onffpn.c`), 0 violations |
| `lint_col80` | 56 files, all within 80 columns |

The `run_c2c` line is the one that matters for D-123: it is VL-22's
identity check re-run against the derived library, and it is what turns
"these substitutions cannot change a result" from an argument into a
measurement.

### 6.2 MVS 3.8j — the engine's integer units

**Platform:** MVS 3.8j, TK5 with Update 5, under SDL Hercules 4.9.1 on
x86-64 Windows 11. **Compiler:** GCCMVS (GCC 3.2.3) at `-O1` (D-100).
**Codepage:** Hercules `819/1047` (VL-18). **Float backend:** none — these
three units are integer-only by construction.

```bash
python tools/mvsunit.py
```

SCRATCH, ALLOC, WRITEH, WRITEC, COMP1–COMP4, ASM1–ASM4, LKED and GO **all
RC 0000**, no compiler or assembler diagnostic of any kind, and:

```
  51 result lines recovered from the job listing
  run_units [MVS38J]: 19 passed, 0 failed
```

This is the first ONFLY engine code to compile and run on MVS.

### 6.3 The finding: EBCDIC reached the CRC through the test

The **first** run of §6.2 reported `16 passed, 3 failed`:

```
    FAIL TU-03 crc a                        C=48BD5C3B oracle=E8B7BE43
    FAIL TU-03 crc abc                      C=62B280F6 oracle=352441C2
    FAIL TU-03 crc check                    C=8A097905 oracle=CBF43926
```

The three MVS values are exactly `zlib.crc32` of the same characters in
EBCDIC — `0x81`, `0x818283`, `0xF1F2F3F4F5F6F7F8F9` — confirmed numerically
before anything was changed. `empty` and `allbytes` agreed, because their
bytes are built numerically rather than from literals.

So the CRC implementation was correct on both platforms and the **inputs**
differed: `tests/tstunit.c` was passing `onfcrc` C character literals, which
are code-page dependent. The three vectors are now byte arrays, and the
re-run gives 19 of 19.

It is worth being precise about what this was and was not. It was not an
engine defect, and the engine never had one here. It was a **test** that
could not have detected an engine defect on an EBCDIC host, because it
could not tell a wrong CRC from a differently-encoded input. That class of
test is worse than no test, and it was found by the first job that ever put
engine code on MVS — which is the argument for having run it.

### 6.4 MVS 3.8j — the kernel through SoftFloat 2c

**Platform:** MVS 3.8j, TK5 with Update 5, under SDL Hercules 4.9.1 on
x86-64 Windows 11. **Compiler:** GCCMVS (GCC 3.2.3) at `-O1`.
**Codepage:** `819/1047`. **Float backend:** SOFT2C — Berkeley SoftFloat
2c's `bits32` build, as derived under D-123, amalgamated under D-110 and
renamed under D-111.

```bash
python tools/mvsker.py
```

A 5,153-card deck of seven translation units. SCRATCH, ALLOC, WRITEH,
WRITEC, **COMP1–COMP7, ASM1–ASM7, LKED and GO all RC 0000**, no compiler
or assembler diagnostic:

```
mvsker: amalgamated softfloat/c2c/softfloat.c -> 3563 cards, inlining
        milieu.h, onfproc.h, softfloat.h, softfloat-macros, softfloat-specialize
mvsker: 5153 cards, longest 80 columns, GCCMVS -O1
  939 result lines recovered from the job listing
  run_ker [MVS38J/SOFT2C]: 449 passed, 0 failed
      case 0 seed=1         rate=0     steps=200  rc=0  total spikes=0
      case 1 seed=1         rate=40    steps=500  rc=0  total spikes=17
      case 2 seed=1         rate=120   steps=500  rc=0  total spikes=51
      case 3 seed=1         rate=200   steps=500  rc=0  total spikes=86
      case 4 seed=0         rate=120   steps=500  rc=0  total spikes=40
      case 5 seed=999999999 rate=200   steps=300  rc=0  total spikes=58
      case 6 seed=7         rate=9999  steps=100  rc=0  total spikes=810
```

Those seven totals are **identical** to the x86 SOFT3E, SOFT2C and NATIVE
runs in §6.1. Case 0 is ACC-2 in miniature: rate 0 has no other noise
source, so zero spikes is exact rather than statistical, and it holds on
MVS.

This is the first binary64 arithmetic ONFLY has performed on MVS through
its own API rather than through a SoftFloat test driver, and the first
time the kernel has run anywhere but x86.

One report-quality defect was fixed on the way. The diagnostic filter in
`mvsunit.py` and `mvsker.py` searched the listing for `IFO\d{3}` anywhere
on a line, and the D-111 rename prologue *quotes* "IFO196 FLOAT64@ HAS
BEEN PREVIOUSLY DEFINED" in its own header comment to say what it exists
to prevent. GCCMVS echoes the source into the listing, so a clean run
reported the explanation as though it were the failure. The filter now
anchors the match at the start of the line, where a real Assembler XF
message stands and a comment's continuation asterisk does not. A filter
that cries wolf on a comment is worse than no filter, because the next
real IFO196 would be read as the same false positive.

### 6.5 The full engine path, x86 and MVS

```bash
mingw32-make syn        # x86, all three backends
python tools/mvssyn.py  # MVS 3.8j, SOFT2C
```

x86-64, Windows 11, MinGW gcc 6.3.0:

```
run_syn [SOFT3E backend, WIN32]: 60 passed, 0 failed
run_syn [NATIVE backend, WIN32]: 60 passed, 0 failed
run_syn [SOFT2C backend, WIN32]: 60 passed, 0 failed
cmpback: SOFT3E, NATIVE, SOFT2C agree bit-for-bit on 41 result lines
```

MVS 3.8j, TK5 Update 5, Hercules 4.9.1, GCCMVS at `-O1`, codepage
`819/1047`, backend SOFT2C:

```
mvssyn: amalgamated softfloat/c2c/softfloat.c -> 3563 cards, inlining milieu.h, onfproc.h, softfloat.h, softfloat-macros, softfloat-specialize
mvssyn: 6372 cards, 11 translation units, longest 80 columns, GCCMVS -O1
  28 job steps, every one COND CODE 0000
  diagnostics: none
  42 result lines recovered from the job listing
  run_syn [SOFT2C backend, MVS38J]: 60 passed, 0 failed
```

### 6.6 Three defects in the reporting, all found by running it

Neither changed a computed result. Both would have made a later report
wrong, which is worse, because a wrong report is believed.

**The listing filter reported a comment as a diagnostic.** `mvsunit.py` and
`mvsker.py` searched each listing line for `IFO\d{3}` anywhere, and the
D-111 rename prologue *quotes* "IFO196 FLOAT64@ HAS BEEN PREVIOUSLY
DEFINED" in its own header comment to say what it exists to prevent.
GCCMVS echoes the source into the listing, so a clean run announced the
explanation as though it were the failure. The match is now anchored at the
start of the line, where a real Assembler XF message stands and a comment's
continuation asterisk does not. A filter that cries wolf on a comment is
worse than no filter: the next real IFO196 would be read as the same false
positive.

**The MVS engine named the wrong float backend.** `tools/mvssyn.py`
reported `run_syn [SOFT3E backend, MVS38J]` while linking SoftFloat 2c.
`ONF_FPID` falls through to its default unless `ONF_FP_SOFT2C` is defined,
and the MVS compiles never defined it. The arithmetic was 2c — it is the
only float library in the deck and `onffp2.c` the only backend object — but
the run manifest named the other one, which is precisely what NFR-OBS-01
requires and D-124 exists to guarantee.

`-DONF_FP_SOFT2C` cannot be passed: a JCL field ends at column 71, the
compile PARM card is already 67 columns, and the option would make it 83.
`tools/mvsbld.with_defines` puts the definition in front of each unit as a
card instead, which is what `-D` means to the preprocessor, assembled at
submit time and never written to disk.

This one was only visible because the harvest was fixed first. The earlier
runs labelled their output from a string in the tool — `[MVS38J/SOFT2C]` —
so the program's own claim was never read. Both tools now take the backend
and the platform from the banner the program prints, and VL-33 was amended
to say so.

**And the fix for that had a defect of its own.** The first attempt found
the platform by searching the raw job listing for `# tstunit on platform
<id>` — and GCCMVS echoes the SOURCE into the listing, so it matched
`tstunit.c`'s own `printf` format string and reported the platform as
`%s`. The search now runs over the harvested output lines and is anchored
at the start of one. Three defects of the same family in one session, none
of which changed a number and all of which would have made a report claim
something the run did not: the lesson is that a harness which labels
results deserves the same suspicion as the code it is testing.


### What none of this proves

- **No result above is an s390x, z/OS or real IBM Z result.** VL-01 and
  VL-04 stand unchanged. Nothing in this session touched Linux s390x;
  QEMU is not installed on this host.
- **No real network file has reached MVS.** The kernel job uses the
  64-neuron synthetic network `tests/tstker.c` builds, because the MVP
  network is 885 KB of binary and moving it needs a binary-transparent
  transport — Gate G2, which is not done. So `onfdec.c`, the integrity
  checks of FR-LOD-02 and every golden-suite fingerprint remain unproven
  on MVS.
- **ONFLYENG itself has not been built on MVS.** `engine/src/onflyeng.c`,
  the batch file adapter and the startup self-test are untouched here.
  The startup self-test is a live problem for MVS and is stated in §8.
- **2c and 3e are proven to agree on TestFloat's level-1 vectors, not
  universally.** 260,376 cases is very strong evidence, not a theorem.
- **The x86 SOFT2C fingerprints are not an ACC-5 row** (see §5, P-08).
- **Four workarounds remain load-bearing and none is in the repository:**
  the `-O1` pin (VL-17), the `819/1047` codepage (VL-18), the D-110
  amalgamation and the D-111 renames. A Hercules restart silently reverts
  the codepage; `tools/mvsub.py` refuses to submit when it has (D-103).
- **NFR-MNT-02 is now satisfied by construction for both soft backends, and
  that is an inspection result, not a test.** Nothing in the suite executes
  two ONFLY tasks concurrently, because neither MVS 3.8j batch nor the x86
  harness does.

## 7. Related docs

- `docs/ONFLY-SRS.md` — NR-01…NR-05, NR-10, NR-14, NFR-MNT-02, NFR-OBS-01
  (amended), Section 8.3 (amended), Appendix A.1 (D-121…D-124), A.2 (P-08),
  Appendix D (VL-31, VL-33, VL-35).
- `docs/implementations/2026-09-11-gate-g1-closed-softfloat-2c.md` — how 2c
  came to be the MVS backend, and the four GCCMVS workarounds.
- `docs/implementations/2026-09-11-gccmvs-64bit-matrix.md` — why Release 3e
  cannot be used on MVS.
- `third_party/MANIFEST.md` — provenance and licences of 2c and 3e.

## 8. Follow-ups (out of scope here)

1. **ONFLYENG's startup self-test cannot be `onfint.c` on MVS.** D-79 has
   the engine call `onfitst` at startup, and `onfint.c` is the 64-bit
   test — which ICEs under GCCMVS (VL-21) and would give wrong answers if
   it compiled (VL-19). Under NR-14 as D-118 amended it, a platform whose
   engine uses no 64-bit integer needs the 32-bit form. A 32-bit,
   engine-callable self-test factored out of `tests/tst32.c` is needed
   before ONFLYENG can be built on MVS at all. **This is an owner decision**
   (which test runs at startup, selected how), not something to assume.
2. **Gate G2, transport.** Still open, and still the blocker for the
   golden suite on MVS. What changed is that it is now the *only* blocker
   for it: `onfdec.c` and FR-LOD-02 have been proven correct there over an
   embedded image (VL-35), so what Gate G2 has left to establish is that a
   real network file arrives intact — the other half of R-07, and the half
   no amount of embedding can answer.
3. **P-08**, the x86/SOFT2C determinism-matrix row.
4. **Phase D** (Linux s390x) needs QEMU, which is not installed here.
