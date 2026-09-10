# -*- coding: utf-8 -*-
"""ONFLY record layout: the single master definition.

Contract (IR-COM-01, D-18): this module is the ONLY place the COMMAREA layout
is written down.  The COBOL copybook, the C header and the Python struct
accessors are all generated from it by layout/generate.py.  Generated files
carry a "DO NOT EDIT" banner and are never edited by hand.

Why a master definition at all: the same 412 bytes are read by a COBOL driver
compiled in 1968-era MVT COBOL, by a C engine compiled by GCCMVS, and by a
Python oracle.  Three hand-maintained copies of one layout drift silently, and
the drift shows up as a wrong answer, not as a build error.

Invariants asserted at import time:
  * total record length is exactly 412 bytes (IR-COM section 4.3)
  * every 2-byte field sits at an even offset and every 4-byte field at a
    multiple of 4 (IR-COM-03), so C and COBOL agree with no packing directives
  * fields tile the record with no gaps and no overlaps
  * every declared value range fits the COBOL PIC digit count (IR-COM-02), so
    the TRUNC compiler option can never alter a stored value
"""

RECORD_LEN = 412
MAX_OUT = 32          # IR-COM: ONF-OUT OCCURS 32; header R <= 32 (IR-NET)
OUT_ENTRY_LEN = 12

# kind -> (byte width, COBOL PIC/usage, C accessor family)
#   'chr'  fixed-length alphanumeric, host code page, no translation
#   'i16'  signed halfword binary, big-endian on the wire
#   'i32'  signed fullword binary, big-endian on the wire
#   'byt'  opaque bytes (never code-page translated)

class Field(object):
    def __init__(self, name, cobol, kind, off, size, digits=None,
                 lo=None, hi=None, note=""):
        self.name = name        # C / Python identifier
        self.cobol = cobol      # COBOL data-name
        self.kind = kind
        self.off = off
        self.size = size
        self.digits = digits    # COBOL PIC digit count for binary fields
        self.lo = lo
        self.hi = hi
        self.note = note

# ---------------------------------------------------------------------------
# Fixed part of the record, offsets 0..27 (SRS section 4.3 table)
# ---------------------------------------------------------------------------
HEAD = [
    Field("stimcode", "ONF-STIM-CODE",  "chr",  0, 8, note="'SUGR','WATR','BITR', space padded"),
    Field("seed",     "ONF-SEED",       "i32",  8, 4, digits=9, lo=0, hi=999999999),
    Field("stimrate", "ONF-STIM-RATE",  "i16", 12, 2, digits=4, lo=0, hi=9999, note="Hz"),
    Field("simms",    "ONF-SIM-MS",     "i16", 14, 2, digits=4, lo=1, hi=9999, note="ms, bounded by header maximum"),
    Field("rc",       "ONF-RC",         "i16", 16, 2, digits=4, lo=0, hi=9999, note="return code, Appendix E"),
    Field("outcount", "ONF-OUT-COUNT",  "i16", 18, 2, digits=4, lo=0, hi=MAX_OUT),
    Field("fprint",   "ONF-FPRINT",     "byt", 20, 4, note="CRC-32 big-endian bytes, IR-COM-05"),
    Field("steps",    "ONF-STEPS",      "i32", 24, 4, digits=9, lo=0, hi=999999999),
]
HEAD_LEN = 28

# ---------------------------------------------------------------------------
# One ONF-OUT entry, offsets relative to the start of the entry
# ---------------------------------------------------------------------------
OUT = [
    Field("id",       "ONF-OUT-ID",      "i32", 0, 4, digits=9, lo=0, hi=999999999),
    Field("latus",    "ONF-OUT-LAT-US",  "i32", 4, 4, digits=9, lo=-1, hi=999999999,
          note="first-spike latency in microseconds, -1 if the neuron did not spike"),
    Field("spikes",   "ONF-OUT-SPIKES",  "i16", 8, 2, digits=4, lo=0, hi=9999),
    Field("filler",   "FILLER",          "byt",10, 2, note="zero"),
]

# ---------------------------------------------------------------------------
# Self-validation.  These run on import, so a bad edit to this file fails the
# build rather than producing a plausible-looking wrong layout.
# ---------------------------------------------------------------------------
def _check():
    # tiling and alignment of the fixed part
    cur = 0
    for f in HEAD:
        assert f.off == cur, "gap/overlap at %s: expected %d got %d" % (f.name, cur, f.off)
        if f.size == 2:
            assert f.off % 2 == 0, "IR-COM-03: %s halfword at odd offset %d" % (f.name, f.off)
        if f.size == 4 and f.kind in ("i32",):
            assert f.off % 4 == 0, "IR-COM-03: %s fullword at offset %d" % (f.name, f.off)
        cur += f.size
    assert cur == HEAD_LEN, "fixed part is %d bytes, expected %d" % (cur, HEAD_LEN)

    # tiling and alignment of one OUT entry
    cur = 0
    for f in OUT:
        assert f.off == cur, "gap/overlap at OUT.%s" % f.name
        cur += f.size
    assert cur == OUT_ENTRY_LEN, "OUT entry is %d bytes, expected %d" % (cur, OUT_ENTRY_LEN)

    # every OUT entry must itself land on a 4-byte boundary so its i32 fields do
    for k in range(MAX_OUT):
        base = HEAD_LEN + k * OUT_ENTRY_LEN
        assert base % 4 == 0, "OUT entry %d starts at %d, not a multiple of 4" % (k, base)
        for f in OUT:
            if f.kind == "i32":
                assert (base + f.off) % 4 == 0
            if f.size == 2:
                assert (base + f.off) % 2 == 0

    assert HEAD_LEN + MAX_OUT * OUT_ENTRY_LEN == RECORD_LEN, "record length mismatch"

    # IR-COM-02: declared ranges must fit the PIC digit count, so TRUNC is inert
    for f in HEAD + OUT:
        if f.digits is not None:
            limit = 10 ** f.digits - 1
            assert abs(f.lo) <= limit and abs(f.hi) <= limit, \
                "IR-COM-02: %s range exceeds PIC S9(%d)" % (f.name, f.digits)
            # and it must fit the binary width COBOL will allocate
            width = {2: 15, 4: 31}[f.size]
            assert -(2 ** width) <= f.lo and f.hi <= 2 ** width - 1, \
                "%s range exceeds %d-byte binary" % (f.name, f.size)

_check()
