# 2026-09-12 — TBD-06's maximum duration measured; TBD-19 closed

| Field | Value |
|---|---|
| Date | 2026-09-11 → 2026-09-12 |
| Author | Claude (ONFLY senior engineer session) |
| Phase / gate | Gate G3 consequences; Phase G design |
| Owner decisions relied on | D-133 … D-140 |
| Requirements touched | NFR-PERF-01, FR-SIM-06, SR-EXT-03, FR-SIM-04, FR-SIM-07, IR-COM-01, IR-COM-04, ACC-5, NFR-MNT-02 |
| Open items closed | **TBD-19 (fully)**; TBD-06's *standard* and *maximum* duration; TBD-06 remains open on seeds |

## 1. Problem / motivation

Gate G3 measured engine speed on TK5 for the first time (VL-41). Two open items
depended on that number and could not be settled without it:

- **TBD-06** — the standard duration, the maximum duration, and seeds per rate.
  D-37 had set 1000 ms / 5000 ms *provisionally*, explicitly pending G3.
- **TBD-19** — the streaming interface for D-128's live view. D-128 itself said
  the cost "collides directly with the performance question Gate G3 has never
  measured", and that a real number might force a much smaller network or a
  shorter duration.

Designing either before measuring risked designing the wrong one.

## 2. What changed

| File | Change |
|---|---|
| `docs/ONFLY-SRS.md` | D-133…D-140; VL-41…VL-44; NFR-PERF-01 and FR-SIM-06 amended; Gate G3 row; TBD-06 and TBD-19 updated; D-37 marked superseded in part. |
| `tests/tstprf.c` | `ONFPRF_STEPS` / `ONFPRF_ONLY` overrides so one configuration can be measured directly. |
| `tools/mvsprf.py` | `--steps`; host-side certification; `MAXDUR` condition reporting; step-count-aware reporting. |

## 3. Numerical results

Measured on TK5, MVS 3.8j, GCCMVS `-O1`, SOFT2C backend. Every figure below was
certified from **outside** the guest (see §5).

### 3.1 One request at the 1000 ms standard duration (VL-41)

| N | edges | per request | ns / neuron-step | vs x86 SOFT2C |
|---|---|---|---|---|
| 250 | 932 | 102 s | 40,800 | 1,127× |
| 500 | 1,950 | 198 s | 39,600 | 1,178× |
| 1,000 | 3,979 | 385 s | 38,500 | 1,193× |
| 2,000 | 7,983 | 753 s | 37,650 | 1,205× |
| 4,000 | 16,194 | 1,462 s | 36,550 | 1,184× |

x86 SOFT2C reference, same harness: 90.5 ms at N=250 rising to 1.235 s at
N=4000, i.e. **31–36 ns per neuron-step**.

**MVS is ≈ 1,180× slower than this x86 host.** D-128 had estimated "two to three
orders of magnitude" and said plainly it was not a measurement; the real figure
is past the top of that range.

Every configuration returned `rc=0` and **421 spikes**, bit-for-bit what the x86
build produces — so the timed computation is the verified one.

### 3.2 The duration bracket at N=1000

| Duration | Steps | Measured | Fits 600 s? |
|---|---|---|---|
| 1000 ms | 10,000 | **385 s** | ✅ |
| 1300 ms | 13,000 | **507 s** | ✅ (93 s margin, 15.5%) |
| 1500 ms | 15,000 | **658 s** | ❌ (58 s over, 9.7%) |

### 3.3 Cost is super-linear in duration — the finding that mattered

| Interval | Marginal cost |
|---|---|
| 1000 → 1300 ms | 0.407 s per ms |
| 1300 → 1500 ms | **0.755 s per ms** |

Per-neuron-step cost over the same points: 38.5 µs → 39.0 µs → **43.9 µs**.
Nearly flat, then jumping.

Spike counts — 421, 538, 624 — grow roughly in proportion to the step count
throughout, so **this is not simply more spiking**, and the mechanism is not
established. Activity concentrating in high-degree neurons would explain it;
nothing here measures that, and it is recorded as a question.

What matters operationally does not depend on the cause: **the curve steepens,
so extrapolating upward is unsafe.**

### 3.4 TBD-19 volumes at N=1000, 1300 ms maximum

| Content | Per run |
|---|---|
| Spike events (538 × 8 bytes) | ≈ 4.2 KB |
| Readout snapshots, 8 neurons × 72 B, every 100 steps | ≈ 9.4 KB |
| Readout snapshots, every 10 steps | ≈ 94 KB |
| *Full per-neuron snapshot, for comparison* | 8 KB **each**; 800 KB per 100 frames |

At ~390× slower than real time, a 10-step interval yields a frame every 0.39 s
of wall clock — ≈ 2.5 frames/second, 1,300 frames per run.

## 4. Design decisions and their consequences

