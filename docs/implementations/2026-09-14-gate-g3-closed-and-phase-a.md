# 2026-09-14 — Gate G3 closed, Phase A complete, and two defects found in passing

| Field | Value |
|---|---|
| Date | 2026-09-14 |
| Author | Engineer, with the owner deciding the closure and its form |
| Phase / gate | **Gate G3 — Performance (Spike S3)**; **Phase A — Foundations** (SRS Section 9) |
| Owner decisions relied on | D-248 (close G3 before marking A), D-249 (fix both defects now), D-250 (stop after), D-251 (G3 CLOSED), D-252 (Phase A COMPLETE), D-253 (correct VL-41 forward) |
| Requirements touched | NFR-PERF-01 and ACC-6 (obligation restated, not discharged); IR-NET-09 / Appendix C step 0 (why G3's figures are a lower bound) |
| Open items closed | Proposal P-12 resolved; Gate G3's missing closure |

## 1. Problem / motivation

Closing Gate G0 (D-241) left Phase A one row short of readable. Section 9.2's
Phase A row read

> G0; spikes S1–S4 — **S1 (G1), S2 (G2), S4 (G4) closed; S3 (G3) measured**

while D-246 and D-247 had just given Phases B and C completion markers in
their phase-name cells. Phase A was the only phase with no marker at all, and
the reason was one word: **G3 was "MEASURED", never "CLOSED"** — no decision
number, exactly the defect D-235 caught in G0.

The owner's instruction was to close G3 first rather than paper over it.
**Auditing it before stamping it turned out to matter**, because G3's evidence
carries a limit that its row does not mention and that bears directly on the
MVP's performance acceptance.

## 2. What changed

| File | Change |
|---|---|
| `docs/ONFLY-SRS.md` | G3's row marked CLOSED; Phase A's row marked COMPLETE with every gate's state named; D-248…D-253 in Appendix A.1; VL-90 in Appendix D. |
| `tools/mvsub.py` | `summarise()`'s alternation extracted to `KEEP_RE`, with `ABEND` anchored as `\bABEND(ED)?\b` and `COMPLETION CODE` added. |
| `tests/run_sub.py` | New. 16 cases pinning both directions of that fix. |
| `tools/fixtures.py` | New. Populates and verifies `data/networks/*.bin` in a fresh checkout. |
| `Makefile` | `sub` target (wired into `test`); `fixtures` and `fixtures-check` targets (deliberately **not** wired into `test`). |

## 3. Implementation approach

### 3.1 What G3's closure rests on, and what it does not

G3 asked one question: *how large can N and the duration be within the bound?*
It answered it — 36.6 to 40.8 µs per neuron-step on TK5, the candidate N cut
from five values to {250, 500, 1000}, the 1000 ms standard duration confirmed,
the maximum since fixed at 1300 ms (D-138). That output fed SR-EXT-03, which
determined N = 500. On its own terms the gate is discharged, and D-251 closes
it.

**But every figure behind it was measured on a quiet synthetic network**, and
VL-41, VL-42 and VL-43 each say so in their own final sentence — *"a quiet
synthetic network whose activity is driven by eight stimulus neurons, one host,
one day, single samples."*

That is not a stylistic caveat. The network the MVP actually ships is `srext`,
admitted 2026-09-13 by D-205: 501 neurons carrying a **format v1.1
compensating-input table** (D-190, IR-NET-09) that **did not exist** when G3
was measured on 2026-09-11, two days earlier. The table is neither free nor
neutral:

- Appendix C step 0 adds one binary64 addition per neuron per step.
- More importantly, the table exists *precisely to raise activity* — it stands
  for the drive that the dropped presynaptic neurons supplied.

And rising activity is exactly the mechanism VL-42 identified as the cause of
**super-linear** cost growth: spikes rose 48% for 50% more steps, per-neuron-step
cost went from 38.5 µs to 43.9 µs, and that growth refuted two successive
duration estimates in a row (D-134's 2000 ms, then D-136's 1500 ms).

So G3's timings are a **lower bound** on what the shipped network costs, and
the error is in the unfavourable direction. VL-90 records this and restates the
obligation: **NFR-PERF-01 and ACC-6 are not established by G3** and must be
measured on `srext` itself at Phase E — which is what TX-04 already exists to
do. The owner declined re-measuring now on the grounds that it is Phase E
verification performed under a Phase A heading.

VL-90 also carries D-253's forward correction: VL-41's own text still reads
*"Against NFR-PERF-01's five-minute bound, only N=250 and N=500 fit"*, a bound
D-133 superseded by raising it to ten minutes, under which N=1000 also fits.
Following the VL-79/VL-80 precedent, the dated entry is left as recorded and
corrected by a later one rather than edited.

### 3.2 A word boundary, and why it is worth a test

`summarise()` in `tools/mvsub.py` is the funnel through which thousands of
lines of JES2 output reach a person — and, through the gate tooling, reach a
gate record. Its alternation contained a bare `ABEND`, which matches any line
merely *containing* those five letters. MVS listings are full of them. Gate G0
listed the members of `SYS2.JCLLIB`, two of which are named `JOBABEND` and
`ABEND0C1`, and a job that ended cleanly was summarised as:

```
IEF142I ONFG0CAT AMSLIST - STEP WAS EXECUTED - COND CODE 0004
  JOBABEND
  ABEND0C1
```

A false abend in a gate record is worse than silence: the reader must go and
disprove it before trusting anything else in the record.

The fix is `\bABEND(ED)?\b`. In `JOBABEND` the preceding `B` means there is no
word boundary before `ABEND`; in `ABEND0C1` the following `0` means there is
none after it. Both are rejected.

**The risk of a fix like that is the opposite failure — silently dropping a
real abend — so `tests/run_sub.py` pins both directions**, 16 cases: the four
false positives must be dropped, and `ABEND S0C4`, `ABEND=S806`, `ABENDED`,
`IEF450I` and a bare `COMPLETION CODE - SYSTEM=0C1` must all still be kept.
`COMPLETION CODE` was added because that is how an abend is reported when the
word itself never appears.

### 3.3 Never trust a filename

`tools/fixtures.py` exists because of a concrete 94 seconds wasted in this
session. `data/networks/*.bin` is gitignored — 322 MB across four files, with
digests committed in `MANIFEST.json` instead — so a fresh worktree starts
without them. This one held a single `onfnet-malecns-v1.0-path.bin` at its
**v1.0** size, 885,416 bytes, where the manifest records v1.1 at 951,200, and
`srext` was absent entirely. `mingw32-make test` ran for a minute and a half
and then failed with

```
netread.NetworkFileError: ONF103E UNSUPPORTED FORMAT VERSION
```

which is the engine correctly rejecting a stale file, reported four call frames
away from anything that mentions fixtures.

The contract of `fixtures.py` is a single rule: **a fixture is accepted only if
its byte count, its CRC-32 and its SHA-256 all match the manifest.** That rule
is the point rather than diligence — the stale file above had exactly the right
name, in exactly the right place, and was wrong. Every candidate is verified
*before* it is linked and the result is verified *again* afterwards.

Sources are searched in order: `$ONFLY_FIXTURES`, the main checkout this
worktree belongs to, then sibling worktrees. Nothing outside the project tree
is searched and nothing is written outside `data/networks/`. A network found
nowhere is reported as what it is — a file that `prep/emit.py` must regenerate
from the MaleCNS data — not as a link failure.

**Files are copied, never hard linked — and the first version of this tool got
that wrong.** It hard linked by default, on the reasoning that fixtures are
immutable so links are free and save 322 MB per worktree. That reasoning is
wrong, and the project had already paid for it: on 2026-09-13 the networks were
hard linked between worktrees for exactly that reason, and
`prep/extract.py --refixture` then wrote **through** the links, silently
replacing six network files belonging to a different worktree. Nothing reported
it. A fixture is immutable only until some tool decides to re-emit it.

The defect was caught before it could do harm a second time, and two things
were repaired:

- `place()` now copies by default; `--link` is an explicit opt-in for a caller
  who knows their tree is read-only, and the reasoning is written into the
  function so the next person to think links are free reads the incident first.
- The fixtures this session had already hard-linked into the worktree were
  converted to independent copies. `fsutil hardlink list` showed 2–3 names per
  file beforehand and exactly 1 afterwards, with every CRC-32 preserved across
  the conversion.

`fixtures` is deliberately **not** a prerequisite of `test`. It reaches outside
the checkout, and a test target must not do that on its own.

## 4. Mathematical / numerical details

None introduced. The one quantitative claim is VL-90's, and it is a statement
about the *direction* of an error rather than its size: adding a per-neuron
input at Appendix C step 0 both adds arithmetic and raises activity, and VL-42
measured that per-neuron-step cost rises with activity (38.5 µs → 43.9 µs as
spikes went 421 → 624). How much the compensated network costs is unmeasured —
deliberately, since measuring it is TX-04.

## 5. Design decisions

| Choice | Made by | Why |
|---|---|---|
| Close G3 before marking Phase A | Owner, D-248 | A gate with a measurement but no closure is the defect D-235 caught in G0; papering over it in the phase row would have repeated it one level up |
| Close G3 on its own terms rather than re-measuring | Owner, D-251 | Re-measuring on `srext` is TX-04 — Phase E verification — and doing it under a Phase A heading would blur the phases. The obligation is carried in VL-90 instead |
| Correct VL-41 forward, not in place | Owner, D-253 | The VL-79/VL-80 precedent: a dated measurement is corrected by a later entry, never rewritten |
| Marker in the phase-name cell | Owner, D-252 | Matches the form D-246 and D-247 gave B and C. P-12 as drafted put it inline and was superseded before it was ever applied |
| Raise the synthetic-network gap before stamping the gate | Engineer | The instruction was to close G3; the evidence had a limit its row did not mention, and reporting it is not the same as refusing |
| `run_sub` wired into `test`; `fixtures` not | Engineer | One is pure Python with no external reach; the other touches files outside the checkout |

## 6. Verification

**Platform:** x86-64 Windows 11 26200, Intel i7-13650HX. Python 3.13.14,
mingw32 gcc 6.3.0, GNU Make 3.82.90. No MVS or s390x run was needed for this
change and none is claimed.

```
$ mingw32-make sub
python tests/run_sub.py
run_sub: 16 passed, 0 failed

$ mingw32-make fixtures-check
fixtures: full   OK       299515264 bytes, CRC 44C8B933
fixtures: hop2   OK       21588672 bytes, CRC 7B88494F
fixtures: path   OK       951200 bytes, CRC 70A9A555
fixtures: srext  OK       171768 bytes, CRC 038CAE79
fixtures: all 4 networks present and verified against MANIFEST.json
```

`fixtures.py`'s recovery paths were exercised against the real failure modes,
not only the happy one:

```
# a fixture deleted outright
fixtures: path   COPIED   951200 bytes, CRC 70A9A555  <- ...6642cd/data/networks/...

# a fixture present, correctly named, and STALE at the v1.0 size
fixtures: path   MISSING  885416 bytes, expected 951200
fixtures: 1 network(s) missing or wrong
```

The second case is the one that matters: the diagnosis is now
`885416 bytes, expected 951200` instead of an `ONF103E` raised four frames deep.

And the recovered file is an independent copy, not a link:

```
$ fsutil hardlink list data/networks/onfnet-malecns-v1.0-path.bin | wc -l
1
```

The seven fixtures this session had already hard-linked were converted the same
way, CRC-32 verified before and after each conversion:

```
onfnet-malecns-v1.0-full.bin    unlinked, 299515264 bytes, CRC 44C8B933 preserved
onfnet-malecns-v1.0-srext.bin   unlinked,    171768 bytes, CRC 038CAE79 preserved
...   (7 files, 2-3 names each beforehand, exactly 1 afterwards)
```

### 6.1 What this does **not** prove

- **Gate G3's closure does not establish NFR-PERF-01 or ACC-6.** Every timing
  behind it is a quiet synthetic network on one host on one day in single
  samples, taken before format v1.1 existed. The shipped `srext` network has
  not been timed on TK5 at all. That is TX-04's job, at Phase E (VL-90).
- **No performance measurement was taken in this session.** Nothing here
  re-ran `tools/mvsprf.py`; G3's numbers are quoted from VL-41…VL-43 as the
  record of a 2026-09-11 session, not reproduced.
- **`run_sub` tests a regular expression, not MVS.** It proves the summariser
  classifies lines correctly; it says nothing about whether any job ran.
- **`fixtures.py` was exercised on this host only**, on NTFS. The `--link`
  path is implemented but is now off by default and was exercised only before
  the default was corrected; the copy path is what the tests above cover.

## 7. Related docs

- SRS Section 9.1 (G3), Section 9.2 (Phase A), Appendix A.1 (D-248…D-253),
  Appendix D (VL-90, correcting VL-41 forward)
- `docs/implementations/2026-09-14-gate-g0-environment.md` — the session this
  grew out of, and where both defects were found
- `docs/implementations/2026-09-11-gate-g3-measured.md` — G3's original
  measurement
