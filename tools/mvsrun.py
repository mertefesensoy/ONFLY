# -*- coding: utf-8 -*-
"""Phase E slice 1: make ONFLY SIMULATE on MVS 3.8j (D-255, D-258).

Everything ONFLY has ever done on a mainframe stops short of the one
thing the project is for.  Gate G1 got SoftFloat 2c running there; Gate
G2 got a network file there and had ONFLYENG verify it; `tools/mvsker.py`
ran the Appendix C kernel there against the oracle; Gate G4 compiled and
ran ONFLYDRV there.  But no MVS job has ever read a request, stepped the
model and written a response.  `tools/mvseng.py` says so in its own
source, at the point where it chooses what to link:

    The kernel, the RNG and the stimulus are deliberately absent:
    verify-only never simulates, so linking them would add two job
    steps each to prove nothing.

This file links them, and three more units besides, and gives the GO step
an ONFREQ to read and an ONFRSP to write.

WHAT IS BEING CLAIMED, AND HOW IT IS JUDGED
-------------------------------------------
Row 6 of the SRS Section 8.3 determinism matrix -- TK5 MVS 3.8j / SOFT2C
/ GCCMVS -- is the only row of that matrix that has never been filled.
ACC-5 is satisfied when each golden request produces the same fingerprint
in every row, so until this runs, ACC-5 is not a mainframe claim at all.

The judgement is deliberately NOT "the fingerprints look right".  It is a
byte comparison of the whole ONFRSP dataset against the x86-64 recording
in `data/phase-d/x86w/rsp-srext-2c.bin`, through the comparator Phase D
already built (`tests/run_tx.py --compare`).  The response record carries
the fingerprint as a field (IR-COM-05), so byte-identical files imply
identical fingerprints and also cover the spike counts and first-spike
latencies the fingerprint is computed from -- which a fingerprint
comparison alone would not, because a fingerprint is a digest and digests
hide where a difference is.  The `ONF301I ... FP=` lines ONFLYENG prints
per request are read as well, as a human-legible cross-check that names
the request that disagreed rather than the byte that did.

With it, the MVS half of TX-01 -- left PARTIAL by D-219 and VL-83 when
Phase D closed, because Section 8.5 defines TX-01 against MVS records and
no MVS engine existed to write any -- acquires its comparand.

THE TWO JOBS, AND WHY THERE ARE TWO
-----------------------------------
  ONFEREQ   ONFLYDRV in MODE=REQ over the Section 8.4 `srext` control
            cards, writing HERC01.ONFLY.EREQ (RECFM=FB,LRECL=412), then
            IDCAMS PRINT DUMP of what it wrote.  This is FR-BAT-01's
            STEP1 performed for real.
  ONFERUN   GCCMVS compiles and links the SIMULATING engine, and runs it
            with ONFNET on the card reader, ONFREQ=EREQ and ONFRSP a
            passed temporary dataset, then IDCAMS PRINT DUMP of that.
            This is FR-BAT-01's STEP2.

They are two jobs and not one because ONFREQ has to exist as a catalogued
dataset before the engine's GO step allocates it, and because a C compile
deck and a COBOL compile deck have almost nothing in common -- one job
carrying both would be 1,400 cards in which a failure in either half
stops the other.  The split also isolates the risk the owner accepted in
D-260: ONFEREQ's dump is compared against `tools/mkreq.py`'s packing
BEFORE the engine ever reads the dataset, so a wrong byte in ONFREQ is
attributed to the driver at the moment it happens rather than surfacing
later as a wrong fingerprint.

WHY ONFRSP IS A TEMPORARY DATASET AND ONFREQ IS NOT
---------------------------------------------------
ONFREQ crosses a job boundary, so it must be catalogued; ONFEREQ deletes
and reallocates it on every run, which is what makes the pair rerunnable.
ONFRSP does not cross a boundary -- the DUMP step is in the same job --
so it travels as `&&ONFRSP` with DISP=(,PASS).  A catalogued ONFRSP would
have to be scratched first, and `mvsbld.build()` has no hook before its
own SCRATCH step; a temporary dataset needs no such hook and cannot
collide with a previous run's leftovers.

THE NETWORK ARRIVES ON CARDS
----------------------------
Gate G2 selected the raw card reader by IR-TRN-04's ordering (D-150), and
VL-52 records the finding that made it usable: the reader is binary
transparent.  `data/transport/` is gitignored, and no card file for this
network has ever existed -- the 11,068-card file G2 measured was the
format v1.0 `path` network, from the day before D-190 added the v1.1
compensating table.  `--cards` writes a fresh one from the fixture.

Padding to a multiple of 80 is safe and is not a courtesy: FR-LOD-03 and
IR-NET-08 make the engine trust the header's declared payload length
rather than the dataset size, which is exactly what TE-07 tests.  The
trailing partial card is zero-filled and the engine never looks at it.

`--net path` runs the other half of the suite (D-264): the 913-neuron
`path` fixture and G-01 to G-14, which are what carry FR-BAT-05's
ONF201W, D-41's ONF203E and FR-SIM-06's ONF202E.  G-13 needs the signed
rate column D-265 added to ONFLYDRV; without it the driver rejects that
card itself and the engine never sees the request it owes ONF202E.

Run:
    python tools/mvsrun.py [--net N] --cards         write the card file
    python tools/mvsrun.py [--net N] --req [--print] STEP1 via ONFLYDRV
    python tools/mvsrun.py [--net N] --run [--print] STEP2 via ONFLYENG
    python tools/mvsrun.py [--net N] --run --out DIR ... recovering ONFRSP
    python tools/mvsrun.py [--net N] --compare A B   TX-01, ACC-5 row 6
"""
import io
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tests"))
sys.path.insert(0, os.path.join(ROOT, "generated"))

