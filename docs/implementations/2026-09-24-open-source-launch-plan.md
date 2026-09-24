# 2026-09-24: The open-source launch plan, before Phase F

| Field | Value |
|---|---|
| Date | 2026-09-24 |
| Author | Mert Efe Sensoy |
| Phase / gate | None. Planning work between Phase G (COMPLETE, D-442) and Phase F (blocked on IBM Z access the project does not have) |
| Owner decisions relied on | OA-1 to OA-10 of 2026-09-24 (numbered O-1 to O-10 until the same day's renumbering), recorded in the plan's Section 0.1 and numbered as D-rows at its slice A3; D-126, D-132, D-50, D-62; D-478 and D-479 (on the parallel branch) |
| Requirements touched | None changed. Cited: NFR-LIC-01, ACC-1 to ACC-7, Section 8.3 |
| Open items closed | none |

## 1. Problem / motivation

The owner wants ONFLY launched as a professional open-source project before
the IBM Z access request is made, so that other people can replicate its
results first. The name of the hosted IBM Z access program must not appear in
any public documentation. Public documents must also say plainly that the
project has no IBM Z access yet.

Checking the ground before planning changed the task. The repository has been
public on GitHub since 2026-09-10. It has no README, and a stale access pitch
at its root names the program. The name appears in 8 tracked Markdown files,
in both tracked `.docx` files and in 2 commit messages. A fresh clone cannot
replicate anything: `make test` cannot pass, and the networks are gitignored.
So the work became a plan to **launch an already open repository truthfully**,
not to open one. The plan is `docs/plan/2026-09-24-open-source-launch.md`.

## 2. What changed

| File | Change |
|---|---|
| `docs/plan/2026-09-24-open-source-launch.md` | New: the launch and outreach plan, proposal P-41 (provisional number; P-40 until the same day's renumbering), approved by the owner (OA-5) and published in full at the owner's choice (OA-6). |
| `docs/status/2026-09-24-status.md` | New: today's status snapshot, with a same-day correction about the parallel session and the red `make test`. |
| `docs/implementations/2026-09-24-open-source-launch-plan.md` | New: this record. |

No code, test, network, SRS row or generated file changed. `docs/ONFLY-SRS.md`
was deliberately not edited, because a parallel session is writing to it
(Section 5).

## 3. Implementation approach

The work had three stages, and every repository step in it was read-only.

1. **Audit.** Six independent read-only audits covered six areas: where the
   name appears, licensing and provenance, the replication path, repository
   hygiene, a register of public claims, and the outreach landscape (web
   research). A completeness critic then spot-checked their three most
   consequential findings on disk. None of them ran a build, a test or a lab.
2. **Owner questions.** Four decisions shaped the plan's structure and were
   put to the owner before drafting (OA-1 to OA-4). Three more came at approval
   (OA-5 to OA-7), and the two no-access confirmations of the plan's 3.2 came
   after it was pushed (OA-8, OA-9), followed by the Wave -1 scope for the
   IBM Community post (OA-10).
3. **Draft, critique, revise.** One draft was written. Four independent
   critics reviewed it: honesty and name leaks, licensing, engineering
   sequencing, and outreach capacity. Each returned concrete fixes, and the
   final plan applies them. The engineer then read the whole plan, corrected
   two points in it, and re-ran the leak checks of Section 6.

The plan sequences its work by reversibility. Wording, licence files,
documentation, replicability and community files come first. The tag, the
release, the Zenodo DOI, archive saves and outreach come last, each gated on
the plan's name scans passing on the exact tree or text being published.

## 4. Mathematical / numerical details

Omitted: this is a planning change. The plan's replication ladder quotes
recorded wall clocks and results from existing VL rows and does not derive
any new figure.

## 5. Design decisions

- **Scrub forward only (OA-1).** The owner chose this over a fresh public
  repository and over a filter-repo rewrite. The audit found that the rewrite
  would not un-publish anything. GitHub still serves force-pushed-away
  commits by SHA, as the parallel branch showed today. The PR refs pin the old
  history, and 591 unique cloners have taken copies. The plan therefore never
  claims that the name is gone, only that current public documents do not
  use it.
- **Rewrite the summary as a public overview (OA-2)**, written new from the
  claims register. The old text is stale and partly false, so it is not
  edited.
- **Neutral wording plus a decision row (OA-3).** The critics added one
  refinement. Where a row states a property of that one program, the
  substitute keeps a definite reference ("the hosted IBM Z environment the
  project plans to request"), so no row's claim widens to hosted IBM Z
  environments in general.
- **The name guard stores no form of the word.** The draft carried the name
  in base64, and the honesty critic caught it. The final plan reads the token
  from an environment variable, and its committed guard keeps only a salted
  digest.
- **The no-access statement is about the project, not the person.** A
  statement about the owner's own access could be read against the owner's
  IBM community activity, so the plan's wording describes what ONFLY has run
  on. It also required two confirmations before first publication, and both
  were given on 2026-09-24. OA-8: no ONFLY artifact was ever built, uploaded or
  run on any IBM Z system under any account; the only mainframe environment it
  has run on is MVS 3.8j emulated by Hercules. OA-9: the owner has no active
  IBM Z account today. The wording "the project does not have IBM Z access
  yet" therefore stands.
- **Publishing the full plan (OA-6).** The engineer recommended a private full
  plan plus a short public version, because the plan describes surfaces
  outside the repository and the scrub itself. The owner chose to publish it
  all, following the project's convention for plans of record.
- **No SRS edit today.** A parallel session holds D-468 to D-478 and P-39,
  unmerged, and is still editing the SRS. The owner answers are therefore
  recorded as OA-1 to OA-10 in the plan and become D-rows at its slice A3,
  after that branch merges. This avoids two sessions claiming the same
  decision numbers.
- **Renumbered later the same day.** The parallel session took P-40 for its
  own proposal (D-480) and added D-479 and D-480, and SRS Section 8.2 already
  uses O-1 to O-5 for the oracles. The plan therefore became P-41 (still
  provisional until the merge), its owner answers became OA-1 to OA-10, slice
  A's exit now checks for D-480, and open-decision items 2 and 3 are marked
  settled in substance (OA-8 and OA-9; D-479). The pushed commit subjects
  that say "P-40" (f2e4b2f, 4b1de9f, f8d2a05, 11c074d) cannot change and mean
  this plan; the plan's header says so.

## 6. Verification

Everything below was run on x86-64 Windows 11 with Python 3.13 in this
session. No build, test suite or lab was run.

- **The plan contains the name in no form, and no em dashes.** The checks
  counted em dashes, the name case-insensitively with every non-alphanumeric
  character removed, and its base64 form: all three were 0. This is the
  plan's own check 11.16, with the token supplied from outside the file.
- **The claims the plan rests on were re-checked by hand.**
  - `make test` cannot pass: `tests/run_mvsjcc.py:303-312` requires
    `data/phase-e/jcc/rsp-path-2c.bin`, and `git ls-files data/phase-e/jcc`
    lists only `rsp-srext-2c.bin` and two listings.
  - The repository is public: `gh repo view` returns `"visibility":"PUBLIC"`.
  - The parallel session's numbering: `grep` of its SRS shows D-468 to D-478
    and P-39.
  - The IBM Community post is live: the owner's own backlink tracker records
    it as public since 2026-09-18.

**What this does not prove.** The plan's replication, licensing and outreach
statements come from the audits' reading of the repository and of web pages.
Web-sourced facts (channel rules, dates, programme terms, other people's
affiliations) are marked "re-verify at time of use" in the plan and were not
checked on disk. No licensing statement in the plan is legal advice; its
Section 3.5 lists the six questions that need qualified input before the
release. The counts of name occurrences describe `main` at 4a25639 and the
parallel branch's f0ec691 on 2026-09-24, and are rebuilt by scan at slice B.

## 7. Related docs

- `docs/plan/2026-09-24-open-source-launch.md`: the plan (P-41, formerly P-40)
- `docs/status/2026-09-24-status.md`: today's status snapshot
- `docs/implementations/2026-09-18-acc5-row7-path-handover.md`: why row 7's
  `path` half, and so a green `make test`, is missing
- `docs/ONFLY-SRS.md`: Section 8.3, Section 9.2, Appendix A (D-126, D-132, D-50,
  D-62), NFR-LIC-01
