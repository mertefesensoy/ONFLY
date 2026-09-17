# 2026-09-17 — Phase G, first component: the `EXEC CICS` transaction

| Field | Value |
|---|---|
| Date | 2026-09-17 |
| Author | Senior engineer |
| Phase / gate | Phase G — transaction demonstrator (second MVP), `EXEC CICS` half |
| Owner decisions | D-391 … D-400 (this session); relies on D-129, D-130, D-131, D-156, D-224, D-366, D-383 |
| Requirements touched | Section 3.7, IR-COM-01, IR-COM-02, IR-COM-04, IR-COM-05, IR-COM-06, IR-JCL-03, FR-SIM-07, FR-BAT-04, C-03, C-04, C-08, NR-04, NR-05, ACC-5 |
| Open items closed | none. VL-37's "how a Raincode COBOL program on .NET would reach [the C89 engine] remains unasked" is **answered** and recorded as VL-117 |
| Plan of record | P-22, approved by D-396 |
| Platform | **x86-64 Windows only.** Nothing here is proven for MVS 3.8j, Linux s390x or z/OS |

## 1. Problem / motivation

Section 9.2's Phase G row names three components:

> ONFLY as a transaction written in real `EXEC CICS`, verified against Raincode on the
> development host (D-130, VL-37); the flow shown on a real 3270 driven by INTERCOMM on
> TK5 (D-131); a live view of the network rendered on x86 from streamed engine output
> (D-126, D-127, D-128)

The third landed on 2026-09-16/17 as Stages 1 to 4. The **first** was unbuilt. What
existed was four *probes* from D-129 in `tests/raincode/`, which answered whether the
compiler and the runtime work. They do not contain ONFLY's transaction: their LINK
target `ONFCENG.cbl` is a COBOL stub whose own comments say *"It computes nothing —
the engine is C and lives elsewhere."*

VL-37 closed on the gap in so many words: *"nothing about the engine boundary: these
probes LINK COBOL to COBOL, while ONFLY's engine is C89 and how a Raincode COBOL
program on .NET would reach it remains unasked."*

D-395 asked it. This is the answer, built.

## 2. What changed

| File | What it is |
|---|---|
| `engine/include/onfcics.h` | The CICS adapter's contract: `onfcini`, `onfcrun`, `onfcend`, `onfclen`. Handle-based, opaque anchor |
| `engine/src/onfcics.c` | The adapter. Loads a network once, drives `onfrq1` per COMMAREA, frees on demand. C89 + `long long`, no floating-point literal |
| `cics/onfcics.cs` | The LINK target: `[RainCodeExport("ONFLYENG")]`, `SetIsQIXModule()`, layout-blind, P/Invokes the engine |
| `cics/onfcics.csproj` | References the installed Raincode assemblies by `HintPath` — no NuGet restore, no network |
| `cics/ONFCSUG.cbl` | The **SUGR direct transaction**. Real `EXEC CICS LINK`, TS queue, DISPLAY trace |
| `cics/ONFCBUZ.cbl` | The **BUZZ menu transaction**. Compiled only; `SEND MAP`/`RECEIVE` cannot execute here |
| `cics/ONFCBUZ.bms` | The BUZZ mapset — stimulus, rate, duration, seed in; readout, spikes, latency, Hz, RC, fingerprint out |
| `tests/tstcics.c` | Drives a request dataset through the adapter and writes an ONFRSP, for the byte comparison |
| `tests/run_cics.py` | P-22's V3 and V4, with the skip rule D-394 requires |
| `tools/cicsbld.py` | The `make cics` body: seven steps, each adding one unknown |
| `Makefile` | New `cics` target; `onfcics.c` joins the `c04` lint; `col80` now walks `cics` |
| `tools/lint_col80.py` | `.bms` added (card image, column 72 continuation); `.cs`/`.csproj` excluded **explicitly** (D-398) |
| `tools/lint_lic.py` | `.cs`, `.csproj`, `.bms` added to the INTERCOMM scan (D-398) |
| `.gitignore` | `cics/obj/`, `cics/bin/` — dotnet's output beside the sources |
| `docs/ONFLY-SRS.md` | D-391…D-400 in A.1; P-22 in A.2, struck through on approval; **VL-117** in Appendix D |

## 3. Implementation approach

### 3.1 The probe that shaped the design (VL-117)

D-395 required the two unknowns to be settled *before* any ONFLY code was written, and
to stop rather than fall back if either failed. A throwaway probe — a COBOL program
doing `EXEC CICS LINK` to a C# module that P/Invoked a `gcc -shared` DLL — passed:

