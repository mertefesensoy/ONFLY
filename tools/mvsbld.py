# -*- coding: utf-8 -*-
"""Build a GCCMVS compile-assemble-link-go deck from repository sources.

`tools/mvstt01.py` grew one of these inline for TT-01.  D-104 needs a
second, with an extra include library, so the deck shape is factored out
here rather than copied -- two copies of this much MVS-specific knowledge
would drift, and every line of it was paid for by a failure.

WHAT THE SHAPE COSTS, AND WHY IT IS THIS SHAPE
----------------------------------------------
Each item below was found by being bitten, not by reading a manual.

`DD DATA,DLM=` rather than `DD *`.  A C source opens with `/*` in column
1, which is JES2's end-of-data delimiter, so a plain `DD *` stream is
terminated by the first card of the first comment block and IEBUPDTE
reports "IEB823I SYSIN HAS NO RECORDS".  The compile then fails three
steps later with 013-18, member not found, where the cause is invisible.

REGION=8M.  Without a region GCCMVS does not fail, it spins at 100% of a
core until cancelled.  Every job in JCC.CNTL carries one.

JCL fields end by column 71.  Column 72 is the continuation indicator, so
a JCL card of 72 to 80 columns passes the reader's own 80-column limit and
is still rejected -- "IEF629I INCORRECT USE OF APOSTROPHE IN THE PARM
FIELD" is what that looks like when the card is a PARM.  jcl_card()
enforces it.  Data cards are not JCL and keep all 80.

INCLUDE carries QUOTED includes and SYSINCL carries ANGLED ones, which is
the opposite of what the names suggest.  The other way round GCCMVS
reports "onfint.h: An error has occurred" and cannot find it.

Two include libraries, not one concatenation.  PDPCLIB.INCLUDE is VB/255
and an IEBUPDTE-written dataset is FB/80; MVS will not concatenate unlike
record formats and the compile abends S001-1 before a line is read.  So
ONFLY's own headers live in an FB/80 library on INCLUDE, and anything that
must be found by an ANGLE-bracket include -- the NR-04 stdint.h and
stdbool.h shims, because PDPCLIB has neither -- lives in a VB/255 library
concatenated after PDPCLIB.INCLUDE on SYSINCL.  IEBUPDTE cannot write VB
at all, so those members go in through IEBGENER, one step each.  PDPCLIB
is first in the concatenation because it has the larger block size, which
MVS requires.

-O1.  The only optimisation level of five that compiles a 64-bit addition
(D-100, VL-17).
"""
import io
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

USER = "HERC01"
OPT = "-O1"
DLM = "ZZ"
CARD = 80
JCL_FIELD = 71

HDR_DSN = "%s.ONFLY.H" % USER      # FB/80, quoted includes
VBH_DSN = "%s.ONFLY.VBH" % USER    # VB/255, angle-bracket includes
SRC_DSN = "%s.ONFLY.C" % USER      # FB/80, translation units


class DeckError(Exception):
    pass


def cards_of(relpath):
    """A repository file as card images, checked against 80 columns."""
    path = os.path.join(ROOT, relpath)
    text = io.open(path, encoding="ascii").read()
    out = []
    for n, line in enumerate(text.splitlines(), 1):
        line = line.rstrip()
        if len(line) > CARD:
            raise DeckError(
                "%s:%d is %d columns; the reader would discard the rest "
                "without saying so (D-93)" % (relpath, n, len(line)))
        if DLM == line[:len(DLM)] and line.strip() == DLM:
            raise DeckError(
                "%s:%d is exactly the inline delimiter %r and would end "
                "the data stream" % (relpath, n, DLM))
        out.append(line)
    return out


