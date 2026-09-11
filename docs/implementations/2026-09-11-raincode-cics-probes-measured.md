# 2026-09-11 — The Raincode CICS probes, run

| Field | Value |
|---|---|
| Date | 2026-09-11 |
| Author | Claude (ONFLY senior engineer session) |
| Phase / gate | Phase G (transaction demonstrator, second MVP) |
| Owner decisions relied on | D-126, D-127, D-129 |
| Requirements touched | Section 3.7 (BUZZ / ONFLYENG), IR-COM-01 |
| Open items closed | none — but D-129's question is now answered, and the answer forces an owner decision |

## 1. Problem / motivation

D-129 says Raincode's free edition is verified **before** the transaction plan
commits to it. The reason is narrow and load-bearing: VL-34 established that
Raincode's compiler accepts `EXEC CICS` natively, and VL-36 established from the
installer's File table that the QIX runtime binaries ship with it — but neither
showed that a CICS transaction *runs*. "Compiles CICS" and "runs CICS" were not
known to be the same offer.

Without that fact the Phase G plan is a guess. D-127 commits Phase G to showing
the transaction flow **on a real 3270** plus a live view of the network. If the
free edition cannot execute a terminal statement, that half of D-127 is not
reachable on this host and the plan has to change — which is much cheaper to
discover now than after a transaction layer is written against it.

## 2. What changed

| File | Change |
|---|---|
| `docs/ONFLY-SRS.md` | Added VL-37 to Appendix D: the measured result, including the correction it forces on VL-36. |
| `tools/rcprobe.py` | Added `--cols`, `--bms` and `--run` steps; fixed a `UnicodeEncodeError` that killed the BMS step; widened the run filter so `ONFCENG entered` is shown. |
| `tests/raincode/README.md` | Replaced the "exact options are not stated here, because I have not run Raincode" caveat with the measured recipe and the statement-level result table. |
| `.gitignore` | Ignore `tests/raincode/*.dll`, `*.pdb` and `bmsout/` — compiler and map-assembler output. |

## 3. Implementation approach

The probes themselves were already written (D-129, previous session). This
change is the running of them, plus the tooling to make that reproducible.

`tools/rcprobe.py` now runs six steps in dependency order: `--inventory`,
`--cols`, `--bms`, `--compile`, `--run`, `--howrun`. Three are new.

**`--bms`** assembles `ONFCMS.bms` with `-GenBasedSymbolicMap=true`. This flag is
the whole reason the step needs a tool rather than a documented command. The
default, `-GenSymbolicMap`, writes **two** copybooks — an input structure and an
output structure in separate files. IBM's `TYPE=DSECT` writes **one**, whose
output structure redefines its input structure. `ONFCMAP.cbl` says `COPY ONFCMS`
once, as a program written for MVS would, so it needs the IBM shape;
`-GenBasedSymbolicMap` produces exactly that (`01 ONFCMPO REDEFINES ONFCMPI`).

**`--run`** invokes `rclrun.exe -Qix=true <program>`. This is the finding that
`--howrun` was built to produce and did not have to: Raincode's Getting Started
implies a C# host is required to put the execution context into QIX mode, and
the shipped `qix_factory` sample does exactly that. But `rclrun` has an entire
QIX option group (`-Qix`, `-QixCommarea`, `-QixApplId`, `-QixSysId`,
`-QixDumpCommareaOnExit`, …), and `-Qix=true` reaches the same place with no host
to write. `--howrun` is kept because the host route is the one that survives if
a program ever needs a custom QIX factory.

The run step deliberately **does not** fold its result into the exit code. On
this installation probes 2 and 3 are *expected* to abend; that abend is the
measurement, not a build failure, and reducing it to pass/fail would destroy the
information. It prints the deciding lines instead — program output, the abend
line, and any `not implemented` text — and filters .NET stack frames.

**`--cols`** checks every probe source against column 72 before anything is
compiled. Its contract: returns the count of over-long lines, prints one line
per offender, prints an "ok" line when there are none. See §5 for why it exists.

**Contract of the new functions.** `check_columns(limit=72)` reads every `.cbl`
and `.bms` under `tests/raincode`, has no side effects, returns an offender
count. `bms(rcbin)` writes into `tests/raincode/bmsout` (created by `main`),
returns 1 on a non-zero `rcbms` exit and 0 otherwise. `run_probes(rcbin)` runs
each program with empty stdin and a 300-second timeout, has no side effects on
the repository, and returns a count of programs that neither printed `PASS` nor
exited 0 — a number the caller currently ignores, by design.