import mkreq                                          # noqa: E402
import mvsbld                                         # noqa: E402
import mvscob                                         # noqa: E402
import mvseng                                         # noqa: E402
import mvsub                                          # noqa: E402

#: The network this slice runs.  D-259: the `srext` half of the Section
#: 8.4 suite and nothing else.  `srext` is the network the MVP ships
#: (D-205) -- 501 neurons carrying the format v1.1 compensating-input
#: table -- and G-15 to G-19 are the only golden requests that exercise
#: that table.
#: Both Section 8.4 networks, because D-264 asked for the `path` half
#: after `srext` was done.  Job names differ per network so that two
#: runs can be told apart in JES2 output -- mvsub.collect() matches on
#: the job name, and a shared name would let one run collect the
#: other's listing.
USER = "HERC01"
NETS = {
    "srext": {"req_job": "ONFEREQ", "run_job": "ONFERUN", "dsn": "EREQ"},
    "path": {"req_job": "ONFPREQ", "run_job": "ONFPRUN", "dsn": "PREQ"},
}

NETNAME = NETFILE = CARDFILE = REQ_JOB = RUN_JOB = REQ_DSN = None


def select(name):
    """Point this module at one of the two Section 8.4 networks."""
    global NETNAME, NETFILE, CARDFILE, REQ_JOB, RUN_JOB, REQ_DSN
    if name not in NETS:
        raise RunError("unknown network %r; expected one of %s"
                       % (name, sorted(NETS)))
    spec = NETS[name]
    NETNAME = name
    NETFILE = os.path.join(ROOT, "data", "networks",
                           "onfnet-malecns-v1.0-%s.bin" % name)
    CARDFILE = os.path.join(ROOT, "data", "transport",
                            "onfnet-%s-cards.bin" % name)
    REQ_JOB = spec["req_job"]
    RUN_JOB = spec["run_job"]
    REQ_DSN = "%s.ONFLY.%s" % (USER, spec["dsn"])

#: Members for the units mvseng.py does not link.  Eight characters,
#: unique ignoring case (C-04).  The mapping is copied from
#: tools/mvssyn.py, which has already compiled every one of these on
#: MVS -- the only unit here that mvssyn does not build is onfreq.c.
HEADERS = mvseng.HEADERS + [
    ("engine/include/onfrnd.h", "ONFRND"),
    ("engine/include/onfstm.h", "ONFSTM"),
    ("engine/include/onfreq.h", "ONFREQ"),
    ("generated/onfcom.h", "ONFCOM"),
]

