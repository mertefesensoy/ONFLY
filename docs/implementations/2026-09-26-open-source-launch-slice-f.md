# 2026-09-26 -- P-41 slice F, community infrastructure

| Field | Value |
|---|---|
| Date | 2026-09-26 |
| Author | Mert Efe Şensoy (owner); drafted by the engineering agent under the owner's decisions |
| Phase / gate | None. D-576: P-41's slice F is not a Section 9 phase; its exit is P-41's own |
| Owner decisions relied on | D-576 to D-596 (this session); earlier D-24 and D-126 (TBD-15), D-478, D-479, D-484 to D-486, D-504, D-505, D-518, D-520, D-530, D-544, D-545, D-548, D-554, D-558, D-562, D-573 |
| Plan of record | P-46, `docs/plan/2026-09-26-open-source-slice-f.md`, approved as drafted by D-579 |
| Requirements touched | NFR-LIC-01 (the register gains the CI tools, `tools/lint_ntc.py` holds it); NR-04 and NR-05 by way of the `shim` target's build flags on `x86w` (D-596); no requirement text changed |
| Open items closed | none in SRS Appendix B; P-41 items 7 (CI half), 12, 24 and 25 closed by D-586, D-580, D-581 and D-582 |

## 1. Problem / motivation

The repository has been public since 2026-09-10, and slices A to E made
what it says true and what it claims replicable. It still had no way for
anyone else to take part: no contribution guide, no code of conduct, no
security policy, no support statement, no issue forms, no citation file and
no continuous integration. GitHub's community profile, read on `main` at the
start of this session, reported health 28 and every file `null` (P-46 S1).

Without CI, every guard slices B to E wrote (the name guard, the notices
check, strict mode) ran only when the owner ran it. A pull request from a
stranger would have been checked by nobody.

## 2. What changed

| File | Change |
|---|---|
| `CONTRIBUTING.md` | New (F1): D-, P- and VL-rows, where to start, the rules the code follows, the strict test commands, and the contribution terms of D-581 under section D.6 of GitHub's terms |
| `CODE_OF_CONDUCT.md` | New (F2): Contributor Covenant 2.1 adopted by reference (D-585), reports to the owner's address (D-582) |
| `SECURITY.md` | New (F2): scope (malformed network and request files, the lab tooling), private vulnerability reporting, `main` supported until the first release |
| `SUPPORT.md` | New (F3): one maintainer, D-580's tiers and 14-day window, Discussions for questions, tested platforms as the README states them, CI as smoke tests (D-586) |
| `.github/ISSUE_TEMPLATE/bug_report.yml`, `replication_report.yml`, `proposal.yml`, `config.yml` | New (F4): three issue forms, the third added by D-589; blank issues off; links to Discussions and to private reporting |
| `.github/pull_request_template.md` | New (F4): requirement IDs, tests with platform, what the change does not prove |
| `CITATION.cff` | New (F5): CFF 1.2.0, no `version` key (D-587), the C2 opening sentence and CAN-01 and CAN-03 in the abstract, four references |
| `CHANGELOG.md` | New (F5): seeded from Section 9.2's phase markers and P-41's slice marks, under Unreleased |
| `.mailmap` | New (F5): both commit identities shown as "Mert Efe Şensoy" |
| `.github/workflows/ci.yml` | New (F6): four jobs, `name-guard`, `python-bare`, `nonet-linux`, `nonet-windows`; actions pinned by SHA (D-579) |
| `.github/dependabot.yml`, `.github/CODEOWNERS` | New (F6) |
| `THIRD_PARTY_NOTICES.md` | Section 7 names the three actions, MSYS2 and the runner images (NFR-LIC-01) |
| `tools/lint_ntc.py` | `TOOLS` gains the same five names, so the register cannot drop them silently |
| `tests/test_fixt.py` | Imports `prep/extract.py` under `try`; its two classes that use it skip through `onfres` when numpy is absent (D-591) |
| `Makefile` | `x86w` adds `-std=gnu11` to the SoftFloat flags (D-596) |
| `README.md` | Linux x86-64 named as tested (P-46 T5, VL-140); Citing points to `CITATION.cff` (D-590) |
| `docs/ONFLY-SRS.md` | D-576 to D-596; P-46 in A.2, struck as approved; VL-142 |
| `docs/plan/2026-09-26-open-source-slice-f.md` | New: P-46, the plan of record |
| `docs/plan/2026-09-24-open-source-launch.md` | Items 7, 12, 24 and 25 marked closed; status line; slice F marked |

Settings changed on GitHub, not in the tree: under D-593 the engineer ran the
three approved commands (topics; wiki and projects off, head branches
auto-deleted, Discussions on; the `proposal` label). The owner's own
settings are listed in Section 6.

## 3. Implementation approach

**Community files.** Every statement in them is traced to a D-row, a
requirement or the claims register: the support tiers are D-580's words, the
contribution terms D-581's, the contacts D-582's, and the tested platforms
are the README's after T5, so the two cannot disagree. Pronouns for the
maintainer are avoided; the files say "the maintainer". The one name the
guard protects is described as a guard that exists, never named.

