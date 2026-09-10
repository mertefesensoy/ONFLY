# 2026-09-11 — Signed connectivity: neurotransmitter to synaptic sign

| Field | Value |
|---|---|
| Date | 2026-09-11 |
| Author | ONFLY engineering session |
| Phase / gate | Phase C — Science (x86); scope set by D-53 |
| Owner decisions relied on | D-53, D-54, D-55, D-56 |
| Requirements touched | FR-PRP-03, SR-MOD-05, FR-PRP-01 |
| Open items closed | TBC-04 (by D-54 and D-55) |

## 1. Problem / motivation

FR-PRP-03 requires synapses aggregated into directed neuron-pair counts, each
pair signed from the presynaptic neuron's predicted neurotransmitter, and
SR-MOD-05 fixes the weight as `synapse count × sign × W_syn`. Without a sign
there is no inhibition, and without inhibition a recurrent LIF network of
125 million synapses does not settle — it saturates.

The sign depends entirely on a mapping the SRS deliberately left open as TBC-04,
because getting it wrong is quiet. Every neuron still fires; the network simply
behaves like a different animal.

## 2. What changed

| File | Change |
|---|---|
| `docs/ONFLY-SRS.md` | Recorded D-53…D-56; closed TBC-04; added VL-13. |
| `prep/signs.py` | New: scope, sign assignment, and the statistics both decisions require. |
| `tests/test_signs.py` | New: TP-01, 15 tests across the mapping, the assignment and the real data. |
| `docs/malecns-sign-assignment.json` | Generated statistics. |
| `Makefile` | New `prep` target, wired into `test`. |

## 3. Implementation approach

Three filters, applied in this order, each from an owner decision:

1. **D-56, scope.** Only annotated-neuron → annotated-neuron edges.
2. **D-54, sign.** ACh `+1`; GABA, glutamate, histamine `−1`; monoamines excluded.
3. **D-55, unknown.** Neurons with no definite prediction lose their outgoing edges.

The aggregation FR-PRP-03 asks for is already done upstream — one row per
ordered pair — so the module **verifies** that rather than recomputing it, and
raises if it ever stops holding. A file that turned out to hold one row per
*synapse* would otherwise produce a network whose weights were silently all 1.

`W_syn` is deliberately **not** applied here. It is a calibrated free parameter
(SR-CAL) and belongs to the calibration stage; baking it in now would make every
downstream artifact depend on a value that has not been fitted.

### A memory failure worth recording

The first version mapped each of 152 million rows to a transmitter *name* and
died:

```
numpy._core._exceptions._ArrayMemoryError: Unable to allocate 1.00 GiB
for an array with shape (1, 134873980) and data type object
```

The name is only ever needed to describe the far smaller *dropped* subset, so
bodies now map straight to an `int8` sign. The rewrite also replaced a
`drop_duplicates` over 152 million rows — which materialises a second frame of
the same size merely to answer a yes/no question — with a uniqueness check on
the already-scoped set. Applying D-56 first turned out to matter for tractability
as well as for correctness: it cuts the working set by a factor of six before any
per-row work happens.

## 4. Numerical details

Measured on the full dataset:

| Stage | Rows | Synapses | % of connectome synapses |
|---|---|---|---|
| Connectome as retrieved | 151,856,684 | 311,833,243 | 100% |
| After D-56 (neuron → neuron) | 26,028,386 | 125,365,933 | **40.2%** |
| After D-54/D-55 (signed) | 24,775,486 | 121,581,733 | **39.0%** |

Aggregation verified: 26,028,386 distinct `(pre, post)` pairs for 26,028,386
rows, so the upstream file is one row per pair exactly.

**Where the loss actually comes from.** This was measured rather than assumed,
and the answer was not the obvious one. The sign filter alone, without the
neuron restriction, would keep 92.7% of synapses — it costs only 7.3%. The
neuron→neuron restriction costs 59.8%. Once scoped, D-55's exclusion of
unknown-transmitter sources costs a further 1.2 points only.

