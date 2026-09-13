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
from onfly_oracle import kernel as okernel  # noqa: E402

OK, MAGIC, SENT, VER, HCRC, MEM, PLEN, PCRC = 0, 101, 102, 103, 104, 105, 106, 107
BIAS = 109          # ONF109E COMPENSATION TABLE INVALID (IR-NET-09, D-190)


_NET_ARGS = {}


def build_oracle_network():
    """The same network sample_network() serialised, as an oracle Network."""
    a = _NET_ARGS
    return okernel.Network(
        n=a["n"], rowptr=a["rowptr"], target=a["target"], weight=a["weight"],
        stim=a["stim"], readout=a["readout"], dt_us=a["dt_us"],
        delay=a["delay"], refract=a["refract"], u_th=a["u_th"],
        u_reset=a["u_reset"], p11=a["p11"], p12=a["p12"], p22=a["p22"],
        g_eps=a["g_eps"],
        bias_rates=a.get("bias_rates", ()), bias_rows=a.get("bias_rows", ()))


# v1.1 compensating-input table for the sample network (D-190, D-191).
#
# The fixture carries a real table rather than none, so that every path that
# uses it -- TE-01..TE-09 here, the embedded-network engine path in
# tests/tstsyn.c, and the oracle comparison -- exercises the compensating
# input instead of only its absence.  A code path tested nowhere but on the
# platform that is hardest to test is a code path nobody has tested.
#
# The values are exact binary fractions (2^-7 and 2^-5 times a small integer)
# so that a reader can check an arrival by hand and no rounding hides a
# mistake.  The rate 0 row is zero, which netwrite.build asserts and the
# decoder re-checks on the raw bytes: ACC-2 requires a rate 0 request to
# produce no spike anywhere.
_BIAS_RATES = [0, 40, 200]


def _bias_rows(n):
    return [[0.0] * n,
            [0.0078125 * ((i % 4) + 1) for i in range(n)],
            [0.03125 * ((i % 4) + 1) for i in range(n)]]


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
    _NET_ARGS.update(dict(
        n=n, rowptr=rowptr, target=target, weight=weight,
        stim=[0, 1, 2, 3], readout=[12, 13, 14, 15],
        dt_us=100, delay=18, refract=22,
        u_th=7.0, u_reset=0.0,
        p11=0.9950124791926823, p12=0.004937935295309022,
        p22=0.9801986733067553, g_eps=1e-300,
        bias_rates=_BIAS_RATES, bias_rows=_bias_rows(n)))
    return netwrite.build(
        n=n, rowptr=rowptr, target=target, weight=weight,
        stim=[0, 1, 2, 3], readout=[12, 13, 14, 15],
        dt_us=100, delay=18, refract=22, max_ms=5000,
        u_th=7.0, u_reset=0.0,
        p11=0.9950124791926823, p12=0.004937935295309022,
        p22=0.9801986733067553, g_eps=1e-300, w_syn=0.275, v_rest=-52.0,
        bias_rates=_BIAS_RATES, bias_rows=_bias_rows(n))


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


def repair_paycrc(data):
    """Recompute the payload CRC, then the header CRC that covers it.

    TE-10's cases corrupt the compensating-input table, which lives in the
    payload.  Without this they would stop at check 6 and prove only that the
    payload CRC works -- which TE-05 already proves.  Resealing both CRCs
    models a PRODUCER that emitted a malformed table, which is the failure
    ONF109E exists for; a TRANSPORT that damaged it is TE-05's case.
    """
    b = bytearray(data)
    paylen = struct.unpack_from(">I", b, L.NETHDR["paylen"][1])[0]
    struct.pack_into(">I", b, L.NETHDR["paycrc"][1],
                     crc32(bytes(b[L.NETHDR_LEN:L.NETHDR_LEN + paylen])))
    return repair_hdrcrc(bytes(b))


