# -*- coding: utf-8 -*-
"""Gate G4, MVS half: compile and run ONFLYDRV under MVT COBOL on TK5.

Gate G4 asks two things (SRS 9.1): does COPY work under the OS/360 MVT
ANS COBOL compiler (IKFCBL00), and does the driver skeleton pass the
Enterprise COBOL proxy.  tests/run_cob.py answers the second on x86.
This script answers the first on the real compiler, and goes one step
further: the driver is RUN in request mode and the dataset it writes
is hex-dumped back to the listing by IDCAMS, so the bytes MVT COBOL
produced are compared against the Python packing of the same cards.
That is TU-07's "sentinel values round-tripped through ONFLYDRV" half.

THE JOB
-------
  SCRATCH/ALLOC   fresh FB/80 libraries for the copybook and the source
  WRITEL, WRITES  IEBUPDTE writes generated/ONFCOM.cpy as COBLIB(ONFCOM)
                  and cobol/ONFLYDRV.cbl as COBSRC(ONFLYDRV)
  COB             IKFCBL00 with COBLIB on SYSLIB, the PARM of TK5's own
                  SYS2.PROCLIB(COBUCLG) plus LIB for the COPY facility
  LKED            IEWL against SYS1.COBLIB, as COBUCLG does
  GO              MODE=REQ over inline cards -> HERC01.ONFLY.G4REQ,
                  RECFM=FB,LRECL=412
  DUMP            IDCAMS PRINT ... DUMP of that dataset
  GO2             MODE=RPT reading G4REQ back as ONFRSP -> ONFRPT on
                  SYSOUT, so the READ INTO and edited-move path is also
                  exercised on MVT COBOL (extra evidence, not a gate
                  criterion)

The DD names, dataset attributes and step conditioning follow
IR-JCL-01 and IR-JCL-04.  The proc itself is not used: every card is
in this file so the deck can be read without a TK5 to hand, exactly
as tools/mvsbld.py does for GCCMVS.

WHAT THE LISTING IS READ FOR
----------------------------
  * step condition codes and any COB diagnostics (IKF...)
  * the IDCAMS dump, parsed back into bytes and compared to the
    expected records with the stimulus code in EBCDIC
  * the ONF401E / ONF302I lines the driver DISPLAYs
  * the RPT echo lines

Run:  python tools/mvscob.py [--print] [--parm '...'] [--no-rpt]
      python tools/mvscob.py --copy68 [--print]   the COBOL-68 COPY probe
"""
import io
import os
import re
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "generated"))

import mvsub  # noqa: E402
import onfcom_py as L  # noqa: E402

JOB = "ONFCOB"
USER = "HERC01"
LIB_DSN = "%s.ONFLY.COBLIB" % USER
SRC_DSN = "%s.ONFLY.COBSRC" % USER
REQ_DSN = "%s.ONFLY.G4REQ" % USER
DLM = "ZZ"
JCL_FIELD = 71

# TK5's SYS2.PROCLIB(COBUCLG) PARM, read back from the running system
# on 2026-09-12 (job ONFPROC), with LIB added so the compiler reads
# COPY text from SYSLIB.
DEFAULT_PARM = "LOAD,SUPMAP,SIZE=2048K,BUF=1024K,LIB"

# The cards run on MVS: one per spelling D-159 allows, plus a comment,
# plus one bad card so ONF401E is seen on the real compiler too.  The
# expected records exclude the bad card and the comment.
CARDS = [
    ("MODE=REQ", None),
    ("* GATE G4 CONTROL CARDS (IR-JCL-02)", None),
    ("SUGR 0120 1000 000000001", ("SUGR", 120, 1000, 1)),
    ("SUGR   40 1000         1", ("SUGR", 40, 1000, 1)),
    ("SUGR 0000 1000 999999999", ("SUGR", 0, 1000, 999999999)),
    ("WATR  200    1         0", ("WATR", 200, 1, 0)),
    ("SUGR 12X0 1000 000000001", "bad"),
    ("SUGR 9999 1300         7", ("SUGR", 9999, 1300, 7)),
]


class DeckError(Exception):
    pass


def cards_of(relpath):
    text = io.open(os.path.join(ROOT, relpath), encoding="ascii").read()
    out = []
    for n, line in enumerate(text.splitlines(), 1):
        line = line.rstrip()
        if len(line) > 80:
            raise DeckError("%s line %d is %d columns" % (relpath, n, len(line)))
        if line.startswith("./") or line.startswith("//") or line == DLM:
            raise DeckError("%s line %d would be taken as JCL or IEBUPDTE "
                            "control: %r" % (relpath, n, line))
        out.append(line)
    return out


