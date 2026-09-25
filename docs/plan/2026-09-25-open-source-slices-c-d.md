# Plan: P-41 slices C and D, licence and notices with a truthful public surface (2026-09-25)

| Field | Value |
|---|---|
| Scope | D-513: slices C and D of `docs/plan/2026-09-24-open-source-launch.md` (P-41, approved by D-488), together |
| Decisions it rests on | D-514 push the working branch only; D-515 item 8 pending legal input; D-516 item 20 CC BY 4.0; D-517 item 21 amend C-08; D-518 item 23 "Şensoy"; D-519 item 10 no roles; D-520 item 29 personal project; D-521 `reuse` pinned in scratch; D-522 item 4 AI-use section; D-523 item 16 tagline kept; D-524 item 17 reader classes only; D-525 item 18 glossary; D-526 item 19 correct and annotate; D-527 item 32 a VL row; D-528 item 9 deferred; D-529 item 13 `docs/overview.md` without `.docx`; D-530 no README image. Earlier: D-50, D-62, D-132, D-478, D-484 to D-512 |
| Proposal | P-43 |
| Not a phase | No Section 9 phase opens or closes. The exits are P-41's own for C and D, as D-513 states them |
| Platform | x86-64 Windows 11, MinGW.org gcc 6.3.0 (32-bit), Python 3.13.14. Nothing here runs on s390x, MVS or z/OS |

Every new public file follows P-41 3.4: no em dashes, plain measured prose,
no IBM or program logos, one author spelling (D-518). Every factual sentence
in the README and the overview comes from P-41's claims register (Section 5)
and is mapped to its CAN entry in slice D's implementation doc. No text names
the hosted IBM Z access program; `tools/lint_name.py` and the installed hooks
check every commit.

## 1. The component register (what "every LIC-00 component" means here)

The licensing audit behind P-41 is not in the repository, so its LIC-00 list
is rebuilt here from P-41 C2 to C6 and a scan of the tree. This list is what
slice C's exit is checked against, and `tools/lint_ntc.py` (Section 2, verified by C-V1)
holds `THIRD_PARTY_NOTICES.md` to it.

**In the tree:**

| # | Component | Paths | Terms |
|---|---|---|---|
| 1 | Berkeley SoftFloat 3e | `third_party/SoftFloat-3e/`; derived `softfloat/onfrpk.c`, `softfloat/onfprim.c`, `softfloat/onfsub.c` | BSD-3-Clause |
| 2 | Berkeley TestFloat 3e | `third_party/TestFloat-3e/`; generated vectors `generated/onftfv.h` | BSD-3-Clause |
| 3 | Berkeley SoftFloat 2c | `third_party/SoftFloat-2c/`; derived `softfloat/c2c/*` | Its own legal notice, reproduced verbatim: use restriction and indemnity; not BSD |
| 4 | Shiu et al. model code | `reference/shiu/model.py`, `reference/shiu/utils.py`, `reference/shiu/LICENSE` | MIT, Philip Shiu and Nico Spiller |
| 5 | MaleCNS v1.0 derived data | `data/networks/`, `data/geom/`, `data/calibration/`, `data/phase-*/`, `data/g0/`, `docs/malecns-*`, `docs/media/` | Upstream CC BY 4.0 (D-50), all four parties; ONFLY's contribution CC BY 4.0 (D-516) |
| 6 | FlyWire-derived material | P-41 item 8 inventory: `reference/shiu/results/`, the twelve `data/calibration/*.json` item 8 names, `docs/implementations/2026-09-12-phase-c-calibration.md`, the SRS text quoting the curve, `reference/shiu/rerun.py`, and W_syn 0.2969 | Pending legal input (D-515): FlyWire's own terms cited, no position taken |

**Correction, 2026-09-26 (D-539).** Row 5 above listed `data/g0/`. It is not
MaleCNS-derived: `data/g0/inventory.json` holds only host, MVS, s390x and x86
environment facts. The register, `REUSE.toml` and `tools/lint_ntc.py` leave it
out of row 5, and it falls under ONFLY's own MIT annotation. The row is left
as approved.

**Used but not included:** JCC, Raincode, INTERCOMM (D-132), SDL Hercules,
TK5, GCCMVS, PDPCLIB, GnuCOBOL, QEMU, wc3270, .NET, brian2, numpy, pandas,
pyarrow, matplotlib, Pillow, the npm `docx` package (D-508), the `reuse` tool
(D-521), MinGW gcc, GNU Make, Python. Each is stated as its upstream publishes
it, with the date checked; nothing is asserted that the upstream page does not
say, and MVS 3.8j is not called public domain.

