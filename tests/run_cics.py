# -*- coding: utf-8 -*-
"""Phase G, first component: the EXEC CICS transaction, verified (P-22).

Two checks, and they prove different things.  Keeping them apart is D-400's
whole point, so read the failure before concluding anything.

  V4  BYTE IDENTITY, at the adapter.
      tests/tstcics.c drives the Section 8.4 `srext` requests through
      onfcini/onfcrun -- the engine side of the LINK target -- and writes an
      ONFRSP.  The batch engine writes its own ONFRSP from the SAME ONFREQ.
      The two files must be byte-identical.  Nothing is interpreted: if one
      byte of one response record differs, this fails.

  V3  THE TRANSACTION ITSELF, under the CICS runtime.
      cics/ONFCSUG.cbl is run under `rclrun -Qix=true`, which dispatches
      EXEC CICS LINK to the .NET module, which P/Invokes the same engine.
      Its reported fingerprint must equal the one in the batch response for
      the same request, and its reported readout fields must agree too.

WHY V4 IS NOT MEASURED THROUGH THE COBOL
---------------------------------------
Because it cannot be.  Measured on 2026-09-17 (D-400): QIX copies the
COMMAREA into the run unit and never back, so after the run the runner's own
CommArea still held the request -- rc 0, outcount 0, fingerprint all zero --
although ONFCSUG had demonstrably filled it and printed FP=BAF81D91.  That
is real CICS behaviour, not a Raincode defect: a top-level transaction has no
caller to return a COMMAREA to.  So the bytes are compared where they exist,
and the transaction is held to the fingerprint, which IR-COM-05 defines as a
CRC-32 over every field of the response.

SKIPPING
--------
This prints a skip line and exits 0 when Raincode or the .NET SDK is absent,
the same rule D-156 set for the GnuCOBOL proxy and D-394 restated here:
`make test` must stay runnable on a bare checkout.  A skip says which piece
was missing -- a skip that does not name what it skipped has stopped
protecting anything (the failure D-390 records).

usage:  python tests/run_cics.py <batch-engine-exe> <tstcics-exe> <rundir>
"""
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "generated"))

import mkreq                                        # noqa: E402
import onfcom_py as LAYOUT                          # noqa: E402
import onfres                                       # noqa: E402

NETWORK = os.path.join(ROOT, "data", "networks",
                       "onfnet-malecns-v1.0-srext.bin")

# The transaction is driven with one request, and it is G-16 deliberately:
# Section 8.4 calls it "a sampled rate: Appendix C step 0 selects that row
# exactly", so a wrongly selected compensation row would move the answer
# rather than hide inside it.
G16_CARD = "SUGR   40 1000     1"

RC_VARS = ("RCDIR", "RCBIN")


def machine_env(name):
    """Read a machine-level environment variable from the registry.

    The Raincode installer sets RCDIR and RCBIN machine-wide, and a shell
    started before the install does not have them.  tools/rcprobe.py reads
    them the same way and for the same reason: telling someone to reboot to
    run a test is a poor answer.
    """
    value = os.environ.get(name)
    if value:
        return value
    if os.name != "nt":
        return None
    try:
        import winreg
    except ImportError:
        return None
    path = r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path) as key:
            return winreg.QueryValueEx(key, name)[0]
    except OSError:
        return None


def rc_environment():
    env = dict(os.environ)
    for name in RC_VARS:
        value = machine_env(name)
        if value:
            env[name] = value
    return env


def rcbin(env):
    """The Raincode bin directory, or None."""
    bin_dir = env.get("RCBIN")
    if bin_dir and os.path.isdir(bin_dir):
        return bin_dir
    top = env.get("RCDIR")
    if top:
        cand = os.path.join(top, "bin")
        if os.path.isdir(cand):
            return cand
    return None


def run(argv, cwd=None, env=None):
    proc = subprocess.Popen(argv, cwd=cwd, env=env, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT)
    out = proc.communicate()[0].decode("latin-1", "replace")
    return proc.returncode, out


def decode(rec):
    """The response fields of one 412-byte record."""
    import struct
    head = struct.unpack(LAYOUT.HEAD_FMT, rec[:LAYOUT.HEAD_LEN])
    outs = []
    for i in range(head[5]):
        off = LAYOUT.HEAD_LEN + i * LAYOUT.OUT_LEN
        outs.append(struct.unpack(LAYOUT.OUT_FMT,
                                  rec[off:off + LAYOUT.OUT_LEN])[:3])
    return {
        "rate": head[2], "ms": head[3], "rc": head[4],
        "outcount": head[5],
        "fp": head[6].hex().upper(),
        "steps": head[7],
        "outs": outs,
    }