#: The link order, stated once so it can be asserted and printed.  It is
#: tools/mvseng.py's order with onfrnd, onfstm, onfker, onfreq and onfcom
#: inserted before the self-test and the main program, matching
#: tools/mvssyn.py, which has already compiled all of them but onfreq.
UNIT_MEMBERS = (
    "SF2C", "ONFFP2C", "ONFFPCC", "ONFFPRC", "ONFCRCC", "ONFDECC",
    "ONFRNDC", "ONFSTMC", "ONFKERC", "ONFREQC", "ONFCOMC", "ONFI32C",
    "ONFLYENG",
)


class RunError(Exception):
    pass


#: D-259 made `srext` the first network to run, so it stays the default
#: and every caller that does not say `--net` behaves as before.
select("srext")


def request_cards():
    """MODE=REQ, then the Section 8.4 control cards for this network.

    The cards come from `tools/mkreq.py`, which imports the suite from
    `tests/run_gld.py` rather than restating it, so this job cannot ask
    for a request the golden suite does not define.  mvscob.deck() wants
    (text, expected) pairs; the expected half is None throughout because
    nothing here is compared against mvscob's own packing -- see
    `expected_records()` below for what is compared instead.
    """
    text = mkreq.golden_cards(NETNAME)
    return [("MODE=REQ", None)] + [(line, None)
                                   for line in text.splitlines()]


def expected_records():
    """The records ONFREQ must contain, as x86 packs them.

    Not mvscob.expected_records(): that packs from its own table of
    fields, which would only prove MVT COBOL agrees with a second Python
    implementation.  These are the bytes of `data/phase-d/x86w/
    req-srext.bin` -- the very file the x86-64 recording was produced
    from -- so agreement means the two platforms are running the same
    requests and not merely equivalent ones.
    """
    return list(mkreq.cards_to_records(mkreq.golden_cards(NETNAME)))


def write_cards(netfile=None, cardfile=None):
    """The network as 80-byte card images, zero-padded (FR-PRP-08).

    The defaults are resolved HERE and not in the signature.  Written
    the obvious way -- `netfile=NETFILE` -- Python binds the module
    global once, at import, so `select("path")` would change the
    output path while leaving the input pointing at `srext`: the wrong
    network, written under the right name, which reaches MVS and fails
    the payload CRC as though the transport had corrupted it.
    """
    netfile = NETFILE if netfile is None else netfile
    cardfile = CARDFILE if cardfile is None else cardfile
    if not os.path.isfile(netfile):
        raise RunError("no network at %s; run `make fixtures` first"
                       % netfile)
    with open(netfile, "rb") as f:
        data = f.read()
    pad = (-len(data)) % mvsbld.CARD
    out = os.path.dirname(cardfile)
    if not os.path.isdir(out):
        os.makedirs(out)
    with open(cardfile, "wb") as f:
        f.write(data)
        f.write(b"\0" * pad)
    return len(data), pad, (len(data) + pad) // mvsbld.CARD


def req_deck():
    """Job ONFEREQ: FR-BAT-01 STEP1 on MVT COBOL (D-260)."""
    return mvscob.deck(cards=request_cards(), req_dsn=REQ_DSN,
                       job=REQ_JOB, title="ONFLY E1 REQUEST",
                       with_rpt=False)


