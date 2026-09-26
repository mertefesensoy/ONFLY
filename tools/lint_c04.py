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

Symbols whose names contain a dot are skipped: section symbols such as .text,
and the optimiser's own clones such as onfirun.part.0. A dot cannot occur in a
C identifier, so those never reach the linkage editor (D-83).

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


def is_elf(path):
    """True when `path` is an ELF object, judged by its magic bytes.

    D-559: the one-underscore prefix stripped below is a COFF convention
    (mingw32).  ELF objects, on Linux x86-64 and s390x, carry the C name
    unprefixed, so stripping there misreads a name.
    """
    try:
        with open(path, "rb") as fh:
            return fh.read(4) == b"\x7fELF"
    except OSError:
        return False


def linkage_name(name, elf):
    """The identifier as C wrote it: COFF's ABI underscore removed, on COFF only."""
    if not elf and name.startswith("_") and not name.startswith("__"):
        return name[1:]
    return name


def reserved(name):
    """True for a name C89 7.1.3 reserves to the implementation for any use.

    That is a name beginning with two underscores (libgcc's __udivdi3, the
    stack protector's __stack_chk_fail) or with an underscore and an
    upper-case letter (the ELF linker's _GLOBAL_OFFSET_TABLE_).  No C
    program may define one, so C-04 has nothing to say about it (D-559).
    On COFF a C name of the second kind appears as `__X...`, so there the
    rule is exactly the two-underscore rule it replaces.
    """
    return name.startswith("__") or (
        len(name) > 1 and name[0] == "_" and name[1].isupper())


def nm_symbols(path):
    """Return (name, type) for every external symbol in an object file."""
    elf = is_elf(path)
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
        # Section symbols such as .text carry no linkage name.  Neither do the
        # optimiser's clones of a function -- onfirun.part.0, foo.isra.1,
        # bar.constprop.2 -- which GCC emits at -O2 and names after the
        # function it split.  A dot cannot appear in a C identifier at all, so
        # no name containing one is something the MVS linkage editor will ever
        # be shown, and measuring it against C-04 reports a defect that does
        # not exist (D-83).
        if "." in name:
            continue
        # mingw32 and other COFF targets prefix externals with an underscore;
        # it is an ABI artifact, not part of the identifier the linkage editor
        # would see, so it is stripped before measuring -- on COFF only
        # (D-559): ELF has no such prefix.
        name = linkage_name(name, elf)
        if not name:
            continue
        # The ORIGINAL case is kept.  nm spells a global symbol with an
        # upper-case letter and a file-local one with lower case, and the
        # difference is exactly what C-04 is about: it constrains EXTERNAL
        # names, the ones the MVS linkage editor is shown.  SoftFloat 2c's
        # file-local addFloat64Sigs and roundAndPackFloat64 collide at
        # eight characters and Assembler XF accepted them without a word,
        # because they are never ENTRY.  Measuring them would report
        # defects that do not exist -- the same reasoning as D-83.
        syms.append((name, typ))
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
    args = [a for a in argv[1:] if not a.startswith("--")]
    # D-111.  Without this the lint reports vendored collisions and passes,
    # which is how SoftFloat 2c reached the assembler on MVS before anyone
    # noticed that eighteen of its float64_* names truncate to FLOAT64@
    # (VL-25).  --enforce-all makes EVERY external actionable and is used
    # on the objects that actually go to MVS: nothing there gets an
    # exemption, because the linkage editor gives none.
    enforce_all = "--enforce-all" in argv
    if not args:
        sys.stderr.write("usage: lint_c04.py [--enforce-all] "
                         "<object-or-directory> [...]\n")
        return 2

    seen = {}
    for obj in iter_objects(args):
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

    if enforce_all:
        # Names beginning with two underscores are reserved to the
        # implementation in C89: __udivdi3 and __umoddi3 are libgcc's
        # synthesised 64-bit divide and modulo, emitted by the compiler
        # rather than chosen by anyone here, so C-04 has nothing to say
        # about them and renaming them is not possible.  They are not
        # ignored elsewhere: VL-21 records that PDPCLIB supplies neither,
        # measured by linking an EXTRN against PDPCLIB.NCALIB.
        # D-559 widens "two underscores" to C89 7.1.3's whole reserved
        # class, so that ELF's _GLOBAL_OFFSET_TABLE_ is read for what it is.
        glob = set(n for n, types in seen.items()
                   if any(t.isupper() for t in types)
                   and not reserved(n))
        bad_names = sorted(n for n in glob if len(n) > MVS_MAX)
        bad_groups = {k: v for k, v in collisions.items()
                      if len([n for n in v if n in glob]) > 1}
        print("  %d of %d externals are global; C-04 constrains those"
              % (len(glob), len(seen)))
        for n in bad_names[:12]:
            print("      %s (%d) is over %d characters" % (n, len(n), MVS_MAX))
        for k in sorted(bad_groups):
            print("      %s <- %s" % (k, ", ".join(bad_groups[k])))
        bad = len(bad_names)
        collisions = bad_groups
        if bad or collisions:
            print("lint_c04: FAIL - %d name(s) over %d characters and %d "
                  "collision group(s); C-04 admits no exemption on an "
                  "object bound for MVS (D-111)"
                  % (bad, MVS_MAX, len(collisions)))
            return 1
        print("lint_c04: every external satisfies C-04 "
              "(<= %d characters, unique ignoring case; C89 guarantees "
              "only %d)" % (MVS_MAX, C89_SIGNIFICANT))
        return 0

    # Without --enforce-all only ONFLY's own names are actionable.  The
    # Release 3e names are reported rather than failed on: under NR-03 and
    # D-105 the MVS backend is Release 2c, so 3e is not on a path to an
    # MVS linkage editor, and whether it ever reaches one on z/OS is an
    # open question rather than a settled exemption.
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
