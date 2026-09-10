# -*- coding: utf-8 -*-
"""CRC-32/ISO-HDLC reference (IR-NET-07, oracle O-4).

The SRS names Python's ``zlib.crc32`` as the reference.  This module does not
call it.  It implements the algorithm from its parameters and is then checked
*against* zlib in the tests, so agreement is evidence rather than tautology --
a wrapper around zlib could not detect a wrong polynomial or a wrong reflection
convention, because it would share the bug.

Parameters (CRC-32/ISO-HDLC, the "zlib polynomial" of IR-NET-07):

    width    32
    poly     0x04C11DB7, reflected to 0xEDB88320 for the LSB-first form
    init     0xFFFFFFFF
    refin    true      bits of each input byte are processed least significant first
    refout   true      the register is already in reflected form, so no final swap
    xorout   0xFFFFFFFF

All arithmetic is unsigned 32-bit (NR-11).  The mask after every shift is what
keeps that true in Python, where integers do not wrap.

Contract:
    crc32(data, crc=0) -> int in [0, 2**32)
      data  a bytes-like object
      crc   a running value from a previous call, so a stream can be checksummed
            in pieces; 0 starts a fresh computation
    Side effects: none.  The table is built once at import.
"""

POLY_REFLECTED = 0xEDB88320
INIT = 0xFFFFFFFF
XOROUT = 0xFFFFFFFF
MASK32 = 0xFFFFFFFF


def _build_table():
    """Byte-at-a-time table for the reflected form.

    Entry i is the register state after feeding byte i into a zero register.
    Built by explicit bit loops rather than any library call.
    """
    table = []
    for i in range(256):
        reg = i
        for _ in range(8):
            if reg & 1:
                reg = (reg >> 1) ^ POLY_REFLECTED
            else:
                reg >>= 1
        table.append(reg & MASK32)
    return table


TABLE = _build_table()


def crc32(data, crc=0):
    """Return the CRC-32/ISO-HDLC of ``data``, continuing from ``crc``."""
    reg = (crc ^ INIT) & MASK32
    for byte in bytearray(data):
        reg = TABLE[(reg ^ byte) & 0xFF] ^ (reg >> 8)
        reg &= MASK32
    return (reg ^ XOROUT) & MASK32


def crc32_bitwise(data, crc=0):
    """Bit-at-a-time form of the same CRC.

    Deliberately independent of :func:`crc32` and of its table, so the two can
    be cross-checked.  Too slow for production use; used only by the tests and
    to generate vectors for the C implementation.
    """
    reg = (crc ^ INIT) & MASK32
    for byte in bytearray(data):
        reg ^= byte
        for _ in range(8):
            if reg & 1:
                reg = (reg >> 1) ^ POLY_REFLECTED
            else:
                reg >>= 1
            reg &= MASK32
    return (reg ^ XOROUT) & MASK32
