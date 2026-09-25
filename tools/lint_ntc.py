# -*- coding: utf-8 -*-
"""Hold the licence notices to the component register (NFR-LIC-01, P-43).

WHY THIS EXISTS
---------------
Until P-41's slice C, ONFLY's third-party terms lived in a block appended
to LICENSE.  That block named two of MaleCNS's four parties, called the
SoftFloat 2c derivatives BSD, which they are not, and left out SoftFloat
2c itself, the Shiu et al. code, the FlyWire-derived material and every
tool the labs depend on.  It also stopped GitHub detecting the licence at
all, because LICENSE was no longer the MIT text.

Slice C moves the terms into one register, THIRD_PARTY_NOTICES.md, and
leaves LICENSE as the MIT text alone.  A register kept only by care drifts
the first time a path is renamed or a component is added, and the drift
is invisible: a notices file reads as complete whether or not it is.  So
the rule is mechanical, as tools/lint_lic.py made D-132's rule mechanical.

WHAT IT CHECKS
--------------
1. LICENSE is the MIT text and nothing else: it opens "MIT License" and
   no line follows the disclaimer's closing "SOFTWARE.".
2. THIRD_PARTY_NOTICES.md names every component in COMPONENTS and every
   path each one lists, and every tool in TOOLS.
3. Every path in COMPONENTS exists in the tree, so a rename that leaves
   the register pointing at nothing fails here rather than in a reader's
   hands.
4. The BSD-derived SoftFloat 3e files carry the full BSD conditions and
   disclaimer (P-41 C7), not only a pointer to COPYING.txt.
5. The two notices that travel with the data exist:
   reference/shiu/results/NOTICE.md and data/README.md.

WHAT IT CANNOT DO
-----------------
It checks that the register names things, not that what it says about
them is right.  Whether a licence is stated correctly is a matter of
reading the upstream terms, and P-43 records the date each was checked.
It is not legal advice and neither is the register.  It does not run
`reuse lint`; that tool is not a declared dependency (D-521).

usage:  python tools/lint_ntc.py [--self-test]
        exit 0 clean, 1 on a finding, 2 on an internal error
"""
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

NOTICES = "THIRD_PARTY_NOTICES.md"

# P-41 item 8's inventory of FlyWire-derived material (D-515).  W_syn is
# named in the register as a value, not a path, so it is not listed here.
ITEM8 = (
    "reference/shiu/results/",
    "reference/shiu/rerun.py",
    "docs/implementations/2026-09-12-phase-c-calibration.md",
) + tuple("data/calibration/%s.json" % n for n in (
    "acc1-candidate", "acc4", "acc4-phg9", "acc4-right", "acc4-tpgrn",
    "search-log", "search-log-rerun", "seeds", "wsens-d52-s30",
    "wsens-right-s30", "wsens-tpgrn-s30", "wsens-tpgrn-s4"))

# P-43 Section 1: the components in the tree, each with the paths the
# register must name.  A trailing slash is a directory.
COMPONENTS = (
    ("Berkeley SoftFloat Release 3e", (
        "third_party/SoftFloat-3e/", "softfloat/onfrpk.c",
        "softfloat/onfprim.c", "softfloat/onfsub.c")),
    ("Berkeley TestFloat Release 3e", (
        "third_party/TestFloat-3e/", "generated/onftfv.h")),
    ("Berkeley SoftFloat Release 2c", (
        "third_party/SoftFloat-2c/", "softfloat/c2c/")),
    ("Shiu et al.", (
        "reference/shiu/model.py", "reference/shiu/utils.py",
        "reference/shiu/LICENSE")),
    ("MaleCNS v1.0", (
        "data/networks/", "data/geom/", "data/calibration/",
        "data/phase-d/", "data/phase-e/", "docs/media/")),
    ("FlyWire", ITEM8),
)

# P-43 Section 1: used, not included.
TOOLS = ("JCC", "Raincode", "INTERCOMM", "Hercules", "TK5", "GCCMVS",
         "PDPCLIB", "GnuCOBOL", "QEMU", "wc3270", ".NET", "brian2",
         "numpy", "pandas", "pyarrow", "matplotlib", "Pillow", "docx",
         "reuse", "MinGW", "GNU Make", "Python")

BSD_FILES = ("softfloat/onfrpk.c", "softfloat/onfprim.c")
BSD_PHRASES = (
    "Redistribution and use in source and binary forms",
    "THIS SOFTWARE IS PROVIDED BY THE REGENTS AND CONTRIBUTORS",
)

DATA_NOTICES = ("reference/shiu/results/NOTICE.md", "data/README.md")


def read(root, rel):
    path = os.path.join(root, *rel.split("/"))
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return None


def exists(root, rel):
    path = os.path.join(root, *rel.rstrip("/").split("/"))
    return os.path.isdir(path) if rel.endswith("/") else \
        os.path.isfile(path)


def check_licence(root):
    text = read(root, "LICENSE")
    if text is None:
        return ["LICENSE: missing"]
    lines = [ln.rstrip() for ln in text.splitlines()]
    while lines and not lines[-1]:
        lines.pop()
    out = []
    if not lines or lines[0] != "MIT License":
        out.append("LICENSE: does not open with 'MIT License'")
    if not lines or not lines[-1].endswith("SOFTWARE."):
        out.append("LICENSE: text follows the MIT disclaimer; third-party "
                   "terms belong in %s" % NOTICES)
    return out


