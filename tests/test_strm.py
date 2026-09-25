# -*- coding: utf-8 -*-
"""TU-11: the chunk stream (IR-STM-01..04, D-380).

WHAT THIS PROVES, AND WHY THE OBVIOUS TEST IS NOT ENOUGH
--------------------------------------------------------
`make golden` already re-checks the nineteen Section 8.4 fingerprints, and
`tools/cmpchk.py` already sweeps the chunk size.  Between them they prove the
RESPONSE does not change when a run is chunked.  Neither of them says
anything about the stream itself: a driver that emitted a plausible animation
beside the real run -- right shape, wrong numbers -- would pass both.

So this file checks three different things, and the second is the one that
matters:

  Inertness (IR-STM-04)
      The ONFRSP dataset is byte-identical with and without `STREAM=`.  A
      stream that perturbed an answer would not be a bug in a feature, it
      would be the determinism claim of Phase E failing.

  Agreement (IR-STM-04)
      The `ONFSC` counts for a readout neuron sum to that neuron's
      ONF-OUT-SPIKES in the response, and the chunk in which they first rise
      brackets its ONF-OUT-LAT-US.  This is what ties the drawing to the
      computation: it can only pass if the stream is the same run.

  Form (IR-STM-02, IR-STM-03)
      Line tags in the required order, every field numeric, membrane values
      exactly sixteen hexadecimal digits, and `ONFSC` genuinely sparse -- no
      zero deltas, and the declared count equal to the pairs that follow.

Plus the two failure paths D-381 added messages for, ONF908S and ONF907S, and
a second chunk size so that the stream's own totals are shown independent of
K rather than only the fingerprint being so.

WHAT IT DOES NOT PROVE
----------------------
Everything here is the host it runs on.  No claim is made for Linux s390x,
MVS 3.8j or z/OS: no MVS engine has ever written a stream, which is Stage 5
of the Phase G plan and out of scope under D-374.

Run:  python tests/test_strm.py <onflyeng> [<onflyeng> ...]
Exit status 0 when every case behaves as specified, 1 otherwise.
"""
import os
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for sub in ("generated", "tools", "tests"):
    sys.path.insert(0, os.path.join(ROOT, sub))

import onfcom_py as L                              # noqa: E402
import mkreq                                       # noqa: E402
import run_gld                                     # noqa: E402
import goldfp                                      # noqa: E402

sys.path.insert(0, os.path.join(ROOT, "layout"))
sys.path.insert(0, os.path.join(ROOT, "oracle"))
import netread                                     # noqa: E402
import netwrite                                    # noqa: E402
from onfly_oracle import kernel as okernel         # noqa: E402

#: D-376's demo chunk size, and a second that divides neither the step count
#: nor itself into it evenly, so the last chunk is short.
K_DEMO = 50
K_ODD = 7

# D-406.  The same number engine/src/onflyeng.c defines as ONF_STMCOL,
# restated here rather than parsed out of the C, because a test that
# read its expectation from the thing under test would agree with any
# value the emitter happened to use.
ONF_STMCOL = 80

RC_ENV = 16

#: The srext half of Section 8.4, as SRS Section 8.3 rows 6 and 7 record it.
#: Moved to tools/goldfp.py when Stage 5 gave the same table a second and a
#: third consumer; the reasoning for writing the values out rather than
#: recomputing them travels with them and is restated there.
GOLD_SREXT = goldfp.SREXT


class StreamError(Exception):
    """A stream that does not parse.  Raised rather than returned so that a
    malformed stream cannot be silently treated as an empty one."""


def check(label, ok, detail=""):
    print("  %-4s %-52s %s" % ("ok" if ok else "FAIL", label, detail))
    return (1, 0) if ok else (0, 1)


def run_engine(exe, netpath, reqpath, rsppath, parm="", stmpath=None):
    """Invoke ONFLYENG and return (return code, [output lines]).

    stmpath is passed positionally whether or not a stream was asked for, so
    that the two runs of the inertness check differ in the PARM alone."""
    # Absolute, as run_req.py does: a relative executable path with an empty
    # first argument is not found by CreateProcess on this host.
    args = [os.path.abspath(exe), parm, netpath, reqpath, rsppath]
    if stmpath is not None:
        args.append(stmpath)
    proc = subprocess.Popen(args, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT)
    out = proc.communicate()[0].decode("ascii", "replace").splitlines()
    return proc.returncode, out


def decode_records(raw):
    """Every response record, as dictionaries of named fields."""
    recs = []
    for base in range(0, len(raw), L.RECORD_LEN):
        rec = raw[base:base + L.RECORD_LEN]
        head = dict(zip(L.HEAD_FIELDS,
                        struct.unpack(L.HEAD_FMT, rec[:L.HEAD_LEN])))
        outs = []
        for j in range(head["outcount"]):
            off = L.HEAD_LEN + j * L.OUT_LEN
            outs.append(dict(zip(L.OUT_FIELDS,
                                 struct.unpack(L.OUT_FMT,
                                               rec[off:off + L.OUT_LEN]))))
        head["outs"] = outs
        head["fphex"] = "".join("%02X" % b for b in head["fprint"])
        recs.append(head)
    return recs


