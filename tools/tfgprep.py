# -*- coding: utf-8 -*-
"""Prepare out-of-tree build directories for the TestFloat generator (D-225).

NR-14 requires the TestFloat vector suite to pass on every platform, but
third_party/ ships only a Win32-MinGW build of testfloat_gen, and D-28 and
D-35 commit third_party/ to byte-identity with the published archives, so a
new build directory cannot be added there.

Both vendored Makefiles declare SOURCE_DIR, SPECIALIZE_TYPE and PLATFORM with
``?=`` and put ``-I.`` -- the build directory -- first on the include path.
That is upstream's own mechanism for a new platform: a build directory holding
nothing but a platform.h.  This script creates those directories under the
ONFLY build tree and drops softfloat/tfgen/platform.h into each; the Makefile
then runs the vendored Makefiles with -C pointed at them.

Contract
--------
Inputs   one or more directory paths, relative to the repository root.
Effect   each directory exists afterwards and contains a platform.h that is a
         byte-for-byte copy of softfloat/tfgen/platform.h.  A file whose
         content already matches is LEFT ALONE, mtime included.
Output   one line per directory, saying whether it was written or unchanged.
Exit     0 on success; a non-zero OSError propagates rather than being
         swallowed, because a silently missing platform.h would be found only
         as a confusing compile error deep inside third_party.

Why the content check matters, and is not an optimisation
---------------------------------------------------------
platform.h is the first prerequisite of every object in both vendored
Makefiles.  Copying it unconditionally updates its mtime, which makes all
481 objects out of date, so every TT-02 run would rebuild the whole of
SoftFloat and TestFloat from scratch.  Measured on the s390x guest under TCG
emulation that is over an hour, against seconds for a relink.  Leaving an
identical file untouched is what makes the rule incremental.

Run:  python tools/tfgprep.py <dir> [<dir> ...]
"""
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "softfloat", "tfgen", "platform.h")


def main(argv):
    if not argv:
        sys.stderr.write("usage: tfgprep.py <dir> [<dir> ...]\n")
        return 2
    if not os.path.isfile(SRC):
        sys.stderr.write("tfgprep: missing %s\n" % SRC)
        return 2
    with open(SRC, "rb") as f:
        want = f.read()

    for d in argv:
        if not os.path.isdir(d):
            os.makedirs(d)
        dst = os.path.join(d, "platform.h")
        have = None
        if os.path.isfile(dst):
            with open(dst, "rb") as f:
                have = f.read()
        if have == want:
            print("tfgprep: %s unchanged (%d bytes)" % (dst, len(want)))
            continue
        shutil.copyfile(SRC, dst)
        print("tfgprep: %s <- softfloat/tfgen/platform.h (%d bytes)"
              % (dst, len(want)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
