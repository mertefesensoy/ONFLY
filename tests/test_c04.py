# -*- coding: utf-8 -*-
"""The C-04 lint reads COFF and ELF objects correctly (D-559).

`tools/lint_c04.py` measures every external name against the MVS linkage
editor's 8 characters.  It used to strip one leading underscore from every
name, because mingw32's COFF objects prefix each C identifier with one.
ELF objects do not, so on Linux x86-64 the lint turned the ELF linker's own
symbol `_GLOBAL_OFFSET_TABLE_`, which position-independent code references,
into the 20-character "global" `GLOBAL_OFFSET_TABLE_` and failed.

What is pinned here:
  - the underscore is stripped on COFF only;
  - a name beginning with two underscores, or with an underscore and an
    upper-case letter, is the implementation's (C89 7.1.3), whatever the
    object format;
  - on COFF the new rule changes nothing: a stripped name can never begin
    with an underscore and an upper-case letter, so x86w's result is the
    same as before;
  - ONFLY's and SoftFloat's names are never reserved, so --enforce-all
    (D-111) still enforces every one of them.

Run:  python tests/test_c04.py
"""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import lint_c04 as L                                   # noqa: E402

ok = bad = 0


def check(label, cond, detail=""):
    global ok, bad
    ok, bad = (ok + 1, bad) if cond else (ok, bad + 1)
    print("  %-4s %-58s %s" % ("ok" if cond else "FAIL", label, detail))


def main():
    # --- the underscore is a COFF convention -------------------------------
    check("COFF: _onfrun is the C name onfrun",
          L.linkage_name("_onfrun", elf=False) == "onfrun")
    check("COFF: __udivdi3 keeps both underscores",
          L.linkage_name("__udivdi3", elf=False) == "__udivdi3")
    check("ELF: onfrun is onfrun, nothing stripped",
          L.linkage_name("onfrun", elf=True) == "onfrun")
    check("ELF: _GLOBAL_OFFSET_TABLE_ keeps its underscore",
          L.linkage_name("_GLOBAL_OFFSET_TABLE_", elf=True)
          == "_GLOBAL_OFFSET_TABLE_")

    # --- C89 7.1.3: the implementation's names ------------------------------
    for name in ("__udivdi3", "__stack_chk_fail", "_GLOBAL_OFFSET_TABLE_",
                 "_DYNAMIC"):
        check("reserved to the implementation: %s" % name, L.reserved(name))
    for name in ("onfrun", "ONFDEC", "softfloat_roundPackToF64", "f64_add",
                 "float64_add", "main", "_onflocal"):
        check("not reserved: %s" % name, not L.reserved(name))

    # --- on COFF the new rule can change nothing ----------------------------
    # Every raw COFF symbol, after linkage_name(): either it began with two
    # underscores (reserved before and after), or one underscore was
    # stripped and what remains is the C name.  A C name beginning with an
    # underscore and an upper-case letter would appear raw as `__X...`.
    for raw in ("_onfrun", "__udivdi3", "__Xfoo", "_Zbar", "_main"):
        got = L.linkage_name(raw, elf=False)
        before = got.startswith("__")
        check("COFF %s: reserved exactly as before" % raw,
              L.reserved(got) == before, "-> %s" % got)

    # --- object format from the file's own magic ----------------------------
    fd, path = tempfile.mkstemp(suffix=".o")
    os.close(fd)
    try:
        open(path, "wb").write(b"\x7fELF\x02\x01\x01" + b"\0" * 57)
        check("an ELF object is recognised by its magic", L.is_elf(path))
        open(path, "wb").write(b"\x4c\x01\x05\x00" + b"\0" * 60)
        check("an i386 COFF object is not ELF", not L.is_elf(path))
    finally:
        os.remove(path)
    check("an unreadable path is not ELF", not L.is_elf(path))

    print("test_c04: %d passed, %d failed" % (ok, bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
