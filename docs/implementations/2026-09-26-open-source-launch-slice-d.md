# 2026-09-26: P-41 slice D, a truthful public surface

| Field | Value |
|---|---|
| Date | 2026-09-25 to 2026-09-26 |
| Author | Mert Efe Şensoy |
| Phase / gate | None. Slice D of P-41 (`docs/plan/2026-09-24-open-source-launch.md`), run together with slice C under D-513; plan of record P-43 (D-531) |
| Owner decisions relied on | D-513, D-514, D-522 to D-530, D-531 to D-540; earlier D-485, D-491, D-492, D-512 |
| Requirements touched | C-07 and ACC-3 (requirement text amended, D-535); Sections 1.1, 2.3, 2.4, 9.2 row F; Appendices D (VL-139), F and G |
| Open items closed | P-41 items 4, 13, 16, 17, 18, 19, 32 (D-522 to D-527, D-529); item 9 deferred (D-528) |

## 1. Problem / motivation

A visitor to the repository found no README, so GitHub showed the licence
text instead. Slice B had removed the old summary, which named the hosted
IBM Z access program and was stale. Nothing public said that ONFLY has never
run on IBM Z hardware. Code comments called the emulated Hercules lab "a
mainframe". The first files a replicator reads were out of date:
* `data/phase-d/README.md` still said no MVS engine exists;
* `tests/run_gld.py` still called the durations provisional and rows 4 to 8
  unrun.

The SRS itself gave the ACC-3 40 Hz margin as 0.56 Hz where the record says
0.85 Hz.

## 2. What changed

| File | Change |
|---|---|
| `README.md` | New: description, the no-access statement, status and matrix, what can be reproduced today, limits, map, licence, trademarks, AI use, citing (D-532, D-533). |
| `docs/overview.md` | New: the public account replacing the removed summary, built from P-41's claims register (D-534, D-529). |
| `docs/README.md` | New: a reading guide to the SRS and the records. |
| `generated/README.md` | New: which program writes each generated file, and why they are committed. |
| `tools/README.md` | New: a map of the tools by purpose. |
| `data/phase-d/README.md` | A dated update below the stale sentence, which is kept. |
| `tests/run_gld.py` | Docstring and one comment: rows 4 to 8 and the durations described as they are now. |
| `Makefile` | The comment above `golden` brought up to date. |
| 12 files under `tests/`, `tools/` and the `Makefile` | 25 occurrences of "mainframe" in comments qualified as the emulated MVS lab; comments only. |
| `docs/ONFLY-SRS.md` | Front matter; Sections 1.1, 2.3 and 2.4; C-07; ACC-3's margin; row F; VL-139; three glossary entries; D-513 to D-540; P-43 (D-535, D-536, D-538). |
| `docs/plan/2026-09-24-open-source-launch.md` | Status, and the item rows the new D-rows close. |
| `docs/plan/2026-09-25-open-source-slices-c-d.md` | P-43, and its D-539 correction note. |
| `docs/implementations/2026-09-25-open-source-launch-slice-b.md` | A dated correction note on its 11.13 figure (D-537). |
| GitHub repository description | Set to CAN-01's summary plus P-41 3.2's short form (D-540). |

## 3. Implementation approach

**Every result sentence comes from the claims register.** P-41 Section 5 is
the register, and a sentence about what ONFLY does or has shown is either a
register entry's ready phrasing or a narrower restatement of one. Structural
sentences, such as where a file is, which licence covers what and how to
cite, are sourced to the file or D-row that fixes them. The full map is in
section 6.

**The drafts went back to the owner before commit.** The README (D-532),
its AI-use paragraph as a separate question because only the owner can
confirm it (D-533), and the overview (D-534).

**Stale statements were dated, not rewritten.** The record sentences in
`data/phase-d/README.md` are kept, with a dated update after them. Docstrings
and comments that describe current behaviour are corrected in place and say
when.

## 4. Mathematical / numerical details

**The ACC-3 margin at 40 Hz (D-526).** For a tested rate, ACC-3 defines:
* the tolerance, T = max(0.10 × ref, 1 Hz);
* the difference, d = sub − ref;
* the margin, m = T − |d|.

From `data/calibration/acc3-srext.json`:
* ref = 14.35 Hz and sub = 13.7667 Hz, so d = −0.5833 Hz;
* T = max(1.435, 1) = 1.435 Hz;
* m = 1.435 − 0.5833 = 0.8517 Hz.