## 2. Slice C: licence and notices

| Step | Work | Files |
|---|---|---|
| C1 | `LICENSE` keeps only the MIT text; the appended third-party block is removed, and the copyright line reads "Mert Efe Şensoy" (D-518) | `LICENSE` |
| C2 | New `THIRD_PARTY_NOTICES.md`, one entry per Section 1 row (name, version, upstream, paths, SPDX ID or LicenseRef, committed or tool only, required notice), opening with P-41 C2's two paragraphs | `THIRD_PARTY_NOTICES.md` |
| C3, C4 | SoftFloat 3e, TestFloat 3e and SoftFloat 2c entries; 2c's legal notice verbatim, and the statement that every SOFT2C build (every MVS build, and the SOFT2C third of the x86 `make test`) includes 2c and inherits its terms | same |
| C5 | Shiu code (MIT, other holders); MaleCNS with all four parties, the CC BY 4.0 link, the citation and a note of modification; FlyWire per D-515 with the citations its guide asks for. New `reference/shiu/results/NOTICE.md` (a new file, so no digested file changes; only `prep/calibrate.py` reads that directory, and it reads one named file). One non-commercial line added to `reference/shiu/rerun.py`'s docstring, which no manifest digests | `reference/shiu/results/NOTICE.md`, `reference/shiu/rerun.py` |
| C6 | The used-but-not-included tools, each re-verified upstream on the day | `THIRD_PARTY_NOTICES.md` |
| C7 | `softfloat/onfrpk.c` (hand-derived, D-35) gains the full BSD-3-Clause conditions and disclaimer by hand; `softfloat/onfprim.c` is generated, so `softfloat/derive3e.py` is changed to emit them and the file regenerated, never hand-edited (IR-COM-01). Comments only | `softfloat/onfrpk.c`, `softfloat/derive3e.py`, `softfloat/onfprim.c` |
| C8 | New `data/README.md`: MaleCNS attribution for committed derived data and media; ONFLY's part under CC BY 4.0 (D-516); `data/calibration/` per D-515, not assumed CC BY; the stale `"pass": false` in `acc4.json` explained (D-526) | `data/README.md` |
| C9 | The non-affiliation and trademark text, without the roles sentence (D-519), naming "a personal project by Mert Efe Şensoy" (D-520); the IBM mark list rebuilt from marks the new public files actually use and re-checked against IBM's page on the day | `THIRD_PARTY_NOTICES.md`, `README.md` |
| C10 | `REUSE.toml` and a `LICENSES/` directory so that `reuse lint` passes on the whole tree: a catch-all MIT annotation for ONFLY's own files first, then later annotations that override it for rows 1 to 6, which is the REUSE rule that the last matching annotation wins. FlyWire-touched paths get `LicenseRef-FlyWire-Pending`, whose text in `LICENSES/` says what D-515 says | `REUSE.toml`, `LICENSES/*.txt` |
| C11 | `tools/lint_lic.py`'s `SOURCE_SUFFIXES` gains `.md` and `.json`. Measured today: no tracked `.md` or `.json` outside the existing exemptions names an INTERCOMM macro, so this adds coverage and no finding | `tools/lint_lic.py` |
| C12 | The SRS rows of Section 5 below: NFR-LIC-01, C-08, Appendix G | `docs/ONFLY-SRS.md` |

**The notices check (P-41 11.12), to be written test-first:**
`tools/lint_ntc.py` asserts that `THIRD_PARTY_NOTICES.md` names each Section 1
component and each item 8 path; that `softfloat/onfrpk.c` and
`softfloat/onfprim.c` each contain "Redistribution and use in source and
binary forms"; that `reference/shiu/results/NOTICE.md` and `data/README.md`
exist; and that `LICENSE` holds only the MIT text, with no line after the
disclaimer. Its self-test is shown failing on today's tree before the notices
are written. It joins `make test` as a `ntclint` target beside `liclint` and
`namelint`. `reuse lint` is **not** put in `make test`, because `reuse` is not
a declared dependency until slice E's `requirements.txt`; it is run by hand
from the scratch install (D-521) and its output kept in the implementation doc.

## 3. Slice D: a truthful public surface

