# Plan: P-41 slice E, replicability (2026-09-26)

| Field | Value |
|---|---|
| Scope | D-542: slice E of `docs/plan/2026-09-24-open-source-launch.md` (P-41, approved by D-488) |
| Decisions it rests on | D-543 push this session's branch only; D-544 item 11, first tag `v0.5.0`; D-545 item 5, `srext` and `path` as release assets, staged locally for this slice. Earlier: D-225, D-233, D-249, D-291, D-450, D-453, D-454, D-464, D-497, D-504, D-515, D-516 |
| Proposal | P-44, APPROVED as drafted 2026-09-26 (D-546); its questions answered as D-547 to D-554 (Section 7); carried out, with D-555 to D-563 decided on the way, and slice E marked COMPLETE 2026-09-26 (D-563) |
| Not a phase | No Section 9 phase opens or closes. The exit is P-41's own for slice E, as D-542 states it, verified by P-41's 11.8 and 11.9 |
| Platforms | **Windows:** x86-64 Windows 11, MinGW.org gcc 6.3.0 (32-bit i686), GNU Make 3.82.90 running recipes under Git's `sh.exe`, Python 3.13.14. **Linux x86-64:** the host named by Q1 (Section 7). Nothing here runs on s390x, MVS or z/OS |

Every new public file follows P-41 3.4: no em dashes, plain measured prose,
one author spelling (D-518). No text names the hosted IBM Z access program;
`tools/lint_name.py` and the installed hooks check every commit, and the
staged diff and each commit message are also checked with
`python tools/lint_name.py --staged` and `--message` before committing.

## 1. What the survey found (measured 2026-09-26, this session)

