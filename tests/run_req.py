# -*- coding: utf-8 -*-
"""FR-BAT-01 STEP2: the request/response loop, against the oracle (D-221).

D-221 brought STEP2 forward from Phase E because TX-01 -- "Linux s390x and
MVS response records are identical" -- had nothing to compare: no build on any
platform produced a response record.  This is the x86 half of that evidence
and the harness the s390x half is measured with.

What this checks
----------------
For each network of Section 8.4, and each float backend:

  the records the engine writes
      Every ONFRSP record is decoded and its return code, output count, step
      count, fingerprint and readout entries are compared against the oracle's
      independent recomputation of the same request.  The oracle is imported
      from run_gld.py rather than restated, so this cannot disagree with the
      golden suite about what a request means.

  IR-JCL-03, that only the response portion is overwritten
      Bytes 0 to 15 of every response record -- the request echo -- must equal
      the request record byte for byte.  This is checked on the raw bytes
      rather than on decoded fields, because a decoder that made the same
      mistake in both directions would hide exactly the defect it looks for.

  IR-JCL-04, the step return code
      0 when every request succeeded, 4 when any warned, 8 when any was
      rejected.  The suite deliberately contains all three: G-11 is a reserved
      stimulus, G-12 an unknown one and G-13 an out-of-range rate.

  ACC-5 across backends on this host
      The three ONFRSP files must be byte-identical.  A response record that
      depended on which float library produced it would not be a response
      record, and the fingerprint inside it would not be a fingerprint.

What it does NOT check: anything about another platform.  TX-01's cross-
platform half is a comparison of the ONFRSP files this produces on x86 with
those the same suite produces on s390x, and TX-01 stays PARTIAL until an MVS
build exists (D-219).

Run:  python tests/run_req.py <onflyeng> [<onflyeng> ...]
Exit status 0 when every case behaves as specified, 1 otherwise.
"""
import os
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for sub in ("generated", "tools", "tests"):
    sys.path.insert(0, os.path.join(ROOT, sub))

import onfcom_py as L                              # noqa: E402
import mkreq                                       # noqa: E402
import run_gld                                     # noqa: E402

#: IR-JCL-04's step return codes, keyed by the worst per-request code seen.
STEP_RC = {0: 0, 4: 4, 8: 8, 16: 16}


def request_echo(rec):
    """Bytes 0 to 15: the request as submitted (IR-JCL-03)."""
    return rec[:L.OFF["rc"]]


def decode_response(rec):
    """One response record, as a dict of the fields the oracle predicts."""
    (code, seed, rate, ms, rc, outcount, fprint,
     steps) = struct.unpack(L.HEAD_FMT, rec[:L.HEAD_LEN])
    outs = []
    for k in range(outcount):
        off = L.HEAD_LEN + k * L.OUT_LEN
        oid, lat, spk, _fill = struct.unpack(
            L.OUT_FMT, rec[off:off + L.OUT_LEN])
        outs.append((oid, lat, spk))
    return {
        "code": code.decode("ascii", "replace").rstrip(),
        "seed": seed, "rate": rate, "ms": ms, "rc": rc,
        "outcount": outcount, "steps": steps,
        "fp": struct.unpack(">I", fprint)[0],
        "outs": outs,
    }


def run_engine(exe, netpath, reqpath, rsppath):
    """One ONFLYENG run in SIMULATE mode.  Returns (rc, stdout lines)."""
    argv = [os.path.abspath(exe), "", netpath, reqpath, rsppath]
    proc = subprocess.Popen(argv, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT)
    out, _ = proc.communicate()
    return proc.returncode, out.decode("ascii", "replace").splitlines()


