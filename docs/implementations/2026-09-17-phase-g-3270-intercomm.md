# 2026-09-17 — Phase G, second component: the 3270 flow

| Field | Value |
|---|---|
| Date | 2026-09-17 |
| Author | ONFLY engineering (with the owner deciding, through AskUserQuestion) |
| Phase / gate | G (second MVP), second component |
| Owner decisions relied on | D-424 (scope), D-425 (commit and push), D-426 (the transaction starts a run), D-427 (tables may be replaced, with backups), D-428 (P-30 is the plan of record), D-429 (`SUGR` starts, `BUZZ` shows), D-430 (slice 5 asserts G-16), D-431 (the subsystem is bound into the core), D-432 (backups in an ONFLY-owned dataset) |
| Requirements touched | FR-BAT-01, FR-BAT-04, FR-BAT-06, IR-JCL-02, IR-JCL-03, IR-COM-01, C-03, C-04, D-93, D-132 |
| Open items closed | none |

## 1. Problem / motivation

Phase G has three components and two were built: the `EXEC CICS` transaction
(D-391…D-402, VL-117) and the live view (D-403…D-423). The third — D-127's
requirement that the transaction flow be **shown on a real 3270** — was
unbuilt. D-127 gave the reason in one sentence: *"an x86 window alone invites
the reply that a PC drew the picture."* D-131 settled that the 3270 is driven
by the transaction monitor on TK5, because VL-37 measured that the free
Raincode edition cannot drive a terminal at all.

Without this, Phase G is incomplete, and D-126 makes the IBM permissions
request **with Phase G in hand**.

## 2. What changed

