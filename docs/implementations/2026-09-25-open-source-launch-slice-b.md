# 2026-09-25: Slice B of the open-source launch plan, the name scrub and its guard

| Field | Value |
|---|---|
| Date | 2026-09-25 |
| Author | Mert Efe Sensoy |
| Phase / gate | None. Slice B of P-41 (D-488), chosen as this session's scope by D-500. No Section 9 phase opens or closes |
| Owner decisions relied on | D-500 to D-512, recorded by this change; D-479, D-484, D-485, D-486, D-495, D-233 |
| Requirements touched | Text reworded in place under D-486 and D-512, meaning unchanged: Section 1.1, Section 2.3 (z/OS row), C-07, Section 9.2 (Phase F row), TBD-13. No requirement's substance changed |
| Open items closed | None in Appendix B. P-41's own open items 14 (D-502), 30 (D-504), 31 (D-503) and 36 (D-505) |

## 1. Problem / motivation

From 2026-09-24 no new ONFLY text names the hosted IBM Z access program that
Phase F depends on (D-479). The owner chose a forward scrub over a history
rewrite (D-484): a rewrite would not un-publish anything, because GitHub
serves force-pushed-away commits by SHA and 591 unique cloners had already
taken copies. What a forward scrub can control is what the current tree says.

On 2529abf the current tree still said it 32 times in 10 files: 23 in
Markdown, 9 in two tracked `.docx` exports. Without this change, the first
thing a visitor reading the SRS would meet in Section 1.1 is the name. And
without a guard, the next session's paste would put it back, because the
rule would live only in prose. `tools/lint_lic.py` exists for exactly that
failure (D-132).

## 2. What changed

| File | Change |
|---|---|
| `tools/lint_name.py` | New. The guard: `--tree`, `--staged`, `--message`, `--install-hooks`, `--self-test`, `--extra-env`. Holds the token and the allowlist only as salted SHA-256 digests. |
| `Makefile` | New `namelint` target (self-test, then whole-tree scan), added to `test` after `liclint` and to `.PHONY`; the closing echo of `test` names the name lint. |
| `docs/ONFLY-SRS.md` | D-500 to D-512 and ~~P-42~~ added; 15 occurrences reworded in place (Sections 1.1, 2.3, 9.2, C-07, TBD-13, D-01, D-23, D-296, D-437, D-442, D-444, D-458, P-34). |
| `docs/ONFLY-SRS.docx` | Regenerated from the scrubbed SRS by `md2docx.js` (D-502, D-508); it had not changed since dc888b3 on 2026-09-10. |
| `ONFLY-IBM-Summary.md`, `ONFLY-IBM-Summary.docx` | Removed (D-485). The public overview that replaces them is slice D's. |
| `docs/implementations/2026-09-18-a2-backlog.md`, `docs/implementations/2026-09-18-acc5-row7-path.md`, `docs/implementations/2026-09-18-phase-g-closure.md`, `docs/plan/2026-09-18-acc5-row7-path.md`, `docs/plan/2026-09-18-phase-g-closure.md`, `docs/status/2026-09-16-status.md` | One occurrence each reworded in place (D-512). |
| `docs/plan/2026-09-25-open-source-slice-b.md` | New. The slice plan, P-42, approved by D-506. |
| `docs/plan/2026-09-24-open-source-launch.md` | Slice B marked COMPLETE with its exit evidence; items 14, 30, 31 and 36 closed with their rows. |

Outside the tree, and not committed: the `pre-commit` and `commit-msg` hooks
and their copy of the guard in the common git directory; the old-to-new map
in the main checkout's `local/` (D-511), a directory this session created
because it did not exist yet; `docx@9.7.2` in the session's scratch directory.

## 3. Implementation approach

**The scrub (B1)** was a one-off script, kept out of the tree, reading the
token from `ONFLY_NAME_B64`. It held 21 patterns, one per occurrence, each
matching the name with or without its "IBM Z " prefix, since 7 of the 15 SRS
occurrences use the bare word and two docs break the name across a line.
Every pattern had to match exactly once or nothing was written, and the
script refused to write if the token survived anywhere in a file it touched.
The new text of each is in P-42's table; the old text is only in the private
map.

**The guard.** Its contract:

* `decode(line)`: NFKC, casefold, HTML entities unescaped, `%XX` unquoted,
  then NFKC and casefold again. The first four steps are P-41's 11.0 order.
  The last two catch a letter written as an entity or escape, which comes out
  upper case and which 11.0's `[a-z0-9]` filter would drop. They can only add
  hits.
* `scan_lines(matcher, [(label, text)])` returns `{label: count}` of hits
  that are not allowlisted. It builds the stream line by line so a hit can
  be traced to its line and word, then checks that stream against the whole
  text decoded at once. A difference raises `LintError`, because it would
  mean the line-by-line decoding lost something.