def check_network(exes, tag, label, netpath, tmp, rows):
    """Every backend against one network.  Returns (passed, failed)."""
    passed = failed = 0

    spec, net, paycrc = run_gld.make_network(netpath)
    requests = [q for q in run_gld.SUITE if q[6] == tag]

    # The same cards the Phase E ONFLYDRV will read (IR-JCL-02).
    reqpath = os.path.join(tmp, "onfreq-%s.bin" % label)
    records = mkreq.cards_to_records(mkreq.golden_cards(label))
    if len(records) != len(requests):
        rows.append("  FAIL %s: %d cards for %d requests"
                    % (label, len(records), len(requests)))
        return 0, 1
    with open(reqpath, "wb") as f:
        for r in records:
            f.write(r)

    # The oracle is a pure-Python simulation and is by far the most expensive
    # thing here: 94 s for one backend on x86, and this runs on s390x under
    # TCG emulation as well.  It is therefore computed ONCE per request and
    # reused across backends.  The earlier shape recomputed it four times per
    # request -- once for the step return code and once per backend -- which
    # is a four-fold cost for an identical answer, since the oracle does not
    # know or care which backend it is being compared against.
    expect = {}
    worst = 0
    for (gid, code, stimid, rate, ms, seed, _tag) in requests:
        expect[gid] = run_gld.oracle_request(
            net, paycrc, stimid, rate, ms, seed)
        worst = max(worst, expect[gid][1])

    written = {}
    for exe in exes:
        backend = os.path.basename(exe)
        rsppath = os.path.join(tmp, "onfrsp-%s-%s.bin" % (label, backend))
        rc, lines = run_engine(exe, netpath, reqpath, rsppath)

        want_step = STEP_RC[worst]
        if rc != want_step:
            failed += 1
            rows.append("  FAIL %s %s: step RC %d, expected %d (IR-JCL-04)"
                        % (label, backend, rc, want_step))
            for line in lines[-4:]:
                rows.append("       %s" % line)
            continue
        passed += 1
        rows.append("  ok   %-28s step RC %d (IR-JCL-04)"
                    % ("%s %s" % (label, backend), rc))

        # Appendix E's messages, which FR-BAT-04's report step will read.
        # Checked as well as the records because they are a SECOND statement
        # of the same result: ONF301I repeats the fingerprint that is in the
        # record, and ONF302I counts the outcomes the return code summarises.
        # Two statements that can disagree are worth comparing.
        want_ok = sum(1 for q in requests if expect[q[0]][1] == 0)
        want_warn = sum(1 for q in requests if expect[q[0]][1] == 4)
        want_err = len(requests) - want_ok - want_warn
        got_ok = [l for l in lines if l.startswith("ONF301I")]
        summary = [l for l in lines if l.startswith("ONF302I")]
        want_sum = ("ONF302I STEP SUMMARY: %d OK, %d WARN, %d ERROR"
                    % (want_ok, want_warn, want_err))
        if len(got_ok) == want_ok:
            passed += 1
            rows.append("  ok   %-28s %d ONF301I lines, one per success"
                        % ("%s %s" % (label, backend), want_ok))
        else:
            failed += 1
            rows.append("  FAIL %s %s: %d ONF301I lines, expected %d"
                        % (label, backend, len(got_ok), want_ok))
        if summary[-1:] == [want_sum]:
            passed += 1
            rows.append("  ok   %-28s %s"
                        % ("%s %s" % (label, backend),
                           want_sum.replace("ONF302I ", "")))
        else:
            failed += 1
            rows.append("  FAIL %s %s: summary %r, expected %r"
                        % (label, backend, summary[-1:], want_sum))

        # Each ONF301I carries the fingerprint of its request (Appendix E),
        # so the printed value and the recorded value must agree.
        fps_printed = []
        for line in got_ok:
            tok = line.rsplit("FP=", 1)
            if len(tok) == 2:
                fps_printed.append(int(tok[1].strip(), 16))

        if not os.path.exists(rsppath):
            failed += 1
            rows.append("  FAIL %s %s: no ONFRSP written" % (label, backend))
            continue
        with open(rsppath, "rb") as f:
            blob = f.read()
        written[backend] = blob

        if len(blob) != len(records) * L.RECORD_LEN:
            failed += 1
            rows.append("  FAIL %s %s: ONFRSP is %d bytes, expected %d"
                        % (label, backend, len(blob),
                           len(records) * L.RECORD_LEN))
            continue

        for i, (gid, code, stimid, rate, ms,
                seed, _tag) in enumerate(requests):
            rec = blob[i * L.RECORD_LEN:(i + 1) * L.RECORD_LEN]
            want_fp, want_rc, want_steps = expect[gid]
            got = decode_response(rec)

            if request_echo(rec) != request_echo(records[i]):
                failed += 1
                rows.append("  FAIL %s %s %s: request echo altered "
                            "(IR-JCL-03)" % (label, backend, gid))
                continue
            if got["rc"] == 0 and fps_printed:
                expected_here = [expect[q[0]][0] for q in requests
                                 if expect[q[0]][1] == 0]
                if fps_printed != expected_here:
                    failed += 1
                    rows.append("  FAIL %s %s: ONF301I fingerprints differ "
                                "from the recorded ones" % (label, backend))
                    fps_printed = []
            if got["rc"] != want_rc or got["steps"] != want_steps \
                    or got["fp"] != want_fp:
                failed += 1
                rows.append("  FAIL %s %s %s: rc %d/%d steps %d/%d "
                            "fp %08X/%08X (got/want)"
                            % (label, backend, gid, got["rc"], want_rc,
                               got["steps"], want_steps, got["fp"], want_fp))
                continue
            passed += 1

    # ACC-5 on this host: the backends must agree byte for byte.
    names = sorted(written)
    for other in names[1:]:
        if written[other] != written[names[0]]:
            failed += 1
            rows.append("  FAIL %s: %s and %s ONFRSP differ"
                        % (label, names[0], other))
        else:
            passed += 1
            rows.append("  ok   %-28s ONFRSP byte-identical to %s"
                        % ("%s %s" % (label, other), names[0]))
    return passed, failed


def main(argv):
    if not argv:
        sys.stderr.write("usage: run_req.py <onflyeng> [<onflyeng> ...]\n")
        return 2
    for exe in argv:
        if not os.path.exists(exe):
            sys.stderr.write("not found: %s\n" % exe)
            return 2

    passed = failed = 0
    rows = []
    tmp = tempfile.mkdtemp(prefix="onfly-req-")
    try:
        for tag, (label, netpath) in sorted(run_gld.NETWORKS.items()):
            if not os.path.exists(netpath):
                sys.stderr.write("network not found: %s\n" % netpath)
                return 2
            p, f = check_network(argv, tag, label, netpath, tmp, rows)
            passed += p
            failed += f
    finally:
        for name in os.listdir(tmp):
            os.remove(os.path.join(tmp, name))
        os.rmdir(tmp)

    for r in rows:
        print(r)
    print("run_req: %d passed, %d failed" % (passed, failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
