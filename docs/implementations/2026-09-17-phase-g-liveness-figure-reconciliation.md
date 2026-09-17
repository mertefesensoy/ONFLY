# 2026-09-17 — Phase G Stage 5: reconciling the two liveness figure sets

| Field | Value |
|---|---|
| Date | 2026-09-17 |
| Author | Senior engineer (session `sweet-albattani-27739a`) |
| Phase / gate | Phase G, transaction demonstrator, third component (live view), Stage 5 |
| Owner decisions relied on | D-436 (this change); background: D-128, D-415, D-417, D-418, D-420, D-422 |
| Numbering | Drafted as D-424 / VL-135's predecessor VL-129, then renumbered: `main` had meanwhile taken D-424..D-435 and VL-129..VL-134 for Phase G's 3270 component. This change is **D-436** and **VL-135** |
| Requirements touched | None. No requirement text changed. IR-STM-04 and D-128 are the claim being recorded |
| Open items closed | none |

## 1. Problem / motivation

Two records of the same Phase G Stage 5 liveness claim carried different numbers,
and **neither said which run it described**:

| Record | Figures |
|---|---|
| `docs/implementations/2026-09-17-phase-g-stage5-mvs-live-view.md` §6.1, row V6 | `first ONFSC at +31.3 s, job END banner at +1011.3 s`, `1020 of 1020 punch writes landed before the job ended` |
| `docs/ONFLY-SRS.md` §9.2, Phase G row (written by D-417, adopting P-28) | `the first ONFSC reached the host at +28.3 s against a job END banner at +1148.1 s -- 1,027 of 1,028 punch writes landed while the job was still running` |

§6.3 of the implementation doc records **four** MVS runs, so the natural
hypothesis was that the two sets came from different runs. But because neither
record named a run, the two could not both be read as true: a reader takes each
as *the* liveness measurement of the completed component, and only one run can be
that. The SRS sentence was worse than ambiguous. Its surrounding clauses had
been refreshed to run 4's results (19,909 lines, byte-identity with x86) while
the liveness clause still held run 1's, so **the sentence as a whole described no
single run that was ever executed**.

The failure this would have caused is not internal. These figures are candidates
for external publication (an IBM Z Champion community story). Quoting
`+1148.1 s` beside "the streams are byte-identical" would have put a number in
public that no run produced, with the repository unable to say which job it came
from.

The constraint on fixing it: a TK5 run costs about 17 minutes plus setup, and the
owner's standing instruction was not to re-run to resolve a documentation
question. So the reconciliation had to be done from **recovered evidence**.

## 2. What changed

| File | Change |
|---|---|
| `docs/ONFLY-SRS.md` | §9.2 Phase G row: the liveness sentence now reports **both** valid runs, each naming its job, and cites D-436 and VL-135. |
| `docs/ONFLY-SRS.md` | Appendix A.1: **D-436** added, the owner's decision on how to reconcile the records, with the process finding on how the drift happened. |
| `docs/ONFLY-SRS.md` | Appendix D: **VL-135** added, registering the liveness measurement with both runs, their job numbers, the MVS-clock corroboration, and the limits (polling granularity, what a punch-write count is, why the two runs are not a repeatability figure). |
| `docs/ONFLY-SRS.md` | Appendix D: **VL-118**'s denominator corrected from 19,910 lines to 19,909, with a dated note on the off-by-one. |
| `docs/ONFLY-SRS.md` | Appendix A.2: the struck-through **P-28** row annotated to record that its figures were run 1's, superseded by D-436. Its drafted text is kept as written. |
| `docs/implementations/2026-09-17-phase-g-stage5-mvs-live-view.md` | §6.1 row V6 now names **run 4, JOB 328**, and cites VL-135 and run 1's independent figures. |
| `docs/implementations/2026-09-17-phase-g-stage5-mvs-live-view.md` | §6.2 wall-clock bullet says which run each timing came from and points at VL-135. |
| `docs/implementations/2026-09-17-phase-g-stage5-mvs-live-view.md` | §6.3 run table gains a **Job** column and an **MVS clock** column, with a note on where they were recovered from. |
| `docs/implementations/2026-09-17-phase-g-stage5-mvs-live-view.md` | §7 links this document. |
| `docs/implementations/2026-09-17-phase-g-liveness-figure-reconciliation.md` | This file. |