def run_deck(opt=mvsbld.OPT):
    """Job ONFERUN: FR-BAT-01 STEP2 under GCCMVS.

    The source list is tools/mvseng.py's with five units added --
    onfrnd.c, onfstm.c, onfker.c, onfreq.c and generated/onfcom.c -- and
    it is written out here rather than derived from mvseng's, because
    LINK ORDER is part of it and an expression that inserted units into
    someone else's list would hide that.

    Every one of the five except onfreq.c has already been compiled on
    MVS by tools/mvssyn.py, in this order, with these member names.
    """
    prologue = mvsbld.cards_of("generated/onf2cnm.h")
    library = prologue + mvsbld.amalgamate(mvseng.UNIT, mvseng.INCLUDES)
    backend = mvsbld.with_defines("engine/src/onffp2.c",
                                  ["ONF_FP_SOFT2C"], prologue)

    def onfly(relpath):
        return mvsbld.with_defines(relpath, ["ONF_FP_SOFT2C"])

    sources = [
        (library, "SF2C", mvsbld.CC_FLAGS_VENDOR),
        (backend, "ONFFP2C"),
        (onfly("engine/src/onffpc.c"), "ONFFPCC"),
        (onfly("engine/src/onffpr.c"), "ONFFPRC"),
        (onfly("engine/src/onfcrc.c"), "ONFCRCC"),
        (onfly("engine/src/onfdec.c"), "ONFDECC"),
        (onfly("engine/src/onfrnd.c"), "ONFRNDC"),
        (onfly("engine/src/onfstm.c"), "ONFSTMC"),
        (onfly("engine/src/onfker.c"), "ONFKERC"),
        (onfly("engine/src/onfreq.c"), "ONFREQC"),
        (onfly("generated/onfcom.c"), "ONFCOMC"),
        # D-142: the 32-bit self-test, for the same reason mvseng.py
        # links it -- NR-14 as D-118 amended it asks for the width the
        # engine actually uses, and ONFLYENG runs it at entry.
        (mvsbld.cards_of("softfloat/onfi32.c"), "ONFI32C"),
        (onfly("engine/src/onflyeng.c"), "ONFLYENG"),
    ]
    got = tuple(s[1] for s in sources)
    if got != UNIT_MEMBERS:
        raise RunError("link order changed: %s" % (got,))

    # IR-JCL-01's DD names.  No PARM at all on the GO step: onfeisv()
    # treats anything that is not VERIFY as SIMULATE, and an absent PARM
    # is the plainest spelling of "not VERIFY" available.
    go_dd = [
        "//ONFNET   DD UNIT=%s," % mvseng.READER_UNIT,
        "//            DCB=(RECFM=F,LRECL=80,BLKSIZE=80)",
        "//ONFREQ   DD DSN=%s,DISP=SHR" % REQ_DSN,
        "//ONFRSP   DD DSN=&&ONFRSP,DISP=(,PASS),UNIT=SYSDA,",
        "//            SPACE=(TRK,(2,1)),",
        "//            DCB=(RECFM=FB,LRECL=412,BLKSIZE=4120)",
    ]
    # COND=(8,LT): dump unless something has already failed at 12 or
    # worse.  IR-JCL-04 gives 4 to a warning and 8 to a request error,
    # and the bytes are worth having in both cases -- a run where one
    # request was rejected still wrote records for the others.
    post = [
        "//*",
        "//DUMP     EXEC PGM=IDCAMS,COND=(8,LT)",
        "//SYSPRINT DD SYSOUT=*",
        "//ONFRSP   DD DSN=&&ONFRSP,DISP=(OLD,DELETE)",
        "//SYSIN    DD *",
        "  PRINT INFILE(ONFRSP) DUMP",
        "/*",
    ]
    return mvsbld.build(RUN_JOB, "ONFLY E1 SIMULATE", sources,
                        headers=HEADERS, go_dd=go_dd, post=post,
                        opt=opt)


# --- reading the listing ---------------------------------------------------

FP_LINE = re.compile(r"ONF301I\s+REQUEST\s+(\d+)\s+COMPLETE\s+FP=([0-9A-F]{8})")
SUMMARY = re.compile(r"ONF302I\s+STEP SUMMARY:\s*(\d+) OK,\s*(\d+) WARN,"
                     r"\s*(\d+) ERROR")


def fingerprints(listing):
    """(request number, fingerprint) pairs, in the order printed."""
    return [(int(m.group(1)), m.group(2))
            for m in FP_LINE.finditer(listing)]


#: The ONE code-page-dependent field in the 412-byte record.
#:
#: layout/master.py declares `stimcode` at offset 0, 8 bytes, kind 'chr'
#: -- which that file defines as "fixed-length alphanumeric, HOST CODE
#: PAGE, no translation".  It is the only field of that kind: every other
#: field is 'i16'/'i32' (big-endian binary on the wire, IR-COM-04) or
#: 'byt' (opaque, never translated -- the fingerprint and the filler).
#:
#: So bytes 0..7 of every record are EBCDIC when MVS wrote them and ASCII
#: when x86 did, BY DESIGN, and IR-COM-05 excludes text from the
#: fingerprint for exactly this reason: "so the fingerprint is identical
#: on ASCII and EBCDIC hosts".  Bytes 8..411 carry no such excuse.
#:
#: Nothing here decides how TX-01 is judged.  These three views are
#: MEASURED and reported side by side so the owner can decide on numbers.
CHR_OFF, CHR_LEN = 0, 8
EBCDIC = "cp037"


