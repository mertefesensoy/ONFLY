# 2026-09-24: ACC-5 row 7's `path` half, resumed and filled

| Field | Value |
|---|---|
| Date | 2026-09-24 |
| Author | Claude (senior engineer), for the owner Mert Efe Şensoy |
| Phase / gate | Phase E (MVS MVP), exit criterion ACC-5, Section 8.3 row 7; Phase E re-evidenced in full under D-474 |
| Owner decisions relied on | D-468 to D-476 |
| Requirements touched | ACC-5 (Section 8.3 row 7), ACC-1 to ACC-4, ACC-6, ACC-7 (re-evidenced, not changed), IR-JCL-04, NFR-OBS-01 |
| Open items closed | none; proposals P-38 (adopted, D-472) and P-39 (approved, D-473) |

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
| `tests/run_mvsjcc.py` | Five new checks for D-471 and D-472, written before the code and shown failing, plus the `compare_quiet()` helper. |
| `tools/row7amend.py` | New: writes row 7's `path` result and VL-138 into the SRS from the response records and the listing, refusing on any mismatch. |
| `data/phase-e/jcc/rsp-path-2c.bin`, `ONFJPRUN.txt` | New: the JOB 400 recording, written by `mvsjcc --run`. |
| `docs/ONFLY-SRS.md` | D-468 to D-476 in A.1; P-38 struck, P-39 added and approved in A.2; Section 8.3 row 7 and VL-138 written by `tools/row7amend.py`. |
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

*Filled in when the run lands; see the GOAL REPORT of the 2026-09-24 session.*

## 7. Related docs

* `docs/ONFLY-SRS.md` Section 8.3 (row 7), Section 8.4, VL-91, VL-93, VL-138
* `docs/plan/2026-09-24-acc5-row7-path-resume.md`
* `docs/implementations/2026-09-18-acc5-row7-path-handover.md`
