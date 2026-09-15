# 2026-09-15 — Phase E slice 5: the acceptance sweep, and the one that fails

| Field | Value |
|---|---|
| Date | 2026-09-15 |
| Author | ONFLY senior engineer |
| Phase / gate | Phase E — MVS MVP |
| Owner decisions relied on | D-279, D-280, D-282, D-283, D-285, D-286, D-287, D-288, D-289, D-290, D-291 |
| Requirements touched | ACC-1 … ACC-7, SR-CAL-05, SR-EXT-02, NFR-MEM-01, NFR-PERF-01, NFR-OBS-01, FR-BAT-01, FR-BAT-04, FR-BAT-05, FR-BAT-06, FR-LOD-02, IR-JCL-04, IR-COM-05, TX-01, TX-02, TX-04 |
| Open items closed | none |

## 1. Problem / motivation

Phase E's exit content is *GCCMVS build; ONFLYDRV; JCL; BUZZ
demonstration; ACC-1 … ACC-7*. The first four were done earlier on
2026-09-15 (slices 1–3) and row 7 of the determinism matrix was filled
in slice 4. What remained was the acceptance criteria themselves — and
two problems with the evidence that existed for them.

**The first is date.** ACC-1, ACC-2 and ACC-3 passed in Phase C
(VL-76, VL-77, VL-78), but against `data/calibration/diag-F3-n500.bin`,
the *candidate* that D-205 later admitted and emitted as
`data/networks/onfnet-malecns-v1.0-srext.bin`. Nothing had ever
evaluated them against the shipped file under its shipped name. D-207
established the principle for Phase C — that a phase's completion should
rest on evidence produced now rather than cited from an earlier session
— and D-280 extends it to Phase E.

**The second is that the source moved underneath them.** D-285 added a
cast to the vendor SoftFloat library so that JCC would emit an object at
all. It is a null change by construction, but "by construction" is an
argument and this project measures. Every MVS result recorded earlier
on 2026-09-15 — row 6's nineteen fingerprints, ACC-6's 166 s, ACC-7's
BUZZ run — was produced from the text before that cast. Each has to be
produced again or reported as standing on superseded source.

**And one criterion cannot be made to pass.** ACC-4 compares the full
MaleCNS brain against Shiu et al.'s FlyWire-based reference. VL-64
recorded it failing at 10 and 40 Hz, where MN9 fires and the reference
is silent. The owner has already declined to change the stimulus set
(D-177) and declined to relabel the criterion (D-195, D-206), and
SR-CAL-05 forbids widening tolerances after the fact. D-280's
instruction is to re-run it and report the finding — so the re-run
changes the date on the evidence, not the verdict, and Phase E ends
PARTIAL on this one criterion however well everything else goes.

## 2. What changed

| File | Change |
|---|---|
| `prep/extract.py` | `--acc3-file` now applies D-202's exclusion through `acc3_excluded()`, the function `acc3_eval()` already used (D-289). |
| `tools/fixtures.py` | `digests()` streams in 8 MiB blocks. It read whole files, which cannot verify the 1,051,241,946-byte connectome weights on Windows. |
| `tools/mvsrun.py` | `--install-net`; row 6's `ONFNET` reads the installed dataset (D-286); per-network dataset and job names. |
| `docs/ONFLY-SRS.md` | D-288 … D-291; Section 8.3 rows 6 and 7; VL-94 in Appendix D. |
| `tests/test_fixt.py` | New, in the `prep` target. Fifteen cases over the streamed digests and D-202's exclusion rule. |
| `data/phase-e/` | The TK5 recordings this session produced. |
| `data/calibration/` | `acc1-candidate.json` and `acc3-srext.json` for the shipped network. |

## 3. Implementation approach

### 3.1 What "re-run" means for each criterion

The seven criteria are not the same kind of thing, and saying "re-run
them" hides that. What each one actually needs:

