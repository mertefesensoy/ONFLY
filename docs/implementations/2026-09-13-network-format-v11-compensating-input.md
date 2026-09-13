# 2026-09-13 — Network format v1.1: the per-neuron compensating input

| Field | Value |
|---|---|
| Date | 2026-09-13 |
| Author | ONFLY senior engineer |
| Phase / gate | Phase C (Science, x86) — resolving the SR-EXT-03 escalation |
| Owner decisions relied on | D-190, D-191, D-192, D-193, D-194 (and D-184…D-189 for the evidence that led here) |
| Requirements touched | IR-NET-01, IR-NET-03, IR-NET-05, IR-NET-07, **IR-NET-09 (new)**, Appendix C, Appendix E (**ONF109E**, new), ACC-2, ACC-3, SR-EXT-01, SR-EXT-02, NFR-MNT-01, NFR-OBS-01 |
| Open items closed | none — SR-EXT-03's escalation is still open |

## 1. Problem / motivation

SR-EXT-03 requires N to be the smallest of {250, 500, 1000, 2000, 4000}
satisfying ACC-3, and escalates to the owner if none does. Twelve
constructions have now been measured (VL-66…VL-71) and none comes within 62%
of the full brain's readout response, where ACC-3 allows 10%.

The measurement that explains all twelve is in VL-70. Every kept neuron fires
in the full brain — SR-EXT-01 selects them for exactly that — but at 80 Hz,
seed 1, only **153 of 501** and **456 of 1,001** fire inside their own
subcircuit. What a truncation removes is not merely synaptic *mass* but the
*drivers* of most of its own neurons, and no selection rule and no rescaling
of a surviving edge can supply an input whose source is gone. That is why
every network-level fix failed and why the owner chose (D-190) to change the
model instead.

Without this, the MVS MVP would have to ship a subcircuit whose readout
behaviour bears no quantitative relation to the brain it is cut from, and
Section 6.4 would have to be amended to say so.

## 2. What changed

| File | Change |
|---|---|
| `layout/master.py` | Header grows `offbias` (u32 @152) and `nbias` (u32 @156); `paylen`→160, `paycrc`→164, `hdrcrc`→168; length 172; CRC covers 0–167; `NET_VMINOR` = 1. |
| `layout/netwrite.py` | Writes the compensating-input section and asserts its three invariants. |
| `layout/netread.py` | Reads and re-checks it; raises ONF109E. |
| `engine/include/onfker.h` | `struct onfnet` grows `nbias`, `brate`, `bias`. |
| `engine/src/onfker.c` | Appendix C step 0 (row selection) and one added `⊕` per neuron per step. |
| `engine/include/onfdec.h`, `engine/src/onfdec.c` | `ONFD_BIAS`; `onfldp` grows two parameters; table decoded, validated, and counted in the FR-LOD-04 memory budget. |
| `engine/src/onflyeng.c` | `BIAS ROWS` in the NFR-OBS-01 manifest; ONF109E in the message table. |
| `oracle/onfly_oracle/kernel.py` | `Network.bias_row()` and the matching ARRIVALS change. |
| `prep/emit.py` | `build_network` forwards `bias_rates` / `bias_rows`. |
| `prep/extract.py` | `--ratebias` (per-rate full-brain activity), `--biasnet` (compensated subcircuits + ACC-3), `--refixture` (re-emit every fixture at v1.1). |
| `tests/test_bias.py` | **TP-08**, 14 cases: row selection, the tie rule, the rate 0 invariant, header fields. |
| `tests/run_dec.py` | **TE-10**, 3 cases: the C decoder must reject a malformed table with ONF109E. The sample network now carries a real table. |
| `tests/tstsyn.c`, `tests/tstgld.c`, `tests/run_syn.py` | Header offsets now come from the generated header instead of literals. |
| `tests/tstker.c`, `tests/tstprf.c` | Hand-built `struct onfnet`s initialise the new fields. |
| `tools/gensyn.py`, `tools/runnet.c` | `ONFSYN_NBIAS`; runner allocates and passes the table. |
| `Makefile` | TP-07 and TP-08 join the `prep` target. |
| `docs/ONFLY-SRS.md` | D-190…D-193; VL-70, VL-71; IR-NET-09; ONF109E; Section 4.1 tables; Appendix C amendment; Phase C status. |

