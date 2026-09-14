# 2026-09-14 — Gate G0: the environment, measured

| Field | Value |
|---|---|
| Date | 2026-09-14 |
| Author | Engineer, with the owner deciding scope and standard |
| Phase / gate | **Gate G0 — Environment** (SRS Section 9.1); Phase A |
| Owner decisions relied on | D-235 (scope), D-237 (plan, and authority to start both labs), D-238 (evidence standard), D-239 (x86 proof), D-240 (authorised SRS text changes), D-236 (push target) |
| Requirements touched | A-03, A-04 (Section 2.6); NR-11 and NR-14 incidentally; NFR-PERF-02 |
| Open items closed | A-03 and A-04 leave "TBC at Gate G0" |

## 1. Problem / motivation

Gate G0 asks "Is every lab platform ready?". Its exit criterion names four
things: TK5 Update 5 running; GCCMVS and JCC inventory recorded; Linux s390x
with gcc under QEMU; x86 Python environment.

**It had never been closed, and the defect was in the record, not the lab.**
Every other gate in Section 9.1 carries a date, a decision number and its
measured evidence — G1 "CLOSED 2026-09-11 (D-119)", G2 "CLOSED 2026-09-12
(D-150)", G4 "CLOSED 2026-09-12 (D-161)", G3 "MEASURED 2026-09-11 (VL-41)".
G0's row carried none of the three. `grep -rn 'G0' docs/implementations/`
returned only incidental mentions inside the Gate G1 documents. And A-03 and
A-04 still read "TBC at Gate G0" in the Section 2.6 assumptions table, after
a G1, a G2 and a G4 that used GCCMVS daily.

Phase A's row in Section 9.2 lists G0 first among its contents. So Phase A was
not in fact complete, and Phase E's dependency on it was not in fact met. The
owner stopped the session's proposed Phase E work for exactly this reason
(D-235).

**The failure this prevents** is not hypothetical. Usage is not a record: the
project had been relying on GCCMVS for three days while its own contract still
said the compiler's presence was unconfirmed, and — as §3.2 below shows — the
one sentence anybody had written about where GCCMVS lives was filed inside a
Gate G1 document as a correction to an earlier mistake, where no reader of the
assumptions table would ever find it.

## 2. What changed

| File | Change |
|---|---|
| `tools/g0.py` | New. The Gate G0 inventory: host facts, the x86 clause, the MVS liveness clause, the s390x clause, and the one C probe every platform builds. Merges each section into `data/g0/inventory.json`. |
| `tools/mvsg0.py` | New. The MVS half: the catalog job that runs A-03's and A-04's own commands, and the two compile-link-go jobs that make GCCMVS and JCC prove themselves. |
| `data/g0/inventory.json` | New. The gathered record, raw output and parsed answer side by side. |
| `docs/ONFLY-SRS.md` | A-03 and A-04 status cells replaced with what was measured; D-235…D-240 added to Appendix A.1; VL-86…VL-89 added to Appendix D; Section 9.1's G0 row annotated. |
| `data/networks/*.bin` | Not a change to the repository — these are gitignored fixtures, hard-linked into this worktree from the Phase D worktree and verified against `MANIFEST.json` (§3.4). |

## 3. Implementation approach

### 3.1 "Present" versus "present and working" (D-238)

The exit criterion's word is "inventory", which a catalog listing would satisfy
literally. The owner chose the stronger reading: every platform must **run**
something in this session. That choice is what turned the gate from a
paperwork exercise into a measurement, and it is what produced §3.2.

So each toolchain builds and runs one probe, `g0.probe_source()`. It is the
smallest C that can carry the evidence, and it is deliberately shared between
MVS and s390x so their answers are comparable line for line:

```c
w = 0x01020304UL;
b0 = (unsigned int)((w >> 24) & 0xFFUL);
printf("ONFG0 VERSION %s\n", __VERSION__);      /* guarded by #ifdef */
printf("ONFG0 STDC %d\n",     (int)__STDC__);
printf("ONFG0 INTBITS %d\n",  (int)(sizeof(int) * 8));
printf("ONFG0 LONGBITS %d\n", (int)(sizeof(long) * 8));
printf("ONFG0 TOPBYTE %02X\n", (int)b0);
```

Three properties of it are deliberate:

- **The version string comes back from a running binary**, not from a
  filename or a configuration file. That is a different and much stronger
  claim: it says the compiler front end, the assembler, the linkage editor
  and the runtime all work.
- **Byte order is observed by shifting**, never by casting a pointer over the
  bytes — FR-LOD-05's rule applied to the probe itself.