def expected_records():
    recs = []
    for text, exp in CARDS:
        if isinstance(exp, tuple):
            code, rate, ms, seed = exp
            head = struct.pack(L.HEAD_FMT, code.ljust(8).encode("cp037"),
                               seed, rate, ms, 0, 0, b"\0\0\0\0", 0)
            recs.append(head + struct.pack(L.OUT_FMT, 0, 0, 0, b"\0\0") * L.MAX_OUT)
    return recs


def deck(parm=DEFAULT_PARM, with_rpt=True):
    d = []

    def a(card):
        if card.startswith("//") and len(card) > JCL_FIELD:
            raise DeckError("JCL card exceeds column %d: %s" % (JCL_FIELD, card))
        d.append(card)

    a("//%-8s JOB (001),'ONFLY G4 COBOL',CLASS=A,MSGCLASS=A," % JOB)
    a("//             USER=%s,PASSWORD=CUL8TR," % USER)
    a("//             REGION=4M,TIME=1440,MSGLEVEL=(1,1)")
    a("//*")
    a("//SCRATCH  EXEC PGM=IEFBR14")
    for n, dsn in enumerate((LIB_DSN, SRC_DSN, REQ_DSN), 1):
        a("//D%d       DD DSN=%s,DISP=(MOD,DELETE)," % (n, dsn))
        a("//            UNIT=SYSDA,SPACE=(TRK,(1,1))")
    a("//*")
    a("//ALLOC    EXEC PGM=IEFBR14")
    for n, dsn in enumerate((LIB_DSN, SRC_DSN), 1):
        a("//M%d       DD DSN=%s,DISP=(,CATLG,DELETE)," % (n, dsn))
        a("//            UNIT=SYSDA,SPACE=(TRK,(10,5,5)),")
        a("//            DCB=(RECFM=FB,LRECL=80,BLKSIZE=3200)")
    a("//*")
    # The copybook library is still written so that --copy68 can probe
    # MVT's own COPY form against it; the driver itself is the GENERATED
    # source with the layout expanded (D-161), so the COB step below
    # needs SYSLIB only for that probe.
    for step, dsn, member, relpath in (
            ("WRITEL", LIB_DSN, "ONFCOM", "generated/ONFCOM.cpy"),
            ("WRITES", SRC_DSN, "ONFLYDRV", "generated/ONFLYDRV.cbl")):
        a("//%-8s EXEC PGM=IEBUPDTE,PARM=NEW" % step)
        a("//SYSPRINT DD SYSOUT=*")
        a("//SYSUT2   DD DSN=%s,DISP=OLD" % dsn)
        a("//SYSIN    DD DATA,DLM='%s'" % DLM)
        a("./ ADD NAME=%s" % member)
        d.extend(cards_of(relpath))
        a("./ ENDUP")
        a(DLM)
        a("//*")
    # --- compile: SYS2.PROCLIB(COBUCLG)'s COB step, spelled out ------
    a("//COB      EXEC PGM=IKFCBL00,")
    a("//            PARM='%s'" % parm)
    a("//SYSPRINT DD SYSOUT=*")
    # Without SYSPUNCH the compiler says IEC130I twice and carries on;
    # a DUMMY keeps the listing to real diagnostics (measured 2026-09-12).
    a("//SYSPUNCH DD DUMMY")
    for n in range(1, 5):
        a("//SYSUT%d   DD UNIT=SYSDA,SPACE=(460,(700,100))" % n)
    a("//SYSLIN   DD DSN=&&LOADSET,DISP=(MOD,PASS),UNIT=SYSDA,")
    a("//            SPACE=(80,(500,100))")
    a("//SYSLIB   DD DSN=%s,DISP=SHR" % LIB_DSN)
    a("//SYSIN    DD DSN=%s(ONFLYDRV),DISP=SHR" % SRC_DSN)
    a("//*")
    a("//LKED     EXEC PGM=IEWL,PARM='LIST,XREF,LET',COND=(5,LT,COB)")
    a("//SYSLIN   DD DSN=&&LOADSET,DISP=(OLD,DELETE)")
    a("//SYSLMOD  DD DSN=&&GODATA(RUN),DISP=(NEW,PASS),UNIT=SYSDA,")
    a("//            SPACE=(1024,(50,20,1))")
    a("//SYSLIB   DD DSN=SYS1.COBLIB,DISP=SHR")
    a("//SYSUT1   DD UNIT=SYSDA,SPACE=(1024,(50,20))")
    a("//SYSPRINT DD SYSOUT=*")
    a("//*")
    # --- run, request mode ------------------------------------------
    a("//GO       EXEC PGM=*.LKED.SYSLMOD,COND=((5,LT,COB),(5,LT,LKED))")
    a("//SYSOUT   DD SYSOUT=*")
    a("//SYSPRINT DD SYSOUT=*")
    a("//ONFREQ   DD DSN=%s,DISP=(,CATLG,DELETE)," % REQ_DSN)
    a("//            UNIT=SYSDA,SPACE=(TRK,(2,1)),")
    a("//            DCB=(RECFM=FB,LRECL=412,BLKSIZE=4120)")
    a("//ONFCTL   DD *")
    for text, _ in CARDS:
        a(text)
    a("/*")
    a("//*")
    # --- hex dump of what was written --------------------------------
    a("//DUMP     EXEC PGM=IDCAMS,COND=((5,LT,COB),(5,LT,LKED))")
    a("//SYSPRINT DD SYSOUT=*")
    a("//ONFREQ   DD DSN=%s,DISP=SHR" % REQ_DSN)
    a("//SYSIN    DD *")
    a("  PRINT INFILE(ONFREQ) DUMP")
    a("/*")
    a("//*")
    if with_rpt:
        a("//GO2      EXEC PGM=*.LKED.SYSLMOD,COND=((5,LT,COB),(5,LT,LKED))")
        a("//SYSOUT   DD SYSOUT=*")
        a("//SYSPRINT DD SYSOUT=*")
        a("//ONFRSP   DD DSN=%s,DISP=SHR" % REQ_DSN)
        a("//ONFRPT   DD SYSOUT=*,DCB=(RECFM=FBA,LRECL=133,BLKSIZE=133)")
        a("//ONFCTL   DD *")
        a("MODE=RPT")
        a("/*")
    a("//")
    return d


