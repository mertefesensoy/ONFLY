# -*- coding: utf-8 -*-
"""Write an AWS tape image, and the test file IR-TRN-02 asks for.

Gate G2 chooses the transport that moves a network file into TK5
intact.  D-141 opens it on the AWS tape image because tape is
binary-transparent by construction: there is no code page to translate
through, no line ending to insert and no trailing blank to truncate,
which is the whole of IR-TRN-01.

THE AWSTAPE FORMAT
------------------
A tape image is a flat file of blocks, each preceded by a six-byte
header:

    bytes 0-1   length of THIS block          little-endian
    bytes 2-3   length of the PREVIOUS block  little-endian
    byte  4     flags
    byte  5     reserved, zero

The two-byte lengths are little-endian even though the data they
describe is destined for a big-endian machine; that is the format's
own convention, not ONFLY's, and getting it backwards produces an
image Hercules reads as garbage rather than one it rejects.

Flags, from Hercules' own hetlib:

    0x80  start of a record
    0x40  a tape mark
    0x20  end of a record

A whole data block is 0xA0, start and end together.  A tape mark is a
header with zero length and 0x40, and two consecutive tape marks are
end of volume.

WHY LRECL 80 AND BLOCKS OF 32720
--------------------------------
IR-NET-08 fixes the network on MVS as RECFM=FB, LRECL=80, zero-padded
at the end, with the header's declared length authoritative rather
than the dataset size.  An FB block must be a whole number of records,
so the block size has to be a multiple of 80; 32720 is 409 records and
the largest such multiple not exceeding MVS's 32760-byte QSAM limit.

The obvious choice of 32760 is WRONG here and was written first: it is
the QSAM maximum but it is not a multiple of 80, so a tape written
that way cannot be read as the FB/80 dataset IR-NET-08 requires.  The
payload is padded with zero bytes to a record boundary for the same
reason -- 885,416 bytes becomes 885,440, which is 11,068 records.

THE TEST FILE
-------------
IR-TRN-02 requires "a test file containing every byte value 0x00-0xFF
plus a real network file".  Every byte value is the point: a transport
that translates code pages mangles some values and not others, and one
that truncates trailing blanks destroys 0x40 specifically, which is
EBCDIC space and the most likely thing to go wrong.  So the file is
built to make each failure mode identifiable rather than merely
detectable -- see build_testfile.

usage:
    python tools/mkaws.py --testfile              write the test file
    python tools/mkaws.py --wrap IN OUT           wrap IN as an AWS image
    python tools/mkaws.py --unwrap IN OUT         recover blocks from one
    python tools/mkaws.py --crc FILE              CRC-32 of a file
"""
import binascii
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

XPORT = os.path.join(ROOT, "data", "transport")
TESTFILE = os.path.join(XPORT, "tst256.bin")

# IR-NET-08's record length, and the largest whole number of those
# records that fits MVS's 32760-byte QSAM limit: 409 x 80.
LRECL = 80
BLKSIZE = 32720

AWS_NEWREC = 0x80
AWS_TAPEMARK = 0x40
AWS_ENDREC = 0x20


def aws_header(curlen, prvlen, flags):
    """Six bytes, both lengths little-endian.  See the module docstring."""
    return struct.pack("<HHBB", curlen, prvlen, flags, 0)


def wrap(src, dst, blksize=BLKSIZE, lrecl=LRECL):
    """Wrap a flat file as a single-file AWS tape image.

    Layout: the data blocks, one tape mark to end the file, and a
    second tape mark for end of volume.  MVS reads that as one
    unlabelled dataset -- which is what LABEL=(1,NL) in the JCL will
    ask for.

    The payload is zero-padded to a record boundary (IR-NET-08), so
    the image is a whole number of LRECL records and the final block
    is short only if the file does not fill it.  Returns the PADDED
    length, since that is what MVS will see.
    """
    data = open(src, "rb").read()
    if lrecl and len(data) % lrecl:
        data += b"\x00" * (lrecl - len(data) % lrecl)
    prev = 0
    out = []
    for off in range(0, len(data), blksize):
        block = data[off:off + blksize]
        out.append(aws_header(len(block), prev, AWS_NEWREC | AWS_ENDREC))
        out.append(block)
        prev = len(block)
    # Tape mark, then end of volume.
    out.append(aws_header(0, prev, AWS_TAPEMARK))
    out.append(aws_header(0, 0, AWS_TAPEMARK))
    blob = b"".join(out)
    with open(dst, "wb") as fh:
        fh.write(blob)
    nblocks = (len(data) + blksize - 1) // blksize
    return len(data), nblocks, len(blob)


