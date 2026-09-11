# -*- coding: utf-8 -*-
"""Gate G3: measure one request at the standard duration on MVS 3.8j.

G3 asks how large N and the duration can be within five minutes, and
NFR-PERF-01 bounds one request at the standard duration to five minutes
of wall-clock time on the TK5 reference host.  SR-EXT-03 makes N the
smallest of 250, 500, 1000, 2000, 4000 that satisfies it.  Until now
those have rested on an estimate -- D-128 records "two to three orders
of magnitude slower than x86" and says plainly that it is not a
measurement.  This replaces it with one.

tests/tstprf.c runs the real workload rather than a micro-benchmark:
one onfrun() call at 10,000 steps, the provisional standard duration
(D-37), at each N in SR-EXT-03's sequence.

THREE CLOCKS, DELIBERATELY
--------------------------
VL-40 measured what is available: clock() is a PDPCLIB stub returning
-1, time() has one-second resolution, and MVS itself reports per-step
CPU time via IEF374I at centisecond resolution.  All three matter here
for different reasons, so all three are reported:

  time() inside the program   attributes time to a specific N, which
                              the other two cannot do
  IEF374I for the GO step     MVS's own accounting, independent of
                              PDPCLIB, and a cross-check that the
                              program's own arithmetic is not lying
  host wall clock             what NFR-PERF-01 is actually written in,
                              and the only one that includes Hercules'
                              own overhead

A disagreement between the first two would matter more than either
number, which is why they are not collapsed into one.

Run:  python tools/mvsprf.py [--print]
"""
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import mvsbld  # noqa: E402
import mvsub  # noqa: E402

JOB = "ONFPRF"

# SetThreadExecutionState flags (winbase.h).
ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001


def keep_awake(on):
    """Ask Windows not to idle-sleep while the measurement runs.

    This is the documented application API for "work is in progress",
    the same one installers and media players use.  It sets nothing
    persistent: the assertion is scoped to this process and is cleared
    on the way out, so no power setting is changed and nothing needs
    undoing if this crashes.

    It is a partial defence and is documented as one.  It prevents the
    IDLE timeout.  It does NOT prevent sleep caused by closing a
    laptop lid, which is a separate policy -- and closing the lid is
    exactly what invalidated the first attempt at this measurement.
    trust() is the backstop for everything this cannot prevent.
    """
    if not sys.platform.startswith("win"):
        return False
    try:
        import ctypes
        flags = ES_CONTINUOUS | (ES_SYSTEM_REQUIRED if on else 0)
        return ctypes.windll.kernel32.SetThreadExecutionState(flags) != 0
    except Exception:
        return False

B32 = "third_party/SoftFloat-2c/softfloat/bits32/"
INCLUDES = {
    "milieu.h": "softfloat/c2c/milieu.h",
    "softfloat.h": "softfloat/c2c/softfloat.h",
    "softfloat-macros": B32 + "softfloat-macros",
    "softfloat-specialize": "softfloat/c2c/softfloat-specialize",
    "onfproc.h": "softfloat/c2c/onfproc.h",
}
UNIT = "softfloat/c2c/softfloat.c"

HEADERS = [
    ("engine/include/onfplat.h", "ONFPLAT"),
    ("engine/include/onffp.h", "ONFFP"),
    ("engine/include/onfker.h", "ONFKER"),
    ("engine/include/onfrnd.h", "ONFRND"),
    ("engine/include/onfstm.h", "ONFSTM"),
    ("softfloat/c2c/milieu.h", "MILIEU"),
    ("softfloat/c2c/softfloat.h", "SOFTFLOA"),
    ("softfloat/c2c/onfproc.h", "ONFPROC"),
]

RESULT = re.compile(r"^\s*(?:#\s|PERF\b)")
PERF = re.compile(r"^PERF n=(\d+) e=(\d+) reps=(\d+) secs=(\d+) "
                  r"spikes=(\d+) rc=(\d+)")
GOCPU = re.compile(r"IEF374I STEP /GO\s*/ STOP\s+\S+\s+CPU\s+"
                   r"(\d+)MIN\s+([\d.]+)SEC")

# NFR-PERF-01's bound, in seconds.
LIMIT = 300.0
# D-37's provisional standard duration, matching tests/tstprf.c.
STDSTEPS = 10000