| ID | What it is measured on | What re-running it costs |
|---|---|---|
| ACC-1 | The shipped `srext` network, x86, 5 rates × 30 seeds | `prep/extract.py --acc1`, about a minute |
| ACC-2 | The same pass; rate 0 must give zero spikes everywhere | included in ACC-1's pass, plus every MVS and s390x run |
| ACC-3 | `srext` against the **full-brain** reference in `acc4.json` | `prep/extract.py --acc3-file`, a few minutes |
| ACC-4 | The **full brain** against Shiu's reference, 151 runs | `prep/acc4.py`, about 90 minutes |
| ACC-5 | Every row of Section 8.3 — rows 6 and 7 are the MVS ones | two TK5 jobs, about 15 minutes each, plus `path` |
| ACC-6 | One request, timed on TK5 | the TX-04 job, about 4 minutes |
| ACC-7 | BUZZ end to end on TK5 | about 15 minutes |

ACC-2 is the one worth noticing: it is not a separate run at all. It is
a property every other run either has or does not — *a request with rate
0 produces zero spikes in every neuron, on every platform and backend* —
so it is evaluated wherever G-15 and G-01 appear, which is the x86
suite, the s390x suite, row 6 and row 7.

### 3.2 The order, and why the lab goes first

D-283 serializes the lab work ahead of the x86 science. The reason is
ACC-6: NFR-PERF-01 bounds wall-clock time on the TK5 reference host, and
§6.2c of the slice 1 document measured the same MVS work 23% apart
under load. A figure taken while 151 full-brain runs saturate the host
is not a measurement of the bound, it is a measurement of the
contention. Everything else in the sweep is insensitive to load —
return codes and fingerprints do not change with CPU pressure — so only
ACC-6 actually constrains the order, and it constrains it completely.

### 3.3 What D-288 actually constrains, once the numbers are known

D-288 narrowed D-283 to "all x86 work stops before TX-04". Once ACC-4
was running it became clear that this fixes the whole order, not just
one step: ACC-4 is 151 full-brain runs and at `--jobs 10` on a host also
carrying Hercules and a TCG guest it runs for roughly two hours. TX-04
cannot start until it ends.

So TX-04 moves to **last**, and SUGR — 65 minutes of TK5 time that
cares nothing about host load — fills the window instead of idling in
it. The order becomes: the JCC predefine probe, the two installs, BUZZ,
the row 7 re-run, SUGR, and then TX-04 on a quiet machine.

That is not a deviation from D-288; it is D-288 applied to a fact D-288
did not have. What the owner protected — a performance figure taken on
an uncontended host — is exactly what this preserves.

### 3.4 ACC-3 depends on ACC-4's output file, so it is run twice

`--acc3-file` reads the full brain's per-rate means from
`data/calibration/acc4.json` and uses them both as the comparand and to
compute each tolerance. `prep/acc4.py` **writes** that file. So an
ACC-3 measured before ACC-4 finishes is measured against the *previous*
ACC-4's numbers.

The means ought to be identical — the full-brain run is deterministic
given the same network, the same 30 seeds and the same x86 NATIVE build,
and D-285 touched only the soft backend, which `build/runnet.exe` does
not contain. "Ought to" is not a measurement, so ACC-3 is simply run
again after ACC-4 lands and the two are compared. It costs 79 seconds,
which is less than the cost of explaining why the first one was
sufficient.

### 3.5 The s390x rows, and a VM that did not need restarting

D-290 asked for ACC-5's rows 4 and 5 to be re-established for the same
reason as rows 6 and 7 — they were Phase D results against pre-D-285
source. The guest turned out to be **already running**, left up from
the 2026-09-14 session, but with its 9p share exporting a *different*
worktree (`onfly-senior-engineer-30d72c`). A 9p device cannot be
re-pointed on a live QEMU, so the obvious move was to stop and restart
it.

That was not done. Restarting a running VM is a lab action, and it was
not necessary: this session's source was copied into the guest over ssh
into `~/onfly-d068b7` and built there, which touches no VM
configuration and cannot disturb anything else using the machine. The
copy excludes `.git` (a file pointing at a Windows path, useless in the
guest and the reason `liclint` skips there under D-233), `build`,
`data/malecns` and `data/transport`, and the two large networks — the
Section 8.4 suite runs against `path` and `srext`, which are 1.1 MB
between them.