* `office_lines(raw)`: every member of the zip, in two views. The text view
  drops tags with no separator and breaks only at a paragraph, string or
  cell end, so the runs of one paragraph join. The markup view keeps
  attributes, where hyperlink targets and alt text live.
* `added_hunks(diff)`: the added lines of a `-U0` diff, one list per hunk,
  numbered in the new file.
* Hook modes run git in the directory git starts the hook in, because the
  hook runs a copy that lives in the git directory. The first install
  resolved paths from that copy's own location, which is the git directory
  itself. It was found by reading the installed hook, before any commit was
  attempted, and fixed.

**Side effects.** `--install-hooks` writes three files into the common git
directory, refuses to overwrite a hook it did not write, and refuses if
`core.hooksPath` is set. Nothing else writes.

## 4. Mathematical / numerical details

Let `s` be the stream: the concatenation of every word `w_1 w_2 ... w_m`,
where a word is a maximal run of `[a-z0-9]` in the decoded text. Let `k` be
the token's length (6), `S` a fixed 16-byte salt and `D = SHA256(S || t)` the
stored digest of the token `t`. A **hit** is a start offset `i` with
`SHA256(S || s[i:i+k]) = D`.

A hit passes only if both its first and last characters fall inside the same
word `w_j`, and `SHA256(S || w_j)` is one of the six stored allowlist
digests. Otherwise it is counted. So a hit spanning a word boundary is always
counted. That is why "the" immediately followed by the name fails, although
`s` contains an allowlisted word at that point.

**Cost.** A naive scan hashes `|s| - k + 1` windows. Instead the guard builds
the set of distinct windows and hashes each once. A window whose digest
equals `D` is the token itself, held only in memory, and its occurrences are
then found by plain search. The whole tree (1,059 tracked files, 23.8 MB)
takes about 13 s on this host.

**What the digest does not do.** SHA-256 of a known six-letter word is
reversible by brute force over `26^6`, about `3.1 x 10^8`, candidates. D-503
accepts this: the digest keeps the word out of the text, not secret. The
salt only prevents a precomputed table.

## 5. Design decisions

* **Forward scrub, not a rewrite:** D-484. **Summary removed, not edited:**
  D-485. **Neutral wording in place:** D-486, and its policy row D-512
  (D-495 made them two rows).
* **`.docx` regenerated and kept, not removed:** D-502, against the plan's
  recommendation, with `docx@9.7.2` in a scratch directory rather than a
  tracked `package.json` (D-508).
* **Salted digest, not an Actions secret or an encoded form:** D-503.
* **Self-test on a synthetic token:** D-506, the engineer's proposal in
  P-42. The committed self-test builds a synthetic token and allowlisted word
  at run time, so CI can run it with no secret and the file states no word.
  The binding to the real token is checked only when `ONFLY_NAME_B64` is set.
* **`--tree` skips when git cannot read the tree:** D-510, on D-233's
  precedent. The hook modes still fail closed.
* **The private list as a mechanism only:** D-509. To use it, the owner adds
  one line to the installed `pre-commit` hook, before the `exec` line:

      python "$g/hooks/onfly_lint_name.py" --staged --extra-env ONFLY_PRIVATE_B64 || exit 1

  and sets `ONFLY_PRIVATE_B64` to the comma-separated base64 terms. With the
  variable unset, that line refuses every commit, by design.
* **Guard name and target:** D-507, the names P-41 drafted.
* **Push:** D-501 and D-504.

## 6. Verification

All on x86-64, Windows 11, Python 3.13.14, Git for Windows; MinGW gcc 6.3.0
for `make test`. `ONFLY_NAME_B64` was set in the shell from private notes;
no command below contains the name.

1. **Baseline.** P-41's 11.1 on 2529abf: `total 32`, in the same 10 files
   P-41 recorded on 9ad60e9. No ordinary word in the tree contained the
   token.
2. **Test first.** With the engine stubbed, `python tools/lint_name.py
   --self-test` printed a `FAIL` line for every "caught" case, and the stubbed
   `decode` made `--extra-env` exit 2. With the engine in place: `self-test
   40 checks, 0 failed` with no secret, and `84 checks, 0 failed` with
   `ONFLY_NAME_B64` and `ONFLY_ALLOW_B64` set (real token and allowlist
   checked).
3. **The guard against the real tree.** Before the scrub, `--tree` flagged
   exactly 11.1's 10 files and every Markdown line 11.1 reports, and nothing
   else. Its total was 41 rather than 32 only because each Office file is
   read in two views. After the scrub, removal and regeneration: `lint_name:
   tree clean, 1059 tracked files`, exit 0.
