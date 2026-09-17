# 2026-09-17 — Phase G, first component: the `EXEC CICS` transaction

| Field | Value |
|---|---|
| Date | 2026-09-17 |
| Author | Senior engineer, for owner approval |
| Phase / gate | Phase G — transaction demonstrator (second MVP), `EXEC CICS` half |
| Owner decisions relied on | D-130, D-131, D-392, D-393, D-394, D-395 (this session); D-129, D-224, D-366, D-383 |
| Requirements touched | IR-COM-01…06, FR-SIM-07, FR-BAT-05, C-03, C-04, NR-05, Section 3.7, ACC-5 |
| Open items closed | none — this is a plan, not an implementation |
| Status | **PROPOSED (P-22). Not approved. No ONFLY code written yet.** |

This file is a plan, so it is not in `docs/implementations/`; that directory records
what was done. The implementation document is written when the work lands.

## 1. Problem / motivation

Section 9.2's Phase G row names three components. The third — the live view — landed
on 2026-09-16/17 as Stages 1 to 4 (D-364…D-390). The **first** is still unbuilt:

> ONFLY as a transaction written in real `EXEC CICS`, verified against Raincode on the
> development host (D-130, VL-37)

What exists today is four *probes* from D-129 in `tests/raincode/`. They answered
whether the compiler and runtime work. They do not contain ONFLY's transaction: their
LINK target, `ONFCENG.cbl`, is a COBOL stub whose own comments say *"It computes
nothing — the engine is C and lives elsewhere."* VL-37 closes on the gap in so many
words:

> nothing about the engine boundary: these probes LINK COBOL to COBOL, while ONFLY's
> engine is C89 and how a Raincode COBOL program on .NET would reach it remains
> unasked.

D-395 asked it, and the probe below answers it.

## 2. What the probe measured (this session, x86-64 Windows)