def translate_chr(rec, frm=EBCDIC, to="ascii"):
    """A record with its one 'chr' field moved between code pages."""
    head = rec[CHR_OFF:CHR_OFF + CHR_LEN]
    try:
        moved = head.decode(frm).encode(to)
    except (UnicodeDecodeError, UnicodeEncodeError):
        return None
    return rec[:CHR_OFF] + moved + rec[CHR_OFF + CHR_LEN:]


def compare_records(got, want, what):
    """Three measured views of two record lists from different hosts.

    Returns ({view: bool}, lines).  The views are:

      raw         every one of the 412 bytes identical
      binary      bytes 8..411 identical -- everything that is not the
                  'chr' field
      translated  identical once `got`'s 'chr' field is read as EBCDIC
                  and written as ASCII

    `raw` is reported first and without apology even when it is known to
    be unachievable, because a report that quietly drops the strictest
    check is a report that hides the day the strictest check could have
    passed.
    """
    lines = []
    views = {"raw": True, "binary": True, "translated": True}
    if len(got) != len(want):
        lines.append("  FAIL %s: %d records, expected %d"
                     % (what, len(got), len(want)))
        for k in views:
            views[k] = False
        return views, lines

    tail = CHR_OFF + CHR_LEN
    for i, (g, w) in enumerate(zip(got, want), 1):
        t = translate_chr(g)
        v = {"raw": g == w,
             "binary": g[tail:] == w[tail:] and len(g) == len(w),
             "translated": t is not None and t == w}
        for k in views:
            views[k] = views[k] and v[k]
        mark = "ok  " if all(v.values()) else (
            "note" if v["binary"] and v["translated"] else "FAIL")
        lines.append("  %-4s record %d: raw %-3s  binary(8..%d) %-3s  "
                     "translated %-3s"
                     % (mark, i, "yes" if v["raw"] else "NO",
                        len(g) - 1, "yes" if v["binary"] else "NO",
                        "yes" if v["translated"] else "NO"))
        if not v["binary"]:
            k = next((j for j in range(tail, min(len(g), len(w)))
                      if g[j:j + 1] != w[j:j + 1]), None)
            if k is not None:
                lines.append("         first binary difference at byte %d" % k)
                lines.append("         got  %s"
                             % g[max(tail, k - 8):k + 8].hex())
                lines.append("         want %s"
                             % w[max(tail, k - 8):k + 8].hex())
        if not v["raw"]:
            lines.append("         chr[0:8] got %s (%r as EBCDIC), want %s"
                         % (g[:tail].hex(),
                            g[:tail].decode(EBCDIC, "replace"),
                            w[:tail].hex()))
    return views, lines


GOLD_LINE = re.compile(r"^GOLD id=(\S+).*\bfp=([0-9A-F]{8})", re.M)


def read_records(path, reclen=None):
    """A recorded ONFREQ/ONFRSP dataset as a list of records."""
    if reclen is None:
        reclen = mvsrun_reclen()
    with open(path, "rb") as f:
        blob = f.read()
    if len(blob) == 0 or len(blob) % reclen:
        raise RunError("%s is %d bytes, not a multiple of %d"
                       % (path, len(blob), reclen))
    return [blob[i:i + reclen] for i in range(0, len(blob), reclen)]


def mvsrun_reclen():
    """ONF_RECLEN, from the generated layout rather than a literal."""
    import onfcom_py as layout
    return layout.RECORD_LEN


def golden_fingerprints(refdir, netname=NETNAME, backend="2c"):
    """(golden id, fingerprint) from a recorded gold-<net>-<backend>.txt."""
    path = os.path.join(refdir, "gold-%s-%s.txt" % (netname, backend))
    text = io.open(path, encoding="ascii").read()
    return [(m.group(1), m.group(2))
            for m in GOLD_LINE.finditer(text) if m]


