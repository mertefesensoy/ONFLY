# -*- coding: utf-8 -*-
"""Phase G Stage 5: ONFLYENG streams from MVS while the job is running.

WHAT IS NEW HERE, AND WHAT IS NOT
---------------------------------
Not new: the engine.  This submits `tools/mvsrun.py`'s own `run_deck()`
with exactly two additions -- `PARM='STREAM=nnn'` on the GO step and an
ONFSTM DD -- so the program that runs is the program ACC-5 row 6 was
filled with (D-255, VL-91).  A deck assembled here from its own source
list could differ from that one in link order and nobody would see it,
so the list is imported rather than restated.

New: the output leaves MVS *while the job is still running*, which is
what D-128 means by live and what P-17's risk table left unmeasured.

WHY THE 10D PUNCH AND NOT SYSOUT
--------------------------------
Measured on TK5 on 2026-09-17, from the Hercules console, before any
job was submitted:

    $DU            READER1 00C  PRINTER1 00E  PRINTER2 00F
                   PRINTER3 002  PUNCH1 00D          -- all five JES2's
    D U,,,00C,8    00C 00D 00E 00F  all status A     -- allocated to it

Every device a `SYSOUT=` DD could reach belongs to JES2, and JES2
spools: its output reaches the host when the job ENDS.  So SYSOUT can
carry a recording and cannot carry a live view.

    D U,,,10C,4    10C 2540 O       10D 2540 O

10C and 10D are online, unallocated and named by no JES2 device.
`tools/mvseng.py` already reads 10C as a DEVICE for the reader
transport.  10D is its punch counterpart:

    010D 3525 pch/pch10d.txt ascii

Hercules translates EBCDIC to ASCII on the way out and appends to a
plain host file.  A probe job in the same session wrote twelve cards
with a CPU burn between them and the host watched the file every 250
ms: twelve size changes, one per ~1.25 s, ALL of them before the job's
END banner at t=16.8 s.

THE 80-COLUMN TRAP, WHICH IS WHY D-406 EXISTS
---------------------------------------------
The same probe wrote lines of 79, 80, 81 and 200 columns.  They arrived
as 79, 80, 80 and 80 bytes: one card per line, no split, no message,
COND CODE 0000, and the tail simply gone.  That is the D-93 failure
class, and at K=50 it would take 797 of the 1,000 ONFSC lines the srext
golden suite produces.  D-406 answers it -- ONFSD continuations, on
both platforms, so one format exists -- and this file checks the
result rather than trusting it.

WHAT THIS PROVES AND WHAT IT DOES NOT
-------------------------------------
It proves things for **TK5 MVS 3.8j, GCCMVS, SOFT2C**, on the `srext`
network, and for nothing else.  JCC is not attempted; Linux s390x and
z/OS are not touched; and a live channel on THIS device says nothing
about whether MVS spooled output can be followed, which it cannot.

usage:
    python tools/mvsstm.py --run [--k 50] [--opt=-O1]
    python tools/mvsstm.py --print            emit the deck, submit nothing
    python tools/mvsstm.py --compare          MVS stream against x86's
    python tools/mvsstm.py --recover          read a finished job's output
"""
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import goldfp                                         # noqa: E402
import mvsbld                                         # noqa: E402
import mvsrun                                         # noqa: E402
import mvsub                                          # noqa: E402

#: D-407.  All five srext golden requests at K = 50: 10,000 steps at
#: dt = 100 us gives 200 chunks each, and the fingerprint panel then
#: shows five rows rather than one.
K_DEMO = 50

#: Where the stream arrives on the host.  Hercules appends, so this file
#: also holds every earlier run and the offset taken before submitting is
#: what separates them.
PUNCH = os.path.join(mvsub.tk5_dir(), "pch", "pch10d.txt")

#: What this writes, for tools/liveview.py --follow to read.
OUTDIR = os.path.join(ROOT, "build")
OUTSTM = os.path.join(OUTDIR, "mvs-stream.txt")

#: UNIT=10D, not 00D.  00D is JES2's PUNCH1 and is allocated to it, so a
#: job naming it waits rather than fails -- which would look like a hung
#: engine and be debugged as one.
STM_DD = [
    "//ONFSTM   DD UNIT=10D,",
    "//            DCB=(RECFM=F,LRECL=80,BLKSIZE=80)",
]


class StmError(Exception):
    pass


