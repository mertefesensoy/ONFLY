# 2026-09-25: Slice A of the open-source launch plan closes

| Field | Value |
|---|---|
| Date | 2026-09-25 |
| Author | Mert Efe Sensoy |
| Phase / gate | None. Slice A of P-41, the open-source launch plan, between Phase G (COMPLETE, D-442) and Phase F (waiting on the IBM Z access request) |
| Owner decisions relied on | D-484 to D-499, recorded by this change; D-126, D-479, D-480 |
| Requirements touched | None changed. Cited: ACC-5, Section 8.3 |
| Open items closed | None in Appendix B. P-41's own open items 2, 3, 6 and 42 |

## 1. Problem / motivation

P-41 was drafted on 2026-09-24 while a parallel session was writing to this
SRS. So the owner's ten answers from that day (OA-1 to OA-10) could not become
decision rows without risking a number clash, and one clash had already
happened: the plan was drafted as P-40, and the parallel session used P-40 for
a different proposal (D-480). Slice A of the plan exists to wait for that
session, take its work in, and only then give the answers their numbers.

On 2026-09-25 the owner reported the parallel session's work done. Without
this change, slice B would rest on answers recorded only in a plan file, and
Appendix A.2 would not list the plan of record at all.

## 2. What changed

| File | Change |
|---|---|
| `docs/ONFLY-SRS.md` | Sixteen new rows, D-484 to D-499, after D-483 in Appendix A.1, and ~~P-41~~ after ~~P-40~~ in Appendix A.2. No other line changed: the diff is 17 insertions and 0 deletions. |
| `docs/plan/2026-09-24-open-source-launch.md` | Header and status: approved by D-488, slice A COMPLETE by D-494, P-41 confirmed. Each answer mapped to its row (OA-1 is D-484 through OA-10 is D-493). Slice A marked complete with its exit evidence. Open items 2, 6 and 42 closed with their rows. The claims register (CAN-02, MUST-NOT 8) and replication rung R4 brought in line with VL-138. Two table cells repaired. Name baseline at 9ad60e9 added. |
| `docs/implementations/2026-09-25-open-source-launch-slice-a.md` | New: this record. |

The merge commit 7cb7389 also brought `main`'s eight new commits into the
branch: D-468 to D-483, VL-138, the row 7 `path` recording, `tools/row7amend.py`
and the row 7 resume plan and implementation doc.

## 3. Implementation approach

1. **State first.** A fetch showed `origin/main` at 9ad60e9, equal to the
   parallel branch. Its session was idle in the session list. The highest
   numbers in use were D-483 and P-40. The branch and `main` changed no path in
   common, so a merge could not conflict.
2. **Merge, not rebase (D-498).** `git merge --no-ff origin/main` produced
   7cb7389. The branch's six earlier commits, which P-41 and two other documents
   cite by ID, stay reachable.
3. **Records written by a checking script.** Every targeted replacement had to
   match exactly once, and every new A.1 row had to have four cells (A.2: three).
   The script refused to reuse a number already present, and refused to write
   if the program's name or an em dash appeared. Nothing is written unless every
   check passes.
4. **Checked again independently** by a second script (Section 6).

## 4. Mathematical / numerical details

Omitted: this change records decisions and updates a plan. It derives no
figure; the figures it quotes come from VL-13, VL-91 and VL-138.

## 5. Design decisions

- **Merge rather than rebase (D-498).** The plan's A3 step said "rebase". A
  rebase would have rewritten six pushed commits whose IDs the plan, its first
  implementation doc and the 2026-09-24 status snapshot cite. The owner chose
  the merge, accepting `main`'s first merge commit.
- **Two rows for item 42 (D-495).** D-486 records the answer now. The
  wording-policy row is written with the scrub itself in slice B3, so the rule
  appears in the record at the same time as the text it governs.
- **Every answer gets its own row, including the session-scoped OA-7 (D-490).**
  This follows D-443, D-446 and D-460, which record each session's git reach.
- **A row for a direct instruction (D-499).** The fast-forward of `main` on
  2026-09-24 was instructed in plain chat, not through AskUserQuestion. It is
  recorded because it changed `main`, as D-467 recorded a direct instruction.
- **Item 6 closed as (a) (D-497), with its caveat kept.** The green runs are
  the parallel session's records. Slice E2 still has to show that the four
  checks masked by `tail -1` can fail.
- **The claims register follows the record, not a decision.** VL-138 made
  "JCC 5 of 19" false, so CAN-02, MUST-NOT 8 and rung R4 were brought into line.
  Public copy is written from the register, so it must never lag the SRS.
- **Pipes in table cells.** GitHub splits a table row on `|` even inside a code
  span. This SRS escapes all 18 such pipes, and two cells in P-41 did not; they
  now use `\|`.

## 6. Verification

Run in this session on x86-64 Windows 11 with Python 3.13 and git. No build,
no test suite and no lab was run.

- **Slice A exit (P-41):**
  - `git rev-list --count origin/main..origin/claude/onfly-senior-engineer-ac25b2`
    gave `0`;
  - `git cherry origin/main origin/claude/onfly-senior-engineer-ac25b2 | grep -c '^+'`
    gave `0`;
  - `git show origin/main:docs/ONFLY-SRS.md | grep -c '^| D-480 '` gave `1`.
- **Name baseline for slice B:** the plan's 11.1 scan of `main` at 9ad60e9 gave
  `TREE origin/main: 32 occurrences in 10 files`. The private memory files gave
  `0` (11.14).
- **The new records:** the checking script printed
  `SRS: inserted 16 A.1 rows after D-483 and ~~P-41~~ after ~~P-40~~`. The
  independent script printed:
  - `A.1 new rows with 4 cells: True` and `P-41 row cells: 3`;
  - `added lines: name 0 | em dashes 0`;
  - `plan: unescaped code-span pipes in table rows: []`;
  - all ten `OA-n (D-nnn)` mappings present.
- `git diff --check` reported nothing.

**What this does not prove.**
- D-497's green `make test` runs come from the parallel session's record
  (`docs/implementations/2026-09-24-acc5-row7-path-resume.md`), not from this
  session. The only suite code run here is `tests/run_mvsjcc.py` on e2ab256,
  on 2026-09-24 (D-499).
- The name scan covers text and the members of Office zip files, not images.
- The parallel session's own results, D-468 to D-483, are cited, not re-checked.

## 7. Related docs

- `docs/plan/2026-09-24-open-source-launch.md`: P-41, the plan of record
- `docs/implementations/2026-09-24-open-source-launch-plan.md`: how the plan
  was drafted
- `docs/implementations/2026-09-24-acc5-row7-path-resume.md`: VL-138 and the
  recorded green runs D-497 relies on
- `docs/status/2026-09-24-status.md`: the status snapshot this change moves on
  from
- `docs/ONFLY-SRS.md`: Appendix A.1 (D-484 to D-499), Appendix A.2 (P-41),
  Section 8.3