One thing went wrong and is worth recording: 870 MB arrived rather than
the expected twelve, because `data/calibration/signed.npz` — the 594 MB
signed-count cache built minutes earlier for ACC-4 — was not in the
exclude list. It was removed guest-side, leaving 303 MB against 21 GB
free. An exclude list written from what a tree *should* contain will
miss what a tool put there an hour ago.

### 3.6 Why row 6 is run again at all

D-285 changed the text every platform compiles. Row 6's nineteen
fingerprints, ACC-6's 166 s and ACC-7's BUZZ run were all recorded
earlier on 2026-09-15, from before that change. The cast is neutral by
construction and now also by measurement on x86 (§6), but "we re-ran the
x86 suite and it was fine, so the MVS result still stands" is an
inference across platforms, and this project does not make those. The
MVS results are produced again on MVS.

## 4. Mathematical / numerical details

Four of the seven criteria are statistical, and they compare three
different things. Getting them confused is easy, so they are set out
here in plain English with their notation.

### 4.1 The three quantities being compared

Let *R* be a validation rate, one of {10, 40, 60, 120, 200} Hz (D-165),
and let each measurement be over seeds *s* = 1…30 (D-135) at the
standard duration of 1000 ms (D-73). For each rate there are three
numbers:

| Symbol | What it is |
|---|---|
| **F(R)** | the **full MaleCNS brain's** mean MN9 firing rate, 184,099 neurons, x86 NATIVE |
| **S(R)** | the **shipped subcircuit's** mean MN9 rate, 501 neurons, the `srext` network |
| **K(R)** | **Shiu et al.'s reference** MN9 rate, from the D-164 re-run of their published code on FlyWire |

The mean is over both MN9 neurons and all 30 seeds; the rate in Hz is
spikes ÷ 1 s, so at 1000 ms the count and the rate are numerically
equal.

### 4.2 ACC-3 compares S against F — "did truncation lose anything?"

ACC-3 asks whether cutting 184,099 neurons down to 501 changed the
answer. It is satisfied at rate *R* when

    |S(R) − F(R)|  ≤  max( 0.10 × F(R),  1 Hz )

The 1 Hz floor (D-166) exists because a relative tolerance is
meaningless near zero: 10% of 0.02 Hz is not a tolerance, it is a
rounding error.

D-202 added an **exclusion rule**, and it is not a loosening. A rate
whose reference satisfies sd(F) ≥ mean(F) is excluded from the
criterion and *reported* instead of tested. At such a rate the
full-brain reference is not a reproducible quantity at all — it is the
frequency of a rare event, and requiring a 501-neuron truncation to
match it would be requiring it to reproduce a coin toss. On the D-135
seeds this excludes exactly one rate, 10 Hz, where F = 3.67 ± 4.22 Hz.
At the other four, F is 14.35 ± 8.45, 28.38 ± 7.85, 68.38 ± 8.19 and
88.80 ± 5.07 — every one with sd well below its mean.

### 4.3 ACC-4 compares F against K — "is this still the fly?"

ACC-4 asks whether the MaleCNS model reproduces Shiu's published
behaviour. It has two clauses.

**Magnitude**, at each validation rate:

    |F(R) − K(R)|  ≤  max( 0.25 × K(R),  2 Hz )

**Shape**, across rates: F must not *decrease* from one validation rate
to the next by more than one standard error of its own mean at the lower
rate — se = sd/√30, the interpretation recorded as proposal P-11 because
the SRS does not say whose standard error — and the onset rate, the
lowest rate at which F exceeds 1 Hz, must be within one sampled rate of
K's onset.

**Where it fails, and why the failure is structural.** From
`data/calibration/acc4.json`, measured 2026-09-12:

| R (Hz) | F(R) ± sd | K(R) | tolerance | magnitude |
|---|---|---|---|---|
| 10 | 3.67 ± 4.22 | **0.00** | ±2.0 | **fail** |
| 40 | 14.35 ± 8.45 | **4.73** | ±2.0 | **fail** |
| 60 | 28.38 ± 7.85 | 32.07 | ±8.02 | pass |
| 120 | 68.38 ± 8.19 | 64.43 | ±16.11 | pass |
| 200 | 88.80 ± 5.07 | 77.57 | ±19.39 | pass |

Shape passes (`shape_pass: true`, no decrease beyond one standard
error), and the onset clause passes even though ONFLY's onset is 10 Hz
against the reference's 40 Hz, because 10 Hz is within one *sampled*
rate of 40 Hz on the {10, 40, 60, …} grid.

So the failure is confined to the two lowest rates, and it is one-sided:
**the MaleCNS fly responds to sugar where Shiu's FlyWire fly does not.**
Note what the tolerance does at those rates. Where K = 0, the relative
term 0.25 × K is also 0, so the entire tolerance is the 2 Hz floor —
there is no rate at all at which a model that fires when the reference
is silent can pass. That is by design (SR-CAL-05, R-03): the criterion
is meant to detect exactly this, and D-177 chose to report it as a
finding about two connectomes rather than to tune the stimulus set until
it went away.

## 5. Design decisions

**D-280 — ACC-4 is re-run, and its failure reported.** The alternative
offered was to cite VL-64's 2026-09-12 measurement and say plainly it
was not re-run, which would have saved about 90 minutes of host time.
The owner chose the re-run. The verdict is not in question — SR-CAL-05
forbids widening tolerances after the fact, D-177 kept the stimulus set
and D-195 and D-206 refused to relabel the criterion — so what the
re-run buys is that Phase E's one failing criterion fails *on evidence
from the session that reports it*, which is the same standard D-207 set
for Phase C.

**D-283 — serialization.** See §3.2. The engineer proposed overlapping
at reduced `--jobs` to save about 90 minutes of wall clock, with ACC-6
then cited rather than re-measured; the owner chose the clean figure
over the saved time.

**D-287 — both `path` jobs.** ONFPRUN re-establishes ACC-5 row 6's
fourteen `path` fingerprints against the post-D-285 source; SUGR is the
only job that prints ONF201W, ONF203E and ONF202E through **ONFLYDRV**
on MVS. The engineer stated before the choice that neither substitutes
for the other: SUGR has no IDCAMS dump step — `tests/run_mvsrun.py`
pins it to FR-BAT-01's exactly three EXEC steps — so it recovers no
records to compare, and ONFPRUN runs the engine alone, so it prints no
report. About 130 minutes between them, which the owner accepted.

**D-290 — the s390x rows.** See §3.3. Asked because starting a VM is a
lab action; it then turned out not to need starting, only feeding.

**D-291 — NFR-OBS-01 under JCC.** Row 7's own run manifest printed
`COMPILER UNKNOWN` and `PLATFORM UNKNOWN`. `ONF_CCID` keys off
`__GNUC__`, `__IBMC__` and `__MVS__`; `ONF_PLATID` off `__MVS__`,
`__s390x__` and `_WIN32`; JCC defines none of them. The comment above
`ONF_CCID` states the field's purpose exactly: *the same source produces
different object code under GCCMVS, JCC, gcc and clang … a result that
does not name its compiler cannot be compared with another.* So the one
determinism row that exists to vary the compiler was the row unable to
name it. The owner chose to probe JCC's predefines and key the branches
on what it actually defines, rather than pass `-D` from the deck — the
difference being whether the manifest reports what the compiler knows or
what the deck asserted, and NFR-OBS-01 exists to provide the former.

**Engineer's call, recorded not decided: ACC-2 is not given a run of its
own.** Section 6.4 defines it as a property holding *on every platform
and backend*, and G-01 and G-15 are rate-0 requests already present in
the x86 suite, the s390x suite, row 6 and row 7. A dedicated ACC-2 run
would test one platform where the suite tests four.

## 6. Verification

Every figure is from 2026-09-15, in the session that reports it.

