# ONFLY open-source launch and outreach, before Phase F

**APPROVED as drafted on 2026-09-24 (D-488) and published in full at the
owner's choice (D-489). Slice A COMPLETE 2026-09-25 (D-494). Slice B
COMPLETE 2026-09-25 (D-500 to D-512).** This file is
the proposal P-41 records; Appendix A.2 carries it, struck as approved. Until
the renumbering of 2026-09-24 it called itself P-40; that number went to
D-480's proposal, so the pushed commits f2e4b2f, 4b1de9f, f8d2a05 and 11c074d
say "P-40" in their subjects and mean this plan. Approval does not start any
slice early: each open decision in Section 10 is still put to the owner and
recorded as a D-row.

| Field | Value |
|---|---|
| Date | 2026-09-24 |
| Status | APPROVED 2026-09-24 (D-488); slice A COMPLETE 2026-09-25 (D-494); slice B COMPLETE 2026-09-25 (D-500 to D-512); slices C and D are next |
| Proposal | P-41, confirmed at slice A3 on 2026-09-25 (D-494); P-40 until the renumbering of 2026-09-24 |
| Scope | Launching the already public repository github.com/mertefesensoy/ONFLY so that other people can find it, understand it truthfully and replicate what it claims, **before** Phase F. Not a phase: no phase opens or closes here. Phases A to E and G stay COMPLETE; Phase F stays blocked on IBM Z access the project does not have; Phase H stays blocked on TBD-13 |
| Authorising owner answers | recorded as D-484 to D-493: OA-1 (scrub forward only), OA-2 (rewrite the IBM summary as a public overview), OA-3 (neutral term plus a decision row), OA-4 (all four audiences, sequenced by this plan), OA-5 (plan approved), OA-6 (published in full), OA-7 (commit and push the working branch), OA-8 and OA-9 (the two no-access confirmations of 3.2), OA-10 (Wave -1 scope for the IBM Community post); see 0.1 |
| Standing decisions it obeys | D-126 (phase order A, B, C, D, E, G, F, H: the IBM Z access request is made with Phase G in hand), D-132 (no INTERCOMM-derived material enters the repository), D-50 (MaleCNS is CC BY 4.0 and needs attribution wherever it or its derivatives appear), D-62 (the repository is MIT), D-478 (every commit has one author, the owner, with no co-author or tool-attribution trailer) and D-479 (no new text names the program; OA-3's neutral wording applied to new text), both on `main` since 2026-09-24 |
| Inputs | Six read-only audits of 2026-09-24 (exposure, licensing, replication, hygiene, claims, outreach), a completeness critic, and four critics of the draft. None of them ran a build or a test |
| Platforms | None measured. Every command in Section 11 is a check to run when the work is done; items marked "to be written" do not exist yet |

**What approving P-41 approves.** The plan in principle, and these
build-system changes, each of which still lands only with its slice's owner
check: a `requirements.txt`; a Linux x86-64 `ONFPLAT` value and a branch in
`engine/include/onfplat.h`; Makefile targets `namelint`, `test-nonet` and
`quick` (and `evidence` if item 6 is (c)); removal of the `| tail -1` masking
and of the fixed closing echo of `test`; `tools/lint_name.py` and two git
hooks; `.md` and `.json` in `tools/lint_lic.py`'s scan; a download source,
`--from` and a required-set rule in `tools/fixtures.py`; a field in
`data/networks/MANIFEST.json`, amended with `prep/netman.py`; a `.github/`
directory with CI. The owner may instead approve slice by slice.

## 0.1 The owner answers this plan rests on

Given on 2026-09-24 through AskUserQuestion and recorded here as OA-1 to OA-10
("owner answer"). They were numbered O-1 to O-10 until the renumbering of
2026-09-24, and commits f2e4b2f to f2fa6cb, the status snapshot of that day and
the website repository's post record cite them that way. They were renamed
because SRS Section 8.2 already uses O-1 to O-5 for the oracles. At slice A3, on
2026-09-25, they became D-484 to D-493 in the order below (OA-1 is D-484 and
OA-10 is D-493), and P-41 entered Appendix A.2 struck as approved by D-488
(D-494). Where D-479 already records part of an answer (OA-1's forward-only
scrub and OA-3's wording for new text), D-484 and D-486 cite it rather than
repeat it.

| ID | Question | Answer | Alternatives offered |
|---|---|---|---|
| OA-1 (D-484) | Git history that names the hosted IBM Z access program | **Scrub forward only.** Replace the name in current files and add a guard so it cannot return. History is not rewritten | A fresh public repository with the old one private; a filter-repo rewrite and force-push |
| OA-2 (D-485) | `ONFLY-IBM-Summary.md` and `.docx` | **Rewrite as a public overview** with no access request and no program name | Remove it and keep it private; keep it and scrub the name |
| OA-3 (D-486) | SRS rows that name the program | **Neutral term plus a decision.** Replace the name in place with wording such as "a hosted IBM Z environment", and record the wording policy as a new D-row that does not name the program | Visible redaction marks; free rewrite of the rows |
| OA-4 (D-487) | Audiences | **All four, sequenced by this plan:** neuroscience and connectomics researchers; mainframe hobbyists (Hercules, TK5); the IBM Z and open mainframe community; general developers | Not recorded |
| OA-5 (D-488) | Approve this plan (then numbered P-40, now P-41)? | **Approve** as drafted | Change; discuss first |
| OA-6 (D-489) | Where the plan lives, given that it describes surfaces outside the repository and the scrub | **All public in `docs/plan`**, following the project's convention | Full plan private in the gitignored `local/` with a short public version (the engineer's recommendation); all private until slice B lands |
| OA-7 (D-490) | Git in the drafting session | **Commit, and push the working branch** `claude/project-status-cee560`; `main` is not touched and `docs/ONFLY-SRS.md` is not edited while the parallel session holds it | Commit locally without pushing (the engineer's recommendation); no git changes |
| OA-8 (D-491) | Plan 3.2 confirmation (1): has any ONFLY code, JCL, COBOL, data or prototype ever been built, uploaded or run on an IBM Z system, under any account held now or before? | **No.** The only mainframe environment ONFLY has run on is MVS 3.8j emulated by Hercules on the owner's laptop, which comes before any IBM Z system and involves no IBM Z account | Asked as a yes or no confirmation |
| OA-9 (D-492) | Plan 3.2 confirmation (2): an active IBM Z account of any kind today? | **None.** The wording "the project does not have IBM Z access yet" stands | An account not usable for ONFLY; an account whose terms might allow project work |
| OA-10 (D-493) | Wave -1 scope for the live IBM Community post | **Two facts and the name only**, in one save: the acceptance-criteria paragraph (with a one-line dated correction) and the synapse count, both contradicted by the SRS (D-202, D-340, D-341; VL-13, D-56), and the program's name replaced silently. The title, SEO description, CICS paragraph, caption, bio, disclosure line and the discussion thread stay as they are; for 7.1 rule 6 they count as accepted by the owner. The exact edits are kept in the owner's private notes. **Applied by the owner on 2026-09-24 and verified live the same day** by an anonymous fetch: all four edits present word for word, the name absent, no moderation hold | The full rewrite drafted first; the two facts only; leave the post unchanged |

Two owner constraints are absolute. First, the name of the hosted IBM Z
access program does not appear in any public documentation from now on, in
any casing, spacing, compound or encoded form; this plan says "the hosted IBM
Z access program" and "the IBM Z access request". Second, public documents
say bluntly that the project does not have IBM Z access yet (3.2).

---

## 1. Problem / motivation

The repository has been public since 2026-09-10 and has not been launched from
the repository; an IBM Community blog post and discussion thread about ONFLY
(published 2026-09-16, public 2026-09-18) exist and are corrected in Wave -1
(7.2). The traffic API reports 2,181 clones by 591 unique cloners between
2026-09-10 and 2026-09-23, most likely automated, and 1 unique visitor to the
web page. It has 0 stars, 0 forks and 0 watchers. A visitor today sees:

* **No README.** GitHub shows the LICENSE text instead, and the About box is
  empty.
* **An IBM pitch as the only introduction.** `ONFLY-IBM-Summary.md` names the
  hosted IBM Z access program, holds a draft access request next to the
  owner's IBM community titles, says evidence is "to be added" (Phases E and
  G closed on D-348 and D-442), and says the curve must match "within ±25%"
  under criteria "fixed in advance". Neither is true any longer.
* **No statement that ONFLY has not run on IBM Z.** VL-01, VL-04 and VL-82
  state the emulation limits deep in Appendix D, but no record says ONFLY has
  never run on IBM Z hardware, while public phrases call the Hercules lab "a
  mainframe".
* **A licence GitHub cannot detect** (NOASSERTION).
* **Nothing a stranger can run end to end:** `make test` is red on `main`,
  the networks are gitignored, and the Makefile builds only with 32-bit
  MinGW on Windows or on s390x.

Why launch **before** Phase F:

1. **Replication by others is the strongest evidence available.** Every
   result so far comes from one person on one laptop. Nineteen fingerprints
   matched on a stranger's machine are worth more than another owner run.
2. **It strengthens the IBM Z access request.** D-126 already says publicly
   that the request is made with Phase G in hand; outside replications,
   issues and upstream bug reports make it a better request.
3. **Phase F must not be the first time anyone else sees the work.** The
   first z/OS row should land on code outsiders have already built and
   questioned.

Why now: with no forks, a rename, a licence restructure or a file removal
costs nothing today and more with every fork.

---

## 2. What the audit found

Stated as findings. Counts are at `main` (4a25639) unless marked.

### 2.1 Launch blockers

| Group | Finding | Evidence |
|---|---|---|
| Name exposure | **23 occurrences in 8 tracked Markdown files**, 15 in `docs/ONFLY-SRS.md` (D-01, D-23, D-296, D-437, D-442, D-444, D-458, P-34, C-07, TBD-13, 1.1, 2.3, 9.2 row F) | exposure NAME-01, replication X7, licensing LIC-01 |
| Name exposure | **9 more inside the two tracked `.docx` files** (summary 2, SRS 7), invisible to `git grep` because they are zip archives. Re-counted for this plan with the 11.1 scan: 32 at 4a25639, 33 on the parallel branch's tip f0ec691, and 32 there again at 00a73fb once D-479 neutralised D-468's occurrence, and 32 at 9ad60e9, `main` on 2026-09-25 | exposure NAME-02 |
| Name exposure | **Beyond a forward scrub's reach:** two commit messages and every tree on `main`, the PR refs, the parallel session's branch pushed today, a force-pushed branch whose old commits GitHub still serves by SHA, cloned copies and likely archives. Exact references are in the owner's private notes | exposure HIST-01, critic GAP-1, GAP-2 |
| Outreach already live | The IBM Community post and thread predate the register: the post says acceptance criteria were fixed before measurement (contradicted by D-202, D-340, D-341), its title and search description call the emulated lab a mainframe without qualification, its CICS sentence is stale since D-442, its synapse count lacks VL-13's scope, and it carries no disclosure line. The full list is in private notes | outreach critic; post record |
| First impression | No root README; the root summary is stale, partly false and addressed to IBM | hygiene F-01, F-02; claims F-01 |
| Truthfulness | No public no-access statement; "a real mainframe", "a running mainframe" and "submits it to a mainframe" in code comments, "on a mainframe" (D-255, VL-50) and the tagline "served as a CICS transaction" (SRS:3) read as hardware or CICS claims | exposure CLAIM-01; claims F-02, F-06 |
| Replicability | `make test` cannot pass: `tests/run_mvsjcc.py:303-312` requires `data/phase-e/jcc/rsp-path-2c.bin`, lost with JOB 398 (D-467); the handover records `tests/run_mvsjcc.py` at 43 passed, 1 failed (handover:38). *Resolved 2026-09-24: VL-138 supplied the recording, and green `make test` runs are recorded (D-497)* | replication X1, critic GAP-15 |
| Replicability | Networks gitignored (`.gitignore:29`): `srext` 171,768 B, `path` 951,200 B; `tools/fixtures.py:129-156` searches only `$ONFLY_FIXTURES` and the owner's checkouts | replication X2, hygiene F-06 |

### 2.2 High findings

| Group | Finding | Evidence |
|---|---|---|
| Licence | NOASSERTION, because LICENSE:23-41 appends third-party terms to the MIT text | licensing LIC-02 |
| Licence | The appended notice names 2 of 4 MaleCNS parties, calls the SoftFloat 2c derivatives BSD, and omits SoftFloat 2c (use restriction, indemnity), the Shiu et al. code, JCC (proprietary) and FlyWire | licensing LIC-03, LIC-07; claims F-11 |
| Licence | FlyWire data is CC BY-NC 4.0 (re-verify). The FlyWire-derived reference curve sits in `reference/shiu/results/` and is embedded in 12 `data/calibration/*.json` files and one implementation doc; W_syn 0.2969 was fitted to it and multiplies every edge weight of every network | licensing LIC-04; `git grep` on the curve's values |
| Licence | No trademark or non-affiliation statement; `tools/lint_lic.py` does not scan `.md` or `.json`; tracked `tools/mvsicom.py` generates JCL naming INTERCOMM datasets, against D-132's wording | licensing LIC-09, LIC-11 |
| Surface | `docs/ONFLY-SRS.docx` is the 2026-09-10 baseline export | claims F-05 |
| Replicability | No non-MinGW x86-64 build, no dependency manifest (numpy and pandas are hard requirements), no CI; the science re-measurement chain is undocumented and overwrites tracked manifests; the TK5 lab has no archive digests and ACC-6 certification is Windows-only | replication X3, X4, X5, R2, R4 |
| Community | Health 14%: no CONTRIBUTING, CODE_OF_CONDUCT, SECURITY, CITATION.cff, CHANGELOG or `.github/`; private vulnerability reporting off; no tags or releases | hygiene F-05, F-07 |
| Process | A parallel session writes to the SRS today; its D-478 bears on AI-use disclosure | critic GAP-1, GAP-3 |
| Outside the repo | Surfaces the owner controls, and a scheduled task that writes ONFLY posts, can reintroduce text the register forbids | critic GAP-4 |
| Ordering | A DOI, tag, release archive or archive save would permanently capture an unscrubbed tree | critic GAP-5 |

### 2.3 Medium and low findings that shape the plan

Two acceptance criteria were amended after measurement (D-202,
D-340/D-341; claims F-07). `data/calibration/acc4.json` still records
`"pass": false` while the SRS reports ACC-4 PASS by re-evaluation (F-08). The
SRS gives the ACC-3 40 Hz margin as 0.56 Hz; the acceptance record says
0.85 Hz (F-09). Four Makefile checks cannot fail because of `| tail -1`
(lines 495, 508, 540, 583; two are in `test`; replication X6). The owner's
absolute paths are in 7 tracked data files, and one silently disables the
`--admit` self-check elsewhere (X3, X8). The lab's reader, console and 3270
ports are unauthenticated and their bind address is not in the repository;
TK5's default TSO login is hard-coded in the decks (GAP-6, CRED-01). The name
ONFLY collides with a software company (LIC-17, re-verify). The hero GIFs
autoplay without a pause control and their annotation contrast is 3.4:1
(GAP-14).

Confirmed fine: no raw MaleCNS or FlyWire data, no INTERCOMM-derived code and
no Raincode, JCC or IBM binaries were ever committed; no secret-shaped content
exists on any ref; no code parses the SRS, so a wording scrub breaks no test.

**What forward scrubbing can and cannot do.** OA-1 controls what a visitor
finds in the current tree from the day the scrub lands. It cannot un-publish
commit messages, earlier trees, PR refs, today's branch, commits served by
SHA, cloned copies or archives. The plan never claims the name is "gone",
only that current public documents do not use it.

---

## 3. Principles

### 3.1 The honesty register

Every public sentence about what ONFLY does or has shown comes from the
claims register (Section 5), and every entry cites the VL or D row that
evidences it. A claim not in the register is not made: not in README,
overview, release notes, posts, replies, talks or papers. When a result
changes, the register changes first.

### 3.2 The blunt no-access statement

It is about the **project**, not the person, and it states the project's
history, not that IBM Z hardware is unobtainable. Long form:

> **ONFLY has not run on IBM Z hardware. The project does not have IBM Z
> access yet.** Every MVS result in this repository comes from MVS 3.8j
> running under the Hercules emulator, and every s390x result from Linux
> running under QEMU, both on one x86-64 laptop. Nothing here has run on
> z/OS or on IBM CICS Transaction Server.

Short form: "No IBM Z hardware used: the project does not have IBM Z access
yet. MVS and s390x results are emulated (Hercules, QEMU)."

| Where | Form |
|---|---|
| README, first screen, under the one-paragraph description and above any build step | Long form, quoted |
| GitHub repository description | Short form, at the end |
| SRS 1.1, replacing the parenthetical that names the program | First sentence of the long form, citing the standing VL row of item 32 and SRS 8.3 row 8 being empty |
| SRS 2.3 platform matrix and 9.2 row F | "not available to this project yet" |
| `docs/overview.md` (OA-2) | Long form, first section |
| Release notes and outreach posts | Short or long form |

It is reviewed, and changed only by a D-row, whenever anything adds a
platform (a CI runner, a hosted VM, Phase F). Before first publication the
owner confirms two things, and a D-row records them without naming any
program. (1) No ONFLY code, JCL, COBOL, data or prototype was ever built or
run on any IBM Z system under any account the owner holds or has held,
including training and certification accounts. (2) Whether the owner has any
active IBM Z account today, and whether its terms allow project work. If (2)
is yes, the second sentence becomes "No IBM Z system is available for ONFLY's
work yet." Only if (1) is confirmed, public FAQ copy may add: "The maintainer
has used IBM Z learning systems for coursework; ONFLY was never built or run
on them."

**Both confirmations were given on 2026-09-24 (OA-8, OA-9).** (1) ONFLY has
never touched an IBM Z system under any account: the only mainframe
environment it has run on is MVS 3.8j emulated by Hercules on the owner's
laptop, which is not IBM Z hardware and involves no IBM Z account. (2) The
owner has no active IBM Z account today. The long and short forms above
therefore stand unchanged, and CAN-03 is usable.

### 3.3 Vocabulary

Historical records are not rewritten for vocabulary; the name scrub is the
one exception (OA-3). If item 18 is (a), SRS Appendix F gains three entries:

* **mainframe (in this repository's records):** the emulated System/370
  running MVS 3.8j under Hercules on an x86-64 laptop (the TK5 lab). It never
  means IBM Z hardware.
* **real 3270, real EXEC CICS:** the real TN3270 protocol against Hercules'
  emulated terminal, and source written against the real EXEC CICS API.
  Neither implies IBM hardware or IBM CICS.
* **hosted IBM Z environment:** IBM Z hardware reached over the network
  through an IBM access program. ONFLY has not used one.

New public copy never uses "mainframe" unqualified; it says "MVS 3.8j
emulated by Hercules on a laptop" or "the emulated MVS lab".

### 3.4 One maintainer, irreversible steps last, writing rules

ONFLY has one maintainer, and every channel opened is one the owner answers.
The last public post of a wave is at least 14 days before the first public
post of the next.

Steps are ordered by how hard they are to undo. Wording, licence files and
documentation come first. A tag, a release, a Zenodo DOI, an archive save, a
force-push ruleset, branch deletion and public posts come last, each gated on
the Section 11 scans passing on the exact tree or text being captured. Every
push to the public repository is made or approved by the owner, at the
cadence item 30 sets; because the repository is public, a push is a
publication.

New public files: no em dashes; plain, measured, specific prose in the
register of `docs/implementations/2026-09-18-phase-g-closure.md`; no IBM or
program logos or badges; one author spelling (item 23). Existing evidence
records are not swept for style.

### 3.5 Where the owner should get advice before an irreversible step

This plan records options and recommendations; it is not legal advice. On
these six questions it recommends qualified input, or for (4) a written answer
from the programme, before slice G. Where to ask is the owner's choice.

1. The status of FlyWire-derived material and of W_syn in the networks (item 8).
2. The SoftFloat 2c indemnity the owner carries as distributor of derivative
   files (C4).
3. Copyright ownership and affiliation (item 29).
4. The IBM programme terms on content licence, branding and disclosure, by a
   written question to the programme managers (item 34).
5. The ONFLY name against the Onfly company, before the DOI (item 9).
6. Whether `tools/mvsicom.py`'s generated JCL is INTERCOMM-derived (item 35).

---

## 4. Workstreams, as ordered slices

A slice starts only when the previous slice's exit holds, except where marked
parallel. Each slice that changes the repository ends with an implementation
doc under `docs/implementations/`. The order below assumes item 5 is (b),
release assets; if the owner takes (a), E and F lose their staged-asset
steps and G5 becomes a plain clean-clone check.

| Slice | What | Reversible | Depends on |
|---|---|---|---|
| A | Coordinate with the parallel session, wait for its merge, number OA-1 to OA-10 | yes | nothing |
| B | Name scrub, D-rows, guard | mostly (the D-rows are public record) | A |
| C | Licence and notices | yes | B |
| D | Truthful public surface | yes | B (parallel with C) |
| E | Replicability, with locally staged network assets | yes | A (row 7 outcome), C, items 5 and 11 closed |
| F | Community infrastructure, network-free CI, settings | yes, except the ruleset | C, D, E |
| H0 | Write-up, FAQ, media kit (owner-written) | yes | D; runs during E and F |
| W1a | Trusted testers on a release-candidate branch | yes | E, F, H0 |
| G | Release: version, tag, assets, Zenodo; then the public download check, branch retirement, archive save | **no** | B to F verified, W1a corrections merged, G entry items closed |
| H | Outreach waves W1b onwards | **no** | G |
| I | Academic track | **no** | W3 settled |
| J | Phase F access request, prepared privately | not public | G, H under way |

Wave -1 (correcting live copy outside the repository) is not a slice: it is
an owner action that starts on approval of this plan and is not gated on A
to G (7.2).

### Slice A: coordinate with the parallel session (COMPLETE 2026-09-25, D-494)

The session on `claude/onfly-senior-engineer-ac25b2` recorded D-468 to D-483,
P-39 and P-40. It re-ran the row 7 `path` job (D-471; JOB 400 was lost,
D-477) and filled the row with JOB 402 (VL-138), and it closed
with D-481 to D-483 at 9ad60e9. Its tip was 0d6fd6f at briefing,
f0ec691 when this was drafted and 00a73fb at the status check of 2026-09-24.
Its D-468 introduced the program name; D-479 neutralised that occurrence in a
forward commit and adopted the neutral wording for all new text.

| Step | Work |
|---|---|
| A1 | The owner tells that session, through the owner's own channel, that new text must not use the program's name. **Done 2026-09-24: D-479 records it on that branch** |
| A2 | No commit here touches `docs/ONFLY-SRS.md` until that branch has merged; this plan stays in `docs/plan/`. **Held until the merge of 2026-09-25** |
| A3 | After the merge, rebase; P-41 is confirmed, or renumbered if the merge took it; OA-1 to OA-10 each become a D-row with the next free numbers (the wording policy per item 42), citing D-479 where it already records part of an answer; slice B's occurrence list is rebuilt by scan, not from the audits' line numbers. **Done 2026-09-25 (D-494)** by the merge commit 7cb7389 rather than a rebase (D-498): P-41 confirmed, OA-1 to OA-10 recorded as D-484 to D-493, the item 42 policy row left to B3 (D-495) |

**Exit:** three things. The owner confirms the parallel session is closed;
the branch has no commit `main` lacks; D-480, the branch's last row at
00a73fb, is on `main` (if the branch adds rows before merging, check its last
row instead). The private memory files scan clean (11.14). On a hand-off instead of a merge, B4's hooks are
not installed until that session has stopped. **Verify:**

    git fetch origin && git rev-list --count origin/main..origin/claude/onfly-senior-engineer-ac25b2
    git cherry origin/main origin/claude/onfly-senior-engineer-ac25b2 | grep -c '^+'
    git show origin/main:docs/ONFLY-SRS.md | grep -c '^| D-480 '

Expected: `0`, `0` (use the second if the branch was rebased), `1`.

**Met 2026-09-25 (D-494).** The owner reported the parallel session's work
done, and it was idle. At 9ad60e9 the three commands gave `0`, `0` and `1`,
and the memory files scanned 0 (11.14). The session's hooks were never
installed, so B4 is unconstrained.

### Slice B: name scrub, decision rows and guard (COMPLETE 2026-09-25, D-500 to D-512)

| Step | Work |
|---|---|
| B1 | Every occurrence 11.1 reports is replaced in place. Where the sentence states a property of that one program (C-07, D-23, the SRS 2.3 row, TBD-13, D-01), the name becomes "the hosted IBM Z environment the project plans to request". "A hosted IBM Z environment" is used only where the sentence is generic, and "the IBM Z access request" where it is about the request. Includes the frozen snapshot `docs/status/2026-09-16-status.md`; D-468 no longer needs it, because D-479 neutralised its occurrence |
| B2 | `git rm ONFLY-IBM-Summary.md ONFLY-IBM-Summary.docx`: the old text is stale and partly false, so it is not edited (OA-2); slice D writes the overview new. `docs/ONFLY-SRS.docx` per item 14. Zips are checked with 11.1, never with `git grep`. The root has no introduction between B and D, and nothing is announced in that window |
| B3 | The wording-policy D-row, worded as below, as its own row (D-495); the slice's implementation doc uses the same wording; the old-to-new map is kept in private notes only |
| B4 | The guard (below) |
| B5 | A record, not work: the planning session of 2026-09-24 that drafted this plan replaced the name in the two private memory files that used it and recorded the naming rule there, so later sessions stop reintroducing it. 11.14 re-checks them |
| B6 | Pushed at once if item 30 is (c), to end name exposure in the current tree |

Proposed D-row text:

> **Public wording policy: rows that named a specific hosted IBM Z access
> program now say "the hosted IBM Z environment the project plans to
> request", "a hosted IBM Z environment" where the sentence is generic, or
> "the IBM Z access request", edited in place.** The substitute keeps the
> definite reference, so no row's claim widens from one program to hosted IBM
> Z environments in general. No decision's substance, date, alternatives or
> rationale changes. This is a redaction rule, separate from the
> strike-through supersession of D-134 and D-136: replaced words are not kept
> as struck text. Public documents do not name the program.

**The guard**, a committed `tools/lint_name.py` (to be written; name to be
confirmed) in the style of the existing lints:

* **Normalise:** NFKC, then casefold, then unescape HTML entities and `%XX`,
  then drop every character outside `[a-z0-9]`, keeping a map back to raw
  offsets so a hit can be reported by line.
* **Match without storing the word:** slide a window of the token's length
  over the normalised text and compare each window's salted SHA-256 with one
  stored digest (item 31). A hash of one known word is reversible by brute
  force; this keeps the word out of the text, not secret.
* **Allowlist:** a short list of ordinary words that contain the token is
  kept, like the token itself, only as salted digests in the guard, and a
  match inside an allowlisted word passes. The self-test covers both cases.
* **Office files:** every member of a `.docx`, `.xlsx` or `.pptx` zip,
  whatever its extension (the `.rels` files hold hyperlink targets), with
  Word text extracted per paragraph and table cell.
* **Where:** a `pre-commit` hook scans only added lines (`git diff --cached
  -U0`) plus the index blob of any staged Office file (`git show :<path>`), so
  branches based on pre-scrub `main` are not blocked by old text; a
  `commit-msg` hook scans the message; both live in the common git directory
  (`git rev-parse --git-common-dir`) so all worktrees share them. A
  `namelint` target joins `test` beside `liclint`. CI (slice F) scans the
  whole tree, Office files and the pushed range's messages.
* **Output:** path, line and count only, never the matched text, because CI
  logs are public.
* **Broader list, private:** a further private list lives in an untracked
  local hook that reads it from an environment variable and fails closed when
  the variable is unset.
* **Self-test:** must catch the token after "the", in upper case, prefixed
  with "Z", and split by a no-break space, a zero-width space, a soft hyphen,
  a line break, Markdown emphasis or an HTML entity; must pass each
  allowlisted word and its capitalised form.
* **Not covered:** GitHub issue, PR, Discussion and release text; the
  repository description; tag messages (except through 11.3 and 11.4);
  commits made in the web UI; messages carried over by cherry-pick or rebase,
  where `commit-msg` does not fire; images.

**Exit:** 11.1 and 11.2 report 0; the self-test and the hook checks of 11.10
pass; the D-rows and implementation doc exist. **Verify:** 11.1, 11.2, 11.3,
11.10, and `python tools/lint_name.py --self-test`.

**Met 2026-09-25 (D-500 to D-512), by the plan of record P-42 (D-506).** All 21
Markdown occurrences were reworded in place (D-512); `ONFLY-IBM-Summary.md`
and its `.docx` were removed (D-485); `docs/ONFLY-SRS.docx` was regenerated
from the scrubbed SRS (D-502, D-508). The guard is `tools/lint_name.py` with
the `namelint` target (D-507), holding the token and six allowlisted words
as salted digests only (D-503); its self-test runs on a synthetic token and
needs no secret (D-506). Measured on x86-64 Windows: the self-test at `40
checks, 0 failed` without the token and `84 checks, 0 failed` with it;
`--tree` at `tree clean`; in a throwaway worktree at 2529abf, a staged sample
and a message carrying the token both refused and a clean commit accepted;
`core.hooksPath` unset. 11.1 on the staged tree, 11.2, 11.3 on the commit
message and 11.13 are in `docs/implementations/2026-09-25-open-source-launch-slice-b.md`.
Two amendments to this section, both by owner answer: `--tree` SKIPs where
git cannot read the tree (D-510), and the broader private list is a
mechanism the owner installs (D-509).

### Slice C: licence and notices (parallel with D)

| Step | Work |
|---|---|
| C1 | `LICENSE` keeps only the MIT text (LICENSE:1-21). No pointer line is ever added inside LICENSE, which would break detection again |
| C2 | New root `THIRD_PARTY_NOTICES.md`, one entry per LIC-00 component (name, version, upstream, path, SPDX ID or LicenseRef, committed or fetched or tool only, required notice). It opens, as does the README licence section: "The MIT licence in LICENSE covers ONFLY's own files. The paths listed in THIRD_PARTY_NOTICES.md are under their own terms, which govern those files, including SoftFloat 2c (not BSD; use restriction and indemnity), MaleCNS-derived data (CC BY 4.0) and the FlyWire-derived material (item 8)." It also says: "ONFLY's own files in every earlier commit of this repository are also available under the MIT licence. Earlier versions of LICENSE described the files under softfloat/c2c as BSD; that was wrong, and those files have always been under the SoftFloat 2c terms." |
| C3 | SoftFloat 3e and TestFloat 3e (BSD-3-Clause), naming the BSD-derived files under `softfloat/` (`onfrpk.c`, `onfprim.c`, `onfsub.c`), the TestFloat-generated vectors in `generated/onftfv.h`, and the files that are ONFLY's own MIT code |
| C4 | **SoftFloat 2c**, legal notice reproduced verbatim, stating that every SOFT2C build (every MVS build, and the SOFT2C third of the x86 `make test` that R1 runs) includes SoftFloat 2c and inherits its use restriction and indemnity, and that `softfloat/c2c/*` follows these terms. The README licence section carries a two-sentence summary, because the terms bind whoever builds. No ONFLY release ships a SOFT2C binary |
| C5 | The Shiu et al. code in `reference/shiu/` (MIT, other holders). **MaleCNS v1.0** with all four parties (HHMI Janelia, MRC Laboratory of Molecular Biology, University of Cambridge, Google Research), CC BY 4.0 link, citation and a note of modification. **FlyWire** snapshot 630: not redistributed, non-commercial terms (re-verify), citations as FlyWire's citation guide requires, re-verified at time of writing (at least Dorkenwald et al. 2024 and Schlegel et al. 2024). A new `reference/shiu/results/NOTICE.md` (a new file, so no digested file changes; confirm no test enumerates that directory) and a one-line non-commercial note in the `reference/shiu/rerun.py` docstring. The status of all FlyWire-derived material per item 8. `docs/malecns-celltype-mapping.json` is MaleCNS data, not FlyWire material: its `flywireType` labels are read from the MaleCNS annotations (`prep/celltypes.py:88`) |
| C6 | Build tools and lab software, none included, each tool's licence stated as published upstream with the date checked. JCC is proprietary (Jason Paul Winter); its terms allow free software to be compiled without payment, business use may need a paid JCC licence, and ONFLY grants no right to JCC (re-verify terms). JCC-generated assembly is committed only with the source it came from. Raincode needs registration, and terminal CICS needs a Raincode licence. INTERCOMM is under Tetragon LLC terms with a non-commercial clause and is not included (D-132). Also Hercules, TK5, GCCMVS, PDPCLIB, GnuCOBOL, QEMU, wc3270, .NET, brian2, Python packages. The notices do not assert that MVS 3.8j is public domain |
| C7 | `onfrpk.c` and `onfprim.c` carry the full BSD conditions and disclaimer; `softfloat/derive3e.py` emits them for the generated file. Source bytes change; object files and fingerprints do not |
| C8 | `data/README.md`: MaleCNS attribution for committed derived data and media; the licence of ONFLY's own part (item 20); `data/calibration/` per item 8, not assumed CC BY; the network notice of E3 |
| C9 | Trademark and non-affiliation text (below), in README and the notices. The IBM mark list is rebuilt at C time by scanning the new public files for IBM marks actually used (for example LinuxONE, Enterprise COBOL, TSO, JES2), and re-verified against IBM's trademark page on the day |
| C10 | `REUSE.toml` path annotations for `reference/shiu/results/**`, `data/**`, `docs/malecns-*` and `docs/media/**`, so no byte-exact or digested file is edited; a `LICENSES/` directory is optional |
| C11 | `tools/lint_lic.py`'s `SOURCE_SUFFIXES` gains `.md` and `.json` outside the exempt paths, so every new public file is under the D-132 guard |
| C12 | D-rows: NFR-LIC-01 (SRS:460) amended to name `THIRD_PARTY_NOTICES.md` as the single register, cover every LIC-00 component and drop the unverified GCCMVS sentence; FlyWire added to SRS Appendix G; C-08 per item 21 |

> ONFLY is a personal project by `<owner name, item 23>`. It is not an IBM
> product and is not affiliated with, sponsored by or endorsed by IBM, or by
> any organisation or person whose data, software or tools it uses, including
> HHMI Janelia, the MRC Laboratory of Molecular Biology, the University of
> Cambridge, Google Research, the FlyWire consortium, Raincode and the authors
> of Shiu et al. (2024). `<If item 10 allows it: The author's participation in
> IBM community programmes does not make ONFLY an IBM project; the views and
> results here are the author's own.>` IBM, IBM Z, z/OS, CICS, MVS and VTAM
> are trademarks or registered trademarks of International Business Machines
> Corporation, registered in many jurisdictions worldwide; a current list is
> at https://www.ibm.com/legal/copytrade. Linux is the registered trademark of
> Linus Torvalds in the U.S. and other countries. Other product and company
> names, including Raincode, QIX and INTERCOMM, may be trademarks of their
> owners and are used only to identify those products.

**Exit:** every LIC-00 component and every item 8 inventory path has an
entry; local checks pass; GitHub reports MIT after the push. **Verify:**
`mingw32-make col80 lint liclint golden`, `python softfloat/derive3e.py
--check`, identical `build/obj/*.o` hashes before and after C7, 11.12, and
11.5 after push.

### Slice D: a truthful public surface (parallel with C)

| Step | Work |
|---|---|
| D1 | Root `README.md`, in order: one-paragraph description (CAN-01); the no-access statement; a status table (phases with closing D-rows; matrix rows with counts; row 8 empty); what you can reproduce, three tiers, linking `REPLICATING.md`; tested platforms (x86-64 Windows MinGW32, Linux once E4 lands; macOS and arm64 untested, reports welcome through the replication template); the limits with CAN-15; a repository map; licence, notices and the SoftFloat 2c summary; INTERCOMM is under Tetragon LLC terms with a non-commercial clause, is not included, and the 3270 demonstration cannot be reproduced from a clone; trademarks; the item 9 line; how the project is built (item 4); how to cite. One small static poster image linking to the short GIF, with alt text and the attribution caption of 7.1 |
| D2 | `docs/overview.md` (OA-2), written new from Section 5, not by editing the old summary. No request, no program name, no IBM titles beside a request. `md2docx.js` per item 14 |
| D3 | The 3.3 glossary entries in SRS Appendix F, if item 18 is (a) |
| D4 | `docs/README.md`, a reading guide, so newcomers do not start with an 813 KB single page; short READMEs for `generated/` (committed on purpose: MVS has no Python) and `tools/` |
| D5 | SRS front matter, each by a D-row: version and date (SRS:8-9); reader classes at SRS:23 and :117, which name "IBM reviewers" and the one-page summary; the tagline (item 16); SRS 1.1, 2.3, C-07 and 9.2 row F per 3.2; the ACC-3 margin and `acc4.json` note (item 19) |
| D6 | Stale statements a replicator reads first: `data/phase-d/README.md` ("no MVS engine exists yet"), the `tests/run_gld.py` docstring, Makefile:289-291, the `tools/fixtures.py:295` message. And, defined by search rather than list, every occurrence of "mainframe" in tracked code and docstrings (`git grep -n -i mainframe -- '*.py' '*.c' '*.h' Makefile`) is qualified as the emulated MVS lab; known sites include Makefile:843 and :849, `tests/run_ic3270.py:4-5` and :19, and `tests/run_mvsjcc.py:5` (comments, not records) |

**Exit:** every factual sentence in README and overview maps to a CAN entry;
the no-access statement is everywhere 3.2 lists. **Verify:** 11.7, 11.13, and
a read of README against Section 5 by a W1a reader.

### Slice E: replicability

**Entry:** item 11 closed (the tag is in the download URL) and item 5 decided.

| Step | Work |
|---|---|
| E2 | First: remove the `\| tail -1` masking at Makefile:495, :508, :540 and :583 (write the output to a file, check the exit status, then print the last line). An unmasked failure becomes a finding recorded by a D-row, not a blocker hidden again; the implementation doc says what earlier greens did not cover |
| E1 | **A green `make test`.** The parallel row 7 run may supply `rsp-path-2c.bin`; if not, item 6. `main` is never launched red, and no badge is shown for anything CI does not run. The fixed closing echo of `test` (Makefile:787-788) becomes counts of PASS, SKIP and PENDING |
| E3 | **Networks.** `srext` (171,768 B, SHA-256 `bf09a3ad18a82b8ecc0dd2fd397d81e332f38c98a78325269f5c39d2b3b1f66d`) and `path` (951,200 B, SHA-256 `168627c833d7af0f33bd0ed8d2bd1fbb407fd3c4436e0f57558c772cbb8b28f9`) are the required set, marked `"distributed": true` in `data/networks/MANIFEST.json` (amended with `prep/netman.py`, never by re-running the generator). `tools/fixtures.py --check` exits 0 when the required set verifies and prints `NOT DISTRIBUTED (regenerate with prep/emit.py)` for `hop2` and `full`; a case in `tests/test_fixt.py` pins this. `fixtures.py` gains a documented download source and `--from <dir>` for locally staged assets; `--check` stays the only acceptance test. A `NETWORKS-NOTICE.md` (release asset, repeated verbatim in the release notes and in `data/README.md`, and printed by `fixtures.py` after download) states: (1) Contains data derived from MaleCNS v1.0 by HHMI Janelia, the MRC Laboratory of Molecular Biology, the University of Cambridge and Google Research, licensed under CC BY 4.0, https://creativecommons.org/licenses/by/4.0/; (2) the citation the dataset's licensor asks for, re-verified on its download page at release time; (3) dataset male-cns:v1.0, uuid 4b2087c0fbe046bfaf0d60bc970e3e5d, with a link; (4) Modified by ONFLY: neurons selected (`srext` 501, `path` 913), synapse counts aggregated per pair and signed, multiplied by a calibrated W_syn of 0.2969 mV, a compensating-input table added, encoded in ONFLY network format 1.1; (5) the item 8 sentence on W_syn; (6) No endorsement by the dataset's creators is implied; (7) the licence of ONFLY's contribution per item 20. The `.bin` format carries no text (IR-NET-02), so the notice travels beside the file |
| E4 | **Linux x86-64**, made only after the row 7 run has closed. A new branch in `engine/include/onfplat.h`, after the JCC branch, sets a real platform ID (not UNKNOWN, the D-291 failure class) and `ONF_FP_LITTLE`; a new `ONFPLAT` value reuses D-225's out-of-tree TestFloat build. `onfplat.h` is submitted to MVS as member ONFPLAT (`tools/mvseng.py:93` and five other tools) and rows 6 and 7 were recorded from its current bytes, so the evidence is fixed in advance: preprocessor output unchanged for existing targets (`gcc -E` with `-D__MVS__`, `-DJCC`, `-D__s390x__`, and on the x86w host) and x86w object files byte-identical before and after. A D-row records whether that suffices or rows 6 and 7 need a re-run. A `-Werror` failure on a newer gcc is handled per item 7. NATIVE uses `-msse2 -mfpmath=sse` (Makefile:70), so non-x86 hosts are untested |
| E5 | `requirements.txt`: core numpy 2.4.4, pandas 2.3.3, pyarrow 21.0.0 on Python 3.13 (the recorded versions); extras matplotlib and a GIF writer (live view), brian2 (Shiu re-run). `tests/test_seeds.py:60` imports numpy unconditionally, so a clean skip is new work. A strict mode (`ONFLY_NOSKIP=1`) turns D-233 skips into failures; CI uses it |
| E6 | `REPLICATING.md`: the Section 6 ladder, each rung with what it proves and does not; R2b carries FlyWire's non-commercial note |
| E7 | One documented network regeneration recipe ending in `python tools/fixtures.py --check` and restoring the tracked manifests; `--admit` fails loudly when its comparand is absent (replication X3) |
| E8 | Lab guide: TK5 archive digests; the 819/1047 codepage step; **bind the card reader (3505), console (8038) and 3270 (3270) ports to 127.0.0.1 or firewall them, and never run the lab on an untrusted network**, because the reader accepts any JCL from whoever connects; change the TK5 default HERC01 password on any lab reachable from another machine; the s390x guest bring-up script and cloud-init data committed without keys, after secret scanning is on (F7) |
| E9 | Two Makefile targets (to be written): `test-nonet` (the network-free checks, for example lint liclint col80 c04 c04mvs sub mvsrun mvsjcc ic3270 names tt01 tt02 c2c sfs shim layout units fp kernel syn prep, with its time measured and recorded) and `quick` (build the engine and check the committed fingerprints without the labs) |

**Exit:** a clean clone on Windows MinGW and on Linux x86-64 (the host is
named in the implementation doc: WSL2, a container or CI; if CI, F6's
workflow lands inside slice E) reaches R0, R1 and R2a with **locally staged** assets
(`fixtures.py --from`), in a fresh venv built only from `requirements.txt`,
with `ONFLY_FIXTURES` unset and `ONFLY_NOSKIP=1`. **Verify:** 11.8 and 11.9.

### Slice F: community infrastructure

| Step | Work |
|---|---|
| F1 | `CONTRIBUTING.md`: how the project is run (D-rows are owner decisions, P-rows proposals, VL-rows limits); an outside proposal enters as an issue labelled `proposal`, which the owner may record as a P-row and decide as a D-row; contributors never write D-rows; the bottom-up test rule; byte-exactness of `third_party/` and `generated/`; the implementation doc template; contribution terms (item 24) |
| F2 | `CODE_OF_CONDUCT.md` (Contributor Covenant 2.1, contact per item 25); `SECURITY.md` (scope: malformed network and request files, local lab tooling; GitHub private vulnerability reporting, switched on by the owner) |
| F3 | `SUPPORT.md`: one maintainer; tiers and response window per item 12; tested platforms as in D1 |
| F4 | Issue templates: `bug_report.yml` (platform, compiler and version, backend, ONFnnn messages, `make test` counts); `replication_report.yml` (OS, ABI, compiler and version, backend, network SHA-256, G-01 to G-19 fingerprints, SKIP count), the route by which a stranger's result becomes a candidate matrix entry; `config.yml` pointing to the one canonical inbox (item 12); a PR template |
| F5 | `CITATION.cff` (ONFLY, MaleCNS, Shiu et al. 2024, FlyWire; `license: MIT` with the C2 opening sentence in its abstract; affiliation per item 29), `CHANGELOG.md` seeded from the phase markers, `.mailmap` per item 36 |
| F6 | CI (to be written) with supply-chain controls: actions pinned to full commit SHAs; `permissions: contents: read`; `persist-credentials: false` on checkout; `push` and `pull_request`, never `pull_request_target`; no secrets; `timeout-minutes` and `concurrency` per job; pip installs from `==` pins, with hashes if feasible; `gcc -v`, `python -VV` and `pip freeze` logged; Dependabot for actions; a CODEOWNERS entry for `.github/`. Jobs that must exist and pass at launch: `name-guard` (whole tree and Office files, pushed-range messages with `fetch-depth: 0`, handling an all-zero `before` SHA, counts only); `python-bare` (Python checks on a bare checkout); `nonet-linux` (`test-nonet` on ubuntu-latest, `ONFLY_NOSKIP=1`); `nonet-windows` (windows-latest MSYS2 MINGW32, which matches `x86w`'s ONFPLAT value but not its recorded toolchain). `golden` (networks verified by `fixtures.py --check` before any test) lands in G5, when networks can be downloaded |
| F7 | Settings, all owner actions: description ending in the short statement; topics; Discussions per item 12; wiki and projects off; auto-delete head branches; social preview (if derived from MaleCNS imagery, the image itself carries "Data: MaleCNS v1.0, CC BY 4.0, modified"); default `GITHUB_TOKEN` read-only; Actions may not create or approve PRs; only GitHub-owned and listed actions allowed; approval required for workflows from outside contributors' forks; secret scanning and push protection on; a ruleset on `main` blocking force-push and deletion (OA-1 rules out a rewrite, so it blocks nothing needed; it goes on after slice B) |

**Exit:** the community profile lists every file; the four named jobs exist
and pass on `main`. **Verify:** 11.6 and 11.10 after push.

### Slice G: release (first irreversible step)

**Entry:** B to F verified; W1a done and its corrections merged; items 4, 5,
8, 9, 11, 14, 20, 22, 23 and 29 closed by D-rows; `git status --porcelain`
empty and `git rev-parse HEAD` the commit to be tagged; **11.1 to 11.4 pass
on that commit and on the tag message and release notes before they are
published.**

| Step | Work |
|---|---|
| G1 | Version per item 11. Release notes carry the Section 8.4 fingerprints, network SHA-256 values, matrix status with counts, the limits, CAN-15, the no-access statement and the NETWORKS-NOTICE text; scanned with 11.3 before `gh release create --notes-file` |
| G2 | **Zenodo integration enabled before the tag** (only later releases are archived; Zenodo behaviour, re-verify). A `.zenodo.json` with licence MIT and a description stating: ONFLY's own code is MIT; the archive also contains third-party components and data under their own terms, listed in THIRD_PARTY_NOTICES.md, including SoftFloat 2c (not BSD), BSD-3-Clause SoftFloat 3e and TestFloat 3e, CC BY 4.0 MaleCNS-derived data and FlyWire-derived material (item 8). The CFF `license` key stays a single MIT (a list means alternatives; re-verify). The owner checks the Zenodo record's licence and description before publishing. Re-verify whether Zenodo archives release assets; if it does, `NETWORKS-NOTICE.md` is among them |
| G3 | Annotated (optionally signed) tag, release, assets: `srext`, `path`, `SHA256SUMS`, `NETWORKS-NOTICE.md`; `hop2` and `full` only by owner decision |
| G4 | After the DOI is minted, a follow-up commit adds the concept DOI to README and `CITATION.cff` |
| G5 | Right after publication, a public-download clean clone: anonymous `curl -fsSLO` of each asset, `fixtures.py --check`, `make test`; the CI `golden` job lands |
| G6 | Session branches per item 15. Public pointer tags on pre-scrub commits are incompatible with 3.4 and are not created; pointer tags stay local, and remote branches are deleted without new public tags |
| G7 | Software Heritage save only if item 37 chooses it, after G6 |

**Exit:** release and assets verify anonymously; the DOI resolves; 11.4 on
the release body and Zenodo description reports 0. **Verify:** 11.4 and 11.11.

### Slice H: outreach

H0 (owner-written, during E and F): (1) **the write-up**, 1,500 to 2,500
words, every factual sentence mapped to a CAN id, reviewed by a W1a reader,
host per item 39; (2) **`docs/FAQ.md`**, built from the register and reused
as saved replies, answering at least: is this a brain upload or whole-brain
emulation; what running it on MVS tells us about the fly (nothing
biological); what the fitted input term is and whether the 10% agreement is
partly built in (D-205, VL-74); whether criteria changed after results
(CAN-15, VL-114); whether determinism is correctness (VL-05); why emulated,
and why not IBM's free s390x runners or community VMs (CAN-03, item 26);
whether it ran on z/OS or CICS (CAN-09, CAN-11); whether AI was used (item
4); that z/OS on Hercules is never involved; macOS and arm64; why COBOL and
C89; and the maintainer's IBM roles (7.1); (3) **a media kit**: a static
poster PNG; a 30 to 60 s MVS live-stream clip with "MVS 3.8j emulated by
Hercules on a laptop" burned into the frame; for neuro channels, the ACC-4
curve against the reference with error bars, showing both the shape
agreement and the magnitude gap. Every item has alt text and the 7.1
attribution line; the 3.4:1 contrast is fixed before any clip is reused.

Waves, rules and skeletons are in Section 7. Every web-sourced fact is
re-verified on the day it is used.

### Slice I: academic track

**Entry:** W3 has settled. Every venue, date and policy is re-verified at
submission; AI-use disclosure per item 4. Order: (1) a ReScience C article
(venue fit to be re-verified) reporting the re-run of Shiu et al.'s published
code (D-164) and the port of the model to MaleCNS, measured on x86-64 NATIVE
with VL-78's bit-exact agreement on SOFT3E and SOFT2C for the subcircuit, and
leading with the magnitude mismatch (CAN-08) and both amended criteria
(CAN-15); (2) JOSS on or after **2027-03-11** (six months public), once CI,
releases, a changelog, CONTRIBUTING and one outside use exist; (3) virtual
venues first (FPTalks, INCF or OCNS Software WG sessions); (4) later if
capacity: a preprint (arXiv endorsement asked only of a TEDU faculty member,
never of authors or maintainers contacted in wave 1), FOSDEM 2027, a
Drosophila 2027 or CNS*2027 poster. In-person venues are conditional on visa
lead times and funding and are decided by the owner. TÜBİTAK 2209-A per item
41.

### Slice J: the Phase F access request, prepared privately

| Step | Work |
|---|---|
| J1 | Drafted **outside the repository** or in a gitignored private folder, never exported into the tree. It is the only place the program is named, because it goes to that program |
| J2 | It cites the launch record: release and DOI, replication-report issues, upstream bug reports, any preprint |
| J3 | Before Phase F starts, a D-132-style provenance rule: nothing supplied by the hosted environment (sample JCL, course material, system datasets) enters the MIT tree; ONFLY's own output produced there is published only after the terms governing system access are checked |
| J4 | **On the day access is granted**, one D-row replaces the no-access statement (README, description, SRS 1.1, 2.3, 9.2 row F, overview) with a dated statement: the project has IBM Z access through a hosted IBM Z environment, row 8 results appear as they land, and everything before that date is emulated. Row 8 provenance records z/OS level, hardware model, compiler levels and "a hosted IBM Z environment". The program is still not named |

---

## 5. Claims register

Condensed from the claims audit. Evidence IDs are SRS rows.

### 5.1 CAN: what may be said

| ID | Ready phrasing | Evidence | Limits that travel with it |
|---|---|---|---|
| CAN-01 | "ONFLY simulates the sugar-to-feeding circuit of the male fruit fly: a 501-neuron subcircuit taken from the MaleCNS v1.0 connectome, run with the leaky integrate-and-fire model of Shiu et al. (2024) in a portable C89 engine with a COBOL batch driver." | SR-EXT-02, D-205, D-66, D-71 | Drawn from a scoped network holding 39.0% of MaleCNS synapses (VL-13); pharyngeal and taste-peg stimulus (VL-12); one fitted input term (D-205) |
| CAN-02 | "All 19 golden requests produce identical fingerprints and response records on x86-64 (a Python reference and three C floating-point builds) and on Linux s390x under QEMU. On MVS 3.8j under Hercules with the GCCMVS compiler the fingerprints are identical, and the response records are identical byte for byte apart from one text field that MVS stores in EBCDIC. With a second MVS compiler, JCC, all 19 reproduce the same way." | 8.3, VL-91, VL-95, VL-99, VL-101, VL-136, VL-137, VL-138, D-261 | Row 7 filled 2026-09-24 (VL-138); row 8 empty; consistency, not correctness (VL-05) |
| CAN-03 | "ONFLY has not run on IBM Z hardware, and the project does not have IBM Z access yet: every s390x and MVS result comes from emulators (QEMU and Hercules) on one x86-64 laptop." | Row 8 empty; the standing VL row (item 32) and item 2's D-row, once written; the owner's confirmations OA-8 and OA-9 | Usable since OA-8 and OA-9 (2026-09-24); revisit whenever a platform is added (3.2) |
| CAN-04 | "The s390x results come from Ubuntu 24.04 running under QEMU's instruction-by-instruction emulation, so they show the code gives the same results on a big-endian system, but say nothing about floating point on real s390x hardware." | VL-82, VL-01, VL-99, VL-05 | QEMU TCG only |
| CAN-05 | "Under Hercules 4.9.1 on an Intel Core i7-13650HX laptop, one standard 1000 ms request on the shipped network used 161 s of emulated CPU, inside the project's 10-minute budget; this is an emulator figure from one run and says nothing about IBM Z performance." | VL-106, VL-04 | One sample; never quote MIPS |
| CAN-06 | "On x86-64, sugar at 40, 60, 120 and 200 Hz made the MN9 feeding motor neurons fire in all 30 seeds at every rate, and zero sugar produced zero spikes in all 501 neurons; these science checks have been run on x86-64 only." | VL-105 | 10 Hz untested (reference is 0) |
| CAN-07 | "On x86-64, the 501-neuron subcircuit, which carries one fitted input term standing in for the neurons it leaves out, stays within 10% of the MN9 rate of the 184,099-neuron annotated MaleCNS network (39.0% of its synapses) at 40, 60, 120 and 200 Hz; 10 Hz is excluded because that network's rate is too variable there to test against." | VL-98, D-202, D-357, VL-13 | 40 Hz margin 0.85 Hz, below the reference SE; a re-seeded campaign passes 52 to 60% of the time (VL-114); not whole-brain (VL-13) |
| CAN-08 | "Compared with Shiu et al.'s model of the female FlyWire connectome, re-run from their published code, ONFLY's model on the 184,099-neuron annotated MaleCNS network (39.0% of its synapses), with the synaptic weight re-calibrated to 0.2969 mV and a pharyngeal and taste-peg sugar input, rises with sugar in the same shape but fires more at low rates: 3.67 Hz at 10 Hz where the reference is silent, and 14.35 Hz against 4.73 Hz at 40 Hz. No single synaptic weight removes that gap, so the agreement shows consistency of shape, not identity." | VL-112, VL-103, VL-108, VL-109, VL-06, D-164, VL-63 | Full annotated network, not the subcircuit; PASS by re-evaluation under the amended criterion; different stimulus (VL-12); scoped network (VL-13) |
| CAN-09 | "The transaction is written in real EXEC CICS and runs on x86-64 Windows under Raincode's CICS-compatible runtime, not under IBM CICS; its menu-screen program has never executed for lack of a licence, and running it concurrently is untested." | VL-117, VL-136, VL-37, D-440 | Windows only |
| CAN-10 | "The C engine, the Python reference, the x86-64 test suite and the two shipped networks are public; the MVS results need your own TK5 and Hercules setup and hours of emulated CPU, and the 3270 demonstration cannot be reproduced from the repository at all." | D-132, D-394, VL-88 | True only after slices E and G |
| CAN-11 | "On the emulated MVS 3.8j lab, typing a request on a 3270 session under INTERCOMM, a transaction monitor that is not CICS, starts an ONFLY batch run and then shows its result and golden fingerprint; this part cannot be reproduced from the repository because INTERCOMM's licence keeps its code out." | VL-129 to VL-134, VL-136 | The simulation is a batch job the transaction starts |
| CAN-12 | "The emulated MVS job streams its spike data to the host while it is still running, and for the five shipped-network golden requests that stream is byte-identical to the x86-64 one once line endings are normalised (D-414)." | VL-135, VL-136, D-414 | Two runs; `srext` only |
| CAN-13 | "The three-step BUZZ batch job (COBOL driver, C engine, COBOL report) ran end to end on emulated MVS 3.8j with return code 0 and printed the five shipped-network golden fingerprints." | VL-104 | One run; `srext` only |
| CAN-14 | "Comparing the full MVS and x86 output streams line by line exposed a GCCMVS code-generation fault that had turned every +0.0 in the MVS kernel into a tiny subnormal, a difference no fingerprint had ever caught; the fault is worked around, not fully characterised." | D-420, VL-118 to VL-127 | No minimal reproducer or assembler listing yet (VL-127); JCC not examined for it |
| CAN-15 | "Two acceptance criteria were changed after we saw the results: ACC-3 no longer tests 10 Hz, and ACC-4 no longer tests magnitude. Both changes and the failing numbers are recorded in the specification." | D-202, D-340, D-341, D-448 | Say it wherever ACC-3 or ACC-4 is cited |

### 5.2 MUST NOT: what is never said

| # | Never say | Say instead |
|---|---|---|
| 1 | Runs on IBM Z, a mainframe, z/OS, LinuxONE or real s390x hardware | "emulated", paired with CAN-03 |
| 2 | "Served as a CICS transaction", "runs on CICS", "CICS-ready" | CAN-09 |
| 3 | Mainframe or IBM Z performance, MIPS equivalence, "N times slower than a mainframe" | CPU seconds with host, Hercules version and network (CAN-05) |
| 4 | Reproduces Shiu et al., "matches the fly", "within 25% of the published model" | CAN-08, keeping "shape, not magnitude" |
| 5 | The whole fly brain, the complete connectome, all synapses, a synapse count without VL-13's scope, a pure-connectome 501-neuron circuit | "a 501-neuron subcircuit with one fitted input term" |
| 6 | "Criteria fixed in advance", "all criteria passed as originally written" | CAN-15 |
| 7 | The science was validated on MVS, s390x or "the mainframe" | "measured on x86-64" |
| 8 | "ACC-5 passes on every platform": row 8 (z/OS) is empty | CAN-02 with per-row counts. Since VL-138 both MVS compilers cover all 19, which CAN-02 now says |
| 9 | "Clone, run make test, reproduce everything"; a badge for a job CI does not run | CAN-10 and the ladder |
| 10 | "Deterministic means correct"; a fingerprint proves identical internal state | "identical response records and fingerprints" (VL-118 shows state can differ) |
| 11 | ACC-3 is robust under re-measurement | CAN-07 with VL-114 |
| 12 | "First" anything; IBM endorsement or affiliation | The non-affiliation text (C9) |
| 13 | Unmodified SoftFloat; an Enterprise COBOL-compatible driver | "SoftFloat 3e and 2c with documented derivations"; "COBOL checked by a GnuCOBOL proxy" |
| 14 | "Upload", "brain emulation", "digital fly", "whole brain" | CAN-01 |
| 15 | Unscoped "bit-identical" or "same bytes"; IEEE arithmetic done by S/370 hardware | "identical response records and fingerprints" (CAN-02) or the scoped stream claim (CAN-12); "IEEE 754 in software (SoftFloat)" |

---

## 6. Replication ladder

Wall clocks are **as recorded** on the owner's host (Intel Core i7-13650HX,
15.6 GB RAM), not predictions for other machines.

### 6.1 Commands, prerequisites and costs

| Rung | What | Entry command | Prerequisites | Recorded wall clock | Compare against |
|---|---|---|---|---|---|
| R0 | Check the committed evidence | `python tests/run_tx.py --compare data/phase-d/x86w data/phase-d/s390x`; `python tests/run_mvsrun.py` | Python 3 | seconds | The committed recordings |
| R1 | x86-64 build, suite, 19 golden fingerprints | `mingw32-make fixtures && mingw32-make testfloat && mingw32-make test` | The recorded toolchain, MinGW.org GCC-6.3.0-1 (32-bit i686); any other compiler is a new data point, not a reproduction. GNU Make, Python 3.13 with `requirements.txt`, two networks | 6 min 58 s (G0 doc); roughly 12 min after D-369 added the chunk sweep | SRS 8.3 row 3b, G-01 `6C143127` to G-19 `C4C320BC`; `data/phase-d/x86w/` |
| R2a | Science, re-measured deterministically on the replicator's runner | `python prep/extract.py --acc1 data/networks/onfnet-malecns-v1.0-srext.bin --label srext --jobs 8`; `python prep/extract.py --acc3-file data/networks/onfnet-malecns-v1.0-srext.bin --label srext --jobs 8`; `python prep/acc4.py --reeval data/calibration/acc4.json` | R1, `make runner` | 48 s (VL-105); 80 s (VL-98); ACC-4 re-evaluation runs no simulation | The verdict lines of VL-98, VL-105, VL-112 |
| R2b | Science, re-measured from the source data | MaleCNS download (1,109,008,094 B); `prep/emit.py full`; `prep/calibrate.py --cache`; `prep/acc4.py --jobs 14` | 15.6 GB RAM class host | 6,971 s for ACC-4 (VL-97); the Shiu re-run needs brian2, gone even on the owner's host (VL-88) | VL-97, the committed reference CSV |
| R3 | Linux s390x under QEMU | documented qemu-system-s390x line; `make ONFPLAT=s390x CC=gcc PYTHON=python3 test` in the guest | QEMU, Ubuntu 24.04 s390x image (digest recorded) | TestFloat build about 90 min; full suite "costs hours" | `data/phase-d/s390x/`, VL-99 |
| R4 | TK5 MVS 3.8j: rows 6, 7, ACC-6, ACC-7 | `python tools/mvsrun.py --run [--net path]`; `python tools/mvsjcc.py --run [--net path]`; `python tools/mvsrun.py --buzz` | SDL Hercules 4.9.1, TK5 (Update level not self-reported, VL-86), codepage 819/1047, JCC for row 7 | row 6 `srext` 855.7 s wall for the whole job (VL-91); row 6 `path` GO step CPU 63 min 04.79 s (VL-91); row 7 `srext` 940.9 s wall (VL-96); row 7 `path` GO step CPU 79 min 51.84 s (VL-138; D-471's six-hour estimate refuted); ACC-7 STEP2 14 min 04.18 s for five requests (VL-104) | `data/phase-e/mvs/`, `data/phase-e/jcc/` |
| R5 | Raincode EXEC CICS | `mingw32-make cics` | Raincode free edition, .NET, Windows, x86_64 gcc | none recorded | VL-117, VL-136 |
| R6 | INTERCOMM 3270 flow | `python tools/mvstx.py` | INTERCOMM, kept out by D-132 | result after 92 s (VL-133) and after 301 s on the Phase G re-verification (VL-136) | VL-129 to VL-134 |
| R7 | Live view | `mingw32-make clips` or `python tools/liveview.py --engine build/onflyeng_nat.exe`; MVS half via `tools/mvsstm.py` | R1, matplotlib, a GIF writer | about 20 s (x86 half) | VL-136, the committed GIFs |

### 6.2 What each rung proves, blockers today, target after this plan

| Rung | Proves | Does not prove | Blocked today by | Target |
|---|---|---|---|---|
| R0 | The owner's recordings agree with each other | That the checker ran anything | Nothing; `mvsjcc --compare` needs D-472's guard to be trusted | Documented as "check the evidence" |
| R1 | The build reproduces the recorded fingerprints on the replicator's toolchain | Correctness (VL-05); anything about MVS; row 3b's toolchain, unless it is the recorded one | Red `make test`; networks absent; MinGW-only recipes | Green on MinGW and Linux from a clean clone |
| R2a | The recorded ACC-1 and ACC-3 numbers reproduce on the replicator's NATIVE runner against the committed reference; ACC-4's verdict follows from its recorded measurement | That a re-seeded campaign passes (VL-114); anything about ACC-4 magnitude | Networks absent; pandas undeclared | Documented, minutes, in E's exit on both platforms |
| R2b | The science result reproduces as a measurement | Anything on MVS or s390x | Undocumented chain; overwrites tracked manifests; an absolute path skips a self-check | Documented recipe with RAM and disk budgets |
| R3 | The same results on a big-endian system, under emulation | Real s390x floating point | Guest bring-up not in the tree; test_seeds needs numpy, pandas | Bring-up script and package list committed |
| R4 | GCCMVS and JCC each reproduce all 19 x86 fingerprints (VL-91, VL-138), under emulation | IBM Z behaviour or performance | No archive digests; codepage outside the tree; ACC-6 clock Windows-only | Lab guide with digests and safety note |
| R5 | EXEC CICS source runs in process under a CICS-compatible runtime | IBM CICS; terminal flow; concurrency | Proprietary, Windows-only | Stated as owner-demonstrated |
| R6 | A 3270 transaction starts the batch job on emulated MVS | CICS anything | Out of the tree by design | Stated as not reproducible |
| R7 | The x86 stream renders; the MVS stream matched it (`srext`) | More than five requests | `srext` absent; matplotlib undeclared; `clips` overwrites tracked GIFs | Reproducible; `clips` output per item 38 |

---

## 7. Outreach plan

### 7.1 Rules for every post

1. Register sentences only. In neuroscience channels lead with what did not
   replicate (CAN-08, CAN-15); in mainframe channels with the emulator framing
   (CAN-03).
2. No hype: never "uploading a fly brain", "brain emulation", "digital fly" or
   "whole brain"; this audience is wary of such framing and will check.
3. No claim about IBM hardware, IBM performance or IBM CICS.
4. **Disclosure.** In every post in an IBM-run or IBM-sponsored channel, in any
   post that praises or recommends an IBM product, in any piece whose byline
   or bio shows the owner's IBM roles, and in any piece that discusses using
   IBM Z, the same post carries: "I am an IBM Champion (2026) and an IBM Z
   Student Ambassador. ONFLY is a personal project, not affiliated with or
   endorsed by IBM, and these views are my own." Which disclosure rules apply
   depends on jurisdiction (the audiences are international and the owner
   lives in Türkiye); this is not legal advice. No IBM logo or badge is used;
   nothing learned under an IBM NDA is used. Whether ONFLY is ever presented in
   a programme capacity is item 34. Programme terms are re-verified before the
   first IBM-channel post.
5. **The naming rule covers replies.** The owner's posts and replies never
   name the program; other people's comments are never edited, and are never
   answered with the name. The prepared answer to "why does an ambassador's
   project have no IBM Z access?": "My own IBM community activity is separate
   from ONFLY. ONFLY has not run on IBM Z hardware, and the project does not
   have IBM Z access yet. When that changes, the README will say so with a
   date."
6. **Corrections.** A factual error in a post is corrected in the register
   first, then in the same channel, visibly and with a date. Bringing old copy
   under the naming rule is a silent in-place edit under OA-3 and is never
   announced. No new wave starts while any live ONFLY copy the owner controls
   breaks a MUST-NOT.
7. Private replies from authors, maintainers or reviewers are never quoted or
   named in public without written permission, and never presented as
   endorsement.
8. Never state a named person's employer, or repeat a company's disputed
   claims, in anything public. Affiliations are checked on the day of a
   private email and used only in its salutation.
9. Never ask anyone, ambassador and champion networks included, for votes,
   stars, comments or submissions. The owner takes part in a community before
   posting to it.
10. Any post that shows a MaleCNS-derived image carries: "Data: MaleCNS v1.0
    (HHMI Janelia, MRC LMB, University of Cambridge, Google Research), CC BY
    4.0, modified by ONFLY."
11. One outreach calendar: ONFLY copy produced outside this plan (the weekly
    blog task, the backlink tracker's open items) follows item 40.
12. Every channel rule and date below is web-sourced: **re-verify at time of
    use**.

### 7.2 Waves

Dates are targets; a wave starts only when its gate holds. L is the day the
slice G release is published. The owner carries the whole reply load. The
open decisions are batched into two or three owner sessions at the start of
wave 0.

| Wave | Dates (targets, re-verify) | Gate | Audience | Channels (CORE) | Angle | Success signal |
|---|---|---|---|---|---|---|
| -1 Correct what is live | From approval of P-41; not gated on A to G | Owner login | Readers of existing copy | Inventory first: the IBM Community post and thread, the ONFLY pages and the SoftFloat article on the personal site, LinkedIn Featured, speaker bios, whatever the weekly blog task has published. Then one batched save to the blog (each save may re-queue moderation), checking the search-description panel as well as the body | Corrections: the fixes listed in private notes, silent where 7.1 rule 6 says so; a dated visible correction ("Correction, `<date>`: an earlier version said the acceptance criteria were fixed before measurement. Two were changed after results were seen: ACC-3 no longer tests 10 Hz, and ACC-4 no longer tests magnitude. Details: `<link>`."); title and search text qualified to "emulated MVS 3.8j"; the disclosure line; the CICS sentence updated; the synapse count scoped (VL-13) | No live copy the owner controls breaks a MUST-NOT |
| 0 Readiness | now to about 2026-10-11 | none | none | none | none | Slices A to F and H0 done |
| W1a Trusted testers | 2026-10-12 to 10-25, before G | E, F, H0 | 3 or 4 people the owner knows (for example a TEDU faculty member or classmate on Linux, one on Windows, one TK5 hobbyist if available) | Private invitation to a release-candidate branch, with no GitHub release and no Zenodo hook | Each has one task: clean-clone R0 and R1 plus a `replication_report` issue, or a read of README, overview and write-up against Section 5 | At least 2 testers reach R1 from a clean clone and file reports |
| W1b Upstream and authors | L+1 to L+21; L target 2026-10-26 | G | Upstream maintainers; the model's authors | The GCCMVS report, only with its reproducer (7.3 a); JCC and TK5 findings to their maintainers; one email to the corresponding author of Shiu et al. with the first author in CC, asking for technical feedback, not endorsement, pointing to the stable release | Concrete findings with evidence | The GCCMVS report answered within 30 days (a signal, not a gate); corrections fixed |
| W2a Verifiers | target 2026-11-17 to 11-27 | W1 corrections merged; item 4 closed and stated in README | Mainframe hobbyists; connectomics | One post in one group (H390-MVS or turnkey-mvs, after reading its guidelines and some weeks of archive; plain text, links not attachments, answers in the list); one neuPrint group question on the cell-type mapping; the awesome-fly and Awesome-Mainframes PRs; the TEDU project-page request | Hobbyists: JCL, COND CODEs, how to repeat R4. Neuro: reproducible execution of a published model on an extracted subcircuit, not new biology | At least one replication report or technical correction from someone the owner does not know; no thread unanswered for more than 3 days in its first week |
| W2b IBM Z and open mainframe | at least 14 days after W2a's last post: target 2026-12-11 to 12-17 | W2a corrections merged; item 34 answered | IBM Z and open mainframe | One post with the disclosure: an update in the existing IBM Community thread, or one OMP Slack post | Portable C89 with a COBOL batch driver; EXEC CICS source under a CICS-compatible runtime; Hercules only as a hobbyist lab | Substantive technical replies; no MUST-NOT breached in replies |
| W3 Broad | at least 14 days after W2b: 2027-01-12 to 01-28, Tue to Thu, avoiding the TEDU exam calendar (re-verify) and any day with a morning commitment after it | W2 replies handled; the reproducer exists (preferably answered upstream); an outside tester ran `make quick` on a clean machine in under 5 minutes | General developers | The write-up submitted to HN once as a normal link; a Hackaday tip | "Identical output records from x86-64 and emulated MVS 3.8j: a fruit fly circuit in C89 with software floating point", or "+0.0 returned as a subnormal: a compiler bug hunt on emulated MVS 3.8j" | Counts of non-owner issues, replication reports and substantive corrections within 30 days; not stars, points or clones |
| Academic | from 2027-02, after W3 settles | Slice I | Researchers | ReScience C first | Replication with its limits | Reviews |

**Later if capacity** (dropped first): one of comp-neuro or Neurostars, only
if the neuPrint question yields nothing; Planet Mainframe; a second IBM
Community article; the IBM Developer tutorial (item 40); an FPTalks pitch;
FOSDEM; a preprint; Devnot and a Kommunity talk (after W3). **Cut:** Reddit;
lobste.rs as an active step (organic submissions by others are fine); Bluesky
and neuromatch.social unless the owner already has an active presence there.

**Slip rules.** If L falls after 2026-11-09, W2b moves to 2027-01 and W3 to
2027-02-09 to 02-25, again checked against the exam calendar. FOSDEM is then
decided on its own. IBM-side posts stay out of IBM TechXchange week
(2026-10-26 to 10-29) and GS UK Forge26 week (2026-11-02 to 11-05), both
re-verify.

**Reply load.** At most two new public posts a week. The owner sets a weekly
outreach hour cap and the drop order above (item 12). Each post is checked
daily for 7 days, then closed with one reply pointing to issues. Every post
names one canonical inbox. Saved replies come from the FAQ. Anything needing
a lab run becomes an issue, not a promise. During waves, a weekly private
snapshot of `gh api repos/mertefesensoy/ONFLY/traffic/views` and
`.../traffic/popular/referrers` is saved, because the API keeps 14 days.

### 7.3 Message skeletons

These obey the register. Angle brackets are placeholders filled from the
record, never from memory. The text actually sent to individuals is kept in
private notes.

**(a) Upstream report to the GCCMVS maintainers.** Prerequisite: a standalone
C89 reproducer of about 20 lines, comparing a no-argument function that
returns a two-word struct with the same struct returned from a two-argument
function, built with GCCMVS 3.2.3 at -O1 on TK5 with its assembler listing
read, and the same reproducer under JCC (one lab run, opened as an issue).
Until it exists:

> Subject: GCCMVS 3.2.3 -O1: a no-argument function returning a struct returns
> wrong bytes
>
> Under GCCMVS 3.2.3 at -O1 on MVS 3.8j (TK5, Hercules 4.9.1), a no-argument
> function returning a two-word struct returned a subnormal near 1e-318
> instead of +0.0, while the same type returned from a two-argument function
> was correct. Source and both outputs: `<permalink>`. We have a workaround
> and have not built a minimal reproducer yet.

With the reproducer, the last sentence becomes "Reproducer and assembler
listing attached: `<permalink>`."

**(b) H390-MVS announcement**

> Subject: ONFLY: a C89 engine and COBOL batch driver on TK5
>
> On MVS 3.8j under Hercules (TK5, Update 5 archive as installed; the level
> is not self-reported), the engine jobs reproduce all 19 golden fingerprints
> under GCCMVS, and under JCC `<count>` of 19 so far. The three-step BUZZ job
> (COBOL driver, C engine, COBOL report) ran end to end once, at COND CODE 0,
> on the five shipped-network requests. JCL, COND CODEs, listings and how to
> repeat it: `<REPLICATING.md, R4>`. The project has no IBM Z access; all of
> this is emulated. Reports from other Hercules setups are very welcome.

**(c) Email to the model's authors** (one email, first author in CC)

> Dear `<name>`,
>
> `<one line on who the sender is, per item 29>`; this is a personal project
> (`<release link>`). I re-ran your published code on FlyWire 630 to get the
> reference curve, then ran the same model on MaleCNS with the synaptic weight
> recalibrated to 0.2969 mV and a pharyngeal and taste-peg sugar input rather
> than your labellar GRNs. The response rises in your model's shape, but at
> 10 Hz it fires at 3.67 Hz where the reference is 0.00, and at 40 Hz at
> 14.35 Hz against 4.73 Hz. I judged agreement on the curve's shape, not its
> magnitude, a choice I made after seeing these numbers. `<one answerable
> question, for example on the cell-type mapping at <link>>` I am not asking
> for endorsement, and no reply is needed.

**(d) IBM Community thread update or OMP Slack post**

> ONFLY is a personal project: a C89 engine with a COBOL batch driver. The
> engine's golden fingerprints are identical on x86-64, on Linux s390x under
> QEMU and on MVS 3.8j under Hercules; under a second MVS compiler, `<count>`
> of 19 so far. Its EXEC CICS transaction source runs only on x86-64 Windows
> under Raincode's CICS-compatible runtime, not IBM CICS. ONFLY has not run on
> IBM Z hardware; the project does not have IBM Z access yet. `<disclosure
> line, always>` `<link>`

Before posting, each platform the COBOL driver is claimed on is checked
against the record.

**(e) General-developer write-up, title and first lines**

> Same output bytes on a laptop and on emulated MVS 3.8j: simulating a fruit
> fly circuit in C89 with software floating point. How the byte comparison
> was built, the compiler fault it found, and what it does not prove (it
> never ran on IBM Z hardware).

The body names both normalisations: the EBCDIC text field translated (D-261)
and line endings normalised (D-414).

**(f) Awesome-list entry**

> `[ONFLY](<url>)`: deterministic C89 simulation, with a COBOL batch driver,
> of a 501-neuron MaleCNS sugar-feeding subcircuit (extracted circuit, not
> whole brain); identical response records on x86-64, emulated s390x and
> emulated MVS 3.8j. Personal student project, not affiliated with FlyEM or
> FlyWire.

---

## 8. Risks and mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| Live copy outside the repository already contradicts the register | Certain today | Wave -1, before any new wave (7.1 rule 6) |
| The name returns through a session, memory file, copy-paste or commit message | High without a guard | Slice B guard in both hooks, `namelint` in `test`, CI; the parallel session told first; replies covered by 7.1 rule 5 |
| The parallel session's SRS edits conflict with the scrub | High | Scrub only after its merge; occurrence list rebuilt by scan |
| The row 7 `path` run is lost a third time (JOB 398, JOB 400) | Retired 2026-09-24: JOB 402 filled the row (VL-138) | Item 6 closed by D-497 |
| An archive, fork or release captures an unscrubbed tree, or a tree before outside eyes | Certain for the past, avoidable now | Slice G gated on Section 11 and on W1a; the plan never claims the name is gone |
| A stranger's Linux result differs from the recorded fingerprints | Medium | A finding, not a failure: the replication template records it; Linux is not evidence until item 7 admits it |
| Hostile reception in neuroscience channels | Medium | Register only; lead with non-replication; authors' private feedback first |
| One maintainer overwhelmed, in term time | High | CORE set only; 14-day spacing; hour cap and drop order; one inbox; saved replies |
| The schedule slips | High | Slip rules (7.2); decisions batched |
| IBM reuses programme-participation material beside the program's name | Low to medium | Item 34; W2b waits for a written answer |
| FlyWire non-commercial terms reach released files | Medium until item 8 is decided | Item 8 inventory decided before G, legal input (3.5) |
| CI supply-chain compromise | Low | F6 and F7 controls |
| Replicators expose the lab's unauthenticated ports or default login | Low to medium | Lab safety note (E8) |
| Broad channels ignore or reject the write-up | Medium | Submitted once as a normal link (channel rules re-verify); silence is a normal outcome |
| Confusion with, or a claim from, a company called Onfly | Low to medium; not assessed legally | Item 9 decided before G |
| Copy outside the repository drifts from the register | Medium | Item 40; the weekly task paused until the register is committed |
| Readers find AI assistance after launch | Medium | Item 4 closed before W2a |

---

## 9. What this plan will NOT prove or change

1. **No new science.** No ACC verdict, seed, reference or deviation changes.
2. **No IBM Z result.** Row 8 stays empty; the access request is not sent.
3. **Forward scrubbing does not un-publish** anything already public.
4. **The wording D-row changes no decision's substance**, and keeps each
   definite reference definite.
5. **Row 7's `path` half came from the parallel session (VL-138), not from
   this plan.** Item 6 closed as (a) (D-497), so no pending-state rule was needed.
6. **An outside R1 replication shows consistency, not correctness** (VL-05).
7. **A CI green on another toolchain does not reproduce row 3b's toolchain**
   (MinGW.org GCC-6.3.0-1, 32-bit).
8. **Launch reception is not evidence** that ONFLY is right, and silence in a
   niche channel is a normal outcome, not a reason to move to broader
   channels early.
9. **The licensing work is not legal advice** (3.5).
10. **Web-sourced outreach facts are unverified on disk.**
11. **Phase H and TBD-13 are untouched.** No real CICS is sought or used.

---

## 10. Open decisions for the owner

Not settled by OA-1 to OA-10 unless marked; each is resolved by a D-row, never
on silence. Items 2, 3, 4, 6, 10, 13, 14, 16 to 21, 23, 30, 31, 32, 36 and 42 are closed, items 8 and 29 are answered for slices C and D, and item 9 is deferred; their rows name the D-row.
"Legal" marks items where qualified input is advisable (3.5).

| # | Decision | Options | Recommendation | Legal |
|---|---|---|---|---|
| 1 | Naming-ban scope beyond this repository: surfaces the owner controls outside ONFLY (listed in private notes) | (a) repository only; (b) every public page or post that mentions ONFLY; (c) every public surface. Under (b), whether the certification entry on the personal website stays is a separate choice: (b1) keep it, on a page that does not mention ONFLY; (b2) remove it | (b), with (b1) or (b2) left to the owner | |
| 2 | No-access wording, and the two confirmations of 3.2 | (a) about the project (3.2); (b) about the person; (c) also say the request is unsent | **Closed by D-491 and D-492 (OA-8, OA-9): (a) stands.** (c) adds nothing D-126 does not already say | |
| 3 | Coordination with the parallel session | (a) scrub after its merge; (b) pause its SRS edits now; (c) it scrubs its own D-468 before merging | **Resolved by D-479 (2026-09-24, on the parallel branch): (c), plus A1.** That session neutralised its own D-468 in a forward commit; every other occurrence waits for slice B | |
| 4 | AI-use disclosure, given D-478 and venue policies (JOSS and TÜBİTAK 2209-A require one; re-verify). An entry condition for W2a | (a) a short README section: tools, what they did, how outputs were verified; (b) only where a venue requires; (c) none | (a): SRS:23 already names an agentic tool and pre-rewrite commits with trailers are fetchable by SHA. D-478 governs commit metadata only, so there is no conflict. The jurisdiction-dependent copyright status of tool-generated code is a question for paper authorship statements, not resolved here. **Closed 2026-09-25 by D-522 as (a)**; the paragraph's accuracy confirmed by D-533 | |
| 5 | Network distribution | (a) commit `srext` and `path` (1,122,968 B; reverses `.gitignore:29`), which removes the E/G ordering dependency; (b) release assets with SHA256SUMS, staged locally for E (the order of Section 4); (c) a Zenodo dataset under CC BY 4.0; same question for `hop2` and `full` (21.6 MB, 299.5 MB) | (b), with (c) later if a data DOI is wanted; `hop2` and `full` regenerate-only. Decide after item 8 | yes |
| 6 | The `make test` gate, with a date by which the owner chooses | (a) wait for the row 7 run; (b) amend D-464 so a missing row 7 recording reports PENDING, not FAIL. D-464 required both halves because a test that skips a missing recording lets the path half rot silently ("Requiring both is the point", Makefile:820-838); so (b) needs a committed marker naming its D-row, `run_mvsjcc.py` printing PENDING plus that D-row, and failure if marker and recording are both present or both absent; (c) `make test` for replicators and `make evidence` (mvsrun, mvsjcc, names) keeping D-464's strictness as R0 | **Closed 2026-09-25 by D-497 as (a):** the row 7 run landed (VL-138) and green runs are recorded; E2's caveat stays with slice E | |
| 7 | Linux build and CI, and how OS, ABI and compiler version enter SRS 8.3 (rows 1 to 3 name only "x86-64" and "gcc or clang") | (a) new rows; (b) provenance sub-rows under 2, 3 and 3b; (c) CI smoke tests only, never matrix evidence. And: a `-Werror` failure on a newer gcc gets a source fix with an evidence note, or a documented flag override for compilers with no recorded row | (b) for the owner's own Linux 19 of 19, (c) for CI; a source fix only with evidence that fingerprints are unchanged | |
| 8 | Status of FlyWire-derived material. Inventory: `reference/shiu/results/` (the curve); `data/calibration/{acc1-candidate, acc4, acc4-phg9, acc4-right, acc4-tpgrn, search-log, search-log-rerun, seeds, wsens-d52-s30, wsens-right-s30, wsens-tpgrn-s30, wsens-tpgrn-s4}.json`, which embed it; `docs/implementations/2026-09-12-phase-c-calibration.md` and SRS text quoting it; `reference/shiu/rerun.py` (21 FlyWire root IDs from Shiu's MIT notebook); W_syn 0.2969, fitted to the curve (SR-CAL-03) and multiplied into every edge weight of `srext`, `path`, `hop2` and `full` | (a) all of it CC BY-NC 4.0, which puts NC terms on the network assets and `data/calibration`; (b) the curve and the files that reproduce it CC BY-NC, with a stated position that one fitted scalar and identifiers are not Adapted Material, taken on legal input; (c) the curve treated as factual model output under MIT or CC BY with FlyWire attribution | Owner takes legal input before slice G; whichever is chosen, THIRD_PARTY_NOTICES, `data/README.md` and the release notes say in one sentence what it means for the network binaries. **Answered for slices C and D by D-515: pending legal input.** The notices cite FlyWire's terms and take no position; the item stays open until slice G | yes |
| 9 | Name collision with Onfly, a travel and expense software company (re-verify); trademark registrations not checked | (a) keep, with the README line "ONFLY is unrelated to Onfly, the travel and expense software company."; (b) rename before slice G | Decide before G; a clearance search or advice first if certainty is wanted; a rename is cheapest now. **Deferred by D-528:** no README line in slice D; decided before slice G | yes |
| 10 | IBM roles in launch copy | (a) not in the repository; disclosure per 7.1 rule 4 in posts; (b) in README with the non-affiliation line; (c) nowhere | (a); the C9 roles sentence only under (b). **Closed 2026-09-25 by D-519 as (a)** | |
| 11 | Version scheme; closes before slice E | (a) SemVer from v0.1.0; (b) first tag v0.5.0, matching the `ONF_ENGVER` "0.5.0" every evidence file prints; (c) v1.0.0 | (b): one number in front of readers; `ONF_ENGVER` bumped by hand thereafter; the owner defines 1.0.0 (for example row 8 filled) | |
| 12 | Support policy, reply budget, canonical inbox | Tiers and window as in F3; weekly outreach hour cap; issues or Discussions as the one inbox | Supported: x86-64 suite, evidence audit; best effort: s390x, TK5; unsupported: Raincode, INTERCOMM, z/OS; 14-day window for issues, daily checks for 7 days on posts; issues as the inbox and Discussions off at launch | |
| 13 | Where the overview lives | (a) `docs/overview.md`; (b) repository root; (c) README only | (a). **Closed 2026-09-25 by D-529 as (a)**, Markdown only, no `.docx` | |
| 14 | `.docx` exports and `md2docx.js` | (a) remove both tracked `.docx`, export as release assets on request, move `md2docx.js` to `tools/` with a neutral palette; (b) regenerate and keep tracking | (a): tracked binary exports drift and cannot be grepped. **Closed 2026-09-25 by D-502 as (b):** the SRS export is regenerated and kept, with `docx@9.7.2` installed outside the tree (D-508); `md2docx.js` stays where it is | |
| 15 | Retiring session branches (after G) | (a) remote branches deleted, pointer tags local only (amends the D-443, D-446, D-460 practice); (b) keep | (a) after the parallel branch merges; deletion hides branches, not commits | |
| 16 | Tagline "A fruit fly's brain, served as a CICS transaction" (SRS:3) | (a) replace; (b) qualify; (c) keep | (a), e.g. "A fruit fly's sugar-feeding circuit in C89 and COBOL, with identical outputs from x86-64 to emulated MVS 3.8j". **Closed 2026-09-25 by D-523 as (c)**, against this recommendation; the README does not repeat the tagline | |
| 17 | Indirect references to the request (D-01, D-126 and others; "IBM reviewers" at SRS:23, :117) | (a) keep decision rationale, rewrite reader classes; (b) remove all | (a): the ban is on the name. **Closed 2026-09-25 by D-524 as (a)** | |
| 18 | Historical "mainframe" vocabulary | (a) glossary (3.3); (b) edit each record | (a). **Closed 2026-09-25 by D-525 as (a)** | |
| 19 | ACC-3 margin (0.56 Hz in text, 0.85 Hz in the record); `acc4.json` `"pass": false` | (a) correct the text, annotate the record; (b) regenerate `acc4.json` (about 6,971 s) | (a). **Closed 2026-09-25 by D-526 as (a)**; the margin is 0.85 Hz (D-535) | |
| 20 | Licence of ONFLY's own part of MaleCNS-derived data, media **and the network files** | (a) CC BY 4.0; (b) MIT; (c) CC0 with upstream attribution | (a), subject to item 8. **Closed 2026-09-25 by D-516 as (a)** | yes |
| 21 | C-08 forbids CICS in component names; `onfcics`, `cics/` and others use it | (a) amend C-08: "onfcics, Onfly.Cics and cics/ are internal identifiers never presented as a product name; public copy never calls any part ONFLY CICS"; (b) rename before launch | (a). **Closed 2026-09-25 by D-517 as (a)**; C-08 amended by D-535 | |
| 22 | Absolute paths in 7 tracked data files, one disabling a self-check | (a) keep as evidence, write relative paths from now on, fix the self-check; (b) scrub | (a) | |
| 23 | Author spelling in public documents and `CITATION.cff` (D-478 already fixes commit identity) | Sensoy or Şensoy | Owner's choice. **Closed 2026-09-25 by D-518: "Şensoy"** | |
| 24 | Contribution terms | (a) contributions accepted under the licence of the path they change (MIT for ONFLY code), as GitHub's terms of service provide (re-verify); no non-commercial or unlicensed third-party material (D-132); (b) DCO sign-off | (a); `third_party/` is never edited (D-35), so PRs touching it are declined | yes |
| 25 | Contact channel for conduct and security | (a) private vulnerability reporting plus a dedicated address; (b) reporting only | (a) if a dedicated address is acceptable, else (b) | |
| 26 | IBM's free s390x CI runners or LinuxONE community VMs before Phase F (re-verify) | (a) not before launch; (b) adopt, and change the statement for Linux on Z | (a); revisit after launch | |
| 27 | Decision log citing commits no branch reaches (D-478 cites two) | (a) allow, marked unreachable; (b) cite the rewritten commits | (a) | |
| 28 | Fixing `\| tail -1` changes what earlier greens covered | (a) fix and record; (b) leave | (a) | |
| 29 | Copyright ownership and affiliation, before slice G: confirm no agreement or policy (university IP policy, IBM programme terms, internship or employment agreement, a grant) assigns, exclusively licenses or claims rights in ONFLY or requires an acknowledgement; decide whether TED University appears in `CITATION.cff`, Zenodo metadata, preprints and posts | (a) no affiliation, personal project; (b) affiliation after checking the university's publicity policy | (a) until checked. **Answered as (a) for the non-affiliation text by D-520**; the check before slice G is still advised | yes |
| 30 | Push cadence | (a) push each slice to `main` as it lands (per-slice GitHub checks; intermediate states public); (b) hold B to F on a branch and push once; (c) push B at once to end name exposure in the current tree, then batch C to F | (c); every GitHub-side check runs after the push. **Closed 2026-09-25 by D-504 as (c)** | |
| 31 | How the committed guard and the scans hold the token | (a) accept encoded forms in the tree; (b) scripts read it from a gitignored file or environment variable, CI from an Actions secret (guard skipped on fork PRs); (c) the committed guard keeps only a salted digest, ad hoc scans read `ONFLY_NAME_B64` from the environment, and no public text carries an encoded form or describes the allowlist's words | (c): works in CI without secrets and keeps every public file free of the word in any form. **Closed 2026-09-25 by D-503 as (c)** | |
| 32 | A standing VL entry "no IBM Z hardware has been used", dated and citing item 2's D-row | (a) yes; (b) README only | (a); SRS 1.1 and CAN-03 then cite it. **Closed 2026-09-25 by D-527 as (a)**: VL-139 | |
| 33 | PR #1 body wording ("the document handed to IBM") and its earlier revision | (a) edit the body; (b) leave it | (a), knowing that edit history stays visible | |
| 34 | ONFLY in an IBM programme capacity | (a) never: ONFLY posts are personal, not logged as advocacy acts or deliverables, not posted in programme-only spaces; (b) allowed after a written answer from the programme managers on whether a personal IBM Community post by an ambassador falls under the content-licence clause, and whether stating the role title in a disclosure is allowed under the branding clause. Also: whether the existing post and thread were logged as advocacy acts | (a) until that answer exists; W2b waits for it | yes |
| 35 | D-132 wording against tracked `tools/mvsicom.py`, which generates JCL naming INTERCOMM datasets and relinking ICOMCR | (a) reword D-132, or add a note, so tracked generators that only name INTERCOMM datasets and procedures are explicitly allowed; (b) move the generator into `local/` | Owner's call after legal input; (b) is the conservative default | yes |
| 36 | Owner email in tracked files (none today; D-478 writes it into SRS:1108; a `.mailmap` would too) | (a) accept, since it is in every commit's metadata; (b) keep it out: no `.mailmap`, and D-478's address reviewed when B edits the merged SRS | Owner's call. **Closed 2026-09-25 by D-505 as (a):** D-478 is left as written | |
| 37 | A Software Heritage save | (a) request one after G6; (b) leave it to the archive's own crawler. First check existing visits (11.15) | Owner's call; if (a), only after G6 | |
| 38 | `clips` default output (D-388, D-389 set it to overwrite tracked GIFs) | (a) default to `build/`, tracked GIFs updated only by an explicit flag; (b) keep | (a), by a D-row amending D-388 | |
| 39 | Host of the write-up | (a) in the repository, rendered by GitHub; (b) the personal site, after item 1; (c) dev.to | (a), or (b) after item 1, with the repository as the call to action | |
| 40 | ONFLY copy produced outside this plan: the weekly blog task and the backlink tracker's items (a second IBM Community article, speaker bios, an IBM Developer tutorial, a TEDU page, Devnot, Kommunity) | (a) one calendar: the task paused for ONFLY until the register is committed, then given the register and the naming rule as inputs, every PR it opens passing the Section 11 scans; tracker items folded into the waves; (b) run separately | (a); every ONFLY post links the repository as its call to action; whether ONFLY outreach serves the backlink strategy at all is the owner's call | |
| 41 | TÜBİTAK 2209-A (the 2025 call ran 13 Oct to 19 Nov; re-verify), which collides with W1 and W2 | (a) apply, forward-looking work only, with a TEDU advisor; (b) skip this cycle | Owner's call; (a) only if it does not displace CORE outreach | |
| 42 | OA-3's D-row and the wording-policy row | (a) one row; (b) two rows | (b): the answer and the policy it produces are separate records. **Closed 2026-09-25 by D-495 as (b)** | |

---

## 11. Verification

Run from the repository root. **No command in this plan contains the
program's name in any encoding.** Each reads it from the environment variable
`ONFLY_NAME_B64`, which the owner sets from private notes. The scans do not
use the slice B guard, so they check it rather than trust it, and they have no
allowlist, so any hit is inspected by hand. On `main` at 4a25639, 11.1
reports 32 (23 in Markdown, 9 in the two `.docx`), 33 on f0ec691, 32 on
00a73fb and 32 on 9ad60e9, and 11.3
over all of `main` reports 2; the targets after slice B are 0 for the tree and
0 from the scrub commit on.

**11.0 A shared matcher** (Bash; reads stdin, prints a count only)

    namecheck() { python -c "import base64,html,os,re,sys,unicodedata,urllib.parse as u; w=base64.b64decode(os.environ['ONFLY_NAME_B64']).decode(); t=re.sub('[^a-z0-9]','',u.unquote(html.unescape(unicodedata.normalize('NFKC',sys.stdin.read()).casefold()))); n=t.count(w); print('hits:', n); sys.exit(1 if n else 0)"; }

**11.1 A commit's tree, including Office files and paths** (Bash; fails
closed: any read or unzip error exits 2)

    python - <commit> <<'EOF'
    import base64, html, io, os, re, subprocess, sys, unicodedata, zipfile
    import urllib.parse as u
    w = base64.b64decode(os.environ['ONFLY_NAME_B64']).decode()
    def norm(t):
        t = u.unquote(html.unescape(unicodedata.normalize('NFKC', t).casefold()))
        return re.sub('[^a-z0-9]', '', t)
    def text(n, raw):
        if n.lower().endswith(('.docx', '.xlsx', '.pptx')):
            z = zipfile.ZipFile(io.BytesIO(raw))
            return '\n'.join(re.sub(r'<[^>]+>', '\n', z.read(m).decode('utf-8', 'ignore'))
                             for m in z.namelist())
        return raw.decode('utf-8', 'ignore')
    c = sys.argv[1]
    git = lambda *a: subprocess.run(('git',) + a, capture_output=True, check=True).stdout
    hits = 0
    try:
        for n in [n for n in git('ls-tree', '-r', '-z', '--name-only', c).decode().split('\0') if n]:
            k = norm(n + '\n' + text(n, git('cat-file', 'blob', c + ':' + n))).count(w)
            if k:
                hits += k
                print('%4d  %s' % (k, n))
    except Exception as e:
        print('scan error:', type(e).__name__)
        raise SystemExit(2)
    print('total', hits)
    raise SystemExit(1 if hits else 0)
    EOF

Expected after slice B, and on the commit to be tagged: `total 0`, exit 0.

**11.2 Untracked files about to be added:** `git ls-files -z --others
--exclude-standard | xargs -0 cat | namecheck`, expected `hits: 0`.

**11.3 Commit messages, the tag message and the release notes**

    git log --format=%B <scrub>^..HEAD | namecheck
    git tag -l --format='%(contents)' <tag> | namecheck
    namecheck < <release-notes-file>

Expected: `hits: 0` for each, the last two before publication.

**11.4 GitHub-side surfaces**, before G3 and again after G4

    gh api repos/mertefesensoy/ONFLY --jq '.description, (.topics|join(" "))' | namecheck
    gh release view <tag> --json body --jq .body | namecheck
    gh pr view 1 --json body --jq .body | namecheck
    curl -s https://zenodo.org/api/records/<record> | namecheck

Expected: `hits: 0` for each (the PR check only after item 33 is (a)).

**11.5 Licence detection** (after push)

    gh api repos/mertefesensoy/ONFLY/license --jq .license.spdx_id

Expected: `MIT` (today `NOASSERTION`).

**11.6 README, community files, settings** (after push)

    gh api repos/mertefesensoy/ONFLY/readme --jq .path
    gh api repos/mertefesensoy/ONFLY/community/profile --jq '.health_percentage, .files'
    gh api repos/mertefesensoy/ONFLY --jq '{description, topics, has_discussions, has_wiki, has_projects}'
    gh api repos/mertefesensoy/ONFLY/private-vulnerability-reporting --jq .enabled

Expected: `README.md`; every community file present; the description ends
with the short no-access statement; Discussions, wiki and projects as item 12
and F7 set them; `true`.

**11.7 The no-access statement is where 3.2 puts it**

    grep -c 'ONFLY has not run on IBM Z hardware' README.md docs/overview.md docs/ONFLY-SRS.md

Expected: at least 1 in each file.

**11.8 The test suite**, in a fresh clone outside the owner's worktrees, a
fresh venv from `requirements.txt` only, `ONFLY_FIXTURES` unset,
`ONFLY_NOSKIP=1` (to be written), assets staged with `--from` before G and
downloaded after

    mingw32-make fixtures && mingw32-make testfloat && mingw32-make test
    make ONFPLAT=<linux-x86-64> PYTHON=python3 fixtures test
    make quick

Expected: exit 0; the closing line reports PASS, SKIP and PENDING counts with
SKIP 0 (the Linux platform name is provisional).

**11.9 Network checksums**

    python tools/fixtures.py --check
    (cd <download dir> && sha256sum -c SHA256SUMS)

Expected: exit 0; two `OK` lines (`srext`
`bf09a3ad18a82b8ecc0dd2fd397d81e332f38c98a78325269f5c39d2b3b1f66d`, `path`
`168627c833d7af0f33bd0ed8d2bd1fbb407fd3c4436e0f57558c772cbb8b28f9`) and two
`NOT DISTRIBUTED` lines; every checksum OK.

**11.10 CI and the guard**

    gh run view <id> --json jobs --jq '.jobs[]|[.name,.conclusion]'
    python tools/lint_name.py --self-test
    git config --get-all core.hooksPath

Expected: `name-guard`, `python-bare`, `nonet-linux`, `nonet-windows` (and
`golden` after G5) each `success`; the self-test passes; no `core.hooksPath`
output. Then, in a throwaway `git worktree add`, a commit adding a synthetic
sample built from `ONFLY_NAME_B64` and a commit whose message contains it are
both rejected; the worktree is removed afterwards.

**11.11 Release, downloaded anonymously**

    gh release view <tag> --json tagName,assets --jq '.tagName, [.assets[].name]'
    curl -fsSLO https://github.com/mertefesensoy/ONFLY/releases/download/<tag>/SHA256SUMS
    curl -fsSLO https://github.com/mertefesensoy/ONFLY/releases/download/<tag>/<asset>
    sha256sum -c SHA256SUMS
    gh release view <tag> --json body --jq .body | grep -c 'CC BY 4.0'

Expected: the G3 assets including `NETWORKS-NOTICE.md`; every checksum OK;
at least 1; the README's DOI resolves.

**11.12 Licence notices** (a check script, to be written in slice C)

Asserts that `THIRD_PARTY_NOTICES.md` names each LIC-00 component and each
item 8 inventory path; that
`grep -c "Redistribution and use in source and binary forms" softfloat/onfrpk.c softfloat/onfprim.c`
gives at least 1 for each; that `reference/shiu/results/NOTICE.md` and
`data/README.md` exist; that `reuse lint` passes; and that the release body
and `NETWORKS-NOTICE.md` contain "CC BY 4.0" and all four MaleCNS parties.

**11.13 No em dashes in anything slices B to G add or edit**

    python -c "import sys; n=sum(open(f,encoding='utf-8').read().count(chr(0x2014)) for f in sys.argv[1:]); print('em dashes:', n); sys.exit(1 if n else 0)" $(git diff --name-only --diff-filter=A <scrub>^..HEAD) CITATION.cff CHANGELOG.md data/README.md
    git diff <scrub>^..HEAD -- docs/ONFLY-SRS.md | grep '^+' | python -c "import sys; n=sys.stdin.read().count(chr(0x2014)); print('em dashes in added SRS lines:', n); sys.exit(1 if n else 0)"

Expected: `0` for both. The release notes and `.github/` templates are
checked the same way before publication.

**11.14 Private memory files** (slice A exit)

    cat "$ONFLY_MEMORY_DIR"/*.md | namecheck

`ONFLY_MEMORY_DIR` is the private memory directory; its path is in the
owner's private notes, not in this file.

Expected: `hits: 0` (it was 0 on 2026-09-24).

**11.15 Existing archive visits** (before item 37 is decided)

    curl -s https://archive.softwareheritage.org/api/1/origin/https://github.com/mertefesensoy/ONFLY/visits/

**11.16 This plan itself, before it is committed**

    python -c "import base64,os,re; b=os.environ['ONFLY_NAME_B64']; w=base64.b64decode(b).decode(); t=open('docs/plan/<this file>',encoding='utf-8').read(); print(re.sub('[^a-z0-9]','',t.casefold()).count(w), t.count(b))"

Expected: `0 0`.

---

## 12. Related docs

- `docs/ONFLY-SRS.md`: 1.1, 2.3, 6.4 (ACC-3, ACC-4), 8.3 and 8.4, 9.2;
  Appendix A.1 (D-35, D-50, D-62, D-126, D-132, D-164, D-202, D-205, D-261,
  D-340, D-341, D-388, D-414, D-420, D-464, D-467, D-468 to D-483, and
  D-484 to D-499 for this plan); A.2 (P-38, P-39, P-40 and P-41); B (TBD-13); D (VL-01, VL-04, VL-05, VL-12,
  VL-13, VL-63, VL-78, VL-82, VL-86, VL-88, VL-91, VL-96 to VL-98, VL-104 to
  VL-114, VL-118 to VL-137); F (glossary); G (references); NFR-LIC-01
- `docs/plan/2026-09-18-acc5-row7-path.md` and
  `docs/implementations/2026-09-18-acc5-row7-path-handover.md`: why row 7's
  `path` half is missing
- `docs/plan/2026-09-24-acc5-row7-path-resume.md`: the parallel session's
  plan (on its branch until merged)
- `docs/implementations/2026-09-25-open-source-launch-slice-a.md`: slice A's
  closing record (D-494 to D-499)
- `docs/plan/2026-09-18-a2-backlog.md`: the plan format followed here
- `docs/implementations/_TEMPLATE.md`: the doc each slice ends with
- `data/networks/MANIFEST.json`, `data/malecns/MANIFEST.json`,
  `third_party/MANIFEST.md`, `reference/shiu/LICENSE`, `tools/lint_lic.py`,
  `engine/include/onfplat.h`, `tools/fixtures.py`: sources for slices C and E
- `docs/status/2026-09-24-status.md`: today's status snapshot (untracked)
