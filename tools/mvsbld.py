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

# What onfplat.h reports as ONF_PLATID on this target, for reports
# whose driver prints no banner of its own.
PLATFORM = "MVS38J"
OPT = "-O1"
DLM = "ZZ"
CARD = 80
JCL_FIELD = 71

# The default region.  Every job in JCC.CNTL and SYS2.JCLLIB(TESTGCC)
# carries 8M, and without a region GCCMVS spins at 100% of a core instead
# of failing.  It is a parameter because it is also a measured limit: a
# 12,000-vector TT-02 table ended COMP2 in ABEND S878, insufficient
# virtual storage, at 8M (TBD-14).
REGION = "8M"

# The default C flags.  -Wno-long-long is required, not cosmetic: the
# procedures compile with -ansi -pedantic-errors, under which `long long`
# is an ERROR, and NR-04 defines the dialect as "C89 plus long long".
#
# A source entry may carry its own flags as a third element.  That exists
# for third_party: upstream SoftFloat 2c warns in float64_rem about
# pointer signedness, -pedantic-errors makes that fatal, and D-28 and
# D-35 forbid editing the file to silence it.  The x86 Makefile makes the
# same exception for the same reason, so the two builds stay comparable.
CC_FLAGS = "-ansi -pedantic-errors -Wno-long-long"
CC_FLAGS_VENDOR = "-ansi -Wno-long-long"

HDR_DSN = "%s.ONFLY.H" % USER      # FB/80, quoted includes
VBH_DSN = "%s.ONFLY.VBH" % USER    # VB/255, angle-bracket includes
SRC_DSN = "%s.ONFLY.C" % USER      # FB/80, translation units


class DeckError(Exception):
    pass


def with_defines(relpath, names, extra=()):
    """A source preceded by `#define` cards, as `-D` would have done.

    The x86 build selects the float backend with -DONF_FP_SOFT2C.  That
    cannot be done here: a JCL field ends at column 71 (see the note at the
    top of this file), the compile PARM card is already 67 columns, and
    adding the option would make it 83.

    So the definitions go in front of the source as cards, which is exactly
    what -D means to the preprocessor.  They are assembled at submit time
    and never written to disk, so there is no second copy of the source to
    drift from the first -- the same property D-110's amalgamation and
    D-111's rename prologue rely on.

    This matters for more than tidiness.  Without it the MVS engine links
    SoftFloat 2c and then reports SOFT3E in its run manifest, because
    ONF_FPID falls through to the default.  NFR-OBS-01 requires the manifest
    to name the backend, and D-124 exists precisely so that a fingerprint
    can never be attributed to the wrong library.

    `extra` is prepended before the defines, for a generated prologue such
    as the C-04 rename map.
    """
    cards = list(extra)
    for name in names:
        cards.append("#define %s 1" % name)
    return cards + cards_of(relpath)


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


def _cards(src):
    """Cards for a source entry: a repository path, or cards already built.

    amalgamate() returns cards rather than writing a file (D-110), so a
    caller can hand those straight to build() in place of a path.
    """
    if isinstance(src, (list, tuple)):
        return list(src)
    return cards_of(src)


def amalgamate(relpath, include_map, _seen=None, _depth=0):
    """Cards for `relpath` with its quoted includes inlined, recursively.

    D-110.  This exists because GCCMVS resolves `#include "name"` to the PDS
    member given by the first EIGHT characters of the name (VL-23), so
    SoftFloat 2c's `softfloat.h`, `softfloat-macros` and
    `softfloat-specialize` all name one member and three files cannot
    occupy it.  D-109's probe established there is no way round it: the
    compiler's own option list contains nothing that changes the mapping,
    and `-remap`, which is GCC's mechanism for exactly this, is accepted
    and inert on this port (VL-24).

    `include_map` maps an include spelling to a repository path and is
    supplied by the caller.  It is never derived, for the same reason
    member names are not: a rule that guessed would fail silently on the
    first name that did not fit it.  An include this map does not name is
    an error rather than a passthrough, so a new `#include` appearing
    upstream stops the build instead of being quietly left unresolved.

    Angle-bracket includes are left exactly as they are: those resolve
    from PDPCLIB on SYSINCL and have never collided.

    Nothing is written to disk.  The expansion is assembled into the deck
    on every run, so there is no second copy of the source to drift from
    the first -- which is the concern D-94 raised about amalgamating the
    engine source, and the reason it does not arise here.
    """
    if _seen is None:
        _seen = []
    if _depth > 8:
        raise DeckError("include nesting too deep at %s" % relpath)
    out = []
    for line in cards_of(relpath):
        stripped = line.strip()
        if stripped.startswith("#include") and '"' in stripped:
            name = stripped.split('"')[1]
            if name not in include_map:
                raise DeckError(
                    '%s includes "%s", which is not in the include map; '
                    "add it explicitly rather than letting it resolve by "
                    "accident" % (relpath, name))
            _seen.append(name)
            out.append("/* ONFLY: inlined \"%s\" (D-110) */" % name[:40])
            out.extend(amalgamate(include_map[name], include_map,
                                  _seen, _depth + 1))
            out.append("/* ONFLY: end of \"%s\" */" % name[:40])
        else:
            out.append(line)
    for card in out:
        if len(card) > CARD:
            raise DeckError("amalgamated card over %d columns: %s"
                            % (CARD, card[:90]))
    return out