**D-133** raised NFR-PERF-01 from 5 to 10 minutes — the first requirement this
project has changed on a measurement rather than a judgement. N=1000 was
excluded by 85 seconds against a bound chosen before anything had been measured.
**SR-EXT-03's candidate set became {250, 500, 1000}**; N=2000 and N=4000 remain
excluded and no plausible bound recovers them.

**D-134 → D-136 → D-138** set the maximum duration three times. The first two
were estimates and both were refuted by measurement:

| Decision | Value | Fate |
|---|---|---|
| D-37 | 5000 ms | refuted — 510 s at N=250, past even the raised bound |
| D-134 | 2000 ms | refuted — 770 s at N=1000, 170 s over |
| D-136 | 1500 ms | refuted by VL-42 — 658 s measured, 58 s over |
| **D-138** | **1300 ms** | **measured to fit: 507 s, 93 s margin** |

**D-137** stopped the pattern: settle it by measuring where the bound is crossed,
not by a third estimate. Measuring 1400 ms was then declined on evidence —
interpolation puts it near 581 s, a 19 s margin, numerically the same thin
position D-136 took, in exactly the region where §3.3 shows the curve steepening.

**D-139 / D-140** closed TBD-19: spike events for all neurons plus membrane
snapshots for the readout set only; the caller drives the run in chunks; the
interval travels in the request.

The decisive argument for chunking was **not** streaming. VL-43 measured one
request at 507 s, and Phase H runs ONFLY under CICS where holding a task that
long is precisely what Section 3.7's ICVR note forbids. The work must be
breakable into pieces for CICS regardless, so the live view comes nearly free.

## 5. Measurement methodology — and a guard that does not work

**Every clock inside the guest is untrustworthy for this.** `time()` and MVS's
own `IEF374I` CPU accounting are both driven from the host clock through
Hercules, so both advance through a host sleep while nothing executes.

The natural guard — compare elapsed against the CPU time MVS charges the step —
**was written, tested and discarded**. The contaminated run reported
`CPU 61MIN 21.92SEC` against 61 minutes 32 seconds elapsed, a ratio of **1.00**,
while roughly **38 of those minutes were spent in Modern Standby**.

The sound check is host CPU charged to the **Hercules process** against host
elapsed wall clock. `trust()` rejects below 70% of a core, and refuses to print
a G3 result it cannot certify at all. It was shown to fire: fed the real
contaminated shape it reports `37% of one core sustained` and
`*** MEASUREMENT REJECTED ***`.

Reported runs were additionally confirmed against the Windows event log: zero
Modern Standby transitions in each run's window.

Ancillary findings (VL-40): `clock()` is a PDPCLIB stub returning **−1** despite
`CLOCKS_PER_SEC` being defined as 1000; `time()` has one-second resolution.

## 6. Withdrawn claims

Three of my own, corrected in the record rather than quietly patched:

1. **"Every step performs identical work"** — false (§3.3). This put 578 s on a
   decision whose real value was 658 s, and made VL-41's entire duration-headroom
   column optimistic; it is annotated as upper bounds, not predictions.
2. **"The wall/CPU ratio catches a sleeping host"** — it does not (§5).
3. **"A hardware backend on z/OS pays the same marshalling"** — too pessimistic.
   VL-44 measured x86 NATIVE 3.6–4.3× *slower* than SOFT2C, but the expensive
   half is a byte-swap guarded by `#ifdef ONF_FP_LITTLE` that a big-endian host
   never compiles. The MVS figures are unaffected either way: SoftFloat 2c's
   `bits32` `float64` is structurally identical to `onf_f64`, so its conversion
   is two field assignments and no byte moves.

## 7. Verification

```bash
python tools/mvsclk.py                          # what clocks exist
python tools/mvsprf.py                          # the sweep
python tools/mvsprf.py --verify --steps 13000   # one configuration directly
```

`mingw32-make test` — green on SOFT3E, SOFT2C and NATIVE.

## 8. Not proven

- **One host, one day, single samples**, on a *quiet* synthetic network whose
  activity is driven by eight stimulus neurons and barely varies with N. A
  denser MaleCNS subcircuit would cost more.
- **Where between 1300 and 1500 ms the bound is crossed** is unmeasured, and
  §3.3 says not to interpolate it.
- **Whether the same steepening occurs at N=250 or N=500** is unmeasured.
- **VL-44's big-endian claim is argued, not measured** — no s390x build was
  timed, though Gate G0 provides the platform to do it.
- **TBD-06 remains open on seeds per rate** (D-135), deferred until the first
  full acceptance run measures the actual variance.

## 9. Related docs

- `docs/ONFLY-SRS.md` — D-133…D-140, VL-40…VL-44, TBD-06, TBD-19, NFR-PERF-01.
- `docs/implementations/2026-09-11-gate-g3-measured.md` — the measurement itself.
- `docs/implementations/2026-09-12-gate-g2-closed-transport.md` — the next gate.
