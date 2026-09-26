# -*- coding: utf-8 -*-
"""TE-09: ONFLYENG's verify-only mode, and the NFR-OBS-01 run manifest.

IR-TRN-03 requires ONFLYENG to offer a verify-only mode, PARM='VERIFY', that
runs the FR-LOD-02 checks and reports the result *without simulating*.  Three
separate claims live in that sentence, and this script checks each one:

  it runs the FR-LOD-02 checks
      Every corruption tests/run_dec.py builds for TE-01..TE-06 is replayed
      through the program, and the message and return code must be the ones
      Appendix E and IR-JCL-04 specify.  The cases are imported rather than
      rewritten, so a change to the decoder's test data reaches this test too.

  it reports the result
      A clean network must produce ONF003I and return code 0; every corrupt
      one an ONF1xxE and return code 12.  A dataset that cannot be read at all
      produces ONF108E (D-85), which is neither of those and needed its own
      catalog entry.

  without simulating
      Proved structurally rather than by timing: the linked program must
      contain no kernel entry point at all.  A program that does not contain
      onfrun cannot have called it, which is a stronger statement than any
      measurement of how long a run took.  Skipped, with a message, where nm
      is unavailable.

NFR-OBS-01 is checked separately: every field the requirement names must
appear in the ONF002I block.  D-81's ONF905S path is checked too, because a
run that simulates nothing must say so rather than report success.

TE-08 goes through the program too (D-567).  FR-LOD-04's configured limit is
the build constant ONF_MEMLIM, so each TE-08 case of tests/run_dec.py runs on
an ONFLYENG built with -DONF_MEMLIM set to that case's limit, passed here as
`--limit N=EXE`; a case with no such build FAILS rather than skipping.  The
shipped build is checked against D-568 as well: on every platform this runs
on the limit is 0, so a network whose header demands more than MVS's 8M
must still verify.  That is the one TE-08 fact about the shipped binary an
x86 or s390x host can observe; the MVS half is tools/mvsrun.py --te08.

Run:  python tests/run_eng.py <onflyeng> <onflyeng-noreq>
                              [--limit N=<onflyeng built at ONF_MEMLIM=N>]...
Exit status 0 when every case behaves as specified, 1 otherwise.
"""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
for sub in ("layout", "generated", "oracle", "tools"):
    sys.path.insert(0, os.path.join(ROOT, sub))

import onfres                         # noqa: E402
import run_dec                        # noqa: E402

# IR-JCL-04 return codes.
RC_OK, RC_INTEG, RC_ENV = 0, 12, 16

# NFR-OBS-01 names each of these; the manifest is incomplete without any one.
MANIFEST_FIELDS = (
    "ENGINE VERSION",
    "FLOAT BACKEND",
    "COMPILER",
    "NET FORMAT",
    "HEADER CRC",
    "PAYLOAD CRC",
    "DT",
    "N ",
    "E ",
)


def run(exe, args):
    """Run ONFLYENG and return (return code, [output lines])."""
    proc = subprocess.Popen([exe] + args, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT)
    out = proc.communicate()[0].decode("ascii", "replace")
    return proc.returncode, out.splitlines()


def message(lines):
    """The last ONFnnns message the program printed, by identifier."""
    found = None
    for line in lines:
        if line.startswith("ONF") and len(line) > 7:
            token = line.split()[0]
            if token.startswith("ONF002I"):
                continue          # the manifest is many lines, not a verdict
            found = token
    return found


def manifest(lines):
    """The ONF002I block, as the text after the message identifier."""
    return [line[len("ONF002I"):].strip()
            for line in lines if line.startswith("ONF002I")]


def sample_request():
    """One valid 412-byte SUGR request, for the D-228 observational check.

    Built through tools/mkreq.py so that it is the same shape ONFLYDRV will
    produce, not a hand-rolled buffer that could be malformed in a way that
    made ONFLYENG reject it before ever reaching the question under test.
    """
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import mkreq
    return mkreq.pack("SUGR", 120, 100, 1)


#: Every external name through which the kernel can be entered.  D-366 split
#: onfrun into onfinit and onfcont, so looking for onfrun alone would no
#: longer mean what this check says it means: a build could hold the whole
#: simulation and still answer "absent" because the one composition function
#: happened not to be linked.  The list is the header's, and if the header
#: grows another entry point this list has to grow with it.
KERNEL_ENTRIES = ("onfrun", "onfinit", "onfcont")


def kernel_absent(exe):
    """True when the program contains no kernel entry point.

    Returns None when nm is not available, so the check reports itself as
    skipped rather than silently passing.
    """
    try:
        out = subprocess.check_output(["nm", exe], stderr=subprocess.STDOUT)
    except (OSError, subprocess.CalledProcessError):
        return None
    text = out.decode("ascii", "replace")
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        name = parts[-1].lstrip("_")
        if name in KERNEL_ENTRIES:
            return False
    return True


