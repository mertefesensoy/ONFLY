# 2026-09-15 — Phase E handover: what is running, and how to resume

| Field | Value |
|---|---|
| Date | 2026-09-15 |
| Author | ONFLY senior engineer |
| Phase / gate | Phase E — MVS MVP |
| Owner decisions relied on | D-279 … D-292 |
| Requirements touched | ACC-1 … ACC-7, NFR-OBS-01, ACC-5 rows 4–7 |
| Open items closed | none |

## 1. Problem / motivation

The owner is travelling with the machine. Four long jobs were in flight
when the session's turn budget ran out, two labs are up, and the next
session will not be this one. This document exists so that whoever
resumes — including a later Claude session with no memory of this one —
can tell in one read what was finished, what was interrupted, what is
safe to re-run, and what must **not** be re-run blindly.

Everything committed is on `origin/main`. The worktree is clean.

## 2. What is finished and needs nothing

These are measured, recorded and pushed. Do not re-run them to "check".

| Result | Where it is recorded |
|---|---|
| **ACC-5 row 7 PASS** — JCC builds the whole engine, same five `srext` fingerprints | SRS §8.3 row 7, VL-93, slice 4 doc |
| **ACC-5 row 6 PASS** (re-run on post-D-285 source) | SRS §8.3 row 6, VL-95 |
| **ACC-1, ACC-2, ACC-3 PASS** on the shipped `srext` network | VL-94, slice 5 doc §6.1–6.2 |
| **ACC-5 rows 1–3** (x86 oracle/NATIVE/SOFT3E), 20 passed each | slice 5 doc |
| `mingw32-make test` **exit 0** | slice 5 doc |
| D-285 neutral on x86: 260,376 + 781,128 TestFloat cases | slice 4 doc §6.7 |
| C-04 read off JCC's own PRELINK map: 58 symbols, none over 8 | slice 4 doc §6.6 |

## 3. What was interrupted, and whether it is safe to re-run

**All four are safe to re-run from scratch.** None of them mutates
anything another result depends on; each one's first step scratches what
it is about to create. But read the notes.

### 3.1 ONFPRUN — ACC-5 row 6, the `path` half (TK5)

    python tools/mvsrun.py --net path --run --out data/phase-e/mvs

Submitted 12:23, ~110 min elapsed, not finished. Its previous run cost
63 min of CPU; this one shared the host with 151 full-brain runs and a
TCG guest, and MVS itself said so:

    /11.23.19 JOB 304 $HASP308 ONFPRUN ESTIMATED TIME EXCEEDED
    /11.53.28 JOB 304 $HASP308 ONFPRUN ESTIMATED TIME EXCEEDED BY 30 MINUTES

**It was cancelled deliberately, as part of D-293's clean shutdown**, so
that JES2 could drain before MVS was quiesced — a shutdown around an
active initiator is how a 1981 operating system ends up with datasets
it never closed:

    IEE301I ONFPRUN  CANCEL COMMAND ACCEPTED
    JOB 304  IEF450I ONFPRUN GO - ABEND S222 U0000 - TIME=12.11.49
    JOB 304  $HASP395 ONFPRUN  ENDED
    JOB 304  $HASP150 ONFPRUN  ON PRINTER1    10,156 LINES
    JOB 304  $HASP250 ONFPRUN  IS PURGED

S222 is operator cancel, not a failure of the engine.

**Recovery will NOT work for this run and must not be attempted.**
`python tools/mvsrun.py --net path --recover` reads the last *completed*
ONFPRUN out of the printer — and the 10,156 lines above are a cancelled
job, not a completed one. `process_run()` would find fewer than
fourteen response records and refuse to write anything, which is the
right behaviour, but do not mistake the printer's 10,156 lines for a
result. **Resubmit it**: 65+ minutes on an otherwise quiet host.

It writes `data/phase-e/mvs/rsp-path-2c.bin`, which
`tests/run_mvsrun.py` checks against the fourteen `path` golden
fingerprints. The file currently in the tree is the **pre-D-285**
recording and still passes, because the cast is neutral — so a green
`make test` does **not** tell you this job finished.

### 3.2 ACC-4 (x86)

    python prep/acc4.py --jobs 10

Submitted 12:25, ~100 min elapsed. 151 full-brain runs. It writes
`data/calibration/acc4.json` **only at the end**, so an interrupted run
leaves nothing and costs nothing.

**Two things to know.** It needs the 1 GB connectome-weights feather and
the 594 MB `signed.npz` cache, both of which this session put in place —
`tools/fixtures.py --malecns weights annotations neurotransmitters`
re-fetches the first if the worktree is ever cleaned. And **ACC-3 reads
the file ACC-4 writes**: if ACC-4 is re-run, re-run

    python prep/extract.py --acc3-file data/networks/onfnet-malecns-v1.0-srext.bin --label srext --jobs 8

afterwards and compare, because `acc4.json` supplies both ACC-3's
comparand and its tolerances (slice 5 §3.4).

### 3.3 The s390x golden suite — ACC-5 rows 4 and 5

    wsl.exe -d Ubuntu -- bash -lc "ssh -i ~/onfly-s390x/id_ed25519 -p 2222 \
      -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
      onfly@127.0.0.1 'cd ~/onfly-d068b7 && make ONFPLAT=s390x CC=gcc \
      PYTHON=python3 BUILD=/tmp/b390d0 golden'"

Submitted 12:31; SOFT3E and NATIVE completed, SOFT2C was running.
`run_gld` prints its verdict per backend as it goes, but the **target**
only succeeds at the end, so no s390x figure is claimed.

