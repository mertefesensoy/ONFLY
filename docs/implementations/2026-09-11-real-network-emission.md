# 2026-09-11 — Emitting real MaleCNS networks; the engine runs the fly

| Field | Value |
|---|---|
| Date | 2026-09-11 |
| Author | ONFLY engineering session |
| Phase / gate | Phase C — Science (x86) |
| Owner decisions relied on | D-37, D-52, D-54, D-55, D-56, D-57, D-58, D-59, D-60 |
| Requirements touched | FR-PRP-06, FR-PRP-07, IR-NET-01…08, FR-LOD-01…05, SR-MOD-05, NR-08 |
| Open items closed | none. G_EPS fixed by D-60 |

## 1. Problem / motivation

Everything up to this point had been verified against a **synthetic** network
built inside a test. That proves the kernel computes Appendix C and the decoder
enforces IR-NET, but it does not prove ONFLY can process the actual connectome:
real data has 13,521 neurons rather than 64, 1.7 million edges rather than 512,
and a degree distribution nothing like a generated one.

It also leaves the project's central claim untested. ONFLY exists to answer
*"if this fly tastes sugar, what do its feeding motor neurons do?"* Until a real
network runs, that question has never actually been put to the engine.

## 2. What changed

| File | Change |
|---|---|
| `docs/ONFLY-SRS.md` | Recorded D-57…D-60. |
| `prep/emit.py` | New: builds and emits network files from signed connectivity. |
| `layout/netwrite.py` | Vectorised section packing and the IR-NET-06 order check. |
| `tests/tstdec.c` | Buffers sized from the file and header instead of fixed at compile time. |
| `data/networks/MANIFEST.json` | Generated: digests, parameters and their status. |

## 3. Implementation approach

`prep/emit.py` applies the owner's filters (D-56 scope, D-54/D-55 signs), selects
a node set, remaps body ids to contiguous indices **sorted ascending by body id**
so the mapping is reproducible and independent of edge order, then builds CSR.

Sorting edges by `(pre, post)` delivers both CSR requirements at once: rows
grouped, and targets strictly ascending within each row as IR-NET-06 demands.
That ordering is normative rather than cosmetic — floating-point addition does
not associate, so a row accumulated in another order is a different answer.

`W_syn` is applied **here and only here**. `prep/signs.py` deliberately stops at
the signed synapse count, because `W_syn` is a calibrated free parameter
(SR-CAL); baking it in earlier would make every intermediate artifact depend on
a value nobody has fitted yet.

## 4. Numerical details

Propagator coefficients, computed on x86 in binary64 and shipped as bit patterns
so no target platform converts decimal to binary floating point (FR-PRP-06,
NR-06). With `dt = 0.1 ms`, `τ_mbr = 20 ms`, `τ_syn = 5 ms`:

- `P11 = e^(−dt/τ_mbr)` = `0x3FEFD7246927D28B`
- `P22 = e^(−dt/τ_syn)` = `0x3FEF5DC99BADEC5B`
- `P12 = τ_syn/(τ_syn − τ_mbr) · (e^(−dt/τ_syn) − e^(−dt/τ_mbr))`

`U_th = V_th − V_rest = −45 − (−52) = 7.0` mV (`0x401C000000000000`), and
`U_reset = V_reset − V_rest = 0`.

**G_EPS (D-60) = 2⁻¹⁰²², bit pattern `0x0010000000000000`**, about
`2.2250738585072014e-308`. This is the smallest *normal* binary64, so clamping
below it removes exactly the subnormals and touches no normal value — which is
precisely what NR-08 says the clamp is for. The alternatives considered (1e-300,
1e-30) would silence normal values the model may legitimately carry, making them
modelling changes rather than numerical hygiene.

## 5. Design decisions

D-57 … D-60 are the owner's. Mine within them:

- **Node indices sorted by body id**, so the index mapping is a deterministic
  function of the node set alone.
- **Sort by `(pre, post)`** to satisfy row grouping and IR-NET-06 in one pass.
- **Refuse to emit** a network missing any stimulus or readout neuron. A network
  with no readout is not a network worth writing, and failing loudly beats
  emitting one that silently reports nothing.

## 6. Verification

The C engine on the real 2-hop network:

```
RESULT rc=0 need=2379696 len=20615112
DECODED n=13521 e=1704385 ns=14 nr=2 dtus=100 delay=18 refract=22
CONSTS uth=401C0000:00000000 p11=3FEFD724:6927D28B p22=3FEF5DC9:9BADEC5B
LOAD rc=0
```