def parse_stream(path):
    """Parse ONFSTM into one dictionary per streamed request.

    The parser is strict on purpose.  A lenient parser would let a defect in
    the emitter through as a shrug, and the emitter is what is under test."""
    reqs = []
    cur = None
    prevstep = 0
    with open(path, "r") as fh:
        for lineno, line in enumerate(fh, 1):
            f = line.split()
            if not f:
                raise StreamError("line %d is blank" % lineno)
            tag = f[0]
            if tag == "ONFSH":
                if cur is not None:
                    raise StreamError("ONFSH inside a request at %d" % lineno)
                if len(f) != 10:
                    raise StreamError("ONFSH has %d fields at %d"
                                      % (len(f), lineno))
                cur = {"ver": int(f[1]), "n": int(f[2]), "nr": int(f[3]),
                       "dtus": int(f[4]), "k": int(f[5]), "steps": int(f[6]),
                       "seed": int(f[7]), "rate": int(f[8]), "paycrc": f[9],
                       "ro": None, "chunks": [], "total": {}, "first": {},
                       "usparse": True}
                prevstep = 0
            elif tag == "ONFSR":
                # D-413: repeated until nr indices have been written, so a
                # second ONFSR is a continuation and not a stray.  "Before
                # any chunk" is what still makes a stray one detectable.
                if cur is None or cur["chunks"]:
                    raise StreamError("stray ONFSR at %d" % lineno)
                if cur["ro"] is None:
                    cur["ro"] = []
                if len(cur["ro"]) >= cur["nr"]:
                    raise StreamError("ONFSR past nr=%d at %d"
                                      % (cur["nr"], lineno))
                cur["ro"].extend(int(x) for x in f[1:])
            elif tag == "ONFSC":
                if cur is None or cur["ro"] is None:
                    raise StreamError("stray ONFSC at %d" % lineno)
                chunk, step, nfired = int(f[1]), int(f[2]), int(f[3])
                pairs = f[4:]
                if len(pairs) % 2 != 0:
                    raise StreamError("ONFSC pairs are odd at %d" % lineno)
                seen = []
                for a in range(0, len(pairs), 2):
                    idx, delta = int(pairs[a]), int(pairs[a + 1])
                    if delta == 0:
                        cur["usparse"] = False
                    seen.append((idx, delta))
                    cur["total"][idx] = cur["total"].get(idx, 0) + delta
                    if idx not in cur["first"]:
                        cur["first"][idx] = (prevstep, step)
                cur["chunks"].append({"chunk": chunk, "step": step,
                                      "nfired": nfired, "pairs": seen,
                                      "lo": prevstep})
                prevstep = step
            elif tag == "ONFSD":
                # D-406.  A continuation of the ONFSC above it, carrying the
                # same chunk and step and no count of its own -- the count is
                # the chunk's and lives on the ONFSC.  Checked here rather
                # than assumed: an ONFSD whose chunk or step disagreed with
                # the line it continues would be a splicing defect, and the
                # whole reason for the tag is that such a defect is visible.
                if cur is None or not cur["chunks"]:
                    raise StreamError("stray ONFSD at %d" % lineno)
                c = cur["chunks"][-1]
                if "u" in c:
                    raise StreamError("ONFSD after the chunk's ONFSU at %d"
                                      % lineno)
                if int(f[1]) != c["chunk"] or int(f[2]) != c["step"]:
                    raise StreamError("ONFSD %s/%s continues chunk %d/%d "
                                      "at %d" % (f[1], f[2], c["chunk"],
                                                 c["step"], lineno))
                pairs = f[3:]
                if not pairs:
                    raise StreamError("empty ONFSD at %d" % lineno)
                if len(pairs) % 2 != 0:
                    raise StreamError("ONFSD pairs are odd at %d" % lineno)
                for a in range(0, len(pairs), 2):
                    idx, delta = int(pairs[a]), int(pairs[a + 1])
                    if delta == 0:
                        cur["usparse"] = False
                    c["pairs"].append((idx, delta))
                    cur["total"][idx] = cur["total"].get(idx, 0) + delta
                    if idx not in cur["first"]:
                        cur["first"][idx] = (c["lo"], c["step"])
            elif tag == "ONFSU":
                # D-412: repeated, with the same chunk and step, until nr
                # columns have been written.  Accumulating rather than
                # assigning is the whole difference; the chunk and step are
                # checked for the reason the ONFSD ones are, so that a
                # continuation spliced from the wrong chunk is visible.
                if cur is None or not cur["chunks"]:
                    raise StreamError("stray ONFSU at %d" % lineno)
                c = cur["chunks"][-1]
                if "u" not in c:
                    c["u"] = []
                    c["ustep"] = int(f[2])
                elif len(c["u"]) >= cur["nr"]:
                    raise StreamError("ONFSU past nr=%d at %d"
                                      % (cur["nr"], lineno))
                elif int(f[1]) != c["chunk"] or int(f[2]) != c["ustep"]:
                    raise StreamError("ONFSU %s/%s continues chunk %d/%d "
                                      "at %d" % (f[1], f[2], c["chunk"],
                                                 c["ustep"], lineno))
                c["u"].extend(f[3:])
            elif tag == "ONFSE":
                if cur is None:
                    raise StreamError("stray ONFSE at %d" % lineno)
                cur["nchunk"] = int(f[1])
                cur["rc"] = int(f[2])
                cur["fp"] = f[3]
                reqs.append(cur)
                cur = None
            else:
                raise StreamError("unknown tag %r at %d" % (tag, lineno))
    if cur is not None:
        raise StreamError("stream ends inside a request")
    return reqs


