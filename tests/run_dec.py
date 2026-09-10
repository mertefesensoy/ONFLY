# -*- coding: utf-8 -*-
"""TE-01 … TE-08: network integrity checks against deliberately corrupt files.

Every case here corrupts exactly one thing and asserts the engine reports the
specific Appendix E condition for it. The point is not that a bad file is
rejected -- almost any check would do that -- but that the engine says *which*
check failed, because that is what tells an operator whether to re-send the file
in binary mode or to rebuild it (NFR-REL-01: no abnormal outcome is silent).

Run:  python tests/run_dec.py <path-to-tstdec-executable>
"""
import os
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for sub in ("layout", "generated", "oracle"):
    sys.path.insert(0, os.path.join(ROOT, sub))

import netwrite                       # noqa: E402
import onfcom_py as L                 # noqa: E402
from onfly_oracle.crc32 import crc32  # noqa: E402

OK, MAGIC, SENT, VER, HCRC, MEM, PLEN, PCRC = 0, 101, 102, 103, 104, 105, 106, 107


def sample_network():
    """A small, valid network: 16 neurons, a simple ascending CSR structure."""
    n = 16
    rowptr, target, weight = [0], [], []
    for i in range(n):
        for k in range(3):
            t = (i + 1 + k * 3) % n
            target.append(t)
        # IR-NET-06 requires strictly ascending targets within a row.
        row = sorted(set(target[rowptr[-1]:]))
        del target[rowptr[-1]:]
        target.extend(row)
        for _ in row:
            weight.append(0.275 * (len(weight) % 5 + 1))
        rowptr.append(len(target))
    return netwrite.build(
        n=n, rowptr=rowptr, target=target, weight=weight,
        stim=[0, 1, 2, 3], readout=[12, 13, 14, 15],
        dt_us=100, delay=18, refract=22, max_ms=5000,
        u_th=7.0, u_reset=0.0,
        p11=0.9950124791926823, p12=0.004937935295309022,
        p22=0.9801986733067553, g_eps=1e-300, w_syn=0.275, v_rest=-52.0)


def patch(data, offset, raw):
    b = bytearray(data)
    b[offset:offset + len(raw)] = raw
    return bytes(b)


def repair_hdrcrc(data):
    """Recompute the header CRC so a case tests its own check, not check 4."""
    b = bytearray(data)
    struct.pack_into(">I", b, L.NETHDR["hdrcrc"][1],
                     crc32(bytes(b[:L.NETHDR_CRC_COVERS])))
    return bytes(b)


def cases(good):
    off = lambda name: L.NETHDR[name][1]          # noqa: E731
    out = []

    out.append(("TE-00 valid file", good, 0, OK))

    # TE-01: not an ONFLY network, or the first bytes were mangled.
    out.append(("TE-01 corrupt magic",
                repair_hdrcrc(patch(good, off("magic"), b"\xDE\xAD\xBE\xEF")),
                0, MAGIC))

    # TE-02: the sentinel is what catches a text-mode or EBCDIC transfer.
    out.append(("TE-02 corrupt sentinel",
                repair_hdrcrc(patch(good, off("sentinel"), b"\x04\x03\x02\x01")),
                0, SENT))

    # TE-03: engine and network format versions differ.
    out.append(("TE-03 wrong version",
                repair_hdrcrc(patch(good, off("vmajor"), b"\x00\x09")),
                0, VER))

    # TE-04: header corrupted in transport.  Flip a byte the CRC covers and do
    # NOT repair it -- that is the whole point of this case.
    out.append(("TE-04 header CRC mismatch",
                patch(good, off("refract"), b"\x00\x00\x00\x63"),
                0, HCRC))

    # TE-06: a truncated transfer.  The declared payload length now exceeds
    # what the file actually contains.
    big = struct.pack(">I", struct.unpack(">I", good[off("paylen"):off("paylen") + 4])[0] + 4096)
    out.append(("TE-06 payload length inconsistent",
                repair_hdrcrc(patch(good, off("paylen"), big)),
                0, PLEN))

    # TE-05: payload corrupted in transport, header intact.
    payload_byte = L.NETHDR_LEN + 40
    flipped = bytearray(good)
    flipped[payload_byte] ^= 0xFF
    out.append(("TE-05 payload CRC mismatch", bytes(flipped), 0, PCRC))

    # TE-08: the network exceeds the configured region (FR-LOD-04, NFR-MEM-01).
    out.append(("TE-08 exceeds memory limit", good, 64, MEM))
    out.append(("TE-08 within memory limit", good, 1 << 20, OK))

    # TE-07: an FB dataset is zero-padded to an 80-byte record boundary, so the
    # file is LONGER than the payload.  The engine must trust the header's
    # declared length, not the dataset size (FR-LOD-03, IR-NET-08).
    out.append(("TE-07 FB zero padding tolerated",
                netwrite.to_fb80(good), 0, OK))

    return out


def main():
    if len(sys.argv) < 2:
        sys.stderr.write("usage: run_dec.py <tstdec executable>\n")
        return 2
    exe = os.path.abspath(sys.argv[1])
    if not os.path.exists(exe):
        sys.stderr.write("not found: %s\n" % exe)
        return 2

    good = sample_network()
    tmp = tempfile.mkdtemp(prefix="onfly_dec_")
    passed = failed = 0
    lines = []

    for name, data, limit, want in cases(good):
        path = os.path.join(tmp, name.split()[0] + "_%d.net" % limit)
        with open(path, "wb") as fh:
            fh.write(data)
        argv = [exe, path] + ([str(limit)] if limit else [])
        proc = subprocess.Popen(argv, stdout=subprocess.PIPE)
        out, _ = proc.communicate()
        got = None
        for line in out.decode("ascii", "replace").splitlines():
            if line.startswith("RESULT"):
                for tok in line.split():
                    if tok.startswith("rc="):
                        got = int(tok[3:])
        if got == want:
            passed += 1
            lines.append("  ok   %-36s rc=%d" % (name, got))
        else:
            failed += 1
            lines.append("  FAIL %-36s rc=%s want=%d" % (name, got, want))

    print("run_dec: %d passed, %d failed" % (passed, failed))
    for l in lines:
        print(l)
    print("  (file %d bytes, FB-padded %d bytes -- the engine trusts the header,"
          % (len(good), len(netwrite.to_fb80(good))))
    print("   not the dataset size)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
