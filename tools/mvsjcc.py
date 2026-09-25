# -*- coding: utf-8 -*-
"""Row 7 of the determinism matrix: ONFLYENG under JCC on TK5 (D-281).

WHAT IS BEING CLAIMED
---------------------
SRS Section 8.3 lists eight rows and ACC-5 is satisfied only when every
golden request gives the same fingerprint in all of them.  Row 6 --
TK5 / SOFT2C / GCCMVS -- was filled on 2026-09-15 (D-255, VL-91).  Row 7
is the same platform and the same backend through a *different compiler*:

    | 7 | TK5 MVS 3.8j | SOFT2C | JCC (engine-only if JCC cannot build
    |   |              |        | the soft backend, VL-03)             |

That parenthesis is the point.  A second compiler on the same machine is
the only check ONFLY has that a fingerprint is a property of the SOURCE
and not of one code generator.  Everything the engine does is integer
work over a software float library, so a code-generation difference would
not show up as a rounding difference -- it would show up as a wrong
answer, or not at all.  Row 7 is what distinguishes those two.

WHAT THE PROJECT ALREADY KNOWS ABOUT JCC, AND WHAT IT DOES NOT
--------------------------------------------------------------
Known:

  A-04    JCC is installed: 12 datasets on TK5002, reached by STEPLIB
          (JCC.LINKLIB) and not by the linklist, unlike GCCMVS.
  G0      JCC 1.50.00 compiled, prelinked, linked and ran a 20-line
          probe with every step at COND CODE 0000 (tools/mvsg0.py).
          It defines no __VERSION__.
  VL-03   Recorded in advance: if JCC cannot compile the soft backend,
          the cross-check covers only what JCC can build.

Not known when this file was written, and measured by the probes below
on 2026-09-15.  The answers are kept here because each one cost a
job on the emulated MVS lab to find and none of them is guessable:

  * **Does JCC compile the SoftFloat 2c amalgamation?**  Yes -- but only
    after D-285.  Before it, JCC rejected `float64_rem`'s `add64` call
    and wrote **no object at all** for the unit, so F64ADD, F64SUB,
    F64MUL, F64LT and F64LE were every one unresolved at link.
  * **Does JCC compile ONFLY's own C89?**  Yes, twelve of the thirteen
    units at RC 0 on the first attempt.
  * **Does PRELINK accept a CONCATENATED object input?**  Yes, thirteen
    of them at COND CODE 0000.  `tools/mvstt01.py` records in its own
    source that it could not be made to with TWO; that note is either
    wrong or was about something else.
  * **What does JCC's RC 1 mean?**  It can mean *no object written*.  A
    `warning:` gives RC 0 and a usable object; a `type error` gives RC 1
    and nothing.  `--mini warn|typebad|type` is the measurement.
  * **Can JCC's libc open a DD?**  Only as `//DDN:NAME`; PDPCLIB's
    `DD:NAME` returns NULL (D-284).  And **not at all** on a
    unit-record device, in any mode, which is why D-286 installs the
    network as a catalogued dataset that rows 6 and 7 both read.
  * **Does it split PARM into argv?**  Yes, on blanks, exactly as
    PDPCLIB does -- which is what makes D-284 work with no engine
    source change.

One thing it does NOT do: identify itself.  The run manifest NFR-OBS-01
requires printed `COMPILER UNKNOWN` and `PLATFORM UNKNOWN` under JCC,
because `ONF_CCID` and `ONF_PLATID` key off macros JCC does not define.
`--ccprobe` asks it which macros it does define (D-291).

THE TOOLCHAIN, READ OFF THE MACHINE AND NOT GUESSED
---------------------------------------------------
SYS2.PROCLIB(JCCCL), printed by IEBPTPCH on 2026-09-15, is four steps:

    COMPILE  PGM=JCC      PARM='-I//DDN:JCCINCL //DDN:SYSIN -o
                                -list=//DDN:SYSPRINT'
             STEPLIB JCC.LINKLIB, JCCINCL/JCCINCS JCC.INCLUDE,
             object out on JCCOASM as FB/80, work file on JCCOUTPT
    PRELINK  PGM=PRELINK  PARM='-r //DDN:L //DDN:O //DDN:I'
             L = JCC.OBJ (the C runtime), I = in, O = out
    LKED     PGM=IEWL     PARM='NCAL,MAP,LIST,XREF,NORENT'
    GO       PGM=GO       STEPLIB &&GOSET

Two differences from the GCCMVS path in tools/mvsbld.py matter:

  1. JCC emits an OBJECT deck directly.  There is no separate assembly
     step, so IFOX00 -- which rejected GCCMVS's 64-bit output and is how
     A-05 was disproved -- is not in this path at all.
  2. IEWL is given NCAL here, because PRELINK has already resolved the
     runtime out of JCC.OBJ.  The GCCMVS path deliberately does NOT use
     NCAL, because there the linkage editor is what searches PDPCLIB.

WHY A PROBE FIRST
-----------------
The full link is thirteen translation units and roughly 8,500 cards.
Submitting that to answer "does JCC compile SoftFloat at all" would spend
a long compile to learn something three units can say.  --probe compiles
three representative units and then asks PRELINK to read all three as a
concatenation:

    SF2C      the SoftFloat 2c amalgamation -- VL-03's named risk, and
              by far the largest unit
    ONFCRCC   plain ONFLY C89 with no float in it
    ONFRNDC   the PRNG: shifts and masks on unsigned 32-bit, the
              arithmetic NR-11 constrains

BOTH HALVES OF THE SUITE
------------------------
Until 2026-09-18 this file ran `srext` only and refused `--net`, so row
7 covered five of the nineteen Section 8.4 requests and none of the
three rejection paths -- G-11's ONF201W, G-12's ONF203E and G-13's
ONF202E are all `path` requests.  D-458 makes the `path` half the scope
of that session and D-462 gives each network its own job name and its
own response dataset:

    srext   ONFJRUN    HERC01.ONFLY.JRSP
    path    ONFJPRUN   HERC01.ONFLY.JPRSP

`srext` keeps what VL-93 recorded and stays the default, so every
caller that says no `--net` behaves exactly as before (D-259).

Run (repository root):

    python tools/mvsjcc.py --probe
    python tools/mvsjcc.py --net path --run --out data/phase-e/jcc
    python tools/mvsjcc.py --net path --recover --out data/phase-e/jcc
    python tools/mvsjcc.py --net path --compare data/phase-e/jcc \\
                                                data/phase-d/x86w

`--recover` is for when the submitter dies and the job does not: the
`path` job runs for hours, and MVS keeps it and JES2 keeps its output
regardless of what happened on the x86 side (D-465).
"""
import io
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import mvsbld                                            # noqa: E402
import mvscob                                            # noqa: E402
import mvseng                                            # noqa: E402
import mvsrun                                            # noqa: E402
import mvsub                                             # noqa: E402

USER = mvsbld.USER
REGION = mvsbld.REGION
DLM = mvsbld.DLM
JCL_FIELD = mvsbld.JCL_FIELD

#: The JCC datasets, as A-04 confirmed them at Gate G0: all on TK5002.
JCC_LOAD = "JCC.LINKLIB"
JCC_INCL = "JCC.INCLUDE"
JCC_OBJ = "JCC.OBJ"