def check_width(path, tag):
    """D-406: no line exceeds ONF_STMCOL columns.

    This is the clause the MVS half turns on, and it is checked on x86
    because the bound is arithmetic and arithmetic does not need the
    emulated MVS lab to be wrong.  What the lab adds is the CONSEQUENCE:
    measured on TK5 on 2026-09-17, a line of 81 columns written to the
    10D punch arrives as 80 bytes -- no split, no message, COND CODE
    0000, and the tail simply gone.  A stream that failed this check
    would reach the viewer looking complete and be missing spikes.

    The longest line is reported even when the check passes, because a
    stream creeping toward the bound is worth seeing before it crosses
    it.
    """
    worst = 0
    where = 0
    with open(path, "r") as fh:
        for lineno, line in enumerate(fh, 1):
            n = len(line.rstrip("\n"))
            if n > worst:
                worst = n
                where = lineno
    return check("D-406 %s no line exceeds %d columns" % (tag, ONF_STMCOL),
                 worst <= ONF_STMCOL,
                 "longest is %d columns at line %d" % (worst, where))


def wide_network(nr=30):
    """A network with enough readout neurons to make ONFSR and ONFSU wrap.

    WHY A NETWORK HAD TO BE BUILT FOR THIS.  D-412 and D-413 bound the
    membrane line and the readout-name line, and neither can wrap on any
    network ONFLY ships: `nr` is 2 on all four, which puts ONFSU at 49
    columns and ONFSR at 10.  So the two branches the owner asked for
    would have shipped UNEXERCISED, and a wrap that is never taken is a
    wrap nobody knows is right.

    nr = 30 crosses both bounds and neither marginally: ONFSR becomes
    5 + 30x3 = 95 columns unwrapped, and ONFSU 5 + 4 + 5 + 30x17 = 524.

    The first version of this used nr = 20 and asserted ONFSR would wrap
    at 85 columns.  It did not: the arithmetic had assumed three-digit
    indices, and at n = 64 they are two digits, so the line came to 65
    and the check failed.  The check earned its place on its first run --
    which is the argument for asserting that a branch was TAKEN rather
    than only that the output looks right.

    It is a small synthetic network on tests/run_dec.py's pattern, not a
    MaleCNS one.  Nothing scientific is claimed from it -- it exists to
    make two `if` statements in the emitter execute.
    """
    n = 64
    rowptr, target, weight = [0], [], []
    for i in range(n):
        row = sorted(set((i + 1 + k * 7) % n for k in range(5)))
        target.extend(row)
        for _ in row:
            weight.append(0.275 * (len(weight) % 5 + 1))
        rowptr.append(len(target))
    readout = list(range(n - nr, n))
    return netwrite.build(
        n=n, rowptr=rowptr, target=target, weight=weight,
        stim=[0, 1, 2, 3], readout=readout,
        dt_us=100, delay=18, refract=22, max_ms=5000,
        u_th=7.0, u_reset=0.0,
        p11=0.9950124791926823, p12=0.004937935295309022,
        p22=0.9801986733067553, g_eps=1e-300, w_syn=0.275, v_rest=-52.0)