def deck(k=K_DEMO, opt=None):
    """mvsrun's own engine deck, with the stream turned on.

    `go_parm` and the extra DD are the whole difference.  mvsbld.build
    checks every card it is given against column 71, so a DD card that
    ran off the end would be refused here rather than accepted and
    misread by MVS.
    """
    if opt is None:
        opt = mvsbld.OPT
    if not (1 <= k <= 999999):
        raise StmError("K must be in 1..999999 (IR-STM-01), not %r" % k)
    sources = mvsrun._sources(opt)
    go_dd = [
        "//ONFNET   DD DSN=%s,DISP=SHR" % mvsrun.NET_DSN,
        "//ONFREQ   DD DSN=%s,DISP=SHR" % mvsrun.REQ_DSN,
        "//ONFRSP   DD DSN=%s,DISP=(,CATLG,DELETE)," % mvsrun.RSP_DSN,
        "//            UNIT=SYSDA,SPACE=(TRK,(2,1)),",
        "//            DCB=(RECFM=FB,LRECL=412,BLKSIZE=4120)",
    ] + STM_DD
    return mvsbld.build(mvsrun.RUN_JOB, "ONFLY G5 STREAM", sources,
                        headers=mvsrun.HEADERS, go_dd=go_dd,
                        go_parm="STREAM=%d" % k,
                        scratch=[mvsrun.RSP_DSN], opt=opt)


def punch_size():
    try:
        return os.path.getsize(PUNCH)
    except OSError:
        return 0


class Harvest(object):
    """Copy the punch file into `out` as it grows, a line at a time.

    Incremental, not a copy at the end.  `tools/liveview.py --follow`
    reads `out` while this is still writing it, so a harvest that ran
    once when the job finished would give the viewer a finished
    recording -- the thing D-128 ruled out -- while the mechanism that
    made a live view possible sat unused two feet away.

    A partial last line is held back until its newline arrives, for the
    reason liveview's own Tail holds one back: a half-parsed chunk does
    not fail, it draws something subtly wrong.
    """

    def __init__(self, base, out):
        self.pos = base
        self.lines = 0
        self.fh = open(out, "wb")

    def poll(self):
        """Move whatever whole lines have arrived.  Returns bytes moved."""
        try:
            size = os.path.getsize(PUNCH)
        except OSError:
            return 0
        if size <= self.pos:
            return 0
        with open(PUNCH, "rb") as src:
            src.seek(self.pos)
            raw = src.read(size - self.pos)
        cut = raw.rfind(b"\n")
        if cut < 0:
            return 0
        chunk = raw[:cut + 1]
        self.fh.write(chunk)
        self.fh.flush()
        self.pos += len(chunk)
        self.lines += chunk.count(b"\n")
        return len(chunk)

    def close(self):
        self.fh.close()


def follow(base, job, timeout):
    """Submit nothing; watch.  Returns (timings, printer text).

    The two numbers the liveness claim rests on are taken here and
    nowhere else, because this is the only process that can see both the
    punch file and the job's END banner:

        first       when the first ONFSC line reached the host
        ended       when JES2 printed the job's END banner

    `first < ended` is the claim.  Nothing else in this file, and
    nothing in tools/liveview.py, is entitled to make it.

    The punch is watched four times a second and the printer once every
    two.  They are separate intervals because they cost differently: the
    punch check is a stat, while the printer check re-reads a listing
    that a 9,000-card deck grows into megabytes.  Polling that at the
    punch's rate would spend the job's whole duration reading it.
    """
    t0 = time.time()
    before = len(mvsub.read_printer())
    first = None
    ended = None
    marks = []
    harvester = Harvest(base, OUTSTM)
    saw_onfsc = False
    deadline = t0 + timeout
    next_printer = 0.0
    try:
        while time.time() < deadline:
            moved = harvester.poll()
            if moved:
                marks.append((time.time() - t0, harvester.pos - base))
                if not saw_onfsc:
                    # Only a real stream line starts the clock.  A file
                    # that merely grew would time something else.
                    with open(OUTSTM, "rb") as fh:
                        if b"ONFSC" in fh.read():
                            saw_onfsc = True
                            first = time.time() - t0
            if time.time() >= next_printer:
                out = mvsub.read_printer()[before:]
                next_printer = time.time() + 2.0
                if re.search(r"END\s+JOB\s+\d+\s+%s\b" % job, out):
                    ended = time.time() - t0
                    break
            time.sleep(0.25)
        # The last cards can land after the banner is printed.
        stop = time.time() + 5.0
        while time.time() < stop:
            if harvester.poll():
                marks.append((time.time() - t0, harvester.pos - base))
            time.sleep(0.25)
    finally:
        harvester.close()
    out = mvsub.read_printer()[before:]
    return ({"first": first, "ended": ended, "marks": marks,
             "lines": harvester.lines}, out)


