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
         byte-for-byte copy of softfloat/tfgen/platform.h.
Output   one line per directory, naming it and the bytes copied.
Exit     0 on success; a non-zero OSError propagates rather than being
         swallowed, because a silently missing platform.h would be found only
         as a confusing compile error deep inside third_party.

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
    for d in argv:
        if not os.path.isdir(d):
            os.makedirs(d)
        dst = os.path.join(d, "platform.h")
        shutil.copyfile(SRC, dst)
        print("tfgprep: %s <- softfloat/tfgen/platform.h (%d bytes)"
              % (dst, os.path.getsize(dst)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
