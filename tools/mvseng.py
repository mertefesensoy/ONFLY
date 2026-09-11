# -*- coding: utf-8 -*-
"""Run ONFLYENG on MVS 3.8j, reading the network from tape (Gate G2).

D-141 opens Gate G2 on the AWS tape image and checks integrity with
ONFLYENG's verify-only mode.  Two firsts happen in the same job, and
that is worth stating plainly because it affects how a failure is
read:

  * the first time a network file reaches MVS at all, by any transport
  * the first time ONFLYENG itself runs on MVS

D-141 records the attribution risk.  What makes it tractable is that
FR-LOD-02 fixes the ORDER of the checks -- magic constant, byte-order
sentinel, format version, header CRC-32, declared payload length,
payload CRC-32 -- and ONFLYENG reports the first one that fails.  So
the failure is self-attributing:

  nothing runs, or ONF901S        the port, not the transport
  ONF101E, wrong magic            the bytes were mangled in transit
  ONF103E, sentinel               a code-page translation happened
  ONF107E/ONF108E, a CRC          the bytes changed somewhere
  ONF003I, verified               both the port and the transport work

THE TAPE
--------
`0:0480 3420 *` is an empty drive nothing else uses, so mounting an
image there is the least disruptive change available to a lab the
parallel session shares, and `devinit 0480 *` puts it back.  Mounting
also rewinds, which is how a repeated transfer starts from the load
point rather than from wherever the last read left the tape.

The image is written by tools/mkaws.py to IR-NET-08's shape: RECFM=FB,
LRECL=80, blocks of 32720 which is 409 whole records, payload
zero-padded to a record boundary.

usage:
    python tools/mvseng.py [--print] [--mount] [--unmount]
                           [--image PATH]
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

JOB = "ONFENG"

# Hercules names the device 0:0480 and its console takes the four-digit
# form; MVS 3.8j UCB addresses are three digits, so the JCL says 480.
# They are not interchangeable -- UNIT=0480 in JCL is not the tape.
TAPE_DEV = "0480"
JCL_UNIT = "480"
DEFAULT_IMAGE = os.path.join(ROOT, "data", "transport", "onfnet.aws")

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
    ("engine/include/onfdec.h", "ONFDEC"),
    ("engine/include/onfcrc.h", "ONFCRC"),
    ("engine/include/onffpr.h", "ONFFPR"),
    ("generated/onfnhd.h", "ONFNHD"),
    ("generated/onfivec.h", "ONFIVEC"),
    ("softfloat/onfint.h", "ONFINT"),
    ("softfloat/c2c/milieu.h", "MILIEU"),
    ("softfloat/c2c/softfloat.h", "SOFTFLOA"),
    ("softfloat/c2c/onfproc.h", "ONFPROC"),
]

# The GO step's network DD.  LABEL=(1,NL) is an unlabelled tape, which
# is what mkaws.py writes -- no VOL1/HDR1 records, just data blocks and
# a tape mark.  The DCB must be stated here because an NL tape carries
# no label for MVS to read it from.
GO_DD = [
    "//ONFNET   DD UNIT=%s,DISP=OLD,LABEL=(1,NL)," % JCL_UNIT,
    "//            DCB=(RECFM=FB,LRECL=80,BLKSIZE=32720)",
]

# ONFLYENG's own output, and the messages Appendix E defines.  Anything
# else in the listing belongs to JES2 or the compiler.
RESULT = re.compile(r"^\s*(?:#\s|ONF\d{3}[IEWS]\b|MANIFEST\b|ONFLYENG\b)")


def console(command):
    """Send one command to the Hercules console and return the log."""
    try:
        from urllib.request import urlopen
        from urllib.parse import quote
    except ImportError:                                   # Python 2
        from urllib2 import urlopen                       # noqa: F401
        from urllib import quote                          # noqa: F401
    host, port = mvsub.console_addr()
    url = ("http://%s:%d/cgi-bin/tasks/syslog?command=%s"
           % (host, port, quote(command)))
    return urlopen(url, timeout=20).read().decode("latin-1")


def mount(image):
    """Mount the AWS image, which also rewinds to the load point.

    Reversible by design: `devinit 0480 *` restores the empty drive,
    and nothing else in the lab uses this address.
    """
    if not os.path.isfile(image):
        sys.stderr.write("mvseng: no image at %s -- build it with\n"
                         "        python tools/mkaws.py --wrap "
                         "data/networks/<net>.bin %s\n" % (image, image))
        return False
    console("devinit %s %s" % (TAPE_DEV, image.replace("\\", "/")))
    body = console("devlist TAPE")
    ok = os.path.basename(image) in body
    sys.stdout.write("mvseng: %s %s on %s\n"
                     % ("mounted" if ok else "FAILED to mount",
                        os.path.basename(image), TAPE_DEV))
    return ok


def unmount():
    console("devinit %s *" % TAPE_DEV)
    sys.stdout.write("mvseng: %s returned to an empty drive\n" % TAPE_DEV)


def deck():
    prologue = mvsbld.cards_of("generated/onf2cnm.h")
    library = prologue + mvsbld.amalgamate(UNIT, INCLUDES)
    backend = mvsbld.with_defines("engine/src/onffp2.c",
                                  ["ONF_FP_SOFT2C"], prologue)

    def onfly(relpath):
        return mvsbld.with_defines(relpath, ["ONF_FP_SOFT2C"])

    # Mirrors the x86 `eng` target's SOFT link, with onffp2 in place of
    # onffps.  The kernel, the RNG and the stimulus are deliberately
    # absent: verify-only never simulates, so linking them would add
    # two job steps each to prove nothing.
    sources = [
        (library, "SF2C", mvsbld.CC_FLAGS_VENDOR),
        (backend, "ONFFP2C"),
        (onfly("engine/src/onffpc.c"), "ONFFPCC"),
        (onfly("engine/src/onffpr.c"), "ONFFPRC"),
        (onfly("engine/src/onfcrc.c"), "ONFCRCC"),
        (onfly("engine/src/onfdec.c"), "ONFDECC"),
        (onfly("softfloat/onfint.c"), "ONFINTC"),
        (onfly("engine/src/onflyeng.c"), "ONFLYENG"),
    ]
    return mvsbld.build(JOB, "ONFLY G2 TAPE VERIFY", sources,
                        headers=HEADERS, go_parm="VERIFY", go_dd=GO_DD)


def main(argv):
    try:
        sys.stdout.reconfigure(errors="replace")
    except (AttributeError, ValueError):
        pass

    image = DEFAULT_IMAGE
    for i, a in enumerate(argv):
        if a == "--image" and i + 1 < len(argv):
            image = argv[i + 1]

    if "--unmount" in argv:
        unmount()
        return 0

    d = deck()
    mvsub.check_cards(d)
    if "--print" in argv:
        sys.stdout.write("\n".join(d) + "\n")
        return 0

    sys.stdout.write("mvseng: %d cards, longest %d columns, GCCMVS %s\n"
                     % (len(d), max(len(c) for c in d), mvsbld.OPT))

    if not mount(image):
        return 2
    if "--mount" in argv:
        return 0

    t0 = time.time()
    before = mvsub.submit(d)
    out = mvsub.collect(JOB, before, timeout=3600, poll=5)
    wall = time.time() - t0
    if out is None:
        sys.stderr.write("mvseng: %s did not finish in 3600 s\n" % JOB)
        return 1

    sys.stdout.write("mvseng: round trip %.1f s\n" % wall)
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

    sys.stdout.write("=== ONFLYENG output ===\n")
    lines = [l.rstrip().strip() for l in out.splitlines()
             if RESULT.match(l.rstrip())]
    for line in lines[:40]:
        sys.stdout.write("  %s\n" % line[:116])
    if not lines:
        sys.stdout.write("  (nothing) -- the program printed no manifest, "
                         "so read the step results above\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