```
PRBCS entered, arity=1
PRBCS parm[0] size=257448
PRBCS raw in : 00-00-00-07-00-00-00-23-00-00-00-00-20-20-20-20
PRBCS decoded a=7 b=35
PRBCS native prbadd -> 42
PRBCS raw out: 00-00-00-07-00-00-00-23-00-00-00-2A-50-4E-41-54
PRBLNK sum=   42 tag=PNAT
PRBLNK PASS link-to-csharp and pinvoke
```

Eight findings came out of it; three changed the design and are in the code as
comments, so the next reader cannot delete them as noise:

1. `EXEC CICS LINK` reaches a `[RainCodeExport]` module **only** if it calls
   `SetIsQIXModule()` in its constructor. Without it the LINK abends *"Module PRBCS not
   compiled as a QIX module but called using QIX LINK"*. `[RainCodeExport]` alone is
   enough for a COBOL `CALL` and is not enough for a LINK.
2. The COMMAREA is **parameter 0**, arity 1. There is no separate DFHEIBLK parameter.
3. `GetParameterAddress(ec, 0).Size` reported **257448** for a 16-byte record — the
   address-space slice. It is never a length. The length comes from `onfclen()`.

And two toolchain findings that cost real time:

7. The DLL must be built by the msys2 **x86_64** gcc. The Makefile's `CC = gcc` is
   MinGW 6.3.0 whose `-dumpmachine` is `mingw32`, and a 32-bit DLL cannot be
   P/Invoked from 64-bit .NET.
8. That gcc **exits 1 printing nothing at all** unless `C:\msys64\mingw64\bin` is on
   `PATH`, because the driver cannot then load `cc1`. `tools/cicsbld.py` puts it there.

### 3.2 The adapter is a peer of the batch adapter, not a layer

`onfcrun` decodes nothing and validates nothing of its own. It calls `onfrqg`,
`onfrq1`, `onfrqp` — the single request sequence D-224 established and D-383 split.
The bytes crossing this boundary are therefore the bytes TX-01 and TX-02 already prove,
not a second implementation of them. That is why V4 can be a `cmp`, not an argument.

**Handle, not a file-scope pointer.** Section 3.7 requires a CICS program to be
*"reentrant and threadsafe … CONCURRENCY(REQUIRED)"* with the network *"loaded once at
region startup … and anchored for all tasks; transactions only read it."* A file-scope
pointer would be task-shared mutable state whose safety nothing here could examine, one
`rclrun` run unit being one task. A handle costs one parameter and puts the anchor in
the caller, which is where CICS shared storage lives.

### 3.3 The module is layout-blind

`cics/onfcics.cs` names no field, no offset, and not even the record's length —
`onfclen()` reports it, out of `generated/onfcom.h`, out of `layout/master.py`. A
hand-written C# view of the record would have been a third statement of a generated
layout beside the COBOL copybook and the C header, free to drift from both, which is
exactly what IR-COM-01 forbids. The module copies 412 opaque bytes in and out.

`MemoryArea.CopyTo(offset, length, byte[])` and
`MemoryArea.CopyFromBytesOffsetLength(...)` are what make that possible; they were
found by reflecting over `RainCodeLegacyRuntime.dll`, because the shipped XML
documentation carries almost nothing.

### 3.4 The transaction

`ONFCSUG` takes the request in the COMMAREA — from a bridge, a START with data, BUZZ's
LINK, or `rclrun -QixFile` — checks `EIBCALEN`, LINKs to `ONFLYENG`, and formats the
reply the way `ONFLYDRV` formats a report line: spike count, first-spike latency, rate
in Hz to one decimal (`COMPUTE ... ROUNDED`, D-272), the return code, and the
fingerprint as eight hexadecimal characters.

Its `DFHCOMMAREA` is declared `PIC X(412)` with no field names. CICS requires the
linkage item to be called `DFHCOMMAREA` while the generated copybook's 01 is
`ONF-COMMAREA`, and bridging the two needs `COPY ... REPLACING`, which C-03 warns MVT
COBOL supports only partially. So the LINK is given the unnamed block directly and the
reply is copied into the generated record afterwards **purely to be read**. The one
layout fact spelled out is 412, which SRS Section 4.3 states normatively in its own text.

Both COBOL sources are held to **72** columns, not 80: `cobrc` truncates past column 72
with no diagnostic at all (VL-37), and D-93's 80-column rule is about the TK5 card
reader. `tools/cicsbld.py --cols` checks it mechanically, because this compiler will not.