def main(argv):
    if len(argv) != 4:
        print(__doc__.strip().splitlines()[-1])
        return 2
    batch_exe, cics_exe, rundir = argv[1], argv[2], argv[3]

    rows = []
    bad = 0

    if not os.path.exists(NETWORK):
        onfres.skip("cics/network", "no %s; run `make fixtures`" % NETWORK)
        return 0

    if not os.path.isdir(rundir):
        os.makedirs(rundir)

    # --- the request dataset, the same cards ONFLYDRV reads (IR-JCL-02) ---
    records = mkreq.cards_to_records(mkreq.golden_cards("srext"))
    reqpath = os.path.join(rundir, "ONFREQ.bin")
    with open(reqpath, "wb") as f:
        for rec in records:
            f.write(rec)

    # --- V4: the adapter against the batch engine, byte for byte ---------
    batch_rsp = os.path.join(rundir, "ONFRSP.batch")
    cics_rsp = os.path.join(rundir, "ONFRSP.cics")

    code, out = run([batch_exe, "", NETWORK, reqpath, batch_rsp])
    if code != 0:
        rows.append("  FAIL batch engine exit %d\n%s" % (code, out))
        bad += 1
    code, out = run([cics_exe, NETWORK, reqpath, cics_rsp])
    if code != 0:
        rows.append("  FAIL tstcics exit %d\n%s" % (code, out))
        bad += 1

    if bad == 0:
        with open(batch_rsp, "rb") as f:
            a = f.read()
        with open(cics_rsp, "rb") as f:
            b = f.read()
        if a == b:
            rows.append("  V4 PASS  %d bytes, %d records, byte-identical"
                        % (len(a), len(a) // LAYOUT.RECORD_LEN))
        else:
            bad += 1
            rows.append("  V4 FAIL  batch %d bytes, cics %d bytes" %
                        (len(a), len(b)))
            for i in range(min(len(a), len(b))):
                if a[i] != b[i]:
                    rows.append("       first difference at byte %d: "
                                "batch %02X, cics %02X"
                                % (i, a[i], b[i]))
                    break

    if bad:
        print("run_cics: the adapter check failed; the transaction is not run")
        for row in rows:
            print(row)
        return 1

    # --- V3: the transaction, under the CICS runtime ----------------------
    env = rc_environment()
    bin_dir = rcbin(env)
    if bin_dir is None:
        text, fatal = onfres.skipline(
            "cics/raincode", "V3 Raincode not found (neither RCBIN nor RCDIR)")
        rows.append("  " + text)
        bad += 1 if fatal else 0
        print("run_cics: %d checks" % len(rows))
        for row in rows:
            print(row)
        return 1 if bad else 0

    # The one request, and the batch answer it must match.
    g16 = mkreq.cards_to_records(G16_CARD)
    g16req = os.path.join(rundir, "G16REQ.bin")
    with open(g16req, "wb") as f:
        f.write(g16[0])
    g16batch = os.path.join(rundir, "G16RSP.batch")
    code, out = run([batch_exe, "", NETWORK, g16req, g16batch])
    if code != 0:
        print("run_cics: FAIL batch engine on G-16, exit %d\n%s" % (code, out))
        return 1
    with open(g16batch, "rb") as f:
        want = decode(f.read())

    # rclrun is run where the modules are, not where the output goes: the
    # compiled COBOL, the .NET module and the native engine DLL all sit
    # beside tstcics.exe, and Windows resolves the DLL from the working
    # directory.  Run it from the output directory instead and the module
    # dictionary reports "Failed to load module onfcics" and then "Entry
    # name not found: ONFCSUG", which reads like a compile failure and is
    # not one.
    moddir = os.path.dirname(os.path.abspath(cics_exe))
    env["ONFNET"] = NETWORK
    code, out = run([os.path.join(bin_dir, "rclrun.exe"),
                     "-Qix=true", "-AutoMapAssembly=onfcics",
                     "-QixFile=" + os.path.abspath(g16req),
                     "ONFCSUG"], cwd=moddir, env=env)

    hdr = re.search(r"ONFCSUG SUGR\s+RATE=\s*(-?\d+) MS=\s*(\d+) "
                    r"SEED=\s*(\d+) RC=\s*(\d+) FP=([0-9A-F]{8})", out)
    if hdr is None:
        bad += 1
        rows.append("  V3 FAIL  no ONFCSUG header line in the run output")
        rows.append("       exit %d\n%s" % (code, out[:2000]))
    else:
        got_rate, got_ms, got_rc, got_fp = (int(hdr.group(1)),
                                            int(hdr.group(2)),
                                            int(hdr.group(4)),
                                            hdr.group(5))
        if got_fp != want["fp"]:
            bad += 1
            rows.append("  V3 FAIL  fingerprint %s, batch says %s"
                        % (got_fp, want["fp"]))
        elif got_rc != want["rc"] or got_rate != want["rate"] \
                or got_ms != want["ms"]:
            bad += 1
            rows.append("  V3 FAIL  echo/rc differ: transaction "
                        "rate %d ms %d rc %d; batch rate %d ms %d rc %d"
                        % (got_rate, got_ms, got_rc,
                           want["rate"], want["ms"], want["rc"]))
        else:
            rows.append("  V3 PASS  transaction FP=%s RC=%d, equal to the "
                        "batch response" % (got_fp, got_rc))

        outs = re.findall(r"ONFCOUT\s+ID=\s*(-?\d+) SPK=\s*(-?\d+) "
                          r"LAT=\s*(-?\d+)", out)
        got_outs = [(int(a), int(c), int(b)) for a, b, c in outs]
        if got_outs != [tuple(t) for t in want["outs"]]:
            bad += 1
            rows.append("  V3 FAIL  readouts %r, batch %r"
                        % (got_outs, want["outs"]))
        else:
            rows.append("  V3 PASS  %d readout entries agree with the batch "
                        "response" % len(got_outs))

    print("run_cics: %d checks, %d failed" % (len(rows), bad))
    for row in rows:
        print(row)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