def report_live(t):
    """Say what was measured, and say plainly when it was not met."""
    sys.stdout.write("mvsstm: first ONFSC at %s, job END banner at %s\n"
                     % ("+%.1f s" % t["first"] if t["first"] is not None
                        else "NEVER",
                        "+%.1f s" % t["ended"] if t["ended"] is not None
                        else "NOT SEEN"))
    during = [m for m in t["marks"]
              if t["ended"] is not None and m[0] < t["ended"] - 0.5]
    sys.stdout.write("mvsstm: %d of %d punch writes landed before the job "
                     "ended\n" % (len(during), len(t["marks"])))
    live = (t["first"] is not None and t["ended"] is not None
            and t["first"] < t["ended"] and len(during) > 2)
    if live:
        sys.stdout.write("mvsstm: LIVE -- the stream left MVS while the "
                         "job was running (D-128)\n")
    else:
        sys.stdout.write("mvsstm: NOT LIVE -- output did not precede the "
                         "job's end; this is a recording, not a live "
                         "view\n")
    return live


def check_width(path):
    """D-406 on the MVS side: the bound held where it actually matters."""
    worst, where, lines = 0, 0, 0
    with open(path, "r") as fh:
        for lineno, line in enumerate(fh, 1):
            lines += 1
            nch = len(line.rstrip("\n"))
            if nch > worst:
                worst, where = nch, lineno
    ok = worst <= 80
    sys.stdout.write("mvsstm: %d lines, longest %d columns at line %d -- "
                     "%s\n" % (lines, worst, where,
                               "within the D-406 bound" if ok
                               else "OVER THE BOUND"))
    return ok


def fingerprints(path):
    """(rate, fingerprint) for every request the stream completed."""
    seen = []
    rate = None
    for line in open(path, "r"):
        f = line.split()
        if not f:
            continue
        if f[0] == "ONFSH" and len(f) >= 9:
            rate = int(f[8])
        elif f[0] == "ONFSE" and len(f) >= 4:
            seen.append((rate, f[3]))
            rate = None
    return seen


def report_fp(seen):
    """The MVS fingerprints against Section 8.4, one row each."""
    sys.stdout.write("mvsstm: %d completed requests\n" % len(seen))
    allok = bool(seen)
    for rate, fp in seen:
        gold = goldfp.SREXT.get(rate)
        ok = gold == fp
        allok = allok and ok
        sys.stdout.write("   %-5s rate %-5s golden %-9s MVS %-9s %s\n"
                         % (goldfp.SREXT_ID.get(rate, "-"), rate,
                            gold or "(none)", fp,
                            "AGREE" if ok else "DIFFERS"))
    return allok


def compare_stream(mvspath, x86path):
    """V5: the MVS stream against the x86 stream, under D-414's rule.

    THE ONE ALLOWANCE, AND WHY IT IS SAFE
    -------------------------------------
    ONFLYENG opens ONFSTM in TEXT mode.  On MVS that is what makes each
    newline a RECORD -- binary mode there would write a byte stream into
    an 80-byte RECFM=F dataset and the newline would become data -- and
    on Windows the same text mode writes CRLF.  So the x86 host's CRLF is
    mapped to LF before the comparison (D-414), and nothing else is
    allowed for: no case folding, no whitespace trimming, no field-wise
    reading.  Hercules strips a card's trailing blanks and the emitter
    writes none, so the two should meet exactly.

    The allowance is checkable rather than trusted: the files differ by
    exactly one byte per line, which is reported, so a difference hiding
    inside the line endings would show up as a mismatch in that count.

    A DIFFERENCE IS CHARACTERISED, NOT JUST ANNOUNCED
    -------------------------------------------------
    VL-118 exists because this printed "streams DIFFER" and the useful
    facts -- how many lines, which request, which tag -- had to be dug
    out by hand afterwards.  A comparison that says only "not equal"
    about two 1.5 MB files has told the reader almost nothing.
    """
    a = open(mvspath, "rb").read()
    b = open(x86path, "rb").read()
    ncr = b.count(b"\r\n")
    bn = b.replace(b"\r\n", b"\n")
    sys.stdout.write("mvsstm: MVS %d bytes / %d lines, x86 %d bytes / %d "
                     "lines\n" % (len(a), a.count(b"\n"), len(b),
                                  b.count(b"\n")))
    sys.stdout.write("mvsstm: D-414 -- %d CRLF on the x86 side, %d bytes "
                     "of difference accounted for by them\n"
                     % (ncr, len(b) - len(bn)))
    if a == bn:
        sys.stdout.write("mvsstm: streams are BYTE-IDENTICAL under D-414's "
                         "rule (%d bytes)\n" % len(a))
        return True

    al, bl = a.split(b"\n"), bn.split(b"\n")
    diff = [i for i in range(min(len(al), len(bl))) if al[i] != bl[i]]
    tags = {}
    for i in diff:
        t = al[i].split()[0].decode("ascii", "replace") if al[i] else "(empty)"
        tags[t] = tags.get(t, 0) + 1
    sys.stdout.write("mvsstm: streams DIFFER -- %d of %d lines, by tag %s\n"
                     % (len(diff), len(al),
                        ", ".join("%s x%d" % kv
                                  for kv in sorted(tags.items()))))
    # Which request each differing line belongs to: the ONFSE lines
    # partition the stream, so this needs no field parsing.
    ends = [i for i, l in enumerate(al) if l.startswith(b"ONFSE")]
    byreq = {}
    for i in diff:
        r = sum(1 for e in ends if e < i) + 1
        byreq[r] = byreq.get(r, 0) + 1
    sys.stdout.write("mvsstm: by request %s\n"
                     % ", ".join("#%d x%d" % kv
                                 for kv in sorted(byreq.items())))
    i = diff[0]
    sys.stdout.write("   first difference at line %d\n"
                     "   MVS %s\n   x86 %s\n"
                     % (i + 1, al[i][:90].decode("ascii", "replace"),
                        bl[i][:90].decode("ascii", "replace")))
    return False


