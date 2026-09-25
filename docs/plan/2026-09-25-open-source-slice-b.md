# Plan: P-41 slice B, the name scrub, the wording-policy row and the guard (2026-09-25)

| Field | Value |
|---|---|
| Scope | D-500: slice B of `docs/plan/2026-09-24-open-source-launch.md` (P-41, approved by D-488) |
| Decisions it rests on | D-484 forward scrub only, D-485 summary removed, D-486 neutral wording in place, D-495 two rows, D-501 push, D-502 `.docx` regenerated, D-503 salted digest, D-504 push B at once, D-505 email left as written |
| Proposal | P-42 |
| Not a phase | No Section 9 phase opens or closes. The exit is P-41's own: 11.1, 11.2, 11.3, the guard's self-test and the hook checks of 11.10 |

**Baseline, measured this session with P-41's 11.1 on 2529abf:** 32
occurrences in 10 files, 23 in Markdown and 9 in the two `.docx` files. This
matches the figure P-41 recorded on 9ad60e9. No ordinary word in the tree
contains the token today; every hit is the name itself.

No command in this plan contains the name in any encoding. Scans read it
from `ONFLY_NAME_B64`, set in the shell from private notes.

## Slice 1: the guard, test first (B4)

`tools/lint_name.py` (name to be confirmed), in the style of
`tools/lint_lic.py`, 80 columns (the `col80` target walks `tools/`).

* **Engine.** The text is decoded one line at a time: NFKC, casefold, HTML
  entities unescaped, `%XX` unquoted. That is 11.0's order, and no entity or
  escape spans a line, so the result equals 11.0's. A *word* is a maximal run
  of `[a-z0-9]` in the decoded text. The *stream* is the words concatenated
  across lines, so a token split by a line break, a soft hyphen, a zero-width
  space, emphasis or an entity is still one run in the stream.
* **Match without the word (D-503).** Every window of the token's length in
  the stream is hashed as `sha256(salt + window)` and compared with one stored
  digest. Each distinct window is hashed once per run, so a whole-tree scan
  of the 23.8 MB tree is a few seconds, not a minute.
* **Allowlist.** A few ordinary English words contain the token. They are
  stored only as salted digests, like the token, and no text names them
  (D-503). A hit passes only when it lies wholly inside one word whose digest
  is on the list. A hit spanning two words never passes, which is what makes
  "the" followed by the name fail even though the two run together in the
  stream.
* **Office files.** Every member of a `.docx`, `.xlsx` or `.pptx` zip,
  `.rels` included; Word text is taken per paragraph and table cell, with the
  runs inside one paragraph joined, so a name split across two runs is one
  word.
* **Modes.** `--tree` scans every tracked path and file, as 11.1 does;
  `--staged` scans only added lines of `git diff --cached -U0`, joined per
  hunk, plus the index blob of any staged binary or Office file and every
  added path; `--message FILE` scans a commit message; `--install-hooks`
  copies the guard into the common git directory (`git rev-parse
  --git-common-dir`) and writes `pre-commit` and `commit-msg` hooks that call
  that copy, so a worktree whose branch predates the guard is still checked.
  It refuses to overwrite a hook it did not write and fails if
  `core.hooksPath` is set.