| # | Finding | How it was measured |
|---|---|---|
| S1 | The four `\| tail -1` masks P-41 placed at Makefile:495, :508, :540 and :583 are now at **:521 (`tt0132`), :534 (`tf2`), :566 (`c2c`) and :609 (`sfs`)**. Only `c2c` and `sfs` are prerequisites of `test`; `tt0132` and `tf2` run only when named. In each, the recipe's status is `tail`'s, so the test program's own exit status has never reached make | `grep -n "tail -1" Makefile`; the `test:` prerequisite line |
| S2 | The masks entered in four commits of 2026-09-11 (`ea4148d` D-104, `b257fe6`, `c43ac57` D-112/D-115, `7537073` D-116 to D-118) | `git log -S"\| tail -1" -- Makefile` |
| S3 | `test`'s closing line is a fixed `@echo` that says every listed check "passed" whatever was skipped | Makefile, the `test:` recipe |
| S4 | 18 Python files print a skip line, in at least four spellings (`SKIP -`, `SKIP:`, `SKIPPED`, `skip`), with no shared helper, so no strict mode can be added in one place today | `grep -rniE "print\(.*skip\|write\(.*skip" tests tools prep` |
| S5 | `prep/netman.py` cannot write `"distributed": true`: `set_field()` refuses a key that does not already exist (by design, so a typo cannot create a plausible key), and `read_text()` yields only strings | `prep/netman.py`, `set_field` and `read_text` |
| S6 | `prep/extract.py --admit` writes `onfnet-malecns-v1.0-srext.bin` **before** comparing it with the measured artifact, and when that comparand file is absent it skips the comparison without a word (replication X3). It also rewrites `networks.srext` wholesale, so it would drop any mark this slice adds | `prep/extract.py` lines 2111 to 2228 |
| S7 | On Linux x86-64 gcc, none of the macros `onfplat.h` keys `ONF_PLATID` on is defined, so the manifest would print `PLATFORM UNKNOWN`, the D-291 failure class. `gcc -dM -E` there defines `__linux__` and `__x86_64__` | `onfplat.h` lines 69 to 91; `gcc -dM -E -x c /dev/null` in WSL |
| S8 | This host's WSL2 Ubuntu is 26.04 with gcc 15.2.0, GNU Make 4.4.1, git, sha256sum and Python 3.14.4, but **no pip and no venv** (`ensurepip` is absent), and `sudo` asks for a password, which the engineer cannot enter | `which`, `python3 -m pip`, `dpkg -l python3.14-venv`, `sudo -n true` in WSL |
| S9 | **pyarrow 21.0.0, P-41's recorded pin, has no Python 3.14 wheel** (cp39 to cp313 only); 22.0.0 is the first with cp314 Linux wheels. numpy 2.4.4 and pandas 2.3.3 both have cp314 wheels | PyPI JSON metadata, read this session; nothing downloaded |
| S10 | gcc 15.2.0 compiles 12 of the 14 files in `engine/src` and `generated` under `-std=c89 -pedantic -Wall -Wextra -Werror -O2` with no diagnostic; the other two stopped only on the probe's missing SoftFloat include path. So item 7's `-Werror` question has not arisen for engine code; the tests, tools and SoftFloat units are unprobed | a compile-only probe in WSL, objects in `/tmp` |
| S11 | The host's Python packages match P-41 E5's pins: numpy 2.4.4, pandas 2.3.3, pyarrow 21.0.0 on Python 3.13.14; the live view's GIF writer is matplotlib's `PillowWriter` (matplotlib 3.10.7, Pillow 12.2.0); the Shiu re-run recorded brian2 2.10.1 with numpy 2.5.3 and pandas 3.0.5, which conflict with the core pins | `import` on the host; `tools/liveview.py:307`; `docs/implementations/2026-09-12-phase-c-calibration.md:144` |
| S12 | R0 passes today: `python tests/run_tx.py --compare data/phase-d/x86w data/phase-d/s390x` gives `run_tx: 25 identical, 0 differing`, exit 0 | run this session |
| S13 | The three lab archives E8 needs digests for are on the host: `C:\hercules-lab\dl\Hercules-4.9.1-x64.zip` (8,280,669 B), `mvs-tk5.zip` (498,312,872 B), `mvstk5-update5.zip` (350,462,458 B) | `Get-ChildItem` |
| S14 | `REUSE.toml` puts `data/networks/**` under CC BY 4.0, so a notice file there would be labelled as data unless it joins the data READMEs' MIT override | `REUSE.toml` lines 28 to 50 |
| S15 | Baseline in this worktree before any change, all four networks staged: `mingw32-make testfloat` exit 0, then `mingw32-make test` **exit 0 in 701 s**, closing with the fixed echo of S3 | `mingw32-make testfloat && mingw32-make test`, x86-64 Windows 11, MinGW gcc 6.3.0 |
| S16 | That green run printed **10 skip lines in four classes**, none of which any clone can clear today: 2 in `ic3270` (`local/onflytx` is kept out of every clone by D-132); 1 in `names` (D-269's regeneration check needs the MaleCNS annotations feather); 1 in `test_varnt` (needs both MaleCNS feathers, one of them 1,051,241,946 B); and 6 for TE-08, two cases on each of three backends, in `run_eng.py`'s whole-program replay. TE-08 passes at the decoder level in `run_dec.py`; the replay skips with the reason "ONFLYENG does not expose (TBD-14)", but **TBD-14 was closed at 8M by D-116 on 2026-09-11**, so the stated reason is stale. So 11.8's "SKIP 0" cannot be met as written. *(Corrected 2026-09-26 by D-555: there are **11**, not 10. The eleventh is a unittest class skip in `tests/test_signs.py`, `TestAgainstRealData`, reported only as `OK (skipped=1)`, which a grep for printed skip lines does not find; it needs the 43,282,834 B MaleCNS neurotransmitters feather. The clean clone of group 2 prints the same 11. D-555 adds it to D-548's table.)* | `grep` of the baseline log for skip lines; `tests/run_eng.py:164-176`; Appendix B |
| S17 | A clone in the session's scratch directory fails at checkout: the directory's own path is 176 characters, which with the repository's longest path (80 characters) passes Windows' 260-character limit, and MinGW gcc 6.3.0 cannot use long paths. So 11.8's Windows clone needs a short directory outside the worktrees | `git clone` into scratch, every file then staged as deleted |

## 2. The work, in P-41's order

### E2. Unmask the four `| tail -1` sites (first)

