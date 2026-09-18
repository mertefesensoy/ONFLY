# -*- coding: utf-8 -*-
"""`prep/netman.py`, and the note it was written to correct (D-450..D-453).

TWO THINGS ARE CHECKED, AND THEY FAIL FOR DIFFERENT REASONS
------------------------------------------------------------
**The artefact.**  `data/networks/MANIFEST.json` must carry the acceptance
note D-452 fixed.  This is the half that catches a SILENT REVERT: a later
`prep/extract.py` admission rewrites `networks.srext` wholesale and would
drop the amendment, exactly as `prep/names.py` warns for the names
section.  Nothing else in the tree would notice, because the note is
prose that no code reads.  If this half fails, re-run the amend.

**The tool.**  `prep/netman.py` must be incapable of moving a network
byte.  That is the property the whole approach rests on: D-269 records
that re-running the generator would rewrite `data/networks/*.bin`, and
if any byte differed every Section 8.4 fingerprint and every MVS result
taken against them would have to be redone.  The amend path is only
acceptable because it cannot do that.  If this half fails, the tool is
wrong and the artefact half's PASS means nothing.

The tool half works on a COPY in a temporary directory.  It never writes
the real manifest, so running this test is safe in any order and on a
tree with local changes.

Run:  python tests/test_netman.py
Exit status 0 when both halves hold, 1 otherwise.
"""
import ast
import io
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "prep"))

import netman  # noqa: E402

MANIFEST = os.path.join(ROOT, "data", "networks", "MANIFEST.json")
EXTRACT = os.path.join(ROOT, "prep", "extract.py")

# D-452's text, as the owner approved it on 2026-09-18.  Held here as a
# golden value: the manifest is generated, so the only way to state what
# it OUGHT to say is to say it somewhere a generator run cannot reach.
EXPECTED_NOT_PROVEN = (
    "Nothing is proven for z/OS: Section 8.3 row 8 is empty. "
    "ACC-1, ACC-2 and ACC-3 are x86-64 results "
    "(VL-76, VL-77, VL-78, VL-98, VL-105). "
    "ACC-4 compares the full brain against Shiu, not this network, and "
    "passes on the shape clause as amended by D-340 and D-341, with "
    "magnitude deviations at 10 and 40 Hz reported, not tested (VL-112). "
    "Proven since this note was first written: Linux s390x under QEMU "
    "(D-234), and MVS 3.8j, where GCCMVS decoded the v1.1 header and "
    "both GCCMVS and JCC reproduced the five srext golden fingerprints: "
    "ACC-5 rows 6 and 7 (VL-91, VL-93, VL-95, VL-96), ACC-6 PASS "
    "(VL-102, VL-106), ACC-7 PASS (VL-104). Row 7 covers the five srext "
    "requests only. Both labs are emulators (VL-01)."
)

# Modules that reach a connectome or an emitted network.  netman.py must
# import none of them, which is what makes its safety structural rather
# than a promise in a docstring.
FORBIDDEN_IMPORTS = ("extract", "emit", "calibrate", "activity", "numpy",
                     "pandas", "geom")


def check(label, ok, detail=""):
    print("  %-4s %-54s %s" % ("ok" if ok else "FAIL", label, detail))
    return (1, 0) if ok else (0, 1)


def main():
    ok = bad = 0

    # ---- the artefact -------------------------------------------------
    man = netman.load(MANIFEST)
    note = netman.get_field(man, "srext", "acceptance.not_proven")
    a, b = check("srext acceptance note is D-452's text",
                 note == EXPECTED_NOT_PROVEN,
                 "%d chars" % len(note or ""))
    ok += a
    bad += b
    if note != EXPECTED_NOT_PROVEN:
        print("       found: %s" % note)

    # The stale note claimed ACC-5, ACC-6 and ACC-7 were unevaluated and
    # that ACC-4 failed.  Name the exact phrases so a partial revert is
    # reported as itself rather than as "the text differs".
    for stale in ("ACC-5, ACC-6 and ACC-7 are unevaluated",
                  "ACC-4 fails",
                  "has never been decoded by GCCMVS",
                  "Every result is x86-64"):
        a, b = check("the stale clause is gone: %.40s" % stale,
                     stale not in (note or ""))
        ok += a
        bad += b

    # ---- the generator emits the same text (D-454) --------------------
    # Read as source, not imported: `prep/extract.py` pulls in the whole
    # extraction pipeline and needs a connectome on disk, which a clone
    # does not have.  The literal is adjacent string fragments, which
    # the parser has already folded into one constant.
    gen = None
    tree = ast.parse(io.open(EXTRACT, encoding="utf-8").read())
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        for k, v in zip(node.keys, node.values):
            if isinstance(k, ast.Constant) and k.value == "not_proven":
                gen = ast.literal_eval(v)
    a, b = check("prep/extract.py emits the same note",
                 gen == EXPECTED_NOT_PROVEN,
                 "%s" % ("%d chars" % len(gen) if gen is not None
                         else "no not_proven literal found"))
    ok += a
    bad += b

    # ---- the tool: structural safety ----------------------------------
    # Parsed, not grepped: a docstring line beginning "from " is prose,
    # and matching it would make this check fail, or pass, for a reason
    # that has nothing to do with what netman imports.
    src = io.open(netman.__file__.replace(".pyc", ".py"),
                  encoding="utf-8").read()
    imported = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Import):
            imported.update(n.name.split(".")[0] for n in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add((node.module or "").split(".")[0])
    hits = sorted(imported & set(FORBIDDEN_IMPORTS))
    a, b = check("netman imports nothing that reaches a network",
                 not hits, "imports: %s" % ", ".join(sorted(imported)))
    ok += a
    bad += b

    # ---- the tool: an amend moves no digest ---------------------------
    tmp = tempfile.mkdtemp(prefix="onfnetman")
    try:
        copy = os.path.join(tmp, "MANIFEST.json")
        shutil.copyfile(MANIFEST, copy)
        before = netman.digest_of(netman.load(copy))

        work = netman.load(copy)
        prev = netman.set_field(work, "srext", "acceptance.not_proven",
                                "a deliberately different note")
        netman.save(work, copy)
        after = netman.digest_of(netman.load(copy))

        a, b = check("every network digest survives an amend",
                     before == after,
                     "%d network(s): %s" % (len(after),
                                            ", ".join(sorted(after))))
        ok += a
        bad += b
        a, b = check("the amend actually changed the field",
                     netman.get_field(netman.load(copy), "srext",
                                      "acceptance.not_proven")
                     == "a deliberately different note"
                     and prev == EXPECTED_NOT_PROVEN)
        ok += a
        bad += b

        # Only the one field moved.  Compare the whole document with that
        # field put back: anything else that changed shows up here.
        restored = netman.load(copy)
        netman.set_field(restored, "srext", "acceptance.not_proven", prev)
        a, b = check("nothing but that field moved",
                     json.dumps(restored, sort_keys=True)
                     == json.dumps(netman.load(MANIFEST), sort_keys=True))
        ok += a
        bad += b

        # A typo in --field must not invent a key that reads like a real
        # one.  Both of these exit rather than write.
        for net, field in (("nosuchnet", "acceptance.not_proven"),
                           ("srext", "acceptance.no_such_field"),
                           ("srext", "no_such_block.x")):
            try:
                netman.set_field(netman.load(copy), net, field, "x")
                refused = False
            except SystemExit:
                refused = True
            a, b = check("refuses networks.%s.%s" % (net, field), refused)
            ok += a
            bad += b
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("test_netman: %d passed, %d failed" % (ok, bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