**The guest holds a copy of this session's source, not a 9p mount.**
Its `/onfly` share points at the *unrelated* worktree
`onfly-senior-engineer-30d72c`; this session's tree was copied to
`~/onfly-d068b7` over ssh and verified byte-identical (slice 5 §3.5).
**If the guest is shut down and later restarted, that copy survives in
the qcow2** — but re-verify it before trusting it:

    sha256sum ~/onfly-d068b7/softfloat/c2c/softfloat.c
    # must be 276b1e7d7d29b72e2e15d43395d313e078095d02703045dc7c4d40858ba10822

`scratchpad/s390push.sh` re-copies it if needed. Exclude
`data/calibration/signed.npz` — it is 594 MB and the suite never reads
it.

### 3.4 `mingw32-make test`

A second full run was started late and did not finish. **The first one
completed and exited 0**, and is what the goal report cites. Re-running
costs about 10 minutes and needs nothing.

## 4. Numerical details

None. Nothing in this handover changes any arithmetic. The one source
change of the session, D-285's `(bits32 *)` cast, is argued neutral in
slice 4 §4 and measured neutral in §6.7.

## 5. Design decisions

Thirteen owner decisions, D-279 … D-292, all taken through
AskUserQuestion and recorded in SRS Appendix A.1 before any code
depending on them was written. Nothing in this document decides
anything; it records state.

## 6. Verification

Every figure cited in §2 is reproduced in the slice 4 and slice 5
documents with its exact command and an excerpt of real output, and
each carries its platform, compiler and float backend.

## 7. The single smallest piece of unfinished work

**NFR-OBS-01 is not met under JCC.** Row 7's own run manifest prints

    ONF002I   COMPILER        UNKNOWN
    ONF002I   PLATFORM        UNKNOWN

because `ONF_CCID` keys off `__GNUC__`, `__IBMC__` and `__MVS__` and
`ONF_PLATID` off `__MVS__`, `__s390x__` and `_WIN32` — and JCC defines
none of the six. The requirement asks the manifest to carry compiler
identification, and the determinism row that exists to *vary* the
compiler is the row that cannot name it.

D-291 chose the fix: ask JCC which macros it defines, then key the
branches on those. The probe is **written, tested and committed**:

    python tools/mvsjcc.py --ccprobe        # ~1 minute of TK5 time

It reports every candidate in `mvsjcc.CCMACROS` as DEFINED (with its
expansion) or `-`. Then add the matching `#elif` to
`engine/src/onflyeng.c` and `engine/include/onfplat.h`, and re-run row 7
once (~18 min) so the manifest is evidenced rather than asserted.

Those branches change no code on any platform whose macros are
undefined, so x86, s390x and the GCCMVS build are unaffected — but the
`git diff` in slice 4 §5, which shows `engine/` untouched, is a
statement about the row 7 run and stops being true once they are added.

## 8. Restarting the labs (resuming later the same day, D-293)

Both were shut down cleanly, so both must be started again. Neither
starts by itself.

**TK5 / Hercules** — `cmd.exe /c "cd /d C:\hercules-lab\mvs-tk5 && .\mvs.bat"`
with `run_in_background: true`. Two traps, both previously measured:
`NoDefaultCurrentDirectoryInExePath=1` is set on this host so a bare
`mvs.bat` fails even from the right directory — it must be `.\mvs.bat`;
and `mvs.bat`'s last line launches a bundled `tail.exe` that throws a
dialog, which is harmless and can be killed.

**Then set the codepage.** A restart silently returns Hercules to
`default`, where ONFLY C cannot reach GCCMVS (VL-18, D-101, D-103):

    codepage 819/1047        # via the console, or tools/mvsg0.py

`tools/mvsub.py` refuses to submit on the wrong codepage (D-103), so
this fails loudly rather than silently — but it fails *every* submission
until it is set.

**What survives on TK5 and what does not.** The catalogued datasets do:
`HERC01.ONFLY.ENET` and `.PNET` (the installed networks, D-286),
`.EREQ`/`.PREQ`, `.LOADLIB`, `.ONFNAM`. So `--install-net` does **not**
need repeating. `HERC01.ONFLY.PRSP` may hold a partial response dataset
from the cancelled run; nothing needs doing, because every job's own
SCRATCH step deletes what it is about to create.

**s390x guest** — see [[onfly-s390x-lab]] for the qemu line; it must be
started under `setsid`, because `qemu-system-s390x` installs its own
SIGHUP handler that overrides `nohup`. Boot to sshd takes about two
minutes under TCG, and the port forward listens well before sshd does,
so poll `uname -m` rather than the port.

**Its copy of this session's source was digested immediately before
shutdown and must be re-verified before it is trusted:**

    sha256sum ~/onfly-d068b7/softfloat/c2c/softfloat.c
    # 276b1e7d7d29b72e2e15d43395d313e078095d02703045dc7c4d40858ba10822
    sha256sum ~/onfly-d068b7/data/networks/onfnet-malecns-v1.0-srext.bin
    # bf09a3ad18a82b8ecc0dd2fd397d81e332f38c98a78325269f5c39d2b3b1f66d

If either differs, re-copy with `scratchpad/s390push.sh` and exclude
`data/calibration/signed.npz` (594 MB, never read by the suite).

## 9. Related docs

- [Phase E slice 4 — JCC and row 7](2026-09-15-phase-e-slice-4-jcc-row-7.md)
- [Phase E slice 5 — the acceptance sweep](2026-09-15-phase-e-slice-5-acceptance.md)
- [Phase E slice 1](2026-09-15-phase-e-slice-1-mvs-simulation.md),
  [slice 2](2026-09-15-phase-e-slice-2-names-and-report.md),
  [slice 3](2026-09-15-phase-e-slice-3-buzz.md)
- SRS Appendix A.1 (D-279 … D-292), Appendix D (VL-93, VL-94, VL-95),
  Section 8.3 rows 6 and 7
