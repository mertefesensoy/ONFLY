# 2026-09-26: P-41 slice E, replicability

| Field | Value |
|---|---|
| Date | 2026-09-26 |
| Author | Mert Efe Şensoy (owner); drafted with Claude Code under the owner's decisions |
| Phase / gate | None. P-41's slice E (D-542), not a Section 9 phase; its exit is P-41's 11.8 and 11.9 |
| Owner decisions relied on | D-542 to D-555; earlier D-132, D-156, D-233, D-249, D-450, D-453, D-454, D-464, D-497, D-504, D-515, D-516 |
| Requirements touched | NR-14 and TT-01/32, TT-02 (the unmasked drivers); FR-PRP-07 (the network notice); NFR-LIC-01 (the notices lint); IR-NET-02 (why the notice is a separate file) |
| Open items closed | P-41 items 5 (D-545) and 11 (D-544); item 7 answered for slice E only (D-554). No SRS Appendix B item |
| Plan of record | P-44, `docs/plan/2026-09-26-open-source-slice-e.md`, approved by D-546 |

This document is written group by group as P-44 Section 3 orders the work.
Each group's section is added when that group is verified and committed.

## 1. Problem / motivation

P-41's slice E exists because a stranger could not reproduce ONFLY from a
clone. The survey behind P-44 found why, and also found that the build said
less than it knew:

- Four Makefile recipes ran a test program as `prog | tail -1`, so the
  recipe's status was `tail`'s. Two of them, `c2c` and `sfs`, are in
  `make test`. From 2026-09-11 until this slice, a wrong vector in
  SoftFloat 2c's known answers or in the D-104 shift reference could not
  have failed `make test` (P-44 S1, S2).
- `make test` ended with a fixed sentence saying every check "passed",
  whatever had been skipped. A fully stocked, green run prints 11 skip
  lines (P-44 S16 as corrected by D-555), and a replicator missing pandas
  would have got the same sentence over a run that never touched pandas.
- Skips came in at least four printed spellings plus unittest's own
  `OK (skipped=1)`, with no shared helper, so neither a count nor a strict
  mode could be added in one place.

## 2. What changed

### Group 1: E2, E1 and strict mode

| File | Change |
|---|---|
| `tools/lastln.py` | New. Runs one program, prints its last output line as `tail -1` did, and exits with the program's own status; prints the last 20 lines on a failure |
| `tools/onfres.py` | New. The one way a check reports that it did not run: `ONFRES SKIP`, `ONFRES EXEMPT` or `ONFRES PENDING` lines, the strict mode (`ONFLY_NOSKIP=1`), D-548's exemption table with D-555's sixth entry, and `unittest_main()` so unittest skips are counted |
| `tools/testrun.py` | New. Makes each `test` target as its own sub-make, counts a PASS per target by exit status (D-549), counts the markers, and prints the closing line |
| `tests/test_onfres.py` | New. 44 checks over the three tools above, written and shown failing before them |
| `Makefile` | The four `\| tail -1` recipes call `tools/lastln.py`; `test` runs `tools/testrun.py` over a `TESTS` list; new `onfres` target first in that list; the fixed echo becomes a comment describing the suite |
| `tests/run_ic3270.py`, `tests/run_names.py`, `tests/run_mvsrun.py`, `tests/run_eng.py`, `tests/test_txcmp.py`, `tests/test_disc.py`, `tests/test_gain.py`, `tests/test_signs.py`, `tests/test_geom.py`, `tests/test_varnt.py`, `tests/test_seeds.py`, `tests/test_fixt.py`, `tools/lint_lic.py`, `tools/lint_name.py` | Every skip on `make test`'s path reports through `tools/onfres.py`, its reason kept word for word after the prefix; the three unittest files call `onfres.unittest_main()`; `test_seeds.py` gains the guarded numpy import P-41 E5 asks for |
| `tests/run_cob.py`, `tests/run_cics.py`, `tools/cicsbld.py` | The same, for the skips of the `cob` and `cics` targets, which are outside `make test` |

## 3. Implementation approach

### Group 1

**E2, `tools/lastln.py`.** Contract: `python tools/lastln.py PROGRAM [ARG...]`
runs PROGRAM with standard output captured, prints its last line on status
0 (as `tail -1` did), prints its last 20 lines and names the status on a
nonzero one, and exits with that status. A program path that exists is made
absolute first: the first unmasked run showed Windows process creation does
not find the Makefile's `build/tstxxx.exe` spelling, which `sh` had run.
Python rather than `set -o pipefail` because `mingw32-make` picks its recipe
shell from PATH, and `$(PYTHON)` is already every platform's interpreter.

**E1, `tools/onfres.py` and `tools/testrun.py`.** One module owns the
wording of a skip: `skipline(check, reason)` returns the marker line and
whether strict mode makes it fatal, and `skip()` prints it and exits 1 when
it is. The marker is found anywhere in a line, so a site that prints a table
of results keeps its layout. `unittest_main(prefix)` replaces
`unittest.main(verbosity=2)` and reports each skipped test, or each class
skipped in `setUpClass`, as a marker (D-555).

The runner makes each `TESTS` target in its own sub-make and passes every
target already made as `-o <target>`. `-o` was measured on
`mingw32-make` 3.82.90 before it was relied on: a phony `req: eng` rule
ran `req`'s recipe and not `eng`'s. So `fp` and `eng` do not run twice, and
the cost D-549 accepted did not arise.

