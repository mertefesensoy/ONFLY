# -*- coding: utf-8 -*-
"""Judge tstsyn: the whole engine path over an embedded network.

Covers, on whatever platform tstsyn ran on:

  FR-LOD-02  the integrity checks, in order, each corrupted field reported
             by the check that caught it (TE-01..TE-06)
  FR-LOD-04  the memory limit, computed from header counts before anything
             is allocated (TE-08)
  FR-LOD-05  the big-endian payload load
  FR-SIM-01  the kernel, against the Python oracle (O-1)
  IR-COM-05  the response fingerprint, recomputed independently here

Nothing is shipped to the C side as an expected value.  The network is the
one tests/run_dec.py builds for its own TE-01..TE-08 cases, and the oracle
runs on that same network, so the two sides share inputs and nothing else.

Run:  python tests/run_syn.py <tstsyn executable>
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for sub in ("tests", "tools", "layout", "generated", "oracle"):
    sys.path.insert(0, os.path.join(ROOT, sub))

import gensyn                                     # noqa: E402
import run_dec                                    # noqa: E402
from onfly_oracle import kernel as okernel        # noqa: E402
from onfly_oracle.fingerprint import fingerprint  # noqa: E402

# onfdec.h's result codes.  Restated here rather than imported, so that a
# change to the header without a change to the requirement is caught.
ONFD_OK, ONFD_MAGIC, ONFD_SENT, ONFD_VER = 0, 101, 102, 103
ONFD_HCRC, ONFD_MEM, ONFD_PLEN, ONFD_PCRC = 104, 105, 106, 107

#: Which check must catch each corrupted field.  FR-LOD-02 fixes the ORDER,
#: so these are not interchangeable: a build that reported ONFD_HCRC for a
#: broken magic would still reject the file, and would still be wrong --
#: it would send an operator to rebuild the network when the real advice is
#: to re-send it in binary (NFR-REL-01, R-07).
EXPECT_BAD = {
    "magic": ONFD_MAGIC,        # TE-01, resealed
    "sentinel": ONFD_SENT,      # TE-02, resealed
    "version": ONFD_VER,        # TE-03, resealed
    "hdrcrc": ONFD_HCRC,        # TE-04, deliberately NOT resealed
    "paylen": ONFD_PLEN,        # TE-06, resealed
    "paycrc": ONFD_PCRC,        # TE-05, payload damaged, header intact
    "limit": ONFD_MEM,          # TE-08, one byte under the requirement
    "limitok": ONFD_OK,         # TE-08, exactly the requirement
    "fbpad": ONFD_OK,           # TE-07, FB zero padding tolerated
}


class Result(object):
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.backend = "?"
        self.platform = "?"
        self.lines = []

    def check(self, label, got, want):
        if got == want:
            self.passed += 1
        else:
            self.failed += 1
            self.lines.append("  FAIL %-30s C=%s oracle=%s"
                              % (label, got, want))


def parse(text):
    table = {}
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        # The banner is "# tstsyn backend=... platform=...": the marker is a
        # token of its own, so the kind is the token after it.
        if parts[0] == "#":
            parts = parts[1:]
            if not parts:
                continue
        kind = parts[0].lstrip("#")
        f = {}
        for p in parts[1:]:
            if "=" in p:
                k, v = p.split("=", 1)
                f[k] = v
        table.setdefault(kind, []).append(f)
    return table


def compare(text):
    """Judge tstsyn output against the oracle.  Returns a Result.

    Split out from main() so tools/mvssyn.py can hand it lines harvested
    from an MVS job listing and get the identical judgement.
    """
    r = Result()
    table = parse(text)

    for f in table.get("tstsyn", []):
        r.backend = f.get("backend", "?")
        r.platform = f.get("platform", "?")

    # --- the network the C side was given, rebuilt here ------------------
    data = run_dec.sample_network()
    a = run_dec._NET_ARGS
    net = run_dec.build_oracle_network()
    paycrc = int.from_bytes(data[156:160], "big")
    maxms = int.from_bytes(data[48:52], "big")

    # --- FR-LOD-02 on the good image -------------------------------------
    dec = table.get("DEC", [{}])[0]
    r.check("FR-LOD-02 accepts the image", int(dec.get("rc", -1)), ONFD_OK)
    r.check("header n", int(dec.get("n", -1)), a["n"])
    r.check("header e", int(dec.get("e", -1)), len(a["target"]))
    r.check("header ns", int(dec.get("ns", -1)), len(a["stim"]))
    r.check("header nr", int(dec.get("nr", -1)), len(a["readout"]))
    r.check("header dtus", int(dec.get("dtus", -1)), a["dt_us"])

    hdr = table.get("HDR", [{}])[0]
    r.check("IR-NET-07 payload CRC", hdr.get("paycrc", "").upper(),
            "%08X" % paycrc)
    r.check("header maximum duration", int(hdr.get("maxms", -1)), maxms)

    # --- TE-01..TE-06 and TE-08 ------------------------------------------
    seen = {}
    for f in table.get("BAD", []):
        seen[f["name"]] = int(f["rc"])
    for name, want in sorted(EXPECT_BAD.items()):
        r.check("FR-LOD-02 %s" % name, seen.get(name), want)

    # --- FR-SIM-01 and IR-COM-05 -----------------------------------------
    outs = {}
    for f in table.get("SOUT", []):
        outs.setdefault(int(f["q"]), {})[int(f["i"])] = (
            int(f["id"]), int(f["lat"]), int(f["spk"]))

    for q, (label, stimid, rate, ms, seed, rc) in enumerate(gensyn.REQUESTS):
        rows = [f for f in table.get("SYN", []) if int(f["q"]) == q]
        if not rows:
            r.check("%s produced a result" % label, None, "a SYN line")
            continue
        f = rows[0]
        steps = ms * 1000 // a["dt_us"]
        spikes, first = okernel.run(net, seed, rate, steps)

        got_out = outs.get(q, {})
        want_out = []
        for i, nix in enumerate(a["readout"]):
            want_out.append((nix, first[nix], spikes[nix]))
            r.check("%s readout %d" % (label, i), got_out.get(i),
                    (nix, first[nix], spikes[nix]))

        r.check("%s steps" % label, int(f["steps"]), steps)
        r.check("%s outcount" % label, int(f["out"]), len(a["readout"]))
        want_fp = fingerprint(paycrc, stimid, seed, rate, ms, rc,
                              want_out, steps)
        r.check("IR-COM-05 %s fingerprint" % label, f["fp"].upper(),
                "%08X" % want_fp)

        # ACC-2 in miniature: rate 0 has no other noise source, so silence
        # is exact rather than statistical.
        if rate == 0:
            r.check("ACC-2 %s rate 0 is silent" % label,
                    sum(spikes[nix] for nix in range(net.n)), 0)

    return r


def main():
    if len(sys.argv) < 2:
        sys.stderr.write("usage: run_syn.py <tstsyn executable>\n")
        return 2
    exe = os.path.abspath(sys.argv[1])
    if not os.path.exists(exe):
        sys.stderr.write("not found: %s\n" % exe)
        return 2
    proc = subprocess.Popen([exe], stdout=subprocess.PIPE)
    out, _ = proc.communicate()
    if proc.returncode != 0:
        sys.stderr.write("tstsyn exited %d\n" % proc.returncode)
        return 2

    r = compare(out.decode("ascii", "replace"))
    print("run_syn [%s backend, %s]: %d passed, %d failed"
          % (r.backend, r.platform, r.passed, r.failed))
    for line in r.lines:
        print(line)
    return 1 if r.failed else 0


if __name__ == "__main__":
    sys.exit(main())