- **`__VERSION__` is guarded by `#ifdef`.** It is a GCC macro. JCC is a
  different compiler and does not define it; unguarded, "JCC publishes no
  version macro" would have been reported as "JCC cannot compile the probe".

`INTBITS` is not decoration. NR-11 requires `int` to be 32 bits, and NR-14
requires the integer self-test to cover the width the platform's engine
actually uses. Both MVS compilers report `INTBITS 32`, `LONGBITS 32`; the
s390x guest reports `INTBITS 32`, `LONGBITS 64`.

### 3.2 A-03's own probe gives the wrong answer

A-03 and A-04 are written as commands, so `tools/mvsg0.py` runs those commands
rather than paraphrasing them — under IKJEFT01, the batch terminal monitor,
because `LISTC` is a TSO command, with IDCAMS `LISTCAT` beside it under
`COND=EVEN` so the record says which utility answered.

The result for A-04 is clean: 12 `JCC.*` datasets. The result for A-03 is not:

```
 LISTC LEVEL(GCC) ALL
IDC3012I ENTRY GCC. NOT FOUND+
IDC3007I ** VSAM CATALOG RETURN CODE IS 8
```

There is no `GCC.*` dataset on this system at all. **The command A-03 names
cannot confirm A-03.** GCCMVS is the load module `SYS2.LINKLIB(GCC)`, an
*alias* of `GCC370`, on TK5RES, resolved through the linklist; its runtime is
the three `PDPCLIB.*` datasets on TK5002, which `LISTC LEVEL(PDPCLIB)` does
find.

That fact existed in the repository, as a correction buried in §3.3 of
`2026-09-11-gate-g1-on-mvs.md`, where the assumptions table never pointed. It
is now in A-03 itself, which is the only place a reader of the contract would
look.

Getting there took two wrong turns, both recorded because both are instructive:

- The first catalog job named `VOL=SER=PUB000` for an `IEHLIST` step. That is
  a TK4- volume; TK5's are TK5RES/TK5CAT/TK5001/TK5002/WORK0n/TSO00n. MVS did
  not fail the step — it stopped and asked the operator,
  `*00 IEF238D ONFG0CAT - REPLY DEVICE NAME OR 'CANCEL'`, and held the job
  until answered. `LISTDS` replaced it: a TSO command needs no volume and
  cannot hang a job.
- Reading the member list by eye then concluded `SYS2.LINKLIB` held no `GCC`,
  and that the Gate G1 document was wrong about the library. It does hold it,
  and Gate G1 was right. `LISTDS` prints an alias as `GCC  ALIAS(GCC370)`, and
  the throwaway pattern used to skim the listing anchored at end of line, so
  it skipped every alias — including the one entry that answers A-03. It
  counted 483 members where the alias-aware `parse_catalog()` counts 505. The
  lesson is the reason `parse_catalog()` exists at all: a gate record must be
  produced by code that is reviewed, not by a regex typed at a prompt.

### 3.3 What the gate record stores

`data/g0/inventory.json` keeps the raw printer output **and** a parsed answer.
A gate record that forces its reader to re-parse 2,500 lines of JES2 output is
not a record. `parse_catalog()` extracts three things: what `LISTC LEVEL(x)`
said for each level including NOT FOUND, each listed library with its volume
and the members that matter to ONFLY, and `SYS1.PARMLIB(LNKLST00)` — which is
what makes `EXEC PGM=GCC` resolvable at all.

Two bugs in that parsing were found and fixed while writing it, and both would
have produced a confidently wrong record:

- Each `mvsg0` run replaced the whole `mvs` section, so running `--jcc` alone
  deleted the catalog results. The gate record then silently held one third of
  its evidence. Both `mvsg0.main()` and `g0.main()` now merge.
- The last `LISTC` block ran to end of file and absorbed the IDCAMS section, so
  JCC reported 15 datasets instead of 12 and inherited GCC's NOT FOUND line.

### 3.4 Two things that were broken before any measurement could start

**The worktree's network fixtures were stale.** `data/networks/*.bin` is
gitignored, and this worktree held only `onfnet-malecns-v1.0-path.bin` at its
**v1.0** size, 885,416 bytes, where `MANIFEST.json` records v1.1 at 951,200;
`srext`, the MVP network, was absent entirely. The first `mingw32-make test`
therefore failed at the `req` target with
`netread.NetworkFileError: ONF103E UNSUPPORTED FORMAT VERSION`. The four
current networks were hard-linked from the Phase D worktree and **verified
against the committed digests** rather than trusted by filename — byte count
and CRC-32 both match for `full`, `hop2`, `path` and `srext`.