def unwrap(src, dst):
    """Recover the payload from an AWS image.

    This is not decoration.  It is how the writer is checked without
    involving MVS at all: unwrapping a wrapped file must return the
    original bytes followed only by the IR-NET-08 zero padding, so a
    defect in the header arithmetic is caught on x86 in milliseconds
    instead of being misread as a transport failure on the guest.

    Note the round trip is equality on the PAYLOAD PREFIX, not on the
    whole file -- wrap() pads to a record boundary, and a check that
    demanded exact equality would fail on a correct image.
    """
    raw = open(src, "rb").read()
    pos = 0
    out = []
    marks = 0
    while pos + 6 <= len(raw):
        curlen, _prvlen, flags, _z = struct.unpack("<HHBB",
                                                   raw[pos:pos + 6])
        pos += 6
        if flags & AWS_TAPEMARK:
            marks += 1
            if marks >= 2:
                break
            continue
        marks = 0
        out.append(raw[pos:pos + curlen])
        pos += curlen
    blob = b"".join(out)
    with open(dst, "wb") as fh:
        fh.write(blob)
    return len(blob)


def build_testfile(path=TESTFILE):
    """The IR-TRN-02 test file, built so failures are identifiable.

    Four sections, each 256 bytes, and each answering a different
    question about what a transport did to the bytes:

      1  0x00..0xFF ascending      every value present at all
      2  0xFF..0x00 descending     position-dependent damage
      3  0x40 repeated             EBCDIC blank; a transport that
                                   truncates trailing blanks eats this
                                   section and nothing else
      4  0x00 and 0xFF alternating high and low bits together, and a
                                   pattern no text conversion leaves
                                   alone

    Then a 4-byte big-endian length and the CRC-32 of everything
    before it, so the file can be checked without a companion record.
    """
    parts = [bytes(bytearray(range(256))),
             bytes(bytearray(range(255, -1, -1))),
             b"\x40" * 256,
             b"\x00\xff" * 128]
    body = b"".join(parts)
    crc = binascii.crc32(body) & 0xFFFFFFFF
    blob = body + struct.pack(">I", len(body)) + struct.pack(">I", crc)
    if not os.path.isdir(XPORT):
        os.makedirs(XPORT)
    with open(path, "wb") as fh:
        fh.write(blob)
    return len(blob), crc


def crc_of(path):
    return binascii.crc32(open(path, "rb").read()) & 0xFFFFFFFF


def main(argv):
    if "--testfile" in argv:
        size, crc = build_testfile()
        print("mkaws: wrote %s" % TESTFILE)
        print("       %d bytes, body CRC-32 %08X" % (size, crc))
        print("       whole-file CRC-32 %08X" % crc_of(TESTFILE))
        return 0

    if "--wrap" in argv:
        i = argv.index("--wrap")
        src, dst = argv[i + 1], argv[i + 2]
        n, blocks, total = wrap(src, dst)
        print("mkaws: wrapped %s -> %s" % (src, dst))
        print("       %d bytes in %d blocks of <=%d, image %d bytes"
              % (n, blocks, BLKSIZE, total))
        print("       payload CRC-32 %08X" % crc_of(src))
        return 0

    if "--unwrap" in argv:
        i = argv.index("--unwrap")
        src, dst = argv[i + 1], argv[i + 2]
        n = unwrap(src, dst)
        print("mkaws: unwrapped %s -> %s, %d bytes" % (src, dst, n))
        print("       CRC-32 %08X" % crc_of(dst))
        return 0

    if "--crc" in argv:
        i = argv.index("--crc")
        path = argv[i + 1]
        print("%08X  %s" % (crc_of(path), path))
        return 0

    sys.stderr.write(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
