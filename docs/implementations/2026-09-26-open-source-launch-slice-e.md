# 2026-09-26: P-41 slice E, replicability

| Field | Value |
|---|---|
| Date | 2026-09-26 |
| Author | Mert Efe Şensoy (owner); drafted with Claude Code under the owner's decisions |
| Phase / gate | None. P-41's slice E (D-542), not a Section 9 phase; its exit is P-41's 11.8 and 11.9 |
| Owner decisions relied on | D-542 to D-561; earlier D-132, D-156, D-233, D-249, D-291, D-450, D-453, D-454, D-464, D-475, D-497, D-504, D-515, D-516 |
| Requirements touched | NR-14 and TT-01/32, TT-02 (the unmasked drivers); FR-PRP-07 (the network notice and the manifest's distributed marks); NFR-LIC-01 (the notices lint); IR-NET-02 (why the notice is a separate file); C-04 (the ELF-aware lint); NFR-PRT-01 and FR-LNX-02 (one engine source, only the platform header differing, on Linux x86-64); NFR-OBS-01 (the manifest names `X86LINUX`); NR-09 and TX-03 (NATIVE admitted on the Linux host); FR-SIM-01 and ACC-5's golden suite (reproduced on both hosts); ACC-1 to ACC-4 (R2a re-evaluated on both hosts) |
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

### Group 3: E3 and E7

| File | Change |
|---|---|
| `tools/fixtures.py` | `--from DIR` takes networks from DIR only; a network outside the distributed set that is absent prints `NOT DISTRIBUTED (regenerate with prep/emit.py)` and does not fail, one that is present is still verified; the notice is printed after a network is placed; the release URL of D-544's tag is documented, and nothing is downloaded |
| `prep/netman.py` | `--mark KEY` and `set_mark()`: the one way the tool creates a key, a boolean in the whitelist `MARKS = ("distributed",)` (D-551) |
| `data/networks/MANIFEST.json` | `"distributed": true` on `srext` and `path`, written by `prep/netman.py --mark`, not by hand; no network byte fact moved |
| `prep/extract.py` | `verify_comparand()` runs before `admit()` writes, and refuses an absent comparand as well as a differing one (E7); `admit()` and `refixture()` write the mark (D-551, D-557); a `DISTRIBUTED` constant names the set |
| `data/networks/NETWORKS-NOTICE.md` | New. P-41 E3's seven points and a table of the two files' sizes and SHA-256 values |
| `data/README.md` | "What is not here" says how the networks are distributed and staged; a new section repeats the notice verbatim between marker lines |
| `tools/lint_ntc.py` | Checks 5 and 6: the notice exists, and `data/README.md`'s copy equals it byte for byte; four self-test cases |
| `REUSE.toml` | The notice joins the data READMEs' MIT override (P-44 S14) |
| `tests/test_fixt.py` | `AdmitRefuses` (four cases), `Distributed` (five), `Notice` (one) |
| `tests/test_netman.py` | The distributed set as an artefact, the two generator sites, and `--mark`'s refusals, ten checks |

### Group 4: E5 files and E9 targets

| File | Change |
|---|---|
| `requirements.txt` | New. `numpy==2.4.4`, `pandas==2.3.3`, and `pyarrow==21.0.0` below Python 3.14 or `22.0.0` from it (D-547) |
| `requirements-live.txt` | New. The live view: `matplotlib==3.10.7`, `pillow==12.2.0`, on top of the core set |
| `requirements-shiu.txt` | New. The Shiu re-run's recorded environment, `brian2==2.10.1`, `numpy==2.5.3`, `pandas==3.0.5`, marked as conflicting with the core set and not reproduced here (VL-88) |
| `Makefile` | `NONET`, the 23 targets measured network-free in group 2; `test-nonet` and `quick` (`eng golden`), both through `tools/testrun.py` |
| `tests/test_onfres.py` | Four checks holding `NONET` to `TESTS`' order and away from the five targets that need a network |

### Group 5: E4, Linux x86-64

| File | Change |
|---|---|
| `engine/include/onfplat.h` | One branch after JCC's, `defined(__linux__) && defined(__x86_64__)`, setting `ONF_PLATID` to `X86LINUX` (D-550); JCC's comment corrected from "last in the chain" to what stays true |
| `Makefile` | `ONFPLAT=x86l`: the NR-09 native flags as on x86w, TestFloat out of tree, and `SFFLAGS += -std=gnu17` for gcc 15 (D-558); `c04` runs `tests/test_c04.py` before the lint |
| `tools/lint_c04.py` | `is_elf()`, `linkage_name()` and `reserved()`: the COFF underscore stripped on COFF only, and C89 7.1.3's reserved class exempted whole (D-559) |
| `tests/test_c04.py` | New. 23 checks, including that on COFF the new rule equals the old one |

### Group 6: E6 and E8

| File | Change |
|---|---|
| `REPLICATING.md` | New. P-41 Section 6's ladder R0 to R7, each rung with its commands, what it proves and what it does not; staging the networks; strict mode and its eleven exemptions; the regeneration recipe of E7, stated as not re-run end to end since 2026-09-13; FlyWire's non-commercial note at R2b |
| `docs/lab.md` | New. The lab guide: the three archives' SHA-256 values computed this session, the 819/1047 codepage step (VL-18), the safety notes on the 3505, 8038 and 3270 ports and on TK5's default HERC01 password, the MVS rungs with their recorded costs, and the s390x guest described in prose, its bring-up script deferred to slice F (D-552) |

### Group 7: the exit, and what it found

| File | Change |
|---|---|
| `prep/acc4.py` | `record_path()`: `--reeval` uses a path that exists as given, else a name under `data/calibration/` (D-561) |
| `tests/test_disc.py` | `RecordPath`, four cases |
| `docs/ONFLY-SRS.md` | Appendix A.1 D-542 to D-561; A.2 P-44; Appendix D VL-140 |
| `docs/plan/2026-09-24-open-source-launch.md` | Items 5, 7 and 11 recorded as answered |
| `docs/plan/2026-09-26-open-source-slice-e.md` | New. P-44, the plan of record |

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

### Group 3

**The distributed set lives in the manifest.** `fixtures.distributed(e)` is
`e.get("distributed") is True`. The rule "never trust a filename" is kept
whole: only an ABSENT network outside the set is excused, and a present one
is verified by size, CRC-32 and SHA-256 like any other. `--from` replaces the
worktree search of D-249 with the one directory named, so a staged release
cannot be silently completed from somewhere else.

**Two generators, one mark.** `data/networks/MANIFEST.json` has two writers
that replace an entry wholesale: `admit()` for `srext` and `refixture()`
for `path`. Both now write the mark (D-551, D-557), so a regeneration keeps
it, and `tests/test_netman.py` reads their source to hold them to that.

**E7: refuse, then write.** `verify_comparand(diag, sha)` takes the path of
the measured artifact and the SHA-256 of the bytes about to be admitted,
returns only when the two are the same file, and otherwise exits with a
message ending "nothing was written". `admit()` calls it before
`io.open(path, "wb")`, which `test_admit_verifies_before_it_writes` checks
in the function's source.

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

### Group 2: the clean clone, measured

A clone of `3530094` in `build/cc1`, **with no network file**, each `test`
target made alone (`mingw32-make <target>`), after `mingw32-make testfloat`:

| Outcome | Targets |
|---|---|
| exit 0, no `ONFRES SKIP` | `onfres lint liclint namelint ntclint col80 c04 c04mvs sub mvsjcc ic3270 tt01 tt02 c2c sfs shim layout units fp kernel syn decode eng`; `ic3270` and `eng` print only EXEMPT lines |
| exit 0, network checks skipped | `mvsrun` (`mvsrun/network`, `mvsrun/path-network`), `names` (four `names/network`), `prep` (`test_geom/network`) |
| exit 2 | `req`, `golden`, which need the networks |

With the networks staged, the same tree's `make test` prints only the 11
exempt checks (group 1's runs). So the clean clone adds no skip beyond
D-548's table on this host, and the table's 11 entries are all a clone
prints. The first 23 targets are what E9's `test-nonet` holds.

### Group 3

**Tests first.** `tests/test_fixt.py` with its ten new cases before the
code: `FAILED (failures=2, errors=8)`. `tests/test_netman.py`'s new half
before `set_mark()` existed: `AttributeError: module 'netman' has no
attribute 'set_mark'`; with the tool but before the marks,
`test_netman: 21 passed, 2 failed`, the two being the artefact and the
generator checks. `tools/lint_ntc.py --self-test` before its check:
`NameError: name 'NET_NOTICE' is not defined`. After: `test_fixt` `Ran 25
tests ... OK`; `test_netman: 23 passed, 0 failed`; `lint_ntc: self-test 17
checks, 0 failed` and `lint_ntc: ok`.

**The marks moved no network byte.** `bytes`, `crc32` and `sha256` of all
four networks were compared before and after `python prep/netman.py
--network srext --mark distributed` and the same for `path`: identical. The
manifest's diff is two added lines.

**11.9, in a clean clone with no network.** The two files were staged in
`build/stage` with a `SHA256SUMS`. `sha256sum -c SHA256SUMS`:
`onfnet-malecns-v1.0-srext.bin: OK`, `onfnet-malecns-v1.0-path.bin: OK`,
the two digests being P-41's. Before staging, `python tools/fixtures.py
--check` exits 1 with `path` and `srext` `MISSING`. After `python
tools/fixtures.py --from build/stage`, which printed the notice:

    fixtures: full   NOT DISTRIBUTED (regenerate with prep/emit.py)
    fixtures: hop2   NOT DISTRIBUTED (regenerate with prep/emit.py)
    fixtures: path   OK       951200 bytes, CRC 70A9A555
    fixtures: srext  OK       171768 bytes, CRC 038CAE79
    fixtures: the distributed set (path, srext) is present and verified against MANIFEST.json; 2 not distributed (full, hop2)

exit 0. **11.9 PASS** on x86-64 Windows. The download half of 11.9 cannot
be run until slice G publishes a release.

**The targets group 3 touches**, through the runner: `python
tools/testrun.py mingw32-make onfres liclint namelint ntclint mvsrun names
prep`: `7 PASS, 0 SKIP, 0 PENDING, 3 EXEMPT`, exit 0.

### Group 4

`tests/test_onfres.py` before `NONET` existed: `the Makefile defines TESTS
and NONET ... TESTS 28, NONET 0`, `44 passed, 1 failed`. After: `48 passed,
0 failed`.

**`test-nonet`, in a clean clone with no network file** (the clone of
`08b18cf` plus this group's diff, `data/networks/*.bin` removed):
`ONFLY_NOSKIP=1 mingw32-make test-nonet` exits 0 in **109 s**, closing
`ONFLY test: 23 PASS, 0 SKIP, 0 PENDING, 8 EXEMPT`, the eight being
`ic3270`'s two and TE-08's six. That is the time P-41 E9 asked to record.

**`quick`, with the networks**: `ONFLY_NOSKIP=1 mingw32-make quick` exits 0
in **392 s**, `2 PASS, 0 SKIP, 0 PENDING, 6 EXEMPT`. Its golden half prints
`run_gld [SOFT3E backend]: 20 passed, 0 failed`, the same for NATIVE and
SOFT2C, every Section 8.4 fingerprint from `G-01 ... fp=6C143127` to `G-19
... fp=C4C320BC`, then `cmpgld: SOFT3E, NATIVE, SOFT2C agree on all 19
golden requests across 2 networks` and `cmpchk [FR-SIM-10 chunk
invariance]: 24 passed, 0 failed`.

The three requirements files are exercised by group 7's fresh venvs, not
here.

### Group 5

**The MVS evidence fixed in advance (P-41 E4, D-560).** Before the edit,
with `onfplat.h` at SHA-256 `c144ec0b...` and unchanged from HEAD, a script
recorded `gcc -E -P` of each of the 14 files in `engine/src` and
`generated` under `-D__MVS__`, under `-U_WIN32 -U__WIN32__ -DJCC` (this
host's gcc predefines `_WIN32`, which the chain tests before JCC), under
`-D__s390x__` and under the x86w host's own defines, each with the
Makefile's include set and flags for that unit, plus each unit's x86w
object file. Two runs of it were identical. After the edit (`924a0540...`):

    E jcc    14 of 14 identical
    E mvs    14 of 14 identical
    E s390x  14 of 14 identical
    E x86w   14 of 14 identical
    O x86w   14 of 14 identical
    differing entries: none

The preprocessor was MinGW gcc 6.3.0's. GCCMVS's and JCC's own were not
run, and the owner decided (D-560) that rows 6 and 7 are not re-run.

**Linux x86-64, a development run from the worktree** (this host's WSL2
Ubuntu 26.04, gcc 15.2.0, GNU Make 4.4.1, Python 3.14.4 in the D-556 venv
with `requirements.txt`: numpy 2.4.4, pandas 2.3.3, pyarrow 22.0.0).
`make ONFPLAT=x86l testfloat` exits 0 in 121 s. Each target made alone:
25 exit 0; `liclint` and `namelint` skip only because Linux git cannot read
a Windows worktree's `.git` file (a real clone, in group 7, can); the
golden suite passes on all three backends (`run_gld [SOFT3E backend]: 20
passed, 0 failed`, the same for NATIVE and SOFT2C, G-16 `BAF81D91`, G-19
`C4C320BC`). Two targets failed, and each became an owner decision:

| Target | What gcc 15 on Linux did | Decision |
|---|---|---|
| `shim` | `softfloat/c89/stdbool.h:26:13: error: 'bool' cannot be defined via 'typedef'`: gcc 15 defaults to C23 | D-558, `-std=gnu17` on x86l |
| `c04` | `GLOBAL_OFFSET_TABLE_ (20) is over 8 characters`: the lint stripped ELF's `_GLOBAL_OFFSET_TABLE_` as if it carried a COFF prefix | D-559, the lint reads ELF correctly |

After both, on Linux: `make ONFPLAT=x86l c04` exit 0, `test_c04: 23 passed,
0 failed`, `_GLOBAL_OFFSET_TABLE_ (21)` reported as an implementation name
and `lint_c04: every external satisfies C-04`; `make ONFPLAT=x86l shim`
exit 0 with `-std=gnu17` on the compile line, `run_fp [SOFT3E backend]:
2427 passed, 0 failed`. On Windows the ELF-aware lint changes nothing:
`c04` and `c04mvs` still examine 80 and 71 externals and pass.

**x86w after the whole group:** `ONFLY_NOSKIP=1 mingw32-make test` exits 0
in 588 s, `ONFLY test: 28 PASS, 0 SKIP, 0 PENDING, 11 EXEMPT`, no `ONFRES
FAIL` line; the header change, the new platform block and the ELF-aware
lint move nothing on the recorded platform.

### Group 6

**Every factual sentence maps to P-41's claims register** (Section 5), or
to a measurement made in this session:

| Where | Sentence | Source |
|---|---|---|
| REPLICATING.md, opening; lab.md, opening | ONFLY has not run on IBM Z hardware; the project does not have IBM Z access yet; MVS and s390x results come from emulators on one laptop | CAN-03, VL-139 |
| REPLICATING.md, Before you start | the pins are the recorded versions; pyarrow 22.0.0 for Python 3.14 | S9, S11, D-547, this session's Linux venv |
| REPLICATING.md, Before you start | the networks are not in git, no release is published yet | D-544, D-545; CAN-10's claim deliberately not made, since it holds only after slice G |
| REPLICATING.md, Strict mode | eleven exemptions and why | D-548, D-555, this session's runs |
| REPLICATING.md, R0 | recordings agree; the x86-64 and s390x response records are identical | CAN-02; `run_tx: 25 identical, 0 differing` this session |
| REPLICATING.md, R1 | 19 fingerprints on three backends; consistency, not correctness; a new compiler is a new data point | CAN-02 and its VL-05 limit; MUST NOT 10 |
| REPLICATING.md, R1 | `test-nonet` 109 s, `quick` 392 s | Group 4, this session |
| REPLICATING.md, R2a | 48 s and 80 s recorded; ACC-3 at 40 Hz within the reference's precision, re-measured campaigns pass 52 to 60% of the time; two criteria changed after the results | CAN-07 with VL-114; CAN-15; VL-98, VL-105 |
| REPLICATING.md, R2b | the MaleCNS download size; 6,971 s for ACC-4; FlyWire's CC BY-NC terms; brian2 absent | P-41 6.1, VL-97, THIRD_PARTY_NOTICES section 6, VL-88 |
| REPLICATING.md, R3; lab.md, s390x | big-endian under emulation, nothing about real s390x floating point | CAN-04, VL-01, VL-82 |
| REPLICATING.md, R4; lab.md, MVS | GCCMVS and JCC each reproduce all 19 fingerprints under emulation; costs as recorded, one run each | CAN-02, VL-91, VL-138; CAN-05's form, CPU seconds with host and Hercules version |
| REPLICATING.md, R5 | not IBM CICS; menu program never executed; concurrency untested | CAN-09, VL-37 |
| REPLICATING.md, R6 | not reproducible from the repository | CAN-11, D-132 |
| REPLICATING.md, R7 | the MVS stream byte-identical to x86-64 for five requests once line endings are normalised | CAN-12, D-414, VL-136 |
| lab.md, archives | the three SHA-256 values | computed this session from `C:\hercules-lab\dl` |
| lab.md, Update 5 | the Update level is provenance, not measured | VL-86 |

A scan of both files and the notice for MUST NOT phrases found only two
ordinary uses of "first" ("the first line", "the first release that
does"), not a claim of priority. **Documented, not re-run here:** R2b, R3,
R4, R5, R6 and R7, and the E7 recipe.

### Group 7: the exit

P-41's 11.8 and 11.9, and rungs R0, R1 and R2a, in fresh clones of the
**pushed** branch at `88ac979`, cloned from GitHub into
`C:\Users\senso\onfly-e` and WSL's `~/onfly-e` (D-553), each with a fresh
venv built from `requirements.txt` alone, `ONFLY_FIXTURES` unset,
`ONFLY_NOSKIP=1`, and the two networks staged with `--from`. The two runs
overlapped, so their wall clocks are not quoted. VL-140 registers them.

| Check | Windows (MinGW gcc 6.3.0, Python 3.13.14) | Linux x86-64 (gcc 15.2.0, Python 3.14.4) |
|---|---|---|
| venv from `requirements.txt` | numpy 2.4.4, pandas 2.3.3, pyarrow 21.0.0 | numpy 2.4.4, pandas 2.3.3, pyarrow 22.0.0 (D-547) |
| 11.9, `sha256sum -c SHA256SUMS` | both `OK` | both `OK` |
| 11.9, `fixtures.py --check` | exit 0; `path`, `srext` OK; `hop2`, `full` NOT DISTRIBUTED | the same |
| R0, `run_tx --compare` | `25 identical, 0 differing` | the same |
| R0, `run_mvsrun.py` | `49 passed, 0 failed` | the same |
| 11.8 and R1, `make fixtures`, `testfloat`, `test` | all exit 0; `28 PASS, 0 SKIP, 0 PENDING, 11 EXEMPT` | the same, with `ONFPLAT=x86l` |
| 11.8, `make quick` | exit 0; `2 PASS, 0 SKIP, 0 PENDING, 6 EXEMPT` | the same |
| R2a, ACC-1 and ACC-2 | `ACC-1 PASS over the rates it applies to: [40, 60, 120, 200]`; `ACC-2 PASS: rate 0 produced 0 spikes across all 501 neurons` | the same |
| R2a, ACC-3 | `ACC-3 PASS`, `NFR-MEM-01 PASS` | the same |
| R2a, ACC-4 | `--reeval data/calibration/acc4.json` exit 1 (the finding below); `--reeval acc4.json`: `ACC-4 shape PASS ...; ACC-4 PASS`, magnitude reported at 10 and 40 Hz | the same |
| R2a against the records | `acc1-candidate.json` and `acc3-srext.json` differ only in `elapsed_s` | the same |
| the engine's manifest | | `PLATFORM X86LINUX`, `COMPILER GCC`, `FLOAT BACKEND NATIVE` |

So on both hosts every measured number R2a writes is identical to the
committed record; only the run time differs. And on Linux x86-64 the NATIVE
backend meets NR-09's admission tests on that host: TT-02 and the golden
fingerprints equal to both soft backends'.

**Finding: a recorded command that never ran.** `python prep/acc4.py
--reeval data/calibration/acc4.json`, as D-475, P-41 6.1, `data/README.md`
and this slice's `REPLICATING.md` write it, exited 1 in both clones with
`no such record: .../data/calibration/data/calibration/acc4.json`: the
tool joined every relative argument onto `data/calibration/`. D-561 makes it
use a path that exists as given; `tests/test_disc.py` pins four forms,
shown failing (`errors=4`) and then passing (`Ran 10 tests ... OK`), and in
the worktree both `--reeval data/calibration/acc4.json` and `--reeval
acc4.json` now exit 0 with `ACC-4 PASS`.

**The final rerun D-563 required**, at the pushed `ae07dc3`, both hosts,
fresh clones, fresh venvs, the same staging and strict mode: every row of
the table above repeats line for line, and the recorded form `python
prep/acc4.py --reeval data/calibration/acc4.json` now exits 0 with
`ACC-4 shape PASS ...; ACC-4 PASS` on both. The rewritten records again
differ in `elapsed_s` alone (Windows 81 and 79 s, Linux 77 and 76 s,
against the committed 54 and 78 s). On that evidence the owner's D-563 mark
is written: P-41 slice E COMPLETE 2026-09-26.

**Cleanup (D-553).** `C:\Users\senso\onfly-e` and WSL's `~/onfly-e` are
deleted after the run, as are this worktree's scratch clone `build/cc1` and
staging directory `build/stage`.

**Not run this session:** `reuse lint` (not installed here; the new files
fall under `REUSE.toml`'s catch-all and data rules, and the notice's own
entry parses); R2b, R3, R4, R5, R6 and R7; any TK5 or s390x job.

**A warning, not a failure:** gcc 15 warns `'~' on a boolean expression
[-Wbool-operation]` at `softfloat/onfrpk.c:137`, a derived SoftFloat 3e
file built without `-Werror`. It is upstream's arithmetic, derived by
`softfloat/derive3e.py`, and not changed here.

## 7. Related docs

- `docs/ONFLY-SRS.md`: Appendix A.1 D-542 to D-561, A.2 P-44, Appendix D
  VL-139 and VL-140; Section 8.3 (unchanged, D-554); Section 8.5's TT-01/32,
  TT-02 and TE-08.
- `docs/plan/2026-09-24-open-source-launch.md`: P-41, slice E (Section 4),
  the replication ladder (Section 6), items 5, 7 and 11 (Section 10), checks
  11.8, 11.9 and 11.13 (Section 11).
- `docs/plan/2026-09-26-open-source-slice-e.md`: P-44, this slice's plan of
  record, with the survey findings S1 to S17.
- `REPLICATING.md`, `docs/lab.md`, `data/networks/NETWORKS-NOTICE.md`,
  `data/README.md`.
- `docs/implementations/2026-09-26-open-source-launch-slice-c.md` and
  `-slice-d.md`, the slices this one follows.
