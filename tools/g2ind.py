# -*- coding: utf-8 -*-
"""IR-TRN-02 for IND$FILE: ten transfers of each file (D-149).

VL-55 proved IND$FILE binary-transparent on one transfer of one file.
IR-TRN-02 asks for at least ten per method using the test file **and**
a real network file, and D-149 chose to meet that as written.

ONE SESSION, TEN TRANSFERS
--------------------------
VL-55 measured the session lifecycle as the fragile part: a dropped
3270 connection does not log TSO off, so the next logon is refused
`IKJ56425I ... IN USE`; `LOGOFF` is not accepted inside ISPF, which
TK5's ISPLOGON proc lands in; and the LU needs time to settle after a
clean logoff, with back-to-back attempts failing in two different
ways.

Ten logons would therefore be ten chances to hit that.  One logon
carrying ten transfers has none, and is the natural shape for a file
transfer client anyway.

EVERY TRANSFER IS VERIFIED SEPARATELY
-------------------------------------
Each pass is checked on the guest by the same tests/tstxfr.c that
judged tape (VL-51) and the card reader (VL-53), or by ONFLYENG's
verify-only mode for the network.  Transferring ten times and checking
once would establish the repeatability of neither the transport nor
the check.

usage:
    python tools/g2ind.py [--repeat N] [--network] [--test]
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import mvsbld  # noqa: E402
import mvsub  # noqa: E402
import mvsxfr  # noqa: E402
import mvseng  # noqa: E402
import tso3270  # noqa: E402

# Staged under the lab's ASCII path for the same reason every other
# image is (VL-47): the repository lives under a non-ASCII path.
STAGE = os.path.join(mvsub.tk5_dir(), "tape")

TESTSRC = os.path.join(ROOT, "data", "transport", "tst256-cards.bin")
NETSRC = os.path.join(ROOT, "data", "transport", "onfnet-cards.bin")

TEST_DSN = "ONFTST"
NET_DSN = "ONFNETI"


def staged(src, name):
    dst = os.path.join(STAGE, name)
    with open(src, "rb") as f:
        data = f.read()
    with open(dst, "wb") as out:
        out.write(data)
    return dst.replace("\\", "/")


def verify_test(dsn):
    """Check a transferred test file with tests/tstxfr.c."""
    d = mvsxfr.deck(["//ONFTST   DD DSN=%s,DISP=SHR" % dsn])
    before = mvsub.submit(d)
    out = mvsub.collect(mvsxfr.JOB, before, timeout=900, poll=4)
    return out is not None and "XFR000I" in out


def verify_net(dsn):
    """Check a transferred network with ONFLYENG's verify-only mode."""
    d = mvseng.deck(mvsbld.OPT,
                    ["//ONFNET   DD DSN=%s,DISP=SHR" % dsn])
    before = mvsub.submit(d)
    out = mvsub.collect(mvseng.JOB, before, timeout=1800, poll=5)
    return out is not None and "ONF003I" in out


def run(session, local, dsn, verifier, label, repeat):
    user = tso3270.USER
    full = "%s.%s" % (user, dsn)
    results = []
    for n in range(repeat):
        t0 = time.time()
        action = ("Transfer(Direction=send,HostFile='%s',LocalFile=%s,"
                  "Host=tso,Mode=binary,Exist=replace,Recfm=fixed,"
                  "Lrecl=80,BlockSize=80,AllocationUnit=tracks,"
                  "PrimarySpace=60,SecondarySpace=20)"
                  % (full, local))
        status, lines = session.do(action, timeout=600)
        sent = status == "ok"
        note = ""
        for l in lines:
            if "Transfer complete" in l or "bytes transferred" in l:
                note = l.strip()[:60]
        ok = sent and verifier(full)
        took = time.time() - t0
        results.append((ok, took))
        sys.stdout.write("  %s %2d/%d: %s in %.1f s%s\n"
                         % (label, n + 1, repeat,
                            "OK" if ok else "FAILED", took,
                            "  (%s)" % note if note else ""))
        if not sent:
            sys.stdout.write("      transfer status: %s\n" % status)
    return results


def report(label, results):
    good = sum(1 for ok, _ in results if ok)
    times = [t for _, t in results]
    print()
    print("=== IR-TRN-02 IND$FILE %s: %d of %d transfers OK ==="
          % (label, good, len(results)))
    print("    elapsed per transfer: min %.1f s, max %.1f s, "
          "mean %.1f s"
          % (min(times), max(times), sum(times) / len(times)))
    return good == len(results)


def main(argv):
    try:
        sys.stdout.reconfigure(errors="replace")
    except (AttributeError, ValueError):
        pass

    repeat = 10
    for i, a in enumerate(argv):
        if a == "--repeat" and i + 1 < len(argv):
            repeat = int(argv[i + 1])
    do_test = "--network" not in argv or "--test" in argv
    do_net = "--test" not in argv or "--network" in argv

    if not os.path.isdir(STAGE):
        os.makedirs(STAGE)

    session = tso3270.Session()
    allok = True
    try:
        if not tso3270._reach_ready(session, tso3270.USER,
                                    tso3270.PASSWORD):
            sys.stderr.write("g2ind: could not reach TSO READY\n")
            return 1
        print("g2ind: logged on; one session carries every transfer")

        if do_test:
            local = staged(TESTSRC, "ind-tst256.bin")
            res = run(session, local, TEST_DSN, verify_test,
                      "test file", repeat)
            allok = report("test file", res) and allok

        if do_net:
            local = staged(NETSRC, "ind-onfnet.bin")
            res = run(session, local, NET_DSN, verify_net,
                      "network", repeat)
            allok = report("network", res) and allok
    finally:
        session.close()
        print("g2ind: logged off")

    return 0 if allok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
