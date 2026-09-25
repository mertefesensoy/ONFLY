# -*- coding: utf-8 -*-
"""80-column lint for ONFLY-owned source (D-93).

Why this exists, measured rather than assumed
---------------------------------------------
TK5 defines its card reader as

    000C 3505 ${RDRPORT:=3505} sockdev ascii trunc eof

and `trunc` means what it says.  An 85-character card was submitted to the
running system on 2026-09-11 and arrived as exactly 80 characters: columns
81 to 85 were discarded, with no error, no warning and no message of any
kind.  The job completed normally.

That is the failure mode ONFLY exists to rule out.  A truncated vector line
happens to break the compile, which is loud and harmless; a truncated comment
is invisible; and a truncated statement can be neither.  There is no way to
tell from the MVS side which happened, because nothing is reported.

So every ONFLY-owned source that might be transferred to MVS is held to 80
columns, and this lint is what keeps it that way.  Without it a long line
reappears the next time anyone writes one, silently -- the same way the blind
golden fixture survived unnoticed until D-70.

What is exempt, and why
-----------------------
`third_party/` is not checked.  D-28 and D-35 commit that tree to being
byte-identical to the upstream release, so reflowing Berkeley SoftFloat is
not available even though its own sources are longer than 80 columns.  Moving
SoftFloat into MVS needs a transport that preserves long lines -- tape, or a
direct DASD load -- which is TT-02's problem and a separate decision.

A tab is counted as the columns it occupies to the next multiple of 8, since
that is what the card image will contain.

Run:  python tools/lint_col80.py <path> [<path> ...]
Exit status 0 when clean, 1 when any ONFLY-owned line exceeds the limit.
"""
import io
import os
import sys

LIMIT = 80
TABSTOP = 8
# Card-image source only.  ".bms" joins the list because a BMS mapset IS
# card image -- its continuation indicator sits in column 72 -- so a long
# line there is the same silent truncation this lint exists for.
#
# ".cs" and ".csproj" are deliberately NOT here, and the omission is stated
# rather than left to be noticed (D-398).  C# is not card image, no
# MVS tool ever reads it, and an 80-column rule on it would be
# ceremony.  Note that ".cs" does not match the ".c" entry: endswith(".c")
# is false for a name ending in "s".
#
# The CICS COBOL in cics/ is held to a STRICTER limit than this one -- 72
# columns, because cobrc truncates past 72 with no diagnostic at all
# (VL-37) -- and that check lives in tools/cicsbld.py --cols.  This lint
# still covers those files at 80, which is the weaker of the two and costs
# nothing.
SUFFIXES = (".c", ".h", ".cpy", ".jcl", ".cbl", ".cob", ".bms")


def width(line):
    """Columns the line occupies once tabs are expanded."""
    col = 0
    for ch in line:
        if ch == "\t":
            col += TABSTOP - (col % TABSTOP)
        else:
            col += 1
    return col


def files(paths):
    for path in paths:
        if os.path.isfile(path):
            yield path
            continue
        for root, dirs, names in os.walk(path):
            dirs[:] = sorted(d for d in dirs
                             if d not in ("third_party", "build",
                                          "__pycache__", ".git"))
            for name in sorted(names):
                if name.lower().endswith(SUFFIXES):
                    yield os.path.join(root, name)


def main(argv):
    if len(argv) < 2:
        sys.stderr.write("usage: lint_col80.py <path> [<path> ...]\n")
        return 2

    scanned = 0
    bad = []
    for path in files(argv[1:]):
        scanned += 1
        try:
            text = io.open(path, encoding="utf-8").read()
        except UnicodeDecodeError:
            text = io.open(path, encoding="latin-1").read()
        for n, line in enumerate(text.splitlines(), 1):
            w = width(line)
            if w > LIMIT:
                bad.append((path, n, w, line))

    for path, n, w, line in bad:
        rel = os.path.relpath(path)
        sys.stdout.write("lint_col80: %s:%d is %d columns\n" % (rel, n, w))
        sys.stdout.write("            ...%s\n" % line[LIMIT - 8:LIMIT + 12])
        sys.stdout.write("               %s^ column %d truncates here\n"
                         % (" " * 8, LIMIT))

    if bad:
        sys.stdout.write("lint_col80: FAIL - %d line(s) over %d columns in "
                         "%d files scanned\n" % (len(bad), LIMIT, scanned))
        sys.stdout.write("lint_col80: the TK5 card reader discards the excess "
                         "silently (D-93)\n")
        return 1

    sys.stdout.write("lint_col80: %d files scanned, all within %d columns "
                     "(D-93)\n" % (scanned, LIMIT))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
