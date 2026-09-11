# 2026-09-11 — Reconciling the kernel with Shiu et al.'s published code

| Field | Value |
|---|---|
| Date | 2026-09-11 |
| Author | ONFLY engineering session |
| Phase / gate | Phase C — Science (x86); scope set by D-64 |
| Owner decisions relied on | D-64 … D-73 |
| Requirements touched | SR-MOD-01, SR-MOD-02, SR-MOD-03, SR-MOD-04, FR-SIM-01, FR-SIM-03, Appendix C, ACC-5 |
| Open items closed | TBC-01, TBC-02, TBC-05 |

## 1. Problem / motivation

Four open items — TBC-01, TBC-02, TBC-05 and TBC-06 — were all defined as
"confirm against Shiu et al." Until that happened, ONFLY's kernel was a careful
reading of a paper, and SRS Appendix C said so: it was marked **draft**.

That mattered more than a documentation caveat. SR-MOD-03 requires the
integration method and within-step event ordering to *match* Shiu's published
implementation, and ACC-4 judges ONFLY against his reference curve. Calibrating
`W_syn` against a reference while running a subtly different kernel would
produce a carefully fitted wrong answer.

Shiu et al.'s model code is public (`github.com/philshiu/Drosophila_brain_model`,
MIT), so the question was answerable by reading it.

## 2. What changed

| File | Change |
|---|---|
| `docs/ONFLY-SRS.md` | D-64…D-73; closed TBC-01, TBC-02, TBC-05; amended Appendix C; corrected SR-MOD-01; Appendix C is now NORMATIVE. |
| `reference/shiu/` | Vendored `model.py` and `LICENSE` with digests. |
| `engine/src/onfker.c`, `engine/include/onfker.h` | Kernel amended for D-67, D-68, D-69; `isstim` added to the state. |
| `oracle/onfly_oracle/kernel.py` | The same amendments, implemented independently. |
| `layout/netread.py` | New: Python reader for the network format. |
| `tests/run_gld.py` | Golden suite now runs against the real 2-hop network (D-70). |
| `tests/tstgld.c`, `tests/tstdec.c`, `tests/tstker.c`, `tools/runnet.c` | Allocate `isstim`; `tstgld` sizes storage from the file. |

## 3. What the code said

**Confirmed exactly — the SR-MOD-02 table needed no change at all:**

| Parameter | SRS | `model.py` |
|---|---|---|
| V_rest, V_reset | −52 mV | `v_0`, `v_rst` = −52 mV |
| V_th | −45 mV | `v_th` = −45 mV |
| τ_mbr | 20 ms | `t_mbr` = 20 ms |
| τ_syn | 5 ms | `tau` = 5 ms |
| t_rfr | 2.2 ms | `t_rfc` = 2.2 ms |
| T_dly | 1.8 ms | `t_dly` = 1.8 ms |
| W_syn | 0.275 mV | `w_syn` = 0.275 mV |
| dt | 0.1 ms | Brian2 default |

`method='linear'` is Brian2's exact linear integration, confirming the **exact
propagator** rather than forward Euler. The equations match too: Shiu writes
`dv/dt = (v_0 - v + g)/t_mbr`, and with `u = v − v_0` that is exactly
SR-MOD-01's `du/dt = (g − u)/τ_mbr`.

Shiu's `t_run = 1000 ms` and `n_run = 30` independently corroborate TBD-06's
proposed standard duration and seed count, and D-37's provisional choice.

**Five discrepancies, every one against ONFLY:**

| Shiu | Appendix C as drafted | Decision |
|---|---|---|
| `dg/dt … (unless refractory)` — g frozen | g decayed each refractory step | D-67 |
| `eq_rst: g = 0*mV` — g reset on spike | g untouched on spike | D-67 |
| `eq_th: v > v_th` — strict | `u >= U_th` | D-69 |
| `rfc = 0` for Poisson targets | refractory gating applied | D-68 |
| Poisson adds 68.75 mV to `v` | stimulus forces a spike | D-68 (kept) |

The last was kept deliberately: `w_syn × f_poi` = 0.275 × 250 = 68.75 mV against
a 7 mV threshold gap means every Poisson event causes a spike anyway, so forcing
one is behaviourally equivalent and avoids adding a voltage-injection path.

## 4. Why the amendments matter numerically

They are not cosmetic. The same seven kernel cases, before and after:

| Rate (Hz) | 0 | 40 | 120 | 200 | 9999 |
|---|---|---|---|---|---|
| Before | 0 | 16 | 39 | 56 | **40** |
| After | 0 | 17 | 51 | 86 | **810** |

