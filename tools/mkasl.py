# -*- coding: utf-8 -*-
"""IBM standard tape labels, for Gate G2 (D-145).

VL-46 to VL-49 eliminated four explanations for MVS refusing the
unlabelled tape: the device is online, the two-request mount handshake
is answered at both points, the density is honoured and irrelevant, and
the payload cannot be mistaken for a label.  What is left is that
`LABEL=(1,NL)` makes MVS read the first block expecting an 80-byte
label record where tools/mkaws.py writes 32,720 bytes.

A standard label tests that, and unlike a shortened first block it is
the format any MVS reads without special JCL and without a job class
privileged for BLP -- which VL-48 measured TK5 does not grant.

THE LAYOUT
----------
    VOL1  HDR1  HDR2  <tape mark>
    ...data blocks...  <tape mark>
    EOF1  EOF2  <tape mark> <tape mark>

Every label is exactly 80 bytes and each is its own tape block.  The
trailing double tape mark is end of volume.

EVERYTHING HERE IS EBCDIC
-------------------------
MVS reads labels in EBCDIC, which is the whole reason the payload is
safe from being mistaken for one: it begins ASCII `ONF1`, 4F4E4631,
while `VOL1` in EBCDIC is E5D6D3F1 (VL-49).  Only the invariant
subset -- A-Z, 0-9 and space -- appears in these fields, so cp037 and
cp1047 encode them identically and the choice between those codepages
cannot matter here.  That is deliberate: D-101 had to pin the card
reader's codepage because ONFLY source uses characters the two
disagree about, and a label format that needed the same care would be
a liability.

FIELD LAYOUTS
-------------
Positions are 1-based, as every IBM manual states them, and each
builder asserts its own total is 80 so a miscount fails here rather
than as an unreadable tape.

usage:
    python tools/mkasl.py --wrap IN OUT [--serial S] [--dsn D]
    python tools/mkasl.py --dump OUT
"""
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import mkaws  # noqa: E402

# The label character set is the invariant subset, so any EBCDIC
# codepage gives the same bytes.  cp037 is named rather than 1047 only
# because it is the more usual default; see the module docstring.
EBCDIC = "cp037"

LABEL = 80
SERIAL = "ONFNET"
DSN = "ONFNET"
OWNER = "ONFLY"
SYSCODE = "ONFLY"


def fld(text, width):
    """One fixed field: left-justified, blank-padded, EBCDIC."""
    t = (text + " " * width)[:width]
    return t.encode(EBCDIC)


def vol1(serial=SERIAL, owner=OWNER):
    """The volume label.

    1-4 VOL1, 5-10 serial, 11 security, 12-41 reserved,
    42-51 owner, 52-80 reserved.
    """
    rec = (fld("VOL1", 4) + fld(serial, 6) + fld(" ", 1)
           + fld("", 30) + fld(owner, 10) + fld("", 29))
    assert len(rec) == LABEL, len(rec)
    return rec


def hdr1(dsn=DSN, serial=SERIAL, created="026255", blocks=0,
         kind="HDR1"):
    """The first header, and EOF1 with the same shape.

    1-4 kind, 5-21 dataset identifier, 22-27 volume serial,
    28-31 volume sequence, 32-35 dataset sequence, 36-39 generation,
    40-41 version, 42-47 creation date, 48-53 expiry date,
    54 security, 55-60 block count, 61-73 system code, 74-80 reserved.

    The dataset identifier carries the LAST 17 characters of the
    dataset name, which for a name as short as ONFNET is the whole of
    it.  MVS compares this against the DSN in the JCL, so the two must
    agree or the volume is rejected -- which is one of the things this
    experiment is testing.
    """
    rec = (fld(kind, 4) + fld(dsn[-17:], 17) + fld(serial, 6)
           + fld("0001", 4) + fld("0001", 4) + fld("0001", 4)
           + fld("00", 2) + fld(created, 6) + fld(created, 6)
           + fld("0", 1) + fld("%06d" % blocks, 6)
           + fld(SYSCODE, 13) + fld("", 7))
    assert len(rec) == LABEL, len(rec)
    return rec