def check_wide(exe, tmp):
    """D-412 and D-413: the ONFSU and ONFSR continuations, exercised."""
    ok = bad = 0
    nr = 30
    netpath = os.path.join(tmp, "wide.bin")
    with open(netpath, "wb") as fh:
        fh.write(wide_network(nr))
    reqpath = os.path.join(tmp, "wide.req")
    with open(reqpath, "wb") as fh:
        fh.write(mkreq.pack("SUGR", 200, 20, 1))
    rsppath = os.path.join(tmp, "wide.rsp")
    stm = os.path.join(tmp, "wide.stm")
    rc, out = run_engine(exe, netpath, reqpath, rsppath, "STREAM=7", stm)

    a, b = check("D-412/D-413 the wide-readout run completes", rc == 0,
                 "rc=%d %s" % (rc, out[-1] if out else ""))
    ok += a
    bad += b
    if rc != 0:
        return ok, bad

    a, b = check_width(stm, "nr=%d" % nr)
    ok += a
    bad += b

    # The continuations must actually have been TAKEN.  Without this the
    # test would pass just as well against an emitter that never wrapped,
    # which is the failure mode it exists to rule out.
    tags = [l.split()[0] for l in open(stm) if l.split()]
    nsr = tags.count("ONFSR")
    nsu = tags.count("ONFSU")
    nsc = tags.count("ONFSC")
    a, b = check("D-413 ONFSR wrapped", nsr > 1, "%d ONFSR lines" % nsr)
    ok += a
    bad += b
    a, b = check("D-412 ONFSU wrapped", nsu > nsc,
                 "%d ONFSU lines for %d chunks" % (nsu, nsc))
    ok += a
    bad += b

    try:
        streamed = parse_stream(stm)
    except StreamError as exc:
        a, b = check("D-412/D-413 the wrapped stream parses", False,
                     str(exc))
        return ok + a, bad + b
    s = streamed[0]
    a, b = check("D-413 ONFSR reassembles to nr indices",
                 s["ro"] == list(range(64 - nr, 64)),
                 "%d indices" % len(s["ro"]))
    ok += a
    bad += b
    whole = all(len(c["u"]) == nr for c in s["chunks"])
    a, b = check("D-412 every ONFSU reassembles to nr columns", whole,
                 "%d chunks, columns %s"
                 % (len(s["chunks"]),
                    sorted(set(len(c["u"]) for c in s["chunks"]))))
    ok += a
    bad += b
    return ok, bad


def check_form(streamed, rows):
    """IR-STM-02 and IR-STM-03: the shape of what was written."""
    ok = bad = 0
    for s in streamed:
        tag = "rate %d" % s["rate"]
        a, b = check("IR-STM-02 %s ONFSH version is 1" % tag, s["ver"] == 1)
        ok += a
        bad += b
        a, b = check("IR-STM-02 %s ONFSR names nr readouts" % tag,
                     s["ro"] is not None and len(s["ro"]) == s["nr"],
                     "nr=%d ro=%s" % (s["nr"], s["ro"]))
        ok += a
        bad += b
        a, b = check("IR-STM-03 %s ONFSC is sparse" % tag, s["usparse"],
                     "" if s["usparse"] else "a zero delta was emitted")
        ok += a
        bad += b

        # D-406: `nfired` counts the CHUNK, so after a continuation this is
        # the round-trip check -- the pairs reassembled from the ONFSC and
        # every ONFSD that follows it must come to exactly nfired, no more
        # and no fewer.  A dropped continuation line fails here, which is
        # the entire reason nfired was not redefined as a per-line count.
        counts = all(c["nfired"] == len(c["pairs"]) for c in s["chunks"])
        wrapped = sum(1 for c in s["chunks"] if len(c["pairs"]) > 0)
        a, b = check("IR-STM-02 %s ONFSC count equals its pairs, "
                     "reassembled across ONFSD" % tag, counts,
                     "%d chunks, largest %d pairs"
                     % (wrapped, max([len(c["pairs"])
                                      for c in s["chunks"]] or [0])))
        ok += a
        bad += b

        # Every ONFSU must pair with its ONFSC, carry one column per readout
        # neuron, and every column must be exactly the 16 digits of a
        # binary64.
        good = True
        detail = ""
        for c in s["chunks"]:
            u = c.get("u")
            if u is None or c.get("ustep") != c["step"]:
                good = False
                detail = "chunk %d has no matching ONFSU" % c["chunk"]
                break
            if len(u) != s["nr"]:
                good = False
                detail = "chunk %d has %d columns, want %d" % (
                    c["chunk"], len(u), s["nr"])
                break
            for word in u:
                if len(word) != 16:
                    good = False
                    detail = "%r is not 16 hex digits" % word
                    break
                try:
                    struct.unpack(">d", bytes.fromhex(word))
                except (ValueError, struct.error):
                    good = False
                    detail = "%r is not a binary64 bit pattern" % word
                    break
            if not good:
                break
        a, b = check("IR-STM-03 %s ONFSU is 16-digit binary64" % tag,
                     good, detail)
        ok += a
        bad += b

        # The values, not only the shape.  Without this the membrane columns
        # could be any sixteen well-formed hex digits -- a trace panel drawn
        # from noise would pass every check above it.
        vals = []
        for c in s["chunks"]:
            for word in c.get("u", []):
                vals.append(struct.unpack(">d", bytes.fromhex(word))[0])
        finite = all(v == v and abs(v) != float("inf") for v in vals)
        a, b = check("FR-SIM-08 %s every membrane value is finite" % tag,
                     finite)
        ok += a
        bad += b

        if s["rate"] == 0:
            # G-15 is silence (ACC-2): no stimulus, so nothing charges and
            # every readout membrane must be exactly u_reset, which the
            # header gives as zero.  This is the one request whose membrane
            # trace has a known closed form, so it is the one that can catch
            # a column filled with something plausible.
            a, b = check("ACC-2 %s every membrane value is exactly zero"
                         % tag, vals and all(v == 0.0 for v in vals),
                         "%d values, %d nonzero"
                         % (len(vals), sum(1 for v in vals if v != 0.0)))
            ok += a
            bad += b
            a, b = check("ACC-2 %s nothing fires" % tag, not s["total"],
                         "fired: %s" % sorted(s["total"]))
            ok += a
            bad += b
        else:
            a, b = check("IR-STM-03 %s the membrane trace varies" % tag,
                         len(set(vals)) > 1,
                         "%d distinct values over %d samples"
                         % (len(set(vals)), len(vals)))
            ok += a
            bad += b

        chunks_numbered = [c["chunk"] for c in s["chunks"]] == \
            list(range(1, len(s["chunks"]) + 1))
        a, b = check("IR-STM-02 %s chunks are numbered 1..n" % tag,
                     chunks_numbered)
        ok += a
        bad += b
        a, b = check("IR-STM-02 %s ONFSE count equals chunks seen" % tag,
                     s["nchunk"] == len(s["chunks"]),
                     "ONFSE says %d, saw %d" % (s["nchunk"],
                                                len(s["chunks"])))
        ok += a
        bad += b
        rows.append("  %s: %d chunks, K=%d over %d steps"
                    % (tag, len(s["chunks"]), s["k"], s["steps"]))
    return ok, bad