### 6.1 ACC-1 and ACC-2, on the shipped network by its shipped name

```
$ python prep/extract.py --acc1 data/networks/onfnet-malecns-v1.0-srext.bin \
      --label srext --jobs 8
ACC-1 on srext (onfnet-malecns-v1.0-srext.bin), seeds 1..30
  rate   Shiu ref    mean Hz seeds w/ spike fraction verdict
    10       0.00       0.02          1/30          3% not tested (Shiu reference is zero)
    40       4.73      13.77         30/30        100% PASS
    60      32.07      28.88         30/30        100% PASS
   120      64.43      72.07         30/30        100% PASS
   200      77.57      91.35         30/30        100% PASS
ACC-1 PASS over the rates it applies to: [40, 60, 120, 200]
ACC-2 PASS: rate 0 produced 0 spikes across all 501 neurons
```

x86-64 Windows 11, mingw32 gcc, **NATIVE** backend, 81 s. ACC-1 asks
for a spike in at least 90% of seeds; it got 100% at every rate it
applies to. ACC-2's rate-0 case is also exercised on three more
platform/backend combinations by G-15 in the x86, s390x and MVS suites.

### 6.2 ACC-3, against the full brain

```
$ python prep/extract.py --acc3-file data/networks/onfnet-malecns-v1.0-srext.bin \
      --label srext --jobs 8
  rate    subcirc       full      tol    ACC-3
    10       0.02       3.67     1.00     EXCL
    40      13.77      14.35     1.44     PASS
    60      28.88      28.38     2.84     PASS
   120      72.07      68.38     6.84     PASS
   200      91.35      88.80     8.88     PASS
  10 Hz excluded and reported (D-202): reference 3.67 +- 4.22 Hz, subcircuit 0.02 Hz
srext: 501 neurons, 10783 edges, need=255688 (NFR-MEM-01 PASS), ACC-3 PASS (79 s)
```

**This verdict changed during the session, and that is worth stating
plainly.** The first run of the same command printed `ACC-3 FAIL`,
because `--acc3-file` is the D-181 diagnostic and was written before
D-202 amended the criterion: it tested all five rates, including the one
D-202 excludes. The four rates ACC-3 actually tests passed then and
pass now — the numbers above are unchanged — and what moved was the
tool, not the measurement. The change was put to the owner rather than
made, because a change that turns a FAIL into a PASS should not rest on
an engineer's own judgement (D-289).

NFR-MEM-01 is checked in the same pass: the decoded network needs
255,688 bytes against TBD-14's 8 M region.

**Does D-289 make ACC-3 vacuous?** It is a fair question of any change
that turns a FAIL into a PASS, so it was answered rather than asserted.
The same fixed tool was pointed at the D-75 `path` fixture — 913
neurons, never intended as the MVP subcircuit:

```
$ python prep/extract.py --acc3-file data/networks/onfnet-malecns-v1.0-path.bin \
      --label pathchk --jobs 6
  rate    subcirc       full      tol    ACC-3
    10       3.30       3.67     1.00     EXCL
    40       4.55      14.35     1.44     FAIL
    60      18.88      28.38     2.84     FAIL
   120      68.72      68.38     6.84     PASS
   200      92.87      88.80     8.88     PASS
  10 Hz excluded and reported (D-202): reference 3.67 +- 4.22 Hz, subcircuit 3.30 Hz
pathchk: 913 neurons, 72852 edges, need=1104340 (NFR-MEM-01 PASS), ACC-3 FAIL (154 s)
```

It still fails, on the two rates where that network genuinely does not
reproduce the full brain. The exclusion removes one rate from the test;
it does not remove the test. This is the same argument VL-76 made when
D-202 was adopted — *five of the six sizes measured still fail it* —
now shown with the corrected tool rather than the one that predated it.

### 6.3 ACC-5 rows 6 and 7 on the post-D-285 source

Row 6, `srext`, re-run because D-285 changed the text it compiles:

```
$ python tools/mvsrun.py --compare data/phase-e/mvs data/phase-d/x86w
  raw=False  binary=True  translated=True
  ok   G-15 6C3F7272   G-16 BAF81D91   G-17 F9C7EE77
  ok   G-18 4FD0ED1E   G-19 C4C320BC
mvsrun: TX-01 PASS, ACC-5 row 6 PASS
```

Row 7 is in the slice 4 document. Both now read the same installed
network (D-286), so the compiler is the only difference between them.

### 6.4 The file all of this is about

Every result in this document and in slice 4 is about one file, and it
is worth pinning which:

```
MANIFEST says : 171768 bytes  CRC 038CAE79  SHA bf09a3ad18a82b8e...
file on disk  : 171768 bytes  CRC 038CAE79  SHA bf09a3ad18a82b8e...
agree         : True
magic         : 4F4E4631        (TBD-09, closed by D-167)
```

and what the engine itself made of it, identically under GCCMVS and
under JCC:

```
ONF001I NETWORK LOADED N=501 E=10783 CRC=4577D74E
ONF002I   HEADER CRC      B05B9E6A
ONF002I   PAYLOAD CRC     4577D74E
```

The chain therefore runs unbroken from `data/networks/MANIFEST.json`,
through the bytes on disk, through the card images the reader delivered,
through `HERC01.ONFLY.ENET`, to two independently compiled engines on
MVS agreeing on both CRCs. That is what makes D-286's change of
transport a non-issue rather than a caveat.

### 6.5 ACC-4, ACC-6, ACC-7

*(filled in as they land)*

### 6.6 What is NOT proven, per claim

Stated per claim rather than as a list of caveats, because a caveat that
does not say *which result* it limits is not a limit.

**ACC-1 and ACC-2 (§6.1)** — x86-64 Windows 11, mingw32 gcc, **NATIVE**
backend, on `srext` only, 30 seeds per rate. ACC-1's own comparand is
the Shiu reference from the D-164 re-run, itself an x86 measurement
under brian2 — and brian2 is gone from this host (VL-88, D-243), so that
comparand cannot be regenerated here. ACC-2's claim is broader than this
run: Section 6.4 requires it on *every platform and backend*, and what
supports that is the rate-0 request appearing in the x86, s390x and both
MVS suites, not this pass alone.

**ACC-3 (§6.2)** — the same platform and backend. The comparand is the
full brain's own means from `acc4.json`, so ACC-3 says the 501-neuron
subcircuit reproduces the 184,099-neuron model; it says nothing about
whether either matches a fly. That is ACC-4's question, and ACC-4 is the
one that fails. The 10 Hz row is **excluded, not passed**, and any
citation of ACC-3 that omits that is incomplete.

**ACC-5 rows 6 and 7 (§6.3)** — TK5 MVS 3.8j under Hercules 4.9.1,
**SOFT2C** only, GCCMVS 3.2.3 at `-O1` and JCC 1.50.00. Hercules is an
emulator; VL-01's argument about QEMU applies in the same form. `raw`
identity is not achieved and cannot be between an EBCDIC and an ASCII
host — D-261 fixes what identity means, and `binary` and `translated`
both hold.

**D-285's neutrality** — evidenced on x86 by TestFloat over 260,376 and
781,128 cases, and on MVS by both rows reproducing their fingerprints.
It is *not* evidenced on any platform not re-run.

**Everything here is one network version.** All of it is format v1.1
`srext`, payload CRC `4577D74E`, 501 neurons and 10,783 edges. A
different network is a different set of golden entries (Section 8.4),
not a repeat of these.

## 7. Related docs

- SRS Section 6.4 (ACC-1 … ACC-7), 6.2 (SR-CAL-05), 7 (NFR-PERF-01),
  8.3, 8.4, Appendix A.1 (D-279…D-287), Appendix D
- [2026-09-15 — Phase E slice 4](2026-09-15-phase-e-slice-4-jcc-row-7.md)
- [2026-09-13 — the srext subcircuit admitted](2026-09-13-srext-subcircuit-admitted.md)
- [2026-09-12 — Phase C calibration](2026-09-12-phase-c-calibration.md)