| File | Change |
|---|---|
| `tools/ic3270.py` | New. A **live** 3270 session: the emulator stays up and is driven turn by turn, because the flow waits minutes between two entries on a condition Python evaluates. |
| `tools/mvsicom.py` | New. The region's lifecycle (submit without waiting, watch for ready, shut down by operator reply), the backup/install/build/restore jobs, and which VTAM logical unit is free. |
| `tools/mvsrun.py` | Gained the `ONFTX` demonstration specification and an `installed` variant of `demo_deck` — network from the catalogued dataset, datasets pre-allocated, no scratch step — so the job the terminal starts is FR-BAT-01's job and not a second copy. |
| `tests/run_ic3270.py` | New. Everything judgeable without the lab, including the facts each lab failure paid for. Local-dependent checks skip out loud on a clone (D-233's pattern). |
| `Makefile` | `ic3270` in `make test`. |
| `docs/ONFLY-SRS.md` | D-424…D-432 in Appendix A.1, P-30 in A.2, VL-129…VL-132 in Appendix D. |
| `local/onflytx/*` | **Not committed** (D-132): the subsystem, its verb entry and its subsystem entry, which name the monitor's macros and copybooks. |

## 3. Implementation approach

### 3.1 The split the licence forces

D-132 is the shape of this component. The monitor's licence is
non-commercial-only *including derivative works* (VL-38) and this repository is
MIT (D-62), so nothing derived from it enters the tree. In practice:

- **`local/onflytx/`**, ignored in full: the COBOL subsystem, and two card-image
  updates adding ONFLY's verb and subsystem entries.
- **`tools/`**: everything that names only dataset names, message identifiers
  and ONFLY's own module names. Naming a dataset is description, not
  derivation, and `tools/lint_lic.py` draws the line mechanically on every
  `make test`.

The consequence is stated rather than discovered: **the demonstration is not
reproducible from a clone.** A third party gets the tooling and the record, not
the monitor side. `tools/mvsicom.py` raises a message that says so when
`local/onflytx` is absent, rather than failing with "file not found".

### 3.2 The flow

```
  operator                     the region on TK5                MVS batch
  --------                     -----------------                ---------
  LOGON APPLID=INTERCOM
  SUGR,0040,1000,000000001 --> validate the shape
                               read the job skeleton,
                               rewrite its marked card,
                               write the deck to the
                               internal reader             -->  ONFLYDRV STEP1
                           <-- ONF410I RUN STARTED              ONFLYENG STEP2
                                                                ONFLYDRV STEP3
                                                                  writes ONFRSP
  BUZZ,                    --> read the response dataset
                           <-- ONF422I STILL RUNNING, or
                               the echo, fingerprint and
                               one row per readout neuron
```

### 3.3 Three things that are deliberately *not* reimplemented

- **The job.** `tools/mvsrun.py`'s `demo_deck` builds it, once, under the new
  `ONFTX` specification. The subsystem copies the skeleton card for card and
  rewrites only the card whose first eight characters are `*ONFCARD`. That
  marker is a **comment card**: an unreplaced one produces no requests at all
  rather than a plausible wrong one.
- **The request's validity.** FR-BAT-05's reserved codes and FR-SIM-06's
  duration bound belong to ONFLYDRV and ONFLYENG. The subsystem checks the
  *shape* of what was typed and nothing else. A second implementation of a
  validation rule is exactly what produced D-289 and then D-360, silently both
  times.
- **The record layout.** The subsystem carries `COPY ONFCOM.` and
  `tools/mvsicom.py` expands it from `generated/ONFCOM.cpy` before submitting,
  which is what `layout/generate.py` does for `cobol/ONFLYDRV.cbl` and for the
  same reason (VL-57, D-161). It refuses if the statement is missing or
  duplicated, because a source that silently lost its layout would read the
  response record as spaces.

### 3.4 Contracts introduced

`ic3270.Session` — opens a scriptable emulator and connects; `do()` issues one
action and raises `ActionFailed` rather than returning a value nobody checks;
`close()` always quits the emulator, including on an exception, so a TK5
terminal is never left occupied by a crashed script. Side effect: occupies one
of TK5's local 3270s between `open()` and `close()`. It knows nothing about
ONFLY or about any transaction monitor.

`mvsicom.start()` — submits the region and returns only when **this run's** job
number has reported ready. `stop()` — replies to the region's operator message
and returns when JES2 says it is no longer executing. `free_device()` — a
terminal that VTAM shows as free, chosen by state and not by number.

## 4. Numerical details

One formula. The readout's firing rate in hertz, shown on the screen, is the
spike count over the simulated duration expressed in seconds:

    Hz = spikes × 1000 / duration_ms,  rounded to one decimal

with the division guarded so that a duration of zero yields zero rather than a
data exception. This is the same quantity FR-BAT-04's printed report states;
slice 5 checks the screen against the report rather than trusting the two to
agree.

The fingerprint is shown in hexadecimal. Each of the four bytes is placed in
the low half of a halfword whose high half is binary zero — so its value is 0
to 255 whatever its sign bit — and a divide by sixteen splits it into two
nibbles indexing a sixteen-character table. That is ONFLYDRV's own technique,
reused rather than reinvented.

## 5. Design decisions

| Question | Chosen | Alternatives | Why |
|---|---|---|---|
| Where do the numbers come from? | The terminal **starts** a real run (D-426) | Display a response the BUZZ job already wrote; run the engine inside the region | A run the audience starts answers D-127's objection; a lookup does not. The in-region path needs FR-CAL-01's unbuilt stub, PDPCLIB is not reentrant, and VL-104 measured 169 s per 1000 ms request |
| Is the subsystem bound into the core? | Yes, and the core is relinked per change (D-431) | Relink once and load dynamically | The core must be relinked anyway, because the subsystem table is one of its 219 INCLUDEs. The dynamic loader exists in this build but nothing here has exercised it |
| Where do backups live? | A new ONFLY-owned dataset (D-432) | Members beside the originals | It leaves volume `INT001` and the shipped directories untouched |
| How is the result shown? | Four rows of exactly eighty characters | The printed report's own lines | An unformatted 3270 write fills the buffer row by row, so a line padded to the row width lands on its own row and needs no control character. The printed report is 133 columns and would wrap |
| How does `BUZZ` know the result is fresh? | By the request echo | By the presence of a record | The dataset keeps the previous run's record, so "is there a record" is always yes. IR-JCL-03 puts the echo in the first sixteen bytes, so the comparison is exact |

## 5b. What the unattended check found on its first run

This is the argument for `tools/mvstx.py` existing, so it is written
down rather than left in a commit message. The flow had already been
driven by hand and looked right. The first unattended run **failed**,
and it was right to.

**The freshness test compared the wrong things.** `BUZZ,` answered with
a stale 100 ms record while the 1000 ms job it had just started was
still executing. The parse and the submitted job were correct — job 377
ran `RATE=40 MS=1000 SEED=1` and reported `FP=BAF81D91`, G-16's golden
value — so the fault was only in comparing the response's echo with
what `SUGR,` last sent: `MOVE W-CMD-MS TO W-LAST-MS` over a `PIC 9(4)`
receiver. The characters are now read back through a numeric
`REDEFINES` and both sides of the comparison are binary. That is
ONFLYDRV's own technique and it is there for the same reason (D-159):
this dialect's alphanumeric-to-numeric move is not to be trusted with a
comparison.

A hand-run demonstration would not have caught this. Typed by a person,
`SUGR,` then `BUZZ,` a minute later shows numbers that look entirely
plausible — they are real numbers from a real run, just not from *this*
run.

**The internal reader re-sent an earlier deck.** Two entries produced
three jobs, the third carrying the *first* entry's request, and JES2
answered `$HASP301 ONFTX - DUPLICATE JOB NAME - JOB DELAYED`. Each
submission now ends with a `/*EOF` card, which is what tells the
internal reader that the job is complete.

**And one in the tooling.** A second region submitted while the first
is up is held by JES2 on its duplicate name and released the instant
the first ends — so `stop()` watched a region end, be replaced by the
held one, and time out. Its caller would then have built against a
running region. It now names that case instead of reporting a failed
shutdown.

`BUZZ,` also gained a row saying what it is waiting for
(`ONF423I ASKED RATE= MS= SEED=`), so the screen never leaves the
operator guessing which run it is answering about — and so both sides
of that comparison are visible on the terminal itself.

## 6. Verification

See Appendix D, VL-129 to VL-132, for what each slice measured and what it does
not prove. Every result below is **TK5 MVS 3.8j under Hercules
4.9.1.11612-SDL-gee86c4de**, with MVT ANS COBOL `IKFCBL00` for the subsystem and
the GCCMVS-built engine from `HERC01.ONFLY.LOADLIB`; the terminal is `ws3270`
4.5ga6 on the x86-64 Windows host. Nothing here was run on z/OS, on Linux
s390x, or on real hardware.

Off-lab, on any host:

```bash
python tests/run_ic3270.py
```

On the lab, from nothing:

```bash
python tools/mvsicom.py --backup
python tools/mvsicom.py --install
python tools/mvsicom.py --txinstall
python tools/mvsicom.py --build
python tools/mvsicom.py --start
```

To undo every change to the installation:

```bash
python tools/mvsicom.py --stop
python tools/mvsicom.py --restore
```

## 7. Related docs

- `docs/plan/2026-09-17-phase-g-3270-intercomm.md` — the plan (P-30, D-428).
- `docs/ONFLY-SRS.md` — Sections 3.7 and 9.2; D-125…D-132; D-424…D-432;
  VL-32, VL-37, VL-38, VL-39, VL-57, VL-102, VL-104, VL-117, VL-129…VL-132.
- `docs/implementations/2026-09-17-phase-g-cics-transaction.md` — the first
  component.
- `docs/implementations/2026-09-17-phase-g-stage5-mvs-live-view.md` — the third.
