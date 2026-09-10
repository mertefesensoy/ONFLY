# 2026-09-10 — Response fingerprint and the golden request suite

| Field | Value |
|---|---|
| Date | 2026-09-10 |
| Author | ONFLY engineering session |
| Phase / gate | Phase B — Engine and oracle (x86) |
| Owner decisions relied on | D-37, D-39, D-40, D-41, D-42 |
| Requirements touched | IR-COM-05, IR-COM-06, FR-SIM-09, FR-SIM-06, FR-BAT-05, NR-11, NR-12, ACC-2, ACC-5 |
| Open items closed | none. TBD-06 remains **open**; D-37 and D-42 are provisional only |

## 1. Problem / motivation

ACC-5 — the criterion the whole project turns on — is defined as "every
golden-suite request yields the same fingerprint on every combination listed in
Section 8.3". Until this change neither the fingerprint nor the golden suite
existed, so ACC-5 was not merely failing, it was unmeasurable.

Two gaps in the specification blocked it, and both were put to the owner rather
than filled in:

- **IR-COM-05 requires a "numeric stimulus ID" that no section of the SRS ever
  assigns.** FR-BAT-05 names the codes only as text. The fingerprint excludes
  text precisely because `SUGR` is different bytes on ASCII and EBCDIC hosts, so
  a number was unavoidable. Resolved by **D-39**.
- **Section 8.4 and Appendix E contradicted each other.** Golden request G-12
  (unknown stimulus code) was listed as expecting ONF202E, but Appendix E
  defines ONF203E as UNKNOWN STIMULUS CODE and ONF202E as REQUEST FIELD OUT OF
  RANGE. Resolved by **D-41**, which also authorised correcting the Section 8.4
  text — the only SRS requirement text changed in this session.

Two further values existed only as prose: the "Standard" duration (**D-37**) and
G-07's "Short" (**D-42**). Both are recorded as **provisional**; Gate G3 still
fixes them, and changing either changes every fingerprint below.

## 2. What changed

| File | Change |
|---|---|
| `docs/ONFLY-SRS.md` | Recorded D-39…D-42; corrected the Section 8.4 G-12 row to ONF203E under D-41; added proposal P-08 to Appendix A.2. |
| `layout/master.py` | Defines the stimulus codes and their numeric IDs, with invariants. |
| `layout/generate.py` | Emits those IDs to the C header and the Python module. |
| `generated/onfcom.h`, `generated/onfcom_py.py` | Now carry `ONF_STIM_*` / `STIM_IDS`. **Do not edit.** |
| `engine/include/onffpr.h`, `engine/src/onffpr.c` | The response fingerprint, IR-COM-05. |
| `oracle/onfly_oracle/fingerprint.py` | Independent reference fingerprint. |
| `tests/tstgld.c`, `tests/run_gld.py` | The 13-request golden suite and its oracle comparison. |
| `tools/cmpgld.py` | Runs two backends on one shared network file and requires identical output. |
| `Makefile` | New `golden` target, wired into `test`. |

## 3. Implementation approach

`onffpr` builds the canonical byte string exactly as IR-COM-05 states — payload
CRC, stimulus ID, seed, rate, duration, return code, output count, step count,
then one triple per valid output entry — every field a big-endian 32-bit
integer, and CRCs the result.

Three properties are deliberate rather than incidental:

- **Only entries below the output count are hashed.** The record always carries
  32 output slots; hashing the unused tail would make the fingerprint depend on
  whatever was left in memory.
- **The payload CRC comes first**, so a fingerprint identifies the network as
  well as the request and two identical requests against different networks
  cannot collide.
- **Nothing textual appears**, which is what lets an EBCDIC host and an ASCII
  host agree.

Negative values reach the fingerprint in normal operation — latency is −1
whenever a readout neuron never spiked — so the two's-complement conversion is
written to avoid relying on signed overflow (NR-11), the same construction used
in the generated accessors.

Request validation runs before any simulation: an unrecognised code is ONF203E,
a reserved code (WATR, BITR) is ONF201W with no simulation (FR-BAT-05), an
out-of-range rate or duration is ONF202E (FR-SIM-06), and NR-12's
`rate × dt_us ≤ 1,000,000` bound is enforced explicitly.

## 4. Mathematical / numerical details

The fingerprint is a CRC-32/ISO-HDLC over `32 + 12k` bytes for `k` output
entries. It is a checksum, not a cryptographic digest: VL-08 applies, and it
detects accidental divergence rather than deliberate forgery.