#: JCC's own options, taken from SYS2.PROCLIB(JCCCL)'s JOPTS default.
#: GCCMVS's -ansi -pedantic-errors -Wno-long-long are GCC spellings and
#: are not offered to a compiler that has never seen them: a probe that
#: failed on an unrecognised option would prove nothing about the source.
#:
#: The two DD names are ONFH and LST rather than INCLUDE and SYSPRINT
#: only because of column 71.  The whole PARM has to fit on one card --
#: a quoted JCL string can be continued, but only by taking every column
#: through 71 as part of the string, so where the break falls becomes
#: part of the compiler's command line.  That is exactly the class of
#: silent, position-dependent corruption D-93 exists to refuse, so the
#: names are shortened instead and the card is 70 columns.
JCC_LIST_DD = "LST"
JCC_HDR_DD = "ONFH"
JCC_OPTS = "-o -list=//DDN:%s" % JCC_LIST_DD

#: Where the source and headers are staged.  The same three datasets
#: tools/mvsbld.py uses, so a JCC job and a GCCMVS job never see
#: different copies of the same header.
HDR_DSN = mvsbld.HDR_DSN
SRC_DSN = mvsbld.SRC_DSN


class JccError(Exception):
    pass


def probe_sources():
    """The three units --probe compiles, with their member names.

    Each is built exactly as tools/mvsrun.py builds it, including the
    ONF_FP_SOFT2C define and the generated/onf2cnm.h prologue, so that a
    failure here is a failure of the same text the real link would feed
    the compiler -- not of a simplified stand-in.
    """
    prologue = mvsbld.cards_of("generated/onf2cnm.h")
    library = prologue + mvsbld.amalgamate(mvseng.UNIT, mvseng.INCLUDES)
    return [
        (library, "SF2C"),
        (mvsbld.with_defines("engine/src/onfcrc.c", ["ONF_FP_SOFT2C"]),
         "ONFCRCC"),
        (mvsbld.with_defines("engine/src/onfrnd.c", ["ONF_FP_SOFT2C"]),
         "ONFRNDC"),
    ]


#: The spellings of a DD name a C runtime might accept on fopen().  The
#: engine uses the first (D-86, `ONF_NETDD`), because that is PDPCLIB's;
#: JCC ships its own libc and its own procedures spell a DD
#: `//DDN:SYSIN`, so whether one source can open a DD under both
#: runtimes is a question about JCC's fopen and not about ONFLY.  It is
#: asked here rather than assumed, because the failure mode -- ONF901S
#: on a dataset that is present and correct -- would otherwise be read
#: as a transport or allocation fault.
DD_SPELLINGS = ("DD:ONFNET", "//DDN:ONFNET", "DDN:ONFNET", "dd:onfnet")


def ddprobe_source():
    """A small C program: which fopen spelling, and how PARM becomes argv.

    Two questions in one program because they need one job between them.

    The fopen half prints one line per candidate so a failure names the
    spelling rather than the program, and reads four bytes from any that
    opens -- an fopen that succeeds and then reads nothing would be a
    false pass.

    The argv half exists because D-284 puts the three dataset names in
    the PARM.  Whether JCC's startup splits a PARM on blanks the way
    PDPCLIB does was unmeasured when that decision was taken, and the
    failure mode is silent: a runtime that handed the whole PARM over as
    one argument would leave argv[2] holding all three names, the engine
    would try to open that as a dataset, and the job would fail with a
    message about ONFNET that had nothing to do with ONFNET.
    """
    src = [
        "#include <stdio.h>",
        "",
        "int main(int argc, char **argv)",
        "{",
        "    static char *names[] = {",
    ]
    for s in DD_SPELLINGS:
        src.append('        "%s",' % s)
    src.extend([
        "        0",
        "    };",
        "    int i;",
        "    FILE *f;",
        "    unsigned char b[4];",
        "    size_t n;",
        "",
        "    for (i = 0; names[i] != 0; i++) {",
        "        f = fopen(names[i], \"rb\");",
        "        if (f == 0) {",
        "            printf(\"DDPROBE %-14s FOPEN-NULL\\n\", names[i]);",
        "            continue;",
        "        }",
        "        n = fread(b, 1, 4, f);",
        "        printf(\"DDPROBE %-14s OPEN read=%d %02X%02X%02X%02X\\n\",",
        "               names[i], (int)n, b[0], b[1], b[2], b[3]);",
        "        fclose(f);",
        "    }",
        "",
        "    printf(\"ARGVPROBE argc=%d\\n\", argc);",
        "    for (i = 0; i < argc; i++) {",
        "        printf(\"ARGVPROBE argv[%d]=<%s>\\n\", i, argv[i]);",
        "    }",
        "    return 0;",
        "}",
    ])
    return src


def ddprobe_deck():
    """Compile, prelink, link and run the fopen probe with ONFNET allocated.

    ONFNET is pointed at the very member this job just staged, so it is
    a real, readable, non-empty dataset that cannot be stale: a failure
    to open it is the runtime's and not the allocation's.
    """
    d = deck("ONFJDDP", [(ddprobe_source(), "DDPROBE")], (), prelink=True)
    # deck() closes with `//`; replace that with the link and go steps.
    assert d[-1] == "//"
    d = d[:-1]
    d.append("//LKED     EXEC PGM=IEWL,COND=(4,LT),")
    d.append("//            PARM='NCAL,MAP,LIST,XREF,NORENT'")
    d.append("//SYSLIN   DD DSN=&&OBJMOD,DISP=(OLD,DELETE)")
    d.append("//SYSUT1   DD UNIT=SYSDA,SPACE=(CYL,(5,2))")
    d.append("//SYSPRINT DD SYSOUT=*")
    d.append("//SYSLMOD  DD DSN=&&GOSET(GO),UNIT=SYSDA,")
    d.append("//            SPACE=(4096,(100,20,1)),DISP=(,PASS),")
    d.append("//            DCB=(RECFM=U,BLKSIZE=4096)")
    d.append("//*")
    # The PARM D-284 will use, spelled exactly as the real GO step will
    # spell it, so that what is measured is what will run.
    d.append("//GO       EXEC PGM=*.LKED.SYSLMOD,COND=(4,LT),")
    d.append("//   PARM='RUN //DDN:ONFNET //DDN:ONFREQ //DDN:ONFRSP'")
    d.append("//STDOUT   DD SYSOUT=*")
    d.append("//STDERR   DD SYSOUT=*")
    d.append("//SYSPRINT DD SYSOUT=*")
    d.append("//ONFNET   DD DSN=%s(DDPROBE),DISP=SHR" % SRC_DSN)
    d.append("//")
    return d


