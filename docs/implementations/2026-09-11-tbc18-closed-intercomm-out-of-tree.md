# 2026-09-11 — TBC-18 closed: INTERCOMM stays out of the tree

| Field | Value |
|---|---|
| Date | 2026-09-11 |
| Author | Claude (ONFLY senior engineer session) |
| Phase / gate | Phase G (transaction demonstrator, second MVP) |
| Owner decisions relied on | D-62 (MIT), D-130, D-131, **D-132** |
| Requirements touched | NFR-LIC-01 |
| Open items closed | **TBC-18** |

## 1. Problem / motivation

D-131 chose INTERCOMM on TK5 to drive Phase G's 3270. That made TBC-18
blocking: the SRS already required it settled *before any transaction code is
written*, and Phase G now depends on INTERCOMM.

TBC-18 asked whether an ONFLY subsystem using INTERCOMM's macros and copybooks
is a derivative work under its noncommercial-only clause. Until it was settled,
no Phase G code could be written at all.

The failure this prevents is not a build break. It is shipping a repository
whose MIT licence makes a promise the project has no right to make — every
recipient of an MIT work may use it commercially, and INTERCOMM forbids exactly
that for derivative works. That kind of defect is invisible in testing, survives
indefinitely, and is expensive to unwind once other people have relied on it.

## 2. What changed

| File | Change |
|---|---|
| `docs/ONFLY-SRS.md` | Added VL-38 (the actual licence text and the collision) and D-132 (the resolution); struck TBC-18 in Appendix B; unblocked the Phase G row; corrected "Tetragon Software LLC" to "Tetragon LLC". |
| `tools/lint_lic.py` | New. Scans tracked source files for INTERCOMM-derived names and fails the build if any appear. |
| `Makefile` | Added the `liclint` target and made `test` depend on it. |
| `.gitignore` | Ignore `local/`, the directory the INTERCOMM shim lives in. |

## 3. Implementation approach

**Getting the facts first.** The terms do not ship with the TK5 package —
`Packages/intercomm/` holds a job log and a DASD volume, and no licence file
exists anywhere in the lab directory. They live in the front matter of the
INTERCOMM manuals, and were read from the Release 11 DSECTS manual (September
1998). This matters because the SRS had been characterising the licence from
memory, and got the copyright holder's name wrong.

**The check.** `tools/lint_lic.py` scans `git ls-files` output — tracked files
only — for a list of INTERCOMM macro, copybook and service names taken from the
Release 11 DSECTS list. Contract: no side effects; exit 0 clean, 1 on a finding,
2 if git cannot be run. Findings print path, line, the matched name and the line
text.

Three details that are load-bearing rather than incidental:

- **Tracked files only.** Untracked and ignored files are exactly where this
  material is *supposed* to live. Flagging `local/` would be backwards.
- **Word boundaries.** `GETV` is an INTERCOMM service; `GETVAL` is not, and
  `FEOV` must not match `FOREVER`. Both were verified as negative controls.
- **A narrow path exemption.** The SRS, the implementation docs and the linter
  itself all name these macros in order to *explain* the rule. Prose about
  INTERCOMM is not a derivative work of it. The exemption is by exact path plus
  `docs/implementations/`, deliberately narrow — widening it is how this check
  would quietly stop working.

## 4. Mathematical / numerical details

None — this is a structural and licensing change.

## 5. Design decisions

**Why remove the question instead of answering it (D-132).** Whether a given
file is a derivative work is a legal question, not an engineering one, and I am
not in a position to answer it. But it only needs answering if INTERCOMM-derived
material enters the MIT tree — and D-130 had already made that avoidable, by
putting ONFLY's real transaction source in `EXEC CICS`. The INTERCOMM side is
demonstration scaffolding, not product. Keeping scaffolding out of the
repository costs nothing that matters and eliminates the conflict outright.

**Alternatives the owner rejected**, recorded in D-132 with their reasons: a
separate non-MIT subtree carrying Tetragon's notice (keeps the demo reproducible
from a clone, but ONFLY stops being cleanly MIT and users of that subtree
inherit the non-commercial limit); relicensing the whole repository
non-commercial (reverses D-62 and buys less clarity than it appears to, since
the vendored SoftFloat and TestFloat stay three-clause BSD either way); writing
to Tetragon LLC for clarification (blocks Phase G on an outside party, with no
published interpretation of the clause to work from).

**Why a linter rather than a note in the SRS.** A licensing rule kept only in
prose gets broken six months later by someone pasting in a copybook to save an
afternoon, and the breach is invisible in review because the file looks like
ordinary COBOL. The check is not clever and does not need to be: it recognises
names, not derivation, and someone determined to paste INTERCOMM code in while
renaming everything will get past it. It catches the realistic failure, which is
the careless one.

**The cost, stated rather than discovered later.** Phase G's 3270 demonstration
will **not be reproducible from a clone** of this repository. Anyone wanting to
reproduce it must obtain INTERCOMM themselves from TK5 and rebuild the shim from
the documented layouts. That is the price of D-132 and it is the owner's
accepted trade.

## 6. Verification

```bash
mingw32-make liclint
```

Expected: `lint_lic: ok -- no INTERCOMM-derived names in the tree (D-132)`,
exit 0. Observed on 2026-09-11 across 752 tracked source files.

**Negative control** — the check must be shown to fail, not just to pass:

```bash
printf '       01 X.\n           COPY MSGHDR.\n' > tests/tmp_lic_probe.cbl
git add tests/tmp_lic_probe.cbl
python tools/lint_lic.py            # expect exit 1 and a MSGHDR finding
git rm --cached tests/tmp_lic_probe.cbl && rm tests/tmp_lic_probe.cbl
```

Observed: exit 1, reporting `tests/tmp_lic_probe.cbl:2  MSGHDR`. The same probe
file also contained `ONF-GETVAL` and `ONF-FOREVER-FLAG`, neither of which was
flagged — confirming the word boundaries hold against `GETV` and `FEOV`.

`liclint` is a dependency of `make test`, so it runs in every full build.

## 7. Related docs

- `docs/ONFLY-SRS.md` — VL-38 (the licence text and the collision), D-132 (the
  resolution), D-130 / D-131 (why INTERCOMM is in Phase G at all), D-62 (MIT),
  NFR-LIC-01, Appendix B TBC-18 (struck).
- `docs/implementations/2026-09-11-raincode-cics-probes-measured.md` — VL-37,
  the measurement that led to D-130 and D-131.