def bias_row_offset(data):
    """Absolute offset of the compensating table's first f64 row."""
    off = struct.unpack_from(">I", data, L.NETHDR["offbias"][1])[0]
    nbias = struct.unpack_from(">I", data, L.NETHDR["nbias"][1])[0]
    pad = ((4 * nbias + L.NET_ALIGN - 1) // L.NET_ALIGN) * L.NET_ALIGN
    return off + pad


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

    # --- TE-10: a malformed compensating-input table (IR-NET-09, D-190) --
    # These reach onfldp, not onfdec, so they need the "run" argument; the
    # header checks above stop before the payload is converted.  Each one
    # reseals both CRCs, so what fails is the table check and nothing else.
    #
    # The rate 0 case is the one that matters most.  ACC-2 promises zero
    # spikes everywhere at rate 0 on every platform and backend; a table
    # whose first row were non-zero would break that silently, everywhere at
    # once, and the only thing standing between a mis-emitted network and
    # that outcome is this check.
    bias_off = bias_row_offset(good)
    te10 = [
        ("TE-10 rate 0 row not zero",
         repair_paycrc(patch(good, bias_off, struct.pack(">d", 1e-300)))),
        ("TE-10 rates not ascending",
         repair_paycrc(patch(good, struct.unpack_from(
             ">I", good, L.NETHDR["offbias"][1])[0] + 4,
             struct.pack(">I", 0)))),
        ("TE-10 table does not start at 0",
         repair_paycrc(patch(good, struct.unpack_from(
             ">I", good, L.NETHDR["offbias"][1])[0],
             struct.pack(">I", 1)))),
    ]
    for name, data in te10:
        path = os.path.join(tmp, name.split()[0] + "_%d.net" % len(lines))
        with open(path, "wb") as fh:
            fh.write(data)
        proc = subprocess.Popen([exe, path, "0", "run"], stdout=subprocess.PIPE)
        out, _ = proc.communicate()
        got = None
        for line in out.decode("ascii", "replace").splitlines():
            if line.startswith("LOAD"):
                got = int(line.split("=")[1])
        if got == BIAS:
            passed += 1
            lines.append("  ok   %-36s LOAD rc=%d" % (name, got))
        else:
            failed += 1
            lines.append("  FAIL %-36s LOAD rc=%s want=%d"
                         % (name, got, BIAS))

    # --- end-to-end: file on disk -> decode -> load -> simulate ----------
    # This is the first path that goes all the way from a serialised network to
    # per-neuron results, so it exercises onfldp's big-endian conversion and the
    # CSR structure checks, not just the header integrity checks above.
    path = os.path.join(tmp, "endtoend.net")
    with open(path, "wb") as fh:
        fh.write(good)
    proc = subprocess.Popen([exe, path, "0", "run"], stdout=subprocess.PIPE)
    out, _ = proc.communicate()
    cspk, cfst, loadrc, runrc = {}, {}, None, None
    for line in out.decode("ascii", "replace").splitlines():
        p_ = line.split()
        if line.startswith("LOAD"):
            loadrc = int(p_[1].split("=")[1])
        elif line.startswith("RUN "):
            runrc = int([t for t in p_ if t.startswith("rc=")][0][3:])
        elif line.startswith("OUT"):
            f = dict(t.split("=", 1) for t in p_[1:])
            cspk[int(f["i"])] = int(f["s"])
            cfst[int(f["i"])] = int(f["f"])

    if loadrc == 0 and runrc == 0:
        net = build_oracle_network()
        ospk, ofst = okernel.run(net, 1, 120, 500)
        mismatch = [i for i in range(net.n)
                    if (cspk.get(i), cfst.get(i)) != (ospk[i], ofst[i])]
        if mismatch:
            failed += 1
            lines.append("  FAIL end-to-end: %d of %d neurons differ from the "
                         "oracle (first: %d)" % (len(mismatch), net.n, mismatch[0]))
        else:
            passed += 1
            lines.append("  ok   %-36s %d neurons match the oracle, %d spikes"
                         % ("end-to-end file->decode->load->run",
                            net.n, sum(ospk)))
    else:
        failed += 1
        lines.append("  FAIL end-to-end: LOAD rc=%s RUN rc=%s" % (loadrc, runrc))

    print("run_dec: %d passed, %d failed" % (passed, failed))
    for l in lines:
        print(l)
    print("  (file %d bytes, FB-padded %d bytes -- the engine trusts the header,"
          % (len(good), len(netwrite.to_fb80(good))))
    print("   not the dataset size)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
