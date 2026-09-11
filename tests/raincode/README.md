# Raincode probes — does the free edition *run* CICS? (D-129)

These are not tests. They are a measurement, and they exist to settle one
fact: Raincode's compiler demonstrably **compiles** `EXEC CICS`, but
nothing in their documentation says whether the free download includes
**QIX**, the runtime that actually executes it (VL-34). "Compiles CICS"
and "runs CICS transactions" are not yet known to be the same offer, and
that single fact decides how ONFLY's transaction layer gets built.

Nothing here is wired into `make test` — none of it can run without
Raincode installed, and the suite must stay runnable on a bare checkout.

## What each probe asks, and why in this order

| Probe | Files | Asks |
|---|---|---|
| 1 | `ONFCLNK.cbl`, `ONFCENG.cbl` | Does `EXEC CICS LINK` with ONFLY's real 412-byte COMMAREA compile, run, and come back intact? |
| 2 | `ONFCTRM.cbl` | Is there a terminal at all? (`SEND TEXT`, no BMS) |
| 3 | `ONFCMS.bms`, `ONFCMAP.cbl` | Does BMS exist — can a map be assembled and used? |

The order is deliberate: each probe adds exactly one unknown. Probe 1
needs no terminal, so a failure there is about LINK or the record. Probe
2 needs a terminal but no map. Probe 3 needs both plus a map assembler,
which is the thing most likely to be missing.

Probe 1 is the one that matters most. Section 3.7 says "ONFLYENG will be
LINKed with the COMMAREA of IR-COM" — probe 1 is that sentence compiled.

## Running them

From Raincode's Getting Started: the compiler is `%RCBIN%\cobrc.exe` and
the runner is `%RCBIN%\rclrun.exe`. CICS is not a separate compile step —
their documentation says the statements "translate to calls to the legacy
program execution context", and that context must be started with
`QixMode = true`. So there is a host side, set up outside the COBOL.

```
%RCBIN%\cobrc.exe ONFCENG.cbl
%RCBIN%\cobrc.exe ONFCLNK.cbl
```

`ONFCLNK` does `COPY ONFCOM`, which lives in `generated/ONFCOM.cpy` at
the repository root — point the compiler's copybook path there.

**Exact options and the QIX host setup are not stated here**, because I
have not run Raincode and will not guess at a command line and present it
as fact. Take them from their Getting Started guide; the probes are the
part that is ONFLY-specific.

## Reading the result

| What happens | What it means |
|---|---|
| Probe 1 compiles **and runs**, `ONFCLNK PASS` | The free edition runs CICS. ONFLY can be written in real `EXEC CICS` and developed on the PC. |
| Probe 1 compiles, nothing will run it | The free edition is a compiler only. The CICS API is available for authoring; the runtime is not. INTERCOMM stays the only way to see a transaction execute before z/OS. |
| Probe 1 will not compile | Read *why* before concluding. `COPY` failing is a finding about COPY, not about CICS — paste the copybook inline and run again. |
| Probe 2 works, probe 3 does not | A transaction can be driven from a 3270 but not with formatted screens. D-127's flow is still possible, just character output instead of a menu. |
| Probes 2 and 3 both work | The whole of D-127's 3270 half is reachable on the PC, and `ONFCMS.bms` is the seed of the real BUZZ map. |

## What these probes deliberately do not prove

- **Nothing about the mainframe.** Raincode targets .NET. Even a clean
  pass says nothing about MVS or z/OS, and TK5 still cannot compile
  `EXEC CICS` at all — that has not changed.
- **Nothing about the engine boundary.** These probes LINK COBOL to
  COBOL. ONFLY's engine is C89, and how a Raincode COBOL program on .NET
  reaches it is a different and unanswered question. On MVS the driver
  and engine talk through JCL steps and files (D-08).
- **Nothing about fidelity.** QIX is an emulation of CICS, not CICS. The
  same caveat VL-02 records for the GnuCOBOL dialect proxy applies here
  one level up: a proxy pass is not proof.
- **`ONFCENG.cbl` duplicates the generated layout by hand.** That is
  allowed in a probe and forbidden in the real driver, where IR-COM-01
  governs. The note in that file explains why the copy exists and what
  the clean answer (`COPY ... REPLACING`) would need.

## Dialect

The COBOL is written in the MVT / Enterprise intersection D-17 fixes — no
scope terminators, no inline `PERFORM`, no `COMP-5` — even though nothing
forces that here. If Raincode rejects that style, it is worth knowing
early: it would mean ONFLYDRV cannot be one source across both worlds.
