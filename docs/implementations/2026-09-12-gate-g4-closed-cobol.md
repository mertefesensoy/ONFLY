# 2026-09-12 — Gate G4 closed: the COBOL driver skeleton on MVT COBOL and the GnuCOBOL proxy

| Field | Value |
|---|---|
| Date | 2026-09-12 |
| Author | Claude (ONFLY senior engineer session) |
| Phase / gate | **Gate G4 (Spike S4, COBOL)** — the last open Phase A gate |
| Owner decisions relied on | D-151 … D-161 |
| Requirements touched | FR-BAT-01, FR-BAT-03, IR-COM-01, IR-COM-02, IR-COM-03, IR-COM-04, IR-JCL-01, IR-JCL-02, IR-JCL-03, IR-JCL-04, C-03, D-17, D-18, TU-07 (driver half), VL-02 |
| Open items closed | **Gate G4**; none of Appendix B's TBC/TBD items |

## 1. Problem / motivation

Gate G4 asks two questions (SRS 9.1): does COPY work in MVT COBOL, and does
the driver skeleton pass the GnuCOBOL IBM-dialect check. Phase E depends on
the answer: ONFLYDRV must be *one* COBOL source that compiles unchanged under
the 1968-era OS/360 MVT ANS COBOL compiler on MVS 3.8j and, later, under
Enterprise COBOL (FR-BAT-03, D-17). Until this session no COBOL had been
compiled on TK5 at all, and the risk register (R-04) rated MVT COBOL's
limitations as *high* likelihood.

The failure this prevents is silent layout drift. The 412-byte COMMAREA is
read by a C engine, a COBOL driver and a Python oracle (IR-COM-01). If the
COBOL side's bytes differed from the other two by even one halfword, the
engine would decode a wrong request and produce a plausible wrong answer,
not an error. So the gate was run past "it compiled" to "the bytes it wrote
equal the bytes Python packs".

## 2. What changed

| File | Change |
|---|---|
| `cobol/ONFLYDRV.cbl` | New. The driver **template**: FR-BAT-03's single source in the MVT/Enterprise intersection, with an honest `COPY ONFCOM.` statement. |
| `generated/ONFLYDRV.cbl` | New, generated. The template with the copybook expanded in place; the file every compiler actually builds (D-161). Never edited. |
| `layout/generate.py` | `gen_cobol_driver()`: expands the template's one COPY statement; refuses a template with zero, two, or a stray COPY. |
| `tests/run_cob.py` | New. The x86 half: GnuCOBOL syntax checks, a real run in both modes, byte comparison of ONFREQ against `generated/onfcom_py.py`. Skips with exit 0 when no `cobc` exists (D-156). |
| `tools/mvscob.py` | New. The MVS half: one job — IEBUPDTE, IKFCBL00, IEWL, GO in REQ mode, IDCAMS `PRINT DUMP`, GO in RPT mode — and the byte comparison of the dump. `--copy68` reproduces the COBOL-68 COPY probe. |
| `Makefile` | `make cob` target (outside `test`, D-156); `generated/ONFLYDRV.cbl` joins `GENERATED` with the template as a prerequisite; `cobol/` joins the 80-column lint. |
| `docs/ONFLY-SRS.md` | D-151 … D-161; VL-57 … VL-60; Gate G4 closed; Phase A row updated. |

The host also gained GnuCOBOL 3.2.0 through MSYS2 (`pacman -S
mingw-w64-x86_64-gnucobol`, D-152). Nothing of it is in the repository.

## 3. Implementation approach

### 3.1 The driver skeleton, and why it is shaped this way

`ONFLYDRV` selects its mode from the first control card, `MODE=REQ` or
`MODE=RPT` (D-158). REQ parses IR-JCL-02 cards into request records and writes
them to ONFREQ; RPT reads ONFRSP and echoes the numeric fields to ONFRPT. It
is a skeleton by decision (D-155): names, the Hz column, the hexadecimal
fingerprint and FR-BAT-05 belong to Phase E, which extends this file rather
than replacing it.