def parse_args(argv):
    """(exe, vexe, {limit: exe}) from the command line, or None if malformed.

    Positional: the shipped ONFLYENG and, optionally, the -DONF_NOREQ
    variant.  `--limit N=EXE`, repeatable: an ONFLYENG built with
    -DONF_MEMLIM=N, for the TE-08 case whose limit is N (D-567).
    """
    pos, limexe = [], {}
    i = 0
    while i < len(argv):
        if argv[i] == "--limit":
            if i + 1 >= len(argv) or "=" not in argv[i + 1]:
                return None
            n, path = argv[i + 1].split("=", 1)
            if not n.isdigit():
                return None
            limexe[int(n)] = os.path.abspath(path)
            i += 2
        else:
            pos.append(os.path.abspath(argv[i]))
            i += 1
    if len(pos) not in (1, 2):
        return None
    return pos[0], (pos[1] if len(pos) == 2 else None), limexe


def main():
    args = parse_args(sys.argv[1:])
    if args is None:
        sys.stderr.write("usage: run_eng.py <onflyeng> [<onflyeng-noreq>] "
                         "[--limit N=<onflyeng>]...\n")
        return 2
    exe, vexe, limexe = args
    # D-228: the -DONF_NOREQ variant, built with the request loop compiled
    # out.  Optional so that an invocation written before D-221 still runs,
    # but then the structural half reports itself as skipped rather than
    # passing on a binary it no longer holds for.
    for path in [exe] + ([vexe] if vexe else []) + list(limexe.values()):
        if not os.path.exists(path):
            sys.stderr.write("run_eng: not found: %s\n" % path)
            return 2

    good = run_dec.sample_network()
    tmp = tempfile.mkdtemp(prefix="onfly_eng_")
    ok = bad = 0
    lines = []

    def check(label, cond, detail=""):
        if cond:
            lines.append("  ok   %-44s %s" % (label, detail))
            return 1, 0
        lines.append("  FAIL %-44s %s" % (label, detail))
        return 0, 1

    try:
        # --- FR-LOD-02 and FR-LOD-04 checks, replayed through the program --
        #
        # A TE-08 case carries its own memory limit.  FR-LOD-04's limit is
        # the build constant ONF_MEMLIM (D-567), so the case runs on the
        # ONFLYENG built at that limit, not on the shipped one; without that
        # build the case fails, because a replay that quietly dropped it is
        # how this check went unrun from D-78 to D-564.
        for name, data, limit, want in run_dec.cases(good):
            use = exe
            label = name
            if limit:
                use = limexe.get(limit)
                label = "%s (ONF_MEMLIM=%d)" % (name, limit)
                if use is None:
                    a, b = check(label, False, "no ONFLYENG built with "
                                 "-DONF_MEMLIM=%d was given (D-567)" % limit)
                    ok += a
                    bad += b
                    continue
            path = os.path.join(tmp, name.split()[0] + "_%d.net" % limit)
            with open(path, "wb") as fh:
                fh.write(data)

            rc, out = run(use, ["VERIFY", path])
            msg = message(out)
            if want == 0:
                wantmsg, wantrc = "ONF003I", RC_OK
            else:
                wantmsg, wantrc = "ONF%03dE" % want, RC_INTEG
            a, b = check(label, msg == wantmsg and rc == wantrc,
                         "msg=%s rc=%s (want %s rc=%d)"
                         % (msg, rc, wantmsg, wantrc))
            ok += a
            bad += b

        # D-568: the shipped build's own limit.  Every host this script runs
        # on (x86-64 Windows, Linux x86-64, Linux s390x) has ONF_MEMLIM 0, so
        # a network demanding just over MVS's 8M must still verify here.  An
        # ONF105E would mean the MVS limit had leaked onto this platform,
        # which would refuse D-216's full network (330,443,656 B).
        over = run_dec.overlimit_network(good)
        path = os.path.join(tmp, "over.net")
        with open(path, "wb") as fh:
            fh.write(over)
        rc, out = run(exe, ["VERIFY", path])
        a, b = check("D-568 no limit off MVS (need %d)"
                     % run_dec.need_bytes(over),
                     message(out) == "ONF003I" and rc == RC_OK,
                     "msg=%s rc=%s (want ONF003I rc=0)" % (message(out), rc))
        ok += a
        bad += b

        # --- the manifest, NFR-OBS-01 --------------------------------------
        path = os.path.join(tmp, "good.net")
        with open(path, "wb") as fh:
            fh.write(good)
        rc, out = run(exe, ["VERIFY", path])
        man = manifest(out)
        body = "\n".join(man)
        for field in MANIFEST_FIELDS:
            a, b = check("NFR-OBS-01 manifest has %s" % field.strip(),
                         any(entry.startswith(field) for entry in man),
                         "")
            ok += a
            bad += b
        a, b = check("NFR-OBS-01 manifest names the backend",
                     "SOFT" in body or "NATIVE" in body, "")
        ok += a
        bad += b

        # --- without simulating, proved two ways (D-228) --------------------
        #
        # Structurally, on the -DONF_NOREQ variant.  D-221 links the kernel
        # into the shipped engine, so this argument no longer holds for it;
        # the variant is what keeps the argument available at all.
        if vexe is None:
            text, fatal = onfres.skipline(
                "eng/noreq-variant", "IR-TRN-03 contains no kernel entry "
                "point: no -DONF_NOREQ variant given")
            lines.append("  " + text)
            bad += 1 if fatal else 0
        else:
            absent = kernel_absent(vexe)
            if absent is None:
                text, fatal = onfres.skipline(
                    "eng/nm", "IR-TRN-03 contains no kernel entry point: "
                    "nm unavailable")
                lines.append("  " + text)
                bad += 1 if fatal else 0
            else:
                a, b = check("IR-TRN-03 variant has no kernel entry point",
                             absent, "%s: %s"
                             % ("/".join(KERNEL_ENTRIES),
                                "absent" if absent else "PRESENT"))
                ok += a
                bad += b
            # The variant is the one build that can still emit ONF905S
            # (D-227), so the message is tested rather than only documented.
            rc, out = run(vexe, ["", path])
            a, b = check("D-227 variant emits ONF905S without VERIFY",
                         message(out) == "ONF905S" and rc == RC_ENV,
                         "msg=%s rc=%s" % (message(out), rc))
            ok += a
            bad += b

        # Observationally, on the SHIPPED engine.  A valid request dataset is
        # supplied on purpose: if verify-only simulated, it would have written
        # response records, so the absence of the file is the evidence.  This
        # is not a timing measurement, which is what the structural argument
        # was originally preferred over.
        reqp = os.path.join(tmp, "onfreq.bin")
        rspp = os.path.join(tmp, "onfrsp.bin")
        with open(reqp, "wb") as fh:
            fh.write(sample_request())
        rc, out = run(exe, ["VERIFY", path, reqp, rspp])
        a, b = check("IR-TRN-03 VERIFY writes no ONFRSP",
                     not os.path.exists(rspp),
                     "ONFRSP %s" % ("absent"
                                    if not os.path.exists(rspp)
                                    else "WRITTEN"))
        ok += a
        bad += b
        a, b = check("IR-TRN-03 VERIFY runs no request",
                     not any(l.startswith("ONF301I")
                             or l.startswith("ONF302I") for l in out),
                     "ONF301I/ONF302I present" if any(
                         l.startswith("ONF301I") or l.startswith("ONF302I")
                         for l in out) else "")
        ok += a
        bad += b
        a, b = check("IR-TRN-03 VERIFY still reports ONF003I rc 0",
                     message(out) == "ONF003I" and rc == RC_OK,
                     "msg=%s rc=%s" % (message(out), rc))
        ok += a
        bad += b

        # --- the PARM itself ------------------------------------------------
        for parm, wantmsg, wantrc, why in (
                ("VERIFY", "ONF003I", RC_OK, "verify-only, IR-TRN-03"),
                ("verify", "ONF003I", RC_OK, "PARM case is not significant"),
                ("", "ONF906S", RC_ENV,
                 "SIMULATE with no ONFREQ supplied, D-226"),
                ("XYZZY", "ONF906S", RC_ENV,
                 "an unknown PARM is not VERIFY, so SIMULATE")):
            rc, out = run(exe, [parm, path])
            msg = message(out)
            a, b = check("PARM=%-7r %s" % (parm, why),
                         msg == wantmsg and rc == wantrc,
                         "msg=%s rc=%s (want %s rc=%d)"
                         % (msg, rc, wantmsg, wantrc))
            ok += a
            bad += b

        # --- D-85: a dataset that cannot be read at all ---------------------
        missing = os.path.join(tmp, "no_such_file.net")
        rc, out = run(exe, ["VERIFY", missing])
        a, b = check("ONF108E absent dataset",
                     message(out) == "ONF108E" and rc == RC_INTEG,
                     "msg=%s rc=%s" % (message(out), rc))
        ok += a
        bad += b

        empty = os.path.join(tmp, "empty.net")
        with open(empty, "wb") as fh:
            fh.write(b"")
        rc, out = run(exe, ["VERIFY", empty])
        a, b = check("ONF108E empty dataset",
                     message(out) == "ONF108E" and rc == RC_INTEG,
                     "msg=%s rc=%s" % (message(out), rc))
        ok += a
        bad += b
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    for line in lines:
        print(line)
    print("run_eng: %d passed, %d failed" % (ok, bad))
    if bad:
        print("run_eng: FAILED")
        return 1
    print("run_eng: ok   TE-09 verify-only mode and the NFR-OBS-01 manifest")
    return 0


if __name__ == "__main__":
    sys.exit(main())
