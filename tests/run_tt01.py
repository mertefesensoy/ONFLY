# -*- coding: utf-8 -*-
"""TT-01 driver: check the C 64-bit arithmetic against a Python oracle.

The C binary already checks itself against generated/onfivec.h.  That is the
check ONFLYENG performs at startup, and it is necessary -- but on its own it
proves only that the compiler agrees with the table.  If tools/genint.py had
computed an expectation wrongly, the table would be wrong and the C self-test
would pass anyway.

So this script does not trust the table.  It reads the *operands* out of the
generated header, recomputes every expectation from scratch with exact Python
integers, and then checks three things:

  1. the table's stored expectation equals Python's -- catches a generator bug;
  2. what the C binary actually computed equals Python's -- catches a compiler
     or engine bug, which on S/370 is risk R-01;
  3. onfitst returned 0, and onfirun reported no cross-check failure.

Section 8.2 makes Python the oracle for ONFLY.  The bit assignments for the
comparison groups are read from the header rather than restated here, so a
change to them cannot make this script quietly disagree with the engine.

Run:  python tests/run_tt01.py <path-to-tstint-executable>
Exit status 0 when every vector agrees, 1 otherwise.
"""
import io
import os
import re
import subprocess
import sys

M64 = (1 << 64) - 1
SIGN = 1 << 63

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
HEADER = os.path.join(ROOT, "generated", "onfivec.h")

VEC_RE = re.compile(
    r"^\s*\{\s*0x([0-9A-Fa-f]{8})U,\s*0x([0-9A-Fa-f]{8})U,"
    r"\s*0x([0-9A-Fa-f]{8})U,\s*0x([0-9A-Fa-f]{8})U,"
    r"\s*0x([0-9A-Fa-f]{8})U,\s*0x([0-9A-Fa-f]{8})U\s*\},\s*$")
ARR_RE = re.compile(r"^static const struct onfiv (\w+)\[(\d+)\] = \{")
GRP_RE = re.compile(r'^\s*\{\s*"(\w+)",\s*(\d+)U,\s*(\w+)\s*\},\s*$')
CMP_RE = re.compile(r"^#define ONFI_CMP_(\w+)\s+0x([0-9A-Fa-f]+)U")


def parse_header(path):
    """Return (groups, cmpbits).

    groups is a list of (name, [vector, ...]) in ONFI_OP_* order, where each
    vector is the six-tuple (ahi, alo, bhi, blo, rhi, rlo).
    """
    text = io.open(path, encoding="ascii").read()
    arrays = {}
    cmpbits = {}
    current = None
    ingrp = False
    order = []

    for line in text.splitlines():
        m = CMP_RE.match(line)
        if m:
            cmpbits[m.group(1).lower()] = int(m.group(2), 16)
            continue
        m = ARR_RE.match(line)
        if m:
            current = m.group(1)
            arrays[current] = []
            continue
        if line.startswith("static const struct onfivg"):
            ingrp = True
            current = None
            continue
        if ingrp:
            m = GRP_RE.match(line)
            if m:
                order.append((m.group(1), int(m.group(2)), m.group(3)))
                continue
            if line.startswith("};"):
                ingrp = False
            continue
        if current is not None:
            m = VEC_RE.match(line)
            if m:
                arrays[current].append(tuple(int(g, 16) for g in m.groups()))
            elif line.startswith("};"):
                current = None

    groups = []
    for name, count, arr in order:
        if arr not in arrays:
            raise SystemExit("run_tt01: group %s names missing array %s"
                             % (name, arr))
        if len(arrays[arr]) != count:
            raise SystemExit("run_tt01: group %s declares %d vectors, array "
                             "holds %d" % (name, count, len(arrays[arr])))
        groups.append((name, arrays[arr]))
    if not groups:
        raise SystemExit("run_tt01: no groups parsed from %s" % path)
    return groups, cmpbits


def cmpword(a, b, bits):
    r = 0
    if a < b:
        r |= bits["lt"]
    if a <= b:
        r |= bits["le"]
    if a == b:
        r |= bits["eq"]
    if a > b:
        r |= bits["gt"]
    if a >= b:
        r |= bits["ge"]
    if a != b:
        r |= bits["ne"]
    return r