def report(rows, gocpu, wall, hcpu0, hcpu1):
    """Turn the raw rows into the numbers G3 actually asks for."""
    print("=== Gate G3: one request at the standard duration "
          "(%d steps) ===" % STDSTEPS)
    print("  %6s %8s %6s %6s %12s %14s %10s"
          % ("N", "edges", "reps", "secs", "per request", "ns/neuron-step",
             "spikes"))
    results = []
    for n, e, reps, secs, spikes, rc in rows:
        if reps == 0:
            continue
        per = float(secs) / float(reps)
        nsteps = float(n) * float(STDSTEPS)
        ns = (per / nsteps) * 1e9
        results.append((n, per, ns))
        print("  %6d %8d %6d %6d %10.2f s %12.1f %10d"
              % (n, e, reps, secs, per, ns, spikes))
        if rc != 0:
            print("       kernel returned rc=%d at n=%d" % (rc, n))

    if not results:
        return None

    print()
    print("  NFR-PERF-01 bound: %.0f s of wall clock per request" % LIMIT)
    ok = [n for n, per, _ in results if per <= LIMIT]
    if ok:
        print("  Largest N meeting it at this duration: %d" % max(ok))
        print("  SR-EXT-03 picks the SMALLEST of 250/500/1000/2000/4000")
        print("  that also satisfies ACC-3 and NFR-MEM-01, so this is a")
        print("  ceiling, not the answer to SR-EXT-03 on its own.")
    else:
        print("  No measured N meets it at this duration.")

    # Headroom is the useful form for TBD-06: how much longer than the
    # provisional standard duration would still fit.
    print()
    print("  Duration headroom at the five-minute bound:")
    for n, per, _ in results:
        factor = LIMIT / per
        print("    N=%-5d  %6.1fx the standard duration "
              "(~%.0f ms of simulated time)"
              % (n, factor, factor * 1000.0))

    print()
    if gocpu is not None:
        # Reported for the record, NOT used to certify: see trust().
        print("  MVS says the GO step used %.2f s CPU -- recorded, but"
              % gocpu)
        print("  not used as evidence; guest clocks cannot see a sleep.")
    print("  Host wall clock for the whole round trip: %.1f s" % wall)
    if not trust(hcpu0, hcpu1, wall):
        return None
    return results


def herc_cpu():
    """Seconds of host CPU the Hercules process has consumed, or None.

    This is the only clock in the whole arrangement that cannot be
    fooled by the host sleeping, because it is charged by the host
    kernel to a host process for instructions that host actually
    retired.  Everything the guest can see is downstream of Hercules
    and inherits whatever Hercules believes about time.
    """
    try:
        import subprocess as sp
        out = sp.run(["powershell", "-NoProfile", "-Command",
                      "(Get-Process hercules -ErrorAction "
                      "SilentlyContinue).CPU"],
                     stdout=sp.PIPE, stderr=sp.DEVNULL, timeout=30)
        text = out.stdout.decode("ascii", "replace").strip()
        return float(text.splitlines()[0]) if text else None
    except Exception:
        return None


def trust(hcpu0, hcpu1, wall):
    """Refuse the measurement if the host was not really running it.

    WHY THIS EXISTS, AND WHY IT IS NOT THE OBVIOUS CHECK
    ---------------------------------------------------
    The first full attempt at this measurement ran while the host
    entered Modern Standby three times, because its lid was closed part
    way through.  tests/tstprf.c times with time(), which Hercules
    derives from the host clock, so across a sleep the guest clock
    advances while almost no instructions execute: a configuration
    spanning a sleep records wall-clock seconds it never spent
    computing.  Nothing in the output looks wrong.  The numbers are
    simply too large, and a Gate G3 result that is quietly too large is
    worse than none, because it would size N and the standard duration
    far too conservatively and no later measurement would obviously
    contradict it.

    The obvious guard is to compare the program's wall clock against
    the CPU time MVS charges the step, on the reasoning that CPU time
    accrues only while instructions execute.  THAT GUARD DOES NOT WORK
    HERE, and it was written and discarded rather than assumed.  The
    contaminated job reported `CPU 61MIN 21.92SEC` against 61 minutes
    32 seconds of elapsed guest time -- a ratio of 1.00 -- despite
    roughly 38 of those minutes being spent asleep.  MVS's accounting
    is derived from a timer Hercules drives from the host clock, so the
    guest's idea of CPU time and the guest's idea of wall time inflate
    together and their ratio says nothing.  Every clock inside the
    guest shares this defect.

    So the check has to come from outside the guest: the host CPU
    seconds charged to the Hercules PROCESS, against host elapsed wall
    clock.  A compute-bound guest keeps one emulated CPU busy, so
    Hercules should consume close to one core for the whole run.  If it
    consumed far less, the host was not executing it, whatever the
    guest believes.

    Still a floor, not a ceiling: it detects a host that stopped, not
    one that was merely slow.
    """
    if hcpu0 is None or hcpu1 is None:
        print("  COULD NOT READ THE HERCULES PROCESS CPU -- the one")
        print("  clock outside the guest is unavailable, so this run")
        print("  cannot be certified. Not a Gate G3 result.")
        return False
    used = hcpu1 - hcpu0
    frac = used / wall if wall > 0 else 0.0
    print("  Host CPU charged to Hercules: %.1f s over %.1f s elapsed"
          % (used, wall))
    print("  => %.0f%% of one core sustained" % (frac * 100.0))
    if frac < 0.70:
        print()
        print("  *** MEASUREMENT REJECTED ***")
        print("  Hercules only got %.0f%% of a core. The host stopped"
              % (frac * 100.0))
        print("  executing it for roughly %.0f%% of the run -- it slept,"
              % ((1.0 - frac) * 100.0))
        print("  or something else took the CPU. The guest's own clocks")
        print("  cannot see this: they are driven from the host clock,")
        print("  so they advance through a sleep. Re-run with the host")
        print("  kept awake, the lid open, and nothing else running.")
        return False
    print("  Certified: the host executed the guest throughout.")
    return True