* **Fails closed.** Any read, unzip or git error exits 2, and so does a
  disagreement between the whole-text count (11.0's rule) and the per-line
  count. The hooks exit non-zero when Python is missing.
* **Output.** Path, line and count only, never the matched text (CI logs are
  public, P-41).
* **Self-test, written first and shown failing.** The engine is exercised
  with a synthetic token and a synthetic allowlisted word built at run time,
  so the self-test needs no secret and states no word. It must catch the
  token plain, after "the", in upper case, prefixed with "Z", and split by a
  no-break space, a zero-width space, a soft hyphen, a line break, Markdown
  emphasis, an HTML entity and a `%XX` escape, inside a `.docx` split across
  two runs, and in a path; and it must pass the allowlisted word and its
  capitalised form. With `ONFLY_NAME_B64` set it also checks that the stored
  digest is the real token's and that the real token, plain and split, is
  caught.
* **Makefile.** A `namelint` target, `$(PYTHON) tools/lint_name.py
  --self-test --tree`, joins `test` beside `liclint`.

## Slice 2: the scrub (B1, B2, B3)

* **B1.** A one-off script under the scratchpad, reading `ONFLY_NAME_B64`,
  replaces each of the 21 Markdown occurrences that remain after B2 with the
  text below, and fails unless it made exactly that many replacements. The
  old-to-new map is written to private notes only (P-41 B3).
* **B2.** `git rm ONFLY-IBM-Summary.md ONFLY-IBM-Summary.docx` (D-485).
  `docs/ONFLY-SRS.docx` is regenerated from the final SRS by `node md2docx.js
  docs/ONFLY-SRS.md docs/ONFLY-SRS.docx srs "<the SRS's own version line>"`
  as the last edit before the commit (D-502).
* **B3.** The wording-policy row, P-41's text unchanged, as its own D-row
  (D-495).

The new text, by place. Old text is not shown here.

| Place | New text |
|---|---|
| SRS 1.1 | "...can later run on z/OS (the hosted IBM Z environment the project plans to request) and behind IBM CICS transactions." |
| SRS 2.3, platform column | "z/OS on the hosted IBM Z environment the project plans to request" |
| SRS 2.5, C-07 | "The hosted IBM Z environment the project plans to request does not allow the user to define CICS programs or transactions." |
| SRS 9.2, Phase F | "Port to the hosted IBM Z environment the project plans to request; determinism row 8" |
| D-01, decision | "...before moving to the hosted IBM Z environment the project plans to request; request project permissions with the MVP in hand" |
| D-01, alternatives | "Start directly on the hosted IBM Z environment the project plans to request" |
| D-23 | "...since the hosted IBM Z environment the project plans to request allows no CICS resource definition, the design is batch-first..." |
| D-296 | "...and F additionally on the IBM Z access request, which has not been granted" |
| D-437, alternatives | "...begin Phase F on the hosted IBM Z environment the project plans to request" |
| D-437, rationale | "Phase F is recorded as blocked on the IBM Z access request, which D-126 makes **with Phase G in hand**, so closing Phase G is also what unblocks it" |
| D-442 | "...and D-126's condition for the IBM Z access request -- made with Phase G in hand -- is met" |
| D-444 | "...begin Phase F on the hosted IBM Z environment the project plans to request, whose whole output with no access granted would be a permissions request rather than running code" |
| D-458 | "...start Phase F (z/OS), which Section 9.2 gates on the IBM Z access request, which the engineer cannot grant" |
| P-34 | "...and D-126 makes the IBM Z access request **with Phase G in hand**, so the missing marker..." |
| TBD-13 | "...where does a real CICS come from for Phase H? The hosted IBM Z environment the project plans to request allows no CICS resource definition (D-23), so it is still open" |
| `docs/implementations/2026-09-18-a2-backlog.md` | "...and F blocked on the IBM Z access request, which has not been granted, the backlog was..." |
| `docs/implementations/2026-09-18-acc5-row7-path.md` | "...and Phase F blocked on the IBM Z access request, which has not been granted, this was the largest..." |
| `docs/implementations/2026-09-18-phase-g-closure.md` | "D-126 makes the IBM Z access request **with Phase G in hand**..." |
| `docs/plan/2026-09-18-acc5-row7-path.md` | "...and Phase F cannot start until the IBM Z access request is granted." |
| `docs/plan/2026-09-18-phase-g-closure.md` | "Phase F is blocked on the IBM Z access request, and D-126 says the permissions request is made **with Phase G in hand**." |
| `docs/status/2026-09-16-status.md`, row F | "Needs the IBM Z access request granted; D-126 makes that request with Phase G in hand" |

Every other word of every edited row stays as it is. The 13 SRS lines carry
no em dash today, so P-41's 11.13 check on added SRS lines can pass.

## Slice 3: verify

1. 11.1 on the commit: `total 0`, exit 0. 11.2 on untracked files: `hits: 0`.
2. `python tools/lint_name.py --self-test`, with and without `ONFLY_NAME_B64`.
3. `python tools/lint_name.py --install-hooks`; `git config --get-all
   core.hooksPath` prints nothing; then, in a throwaway `git worktree add`, a
   commit adding a sample built from `ONFLY_NAME_B64` and a commit whose
   message carries it are both rejected, and the worktree is removed.
4. 11.13 on the added files and the added SRS lines: `0` and `0`.
5. `mingw32-make fixtures` and then `mingw32-make test`, which now includes
   `namelint`: exit 0 on SOFT3E, SOFT2C and NATIVE.

## Slice 4: record, commit, push (B6)

The implementation doc `docs/implementations/2026-09-25-open-source-launch-slice-b.md`;
P-41 marks slice B COMPLETE with its exit evidence and items 14, 30, 31 and 36
closed; P-42 struck as approved; the memory file updated. One commit, then
`main` fast-forwarded and pushed (D-501, D-504), then 11.3 over
`<scrub>^..origin/main`: `hits: 0`.

## Not in this plan

* **The name is not gone.** It stays in git history, the PR refs, GitHub's
  caches and every earlier clone (D-484); slice B changes what the current
  tree says, and nothing more is ever claimed.
* **CI** scanning of the whole tree and the pushed range is slice F. Until
  then the guard runs only where its hooks are installed and in `make test`.
* **Not covered by the hooks:** commits made in the GitHub web UI; messages
  carried over by cherry-pick or rebase, where `commit-msg` does not fire;
  issue, PR, release and tag text; images; a name split across an unchanged
  line and an added one.
* **Paraphrase.** The guard recognises the token, not a description of the
  program.
* **The SRS's pointers to the removed summary** (SRS 1.1 and the 2.4 reader
  row) stay until slice D5 rewrites the reader classes (item 17).
* **The regenerated `.docx`** is an export; its layout is not reviewed, and
  it will drift from the Markdown again until slice D or a later D-row
  settles how exports are produced.
