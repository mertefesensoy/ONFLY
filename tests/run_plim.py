# -*- coding: utf-8 -*-
"""FR-LOD-04, D-567, D-568, D-572: what onfplat.h configures on each platform.

engine/include/onfplat.h is the one file NFR-PRT-01 lets differ by platform,
and three of its macros must agree about which platform they are on:
ONF_PLATID, which the run manifest prints (NFR-OBS-01); ONF_MEMLIM,
FR-LOD-04's configured limit (D-567, D-568); and ONF_MAXPAY, the sanity bound
on a declared payload length (D-147, D-231).  Before D-572 two of them did
not: with only JCC's macros defined, ONF_PLATID said MVS38J while ONF_MAXPAY
gave a development host's 512 MB (P-45 S5).

This preprocesses the header once per platform with the compiler's own
predefined macros removed (-undef) and only that platform's added, and reads
the values back with -dM.  It also checks the -DONF_MEMLIM override D-567
relies on for TE-08's test builds: a header that defined ONF_MEMLIM without
an #ifndef guard would override the build's value, and the replay in
tests/run_eng.py would test the wrong limit.

What it proves and what it does not: the header's logic, under the
preprocessor it is given.  It does not prove what JCC or GCCMVS make of the
same text; those run only on TK5 (Section 8.3 rows 6 and 7).

Contract: runs the compiler named on the command line, writes nothing.
Run:  python tests/run_plim.py <cc>
Exit status 0 when every platform gets its values, 1 otherwise, 2 on usage.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import run_dec                        # noqa: E402

HEADER = os.path.join(ROOT, "engine", "include", "onfplat.h")

#: D-147's MVS bound and D-231's bound elsewhere, in bytes.
MAXPAY_MVS = 67108864
MAXPAY_ELSE = 536870912

#: (label, macros, ONF_PLATID, ONF_MEMLIM, ONF_MAXPAY).  The last four rows
#: pin the ORDER: JCC is matched after __s390x__ and _WIN32 in ONF_PLATID's
#: chain (D-291), so ONF_MEMLIM must follow the same order, and an explicit
#: -DONF_MEMLIM must win on any platform.
CASES = (
    ("MVS 3.8j, GCCMVS", ["-D__MVS__"], "MVS38J",
     run_dec.MVS_MEMLIM, MAXPAY_MVS),
    ("CMS", ["-D__CMS__"], "MVS38J", run_dec.MVS_MEMLIM, MAXPAY_MVS),
    ("MVS 3.8j, JCC", ["-DJCC"], "MVS38J", run_dec.MVS_MEMLIM, MAXPAY_MVS),
    ("Linux s390x", ["-D__s390x__"], "S390X", 0, MAXPAY_ELSE),
    ("Linux s390 (31-bit)", ["-D__s390__"], "S390X", 0, MAXPAY_ELSE),
    ("x86-64 Windows", ["-D_WIN32"], "WIN32", 0, MAXPAY_ELSE),
    ("Windows, __WIN32__", ["-D__WIN32__"], "WIN32", 0, MAXPAY_ELSE),
    ("Linux x86-64", ["-D__linux__", "-D__x86_64__"], "X86LINUX", 0,
     MAXPAY_ELSE),
    ("no platform macro", [], "UNKNOWN", 0, MAXPAY_ELSE),
    ("JCC and __s390x__", ["-DJCC", "-D__s390x__"], "S390X", 0, MAXPAY_ELSE),
    ("JCC and _WIN32", ["-DJCC", "-D_WIN32"], "WIN32", 0, MAXPAY_ELSE),
    ("MVS, -DONF_MEMLIM=64", ["-D__MVS__", "-DONF_MEMLIM=64"], "MVS38J",
     64, MAXPAY_MVS),
    ("Windows, -DONF_MEMLIM=1048576", ["-D_WIN32", "-DONF_MEMLIM=1048576"],
     "WIN32", 1048576, MAXPAY_ELSE),
)


def macros(cc, defs):
    """{name: replacement text} for the header under `defs`, or an error."""
    cmd = [cc, "-undef", "-E", "-dM"] + defs + [HEADER]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    out, err = proc.communicate()
    if proc.returncode != 0:
        return None, err.decode("ascii", "replace").strip()
    found = {}
    for line in out.decode("ascii", "replace").splitlines():
        parts = line.split(None, 2)
        if len(parts) == 3 and parts[0] == "#define":
            found[parts[1]] = parts[2].strip()
    return found, err.decode("ascii", "replace").strip()


def number(text):
    """An integer macro's value, its L or UL suffix removed; None if absent."""
    if text is None:
        return None
    t = text.rstrip("uUlL")
    return int(t) if t.isdigit() else None


def main():
    if len(sys.argv) != 2:
        sys.stderr.write("usage: run_plim.py <cc>\n")
        return 2
    cc = sys.argv[1]
    ok = bad = 0
    for label, defs, platid, memlim, maxpay in CASES:
        try:
            found, err = macros(cc, defs)
        except OSError as exc:
            found, err = None, str(exc)
        if found is None:
            bad += 1
            print("  FAIL %-32s preprocessor: %s" % (label, err))
            continue
        got = (found.get("ONF_PLATID", "").strip('"'),
               number(found.get("ONF_MEMLIM")),
               number(found.get("ONF_MAXPAY")))
        want = (platid, memlim, maxpay)
        # A warning here is a redefinition: the header overriding -D.
        good = got == want and "redefined" not in err
        detail = "PLATID %s MEMLIM %s MAXPAY %s" % got
        if good:
            ok += 1
            print("  ok   %-32s %s" % (label, detail))
        else:
            bad += 1
            print("  FAIL %-32s %s (want PLATID %s MEMLIM %s MAXPAY %s)%s"
                  % ((label, detail) + want
                     + ((" " + err) if err else "",)))
    print("run_plim: %d passed, %d failed" % (ok, bad))
    if bad:
        print("run_plim: FAILED")
        return 1
    print("run_plim: ok   ONF_PLATID, ONF_MEMLIM and ONF_MAXPAY agree on "
          "every platform")
    return 0


if __name__ == "__main__":
    sys.exit(main())
