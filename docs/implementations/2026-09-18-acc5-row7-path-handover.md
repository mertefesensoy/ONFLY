# Handover: ACC-5 row 7's `path` half, interrupted 2026-09-18

**Read this before resuming.** The session was stopped mid-run because the
owner had to travel with the host machine. Nothing here is a failure; the
work is complete up to the point where a mainframe job was in flight, and
that job was lost to the shutdown.

| Field | Value |
|---|---|
| Date | 2026-09-18 |
| Scope | Section 8.3 row 7's `path` half (D-458) |
| Plan of record | `docs/plan/2026-09-18-acc5-row7-path.md` (P-37, approved by D-461) |
| Decisions recorded | D-458 to D-466 |
| Proposals raised | P-37 (the plan), P-38 (`--compare` labels any directory "row 7") |
| State | Slices 1 and 2 **COMPLETE**. Slice 3 **RUN AND LOST**. Slices 4 and 5 **NOT STARTED** |

---

## 1. What is done and needs no repeating

**Slice 1, the lab.** TK5 was brought up from cold and the two things that
are easy to get wrong were both measured rather than assumed:

* The Hercules codepage had silently reset to `default`, exactly as VL-87
  says it does on a restart. It was set to `819/1047` and `mvsub`'s own
  guard then returned `check_codepage: OK`. **A resumed session must do this
  again**, because it is a property of the running Hercules, not of the disk.
* `HERC01.ONFLY.PNET` and `HERC01.ONFLY.PREQ` are **both still catalogued**,
  confirmed by an IDCAMS `LISTCAT LEVEL(HERC01.ONFLY)` job (`ONFLIST`,
  JOB 397) at `COND CODE 0000`. So `--install-net` and `--req` do **not**
  need repeating. `HERC01.ONFLY.JPRSP` was absent, which is correct: the run
  job creates it.

**Slice 2, the tool.** All committed. `tools/mvsjcc.py` takes
`--net srext|path`, each network carries its own job name and response
dataset (D-462), `check_names()` asserts they cannot cross over, the collect
timeout is 14400 s, and `--recover` exists (D-465). `tests/run_mvsjcc.py`
stands at **43 passed, 1 failed** on x86-64 with Python 3.13; the single
failure is `path: the TK5 JCC recording is present`, which is the artefact
slice 3 was producing and is *supposed* to fail until it exists.

---

## 2. What was lost, and exactly what it cost

`ONFJPRUN` **JOB 398**, submitted 13:34:32, started 13:34:33.

* All thirteen JCC compiles, `PRELINK`, `LKED` and `SCRATCH2` completed at
  `RC= 0000` **within fifteen seconds**. JCC compiles far faster than
  GCCMVS, whose `COMP1` alone cost 43.54 s in the row 6 `path` job. The
  whole cost of this job is the `GO` step.
* `GO` began 13:34:48 and was cancelled at 14:38:55 by `/C ONFJPRUN`, giving
  `IEF450I ONFJPRUN GO - ABEND S222 U0000`, which is the operator-cancel
  code and not a defect.
* `$HASP308 ONFJPRUN ESTIMATED TIME EXCEEDED` appeared at 14:33:50. **This
  is benign.** It is JES2 comparing elapsed time against the accounting
  estimate on the JOB card, `JOB (001)`, not a cancellation. The governing
  limit is `TIME=1440`, twenty-four hours. Row 6's `path` run drew the same
  message on JOB 304.

The run must be repeated in full: the response dataset is written by the
`GO` step, the step abended, and the `DUMP` step is `COND=(8,LT)` so it was
skipped. `mvsjcc` reported `recovered 0 response records from the IDCAMS
dump` and exited 1, correctly.

### 2.1 But it did not die silently, and what it said matters

The cancel spooled the job, so the listing survives and is committed as
`data/phase-e/jcc/ONFJPRUN-partial-JOB398.txt`. Two things in it change the
plan for the next run.

**Two requests completed, and both agree with Section 8.4:**

    ONF301I REQUEST 1 COMPLETE FP=6C143127        golden G-01 6C143127
    ONF301I REQUEST 2 COMPLETE FP=5CAB2AA0        golden G-02 5CAB2AA0

This is the **first JCC evidence on the `path` network in the project's
history**, and as far as it goes it is agreement. It is not row 7 and must
not be recorded as row 7: two of fourteen, no response records, no
whole-record comparison under D-261, and neither of the three rejection
paths among them.

**The cost is far worse than the estimate the owner was given.**

    IEF374I STEP /GO / STOP 26261.1238
            CPU 63MIN 51.67SEC  SRB 0MIN 00.04SEC  VIRT 2568K  SYS 340K

Row 6 ran **all fourteen** requests in `CPU 63 min 04.79 s` (VL-91, JOB 279).
JCC spent **63 min 51.67 s** and reported **two**. The 0.874 factor this
session extrapolated from `srext` is therefore **not transferable to
`path`**, and the "55 min to 2 h 18 min" figure in the plan of record and in
D-461 is wrong for JCC. A straight scaling over the twelve requests that
actually simulate suggests something in the region of **six hours of GO
CPU**, but that is an estimate from a single truncated sample and should be
labelled as such.

**One thing that is NOT established**: whether only two requests completed,
or whether more completed and their `printf` output was still in the C
runtime's buffer when the S222 abend discarded it. Nothing in the listing
distinguishes those. Treat "two completed" as *two reported*.