# ---------------------------------------------------------------------------
# The COPY probe (VL-57).  Gate G4's literal question is "does COPY work
# in MVT COBOL".  The first driver build answered: not the standalone
# statement (IKF1041I-E).  This program asks about the COBOL-68 form
# `01 name COPY member.` -- the only form IKFCBL00 documents -- against
# the same copybook library, and prints through the copied fields so
# that "compiled" also means "the layout resolved".
# ---------------------------------------------------------------------------
COPY68_PROG = [
    "       IDENTIFICATION DIVISION.",
    "       PROGRAM-ID. ONFCPY68.",
    "       ENVIRONMENT DIVISION.",
    "       CONFIGURATION SECTION.",
    "       SOURCE-COMPUTER. IBM-370.",
    "       OBJECT-COMPUTER. IBM-370.",
    "       DATA DIVISION.",
    "       WORKING-STORAGE SECTION.",
    "       01  ONF-COMMAREA COPY ONFCOM.",
    "       PROCEDURE DIVISION.",
    "       MAIN-PARA.",
    "           MOVE 7 TO ONF-RC.",
    "           MOVE 2 TO ONF-OUT-COUNT.",
    "           MOVE 5 TO ONF-OUT-ID (2).",
    "           DISPLAY 'ONFCPY68 RC=' ONF-RC ' OUT=' ONF-OUT-COUNT",
    "               ' ID2=' ONF-OUT-ID (2).",
    "           STOP RUN.",
]


