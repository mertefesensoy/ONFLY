# -*- coding: utf-8 -*-
"""C-04 lint: external identifier length and case-insensitive uniqueness.

C-04 states the constraint precisely: C89 guarantees only 6 significant,
case-insensitive characters for external identifiers, and the MVS linkage
editor accepts 8 uppercase characters. ONFLY's own externals are 6 or 7
characters by design; this lint is what stops that from quietly regressing.

It also sizes a known problem rather than leaving it as a worry. Every
Berkeley SoftFloat external -- softfloat_roundPackToF64, softfloat_shiftRightJam64
and the rest -- is far longer than 8 characters. This lint cannot fix that:
whether GCCMVS truncates, mangles or maps such names is a Gate G1 question that
only a GCCMVS build can answer (assumption A-03, risk R-01). What it can do is
produce the exact list, so G1 starts knowing the scale.

Reported in three groups, because the remedies differ completely:

  ONFLY     names ONFLY defines. A violation here is a defect to fix now.
  SOFTFLOAT names from the vendored library. Gate G1 decides what happens.
  OTHER     C runtime and compiler support names, supplied on MVS by PDPCLIB.

Case-insensitive collisions are checked on the first 8 characters, because two
names that differ only after character 8, or only in case, are the same symbol
to the MVS linkage editor. That is the failure mode that produces a program
which links cleanly and calls the wrong function.

Run:  python tools/lint_c04.py <object-or-directory> [...]
Exit status 0 unless an ONFLY-owned name violates the rule.
"""
import os
import subprocess
import sys

MVS_MAX = 8
C89_SIGNIFICANT = 6

# Symbol types nm reports for externals: defined code/data, and undefined.
DEFINED = set("TDBRSC")
UNDEFINED = set("U")


def nm_symbols(path):
    """Return (name, type) for every external symbol in an object file."""
    try:
        out = subprocess.check_output(["nm", path], stderr=subprocess.STDOUT)
    except (OSError, subprocess.CalledProcessError) as exc:
        sys.stderr.write("nm failed on %s: %s\n" % (path, exc))
        return []
    syms = []
    for line in out.decode("ascii", "replace").splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        typ, name = parts[-2], parts[-1]
        if len(typ) != 1:
            continue
        if typ.upper() not in DEFINED | UNDEFINED:
            continue
        # Section symbols such as .text carry no linkage name.
        if name.startswith("."):
            continue
        # mingw32 and other COFF targets prefix externals with an underscore;
        # it is an ABI artifact, not part of the identifier the linkage editor
        # would see, so it is stripped before measuring.
        if name.startswith("_") and not name.startswith("__"):
            name = name[1:]
        if not name:
            continue
        syms.append((name, typ.upper()))
    return syms


def classify(name):
    if name.startswith("softfloat_") or name.startswith("f64_") \
            or name.startswith("f32_") or name.startswith("f128") \
            or name.startswith("extF80") or name.startswith("ui32_") \
            or name.startswith("ui64_") or name.startswith("i32_") \
            or name.startswith("i64_") or name.startswith("f16_"):
        return "SOFTFLOAT"
    if name.startswith("onf") or name.startswith("ONF"):
        return "ONFLY"
    return "OTHER"


def iter_objects(paths):
    for p in paths:
        if os.path.isfile(p):
            yield p
        else:
            for root, dirs, files in os.walk(p):
                dirs.sort()
                for f in sorted(files):
                    if f.endswith((".o", ".obj")):
                        yield os.path.join(root, f)


def main(argv):
    if len(argv) < 2:
        sys.stderr.write("usage: lint_c04.py <object-or-directory> [...]\n")
        return 2

    seen = {}
    for obj in iter_objects(argv[1:]):
        for name, typ in nm_symbols(obj):
            seen.setdefault(name, set()).add(typ)

    groups = {"ONFLY": [], "SOFTFLOAT": [], "OTHER": []}
    for name in sorted(seen):
        if len(name) > MVS_MAX:
            groups[classify(name)].append(name)

    # Case-insensitive collisions on the first MVS_MAX characters.
    trunc = {}
    for name in seen:
        trunc.setdefault(name[:MVS_MAX].upper(), []).append(name)
    collisions = {k: sorted(v) for k, v in trunc.items() if len(set(v)) > 1}

    onfly_bad = groups["ONFLY"]
    onfly_collisions = {k: v for k, v in collisions.items()
                        if any(classify(n) == "ONFLY" for n in v)}

    print("lint_c04: %d distinct external names examined" % len(seen))
    for group in ("ONFLY", "SOFTFLOAT", "OTHER"):
        names = groups[group]
        if not names:
            print("  %-9s 0 names longer than %d characters" % (group, MVS_MAX))
            continue
        print("  %-9s %d names longer than %d characters" % (group, len(names), MVS_MAX))
        shown = names if group == "ONFLY" else names[:6]
        for n in shown:
            print("      %s (%d)" % (n, len(n)))
        if len(names) > len(shown):
            print("      ... and %d more" % (len(names) - len(shown)))

    if collisions:
        print("  case-insensitive collisions in the first %d characters:" % MVS_MAX)
        for key in sorted(collisions):
            print("      %s <- %s" % (key, ", ".join(collisions[key])))
    else:
        print("  no case-insensitive collisions in the first %d characters"
              % MVS_MAX)

    # Only ONFLY's own names are actionable here.  The SoftFloat names are a
    # Gate G1 question (D-45), so they are reported and not failed on.
    if onfly_bad or onfly_collisions:
        print("lint_c04: FAIL - %d ONFLY name(s) violate C-04"
              % (len(onfly_bad) + len(onfly_collisions)))
        return 1
    print("lint_c04: ONFLY names satisfy C-04 "
          "(<= %d characters, unique ignoring case; C89 guarantees only %d)"
          % (MVS_MAX, C89_SIGNIFICANT))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