A check is exempt only under its own name, so a site whose check can skip
for more than one reason names each cause: `run_names.py`'s D-269
regeneration is `names/regenerate-feather` when the feather is absent
(exempt, D-545), `names/regenerate-pandas` when pandas is, and
`names/regenerate` for anything else.

## 4. Mathematical / numerical details

None. Nothing in group 1 touches the kernel, the float layer or a
fingerprint.

## 5. Design decisions

| Choice | Decided by | Alternatives |
|---|---|---|
| A Python wrapper for the four masks | P-44, approved by D-546 | `set -o pipefail`, which `cmd.exe` recipes cannot use |
| A PASS per target, measured by sub-make status | D-549 | One sub-make, PASS inferred from the exit |
| The exemption table, keyed by check name | D-548, D-555 | Meet SKIP 0 literally; fail dependency skips only |
| `-o` for targets already made | Engineer, within D-549 | Re-running `fp` and `eng`, which D-549 accepted and which would also have counted their markers twice |
| Importing `onfres` lazily in `lint_name.py` and `lint_lic.py` | Engineer | A top-level import, which would have made the commit guard's hook modes depend on a new module |
| `prep/seeds.py:695` and `prep/activity.py:75` left as they are | Engineer | Neither is a skipped check: the first prints whether a recorded run was reproduced, the second passes over a log file still being written |

## 6. Verification

Every result in this section is **x86-64 Windows 11, MinGW.org gcc 6.3.0
(32-bit), GNU Make 3.82.90, Python 3.13.14**, across the SOFT3E, SOFT2C and
NATIVE backends wherever the suite builds all three. Nothing here was run on
Linux s390x, MVS 3.8j or z/OS.

### Group 1

**The tests came first.** `python tests/test_onfres.py mingw32-make` before
the tools existed: `ModuleNotFoundError: No module named 'onfres'`, exit 1.
After: `test_onfres: 44 passed, 0 failed`, exit 0. Two of its cases were
added after a failure each found: the relative-path case (the first
unmasked run) and the unittest cases (D-555).

**E2, the four programs unmasked**, each target run alone:

| Target | Exit | Last line |
|---|---|---|
| `tt0132` | 0 | `# tst32 0 of 1068 vectors wrong` |
| `tf2` | 0 | `# tsttf2 0 of 4500 vectors wrong` |
| `c2c` | 0 | `# tst2c 0 of 1854 vectors wrong` |
| `sfs` | 0 | `# tstsfs 0 of 126 results wrong` |

All four programs `return (bad == 0) ? 0 : 1`, so from now on a wrong
vector fails make. **No finding:** the greens since 2026-09-11 were right,
but they were not guarded, and for `c2c` and `sfs` they could not have gone
red on those programs' own verdicts.

**Strict mode, site by site.** `ONFLY_NOSKIP=1` on `run_ic3270.py`,
`run_names.py`, `run_eng.py` and `test_signs.py`: each prints its skips as
`ONFRES EXEMPT` and exits 0. `tools/lint_lic.py` outside a git tree: exit 0
normally, and under strict mode `ONFRES FAIL liclint/git: ONFLY_NOSKIP=1
turns this skip into a failure (D-548)`, exit 1.

**The full suite through the runner**, `mingw32-make test`, all four
networks staged: exit 0 in 614 s, closing

    ONFLY test: 28 PASS, 0 SKIP, 0 PENDING, 11 EXEMPT (PASS counts targets; SKIP, PENDING and EXEMPT count checks; D-548, D-549)

with the 11 EXEMPT lines exactly D-548 and D-555's table: two
`ic3270/onflytx-*`, `names/regenerate-feather`, six `eng/TE-08`,
`test_signs/TestAgainstRealData` and `test_varnt/feathers`. The same run
under **`ONFLY_NOSKIP=1 mingw32-make test`**: exit 0 in 633 s, the same
closing line, and no `ONFRES FAIL` line, so on this host strict mode passes
with exactly the exemptions D-548 and D-555 allow and nothing else skipped.
This is the worktree, with the networks staged, not yet 11.8's fresh clone.

**Findings recorded, not changed here:**

1. `tests/run_names.py`'s D-269 regeneration reported **every**
   `NamesError` as a passing row, so with the feather present a real
   regeneration fault (a repeated index, an over-long name) would have
   passed. It is now a named SKIP, which strict mode fails; making it a
   hard FAIL is a follow-up.
2. `tests/run_eng.py`'s TE-08 reason says ONFLYENG does not expose a limit
   "(TBD-14)", but D-116 closed TBD-14 at 8M on 2026-09-11. The reason is
   kept word for word, as P-44 requires; whether ONFLYENG should expose
   FR-LOD-04's limit is D-548's open question.
3. The first full run counted `test_onfres.py`'s own demo markers, printed
   in its detail column, as real skips (27 PASS, 6 SKIP, 1 PENDING, 12
   EXEMPT). The test now breaks the token in anything it prints.
4. P-44 S4 counted 18 files. `run_tt02.py` and `run_c2c.py` were in it
   only for their NaN case counts, `run_eng.py` was missing from it, and
   unittest's own skips were invisible to it (D-555).
