# -*- coding: utf-8 -*-
"""Read an ONFLY network file in Python (IR-NET-01 … IR-NET-08).

The counterpart to netwrite.py, and the reason the Python oracle can be row 1 of
the Section 8.3 determinism matrix on a real network rather than only on a
fixture built in memory.

It is also a second, independent implementation of the decode the C engine does.
Where `engine/src/onfdec.c` reads with explicit byte shifts in C89, this reads
with `struct` in Python. Agreement between them is therefore evidence about the
*format*, not a shared-code tautology.

Offsets come from the generated module, never from constants written out here,
so this file cannot drift from the C header (NFR-MNT-01).

Integrity is checked exactly as FR-LOD-02 requires, in the same order, so a file
this module accepts is one the engine would accept too.

Run:  python layout/netread.py <network file>
"""
import os
import struct
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_ROOT, "generated"))
sys.path.insert(0, os.path.join(_ROOT, "oracle"))

import onfcom_py as L                       # noqa: E402
from onfly_oracle.crc32 import crc32        # noqa: E402


class NetworkFileError(Exception):
    """Raised with the Appendix E condition the engine would report."""

    def __init__(self, code, message):
        Exception.__init__(self, "ONF%03dE %s" % (code, message))
        self.code = code


def _u32(b, off):
    return struct.unpack_from(">I", b, off)[0]


def _u16(b, off):
    return struct.unpack_from(">H", b, off)[0]


def _f64(b, off):
    return struct.unpack_from(">d", b, off)[0]