def copy68_deck(parm=DEFAULT_PARM):
    """A job that compiles, links and runs COPY68_PROG against the
    copybook library the main job leaves behind (HERC01.ONFLY.COBLIB)."""
    d = []

    def a(card):
        if card.startswith("//") and len(card) > JCL_FIELD:
            raise DeckError("JCL card exceeds column %d: %s" % (JCL_FIELD, card))
        d.append(card)

    a("//ONFCPY68 JOB (001),'ONFLY G4 COPY68',CLASS=A,MSGCLASS=A,")
    a("//             USER=%s,PASSWORD=CUL8TR,REGION=4M,MSGLEVEL=(1,1)" % USER)
    a("//COB      EXEC PGM=IKFCBL00,")
    a("//            PARM='%s'" % parm)
    a("//SYSPRINT DD SYSOUT=*")
    a("//SYSPUNCH DD DUMMY")
    for n in range(1, 5):
        a("//SYSUT%d   DD UNIT=SYSDA,SPACE=(460,(700,100))" % n)
    a("//SYSLIN   DD DSN=&&LOADSET,DISP=(MOD,PASS),UNIT=SYSDA,")
    a("//            SPACE=(80,(500,100))")
    a("//SYSLIB   DD DSN=%s,DISP=SHR" % LIB_DSN)
    a("//SYSIN    DD *")
    d.extend(COPY68_PROG)
    a("/*")
    a("//LKED     EXEC PGM=IEWL,PARM='LIST,XREF,LET',COND=(5,LT,COB)")
    a("//SYSLIN   DD DSN=&&LOADSET,DISP=(OLD,DELETE)")
    a("//SYSLMOD  DD DSN=&&GODATA(RUN),DISP=(NEW,PASS),UNIT=SYSDA,")
    a("//            SPACE=(1024,(50,20,1))")
    a("//SYSLIB   DD DSN=SYS1.COBLIB,DISP=SHR")
    a("//SYSUT1   DD UNIT=SYSDA,SPACE=(1024,(50,20))")
    a("//SYSPRINT DD SYSOUT=*")
    a("//GO       EXEC PGM=*.LKED.SYSLMOD,COND=((5,LT,COB),(5,LT,LKED))")
    a("//SYSOUT   DD SYSOUT=*")
    a("//SYSPRINT DD SYSOUT=*")
    a("//")
    return d


def run_copy68(argv):
    d = copy68_deck()
    mvsub.check_cards(d)
    if "--print" in argv:
        sys.stdout.write("\n".join(d) + "\n")
        return 0
    before = mvsub.submit(d, codepage=False)
    out = mvsub.collect("ONFCPY68", before, timeout=180)
    if out is None:
        sys.stderr.write("mvscob: ONFCPY68 did not finish\n")
        return 1
    for l in out.splitlines():
        if re.search(r"COND CODE|IKF\d{4}I|ONFCPY68 RC=|CARD   ERROR", l):
            sys.stdout.write("  %s\n" % l.rstrip()[:116])
    ok = "ONFCPY68 RC=0007 OUT=0002 ID2=000000005" in out
    sys.stdout.write("  %s\n" % ("PASS: the COBOL-68 form '01 name COPY member.'"
                                 " resolves the generated copybook on IKFCBL00"
                                 if ok else "FAIL: see above"))
    return 0 if ok else 1


# IDCAMS PRINT DUMP: an offset of six hex digits, then up to eight
# groups of eight hex digits, then a character rendering between
# asterisks.  The rendering is ignored; only the hex is trusted.
DUMP_LINE = re.compile(r"^\s*([0-9A-F]{6})\s+((?:[0-9A-F]{8}\s+){1,8})")
RECNO = re.compile(r"RECORD SEQUENCE NUMBER\s*-\s*(\d+)")


def parse_dump(listing):
    """Return the records IDCAMS dumped, as bytes, in order."""
    recs = []
    cur = None
    for line in listing.splitlines():
        m = RECNO.search(line)
        if m:
            cur = bytearray()
            recs.append(cur)
            continue
        if cur is None:
            continue
        m = DUMP_LINE.match(line)
        if m:
            off = int(m.group(1), 16)
            if off != len(cur):
                # a gap or a repeated line would mean the dump format is
                # not what this parser expects; refuse rather than guess
                raise DeckError("dump offset %06X but %d bytes parsed so far"
                                % (off, len(cur)))
            cur.extend(bytes.fromhex(m.group(2).replace(" ", "")))
    return [bytes(r) for r in recs]


def compare(recs):
    want = expected_records()
    lines = []
    ok = True
    if len(recs) != len(want):
        lines.append("dumped %d records, expected %d" % (len(recs), len(want)))
        ok = False
    for i, (g, w) in enumerate(zip(recs, want)):
        if g == w:
            lines.append("record %d: %d bytes, identical to the Python packing"
                         " (head %s)" % (i + 1, len(g), g[:L.HEAD_LEN].hex()))
        else:
            ok = False
            k = next((j for j in range(min(len(g), len(w)))
                      if g[j:j + 1] != w[j:j + 1]), min(len(g), len(w)))
            lines.append("record %d: DIFFERS at byte %d (len %d vs %d)\n"
                         "    got  %s\n    want %s"
                         % (i + 1, k, len(g), len(w), g[:32].hex(), w[:32].hex()))
    return ok, lines