**The Hercules codepage had reset.** `tools/mvsg0.py` reported
`codepage was default, now 819/1047` on its first submission. This is exactly
the silent-failure class D-103 was written for: a restart returns Hercules to
`default`, where ASCII `|` arrives as EBCDIC 0x6A and GCCMVS will not lex it
(VL-18). Setting it is executing D-101, not deciding anything.

## 4. Mathematical / numerical details

None. Gate G0 measures an environment; it computes nothing. The one numeric
result recorded is Hercules' own highest observed rate, 45.633024 MIPS, kept
because NFR-PERF-02 requires every performance measurement to record it.

## 5. Design decisions

| Choice | Made by | Why |
|---|---|---|
| Close G0 before any Phase E work | Owner, D-235 | The gate row carried no date and no decision; Phase A therefore was not complete |
| "Present and working", not "present" | Owner, D-238 | Answering "is every platform ready?" from a catalog listing would be answering it by assumption |
| Full `mingw32-make test` as the x86 proof | Owner, D-239 | Strongest available statement, and it re-confirms nothing regressed since Phase D |
| Annotate the G0 row and A-03/A-04 | Owner, D-240 | Matches how G1, G2 and G4 are annotated; no requirement wording changes |
| One probe shared by MVS and s390x | Engineer | Four differently-worded answers would not be comparable |
| `LISTDS` rather than `IEHLIST` | Engineer | Forced by measurement: `IEHLIST` needs a volume, and a wrong one stops the job on an operator reply rather than failing it |
| Evidence from this session only | Engineer | The skill's rule: a result not produced in this session is not reported as one. Earlier sessions are cited as provenance and labelled as not re-measured |

## 6. Verification

**Platform for every MVS result:** MVS 3.8j TK5 under SDL Hercules
4.9.1.11612-SDL-gee86c4de (build date Dec 7 2025, Windows MSVC AMD64, modes
S/370 ESA/390 z/Arch), on x86-64 Windows 11 26200, Intel i7-13650HX, 15.6 GB.
Codepage 819/1047. Every figure is from a job submitted in this session through
the 3505 card reader and read back from `prt/prt00e.txt`.

### 6.1 Clause 1 — TK5 running

```
HHC01413I Hercules version 4.9.1.11612-SDL-gee86c4de
HHC01415I Build date: Dec  7 2025 at 03:49:55
HHC01417I Modes: S/370 ESA/390 z/Arch
/21.12.40   MVS038J MVS 3.8j TK5 system initialization complete CN=00
HHC02268I MIPS: 45.633024
```

Three jobs ran to completion: `ONFG0CAT`, `ONFG0GCC`, `ONFG0JCC`.

### 6.2 Clause 2 — GCCMVS and JCC

Command: `python tools/mvsg0.py --cat --gcc --jcc`

```
LISTC LEVEL(GCC) ALL      IDC3012I ENTRY GCC. NOT FOUND+      (0 datasets)
LISTC LEVEL(PDPCLIB) ALL  PDPCLIB.INCLUDE / .MACLIB / .NCALIB (3, TK5002)
LISTC LEVEL(JCC) ALL      JCC.CNTL ... JCC.TCPIP.SRC          (12, TK5002)

SYS2.LINKLIB  TK5RES  505 members  GCC (alias of GCC370), IKFCBL00
SYS2.PROCLIB  TK5RES  143 members  GCCC GCCCG GCCCL GCCCLG GCCISP5
                                   JCCC JCCCG JCCCL JCCCLG
                                   COBUC COBUCG COBUCL COBUCLG ...
LNKLST00  SYS1.LINKLIB, SYS1.PPLIB, SYS1.CMDLIB, SYS2.CMDLIB,
          NJE38.AUTHLIB(TK5001), SYS2.LINKLIB, SYS1.PL1LIB,
          SYS1.FORTLIB, SYS2.DSSLIB
```

GCCMVS — every step COND CODE 0000 (SCRATCH, ALLOC, WRITEC, COMP1, ASM1,
LKED, GO):

```
ONFG0 VERSION 3.2.3 MVS V8.5
ONFG0 STDC 1   INTBITS 32   LONGBITS 32   TOPBYTE 01
```

JCC — every step COND CODE 0000 (COMPILE, PRELINK, LKED, GO):

```
ONFG0 VERSION (no __VERSION__ macro)
ONFG0 STDC 1   INTBITS 32   LONGBITS 32   TOPBYTE 01
* Compiled by JCC - version 1.50.00      (from JCC's generated assembler)
JCC-RC:0, 352256 heap bytes used, 266240 stack bytes used, Total Time:89ms
```

### 6.3 Clause 3 — Linux s390x under QEMU

