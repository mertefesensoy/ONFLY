# 2026-09-12 — Gate G2 closed: three transports measured, the card reader selected

| Field | Value |
|---|---|
| Date | 2026-09-12 |
| Author | Claude (ONFLY senior engineer session) |
| Phase / gate | **Gate G2 (Spike S2, transport)** |
| Owner decisions relied on | D-141 … D-150 |
| Requirements touched | A-07, IR-TRN-01, IR-TRN-02, IR-TRN-03, IR-TRN-04, FR-PRP-08, FR-LOD-01…FR-LOD-05, IR-NET-08, NFR-OBS-01, NR-14 |
| Open items closed | **Gate G2**; A-07 confirmed |

## 1. Problem / motivation

Gate G2 asks which transport moves binary into TK5 safely. Until this session the
answer was unknown in both directions: VL-35 recorded that *no file could reach
MVS at all* until G2 chose and proved a binary-transparent transport, so the
engine was verified on MVS only against a network embedded in its own source.

Phase E depends on G2. Without it, ONFLY could simulate on the mainframe but
could never be given the real MaleCNS subcircuit to simulate.

The failure this prevents is subtle rather than loud. A transport that
translates a code page, inserts a line ending, or truncates trailing blanks
produces a file that *looks* present and decodes to wrong numbers. IR-TRN-01
names those three mechanisms specifically because each is silent.

## 2. What changed

| File | Change |
|---|---|
| `tools/mkaws.py` | New. Writes the IR-TRN-02 test file and wraps a flat file as an AWS tape image. |
| `tools/mkasl.py` | New. Adds IBM standard labels — VOL1, HDR1, HDR2, EOF1, EOF2 — in EBCDIC. |
| `tools/mvseng.py` | New. Builds ONFLYENG under GCCMVS and runs it against tape or card reader. |
| `tools/mvsxfr.py` | New. Drives the test file by tape, card reader or catalogued dataset. |
| `tools/mvsind.py` | New. Answers whether IND$FILE exists on TK5, via S806. |
| `tools/tso3270.py` | New. Scripted TSO logon and IND$FILE `Transfer()` over ws3270's script port. |
| `tools/g2ind.py` | New. IND$FILE's twenty transfers in one session. |
| `tests/tstxfr.c` | New. Checks the transferred test file on MVS; reports four sections separately. |
| `tests/tstclk.c`, `tools/mvsclk.py` | New (G3, prior day). Clock availability probe. |
| `engine/src/onflyeng.c` | **FR-LOD-03 defect fixed**: reads by the header's declared length, not by seeking. Self-test width selected by backend (D-142). |
| `softfloat/onfi32.c`, `softfloat/onfi32.h` | New. TT-01/32 as a linkable suite, so ONFLYENG and `tst32.c` run the same code. |
| `tests/tst32.c` | Now drives the extracted suite instead of duplicating it. |
| `tools/mvsbld.py` | `build()` gains optional `go_parm` and `go_dd`. |
| `Makefile` | `tt0132` links `onfi32.c`; `liclint` added to `test`. |
| `docs/ONFLY-SRS.md` | D-141…D-150, VL-45…VL-56; Gate G2 closed; A-07 confirmed. |

## 3. Implementation approach

### 3.1 One checker, three transports

Every transfer is verified **on the guest**, by the same two programs regardless
of how the bytes arrived:

- the **network file** by ONFLYENG's verify-only mode (IR-TRN-03), which runs
  FR-LOD-02's six checks in order and prints `ONF003I`;
- the **test file** by `tests/tstxfr.c`, which prints `XFR000I`.

Using one checker per file across all three methods is what makes the results
comparable rather than three separate assertions.

### 3.2 The test file is built so failures name their own mechanism

`tools/mkaws.py --testfile` writes four 256-byte sections, each chosen so a
particular corruption appears in exactly one:

| Section | Content | What its failure would mean |
|---|---|---|
| 1 | `0x00`…`0xFF` ascending | some byte value did not survive at all |
| 2 | `0xFF`…`0x00` descending | damage depends on position |
| 3 | 256 × `0x40` | **EBCDIC blank** — eaten by trailing-blank truncation |
| 4 | `0x00`/`0xFF` alternating | a pattern no text conversion leaves intact |

Then a 4-byte big-endian length and the CRC-32 of the body, so the file checks
itself and `tstxfr.c` needs to be told nothing.

### 3.3 The file describes itself, which matters on tape

FB blocking pads 1,032 bytes to 1,040. The trailer therefore sits **at byte
1024, not at the end of what is read**. A checker assuming the trailer was last
would fail a perfectly good transfer. Verified on x86 against both forms before
going near the guest.

## 4. Numerical results