def check_agreement(recs, streamed, gold=False):
    """IR-STM-04: the stream describes the same run as the response.

    Only simulated requests appear in the stream, so the response records are
    filtered the same way before the two are paired in order."""
    ok = bad = 0
    # IR-STM-02: one envelope per REQUEST, not per simulated request, so the
    # two lists pair one to one and a rejected request is visible in the
    # stream rather than absent from it.
    if len(recs) != len(streamed):
        return check("IR-STM-02 one stream envelope per request", False,
                     "%d requests, %d streamed" % (len(recs), len(streamed)))
    a, b = check("IR-STM-02 one stream envelope per request", True,
                 "%d requests" % len(recs))
    ok += a
    bad += b

    for rec, s in zip(recs, streamed):
        tag = "rate %d" % s["rate"]
        if rec["rc"] != 0:
            # Warned or rejected: the envelope must be there and empty.
            a, b = check("IR-STM-02 %s rc=%d is an empty envelope"
                         % (tag, rec["rc"]),
                         s["steps"] == 0 and not s["chunks"]
                         and s["nchunk"] == 0 and not s["total"],
                         "steps=%d chunks=%d" % (s["steps"],
                                                 len(s["chunks"])))
            ok += a
            bad += b
            a, b = check("IR-STM-04 %s ONFSE carries the record's rc" % tag,
                         s["rc"] == rec["rc"] and s["fp"] == rec["fphex"],
                         "stream rc=%d fp=%s, record rc=%d fp=%s"
                         % (s["rc"], s["fp"], rec["rc"], rec["fphex"]))
            ok += a
            bad += b
            continue
        a, b = check("IR-STM-04 %s ONFSE fingerprint equals ONF-FPRINT" % tag,
                     s["fp"] == rec["fphex"],
                     "stream %s, record %s" % (s["fp"], rec["fphex"]))
        ok += a
        bad += b

        # D-380's first guard, and the one with the most at stake: the
        # Section 8.4 fingerprint must still be the value TK5 produced under
        # two compilers.  A stream that moved one would not have broken a
        # feature, it would have broken ACC-5.
        #
        # Only for the golden deck.  The same rate at a different DURATION is
        # a different request with a different fingerprint, and checking it
        # against G-16 would be comparing two unrelated runs.
        if gold:
            want = GOLD_SREXT.get(s["rate"])
            a, b = check("ACC-5 %s fingerprint unchanged under STREAM="
                         % tag,
                         want is not None and s["fp"] == want,
                         "streamed %s, Section 8.3 rows 6 and 7 record %s"
                         % (s["fp"], want))
            ok += a
            bad += b
        a, b = check("IR-STM-04 %s ONFSH steps equals ONF-STEPS" % tag,
                     s["steps"] == rec["steps"],
                     "stream %d, record %d" % (s["steps"], rec["steps"]))
        ok += a
        bad += b

        for out in rec["outs"]:
            nid = out["id"]
            total = s["total"].get(nid, 0)
            a, b = check("IR-STM-04 %s n%d spikes sum to ONF-OUT-SPIKES"
                         % (tag, nid), total == out["spikes"],
                         "stream %d, record %d" % (total, out["spikes"]))
            ok += a
            bad += b

            rose = s["first"].get(nid)
            if out["latus"] == -1:
                good = rose is None
                detail = "record says never; stream %s" % (
                    "agrees" if good else "has it rising")
            elif rose is None:
                good = False
                detail = "record says %d us; stream never has it rise" \
                    % out["latus"]
            else:
                lo, hi = rose
                # The chunk that carried the first spike covers completed
                # step counts (lo, hi], and FR-SIM-05's latency for the step
                # at 0-based index i is (i + 1) * dtus -- so the bracket in
                # microseconds is (lo * dtus, hi * dtus].
                good = lo * s["dtus"] < out["latus"] <= hi * s["dtus"]
                detail = "%d us in (%d, %d]" % (out["latus"],
                                                lo * s["dtus"],
                                                hi * s["dtus"])
            a, b = check("IR-STM-04 %s n%d first rise brackets latency"
                         % (tag, nid), good, detail)
            ok += a
            bad += b
    return ok, bad


