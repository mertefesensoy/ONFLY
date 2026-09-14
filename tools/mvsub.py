# -*- coding: utf-8 -*-
"""Submit a job to TK5 and retrieve its output (Gate G2 transport, D-88).

TK5 defines its card reader as a socket device:

    000C 3505 ${RDRPORT:=3505} sockdev ascii trunc eof

so a deck is submitted by opening a TCP connection to the reader port,
sending the cards as ASCII lines, and closing the write side, which the
`eof` option turns into an end-of-file.  Printer 000E writes to the plain
file `prt/prt00e.txt`, so a job's output is read back by watching that file
grow.  Between the two, the whole submit-run-read cycle is scriptable and
needs no 3270 terminal, which matters because this host has none.

The 80-column check is the point, not a nicety
----------------------------------------------
`trunc` means the reader discards everything past column 80.  Measured on
the running system on 2026-09-11: an 85-character card arrived as exactly 80
characters, with no error, no warning and no message, and the job completed
normally.  Silent truncation of source is the failure class ONFLY exists to
rule out, so this module refuses to submit an over-length card rather than
letting MVS quietly drop the end of it (D-93).

Job output is delimited by JES2's own banner lines, which name the job:

    ****A  START  JOB   nn  JOBNAME ...
    ****A   END   JOB   nn  JOBNAME ...

so the text belonging to one job can be separated from whatever else the
printer happens to be holding.

Environment:
  ONFLY_TK5   the TK5 directory (default C:\\hercules-lab\\mvs-tk5)
  ONFLY_RDR   reader host:port  (default 127.0.0.1:3505)
"""
import io
import os
import re
import socket
import sys
import time

CARD = 80
DEFAULT_TK5 = r"C:\hercules-lab\mvs-tk5"
DEFAULT_RDR = "127.0.0.1:3505"
DEFAULT_CON = "127.0.0.1:8038"

# The codepage the reader must be on (D-101, D-103, VL-18).  On Hercules'
# `default` page ASCII '|' is delivered as EBCDIC 0x6A, which GCCMVS will
# not lex, so every ONFLY source using '|=' or '||' fails to compile with a
# diagnostic that points at the source rather than at the configuration.
# 819/037 fixes '|' and breaks '^', '[' and ']'.  Only 819/1047 carries all
# of them.  This is host configuration, it is not in the repository, and a
# Hercules restart silently reverts it -- which is why it is checked here
# rather than merely written down.
REQUIRED_CP = "819/1047"


def tk5_dir():
    return os.environ.get("ONFLY_TK5", DEFAULT_TK5)


def printer_path():
    return os.path.join(tk5_dir(), "prt", "prt00e.txt")


def reader_addr():
    spec = os.environ.get("ONFLY_RDR", DEFAULT_RDR)
    host, _, port = spec.partition(":")
    return host, int(port or "3505")


def console_addr():
    spec = os.environ.get("ONFLY_CON", DEFAULT_CON)
    host, _, port = spec.partition(":")
    return host, int(port or "8038")


class CardTooLong(Exception):
    pass


class WrongCodepage(Exception):
    pass


def current_codepage():
    """Ask the running Hercules which codepage it is on.

    Returns the name, or None if the console cannot be reached.  The
    command is a query and changes nothing.
    """
    try:
        from urllib.request import urlopen
        from urllib.parse import quote
    except ImportError:                                  # Python 2
        from urllib2 import urlopen                      # noqa: F401
        from urllib import quote                         # noqa: F401
    host, port = console_addr()
    url = ("http://%s:%d/cgi-bin/tasks/syslog?command=%s"
           % (host, port, quote("codepage")))
    try:
        body = urlopen(url, timeout=10).read().decode("latin-1")
    except Exception:
        return None
    # The console echoes the whole log, so take the LAST answer: an
    # earlier line could be from a previous query.
    found = None
    for m in re.finditer(r"Codepage is ([^\s<]+)", body):
        found = m.group(1)
    return found


def check_codepage(required=REQUIRED_CP):
    """Raise unless Hercules is on the codepage ONFLY source needs.

    D-103.  A wrong codepage does not fail loudly on its own: the deck is
    accepted, the job runs, and the compile fails on a source line, so the
    hours go into reading C rather than into reading the configuration.
    An unreachable console is also refused rather than assumed good --
    every lab operation here already depends on that console, so silence
    from it means something is wrong.
    """
    cp = current_codepage()
    if cp is None:
        raise WrongCodepage(
            "cannot reach the Hercules console at %s:%d to check the "
            "codepage; ONFLY needs %s (D-101, VL-18). Set ONFLY_CON if "
            "the console is elsewhere." % (console_addr() + (required,)))
    if cp != required:
        raise WrongCodepage(
            "Hercules is on codepage %s but ONFLY source needs %s: on any "
            "other page '|' does not survive into GCCMVS and every source "
            "using '|=' or '||' fails to compile (D-101, VL-18). Fix it "
            "with the Hercules console command:  codepage %s"
            % (cp, required, required))