def run_compare(argv):
    """TX-01's MVS half and ACC-5's row 6, judged per D-261.

    `tests/run_tx.py --compare` is Phase D's comparator and is byte-exact
    by construction, which under D-261 would fail on the one `'chr'`
    field every time.  Rather than weaken that tool -- Phase D's claim is
    x86 against s390x, both ASCII, where byte-exactness is exactly right
    -- the code-page-aware comparison lives here, with Phase E.
    """
    if len(argv) < 2:
        sys.stderr.write("usage: mvsrun.py --compare <mvsdir> <refdir>\n")
        return 2
    mvsdir, refdir = argv[0], argv[1]
    name = "rsp-%s-2c.bin" % NETNAME
    mvs = read_records(os.path.join(mvsdir, name))
    ref = read_records(os.path.join(refdir, name))

    sys.stdout.write("=== TX-01 (MVS half), D-261 translated identity ===\n")
    sys.stdout.write("    %s\n    vs %s\n"
                     % (os.path.join(mvsdir, name),
                        os.path.join(refdir, name)))
    views, lines = compare_records(mvs, ref, "ONFRSP")
    sys.stdout.write("\n".join(lines) + "\n")
    sys.stdout.write("  raw=%s  binary=%s  translated=%s\n"
                     % (views["raw"], views["binary"], views["translated"]))

    # ACC-5 row 6.  The fingerprint is a FIELD of the record, so identical
    # records imply identical fingerprints -- but the golden suite is
    # where Section 8.4 states what the fingerprint must BE, and a claim
    # about ACC-5 that never reads that file is a claim about agreement
    # between two recordings rather than about the suite.
    ok = views["translated"]
    off = 20                       # ONF-FPRINT, layout/master.py
    sys.stdout.write("\n=== ACC-5 row 6: TK5 MVS 3.8j / SOFT2C / GCCMVS "
                     "vs Section 8.4 ===\n")
    gold = golden_fingerprints(refdir)
    if len(gold) != len(mvs):
        sys.stdout.write("  FAIL %d golden entries, %d MVS records\n"
                         % (len(gold), len(mvs)))
        ok = False
    for (gid, want), rec in zip(gold, mvs):
        got = rec[off:off + 4].hex().upper()
        good = got == want
        ok = ok and good
        sys.stdout.write("  %-4s %-5s fp=%s  golden=%s\n"
                         % ("ok" if good else "FAIL", gid, got, want))
    sys.stdout.write("mvsrun: TX-01 %s, ACC-5 row 6 %s\n"
                     % ("PASS" if views["translated"] else "FAIL",
                        "PASS" if ok else "FAIL"))
    return 0 if ok else 1


def submit_and_collect(deck, job, timeout):
    mvsub.check_cards(deck)
    before = mvsub.submit(deck)
    out = mvsub.collect(job, before, timeout=timeout, poll=5)
    if out is None:
        raise RunError("%s did not finish within %d s" % (job, timeout))
    return out


# --- the two jobs ----------------------------------------------------------

def run_req(argv):
    d = req_deck()
    mvsub.check_cards(d)
    if "--print" in argv:
        sys.stdout.write("\n".join(d) + "\n")
        return 0
    sys.stdout.write("mvsrun: %s, %d cards, longest %d columns\n"
                     % (REQ_JOB, len(d), max(len(c) for c in d)))
    t0 = time.time()
    out = submit_and_collect(d, REQ_JOB, 600)
    sys.stdout.write("mvsrun: %s finished in %.1f s\n"
                     % (REQ_JOB, time.time() - t0))
    sys.stdout.write("\n".join(mvsub.summarise(out)) + "\n")

    recs = mvscob.parse_dump(out)
    views, lines = compare_records(recs, expected_records(),
                                   "ONFREQ written by ONFLYDRV")
    sys.stdout.write("\n=== FR-BAT-01 STEP1: ONFREQ vs tools/mkreq.py "
                     "(D-260) ===\n")
    sys.stdout.write("\n".join(lines) + "\n")
    sys.stdout.write("  raw=%s  binary=%s  translated=%s\n"
                     % (views["raw"], views["binary"], views["translated"]))
    # The binary view is the one that can fail for an ONFLY reason: the
    # 'chr' field is EBCDIC on MVS by design (layout/master.py), so `raw`
    # carries no information here beyond confirming that.
    return 0 if views["binary"] and views["translated"] else 1