## 3. Implementation approach

### 3.1 Where the input enters, and why there

The kernel's state is `u` (membrane, relative to `V_rest`) and `g` (synaptic).
A presynaptic spike adds its weight to `g` through the delay ring. The
compensating input therefore belongs in exactly the same place a real arrival
does — ARRIVALS, step 1 — because that is what it stands in for. It is added
after the delayed arrivals and before anything reads `g`, which fixes its
position in the NR-07 operation order:

```
g[i] = g[i] (+) ring[slot][i]
ring[slot][i] = +0.0
g[i] = g[i] (+) bias[i]
```

Exactly one further `⊕` per neuron per step, and only when the network
carries a table.

**A network with `nbias` = 0 must produce version 1.0's arithmetic exactly.**
That is not decoration: it is what keeps `data/calibration/acc4.json` — the
full-brain ACC-3 reference, 151 runs — valid across the format change. So the
two cases are written as two loops rather than one loop adding `+0.0`; under
NR-07 an added operation is an added operation even when its operand is zero.

### 3.2 Row selection (D-191)

The table is indexed by stimulus rate. Selection is by **nearest sampled
rate, ties to the lower**, clamping beyond either end, decided once per
request before the first step.

Selection is deliberately an *integer* comparison. Interpolating between rows
would need an integer-to-binary64 conversion, and the `onf_fp` API is
`onffadd`, `onffsub`, `onffmul`, `onfflt`, `onffle`, `onffabs`, `onffnf`,
`onffzer`, `onffbit` — there is no such operation, and NR-07 lists none.
Adding one would mean a new primitive to validate on three platforms and two
soft-float libraries, to buy accuracy between sampled rates that no
acceptance criterion is evaluated at.

### 3.3 Protecting ACC-2

ACC-2 says a request with rate 0 produces zero spikes in every neuron, on
every platform and backend, and calls it deterministic. Once the engine can
add a constant to every neuron's `g` at every step, that stops being free: a
table whose first row were non-zero would make neurons fire with no stimulus
at all, everywhere at once, and the failure would look like a modelling
result rather than a corrupt file.

So the invariant is checked three times, by three different implementations:
`netwrite.build` asserts it when writing, `netread.read` re-checks it when
reading, and `onfldp` re-checks it in C **on the raw big-endian bytes**. The
last of those matters most: it means no floating-point comparison — performed
by the very arithmetic under test — stands between the file and the
criterion. A violation is ONF109E.

### 3.4 A drift class this change exposed

Three files read header fields at hand-written offsets: `tests/tstsyn.c`
(`OFF_PAYCRC 156`, `OFF_HDRCRC 160`, `HDRCRC_COVER 160`, `work[164 + 40]`),
`tests/tstgld.c` (`buf[156]`, `buf[48]`) and `tests/run_syn.py`
(`data[156:160]`). Three of those offsets moved. The symptom was a payload
CRC read as `00000003` — which is `nbias` — and every synthetic fingerprint
failing.

They now take their offsets from the generated header, which is what
NFR-MNT-01 and IR-COM-01 exist for. The literals had been correct for as long
as the format had not changed, which is precisely how this kind of defect
survives review.

A second class: `tests/tstker.c` and `tests/tstprf.c` build a `struct onfnet`
by hand rather than decoding one. The new fields were uninitialised stack
contents, and a non-zero `nbias` sent the kernel through a null `bias`
pointer — `tstker` exited 0xC0000005. Both now set all three fields
explicitly.

### 3.5 Contracts introduced

* `netwrite.build(..., bias_rates, bias_rows)` — both None or both given.
  Asserts ascending rates, first rate 0, zero first row, one value per neuron
  per row. Pure.
