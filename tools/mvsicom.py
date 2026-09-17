# -*- coding: utf-8 -*-
"""Bring TK5's transaction region up and down, and see what it did.

WHY A TOOL AND NOT A NOTE
-------------------------
Phase G's second component (D-424, plan P-30 approved by D-428) shows
ONFLY's transaction flow on a real 3270.  The monitor that drives that
3270 is the one D-131 chose, and it runs as a long-lived MVS job: it
starts, it holds the region, it answers an operator reply, and it shuts
down.  None of that fits `tools/mvsub.py`, whose whole contract is
"submit a deck and wait for the END banner" -- here the END banner is
the thing we are trying NOT to reach until the demonstration is over.

So this module drives the region's lifecycle instead: submit without
waiting, watch the system log for the messages that mean it is ready,
and shut it down by replying to its operator message.  VL-32 measured
every one of those messages on 2026-09-11; what was not measured, and
is the whole point of slice 1, is whether a 3270 can log on to it.

D-132 AND WHAT IS NOT IN THIS FILE
----------------------------------
The repository is MIT and the monitor's licence is non-commercial-only
including derivative works (VL-38), so D-132 keeps everything derived
from it out of the tree: the subsystem, its verb entry, its driver and
its JCL live under `local/` and on TK5.  This file holds none of that.
It names datasets and messages, which is description and not
derivation, and `tools/lint_lic.py` checks that the line has not been
crossed.

THE CONSOLE PATH, MEASURED
--------------------------
Hercules' HTTP console at :8038 takes a command and returns the log.
A command prefixed with `/` is passed to the guest as an MVS operator
command -- measured on 2026-09-17, `/d t` answered `IEE136I LOCAL:
TIME=...`.  That is how the region is shut down, because its shutdown
is an operator reply and nothing else can issue one on this host.

usage:  python tools/mvsicom.py --start [--timeout SEC]
        python tools/mvsicom.py --status
        python tools/mvsicom.py --stop
        python tools/mvsicom.py --log [--lines N]
"""
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import mvsub                                          # noqa: E402
import mvsbld                                         # noqa: E402

try:
    from urllib.request import urlopen
    from urllib.parse import quote
except ImportError:                                       # Python 2
    from urllib2 import urlopen                           # noqa: F401
    from urllib import quote                              # noqa: F401

# The job that runs the region.  Named so that it is unmistakably
# ONFLY's own submission and not the shipped one, which is a member of
# a dataset this repository does not own.
JOBNAME = "ONFICOM"
PROC = "ICOMEXEC"
REGION = "8192K"           # the 8M ceiling TBD-14 measured
JOBCLASS = "C"             # the class the shipped run job uses

# What the region says when it is up.  All four were measured at VL-32.
READY = "INTERCOMM IS READY"
STARTING = re.compile(r"INTMI007I")
VTAM_UP = re.compile(r"INTVT001I")
SUBTASKS = re.compile(r"INTTS001I")

# The reply that closes it down cleanly (VL-32).
SHUTDOWN = "NRCD"

# MVS asks for a reply with a two-digit identifier; `d r,r` lists the
# outstanding ones.  The region's is the one naming this job.
REPLY_RE = re.compile(r"^\s*(\d+)\s+(.*)$")


def console(command, lines=200):
    """Issue one Hercules console command; return the syslog text."""
    host, port = mvsub.console_addr()
    url = ("http://%s:%d/cgi-bin/tasks/syslog?command=%s&msgcount=%d"
           % (host, port, quote(command), lines))
    body = urlopen(url, timeout=30).read().decode("latin-1")
    return re.sub(r"<[^>]+>", "", body)


def mvs(command, lines=200, settle=4.0):
    """Issue one MVS operator command through Hercules' `/` prefix.

    THE TIMING, WHICH COST A ROUND OF DEBUGGING.  The console page
    returns the log as it stands when the request is served, which is
    before MVS has answered the command just issued.  Reading that
    reply means issuing, waiting, and reading AGAIN -- a caller that
    trusts the first body sees the PREVIOUS command's output and
    concludes the current one produced nothing.  Measured on
    2026-09-17 against `d r`.
    """
    console("/" + command, lines=lines)
    if settle:
        time.sleep(settle)
    return console("", lines=lines)


def log(lines=200):
    return console("", lines=lines)


def lu_owner(lu):
    """Which VTAM application currently holds a logical unit.

    Returns the name from `IST082I ... ALLOC TO= name`, or None.
    This is how a terminal's state is checked rather than inferred:
    TK5 gives 00C0 to TSO at startup and leaves 00C1..00C6 with the
    network solicitor, and after a session the unit stays with the
    application until the region ends.  A display changes nothing.
    """
    text = mvs("d net,id=%s,e" % lu, lines=40)
    found = None
    for m in re.finditer(r"ALLOC TO=\s*(\S+)", text):
        found = m.group(1)
    return found


def deck():
    """The region job.

    It EXECs the shipped procedure rather than restating it, so that
    nothing about the monitor's own JCL is copied into this repository
    (D-132).  Later slices add `//ICOM.xxx DD` overrides here for
    ONFLY's own datasets; the procedure reserves a place for them and
    needs no change.
    """
    return ["//%s  JOB (001),'ONFLY TX REGION',CLASS=%s,MSGCLASS=X,"
            % (JOBNAME, JOBCLASS),
            "//             USER=%s,PASSWORD=CUL8TR," % mvsbld.USER,
            "//             MSGLEVEL=(1,1)",
            "//*",
            "//ICOM     EXEC %s,IREGSIZ=%s" % (PROC, REGION)]