def read(path):
    """Parse and verify a network file; return a dict of its contents."""
    blob = open(path, "rb").read()
    if len(blob) < L.NETHDR_LEN:
        raise NetworkFileError(101, "file shorter than the header")

    # FR-LOD-02's checks, in the order it specifies.
    if _u32(blob, L.NETHDR["magic"][1]) != L.NET_MAGIC:
        raise NetworkFileError(101, "MAGIC CONSTANT MISMATCH")
    if _u32(blob, L.NETHDR["sentinel"][1]) != L.NET_SENTINEL:
        raise NetworkFileError(102, "BYTE-ORDER SENTINEL MISMATCH")
    if (_u16(blob, L.NETHDR["vmajor"][1]) != L.NET_VMAJOR
            or _u16(blob, L.NETHDR["vminor"][1]) != L.NET_VMINOR):
        raise NetworkFileError(103, "UNSUPPORTED FORMAT VERSION")
    if crc32(blob[:L.NETHDR_CRC_COVERS]) != _u32(blob, L.NETHDR["hdrcrc"][1]):
        raise NetworkFileError(104, "HEADER CRC MISMATCH")

    paylen = _u32(blob, L.NETHDR["paylen"][1])
    if paylen > len(blob) - L.NETHDR_LEN:
        raise NetworkFileError(106, "PAYLOAD LENGTH INCONSISTENT")
    payload = blob[L.NETHDR_LEN:L.NETHDR_LEN + paylen]
    if crc32(payload) != _u32(blob, L.NETHDR["paycrc"][1]):
        raise NetworkFileError(107, "PAYLOAD CRC MISMATCH")

    g = lambda name: _u32(blob, L.NETHDR[name][1])      # noqa: E731
    n, e = g("n"), g("e")
    ns, nr = g("ns"), g("nr")

    def u32s(off, count):
        return list(struct.unpack_from(">%dI" % count, blob, off)) if count else []

    out = {
        "n": n, "e": e,
        "rowptr": u32s(g("offrow"), n + 1),
        "target": u32s(g("offtgt"), e),
        "weight": (list(struct.unpack_from(">%dd" % e, blob, g("offwgt")))
                   if e else []),
        "stim": u32s(g("offstim"), ns),
        "readout": u32s(g("offread"), nr),
        "dt_us": g("dtus"), "delay": g("delay"), "refract": g("refract"),
        "max_ms": g("maxms"),
        "u_th": _f64(blob, L.NETHDR["uth"][1]),
        "u_reset": _f64(blob, L.NETHDR["ureset"][1]),
        "p11": _f64(blob, L.NETHDR["p11"][1]),
        "p12": _f64(blob, L.NETHDR["p12"][1]),
        "p22": _f64(blob, L.NETHDR["p22"][1]),
        "g_eps": _f64(blob, L.NETHDR["geps"][1]),
        "w_syn": _f64(blob, L.NETHDR["wsyn"][1]),
        "paycrc": _u32(blob, L.NETHDR["paycrc"][1]),
        "bytes": len(blob),
    }

    # --- v1.1 compensating-input table (D-190, D-191) ----------------------
    # nbias == 0 means the network drops nothing and needs no compensation;
    # that is the full brain and every network emitted without it.
    nbias = g("nbias")
    out["bias_rates"], out["bias_rows"] = [], []
    if nbias:
        off = g("offbias")
        rates = u32s(off, nbias)
        rowoff = off + ((4 * nbias + L.NET_ALIGN - 1)
                        // L.NET_ALIGN) * L.NET_ALIGN
        rows = []
        for r in range(nbias):
            rows.append(list(struct.unpack_from(
                ">%dd" % n, blob, rowoff + r * 8 * n)) if n else [])
        # The same three invariants netwrite.build asserts on the way out, so
        # that a file which lost them in transit is rejected here rather than
        # quietly simulated with a wrong compensating input.
        if rates != sorted(set(rates)):
            raise NetworkFileError(
                109, "COMPENSATION TABLE INVALID: rates not strictly ascending")
        if rates[0] != 0:
            raise NetworkFileError(
                109, "COMPENSATION TABLE INVALID: does not start at rate 0")
        if any(w != 0.0 for w in rows[0]):
            raise NetworkFileError(
                109, "COMPENSATION TABLE INVALID: rate 0 row is not zero")
        out["bias_rates"], out["bias_rows"] = rates, rows

    # IR-NET-06 is normative for accumulation, so it is verified rather than
    # assumed: a row read out of order would give a different answer, silently.
    tgt, row = out["target"], out["rowptr"]
    for i in range(n):
        for k in range(row[i] + 1, row[i + 1]):
            if tgt[k] <= tgt[k - 1]:
                raise NetworkFileError(
                    106, "IR-NET-06: row %d targets not strictly ascending" % i)
    return out


def as_oracle_network(spec):
    """Build an oracle kernel Network from what :func:`read` returned."""
    from onfly_oracle import kernel as _kernel
    return _kernel.Network(
        n=spec["n"], rowptr=spec["rowptr"], target=spec["target"],
        weight=spec["weight"], stim=spec["stim"], readout=spec["readout"],
        dt_us=spec["dt_us"], delay=spec["delay"], refract=spec["refract"],
        u_th=spec["u_th"], u_reset=spec["u_reset"],
        p11=spec["p11"], p12=spec["p12"], p22=spec["p22"],
        g_eps=spec["g_eps"],
        bias_rates=spec.get("bias_rates") or [],
        bias_rows=spec.get("bias_rows") or [])


def main():
    if len(sys.argv) < 2:
        sys.stderr.write("usage: netread.py <network file>\n")
        return 2
    spec = read(sys.argv[1])
    print("n=%(n)d e=%(e)d ns=%%d nr=%%d dt_us=%(dt_us)d delay=%(delay)d "
          "refract=%(refract)d max_ms=%(max_ms)d" % spec
          % (len(spec["stim"]), len(spec["readout"])))
    print("u_th=%r u_reset=%r w_syn=%r g_eps=%r"
          % (spec["u_th"], spec["u_reset"], spec["w_syn"], spec["g_eps"]))
    print("p11=%r p12=%r p22=%r" % (spec["p11"], spec["p12"], spec["p22"]))
    print("paycrc=%08X bytes=%d" % (spec["paycrc"], spec["bytes"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
