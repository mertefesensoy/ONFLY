# -*- coding: utf-8 -*-
"""Amend one field of `data/networks/MANIFEST.json` in place (D-450, D-453).

WHY THIS EXISTS

The networks manifest is written by `prep/extract.py`'s admission step,
which also re-derives the subcircuit and rewrites the `.bin`.  D-269
records what that costs: if any emitted byte differed, every Section 8.4
fingerprint and every MVS result taken against them would have to be
redone, because IR-COM-05 puts the network's payload CRC inside the
fingerprint.  So a manifest field that has gone stale cannot be fixed by
re-running its generator.

It must not be fixed by hand either: a generated artifact that diverges
from its generator is reverted, silently, by the next generator run.

This module is the third way.  It reads the manifest, sets one field of
one network, and writes the file back.  It is the same shape as
`prep/names.py`'s `register()`, which merges the names section into this
same file without regenerating a network byte (D-269).

THE SAFETY PROPERTY IS STRUCTURAL, NOT PROMISED

This module imports `json`, `io`, `os` and `sys`.  It does not import
`prep.extract`, `prep.emit` or anything that reaches a connectome, and
it opens exactly one path: the manifest.  It therefore cannot rewrite a
`.bin`, and `tests/test_netman.py` asserts that every network's recorded
`bytes`, `crc32` and `sha256` are unchanged across an amend.

CARRIED FORWARD, THE SAME WAY names.py CARRIES IT

A later `prep/extract.py` admission rewrites `networks.<name>` wholesale
and would drop an amendment made here.  That is inherent to amending a
generated file and is why `--check` exists: it re-asserts, without
writing, that the shipped manifest still says what a decision says it
should.  The `make prep` target can then catch a silent revert.

Run:  python prep/netman.py --network srext \\
          --field acceptance.not_proven --from-file note.txt
      python prep/netman.py --network srext \\
          --field acceptance.not_proven --check-file note.txt
      python prep/netman.py --show srext
      python prep/netman.py --network srext --mark distributed

`--mark` is the one way this tool creates a key: it sets a boolean mark
named in MARKS to true (D-551), so the distributed set of D-545 is recorded
in the manifest without re-running a generator.
"""
import argparse
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
NETDIR = os.path.join(ROOT, "data", "networks")
MANIFEST = os.path.join(NETDIR, "MANIFEST.json")

# The three keys a network entry records about its own bytes.  Nothing in
# this module writes them; the test asserts they are untouched, and
# `digest_of()` is what it compares.
BYTE_KEYS = ("bytes", "crc32", "sha256")


def load(path=MANIFEST):
    """Read the manifest, or exit with a message naming the path."""
    if not os.path.isfile(path):
        raise SystemExit("no manifest: %s" % path.replace("\\", "/"))
    return json.loads(io.open(path, encoding="utf-8").read())


def save(man, path=MANIFEST):
    """Write the manifest in the spelling every other writer uses.

    indent=2, sort_keys=True is what `prep/manifest.py`, `prep/emit.py`
    and `prep/names.py` all write.  Any other spelling reformats the
    whole file and buries the one changed line in the diff.
    """
    io.open(path, "w", encoding="utf-8", newline="").write(
        json.dumps(man, indent=2, sort_keys=True) + "\n")
    return path


def digest_of(man):
    """Map every network name to its recorded byte facts.

    The amend must not move any of these.  Returning a plain dict, not a
    hash, so that a failure names the network and the key that moved.
    """
    out = {}
    for name, entry in sorted(man.get("networks", {}).items()):
        out[name] = dict((k, entry.get(k)) for k in BYTE_KEYS)
    return out


def get_field(man, network, field):
    """Read `networks.<network>.<field>`, field being a dotted path.

    Returns None when any segment is absent, which the callers
    distinguish from a present-but-empty value by checking the
    containers themselves.
    """
    node = man.get("networks", {}).get(network)
    if node is None:
        return None
    for seg in field.split("."):
        if not isinstance(node, dict) or seg not in node:
            return None
        node = node[seg]
    return node


def set_field(man, network, field, value):
    """Set `networks.<network>.<field>` and return the previous value.

    Every segment but the last must already exist.  Creating them would
    let a typo in `--field` write a new key that reads like a real one,
    which is the failure this tool is meant to prevent, not cause.
    """
    nets = man.get("networks")
    if not isinstance(nets, dict) or network not in nets:
        raise SystemExit("no such network in the manifest: %s" % network)
    node = nets[network]
    segs = field.split(".")
    for seg in segs[:-1]:
        if not isinstance(node, dict) or seg not in node:
            raise SystemExit("no such field: networks.%s.%s"
                             % (network, field))
        node = node[seg]
    if not isinstance(node, dict) or segs[-1] not in node:
        raise SystemExit("no such field: networks.%s.%s" % (network, field))
    before = node[segs[-1]]
    node[segs[-1]] = value
    return before