Run under D-395, thrown away afterwards; the numbers are recorded here and in
Appendix D because the design rests on them. `PRBLNK.cbl` (COBOL, `EXEC CICS LINK`) →
`PRBCS` (C# module) → `prbnat.dll` (gcc). Output:

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

| # | Finding | Consequence for the design |
|---|---|---|
| 1 | `EXEC CICS LINK` reaches a `[RainCodeExport]` C# module **only** if the module calls `SetIsQIXModule()` in its constructor; without it the LINK abends `Module PRBCS not compiled as a QIX module but called using QIX LINK` | One line in the module, and a comment saying why, or the next reader deletes it |
| 2 | P/Invoke from that module into a gcc-built DLL works | The engine is reachable in-process; D-395's choice is viable |
| 3 | The COMMAREA arrives as **parameter 0**, arity 1 — there is no separate DFHEIBLK parameter | `GetParameterAddress(ec, 0)` |
| 4 | `parm[0].Size` is **257448**, not the record length | The module must trust the length the LINK declares and **never** the area size. Reading `Size` bytes would read the whole address-space slice |
| 5 | `S9(9) COMP` is big-endian here (`00-00-00-07`) and `X(4)` is ASCII (`20-20-20-20`) | IR-COM-04 holds unchanged; IR-COM-05's exclusion of text fields is what keeps the fingerprint identical to the EBCDIC hosts |
| 6 | `-AutoMapAssembliesDirectory=<dir>` fails with `PE image does not have metadata` if a **native** DLL sits in that directory | Map the managed assembly by name: `-AutoMapAssembly=onfceng` |
| 7 | The DLL must be built by the msys2 **x86_64** gcc. The Makefile's `CC = gcc` is MinGW 6.3.0, target `mingw32` — a 32-bit DLL cannot be P/Invoked from 64-bit .NET | The `cics` target uses its own `CC`, defaulted and overridable, and says so |
| 8 | That gcc exits 1 with **no diagnostic at all** unless `C:\msys64\mingw64\bin` is on `PATH` | The build tool puts it there and reports if the compiler is missing, rather than printing an empty failure |

## 3. What is built

Seven files. Nothing generated is edited by hand (IR-COM-01).

| Path | What it is |
|---|---|
| `cics/ONFCSUG.cbl` | The **SUGR direct transaction** (D-393). Real `EXEC CICS`, MVT/Enterprise intersection (C-03, D-17). Builds the COMMAREA through `COPY ONFCOM`, `EXEC CICS LINK PROGRAM('ONFLYENG')`, formats the reply, records it |
| `cics/ONFCBUZ.cbl` | The **BUZZ menu transaction** (D-393). `RECEIVE MAP`, validate, LINK, `SEND MAP`. Compiled and map-generated only: `SEND MAP`/`RECEIVE` return `INVREQ` on this installation (VL-37) |
| `cics/ONFCBUZ.bms` | The BMS map for BUZZ: stimulus, rate, duration, seed in; spike count, latency, Hz, return code, fingerprint out |
| `cics/onfceng.cs` | The LINK target. `[RainCodeExport("ONFLYENG")]`, `SetIsQIXModule()`, **layout-blind** — it copies 412 opaque bytes in and out and P/Invokes the engine. It never names a field |
| `cics/onfceng.csproj` | References the installed Raincode assemblies by `HintPath`; **no NuGet restore, no network** |
| `engine/src/onfcics.c` | The C89 CICS adapter. Three entries, handle-based, no static state |
| `tools/cicsbld.py` | Drives the whole chain and reports; the `make cics` body |
| `tests/test_cics.py` | The check: the transaction's response must equal the batch engine's for the same request |

### 3.1 The C adapter (`engine/src/onfcics.c`)

```c
void *onfcini(const char *netpath, int *rc);   /* load a network, return a handle */
int   onfcrun(void *h, unsigned char *ca, int len);  /* one request, in place */
void  onfcend(void *h);                         /* release it */
```

**Handle-based, deliberately.** A file-scope pointer would be simpler and it is what
the batch adapter can afford, because a batch step is one task. Section 3.7 requires
the opposite of that: *reentrant and threadsafe, `CONCURRENCY(REQUIRED)`*. A handle
costs one parameter and removes the whole question. The anchor lives in the caller,
which is exactly where CICS shared storage lives.

`onfcrun` does **not** re-implement anything. It decodes the request from the COMMAREA
and calls the shared request sequence `onfrq1` — the same one the batch engine, the
MVS driver and `tstgld` use (D-224), and which D-383 split into `onfrqb`/`onfrqc`/
`onfrqe`. So the bytes crossing this boundary are the bytes TX-01 and TX-02 already
prove, not a second implementation of them.

C89 plus `long long`; no `float`, no `double`, no floating-point literal (NR-05);
explicit byte shifts, no pointer casts over the buffer (FR-LOD-05); external names
`onfcini`, `onfcrun`, `onfcend` are 7 characters each and are checked against
`tools/lint_c04.py` **before** the bodies are written (C-04).

### 3.2 The C# module (`cics/onfceng.cs`)

Three responsibilities and no fourth:

1. `SetIsQIXModule()` in the constructor (finding 1).
2. Copy `len` bytes out of parameter 0 — `len` from the LINK, never `area.Size`
   (finding 4) — hand them to `onfcrun`, copy the result back.
3. Hold the handle from `onfcini` for the life of the run unit, so the network is
   loaded once and every LINK only reads it (Section 3.7).

It is **layout-blind**: it declares no offsets and no field names. That is not a
convenience, it is IR-COM-01 — a hand-written C# restatement of the record would be a
third copy of a generated layout, which is the thing IR-COM-01 exists to forbid. The
COBOL side gets the layout from `COPY ONFCOM`; the C side from `generated/onfcom.h`.

### 3.3 The transaction (`cics/ONFCSUG.cbl`)

Real `EXEC CICS`, not INTERCOMM macros (D-130). Mode and flow:

```
build COMMAREA  (COPY ONFCOM — the generated layout, not a copy of it)
EXEC CICS LINK PROGRAM('ONFLYENG') COMMAREA(ONF-COMMAREA) LENGTH(412)
check ONF-RC
format: spike count, first-spike latency, rate in Hz to one decimal,
        return code and message, fingerprint in hexadecimal   (FR-BAT-04)
record the formatted result
EXEC CICS RETURN
```

**Where the result goes is the one open design question in this plan** (§7 Q1).

## 4. Numerical detail

None is new. The transaction changes no arithmetic: it hands 412 bytes to the same
`onfrq1` the batch path uses, and the response fingerprint is IR-COM-05's CRC-32 over
the same canonical byte string. The rate in Hz that FR-BAT-04 prints to one decimal is
computed by the COBOL from the integer spike count and the integer duration, exactly as
`ONFLYDRV` does it — no floating point enters the transaction.

The single claim this component makes numerically is an **equality**: for a given
request, the fingerprint the transaction returns equals the fingerprint the batch
engine returns. That is the exit criterion in §6.

## 5. Design decisions and the alternatives rejected

| Decision | Chosen | Rejected, and why |
|---|---|---|
| Engine boundary | In-process P/Invoke (D-395) | Out-of-process would reload the network per request and could not show Section 3.7's anchor; a COBOL stub proves nothing new |
| Adapter state | Handle | A file-scope pointer contradicts Section 3.7's reentrancy obligation and hides the question |
| C# layout knowledge | None — opaque bytes | A hand-written C# view is a third copy of a generated layout (IR-COM-01). A Raincode-generated view would be acceptable but adds a generator step for no gain, since the module needs no field |
| Request sequence | Reuse `onfrq1` | A CICS-specific request loop would be a second implementation of the one D-224 unified, and the drift D-289/D-360 record twice would have a third place to happen |
| Build | `make cics`, skipped when absent (D-394) | Joining `make test` breaks a bare checkout |
| Packages | `HintPath` to the installed assemblies | NuGet restore pulls fourteen third-party packages from the internet; the local `rcpackages` feed does not carry them |

## 6. Verification plan

Every row states platform, compiler, float backend, and what it does not prove.

| # | Command | Pass looks like | Will not prove |
|---|---|---|---|
| V1 | `python tools/lint_c04.py` | `onfcini`, `onfcrun`, `onfcend` present, no name over 8 characters, no case-insensitive collision | Only that the names are legal; not that GCCMVS accepts the file |
| V2 | `mingw32-make cics` | gcc builds the DLL, `dotnet build` the module, `rcbms` the map, `cobrc` both programs, all clean | x86-64 Windows only |
| V3 | `mingw32-make cics` (run step) | `ONFCSUG` runs under `rclrun -Qix=true` and its response fingerprint **equals the golden fingerprint of G-16** (`srext`, SUGR, 40 Hz, standard, seed 1) | That the engine is right — it is the *same* engine; what is proven is that the CICS path does not change it |
| V4 | `python tests/test_cics.py` | The full 412-byte response record from the transaction is byte-identical to the batch engine's for the same request | One request unless swept |
| V5 | `mingw32-make test` | still exits 0 on SOFT3E, SOFT2C and NATIVE — the new C file must not disturb the existing builds | Nothing about s390x or MVS |
| V6 | BUZZ | `rcbms` emits physical and symbolic maps; `cobrc` compiles `ONFCBUZ.cbl` against the symbolic map | **Compile only.** `SEND MAP`/`RECEIVE` cannot execute here (VL-37); the 3270 half is D-131's INTERCOMM work |

**What none of this proves, and must be said in the report:** nothing about z/OS, where
the LINK target would be a C program from IBM's compiler rather than a .NET module over
a DLL; nothing about real CICS threadsafety, since one run unit runs one task here;
nothing about MVS 3.8j, which VL-32 already settles cannot compile `EXEC CICS` at all.
QIX is an emulation of CICS, so VL-02's caveat — a proxy pass is not proof — applies
here one level up.

## 7. Open questions for the owner

1. **Where the transaction's result goes.** Under the free edition `SEND TEXT` cannot
   run (VL-37), so a direct transaction has no terminal. VL-37 measured `WRITEQ TS` and
   `READQ TS` working with an exact 24-byte round trip. Options: a **TS queue**, which
   is real CICS behaviour and is what a bridge or a later BMS program would read; a
   `DISPLAY`, which is not CICS at all but is what the probes use; or both.
2. **Whether the C# module and its project belong in `cics/` or in a new top-level
   directory.** `cics/` groups the component; but `lint_lic.py`, `lint_col80.py` and
   `lint_c04.py` all walk the tree, and C# is a language none of them has seen.
3. **Whether `ONFLYENG` is the right name for the LINK target**, given C-08: "CICS" is
   a trademark and appears only descriptively — that is satisfied — but `ONFLYENG` is
   also the batch load module's name, and on z/OS the CICS program and the batch program
   would be two different load modules with, presumably, two different names.

## 8. Related docs

- `docs/ONFLY-SRS.md` Section 2.2 (component table), Section 3.7 (CICS obligations),
  Section 4.3 (IR-COM), Section 8.4 (golden suite), Section 9.2 (Phase G row),
  Appendix A.1 (D-129, D-130, D-131, D-392…D-395), Appendix D (VL-02, VL-32, VL-34,
  VL-36, VL-37)
- `docs/implementations/2026-09-11-raincode-cics-probes-measured.md` — the D-129 probes
- `tests/raincode/README.md` — what each probe isolates