def deck(job, sources, headers, prelink=True, listing=True, title=None):
    """A JCC compile deck for `sources`, optionally prelinking them all.

    sources   [(cards or repo path, 8-char member)] in order
    headers   [(repo path, 8-char member)] for #include "x.h"
    prelink   True appends one PRELINK step whose I DD is the
              CONCATENATION of every object produced.  That is the
              question tools/mvstt01.py left open, and it is asked with
              the objects already in hand so that a failure is
              attributable to PRELINK and not to a compile.
    listing   True asks JCC for the generated assembler on a SYSOUT DD.
              It is what makes a probe readable and what makes a real
              build unreadable: three units produced 821 KB, and the
              thirteen-unit link would put several megabytes through the
              printer file every other tool here has to scan.  The
              diagnostics are on STDOUT either way, so nothing needed to
              judge a compile is lost by turning it off.
    """
    d = []

    def a(card):
        if card.startswith("//") and len(card) > JCL_FIELD:
            raise JccError("JCL card exceeds column %d (%d): %s"
                           % (JCL_FIELD, len(card), card))
        d.append(card)

    seen = {}
    for entry in list(sources) + list(headers):
        m = entry[1]
        if len(m) > 8:
            raise JccError("member name %r is over 8 characters" % m)
        if m in seen:
            raise JccError("member name %r used twice" % m)
        seen[m] = 1

    a("//%-8s JOB (001),'%s',CLASS=A,MSGCLASS=A,"
      % (job, (title or "ONFLY JCC ROW7")[:20]))
    a("//             USER=%s,PASSWORD=CUL8TR," % USER)
    a("//             REGION=%s,TIME=1440,MSGLEVEL=(1,1)" % REGION)
    a("//*")

    # --- clear and allocate the staging libraries -------------------------
    a("//SCRATCH  EXEC PGM=IEFBR14")
    for n, dsn in enumerate((HDR_DSN, SRC_DSN), 1):
        a("//D%d       DD DSN=%s,DISP=(MOD,DELETE)," % (n, dsn))
        a("//            UNIT=SYSDA,SPACE=(TRK,(1,1))")
    a("//*")
    a("//ALLOC    EXEC PGM=IEFBR14")
    for n, dsn in enumerate((HDR_DSN, SRC_DSN), 1):
        a("//M%d       DD DSN=%s,DISP=(,CATLG,DELETE)," % (n, dsn))
        a("//            UNIT=SYSDA,SPACE=(TRK,(90,30,40)),")
        a("//            DCB=(RECFM=FB,LRECL=80,BLKSIZE=3200)")
    a("//*")

    # --- write them with IEBUPDTE ----------------------------------------
    for stepname, dsn, items in (("WRITEH", HDR_DSN, headers),
                                 ("WRITEC", SRC_DSN, sources)):
        if not items:
            continue
        a("//%-8s EXEC PGM=IEBUPDTE,PARM=NEW" % stepname)
        a("//SYSPRINT DD SYSOUT=*")
        a("//SYSUT2   DD DSN=%s,DISP=OLD" % dsn)
        a("//SYSIN    DD DATA,DLM='%s'" % DLM)
        for entry in items:
            a("./ ADD NAME=%s" % entry[1])
            d.extend(mvsbld._cards(entry[0]))
        a("./ ENDUP")
        a(DLM)
        a("//*")

    # --- compile each unit with JCC --------------------------------------
    # -I//DDN:INCLUDE is added to JCCCL's own -I//DDN:JCCINCL so that
    # ONFLY's quoted includes resolve out of HERC01.ONFLY.H.  The two -I
    # are given in that order because JCC's own headers must not be
    # shadowed by a repository file that happens to share a name.
    for n, entry in enumerate(sources, 1):
        a("//COMP%d    EXEC PGM=JCC," % n)
        a("//  PARM='-I//DDN:JCCINCL -I//DDN:%s //DDN:SYSIN %s'"
          % (JCC_HDR_DD, JCC_OPTS if listing else "-o"))
        a("//STEPLIB  DD DSN=%s,DISP=SHR" % JCC_LOAD)
        a("//JCCINCL  DD DSN=%s,DISP=SHR" % JCC_INCL)
        a("//JCCINCS  DD DSN=%s,DISP=SHR" % JCC_INCL)
        a("//%-8s DD DSN=%s,DISP=SHR" % (JCC_HDR_DD, HDR_DSN))
        # Unnamed and deleted: JCCOUTPT is scratch.  JCCCL names it
        # &&OUTPT and passes it, which cannot be done thirteen times.
        a("//JCCOUTPT DD UNIT=SYSDA,SPACE=(TRK,(50,20))")
        a("//STDOUT   DD SYSOUT=*")
        if listing:
            a("//%-8s DD SYSOUT=*" % JCC_LIST_DD)
        a("//JCCOASM  DD DSN=&&OBJ%d,UNIT=SYSALLDA," % n)
        a("//            SPACE=(3200,(200,100),RLSE),DISP=(,PASS),")
        a("//            DCB=(RECFM=FB,LRECL=80,BLKSIZE=3200)")
        a("//SYSIN    DD DSN=%s(%s),DISP=SHR" % (SRC_DSN, entry[1]))
        a("//*")

    # --- prelink them all together ---------------------------------------
    if prelink:
        a("//PRELINK  EXEC PGM=PRELINK,COND=(4,LT),")
        a("//            PARM='-r //DDN:L //DDN:O //DDN:I'")
        a("//STEPLIB  DD DSN=%s,DISP=SHR" % JCC_LOAD)
        a("//STDOUT   DD SYSOUT=*")
        a("//L        DD DSN=%s,DISP=SHR" % JCC_OBJ)
        for n in range(1, len(sources) + 1):
            a("//%s DD DSN=&&OBJ%d,DISP=(OLD,DELETE)"
              % ("I       " if n == 1 else "        ", n))
        a("//O        DD DSN=&&OBJMOD,UNIT=SYSALLDA,")
        a("//            SPACE=(3200,(200,100),RLSE),DISP=(,PASS),")
        a("//            DCB=(RECFM=FB,LRECL=80,BLKSIZE=3200)")
        a("//*")
    a("//")
    return d


#: Row 7's own MVS names, one set per Section 8.4 network (D-462).
#:
#: Where the JCC build writes is a dataset of its own, not ONFERSP or
#: ONFPRSP: the GCCMVS result is the comparand row 7 is judged against,
#: and a run that overwrote it would destroy the thing it is being
#: compared to.
#:
#: `srext` keeps the job name and the dataset VL-93 recorded, so that
#: entry stays true and the JES2, printer and punch trail says which
#: half of row 7 produced which listing without anyone having to read
#: its contents.  `path` takes its own pair.  They live HERE and not in
#: `tools/mvsrun.py::NETS`, which documents row 6's jobs: row 7's names
#: belong to row 7's driver.
JCC_NAMES = {
    "srext": {"job": "ONFJRUN", "rsp": "JRSP"},
    "path": {"job": "ONFJPRUN", "rsp": "JPRSP"},
}


def jcc_job():
    """The job name for the network `mvsrun` is currently pointed at.

    Resolved on every call, never bound at import.  `tools/mvsrun.py`
    records the same class of bug biting twice in one session through
    mutable-looking defaults (`write_cards`, `golden_fingerprints`): a
    module global captured once leaves `select("path")` changing half
    the names and not the other half, which is the wrong network
    travelling under the right job name.
    """
    return JCC_NAMES[mvsrun.NETNAME]["job"]


