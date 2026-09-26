# -*- coding: utf-8 -*-
"""Run one program, print the last line of its output, keep its exit status.

WHY THIS EXISTS (P-41 E2, D-546)

Four Makefile recipes ran a test program as `prog | tail -1`, to keep a
long vector dump down to its verdict line.  In a pipeline the recipe's
status is the LAST command's, so it was always tail's 0: a test program
that found a wrong answer and exited nonzero still let make carry on.  Two
of the four, `c2c` and `sfs`, are in `make test` (P-44 S1).

This keeps the one-line output and returns the program's own status.  It
is Python rather than a shell idiom such as `set -o pipefail` because
`mingw32-make` runs recipes under whatever shell it finds on PATH (Git's
`sh.exe` on the owner's host, `cmd.exe` where Git's tools are absent), and
`$(PYTHON)` is the one interpreter every platform's recipes already call.

Contract: `python tools/lastln.py PROGRAM [ARG...]`.  Runs PROGRAM with its
standard output captured and its standard error passed through.  Status 0:
prints the last line of the output, as `tail -1` did, or nothing if there
was none.  Any other status: prints the last 20 lines, so the failure can
be read, names the status on standard error, and exits with that status
(1 if it does not fit an exit code).  Nothing else is written.
"""
import os
import subprocess
import sys

TAIL_ON_FAILURE = 20


def resolve(prog):
    """An existing program path made absolute; anything else unchanged.

    The Makefile names its test programs `build/tstxxx.exe`, relative and
    with a forward slash.  `sh` runs that spelling; Windows process
    creation, which subprocess uses, did not find it on the first unmasked
    run (2026-09-26).  An absolute path is found on every platform, and a
    bare name such as `gcc` is still left to PATH.
    """
    return os.path.abspath(prog) if os.path.isfile(prog) else prog


def main(argv):
    if len(argv) < 2:
        sys.stderr.write("usage: lastln.py PROGRAM [ARG...]\n")
        return 2
    try:
        p = subprocess.run([resolve(argv[1])] + argv[2:],
                           stdout=subprocess.PIPE)
    except OSError as exc:
        sys.stderr.write("lastln: cannot run %s: %s\n" % (argv[1], exc))
        return 2
    lines = p.stdout.decode("utf-8", "replace").splitlines()
    keep = lines[-1:] if p.returncode == 0 else lines[-TAIL_ON_FAILURE:]
    for line in keep:
        sys.stdout.write(line + "\n")
    sys.stdout.flush()
    if p.returncode != 0:
        sys.stderr.write("lastln: %s exited %d\n" % (argv[1], p.returncode))
        return p.returncode if 0 < p.returncode < 256 else 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