**No code changed.** No requirement text changed. No MVS job was run.

## 3. Implementation approach

The question "which run produced which figure set" was answered from three
artefacts that survive outside the repository, none of which was written by the
documents in dispute.

**(1) The Hercules punch, `pch/pch10d.txt`.** `tools/mvsstm.py` takes the punch
file's size before submitting and harvests from that offset; the file itself is
never truncated, because Hercules appends. So after four runs it still held all
four streams end to end. Segmenting it on `ONFSH` boundaries (five per run, one
per `srext` golden request) recovers each run's stream as it was written.

**(2) The JES2 printer, `prt/prt00e.txt`.** It holds every job's `J E S 2  J O B
L O G`, including `IEF403I ... STARTED - TIME=` and `IEF404I ... ENDED - TIME=`
for each `ONFERUN`. This is the **guest's own clock**, which is what makes it an
independent check: `mvsstm.py` measures from the host side and never reads these
banners for timing, only pattern-matching `END JOB` to know when to stop.

**(3) The Stage 5 session's `build/` directory**, which still held
`mvs-stream.txt` and `mvs-stream-job.txt` from the final run.

The identification then runs in three steps:

- **Order the runs by content.** Diffing the four segments pairwise reproduces
  VL-124's finding exactly, which confirms the segmentation is right before it is
  relied on: run 1 differs from run 2 in exactly 200 `ONFSU` lines; runs 2 and 3
  are byte-identical; run 4 is the only one carrying `0000000000000000` for the
  rate 0 request, which is the D-420 fix.
- **Anchor the final run.** `build/mvs-stream.txt` is byte-identical to segment 4,
  and `build/mvs-stream-job.txt` is JOB 328's log. So segment 4 is run 4.
- **Attach the job numbers**, by locating each run's `PARM='STREAM=50'` JCL
  listing in the printer and reading the job log printed with it.

That gives the register in §6.3 of the Stage 5 document, and the two disputed
figure sets fall out of it by matching elapsed times (§4).

## 4. Mathematical / numerical details

There is no new arithmetic, but the identification rests on a numeric argument
that a future reader must be able to audit without re-running anything.

**What the host measures.** `follow()` in `tools/mvsstm.py` starts a clock `t0`
immediately before submitting the deck. It then polls the punch file four times a
second and the printer once every two seconds. `first` is the elapsed time at the
first poll at which the harvested file contains `ONFSC`; `ended` is the elapsed
time at the first printer poll whose text matches `END JOB <n> <job>`. Both are
therefore **upper bounds, each to within one poll interval**, and both include the
latency between submission and JES2 dispatching the job.

**What the guest records.** `IEF404I − IEF403I` is the job's elapsed time on the
guest's own clock, from JES2 dispatch to job end. It excludes the submission
latency the host figure includes, and it has one-second resolution.

So for the same job, the relation expected is

```
    ended  ≈  (IEF404I − IEF403I)  +  submission latency  +  ε,    0 ≤ ε ≤ 2 s