def build(job, title, sources, headers=(), vb_headers=(), opt=OPT,
          asm_parm="DECK,NOLIST"):
    """Return a deck that compiles `sources`, links them and runs the result.

    sources     [(repo path, 8-char member)]  translation units, in link order
    headers     [(repo path, 8-char member)]  found by  #include "x.h"
    vb_headers  [(repo path, 8-char member)]  found by  #include <x.h>
    opt         GCCMVS optimisation flag
    asm_parm    Assembler XF PARM.  The default suppresses the listing;
                pass "DECK" to get it, which is the only way to see WHICH
                statement IFOX00 rejected when it returns RC 8 -- the
                condition code alone says nothing.

    Member names are stated by the caller, never derived: a rule that
    silently truncated to eight characters would reintroduce exactly the
    class of problem D-93 closed, and SoftFloat's own header names collide
    in their first eight characters (softfloat.h and softfloat_types.h both
    give SOFTFLOA), so no derived rule could work anyway.
    """
    d = []

    def a(card):
        if card.startswith("//") and len(card) > JCL_FIELD:
            raise DeckError("JCL card exceeds column %d (%d): %s"
                            % (JCL_FIELD, len(card), card))
        d.append(card)

    seen = {}
    for _p, m in list(sources) + list(headers) + list(vb_headers):
        if len(m) > 8:
            raise DeckError("member name %r is over 8 characters" % m)
        if m in seen:
            raise DeckError("member name %r used twice" % m)
        seen[m] = 1

    a("//%-8s JOB (001),'%s',CLASS=A,MSGCLASS=A," % (job, title[:20]))
    a("//             USER=%s,PASSWORD=CUL8TR," % USER)
    a("//             REGION=8M,TIME=1440,MSGLEVEL=(1,1)")
    a("//*")

    # --- clear and allocate the libraries --------------------------------
    a("//SCRATCH  EXEC PGM=IEFBR14")
    for n, dsn in enumerate((HDR_DSN, VBH_DSN, SRC_DSN), 1):
        a("//D%d       DD DSN=%s,DISP=(MOD,DELETE)," % (n, dsn))
        a("//            UNIT=SYSDA,SPACE=(TRK,(1,1))")
    a("//*")
    a("//ALLOC    EXEC PGM=IEFBR14")
    for n, (dsn, dcb) in enumerate((
            (HDR_DSN, "(RECFM=FB,LRECL=80,BLKSIZE=3200)"),
            (VBH_DSN, "(RECFM=VB,LRECL=255,BLKSIZE=6144)"),
            (SRC_DSN, "(RECFM=FB,LRECL=80,BLKSIZE=3200)")), 1):
        a("//M%d       DD DSN=%s,DISP=(,CATLG,DELETE)," % (n, dsn))
        a("//            UNIT=SYSDA,SPACE=(TRK,(30,10,20)),")
        a("//            DCB=%s" % dcb)
    a("//*")

    # --- write the FB/80 libraries with IEBUPDTE --------------------------
    for stepname, dsn, items in (("WRITEH", HDR_DSN, headers),
                                 ("WRITEC", SRC_DSN, sources)):
        if not items:
            continue
        a("//%-8s EXEC PGM=IEBUPDTE,PARM=NEW" % stepname)
        a("//SYSPRINT DD SYSOUT=*")
        a("//SYSUT2   DD DSN=%s,DISP=OLD" % dsn)
        a("//SYSIN    DD DATA,DLM='%s'" % DLM)
        for relpath, member in items:
            a("./ ADD NAME=%s" % member)
            d.extend(cards_of(relpath))
        a("./ ENDUP")
        a(DLM)
        a("//*")

    # --- write the VB/255 library with IEBGENER, one member per step ------
    for n, (relpath, member) in enumerate(vb_headers, 1):
        a("//VBH%d     EXEC PGM=IEBGENER" % n)
        a("//SYSPRINT DD SYSOUT=*")
        a("//SYSUT2   DD DSN=%s(%s),DISP=OLD" % (VBH_DSN, member))
        a("//SYSIN    DD DUMMY")
        a("//SYSUT1   DD DATA,DLM='%s'" % DLM)
        d.extend(cards_of(relpath))
        a(DLM)
        a("//*")

    # --- compile and assemble each unit ----------------------------------
    for n, (_relpath, member) in enumerate(sources, 1):
        a("//COMP%d    EXEC PGM=GCC," % n)
        a("//  PARM='-S -ansi -pedantic-errors -Wno-long-long"
          "%s -o dd:out -'" % ((" " + opt) if opt else ""))
        a("//SYSINCL  DD DSN=PDPCLIB.INCLUDE,DISP=SHR,DCB=BLKSIZE=32720")
        if vb_headers:
            a("//         DD DSN=%s,DISP=SHR" % VBH_DSN)
        a("//INCLUDE  DD DSN=%s,DISP=SHR" % HDR_DSN)
        a("//SYSIN    DD DSN=%s(%s),DISP=SHR" % (SRC_DSN, member))
        a("//OUT      DD DSN=&&ASM%d,DISP=(,PASS),UNIT=SYSALLDA," % n)
        a("//            DCB=(LRECL=80,BLKSIZE=6160,RECFM=FB),")
        a("//            SPACE=(6160,(500,500))")
        a("//SYSPRINT DD SYSOUT=*")
        a("//SYSTERM  DD SYSOUT=*")
        a("//*")
        a("//ASM%d     EXEC PGM=IFOX00,PARM='%s'," % (n, asm_parm))
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

    # --- link and run -----------------------------------------------------
    # NCAL is deliberately NOT specified: PDPCLIB.NCALIB is the C runtime
    # and the linkage editor must search it, which is how GCCCLG does it.
    a("//LKED     EXEC PGM=IEWL,PARM='MAP,LIST',COND=(4,LT)")
    for n in range(1, len(sources) + 1):
        a("//%s DD DSN=&&OBJ%d,DISP=(OLD,DELETE)"
          % ("SYSLIN  " if n == 1 else "        ", n))
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