Before the next run, decide what to do about this: a six-hour job may want
the suite split across several jobs, or the requests reordered so the three
rejection paths (G-11, G-12, G-13), which barely simulate at all, are
reached early. **That is an owner decision and has not been asked.**

---

## 3. Resuming: the exact sequence

1. Start Hercules. The two traps are documented in the Phase E handover and
   both still apply on this host: `NoDefaultCurrentDirectoryInExePath=1` is
   set, so it must be `.\mvs.bat` and not `mvs.bat`; and the bundled
   `tail.exe` it launches is harmless.
2. **Set the codepage**, or every submission fails: `codepage 819/1047`.
   Confirm with `mvsub.check_codepage()`, which raises rather than warns.
3. Re-run slice 3. Nothing else needs redoing:

       python tools/mvsjcc.py --net path --run --out data/phase-e/jcc

   Budget **1 to 3 hours**. The measured range for the identical fourteen
   requests under GCCMVS is 63 min 04.79 s of `GO` CPU on a quiet host
   (JOB 279) and 157 min 52.69 s on a contended one (JOB 308), and JCC costs
   0.874 of GCCMVS on the same work. This session's lost run had reached 59
   minutes without finishing, which is consistent with the middle of that
   range and says nothing more than that.
   **Do not load the host while it runs.** Host contention is the whole
   explanation for row 6's 2.5x spread, and it would corrupt the timing
   figure the row is meant to report.
4. If the submitter dies but the job finishes, **do not re-run it**:

       python tools/mvsjcc.py --net path --recover --out data/phase-e/jcc

5. Then slice 4:

       python tools/mvsjcc.py --net path --compare data/phase-e/jcc \
                                                   data/phase-d/x86w

   Expect `raw=False binary=True translated=True` and fourteen fingerprints
   equal to Section 8.4's. Note P-38: this command prints
   `ACC-5 row 7 PASS` whatever directory it is given, so check that the
   first path really is `data/phase-e/jcc`.
6. Then slice 5, which is unstarted: amend Section 8.3 row 7, write VL-138,
   finish `docs/implementations/2026-09-18-acc5-row7-path.md` section 5,
   run `mingw32-make test`, commit and push.

A ready-made, measurement-only amender for step 6 was written and is
**deliberately not committed**, because it belongs to a run that no longer
exists: it took the fourteen fingerprints out of
`data/phase-e/jcc/rsp-path-2c.bin` rather than out of the golden file, so
the row could not claim something the run did not produce, and it refused
unless the `GO` CPU and wall figures were passed explicitly. Rewrite it the
same way rather than filling the row by hand.

---

## 4. What is NOT proven, and must not be reported as if it were

**No JCC `path` result exists.** Row 7 still covers five of the nineteen
Section 8.4 requests, exactly as it did before this session. In particular
the three rejection paths G-11 (ONF201W), G-12 (ONF203E) and G-13 (ONF202E)
have still never been reached by a second code generator.

The only comparison run this session was
`tools/mvsjcc.py --net path --compare data/phase-e/mvs data/phase-d/x86w`,
which passed all fourteen fingerprints. **That was row 6's GCCMVS
recording**, pointed at deliberately to prove the tool worked before the JCC
data existed. It is evidence about `tools/mvsjcc.py`, not about JCC, and the
fact that it printed `mvsjcc: ACC-5 row 7 PASS` over GCCMVS records is what
P-38 was raised about.

Everything measured on x86-64 in this session was Windows 11 with
Python 3.13. `mingw32-make test` was **not run**: it was deliberately held
back so as not to contend with TK5, and then the session ended. The tree is
therefore committed without a full-suite green, and
`tests/run_mvsjcc.py` is expected to report **1 failed** until slice 3
succeeds.

---

## 5. Lab state at shutdown

Hercules was stopped cleanly rather than killed, in D-293's sequence,
because a shutdown around an active initiator is how a 1981 operating
system ends up with half-written datasets. What was issued, in order:

    /C ONFJPRUN                  IEE301I ONFJPRUN CANCEL COMMAND ACCEPTED
                                 IEF450I ONFJPRUN GO - ABEND S222 U0000
                                 $HASP150 ONFJPRUN ON PRINTER1 11,176 LINES
                                 $HASP250 ONFJPRUN IS PURGED
    script scripts/shutdown      BSPRS08I - Immediate Shutdown Requested!
                                 $HASP097 PRINTER1/2/3, PUNCH1, READER1
                                 and LINE1..LINE4 all IS DRAINED
                                 BSPSD999 - Shutting down MVS
                                 stopall; sysclear completed
                                 HHC01427I Main storage released
                                 HHC01422I Configuration released

**Cancel the job first.** The output only reached the printer because the
job was cancelled and therefore *ended*; JES2 spools on end, not during. Had
Hercules been killed instead, the 63 minutes of CPU would have produced
nothing at all, including the two fingerprints in section 2.1.

**`exec scripts/shutdown` does not work on this build**: it answers
`HHC02227E Shell/Exec commands are disabled`. The working form is
`script scripts/shutdown`, which is the Hercules script reader rather than a
shell escape. That cost one wasted console round trip here.

Verified down four ways: no `hercules` process, console port 8038 closed,
reader port 3505 closed, and the log ending in `Configuration released`.
No `qemu`, `runnet` or stray `python3.13` process was left behind either.

`HERC01.ONFLY.JPRSP` may exist as a partial or uncatalogued dataset from the
cancelled `GO` step. Nothing needs doing about it: `run_deck()`'s own
`SCRATCH2` step deletes it with `DISP=(MOD,DELETE)` before the next run
allocates it, which is exactly why that step is there.
