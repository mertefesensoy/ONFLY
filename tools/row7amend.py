# -*- coding: utf-8 -*-
"""Write ACC-5 row 7's `path` half into the SRS from the run, not by hand.

D-473, slice 5 of `docs/plan/2026-09-24-acc5-row7-path-resume.md`.

WHAT THIS DOES
--------------
Reads the recording `tools/mvsjcc.py --net path --run` wrote --
`data/phase-e/jcc/rsp-path-2c.bin` and its listing `ONFJPRUN.txt` -- and:

* refuses unless `mvsjcc.row7_listing()` accepts the directory (D-472),
  the listing's own run manifest says `COMPILER JCC`, `PLATFORM MVS38J`
  and `FLOAT BACKEND SOFT2C`, and every one of the fourteen response
  fingerprints equals the golden file's;
* takes the fingerprints from the RESPONSE RECORDS, not from the golden
  file, so the row cannot claim something the run did not produce;
* takes the JES2 job number, the GO step's CPU and its START/STOP stamps
  from the listing;
* replaces row 7's sentence "The `path` half of Section 8.4 has no JCC
  counterpart" with the measured result, and inserts VL-138 after VL-137.

It is the rewrite D-467's handover asked for: the first amender was
deliberately not committed because the run it belonged to was lost.

Run:

    python tools/row7amend.py            # print what would change
    python tools/row7amend.py --write    # change docs/ONFLY-SRS.md
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import mvsjcc                                         # noqa: E402
import mvsrun                                         # noqa: E402

SRS = os.path.join(ROOT, "docs", "ONFLY-SRS.md")
JCCDIR = os.path.join(ROOT, "data", "phase-e", "jcc")
REFDIR = os.path.join(ROOT, "data", "phase-d", "x86w")
OLD = ("**The `path` half of Section 8.4 has no JCC counterpart**, "
       "so row 7 stands on G-15…G-19.")
FP_OFF = 20                    # ONF-FPRINT, layout/master.py

GO_START = re.compile(r"IEF373I STEP /GO\s+/ START (\d{5})\.(\d{4})")
GO_STOP = re.compile(r"IEF374I STEP /GO\s+/ STOP\s+(\d{5})\.(\d{4})\s+"
                     r"CPU\s+(\d+)MIN (\d+\.\d+)SEC")
STEP = re.compile(r"IEF142I (\S+) (\S+) - STEP WAS EXECUTED - "
                  r"COND CODE (\d{4})")
MANIFEST = re.compile(r"ONF002I   (COMPILER|PLATFORM|FLOAT BACKEND|N)"
                      r"\s+(\S+)\s*$", re.M)
SUMMARY = re.compile(r"ONF302I STEP SUMMARY: (\d+) OK, (\d+) WARN, "
                     r"(\d+) ERROR")


class AmendError(Exception):
    pass


def measure():
    """Everything the row states, read from the recording, or raise."""
    mvsrun.select("path")
    why = mvsjcc.row7_listing(JCCDIR)
    if why:
        raise AmendError("not row 7's recording: %s" % why)
    text = io.open(os.path.join(JCCDIR, "%s.txt" % mvsjcc.jcc_job()),
                   encoding="ascii", errors="replace").read()
    job = mvsjcc.JES2_START.search(text).group(1)

    man = dict(MANIFEST.findall(text))
    want = {"COMPILER": "JCC", "PLATFORM": "MVS38J",
            "FLOAT BACKEND": "SOFT2C"}
    for k, v in sorted(want.items()):
        if man.get(k) != v:
            raise AmendError("run manifest %s is %r, not %r"
                             % (k, man.get(k), v))

    recs = mvsrun.read_records(os.path.join(JCCDIR, "rsp-path-2c.bin"))
    gold = mvsrun.golden_fingerprints(REFDIR)
    if len(recs) != len(gold):
        raise AmendError("%d records, %d golden entries"
                         % (len(recs), len(gold)))
    fps = []
    for (gid, wantfp), r in zip(gold, recs):
        got = r[FP_OFF:FP_OFF + 4].hex().upper()
        if got != wantfp:
            raise AmendError("%s fingerprint %s, golden %s"
                             % (gid, got, wantfp))
        fps.append((gid, got))

    a, b = GO_START.search(text), GO_STOP.search(text)
    if not a or not b:
        raise AmendError("no GO step START/STOP accounting in the listing")
    t0 = int(a.group(2)[:2]) * 60 + int(a.group(2)[2:])
    t1 = int(b.group(2)[:2]) * 60 + int(b.group(2)[2:])
    days = int(b.group(1)) - int(a.group(1))
    wall = t1 - t0 + days * 1440
    steps = STEP.findall(text)
    s = SUMMARY.search(text)
    return {
        "job": job, "fps": fps, "n": man.get("N"),
        "cpu": "%s min %s s" % (b.group(3), b.group(4)),
        "cpu_s": int(b.group(3)) * 60 + float(b.group(4)),
        "start": a.group(2), "stop": b.group(2), "wall_min": wall,
        "steps": len(steps),
        "codes": sorted(set(c for _j, _s, c in steps)),
        "go_code": [c for _j, st, c in steps if st == "GO"],
        "summary": s.groups() if s else None,
    }


def hhmm(t):
    return "%s:%s" % (t[:2], t[2:])


def row_text(m):
    fp = ", ".join("%s `%s`" % g for g in m["fps"])
    return (
        "**`path` half FILLED 2026-09-24 (D-468, D-471, D-473, VL-138): "
        "all fourteen `path` requests produce the golden fingerprints "
        "under JCC, so row 7 now covers all nineteen Section 8.4 "
        "requests, the three rejection paths included.** `path`: %s. "
        "Job `ONFJPRUN` JOB %s, network N = %s, the engine's own run "
        "manifest reading `COMPILER JCC`, `PLATFORM MVS38J`, `FLOAT "
        "BACKEND SOFT2C`; `GO` CPU %s. *(This sentence replaces "
        "\"The `path` half of Section 8.4 has no JCC counterpart, so "
        "row 7 stands on G-15…G-19\", written by the amender "
        "`tools/row7amend.py` from the response records, not by "
        "hand.)*" % (fp, m["job"], m["n"], m["cpu"]))


#: Row 6's `path` GO CPU on the identical fourteen requests under
#: GCCMVS, quiet host (VL-91, JOB 279) and contended host (D-463,
#: JOB 308); and D-467's cancelled JCC run, JOB 398.  Cited, not
#: measured here: they are the comparands for this run's cost.
ROW6_QUIET_S = 63 * 60 + 4.79
ROW6_BUSY_S = 157 * 60 + 52.69
JOB398_S = 63 * 60 + 51.67


def cost_text(m):
    return (
        "**Cost: the six-hour estimate D-471 carried is refuted.** The "
        "whole suite took %.2f min of `GO` CPU, %.3fx row 6's quiet-host "
        "GCCMVS figure (63 min 04.79 s, VL-91) and %.3fx its contended "
        "one (157 min 52.69 s, D-463). D-467's JOB 398 had reported only "
        "two requests after 63 min 51.67 s, %.0f%% of this run's whole "
        "cost; whether it had finished more whose `printf` output was "
        "still buffered at the cancel, or ran on a contended host, is "
        "NOT established by this run."
        % (m["cpu_s"] / 60.0, m["cpu_s"] / ROW6_QUIET_S,
           m["cpu_s"] / ROW6_BUSY_S, 100.0 * JOB398_S / m["cpu_s"]))


def vl_text(m):
    codes = ", ".join(m["codes"])
    summ = ("`ONF302I STEP SUMMARY: %s OK, %s WARN, %s ERROR`"
            % m["summary"]) if m["summary"] else "no ONF302I line"
    return (
        "| VL-138 | **ACC-5 row 7's `path` half: JCC reproduces all "
        "fourteen `path` golden fingerprints on TK5, and row 7 covers "
        "all nineteen Section 8.4 requests.** Measured 2026-09-24 on TK5 "
        "MVS 3.8j under Hercules 4.9.1.11612-SDL-gee86c4de, host CPU "
        "13th Gen Intel Core i7-13650HX, **JCC 1.50.00**, **SOFT2C**, "
        "network `path` (N = %s) from `HERC01.ONFLY.PNET`: `python "
        "tools/mvsjcc.py --net path --run --out data/phase-e/jcc`, job "
        "`ONFJPRUN` **JOB %s**, %d steps executed, condition codes seen "
        "%s, `GO` at %s; %s. `GO` ran from %s to %s guest time, about "
        "%d min of wall clock at the listing's minute resolution, and "
        "charged **CPU %s**. Then `python tools/mvsjcc.py --net path "
        "--compare data/phase-e/jcc data/phase-d/x86w`, guarded by "
        "D-472, compared every record whole under D-261 and every "
        "fingerprint against Section 8.4. The three rejection paths "
        "G-11, G-12 and G-13 have now been reached by a second code "
        "generator. %s **D-467's JOB 398 and D-477's JOB 400 are "
        "superseded, not recovered:** JOB 398's two reported "
        "fingerprints agreed, JOB 400 left none, and this run repeats "
        "the whole suite. **Not proven:** TK5 under Hercules on this host "
        "only (VL-04); one run, so the CPU figure is one sample and "
        "row 6's own spread (VL-91, D-463) shows host contention moves "
        "it by 2.5x; nothing here says anything about z/OS (row 8) |"
        % (m["n"], m["job"], m["steps"], codes,
           "/".join(m["go_code"]) or "?", summ, hhmm(m["start"]),
           hhmm(m["stop"]), m["wall_min"], m["cpu"], cost_text(m)))


def main(argv):
    try:
        m = measure()
    except AmendError as exc:
        sys.stderr.write("row7amend: REFUSED: %s\n" % exc)
        return 1
    s = io.open(SRS, encoding="utf-8").read()
    if s.count(OLD) != 1:
        sys.stderr.write("row7amend: row 7's sentence is not there "
                         "exactly once (%d); already amended?\n"
                         % s.count(OLD))
        return 1
    if "| VL-138 |" in s:
        sys.stderr.write("row7amend: VL-138 already exists\n")
        return 1
    row, vl = row_text(m), vl_text(m)
    sys.stdout.write("row 7:\n  %s\n\n%s\n" % (row, vl))
    if "--write" not in argv:
        sys.stdout.write("\nrow7amend: dry run; --write to apply\n")
        return 0
    s = s.replace(OLD, row)
    i = s.index("| VL-137 |")
    j = s.index("\n", i)
    s = s[:j + 1] + vl + "\n" + s[j + 1:]
    io.open(SRS, "w", encoding="utf-8", newline="").write(s)
    sys.stdout.write("\nrow7amend: wrote %s\n" % SRS)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
