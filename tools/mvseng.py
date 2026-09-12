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
parallel session shares, and `devinit 0480 *` puts it back.

The image is written by tools/mkaws.py to IR-NET-08's shape: RECFM=FB,
LRECL=80, blocks of 32720 which is 409 whole records, payload
zero-padded to a record boundary.

THE MOUNT, WHICH IS NOT YET SOLVED (VL-47)
------------------------------------------
Two things here were paid for and are worth not rediscovering.

The image is STAGED to the lab's tape directory first.  Hercules
cannot open a path containing non-ASCII characters -- this repository
lives under one -- and it says so with an HHC00205E buried between a
success message and "device initialized", leaving the drive empty.
See stage().

The tape is loaded in ANSWER to the mount request, never before.  The
syslog shows `HHC00201I ... tape closed` between the job starting and
IEF233A: MVS unloads the drive during allocation, so a pre-mounted
volume is gone by the time it is wanted.

With both fixed, MVS advances to the OPEN-time mount, `IEC501A M
480,ONFNET,NL,6250 BPI`, and then REFUSES the volume -- `IEC502E K`,
dismount and keep -- and asks again.  Why it refuses is not known.
Density, the block size against the 3420's characteristics, and what
MVS reads in the first block of an unlabelled tape are all untested.
No transfer has yet been performed.

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
    # D-142: the 32-bit self-test, because NR-03 puts SoftFloat 2c here
    # and NR-14 as amended asks for the width the engine actually uses.
    # onfivec.h and onfint.h are the 64-bit suite's and are deliberately
    # absent -- VL-45 measured GCCMVS unable to compile that suite.
    ("softfloat/onfi32.h", "ONFI32"),
    ("generated/onf32v.h", "ONF32V"),
    ("softfloat/c2c/milieu.h", "MILIEU"),
    ("softfloat/c2c/softfloat.h", "SOFTFLOA"),
    ("softfloat/c2c/onfproc.h", "ONFPROC"),
]

# The GO step's network DD.  LABEL=(1,NL) is an unlabelled tape, which
# is what mkaws.py writes -- no VOL1/HDR1 records, just data blocks and
# a tape mark.  The DCB must be stated here because an NL tape carries
# no label for MVS to read it from.
GO_DD = [
    "//ONFNET   DD DSN=ONFNET,DISP=(OLD,KEEP),UNIT=%s," % JCL_UNIT,
    "//            VOL=SER=ONFNET,LABEL=(1,NL),",
    "//            DCB=(RECFM=FB,LRECL=80,BLKSIZE=32720)",
]

# DSN is not optional, and leaving it out is what a first attempt does.
# A DD with DISP=OLD and no DSN names an unnamed TEMPORARY dataset,
# which cannot be OLD because it cannot already exist, so MVS rejects
# the step before allocating anything -- "IEF453I JOB FAILED - JCL
# ERROR", with no message naming the DD and no ALLOC line to show how
# far it got.  The device was never the problem: D U,,,480,4 reports
# 480 as an online 3400 throughout.
#
# VOL=SER is not optional either, and omitting it was the SECOND
# attempt's error.  The reasoning that produced it was that an
# unlabelled tape has no label to match a serial against, so naming one
# only invites a mount request.  True, and beside the point: DSN with
# DISP=OLD and no volume sends MVS to the catalog to find out where the
# dataset lives, and nothing called ONFNET is catalogued.  A dataset
# that is not catalogued must carry its own volume.  The failure looks
# identical to the first -- IEF453I, no annotation against the card, no
# ALLOC line -- which is why each attempt here is recorded rather than
# quietly replaced.

# ONFLYENG's own output, and the messages Appendix E defines.  Anything
# else in the listing belongs to JES2 or the compiler.
RESULT = re.compile(r"^\s*(?:#\s|ONF\d{3}[IEWS]\b|MANIFEST\b|ONFLYENG\b)")


def console(command, lines=60):
    """Send one command to the Hercules console and return the log.

    `lines` matters more than it looks.  The page returns only the last
    22 messages by default, and a compile produces far more than that,
    so a watcher polling for one message can miss it entirely between
    polls -- which is how the mount request went unnoticed while the
    job sat waiting for it.
    """
    try:
        from urllib.request import urlopen
        from urllib.parse import quote
    except ImportError:                                   # Python 2
        from urllib2 import urlopen                       # noqa: F401
        from urllib import quote                          # noqa: F401
    host, port = mvsub.console_addr()
    url = ("http://%s:%d/cgi-bin/tasks/syslog?command=%s&msgcount=%d"
           % (host, port, quote(command), lines))
    return urlopen(url, timeout=30).read().decode("latin-1")


def stage(image):
    """Copy the image somewhere Hercules can actually open it.

    THE ROOT CAUSE OF EVERY EARLIER MOUNT FAILURE.  This repository
    lives under a path containing a u-umlaut, and `devinit` given that
    path answers

        HHC00221I 0:0480 Tape file <path>, type AWS
        HHC00205E 0:0480 Tape file <path>, type aws
        HHC02245I 0:0480 device initialized

    -- an error in the middle, "device initialized" after it, and the
    drive left EMPTY.  MVS then asked for the volume forever, which
    looked like an unlabelled-tape mount handshake problem and was
    nothing of the kind.  The lab's own tape directory is plain ASCII
    and short, which also matters: the console is driven over HTTP and
    a long path came back as 400 Bad Request.
    """
    lab = os.path.join(mvsub.tk5_dir(), "tape")
    if not os.path.isdir(lab):
        os.makedirs(lab)
    dst = os.path.join(lab, os.path.basename(image))
    with open(image, "rb") as src:
        data = src.read()
    with open(dst, "wb") as out:
        out.write(data)
    return dst.replace("\\", "/")