Every construct is chosen from the C-03 intersection: no scope terminators,
no inline PERFORM, no COMP-5, no reference modification, no STRING/UNSTRING,
no INITIALIZE, no EVALUATE, relational operators spelled as words, ELSE-IF
chains at most three deep. Two consequences are worth naming:

- **Numeric card fields are character tables.** `PIC X OCCURS 4` under a
  group, with a `PIC 9(4)` REDEFINES. Leading blanks are turned into zeros by
  a PERFORM VARYING loop, *then* the class test runs, *then* the numeric view
  is moved. Without that order a bad card reaches PACK of non-digits and
  abends S0C7 on MVS instead of printing ONF401E.
- **The record is zeroed with `MOVE LOW-VALUES` before the request fields are
  set**, so IR-JCL-03's "response portion zeroed" holds for every one of the
  32 ONF-OUT entries without a loop.

Contract of REQ mode: input ONFCTL (FB/80), output ONFREQ (FB/412); every
accepted card yields exactly one record; every rejected card yields one
`ONF401E ... AT CARD n` line and no record; RETURN-CODE is 0 if nothing was
rejected, else 8. Contract of RPT mode: input ONFRSP (FB/412), output ONFRPT
(FBA/133), one title record then one line per response plus one per readout
entry below the response's OUT-COUNT (capped at 32).

### 3.2 COPY: what MVT COBOL actually supports (VL-57)

The first compile on TK5 rejected the standalone `COPY ONFCOM.` statement
with `IKF1041I-E COPY INVALID AS USED IN WORKING-STORAGE SECTION`. A probe
with the COBOL-68 form `01 ONF-COMMAREA COPY ONFCOM.` compiled clean, linked,
ran and printed through the copied fields. So MVT's COPY works — but only in
a spelling Enterprise COBOL and GnuCOBOL refuse. No single spelling serves
both, which is exactly the case IR-COM-01 anticipated: "if COPY fails under
MVT COBOL, the generator shall inline the layout".

### 3.3 Inlining by expansion (D-161)

`layout/generate.py` reads the template, requires exactly one line matching
`COPY ONFCOM.` and no other COPY, and writes `generated/ONFLYDRV.cbl` with the
copybook text in that line's place between marker comments, under a
DO-NOT-EDIT banner carrying the master's SHA-256. The template stays valid
COBOL-74-or-later (GnuCOBOL compiles it with `-I generated`), the generated
file is purely generated (D-18 stays crisp), and no compiler on any platform
needs a copy library.

### 3.4 One checker on each side

- **x86**: `tests/run_cob.py` compiles the generated file with `cobc
  -std=ibm`, runs it, and compares ONFREQ byte for byte with
  `struct.pack(HEAD_FMT ...)` from the generated Python layout.
- **MVS**: `tools/mvscob.py` runs the same driver under IKFCBL00, then IDCAMS
  `PRINT INFILE(ONFREQ) DUMP` puts the dataset's hex on the listing; the tool
  parses it back into bytes (refusing any gap in the dump offsets rather than
  guessing) and compares against the same packing with the text field in
  EBCDIC (`cp037`; letters, digits and blank are identical in 1047).

The expected bytes come from the generated layout and nothing else. Neither
checker ships an expected file: a change to `layout/master.py` changes both
the copybook and the expectation together.

### 3.5 Carriage control without ADVANCING (VL-59)

The first MVS run in RPT mode printed `NFLY REPORT` and `EQUEST 1 ...`:
IKFCBL00 took the record's first byte as the carriage-control character,
where GnuCOBOL (and Enterprise COBOL under `ADV`) prepend one. The driver now
describes ONFRPT as 133 bytes, writes the ANSI code into byte 1 itself and
uses a plain WRITE. That is what IR-JCL-01's `FBA, LRECL=133` means, and it
behaves identically on every compiler.

## 4. Mathematical / numerical details

None: the change is structural. The only numeric transformation is the
control-card conversion of §3.1, which is decimal text to binary through the
compiler's own MOVE after a class test; the value ranges (IR-COM-02) fit the
PIC digit counts by construction, so TRUNC cannot alter them.

