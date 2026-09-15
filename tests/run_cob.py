# -*- coding: utf-8 -*-
"""Gate G4, x86 half: ONFLYDRV through the GnuCOBOL IBM-dialect proxy.

FR-BAT-03 requires one COBOL source that compiles unchanged under MVT
COBOL on MVS 3.8j and, later, under Enterprise COBOL.  Enterprise COBOL
is not available here, so VL-02 names GnuCOBOL's IBM dialect as the
proxy and says plainly that a proxy pass is not proof.  This script is
that proxy check, plus something the gate did not ask for but Phase E
will depend on: the driver is RUN on x86 and the request records it
writes are compared byte for byte against the layout the Python oracle
and the C engine share (generated/onfcom_py.py).

WHAT IS CHECKED
---------------
  1. `cobc -std=ibm -fsyntax-only` accepts cobol/ONFLYDRV.cbl with the
     generated copybook on the COPY path.  Warnings are allowed and
     printed; an error fails the gate.  `-std=ibm-strict` is run as
     well, as information.
  2. The driver builds to an executable.
  3. MODE=REQ on a clean deck: every record is 412 bytes and equal to
     the Python packing of the same card (IR-JCL-02, IR-JCL-03,
     IR-COM-04); return code 0.
  4. MODE=REQ on a deck with bad cards: ONF401E names each bad card by
     number (blank card, non-digit, blank numeric field, blank stimulus
     code -- D-159, D-160), the good cards still produce records, and
     the return code is 8 (IR-JCL-04).
  5. A first card that is not a mode card: ONF401E at card 1, RC 8,
     no ONFREQ written (D-158).
  6. MODE=RPT: a response file written by Python is echoed with every
     numeric field, including a -1 latency, in the expected columns.

WHAT IT DOES NOT PROVE
----------------------
Anything about MVT COBOL: that is tools/mvscob.py's job, on TK5.  And
it is a proxy for Enterprise COBOL, not Enterprise COBOL (VL-02).

SKIPPING
--------
D-156: this is not part of `make test`.  When no cobc can be found the
script prints why and exits 0, so `make cob` is harmless on a checkout
without GnuCOBOL.  Set ONFLY_COBC to point at a cobc explicitly.

Run:  python tests/run_cob.py [--keep]
"""
import io
import os
import shutil
import struct
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "generated"))

import onfcom_py as L  # noqa: E402

# The template keeps its COPY statement; the generator expands it into
# the file every compiler builds (D-161).  Both are checked: the
# template must stay honest COBOL, and the generated file is the product.
TEMPLATE = os.path.join(ROOT, "cobol", "ONFLYDRV.cbl")
SRC = os.path.join(ROOT, "generated", "ONFLYDRV.cbl")
COPYDIR = os.path.join(ROOT, "generated")
BUILD = os.path.join(ROOT, "build")
WORK = os.path.join(BUILD, "cob")

# Where an MSYS2 install puts cobc when it is not on PATH.  Only a hint:
# ONFLY_COBC and PATH are consulted first.
MSYS2_HINTS = [
    r"C:\msys64\mingw64\bin\cobc.exe",
    r"C:\msys64\ucrt64\bin\cobc.exe",
]


def find_cobc():
    p = os.environ.get("ONFLY_COBC")
    if p and os.path.exists(p):
        return p
    p = shutil.which("cobc")
    if p:
        return p
    for h in MSYS2_HINTS:
        if os.path.exists(h):
            return h
    return None


def cobc_env(cobc):
    """cobc run from outside its own shell needs to be told where its
    dialect files live; the MSYS2 build compiles the path in as
    /mingw64/share/..., which resolves only under an MSYS2 shell."""
    env = dict(os.environ)
    bindir = os.path.dirname(os.path.abspath(cobc))
    prefix = os.path.dirname(bindir)
    cfg = os.path.join(prefix, "share", "gnucobol", "config")
    cpy = os.path.join(prefix, "share", "gnucobol", "copy")
    if os.path.isdir(cfg):
        env.setdefault("COB_CONFIG_DIR", cfg)
    if os.path.isdir(cpy):
        env.setdefault("COB_COPY_DIR", cpy)
    env["PATH"] = bindir + os.pathsep + env.get("PATH", "")
    return env


