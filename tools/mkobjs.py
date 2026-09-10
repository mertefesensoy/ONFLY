# -*- coding: utf-8 -*-
"""Compile a list of C sources to objects in one directory.

Exists so the Makefile can build a set of objects for the C-04 lint without a
shell loop: mingw32-make selects cmd.exe or sh.exe depending on what is on
PATH, and a for-loop written for one is a syntax error in the other.

Run:  python tools/mkobjs.py <outdir> <compile command...> -- <source...>
"""
import os
import subprocess
import sys


def main(argv):
    if "--" not in argv:
        sys.stderr.write("usage: mkobjs.py <outdir> <cc args...> -- <sources...>\n")
        return 2
    split = argv.index("--")
    outdir, cc = argv[1], argv[2:split]
    sources = argv[split + 1:]
    if not os.path.isdir(outdir):
        os.makedirs(outdir)
    failed = 0
    for src in sources:
        obj = os.path.join(outdir, os.path.splitext(os.path.basename(src))[0] + ".o")
        cmd = cc + ["-c", src, "-o", obj]
        if subprocess.call(cmd) != 0:
            sys.stderr.write("failed: %s\n" % " ".join(cmd))
            failed += 1
    print("mkobjs: %d sources compiled into %s, %d failed"
          % (len(sources) - failed, outdir.replace("\\", "/"), failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
