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

# ---------------------------------------------------------------------------
# Network file header (IR-NET-01, SRS section 4.1 table).
#
# 164 bytes.  The header CRC at offset 160 covers bytes 0..159; the payload CRC
# at 156 covers exactly the declared payload length (IR-NET-07).  All integers
# are big-endian; all f64 values are IEEE 754 binary64, big-endian, arriving as
# bit patterns computed on x86 (FR-PRP-06, NR-06).
#
# Generated rather than hand-written for the same reason as the COMMAREA: this
# header is read by C on three platforms and written by Python, and a
# transcription slip between them would surface as a corrupt-network error at
# best and as a wrong answer at worst.
# ---------------------------------------------------------------------------

NETHDR_LEN = 164
NETHDR_CRC_COVERS = 160     # header CRC covers bytes 0..159

# (name, kind, offset, size)  kind: u32 | u16 | f64
NETHDR = [
    ("magic",   "u32",   0, 4), ("sentinel", "u32",   4, 4),
    ("vmajor",  "u16",   8, 2), ("vminor",   "u16",  10, 2),
    ("hdrlen",  "u32",  12, 4), ("flags",    "u32",  16, 4),
    ("n",       "u32",  20, 4), ("e",        "u32",  24, 4),
    ("ns",      "u32",  28, 4), ("nr",       "u32",  32, 4),
    ("dtus",    "u32",  36, 4), ("delay",    "u32",  40, 4),
    ("refract", "u32",  44, 4), ("maxms",    "u32",  48, 4),
    ("method",  "u32",  52, 4),
    ("dt",      "f64",  56, 8), ("uth",      "f64",  64, 8),
    ("ureset",  "f64",  72, 8), ("p11",      "f64",  80, 8),
    ("p12",     "f64",  88, 8), ("p22",      "f64",  96, 8),
    ("geps",    "f64", 104, 8), ("wsyn",     "f64", 112, 8),
    ("vrest",   "f64", 120, 8),
    ("offneur", "u32", 128, 4), ("offrow",   "u32", 132, 4),
    ("offtgt",  "u32", 136, 4), ("offwgt",   "u32", 140, 4),
    ("offstim", "u32", 144, 4), ("offread",  "u32", 148, 4),
    ("paylen",  "u32", 152, 4), ("paycrc",   "u32", 156, 4),
    ("hdrcrc",  "u32", 160, 4),
]

# IR-NET-03: proposed value, final at format version 1.0 when TBD-09 closes.
NET_MAGIC = 0x4F4E4631
# IR-NET-04: any other decoded value means the transport swapped or translated
# bytes; that fails with ONF102E.
NET_SENTINEL = 0x01020304
NET_VMAJOR = 1
NET_VMINOR = 0

# IR-NET-05: payload sections start on 8-byte boundaries relative to the start
# of the file, and padding bytes are zero.
NET_ALIGN = 8


def _check_net():
    cur = 0
    for name, kind, off, size in NETHDR:
        assert off == cur, "network header gap/overlap at %s: %d != %d" % (name, cur, off)
        # Natural alignment, so a big-endian host could overlay the header
        # directly; little-endian hosts still decode by explicit shifts.
        assert off % size == 0, "network header %s at %d is not %d-aligned" % (name, off, size)
        cur += size
    assert cur == NETHDR_LEN, "network header is %d bytes, expected %d" % (cur, NETHDR_LEN)
    assert dict((f[0], f[2]) for f in NETHDR)["hdrcrc"] == NETHDR_CRC_COVERS,         "the header CRC must sit immediately after the bytes it covers"

_check_net()