def jcc_rsp_dsn():
    """The response dataset for the network `mvsrun` is pointed at.

    Resolved on every call, for `jcc_job`'s reason.
    """
    return "%s.ONFLY.%s" % (USER, JCC_NAMES[mvsrun.NETNAME]["rsp"])

#: The GO step's PARM, D-284's mechanism spelled exactly as
#: `python tools/mvsjcc.py --ddprobe` measured it working on 2026-09-15:
#: argc=5, argv[1]='RUN', argv[2..4] the three names.  argv[1] is any
#: word that is not VERIFY -- onfeisv() treats everything else as
#: SIMULATE -- and 'RUN' is chosen because it says so to a reader.
GO_PARM = "RUN //DDN:ONFNET //DDN:ONFREQ //DDN:ONFRSP"


def check_names():
    """Refuse a deck whose job, response dataset and network disagree.

    This is what `main()`'s blanket refusal of `--net` used to stand in
    for.  That refusal said row 7 was `srext` only and named the failure
    mode it was guarding: *the wrong network under the right job name* --
    a run that costs an hour of TK5 and produces a listing nobody can
    trust, because the evidence of which network it read is exactly the
    thing that went wrong.

    D-462 removes that failure mode by construction: each network has
    its own job name and its own response dataset, so a mismatch cannot
    be silent.  This function is the guard restated as an assertion, so
    that the property is checked on every deck rather than achieved by
    a comment.  `tests/run_mvsjcc.py` exercises it for both networks
    with no lab present (D-464).
    """
    if mvsrun.NETNAME not in JCC_NAMES:
        raise JccError("no row 7 names for network %r; expected one of %s"
                       % (mvsrun.NETNAME, sorted(JCC_NAMES)))
    # Every name the deck will carry has to come from the SAME network.
    # mvsrun.NET_DSN and REQ_DSN are set by mvsrun.select(); jcc_job()
    # and jcc_rsp_dsn() read mvsrun.NETNAME.  If a caller ever set the
    # module globals by hand instead of calling select(), these would
    # disagree and the run would read one network and be filed under
    # another.
    spec = mvsrun.NETS[mvsrun.NETNAME]
    want_net = "%s.ONFLY.%s" % (USER, spec["net"])
    want_req = "%s.ONFLY.%s" % (USER, spec["dsn"])
    if mvsrun.NET_DSN != want_net or mvsrun.REQ_DSN != want_req:
        raise JccError(
            "mvsrun is inconsistent for %r: NET_DSN=%s (want %s), "
            "REQ_DSN=%s (want %s) -- call mvsrun.select() rather than "
            "setting the globals"
            % (mvsrun.NETNAME, mvsrun.NET_DSN, want_net,
               mvsrun.REQ_DSN, want_req))
    # The response dataset must not be any of row 6's: row 6's records
    # are what row 7 is judged against (`run_compare`), so a run that
    # overwrote one would destroy its own comparand.
    rsp = jcc_rsp_dsn()
    for other in mvsrun.NETS.values():
        if rsp == "%s.ONFLY.%s" % (USER, other["rsp"]):
            raise JccError("row 7 would write row 6's response dataset %s"
                           % rsp)
    return jcc_job(), rsp


def run_deck():
    """The same thirteen units as row 6, built by JCC, for one network.

    The job is `ONFJRUN` for `srext` and `ONFJPRUN` for `path` (D-462);
    `check_names()` states the invariant that keeps those straight.

    The source list, the defines and above all the LINK ORDER are
    tools/mvsrun.py's, taken from it by calling `_sources()` rather than
    copied, because two copies of a link order is two link orders and
    row 7 is only evidence if it links what row 6 linked.

    The GCCMVS flags in each entry's third field are ignored here: they
    are GCC spellings.  Nothing else about the entries is changed.
    """
    job, rsp_dsn = check_names()

    sources = [(src, member) for (src, member, *_rest)
               in [tuple(e) + ((),) * (3 - len(e)) for e in
                   mvsrun._sources()]]
    got = tuple(m for _s, m in sources)
    if got != mvsrun.UNIT_MEMBERS:
        raise JccError("link order changed: %s" % (got,))

    d = deck(job, sources, mvsrun.HEADERS, prelink=True,
             listing=False, title="ONFLY JCC ROW7")
    assert d[-1] == "//"
    d = d[:-1]

    # IEWL with NCAL, unlike the GCCMVS path: PRELINK has already
    # resolved the C runtime out of JCC.OBJ, so there is nothing left
    # for the linkage editor to search and NCAL says so.  This is
    # SYS2.PROCLIB(JCCCL)'s own PARM, unchanged.
    d.append("//LKED     EXEC PGM=IEWL,COND=(4,LT),")
    d.append("//            PARM='NCAL,MAP,LIST,XREF,NORENT'")
    d.append("//SYSLIN   DD DSN=&&OBJMOD,DISP=(OLD,DELETE)")
    d.append("//SYSUT1   DD UNIT=SYSDA,SPACE=(CYL,(5,2))")
    d.append("//SYSPRINT DD SYSOUT=*")
    d.append("//SYSLMOD  DD DSN=&&GOSET(GO),UNIT=SYSDA,")
    d.append("//            SPACE=(4096,(200,40,1)),DISP=(,PASS),")
    d.append("//            DCB=(RECFM=U,BLKSIZE=4096)")
    d.append("//*")
    # The catalogued response dataset has to be gone before the GO step
    # allocates it, for the reason mvsbld.build() states: a second run
    # otherwise fails at allocation with NOT CATLGD 2, reported nowhere
    # near the DD that caused it.
    d.append("//SCRATCH2 EXEC PGM=IEFBR14,COND=(4,LT)")
    d.append("//D1       DD DSN=%s,DISP=(MOD,DELETE)," % rsp_dsn)
    d.append("//            UNIT=SYSDA,SPACE=(TRK,(1,1))")
    d.append("//*")
    d.append("//GO       EXEC PGM=*.LKED.SYSLMOD,COND=(4,LT),")
    d.append("//   PARM='%s'" % GO_PARM)
    d.append("//SYSPRINT DD SYSOUT=*")
    d.append("//STDOUT   DD SYSOUT=*")
    d.append("//STDERR   DD SYSOUT=*")
    d.append("//SYSTERM  DD SYSOUT=*")
    d.append("//SYSIN    DD DUMMY")
    # D-286: the installed network.  JCC's fopen returns NULL on a
    # unit-record DD in every mode (--rdrprobe), so row 7 could not
    # read the reader at all; row 6 now reads this same dataset, which
    # is what keeps the compiler the only difference between them.
    d.append("//ONFNET   DD DSN=%s,DISP=SHR" % mvsrun.NET_DSN)
    d.append("//ONFREQ   DD DSN=%s,DISP=SHR" % mvsrun.REQ_DSN)
    d.append("//ONFRSP   DD DSN=%s,DISP=(,CATLG,DELETE)," % rsp_dsn)
    d.append("//            UNIT=SYSDA,SPACE=(TRK,(2,1)),")
    d.append("//            DCB=(RECFM=FB,LRECL=412,BLKSIZE=4120)")
    d.append("//*")
    d.append("//DUMP     EXEC PGM=IDCAMS,COND=(8,LT)")
    d.append("//SYSPRINT DD SYSOUT=*")
    d.append("//ONFRSP   DD DSN=%s,DISP=SHR" % rsp_dsn)
    d.append("//SYSIN    DD *")
    d.append("  PRINT INFILE(ONFRSP) DUMP")
    d.append("/*")
    d.append("//")
    return d