## 4. Mathematical / numerical details

None. The one numeric claim is the COMMAREA round trip, which is an equality
check, not a computation: `ONF-RC` 7, `ONF-OUT-COUNT` 2, `ONF-STEPS` 10000 and
the `S9(4)`/`S9(9) COMP` output slots returned bit-identical to what `ONFCENG`
wrote, with the request fields unchanged. That is the property IR-COM-01 needs
from a LINK and it either holds or it does not.

## 5. Design decisions

**Measuring the statement set with `RESP` instead of one probe per statement.**
Probe 2 abended on `RECEIVE` before it ever reached `SEND TEXT`, so "probe 2
failed" did not say which statements work — and the difference matters, because
`SEND TEXT` working would mean character output is reachable without the
terminal server. A scratch program carrying `RESP` on every statement turns each
condition into a value instead of an abend, so one run reports on all of them.
That produced the statement table in the probes README: `LINK`, `WRITEQ TS`,
`READQ TS`, `ASKTIME`, `FORMATTIME`, `ASSIGN` and `RETURN` work; `SEND TEXT`,
`SEND MAP` and `RECEIVE` do not. The alternative — one probe per statement —
costs a compile and a run each and answers no more.

**Why `--cols` exists, and why it is a tool rather than a note.** `cobrc`
silently truncates source past column 72 with **no diagnostic**. A `VALUE`
literal beginning in column 55 was cut to its first 17 characters and compiled
clean; the loss appeared only as short data coming back off a TS queue, and it
was briefly mistaken for a defect in Raincode's TS implementation before the
column arithmetic was checked. That is the second time this project has lost
time to a fixed-format column boundary — the first was the JCL PARM card at
column 71 — and the lesson both times is that the boundary must be checked
mechanically, because the tool downstream will not report crossing it. D-93
already holds ONFLY's source to 80 columns; this is the narrower margin that
this particular compiler cares about.

**Not folding the run result into the exit code.** Considered and rejected:
making `--run` fail the tool would be correct if the probes were tests. They are
not; they are a measurement, and the expected outcome on this installation
includes two abends. A tool that reports "failed" for the documented result
trains its reader to ignore it.

**Ignoring the build products rather than committing them.** `.dll` and `.pdb`
files are compiler output and `bmsout/` is map-assembler output. The project
rule that generated layout files are never edited by hand applies here in its
stronger form: they are not stored either.

## 6. Verification

From a clean checkout with Raincode Crossbow net8.0 installed:

```bash
python tools/rcprobe.py
```

Expected, and what was observed on 2026-09-11:

- `--inventory`: all six binaries present.
- `--cols`: "every probe source ends by column 72".
- `--bms`: exit 0, "Saved physical mapset", producing `bmsout/ONFCMS.cpy` and
  `bmsout/ONFCMS.xml`.
- `--compile`: all four of `ONFCENG`, `ONFCLNK`, `ONFCTRM`, `ONFCMAP` exit 0.
- `--run`: `ONFCLNK` prints

  ```
  ONFCLNK request  code=SUGR
  ONFCENG entered  code=SUGR
  ONFCLNK reply    spikes(1)=  138
  ONFCLNK reply    lat(1)   = 6200
  ONFCLNK PASS link and commarea intact
  ```

  and exits 0. `ONFCTRM` and `ONFCMAP` abend `INVREQ: RECEIVE (APPC) not
  implemented` and `INVREQ: SEND MAP not implemented` respectively.

`ONFCENG entered` is the line that matters in probe 1: without it the caller
could be answering itself, and the LINK would not be proven to have dispatched.

To reproduce the licence wall directly:

```bash
"$RCBIN/QIX.TerminalServerRunner.exe" -TcpPort=3270 -Region=ONFLY
```

fails with "No valid license found … Scanned folder for (\*.rclic)". No `.rclic`
exists anywhere in the installation.

**What none of this verifies** is listed in VL-37 and in the probes README: it
says nothing about MVS or z/OS, nothing about QIX's fidelity to real CICS,
nothing about the C89 engine boundary, and nothing about whether Raincode would
issue a licence on request.

## 7. Related docs

- `docs/ONFLY-SRS.md` — VL-32 (no CICS on TK5, INTERCOMM works there), VL-34
  (Raincode's documented claims), VL-36 (the installer inventory), **VL-37**
  (this measurement), D-126 / D-127 / D-128 (Phase G scope), D-129 (verify
  before committing).
- `tests/raincode/README.md` — the probes, the recipe, the statement table.
