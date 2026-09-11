# Raincode probes — does the free edition *run* CICS? (D-129)

These are not tests. They are a measurement, and they existed to settle
one fact: Raincode's compiler demonstrably **compiles** `EXEC CICS`, but
nothing in their documentation said whether the free download includes
**QIX**, the runtime that actually executes it (VL-34). "Compiles CICS"
and "runs CICS transactions" were not known to be the same offer, and
that single fact decides how ONFLY's transaction layer gets built.

**They have now been run. The answer is: half.** See VL-37, and the
result table below. Program-to-program CICS runs; terminal CICS does
not.

Nothing here is wired into `make test` — none of it can run without
Raincode installed, and the suite must stay runnable on a bare checkout.

## What each probe asks, and why in this order

| Probe | Files | Asks | Result |
|---|---|---|---|
| 1 | `ONFCLNK.cbl`, `ONFCENG.cbl` | Does `EXEC CICS LINK` with ONFLY's real 412-byte COMMAREA compile, run, and come back intact? | **Compiles and passes** |
| 2 | `ONFCTRM.cbl` | Is there a terminal at all? (`SEND TEXT`, no BMS) | Compiles; **will not run** |
| 3 | `ONFCMS.bms`, `ONFCMAP.cbl` | Does BMS exist — can a map be assembled and used? | Map **assembles**, program compiles; **will not run** |

The order was deliberate: each probe adds exactly one unknown. Probe 1
needs no terminal, so a failure there would have been about LINK or the
record. Probe 2 needs a terminal but no map. Probe 3 needs both plus a
map assembler, which was the thing most likely to be missing.

Probe 1 is the one that matters most. Section 3.7 says "ONFLYENG will be
LINKed with the COMMAREA of IR-COM" — probe 1 is that sentence compiled,
and it now also runs.

## Running them

Driven by `tools/rcprobe.py`, which finds the installation, reads the
machine-level environment the installer set (a shell started before the
install does not have `RCDIR`, and `cobrc` refuses to run without it),
and executes the steps below. What follows is what it actually does, not
a recipe taken from documentation.

```
python tools/rcprobe.py                 # all steps
python tools/rcprobe.py --run           # just the run step
```

Compile, from the probe directory, with the repository's real copybook
directory on the include path:

```
cobrc.exe :IncludeSearchPath=<repo>/generated :FatalMissingIncludes=TRUE :QIX=TRUE ONFCENG.cbl
```

`:FatalMissingIncludes=TRUE` matters: it is **off** by default, which
would let a missing `COPY ONFCOM` pass quietly and resurface later as a
mysterious undefined name. With it on, a clean compile is evidence the
copybook resolved.

Assemble the BMS mapset, in the IBM single-copybook shape:

```
rcbms.exe -Language=cobol -GenBasedSymbolicMap=true -CopybooksOutputDirectory=bmsout -MapsOutputDirectory=bmsout ONFCMS.bms
```

`-GenBasedSymbolicMap=true` is the one that matters. The default,
`-GenSymbolicMap`, writes **two** files (`ONFCMSI.cpy`, `ONFCMSO.cpy`);
IBM's `TYPE=DSECT` produces one copybook whose output structure
redefines its input structure, and `-GenBasedSymbolicMap` is that shape —
`01 ONFCMPO REDEFINES ONFCMPI`. `ONFCMAP.cbl` says `COPY ONFCMS` and
needs the single file.

Run — no C# host is required, which is what `--howrun` was looking for:

```
rclrun.exe -Qix=true ONFCLNK
```

`rclrun` has a whole QIX section (`-QixCommarea`, `-QixApplId`,
`-QixSysId`, `-QixDumpCommareaOnExit`, and more). The shipped
`samples/Getting started/qix_factory` sample builds an `ExecutionContext`
with `QixMode = true` in C# and drives `ec.QixInterface.Operation.Link()`
directly; `-Qix=true` reaches the same place without writing one.