def check_engine(exe, netpath, reqpath, tmp, rows):
    """Everything that needs this engine to run."""
    name = os.path.basename(exe)
    print("test_strm: %s" % name)
    ok = bad = 0

    plain = os.path.join(tmp, "%s-plain.rsp" % name)
    withs = os.path.join(tmp, "%s-stream.rsp" % name)
    stm = os.path.join(tmp, "%s.stm" % name)

    rc0, _ = run_engine(exe, netpath, reqpath, plain, "", stm + ".unused")
    rc1, out1 = run_engine(exe, netpath, reqpath, withs,
                           "STREAM=%d" % K_DEMO, stm)

    a, b = check("both runs reach the same step return code", rc0 == rc1,
                 "plain rc=%d, streamed rc=%d" % (rc0, rc1))
    ok += a
    bad += b

    a, b = check("IR-STM-01 a plain run writes no ONFSTM",
                 not os.path.exists(stm + ".unused"))
    ok += a
    bad += b

    raw0 = open(plain, "rb").read()
    raw1 = open(withs, "rb").read()
    a, b = check("IR-STM-04 ONFRSP is byte-identical with and without "
                 "STREAM=", raw0 == raw1,
                 "%d vs %d bytes" % (len(raw0), len(raw1)))
    ok += a
    bad += b

    try:
        streamed = parse_stream(stm)
    except StreamError as exc:
        a, b = check("IR-STM-02 the stream parses", False, str(exc))
        return ok + a, bad + b
    a, b = check("IR-STM-02 the stream parses", True,
                 "%d requests, %d bytes" % (len(streamed),
                                            os.path.getsize(stm)))
    ok += a
    bad += b

    a, b = check_width(stm, "K=%d" % K_DEMO)
    ok += a
    bad += b

    recs = decode_records(raw1)
    a, b = check_form(streamed, rows)
    ok += a
    bad += b
    a, b = check_agreement(recs, streamed, gold=True)
    ok += a
    bad += b

    # FR-SIM-10 at the level of the stream's own content: a different K must
    # move the frame boundaries and nothing else.
    odd = os.path.join(tmp, "%s-odd.rsp" % name)
    stm2 = os.path.join(tmp, "%s-odd.stm" % name)
    run_engine(exe, netpath, reqpath, odd, "STREAM=%d" % K_ODD, stm2)
    raw2 = open(odd, "rb").read()
    a, b = check("IR-STM-04 ONFRSP does not depend on K", raw1 == raw2,
                 "K=%d against K=%d" % (K_DEMO, K_ODD))
    ok += a
    bad += b
    try:
        odds = parse_stream(stm2)
    except StreamError as exc:
        a, b = check("IR-STM-02 the K=%d stream parses" % K_ODD, False,
                     str(exc))
        return ok + a, bad + b
    same = (len(odds) == len(streamed)
            and all(x["total"] == y["total"] for x, y in zip(odds, streamed)))
    a, b = check("IR-STM-04 per-neuron totals do not depend on K", same)
    ok += a
    bad += b
    a, b = check_width(stm2, "K=%d" % K_ODD)
    ok += a
    bad += b
    finer = all(x["nchunk"] > y["nchunk"] for x, y in zip(odds, streamed))
    a, b = check("IR-STM-01 a smaller K gives more chunks", finer,
                 "K=%d: %s; K=%d: %s"
                 % (K_ODD, [x["nchunk"] for x in odds],
                    K_DEMO, [y["nchunk"] for y in streamed]))
    ok += a
    bad += b
    return ok, bad