The constants read back are bit-identical to those the emitter wrote, so the
whole path — compute on x86, serialise big-endian, integrity-check, decode by
byte shift — is lossless.

**The fly responds.** 500 steps (50 ms) at 120 Hz, seed 1:

| | Result |
|---|---|
| Sugar stimulus neurons (PhG9 + dorsal_tpGRN) | 14 neurons, 1–8 spikes each |
| Network total | 1,147 spikes across 404 neurons |
| **MN9 readout, neuron 127** | **8 spikes, first at 28.0 ms** |
| **MN9 readout, neuron 2160** | **1 spike, first at 48.9 ms** |

A first MN9 spike at 28 ms after stimulus onset is a plausible sensorimotor
latency across a two-synapse pathway with 1.8 ms synaptic delays.

The full engine suite was re-run and is green, exit 0.

### Two defects this exposed

**A static buffer that could not hold a real network.** `tests/tstdec.c` had a
4 MB buffer; on the 20.6 MB file the decoder returned ONF106E for a truncated
read — the guard behaving exactly as designed — and a static array large enough
for a real network would not link on a 32-bit host. Buffers are now sized from
the file and the header.

**A writer that did not scale.** `netwrite.py` packed sections with
`struct.pack` over unpacked argument lists and checked IR-NET-06 with a nested
Python loop, both untenable at 24.8 million edges. Both are now vectorised, with
the `struct` path kept for hosts without numpy; the two produce identical bytes.
The order guard still fires:

```
AssertionError: IR-NET-06: row 0 targets are not strictly ascending
(target[1]=1 follows 5)
```

### A third defect: the memory gate was understating by tenfold

Running the full 300 MB network exposed a real FR-LOD-04 defect. The
requirement is "the memory needed for **the decoded network and** simulation
state", but `onfdec` counted only the state — `u`, `g`, the delay ring and the
four int32 arrays — and omitted the decoded CSR arrays entirely.

On a real connectome the network half dominates by an order of magnitude:

| | Before | After |
|---|---|---|
| Reported requirement, full network | 32,401,424 | **330,443,656** |
| Against a 100 MB budget | `rc=0`, accepted | **`rc=105`**, refused |

A gate that understates by tenfold is worse than no gate, because it is
trusted. On a 24-bit region (C-01, NFR-MEM-01) that is the difference between a
clean ONF105E refusal and an abend.

The fix could not simply widen to a 64-bit accumulator: NR-04 confines 64-bit
integer types to SoftFloat and the float layer, and `-pedantic` duly rejected
`long long` in the decoder. It uses checked 32-bit multiply and add helpers
instead, which test before they compute and saturate rather than wrap, so NR-11
is honoured too. Header counts whose u32 value exceeds INT32_MAX arrive negative
and are refused rather than wrapped into a small positive size.

### What these results do not prove

- **x86, 32-bit mingw32 gcc 6.3.0, NATIVE backend** for the network run above.
  Nothing here ran under GCCMVS, JCC, MVS 3.8j, Linux s390x or QEMU.
- **The MN9 response is not an ACC-1 evaluation.** It is one seed at one rate on
  an **uncalibrated** network whose parameters are all still TBC-02. ACC-1
  requires the validation rates with 30 seeds each and TBD-06 settled. What this
  shows is that the pathway conducts, not that it conducts correctly.
- **`W_syn = 0.275` is the FlyWire value**, not a MaleCNS calibration. SR-CAL-01
  requires recalibration on the full-brain model, which has not been done.
- **Neither network is the SR-EXT-01 subcircuit**, which is defined by activity
  in a calibrated full-brain run.
- **VL-12** — the stimulus set is pharyngeal and taste-peg where Shiu et al. use
  labellar. **VL-13** — the network holds 40.2% of the connectome's synapses.
- The 20.6 MB network is far beyond the 24-bit MVS region (C-01); NFR-MEM-01
  sizing for TK5 has not been attempted.

## 7. Related docs

- `docs/ONFLY-SRS.md` — Section 4.1 (IR-NET), Appendix A.1 (D-57…D-60),
  Appendix D (VL-12, VL-13).
- `docs/implementations/2026-09-11-sign-assignment.md`
- `docs/malecns-celltype-mapping.md`