```

with the host figure the larger of the two. Evaluating it:

| Run | Job | `IEF404I − IEF403I` | `ended` as recorded | Excess |
|---|---|---|---|---|
| 1 | JOB 320 | 07.43.04 − 07.23.56 = **1,148 s** | **+1148.1 s** | 0.1 s |
| 3 | JOB 322 | 13.33.50 − 13.12.59 = **1,251 s** | not recorded anywhere | n/a |
| 4 | JOB 328 | 13.57.56 − 13.41.07 = **1,009 s** | **+1011.3 s** | 2.3 s |

Both excesses fall inside the bound, and no other pairing does: matching the SRS's
`+1148.1 s` to run 3 would require an excess of −102.9 s, and matching the
implementation doc's `+1011.3 s` to run 1 would require −136.7 s. Negative excess
is impossible, because the host clock starts strictly before the guest's. **The
assignment is therefore unique**, which is what lets this be settled without a
re-run.

The `first` figures corroborate it independently. The stream cannot begin before
the `GO` step is dispatched, and the printer records that moment as `IEF237I 10D
ALLOCATED TO ONFSTM`:

| Run | Job | `IEF237I` after `IEF403I` | `first` as recorded |
|---|---|---|---|
| 1 | JOB 320 | 07.24.23 − 07.23.56 = **27 s** | **+28.3 s** |
| 4 | JOB 328 | 13.41.37 − 13.41.07 = **30 s** | **+31.3 s** |

In each case the first chunk lands about a second after the thirteen compiles,
thirteen assembles and the link-edit finish, which is what a K = 50 chunk of a
500-neuron network should cost.

**On the punch-write counts.** `1,027 of 1,028` and `1020 of 1020` are *not*
counts of channel programs or of cards. `report_live` counts entries in `marks`,
one per poll at which the harvested file had grown, and the "during" figure is
those with `t < ended − 0.5`. Two consequences the register now states: the
count scales with how long the job ran, not with how much it wrote, which is
why the 1,148 s run has more marks than the 1,009 s run although both streams are
exactly 1,523,612 bytes; and a denominator larger than the numerator means only
that the harvester's five-second drain after the banner caught a final growth,
which is the case `follow()` exists to handle.

**On the 200 differing lines.** Each of the four segments is 19,909 lines and
1,523,612 bytes; the pairwise diffs are 200 lines, all `ONFSU`, between run 1 and
runs 2/3, and 200 again between run 4 and each of the others. This reproduces
VL-124 and is the check that the segmentation is sound.

## 5. Design decisions

The reconciliation itself was **D-436**, taken by the owner through
AskUserQuestion on 2026-09-17. Three options were put:

| Option | Why it was not chosen |
|---|---|
| Replace §9.2's figures with run 4's alone | Defensible, since D-418 had already declined to report run 1's timings, but it discards a valid independent measurement of the claim. |
| Leave both records and annotate each with its run | Changes no figure, but leaves §9.2 reporting liveness from a binary that predates both D-412/D-413 and the D-420 fix, beside a byte-identity claim only run 4 achieved. |
| **Report both runs in §9.2, naming each** (**chosen**) | The claim is stronger for resting on two jobs, and naming them removes the ambiguity that caused the drift. |

Two subsidiary choices, also the owner's:

- **A new VL-135 rather than amending VL-124.** No verification limit in the
  Stage 5 range recorded the liveness timings at all: they existed only in prose
  in two places, which is precisely how they drifted. VL-124 exists to record
  build-sensitivity and overloading it would repeat the mistake.
- **P-28 annotated, not rewritten.** The repository's habit for a superseded
  record is a dated prefix with the original text kept, as VL-118, VL-120 and
  VL-127 carry. P-28's drafted figures are the historical record of what was
  known at D-417 and stay legible as such.

A third item was offered in the same round, declined, and then asked for
directly: **correcting VL-118's `200 of 19,910 lines` to 19,909**. It is now
done, under the same D-436. **The discrepancy is real but cosmetic.** The x86
stream is 1,543,521 bytes with CRLF endings, and 19,910 is what a split on
newline returns when it counts the empty element after the trailing one. Under
D-414's rule the file is 19,909 lines and 1,523,612 bytes, equal to the MVS
stream, which is the figure the rest of the record already used. The numerator,
200, was always right, and nothing the limit asserts depends on the change.
VL-118 is marked "kept as written", so the correction is an inline dated note
rather than a silent edit, in the style Appendix D uses elsewhere.

**P-28's copy of `19,910` was deliberately left alone.** It sits inside a
verbatim quotation of the note as drafted for approval, and the repository keeps
drafted text as written; the annotation on that row now says the figure carries
the same off-by-one.

**What was deliberately not done:** no MVS job was run. The owner's instruction
was explicit and the evidence was sufficient without one.

## 6. Verification

This change is documentation only; there is nothing to execute in it. What can be
re-run is the **identification**, from artefacts outside the repository. All of
the following were run in this session on **x86-64 Windows 11**, Python 3.13,
reading the TK5 lab directory `C:\hercules-lab\mvs-tk5`. Nothing was run on MVS.

**(1) The punch still holds four runs, each 19,909 lines / 1,523,612 bytes.**

```bash
python -c "d=open(r'C:\hercules-lab\mvs-tk5\pch\pch10d.txt','rb').read(); import collections; print(collections.Counter(l[:5] for l in d.split(b'\n') if l).most_common(6))"
```

Observed: `ONFSD 71576, ONFSU 4000, ONFSC 4000, SHORT 30, LONG 30, ONFSR 20`,
with 20 `ONFSH` and 20 `ONFSE`, five per run over four runs.

**(2) The run ordering, by pairwise diff.** Segmenting on `ONFSH` and diffing
gave, in this session:

```
run1 vs run2: 200 differing lines   kinds: {ONFSU: 200}
run2 vs run3: 0 differing lines
run1 vs run4: 200 differing lines   run1 0x...D430F  ->  run4 0000000000000000
run2 vs run4: 200 differing lines   run2 0x...D4113  ->  run4 0000000000000000
run4 vs build/mvs-stream.txt: 0 differing lines
```

This reproduces VL-124 and anchors run 4 to the surviving harvest.

**(3) The job numbers and the MVS clock.**

```bash
grep -aE "IEF40[34]I ONFERUN" "C:/hercules-lab/mvs-tk5/prt/prt00e.txt" | sort -u
```

Observed: JOB 320 `07.23.56`→`07.43.04`; JOB 321 `08.16.11`→`13.10.18` (the
suspension); JOB 322 `13.12.59`→`13.33.50`; JOB 328 `13.41.07`→`13.57.56`. And
`build/mvs-stream-job.txt` in the Stage 5 worktree carries
`$HASP373 ONFERUN STARTED` / `$HASP395 ONFERUN ENDED` for **JOB 328**.

**(4) The documents agree.** After this change, the only liveness figures in the
repository are `+28.3 s / +1148.1 s / 1,027 of 1,028` attributed to run 1
(JOB 320) and `+31.3 s / +1011.3 s / 1020 of 1020` attributed to run 4
(JOB 328), in SRS §9.2, VL-135, and §6.1/§6.3 of the Stage 5 document.

```bash
grep -n "1148.1\|1011.3\|JOB 320\|JOB 328" docs/ONFLY-SRS.md docs/implementations/2026-09-17-phase-g-stage5-mvs-live-view.md
```

### What none of this proves

- **It is a re-identification, not a re-measurement.** Every figure in VL-135 was
  produced by `tools/mvsstm.py` in the Stage 5 session. Nothing here re-measured
  liveness, and the MVS-clock column is a *consistency check* on the host figures,
  not a second measurement of them: it cannot detect an error common to both, such
  as a mis-set `t0`.
- **The punch and printer are outside version control.** They are lab state on
  this development host. If either is cleared, this identification is not
  reproducible, and no future session can re-derive it without a TK5 run. That is
  the reason the job numbers were written into §6.3 rather than left implicit.
- **Run 2 and run 3 remain as they were.** Run 2's timings are void and run 3's
  were never recorded; this change does not recover either.
- **Nothing about the engine was re-verified.** V1 to V9 of the Stage 5 document
  stand on their original measurements; no fingerprint, stream or dataset was
  recomputed.

## 7. Related docs

- `docs/implementations/2026-09-17-phase-g-stage5-mvs-live-view.md` — Stage 5, whose §6.1 V6 and §6.3 this reconciles
- `docs/plan/2026-09-17-phase-g-stage5-mvs-live-view.md` — P-25, the plan of record, whose V6 row is the claim
- `docs/ONFLY-SRS.md` §9.2 Phase G; A.1 **D-436**; A.2 P-28 and P-29; Appendix D **VL-135**, and VL-118 to VL-128
- `docs/ONFLY-SRS.md` §4.7 IR-STM-04 and D-128 — the requirement the liveness claim discharges