def hdr2(recfm="F", blksize=mkaws.BLKSIZE, lrecl=mkaws.LRECL,
         den="3", kind="HDR2"):
    """The second header, and EOF2 with the same shape.

    1-4 kind, 5 record format, 6-10 block length, 11-15 record length,
    16 density, 17 dataset position, 18-34 job/step identification,
    35-36 tape recording technique, 37 printer control, 38 reserved,
    39 block attribute, 40-41 reserved, 42-80 reserved.

    Record format `F` with block attribute `B` is fixed blocked, which
    is IR-NET-08's RECFM=FB.  Density 3 is 1600 BPI, matching the DCB
    the JCL supplies -- VL-49 measured that operand being honoured.
    """
    rec = (fld(kind, 4) + fld(recfm, 1) + fld("%05d" % blksize, 5)
           + fld("%05d" % lrecl, 5) + fld(den, 1) + fld("0", 1)
           + fld("", 17) + fld("", 2) + fld("", 1) + fld("", 1)
           + fld("B", 1) + fld("", 2) + fld("", 39))
    assert len(rec) == LABEL, len(rec)
    return rec


def wrap(src, dst, serial=SERIAL, dsn=DSN, blksize=mkaws.BLKSIZE,
         lrecl=mkaws.LRECL):
    """Write `src` as a standard-labelled AWS tape image.

    The payload is zero-padded to a record boundary exactly as
    mkaws.wrap does, for the same IR-NET-08 reason.  Returns
    (payload bytes, data blocks, image bytes).
    """
    data = open(src, "rb").read()
    if lrecl and len(data) % lrecl:
        data += b"\x00" * (lrecl - len(data) % lrecl)

    out = []
    prev = [0]

    def block(payload, mark=False):
        flags = (mkaws.AWS_TAPEMARK if mark
                 else mkaws.AWS_NEWREC | mkaws.AWS_ENDREC)
        n = 0 if mark else len(payload)
        out.append(mkaws.aws_header(n, prev[0], flags))
        if not mark:
            out.append(payload)
        prev[0] = n

    nblocks = (len(data) + blksize - 1) // blksize

    block(vol1(serial))
    block(hdr1(dsn, serial))
    block(hdr2(blksize=blksize, lrecl=lrecl))
    block(b"", mark=True)

    for off in range(0, len(data), blksize):
        block(data[off:off + blksize])

    block(b"", mark=True)
    block(hdr1(dsn, serial, blocks=nblocks, kind="EOF1"))
    block(hdr2(blksize=blksize, lrecl=lrecl, kind="EOF2"))
    block(b"", mark=True)
    block(b"", mark=True)

    blob = b"".join(out)
    with open(dst, "wb") as fh:
        fh.write(blob)
    return len(data), nblocks, len(blob)


def dump(path, limit=6):
    """Show the leading blocks, decoded, so a wrong label is visible.

    Written because a label that MVS rejects looks identical from the
    outside to one it never read; being able to see VOL1/HDR1/HDR2 as
    text is what distinguishes "written wrong" from "not reached".
    """
    raw = open(path, "rb").read()
    pos = 0
    n = 0
    while pos + 6 <= len(raw) and n < limit:
        curlen, _prv, flags, _z = struct.unpack("<HHBB", raw[pos:pos + 6])
        pos += 6
        if flags & mkaws.AWS_TAPEMARK:
            print("  [tape mark]")
            n += 1
            continue
        payload = raw[pos:pos + curlen]
        pos += curlen
        if curlen == LABEL:
            text = payload.decode(EBCDIC)
            print("  %-4s len=%d  %s" % (text[:4], curlen,
                                         repr(text[:50])))
        else:
            print("  data len=%d  first bytes %s"
                  % (curlen, payload[:8].hex()))
        n += 1


def main(argv):
    if "--wrap" in argv:
        i = argv.index("--wrap")
        src, dst = argv[i + 1], argv[i + 2]
        serial, dsn = SERIAL, DSN
        for j, a in enumerate(argv):
            if a == "--serial" and j + 1 < len(argv):
                serial = argv[j + 1]
            if a == "--dsn" and j + 1 < len(argv):
                dsn = argv[j + 1]
        size, blocks, total = wrap(src, dst, serial, dsn)
        print("mkasl: wrote %s" % dst)
        print("       %d payload bytes in %d blocks, image %d bytes"
              % (size, blocks, total))
        print("       serial %s, dsn %s, SL labels" % (serial, dsn))
        return 0

    if "--dump" in argv:
        i = argv.index("--dump")
        print("mkasl: leading blocks of %s" % argv[i + 1])
        dump(argv[i + 1])
        return 0

    sys.stderr.write(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
