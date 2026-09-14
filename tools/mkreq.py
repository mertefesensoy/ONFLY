# -*- coding: utf-8 -*-
"""Control cards into an ONFREQ dataset (IR-JCL-02, IR-JCL-03, D-222).

STEP1 of FR-BAT-01 is ONFLYDRV in request mode, a COBOL program that Phase E
builds.  Phase D needs the same bytes in order to exercise STEP2 -- the
request loop D-221 brought forward -- on two platforms, so this tool produces
them from the same control cards ONFLYDRV will read.

It is NOT a replacement for ONFLYDRV.  When Phase E builds the COBOL request
mode, the two must agree byte for byte on the same cards, and this tool is
what that comparison will be made against.

Card format (IR-JCL-02), columns 1-based, records fixed at 80 characters:

    1-4     stimulus code, e.g. SUGR
    6-9     rate in Hz
    11-14   duration in ms
    16-24   seed

An asterisk in column 1 marks a comment.  Blank cards are skipped, which is
not in IR-JCL-02 but cannot be confused with anything else: a card that is
entirely blank carries no stimulus code and would otherwise become an
ONF203E request nobody asked for.

Fields are read by slicing fixed columns and then stripping, never by
splitting on whitespace.  That is deliberate: a card whose fields have run
together, or whose seed has drifted a column, must be rejected rather than
silently re-parsed into a different request.  A field that is not an integer
is an error (ONF401E is ONFLYDRV's message for it; this tool reports the card
number and exits non-zero).

Record format (IR-JCL-03): the full 412-byte COMMAREA with the response
portion -- everything from offset 16 -- zeroed.  ONFLYENG overwrites only
that portion.

Run:  python tools/mkreq.py <cards> <onfreq-out>
      python tools/mkreq.py --golden <network> <onfreq-out>
"""
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for sub in ("generated", "tests"):
    sys.path.insert(0, os.path.join(ROOT, sub))

import onfcom_py as L                              # noqa: E402

#: Column slices, 0-based half-open, from IR-JCL-02's 1-based columns.
COL_CODE = (0, 4)
COL_RATE = (5, 9)
COL_MS = (10, 14)
COL_SEED = (15, 24)


def field(card, span, what, lineno):
    """One fixed-column field, stripped.  Never split on whitespace."""
    text = card[span[0]:span[1]].strip()
    if text == "":
        raise ValueError("card %d: %s is blank" % (lineno, what))
    return text


def number(card, span, what, lineno):
    text = field(card, span, what, lineno)
    try:
        return int(text, 10)
    except ValueError:
        raise ValueError("card %d: %s is not an integer: %r"
                         % (lineno, what, text))


def pack(code, rate, ms, seed):
    """One 412-byte request record with the response portion zeroed."""
    if len(code) > 8:
        raise ValueError("stimulus code %r exceeds 8 characters" % code)
    # The code is text in the host code page (Section 4.3).  On this host that
    # is ASCII; an EBCDIC host's ONFLYDRV writes the same characters in its own
    # code page, which is why IR-COM-05 excludes text from the fingerprint.
    head = struct.pack(
        L.HEAD_FMT,
        code.ljust(8).encode("ascii"),
        seed,
        rate,
        ms,
        0,                       # ONF-RC, response portion
        0,                       # ONF-OUT-COUNT, response portion
        b"\0\0\0\0",             # ONF-FPRINT, response portion
        0,                       # ONF-STEPS, response portion
    )
    assert len(head) == L.HEAD_LEN
    return head + b"\0" * (L.RECORD_LEN - L.HEAD_LEN)


def cards_to_records(text):
    """Parse a control-card deck.  Returns a list of 412-byte records."""
    out = []
    for i, raw in enumerate(text.splitlines(), start=1):
        card = raw.rstrip("\r\n")
        if card[:1] == "*":
            continue                              # IR-JCL-02 comment
        if card.strip() == "":
            continue
        card = card.ljust(80)
        code = field(card, COL_CODE, "stimulus code", i)
        rate = number(card, COL_RATE, "rate", i)
        ms = number(card, COL_MS, "duration", i)
        seed = number(card, COL_SEED, "seed", i)
        # Range checking is NOT done here.  IR-JCL-03 says request records
        # carry the request as submitted, and FR-SIM-06, NR-12 and Appendix E
        # put the rejection in ONFLYENG so that an out-of-range request
        # produces a response record and a fingerprint (G-13 depends on
        # exactly that).  What is checked here is only what the 412-byte
        # layout physically cannot carry.
        for value, lo, hi, what in (
                (rate, -32768, 32767, "rate"),
                (ms, -32768, 32767, "duration"),
                (seed, -2147483648, 2147483647, "seed")):
            if value < lo or value > hi:
                raise ValueError("card %d: %s %d does not fit its field"
                                 % (i, what, value))
        out.append(pack(code, rate, ms, seed))
    return out


def golden_cards(netname):
    """The Section 8.4 requests for one network, as a control-card deck.

    The suite is imported from tests/run_gld.py rather than restated, so this
    tool cannot disagree with the requests it is meant to reproduce -- D-212's
    two halves included.  ``netname`` is "path" or "srext".

    Note on G-09.  Section 8.4 asks for "the header maximum" and the C driver
    spells that as a negative sentinel in its own table; run_gld.py carries
    the resolved value, 1300 (D-138), which it asserts against the header.
    Cards carry the resolved value too, because a control card is what an
    operator types and IR-JCL-02 gives it no sentinel.
    """
    import run_gld

    tag = None
    for key, (name, _path) in run_gld.NETWORKS.items():
        if name == netname:
            tag = key
    if tag is None:
        raise ValueError("unknown network %r; expected one of %s"
                         % (netname, sorted(n for n, _ in
                                            run_gld.NETWORKS.values())))

    lines = ["* Section 8.4 golden requests for the %s network" % netname]
    for (gid, code, _stimid, rate, ms, seed, net) in run_gld.SUITE:
        if net != tag:
            continue
        lines.append("%-4s %4d %4d %9d" % (code, rate, ms, seed))
    return "\n".join(lines) + "\n"


def main(argv):
    if len(argv) == 3 and argv[0] == "--golden":
        text = golden_cards(argv[1])
        out = argv[2]
    elif len(argv) == 2:
        with open(argv[0], "r") as f:
            text = f.read()
        out = argv[1]
    else:
        sys.stderr.write(__doc__.rsplit("Run:", 1)[-1])
        return 2

    try:
        records = cards_to_records(text)
    except ValueError as exc:
        sys.stderr.write("mkreq: %s\n" % exc)
        return 1
    if not records:
        sys.stderr.write("mkreq: no requests; ONFLYENG would report "
                         "ONF906S on an empty dataset\n")
        return 1
    with open(out, "wb") as f:
        for r in records:
            f.write(r)
    print("mkreq: %d requests, %d bytes -> %s"
          % (len(records), len(records) * L.RECORD_LEN, out))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
