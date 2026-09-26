# Plan: P-41 slice F, community infrastructure (2026-09-26)

| Field | Value |
|---|---|
| Scope | D-576: P-41's slice F, steps F1 to F7 of `docs/plan/2026-09-24-open-source-launch.md` |
| Decisions it rests on | D-576 scope; D-577 branch fast-forwarded to `54121d6`; D-578 push this session's branch only, `main` untouched until D-504's batch. Earlier: D-478 (one author, no trailer), D-479 and D-484 to D-486 (the name rule), D-504 (slices C to F reach `main` as one batch), D-505 (the owner's address may appear in tracked text), D-518 (the spelling "Şensoy"), D-520 (no affiliation), D-544 and D-573 (the first tag, open again), D-545 (release assets), D-548 (the exemption table), D-554 (item 7 answered for slice E only) |
| Proposal | P-46, APPROVED as drafted 2026-09-26 (D-579). Section 7's questions were answered the same day: Q2 by D-580 (Discussions **on** as the inbox for questions, against the recommendation), Q3 by D-581, Q4 by D-582, Q5 by D-583, Q6 by D-584, Q7 by D-585, Q8 by D-586, Q9 by D-587; and the name scans by D-588 |
| Not a phase | No Section 9 phase opens or closes (D-576). The exit is P-41's own: "the community profile lists every file; the four named jobs exist and pass on `main`", verified by 11.6 and 11.10 after push |
| Platforms | **x86-64 Windows 11:** MinGW.org gcc 6.3.0, GNU Make 3.82.90, Python 3.13.14, for the local `make test`. **GitHub-hosted runners** (new in this slice): `ubuntu-latest` and `windows-latest`, each job logging its own `gcc -v` and `python -VV`. Nothing runs on Linux s390x, on TK5 or on z/OS |

Every new file follows P-41 3.4: no em dashes, plain measured prose, one
author spelling ("Mert Efe Şensoy", D-518). No text names the hosted IBM Z
access program; the staged diff and each commit message are checked with
`python tools/lint_name.py --staged` and `--message` before committing.

## 1. What the survey found (measured 2026-09-26, this session)

| # | Finding | How it was measured |
|---|---|---|
| S1 | GitHub computes the community profile from the default branch. On `main` (cb20a28) it reports health 28 and every file `null`, the README included: `main` has no `README.md`, because slices C to E are on working branches (D-504) | `gh api repos/mertefesensoy/ONFLY/community/profile`; `git ls-tree --name-only cb20a28` |
| S2 | The tree has no `.github/`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `SUPPORT.md`, `CITATION.cff`, `CHANGELOG.md` or `.mailmap` | `ls` at `54121d6` |
| S3 | Actions are enabled with `allowed_actions: all` and `sha_pinning_required: false`; the default `GITHUB_TOKEN` is already read-only and may not approve pull requests | `gh api .../actions/permissions`, `.../actions/permissions/workflow` |
| S4 | Repository settings: `has_wiki` true, `has_projects` true, `has_discussions` false, `topics` empty, `delete_branch_on_merge` false. The description already ends with P-41 3.2's short form (D-540) | `gh api repos/mertefesensoy/ONFLY` |
| S5 | Private vulnerability reporting is **disabled**. Secret scanning and push protection are **enabled**; Dependabot security updates are disabled; there is no ruleset | `gh api .../private-vulnerability-reporting`, `--jq .security_and_analysis`, `.../rulesets` |
| S6 | Commit identities: 375 commits as `Mert Efe Sensoy <sensoymertefe@gmail.com>` and 2 as `MERT EFE ŞENSOY <sensoymertefe@gmail.com>`. One address, two spellings of the name | `git shortlog -sne --all` |
| S7 | The owner's `gh` token carries the `repo` and `workflow` scopes, so a push can add a workflow file | `gh auth status` |
| S8 | Of the 15 `tests/test_*.py` files, 5 import numpy or pandas; each of the 5 already skips through `tools/onfres.py` when the package is missing (`test_disc.py:47`, `test_gain.py:40`, `test_seeds.py:66`, `test_signs.py:32`, `test_varnt.py:41`). A bare Python can therefore run all 15 without an ImportError | `grep` of the imports |
| S9 | `make test-nonet` is 23 targets (Makefile:915). On `x86l` TestFloat builds out of tree as a prerequisite of `tt02`; on `x86w` `mingw32-make testfloat` is a separate first step (Makefile:440-446) | Makefile |
| S10 | D-558's `-std=gnu17` override applies to `ONFPLAT=x86l` only. `windows-latest`'s MSYS2 ships a current mingw-w64 gcc, whose version is **not measured here**; if it is gcc 15, the `shim` target meets the C23 `bool` keyword there as it did in WSL. P-41 F6 already says the Windows job "matches `x86w`'s ONFPLAT value but not its recorded toolchain" | Makefile:89-104; expectation, to be measured by the first CI run |
| S11 | `README.md:84-86` says "Linux on x86-64, macOS and arm64 are untested". Slice E tested Linux x86-64 (VL-140), and `REPLICATING.md:70-73` documents it, so the README line is stale. P-41 F3 makes `SUPPORT.md` list the tested platforms "as in D1", that is, as the README does | `sed -n 84,86p README.md` |
| S12 | `THIRD_PARTY_NOTICES.md` Section 7 and `tools/lint_ntc.py`'s `TOOLS` list every tool used but not included (NFR-LIC-01). CI adds GitHub Actions, the GitHub-hosted runner images and MSYS2 | `THIRD_PARTY_NOTICES.md:219-246`; `tools/lint_ntc.py:87-90` |
| S13 | The three actions F6 needs, at their latest releases, all MIT: `actions/checkout` v7.0.1 at `3d3c42e5aac5ba805825da76410c181273ba90b1`, `actions/setup-python` v7.0.0 at `5fda3b95a4ea91299a34e894583c3862153e4b97`, `msys2/setup-msys2` v2.32.0 at `66cd2cce69caa17b53920067426061ca1de3a884` | `gh api repos/<action>/releases/latest` and `.../commits/<tag>` |
| S14 | `REUSE.toml`'s first annotation covers every path as MIT, so community files ONFLY writes need no new annotation. A verbatim copy of the Contributor Covenant (CC BY 4.0) would need its own annotation and a register entry | `REUSE.toml:19-25` |

## 2. The work, in P-41's order

### F1. `CONTRIBUTING.md`

How the project is run: D-rows are owner decisions, P-rows proposals, VL-rows
verification limits, and the SRS is the contract. An outside proposal enters
as an issue labelled `proposal`, which the owner may record as a P-row and
decide as a D-row; contributors never write D-rows. The bottom-up test rule of
SRS 8.1. `third_party/` is byte-identical to upstream (D-28, D-35) and
`generated/` is never edited by hand (IR-COM-01), so pull requests that edit
either are declined. Every meaningful change carries an implementation doc
from `docs/implementations/_TEMPLATE.md`. The commands a contributor runs
(`make test-nonet`, `ONFLY_NOSKIP=1`) and how to read the closing line. The
contribution terms of item 24 (Q3). The name rule is stated as a guard that
exists (`tools/lint_name.py`), never by naming the word.

### F2. `CODE_OF_CONDUCT.md` and `SECURITY.md`

`CODE_OF_CONDUCT.md` adopts the Contributor Covenant 2.1 in the form Q7
chooses, with the reporting contact of item 25 (Q4). `SECURITY.md`: the scope
is malformed network and request files reaching ONFLYENG (FR-LOD-02's checks,
NFR-REL-01) and the local lab tooling; reports go through GitHub private
vulnerability reporting, which the owner switches on (S5); supported versions
are the `main` branch only until the first release.

### F3. `SUPPORT.md`

One maintainer; the tiers, the response window and the one inbox of item 12
(Q2); the tested platforms exactly as the README states them, after S11's
correction (Section 4, T5); what CI runs and that it is not matrix evidence
(Q8).

### F4. Issue and pull request templates

`.github/ISSUE_TEMPLATE/bug_report.yml` asks for platform, compiler and
version, float backend, the `ONFnnn` messages and the `make test` closing
line. `replication_report.yml` asks for OS, ABI, compiler and version,
backend, the network SHA-256, the G-01 to G-19 fingerprints and the SKIP
count: the route by which a stranger's result becomes a candidate matrix
entry, never an entry by itself. `config.yml` turns blank issues off and
points to the one inbox of item 12. `.github/pull_request_template.md` asks
for the requirement IDs touched, the tests run with their closing line, and
the platform they ran on.

### F5. `CITATION.cff`, `CHANGELOG.md`, `.mailmap`

`CITATION.cff` (CFF 1.2.0): ONFLY by "Mert Efe Şensoy", no affiliation
(D-520), `license: MIT`, the C2 opening sentence in its abstract, the
repository URL, and references to MaleCNS v1.0 (Berg et al., *Cell* 2026,
as D-538 corrected it), Shiu et al. 2024 and FlyWire. The `version` key
follows Q9. `CHANGELOG.md` is seeded from Section 9.2's phase markers and
P-41's slice marks, newest first, each entry naming its closing D-row, under
an "Unreleased" heading, since nothing has been tagged. `.mailmap` maps both
identities of S6 to `Mert Efe Şensoy <sensoymertefe@gmail.com>`, so that
`git shortlog` and GitHub show one author with D-518's spelling; D-505
allows the address in tracked text. No commit is rewritten.

### F6. CI, `.github/workflows/ci.yml`

One workflow, on `push` and `pull_request`, never `pull_request_target`;
`permissions: contents: read` at the top; no secrets; `concurrency` per ref
with cancel-in-progress; `timeout-minutes` on every job; every action pinned
to the full commit SHA of S13 with its tag in a comment; `actions/checkout`
with `persist-credentials: false`. Each job logs `python -VV`, and each job
that compiles logs `gcc -v` and `pip freeze`.

| Job | Runner | What it runs | Pass means |
|---|---|---|---|
| `name-guard` | ubuntu-latest | Checkout with `fetch-depth: 0`; `tools/lint_name.py --self-test` and `--tree`; then every commit message of the pushed range through `--message`. The range is `before..sha` on a push, `base..head` on a pull request, and `origin/main..HEAD` when `before` is all zeros (a new branch) or unreachable (a forced push) | Exit 0; output is counts and paths only, never the matched text |
| `python-bare` | ubuntu-latest | Python 3.13 from `setup-python` and **no** `pip install`: `tools/lint_lic.py`, `tools/lint_ntc.py --self-test` and plain, then each `tests/test_*.py` file as the Makefile invokes it. Not strict: the point is that a bare checkout runs every Python test to a clean pass or a counted `onfres` skip, and never to an ImportError (S8) | Exit 0 for every file; the skip lines are printed and counted |
| `nonet-linux` | ubuntu-latest | Python 3.13, `pip install -r requirements.txt`, then `ONFLY_NOSKIP=1 make ONFPLAT=x86l PYTHON=python test-nonet` | Exit 0 and the closing `ONFLY test:` line with SKIP 0 |
| `nonet-windows` | windows-latest | `msys2/setup-msys2` with `msystem: MINGW32`, `path-type: inherit`, installing `mingw-w64-i686-gcc` and `mingw-w64-i686-make`; Python 3.13 from `setup-python`; `pip install -r requirements.txt`; `mingw32-make testfloat`, then `ONFLY_NOSKIP=1 mingw32-make test-nonet` | As `nonet-linux` |

`.github/dependabot.yml` updates the `github-actions` ecosystem weekly, so
the pinned SHAs do not rot silently; it opens pull requests the owner reviews.
`.github/CODEOWNERS` names `@mertefesensoy` for `.github/`. `golden` is not
written here: it needs the networks, which arrive as release assets in G5.

**Hashes for pip.** F6 asks for them "if feasible". Hash mode needs every
transitive package pinned with a hash for every wheel of both runners and both
Python lines of `requirements.txt`, which is a generated lock file and a new
tool to generate it. This plan does not do it: the `==` pins stay, and the gap
is a follow-up named in the implementation doc.

**A CI failure on a runner toolchain** (S10) is not worked around in the
workflow. It is put to the owner under item 7's second half: a source fix with
evidence that no fingerprint moves, or a documented flag override for a
compiler with no recorded row, on the D-558 precedent.

**Notices.** `THIRD_PARTY_NOTICES.md` Section 7 gains GitHub Actions (the
three actions of S13, MIT), the GitHub-hosted runner images and MSYS2, each
with its terms as its upstream states them; `tools/lint_ntc.py`'s `TOOLS`
gains the same names, so the register cannot lose them silently
(NFR-LIC-01). `tests` for `lint_ntc.py` are its `--self-test`, which already
builds a tree from `TOOLS`.

### F7. Settings, all owner actions in P-41

The engineer changes no security setting: private vulnerability reporting,
the allowed-actions list (GitHub-owned plus `msys2/setup-msys2`), approval for
workflows from outside forks, the read-only token (already so, S3), secret
scanning and push protection (already on, S5) and the ruleset on `main`
blocking force-push and deletion. Those stay the owner's. The rest are
ordinary repository settings: topics, wiki off, projects off, auto-delete
head branches, Discussions per item 12, the `proposal` label, and a social
preview. Q6 asks who applies them. Proposed topics, for the owner to edit:
`drosophila`, `connectome`, `computational-neuroscience`,
`spiking-neural-network`, `deterministic-simulation`, `c89`, `cobol`,
`mvs`, `hercules`, `s390x`, `softfloat`. No IBM mark is a topic
(NFR-BRD-01), and none says "mainframe" unqualified (P-41 3.3).

## 3. Order of work and commits

1. **C1, record.** The owner's answers to Section 7 as D-rows in A.1, this
   plan's approval included, before any file they govern is written.
2. **C2, F1 to F5 and T5.** The community files, the README line, and the
   notices additions of F6 that do not depend on CI running.
3. **C3, F6.** The workflow, Dependabot and CODEOWNERS, with `lint_ntc.py`'s
   `TOOLS`. Push; read each job with `gh run view`. A red job is diagnosed and
   its fix put to the owner (F6, S10) before anything is changed.
4. **C4, record.** VL-142, the implementation doc
   `docs/implementations/2026-09-26-open-source-launch-slice-f.md`, P-41's
   status line, this plan's A.2 row.
5. **The exit on `main`**, as Q5 decides. If the batch is to reach `main`, the
   evidence is put to the owner once more, just before the push, because a
   push to `main` is a publication (P-41 3.4).
6. **F7** by the owner, or by the engineer for the non-security settings as
   Q6 decides; then 11.6 and 11.10.

## 4. SRS text changes this plan asks to be authorised

| # | Change | Where |
|---|---|---|
| T1 | D-rows for every owner answer to Section 7, and for any decision met on the way | Appendix A.1 |
| T2 | This plan's row P-46, struck as approved when it is | Appendix A.2 |
| T3 | **VL-142**, what CI shows and does not: network-free checks on GitHub-hosted x86-64 runners, with their own compilers; not Section 8.3 evidence; `golden` absent until G5 | Appendix D |
| T4 | A D-row recording P-41 3.2's review of VL-139 for the platforms CI adds. GitHub-hosted runners are x86-64 virtual machines, so no IBM Z hardware or access is involved; the proposal is that VL-139 stands unchanged, as D-562 found for WSL2 | Appendix A.1 |
| T5 | Not SRS text, but owner-approved text (D-532): `README.md:86` names Linux x86-64 as tested, citing the WSL2 host of VL-140, so that README and `SUPPORT.md` agree (S11) | `README.md` |

No requirement text changes. No Section 8.3 row changes.

## 5. Verification, and what the exit needs

| Check | Command | Expected |
|---|---|---|
| Local suite, strict | `ONFLY_NOSKIP=1 mingw32-make test` on this host after the last commit | Exit 0; `ONFLY test: 28 PASS, 0 SKIP, 0 PENDING, 5 EXEMPT` |
| Guards on what this slice adds | `mingw32-make namelint ntclint liclint`; `python tools/lint_name.py --staged` and `--message` per commit | Exit 0 |
| 11.13 | P-41's em dash count over every added file and the added SRS lines | 0 in added files; added SRS lines reported under D-536's reading |
| 11.1 to 11.3 | P-41's scans with `ONFLY_NAME_B64` | `total 0` and `hits: 0`, **only if the owner sets the variable**; otherwise NOT RUN, and the committed guard's result stands in |
| CI on the branch | `gh run view <id> --json jobs --jq '.jobs[]\|[.name,.conclusion]'` | The four jobs `success` |
| 11.10 | as above, plus `python tools/lint_name.py --self-test` and `git config --get-all core.hooksPath`, and the throwaway-worktree rejection test | As P-41 states; the rejection test needs `ONFLY_NAME_B64`, else NOT RUN |
| 11.6 | P-41's four `gh api` calls | Every community file listed and PVR `true`: **only after the files reach `main` and the owner has done F7** |

## 6. What this plan will NOT prove or change

1. A green CI job is a smoke test on a GitHub-hosted runner's toolchain. It
   is not Section 8.3 evidence and reproduces no recorded row: `nonet-windows`
   is not MinGW.org gcc 6.3.0, and `nonet-linux` is not WSL2's gcc 15.2.0.
2. No network file, fingerprint or golden request runs in CI; `golden` waits
   for G5.
3. Nothing runs on Linux s390x, TK5 or z/OS. The project still has no IBM Z
   access (VL-139).
4. The community files state policy; whether the owner can keep the stated
   response window is not something a file can prove.
5. Contribution terms (item 24) and the conduct contact (item 25) are marked
   in P-41 as questions where legal input is advisable; this plan records the
   owner's choice and gives no legal advice.
6. The first-tag question D-573 reopened, items 8, 9 and 29's pre-G check,
   and slice G itself stay open.

## 7. Open questions put to the owner with this plan

| # | Question | Options, recommendation first |
|---|---|---|
| Q1 | Approve P-46? | Approve as drafted; change it; discuss first |
| Q2 | Item 12: support policy and inbox | P-41's recommendation: supported x86-64 suite and evidence audit; best effort s390x and TK5; unsupported Raincode, INTERCOMM, z/OS; a 14-day window for issues; issues as the one inbox, Discussions off at launch. Or the same with Discussions on as the inbox for questions |
| Q3 | Item 24: contribution terms (legal input advisable) | Contributions accepted under the licence of the path they change, as GitHub's terms of service provide; no non-commercial or unlicensed third-party material (D-132); `third_party/` edits declined. Or a DCO sign-off on every contributed commit |
| Q4 | Item 25: contact for conduct and security reports | GitHub private vulnerability reporting for security, and the owner's existing address for conduct reports (D-505 already allows it in tracked text). Or PVR plus a new dedicated address the owner creates and supplies |
| Q5 | Slice F's exit on `main` | Push D-504's batch (slices C to F) to `main` at the end, asked once more with the evidence just before the push. Or leave `main` untouched this session and report the exit NOT MET, CI verified on the branch only |
| Q6 | Who applies F7's non-security settings | The engineer, with `gh repo edit` and `gh label create`, after the owner approves the exact commands; security settings stay the owner's. Or the owner applies all of F7, as P-41 wrote it |
| Q7 | The Code of Conduct's form | Adopt Contributor Covenant 2.1 by reference: ONFLY's own text naming and linking the canonical version, with the contact and the enforcement route in plain words, so no third-party text enters the MIT tree. Or the owner adds the verbatim text through GitHub's template, annotated CC BY 4.0 in `REUSE.toml` and the register |
| Q8 | Item 7's CI half, and T3 and T4 | CI is smoke tests only, never Section 8.3 evidence, recorded as VL-142; VL-139 reviewed and unchanged. Or CI results enter Section 8.3 as provenance sub-rows |
| Q9 | `CITATION.cff`'s `version` | No `version` key until the first-tag question D-573 reopened is decided before slice G. Or `0.5.1`, what the engine prints; or `0.5.0`, D-544's tag |