#: Boolean marks `--mark` may CREATE on a network entry (D-551).  The rule
#: `set_field()` keeps, that no absent key is ever created, exists so that a
#: typo cannot write a key that reads like a real one; a whitelist of exactly
#: the keys a decision names keeps that property for marks.
MARKS = ("distributed",)


def set_mark(man, network, key):
    """Set the boolean mark `networks.<network>.<key>` to True.

    Returns the previous value, None when the key was absent.  `key` must
    be in MARKS and the network must exist; anything else exits without
    writing.  Only True is ever written: a network leaves the distributed
    set by a decision, not by this tool.
    """
    if key not in MARKS:
        raise SystemExit("not a mark netman may set: %s (only %s)"
                         % (key, ", ".join(MARKS)))
    nets = man.get("networks")
    if not isinstance(nets, dict) or network not in nets:
        raise SystemExit("no such network in the manifest: %s" % network)
    before = nets[network].get(key)
    nets[network][key] = True
    return before


def read_text(path):
    """Read a replacement value as one line, newlines folded to spaces.

    The manifest holds these notes as single JSON strings.  Taking the
    text from a file rather than a command line keeps a 900-character
    note out of the shell, where quoting would mangle it.
    """
    raw = io.open(path, encoding="utf-8").read()
    return " ".join(raw.split())


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Amend one field of data/networks/MANIFEST.json "
                    "without re-deriving a network (D-450, D-453).")
    ap.add_argument("--network", default=None,
                    help="network key under `networks`, e.g. srext")
    ap.add_argument("--field", default=None,
                    help="dotted path within the entry, "
                         "e.g. acceptance.not_proven")
    ap.add_argument("--from-file", default=None, metavar="TXT",
                    help="file holding the replacement text")
    ap.add_argument("--check-file", default=None, metavar="TXT",
                    help="assert the field already equals this file's "
                         "text; write nothing")
    ap.add_argument("--show", default=None, metavar="NETWORK",
                    help="print a network's acceptance block and exit")
    ap.add_argument("--mark", default=None, metavar="KEY",
                    help="set the boolean mark KEY to true on --network; "
                         "only %s (D-551)" % ", ".join(MARKS))
    a = ap.parse_args(argv)

    man = load()

    if a.mark:
        if not a.network or a.field or a.from_file or a.check_file:
            sys.stderr.write("--mark takes --network and nothing else\n")
            return 2
        before_digests = digest_of(man)
        prev = set_mark(man, a.network, a.mark)
        if digest_of(man) != before_digests:
            sys.stderr.write("REFUSING: the mark moved a network digest\n")
            return 1
        save(man)
        print("netman: networks.%s.%s = true (was %s); network digests "
              "unchanged" % (a.network, a.mark,
                             "absent" if prev is None else prev))
        return 0

    if a.show:
        entry = man.get("networks", {}).get(a.show)
        if entry is None:
            sys.stderr.write("no such network: %s\n" % a.show)
            return 2
        print(json.dumps(entry.get("acceptance", {}),
                         indent=2, sort_keys=True))
        return 0

    if not a.network or not a.field:
        sys.stderr.write("--network and --field are both required\n")
        return 2
    if bool(a.from_file) == bool(a.check_file):
        sys.stderr.write("give exactly one of --from-file, --check-file\n")
        return 2

    if a.check_file:
        want = read_text(a.check_file)
        have = get_field(man, a.network, a.field)
        if have == want:
            print("netman: networks.%s.%s is as expected (%d chars)"
                  % (a.network, a.field, len(want)))
            return 0
        print("netman: networks.%s.%s DIFFERS" % (a.network, a.field))
        print("  expected: %s" % want)
        print("  found:    %s" % have)
        return 1

    before_digests = digest_of(man)
    value = read_text(a.from_file)
    before = set_field(man, a.network, a.field, value)
    after_digests = digest_of(man)
    # Belt and braces.  set_field() cannot reach a byte key, but this is
    # the invariant the whole design rests on, so it is asserted where
    # the write happens and not only in the test.
    if before_digests != after_digests:
        sys.stderr.write("REFUSING: the amend moved a network digest\n")
        return 1
    save(man)
    print("netman: networks.%s.%s amended in %s"
          % (a.network, a.field, MANIFEST.replace("\\", "/")))
    print("  was (%d chars): %s" % (len(before or ""), before))
    print("  now (%d chars): %s" % (len(value), value))
    print("  network digests unchanged: %s"
          % ", ".join("%s crc=%s" % (n, d["crc32"])
                      for n, d in sorted(after_digests.items())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
