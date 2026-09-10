# -*- coding: utf-8 -*-
"""Write an ONFLY network file (IR-NET-01 … IR-NET-08).

This is the emitting half of FR-PRP-07. It takes an already-decided network --
neuron count, CSR structure, weights, stimulus and readout sets, and the
propagator constants -- and serialises it to the byte stream the engine loads.

Everything numeric is big-endian (IR-NET-01) and every binary64 value is written
as its bit pattern, computed here on x86, because no target platform may convert
between decimal text and binary floating point (FR-PRP-06, NR-06).

The file contains no text at all (IR-NET-02); neuron type names travel
separately in the names file.

Layout offsets come from the generated module, never from constants written out
here, so this file and the C decoder cannot drift (NFR-MNT-01).
"""
import os
import struct
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "generated"))
sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "oracle"))

import onfcom_py as L                       # noqa: E402
from onfly_oracle.crc32 import crc32        # noqa: E402


def _pack_u32(values):
    """Pack a sequence as big-endian u32.

    numpy is used when available because these sections reach tens of millions
    of entries for a full-brain network, where struct.pack with an unpacked
    argument list is both very slow and very memory hungry.  The struct path is
    kept so the writer still works without numpy, and the two produce identical
    bytes by construction: both are big-endian u32.
    """
    if len(values) == 0:
        return b""
    try:
        import numpy as np
        return np.asarray(values, dtype=">u4").tobytes()
    except ImportError:
        return struct.pack(">%dI" % len(values), *values)


def _pack_f64(values):
    """Pack a sequence as big-endian IEEE 754 binary64 (IR-NET-01)."""
    if len(values) == 0:
        return b""
    try:
        import numpy as np
        return np.asarray(values, dtype=">f8").tobytes()
    except ImportError:
        return struct.pack(">%dd" % len(values), *values)


def _pack_neuron_table(n, type_ids, stim, readout):
    """N records of 8 bytes: type ID (u32) then flags (u32).

    Flags bit 0 marks a stimulus neuron and bit 1 a readout neuron, so the
    engine can identify both from the neuron table alone without consulting the
    separate index lists.
    """
    try:
        import numpy as np
        tab = np.zeros((n, 2), dtype=">u4")
        tab[:, 0] = np.asarray(type_ids, dtype=">u4")
        flags = np.zeros(n, dtype=">u4")
        if len(stim):
            flags[np.asarray(stim, dtype=np.int64)] |= 1
        if len(readout):
            flags[np.asarray(readout, dtype=np.int64)] |= 2
        tab[:, 1] = flags
        return tab.tobytes()
    except ImportError:
        stim_set, read_set = set(stim), set(readout)
        out = bytearray()
        for i in range(n):
            f = (1 if i in stim_set else 0) | (2 if i in read_set else 0)
            out += struct.pack(">II", type_ids[i], f)
        return bytes(out)


def _check_ascending(n, rowptr, target):
    """IR-NET-06: targets strictly ascend within each row.

    This is asserted rather than fixed up. Sorting silently would hide a defect
    in whatever produced the network, and the order is normative for
    floating-point accumulation: addition does not associate, so a row visited
    in a different order is a different answer, not the same answer computed
    differently.

    Vectorised, because a full-brain network has tens of millions of edges and
    the obvious nested Python loop over them takes minutes. The check is:
    every position that is not the first entry of a row must exceed its
    predecessor.
    """
    e = len(target)
    if e == 0:
        return
    try:
        import numpy as np
    except ImportError:
        for i in range(n):
            row = target[rowptr[i]:rowptr[i + 1]]
            for k in range(1, len(row)):
                assert row[k] > row[k - 1], (
                    "IR-NET-06: row %d targets are not strictly ascending" % i)
        return

    t = np.asarray(target)
    starts = np.asarray(rowptr[:n], dtype=np.int64)
    is_start = np.zeros(e, dtype=bool)
    is_start[starts[starts < e]] = True
    interior = ~is_start
    interior[0] = False                     # nothing precedes position 0
    bad = np.nonzero(interior & (t <= np.concatenate(([t[0]], t[:-1]))))[0]
    if len(bad):
        k = int(bad[0])
        row = int(np.searchsorted(starts, k, side="right") - 1)
        raise AssertionError(
            "IR-NET-06: row %d targets are not strictly ascending "
            "(target[%d]=%d follows %d)" % (row, k, int(t[k]), int(t[k - 1])))


def _align_up(value, to):
    rem = value % to
    return value if rem == 0 else value + (to - rem)


