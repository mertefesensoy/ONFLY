# -*- coding: utf-8 -*-
"""Reference response fingerprint (IR-COM-05, oracle O-1).

Independent of the C implementation: it builds the canonical byte string from
the specification text, not from a shared helper, so agreement between the two
is evidence rather than an echo.

IR-COM-05: the CRC-32 of the network payload CRC, then the numeric stimulus ID,
seed, rate, duration, return code, output count and step count, then each
output entry (ID, latency, spike count) for entries below the output count --
each encoded as a big-endian 32-bit integer.

Text fields are excluded on purpose: the stimulus code's four characters are
different bytes on ASCII and EBCDIC hosts, so including them would make the
same request fingerprint differently on MVS than on Linux and break ACC-5 for
reasons unrelated to the simulation. The code travels as a number (D-39).
"""
import struct

from .crc32 import crc32


def fingerprint(paycrc, stim_id, seed, rate, sim_ms, rc, outputs, steps):
    """Return the fingerprint as an int in [0, 2**32).

    ``outputs`` is a sequence of (neuron_id, latency_us, spikes); only the first
    ``len(outputs)`` entries exist and all of them are included, so the caller
    passes exactly the valid entries rather than a padded array.
    """
    parts = [paycrc & 0xFFFFFFFF, stim_id, seed, rate, sim_ms, rc,
             len(outputs), steps]
    canon = b"".join(struct.pack(">i", v) if v < 0 else struct.pack(">I", v)
                     for v in parts)
    for nid, lat, spk in outputs:
        for v in (nid, lat, spk):
            canon += struct.pack(">i", v) if v < 0 else struct.pack(">I", v)
    return crc32(canon)