**The Code of Conduct by reference (D-585).** The file names and links the
canonical Covenant 2.1 and states, in ONFLY's own words, the contact and the
enforcement route. No third-party text enters the MIT tree, so `REUSE.toml`
needs no new annotation: its catch-all covers every file this slice adds.

**CI.** One workflow, on `push` and `pull_request`, never
`pull_request_target`; `permissions: contents: read` at the top; no
secrets; `concurrency` per ref; `timeout-minutes` on each job; checkout
with `persist-credentials: false`; every action at a full commit SHA with
its tag in a comment. The contract of each job:

- `name-guard`: `lint_name.py --self-test` and `--tree`, then every commit
  message in the event's range through `--message`. The range is
  `before..sha` on a push whose `before` is a reachable ancestor,
  `base..head` on a pull request, and `origin/main..HEAD` otherwise (a new
  branch, whose `before` is all zeros, or a forced push). It prints counts
  and commit IDs only.
- `python-bare`: setup-python's 3.13 with nothing installed, asserted by a
  `find_spec` check that numpy, pandas and pyarrow are absent; the licence
  and notices checks; then the 14 build-free test files (D-592). Not
  strict: its property is that nothing ends in an ImportError.
- `nonet-linux`: `requirements.txt` installed, then `ONFLY_NOSKIP=1 make
  ONFPLAT=x86l PYTHON=python test-nonet`.
- `nonet-windows`: MSYS2 MINGW32 with `mingw-w64-i686-gcc` and
  `mingw-w64-i686-make`, setup-python's CPython on the inherited path,
  `mingw32-make testfloat`, then `ONFLY_NOSKIP=1 mingw32-make test-nonet`.

**Two defects found by running the jobs, each put to the owner.** Running
`python-bare` locally in a package-free venv before writing it found
`tests/test_fixt.py` ending in `ModuleNotFoundError`, through
`prep/extract.py:144` (D-591); P-46's S8 had counted only direct imports.
CI's first run then failed `nonet-windows` at `shim` on MSYS2's gcc 16.1.0,
whose C23 default makes `bool` a keyword (D-596). Neither was worked around
in the workflow (D-586).

**The social preview (D-594, D-595)** is one frame of ONFLY's own
`docs/media/onfly-live-short.gif`, cropped to its 501-neuron panel, with the
CAN-01 wording and "Data: MaleCNS v1.0, CC BY 4.0, modified", built by a
scratch script outside the repository. Measured WCAG contrast against the
GIF's own background (11, 13, 18): title 17.3:1, text and credit 12.1:1,
the panel's own header 14.7:1.

## 4. Mathematical / numerical details

None in the engine. The one number this slice computes is the contrast
ratio of the preview's text, by WCAG 2.x: relative luminance
L = 0.2126 R + 0.7152 G + 0.0722 B over linearised sRGB channels
(c / 12.92 when c <= 0.03928, else ((c + 0.055) / 1.055)^2.4, with c in
[0, 1]), and ratio (L1 + 0.05) / (L2 + 0.05) with L1 the lighter.

## 5. Design decisions