def check_register(root):
    text = read(root, NOTICES)
    if text is None:
        return ["%s: missing" % NOTICES]
    out = []
    for name, paths in COMPONENTS:
        if name not in text:
            out.append("%s: component not named: %s" % (NOTICES, name))
        for rel in paths:
            if rel not in text:
                out.append("%s: %s path not named: %s"
                           % (NOTICES, name, rel))
    for tool in TOOLS:
        if tool not in text:
            out.append("%s: tool not named: %s" % (NOTICES, tool))
    return out


def check_paths(root):
    out = []
    for name, paths in COMPONENTS:
        for rel in paths:
            if not exists(root, rel):
                out.append("register path absent from the tree: %s (%s)"
                           % (rel, name))
    return out


def check_bsd(root):
    out = []
    for rel in BSD_FILES:
        text = read(root, rel)
        if text is None:
            out.append("%s: missing" % rel)
            continue
        for phrase in BSD_PHRASES:
            if phrase not in text:
                out.append("%s: lacks the BSD text '%s...'"
                           % (rel, phrase[:30]))
    return out


def check_data_notices(root):
    return ["%s: missing" % rel for rel in DATA_NOTICES
            if not exists(root, rel)]


def findings(root):
    return (check_licence(root) + check_register(root) + check_paths(root)
            + check_bsd(root) + check_data_notices(root))


MIT_BODY = ("MIT License\n\nCopyright (c) 2026 Someone\n\n"
            "Permission is hereby granted, free of charge, ...\n\n"
            "... IN THE\nSOFTWARE.\n")


def good_tree(root):
    """A minimal tree that satisfies every check."""
    def put(rel, text=""):
        path = os.path.join(root, *rel.rstrip("/").split("/"))
        if rel.endswith("/"):
            if not os.path.isdir(path):
                os.makedirs(path)
            return
        parent = os.path.dirname(path)
        if not os.path.isdir(parent):
            os.makedirs(parent)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
    put("LICENSE", MIT_BODY)
    names = []
    for name, paths in COMPONENTS:
        names.append(name)
        for rel in paths:
            put(rel)
            names.append(rel)
    put(NOTICES, "\n".join(names + list(TOOLS)) + "\n")
    for rel in BSD_FILES:
        put(rel, "\n".join(BSD_PHRASES) + "\n")
    for rel in DATA_NOTICES:
        put(rel, "notice\n")


def self_test():
    checks = [0, 0]

    def check(name, ok):
        checks[0] += 1
        if not ok:
            checks[1] += 1
            print("lint_ntc: self-test FAIL: %s" % name)

    def mutate(root, rel, fn):
        path = os.path.join(root, *rel.split("/"))
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(fn(text))

    def fresh():
        root = tempfile.mkdtemp(prefix="lint_ntc_")
        good_tree(root)
        return root

    cases = (
        ("a good tree passes", None, 0),
        ("text after the MIT disclaimer", lambda r: mutate(
            r, "LICENSE", lambda t: t + "\nTHIRD-PARTY TERMS\n"), 1),
        ("LICENSE not opening with 'MIT License'", lambda r: mutate(
            r, "LICENSE", lambda t: "Licence\n" + t), 1),
        ("LICENSE missing", lambda r: os.remove(
            os.path.join(r, "LICENSE")), 1),
        ("register missing", lambda r: os.remove(
            os.path.join(r, NOTICES)), 1),
        ("a component unnamed", lambda r: mutate(
            r, NOTICES, lambda t: t.replace("Shiu et al.", "")), 1),
        ("an item 8 path unnamed", lambda r: mutate(
            r, NOTICES, lambda t: t.replace(
                "data/calibration/seeds.json", "")), 1),
        ("a tool unnamed", lambda r: mutate(
            r, NOTICES, lambda t: t.replace("wc3270", "")), 1),
        ("a register path renamed away", lambda r: os.remove(
            os.path.join(r, "reference", "shiu", "rerun.py")), 1),
        ("a BSD file without the conditions", lambda r: mutate(
            r, "softfloat/onfprim.c", lambda t: BSD_PHRASES[1]), 1),
        ("a BSD file without the disclaimer", lambda r: mutate(
            r, "softfloat/onfrpk.c", lambda t: BSD_PHRASES[0]), 1),
        ("the Shiu results notice missing", lambda r: os.remove(
            os.path.join(r, "reference", "shiu", "results",
                         "NOTICE.md")), 1),
        ("the data README missing", lambda r: os.remove(
            os.path.join(r, "data", "README.md")), 1),
    )
    for name, fn, want in cases:
        root = fresh()
        try:
            if fn is not None:
                fn(root)
            got = findings(root)
            check(name, (len(got) == 0) if want == 0 else
                  (len(got) >= want))
        finally:
            shutil.rmtree(root, ignore_errors=True)

    print("lint_ntc: self-test %d checks, %d failed" % tuple(checks))
    return 1 if checks[1] else 0


def main(argv):
    if argv == ["--self-test"]:
        return self_test()
    if argv:
        sys.stderr.write(__doc__.split("usage:")[1])
        return 2
    got = findings(ROOT)
    if not got:
        print("lint_ntc: ok -- %s names %d components, %d item 8 paths "
              "and %d tools; LICENSE is the MIT text alone"
              % (NOTICES, len(COMPONENTS), len(ITEM8), len(TOOLS)))
        return 0
    print("lint_ntc: %d finding(s). NFR-LIC-01 keeps third-party terms"
          % len(got))
    print("  in one register, %s, and LICENSE as the MIT text." % NOTICES)
    for f in got:
        print("  " + f)
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as exc:
        sys.stderr.write("lint_ntc: internal error: %s: %s\n"
                         % (type(exc).__name__, exc))
        sys.exit(2)