def mount(image):
    """Mount the AWS image, and VERIFY it, which is a separate thing.

    The first version of this checked whether the image's basename
    appeared in the console output and reported success when it did.
    The console echoes the command it was given, so that check passed
    on every failed mount as well -- it reported "mounted onfnet.aws"
    while the drive stayed empty and HHC00205E sat two lines above.  A
    verification that cannot fail is worse than none, because it is
    believed.

    So success is now the presence of HHC00221I's "format type" and the
    ABSENCE of HHC00205E, both taken from the reply to the devinit
    itself rather than from a later query.
    """
    if not os.path.isfile(image):
        sys.stderr.write("mvseng: no image at %s -- build it with\n"
                         "        python tools/mkaws.py --wrap "
                         "data/networks/<net>.bin %s\n" % (image, image))
        return False
    path = stage(image)
    body = console("devinit %s %s" % (TAPE_DEV, path))
    failed = "HHC00205E" in body
    loaded = "format type" in body
    ok = loaded and not failed
    sys.stdout.write("mvseng: %s %s on %s\n"
                     % ("mounted" if ok else "FAILED to mount",
                        path, TAPE_DEV))
    if failed:
        sys.stdout.write("mvseng: HHC00205E -- Hercules could not open "
                         "the file; check the path for non-ASCII\n")
    return ok


def unmount():
    console("devinit %s *" % TAPE_DEV)
    sys.stdout.write("mvseng: %s returned to an empty drive\n" % TAPE_DEV)


def mount_when_asked(image, timeout=300):
    """Mount only after MVS asks, which is what an operator does.

    VL-46 recorded three JCL forms failing before the fourth reached
    allocation, and then the job sat on

        *IEF233A M 480,ONFNET,,ONFENG,GO

    with the tape ALREADY mounted and the drive reported ready.  That
    is the clue: mounting before submitting means the device never
    makes a not-ready-to-ready TRANSITION while MVS is watching for
    one, and an unlabelled tape gives MVS no label to verify instead.
    Re-issuing devinit mid-allocation only moved it to INTERVENTION
    REQUIRED.

    So the drive starts empty and is loaded in response to the message,
    which is the sequence a human operator performs and the one MVS is
    written to expect.  Returns True if the request was seen and
    answered.
    """
    console("devinit %s *" % TAPE_DEV)
    sys.stdout.write("mvseng: %s left empty; waiting for MVS to ask\n"
                     % TAPE_DEV)
    want = "IEF233A M %s,ONFNET" % JCL_UNIT
    deadline = time.time() + timeout
    while time.time() < deadline:
        body = console("devlist TAPE")
        if want in body:
            console("devinit %s %s"
                    % (TAPE_DEV, os.path.abspath(image).replace("\\", "/")))
            sys.stdout.write("mvseng: %s seen; mounted %s in reply\n"
                             % (want, os.path.basename(image)))
            return True
        time.sleep(4)
    sys.stdout.write("mvseng: no mount request within %d s\n" % timeout)
    return False


def deck(opt=mvsbld.OPT):
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
        # D-142: the 32-bit suite.  Plain cards, no backend define --
        # the self-test is integer-only by construction, which is the
        # property NR-14 exists to check, so the float backend is
        # nothing to it.  The 64-bit onfint.c is NOT built here: VL-45
        # measured GCCMVS failing to compile it at -O0, -O1, -O2 and
        # with no flag, and NR-14 as D-118 amended it never asked for
        # it on a 2c platform anyway.
        (mvsbld.cards_of("softfloat/onfi32.c"), "ONFI32C"),
        (onfly("engine/src/onflyeng.c"), "ONFLYENG"),
    ]
    return mvsbld.build(JOB, "ONFLY G2 TAPE VERIFY", sources,
                        headers=HEADERS, go_parm="VERIFY", go_dd=GO_DD,
                        opt=opt)


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

    opt = mvsbld.OPT
    for i, a in enumerate(argv):
        if a.startswith("--opt="):
            opt = a[len("--opt="):]
    d = deck(opt)
    mvsub.check_cards(d)
    if "--print" in argv:
        sys.stdout.write("\n".join(d) + "\n")
        return 0

    sys.stdout.write("mvseng: %d cards, longest %d columns, GCCMVS %s\n"
                     % (len(d), max(len(c) for c in d),
                        opt if opt else "(none)"))

    if "--mount" in argv:
        return 0 if mount(image) else 2

    # The tape is loaded in ANSWER to the mount request, never before.
    # MVS unloads the drive during allocation -- the syslog shows
    # "HHC00201I ... tape closed" between the job starting and
    # IEF233A -- so a pre-mounted volume is gone by the time it is
    # wanted, which is what left four earlier jobs waiting forever.
    if not os.path.isfile(image):
        sys.stderr.write("mvseng: no image at %s\n" % image)
        return 2
    console("devinit %s *" % TAPE_DEV)

    t0 = time.time()
    before = mvsub.submit(d)
    if not mount_when_asked(image):
        sys.stderr.write("mvseng: the tape was never loaded\n")
    out = mvsub.collect(JOB, before, timeout=1800, poll=5)
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