def run(cmd, env, cwd=None, extra_env=None):
    e = dict(env)
    if extra_env:
        e.update(extra_env)
    p = subprocess.Popen(cmd, cwd=cwd, env=e, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT)
    out = p.communicate()[0].decode("utf-8", "replace")
    return p.returncode, out


# ---------------------------------------------------------------------------
# Expected bytes, from the generated layout and nothing else.
# ---------------------------------------------------------------------------
def request_record(code, rate, ms, seed, text_encoding="ascii"):
    """The record ONFLYDRV must write for one accepted card (IR-JCL-03):
    the request fields set, the response portion and every ONF-OUT
    entry binary zero."""
    head = struct.pack(L.HEAD_FMT, code.ljust(8).encode(text_encoding),
                       seed, rate, ms, 0, 0, b"\0\0\0\0", 0)
    out = struct.pack(L.OUT_FMT, 0, 0, 0, b"\0\0") * L.MAX_OUT
    rec = head + out
    assert len(rec) == L.RECORD_LEN
    return rec


def response_record(code, rate, ms, seed, rc, steps, entries):
    head = struct.pack(L.HEAD_FMT, code.ljust(8).encode("ascii"),
                       seed, rate, ms, rc, len(entries), b"\xDE\xAD\xBE\xEF",
                       steps)
    out = b""
    for (ident, lat, spikes) in entries:
        out += struct.pack(L.OUT_FMT, ident, lat, spikes, b"\0\0")
    out += struct.pack(L.OUT_FMT, 0, 0, 0, b"\0\0") * (L.MAX_OUT - len(entries))
    return head + out


def card(code, rate, ms, seed):
    """An IR-JCL-02 card with each numeric field spelled as given."""
    return "%-4s %4s %4s %9s" % (code, rate, ms, seed)


# The clean deck: one card per spelling D-159 allows.
CLEAN_CARDS = [
    ("SUGR", "0120", "1000", "000000001", ("SUGR", 120, 1000, 1)),
    ("SUGR", "  40", "1000", "        1", ("SUGR", 40, 1000, 1)),
    ("SUGR", "0000", "1000", "999999999", ("SUGR", 0, 1000, 999999999)),
    ("WATR", " 200", "   1", "        0", ("WATR", 200, 1, 0)),
    ("SUGR", "9999", "1300", "        7", ("SUGR", 9999, 1300, 7)),
]

# The bad deck.  (card text, expected: None for accepted, or the
# reason it must be rejected.)  Card 1 is the mode card.
BAD_CARDS = [
    (card("SUGR", "0120", "1000", "000000001"), None),
    ("", "blank card (D-160)"),
    (card("SUGR", "12X0", "1000", "000000001"), "non-digit in rate"),
    (card("SUGR", "    ", "1000", "000000001"), "blank rate field (D-159)"),
    (card("    ", "0120", "1000", "000000001"), "blank stimulus code"),
    ("* A COMMENT CARD", None),
    (card("SUGR", "0120", "1000", "         "), "blank seed field (D-159)"),
    (card("SUGR", "0120", "1000", "000000001"), None),
    # D-265 made the rate column signed.  These are the cases that must
    # still be refused, appended rather than inserted so that every card
    # number checked above keeps the number it had.
    (card("SUGR", "   -", "1000", "000000001"),
     "sign with no digits behind it (D-265)"),
    (card("SUGR", "12-0", "1000", "000000001"),
     "minus that is not the leading character (D-265)"),
    (card("SUGR", "0120", "  -1", "000000001"),
     "the duration column is NOT signed (D-265)"),
    (card("SUGR", "  -1", "1000", "000000001"), None),
]


class Fail(Exception):
    pass


