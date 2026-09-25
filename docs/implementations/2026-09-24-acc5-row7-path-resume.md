# 2026-09-24: ACC-5 row 7's `path` half, resumed and filled

| Field | Value |
|---|---|
| Date | 2026-09-24 |
| Author | Engineer, with the owner deciding scope, run shape and every SRS text change |
| Phase / gate | Phase E (MVS MVP), exit criterion ACC-5, Section 8.3 row 7; Phase E re-evidenced in full under D-474 |
| Owner decisions relied on | D-468 to D-483 |
| Requirements touched | ACC-5 (Section 8.3 row 7), ACC-1 to ACC-4, ACC-6, ACC-7 (re-evidenced, not changed), IR-JCL-04, NFR-OBS-01 |
| Open items closed | none; proposals P-38 (adopted, D-472), P-39 (approved, D-473) and P-40 (adopted, D-480) |

## 1. Problem / motivation

Section 8.3 row 7 (TK5 / SOFT2C / JCC) covered five of the nineteen Section
8.4 golden requests, the `srext` half. It is the only row that varies the
**compiler** while holding platform and float library fixed, so it is the only
evidence that a fingerprint is a property of ONFLY's source rather than of
GCCMVS's code generator. Without the `path` half, the three rejection paths
(G-11 ONF201W, G-12 ONF203E, G-13 ONF202E) had never been reached by a second
code generator.

D-458 made this the 2026-09-18 session's scope. That session's run (JOB 398)
was cancelled after 1 h 02 min of `GO` when the owner had to travel (D-467),
and it showed that the cost estimate was wrong: two of fourteen requests
reported after `CPU 63 min 51.67 s`, against row 6's whole suite in
`63 min 04.79 s`.

Two tool defects stood in the way of a trustworthy resume:

* `RUN_TIMEOUT` was 14400 s (4 h), shorter than the roughly six hours a
  straight scaling of JOB 398 suggests. A collect window that closes before
  the job ends reads as a failure after the CPU has been spent.
* `mvsjcc --compare` printed `ACC-5 row 7 PASS` over **any** directory. On
  2026-09-18 it did so over row 6's GCCMVS recording (P-38). A transcript line
  that can be produced by the wrong evidence is not evidence.

## 2. What changed

| File | Change |
|---|---|
| `tools/mvsjcc.py` | `RUN_TIMEOUT` 14400 to 43200 s (D-471); new `row7_listing()` and `JES2_START`; `run_compare` refuses a directory that is not row 7's and names the measured directory in its verdict (D-472). |
| `tests/run_mvsjcc.py` | Five new checks for D-471 and D-472, written before the code and shown failing, plus the `compare_quiet()` helper. Two more check that the SRS's row 7 sentence and VL-138 equal what `tools/row7amend.py` derives from the committed recording. |
| `tools/row7amend.py` | New: writes row 7's `path` result and VL-138 into the SRS from the response records and the listing, refusing on any mismatch. |
| `data/phase-e/jcc/rsp-path-2c.bin`, `ONFJPRUN.txt` | New: the JOB 402 recording, written by `mvsjcc --run`. |
| `data/phase-e/jcc/ONFJPRUN-partial-JOB400.txt` | New: what JES2's warm start printed of the lost JOB 400 (D-477); nothing from `GO`. |
| `data/calibration/acc1-candidate.json`, `acc3-srext.json` | This session's ACC-1 and ACC-3 records; only `elapsed_s` moved. |
| `Makefile` | The `test` target's closing echo says row 7 covers all nineteen requests (D-481). No rule changes. |
| `docs/ONFLY-SRS.md` | D-468 to D-483 in A.1; P-38 struck, P-39 and P-40 added and ruled on in A.2; Section 8.3 row 7 and VL-138 written by `tools/row7amend.py`; Section 9.2's Phase E caveat updated (D-480); D-468's wording neutralised (D-479). |
| `docs/plan/2026-09-24-acc5-row7-path-resume.md` | New: the plan of record (P-39, D-473). |

## 3. Implementation approach

**`row7_listing(jccdir)`**. Contract: input a directory; output `None` if it
is row 7's recording for the network `mvsrun` is pointed at, otherwise a
one-line reason. No side effects. It requires `<job>.txt`, where `<job>` is
`jcc_job()` (`ONFJRUN` for `srext`, `ONFJPRUN` for `path`, D-462), and
requires the first JES2 `START JOB nnn NAME` banner in its first 4 KB to name
that same job. The name check alone would pass a renamed file; the banner check
is what the renamed-listing test exercises. What it cannot prove is which
compiler ran, which is why the amender additionally reads the engine's own
`ONF002I COMPILER` manifest line.