### 3.5 Where the result goes (D-397)

`WRITEQ TS` — a real CICS statement this installation executes — plus a `DISPLAY`
trace. `SEND TEXT` is not used: it returns `INVREQ` here because the free Raincode
edition holds no terminal facility (VL-37).

## 4. Mathematical / statistical detail

**None is new, and that is the claim.** The transaction changes no arithmetic: it hands
412 bytes to the same `onfrq1` the batch path uses. The kernel's update order, the
propagator constants, the subnormal clamp and the accumulation order are untouched.

The rate in Hz that FR-BAT-04 prints to one decimal is computed in COBOL from two
integers, `(spikes × 1000) / duration_ms`, `ROUNDED` to the nearest tenth — the same
expression `ONFLYDRV` uses (D-272). No floating point enters the transaction; the
engine's binary64 work all happens behind `onf_fp` as NR-07 requires.

The single numeric assertion this component makes is an **equality**, and it is checked
two ways:

- **V4**, byte identity: for the five Section 8.4 `srext` requests, the 2060 bytes the
  adapter writes equal the 2060 bytes the batch engine writes. Not a tolerance, not a
  summary — every byte.
- **V3**, fingerprint identity: the transaction's reported fingerprint equals the batch
  response's. IR-COM-05 defines it as the CRC-32 of a canonical string carrying the
  network payload CRC, the stimulus id, seed, rate, duration, return code, output count
  and step count, then each output triple — so a single differing field moves it.

## 5. Design decisions, and what was rejected

| Decision | Chosen | Rejected, and why |
|---|---|---|
| Engine boundary (D-395) | In-process P/Invoke into a DLL built from the engine sources | Out-of-process would reload the network per request and could not exercise Section 3.7's anchor; a COBOL stub proves nothing new |
| Adapter state | Handle | A file-scope pointer contradicts Section 3.7's reentrancy obligation and hides the question |
| C# layout knowledge | None, not even the length | A hand-written view is a third copy of a generated layout (IR-COM-01) |
| Request sequence | `onfrq1`, reused | A CICS-specific loop would be the second-implementation condition that produced D-289 and D-360, silently both times |
| Packages | `HintPath` to the installed assemblies | NuGet restore wants fourteen third-party packages the local `rcpackages` feed lacks, so it would reach the internet |
| V4's channel (D-399, then D-400) | A C test at the adapter, plus the transaction held to the fingerprint | Reading the bytes back through QIX — **measured impossible**, see below. A guarded static in the module would have been the very task-shared state Section 3.7 forbids |
| Build (D-394) | `make cics`, skipped when absent | Joining `make test` breaks a bare checkout |

### 5.1 The measurement that withdrew D-399

D-399 approved a host runner that would *"allocate the 412-byte area itself, execute
`ONFCSUG` in QIX mode and read the bytes straight back."* It was built, and it does not
work, for a reason worth recording rather than routing around:

**QIX copies the COMMAREA into the run unit and never back.** After `Execute()` the
runner's own `CommArea` still held the request — `rc 0`, `outcount 0`, fingerprint all
zero — although `ONFCSUG` had demonstrably filled it and printed `FP=BAF81D91`. The
`-QixFile` input file is not written back either, and `-QixDumpCommareaOnExit` writes
through the console encoding, so `0x03E8` came out as `0x038A`.

That is **not a Raincode defect**. It is real CICS semantics: a top-level transaction
has no caller to return a COMMAREA to. The other routes were measured shut too —
`ExecuteQix` is neither virtual nor callable before `Execute()` initialises the runner,
and `ITSQueueManager` can only be supplied at `ExecutionContext` construction, which the
runner does internally.

D-400 therefore split V4: the bytes are compared where they exist, and the transaction
is held to the fingerprint. `cics/onfchost.cs` was deleted.

## 6. Verification

Every command below was run **in this session, on x86-64 Windows 11**, with
Raincode Crossbow net8.0 6.0.136.0, .NET SDK 10.0.400, and gcc 16.2.0 (msys2,
`x86_64-w64-mingw32`) for the DLL. The **float backend is NATIVE** (NR-09's
admitted x86 backend); no soft-float build of the CICS path exists.

### V1 — C-04, before the adapter's bodies were written

```
$ mingw32-make c04
lint_c04: 80 distinct external names examined
  ONFLY     0 names longer than 8 characters
  SOFTFLOAT 0 names longer than 8 characters
  OTHER     2 names longer than 8 characters
      ___udivdi3 (10)
      ___umoddi3 (10)
  no case-insensitive collisions in the first 8 characters
lint_c04: every external satisfies C-04
```