The suite's step counts follow `steps = ms × 1000 / dt_us` with `dt_us = 100`,
so 1000 ms is 10,000 steps, 100 ms is 1,000, 1 ms is 10, and the 5000 ms
maximum is 50,000. All integer arithmetic; no decimal-to-binary conversion
occurs on any target (NR-06).

G-07 is the tightest case in the suite: 9999 Hz × 100 µs = 999,900, inside
NR-12's 1,000,000 bound by 100 parts per million. Any increase in dt above
0.1 ms breaks it.

## 5. Design decisions

D-39, D-40, D-41 and D-42 are the owner's and are recorded in Appendix A.1 with
their alternatives. One reading is the architect's and is recorded as a
**proposal**, not a decision:

- **P-08**: `ONF-RC` carries Appendix E's *RC column* (0, 4, 8, 12, 16) rather
  than the message number. Section 4.3 says only "Return code (Appendix E)",
  and Appendix E has both columns. The RC column is the one headed "return
  code" and matches IR-JCL-04's step codes, so this is the direct reading — but
  if it is wrong, every golden fingerprint changes. It sits in Appendix A.2
  awaiting confirmation.

## 6. Verification

```
mingw32-make test
```

Golden suite, identical under both backends (fingerprints are provisional —
they depend on D-37 and D-42):

| ID | Code | Rate | ms | Seed | RC | Steps | Fingerprint |
|---|---|---|---|---|---|---|---|
| G-01 | SUGR | 0 | 1000 | 1 | 0 | 10000 | `B27B3D96` |
| G-02 | SUGR | 10 | 1000 | 1 | 0 | 10000 | `B74C2A62` |
| G-03 | SUGR | 40 | 1000 | 1 | 0 | 10000 | `A6A76246` |
| G-04 | SUGR | 120 | 1000 | 1 | 0 | 10000 | `8F1FDDE6` |
| G-05 | SUGR | 200 | 1000 | 1 | 0 | 10000 | `62CCD3B9` |
| G-06 | SUGR | 200 | 1000 | 999999999 | 0 | 10000 | `7908E066` |
| G-07 | SUGR | 9999 | 100 | 7 | 0 | 1000 | `6B9E081E` |
| G-08 | SUGR | 120 | 1 | 7 | 0 | 10 | `F3F9A80F` |
| G-09 | SUGR | 120 | 5000 | 7 | 0 | 50000 | `790CAE81` |
| G-10 | SUGR | 120 | 1000 | 0 | 0 | 10000 | `21CF2FCA` |
| G-11 | WATR | 120 | 1000 | 1 | **4** | 0 | `CEB97507` |
| G-12 | XXXX | 120 | 1000 | 1 | **8** | 0 | `B8EBA04E` |
| G-13 | SUGR | −1 | 1000 | 1 | **8** | 0 | `6FEED5DF` |

```
run_gld [SOFT backend]: 14 passed, 0 failed
run_gld [NATIVE backend]: 14 passed, 0 failed
  ok   all 13 fingerprints are distinct
cmpgld: soft and native agree on all 13 golden requests (93 output lines)
```

The distinctness check exists because a fingerprint that returned a constant
would pass every comparison above while proving nothing.

### What these results do not prove

- **x86, 32-bit mingw32 gcc 6.3.0, Windows 11 only**, on both the SOFT and
  NATIVE backends. That is rows 1, 2 and 3 of the Section 8.3 determinism
  matrix. **Rows 4 to 8 — Linux s390x, MVS 3.8j under GCCMVS, MVS under JCC,
  and z/OS — have not been run**, because none of those platforms is installed
  here. **ACC-5 is therefore NOT satisfied**; only its x86 rows are.
- The fingerprints above are **provisional**. D-37 and D-42 are provisional
  durations, TBD-06 is open, and Gate G3 fixes the real values. They are not
  reference values and must not be quoted as such.
- The network is **synthetic**. No MaleCNS data, no calibrated W_syn, no
  extracted subcircuit — all Phase C. So ACC-1, ACC-3 and ACC-4 remain
  unevaluated. ACC-2 is exercised only in miniature by G-01.
- VL-05 applies: identical fingerprints prove cross-platform consistency, not
  scientific correctness.
- P-08 is unconfirmed. If `ONF-RC` should carry message numbers rather than RC
  values, every fingerprint in the table changes.

## 7. Related docs

- `docs/ONFLY-SRS.md` — Sections 4.3, 8.3, 8.4, Appendix A.1 (D-37…D-42),
  Appendix A.2 (P-08), Appendix E.
- `docs/implementations/2026-09-10-phase-b-foundations.md` — the layout
  generator, float layer, kernel and network decoder this builds on.