def check_reject(exe, netpath, tmp, rows):
    """IR-STM-02: a warned or rejected request still gets its envelope.

    WHY THIS HAS ITS OWN DECK.  The srext half of Section 8.4 is five valid
    requests, so nothing in it reaches the rejection path -- which is exactly
    how the first version of the emitter shipped with a defect: it wrote
    ONFSE with no preceding ONFSH, so a consumer met an end line for a
    request it had never been told about, and this file's own parser raised
    on it.  The golden suite could not have caught that.  This deck can.

    The three cards are the srext counterparts of G-11, G-12 and G-13: a
    reserved stimulus (ONF201W), an unknown one (ONF203E) and a rate out of
    range (ONF202E), with a valid request first so the file is not entirely
    rejections."""
    print("test_strm: the rejection envelope (%s)" % os.path.basename(exe))
    ok = bad = 0
    reqpath = os.path.join(tmp, "rej.req")
    with open(reqpath, "wb") as fh:
        fh.write(mkreq.pack("SUGR", 40, 20, 1))      # valid
        fh.write(mkreq.pack("WATR", 40, 20, 1))      # ONF201W, FR-BAT-05
        fh.write(mkreq.pack("XXXX", 40, 20, 1))      # ONF203E
        fh.write(mkreq.pack("SUGR", -1, 20, 1))      # ONF202E
    rsppath = os.path.join(tmp, "rej.rsp")
    stmpath = os.path.join(tmp, "rej.stm")
    rc, out = run_engine(exe, netpath, reqpath, rsppath,
                         "STREAM=%d" % K_DEMO, stmpath)
    a, b = check("IR-JCL-04 the step return code is 8", rc == 8, "rc=%s" % rc)
    ok += a
    bad += b

    try:
        streamed = parse_stream(stmpath)
    except StreamError as exc:
        a, b = check("IR-STM-02 the stream parses with rejections", False,
                     str(exc))
        return ok + a, bad + b
    a, b = check("IR-STM-02 the stream parses with rejections", True,
                 "%d envelopes" % len(streamed))
    ok += a
    bad += b

    recs = decode_records(open(rsppath, "rb").read())
    a, b = check_agreement(recs, streamed)
    ok += a
    bad += b
    got = [s["rc"] for s in streamed]
    a, b = check("IR-STM-04 the stream reports every return code",
                 got == [0, 4, 8, 8], "stream rcs %s" % got)
    ok += a
    bad += b
    return ok, bad


def check_membrane(exe, netpath, tmp):
    """IR-STM-03: the ONFSU columns really are the membrane potential.

    WHY THIS IS NOT REDUNDANT.  Everything else about ONFSU is shape -- the
    right number of columns, sixteen hex digits, a finite value, a value that
    varies.  A negative control run while writing this file replaced the
    column with the neuron's spike count and passed every one of those: a
    small integer read as a binary64 is a subnormal, so it is finite; it
    varies; and in the silent request it is zero, which is exactly what the
    membrane should be.  Shape checks cannot tell a membrane from anything
    else shaped like one.

    So the values are compared against the oracle, bit for bit, at every
    chunk boundary.  The oracle is O-1 -- plain Python floats, explicit
    left-to-right loops -- and NR-01 makes the engine's arithmetic correctly
    rounded, so the two must agree exactly, not approximately.

    The request is short and deliberately not from Section 8.4: the oracle
    runs about 500 neuron-steps per millisecond of simulated time here, so a
    1000 ms golden request would cost minutes.  20 ms at 200 Hz is enough for
    the membrane to charge, spike and reset, which is the behaviour the panel
    D-345 describes exists to show."""
    print("test_strm: membrane against the oracle (%s)"
          % os.path.basename(exe))
    ok = bad = 0
    ms, rate, seed, k = 20, 200, 1, 10

    reqpath = os.path.join(tmp, "mem.req")
    with open(reqpath, "wb") as fh:
        fh.write(mkreq.pack("SUGR", rate, ms, seed))
    rsppath = os.path.join(tmp, "mem.rsp")
    stmpath = os.path.join(tmp, "mem.stm")
    run_engine(exe, netpath, reqpath, rsppath, "STREAM=%d" % k, stmpath)

    try:
        streamed = parse_stream(stmpath)
    except StreamError as exc:
        return check("IR-STM-03 the membrane stream parses", False, str(exc))
    if len(streamed) != 1:
        return check("IR-STM-03 one streamed request", False,
                     "got %d" % len(streamed))
    s = streamed[0]

    spec = netread.read(netpath)
    onet = netread.as_oracle_network(spec)
    ost = okernel._init(onet, seed, rate)

    mismatch = None
    for c in s["chunks"]:
        okernel._advance(onet, ost, c["step"] - c["lo"])
        for col, nix in enumerate(s["ro"]):
            want = struct.pack(">d", ost.u[nix]).hex().upper()
            got = c["u"][col]
            if want != got:
                mismatch = ("chunk %d neuron %d: stream %s, oracle %s"
                            % (c["chunk"], nix, got, want))
                break
        if mismatch:
            break

    a, b = check("IR-STM-03 ONFSU equals the oracle membrane bit for bit",
                 mismatch is None,
                 mismatch or "%d chunks x %d readouts over %d steps"
                 % (len(s["chunks"]), len(s["ro"]), s["steps"]))
    ok += a
    bad += b

    # A guard on the guard: if the sampled trace were flat, the comparison
    # above would be agreeing with a flat oracle and would prove nothing.
    # This says only that the samples vary and include u_reset -- it does not
    # claim to have observed a spike, which the counts above are for.
    seen = [struct.unpack(">d", bytes.fromhex(c["u"][0]))[0]
            for c in s["chunks"]]
    a, b = check("IR-STM-03 the sampled membrane varies and includes u_reset",
                 max(seen) > min(seen) and min(seen) <= 0.0,
                 "min %.6g, max %.6g over %d samples"
                 % (min(seen), max(seen), len(seen)))
    ok += a
    bad += b
    return ok, bad