def check_cards(cards):
    """Raise unless every card fits in 80 columns.

    Tabs are rejected outright rather than expanded: what a tab becomes in a
    card image depends on who writes it, and a guess here would be exactly
    the kind of silent difference this module exists to prevent.
    """
    for n, card in enumerate(cards, 1):
        if "\t" in card:
            raise CardTooLong("card %d contains a tab; expand it first" % n)
        if len(card) > CARD:
            raise CardTooLong(
                "card %d is %d columns:\n  %s\n  %s^ column %d, "
                "the reader discards the rest without saying so"
                % (n, len(card), card[:CARD + 10], " " * (CARD - 1), CARD))


def read_printer():
    path = printer_path()
    if not os.path.exists(path):
        return ""
    return io.open(path, encoding="latin-1", errors="replace").read()


def submit(cards, check=True, codepage=True):
    """Send a deck to the reader.  Returns the printer length before it.

    Two preconditions are enforced, both because their failure is silent:
    the reader truncates past column 80 without a message (D-93), and a
    wrong codepage corrupts '|' on the way in (D-103).  Pass
    codepage=False only to submit a deck that contains no C source.
    """
    if codepage:
        check_codepage()
    if check:
        check_cards(cards)
    before = len(read_printer())
    host, port = reader_addr()
    sock = socket.create_connection((host, port), timeout=30)
    try:
        sock.sendall(("\n".join(cards) + "\n").encode("ascii"))
        sock.shutdown(socket.SHUT_WR)
    finally:
        sock.close()
    return before


def collect(jobname, before, timeout=180, poll=2.0):
    """Wait for jobname's output and return it.

    Returns the text between JES2's START and END banners for the job, or
    None if the END banner has not appeared before the timeout.  Waiting for
    END rather than for any output at all is what stops a long compile being
    reported as a truncated one.
    """
    upper = jobname.upper()
    start_re = re.compile(r"START\s+JOB\s+\d+\s+" + re.escape(upper) + r"\b")
    end_re = re.compile(r"END\s+JOB\s+\d+\s+" + re.escape(upper) + r"\b")
    deadline = time.time() + timeout
    while time.time() < deadline:
        text = read_printer()[before:]
        if end_re.search(text):
            lines = text.splitlines()
            first = last = None
            for i, line in enumerate(lines):
                if first is None and start_re.search(line):
                    first = i
                if end_re.search(line):
                    last = i
            if first is not None and last is not None:
                return "\n".join(lines[first:last + 1])
            return text
        time.sleep(poll)
    return None


def run(cards, jobname, timeout=180):
    """Submit and wait.  Returns the job's printer output, or None."""
    before = submit(cards)
    return collect(jobname, before, timeout=timeout)


# The lines worth keeping out of a job's printer output.
#
# `ABEND` is anchored on both sides, and that is the whole point of
# spelling this out rather than leaving a bare word in the alternation.
# An unanchored `ABEND` matches any line that merely CONTAINS those five
# letters, and MVS listings are full of them: Gate G0 listed the members
# of SYS2.JCLLIB, which include `JOBABEND` and `ABEND0C1`, and every one
# of those member names was reported as though a job had abended (D-249).
# A gate record that cries abend over a directory listing is worse than
# one that says nothing, because the reader has to go and disprove it.
#
# `\bABEND(ED)?\b` rejects both: in `JOBABEND` the preceding `B` means
# there is no word boundary before `ABEND`, and in `ABEND0C1` the
# following `0` means there is none after it.  It still matches the forms
# MVS actually uses -- `ABEND S0C4`, `ABEND=S806`, `ABENDED` -- and
# `COMPLETION CODE` is added because a system completion code is how an
# abend is reported when the word itself does not appear.
KEEP_RE = re.compile(
    r"IEF142I|IEF450I|IEF472I|COND CODE|COMPLETION CODE|"
    r"\bABEND(ED)?\b|\$HASP|IEC\d|IEW\d|JCC[A-Z]?\d|"
    r"ERROR|WARNING|SEVERE")


def summarise(out):
    """The lines a reader actually wants: step results and diagnostics."""
    if out is None:
        return ["(no output: the job did not finish within the timeout)"]
    keep = []
    for line in out.splitlines():
        if KEEP_RE.search(line):
            keep.append(line.rstrip())
    return keep or ["(no step-result lines found)"]


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: mvsub.py <deck-file> <jobname>\n")
        return 2
    deck = io.open(argv[1], encoding="ascii").read().splitlines()
    jobname = argv[2]
    try:
        out = run(deck, jobname)
    except CardTooLong as exc:
        sys.stderr.write("mvsub: %s\n" % exc)
        return 1
    if out is None:
        sys.stderr.write("mvsub: %s did not finish in time\n" % jobname)
        return 1
    sys.stdout.write(out + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