**Design.** A new `tools/lastln.py` runs one program, prints only the last
line of its standard output, and exits with **that program's** status; on a
nonzero status it prints the last 20 lines instead, so the failure is
readable. Each of the four recipes becomes
`$(PYTHON) tools/lastln.py $(BUILD)/tstxxx.exe`. Python rather than a shell
idiom because `mingw32-make` picks its recipe shell from `PATH` (Git's `sh.exe`
here, `cmd.exe` where Git's tools are not on `PATH`), and `$(PYTHON)` is the
one interpreter every platform's recipes already call, so one spelling holds
on MinGW, Linux x86-64 and s390x.

**Verify.** A test (`tests/test_lastln.py`) runs `lastln.py` over a
synthetic program that exits 0 and one that exits 3, and asserts the status
passes through. Then all four targets are run unmasked. **Any nonzero exit is a
finding recorded by a D-row, not hidden again**, and the implementation doc
states what earlier greens did not cover: since S2's commits, a `c2c` or
`sfs` failure in its final program could not have failed `make test`.

### E1. A green `make test` whose closing line counts what ran

**Design (Q4 chooses between two).** One helper module, `tests/onfres.py`,
is the only way a check reports a skip or a pending item: `skip(check,
reason)` and `pending(check, reason)` print one fixed-form line,
`ONFRES SKIP <check>: <reason>` or `ONFRES PENDING <check>: <reason>`. The 18
sites of S4 call it; their existing reasons are kept word for word after the
prefix. The fixed `@echo` is replaced by a runner, `tools/testrun.py`, that
prints the closing line `ONFLY test: <p> PASS, <s> SKIP, <q> PENDING` and exits
nonzero if any target failed. What counts as a PASS is Q4.

PENDING has no user today: D-497 closed item 6 as (a), so no check reports a
missing recording as pending. The count exists because 11.8 asks for it, and it
is expected to read 0.

**Verify.** `tests/test_onfres.py` pins the line format and the strict-mode
exit. `mingw32-make test` exits 0 and its last line carries the three counts.

### E5. `requirements.txt` and the strict mode

**Files.** `requirements.txt` holds the core pins `numpy==2.4.4`,
`pandas==2.3.3`, `pyarrow==21.0.0` (the recorded versions, S11), plus
whatever Q1 requires for the Linux Python. `requirements-live.txt` holds
`matplotlib==3.10.7` and `pillow==12.2.0` for the live view (R7).
`requirements-shiu.txt` holds `brian2==2.10.1`, `numpy==2.5.3` and
`pandas==3.0.5` as recorded for the Shiu re-run, in its own environment
because those pins conflict with the core set (S11); it is documented as
not reproduced here, since brian2 is gone from this host (VL-88).

**Strict mode.** With `ONFLY_NOSKIP=1`, `onfres.skip()` prints its line and
exits 1, so every D-233 skip becomes a failure. `tests/test_seeds.py`
imports numpy unconditionally (line 60); it gains a guarded import that
reports through `onfres.skip()`, which is new work, as P-41 says.

**The policy is Q8.** S16 shows that even a fully stocked worktree prints
10 skip lines no clone can clear, so a strict mode that fails every skip
would make 11.8 unreachable by construction. Q8 decides how strict mode and
11.8 treat those skips. Whatever it answers, a clean clone is measured once
on Windows before strict mode is relied on, and every skip line it prints is
listed in the implementation doc.

### E3. Networks: `--from`, the distributed set, the notice

- **`tools/fixtures.py --from <dir>`** takes candidates from `<dir>` only,
  copies and verifies them exactly as today. No download code is added: the
  documented source is the release asset URL of D-544's tag,
  `https://github.com/mertefesensoy/ONFLY/releases/download/v0.5.0/<file>`,
  which a replicator fetches with `curl -fsSLO` and then places with
  `--from`. `--check` stays the only acceptance test.
- **The distributed set** is `srext` and `path` (D-545). `--check` exits 0
  when both verify, and prints `NOT DISTRIBUTED (regenerate with
  prep/emit.py)` for `hop2` and `full` instead of failing on them. How the
  set is marked is Q3.
- **`data/networks/NETWORKS-NOTICE.md`** carries P-41 E3's seven points:
  MaleCNS v1.0 attribution and CC BY 4.0 with the licence URL; the citation
  as Appendix G's reference 2 records it (D-538), marked to be re-verified
  on the dataset's page at release time; `male-cns:v1.0`, uuid
  `4b2087c0fbe046bfaf0d60bc970e3e5d`; what ONFLY changed (501 and 913
  neurons, aggregated and signed counts, W_syn 0.2969 mV, the compensating
  table, format 1.1); item 8's sentence as `THIRD_PARTY_NOTICES.md` states
  it (D-515); no endorsement implied; ONFLY's contribution under CC BY 4.0
  (D-516). `fixtures.py` prints it after placing a network, and
  `data/README.md` repeats it verbatim. It joins the data READMEs' MIT
  override in `REUSE.toml` (S14), and `tools/lint_ntc.py` gains a check that
  `data/README.md` repeats it byte for byte.
- **`tests/test_fixt.py`** gains cases pinning `--from`, the `NOT
  DISTRIBUTED` line and exit 0 with `hop2` and `full` absent.

**Verify.** 11.9's first command on this worktree with `hop2` and `full`
removed from a scratch copy: exit 0, two `OK` lines with the SHA-256 values
P-41 E3 lists, two `NOT DISTRIBUTED` lines.

### E7. One network regeneration recipe, and a loud `--admit`

- `prep/extract.py admit()` checks its comparand **before** writing: an
  absent measured artifact ends with a message naming the file and the step
  that produces it, and a mismatch ends before the `.bin` is touched. A test
  drives both refusals with synthetic inputs; no network is re-emitted.
- The recipe (in `REPLICATING.md`, E6) runs R2b's chain to a scratch copy,
  ends in `python tools/fixtures.py --check`, and restores the tracked
  manifests with `git checkout -- data/networks/MANIFEST.json
  data/malecns/MANIFEST.json`, because a regeneration rewrites both. It is
  documented, not run: R2b costs about 6,971 s and needs the 1.1 GB
  download, and nothing in slice E's exit depends on it.

### E9. `test-nonet` and `quick`

- **`test-nonet`** is the subset of `test` that needs no network file, fixed
  by measurement rather than by P-41's example list: each `test` target is
  run in a clean clone with no networks, and a target joins `test-nonet`
  only if it passes there with no `ONFRES SKIP` line. Its wall clock is
  recorded.
- **`quick`** builds the engine and checks the committed fingerprints with
  no lab: `eng` and `golden`, which need the two distributed networks and
  nothing else.

### E4. Linux x86-64 (after the row 7 run, which closed on 2026-09-24, VL-138)

- **`engine/include/onfplat.h`** gains one branch **after** the JCC branch,
  `#elif defined(__linux__) && defined(__x86_64__)`, setting the `ONF_PLATID`
  Q2 names. Placing it last keeps every existing target's chain unchanged.
- **Makefile** gains the `ONFPLAT` value Q2 names: `NATFLAGS = -msse2
  -mfpmath=sse -ffp-contract=off -DONF_FP_NATIVE -DONF_FP_LITTLE`, and the
  out-of-tree TestFloat build D-225 wrote for s390x, which the `else` branch
  already serves for any platform but `x86w`.
- **Evidence fixed in advance (P-41 E4).** `onfplat.h` is submitted to MVS as
  member ONFPLAT, and rows 6 and 7 were recorded from its current bytes. So,
  before and after the edit: `gcc -E -P` of every engine unit with
  `-D__MVS__`, with `-DJCC`, with `-D__s390x__`, and plain on the x86w host,
  compared byte for byte (`-P` drops line markers, which move when lines are
  added); and every x86w object file compared byte for byte. **A D-row then
  records whether that suffices or rows 6 and 7 need a re-run**; that is an
  owner answer after the evidence, not part of this approval.
- **A `-Werror` failure on gcc 15** is handled per item 7, which is open: it
  is put to the owner when met, with the diagnostic in hand (S10 found none
  in the engine units).

### E6. `REPLICATING.md`

The ladder R0 to R7 of P-41 Section 6, each rung with its command, what it
proves and what it does not, the recorded wall clocks labelled as the owner's
host's, and R2b carrying FlyWire's non-commercial note. Every factual
sentence maps to a P-41 claims-register entry, listed in the implementation
doc.

### E8. Lab guide, `docs/lab.md`

TK5 and Hercules archive SHA-256 values computed this session from the S13
files; the 819/1047 codepage step (VL-18); the safety note in bold: bind the
card reader (3505), console (8038) and 3270 ports to 127.0.0.1 or firewall
them, never run the lab on an untrusted network, and change TK5's default
HERC01 password on any lab another machine can reach. The s390x guest
bring-up script and its cloud-init data are Q6.

## 3. Order of work and commits

Each group ends with its tests run and their output shown, then one commit
and a push to this session's branch (D-543). Nothing reaches `main` (D-504).

| Group | Steps | Needs |
|---|---|---|
| 1 | E2, E1, the `onfres` helper and strict mode | Q4, Q8 |
| 2 | Clean-clone skip inventory on Windows (measurement only; a first one was taken while this plan was drafted, Section 1) | group 1 |
| 3 | E3, E7 | Q3 |
| 4 | E5 files, E9 targets | group 2's inventory |
| 5 | E4 | Q1, Q2; then the D-row on rows 6 and 7 |
| 6 | E6, E8 | Q6 |
| 7 | Exit: 11.8 and 11.9 in fresh clones on Windows and Linux x86-64; the implementation doc; slice E's mark in P-41 | Q5, Q7 |

## 4. SRS text changes this plan asks to be authorised

None to requirement text. Appendix A gains the D-rows the answers produce and
this P-44 row; Appendix D gains **VL-140**, registering slice E's exit
measurements (the two clean-clone runs with their counts, toolchains and
wall clocks). If Q5 is answered (b), Section 8.3 gains provenance sub-rows,
and that answer is the authorisation.

## 5. Verification, and what the exit needs

| Check | Command | Expected |
|---|---|---|
| 11.8, Windows | in a fresh clone outside every worktree, a fresh venv from `requirements.txt` only, `ONFLY_FIXTURES` unset, `ONFLY_NOSKIP=1`, networks staged with `--from`: `mingw32-make fixtures && mingw32-make testfloat && mingw32-make test` | exit 0; closing line with PASS, SKIP and PENDING counts, SKIP 0 as Q8 defines it |
| 11.8, Linux | the same, on the Q1 host: `make ONFPLAT=<Q2 name> PYTHON=python3 fixtures test`, then `make quick` | exit 0; SKIP 0 as Q8 defines it |
| 11.9 | `python tools/fixtures.py --check`; `sha256sum -c SHA256SUMS` in the staging directory | exit 0; two `OK`, two `NOT DISTRIBUTED`; every checksum OK |
| R0, R1, R2a | P-41 6.1's commands on both hosts | the verdict lines of VL-98, VL-105, VL-112; the 19 golden fingerprints |
| 11.13 | P-41's em-dash count over every file this slice adds or edits | 0 new |
| guard | `python tools/lint_name.py --tree`, `--staged`, `--message` | exit 0 |

## 6. What this plan will NOT prove or change

- A Linux x86-64 result says nothing about s390x, MVS or z/OS. It is a new
  x86-64 data point with a different compiler, ABI and OS from rows 2, 3 and
  3b, and it proves no IBM Z behaviour (VL-139 stands unchanged).
- Running TT-02 and the golden suite on Linux x86-64 is what NR-09 requires to
  admit the NATIVE backend on that host; the plan reports that admission for
  that host only.
- No network, tag or release is published, and `main` does not move. Item 8
  still gates G3 (D-545).
- Rows 6 and 7 are not re-run unless the D-row after E4's evidence says so.
- CI is not written, unless Q1 chooses it; F6 stays slice F's.
- R2b, R3, R4, R5, R6 and R7 are documented, not re-run.

## 7. Open questions put to the owner with this plan

**All answered 2026-09-26, each by the recommended option:** Q1 by D-547
(WSL2, the owner installs `python3.14-venv`, pyarrow 22.0.0 on Python
3.14); Q2 by D-550 (`X86LINUX`, `x86l`); Q3 by D-551 (`netman.py --mark`);
Q4 by D-549 (a PASS per target, measured); Q5 by D-554 (VL-140 and the
implementation doc; item 7 open for its CI half); Q6 by D-552 (deferred to
slice F); Q7 by D-553 (short directories, deleted after); Q8 by D-548 (the
exemption table).

| # | Question | Options | Recommendation |
|---|---|---|---|
| Q1 | The Linux x86-64 host and its Python | (a) this host's WSL2 Ubuntu 26.04: the owner runs `sudo apt install python3.14-venv` once, and `requirements.txt` pins `pyarrow==22.0.0` for Python 3.14 by an environment marker, the one pin that differs (S9); (b) WSL2 with `uv` installed in user space to get Python 3.13 and the exact pins, a new tool downloaded from its vendor; (c) GitHub Actions on ubuntu-latest with Python 3.13, so F6's workflow lands inside slice E with its supply-chain controls | (a) |
| Q2 | The Linux platform names | `ONF_PLATID` of at most 8 characters, and the `ONFPLAT` value | `X86LINUX` and `x86l` |
| Q3 | How the distributed set is marked | (a) `prep/netman.py` gains a `--mark` for a whitelisted boolean key, `distributed`, which it may create, and `prep/extract.py`'s admission writes the same mark so an admission cannot revert it (the D-454 precedent); (b) the set is a constant in `tools/fixtures.py` and `MANIFEST.json` is untouched, which departs from P-41 E3's wording | (a) |
| Q4 | What `make test` counts as a PASS | (a) `tools/testrun.py` runs each target of the `test` list as its own sub-make, in order, and a PASS is a target whose sub-make exited 0 with no `ONFRES SKIP` line; `fp` and `eng` then build once more each, as prerequisites of `shim` and `req`; (b) one sub-make of the whole list, as today, with only SKIP and PENDING counted from marker lines and PASS reported as the number of targets once the run exits 0 | (a) |
| Q5 | How slice E's Linux result enters the record (item 7) | (a) the implementation doc and VL-140 only, item 7 left open; (b) provenance sub-rows under Section 8.3 rows 2, 3 and 3b naming OS, ABI and compiler version | (a) |
| Q6 | The s390x guest bring-up script and cloud-init data, which P-41 E8 commits only after secret scanning is on (F7, an owner setting) | (a) defer them to slice F, after F7, and commit the rest of the lab guide now; (b) commit them now without keys, checked by a local key-pattern scan | (a) |
| Q7 | Where 11.8's fresh clones and venvs live, given S17 | (a) `C:\Users\senso\onfly-e` on Windows and `~/onfly-e` in WSL, each with a venv holding the pinned packages installed from PyPI (as D-508 and D-521 installed tools outside the tree), both deleted after the run; (b) the same, kept afterwards for the owner to inspect; (c) not allowed, and 11.8 is reported NOT RUN | (a) |
| Q8 | How strict mode and 11.8's "SKIP 0" treat the skips no clone can clear (S16) | (a) a committed exemption table, each entry naming the D-row that makes the skip permanent (D-132 for `ic3270`'s two; D-545 for the two feather checks; TE-08's replay until an owner decision on exposing the limit), printed as `ONFRES EXEMPT` and counted apart; strict mode fails any skip not in the table, and 11.8 reads SKIP 0 with the EXEMPT count beside it, which a D-row records as amending 11.8's expectation; (b) meet SKIP 0 literally: stage both feathers (about 1.07 GB) in the exit runs, expose FR-LOD-04's limit in ONFLYENG so TE-08's replay runs, and move `ic3270`'s two checks into a lab-only target; (c) strict mode fails dependency skips only (Python packages, git, networks), and 11.8 reports the permanent skips as SKIP with each named | (a) |