def main(argv):
    prologue = mvsbld.cards_of("generated/onf2cnm.h")
    library = prologue + mvsbld.amalgamate(UNIT, INCLUDES)
    order = mvsbld.amalgamated_order(UNIT, INCLUDES)
    backend = mvsbld.with_defines("engine/src/onffp2.c",
                                  ["ONF_FP_SOFT2C"], prologue)

    def onfly(relpath):
        return mvsbld.with_defines(relpath, ["ONF_FP_SOFT2C"])

    sources = [
        (library, "SF2C", mvsbld.CC_FLAGS_VENDOR),
        (backend, "ONFFP2C"),
        (onfly("engine/src/onffpc.c"), "ONFFPCC"),
        (onfly("engine/src/onfrnd.c"), "ONFRNDC"),
        (onfly("engine/src/onfstm.c"), "ONFSTMC"),
        (onfly("engine/src/onfker.c"), "ONFKERC"),
        (onfly("tests/tstprf.c"), "TSTPRFC"),
    ]

    deck = mvsbld.build(JOB, "ONFLY GATE G3 PERF", sources, headers=HEADERS)
    mvsub.check_cards(deck)
    if "--print" in argv:
        sys.stdout.write("\n".join(deck) + "\n")
        return 0

    sys.stdout.write("mvsprf: amalgamated %s -> %d cards, inlining %s\n"
                     % (UNIT, len(library), ", ".join(order)))
    sys.stdout.write("mvsprf: %d cards, longest %d columns, GCCMVS %s\n"
                     % (len(deck), max(len(c) for c in deck), mvsbld.OPT))
    sys.stdout.write("mvsprf: the run alone is at least 100 s of guest "
                     "time, and much more if MVS is slow; TIME=1440 so "
                     "there is no step limit to hit\n")

    if keep_awake(True):
        sys.stdout.write("mvsprf: idle sleep suppressed for the run. "
                         "This does NOT cover closing the lid -- keep "
                         "it open, or the run is wasted.\n")
    else:
        sys.stdout.write("mvsprf: could not suppress idle sleep; the "
                         "host must be kept awake by other means.\n")
    try:
        hcpu0 = herc_cpu()
        t0 = time.time()
        before = mvsub.submit(deck)
        out = mvsub.collect(JOB, before, timeout=7200, poll=10)
        wall = time.time() - t0
        hcpu1 = herc_cpu()
    finally:
        keep_awake(False)
    if out is None:
        sys.stderr.write("mvsprf: %s did not finish in 7200 s\n" % JOB)
        return 1

    sys.stdout.write("=== step results ===\n")
    for line in mvsub.summarise(out):
        sys.stdout.write("  %s\n" % line[:116])

    sys.stdout.write("=== diagnostics ===\n")
    seen = {}
    for line in out.splitlines():
        s = line.strip()
        if (s.startswith("<stdin>") or "Internal compiler" in s
                or re.match(r"IFO\d{3}\b", s)):
            if s not in seen:
                seen[s] = 1
                sys.stdout.write("  %s\n" % s[:116])
    if not seen:
        sys.stdout.write("  none\n")

    gocpu = None
    for line in out.splitlines():
        m = GOCPU.search(line)
        if m:
            gocpu = float(m.group(1)) * 60.0 + float(m.group(2))

    rows = []
    for line in out.splitlines():
        m = PERF.match(line.rstrip().strip())
        if m:
            rows.append(tuple(int(g) for g in m.groups()))

    sys.stdout.write("=== program output ===\n")
    for line in out.splitlines():
        s = line.rstrip().strip()
        if RESULT.match(line.rstrip()):
            sys.stdout.write("  %s\n" % s[:116])

    if not rows:
        sys.stderr.write("mvsprf: no PERF lines in the listing\n")
        return 1

    report(rows, gocpu, wall, hcpu0, hcpu1)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
