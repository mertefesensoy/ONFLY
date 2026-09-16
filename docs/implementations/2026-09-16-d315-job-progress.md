# 2026-09-16 — D-315: long jobs the owner can watch without asking

| Field | Value |
|---|---|
| Date | 2026-09-16 |
| Author | ONFLY senior engineer |
| Phase / gate | Phase E — MVS MVP (D-296); engineering support, not a requirement |
| Owner decisions relied on | D-315 |
| Requirements touched | none — this is observability |
| Open items closed | none |

## 1. Problem / motivation

The owner asked to be able to see a running job's progress on their own
screen rather than being told. The request sounded like a request for a
dashboard. It was not: underneath it was a defect.

`prep/extract.py` calls `sys.stdout.flush()` in five places, and its logs
appear as it runs — which is why ACC-1 and ACC-3 were readable within
seconds. **`prep/acc4.py` and `prep/wsens.py` never flushed at all.**
When their output is redirected to a file, CPython block-buffers roughly
8 KB, and a long run writes nothing until the process exits. The
observable consequence on 2026-09-15/16:

| Run | Duration | Log size while running |
|---|---|---|
| ACC-4 re-run | 6,971 s | **0 bytes** |
| W_syn probe, 4 seeds | 3,086 s | **0 bytes** |
| W_syn probe, 30 seeds | 11,047 s | **0 bytes** |

For nearly six hours the only way to tell those jobs were alive was to
count `runnet.exe` processes, and the only way to tell *where* they were
was to notice which `net-<w>.bin` happened to exist on disk. That is not
a missing feature; it is a one-line omission in two files, and it should
have been diagnosed the first time a log read zero bytes rather than the
fifth.

Flushing fixes the log. It does not fix the second half of the problem:
a log is text for a human to read, and "which W_syn point, how many runs
done, how much longer" should be answerable by a command.

## 2. What changed

| File | Change |
|---|---|
| `tools/progress.py` | New. A `Tracker` writing one atomic status file per job, and a CLI to read them. |
| `prep/acc4.py` | `run_many()` flushes after each progress line and takes an optional `tracker`. |
| `prep/wsens.py` | Creates a `Tracker`, stages per W_syn point, notes per-rate means, flushes. |
| `.gitignore` | Ignores `data/progress/`. |

## 3. Implementation approach

### 3.1 The status file, and why it is written the way it is

    data/progress/<job>.json

Contract of `Tracker`:

```python
t = Tracker("wsens-d52-s30", total=480, unit="runs")
t.stage("W_syn 0.2600", total=120)   # optional subdivision
t.tick()                             # +1 done; rewrites the file
t.note(hz_40=13.88)                  # arbitrary context
t.finish("ok")                       # terminal state
```

Every mutator rewrites the whole file. That is a few hundred bytes
against a full-brain run costing tens of seconds, so the cost is noise
and the simplicity is worth more than the saving.

**The write is atomic**, to a temporary file in the same directory
followed by `os.replace()`, which is atomic on Windows and POSIX alike.
This is not defensive habit: the entire point is that a *different*
process reads the file while the writer is running, so a reader that can
observe a half-written file would be a reader that intermittently
crashes on valid data.

**It degrades to silence.** Every write is wrapped and every exception
swallowed. A progress file that could fail the three-hour run it reports
on would be worse than no progress file, and the reader side is equally
forgiving — a `json` parse error during a replace is skipped, not
raised, because the next poll will read the completed replacement.

### 3.2 The reader

`python tools/progress.py` prints every known job once; `--watch [secs]`
clears and refreshes (default 5 s). A job whose last tick is more than
five minutes old is shown as `running?` rather than `running`, so a
dead process does not masquerade as a slow one.

The ETA is straight-line from work already done, and is deliberately
rendered coarsely — `62 min`, not `3721 s`. It is wrong whenever units
differ in cost, which they do here: a W_syn point also emits a 299 MB
network before its runs begin. Presenting it to the second would imply a
precision the method does not have.

### 3.3 The integration point

`acc4.run_many()` is the single place both ACC-4 and both W_syn probes
consume runs, so it is the only place that needed a tick. Its signature
gained `tracker=None`, and **passing `None` reproduces the previous
behaviour exactly** — which is what every existing caller gets, so no
result recorded before today is affected by this change.

## 4. Mathematical / numerical details

None. Nothing here touches arithmetic, the kernel, any `onf_fp`
operation, or any emitted artifact. `Tracker` writes a JSON file and
nothing reads it but a human.

## 5. Design decisions

| Choice | Made by | Note |
|---|---|---|
| Flush, plus a progress file, plus a CLI | **Owner, D-315** | Chosen over flush-alone and over a local web dashboard |
| No web dashboard | **Owner, D-315** | It would add a long-running local process for progress bars |
| Standard library only | Architect | A new dependency would need its own owner decision; none was needed |
| Atomic `os.replace` write | Architect | A concurrent reader must never see a partial file |
| Failures swallowed | Architect | Observability must never fail the run it observes |
| Tick inside `acc4.run_many` | Architect | The one shared place; keeps the change to a single integration point |

## 6. Verification

### 6.1 The tracker, on x86-64 Windows, CPython 3.13

    python -c "... Tracker('smoke', total=10) ... 4 ticks ..."

    smoke            ##########..............  40%  4/10 runs
        status running   elapsed 0 s     eta 0 s     pid 40368
        stage  stage one  4/10
        hz_40=13.77
        last update 2026-09-16 07:27:08

### 6.2 Nothing existing moved

`acc4.run_many`'s new parameter defaults to `None`. The full suite was
run after this change as part of the session's close-out; see the goal
report for that output.

### 6.3 What this does **not** prove

- **The currently running job does not appear in it.** The 480-run shape
  test was launched before the tracker existed, so `data/progress` is
  empty while it runs and its log is still 0 bytes. The fix applies to
  the next job, not to the one that motivated it.
- **x86-64 Windows only.** `os.replace` is atomic on POSIX too, but the
  tool was exercised on this host alone.
- **The ETA is an estimate and is labelled one.** It assumes uniform
  cost per unit, which is false across a W_syn point boundary.
- **Nothing depends on this.** No requirement is verified by it and no
  result in Appendix D rests on it.

## 7. Related docs

- SRS Appendix A.1 (D-315)
- `docs/implementations/2026-09-16-d316-chunk-invariance.md` — the other
  half of the same conversation
