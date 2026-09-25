# -*- coding: utf-8 -*-
"""Drive Phase G's 3270 transaction with nobody watching, and assert.

WHY THIS EXISTS
---------------
D-127 wanted the flow shown on a real 3270 so that nobody could answer
"a PC drew the picture".  A demonstration that can only be PERFORMED
is worth less than one that can be CHECKED: it decays silently, and
the only way to know it still works is to do it again by hand.  VL-39
already noticed that the emulator is scriptable and called that
finding worth more than the closure it was written for.  This is that
finding spent.

WHAT IT ASSERTS, AND WHY THAT ONE THING
---------------------------------------
D-430: the fingerprint on the screen must equal the Section 8.4
golden value for the request typed.  The default request is **G-16** --
`srext`, SUGR, 40 Hz, 1000 ms, seed 1, `BAF81D91` -- because a golden
value is published and fixed and cannot drift with the run.  VL-104
measured 169 s of TK5 CPU for a request of that duration, so the check
waits minutes; it is deliberately not part of `make test`.

It also cross-checks the screen against the PRINTED report the same
job produced.  FR-BAT-04 owns that report and the subsystem formats
its own screen, so the two agree only if both read the same response
record correctly.  Asserting the fingerprint alone would leave the
spike counts and latencies unchecked on the screen path.

usage:  python tools/mvstx.py [--rate N] [--ms N] [--seed N]
                              [--timeout SEC] [--keep]

        --keep   leave the region running afterwards
"""
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import goldfp                                         # noqa: E402
import ic3270                                         # noqa: E402
import mvsicom                                        # noqa: E402
import mvsub                                          # noqa: E402

#: G-16 (D-430).  Rate 40, the standard duration, seed 1.
RATE, MS, SEED = 40, 1000, 1
POLL = 20.0
TIMEOUT = 900

FP_RE = re.compile(r"FP=([0-9A-F]{8})")
ROW_RE = re.compile(r"READOUT\s+(\d+)\s+ID=\s*(-?\d+)\s+LAT-US=\s*"
                    r"(\d+)(-?)\s+SPIKES=\s*(\d+)\s+HZ=\s*([\d.]+)")
#: The printed report's own readout line (FR-BAT-04), which is 133
#: columns wide and carries the neuron NAME the screen has no room for.
RPT_RE = re.compile(r"READOUT\s+(\d+)\s+ID=\s*(\d+)\s+(\S+)\s+"
                    r"LAT-US=\s*(-?\d+)\s+SPIKES=\s*(\d+)")


def say(text):
    """Print and flush.

    This tool waits minutes on emulated MVS, and Python block-buffers
    stdout when it is a file rather than a terminal -- so an
    unflushed run shows nothing at all until it exits, and there is
    no way to tell "waiting" from "hung".  Measured 2026-09-17.
    """
    sys.stdout.write("%s\n" % text)
    sys.stdout.flush()


def command_text(rate, ms, seed):
    """What the operator types.  Fixed columns, as the subsystem reads."""
    return "SUGR,%04d,%04d,%09d" % (rate, ms, seed)


def screen_text(rows):
    return " ".join(r.strip() for r in rows if r.strip())


def golden_for(rate, ms, seed):
    """The Section 8.4 fingerprint for this request, or None.

    The five `srext` golden requests share a stimulus, a duration and
    a seed and differ only in rate, so anything else is not one of
    them and is reported rather than asserted.
    """
    if ms != 1000 or seed != 1:
        return None, None
    return goldfp.SREXT.get(rate), goldfp.SREXT_ID.get(rate)


#: The report's request line (FR-BAT-04), used to identify the run.
REQ_RE = re.compile(r"REQUEST\s+\d+\s+CODE=(\S+)\s+RATE=\s*(-?\d+)\s+"
                    r"MS=\s*(\d+)\s+SEED=\s*(\d+)")