**The 9999 Hz case is the proof of D-68.** With refractory gating, a stimulus
neuron could fire at most once per 22 steps, so 100 steps gave about 4.5 spikes
each across 8 neurons — roughly the 40 observed. Without it they fire nearly
every step: about 100 each, roughly the 810 observed. ONFLY had been **silently
discarding stimulus spikes that Shiu's model delivers**, and biasing precisely
the high-rate end that ACC-4 tests.

ACC-2 silence at rate 0 survives, as it must: with no stimulus there is no other
noise source.

## 5. A verification hole this exposed

After amending four kernel semantics, **not one golden fingerprint changed**.

The golden suite ran against a synthetic 32-neuron network whose readouts never
fired: all 80 output entries were `spk=0, lat=-1`. Each fingerprint therefore
depended only on the request fields and eight constant `(id, −1, 0)` entries, so
it could not detect a kernel change at all. ACC-5 is the project's central
determinism claim, and it was resting on a test blind to the thing it exists to
check.

D-70 points the suite at the real 2-hop MaleCNS network instead, where MN9
demonstrably spikes.

`layout/netread.py` was written to make that possible, and is useful beyond it:
it is a second, independent implementation of the decode `engine/src/onfdec.c`
performs. The C reads with explicit byte shifts in C89; this reads with `struct`
in Python. Agreement is therefore evidence about the **format**, not a
shared-code tautology. Round-trip on the emitted file confirmed `u_th = 7.0`,
`g_eps = 2.2250738585072014e-308` (D-60), the three propagator coefficients and
`paycrc = DDF5DA8C` all read back exactly as written.

## 6. Verification

```
mingw32-make test
```

The C kernel and the Python oracle were amended **independently** and still
agree: `run_ker` 449 passed on both backends, `cmpback` identical on 778 lines.

### Fixing the hole, and proving it is fixed

D-70 pointed the suite at the real 2-hop network (13,521 neurons). That made
fingerprints kernel-sensitive but cost the Python oracle about 1.9 billion
neuron-steps across the suite; a run exceeded 35 minutes without finishing, and
a suite nobody can afford to run stops being run.

D-74 proposed restricting to neurons on a stimulus-to-MN9 path. Implemented
literally that is 28 neurons, and **MN9 never fires in it**: MN9 has 321
presynaptic partners and needs their summed input to cross threshold. That
fixture would have been exactly as blind as the one it replaced.

D-75 settled it: stimulus + hop-1 successors + every MN9 input + MN9 — **913
neurons, 72,852 edges**.

| Fixture | Neurons | MN9 spikes at 40 / 120 / 200 Hz |
|---|---|---|
| synthetic (original) | 32 | 0 / 0 / 0 |
| D-74 literal | 28 | 0 / 0 / 0 |
| 2-hop (D-70) | 13,521 | fires, but oracle > 35 min |
| **D-75 fixture** | **913** | **138 / 194 / 187** |

The whole suite now runs in **1m54s** and `make test` from clean in **2m11s**.

**The proof that the blindness is gone.** Reverting just one of the four
amendments — D-67's reset of `g` on spike — and rerunning:

```
run_gld [NATIVE backend]: 5 passed, 9 failed
  ok   G-01 ... fp=21BBF610
  FAIL G-02 C fp=7C14D717 | oracle fp=D89BE9DD
  FAIL G-03 C fp=4B1606BB | oracle fp=EA2EF71F
```

Nine of fourteen fail. Before the fixture change, four simultaneous kernel
amendments produced **zero** failures. G-01 still passes, correctly: at rate 0
nothing spikes, so no kernel semantics are exercised.

### What these results do not prove

- **x86 32-bit mingw32 gcc 6.3.0, SOFT and NATIVE backends.** Nothing ran under
  GCCMVS, JCC, MVS 3.8j, Linux s390x or QEMU.
- **The reconciliation is against `model.py`, not against the paper's methods
  section.** The code is what produced the published results, but if the two
  disagree this followed the code.
- **TBC-06 remains open** — the reference *curve* has not been obtained, so no
  calibration has been attempted and ACC-4 is unevaluated.
- **`W_syn` is still the uncalibrated FlyWire value**, and VL-12 and VL-13 still
  apply.

## 7. Related docs

- `docs/ONFLY-SRS.md` — Section 6.1 (SR-MOD-01, corrected), Appendix A.1
  (D-64…D-73), Appendix B (TBC-01, TBC-02, TBC-05 closed), Appendix C (normative).
- `docs/implementations/2026-09-11-full-brain-run.md`