def check_parm(exe, netpath, reqpath, tmp):
    """D-381's two messages, and the PARM behaviour they must not disturb."""
    print("test_strm: PARM and failure paths (%s)" % os.path.basename(exe))
    ok = bad = 0
    rsp = os.path.join(tmp, "parm.rsp")

    for parm, why in (("STREAM=", "no number at all"),
                      ("STREAM=0", "zero is not a chunk size"),
                      ("STREAM=abc", "not a number"),
                      ("STREAM=12x", "trailing rubbish"),
                      ("STREAM=1000000", "above the IR-STM-01 bound")):
        rc, out = run_engine(exe, netpath, reqpath, rsp, parm,
                             os.path.join(tmp, "parm.stm"))
        msg = out[0].split()[0] if out else "(no output)"
        a, b = check("ONF908S PARM=%-12r %s" % (parm, why),
                     msg == "ONF908S" and rc == RC_ENV,
                     "msg=%s rc=%s" % (msg, rc))
        ok += a
        bad += b

    # D-226's behaviour, which IR-STM-01 deliberately does not narrow: a PARM
    # that does not begin with STREAM= still means SIMULATE.
    rc, out = run_engine(exe, netpath, reqpath, rsp, "XYZZY",
                         os.path.join(tmp, "parm.stm"))
    a, b = check("an unrecognised PARM still means SIMULATE (D-226)",
                 rc == 0, "rc=%s" % rc)
    ok += a
    bad += b

    # ONF907S: a stream dataset that cannot be opened.  A directory is used
    # because it exists and cannot be opened for writing on any host here.
    baddir = os.path.join(tmp, "notafile")
    os.mkdir(baddir)
    rc, out = run_engine(exe, netpath, reqpath, rsp, "STREAM=%d" % K_DEMO,
                         baddir)
    msg = [ln.split()[0] for ln in out if ln.startswith("ONF907S")]
    a, b = check("ONF907S an unwritable ONFSTM",
                 msg == ["ONF907S"] and rc == RC_ENV,
                 "msgs=%s rc=%s" % (msg, rc))
    ok += a
    bad += b
    return ok, bad


def main(argv):
    if not argv:
        sys.stderr.write("usage: test_strm.py <onflyeng> [<onflyeng> ...]\n")
        return 2

    label, netpath = run_gld.NETWORKS[1]          # srext, the shipped network
    if not os.path.exists(netpath):
        sys.stderr.write("network not found: %s\n"
                         "run `make fixtures` first\n" % netpath)
        return 2

    passed = failed = 0
    rows = []
    tmp = tempfile.mkdtemp(prefix="onfly-strm-")
    try:
        reqpath = os.path.join(tmp, "%s.req" % label)
        with open(reqpath, "wb") as fh:
            for rec in mkreq.cards_to_records(mkreq.golden_cards(label)):
                fh.write(rec)

        for exe in argv:
            p, f = check_engine(exe, netpath, reqpath, tmp, rows)
            passed += p
            failed += f
        p, f = check_reject(argv[0], netpath, tmp, rows)
        passed += p
        failed += f
        p, f = check_membrane(argv[0], netpath, tmp)
        passed += p
        failed += f
        p, f = check_parm(argv[0], netpath, reqpath, tmp)
        passed += p
        failed += f
        print("test_strm: the wide-readout continuations (%s)"
              % os.path.basename(argv[0]))
        p, f = check_wide(argv[0], tmp)
        passed += p
        failed += f
    finally:
        for root, dirs, files in os.walk(tmp, topdown=False):
            for nm in files:
                os.remove(os.path.join(root, nm))
            for nm in dirs:
                os.rmdir(os.path.join(root, nm))
        os.rmdir(tmp)

    for r in rows:
        print(r)
    print("test_strm: %d passed, %d failed" % (passed, failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