* `netread.read()` — returns `bias_rates` / `bias_rows`, empty when absent;
  raises `NetworkFileError(109)` on a malformed table.
* `okernel.Network.bias_row(rate_hz)` — returns the selected row, or None
  when the network has no table. Pure.
* `onfldp(..., brate, bias)` — caller storage for `nbias` and `nbias × n`
  values, or null when `nbias` is 0. Returns `ONFD_BIAS` on a malformed
  table. No allocation, no I/O, no static data.
* `extract.bias_table(arrays, nodes, rate_act)` — pure; returns
  `(rates, rows)`.

## 4. Mathematical / numerical details

### 4.1 What the compensating input is

Let *S* be the kept set. For a kept neuron *i*, the truncation removes every
edge whose target is *i* and whose source is outside *S*. Each spike of such
a source *j* would have added *w<sub>ji</sub>* to *i*'s synaptic variable,
where *w<sub>ji</sub>* = signed synapse count × W_syn. If *j* fires
*S<sub>j</sub>(R)* times in a run of *T* steps at stimulus rate *R*, its mean
contribution per step is *w<sub>ji</sub>·S<sub>j</sub>(R)/T*. Summing over
every dropped presynaptic neuron of *i*:

> **bias[R][i] = Σ<sub>j ∉ S, j→i</sub> w<sub>ji</sub> · S<sub>j</sub>(R) / T**

with *T* = 1000 ms / 0.1 ms = 10,000. Dividing by the measurement's own step
count is what makes this a **per-step** expectation, so a request of any
duration receives the same input per step.

This is a mean-field closure: the dropped subnetwork is replaced by its mean
effect. It is signed, so inhibition dropped from *i* is subtracted exactly as
excitation dropped from *i* is added — the two are not treated separately,
because what *i* experiences is their sum.

Rate 0's row is zero by construction and never measured: ACC-2 fixes the
answer, and a measurement could only contradict a criterion that is true by
definition.

Every kept neuron receives a row entry, **stimulus neurons included**. In the
full brain a stimulus neuron receives synaptic input like any other, and its
Poisson drive is delivered through `force`, not through `g`, so the two do
not interact.

### 4.2 Steady-state scale, for reading the numbers

Within a step the order is: add arrivals and bias to *g*, then decay
*g′ = P22·g*. A constant bias *b* therefore accumulates to a fixed point

> *g\** = P22·*b* / (1 − P22) ≈ 0.9802·*b* / 0.0198 ≈ 49.5·*b*

and *u* relaxes toward *g*. With U_th = 7.0 mV, a sustained bias above about
0.14 mV is enough on its own to drive a neuron to threshold. This is the
arithmetic that makes VL-71's largest value — 18.55 in the N = 1000 table's
160 Hz row — obviously wrong rather than merely large.

### 4.3 Why the estimator changed (D-193)

*S<sub>j</sub>(R)* was first estimated as a mean over 3 seeds. The measured
total activity is strongly non-monotonic — 14,148 / 73,018 / 72,119 / 88,066
/ 96,425 / 103,071 / **457,186** / 322,604 spikes at 10 / 20 / 40 / 60 / 80 /
120 / 160 / 200 Hz — because a run either ignites the hyperactive population
VL-66 found (191 neurons sustaining 250–280 Hz) or does not. Per neuron the
distribution over seeds is therefore **bimodal**, and a mean of a bimodal
quantity sits between the modes, above the typical run when the upper mode is
far away.

The owner chose (D-193) to re-measure with 15 seeds and to use the per-neuron
**median**, which ignores the ignition tail instead of averaging it in. Both
estimators are stored, so VL-71 stays reproducible from the artifact that
produced it.

## 5. Design decisions

Owner's, recorded in Appendix A.1 before any dependent code was written:

* **D-190** — resolve the escalation by changing the model, not ACC-3. The
  alternatives were to make ACC-3 a selection-and-reporting criterion
  (selecting B1-n500 at 62%), to make it a reported measurement with the MVP
  completing on the other six criteria, or to recalibrate W_syn per
  subcircuit. Costs accepted: a format version bump, a kernel change in
  normative Appendix C (frozen by D-71), and an oracle change.