## 5. Design decisions

| Decision | Chosen | Alternatives | Why |
|---|---|---|---|
| D-151 | Gate G4 as the session scope | Phase E, Phase D, Phase C remainder | Last open Phase A gate; hard dependency of Phase E |
| D-152 | GnuCOBOL via MSYS2 pacman | Raincode as proxy; MVT only | Keeps FR-BAT-03, G4 and VL-02 text unchanged |
| D-153 | Commit, fast-forward main, push | Branch only; local only | Matches the repository's history |
| D-154 | The plan as presented | Change; discuss | — |
| D-155 | REQ writes real records, RPT echoes | Constructs only; full driver | A real record to compare bytes against |
| D-156 | `make cob` outside `test` | In `test` | A bare checkout has no cobc |
| D-157 | One COPY in WORKING-STORAGE | COPY in the FD; two COPYs | An FD area exists only while its file is open |
| D-158 | `MODE=REQ` / `MODE=RPT` card | JCL PARM; bare `REQ` | FR-BAT-03 says a control card |
| D-159 | Right-justified or zero-padded; blank invalid | Zero-padded only; left-justified | Both natural spellings; no silent zero |
| D-160 | Blank card is ONF401E | Skip it | Strict reading of IR-JCL-02 |
| D-161 | Template + generator expansion | In-place block; two sources | D-18 stays crisp; no copy library anywhere |

Architect's choices within those: the character-table parser (§3.1), the
IDCAMS dump as the return path for bytes (no other tool on TK5 prints hex
without writing a program), `SYSPUNCH DD DUMMY` to keep the listing clean,
and 4-digit edited widths for two count fields to avoid `IKF5011I-W`.

## 6. Verification

All measured 2026-09-12. Platform, compiler and backend are stated per
result; no floating point is involved anywhere in this gate.

**x86-64, Windows 11, GnuCOBOL 3.2.0 (MSYS2 mingw64), no float backend:**

```
mingw32-make cob        # or: python tests/run_cob.py
```

Pass looks like: three `-fsyntax-only` lines at rc=0 with 0 errors; `5
records, 2060 bytes, identical to the Python packing`; the bad deck at rc=8
with ONF401E at cards 3, 4, 5, 6 and 8; the missing mode card at card 1; the
RPT echo of five 133-byte records including `LAT-US=        -1`; and the
closing `PASS on x86 GnuCOBOL ... says nothing about MVT COBOL`. Without
cobc the script prints `SKIPPED` and exits 0.

**TK5 MVS 3.8j (Hercules 4.9.1), IKFCBL00, no float backend:**

```
python tools/mvscob.py            # the gate job
python tools/mvscob.py --copy68   # the COBOL-68 COPY probe
```

Pass looks like: condition codes `COB=0004, LKED=0000, GO=0008, DUMP=0000,
GO2=0000`; only `IKF4072I-W` in the compiler diagnostics; `ONF401E CONTROL
CARD INVALID AT CARD 0007`; five `record n: 412 bytes, identical to the
Python packing` lines; the RPT echo `intact: title plus 5 request lines`; and
for the probe `ONFCPY68 RC=0007 OUT=0002 ID2=000000005`.

**What this does not prove (Appendix D):** nothing about Enterprise COBOL —
GnuCOBOL's IBM dialect is a proxy (VL-02) and its `ADV` behaviour is from
documentation (VL-59); RPT mode with non-zero readouts ran only on x86
(VL-58); no signed control-card field exists yet, so G-13's rate −1 cannot be
produced by the driver (Phase E).

## 7. Related docs

- SRS 3.4 (FR-BAT), 4.3 (IR-COM), 4.4 (IR-JCL), 9.1 Gate G4, Appendix A
  D-151 … D-161, Appendix D VL-57 … VL-60
- `docs/implementations/2026-09-10-phase-b-foundations.md` — the layout
  generator this extends
- `docs/implementations/2026-09-12-gate-g2-closed-transport.md` — the job
  and listing conventions reused here