**`tools/row7amend.py`**. It is a guard followed by a text substitution. It
refuses unless (a) `row7_listing` accepts the directory, (b) the listing's run
manifest reads `COMPILER JCC`, `PLATFORM MVS38J`, `FLOAT BACKEND SOFT2C`, and
(c) all fourteen fingerprints read at byte offset 20 of each response record
equal the golden file's. Every figure it writes comes from the recording: the
fingerprints from the records, and the job number, step codes, `GO`
START/STOP and CPU from the listing. It replaces exactly one sentence in row 7
and inserts VL-138 after VL-137, refusing if either is already done.

## 4. Mathematical / numerical details

None new. The fingerprint is IR-COM-05's canonical digest, unchanged. The one
piece of arithmetic is the `GO` wall-clock figure: MVS stamps `IEF373I` and
`IEF374I` as `yyddd.hhmm`, so wall = (stop minutes of day − start minutes of
day) + 1440 × (stop day − start day), at one-minute resolution. That is stated
as approximate wherever it is reported.

## 5. Design decisions

* One job, not split (D-471). Splitting would bound a loss but needs new TK5
  datasets and makes row 7's CPU a sum of jobs.
* The P-38 guard in its strong form (D-472) rather than a relabelled PASS line.
* The amender reads the manifest line rather than trusting the job name. That
  was the architect's choice inside D-473's approved "measurement-only
  amender".

## 6. Verification

Every result below was run in the 2026-09-24/25 session. The platform,
compiler and float backend are stated for each.

### 6.1 Slice 1, test first (x86-64, Windows 11, Python 3.13.14)

`python tests/run_mvsjcc.py` before the code change: `44 passed, 5 failed`,
the four new D-471/D-472 checks failing (`RUN_TIMEOUT ... 14400 s`, `path:
--compare refuses row 6's GCCMVS directory  rc=0`, the renamed listing
`rc=0`, the verdict without a directory) plus the known missing recording.
After: `48 passed, 1 failed`, the one failure being the recording slice 3
produces. After slice 3: `run_mvsjcc: 51 passed, 0 failed`.

### 6.2 Slice 3, the run (TK5 MVS 3.8j, Hercules 4.9.1.11612-SDL, JCC 1.50.00, SOFT2C)

    python tools/mvsjcc.py --net path --run --out data/phase-e/jcc

JOB 400 was lost when Hercules went down with a stopped session task (D-477;
the partial listing is `ONFJPRUN-partial-JOB400.txt`). The re-run, **JOB
402**, `finished in 4828.0 s`: 20 build steps at `COND CODE 0000`, `GO` at
`COND CODE 0008` as IR-JCL-04 requires for G-12 and G-13, `ONF302I STEP
SUMMARY: 11 OK, 1 WARN, 2 ERROR`, `recovered 14 response records`. `GO` CPU
**79 min 51.84 s**.

### 6.3 Slice 4, the guarded comparison (x86-64 judging the TK5 recording)

    python tools/mvsjcc.py --net path --compare data/phase-e/jcc data/phase-d/x86w

`raw=False binary=True translated=True` (only the EBCDIC text fields differ,
as D-261 expects), all fourteen `ok`, `mvsjcc: ACC-5 row 7 PASS (path,
measured data/phase-e/jcc)`. The same command pointed at `data/phase-e/mvs`
now answers `refusing to judge ... no ONFJPRUN.txt listing there (D-472)`
and exits 2.

### 6.4 Slice 5 and Phase E re-evidenced (D-474)