def main(argv):
    try:
        sys.stdout.reconfigure(errors="replace")
    except (AttributeError, ValueError):
        pass
    parm = DEFAULT_PARM
    for i, a in enumerate(argv):
        if a == "--parm" and i + 1 < len(argv):
            parm = argv[i + 1]
    if "--copy68" in argv:
        return run_copy68(argv)
    d = deck(parm=parm, with_rpt="--no-rpt" not in argv)
    mvsub.check_cards(d)
    if "--print" in argv:
        sys.stdout.write("\n".join(d) + "\n")
        return 0

    # The deck carries no C source, so the 819/1047 codepage that
    # GCCMVS needs (D-103) is not a precondition here; every character
    # in COBOL source and JCL has the same code point on every page
    # Hercules offers.
    before = mvsub.submit(d, codepage=False)
    out = mvsub.collect(JOB, before, timeout=300, poll=2)
    if out is None:
        sys.stderr.write("mvscob: %s did not finish\n" % JOB)
        return 1
    if not os.path.isdir(os.path.join(ROOT, "build")):
        os.makedirs(os.path.join(ROOT, "build"))
    lst = os.path.join(ROOT, "build", "onfcob.lst")
    io.open(lst, "w", encoding="latin-1", newline="\n").write(out)
    sys.stdout.write("mvscob: listing saved to %s (%d lines)\n"
                     % (os.path.relpath(lst, ROOT), len(out.splitlines())))

    sys.stdout.write("=== step results ===\n")
    for line in mvsub.summarise(out):
        sys.stdout.write("  %s\n" % line[:116])

    sys.stdout.write("=== compiler diagnostics (IKF) ===\n")
    ikf = [l.rstrip() for l in out.splitlines() if re.search(r"\bIKF\d{4}I", l)]
    for l in ikf[:40] or ["  (none)"]:
        sys.stdout.write("  %s\n" % l.strip()[:116])

    sys.stdout.write("=== driver messages ===\n")
    for l in out.splitlines():
        if re.search(r"ONF\d{3}[IWES]", l):
            sys.stdout.write("  %s\n" % l.strip()[:116])

    sys.stdout.write("=== IDCAMS dump vs Python packing ===\n")
    try:
        recs = parse_dump(out)
    except DeckError as e:
        sys.stdout.write("  parse error: %s\n" % e)
        recs = []
    ok, lines = compare(recs)
    for l in lines:
        sys.stdout.write("  %s\n" % l)

    rpt_ok = True
    if "--no-rpt" not in argv:
        sys.stdout.write("=== RPT echo (GO2), as printed by MVS ===\n")
        # The report is FBA: the Hercules printer file keeps the ANSI
        # control character the driver wrote as column 1 ('1' for the
        # title, ' ' for a line) and the text must follow intact from
        # its first character.  Before the driver supplied that byte
        # itself, MVT COBOL consumed the first letter of every line
        # (VL-59).  Source lines that DISPLAY or VALUE these strings
        # are excluded by anchoring the match at column 1 or 2.
        echo = [l.rstrip() for l in out.splitlines()
                if re.match(r"^[ 01+-]?(ONFLY REPORT|REQUEST +\d+ CODE=|"
                            r"  READOUT +\d+ ID=)", l)]
        for l in echo:
            sys.stdout.write("  |%s\n" % l[:116])
        echo = [l[1:] if l and l[0] in " 01+-" and not
                l.startswith("  READOUT") else l for l in echo]
        n_req = sum(1 for l in echo if l.startswith("REQUEST"))
        rpt_ok = (len(echo) >= 1 and echo[0].startswith("ONFLY REPORT")
                  and n_req == len(expected_records()))
        sys.stdout.write("  %s\n" % ("echo intact: title plus %d request lines"
                                     % n_req if rpt_ok else
                                     "echo NOT intact (first character lost, "
                                     "or lines missing)"))

    cc = re.findall(r"IEF142I ONFCOB (\w+) - STEP WAS EXECUTED - COND CODE (\d{4})", out)
    codes = dict(cc)
    sys.stdout.write("=== verdict ===\n")
    sys.stdout.write("  condition codes: %s\n"
                     % ", ".join("%s=%s" % kv for kv in cc))
    passed = ok and rpt_ok and codes.get("COB") in ("0000", "0004") \
        and codes.get("LKED") in ("0000", "0004") and codes.get("GO") == "0008"
    sys.stdout.write("  %s\n" % ("PASS: the generated driver (layout inlined, "
                                 "D-161) compiled under IKFCBL00, ran in both "
                                 "modes, and every record MVT COBOL wrote "
                                 "equals the Python packing (GO ends 8 because "
                                 "of the deliberate bad card)"
                                 if passed else "FAIL: see above"))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
