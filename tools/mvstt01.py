# -*- coding: utf-8 -*-
"""Build, submit and read TT-01 on MVS 3.8j (Gate G1, D-90, D-94, D-95).

TT-01 is the 64-bit integer self-test.  Its whole purpose is to run on a
machine where 64-bit arithmetic does not exist in hardware and the compiler
must synthesise it -- assumption A-05, risk R-01 -- so running it on x86
proves almost nothing.  This is the job that runs it where it matters.

The deck is generated from the actual files in the repository.  Nothing is
transcribed, amalgamated or edited on the way in (D-94): each source becomes
its own PDS member, and `#include "onfint.h"` is resolved by the compiler
through a real include path.  If the MVS result differs from the x86 result,
the difference is the compiler's, which is the only way this test means
anything.

THIS JOB CANNOT SUCCEED TODAY, AND THAT IS THE FINDING
------------------------------------------------------
Gate G1 has not been passed.  How far this job gets depends on two pieces
of host configuration that the repository does not carry, so read a failure
here against both before suspecting the tooling:

  1. The Hercules codepage must be 819/1047 (D-101, VL-18).  On the
     `default` page the reader delivers `|` as EBCDIC 0x6A, GCCMVS rejects
     it, and every source using `|=` or `||` dies in COMP.  A lab restart
     returns Hercules to `default` and reintroduces this silently.
  2. The optimisation level must be -O1 (D-100, VL-17).  It is the only
     level of five that compiles a 64-bit addition at all.

With both in place, COMP1 and ASM1 pass RC 0 -- tests/tstint.c compiles and
assembles on MVS -- and COMP2 fails with an internal compiler error at 902,
on the closing brace of `onfirun`, the function whose switch holds every
64-bit operation at once.

It would fail even if it compiled.  Measured per operation at -O1 (VL-19):
multiply returns zero for a product that is not zero, and `a << 7` drops
bit 63, both silently.  That is what TT-01 exists to detect, arrived at by
probe instead because TT-01 itself will not build.

Which DD carries which include
------------------------------
GCCMVS uses two include DDs and they are the opposite way round from what
the names suggest:

    INCLUDE   the QUOTED includes -- ONFLY's own headers
    SYSINCL   the ANGLED includes -- PDPCLIB

With them the other way round GCCMVS reports `onfint.h: An error has
occurred` and cannot find it.  The two datasets are NOT concatenated and
must not be: PDPCLIB.INCLUDE is VB/255 and ONFLY's headers are FB/80, and
MVS refuses to concatenate unlike record formats -- the compile step abends
S001-1 before a line is read.  Keeping them on separate DDs sidesteps this
entirely, which is also why IEBUPDTE can still write the headers: it writes
card images and cannot write a VB dataset at all.

REGION is not optional
----------------------
Every job in JCC.CNTL and SYS2.JCLLIB(TESTGCC) carries REGION=8M.  Submitted
without one, JCC does not fail: it spins forever at 100% of a core and has
to be cancelled.  Two probe jobs were lost to this before the supplied JCL
was read.  The region is stated here, and stated loudly, because the failure
mode is a hang rather than a message.

Member names
------------
MVS members are eight characters, so the mapping is explicit rather than
derived: a rule that silently truncated would reintroduce exactly the class
of problem D-93 closed.

Run:  python tools/mvstt01.py [--print]
      --print writes the deck to stdout instead of submitting it.
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import mvsub  # noqa: E402

JOB = "ONFTT01"

# The GCCMVS optimisation level (D-100, VL-17).  -O1 is the only one of
# -O0, -O1, -O2, -O3 and -Os that compiles a 64-bit addition at all.
OPT = "-O1"
USER = "HERC01"
HDR_DSN = "%s.ONFLY.H" % USER
SRC_DSN = "%s.ONFLY.C" % USER

# repository file -> PDS member.  Stated, not derived (see the note above).
HEADERS = [
    ("engine/include/onfplat.h", "ONFPLAT"),
    ("softfloat/onfint.h", "ONFINT"),
    ("generated/onfivec.h", "ONFIVEC"),
]
SOURCES = [
    ("tests/tstint.c", "TSTINT"),
    ("softfloat/onfint.c", "ONFINTC"),
]


# The inline-data delimiter.
#
# A C source opens with `/*` in column 1, and `/*` in columns 1-2 is JES2's
# end-of-data delimiter.  With a plain `//SYSIN DD *`, the first card of
# onfplat.h therefore ends the data stream and IEBUPDTE reports
# "IEB823I SYSIN HAS NO RECORDS" -- it is handed nothing at all, and the
# compile then fails with 013-18, member not found, three steps later where
# the cause is no longer visible.
#
# `DD DATA,DLM=` fixes it: the stream then ends only at the named delimiter,
# and cards beginning with `/*` or `//` are passed through as data.  The
# delimiter is checked against every card below rather than assumed safe.
DLM = "ZZ"


def cards_of(relpath):
    """The file as card images, checked against the 80-column limit."""
    path = os.path.join(ROOT, relpath)
    text = io.open(path, encoding="ascii").read()
    out = []
    for n, line in enumerate(text.splitlines(), 1):
        line = line.rstrip()
        if len(line) > 80:
            raise SystemExit("mvstt01: %s:%d is %d columns; the reader would "
                             "discard the rest silently (D-93)"
                             % (relpath, n, len(line)))
        if line.startswith("./"):
            raise SystemExit("mvstt01: %s:%d starts with './', which IEBUPDTE "
                             "would read as a control card" % (relpath, n))
        if line.startswith(DLM):
            raise SystemExit("mvstt01: %s:%d starts with the delimiter %r, "
                             "which would end the data stream early"
                             % (relpath, n, DLM))
        out.append(line)
    return out


def build_deck(opt=OPT):
    """Build the TT-01 deck.  `opt` is an optimisation flag for GCCMVS.

    The default is -O1 (D-100).  D-97 established that the level is
    decisive and not incidental: on one twelve-line 64-bit addition,
    GCCMVS ICEs at -O0 ("unable to generate reloads", at 3590), ICEs
    differently at -O2, -O3 and -Os (at 447), and at -O1 compiles,
    assembles, links, runs and returns the right answer.  -O1 is the only
    level of five that works, so it is not a preference (VL-17).

    The flag stays a parameter rather than becoming a constant so that a
    measurement can always name the level it was taken at, and so that
    re-running VL-15's and VL-16's default-level results stays possible:
    pass --opt= with an empty value for no -O flag at all.
    """
    d = []

    def a(card):
        """Append one card, enforcing JCL's column-71 field limit.

        Two different limits apply to a deck and they are easy to confuse.
        The card reader truncates at column 80 (D-93), and mvsub refuses
        any card longer than that.  A JCL *statement* has a tighter rule:
        its fields must end by column 71, because column 72 is the
        continuation indicator.  A JCL card between 72 and 80 columns
        therefore passes every check D-93 put in place and is still
        wrong -- which is exactly how D-97's " -O1" produced
        "IEF629I INCORRECT USE OF APOSTROPHE IN THE PARM FIELD" and a job
        that did not run.  Data cards written into an inline stream are
        not JCL and keep the full 80 columns, so only lines beginning
        "//" are checked here.
        """
        if card.startswith("//") and len(card) > 71:
            raise ValueError(
                "JCL card exceeds column 71 (%d): %s" % (len(card), card))
        d.append(card)

    a("//%-8s JOB (001),'ONFLY TT-01',CLASS=A,MSGCLASS=A," % JOB)
    a("//             USER=%s,PASSWORD=CUL8TR," % USER)
    # REGION=8M matches every job in JCC.CNTL.  Without it JCC hangs rather
    # than failing, so this line is load-bearing.
    a("//             REGION=8M,TIME=1440,MSGLEVEL=(1,1)")
    a("//*")
    a("//* TT-01, the 64-bit integer self-test (NR-04, NR-14, A-05).")
    a("//* Gate G1 asks whether the compiler synthesises 64-bit integer")
    a("//* arithmetic correctly on S/370, where none of it exists in")
    a("//* hardware.  Risk R-01 is that it does not.")
    a("//*")
    a("//* Generated by tools/mvstt01.py from the repository sources.")
    a("//*")

    # --- delete anything left by an earlier run ---------------------------
    # The job must be re-runnable.  Without this the second submission fails
    # with IEF253I DUPLICATE NAME ON DIRECT ACCESS VOLUME and nothing runs at
    # all.  DISP=(MOD,DELETE) is the idiom: it deletes the dataset if it is
    # there, and creates then deletes it if it is not, so either way the next
    # step starts from nothing.
    a("//SCRATCH  EXEC PGM=IEFBR14")
    a("//D1       DD DSN=%s,DISP=(MOD,DELETE)," % HDR_DSN)
    a("//            UNIT=SYSDA,SPACE=(TRK,(1,1))")
    a("//D2       DD DSN=%s,DISP=(MOD,DELETE)," % SRC_DSN)
    a("//            UNIT=SYSDA,SPACE=(TRK,(1,1))")
    a("//*")

    # --- allocate the two libraries ---------------------------------------
    a("//ALLOC    EXEC PGM=IEFBR14")
    # FB/80, the same as the source library.  This dataset is NOT
    # concatenated with PDPCLIB.INCLUDE -- it cannot be, because that
    # library is VB/255 and MVS will not concatenate unlike record
    # formats (an FB/80 library there abends the compile S001-1).  It
    # does not need to be: INCLUDE and SYSINCL are separate DDs, so
    # the angled-bracket library and the quoted-include library are
    # simply pointed at different datasets.  IEBUPDTE writes card
    # images and cannot write a VB dataset at all, so FB/80 it is.
    a("//MKH      DD DSN=%s,DISP=(,CATLG,DELETE)," % HDR_DSN)
    a("//            UNIT=SYSDA,SPACE=(TRK,(30,10,20)),")
    a("//            DCB=(RECFM=FB,LRECL=80,BLKSIZE=3200)")
    a("//MKC      DD DSN=%s,DISP=(,CATLG,DELETE)," % SRC_DSN)
    a("//            UNIT=SYSDA,SPACE=(TRK,(30,10,20)),")
    a("//            DCB=(RECFM=FB,LRECL=80,BLKSIZE=3200)")
    a("//*")

    # --- write the headers ------------------------------------------------
    a("//WRITEH   EXEC PGM=IEBUPDTE,PARM=NEW")
    a("//SYSPRINT DD SYSOUT=*")
    a("//SYSUT2   DD DSN=%s,DISP=OLD" % HDR_DSN)
    a("//SYSIN    DD DATA,DLM='%s'" % DLM)
    for relpath, member in HEADERS:
        a("./ ADD NAME=%s" % member)
        d.extend(cards_of(relpath))
    a("./ ENDUP")
    a(DLM)
    a("//*")

    # --- write the sources ------------------------------------------------
    a("//WRITEC   EXEC PGM=IEBUPDTE,PARM=NEW")
    a("//SYSPRINT DD SYSOUT=*")
    a("//SYSUT2   DD DSN=%s,DISP=OLD" % SRC_DSN)
    a("//SYSIN    DD DATA,DLM='%s'" % DLM)
    for relpath, member in SOURCES:
        a("./ ADD NAME=%s" % member)
        d.extend(cards_of(relpath))
    a("./ ENDUP")
    a(DLM)
    a("//*")

    # --- compile and assemble each unit with GCCMVS ------------------------
    # GCCMVS is a real GCC: it compiles to assembler, IFOX00 assembles that,
    # and the linkage editor combines the object sets.  This is written out
    # rather than invoked through SYS2.PROCLIB(GCCCLG) because that procedure
    # builds exactly one translation unit, and TT-01 has two.  Every DD below
    # is taken from GCCCLG so the shape stays the one TK5 supports.
    #
    # -Wno-long-long is required, not cosmetic.  The procedures compile with
    # -ansi -pedantic-errors, under which `long long` is an ERROR, and NR-04
    # defines the dialect as "C89 plus long long".  This is the same single
    # relaxation the x86 build makes, for the same reason.
    #
    # ONFLY's headers are added to INCLUDE and SYSINCL, which is what GCCCLG's
    # own comment says to do: "INCLUDE SHOULD HAVE YOUR OWN HEADERS ADDED".
    # PDPCLIB's library comes first in each concatenation because it carries
    # the larger block size.
    for n, (_relpath, member) in enumerate(SOURCES, 1):
        a("//COMP%d    EXEC PGM=GCC," % n)
        # The continued parameter starts in column 5.  JCL allows columns 4
        # to 16, and the original layout used column 12 -- which fitted
        # until D-97 added " -O1" and pushed the closing apostrophe to
        # column 74.  A JCL field must end by column 71, so MVS read an
        # unterminated string and rejected the job with
        # "IEF629I INCORRECT USE OF APOSTROPHE IN THE PARM FIELD".  The
        # card was only 74 columns, well inside the 80-column reader
        # limit, so the col80 lint could not have caught it: 71 is a
        # different limit with a different cause.  jcl() below enforces it.
        a("//  PARM='-S -ansi -pedantic-errors -Wno-long-long"
          "%s -o dd:out -'" % (" " + opt if opt else ""))
        # SYSINCL carries the angled-bracket library and INCLUDE the
        # quoted one, which is the opposite of what the DD names
        # suggest; the other way round, GCCMVS reported
        # "onfint.h: An error has occurred" and could not find it.
        a("//SYSINCL  DD DSN=PDPCLIB.INCLUDE,DISP=SHR,"
          "DCB=BLKSIZE=32720")
        a("//INCLUDE  DD DSN=%s,DISP=SHR" % HDR_DSN)
        a("//SYSIN    DD DSN=%s(%s),DISP=SHR" % (SRC_DSN, member))
        a("//OUT      DD DSN=&&ASM%d,DISP=(,PASS),UNIT=SYSALLDA," % n)
        a("//            DCB=(LRECL=80,BLKSIZE=6160,RECFM=FB),")
        a("//            SPACE=(6160,(500,500))")
        a("//SYSPRINT DD SYSOUT=*")
        a("//SYSTERM  DD SYSOUT=*")
        a("//*")
        a("//ASM%d     EXEC PGM=IFOX00,PARM='DECK,NOLIST'," % n)
        a("//            COND=(4,LT,COMP%d)" % n)
        a("//SYSLIB   DD DSN=SYS1.MACLIB,DISP=SHR,DCB=BLKSIZE=32720")
        a("//         DD DSN=PDPCLIB.MACLIB,DISP=SHR")
        a("//SYSUT1   DD UNIT=SYSALLDA,SPACE=(CYL,(20,10))")
        a("//SYSUT2   DD UNIT=SYSALLDA,SPACE=(CYL,(10,10))")
        a("//SYSUT3   DD UNIT=SYSALLDA,SPACE=(CYL,(10,10))")
        a("//SYSPRINT DD SYSOUT=*")
        a("//SYSLIN   DD DUMMY")
        a("//SYSGO    DD DUMMY")
        a("//SYSPUNCH DD DSN=&&OBJ%d,UNIT=SYSALLDA," % n)
        a("//            SPACE=(80,(500,500)),DISP=(,PASS)")
        a("//SYSIN    DD DSN=&&ASM%d,DISP=(OLD,DELETE)" % n)
        a("//*")


    # --- link and run ------------------------------------------------------
    # NCAL is deliberately NOT specified: PDPCLIB.NCALIB is the C runtime and
    # the linkage editor must search it, which is how GCCCLG does it.  The
    # two object sets are concatenated on SYSLIN, which IEWL reads correctly
    # -- the thing JCC's prelink stage could not be made to do HERE.
    #
    # Read that narrowly.  On 2026-09-15 `tools/mvsjcc.py` put THIRTEEN
    # objects on one PRELINK `I` DD and the step ended COND CODE 0000,
    # so PRELINK plainly can read a concatenation.  Whatever defeated it
    # in this file was something else -- most likely the object shapes
    # involved here, which this note never recorded.  It is left standing
    # rather than deleted because it is a dated observation, and
    # corrected forward on the D-253 precedent.
    a("//LKED     EXEC PGM=IEWL,PARM='MAP,LIST',COND=(4,LT)")
    a("//SYSLIN   DD DSN=&&OBJ1,DISP=(OLD,DELETE)")
    a("//         DD DSN=&&OBJ2,DISP=(OLD,DELETE)")
    a("//SYSLIB   DD DSN=PDPCLIB.NCALIB,DISP=SHR")
    a("//SYSUT1   DD UNIT=SYSALLDA,SPACE=(CYL,(2,1))")
    a("//SYSPRINT DD SYSOUT=*")
    a("//SYSLMOD  DD DSN=&&GOSET(GO),UNIT=SYSALLDA,")
    a("//            SPACE=(1024,(50,20,1)),DISP=(,PASS)")
    a("//*")
    a("//GO       EXEC PGM=*.LKED.SYSLMOD,COND=(4,LT)")
    a("//SYSPRINT DD SYSOUT=*")
    a("//SYSTERM  DD SYSOUT=*")
    a("//SYSIN    DD DUMMY")
    a("//")
    return d


def main(argv):
    opt = OPT
    for arg in argv:
        if arg.startswith("--opt="):
            opt = arg[len("--opt="):]
    deck = build_deck(opt)
    mvsub.check_cards(deck)
    if "--print" in argv:
        sys.stdout.write("\n".join(deck) + "\n")
        return 0

    sys.stdout.write("mvstt01: %d cards, longest %d columns, GCCMVS %s\n"
                     % (len(deck), max(len(c) for c in deck),
                        opt if opt else "(no -O flag)"))
    before = mvsub.submit(deck)
    out = mvsub.collect(JOB, before, timeout=900, poll=5)
    if out is None:
        sys.stderr.write("mvstt01: %s did not finish in 900 s\n" % JOB)
        return 1

    sys.stdout.write("=== step results ===\n")
    for line in mvsub.summarise(out):
        sys.stdout.write("  %s\n" % line[:116])

    sys.stdout.write("=== TT-01 output ===\n")
    shown = 0
    for line in out.splitlines():
        s = line.rstrip()
        if s.startswith("SELF ") or s.startswith("IVEC ") \
                or s.startswith("# tstint") or s.startswith("# TT-01") \
                or s.startswith("# cross-check") \
                or s.startswith("# ONF901S"):
            sys.stdout.write("  %s\n" % s[:116])
            shown += 1
    if not shown:
        sys.stdout.write("  (no TT-01 output found in the job's printout)\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