All measured on TK5 (SDL Hercules 4.9.1.11612-SDL-gee86c4de, MVS 3.8j Update 5)
on 2026-09-12, GCCMVS at `-O1`, SOFT2C float backend.

### 4.1 Payload geometry

| Quantity | Value |
|---|---|
| Network payload | 885,416 bytes |
| Padded to LRECL 80 | 885,440 bytes = **11,068 records** |
| Tape blocking | 28 blocks × 32,720 bytes (409 records); last block 896 bytes |
| Card reader | **11,068 cards** of 80 bytes |
| Test file payload | 1,024 bytes body + 8 trailer = 1,032; padded to 1,040 = 13 records |

`BLKSIZE = 32720` because an FB block must be a whole number of records and
32,720 = 409 × 80 is the largest such multiple ≤ MVS's 32,760-byte QSAM limit.
The obvious 32,760 is **not** a multiple of 80 and produces a tape MVS cannot
read as FB/80.

### 4.2 Integrity — IR-TRN-04 criterion 1

| Method | Test file | Network | Total |
|---|---|---|---|
| AWS tape | 10 / 10 | 10 / 10 | **20 / 20** |
| Raw card reader | 10 / 10 | 10 / 10 | **20 / 20** |
| IND$FILE | 10 / 10 | 10 / 10 | **20 / 20** |

**Integrity separates none of the three.**

### 4.3 Checksums, identical across every method

| Value | Result |
|---|---|
| Test file body CRC-32 | `B6D02D34` — computed on x86 and on MVS, equal in all 30 test-file transfers |
| Network header CRC-32 | `6E556D23` |
| Network payload CRC-32 | `9C0A8413` |
| Network neurons / edges | **N = 913, E = 72,852** — matching `data/networks/MANIFEST.json` exactly |
| Network whole-file CRC-32 | `44D486F1` (manifest; distinct from the payload CRC above) |

### 4.4 Elapsed time — IR-TRN-04 criterion 3

Test file (seconds per transfer):

| Method | min | max | mean |
|---|---|---|---|
| AWS tape | 3.7 | 3.9 | **3.8** |
| Raw card reader | 5.5 | 5.6 | **5.5** |
| IND$FILE | 4.5 | 4.9 | **4.7** |

Network, 885 KB (seconds per transfer):

| Method | min | max | mean |
|---|---|---|---|
| AWS tape | 24.4 | 30.9 | **27.9** |
| Raw card reader | 20.7 | 25.9 | **21.2** |
| IND$FILE | 20.9 | 21.2 | **21.1** |

IND$FILE reported `157 Kbytes/sec in DFT mode`.

> **These are not pure transport times and must not be read as such.** The tape
> and reader figures are whole compile-assemble-link-run jobs, including the
> tape's mount polling; the IND$FILE figure is a transfer plus a separate
> verification job. They are comparable to within a few seconds and no finer.
> The direction reversing between the two payloads — tape fastest on the small
> file, slowest on the large — is itself evidence of that.

### 4.5 Scriptability — IR-TRN-04 criterion 2

| Method | What a transfer requires |
|---|---|
| Raw card reader | one command; no labels, no volume, no mount, no session |
| AWS tape | standard label, volume serial, and answers to **two** mount requests |
| IND$FILE | TSO logon, ISPF exit, a `LOGOFF` ISPF refuses, process-level LU retries |

Integrity ties, so **scriptability decides**, and elapsed time only confirms.

## 5. Design decisions

Each is recorded in the SRS with its alternatives; the reasoning is there and
is not repeated. D-141 (open on tape, check with VERIFY mode), D-142 (self-test
width by backend), D-143 (test the label hypothesis with BLP), D-144 (eliminate
density before writing label code), D-145 (standard-labelled tape), D-146
(evaluate all three), D-147 (fix `onferead`), D-148 (one IND$FILE transfer
first), D-149 (complete its twenty), D-150 (select the reader).

One ordering decision is worth restating because it saved work: **D-144 put a
read-only density check ahead of writing any label records**, on the grounds
that if density were the cause both label options would have been wasted
effort. It was not the cause, and the check cost one 30-second job.

## 6. Defects found, and what each cost

### 6.1 ONFLYENG contravened FR-LOD-03 (fixed, D-147)

FR-LOD-03: *"trust the header's declared length, **not the dataset size**"*.
`onferead()` began `fseek(f, 0L, SEEK_END)` + `ftell` — the dataset size, the
one thing forbidden. A seekable dataset hides the difference entirely; the card
reader is not seekable and was the first device to expose it, rejecting a
network it had delivered in full (`IO[11070]` for 11,068 cards) with `ONF108E`
before a single header check ran.

