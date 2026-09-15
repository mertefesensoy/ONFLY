# 2026-09-15 — Phase E slice 3: install, and the BUZZ job

| Field | Value |
|---|---|
| Date | 2026-09-15 |
| Author | Engineer, with the owner deciding the scope and the FR-BAT-06 amendment |
| Phase / gate | **Phase E — MVS MVP**, slice 3 (SRS Section 9.2) |
| Owner decisions relied on | D-273 (BUZZ runs `srext`; FR-BAT-06 amended), D-274 (G-01…G-14 become a SUGR job) |
| Requirements touched | FR-BAT-01, FR-BAT-06, IR-JCL-01, IR-JCL-04, IR-NAM-03, ACC-7 |
| Open items closed | None |

## 1. Problem / motivation

Slices 1 and 2 each ran a piece of the MVP as its own job: ONFLYDRV writing
requests, ONFLYENG simulating, ONFLYDRV printing. **FR-BAT-01 does not ask for
three jobs.** It asks for one:

> The MVP shall run as one job of three steps: STEP1 ONFLYDRV in request mode
> (control cards → request dataset ONFREQ), STEP2 ONFLYENG (ONFNET + ONFREQ →
> ONFRSP), STEP3 ONFLYDRV in report mode (ONFRSP + ONFNAM → printed report).

And ACC-7 asks for that job to run "end-to-end on TK5 with return code 0 and a
readable report". Until it exists, the MVP has been demonstrated in pieces and
never as the thing itself.

## 2. What changed

| File | Change |
|---|---|
| `tools/mvsrun.py` | `install_eng_deck()`, `install_drv_deck()`, `buzz_deck()`, and the `--install-eng`, `--install-drv`, `--buzz` modes. `_sources()` factored out of `run_deck()`. |
| `tools/mvsbld.py` | `build(lmod=…, run=…)`: link into a PDS member and omit the GO step. |
| `tools/mvscob.py` | `deck(lmod=…)`: the same for the COBOL side; the `WRITEN` step is now available to an install job. |
| `tests/run_mvsrun.py` | Eleven cases over the three new decks. |

## 3. Implementation approach

### 3.1 A demonstration must not be a build

The obvious way to write BUZZ is to take `run_deck()` — which compiles and
links thirteen translation units and then runs them — and bolt a COBOL step on
each end. That deck would be about **9,300 cards**, and the first minutes of
the demonstration would be GCCMVS.

So the programs are **installed** first. Two jobs link into
`HERC01.ONFLY.LOADLIB` and run nothing at all:

```
ONFIENG   GCCMVS, thirteen units -> LOADLIB(ONFLYENG)
ONFIDRV   IKFCBL00 -> LOADLIB(ONFLYDRV), and ONFNAM with it
```

BUZZ is then **50 cards**: a scratch step and STEP1, STEP2, STEP3, each an
`EXEC PGM=` over a `STEPLIB`. `tests/run_mvsrun.py` requires that it stay that
way — one case asserts the EXEC steps are exactly `SCRATCH STEP1 STEP2 STEP3`,
and another that no card names `PGM=GCC`, `PGM=IKFCBL00`, `PGM=IEWL` or
`PGM=IFOX00`, so BUZZ cannot quietly grow back into a build.

### 3.2 Why ONFNAM is installed and not prepared inside BUZZ

The names file has to reach MVS somehow, and IR-NAM-03 requires text-mode
transport. The natural place is an IEBGENER step from inline cards — but a
prep step inside BUZZ would make it **four** steps, where FR-BAT-01 says three.
So `ONFIDRV` writes it alongside the program it belongs with. Installation
puts the MVP in place; BUZZ runs it.

### 3.3 The load library is allocated `DISP=(MOD,CATLG)`

Two install jobs write to one library and neither can be the one that creates
it, because JCL has no conditional allocation. `DISP=(MOD,CATLG)` is the idiom
that is correct on both runs: MOD creates the dataset the first time and finds
it every time after.

### 3.4 IR-JCL-04, transcribed rather than interpreted

> STEP2 shall run only if STEP1 ended below 8; STEP3 shall run only if STEP2
> ended below 12.

becomes

```
//STEP2    EXEC PGM=ONFLYENG,COND=(8,LE,STEP1)
//STEP3    EXEC PGM=ONFLYDRV,COND=(12,LE,STEP2)
```

A JCL `COND` says when to **skip**, so `(8,LE,STEP1)` means "skip STEP2 when 8
is less than or equal to STEP1's return code" — that is, run it when the code
is below 8. Getting the sense backwards produces a job that silently skips its
own work and still ends 0, so both spellings are pinned by a test case.

## 4. Numerical details

None. No arithmetic changed in this slice.

## 5. Design decisions

The one that needed the owner was not about JCL at all. **FR-BAT-06 and ACC-7
contradicted each other**, and had done since D-212: FR-BAT-06 made BUZZ run
"all golden requests" while ACC-7 required return code 0, and Section 8.4
deliberately contains G-11, G-12 and G-13, whose ONF201W, ONF203E and ONF202E
make STEP2 end 8 under IR-JCL-04.

The owner asked for this to be **discussed** before being decided. What the
discussion produced:

- Measured the same day, job `ONFPRUN`: that suite ends `COND CODE 0008` with
  `ONF302I STEP SUMMARY: 11 OK, 1 WARN, 2 ERROR`. Only ACC-7's return-code
  clause fails; "end to end" and "a readable report" both hold, because
  IR-JCL-04 runs STEP3 whenever STEP2 is below 12.
- FR-BAT-06 **predates** the `srext` requests — D-212 added them on
  2026-09-14 — so "all golden requests" was written when the suite was only
  the `path` fixture, which is not the network the MVP ships (`srext`, D-205).
- The `path` suite costs **63 min 04.79 s** of TK5 CPU against **855.7 s** for
  `srext`. Section 8's L5 row asks for BUZZ "within budget".

D-273 amended FR-BAT-06; D-274 gave G-01…G-14 their own SUGR job under
FR-BAT-06's existing naming rule.

## 6. Verification

*(pending: the three jobs have been built and checked off-MVS, and had not been
submitted at the time this section was written)*

```
mingw32-make mvsrun
```
→ `run_mvsrun: 36 passed, 0 failed`, including the BUZZ shape, the IR-JCL-04
conditioning, "BUZZ compiles nothing", and that BUZZ's `STEPLIB` and `ONFNAM`
name exactly what the install jobs create.

### What is NOT proven

- **No slice-3 job has run on TK5.** Everything above is a deck inspected on
  x86. Whether IEWL writes a usable load module into a PDS member, whether
  `PGM=ONFLYENG` resolves through `STEPLIB`, and whether MVT COBOL's
  ONFLYDRV runs from a library rather than from `&&GODATA` are all untested.
- ACC-7 is therefore **NOT RUN**.

## 7. Related docs

- SRS Section 3.4 (FR-BAT-01, FR-BAT-06), 4 (IR-JCL-01, IR-JCL-04), 6.4
  (ACC-7), Appendix A.1 (D-273, D-274)
- [2026-09-15 — Phase E slice 1](2026-09-15-phase-e-slice-1-mvs-simulation.md)
- [2026-09-15 — Phase E slice 2](2026-09-15-phase-e-slice-2-names-and-report.md)