## What was measured

Probe 1:

```
ONFCLNK request  code=SUGR
ONFCENG entered  code=SUGR
ONFCLNK reply    spikes(1)=  138
ONFCLNK reply    lat(1)   = 6200
ONFCLNK PASS link and commarea intact
```

Probes 2 and 3 abend instead:

```
INVREQ: RECEIVE (APPC) not implemented        <- ONFCTRM
INVREQ: SEND MAP not implemented              <- ONFCMAP
```

Terminal statements are not implemented in the standalone `rclrun`
context, which holds no terminal facility. They belong to
`QIX.TerminalServerRunner.exe` — **and that refuses to start**:

```
No valid license found. You are not allowed to use this program any more.
Scanned folder for (*.rclic)
```

No `.rclic` exists anywhere in the installation, and the Installation
Guide only explains how to *relocate* one during an upgrade. `QIX.Cmd.exe`
fails identically. The terminal server also wants `-ConfigConnectionString`,
a SQL Server database holding the region configuration, so a licence alone
would not be the last step.

### The statement-level picture

Taken with `RESP` on every statement, so a condition reports itself as a
value instead of abending the run:

| Statement | Free `rclrun -Qix=true` |
|---|---|
| `LINK` + `COMMAREA` + `LENGTH` | works |
| `WRITEQ TS` / `READQ TS` | works, exact round trip |
| `ASKTIME`, `FORMATTIME` | works |
| `ASSIGN` | returns `RESP` 0, `APPLID` blank (no region) |
| `RETURN` | works |
| `SEND TEXT` | `INVREQ`, `RESP` 16 / `RESP2` 999 |
| `SEND MAP`, `RECEIVE MAP` | `INVREQ`, not implemented |
| `RECEIVE` | `INVREQ`, not implemented |

Every one of these **compiles**. The split is entirely at run time.

## A hazard found along the way

`cobrc` silently truncates source past **column 72** with no diagnostic.
A `VALUE` literal starting in column 55 was cut to its first 17
characters and compiled clean; the loss appeared only as short data
coming back off a TS queue. D-93 holds ONFLY's source to 80 columns —
this says the 72-column boundary needs checking mechanically too, since
this compiler will not tell you.

## What these probes deliberately do not prove

- **Nothing about the mainframe.** Raincode targets .NET. Even a clean
  pass says nothing about MVS or z/OS, and TK5 still cannot compile
  `EXEC CICS` at all (VL-32) — that has not changed.
- **Nothing about the engine boundary.** These probes LINK COBOL to
  COBOL. ONFLY's engine is C89, and how a Raincode COBOL program on .NET
  reaches it is a different and unanswered question. On MVS the driver
  and engine talk through JCL steps and files (D-08).
- **Nothing about fidelity.** QIX is an emulation of CICS, not CICS. The
  same caveat VL-02 records for the GnuCOBOL dialect proxy applies here
  one level up: a proxy pass is not proof.
- **Nothing about licensing terms.** Whether Raincode would issue a key
  for the terminal server on request is a commercial question; no
  measurement here settles it.
- **`ONFCENG.cbl` duplicates the generated layout by hand.** That is
  allowed in a probe and forbidden in the real driver, where IR-COM-01
  governs. The note in that file explains why the copy exists and what
  the clean answer (`COPY ... REPLACING`) would need.

## Dialect

The COBOL is written in the MVT / Enterprise intersection D-17 fixes — no
scope terminators, no inline `PERFORM`, no `COMP-5` — even though nothing
forces that here. **Raincode accepted all of it unchanged**, which is the
useful half of the result: it means ONFLYDRV can plausibly be one source
across both worlds. Note that `rcbms` generates `COMP-5` length fields in
its symbolic maps, but that is generated per-platform, exactly as
`DFHMDF` generates `COMP` ones on MVS, and does not reach ONFLY's own
source.