`onfcini`, `onfcrun`, `onfcend`, `onfclen` are 7 characters each and do not collide
with `onfcont` or `onfcrc`.

### V2, V6 — the build, and BUZZ compile-only

```
$ python tools/cicsbld.py build/cics
=== column 72 check (VL-37) ===
  OK   2 sources within 72 columns
=== the engine as a 64-bit shared library ===
=== the .NET LINK target ===  Build succeeded. 0 Warning(s) 0 Error(s)
=== tests/tstcics.c ===
=== the BUZZ mapset ===
    Generating code for Mapset ONFCBUZ with based structures.
    Saved physical mapset at ...\bmsout\ONFCBUZ.xml
=== the transactions ===   (ONFCSUG.cbl, ONFCBUZ.cbl — both clean)
cicsbld: OK
```

### V3, V4 — the gate

```
$ python tools/cicsbld.py build/cics --run
run_cics: 3 checks, 0 failed
  V4 PASS  2060 bytes, 5 records, byte-identical
  V3 PASS  transaction FP=BAF81D91 RC=0, equal to the batch response
  V3 PASS  2 readout entries agree with the batch response
```

The transaction's own output, from that run:

```
ONFCSUG request code=SUGR
ONF001I NETWORK LOADED: ...onfnet-malecns-v1.0-srext.bin
ONFCSUG SUGR     RATE=   40 MS= 1000 SEED=        1 RC=   0 FP=BAF81D91
ONFCOUT  ID=        9 SPK=  27 LAT=    25800 HZ=     27.0
ONFCOUT  ID=       88 SPK=   0 LAT=       -1 HZ=      0.0
```

`BAF81D91` is G-16's recorded fingerprint — the same value D-370's negative control
moved to `DE3ED68A` when the kernel was deliberately broken. MN9 (identifier 9) fired
27 spikes with a first-spike latency of 25800 µs.

## 7. What is NOT proven

- **Platform.** x86-64 Windows only. Nothing about z/OS, where the LINK target would be
  a C program from IBM's compiler rather than a .NET module over a DLL; nothing about
  Linux s390x; nothing about MVS 3.8j, which VL-32 settles separately — TK5 cannot
  compile `EXEC CICS` at all.
- **Fidelity.** QIX is an emulation of CICS. VL-02's caveat — a proxy pass is not proof
  — applies here one level up.
- **Reentrancy.** Section 3.7's `CONCURRENCY(REQUIRED)` obligation is *addressed by
  design* (no static state anywhere in the adapter) and **not tested**: one `rclrun` run
  unit runs one task, so a reentrancy defect could not surface here.
- **BUZZ has never executed.** `SEND MAP` and `RECEIVE` return `INVREQ`, `RESP2` 999,
  with no `.rclic` licence present (VL-37). `ONFCBUZ.cbl` is compile-verified and map-
  verified only. Its logic — field validation, the LINK, the screen fill — is unrun.
- **A second compiler over the same engine.** The DLL is built by gcc 16.2.0 x86_64
  while the batch engine is built by MinGW 6.3.0 mingw32. That is a real divergence
  risk, and what contains it is V4: the two produce byte-identical responses or the
  build fails.
- **One request under the runtime.** V3 drives G-16 only. V4 covers all five `srext`
  golden requests.
- **The reflection in `run_cics.py` is none** — the deleted host's reflective read went
  with it.

## 8. Follow-ups (out of scope)

- `ONFLYENG` is both the batch load module's name and the LINK target's. Section 3.7
  names it, so it was not changed, but on z/OS these would be two different load
  modules and the collision should be settled before Phase H.
- The `srext` half of ACC-5 row 7 still has no `path` counterpart (carried from D-348).
- Stage 5 of P-17, the MVS streaming half of the live view, remains unbuilt.
- Phase G's second component, the 3270/INTERCOMM flow on TK5 (D-131), is untouched.

## 9. Related docs

- `docs/plan/2026-09-17-phase-g-cics-transaction.md` — P-22, the plan of record
- `docs/implementations/2026-09-11-raincode-cics-probes-measured.md` — the D-129 probes
- `docs/ONFLY-SRS.md` Section 2.2, Section 3.7, Section 4.3, Section 8.4, Section 9.2,
  Appendix A.1 (D-391…D-400), Appendix A.2 (P-22), Appendix D (VL-02, VL-32, VL-37,
  VL-117)