| Step | Work | Files |
|---|---|---|
| D1 | Root `README.md`, in P-41 D1's order: one paragraph from CAN-01; the no-access statement, long form, verbatim from P-41 3.2; a status table (phases with their closing D-rows, Section 8.3 rows with counts, row 8 empty); what can be reproduced today, in three tiers (evidence check R0, x86 suite R1, the emulated labs R3 and R4), stating plainly that the two network files are not distributed yet, so R1 cannot run from a clone until slice E; tested platforms (x86-64 Windows MinGW32 only; Linux, macOS and arm64 untested); the limits with CAN-15; a repository map; licence, notices and the SoftFloat 2c two-sentence summary; INTERCOMM not included and the 3270 demonstration not reproducible from a clone; trademarks (C9); how the project is built, with the AI-use section (D-522); how to cite, in prose. No tagline (D-523), no image (D-530), no name-collision line (D-528), no roles (D-519), no link to a file that does not exist yet | `README.md` |
| D2 | `docs/overview.md`, written new from P-41 Section 5, the no-access long form as its first section, no request and no program name; no `.docx` (D-529) | `docs/overview.md` |
| D3 | Appendix F's three entries (D-525), worded as P-41 3.3 has them | `docs/ONFLY-SRS.md` |
| D4 | `docs/README.md`, a reading guide; short READMEs for `generated/` (committed on purpose: MVS has no Python) and `tools/`. A README in `generated/` edits no generated file | `docs/README.md`, `generated/README.md`, `tools/README.md` |
| D5 | The SRS front-matter and status text of Section 5 below | `docs/ONFLY-SRS.md` |
| D6 | Stale statements a replicator reads first: `data/phase-d/README.md` line 66 ("no MVS engine exists yet") gains a dated note pointing to VL-91 and VL-138, the record itself kept; `tests/run_gld.py`'s docstring (rows 4 to 8 "unrun", durations "PROVISIONAL"); the Makefile comment above `golden` ("thirteen golden requests ... both backends"). Every "mainframe" in tracked code comments and docstrings found by `git grep -n -i mainframe -- '*.py' '*.c' '*.h' Makefile` (25 today) is qualified as the emulated MVS lab. Comments and docstrings only; no code path changes. **Proposed deferral:** `tools/fixtures.py`'s NOT FOUND message is left to slice E, whose E3 rewrites that code path, so it is not changed twice | `data/phase-d/README.md`, `tests/*.py`, `tools/*.py`, `Makefile` |

The README and the overview are shown to the owner as drafts and approved
through AskUserQuestion before they are committed, because they are the first
text a stranger reads.

## 4. Order of work

1. `tools/lint_ntc.py` and its self-test, shown failing; the `ntclint` target.
2. Baseline: object hashes of `softfloat/onfrpk.c` and `softfloat/onfprim.c`
   compiled with the x86w `CFLAGS`, and `python softfloat/derive3e.py --check`.
3. Slice C files, C1 to C11; C7 last among them, then the object hashes again.
4. `reuse` installed pinned into scratch (D-521); `reuse lint` until it passes.
5. Slice D files, D1 to D6; README and overview drafts to the owner.
6. The SRS changes of Section 5, with the D-rows that record them.
7. Verification (Section 6), implementation docs, P-41 status, commit, push
   to the working branch (D-514).

## 5. SRS text changes this plan asks to be authorised

Each is written with a D-row citing this plan's approval. Requirement text is
marked **(req)**.

