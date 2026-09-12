# -*- coding: utf-8 -*-
"""Send IR-TRN-02's all-byte-values test file to MVS and check it.

IR-TRN-02 asks each transport to be evaluated "using a test file
containing every byte value 0x00-0xFF **plus** a real network file".
VL-50 did the network half: ONFLYENG's verify-only mode reported
ONF003I on MVS.  This is the other half.

It needs a separate program because ONFLYENG knows only the ONFNET
format, and the test file is deliberately not that -- it is 1024 bytes
of four diagnostic sections followed by its own length and CRC, so
tests/tstxfr.c can check it without being told anything.

The mount machinery is imported from tools/mvseng.py rather than
copied: the staging to an ASCII path (VL-47) and the load-in-answer-to-
the-request timing (VL-48) were both expensive to find and there must
not be two versions of them to drift apart.

usage:
    python tools/mvsxfr.py [--print] [--repeat N]
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
import mvseng  # noqa: E402

JOB = "ONFXFR"

IMAGE = os.path.join(ROOT, "data", "transport", "tst256-sl.aws")

HEADERS = [
    ("engine/include/onfplat.h", "ONFPLAT"),
    ("engine/include/onfcrc.h", "ONFCRC"),
]

# The same SL form VL-50 proved for the network, with this file's own
# serial and dataset name.  DCB matches what tools/mkasl.py writes into
# HDR2; if they disagreed MVS would reject the volume, so both come
# from the same constants.
GO_DD = [
    "//ONFTST   DD DSN=ONFTST,DISP=(OLD,KEEP),UNIT=%s,"
    % mvseng.JCL_UNIT,
    "//            VOL=SER=ONFTST,LABEL=(1,SL),",
    "//            DCB=(RECFM=FB,LRECL=80,BLKSIZE=32720,DEN=3)",
]

RESULT = re.compile(r"^\s*(?:#\s|XFR\d{3}[IEWS]\b)")


# IR-TRN-02's second transport: the card reader, read as a DEVICE.
#
# My own expectation in D-146 was that this could not work, because
# binary carried through JES2 meets its scan for `//` and `/*`.  That
# reasoning does not apply here and is withdrawn: `$DU` reports JES2
# draining only 00C as READER1, so 10C is free, and a job that
# allocates it by UNIT= reads the device directly without JES2 ever
# seeing the bytes.
#
# A 2540 delivers fixed 80-byte card images, so RECFM=F with LRECL and
# BLKSIZE both 80 and no blocking.  No DSN and no DISP: a unit-record
# device is allocated by its address, not looked up.
READER_UNIT = "10C"
# Hercules names it with four digits; MVS with three (see mvseng).
READER_DEV = "010C"
READER_DD = [
    "//ONFTST   DD UNIT=%s," % READER_UNIT,
    "//            DCB=(RECFM=F,LRECL=80,BLKSIZE=80)",
]


def deck(go_dd=None):
    # No float backend is involved: this is a CRC and four byte
    # comparisons.  Nothing here needs the SoftFloat amalgamation, so
    # the deck is two units instead of eight and compiles in seconds.
    sources = [
        (mvsbld.cards_of("engine/src/onfcrc.c"), "ONFCRCC"),
        (mvsbld.cards_of("tests/tstxfr.c"), "TSTXFRC"),
    ]
    return mvsbld.build(JOB, "ONFLY G2 TRANSPORT TEST", sources,
                        headers=HEADERS,
                        go_dd=GO_DD if go_dd is None else go_dd)


def main(argv):
    try:
        sys.stdout.reconfigure(errors="replace")
    except (AttributeError, ValueError):
        pass

    via_reader = "--reader" in argv
    d = deck(READER_DD if via_reader else None)
    mvsub.check_cards(d)
    if "--print" in argv:
        sys.stdout.write("\n".join(d) + "\n")
        return 0

    if via_reader:
        return run_reader(d, argv)

    if not os.path.isfile(IMAGE):
        sys.stderr.write("mvsxfr: no image at %s -- build it with\n"
                         "        python tools/mkaws.py --testfile\n"
                         "        python tools/mkasl.py --wrap "
                         "data/transport/tst256.bin %s "
                         "--dsn ONFTST --serial ONFTST\n"
                         % (IMAGE, IMAGE))
        return 2

    sys.stdout.write("mvsxfr: %d cards, longest %d columns\n"
                     % (len(d), max(len(c) for c in d)))

    repeat = 1
    for i, a in enumerate(argv):
        if a == "--repeat" and i + 1 < len(argv):
            repeat = int(argv[i + 1])

    # mvseng's watcher keys on the volume name in IEF233A, so it has to
    # be told which one to wait for.
    want_vol = "ONFTST"
    passes = []
    out = None
    for n in range(repeat):
        if repeat > 1:
            sys.stdout.write("--- transfer %d of %d ---\n"
                             % (n + 1, repeat))
        t0 = time.time()
        before = mvsub.submit(d)
        mount_answer(IMAGE, want_vol)
        out = mvsub.collect(JOB, before, timeout=1800, poll=5)
        took = time.time() - t0
        ok = out is not None and "XFR000I" in out
        passes.append((ok, took))
        if repeat > 1:
            sys.stdout.write("    %s in %.1f s\n"
                             % ("OK" if ok else "FAILED", took))

    if out is None:
        sys.stderr.write("mvsxfr: %s did not finish\n" % JOB)
        return 1

    sys.stdout.write("=== step results ===\n")
    for line in mvsub.summarise(out):
        sys.stdout.write("  %s\n" % line[:116])

    sys.stdout.write("=== tstxfr output ===\n")
    lines = [l.rstrip().strip() for l in out.splitlines()
             if RESULT.match(l.rstrip())]
    for line in lines[:20]:
        sys.stdout.write("  %s\n" % line[:116])
    if not lines:
        sys.stdout.write("  (nothing) -- see the step results above\n")
        return 1

    if repeat > 1:
        good = sum(1 for ok, _ in passes if ok)
        times = [t for _, t in passes]
        sys.stdout.write("\n=== IR-TRN-02 test file: %d of %d "
                         "transfers OK ===\n" % (good, repeat))
        sys.stdout.write("    elapsed per transfer: min %.1f s, "
                         "max %.1f s, mean %.1f s\n"
                         % (min(times), max(times),
                            sum(times) / len(times)))
    return 0 if "XFR000I" in out else 1


CARDS = os.path.join(ROOT, "data", "transport", "tst256-cards.bin")


def load_reader(path):
    """Point 010C at a binary file, with no translation of any kind.

    The device options are the whole experiment.  TK5 defines both
    readers `ascii trunc`: `ascii` translates the file from ASCII to
    EBCDIC on the way in, and `trunc` drops trailing blanks -- which
    are respectively the code-page translation and the trailing-blank
    truncation IR-TRN-01 forbids by name.  Omitting both is what "raw
    mode" means in A-07, and whether the bytes then survive is exactly
    what this measures.

    `eof` makes the reader signal end of file rather than waiting for
    more cards, so the job ends instead of hanging.
    """
    body = mvseng.console("devinit %s %s eof"
                          % (READER_DEV, path.replace("\\", "/")))
    ok = "HHC00205E" not in body
    sys.stdout.write("mvsxfr: reader %s <- %s%s\n"
                     % (READER_DEV, path,
                        "" if ok else "  (FAILED to open)"))
    return ok


def run_reader(d, argv):
    """Evaluate the card reader as IR-TRN-02's second transport."""
    if not os.path.isfile(CARDS):
        sys.stderr.write("mvsxfr: no card file at %s -- build it with "
                         "--makecards\n" % CARDS)
        return 2
    # Release before staging: Hercules keeps the card file open while
    # it is loaded and Windows will not overwrite an open file, so a
    # second invocation would fail inside stage() with a permission
    # error that reads as a filesystem problem and is really a device
    # still holding its hopper.
    mvseng.console("devinit %s *" % READER_DEV)
    staged = mvseng.stage(CARDS)

    repeat = 1
    for i, a in enumerate(argv):
        if a == "--repeat" and i + 1 < len(argv):
            repeat = int(argv[i + 1])

    passes = []
    out = None
    took = 0.0
    for n in range(repeat):
        if repeat > 1:
            sys.stdout.write("--- transfer %d of %d ---\n"
                             % (n + 1, repeat))
        # Reloaded before every pass, not once.  A reader is consumed:
        # after a job has read to end of file the deck is spent, and a
        # second job would find an empty hopper.  devinit reloads it,
        # which is the card-reader equivalent of rewinding a tape.
        if not load_reader(staged):
            return 2
        t0 = time.time()
        before = mvsub.submit(d)
        out = mvsub.collect(JOB, before, timeout=900, poll=5)
        took = time.time() - t0
        ok = out is not None and "XFR000I" in out
        passes.append((ok, took))
        if repeat > 1:
            sys.stdout.write("    %s in %.1f s\n"
                             % ("OK" if ok else "FAILED", took))

    if out is None:
        sys.stderr.write("mvsxfr: %s did not finish\n" % JOB)
        return 1

    if repeat > 1:
        good = sum(1 for ok, _ in passes if ok)
        times = [t for _, t in passes]
        sys.stdout.write("\n=== IR-TRN-02 card reader: %d of %d "
                         "transfers OK ===\n" % (good, repeat))
        sys.stdout.write("    elapsed per transfer: min %.1f s, "
                         "max %.1f s, mean %.1f s\n"
                         % (min(times), max(times),
                            sum(times) / len(times)))
    sys.stdout.write("mvsxfr: reader round trip %.1f s\n" % took)
    sys.stdout.write("=== step results ===\n")
    for line in mvsub.summarise(out):
        sys.stdout.write("  %s\n" % line[:116])
    sys.stdout.write("=== tstxfr output ===\n")
    lines = [l.rstrip().strip() for l in out.splitlines()
             if RESULT.match(l.rstrip())]
    for line in lines[:20]:
        sys.stdout.write("  %s\n" % line[:116])
    if not lines:
        sys.stdout.write("  (nothing) -- see the step results above\n")
    return 0 if "XFR000I" in out else 1


def mount_answer(image, volume, timeout=300):
    """Load `image` when MVS asks for `volume`.

    A thin wrapper on mvseng's logic with the volume name made a
    parameter.  Everything it protects against -- the non-ASCII path,
    mounting before the request, matching a stale request from an
    earlier job -- was paid for in VL-47 and VL-48.
    """
    path = mvseng.stage(image)
    want = "IEF233A M %s,%s" % (mvseng.JCL_UNIT, volume)
    stale = set(l for l in mvseng.console("devlist TAPE").splitlines()
                if want in l)
    deadline = time.time() + timeout
    while time.time() < deadline:
        fresh = [l for l in mvseng.console("devlist TAPE").splitlines()
                 if want in l and l not in stale]
        if fresh:
            body = mvseng.console("devinit %s %s"
                                  % (mvseng.TAPE_DEV, path))
            ok = "format type" in body and "HHC00205E" not in body
            sys.stdout.write("mvsxfr: answered; %s %s\n"
                             % ("loaded" if ok else "FAILED to load",
                                path))
            return ok
        time.sleep(3)
    sys.stdout.write("mvsxfr: no mount request within %d s\n" % timeout)
    return False


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