def build(n, rowptr, target, weight, stim, readout,
          dt_us, delay, refract, max_ms,
          u_th, u_reset, p11, p12, p22, g_eps, w_syn, v_rest,
          type_ids=None, method=1):
    """Serialise a network and return it as ``bytes``.

    Arguments mirror the header fields of SRS section 4.1. ``weight`` is a list
    of Python floats; they are written as binary64 bit patterns.

    Contract:
      * target indices must be strictly ascending within each row (IR-NET-06);
        this is asserted rather than fixed up, because silently sorting would
        hide a defect in whatever produced the network, and the order is
        normative for floating-point accumulation.
      * every payload section starts on an 8-byte boundary relative to the
        start of the file, and every padding byte is zero (IR-NET-05).
      * the header CRC covers bytes 0..159 and the payload CRC covers exactly
        the declared payload length (IR-NET-07).

    Returns the complete file as bytes. No side effects.
    """
    e = len(target)
    assert len(rowptr) == n + 1, "rowptr must have n + 1 entries"
    assert len(weight) == e, "one weight per edge"
    assert rowptr[0] == 0 and rowptr[n] == e, "rowptr must span the edge list"

    _check_ascending(n, rowptr, target)

    if type_ids is None:
        type_ids = [0] * n

    # --- payload sections, each 8-byte aligned from the start of the file ---
    # The payload begins immediately after the header; the first few bytes are
    # padding so that section one lands on a multiple of 8.
    sections = []          # (name, alignment-padded absolute offset, bytes)
    cursor = _align_up(L.NETHDR_LEN, L.NET_ALIGN)

    def add(name, blob):
        nonlocal cursor
        cursor = _align_up(cursor, L.NET_ALIGN)
        sections.append((name, cursor, blob))
        cursor += len(blob)
        return sections[-1][1]

    # Neuron table: N records of 8 bytes, type ID then flags.
    # Flags bit 0 = stimulus, bit 1 = readout.
    neur = _pack_neuron_table(n, type_ids, stim, readout)

    off_neur = add("neuron", bytes(neur))
    off_row = add("rowptr", _pack_u32(rowptr))
    off_tgt = add("target", _pack_u32(target))
    off_wgt = add("weight", _pack_f64(weight))
    off_stim = add("stim", _pack_u32(stim))
    off_read = add("readout", _pack_u32(readout))

    # --- assemble the payload, zero-filling every alignment gap -------------
    payload = bytearray()
    base = L.NETHDR_LEN
    for _name, off, blob in sections:
        gap = off - (base + len(payload))
        assert gap >= 0
        payload += b"\x00" * gap          # IR-NET-05: padding bytes are zero
        payload += blob
    paylen = len(payload)

    # --- header -------------------------------------------------------------
    values = {
        "magic": L.NET_MAGIC, "sentinel": L.NET_SENTINEL,
        "vmajor": L.NET_VMAJOR, "vminor": L.NET_VMINOR,
        "hdrlen": L.NETHDR_LEN, "flags": 0,
        "n": n, "e": e, "ns": len(stim), "nr": len(readout),
        "dtus": dt_us, "delay": delay, "refract": refract, "maxms": max_ms,
        "method": method,
        "dt": dt_us / 1000.0, "uth": u_th, "ureset": u_reset,
        "p11": p11, "p12": p12, "p22": p22, "geps": g_eps,
        "wsyn": w_syn, "vrest": v_rest,
        "offneur": off_neur, "offrow": off_row, "offtgt": off_tgt,
        "offwgt": off_wgt, "offstim": off_stim, "offread": off_read,
        "paylen": paylen, "paycrc": crc32(bytes(payload)),
        "hdrcrc": 0,                        # filled in below
    }

    header = bytearray(L.NETHDR_LEN)
    for name in L.NETHDR_ORDER:
        kind, off, size = L.NETHDR[name]
        if kind == "u32":
            struct.pack_into(">I", header, off, values[name] & 0xFFFFFFFF)
        elif kind == "u16":
            struct.pack_into(">H", header, off, values[name] & 0xFFFF)
        else:
            struct.pack_into(">d", header, off, values[name])

    # IR-NET-07: the header CRC covers everything before itself.
    hdrcrc = crc32(bytes(header[:L.NETHDR_CRC_COVERS]))
    struct.pack_into(">I", header, L.NETHDR["hdrcrc"][1], hdrcrc)

    return bytes(header) + bytes(payload)


def to_fb80(data):
    """Pad to a whole number of 80-byte records (IR-NET-08).

    On MVS the file is stored RECFM=FB LRECL=80 and the trailing partial record
    is zero-filled. The header's declared payload length stays authoritative,
    which is exactly why FR-LOD-03 forbids the engine from inferring the size
    from the dataset (TE-07 tests that).
    """
    rem = len(data) % 80
    return data if rem == 0 else data + b"\x00" * (80 - rem)