Platform: Ubuntu 24.04.5 LTS, kernel 6.8.0-139-generic, under
`qemu-system-s390x` in TCG on the same x86-64 host (D-215; VL-82 applies).

```
Linux onfly390 6.8.0-139-generic #139-Ubuntu SMP ... s390x s390x s390x
gcc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0    GNU Make 4.3    Python 3.12.3
ONFG0 VERSION 13.3.0
ONFG0 STDC 1   INTBITS 32   LONGBITS 64   TOPBYTE 01
```

`TOPBYTE 01` is the big-endian result observed on the platform, not assumed.
The worktree is mounted over 9p at `/onfly` and readable from the guest.

The probe proves the toolchain; the guest was also asked to build **this
repository**, which is what "ready" has to mean for a platform Phase D already
depends on:

```
$ make ONFPLAT=s390x CC=gcc PYTHON=python3 BUILD=/tmp/b390g0 units
gcc -std=c89 -pedantic -Wall -Wextra -Werror -O2 -Iengine/include \
    -Igenerated -o /tmp/b390g0/tstunit.exe tests/tstunit.c \
    engine/src/onfcrc.c engine/src/onfrnd.c engine/src/onfstm.c
python3 tests/run_units.py /tmp/b390g0/tstunit.exe
run_units: 19 passed, 0 failed
real    0m15.283s
```

`units` is the cheapest target that compiles ONFLY C under `-Werror` and then
runs it. A full `make test` in the guest costs hours under TCG, and Phase D
already ran it (D-234); repeating it here would re-prove Phase D rather than
G0.

### 6.4 Clause 4 — x86 Python environment

Command: `mingw32-make test` — **EXIT=0**, 23:10:39 to 23:17:37, 6 min 58 s.

```
Python 3.13.14                       gcc (MinGW.org GCC-6.3.0-1) 6.3.0
GNU Make 3.82.90 (i686-pc-mingw32)   cobc (GnuCOBOL) 3.2.0
git 2.53.0.windows.2                 numpy 2.4.4  pandas 2.3.3  pyarrow 21.0.0

ONFLY: NR-05 + licence + col80 + C-04 + C-04/MVS lints, TT-01, TT-02,
SoftFloat 2c vs TestFloat and its known answers, D-104 shift reference,
NR-04 shims, TU-01..TU-07, kernel, the embedded-network engine path,
TE-01..TE-13, the FR-BAT-01 STEP2 request loop, ACC-5 golden suite and
TP-01 all passed on SOFT3E, SOFT2C and NATIVE
```

### 6.5 What these results do **not** prove

- **The TK5 *Update* level is not self-reported.** The running system
  identifies itself as "MVS 3.8j TK5" and nothing more. `SYS2.JCLLIB($HISTORY)`
  turns out to be the JCL-samples changelog (last entry 2025-10-27), not a
  release level. "Update 5" rests on D-89's download provenance
  (`mvstk5-update5.zip`), which was **not re-measured in this session**.
  Recorded as VL-86.
- **brian2 is absent from this host.** No `.venv` exists in the main checkout
  or in any worktree that still has one. SR-CAL-04's Shiu re-run cannot be
  reproduced here as things stand. Phase C is complete so nothing is blocked,
  but re-running ACC-4 would need it reinstalled, which is a new dependency and
  therefore an owner decision. Recorded as VL-88.
- **QEMU is not hardware.** VL-01 and VL-82 stand unchanged: every s390x result
  is `qemu-system-s390x` in TCG, emulated instruction by instruction.
- **Hercules is not an IBM Z.** VL-04 stands: 45.633024 MIPS is a lab figure.
- **Nothing here is about z/OS**, and nothing here compiles ONFLY engine source
  on MVS. The GCCMVS and JCC probes are 20 lines of C with no ONFLY header —
  deliberately, so a failure would be the toolchain's. Whether the engine
  builds on MVS is Phase E's question, not G0's.
- **A gate records a state, and this state is restartable.** Both labs were
  started in this session and the Hercules codepage had to be reset to
  819/1047 first. Recorded as VL-87.

## 7. Related docs

- SRS Section 9.1 (Gate G0), Section 2.6 (A-03, A-04), Appendix A.1
  (D-235…D-240), Appendix D (VL-86…VL-89)
- `docs/implementations/2026-09-11-gate-g1-on-mvs.md` — §3.3 is where the
  GCCMVS location fact previously lived
- `docs/implementations/2026-09-12-gate-g2-closed-transport.md`,
  `2026-09-12-gate-g4-closed-cobol.md` — the closure format this follows
- `docs/implementations/2026-09-14-phase-d-s390x-and-request-loop.md` — the
  s390x guest this clause re-measures
