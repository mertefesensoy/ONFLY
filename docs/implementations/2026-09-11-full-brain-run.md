# 2026-09-11 — FR-PRP-04: the full-brain run

| Field | Value |
|---|---|
| Date | 2026-09-11 |
| Author | ONFLY engineering session |
| Phase / gate | Phase C — Science (x86); scope set by D-61 |
| Owner decisions relied on | D-56, D-59, D-60, D-61, D-62, D-63 |
| Requirements touched | FR-PRP-04, FR-LOD-04, NR-05, NFR-LIC-01, SR-EXT-01 (partially) |
| Open items closed | TBC-12 (fully, by D-62 with D-50) |

## 1. Problem / motivation

Two Phase C stages are blocked on the same thing. SR-CAL-01 requires `W_syn` to
be calibrated **on the full-brain model**, not on a subcircuit. SR-EXT-01 defines
the MVP subcircuit as the N most active neurons **in a full-brain run**. Neither
can begin until the whole 184,099-neuron network has actually been simulated.

Whether that was even possible on this host was an open question: the network
needs 330 MB of decoded arrays and state, against a 32-bit address space.

## 2. What changed

| File | Change |
|---|---|
| `LICENSE` | New: MIT (D-62), with third-party and data terms stated. |
| `docs/ONFLY-SRS.md` | Recorded D-61, D-62, D-63; closed TBC-12 entirely. |
| `tools/runnet.c` | New: the full-brain runner. |
| `tools/fullbrain.sh` | New: drives the D-63 protocol. |
| `prep/activity.py` | New: aggregates runs into the SR-EXT-01 ranking. |
| `Makefile` | New `runner` target; NR-05 lint extended to `tools/`. |

## 3. Implementation approach

`runnet.c` decodes a network, converts the payload into host-order arrays, then
**frees the file buffer before simulating**. That single `free` is what makes the
run possible here: holding both costs 630 MB, releasing the buffer leaves 330 MB,
and on a 32-bit host that is the difference between running and not.

The ranking breaks ties by **ascending neuron index**, as SR-EXT-01 requires, so
the selection is reproducible rather than dependent on `qsort`'s stability.

`FR-SIM-07`'s ban on I/O and allocation applies to the simulation core, which
still receives caller-owned storage and touches neither; the allocation lives in
the tool.

## 4. Numerical details

**Measured throughput: 8.5 million neuron-steps per second** (92.0 M
neuron-steps in 10.84 s), on x86 32-bit mingw32 gcc 6.3.0 with the NATIVE
backend and D-30's SSE2 flags.

That number decided the protocol. One 1000 ms run over 184,099 neurons is
1.84 G neuron-steps, about 3.6 minutes. The protocol SR-EXT-01 actually asks
for — all calibration and validation rates with all seeds, 7 × 30 at the
proposed values — is roughly **12.6 hours**. D-63 therefore runs 7 rates × **1
seed** × 1000 ms, about 25 minutes, and the resulting ranking is **provisional**.

## 5. Design decisions

D-61, D-62 and D-63 are the owner's. Mine within them:

- **Free the file buffer before simulating** (see above).
- **Report elapsed time as integer milliseconds.** The first version printed
  `(double)` seconds, which the NR-05 lint caught once its scope was extended to
  `tools/`. A tool that links the engine has no reason to introduce a
  floating-point type merely to print a duration; an exception granted for
  convenience is one somebody later copies into a place where it matters.
- **Extend the NR-05 lint to `tools/`**, which is how the above was found.

## 6. Verification

```
mingw32-make test
```

The full engine suite is green, exit 0, unchanged by this work.

The full-brain run itself, on x86 32-bit mingw32 gcc 6.3.0, NATIVE backend:

```
NET n=184099 e=24775486 ns=14 nr=2 dtus=100 delay=18 refract=22 need=330443656
```

`need=330443656` is the corrected FR-LOD-04 figure — the memory gate that had
been understating by tenfold until the full network exposed it.

### The protocol result

Seven rates, one seed, 1000 ms each, 184,099 neurons. Total compute about
28 minutes.

| Rate (Hz) | MN9 #1 spikes | MN9 #1 first spike | MN9 #2 spikes | Network spikes | Active neurons |
|---|---|---|---|---|---|
| 10 | 1 | 536.8 ms | 0 | 330,275 | 16,200 |
| 20 | 13 | 154.9 ms | 0 | 1,439,281 | 17,083 |
| 40 | 31 | 47.4 ms | 3 | 152,495 | 6,276 |
| 80 | 39 | — | 4 | 1,443,227 | 16,751 |
| 120 | 274 | — | 51 | 226,679 | 6,902 |
| 160 | 293 | — | 60 | 248,255 | 7,101 |
| 200 | 311 | — | 68 | 256,895 | 6,942 |

**The MN9 dose-response is strictly monotonic** across all seven rates, in both
readout neurons, and first-spike latency falls sharply as concentration rises
(536.8 ms at 10 Hz to 47.4 ms at 40 Hz). That is the qualitative sugar-to-feeding
relationship ACC-1 describes and the shape ACC-4 tests for.

**Global network activity is not monotonic at all** — it swings between 152,495
and 1,443,227 spikes with no relation to the stimulus rate, and the active-neuron
count alternates between roughly 6,500 and 17,000 as though the network were
flipping between two regimes.

Those two observations are worth holding together. The sugar-to-MN9 pathway
behaves sensibly while the network around it does not, which is exactly what an
**uncalibrated** `W_syn` would produce: the pathway's relative weights are right
because they come from real synapse counts, but their absolute scale is the
FlyWire value applied to a different connectome, so global excitation and
inhibition are not in balance. This is the measurement SR-CAL-01 exists to act
on, and it is evidence that calibration is necessary rather than merely
specified.

### Provisional activity ranking

20,275 of 184,099 neurons spiked at least once. Every candidate size in
SR-EXT-01's sequence is therefore reachable:

| N | Total spikes required to make the cut |
|---|---|
| 250 | ≥ 1,014 |
| 500 | ≥ 686 |
| 1,000 | ≥ 561 |
| 2,000 | ≥ 469 |
| 4,000 | ≥ 407 |

### What these results do not prove

- **x86 32-bit mingw32 gcc 6.3.0, NATIVE backend only.** Nothing here ran under
  GCCMVS, JCC, MVS 3.8j, Linux s390x or QEMU, and the 330 MB requirement is
  itself far beyond the 24-bit MVS region (C-01).
- **The activity ranking is NOT the SR-EXT-01 selection.** `W_syn` is the
  uncalibrated FlyWire 0.275 mV, the runs are one seed rather than thirty
  (D-63), and every SR-MOD-02 parameter is still TBC-02.
- **No ACC-n criterion has been evaluated.** The MN9 rate-response curve is the
  *shape* ACC-1 and ACC-4 will be judged on, not a judgement.
- **VL-12** the stimulus set is pharyngeal and taste-peg where Shiu et al. use
  labellar; **VL-13** the network holds 40.2% of the connectome's synapses.

## 7. Related docs

- `docs/ONFLY-SRS.md` — Section 3.1 (FR-PRP-04), Section 6.3 (SR-EXT-01),
  Appendix A.1 (D-61…D-63), Appendix B (TBC-12 closed).
- `docs/implementations/2026-09-11-real-network-emission.md`