| Where | Today | Proposed |
|---|---|---|
| Front matter, Version and Date | "0.1", a dash, "Draft for owner review"; "2026-09-10" | "0.2, public baseline for the open-source launch (D-513)"; "2026-09-10, amended through 2026-09-25" |
| 1.1, first paragraph | ends "...and behind IBM CICS transactions." | adds: "**ONFLY has not run on IBM Z hardware** (VL-139); Section 8.3's row 8 is empty." |
| 1.1, readers | "...and IBM reviewers evaluating a request for project permissions (via the separate one-page summary)." | "...and outside readers, including reviewers of the IBM Z access request when it is made, whom the public overview `docs/overview.md` serves (D-485, D-524)." |
| 2.3, z/OS row | "z/OS on the hosted IBM Z environment the project plans to request" | adds "; not available to this project yet (VL-139)" |
| 2.4, user classes **(req-adjacent)** | "IBM reviewers \| A credible demo and a one-page summary; honest statement of limits" | "Outside readers and replicators, including reviewers of the IBM Z access request \| A truthful overview (`docs/overview.md`), commands to reproduce what is claimed, and an honest statement of limits" |
| C-07 **(req)** | "...does not allow the user to define CICS programs or transactions." | adds "It is not available to this project yet (VL-139)." |
| C-08 **(req)** | "...never in component names." | adds "*(Amended 2026-09-25 by D-517.)* `onfcics`, `Onfly.Cics` and `cics/` are internal identifiers, never presented as a product name, and public copy never calls any part of ONFLY \"ONFLY CICS\"." |
| ACC-3 **(req)**, D-357 note | "a margin of 0.56 Hz" | "a margin of 0.85 Hz *(corrected 2026-09-25 under D-526 from 0.56 Hz: `data/calibration/acc3-srext.json` records a tolerance of 1.435 Hz and a difference of 0.5833 Hz, so 0.8517 Hz; the margin is still below the 1.5425 Hz standard error, so the named rate and every verdict stand)*". D-354 and P-18, which carry the old figure, are records and are left as written (D-524) |
| NFR-LIC-01 **(req)** | "Third-party components and their licenses shall be tracked in the repository: SoftFloat and TestFloat (license text to be recorded, TBC), PDPCLIB (public domain), GCCMVS (GPL compiler; compiled programs are not encumbered), and the MaleCNS data terms (TBC-12)." | "Third-party components, the data ONFLY derives from, and their terms shall be tracked in one register, `THIRD_PARTY_NOTICES.md` at the repository root, covering every vendored or derived component, every source dataset, and every build tool and lab component used but not included. `LICENSE` shall carry only the MIT text (D-62). *(Amended 2026-09-25 by D-5nn: the GCCMVS sentence is dropped as unverified, and the register replaces the list.)*" Verification becomes "I; T: `tools/lint_ntc.py`" |
| 9.2, row F | "Port to the hosted IBM Z environment the project plans to request; determinism row 8" | adds "Not available to this project yet (VL-139)." |
| Appendix D | (none) | **VL-139**: no IBM Z hardware has been used and the project does not have IBM Z access yet; an owner confirmation (D-491, D-492), not a measurement; standing, reviewed by a D-row whenever a platform is added (D-527) |
| Appendix F | (none) | the three P-41 3.3 entries (D-525) |
| Appendix G | 11 references | adds the FlyWire references FlyWire's citation guide names, re-verified on the day |

The tagline stays (D-523). No other requirement text changes.

## 6. Verification, and what each exit needs

| ID | Command | Expected |
|---|---|---|
| C-V1 | `python tools/lint_ntc.py --self-test` then `python tools/lint_ntc.py` | self-test passes; `ok`, exit 0 |
| C-V2 | `reuse lint` (scratch install) | "Congratulations! Your project is compliant" |
| C-V3 | `mingw32-make col80 lint liclint namelint golden` | exit 0 |
| C-V4 | `python softfloat/derive3e.py --check` | exit 0 |
| C-V5 | `gcc $(CFLAGS) -c` of `onfrpk.c` and `onfprim.c`, SHA-256 before and after C7 | identical |
| C-V6 | `gh api 'repos/mertefesensoy/ONFLY/license?ref=<branch>' --jq .license.spdx_id` after the push | `MIT`. If the API does not honour `ref` on this endpoint, reported NOT RUN until D-504's batch reaches `main` (D-514) |
| D-V1 | P-41 11.7: `grep -c 'ONFLY has not run on IBM Z hardware' README.md docs/overview.md docs/ONFLY-SRS.md` | at least 1 in each |
| D-V2 | P-41 11.13 on every file this session adds and on the SRS's added lines | `em dashes: 0` for both |
| D-V3 | The sentence-to-CAN table in slice D's implementation doc | every factual sentence mapped; any sentence without a CAN entry is removed, not added to the register silently |
| B-V1 | `python tools/lint_name.py --tree` | `tree clean` |
| T-V1 | `mingw32-make fixtures && mingw32-make test`, last turn | exit 0 on SOFT3E, SOFT2C and NATIVE |

**Not measurable in this session, and reported as such:** the W1a outside
read that slice D's exit names (it needs a reader other than the owner and
the engineer); P-41 11.1 and 11.2, which need `ONFLY_NAME_B64` and it is not
set in this environment, so B-V1's committed digest stands in for them; and
C-V6 if the API reads only the default branch.

## 7. What this plan will NOT prove or change

1. No science, fingerprint or verdict changes. C7 and D6 edit comments only,
   and T-V1 plus C-V5 show it.
2. No legal position on FlyWire-derived material (D-515) or the name (D-528).
   The notices are not legal advice and say so.
3. Nothing runs on s390x, MVS or z/OS. Rows 4 to 8 are not re-run; `onfprim.c`
   and `onfrpk.c` are SOFT3E sources, which MVS does not build.
4. Nothing reaches `main` (D-514), so GitHub's default-branch licence badge
   and README rendering stay as they are until the batch.
5. Slices E to J are untouched: no networks distributed, no CI, no release.

## 8. Open questions this plan does not settle

None beyond approval. Items 8 and 9 stay open by D-515 and D-528.