The fix reads the 164-byte header, takes `ONF_N_PAYLEN` from offset 152, and
reads exactly that. Two things the first attempt got wrong, both caught before
the guest:

- an unvalidated declared length reaching `malloc` — now bounded by
  `ONF_MAXPAY` = 64 MB, a sanity bound, not the memory limit (FR-LOD-04 governs);
- **TE-06 regressed**: a header declaring more payload than arrives was reported
  `ONF108E` instead of `ONF106E`, collapsing "could not be read" into "disagrees
  with its own header". A short read is now returned as what arrived.

### 6.2 A verification that could not fail

`mount()` checked whether the image's basename appeared in the console reply.
The console echoes the command it was given, so the check passed on **every
failed mount** — reporting success four times while the drive stayed empty and
`HHC00205E` sat two lines above. A verification that cannot fail is worse than
none, because it is believed. It now requires `HHC00221I`'s "format type" *and*
the absence of `HHC00205E`.

### 6.3 A prediction that was wrong (D-146)

I recorded the card reader as *expected to fail*, because binary through JES2
meets its scan for `//` and `/*`. True of inline `DD DATA`, irrelevant here:
`$DU` showed JES2 draining only `00C`, so `10C` allocates directly by `UNIT=`
and JES2 never sees a byte. The reader then won the gate.

## 7. MVS behaviours worth not rediscovering

| Behaviour | Evidence |
|---|---|
| Hercules cannot open a path containing non-ASCII characters | `HHC00205E` buried between a success line and "device initialized"; drive left empty |
| The tape mount is **two** requests | `IEF233A` at allocation, then `IEC501A` at OPEN |
| MVS unloads the drive *during* allocation | `HHC00201I ... tape closed` between job start and `IEF233A` — so pre-mounting cannot work |
| `BLP` is not granted to TK5's class A | MVS reports `NL` in `IEC501A` despite `LABEL=(1,BLP)` |
| `DEN` is honoured but irrelevant | message changed 6250 → 1600 BPI; refusal identical |
| Dropping a 3270 connection does **not** log TSO off | next logon refused `IKJ56425I ... IN USE` |
| `LOGOFF` is not accepted inside ISPF | TK5's `ISPLOGON` proc lands there |
| `Disconnect`/`Connect` inside one ws3270 does not release the LU | four attempts failed; a fresh process succeeded immediately |
| Hercules holds a card file open while loaded | Windows refuses to restage it — `PermissionError` |
| MVS unit addresses are 3 digits, Hercules' 4 | `UNIT=0480` in JCL is not the tape |

## 8. Verification

```bash
python tools/mvseng.py --repeat 10            # tape, network
python tools/mvsxfr.py --repeat 10            # tape, test file
python tools/mvseng.py --reader --repeat 10   # card reader, network
python tools/mvsxfr.py --reader --repeat 10   # card reader, test file
python tools/g2ind.py --repeat 10             # IND$FILE, both files
```

Representative output:

```
ONF001I NETWORK LOADED N=913 E=72852 CRC=9C0A8413
ONF002I   FLOAT BACKEND   SOFT2C
ONF002I   PLATFORM        MVS38J
ONF003I VERIFY-ONLY: NETWORK OK

XFR003I COMPUTED CRC     B6D02D34
XFR004I EBCDIC-BLANK  OK
XFR000I TRANSPORT OK: ALL 256 BYTE VALUES SURVIVED
```

`tstxfr.c` was **shown to fail**, not only to pass: with one `0x40` changed to
`0x20` it reports `XFR005E EBCDIC-BLANK FIRST BAD AT +100, GOT 20` and a CRC
mismatch, exit 12.

x86 regression after the engine changes: `mingw32-make test` green on **SOFT3E,
SOFT2C and NATIVE**; `make eng` 25 passed, 0 failed.

## 9. Not proven

- **Nothing about z/OS or s390x.** Every MVS result is MVS 3.8j under Hercules
  on this x86 host, GCCMVS 3.2.3 at `-O1`, SOFT2C.
- **Elapsed times are job round-trips, not transport times** (§4.4).
- **One network file.** The 885 KB `path` subcircuit; the 20 MB `hop2` and
  299 MB `full` networks were not transferred by any method.
- **The card reader needs a `devinit`**, so a real mainframe without operator
  access to the device would need IND$FILE — which is why it is recorded.
- **`HERC01.ONFTST` and `HERC01.ONFNETI` were left catalogued** on the lab.

## 10. Related docs

- `docs/ONFLY-SRS.md` — D-141…D-150, VL-45…VL-56, Gate G2, A-07, IR-TRN-01…04.
- `docs/implementations/2026-09-11-gate-g3-measured.md` — the preceding gate.
- `docs/implementations/2026-09-11-raincode-cics-probes-measured.md` — VL-37.