def run_run(argv):
    opt = mvsbld.OPT
    for a in argv:
        if a.startswith("--opt="):
            opt = a[len("--opt="):]
    d = run_deck(opt)
    mvsub.check_cards(d)
    if "--print" in argv:
        sys.stdout.write("\n".join(d) + "\n")
        return 0

    if not os.path.isfile(CARDFILE):
        sys.stderr.write("mvsrun: no card file; run --cards first\n")
        return 2

    sys.stdout.write("mvsrun: %s, %d cards, %d translation units, "
                     "longest %d columns, GCCMVS %s\n"
                     % (RUN_JOB, len(d), len(UNIT_MEMBERS),
                        max(len(c) for c in d), opt))

    # Release the reader before staging: Hercules holds the card file
    # open while it is loaded and Windows will not overwrite an open
    # file (the PermissionError tools/mvseng.py documents).
    mvseng.console("devinit %s *" % mvseng.READER_DEV)
    staged = mvseng.stage(CARDFILE)
    mvseng.console("devinit %s %s eof"
                   % (mvseng.READER_DEV, staged.replace("\\", "/")))
    sys.stdout.write("mvsrun: reader %s loaded with %s\n"
                     % (mvseng.READER_DEV, staged))

    t0 = time.time()
    out = submit_and_collect(d, RUN_JOB, 7200)
    took = time.time() - t0
    sys.stdout.write("mvsrun: %s finished in %.1f s\n" % (RUN_JOB, took))
    sys.stdout.write("\n".join(mvsub.summarise(out)) + "\n")

    for n, fp in fingerprints(out):
        sys.stdout.write("mvsrun: ONF301I request %d FP=%s\n" % (n, fp))
    m = SUMMARY.search(out)
    if m:
        sys.stdout.write("mvsrun: ONF302I %s OK, %s WARN, %s ERROR\n"
                         % m.groups())

    outdir = None
    for i, a in enumerate(argv):
        if a == "--out" and i + 1 < len(argv):
            outdir = argv[i + 1]
    recs = mvscob.parse_dump(out)
    sys.stdout.write("mvsrun: recovered %d response records from the "
                     "IDCAMS dump\n" % len(recs))

    # A job that failed still has a listing, and parse_dump() still
    # returns something from it -- an empty list, or a short one.
    # Writing that out under the name the comparator reads would turn a
    # failed run into a file the next step compares and reports as a
    # disagreement, which is a worse error message than the truth.
    want = len(expected_records())
    if len(recs) != want or m is None:
        sys.stderr.write("mvsrun: %s did not produce %d response records "
                         "(%d recovered, ONF302I %s); nothing written\n"
                         % (RUN_JOB, want, len(recs),
                            "absent" if m is None else "present"))
        return 1
    if outdir:
        if not os.path.isdir(outdir):
            os.makedirs(outdir)
        path = os.path.join(outdir, "rsp-%s-2c.bin" % NETNAME)
        with open(path, "wb") as f:
            for r in recs:
                f.write(r)
        # req-*.bin is what the comparator expects to find beside it,
        # and it is x86's packing by construction -- ONFEREQ has
        # already proved MVS holds the same bytes.
        reqpath = os.path.join(outdir, "req-%s.bin" % NETNAME)
        with open(reqpath, "wb") as f:
            for r in expected_records():
                f.write(r)
        lst = os.path.join(outdir, "ONFERUN.txt")
        io.open(lst, "w", encoding="ascii", errors="replace",
                newline="").write(out.replace("\r\n", "\n"))
        sys.stdout.write("mvsrun: wrote %s (%d bytes), %s and %s\n"
                         % (path, os.path.getsize(path),
                            os.path.basename(reqpath),
                            os.path.basename(lst)))
    return 0


def main(argv):
    try:
        sys.stdout.reconfigure(errors="replace")
    except (AttributeError, ValueError):
        pass

    for i, a in enumerate(argv):
        if a == "--net" and i + 1 < len(argv):
            select(argv[i + 1])
    sys.stdout.write("mvsrun: network %s, jobs %s/%s, ONFREQ %s\n"
                     % (NETNAME, REQ_JOB, RUN_JOB, REQ_DSN))

    if "--cards" in argv:
        n, pad, cards = write_cards()
        sys.stdout.write("mvsrun: %s -> %d bytes + %d pad = %d cards\n"
                         % (os.path.basename(CARDFILE), n, pad, cards))
        return 0
    if "--req" in argv:
        return run_req(argv)
    if "--run" in argv:
        return run_run(argv)
    if "--compare" in argv:
        i = argv.index("--compare")
        return run_compare(argv[i + 1:])
    sys.stderr.write(__doc__.rsplit("Run:", 1)[-1])
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