The SRS said 0.56 Hz. The reference mean's standard error over 30 seeds is
sd/√30 = 8.4488/5.4772 = 1.5425 Hz, and D-357's clause names a rate as
within the reference's own precision when m < SE. That holds at either
figure, since 0.85 < 1.54, so no verdict moves.

## 5. Design decisions

* **No tagline in the README** (D-523): the owner kept the SRS tagline, and
  the claims register forbids its wording in public copy.
* **No image, no name-collision line, no roles** (D-530, D-528, D-519).
* **No link to files that do not exist yet** (engineer, P-43). The README
  gives R0 to R4 in three tiers without linking `REPLICATING.md`, which is
  slice E's.
* **`tools/fixtures.py`'s message left to slice E** (P-43): E3 rewrites that
  code path.
* **11.13 read as counting new text** (D-536). See section 6.

## 6. Verification

All on x86-64 Windows 11: MinGW.org gcc 6.3.0 (32-bit), Python 3.13.14.

| ID | Command | Result |
|---|---|---|
| D-V1 | `grep -c 'ONFLY has not run on IBM Z hardware' README.md docs/overview.md docs/ONFLY-SRS.md` | `README.md:1`, `docs/overview.md:1`, `docs/ONFLY-SRS.md:3` |
| D-V2 | P-41 11.13, measured by a script that decodes as UTF-8 (`scratchpad/emdash.py`, run against cb20a28) | All 16 files added: 0 em dashes each. SRS lines this session edited: **0 new, 3 inherited**, two in ACC-3's D-357 sentence and one in row F's label, which D-536 reads as a pass |
| D-V3 | The map below | Every item mapped; none removed |
| D-V4 | `gh api repos/mertefesensoy/ONFLY --jq .description` | The D-540 text, ending "No IBM Z hardware used: the project does not have IBM Z access yet. MVS and s390x results are emulated (Hercules, QEMU)." |
| R0 | `python tests/run_tx.py --compare data/phase-d/x86w data/phase-d/s390x`; `python tests/run_mvsrun.py`; `python tests/run_mvsjcc.py`, in this worktree before any network file or build existed | `run_tx: 25 identical, 0 differing`; `run_mvsrun: 49 passed, 0 failed`; `run_mvsjcc: 53 passed, 0 failed`; each exit 0. This is what the README's first tier promises |

**The 11.13 measurement, and the finding behind D-537.** In this host's
shell, text piped into Python is decoded as cp1252. P-41's one-line 11.13
command therefore reads each em dash as three other characters and prints 0.
It printed 0 for this session's diff, and it did so for slice B's. Decoded
as UTF-8, slice B's SRS diff (2529abf to cb20a28) has 2 added lines with
inherited em dashes, and this session's has 3. Slice B's record now carries
a dated note saying so.

**Sentence-to-claim map (D-V3).** S is a sentence and T a table row, numbered
in reading order by a script that splits each file. CAN ids are P-41 Section
5 entries. "Str." marks a structural statement, with its source.

| README items | Source |
|---|---|
| S01, S02 | CAN-01 |
| S03 | C-02 (no IEEE floating point in S/370), NR-02, CAN-02 |
| S04 to S06 | CAN-03; P-41 3.2 long form verbatim; VL-139 |
| S07, S08 | Str.: the three files exist |
| T09 to T16 | SRS 9.2 phase markers D-252, D-47, D-206, D-234, D-348, D-442; G's wording from CAN-09, CAN-11, CAN-12; F from CAN-03; H from 9.2 row H |
| S17 | Str.: SRS 9.2's note on letters and order |
| S18 to T27 | CAN-02; rows and compilers from SRS 8.3, `data/phase-d/README.md` (MinGW gcc 6.3.0), VL-82 (gcc 13.3.0), rows 6 and 7 (GCCMVS 3.2.3, JCC 1.50.00) |
| S28 | CAN-02 |
| S29 | VL-05; P-41 MUST NOT 10 |
| S30, S31 | Measured this session: R0 above |
| S32 to S36 | CAN-10's limit; sizes from P-41 E3 and `data/networks/MANIFEST.json`; toolchain from P-41 6.1 R1 and 2.2 |
| S37 to S39 | CAN-10, CAN-11, D-132 |
| S40, S41 | SRS 8.3 rows; VL-82; CAN-05 (Hercules 4.9.1); P-41 D1 (untested platforms) |
| S42, S43 | CAN-06; SRS 9.2 Phase E note (ACC-1 to ACC-4 are x86-64 results) |
| S44 to S46 | CAN-07 and its limits (VL-114) |
| S47, S48 | CAN-08 |
| S49, S50 | CAN-15 |
| S51 | CAN-04 |
| S52, S53 | CAN-05 |
| S54, S55 | CAN-09, CAN-11 |
| S56, S57 | CAN-12, CAN-14 |
| T58 to T67 | Str.: the tree |
| S68 to S71 | Str.: `LICENSE`, `THIRD_PARTY_NOTICES.md`, D-516, D-515, `REUSE.toml` |
| S72 | Str.: P-41 C4; the 2c notice |
| S73 | Str.: VL-38, D-132; the INTERCOMM terms read 2026-09-25 |
| S74 to S79 | Str.: P-41 C9 text; D-519, D-520; IBM's page and the Linux Foundation's wording, read 2026-09-25 |
| S80 to S84 | D-522, confirmed accurate by the owner (D-533); D-478 |
| S85, S86 | Str.: Appendix G references 2 (D-538) and 4 |