def run_probe(argv):
    sources = probe_sources()
    d = deck("ONFJPRB", sources, mvseng.HEADERS, prelink=True)
    print("mvsjcc: probe deck %d cards, %d units: %s"
          % (len(d), len(sources), ", ".join(s[1] for s in sources)))
    before = mvsub.submit(d)
    out = mvsub.collect("ONFJPRB", before, timeout=1800)
    if out is None:
        print("mvsjcc: TIMEOUT waiting for ONFJPRB")
        return 1
    path = os.path.join(ROOT, "data", "phase-e", "mvs", "jcc-probe.txt")
    dirn = os.path.dirname(path)
    if not os.path.isdir(dirn):
        os.makedirs(dirn)
    with open(path, "w") as fh:
        fh.write(out)
    print("mvsjcc: listing saved to %s (%d bytes)" % (path, len(out)))
    return 0


def run_ddprobe(argv):
    d = ddprobe_deck()
    print("mvsjcc: ddprobe deck %d cards, %d spellings"
          % (len(d), len(DD_SPELLINGS)))
    before = mvsub.submit(d)
    out = mvsub.collect("ONFJDDP", before, timeout=600)
    if out is None:
        print("mvsjcc: TIMEOUT waiting for ONFJDDP")
        return 1
    path = os.path.join(ROOT, "data", "phase-e", "mvs", "jcc-ddprobe.txt")
    dirn = os.path.dirname(path)
    if not os.path.isdir(dirn):
        os.makedirs(dirn)
    with open(path, "w") as fh:
        fh.write(out)
    for line in out.splitlines():
        if (("DDPROBE " in line or "ARGVPROBE " in line)
                and "./ ADD" not in line and "printf" not in line):
            print(line.rstrip())
    print("mvsjcc: listing saved to %s (%d bytes)" % (path, len(out)))
    return 0


#: Two four-line programs that isolate what JCC's RC 1 means.  The
#: thirteen-unit link left F64ADD and four siblings unresolved because
#: the SoftFloat unit contributed no CSECT at all: JCC reported RC 1 and
#: wrote no object.  Its RC 1 covers BOTH of the diagnostics that unit
#: produces -- seven warnings and one "type error" -- and which of them
#: suppresses the object decides how large the remedy is.  One warning
#: that suppresses an object would mean clearing seven vendor warnings;
#: one type error that does would mean clearing a single line.
MINI = {
    "warn": [
        "#include <stdio.h>",
        "unsigned int negu(unsigned int u)",
        "{",
        "    return -u;                 /* unsigned operand of unary - */",
        "}",
        "int main(void)",
        "{",
        "    printf(\"MINIPROBE warn negu=%u\\n\", negu(3u));",
        "    return 0;",
        "}",
    ],
    "type": [
        "#include <stdio.h>",
        "static void put(unsigned int *p)",
        "{",
        "    *p = 7u;",
        "}",
        "int main(void)",
        "{",
        "    int v = 0;",
        "    put((unsigned int *)&v);   /* the shape of the add64 call */",
        "    printf(\"MINIPROBE type v=%d\\n\", v);",
        "    return 0;",
        "}",
    ],
    "typebad": [
        "#include <stdio.h>",
        "static void put(unsigned int *p)",
        "{",
        "    *p = 7u;",
        "}",
        "int main(void)",
        "{",
        "    int v = 0;",
        "    put(&v);                   /* exactly the add64 diagnostic */",
        "    printf(\"MINIPROBE typebad v=%d\\n\", v);",
        "    return 0;",
        "}",
    ],
}


#: Candidate predefined macros, for D-291.  Row 7's run manifest printed
#: `COMPILER UNKNOWN` and `PLATFORM UNKNOWN`: `ONF_CCID` keys off
#: `__GNUC__`, `__IBMC__` and `__MVS__`, `ONF_PLATID` off `__MVS__`,
#: `__s390x__` and `_WIN32`, and JCC defines none of them.  NFR-OBS-01
#: requires the manifest to carry compiler identification, and the one
#: determinism row that exists to VARY the compiler was the row unable
#: to name it.
#:
#: The list is deliberately wider than the guess.  JCC is an lcc
#: derivative, so `__LCC__` is likely -- but a probe that tested only
#: the likely answer would report "not defined" and leave the real one
#: undiscovered, which is how one probe becomes three.
CCMACROS = (
    "__LCC__", "__JCC__", "JCC", "__lcc__",
    "__MVS__", "__CMS__", "__370__", "__S370__", "__s390__", "__s390x__",
    "__IBMC__", "__GNUC__", "__STDC__", "__STDC_VERSION__",
    "MVS", "__EBCDIC__", "__BIG_ENDIAN__", "_MVS", "__TOS_MVS__",
)


def ccprobe_source():
    """Print, for each candidate macro, whether JCC defines it and to what.

    Every macro is reported -- defined or not -- because "absent from the
    output" and "not defined" look the same in a listing, and the whole
    point is to find the one that IS defined.  A macro that expands to
    nothing is distinguished from one that expands to a value by the
    stringised form, so `-D FOO` and `-D FOO=1` are not confused.

    The stringify is TWO levels, and that is load-bearing.  `#x` in a
    function-like macro suppresses expansion of the argument, so a single
    `STR(FOO)` stringises the token `FOO` whatever FOO is defined to.  The
    first run of this probe on 2026-09-15 used one level and reported
    `__STDC__` as `<__STDC__>`, where C89 requires the value 1 -- the
    column showed macro names, never values, and the paragraph above was
    false of the code below it.  XSTR expands the argument first, then STR
    stringises the result, which is what makes the distinction real.
    """
    src = ["#include <stdio.h>", "",
           "#define STR(x) #x", "#define XSTR(x) STR(x)", "",
           "int main(void)", "{"]
    for m in CCMACROS:
        src.append("#ifdef %s" % m)
        src.append("    printf(\"CCPROBE %-20s DEFINED  <%%s>\\n\","
                   % m)
        src.append("           XSTR(%s));" % m)
        src.append("#else")
        src.append("    printf(\"CCPROBE %-20s -\\n\");" % m)
        src.append("#endif")
    src.append("    return 0;")
    src.append("}")
    return src


def ccprobe_deck():
    d = deck("ONFJCCP", [(ccprobe_source(), "CCPROBE")], (), prelink=True,
             title="ONFLY JCC MACROS")
    assert d[-1] == "//"
    d = d[:-1]
    d.append("//LKED     EXEC PGM=IEWL,COND=(4,LT),")
    d.append("//            PARM='NCAL,MAP,LIST,XREF,NORENT'")
    d.append("//SYSLIN   DD DSN=&&OBJMOD,DISP=(OLD,DELETE)")
    d.append("//SYSUT1   DD UNIT=SYSDA,SPACE=(CYL,(5,2))")
    d.append("//SYSPRINT DD SYSOUT=*")
    d.append("//SYSLMOD  DD DSN=&&GOSET(GO),UNIT=SYSDA,")
    d.append("//            SPACE=(4096,(100,20,1)),DISP=(,PASS),")
    d.append("//            DCB=(RECFM=U,BLKSIZE=4096)")
    d.append("//*")
    d.append("//GO       EXEC PGM=*.LKED.SYSLMOD,COND=(4,LT)")
    d.append("//STDOUT   DD SYSOUT=*")
    d.append("//STDERR   DD SYSOUT=*")
    d.append("//SYSPRINT DD SYSOUT=*")
    d.append("//")
    return d