**Dropped for want of a sign**, 1,252,900 pairs / 3,784,200 synapses:

| Predicted transmitter | Pairs |
|---|---|
| unclear | 814,328 |
| dopamine | 243,358 |
| octopamine | 149,420 |
| serotonin | 45,794 |

No source fell into an "(absent)" bucket, so every scoped presynaptic neuron
had a prediction row — the exclusions are all deliberate categories, not
missing data.

**Resulting balance:**

| | Pairs | Synapses | Share of synapses |
|---|---|---|---|
| Excitatory (+1) | 14,875,726 | 73,861,957 | 60.8% |
| Inhibitory (−1) | 9,899,760 | 47,719,776 | 39.2% |

162,894 distinct presynaptic and 183,971 distinct postsynaptic neurons survive.

The ~61/39 split is a direct consequence of D-54's decision that glutamate is
inhibitory. Had glutamate been signed `+1`, its 29,443 neurons would have moved
from the inhibitory column to the excitatory one, and the network would be
substantially more excitable. That is why the SRS marked it TBC rather than
letting an implementer assume it.

## 5. Design decisions

D-53 … D-56 are the owner's and are in Appendix A.1 with their alternatives.
Choices made by me within them:

- **Filter order.** D-56 before D-54/D-55, because scoping first is both the
  logical order (sign is a property of a node that is in the network) and six
  times cheaper.
- **numpy over pandas** for the per-row work, after the memory failure above.
- **Raise rather than aggregate** if the upstream file ever stops being
  one-row-per-pair. Silently aggregating would hide an upstream format change
  that deserves a human decision.

## 6. Verification

```
mingw32-make test
```

TP-01, 15 tests, exit 0. Structured in two layers: unit tests over a fixture
covering ACh, GABA, glutamate, histamine, a monoamine, `unclear`, and a body
absent from the table entirely; plus two tests against the real MaleCNS data.

Expected signs in the fixture are **written out literally**, not imported from
`NT_SIGN`. A test that imported the mapping and compared it to itself would
pass whatever the mapping said, which is worth nothing on the one decision most
likely to be got wrong by habit.

The two real-data tests are the ones that catch drift:

- every name in the mapping still occurs in the dataset, so the mapping cannot
  quietly go stale against a new release;
- every transmitter present in the dataset is either mapped or *deliberately*
  named as excluded — so a transmitter appearing in a future release cannot be
  silently dropped by a missing dictionary key.

```
Ran 15 tests in 0.593s
OK
```

The full engine suite was re-run unchanged and green in the same command.

### What these results do not prove

- The statistics above are **counts over the retrieved data**, computed on x86
  with Python 3.13 and pandas 2.3.3. They involve no simulation and no float
  backend; nothing here was run under GCCMVS, JCC, MVS 3.8j, Linux s390x or
  QEMU.
- **The signs are not validated against Shiu et al.** D-54 records the owner's
  classification; TBC-04 is closed by decision, not by comparison with the
  published code. If the reference treats glutamate differently, every weight
  of 29,443 neurons flips.
- **VL-13:** the network holds 40.2% of the connectome's synapses. Any ACC-3
  truncation-fidelity result is measured against a full-brain reference that is
  itself already this restricted, and must not be read as a whole-connectome
  simulation.
- **No network file has been emitted, no W_syn calibrated, no subcircuit
  extracted and no full-brain run performed.** ACC-1, ACC-3 and ACC-4 remain
  unevaluated. Phase C is not complete.
- TBC-01, TBC-02, TBC-05 and TBC-06 remain open, and TBD-07 and TBD-08 must be
  fixed before the first calibration run.

## 7. Related docs

- `docs/ONFLY-SRS.md` — Section 3.1 (FR-PRP-03), Section 6.1 (SR-MOD-05),
  Appendix A.1 (D-53…D-56), Appendix B (TBC-04 closed), Appendix D (VL-13).
- `docs/malecns-celltype-mapping.md` — the stimulus and readout sets (D-52).
- `docs/implementations/2026-09-10-phase-b-foundations.md`
