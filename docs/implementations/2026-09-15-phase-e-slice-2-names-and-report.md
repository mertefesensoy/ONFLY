# 2026-09-15 — Phase E slice 2: the names file and FR-BAT-04's report

| Field | Value |
|---|---|
| Date | 2026-09-15 |
| Author | Engineer, with the owner deciding every open design point |
| Phase / gate | **Phase E — MVS MVP**, slice 2 (SRS Section 9.2) |
| Owner decisions relied on | D-266 (slice 2 next), D-267 (the name form), D-268 (which neurons), D-269 (a separate emitter), D-270 (RC → Appendix E message), D-271 (generated stimulus codes), D-272 (rounded Hz) |
| Requirements touched | FR-PRP-07, FR-BAT-04, FR-BAT-05, IR-NAM-01, IR-NAM-02, IR-NAM-03, IR-COM-01, IR-COM-02, IR-COM-05, IR-COM-06, IR-JCL-01 |
| Open items closed | None |

## 1. Problem / motivation

FR-BAT-04 requires the report to print "each readout neuron's **name**", and
IR-COM-06 forbids the response record from carrying one:

> Response entries shall carry numeric readout identifiers, never names;
> ONFLYDRV maps identifiers to names from ONFNAM.

**There was no ONFNAM.** Not on disk, not in `data/networks/MANIFEST.json`, and
nothing in `prep/` that could make one — `grep -rn 'IR-NAM'` over the whole
tree matched exactly two lines, both the DD declaration in the COBOL driver,
which says "Declared for Phase E; the G4 skeleton never opens it". FR-PRP-07
has required the pipeline to emit it since the specification was written.

So the report was not merely unwritten; it was **unwritable**. That is the gap
this slice closes, and it is why the names file came before the report.

## 2. What changed

| File | Change |
|---|---|
| `prep/names.py` | **New.** Emits ONFNAM for a network and registers it in the manifest. |
| `tests/run_names.py` | **New.** 17 cases against IR-NAM-01/02/03, IR-COM-06 and D-267. |
| `data/networks/onfnam-malecns-v1.0-{srext,path}.txt` | **New.** 16 rows each. |
| `data/networks/MANIFEST.json` | A `names` section: digests, and every row with its **original** cell-type spelling (IR-NAM-02). |
| `cobol/ONFLYDRV.cbl` | The FR-BAT-04 report: names table, Appendix E messages, hexadecimal fingerprint, Hz. |
| `layout/generate.py` | A second expandable COPY member, `ONFSTM`, holding the stimulus codes (D-271). |
| `generated/ONFSTM.cpy`, `generated/ONFLYDRV.cbl` | Regenerated. Never edited by hand. |
| `tests/run_cob.py` | The report test, covering every branch of the message logic. |
| `tools/fixtures.py` | `--malecns`, to reach the other gitignored dataset. |
| `Makefile` | `names` target, wired into `test`. |

## 3. Implementation approach

### 3.1 Recovering a body id without a gigabyte

The identifier a response carries is the neuron's **index** in the network —
`readout: [9, 88]` for `srext` — not its MaleCNS body id. Recovering the body
id looks as though it needs the network's whole node list, which exists only
inside the connectome weights file: **1,051,241,946 bytes**.

It does not. `prep/emit.py` assigns indices as

```
searchsorted(nodes, sort(body_ids))          with nodes ascending
```

so the indices come out ascending in the same order as the body ids. **The
k-th smallest index is the k-th smallest body id**, and both lists are already
to hand — indices in the network header, body ids in the reviewed FR-PRP-02
mapping. The pairing is exact. It holds for any network containing every
stimulus and readout neuron, which SR-EXT-01 requires by construction.

That is a derivation, so it is **checked, not trusted**.
`data/networks/SUBCIRCUIT.json` carries the full 501-entry body list for the
N=500 extraction, and the emitter confirms every row against it:

```
names: srext  WROTE   onfnam-malecns-v1.0-srext.txt, 16 rows, 1296 bytes;
       pairing CHECKED against SUBCIRCUIT.json N=500, 16 of 501 rows
```

`bodies[9] == 10331` and `bodies[88] == 16949`, and all fourteen stimulus
indices agree. The `path` fixture of D-75 has no recorded body list, so the
check **reports that it could not run** rather than reporting a pass.

### 3.2 Contract of `prep/names.py`

- **Inputs:** an emitted network file, `docs/malecns-celltype-mapping.json`
  (the FR-PRP-02 reviewed mapping), and the MaleCNS annotations feather.
- **Outputs:** `data/networks/onfnam-malecns-v1.0-<label>.txt` and a `names`
  section in the manifest.
- **Side effects:** writes those two files and nothing else. It **never**
  touches `data/networks/*.bin` — D-269's whole point, since the fingerprint
  includes the network payload CRC (IR-COM-05) and a re-emission that changed
  one byte would invalidate every Section 8.4 fingerprint.
- **Invariant relied on:** the rank pairing of §3.1, checked where checkable.
- **Failure mode:** every error is a `NamesError` naming the missing input;
  `pandas` is imported locally so a checkout without it can still run the
  tests against the committed files.

### 3.3 Three things in the COBOL that needed care

**The hexadecimal fingerprint.** COBOL in the MVT / Enterprise intersection has
no bit operations. A byte is moved into the **low** half of a halfword whose
high half is binary `LOW-VALUE`, so the halfword's value is 0 to 255 and always
positive; `DIVIDE ... GIVING ... REMAINDER` then splits it into two nibbles
which index a sixteen-character table. This keeps the whole conversion inside
IR-COM-02's rule that a value always fits its PIC digits, so the TRUNC option
cannot alter it.