def run_ccprobe(argv):
    d = ccprobe_deck()
    sys.stdout.write("mvsjcc: ccprobe %d cards, %d candidate macros\n"
                     % (len(d), len(CCMACROS)))
    before = mvsub.submit(d)
    out = mvsub.collect("ONFJCCP", before, timeout=1800)
    if out is None:
        sys.stderr.write("mvsjcc: TIMEOUT waiting for ONFJCCP\n")
        return 1
    hits = 0
    for line in out.splitlines():
        s = line.rstrip()
        if "CCPROBE " in s and "printf" not in s and "#" not in s:
            sys.stdout.write(s.strip() + "\n")
            if "DEFINED" in s:
                hits += 1
    sys.stdout.write("mvsjcc: %d of %d candidate macros defined\n"
                     % (hits, len(CCMACROS)))
    return 0


def mini_deck(which):
    """Compile, prelink, link and run one MINI program.

    If the program prints its line, JCC wrote an object despite the
    diagnostic.  If LKED reports an unresolved main, it did not.  Either
    way the answer is one line of printer output rather than an
    inference from a return code.
    """
    d = deck("ONFJMIN", [(MINI[which], "MINIPRB")], (), prelink=True,
             title="ONFLY JCC MINI")
    assert d[-1] == "//"
    d = d[:-1]
    d.append("//LKED     EXEC PGM=IEWL,COND=(4,LT),")
    d.append("//            PARM='NCAL,MAP,LIST,XREF,NORENT'")
    d.append("//SYSLIN   DD DSN=&&OBJMOD,DISP=(OLD,DELETE)")
    d.append("//SYSUT1   DD UNIT=SYSDA,SPACE=(CYL,(5,2))")
    d.append("//SYSPRINT DD SYSOUT=*")
    d.append("//SYSLMOD  DD DSN=&&GOSET(GO),UNIT=SYSDA,")
    d.append("//            SPACE=(4096,(100,20,1)),DISP=(,PASS),")
    d.append("//            DCB=(RECFM=U,BLKSIZE=4096)")
    d.append("//*")
    d.append("//GO       EXEC PGM=*.LKED.SYSLMOD,COND=(4,LT)")
    d.append("//STDOUT   DD SYSOUT=*")
    d.append("//STDERR   DD SYSOUT=*")
    d.append("//SYSPRINT DD SYSOUT=*")
    d.append("//")
    return d


def run_mini(argv):
    which = argv[0] if argv else "warn"
    if which not in MINI:
        sys.stderr.write("mvsjcc: --mini expects one of %s\n"
                         % ", ".join(sorted(MINI)))
        return 2
    d = mini_deck(which)
    sys.stdout.write("mvsjcc: mini probe %r, %d cards\n" % (which, len(d)))
    before = mvsub.submit(d)
    out = mvsub.collect("ONFJMIN", before, timeout=600)
    if out is None:
        sys.stderr.write("mvsjcc: TIMEOUT waiting for ONFJMIN\n")
        return 1
    for line in out.splitlines():
        s = line.rstrip()
        if ("JCC-RC:" in s or "MINIPROBE " in s or "RC= " in s
                or "IEW0461" in s or "cpp:" in s
                or "//DDN:SYSIN:" in s) and "printf" not in s:
            sys.stdout.write(s + "\n")
    return 0


#: Reader-open probe.  The thirteen-unit link succeeded and the engine
#: then answered `ONF108E NETWORK DATASET UNREADABLE: //DDN:ONFNET`,
#: with the step accounting showing `10C.......0` -- nothing read from
#: the card reader.  Under PDPCLIB the same DD on the same device works
#: (row 6 reads its network that way).  This asks which half of it JCC
#: cannot do: open a unit-record device, or read one.
RDR_SRC = [
    "#include <stdio.h>",
    "",
    "int main(void)",
    "{",
    "    FILE *f;",
    "    unsigned char b[80];",
    "    size_t n;",
    "    long total = 0;",
    "    int recs = 0;",
    "",
    "    static char *modes[] = { \"rb\", \"r\", \"rb,type=record\", 0 };",
    "    int m;",
    "",
    "    f = 0;",
    "    for (m = 0; modes[m] != 0; m++) {",
    "        f = fopen(\"//DDN:ONFNET\", modes[m]);",
    "        printf(\"RDRPROBE mode=%-16s %s\\n\", modes[m],",
    "               f == 0 ? \"fopen-NULL\" : \"fopen-OK\");",
    "        if (f != 0) break;",
    "    }",
    "    if (f == 0) {",
    "        printf(\"RDRPROBE no mode opened the reader\\n\");",
    "        return 0;",
    "    }",
    "    while ((n = fread(b, 1, 80, f)) > 0) {",
    "        total += (long)n;",
    "        recs++;",
    "        if (recs == 1) {",
    "            printf(\"RDRPROBE first n=%d %02X%02X%02X%02X\\n\",",
    "                   (int)n, b[0], b[1], b[2], b[3]);",
    "        }",
    "        if (recs >= 4000) break;",
    "    }",
    "    printf(\"RDRPROBE recs=%d total=%ld\\n\", recs, total);",
    "    fclose(f);",
    "    return 0;",
    "}",
]


def rdrprobe_deck():
    d = deck("ONFJRDR", [(RDR_SRC, "RDRPROBE")], (), prelink=True,
             title="ONFLY JCC RDR")
    assert d[-1] == "//"
    d = d[:-1]
    d.append("//LKED     EXEC PGM=IEWL,COND=(4,LT),")
    d.append("//            PARM='NCAL,MAP,LIST,XREF,NORENT'")
    d.append("//SYSLIN   DD DSN=&&OBJMOD,DISP=(OLD,DELETE)")
    d.append("//SYSUT1   DD UNIT=SYSDA,SPACE=(CYL,(5,2))")
    d.append("//SYSPRINT DD SYSOUT=*")
    d.append("//SYSLMOD  DD DSN=&&GOSET(GO),UNIT=SYSDA,")
    d.append("//            SPACE=(4096,(100,20,1)),DISP=(,PASS),")
    d.append("//            DCB=(RECFM=U,BLKSIZE=4096)")
    d.append("//*")
    d.append("//GO       EXEC PGM=*.LKED.SYSLMOD,COND=(4,LT)")
    d.append("//STDOUT   DD SYSOUT=*")
    d.append("//STDERR   DD SYSOUT=*")
    d.append("//SYSPRINT DD SYSOUT=*")
    d.append("//ONFNET   DD UNIT=%s," % mvseng.READER_UNIT)
    d.append("//            DCB=(RECFM=F,LRECL=80,BLKSIZE=80)")
    d.append("//")
    return d