def running():
    """True if the region job is started and has not ended."""
    text = log(400)
    started = None
    for m in re.finditer(r"\$HASP373 %s\b" % JOBNAME, text):
        started = m.start()
    if started is None:
        return False
    ended = None
    for m in re.finditer(r"\$HASP395 %s\b" % JOBNAME, text):
        ended = m.start()
    return ended is None or ended < started


def reply_id(timeout=40):
    """The identifier of the region's outstanding operator message.

    Returns the digits as a string, or None.  `d r` is a display and
    changes nothing, so it is safe to poll.

    MVS 3.8j, NOT z/OS.  `D R,R` -- the spelling a modern reference
    gives -- is answered `IEE305I D COMMAND INVALID` here.  `D R`
    answers `IEE110I ... PENDING REQUEST` with a `SUMMARY: n REPLY ID`
    list.  Measured on 2026-09-17.

    The identifier is read from the region's OWN message rather than
    from that summary whenever it can be: the summary is just numbers,
    so with two outstanding requests it cannot say which is the
    region's, and replying to the wrong one would answer some other
    address space's question.  The summary is used only when exactly
    one request is outstanding, where it cannot be ambiguous.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        text = mvs("d r", lines=80)
        # The region re-issues its message with a fresh identifier
        # after every reply, prefixed `@nn`.
        found = None
        for m in re.finditer(r"@(\d+)\s+INTVT\d+R\s+%s\b" % JOBNAME, text):
            found = m.group(1)
        if found:
            return found
        m = re.search(r"SUMMARY:\s+1 REPLY ID\s*\n\s*/?\s*(\d+)", text)
        if m:
            return m.group(1)
        time.sleep(3)
    return None


def start(timeout=240, poll=3.0):
    """Submit the region and wait until it says it is ready.

    Returns True once the ready message appears.  Prints what it saw,
    because a region that comes up half way -- the monitor started but
    its terminal front end not -- is a real outcome and the log lines
    are the only evidence of which half failed.
    """
    if running():
        sys.stdout.write("mvsicom: %s is already running\n" % JOBNAME)
        return True
    cards = deck()
    sys.stdout.write("mvsicom: submitting %s (%s, REGION=%s)\n"
                     % (JOBNAME, PROC, REGION))
    # codepage=False: this deck carries no C source, so the '|' hazard
    # D-103 records cannot apply -- but the check is cheap and the lab
    # being on the wrong page is worth knowing about either way.
    mvsub.submit(cards)
    deadline = time.time() + timeout
    seen = {}
    while time.time() < deadline:
        text = log(400)
        tail = text[text.rfind("$HASP373 %s" % JOBNAME):] \
            if ("$HASP373 %s" % JOBNAME) in text else text
        for name, pat in (("starting", STARTING), ("vtam", VTAM_UP),
                          ("subtasks", SUBTASKS)):
            if name not in seen:
                m = pat.search(tail)
                if m:
                    line = tail[m.start():].splitlines()[0].strip()
                    seen[name] = line
                    sys.stdout.write("mvsicom: %s\n" % line[:100])
        if READY in tail:
            sys.stdout.write("mvsicom: %s\n" % READY)
            return True
        time.sleep(poll)
    sys.stdout.write("mvsicom: not ready within %d s; saw %d of 3 "
                     "startup messages\n" % (timeout, len(seen)))
    return False


def stop(timeout=120, poll=3.0):
    """Reply to the region's operator message so it closes cleanly."""
    if not running():
        sys.stdout.write("mvsicom: %s is not running\n" % JOBNAME)
        return True
    rid = reply_id()
    if rid is None:
        sys.stdout.write("mvsicom: no outstanding reply found for %s; "
                         "refusing to guess an identifier\n" % JOBNAME)
        return False
    sys.stdout.write("mvsicom: replying %s,%s\n" % (rid, SHUTDOWN))
    mvs("r %s,%s" % (rid, SHUTDOWN))
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not running():
            sys.stdout.write("mvsicom: %s ended\n" % JOBNAME)
            return True
        time.sleep(poll)
    sys.stdout.write("mvsicom: %s still running %d s after the reply\n"
                     % (JOBNAME, timeout))
    return False


def main(argv):
    action, lines, timeout = None, 40, 240
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("--start", "--stop", "--status", "--log"):
            action = a
        elif a == "--lines":
            i += 1
            lines = int(argv[i])
        elif a == "--timeout":
            i += 1
            timeout = int(argv[i])
        else:
            sys.stderr.write("mvsicom: unknown argument %s\n" % a)
            return 2
        i += 1
    if action is None:
        sys.stderr.write(__doc__.split("usage:")[-1])
        return 2
    if action == "--start":
        return 0 if start(timeout=timeout) else 1
    if action == "--stop":
        return 0 if stop() else 1
    if action == "--status":
        sys.stdout.write("mvsicom: %s is %s\n"
                         % (JOBNAME,
                            "RUNNING" if running() else "not running"))
        return 0
    for line in log(lines).splitlines():
        if line.strip():
            sys.stdout.write("%s\n" % line.rstrip()[:118])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