def run(argv):
    k = K_DEMO
    opt = None
    timeout = 7200
    for i, a in enumerate(argv):
        if a == "--k" and i + 1 < len(argv):
            k = int(argv[i + 1])
        elif a.startswith("--opt="):
            opt = a[len("--opt="):]
        elif a == "--timeout" and i + 1 < len(argv):
            timeout = int(argv[i + 1])

    d = deck(k, opt)
    mvsub.check_cards(d)
    if "--print" in argv:
        sys.stdout.write("\n".join(d) + "\n")
        return 0

    if not os.path.isdir(OUTDIR):
        os.makedirs(OUTDIR)
    sys.stdout.write("mvsstm: %s, %d cards, K=%d, ONFNET %s, ONFREQ %s\n"
                     % (mvsrun.RUN_JOB, len(d), k, mvsrun.NET_DSN,
                        mvsrun.REQ_DSN))

    base = punch_size()
    sys.stdout.write("mvsstm: punch file at %d bytes before submission\n"
                     % base)
    if not mvsub.submit(d):
        return 2
    sys.stdout.write("mvsstm: following.  A viewer can be started now, in "
                     "another shell:\n"
                     "    python tools/liveview.py --follow %s "
                     "--requests 5 --save out.gif\n" % OUTSTM)
    timings, out = follow(base, mvsrun.RUN_JOB, timeout)
    sys.stdout.write("mvsstm: %d stream lines -> %s\n"
                     % (timings["lines"], OUTSTM))

    live = report_live(timings)
    width = check_width(OUTSTM)
    seen = fingerprints(OUTSTM)
    fps = report_fp(seen)

    sys.stdout.write("\n".join(mvsub.summarise(out)) + "\n")
    with open(os.path.join(OUTDIR, "mvs-stream-job.txt"), "w") as fh:
        fh.write(out)

    ok = live and width and fps
    sys.stdout.write("mvsstm: %s\n"
                     % ("all three hold: live, within 80 columns, "
                        "fingerprints agree" if ok
                        else "NOT all conditions hold -- see above"))
    return 0 if ok else 1


def recover(argv):
    """Read the punch and the printer for a job that has already run."""
    base = 0
    for i, a in enumerate(argv):
        if a == "--from" and i + 1 < len(argv):
            base = int(argv[i + 1])
    h = Harvest(base, OUTSTM)
    while h.poll():
        pass
    h.close()
    sys.stdout.write("mvsstm: %d stream lines -> %s\n" % (h.lines, OUTSTM))
    check_width(OUTSTM)
    report_fp(fingerprints(OUTSTM))
    return 0


def compare(argv):
    x86 = None
    for i, a in enumerate(argv):
        if a == "--x86" and i + 1 < len(argv):
            x86 = argv[i + 1]
    if x86 is None:
        x86 = os.path.join(OUTDIR, "x86-stream.txt")
    if not os.path.exists(x86):
        sys.stderr.write("mvsstm: no x86 stream at %s\n"
                         "  make one with:\n"
                         "    build/onflyeng_nat.exe STREAM=%d \\\n"
                         "      data/networks/onfnet-malecns-v1.0-srext.bin"
                         " req rsp %s\n" % (x86, K_DEMO, x86))
        return 2
    if not os.path.exists(OUTSTM):
        sys.stderr.write("mvsstm: no MVS stream at %s -- run --run first\n"
                         % OUTSTM)
        return 2
    return 0 if compare_stream(OUTSTM, x86) else 1


def main(argv):
    try:
        sys.stdout.reconfigure(errors="replace")
    except (AttributeError, ValueError):
        pass
    if "--run" in argv or "--print" in argv:
        return run(argv)
    if "--recover" in argv:
        return recover(argv)
    if "--compare" in argv:
        return compare(argv)
    sys.stdout.write(__doc__.rsplit("usage:", 1)[-1])
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