def signed(v):
    return v - (1 << 64) if (v & SIGN) else v


def expected(name, a, b, blo, bits):
    """Recompute one vector with exact Python integers."""
    if name == "MUL":
        return (a * b) & M64
    if name == "DIV":
        return a // b
    if name == "MOD":
        return a % b
    if name == "SHL":
        return (a << blo) & M64
    if name == "SHR":
        return a >> blo
    if name == "ADD":
        return (a + b) & M64
    if name == "SUB":
        return (a - b) & M64
    if name == "CMPU":
        return cmpword(a, b, bits)
    if name == "CMPS":
        return cmpword(signed(a), signed(b), bits)
    raise SystemExit("run_tt01: no oracle for group %s" % name)


def main():
    if len(sys.argv) != 2:
        sys.stderr.write("usage: run_tt01.py <tstint executable>\n")
        return 2
    exe = os.path.abspath(sys.argv[1])
    if not os.path.exists(exe):
        sys.stderr.write("run_tt01: not found: %s\n" % exe)
        return 2
    if not os.path.exists(HEADER):
        sys.stderr.write("run_tt01: %s missing; run `python tools/genint.py`\n"
                         % HEADER)
        return 2

    groups, bits = parse_header(HEADER)
    for want in ("lt", "le", "eq", "gt", "ge", "ne"):
        if want not in bits:
            raise SystemExit("run_tt01: header defines no ONFI_CMP_%s"
                             % want.upper())

    proc = subprocess.Popen([exe], stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT)
    out = proc.communicate()[0].decode("ascii", "replace")
    status = proc.returncode

    got = {}
    selfrc = None
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("SELF "):
            selfrc = int(line.split("rc=", 1)[1])
            continue
        if not line.startswith("IVEC "):
            continue
        f = {}
        for part in line.split()[1:]:
            k, v = part.split("=", 1)
            f[k] = v
        got[(f["op"], int(f["idx"]))] = (int(f["rhi"], 16),
                                         int(f["rlo"], 16),
                                         int(f["rc"]))

    fails = []
    checked = 0
    for name, vectors in groups:
        for idx, (ahi, alo, bhi, blo, rhi, rlo) in enumerate(vectors):
            a = (ahi << 32) | alo
            b = (bhi << 32) | blo
            want = expected(name, a, b, blo, bits)
            checked += 1

            table = (rhi << 32) | rlo
            if table != want:
                fails.append("  TABLE %-5s [%2d] header=%016X oracle=%016X"
                             % (name, idx, table, want))

            key = (name, idx)
            if key not in got:
                fails.append("  MISSING %-5s [%2d] not printed by the binary"
                             % (name, idx))
                continue
            ghi, glo, grc = got[key]
            if grc != 0:
                fails.append("  RC    %-5s [%2d] onfirun returned %d"
                             % (name, idx, grc))
            cval = (ghi << 32) | glo
            if cval != want:
                fails.append("  C     %-5s [%2d] a=%016X b=%016X "
                             "C=%016X oracle=%016X"
                             % (name, idx, a, b, cval, want))

    print("run_tt01: %d vectors in %d groups, recomputed in Python"
          % (checked, len(groups)))
    for name, vectors in groups:
        print("run_tt01:   %-5s %3d" % (name, len(vectors)))

    if selfrc is None:
        fails.append("  SELF  the binary printed no SELF line")
    elif selfrc != 0:
        fails.append("  SELF  onfitst returned %d (group %s vector %d)"
                     % (selfrc, groups[selfrc // 1000][0]
                        if selfrc // 1000 < len(groups) else "?",
                        (selfrc % 1000) - 1))
    if status != 0:
        fails.append("  EXIT  tstint exited %d" % status)

    if fails:
        print("run_tt01: FAILED")
        for line in fails:
            print(line)
        return 1

    print("run_tt01: ok   table, compiler and oracle agree on all %d vectors"
          % checked)
    print("run_tt01: ok   onfitst returned 0; no cross-check failure")
    return 0


if __name__ == "__main__":
    sys.exit(main())