* **D-191** — per-rate table with nearest-row selection, over linear scaling
  (refuted by measurement) and interpolation (needs a primitive that does not
  exist).
* **D-192** — the eight-step plan as presented.
* **D-193** — 15 seeds and a median.

Architect's (engineer's) choices, stated so they are not mistaken for the
owner's:

* Two ARRIVALS loops rather than one adding zero (§3.1). Not a free choice:
  NR-07 makes it the difference between preserving v1.0 arithmetic and not.
* Checking the rate 0 row on raw bytes rather than after conversion (§3.3).
* A real table in the golden `path` fixture and in the synthetic network,
  rather than `nbias` = 0 everywhere: a code path exercised only where it is
  hardest to test is one nobody has tested.
* `nbias` = 0 for the SR-EXT-01 subcircuits under `data/networks/`, keeping
  every compensated construction under `data/calibration/` (D-189), so the
  directory is never ambiguous about which rule produced what.
* **Filenames keep their `v1.0` infix.** That string names the MaleCNS
  dataset version (`male-cns:v1.0`), not the file format, whose version lives
  in the header. Renaming would ripple into `tests/run_gld.py`, both
  manifests and the MVS transport tooling for no gain.

## 6. Verification

Everything below ran **in this session** on x86-64 Windows 11, mingw32 gcc
6.3.0, Python 3.13.14.

**Full suite, all three float backends.**

```
mingw32-make test
```

Exit 0. Final line: `ONFLY: NR-05 + licence + col80 + C-04 + C-04/MVS lints,
TT-01, TT-02, SoftFloat 2c vs TestFloat and its known answers, D-104 shift
reference, NR-04 shims, TU-01..TU-07, kernel, the embedded-network engine
path, TE-01..TE-09, ACC-5 golden suite and TP-01 all passed on SOFT3E, SOFT2C
and NATIVE`.

**TE-10, the new decoder cases** (`mingw32-make decode`):

```
ok   TE-10 rate 0 row not zero            LOAD rc=109
ok   TE-10 rates not ascending            LOAD rc=109
ok   TE-10 table does not start at 0      LOAD rc=109
ok   end-to-end file->decode->load->run   16 neurons match the oracle, 23 spikes
```

The end-to-end line is the important one: it runs a network **with** a table
through the C engine and the Python oracle independently and requires all 16
neurons to agree.

**TP-08** (`python tests/test_bias.py`): `Ran 14 tests … OK`.

**The embedded-network path** (`mingw32-make syn`), which is the MVS path's
x86 rehearsal, with the synthetic network carrying a 3-row table:

```
run_syn [SOFT3E backend, WIN32]: 60 passed, 0 failed
run_syn [SOFT2C backend, WIN32]: 60 passed, 0 failed
cmpback: SOFT3E, NATIVE, SOFT2C agree bit-for-bit on 41 result lines
```

**The science result, in two passes.**

*Pass 1, VL-71* (`--ratebias --jobs 8`, 24 runs in 1,403 s, 3 seeds, mean;
`--biasnet --jobs 14`, 450 runs in 217 s). The compensation rescues the
N = 250 subcircuit from complete silence — the first construction of twelve
to change a truncation's *qualitative* behaviour — but no size meets ACC-3,
and at N = 1000 it makes the fit worse, for the estimator reason in §4.3.

*Pass 2, VL-72* (`--ratebias --jobs 8`, **120 runs in 6,770 s**, 15 seeds,
median; `--biasnet --jobs 14`, 450 runs in 214 s). §4.3's hypothesis is
confirmed directly: mean ÷ median of total activity is 1.80 / 1.02 / 1.76 /
0.99 / 0.97 / 0.98 / 1.42 / 1.37 at 10 / 20 / 40 / 60 / 80 / 120 / 160 /
200 Hz — the ignition tail inflated the estimate at exactly the four rates
whose networks overshot and nowhere else. N = 1000's largest bias falls from
18.55 to 8.12.

