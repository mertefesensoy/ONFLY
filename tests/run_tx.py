# -*- coding: utf-8 -*-
"""TX-01 and TX-02: the same evidence, recorded per platform and compared.

Phase D asks two cross-platform questions and this answers both from one
recording, because they must be answered about the SAME run:

  TX-02  ACC-5, IR-COM-05.  Every golden request produces the same
         fingerprint in every row of the Section 8.3 determinism matrix.
         Recorded as the GOLD and GOUT lines of tests/tstgld.c.

  TX-01  FR-LNX-01.  The Linux build writes the same response records as
         the MVS build.  Recorded as the ONFRSP files tests/run_req.py's
         loop produces.  D-219: until an MVS engine exists, the comparand
         is x86, and TX-01 is reported PARTIAL rather than PASS.

Why one tool and not two
------------------------
A fingerprint that matched while the record around it differed would mean
the fingerprint was not covering what IR-COM-05 says it covers.  Recording
both from the same binaries, in one pass, is what makes that detectable.

What is deliberately NOT compared
---------------------------------
PLATFORM.txt.  It holds ONF_PLATID, the compiler identifier and the engine
version, which are SUPPOSED to differ between rows -- that is how a reader
knows two records came from different machines.  Comparing it would fail
every time; omitting it from the comparison and printing it in the report
is what makes the comparison meaningful.

Run:  python tests/run_tx.py --record  <outdir> <builddir>
      python tests/run_tx.py --compare <dir-a> <dir-b>
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for sub in ("generated", "tools", "tests"):
    sys.path.insert(0, os.path.join(ROOT, sub))

import mkreq                                       # noqa: E402
import run_gld                                     # noqa: E402

#: The three float backends, by the suffix their binaries carry.  D-220 puts
#: SOFT2C here as well as the two rows Section 8.3 names for s390x: it is the
#: library MVS uses and had never run on a big-endian host.
BACKENDS = ("soft", "nat", "2c")


def exe(builddir, stem, backend):
    """A built binary's path, tolerating the .exe suffix on both platforms."""
    for name in ("%s_%s.exe" % (stem, backend), "%s_%s" % (stem, backend)):
        path = os.path.join(builddir, name)
        if os.path.exists(path):
            return path
    return None


def gold_lines(binary, netpath, tag):
    """The GOLD and GOUT lines only.

    The leading '#' line carries backend= and platform=, which differ between
    rows by design, so it is dropped here rather than filtered at comparison
    time -- a recorded artifact should contain what is being claimed about
    it and nothing that would have to be explained away.
    """
    proc = subprocess.Popen([os.path.abspath(binary), netpath, str(tag)],
                            stdout=subprocess.PIPE)
    out, _ = proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError("%s exited %d" % (binary, proc.returncode))
    keep = []
    for line in out.decode("ascii", "replace").splitlines():
        if line.startswith("GOLD") or line.startswith("GOUT"):
            keep.append(line)
    return "\n".join(keep) + "\n"


def platform_note(binary, netpath):
    """ONF002I manifest fields that identify the row (NFR-OBS-01)."""
    proc = subprocess.Popen(
        [os.path.abspath(binary), "VERIFY", netpath],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out, _ = proc.communicate()
    keep = []
    for line in out.decode("ascii", "replace").splitlines():
        if line.startswith("ONF002I"):
            keep.append(line)
    return "\n".join(keep) + "\n"


def record(outdir, builddir):
    if not os.path.isdir(outdir):
        os.makedirs(outdir)
    made = []

    first_eng = None
    for tag, (label, netpath) in sorted(run_gld.NETWORKS.items()):
        if not os.path.exists(netpath):
            sys.stderr.write("network not found: %s\n" % netpath)
            return 2

        cards = mkreq.golden_cards(label)
        reqpath = os.path.join(outdir, "req-%s.bin" % label)
        with open(reqpath, "wb") as f:
            for r in mkreq.cards_to_records(cards):
                f.write(r)
        made.append(reqpath)

        for backend in BACKENDS:
            gld = exe(builddir, "tstgld", backend)
            eng = exe(builddir, "onflyeng", backend)
            if gld is None or eng is None:
                sys.stderr.write("missing %s binaries in %s\n"
                                 % (backend, builddir))
                return 2
            if first_eng is None:
                first_eng = (eng, netpath)

            name = os.path.join(outdir, "gold-%s-%s.txt" % (label, backend))
            with open(name, "w") as f:
                f.write(gold_lines(gld, netpath, tag))
            made.append(name)

            rsp = os.path.join(outdir, "rsp-%s-%s.bin" % (label, backend))
            proc = subprocess.Popen(
                [os.path.abspath(eng), "", netpath, reqpath, rsp],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            proc.communicate()
            if not os.path.exists(rsp):
                sys.stderr.write("no ONFRSP from %s on %s\n"
                                 % (eng, label))
                return 2
            made.append(rsp)

    with open(os.path.join(outdir, "PLATFORM.txt"), "w") as f:
        f.write(platform_note(first_eng[0], first_eng[1]))

    for name in sorted(made):
        print("run_tx: recorded %s (%d bytes)"
              % (os.path.basename(name), os.path.getsize(name)))
    print("run_tx: %d artifacts in %s" % (len(made), outdir))
    return 0


def compare(a, b):
    names_a = set(os.listdir(a)) - set(["PLATFORM.txt"])
    names_b = set(os.listdir(b)) - set(["PLATFORM.txt"])
    same = failed = 0
    rows = []

    for name in sorted(names_a - names_b):
        failed += 1
        rows.append("  FAIL %-28s present in %s only" % (name, a))
    for name in sorted(names_b - names_a):
        failed += 1
        rows.append("  FAIL %-28s present in %s only" % (name, b))

    for name in sorted(names_a & names_b):
        with open(os.path.join(a, name), "rb") as f:
            da = f.read()
        with open(os.path.join(b, name), "rb") as f:
            db = f.read()
        if da == db:
            same += 1
            rows.append("  ok   %-28s identical, %d bytes" % (name, len(da)))
        else:
            failed += 1
            rows.append("  FAIL %-28s DIFFERS (%d vs %d bytes)"
                        % (name, len(da), len(db)))
            if name.endswith(".txt"):
                la = da.decode("ascii", "replace").splitlines()
                lb = db.decode("ascii", "replace").splitlines()
                for i in range(min(len(la), len(lb))):
                    if la[i] != lb[i]:
                        rows.append("       line %d" % (i + 1))
                        rows.append("         %s" % la[i])
                        rows.append("         %s" % lb[i])
                        break
            else:
                for i in range(min(len(da), len(db))):
                    if da[i:i + 1] != db[i:i + 1]:
                        rows.append("       first difference at byte %d "
                                    "(record %d, offset %d)"
                                    % (i, i // 412, i % 412))
                        break

    for side in (a, b):
        note = os.path.join(side, "PLATFORM.txt")
        if os.path.exists(note):
            print("run_tx: %s" % side)
            with open(note) as f:
                for line in f.read().splitlines():
                    print("        %s" % line)

    for r in rows:
        print(r)
    print("run_tx: %d identical, %d differing" % (same, failed))
    return 1 if failed else 0


def main(argv):
    if len(argv) == 3 and argv[0] == "--record":
        return record(argv[1], argv[2])
    if len(argv) == 3 and argv[0] == "--compare":
        return compare(argv[1], argv[2])
    sys.stderr.write(__doc__.rsplit("Run:", 1)[-1])
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