| Question | Chosen | Alternatives | By |
|---|---|---|---|
| Scope | Slice F | Phase E re-evidenced on 0.5.1 (the engineer's recommendation); those ACC-5 rows only; FR-CAL-01 | D-576 |
| Support inbox | Issues for reports, Discussions on for questions | Issues only, Discussions off (P-41's recommendation) | D-580 |
| Contribution terms | Inbound equals outbound, GitHub terms D.6 | DCO sign-off | D-581 |
| Contacts | Private reporting; the owner's address | A new dedicated address | D-582 |
| The exit on `main` | D-504's batch at the end, re-asked with the evidence | `main` untouched, exit NOT MET | D-583 |
| F7 non-security settings | Engineer, each command approved | Owner applies all | D-584, D-593 |
| Code of Conduct | By reference | Verbatim, CC BY 4.0 annotated | D-585 |
| CI and the matrix | Smoke tests, VL-142; VL-139 unchanged | Provenance sub-rows | D-586 |
| `CITATION.cff` version | None until the tag question | 0.5.1; 0.5.0 | D-587 |
| Proposal route | A third issue form | Blank issues on; Discussions | D-589 |
| README Citing | Points to `CITATION.cff` | Unchanged | D-590 |
| `test_fixt.py` on bare Python | Guard the import | Exclude it; lazy import in `extract.py` | D-591 |
| `test_strm.py` | Named as not run in `python-bare` | Build the engine first | D-592 |
| Social preview | Built from ONFLY's own frame | Defer to H0; the whole-brain image offered | D-594, D-595 |
| gcc 16 on `x86w` | `-std=gnu11` | A CI-only variable; guard `stdbool.h` | D-596 |
| pip hashes | Not in this slice | A generated lock file | D-579 |

## 6. Verification

Every result below was produced in this session. Platforms: **x86-64
Windows 11** (the owner's host, MinGW.org gcc 6.3.0, GNU Make 3.82.90,
Python 3.13.14); **GitHub-hosted runners**, whose images and compilers each
line names. Nothing ran on Linux s390x, TK5 or z/OS.

**Community files** (x86-64 Windows, Python 3.13.14 with PyYAML 6.0.3, a
host package, not a project dependency). All five YAML files parse;
`CITATION.cff` has no `version` key (D-587), `license: MIT`, the author
"Şensoy", four references, and `end: '5526.e15'` kept a string (unquoted,
YAML 1.2 reads it as a float). The first parse found two `description:`
values containing `: ` unquoted; both were quoted. `git shortlog -sne HEAD`
with the `.mailmap`: `377  Mert Efe Şensoy <sensoymertefe@gmail.com>`, one
line where there were two identities. That is shown for `git` only: this
session did not check whether GitHub's own views honour `.mailmap`, so P-46
F5's "and GitHub show one author" is not claimed.

**D-591, shown failing first** (x86-64 Windows, a package-free venv made
with `python -m venv --without-pip`, Python 3.13.14, numpy, pandas, pyarrow
and yaml all absent). Before: `python tests/test_fixt.py` exit 1,
`ModuleNotFoundError: No module named 'numpy'` from `prep/extract.py:144`.
After: exit 0, `Ran 25 tests ... OK (skipped=9)`, nine `ONFRES SKIP
test_fixt/...` lines citing D-233 and D-591; with `ONFLY_NOSKIP=1`, exit 1
with `ONFRES FAIL` lines; on the host Python with numpy 2.4.4, exit 0,
`Ran 25 tests ... OK`, nothing skipped.

**D-596, the recorded toolchain unchanged** (x86-64 Windows, MinGW.org gcc
6.3.0). `gcc -dM -E` gives `__STDC_VERSION__ 201112L` with and without
`-std=gnu11`. The 17 SoftFloat units and 5 ONFLY files compiled with
`SFFLAGS` are byte-identical with and without it, 22 of 22, the 5 also
through `-Isoftfloat/c89`. Then `mingw32-make testfloat` and
`ONFLY_NOSKIP=1 mingw32-make test-nonet`: exit 0 in 251 s, `ONFLY test: 23
PASS, 0 SKIP, 0 PENDING, 2 EXEMPT`, the `shim` build line carrying
`-std=gnu11`, `run_fp [SOFT3E backend]: 2427 passed, 0 failed` and
`cmpback: SOFT3E, SOFT3E agree bit-for-bit on 2019 result lines`.

**Notices, shown failing first** (x86-64 Windows). With the five names added
to `TOOLS` and not yet to the register: `lint_ntc: 5 finding(s)`, exit 1,
each `tool not named`. After the Section 7 rows: `lint_ntc: ok --
THIRD_PARTY_NOTICES.md names 6 components, 15 item 8 paths and 27 tools`,
exit 0; `--self-test` 17 checks, 0 failed.

**CI.** Run 36252973589 at `bc545a9`: `name-guard`, `python-bare` and
`nonet-linux` success; `nonet-windows` failure at `shim`, sixteen times
`softfloat/c89/stdbool.h:26:13: error: 'bool' cannot be defined via
'typedef'` on MSYS2's gcc 16.1.0, the fifteen targets before it passing.
Run 36253639874 at `62bb357`, after D-596: all four jobs success.
`nonet-linux` (ubuntu-24.04 image 20260920.314.1, gcc 13.3.0, GNU Make 4.3,
Python 3.13.15) and `nonet-windows` (windows-2025-vs2026 image
20260922.246.2, MSYS2 gcc 16.1.0, GNU Make 4.4.1, CPython 3.13.15) each
close `ONFLY test: 23 PASS, 0 SKIP, 0 PENDING, 2 EXEMPT`, the two EXEMPT
being `ic3270`'s D-132 checks. `python-bare` printed `third-party packages
present: []` and ended with every file passing or skipping through
`onfres`. `name-guard`: `lint_name: tree clean, 1112 tracked files` and
`name-guard: 1 commit messages checked, 0 with findings`. VL-142 registers
these figures and what they do not show.

**GitHub settings, read back** with `gh api repos/mertefesensoy/ONFLY` after
D-593's three commands, each of which exited 0: topics `c89, cobol,
computational-neuroscience, connectome, deterministic-simulation,
drosophila, hercules, mvs, s390x, softfloat, spiking-neural-network`;
`has_discussions` true, `has_wiki` false, `has_projects` false,
`delete_branch_on_merge` true; label `proposal` present. After the owner's
upload, GraphQL `usesCustomOpenGraphImage` reads `true` (D-594).

**Still to be shown at this commit**, and recorded below when it is: the
full strict `make test` on the final commit; CI on the final commit; P-41's
scans 11.1 to 11.3 and 11.13; the batch to `main` (D-583); then 11.6 and
11.10 on `main`.

## 7. Related docs

- `docs/plan/2026-09-26-open-source-slice-f.md` (P-46) and
  `docs/plan/2026-09-24-open-source-launch.md` (P-41), Sections 4 and 11.
- SRS Appendix A.1, D-576 to D-596; Appendix D, VL-139, VL-140 and VL-142.
- `docs/implementations/2026-09-26-open-source-launch-slice-e.md`, whose
  D-558 this slice's D-596 follows.