def write_deck(path, cards):
    """Fixed 80-byte card images with NO line ends: ONFCTL is a record
    sequential file on both platforms, and a newline would shift every
    card after the first by one byte (found the hard way on the first
    run of this script)."""
    with io.open(path, "wb") as f:
        for c in cards:
            f.write(c.ljust(80)[:80].encode("ascii"))


def read_lines(path):
    return io.open(path, encoding="ascii", errors="replace").read()


def ddenv(**kw):
    return dict(("DD_" + k, v) for k, v in kw.items())


def main(argv):
    cobc = find_cobc()
    if cobc is None:
        sys.stdout.write("run_cob: SKIPPED - no cobc found (PATH, ONFLY_COBC, "
                         "or an MSYS2 mingw64 install); D-156 keeps this out "
                         "of make test\n")
        return 0
    env = cobc_env(cobc)
    if not os.path.isdir(WORK):
        os.makedirs(WORK)

    rc, out = run([cobc, "--version"], env)
    ver = out.splitlines()[0] if out else "?"
    sys.stdout.write("run_cob: %s\n" % ver)

    # 1. the proxy check the gate asks for: the generated source under
    #    the IBM dialect (and strict), then the template with COPY
    #    resolved from generated/, which keeps the template honest.
    for std, path, label in (("ibm", SRC, "generated/ONFLYDRV.cbl"),
                             ("ibm-strict", SRC, "generated/ONFLYDRV.cbl"),
                             ("ibm", TEMPLATE, "cobol/ONFLYDRV.cbl (template)")):
        rc, out = run([cobc, "-std=" + std, "-Wall", "-fsyntax-only",
                       "-I", COPYDIR, path], env)
        warns = sum(1 for l in out.splitlines() if "warning:" in l)
        errs = sum(1 for l in out.splitlines() if "error:" in l)
        sys.stdout.write("run_cob: cobc -std=%s -fsyntax-only %s: rc=%d, "
                         "%d warning(s), %d error(s)\n"
                         % (std, label, rc, warns, errs))
        if rc != 0 or errs:
            sys.stdout.write(out.encode(sys.stdout.encoding or 'ascii',
                                'replace').decode(
        sys.stdout.encoding or 'ascii'))
            raise Fail("syntax check failed under -std=%s" % std)
        kinds = sorted(set(l.split("[")[-1].rstrip("]")
                           for l in out.splitlines() if "warning:" in l))
        if kinds:
            sys.stdout.write("run_cob:   warning classes: %s\n"
                             % ", ".join(kinds))

    # 2. build
    exe = os.path.join(WORK, "onflydrv.exe")
    rc, out = run([cobc, "-std=ibm", "-x", "-o", exe, "-I", COPYDIR, SRC], env)
    if rc != 0:
        sys.stdout.write(out.encode(sys.stdout.encoding or 'ascii',
                                'replace').decode(
        sys.stdout.encoding or 'ascii'))
        raise Fail("build failed")
    sys.stdout.write("run_cob: built %s\n" % os.path.relpath(exe, ROOT))

    # 3. clean REQ deck
    ctl = os.path.join(WORK, "clean.ctl")
    req = os.path.join(WORK, "clean.req")
    write_deck(ctl, ["MODE=REQ"] + [card(*c[:4]) for c in CLEAN_CARDS])
    if os.path.exists(req):
        os.remove(req)
    rc, out = run([exe], env, cwd=WORK, extra_env=ddenv(ONFCTL=ctl, ONFREQ=req))
    sys.stdout.write("run_cob: MODE=REQ clean deck: rc=%d\n" % rc)
    for l in out.splitlines():
        sys.stdout.write("run_cob:   %s\n" % l.rstrip())
    if rc != 0:
        raise Fail("clean deck returned %d, expected 0" % rc)
    got = io.open(req, "rb").read()
    want = b"".join(request_record(*c[4]) for c in CLEAN_CARDS)
    if len(got) != len(want):
        raise Fail("clean deck wrote %d bytes, expected %d" % (len(got), len(want)))
    for i, c in enumerate(CLEAN_CARDS):
        g = got[i * L.RECORD_LEN:(i + 1) * L.RECORD_LEN]
        w = request_record(*c[4])
        if g != w:
            k = next(j for j in range(L.RECORD_LEN) if g[j:j + 1] != w[j:j + 1])
            raise Fail("record %d differs at byte %d: got %s want %s"
                       % (i + 1, k, g[:32].hex(), w[:32].hex()))
    sys.stdout.write("run_cob: %d records, %d bytes, identical to the Python "
                     "packing of the same cards (IR-JCL-03, IR-COM-04)\n"
                     % (len(CLEAN_CARDS), len(got)))
    sys.stdout.write("run_cob:   record 1 head: %s\n"
                     % got[:L.HEAD_LEN].hex())

    # 4. bad deck
    ctl = os.path.join(WORK, "bad.ctl")
    req = os.path.join(WORK, "bad.req")
    write_deck(ctl, ["MODE=REQ"] + [c[0] for c in BAD_CARDS])
    if os.path.exists(req):
        os.remove(req)
    rc, out = run([exe], env, cwd=WORK, extra_env=ddenv(ONFCTL=ctl, ONFREQ=req))
    sys.stdout.write("run_cob: MODE=REQ bad deck: rc=%d\n" % rc)
    for l in out.splitlines():
        sys.stdout.write("run_cob:   %s\n" % l.rstrip())
    if rc != 8:
        raise Fail("bad deck returned %d, expected 8 (IR-JCL-04)" % rc)
    bad_nos = [n + 2 for n, c in enumerate(BAD_CARDS) if c[1] is not None]
    for n in bad_nos:
        if ("ONF401E CONTROL CARD INVALID AT CARD %04d" % n) not in out:
            raise Fail("no ONF401E for card %d" % n)
    if out.count("ONF401E") != len(bad_nos):
        raise Fail("expected %d ONF401E lines, saw %d"
                   % (len(bad_nos), out.count("ONF401E")))
    good = [c for c in BAD_CARDS if c[1] is None and not c[0].startswith("*")]
    got = io.open(req, "rb").read()
    if len(got) != len(good) * L.RECORD_LEN:
        raise Fail("bad deck wrote %d records, expected %d"
                   % (len(got) // L.RECORD_LEN, len(good)))
    sys.stdout.write("run_cob: %d bad cards rejected by number, %d good cards "
                     "written, comment skipped, RC 8\n" % (len(bad_nos), len(good)))

    # 5. not a mode card
    ctl = os.path.join(WORK, "nomode.ctl")
    req = os.path.join(WORK, "nomode.req")
    write_deck(ctl, [card("SUGR", "0120", "1000", "000000001")])
    if os.path.exists(req):
        os.remove(req)
    rc, out = run([exe], env, cwd=WORK, extra_env=ddenv(ONFCTL=ctl, ONFREQ=req))
    sys.stdout.write("run_cob: no mode card: rc=%d\n" % rc)
    for l in out.splitlines():
        sys.stdout.write("run_cob:   %s\n" % l.rstrip())
    if rc != 8 or "AT CARD 0001" not in out or os.path.exists(req):
        raise Fail("a missing mode card must be ONF401E at card 1, RC 8, "
                   "no ONFREQ (D-158)")

    # 6. FR-BAT-04: the full report.
    #
    # Six responses, chosen so that every branch of RPT-MESSAGE and of
    # the name lookup is taken at least once:
    #
    #   1  RC 0   ONF301I, two named readouts and one that ONFNAM does
    #             not name, so the *UNNAMED* path is exercised
    #   2  RC 4   ONF201W, a reserved stimulus code, no readouts
    #   3  RC 8   ONF203E -- the code XXXX is not in the generated
    #             table, so D-270 resolves RC 8 that way
    #   4  RC 8   ONF202E -- SUGR is in the table, so the same RC 8
    #             resolves to the other message
    #   5  RC 16  ONF903S
    #   6  RC 0   1 spike in 150 ms = 6.6667 Hz.  This is the case that
    #             DISTINGUISHES D-272: rounded it prints 6.7, truncated
    #             it prints 6.6.
    ctl = os.path.join(WORK, "rpt.ctl")
    rsp = os.path.join(WORK, "rpt.rsp")
    rpt = os.path.join(WORK, "rpt.txt")
    nam = os.path.join(WORK, "rpt.nam")
    write_deck(ctl, ["MODE=RPT"])

    # IR-NAM-01 columns: 1-5 index, 6 blank, 7-40 name.  Written here
    # rather than copied from data/networks so the expected report does
    # not depend on a science artifact.
    with io.open(nam, "wb") as f:
        for ident, text in ((5, "MN9-10331"), (9, "MN9-16949")):
            f.write(("%05d %s" % (ident, text)).ljust(80).encode("ascii"))

    entries1 = [(5, 123456, 7), (9, -1, 0), (77, 500, 3)]
    recs = [response_record("SUGR", 120, 1000, 1, 0, 10000, entries1),
            response_record("WATR", 120, 1000, 1, 4, 0, []),
            response_record("XXXX", 120, 1000, 1, 8, 0, []),
            response_record("SUGR", 9999, 1000, 1, 8, 0, []),
            response_record("SUGR", 120, 1000, 1, 16, 0, []),
            response_record("SUGR", 40, 150, 3, 0, 1500, [(5, 1000, 1)])]
    io.open(rsp, "wb").write(b"".join(recs))
    if os.path.exists(rpt):
        os.remove(rpt)
    rc, out = run([exe], env, cwd=WORK,
                  extra_env=ddenv(ONFCTL=ctl, ONFRSP=rsp, ONFRPT=rpt,
                                  ONFNAM=nam))
    sys.stdout.write("run_cob: MODE=RPT: rc=%d\n" % rc)
    for l in out.splitlines():
        sys.stdout.write("run_cob:   %s\n" % l.rstrip())
    if rc != 0:
        raise Fail("RPT returned %d" % rc)
    # ONFRPT is FBA/133: fixed 133-byte records, byte 1 the ANSI
    # carriage-control character the driver writes itself (VL-59).
    raw = io.open(rpt, "rb").read()
    if len(raw) % 133 != 0:
        raise Fail("ONFRPT is %d bytes, not a multiple of 133" % len(raw))
    recs = [raw[i:i + 133].decode("ascii", "replace")
            for i in range(0, len(raw), 133)]
    lines = [(r[0], r[1:].rstrip()) for r in recs]

    def req(n, code, rate, ms, seed, rc_, out_, steps):
        return (" ", "REQUEST %4d CODE=%-8s RATE=%4d MS=%4d SEED=%9d"
                     " RC=%4d OUT=%4d STEPS=%9d"
                     % (n, code, rate, ms, seed, rc_, out_, steps))

    def msg(ident, text):
        return (" ", ("  %-8s %-48s FP=DEADBEEF" % (ident, text)).rstrip())

    def outl(k, ident, name, lat, spk, hz):
        return (" ", ("  READOUT   %4d ID=%9d %-34s LAT-US=%10d"
                      " SPIKES=%4d HZ=%9s"
                      % (k, ident, name, lat, spk, hz)).rstrip())

    want = [
        ("1", "ONFLY REPORT (FR-BAT-04)"),
        req(1, "SUGR", 120, 1000, 1, 0, 3, 10000),
        msg("ONF301I", "REQUEST COMPLETE"),
        outl(1, 5, "MN9-10331", 123456, 7, "7.0"),
        outl(2, 9, "MN9-16949", -1, 0, "0.0"),
        outl(3, 77, "*UNNAMED*", 500, 3, "3.0"),
        req(2, "WATR", 120, 1000, 1, 4, 0, 0),
        msg("ONF201W", "STIMULUS CODE RESERVED, NOT SIMULATED"),
        req(3, "XXXX", 120, 1000, 1, 8, 0, 0),
        msg("ONF203E", "UNKNOWN STIMULUS CODE"),
        req(4, "SUGR", 9999, 1000, 1, 8, 0, 0),
        msg("ONF202E", "REQUEST FIELD OUT OF RANGE"),
        req(5, "SUGR", 120, 1000, 1, 16, 0, 0),
        msg("ONF903S", "NON-FINITE STATE VALUE, REQUEST ABORTED"),
        req(6, "SUGR", 40, 150, 3, 0, 1, 1500),
        msg("ONF301I", "REQUEST COMPLETE"),
        outl(1, 5, "MN9-10331", 1000, 1, "6.7"),
    ]
    if lines != want:
        sys.stdout.write("got:\n" + "\n".join(repr(l) for l in lines) + "\n")
        sys.stdout.write("want:\n" + "\n".join(repr(l) for l in want) + "\n")
        raise Fail("FR-BAT-04 report differs")
    for cc, l in lines:
        sys.stdout.write("run_cob:   |%s|%s\n" % (cc, l))
    sys.stdout.write("run_cob: FR-BAT-04 report matches: %d FBA/133 records, "
                     "names from ONFNAM, Appendix E messages for RC 0/4/8/8/16 "
                     "with RC 8 resolved both ways (D-270), fingerprint "
                     "DEADBEEF in hex, and 6.7 Hz rounded from 6.6667 "
                     "(D-272)\n" % len(recs))

    # 7. D-265: the real Section 8.4 `path` deck, G-13 included.
    #
    # The cases above are hand-written spellings.  This one is the deck
    # the MVS job actually submits, compared against the very file the
    # x86-64 recording was built from -- so it proves not that the
    # driver handles A minus, but that it produces exactly the fourteen
    # records Section 8.4 defines, with G-13's rate of -1 among them.
    # Without D-265 the driver answered ONF401E here and wrote thirteen.
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    sys.path.insert(0, os.path.join(ROOT, "tests"))
    import mkreq                                       # noqa: E402

    ctl = os.path.join(WORK, "path.ctl")
    req = os.path.join(WORK, "path.req")
    deck = mkreq.golden_cards("path").splitlines()
    write_deck(ctl, ["MODE=REQ"] + deck)
    if os.path.exists(req):
        os.remove(req)
    rc, out = run([exe], env, cwd=WORK, extra_env=ddenv(ONFCTL=ctl,
                                                        ONFREQ=req))
    sys.stdout.write("run_cob: MODE=REQ Section 8.4 path deck: rc=%d\n" % rc)
    for l in out.splitlines():
        sys.stdout.write("run_cob:   %s\n" % l.rstrip())
    if rc != 0:
        raise Fail("the golden path deck returned %d, expected 0; every "
                   "card in it is well formed (D-265)" % rc)
    got = io.open(req, "rb").read()
    want = b"".join(mkreq.cards_to_records(mkreq.golden_cards("path")))
    if got != want:
        n = next((i for i in range(min(len(got), len(want)))
                  if got[i:i + 1] != want[i:i + 1]), min(len(got), len(want)))
        raise Fail("path deck differs at byte %d (record %d, offset %d): "
                   "got %s want %s"
                   % (n, n // L.RECORD_LEN + 1, n % L.RECORD_LEN,
                      got[n:n + 8].hex(), want[n:n + 8].hex()))
    g13 = got[12 * L.RECORD_LEN:13 * L.RECORD_LEN]
    rate13 = struct.unpack(">h", g13[12:14])[0]
    if rate13 != -1:
        raise Fail("G-13's rate is %d, expected -1" % rate13)
    sys.stdout.write("run_cob: %d records identical to tools/mkreq.py's "
                     "packing of the same deck, G-13 rate=%d (D-265)\n"
                     % (len(got) // L.RECORD_LEN, rate13))

    sys.stdout.write("run_cob: PASS on x86 GnuCOBOL (%s), IBM dialect; "
                     "this is the VL-02 proxy, not Enterprise COBOL, and says "
                     "nothing about MVT COBOL\n" % ver)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Fail as e:
        sys.stdout.write("run_cob: FAIL - %s\n" % e)
        sys.exit(1)