def run_rdrprobe(argv):
    d = rdrprobe_deck()
    if not os.path.isfile(mvsrun.CARDFILE):
        sys.stderr.write("mvsjcc: no card file %s\n" % mvsrun.CARDFILE)
        return 2
    mvseng.console("devinit %s *" % mvseng.READER_DEV)
    staged = mvseng.stage(mvsrun.CARDFILE)
    mvseng.console("devinit %s %s eof"
                   % (mvseng.READER_DEV, staged.replace("\\", "/")))
    sys.stdout.write("mvsjcc: rdrprobe %d cards, reader %s loaded\n"
                     % (len(d), mvseng.READER_DEV))
    before = mvsub.submit(d)
    out = mvsub.collect("ONFJRDR", before, timeout=900)
    if out is None:
        sys.stderr.write("mvsjcc: TIMEOUT waiting for ONFJRDR\n")
        return 1
    for line in out.splitlines():
        s = line.rstrip()
        if (("RDRPROBE " in s or "RC= " in s or "JCC-RC:" in s)
                and "printf" not in s):
            sys.stdout.write(s + "\n")
    return 0


#: How long `--run` waits for JES2's END banner.
#:
#: Four hours, not the two this carried while row 7 was `srext` only.
#: The `path` half is fourteen requests on a 913-neuron network instead
#: of five on a 501-neuron one, and row 6 ran exactly that work TWICE
#: with its GO step costing `CPU 63 min 04.79 s` on a quiet host
#: (ONFPRUN JOB 279) and `CPU 157 min 52.69 s` on one shared with the
#: full-brain campaign (JOB 308) -- the same job, the same engine, the
#: same fourteen requests, two and a half times apart.  JCC's code is
#: 0.874x GCCMVS's cost on the identical `srext` work, so the honest
#: upper bound here is over two hours of GO alone plus thirteen
#: compiles, a PRELINK and a link.
#:
#: The cost of this being too small is not a retry: `collect` returns
#: None and the listing is lost AFTER the CPU has already been spent.
#:
#: D-471 raised it from 14400 s to twelve hours.  D-467's lost `path`
#: run reported only two of fourteen requests after 63 min 51.67 s of
#: GO CPU, so the 0.874 factor above does NOT transfer from `srext` to
#: `path`; a straight scaling suggests about six hours, an estimate
#: from one truncated sample.  `--recover` (D-465) is the backstop.
RUN_TIMEOUT = 43200


def run_run(argv):
    """Submit the run job and recover what it wrote.

    The job is `ONFJRUN` for `srext` and `ONFJPRUN` for `path` (D-462).

    The network reaches the GO step exactly as it reaches row 6's: from
    the catalogued dataset D-286 installed, which both rows read, so
    that row 7 differs from row 6 in the compiler and in nothing else.
    """
    d = run_deck()
    job = jcc_job()
    mvsub.check_cards(d)
    if "--print" in argv:
        sys.stdout.write("\n".join(d) + "\n")
        return 0

    sys.stdout.write("mvsjcc: %s, %d cards, %d translation units, "
                     "longest %d columns, network %s from %s, "
                     "response to %s\n"
                     % (job, len(d), len(mvsrun.UNIT_MEMBERS),
                        max(len(c) for c in d), mvsrun.NETNAME,
                        mvsrun.NET_DSN, jcc_rsp_dsn()))

    t0 = time.time()
    before = mvsub.submit(d)
    out = mvsub.collect(job, before, timeout=RUN_TIMEOUT)
    if out is None:
        sys.stderr.write("mvsjcc: TIMEOUT waiting for %s after %d s\n"
                         % (job, RUN_TIMEOUT))
        return 1
    sys.stdout.write("mvsjcc: %s finished in %.1f s\n"
                     % (job, time.time() - t0))
    return process_run(out, argv)


def run_recover(argv):
    """Process a finished run job's listing straight from the printer.

    D-465, and the same mechanism `tools/mvsrun.py::recover` has had
    since Phase E.  The run job can outlive the process that submitted
    it: `srext` is about sixteen minutes and `path` is HOURS, and a
    submitter that is killed takes nothing with it, because MVS still
    has the job and JES2 still has the output.

    The LAST complete START/END pair is the one taken, not the first: a
    job name that has run before appears in the printer more than once,
    and the earlier listing is a previous run's.

    Without this the only recovery is to run the job again, at another
    one to three hours of TK5.
    """
    job = jcc_job()
    text = mvsub.read_printer()
    starts = [m.start() for m in
              re.finditer(r"START\s+JOB\s+\d+\s+" + re.escape(job)
                           + r"\b", text)]
    ends = [m.end() for m in
            re.finditer(r"END\s+JOB\s+\d+\s+" + re.escape(job) + r"\b",
                         text)]
    if not starts or not ends or ends[-1] < starts[-1]:
        sys.stderr.write("mvsjcc: no completed %s in the printer "
                         "(%d start(s), %d end(s))\n"
                         % (job, len(starts), len(ends)))
        return 1
    out = text[starts[-1]:ends[-1]]
    sys.stdout.write("mvsjcc: recovered %d characters of %s listing from "
                     "the printer\n" % (len(out), job))
    return process_run(out, argv)


def process_run(out, argv):
    """Everything the run job's listing is read for."""
    sys.stdout.write("\n".join(mvsub.summarise(out)) + "\n")
    for n, fp in mvsrun.fingerprints(out):
        sys.stdout.write("mvsjcc: ONF301I request %d FP=%s\n" % (n, fp))
    m = mvsrun.SUMMARY.search(out)
    if m:
        sys.stdout.write("mvsjcc: ONF302I %s OK, %s WARN, %s ERROR\n"
                         % m.groups())

    outdir = None
    for i, a in enumerate(argv):
        if a == "--out" and i + 1 < len(argv):
            outdir = argv[i + 1]
    recs = mvscob.parse_dump(out)
    sys.stdout.write("mvsjcc: recovered %d response records from the "
                     "IDCAMS dump\n" % len(recs))
    want = len(mvsrun.expected_records())
    if len(recs) != want or m is None:
        sys.stderr.write("mvsjcc: %s did not produce %d response "
                         "records (%d recovered, ONF302I %s); nothing "
                         "written\n"
                         % (jcc_job(), want, len(recs),
                            "absent" if m is None else "present"))
        return 1
    if outdir:
        if not os.path.isdir(outdir):
            os.makedirs(outdir)
        path = os.path.join(outdir, "rsp-%s-2c.bin" % mvsrun.NETNAME)
        with open(path, "wb") as f:
            for r in recs:
                f.write(r)
        # Named for the job, so the listing on disk says which half of
        # row 7 produced it -- the same reason D-462 gives the two
        # halves different job names in the first place.
        lst = os.path.join(outdir, "%s.txt" % jcc_job())
        io.open(lst, "w", encoding="ascii", errors="replace",
                newline="").write(out.replace("\r\n", "\n"))
        sys.stdout.write("mvsjcc: wrote %s (%d bytes) and %s\n"
                         % (path, os.path.getsize(path),
                            os.path.basename(lst)))
    return 0


