# -*- coding: utf-8 -*-
"""Run manifest for the preparation pipeline (FR-PRP-01, FR-PRP-05, FR-PRP-07).

FR-PRP-01 requires the dataset version, source and retrieval date to be
recorded. FR-PRP-07 requires CRC-32 and SHA-256 digests of every artifact.
FR-PRP-05 requires every chosen value -- W_syn, N, the selected neuron list --
to be recorded here too, as those stages are reached.

The manifest is the answer to "which data produced this result?", asked months
later about a fingerprint someone recorded. It is therefore written as JSON
(machine-readable, diffable) rather than prose, and every number in it is
measured from the file on disk rather than copied from a web page.

Digest choice follows VL-08: CRC-32 is what the engine checks at run time on
platforms with no crypto library, and SHA-256 is kept in the x86 manifest only,
where it can actually be computed.

Run:  python prep/manifest.py
"""
import datetime
import hashlib
import io
import json
import os
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import sources  # noqa: E402

DATA_DIR = os.path.join(ROOT, "data", "malecns")
MANIFEST = os.path.join(DATA_DIR, "MANIFEST.json")


def digests(path, chunk=1 << 20):
    """Return (bytes, crc32, sha256) computed in one pass over the file."""
    size = 0
    crc = 0
    sha = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            buf = fh.read(chunk)
            if not buf:
                break
            size += len(buf)
            crc = zlib.crc32(buf, crc)
            sha.update(buf)
    return size, crc & 0xFFFFFFFF, sha.hexdigest()


def build(verbose=True):
    """Measure every retrieved file and return the manifest as a dict."""
    entries = {}
    missing = []
    for key, (name, expected, supplies) in sorted(sources.FILES.items()):
        path = os.path.join(DATA_DIR, name)
        if not os.path.exists(path):
            missing.append(name)
            continue
        size, crc, sha = digests(path)
        entries[key] = {
            "file": name,
            "url": sources.url(key),
            "supplies": supplies,
            "bytes": size,
            "bytes_expected": expected,
            # A size mismatch means a truncated or resumed transfer, which is
            # exactly the failure a digest is meant to catch before it becomes
            # a wrong scientific result.
            "size_matches_expected": size == expected,
            "crc32": "%08X" % crc,
            "sha256": sha,
        }
        if verbose:
            print("  %-20s %12d bytes  crc=%08X  sha256=%s..."
                  % (key, size, crc, sha[:16]))
    if missing and verbose:
        for m in missing:
            print("  MISSING %s" % m)
    return {
        "dataset": sources.DATASET,
        "dataset_uuid": sources.DATASET_UUID,
        "licence": sources.DATASET_LICENCE,
        "cite": sources.DATASET_CITE,
        "source_base": sources.BASE,
        "retrieved_utc": datetime.datetime.now(
            datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "decisions": ["D-49", "D-50", "D-51"],
        "files": entries,
        "not_retrieved": sources.NOT_RETRIEVED,
        "missing": missing,
    }


def main():
    if not os.path.isdir(DATA_DIR):
        sys.stderr.write("no data directory: %s\n" % DATA_DIR)
        return 2
    print("Building run manifest for %s (uuid %s)"
          % (sources.DATASET, sources.DATASET_UUID))
    man = build()
    io.open(MANIFEST, "w", encoding="utf-8", newline="\n").write(
        json.dumps(man, indent=2, sort_keys=True) + "\n")
    print("wrote %s" % MANIFEST.replace("\\", "/"))
    bad = [k for k, v in man["files"].items() if not v["size_matches_expected"]]
    if bad:
        print("SIZE MISMATCH in: %s" % ", ".join(bad))
        return 1
    if man["missing"]:
        print("incomplete: %d file(s) not yet retrieved" % len(man["missing"]))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
