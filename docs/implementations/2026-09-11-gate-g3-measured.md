# 2026-09-11 — Gate G3 measured: 37–41 µs per neuron-step on TK5

| Field | Value |
|---|---|
| Date | 2026-09-11 |
| Author | Claude (ONFLY senior engineer session) |
| Phase / gate | **Gate G3 (Spike S3, performance)** |
| Owner decisions relied on | D-37 (provisional durations), D-121/D-124 (SOFT2C backend) |
| Requirements touched | NFR-PERF-01, SR-EXT-03, FR-SIM-06 |
| Open items closed | none — TBD-06 now has numbers but remains the owner's to close |

## 1. Problem / motivation

Gate G3 asks how large N and the duration can be within five minutes. Until now
that rested on an estimate: D-128 records "two to three orders of magnitude
slower than x86" and says plainly it is not a measurement.

TBD-19 — the streaming interface for D-128's live view — cannot be designed on
an estimate. D-128 itself says the cost "collides directly with the performance
question Gate G3 has never measured", and that a real number "may force a much
smaller network or a much shorter duration than the golden fixture uses".
Designing the interface first and measuring afterwards risks designing the
wrong one.

## 2. What changed

| File | Change |
|---|---|
| `tests/tstclk.c` | New. Probes what `<time.h>` PDPCLIB actually implements on MVS. |
| `tools/mvsclk.py` | New. Submits the clock probe on its own, for a fast answer. |
| `tests/tstprf.c` | New. Runs one request at the standard duration at each N in SR-EXT-03's sequence and times it. |
| `tools/mvsprf.py` | New. Builds and submits it, certifies the run, and reports the G3 figures. |
| `docs/ONFLY-SRS.md` | Added VL-40 (clocks) and VL-41 (the measurement); updated the Gate G3 row and TBD-06. |

## 3. Implementation approach

**Measure the workload, not a proxy.** `tstprf.c` issues one `onfrun()` call of
10,000 steps — D-37's provisional 1000 ms standard duration at `dt` = 100 µs —
at N = 250, 500, 1000, 2000, 4000. That is precisely the quantity NFR-PERF-01
bounds. A micro-benchmark of the inner loop would have needed an argument that
it was representative; this needs none.

The network is built exactly as `tests/tstker.c` builds its 64-neuron one, so
the shape being timed is the shape the kernel has already been verified against
on this platform (VL-33).

**Self-calibrating repeats.** VL-40 established that `clock()` is a PDPCLIB stub
returning −1 and `time()` has one-second resolution. Each configuration
therefore repeats until at least 20 seconds have elapsed and divides, and waits
for a tick boundary first to remove the up-to-one-second error at the front. In
the event every configuration exceeded 20 s on its first repetition, so all
figures are single timings — at 102–1,462 s the quantisation is immaterial.

**Spike counts are printed** so that −O1 cannot discard the loop, and so a
configuration that timed an empty network would be visible.

## 4. Mathematical / numerical details

Time per neuron-step is the per-request time divided by N × steps:

```
ns_per_neuron_step = (seconds_per_request / (N × 10000)) × 10^9
```

The figures are 40.8, 39.6, 38.5, 37.7 and 36.6 µs at N = 250 … 4000. That this
barely moves across a 16× range of N is itself evidence about *where* the cost
is: the per-neuron state update (`u' = P11·u + P12·g`, `g' = P22·g`, plus the
threshold test) runs N × steps times unconditionally, while edge traversal runs
only on a spike. At N=4000 there are 40 million neuron updates against roughly
29 thousand edge operations. Edge traffic is noise, which is why the figure is
stable — and also why it is a *quiet-network* figure (§5).

Against x86 with the same harness and the same SOFT2C backend — 90.5 ms at
N=250 rising to 1.235 s at N=4000, i.e. 31–36 ns per neuron-step — the ratio is
1,127× to 1,205×, about **1,180×**.

## 5. Design decisions

**Three clocks, then one.** `tools/mvsclk.py` was written first, as a separate
small job, rather than assuming PDPCLIB's `<time.h>`. It cost one 3.6-second
round trip and found that `clock()` returns −1 despite `CLOCKS_PER_SEC` being
defined — a program trusting the macro would have measured nothing.

**The certification is the part worth reading.** The natural guard against a
sleeping host is to compare elapsed time with the CPU time MVS charges the step,
on the reasoning that CPU accrues only while instructions execute. **That guard
is wrong here, and it was written, tested and discarded rather than trusted.**
The contaminated run reported `CPU 61MIN 21.92SEC` against 61 minutes 32 seconds
elapsed — a ratio of 1.00 — while roughly 38 of those minutes were spent in
Modern Standby. MVS's accounting comes from a timer Hercules drives from the
host clock, so guest CPU and guest wall inflate together and their ratio is
uninformative. Every clock visible inside the guest shares this defect.

The sound check is host CPU charged to the **Hercules process** against host
elapsed wall clock: a compute-bound guest keeps one emulated CPU busy, so a
large shortfall means the host stopped executing it. `trust()` rejects below 70%
of a core and refuses to print a G3 result it cannot certify at all.

**Allocation, not static arrays.** The first attempt abended SB37 on SYSPUNCH:
~1.1 MB of static arrays at N=4000 is more than the assembler will punch.
`malloc` is both the fix and the more honest shape, since `onfker.h`'s contract
already anticipates "the future CICS path where per-task storage is at a
premium".

**What is deliberately not concluded.** SR-EXT-03 picks the *smallest* N
satisfying ACC-3, NFR-MEM-01 **and** NFR-PERF-01. This measurement settles only
the third. It narrows the candidate set to {250, 500} and does not choose within
it, because ACC-3 is a separate criterion and the choice is the owner's.

## 6. Verification

```bash
python tools/mvsclk.py     # what clocks exist
python tools/mvsprf.py     # the measurement
```

Observed 2026-09-11, host kept awake, nothing else running:

```
PERF n=250  e=932   reps=1 secs=102  spikes=421 rc=0
PERF n=500  e=1950  reps=1 secs=198  spikes=421 rc=0
PERF n=1000 e=3979  reps=1 secs=385  spikes=421 rc=0
PERF n=2000 e=7983  reps=1 secs=753  spikes=421 rc=0
PERF n=4000 e=16194 reps=1 secs=1462 spikes=421 rc=0
```

421 spikes at every N is the same value the x86 build produces, so the timed
computation is the verified one.

**The certification, independently:** the Windows event log shows zero
Modern Standby transitions between 18:04:36 and 18:53:31, the run's entire
window. This was checked outside the tool because the process that produced the
numbers still held the superseded in-guest check; `tools/mvsprf.py` on disk now
performs the host-side check itself.

**The detector was shown to fire**, not merely to pass: fed the real contaminated
run's shape (23 minutes of Hercules CPU over 61 minutes elapsed) it reports
`37% of one core sustained` and `*** MEASUREMENT REJECTED ***`.

## 7. Related docs

- `docs/ONFLY-SRS.md` — VL-40, VL-41, Gate G3, TBD-06, SR-EXT-03, NFR-PERF-01,
  D-37, D-128.
- `docs/implementations/2026-09-11-raincode-cics-probes-measured.md` — VL-37,
  the other measurement taken this day.