def run_compare(argv):
    """ACC-5 row 7, judged exactly as row 6 was.

    Two comparisons, not one, for the reason tools/mvsrun.py gives: the
    whole-record byte comparison covers the spike counts and latencies a
    fingerprint is a digest OF and would hide, while the golden-suite
    comparison is the only one that checks the fingerprint is what
    Section 8.4 SAYS it is rather than merely what another run produced.

    The x86-64 recording is the comparand for both rows, so a row 6 and
    a row 7 that agree with it agree with each other -- and, unlike a
    direct MVS-to-MVS comparison, a shared defect in the two MVS runs
    cannot make them agree.
    """
    if len(argv) < 2:
        sys.stderr.write("usage: mvsjcc.py --compare <jccdir> <refdir>\n")
        return 2
    jccdir, refdir = argv[0], argv[1]
    why = row7_listing(jccdir)
    if why:
        sys.stderr.write("mvsjcc: refusing to judge %s as ACC-5 row 7: "
                         "%s (D-472)\n" % (jccdir, why))
        return 2
    name = "rsp-%s-2c.bin" % mvsrun.NETNAME
    jcc = mvsrun.read_records(os.path.join(jccdir, name))
    ref = mvsrun.read_records(os.path.join(refdir, name))

    sys.stdout.write("=== ACC-5 row 7: TK5 MVS 3.8j / SOFT2C / JCC ===\n")
    sys.stdout.write("    %s\n    vs %s\n"
                     % (os.path.join(jccdir, name),
                        os.path.join(refdir, name)))
    views, lines = mvsrun.compare_records(jcc, ref, "ONFRSP")
    sys.stdout.write("\n".join(lines) + "\n")
    sys.stdout.write("  raw=%s  binary=%s  translated=%s\n"
                     % (views["raw"], views["binary"], views["translated"]))

    ok = views["translated"]
    off = 20                       # ONF-FPRINT, layout/master.py
    sys.stdout.write("\n=== ACC-5 row 7 vs the Section 8.4 fingerprints "
                     "===\n")
    gold = mvsrun.golden_fingerprints(refdir)
    if len(gold) != len(jcc):
        sys.stdout.write("  FAIL %d golden entries, %d JCC records\n"
                         % (len(gold), len(jcc)))
        ok = False
    for (gid, wantfp), rec in zip(gold, jcc):
        got = rec[off:off + 4].hex().upper()
        good = got == wantfp
        ok = ok and good
        sys.stdout.write("  %-4s %-5s fp=%s  golden=%s\n"
                         % ("ok" if good else "FAIL", gid, got, wantfp))
    sys.stdout.write("mvsjcc: ACC-5 row 7 %s (%s, measured %s)\n"
                     % ("PASS" if ok else "FAIL", mvsrun.NETNAME, jccdir))
    return 0 if ok else 1


#: The first JES2 separator banner of a listing: `START JOB nnn NAME`.
JES2_START = re.compile(r"START\s+JOB\s+(\d+)\s+(\S+)")


def row7_listing(jccdir):
    """Why `jccdir` is not row 7's recording for this network, or None.

    D-472, adopting P-38 in its strong form.  `--compare` used to label
    whatever directory it was given "ACC-5 row 7", and on 2026-09-18 it
    printed a PASS over row 6's GCCMVS records.  Row 7's recording is
    the directory `process_run()` writes: the response file beside the
    listing `<job>.txt`, where <job> is `jcc_job()` for the selected
    network (D-462).  The listing's NAME alone proves nothing, since a
    file can be renamed, so its first JES2 START banner must name the
    same job.  What this cannot prove is which compiler ran: that rests
    on the job name being row 7's and nothing else submitting it.
    """
    job = jcc_job()
    lst = os.path.join(jccdir, "%s.txt" % job)
    if not os.path.isfile(lst):
        return "no %s.txt listing there" % job
    with io.open(lst, encoding="ascii", errors="replace") as f:
        m = JES2_START.search(f.read(4096))
    if m is None:
        return "%s.txt carries no JES2 START banner" % job
    if m.group(2) != job:
        return ("%s.txt is JOB %s %s, not %s"
                % (job, m.group(1), m.group(2), job))
    return None


USAGE = ("usage: python tools/mvsjcc.py [--net srext|path] --probe "
         "| --ddprobe | --ccprobe | --rdrprobe | --mini <which> "
         "| --run [--out DIR] | --recover [--out DIR] "
         "| --compare <jccdir> <refdir>")


def take_net(argv):
    """Consume a leading `--net NAME` and point `mvsrun` at it.

    Until 2026-09-18 this file REFUSED --net outright, because row 7 was
    the `srext` half of Section 8.4 and nothing else, and because
    tools/mvsrun.py does take --net while the two modules share
    `select()` state: a reader who assumed the option worked would have
    got a job that silently ran the wrong network under the right job
    name.  D-458 makes the `path` half this session's scope and D-462
    gives each network its own job name and response dataset, so that
    failure mode is gone by construction rather than by refusal.  What
    the refusal was protecting is now asserted in `check_names()`, which
    every deck goes through.

    `srext` stays the default, so every existing caller that says no
    --net behaves exactly as before (D-259).
    """
    rest = []
    i = 0
    while i < len(argv):
        if argv[i] == "--net":
            if i + 1 >= len(argv):
                sys.stderr.write("mvsjcc: --net needs a network name "
                                 "(one of %s)\n" % ", ".join(
                                     sorted(JCC_NAMES)))
                return None
            name = argv[i + 1]
            if name not in JCC_NAMES:
                sys.stderr.write("mvsjcc: unknown network %r; row 7 "
                                 "knows %s\n"
                                 % (name, ", ".join(sorted(JCC_NAMES))))
                return None
            mvsrun.select(name)
            i += 2
            continue
        rest.append(argv[i])
        i += 1
    return rest


def main(argv):
    argv = take_net(argv)
    if argv is None:
        return 2
    if not argv:
        print(USAGE)
        return 2
    if argv[0] == "--probe":
        return run_probe(argv[1:])
    if argv[0] == "--ddprobe":
        return run_ddprobe(argv[1:])
    if argv[0] == "--ccprobe":
        return run_ccprobe(argv[1:])
    if argv[0] == "--rdrprobe":
        return run_rdrprobe(argv[1:])
    if argv[0] == "--mini":
        return run_mini(argv[1:])
    if argv[0] == "--run":
        # D-328.  Only --run: it is the ACC-5 row 7 job, 22 steps and
        # about 16 minutes of TK5 for `srext` -- and one to three HOURS
        # for `path`, which is what RUN_TIMEOUT is sized against.  The
        # probes above finish in a minute or two and a window for one
        # would outlive the thing it watches.
        if "--print" not in argv and "--no-window" not in argv:
            try:
                sys.path.insert(0, os.path.join(ROOT, "tools"))
                import progress as _pg
                _pg.spawn_window()
            except Exception as exc:
                sys.stdout.write("mvsjcc: no progress window (%s)\n"
                                 % exc)
        return run_run(argv[1:])
    if argv[0] == "--recover":
        return run_recover(argv[1:])
    if argv[0] == "--compare":
        return run_compare(argv[1:])
    print(USAGE)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