Mean MN9 rate over seeds 1…30, full brain 3.67 / 14.35 / 28.38 / 68.38 /
88.80 Hz:

| construction | 10 | 40 | 60 | 120 | 200 | worst | worst >10 Hz |
|---|---|---|---|---|---|---|---|
| C-n250 (median) | 0.00 | 0.00 | 49.50 | 101.00 | 129.00 | 100% | 100% |
| C-n500 (median) | 0.28 | 9.55 | 35.52 | 94.20 | 115.25 | 92% | **38%** |
| C-n1000 (median) | 0.12 | 28.47 | 57.32 | 110.68 | 125.62 | 102% | 102% |
| C-n500 (3-seed mean) | 1.40 | 22.23 | 41.42 | 89.97 | 121.07 | 99% | 55% |
| n500 uncompensated | 0.00 | 8.53 | 18.07 | 29.98 | 37.20 | 100% | 58% |

**All fifteen comparisons fail.** Two different "best" emerge and they
disagree: on ACC-3's own statistic — the worst rate — the leader of thirteen
constructions is still B1-n500 at 62% (VL-70), because it fires 1.40 Hz at
10 Hz where C-n500 fires 0.28; above that floor, over 40–200 Hz, the leader
is C-n500 (median) at 38%.

**Why 10 Hz resists every construction, and it is not a construction
problem.** VL-64 measured the full brain's own 10 Hz response as 3.67 Hz with
a standard deviation of **4.22** over 30 seeds — a spread larger than the
mean, because MN9 fires at 10 Hz only in the seeds where the network ignites.
ACC-3's tolerance there is the 1 Hz absolute floor. So at 10 Hz the criterion
asks a 500-neuron truncation to reproduce, to within 1 Hz, the *frequency of
a rare stochastic event* in a 184,099-neuron network. That is a property of
the criterion meeting this model.

**Where it was left (D-194).** The owner declined to weaken ACC-3 on thirteen
failed constructions and chose to keep looking for one that meets it as
written. The two named next attempts are a compensating input that varies
*within* a run, and one *fitted* per rate against the full brain rather than
measured from it. The session stopped here because the owner is travelling
with the development host, not because the work is complete.

**What these results do NOT prove** (SRS Appendix D):

* Nothing ran on MVS 3.8j, Linux s390x or z/OS. The engine change compiles
  and passes on x86-64 only; the MVS half of the embedded-network path
  (`tools/mvssyn.py`) has not been re-run since the format changed, and
  **the v1.1 header has never been decoded by GCCMVS**.
* The SOFT3E and SOFT2C backends were exercised on x86 only.
* ACC-1 was not evaluated on any compensated network.
* The table is piecewise constant between sampled rates, so a request at an
  unsampled rate uses a neighbour's row. Golden request G-07 (rate 9999)
  clamps to the 200 Hz row.
* The v1.1 fixtures' digests are recorded but no transport test (Gate G2's
  sixty transfers) has been re-run against them.

**A side effect, reported rather than buried.** The `.bin` fixtures were
hard-linked into this worktree from `.claude/worktrees/onfly-senior-engineer-dd7dca`
to avoid copying 300 MB. Re-emission wrote **through those links**, so that
worktree's six network files are now the v1.1 versions and no longer match
its own checked-out manifest. They are gitignored, regenerable artifacts, and
they do match the manifest on `main` as of this session; the links have since
been broken so nothing further propagates. Flagged for the owner.

## 7. Related docs

* `docs/ONFLY-SRS.md` §4.1 (IR-NET-01…09), §6.3, §6.4, Appendix A.1
  D-184…D-194, Appendix C, Appendix D VL-66…VL-72, Appendix E ONF109E.
* `docs/implementations/2026-09-13-truncation-compensation.md` — the eleven
  network-level constructions this replaced.
* `data/calibration/acc3-biasnet.json`, `rate-activity.npz`,
  `data/networks/MANIFEST.json`.