| Overview items | Source |
|---|---|
| S01 to S03 | CAN-03; P-41 3.2 long form |
| S04 | D-491, D-492, VL-139 |
| S05, S06 | CAN-01 |
| S07, S08 | Str.: SRS 1.3 |
| S09 | C-02, NR-02 |
| S10, S11 | CAN-01's limits; VL-13; MUST NOT 5 |
| S12 to S16 | CAN-02; VL-05 |
| S17 | CAN-06 |
| S18, S19 | CAN-07 and VL-114 |
| S20, S21 | CAN-08 |
| S22, S23 | CAN-15 |
| S24 | CAN-04 |
| S25 | CAN-13 |
| S26 | CAN-05 |
| S27, S28 | CAN-12, CAN-14 |
| S29 | CAN-09 |
| S30, S31 | CAN-11 |
| S32 to S35 | CAN-10, stated as it stands before slices E and G |
| S36, S37 | SRS 9.2 rows F and H; TBD-13; VL-139 |
| S38 | Str.: P-41's purpose (D-488) |
| S39 to S41 | Str.: the files |
| S42 | Str.: P-41 C9; D-520 |

**The full suite.** `mingw32-make test` result: see section 7.

**Not proven.**
* No outside reader has read the README against the register. P-41's W1a
  read needs a reader other than the owner and the engineer, and it remains
  to be done before slice G.
* The README's tier 2 cannot be run from a clone until the networks are
  distributed (slice E). It was run here with the networks copied from the
  main checkout.
* Every result the README and overview quote was measured in earlier
  sessions, and each names its platform. This session re-measured only R0
  and the suite in section 7, both on x86-64.
* Nothing ran on s390x, MVS or z/OS this session.

## 7. Suite and push

**T-V1, before the commit.** `mingw32-make fixtures`, `mingw32-make
testfloat` and `mingw32-make test`, run in this worktree from 00:06:44 to
00:18:56 on 2026-09-26. Result: `FIXTURES_EXIT=0`, `TESTFLOAT_EXIT=0`,
`MAKE_EXIT=0`. The platform is x86-64 Windows 11 with MinGW.org gcc 6.3.0,
on the SOFT3E, SOFT2C and NATIVE backends. Among its lines:
* `lint_ntc: self-test 13 checks, 0 failed` and `lint_ntc: ok`, the new
  `ntclint` target;
* `lint_lic: ok`;
* `lint_name: tree clean, 1062 tracked files`;
* `lint_col80: 80 files scanned, all within 80 columns`;
* `run_tt02: 18 of 18 operation runs passed, 781128 cases checked`;
* `run_gld` at `20 passed, 0 failed` on each of SOFT3E, NATIVE and SOFT2C;
* `cmpgld: SOFT3E, NATIVE, SOFT2C agree on all 19 golden requests across 2
  networks`;
* `cmpchk [FR-SIM-10 chunk invariance]: 24 passed, 0 failed`.

Two lines report that a prep test could not remove its temporary network
file under `AppData\Local\Temp`, with WinError 2 and WinError 5. They did not
fail the run and come from a test's cleanup, not from anything this slice
changed. The notices and README files were untracked during this run, so
`lint_lic` and `lint_name` scanned them only after the commit, in the final
run.

The push and GitHub's licence reading are recorded in the follow-up commit.

## 8. Related docs

* `docs/plan/2026-09-25-open-source-slices-c-d.md` (P-43); P-41 slice D and
  Section 5.
* `docs/implementations/2026-09-26-open-source-launch-slice-c.md`.
* `docs/ONFLY-SRS.md`: D-513 to D-540, VL-139, Appendix F.
