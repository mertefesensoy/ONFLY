# -*- coding: utf-8 -*-
"""Run `make test`'s targets one sub-make at a time, and count what ran.

WHY THIS EXISTS (P-41 E1, D-549)

`make test` used to end with a fixed `@echo` saying that every listed check
"passed", whatever had been skipped on the way (P-44 S3).  A replicator
missing pandas got that sentence over a run that never touched pandas.  The
closing line is now counted, not asserted:

    ONFLY test: <p> PASS, <s> SKIP, <q> PENDING, <e> EXEMPT (...)

PASS counts TARGETS, measured: each target named on the command line is
made by its own sub-make, in order, and it is a PASS when that sub-make
exits 0 having printed no `ONFRES SKIP` line.  SKIP, PENDING and EXEMPT
count CHECKS: the marker lines `tools/onfres.py` prints, found anywhere in
a line of the sub-make's output.

A target that fails stops the run, as make itself would, and its status is
the runner's.  A target already made is passed to every later sub-make as
`-o <target>`, so that a phony prerequisite (`shim` needs `fp`, `req` needs
`eng`) is not run a second time and its markers are not counted twice.

Contract: `python tools/testrun.py MAKE TARGET...`.  Output: every byte the
sub-makes write, unchanged, then a per-target table, the checks that did
not run, and the closing line.  Exit status: 0 when every target's sub-make
exits 0, otherwise the first failing sub-make's status.  Variables given on
the outer make's command line reach the sub-makes through MAKEFLAGS, which
make exports to its recipes.
"""
import re
import subprocess
import sys

MARK = re.compile(r"\bONFRES (SKIP|EXEMPT|PENDING) (\S+): ")


def scan(line):
    """(kind, check) for a marker line, or None."""
    m = MARK.search(line)
    return (m.group(1), m.group(2)) if m else None


def closing(npass, nskip, npend, nexempt):
    """The closing line, the one 11.8 reads."""
    return ("ONFLY test: %d PASS, %d SKIP, %d PENDING, %d EXEMPT "
            "(PASS counts targets; SKIP, PENDING and EXEMPT count checks; "
            "D-548, D-549)" % (npass, nskip, npend, nexempt))


def make_one(make, target, done, sink):
    """Make one target; relay its output; return (status, markers)."""
    cmd = [make, "--no-print-directory"]
    for t in done:
        cmd += ["-o", t]
    cmd.append(target)
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT)
    marks = []
    for raw in iter(p.stdout.readline, b""):
        sink.write(raw)
        sink.flush()
        hit = scan(raw.decode("utf-8", "replace"))
        if hit:
            marks.append(hit)
    p.stdout.close()
    return p.wait(), marks


def report(rows, marks, say):
    say("ONFLY test: per target")
    for target, verdict, counts in rows:
        extra = ", ".join("%d %s" % (n, k) for k, n in counts if n)
        say("  %-6s %-10s %s" % (verdict, target, extra))
    if marks:
        say("ONFLY test: checks that did not run")
        for kind, check in marks:
            say("  %-7s %s" % (kind, check))


def main(argv):
    if len(argv) < 3:
        sys.stderr.write("usage: testrun.py MAKE TARGET...\n")
        return 2
    make, targets = argv[1], argv[2:]
    sink = getattr(sys.stdout, "buffer", sys.stdout)

    def say(text):
        sink.write((text + "\n").encode("utf-8"))
        sink.flush()

    done, rows, allmarks = [], [], []
    npass = 0
    for target in targets:
        status, marks = make_one(make, target, done, sink)
        allmarks += marks
        counts = [(k, sum(1 for m in marks if m[0] == k))
                  for k in ("SKIP", "PENDING", "EXEMPT")]
        if status != 0:
            rows.append((target, "FAIL", counts))
            report(rows, allmarks, say)
            say("ONFLY test: FAILED %s (exit %d); later targets not run"
                % (target, status))
            return status
        skipped = dict(counts)["SKIP"] > 0
        rows.append((target, "SKIP" if skipped else "PASS", counts))
        if not skipped:
            npass += 1
        done.append(target)

    report(rows, allmarks, say)
    total = dict((k, sum(1 for m in allmarks if m[0] == k))
                 for k in ("SKIP", "PENDING", "EXEMPT"))
    say(closing(npass, total["SKIP"], total["PENDING"], total["EXEMPT"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