**RC 8 is ambiguous.** The record carries IR-JCL-04's return code and nothing
else, and Appendix E maps 8 to *two* messages. D-270 resolves it from the
stimulus code. This cannot disagree with the engine, and the reason is
structural rather than careful: `engine/src/onfreq.c` tests
`stimid == ONF_STIM_UNKNOWN` **first**, before any range check, so a request
that reached RC 8 with a code the table knows can only have failed a range
check.

**The stimulus codes are generated (D-271), text only.** A group alternating
`PIC X(4)` with `PIC S9(4) COMP` would put every halfword on an odd boundary
unless `SYNCHRONIZED` were specified — exactly the class of platform detail
IR-COM-03 exists to keep out of this program. The driver needs membership, not
the numeric id, so an all-character table cannot have the problem.

## 4. Numerical details

The firing rate is

```
Hz  =  spikes x 1000 / duration_ms          rounded to the nearest tenth
```

evaluated in COBOL **fixed-point decimal**, not floating point, so NR-05 and
NR-07 are not engaged and no `onf_fp` operation takes part. The accumulator is
`PIC S9(7)V9`: seven integer digits because 9999 spikes in 1 ms is 9,999,000 Hz
— not a rate any real run produces, but the widest the record's own PIC digits
admit under IR-COM-02.

D-272 chose ROUNDED over truncation. The proxy test pins **the case that tells
them apart**: one spike in 150 ms is 6.6667 Hz, which prints `6.7` rounded and
`6.6` truncated. A test using only whole rates would have passed either way.

## 5. Design decisions

| Point | Chosen | Alternative rejected, and why |
|---|---|---|
| Emitter | A separate `prep/names.py` (D-269) | Extending `prep/emit.py`, which is literally "the pipeline" FR-PRP-07 names — but it re-derives the networks, and one differing byte would invalidate every golden fingerprint and the MVS results taken the same day |
| Name form | `MN9-10331` (D-267) | `MN9` alone, which IR-NAM-01's "type name" literally says — but both `srext` readouts are MN9, so the report would print two rows a reader cannot tell apart |
| Coverage | Readouts **and** stimulus neurons (D-268) | Readouts only, which is all any current requirement needs; the stimulus rows are for Phase G's BUZZ screen |
| Message | RC 8 disambiguated (D-270) | A generic per-RC text, which drops information Appendix E defines |
| Codes | Generated (D-271) | Hard-coded literals, the drift IR-COM-01 created the copybook to prevent |

## 6. Verification

### 6.1 x86, this session

```
mingw32-make names
```
→ `run_names: 17 passed, 0 failed`, including
`D-269: regenerating reproduces the committed files  0 differing`.

```
mingw32-make cob
```
→ the full FR-BAT-04 report, matched line for line as 133-byte FBA records:

```
|1|ONFLY REPORT (FR-BAT-04)
| |REQUEST    1 CODE=SUGR     RATE= 120 MS=1000 SEED=        1 RC=   0 OUT=   3 STEPS=    10000
| |  ONF301I  REQUEST COMPLETE                                 FP=DEADBEEF
| |  READOUT      1 ID=        5 MN9-10331       LAT-US=    123456 SPIKES=   7 HZ=      7.0
| |  READOUT      3 ID=       77 *UNNAMED*       LAT-US=       500 SPIKES=   3 HZ=      3.0
| |  ONF201W  STIMULUS CODE RESERVED, NOT SIMULATED            FP=DEADBEEF
| |  ONF203E  UNKNOWN STIMULUS CODE                            FP=DEADBEEF
| |  ONF202E  REQUEST FIELD OUT OF RANGE                       FP=DEADBEEF
| |  ONF903S  NON-FINITE STATE VALUE, REQUEST ABORTED          FP=DEADBEEF
| |  READOUT      1 ID=        5 MN9-10331       LAT-US=      1000 SPIKES=   1 HZ=      6.7
```

(columns elided here for width; the test compares the full 132.)

Also `run_cob: 14 records identical to tools/mkreq.py's packing of the same
deck, G-13 rate=-1 (D-265)`.

### 6.2 What is NOT proven

- **Everything above is x86-64 GnuCOBOL 3.2.0 under `-std=ibm` and
  `-std=ibm-strict`.** VL-02 stands: that is a proxy for Enterprise COBOL and
  is not Enterprise COBOL, and it says nothing whatever about MVT COBOL. The
  report has **not** been compiled by IKFCBL00 or printed on TK5.
- The `path` names file's rank pairing is **unchecked** — no recorded body
  list of length 913 exists. The derivation is the same one that is checked
  for `srext`, but that is an argument, not a measurement.
- `*UNNAMED*` is exercised only in the test; no shipped network has a readout
  missing from its names file.
- Nothing here touches IR-NAM-03's transport clause: the file has never been
  sent to MVS, so the ASCII-to-EBCDIC translation it specifies is untested.

## 7. Related docs

- SRS Section 3.1 (FR-PRP-07), 3.4 (FR-BAT-04, FR-BAT-05), 4 (IR-NAM, IR-COM),
  Appendix A.1 (D-266…D-272), Appendix E (the message catalog)
- [2026-09-15 — Phase E slice 1](2026-09-15-phase-e-slice-1-mvs-simulation.md)
- [2026-09-12 — Gate G4 closed](2026-09-12-gate-g4-closed-cobol.md)