def report_rows(rate, ms, seed, jobname="ONFTX"):
    """The printed report of the run that matches this request.

    Returns (readout rows, fingerprint), the rows being
    (n, id, name, latency, spikes) as FR-BAT-04 printed them.

    IDENTIFIED BY THE REQUEST, NOT BY BEING LAST.  The printer file
    accumulates every run, and taking the most recent `ONFTX` job
    compares the screen against whichever run happened last -- which
    on 2026-09-17 was a different rate and duration from the one being
    checked.  The report echoes the request on its own line, so the
    right job can be named rather than assumed.  Circularity is
    avoided by matching on the REQUEST, which the caller typed, and
    not on the fingerprint, which is the thing under test.
    """
    text = mvsub.read_printer()
    i = text.rfind("START  JOB")
    while i > 0:
        if jobname in text[i:i + 120]:
            seg = text[i:]
            j = seg.find("END   JOB")
            if j > 0:
                seg = seg[:j]
            m = REQ_RE.search(seg)
            if m and (int(m.group(2)), int(m.group(3)),
                      int(m.group(4))) == (rate, ms, seed):
                fp = None
                for f in FP_RE.finditer(seg):
                    fp = f.group(1)
                return [t.groups() for t in RPT_RE.finditer(seg)], fp
        i = text.rfind("START  JOB", 0, i)
    return [], None


def run(rate, ms, seed, timeout, keep):
    want, gid = golden_for(rate, ms, seed)
    cmd = command_text(rate, ms, seed)
    say("mvstx: request %s%s"
          % (cmd, (" (%s, golden %s)" % (gid, want)) if want else
             " (no Section 8.4 comparand; reported, not asserted)"))

    started_here = False
    if not mvsicom.running():
        if not mvsicom.start(timeout=300):
            say("mvstx: the region did not come up")
            return 1
        started_here = True
    else:
        say("mvstx: the region is already running")

    dev = mvsicom.free_device()
    if dev is None:
        say("mvstx: no free 3270; every local unit is allocated")
        return 1
    say("mvstx: device %s" % dev)

    got_fp, rows, waited = None, [], 0.0
    t0 = time.time()
    with ic3270.Session(device=dev, settle=3) as s:
        s.logon("INTERCOM")
        started = s.command(cmd)
        say("mvstx: %s" % screen_text(started)[:76])
        deadline = time.time() + timeout
        while time.time() < deadline:
            time.sleep(POLL)
            shown = s.command("BUZZ,")
            text = screen_text(shown)
            m = FP_RE.search(text)
            if m:
                got_fp = m.group(1)
                rows = [t.groups() for t in ROW_RE.finditer(text)]
                waited = time.time() - t0
                say("mvstx: the result came back after %.0f s" % waited)
                for r in shown:
                    if r.strip():
                        say("   |%s" % r[:78])
                break
            say("mvstx: %s" % text[:70])

    if got_fp is None:
        say("mvstx: no result within %d s" % timeout)
        if started_here and not keep:
            mvsicom.stop()
        return 1

    # --- the two checks ---------------------------------------------
    ok = True
    if want:
        good = got_fp == want
        ok = ok and good
        say("mvstx: fingerprint %s %s %s (%s)"
              % (got_fp, "==" if good else "!=", want, gid))
    else:
        say("mvstx: fingerprint %s, reported only" % got_fp)

    rpt, rpt_fp = report_rows(rate, ms, seed)
    if rpt:
        same_fp = (rpt_fp == got_fp)
        ok = ok and same_fp
        say("mvstx: printed report fingerprint %s %s the screen's"
              % (rpt_fp, "matches" if same_fp else "DIFFERS from"))
        for n, rid, name, lat, spk in rpt:
            match = [r for r in rows if r[0].lstrip("0") == n.lstrip("0")]
            if not match:
                say("mvstx: report readout %s has no screen row" % n)
                ok = False
                continue
            srow = match[0]
            slat = ("-" + srow[2]) if srow[3] == "-" else srow[2]
            good = (srow[1].lstrip("0") or "0") == (rid.lstrip("0") or "0") \
                and int(slat) == int(lat) and int(srow[4]) == int(spk)
            ok = ok and good
            say("mvstx: readout %s %s  report id=%s %s lat=%s spikes=%s"
                  % (n, "agrees" if good else "DISAGREES",
                     rid, name, lat, spk))
    else:
        say("mvstx: no printed report found to cross-check against")
        ok = False

    if started_here and not keep:
        mvsicom.stop()
    say("mvstx: %s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


def main(argv):
    rate, ms, seed, timeout, keep = RATE, MS, SEED, TIMEOUT, False
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--rate":
            i += 1
            rate = int(argv[i])
        elif a == "--ms":
            i += 1
            ms = int(argv[i])
        elif a == "--seed":
            i += 1
            seed = int(argv[i])
        elif a == "--timeout":
            i += 1
            timeout = int(argv[i])
        elif a == "--keep":
            keep = True
        else:
            sys.stderr.write("mvstx: unknown argument %s\n" % a)
            return 2
        i += 1
    return run(rate, ms, seed, timeout, keep)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