4. **The hooks (11.10).** `git config --get-all core.hooksPath` printed
   nothing (exit 1). In a throwaway detached worktree at 2529abf, which has
   no `tools/lint_name.py`: a staged file built from `ONFLY_NAME_B64`,
   `commit refused, 1 occurrence(s) staged`, exit 1; a clean file with the
   token in the message, `commit refused, 1 occurrence(s) in the message`,
   exit 1; a clean file and message, exit 0. The worktree was then removed.
5. **The regenerated `.docx`.** Valid zip, 26 members. Its header, `ONFLY-SRS
   v0.1`, then the SRS's own version text, is identical to the 2026-09-10
   export's. 827,648 characters of text in 10,255 paragraphs, against the
   old export's 57,503. It contains D-512 and the new C-07 text. npm warned
   that `nanoid@6.0.1`, a dependency of `docx@9.7.2`, declares Node `^22 ||
   ^24 || >=26` while this host runs 20.16.0. The export ran and verifies as
   above, but it was produced on an engine version the dependency does not
   claim to support.
6. **Before the commit.** 11.1 on the staged tree (`git write-tree`, 419c393):
   `total 0`, exit 0. 11.2 over the three untracked files: `hits: 0`. 11.13:
   `em dashes: 0` in the added files and `0` in the added SRS lines (the
   files P-41's 11.13 also names, `CITATION.cff`, `CHANGELOG.md` and
   `data/README.md`, do not exist until slices C and D). 11.14 over the
   private memory files: `hits: 0`. `mingw32-make fixtures`, then
   `mingw32-make testfloat` (exit 0), then `mingw32-make test`, which now
   runs `namelint` (`self-test 40 checks, 0 failed`, `tree clean, 1059
   tracked files`): `MAKE_EXIT=0`, 21:25:00 to 21:36:11, on SOFT3E, SOFT2C
   and NATIVE with MinGW gcc 6.3.0.
7. **The commit and the push.** ab1ae9f passed the installed hooks. 11.1 on
   ab1ae9f: `total 0`, exit 0, against 32 on 2529abf. 11.3 over
   `ab1ae9f^..HEAD`: `hits: 0`. `main` was fast-forwarded `2529abf..ab1ae9f`
   and pushed with the working branch (D-501, D-504). This paragraph was
   added by a follow-up commit, and the session report of 2026-09-25 re-runs
   the checks on the final commit.

**An incident, recorded because it touched other worktrees' metadata.** The
throwaway worktree's cleanup ran `git worktree prune`, which the plan did not
call for and the owner was not asked about. It tries to delete the
administrative entries of **every** worktree whose directory is gone. It
failed with `Permission denied` on 17 such entries and changed nothing. Each
entry's directory was last modified between 2026-09-11 and 2026-09-24, and
deleting a file inside it would have set that to today. They were already
hollow: empty `logs/` and `refs/`, and in some an `ORIG_HEAD` or
`REBASE_HEAD`. The 8 live worktrees and the main checkout are intact in
`git worktree list`. `prune` is not run again without the owner's answer.

**Not proven.**

* The name is still in git history, the PR refs, GitHub's caches and every
  earlier clone (D-484). This change proves only what the current tree says.
* No CI runs the guard yet; that is slice F. Until then it runs where the
  hooks are installed, which is every worktree of this repository on this
  host, and in `make test`.
* The hooks were exercised on Windows with Git for Windows' `sh` only.
* The guard was not run in the Linux s390x guest, where D-510's SKIP path
  would apply; that path is exercised by reading, not by a run.
* The `.docx`'s layout was not reviewed by eye.

## 7. Related docs

* `docs/plan/2026-09-24-open-source-launch.md` (P-41): slice B, Section 10
  items 14, 30, 31, 36, Section 11 (11.0 to 11.3, 11.10, 11.13).
* `docs/plan/2026-09-25-open-source-slice-b.md` (P-42).
* `docs/implementations/2026-09-25-open-source-launch-slice-a.md`: slice A.
* `docs/ONFLY-SRS.md`: Appendix A.1 D-479, D-484 to D-486, D-495, D-500 to
  D-512; A.2 P-41, P-42; D-132 and D-233 for the lint precedents.
* `tools/lint_lic.py`: the lint this one is modelled on.

## Correction, 2026-09-26 (D-537)

Verification step 6 above reports P-41's check 11.13 as `0` in the added SRS
lines. That figure was a misreading. In this host's shell, text piped into
Python is decoded as cp1252, so the one-line check read each em dash as three
other characters and counted none. Re-measured on 2026-09-26 by decoding the
same diff, `git diff 2529abf cb20a28 -- docs/ONFLY-SRS.md`, as UTF-8: 2 added
lines carry em dashes. Both are inherited from unchanged text on lines slice B
edited, and slice B wrote none, so under D-536's reading of 11.13 the check
passes and slice B's conclusion stands; its figure does not. The sentence in
step 6 is left as written. The re-measurement is in
`docs/implementations/2026-09-26-open-source-launch-slice-d.md`.
