# Phase G, second component — the 3270 flow under INTERCOMM

**Drafted for owner approval before any code is written.** Nothing in here is
committed until the owner approves it; this file is the proposal P-30 records.

| Field | Value |
|---|---|
| Date | 2026-09-17 |
| Phase | G (second MVP), second component |
| Authorising decisions | D-424 (this is the session's scope), D-426 (the transaction starts a real run), D-427 (the tables may be replaced, with backups) |
| Standing decisions it obeys | D-127 (both surfaces), D-131 (the 3270 half is INTERCOMM, not Raincode), D-132 (nothing INTERCOMM-derived is committed), D-125 (the lab may be changed) |
| Platform | MVS 3.8j TK5 under Hercules 4.9.1, plus `ws3270` on the x86-64 Windows host |

---

## 1. Problem / motivation

Phase G has three components. Two are built:

- the `EXEC CICS` transaction, verified in process against Raincode on x86-64
  (D-391…D-402, VL-117);
- the live view, x86 and MVS halves, byte-identical streams (D-403…D-423,
  VL-118…VL-127).

The third is unbuilt: **the transaction flow shown on a real 3270.** D-127 gave
the reason for wanting it in one sentence — *"an x86 window alone invites the
reply that a PC drew the picture"* — and D-131 settled that it is driven by
INTERCOMM on TK5, because VL-37 measured that the free Raincode cannot drive a
terminal at all.

Until this exists, Phase G is incomplete, and D-126 makes the IBM permissions
request **with Phase G in hand**.

## 2. What the lab actually offers (measured today, 2026-09-17)

Read-only survey jobs `ONFGIC1`…`ONFGIC6` on the running TK5. Nothing was
modified.

| Fact | Evidence |
|---|---|
| 31 `INT.*` datasets, catalogued in `SYS1.UCAT.ICOM` on volume `INT001` | `LISTC LEVEL(INT) ALL` |
| The VTAM application is **`INTERCOM`** | `SYS1.VTAMLST(AICOM)`: `INTERCOM APPL AUTH=(NVPACE,PASS,ACQ),BUFFACT=50` |
| The region is started by `INT.JCL.CNTL(RUNICOM)`, which EXECs `ICOMEXEC` at `IREGSIZ=8192K` — the 8M ceiling TBD-14 measured | `IEBGENER` of both members |
| `ICOMEXEC`'s STEPLIB is `INT.MODUSR`, `INT.MODLIB`, `INT.MODREL` — **user library first**, so a new load module needs no change to the shipped ones | the proc |
| The proc carries an explicit `ADD USER FILES HERE` slot, and a run job can add `//ICOM.xxx DD` overrides, so `SYS2.PROCLIB` need not be touched | the proc |
| A subsystem is a program entered `USING` the input message, the system parameter area, the subsystem control area, a return code and a dynamic work area, ending in a call that queues the reply | `INT.SYMUSR(ECHOMSG)`, `INT.SYMUSR(ECHONRC)` |
| The sample subsystem is **COBOL** and uses `01 name COPY member.` — the COBOL-68 spelling VL-57 measured as the only one `IKFCBL00` accepts | `ECHOMSG` source |
| The verb table and subsystem table sources are in `INT.SYMLIB` (`INTVRB00`, `SYCT400`); their assembled forms `BTVRBTB` and `INTSCT` are in `INT.MODUSR` | `LISTDS 'INT.SYMLIB' MEMBERS` |
| The terminal control table names `APPLID=INTERCOM` and carries both a logical-unit table and a **dynamic** logical-unit vector | `INT.SYMLIB(VCT)` |
| A 3270 client reaches VTAM's `Logon ===>` on this host and is scriptable | VL-39, `tools/tn3270.py` |
| The region closes cleanly on `NRCD` | VL-32 |
| One 1000 ms `srext` request costs **169 s** of TK5 CPU (185 s measured alone) | VL-104, VL-102 |

### The one thing that is not known

VL-32 drove INTERCOMM's verbs **from the MVS console WTOR**. No 3270 has ever
logged on to it. Whether this installation's terminal table will accept a
session from one of TK5's local 3270 devices — or whether the dynamic
logical-unit path covers it — is unmeasured. **That is why slice 1 is a spike
and comes before any ONFLY code.** If it fails, the shape of this component
changes and the owner is asked again rather than worked around.

## 3. What is built, and where each piece lives

D-132 draws the line: the repository is MIT and holds no INTERCOMM-derived
material; the subsystem, its verb entry, its driver and its JCL live on TK5 and
under the ignored `local/` directory. `tools/lint_lic.py` enforces it
mechanically and is run in every slice.

**Committed to the repository (MIT):**

| File | Role |
|---|---|
| `tools/ic3270.py` | Drive a scripted 3270 session: connect, log on to a named VTAM application, send a command line, capture the screen, and return it for assertion. Extends what `tools/tn3270.py` proved, and names nothing belonging to INTERCOMM. |
| `tools/mvsicom.py` | Bring the transaction region up and down on TK5; install the artefacts it reads out of `local/`; back up and restore the two tables (D-427). |
| `tools/mvstx.py` | The end-to-end check: bring the region up, drive the flow from `ws3270`, assert the fingerprint on the screen against Section 8.4, shut the region down, and print what it measured. |
| `generated/` skeleton job | The ONFLY job the transaction submits. It is **ONFLY's own JCL**, not INTERCOMM's, so it belongs in the repository; it is the FR-BAT-01 three-step pipeline with one control card the subsystem rewrites. |
| `docs/implementations/2026-09-17-phase-g-3270-intercomm.md` | The record. |

**Under `local/`, never committed:**

the subsystem source, the verb-table and subsystem-table source carrying
ONFLY's entries, and the region run job. These name INTERCOMM's macros and
copybooks and are exactly what D-132 keeps out.

## 4. The flow

Mirroring Section 3.7's names, which already reserve `BUZZ` for the overview
transaction and `SUGR` for the direct sugar transaction:

```
  operator                     INTERCOMM on TK5                 MVS batch
  --------                     ----------------                 ---------
  LOGON APPLID(INTERCOM)
  SUGR 40 1000 1        -->    validate the three numbers
                               read the ONFLY job skeleton,
                               rewrite its one control card,
                               write the deck to the internal
                               reader                      -->  ONFLYDRV STEP1
                        <--    "ONF4nnI RUN STARTED"            ONFLYENG STEP2
                                                                ONFLYDRV STEP3
                                                                  writes ONFRSP
  BUZZ                  -->    read the response dataset
                        <--    "STILL RUNNING" or the
                               readout lines and fingerprint
```

The second entry is what D-426 chose: the transaction **starts** a real engine
run rather than displaying one that already happened. `BUZZ` tells the two
apart by the request echo, which IR-JCL-03 guarantees comes back unchanged in
bytes 0–15 of the response record.

## 5. Slices

Each slice ends with its own evidence printed, and nothing in a later slice is
written before the earlier one has passed.

**Slice 1 — the spike: can a 3270 log on and drive a verb?**
Bring the region up with the shipped tables unchanged. From `ws3270`: log on to
`INTERCOM`, drive the sample verb VL-32 already exercised from the console, and
capture the reply. Shut down with `NRCD`. No ONFLY code, no table change, and
the region is put back exactly as found. *This answers Section 2's unknown. If
the answer is no, stop and ask the owner.*

**Slice 2 — ONFLY's own verb, answering from ONFLY's own subsystem.**
Back up `BTVRBTB` and `INTSCT` (D-427). Add ONFLY's verb and subsystem entries,
assemble, link into `INT.MODUSR`. Compile a minimal ONFLY subsystem with
`IKFCBL00` that replies with a fixed line, and link it. Drive it from
`ws3270`. This separates the plumbing from the logic: when slice 3 misbehaves,
the verb routing is already known good.

**Slice 3 — `SUGR`: parse the parameters and start a real run.**
The subsystem reads the three numbers, rejects what it cannot parse, reads the
ONFLY job skeleton, rewrites the control card and writes the deck to the
internal reader. Validation of the *request itself* stays where it already is —
`ONFLYDRV` and `ONFLYENG` own FR-BAT-05 and FR-SIM-06 — so this adds no second
implementation of a rule that already exists (the D-289 / D-360 failure).

**Slice 4 — `BUZZ`: read the response and format it.**
Spike count, first-spike latency in microseconds, rate in Hz to one decimal,
and the fingerprint in hexadecimal — the FR-BAT-04 fields, on a screen instead
of on a printer.

**Slice 5 — the end-to-end check and the record.**
`tools/mvstx.py` drives the whole flow with no human watching and asserts the
fingerprint against Section 8.4. The proposed regression request is **G-16**
(`srext`, SUGR, 40 Hz, standard duration, seed 1, golden `BAF81D91`) because it
has a golden fingerprint; at 169 s of TK5 CPU the automated run waits about
three minutes, which is acceptable for a check that is not in `make test`. A
shorter duration is better for a live demonstration but has no golden
comparand, so it is reported, not asserted. Then: the implementation doc, the
verification-limit entries, and — as proposals for the owner, never written in
on silence — a test-catalogue row and a Section 9.2 status note.

## 6. What this will not prove

Stated now rather than discovered at the end:

- It is **TK5 only**. Nothing here runs on z/OS, on Linux s390x, or on real
  hardware.
- The transaction **starts** the engine; it does not **contain** it. The
  in-region path is FR-CAL-01's stretch goal and D-426 declined it at its
  stated price. A reviewer watching the screen sees a mainframe transaction
  driving a mainframe batch run, not a simulation inside the transaction's own
  address space.
- The reply travels through INTERCOMM, which is **not CICS**. D-125 measured
  that TK5 carries no CICS at all and never can. ONFLY's real transaction
  source remains the `EXEC CICS` of D-130.
- The demonstration is **not reproducible from a clone**, by construction:
  D-132 keeps the subsystem out of the repository, so a third party gets the
  tooling and the record but not the INTERCOMM side.

## 7. Open questions for the owner

Carried into the approval question rather than settled here:

1. **The verb names.** `SUGR` to start and `BUZZ` to show mirrors Section 3.7,
   but there `BUZZ` is a *menu*, not a result screen.
2. **Whether slice 5's assertion uses G-16** (golden, three minutes) or a short
   request compared against an x86 run made in the same session.

## 8. Related docs

- `docs/ONFLY-SRS.md` — Sections 3.7, 9.2; D-125…D-132; D-424…D-427; VL-32,
  VL-37, VL-38, VL-39, VL-102, VL-104, VL-117.
- `docs/plan/2026-09-17-phase-g-cics-transaction.md` — the first component.
- `docs/plan/2026-09-17-phase-g-stage5-mvs-live-view.md` — the third.
