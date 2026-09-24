# Plan: resume ACC-5 row 7's `path` half (2026-09-24)

| Field | Value |
|---|---|
| Scope | D-468: Section 8.3 row 7's `path` half under JCC on TK5, resumed from D-467 |
| Supersedes | Slices 3 to 5 of `docs/plan/2026-09-18-acc5-row7-path.md` (D-461); slices 1 and 2 of that plan stand |
| Decisions it rests on | D-468 scope, D-469 push, D-470 lab, D-471 one job with a 12 h collect timeout, D-472 P-38 strong form |
| Proposal | P-39 |

## Slice 1: x86 tool changes, test first (D-471, D-472)

* `tests/run_mvsjcc.py` gains checks written BEFORE the code, and shown failing:
  * `RUN_TIMEOUT` is at least 43200 s (D-471).
  * `--compare` refuses `data/phase-e/mvs` for `path`. This is the exact false
    PASS P-38 recorded, and it must now exit non-zero and print no verdict.
  * `--compare` refuses a directory whose `ONFJPRUN.txt` carries another job's
    JES2 banner, which is a renamed listing.
  * `--compare` still accepts `data/phase-e/jcc` for `srext`, whose `ONFJRUN.txt`
    is row 7's own (VL-93), and the verdict line names the measured directory.
* `tools/mvsjcc.py`: `RUN_TIMEOUT = 43200`; a `row7_listing(dir)` check that reads
  `<job>.txt` and requires its first JES2 `START JOB nnn <job>` banner to name
  `jcc_job()`; `run_compare` calls it before comparing anything.
* Run `python tests/run_mvsjcc.py`. Expected: all new checks pass, and one
  known failure, `path: the TK5 JCC recording is present`, until slice 3 lands.

## Slice 2: the lab (D-470)

Start Hercules with `.\mvs.bat`, wait for MVS initialisation, set `codepage
819/1047`, confirm with `mvsub.check_codepage()`. `PNET` and `PREQ` were
measured catalogued on 2026-09-18 (JOB 397); an `ONFLIST` LISTCAT re-confirms
them before the run, because a lab that has been down six days is not assumed.

## Slice 3: the run

`python tools/mvsjcc.py --net path --run --out data/phase-e/jcc` in the
background. The host is left quiet while it runs, because host contention is
the whole of row 6's 2.5x timing spread. If the submitter dies but the job ends:
`--recover`, never a re-run.

## Slice 4: the comparison

`python tools/mvsjcc.py --net path --compare data/phase-e/jcc data/phase-d/x86w`,
now guarded by D-472. Expected: `raw=False binary=True translated=True` and all
fourteen fingerprints equal to Section 8.4.

## Slice 5: the record

A measurement-only amender (not a hand edit) takes the fourteen fingerprints
from `rsp-path-2c.bin` and the `GO` CPU and wall figures from the listing, and
amends Section 8.3 row 7; VL-138 records the run; the implementation doc is
written; `mingw32-make test` runs; commit, fast-forward `main`, push (D-469).

## Not in this plan

Any Hercules configuration change or shutdown. Both are asked for when they
arise (D-470).