def amalgamated_order(relpath, include_map):
    """The include names inlined, in the order the preprocessor sees them."""
    seen = []
    amalgamate(relpath, include_map, seen)
    return seen


def build(job, title, sources, headers=(), vb_headers=(), opt=OPT,
          asm_parm="DECK,NOLIST", region=REGION, go_parm=None,
          go_dd=(), post=()):
    """Return a deck that compiles `sources`, links them and runs the result.

    sources     [(repo path OR cards, 8-char member)]  units, in link order
    go_parm     PARM= for the GO step, or None for no PARM.  Every card
                it produces is checked against column 71 like any other.
    go_dd       extra DD cards for the GO step, appended verbatim after
                the standard three.  The caller writes whole JCL cards
                because a DD's operands vary far too much to model.
    post        whole cards for step(s) AFTER the GO step, appended
                verbatim before the closing `//`.  Phase E slice 1 needs
                an IDCAMS dump of the dataset ONFLYENG just wrote, and
                that is a step rather than a DD, so it cannot travel in
                `go_dd`.  The default is empty and every caller that
                does not pass it emits exactly the deck it emitted
                before -- this loop adds no card when `post` is ().
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
    for entry in list(sources) + list(headers) + list(vb_headers):
        m = entry[1]
        if len(m) > 8:
            raise DeckError("member name %r is over 8 characters" % m)
        if m in seen:
            raise DeckError("member name %r used twice" % m)
        seen[m] = 1

    a("//%-8s JOB (001),'%s',CLASS=A,MSGCLASS=A," % (job, title[:20]))
    a("//             USER=%s,PASSWORD=CUL8TR," % USER)
    a("//             REGION=%s,TIME=1440,MSGLEVEL=(1,1)" % region)
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
        a("//            UNIT=SYSDA,SPACE=(TRK,(90,30,40)),")
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
        for entry in items:
            src, member = entry[0], entry[1]
            a("./ ADD NAME=%s" % member)
            d.extend(_cards(src))
        a("./ ENDUP")
        a(DLM)
        a("//*")

    # --- write the VB/255 library with IEBGENER, one member per step ------
    for n, (relpath, member) in enumerate(list(vb_headers), 1):
        a("//VBH%d     EXEC PGM=IEBGENER" % n)
        a("//SYSPRINT DD SYSOUT=*")
        a("//SYSUT2   DD DSN=%s(%s),DISP=OLD" % (VBH_DSN, member))
        a("//SYSIN    DD DUMMY")
        a("//SYSUT1   DD DATA,DLM='%s'" % DLM)
        d.extend(cards_of(relpath))
        a(DLM)
        a("//*")

    # --- compile and assemble each unit ----------------------------------
    for n, entry in enumerate(sources, 1):
        member = entry[1]
        flags = entry[2] if len(entry) > 2 else CC_FLAGS
        a("//COMP%d    EXEC PGM=GCC," % n)
        a("//  PARM='-S %s%s -o dd:out -'"
          % (flags, (" " + opt) if opt else ""))
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
    # ONFLYENG is driven by its PARM (IR-TRN-03's VERIFY) and reads the
    # network through a DD the caller must allocate (IR-JCL-01), neither
    # of which any earlier job here needed.  Both stay optional so every
    # existing caller emits exactly the cards it emitted before.
    if go_parm:
        a("//GO       EXEC PGM=*.LKED.SYSLMOD,PARM='%s',"
          % go_parm)
        a("//            COND=(4,LT)")
    else:
        a("//GO       EXEC PGM=*.LKED.SYSLMOD,COND=(4,LT)")
    a("//SYSPRINT DD SYSOUT=*")
    a("//SYSTERM  DD SYSOUT=*")
    a("//SYSIN    DD DUMMY")
    for card in go_dd:
        a(card)
    for card in post:
        a(card)
    a("//")
    return d
