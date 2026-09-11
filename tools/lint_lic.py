# -*- coding: utf-8 -*-
"""Keep INTERCOMM-derived material out of the MIT tree (D-132).

WHY THIS EXISTS
---------------
VL-38 recorded the collision exactly.  INTERCOMM's licence, Tetragon
LLC 2005/2022, is three-clause BSD in shape with one clause that is
not: use or redistribution in any form, *including derivative works*,
must be non-commercial only.  The repository is MIT (D-62), which
grants every recipient commercial rights.  Both cannot govern one
file, so ONFLY cannot promise onward commercial rights over anything
derivative of INTERCOMM.

D-132 removes the question rather than answering it: no INTERCOMM-
derived material enters the repository at all.  That is cheap because
D-130 already put ONFLY's real transaction source in `EXEC CICS` --
the INTERCOMM side is demonstration scaffolding, not product.

A licensing rule that lives only in prose is a rule that gets broken
six months later by someone pasting a copybook in to save time, and
the breach is invisible in review because the file looks like ordinary
COBOL.  So the rule is mechanical.

WHAT IT CHECKS
--------------
Tracked files only -- `git ls-files`.  Untracked and ignored files are
exactly where this material is *supposed* to live (`local/`), so
flagging them would be backwards.

It looks for the INTERCOMM names a subsystem cannot be written without.
They come from the Release 11 DSECTS list read in VL-38: the message
header, the COBOL internal prefix area, the verb table area, the
system parameter area, and the service routines a subsystem calls.

WHAT IT CANNOT DO
-----------------
It recognises names, not derivation.  Someone determined to paste
INTERCOMM code in while renaming everything will get past it, and a
file that merely *discusses* INTERCOMM is not a derivative work.  So
prose is exempted deliberately: this file, the SRS, and the
implementation docs all name these macros in order to explain the rule.
The exemption is by path, and it is narrow on purpose -- widening it is
how this check would quietly stop working.

usage:  python tools/lint_lic.py [--verbose]
        exit 0 clean, 1 on a finding, 2 if git is unavailable
"""
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# INTERCOMM macros, copybooks and service routines.  A COBOL subsystem
# cannot avoid the message header; the rest travel with it.
INTERCOMM_NAMES = (
    "MSGHDR",    # Intercomm message header -- the unavoidable one
    "COBDSECT",  # COBOL DWS internal 256-byte prefix area
    "PVRBTBLE",  # BTVERB macro area (the verb table)
    "SPALIST",   # system parameter area
    "SPAEXT",    # SPA extension area
    "INTGLOBE",  # system execution global definitions
    "SCTLISTC",  # SYCTTBL macro area (subsystem control table)
    "SCNLIDS",   # subsystem controller work area
    "INTTCB",    # thread control block
    "MSGQWRK",   # message queuing work area
    "BTVERB",    # verb table macro
    "SYCTTBL",   # subsystem control table macro
    "PMISTOP",   # subsystem return service
    "MSGCOL",    # message collection service
    "FEOV",      # Intercomm file service
    "GETV",      # Intercomm storage service
)

# Files that name these in order to explain the rule.  Narrow by
# design: every entry here is a place where prose about INTERCOMM is
# the point, never a place where INTERCOMM code could hide.
EXEMPT = (
    "tools/lint_lic.py",
    "docs/ONFLY-SRS.md",
)
EXEMPT_DIRS = ("docs/implementations/",)

# Source-shaped files only.  A PDF of an INTERCOMM manual is not source
# and is not what this is looking for.
SOURCE_SUFFIXES = (".cbl", ".cpy", ".cob", ".asm", ".mac", ".jcl",
                   ".c", ".h", ".py", ".txt", ".inc")


def tracked_files():
    try:
        out = subprocess.run(["git", "ls-files"], cwd=ROOT,
                             stdout=subprocess.PIPE, timeout=60)
    except Exception as exc:
        sys.stderr.write("lint_lic: cannot run git: %s\n" % exc)
        return None
    if out.returncode != 0:
        sys.stderr.write("lint_lic: git ls-files failed\n")
        return None
    return out.stdout.decode("utf-8", "replace").split("\n")


def is_exempt(path):
    if path in EXEMPT:
        return True
    for d in EXEMPT_DIRS:
        if path.startswith(d):
            return True
    return False


def main(argv):
    verbose = "--verbose" in argv
    files = tracked_files()
    if files is None:
        return 2

    # Word boundaries, so ONFLY's own GETVAL or a comment containing
    # "forever" does not trip GETV.
    pattern = re.compile(r"\b(%s)\b" % "|".join(INTERCOMM_NAMES))

    findings = []
    scanned = 0
    for path in files:
        path = path.strip()
        if not path or is_exempt(path):
            continue
        if not path.lower().endswith(SOURCE_SUFFIXES):
            continue
        full = os.path.join(ROOT, path)
        if not os.path.isfile(full):
            continue
        scanned += 1
        try:
            with open(full, encoding="utf-8", errors="replace") as fh:
                for n, line in enumerate(fh, 1):
                    m = pattern.search(line)
                    if m:
                        findings.append((path, n, m.group(1),
                                         line.strip()[:70]))
        except OSError as exc:
            sys.stderr.write("lint_lic: cannot read %s: %s\n"
                             % (path, exc))

    if verbose:
        print("lint_lic: scanned %d tracked source files" % scanned)

    if not findings:
        print("lint_lic: ok -- no INTERCOMM-derived names in the tree "
              "(D-132)")
        return 0

    print("lint_lic: INTERCOMM-derived names found in tracked files.")
    print("  D-132: this material must live under local/ or on TK5,")
    print("  never in the repository. VL-38 records why: INTERCOMM is")
    print("  non-commercial-only including derivative works, and this")
    print("  repository is MIT. The two cannot both govern one file.")
    print()
    for path, n, name, text in findings:
        print("  %s:%d  %s" % (path, n, name))
        print("      %s" % text)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