| Criterion | Command | Platform / compiler / backend | Result |
|---|---|---|---|
| ACC-1, ACC-2 | `python prep/extract.py --acc1 data/networks/onfnet-malecns-v1.0-srext.bin --label srext --jobs 14` | x86-64, MinGW gcc 6.3.0, NATIVE | `ACC-1 PASS over the rates it applies to: [40, 60, 120, 200]`; `ACC-2 PASS: rate 0 produced 0 spikes across all 501 neurons`; figures identical to VL-105 |
| ACC-3 | `python prep/extract.py --acc3-file data/networks/onfnet-malecns-v1.0-srext.bin --label srext --jobs 8` | x86-64, MinGW gcc 6.3.0, NATIVE | `ACC-3 PASS`, 10 Hz excluded under D-202; figures identical to VL-98 |
| ACC-4 | `python prep/acc4.py --reeval acc4.json` | re-evaluation of VL-97's stored x86-64 NATIVE full-brain record (D-475) | `ACC-4 shape PASS ...; ACC-4 PASS`; magnitude reported, outside tolerance at 10 and 40 Hz |
| ACC-5 rows 1, 2, 3, 3b, and the recorded rows 6 and 7 | `mingw32-make test` | x86-64, MinGW gcc 6.3.0, SOFT3E / NATIVE / SOFT2C | exit 0; `run_gld` 20/20 on each backend; `cmpgld: SOFT3E, NATIVE, SOFT2C agree on all 19 golden requests across 2 networks`; `run_mvsrun: 49 passed`; `run_mvsjcc: 51 passed`; `test_varnt` SKIPPED (feather files absent) |
| ACC-5 row 7 | slices 3 and 4 above | TK5, JCC 1.50.00, SOFT2C | all 19 Section 8.4 requests now covered |
| ACC-6 | `python tools/mvsrun.py --buzz --tx04` | TK5, GCCMVS 3.2.3 `-O1`, SOFT2C | JOB 403: `STEP2 CPU 235.21 s` against 600 s, `Certified: the host executed the guest throughout.`, `ACC-6 PASS` |
| ACC-7 | `python tools/mvsrun.py --buzz` | TK5, GCCMVS 3.2.3 `-O1`, SOFT2C | JOB 404: four steps at `COND CODE 0`, five fingerprints equal G-15 to G-19, `ACC-7 PASS ... 21 report line(s)` |
| ACC-5 rows 4 and 5 | `make ONFPLAT=s390x CC=gcc PYTHON=python3 BUILD=/tmp/b390 test` in the guest | Linux s390x under qemu-system-s390x (TCG), gcc 13.3.0 | see 6.5 |

`--buzz --tx04` runs the single-request TX-04 job only; D-474 named it for both
ACC-6 and ACC-7, and ACC-7 needed VL-104's `--buzz` as well.

**Two cost observations, measured, not explained.** ACC-6's `STEP2 CPU
235.21 s` is 1.46x VL-106's 161.11 s, and BUZZ's `STEP2 CPU 25 min 01.94 s`
is 1.78x VL-104's 14 min 04.18 s, both with the external clock certifying
98% of a core. Both remain inside NFR-PERF-01. Why this host now charges the
guest more CPU for the same work is not established.

### 6.5 Linux s390x

Ubuntu 24.04 s390x, kernel 6.8.0-139, gcc 13.3.0, GNU Make 4.3, Python
3.12.3, under `qemu-system-s390x` in TCG (D-476), this session's worktree on
9p (the guest's `tools/mvsjcc.py` hashed `66063584...`, the host's own file):

    make ONFPLAT=s390x CC=gcc PYTHON=python3 BUILD=/tmp/b390 test

`START2026-09-24T15:57:42Z` ... `MAKE_EXIT=0`. `run_gld` 20 passed on each of
SOFT3E, NATIVE and SOFT2C; `cmpgld: SOFT3E, NATIVE, SOFT2C agree on all 19
golden requests across 2 networks`; `run_tt02: 18 of 18 operation runs
passed, 781524 cases checked`; `cmpchk [FR-SIM-10 chunk invariance]: 24
passed`; `run_mvsjcc: 51 passed`. ACC-5 rows 4 (SOFT3E) and 5 (NATIVE) are
therefore evidenced in this session. **Skipped by design (D-233), not run
here:** `lint_lic` (git cannot read the 9p tree), `test_signs` and
`test_gain` (pandas and numpy are host-side). The host was suspended twice
while the guest ran; the guest paused with it and resumed, so its wall-clock
figures mean nothing and none is reported.

### 6.6 Lab state at the end

TK5 shut down in D-293's sequence (D-482) and verified down four ways: no
`hercules` process, ports 8038, 3505 and 3270 closed, the log ending
`HHC01422I Configuration released`. The s390x guest powered off (D-483):
qemu gone, port 2222 closed, `Reached target poweroff.target`.

### 6.7 What is not proven

* TK5 results are TK5 under Hercules on this host (VL-04), not real S/370
  hardware; each TK5 figure is one sample.
* s390x results are QEMU's emulation of z/Architecture (VL-01), not IBM Z
  hardware.
* ACC-4 was re-evaluated, not re-measured (D-475).
* Nothing here says anything about z/OS: row 8 is empty and the project does
  not have IBM Z access yet.

## 7. Related docs

* `docs/ONFLY-SRS.md` Section 8.3 (row 7), Section 8.4, VL-91, VL-93, VL-138
* `docs/plan/2026-09-24-acc5-row7-path-resume.md`
* `docs/implementations/2026-09-18-acc5-row7-path-handover.md`
