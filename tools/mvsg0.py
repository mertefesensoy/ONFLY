# -*- coding: utf-8 -*-
"""Gate G0 on MVS: is TK5 running, and what C toolchains does it hold?

SRS Section 9.1 (Gate G0), assumptions A-03 and A-04, D-235, D-238.

WHAT THIS ANSWERS
-----------------
A-03 and A-04 are written as commands, not as prose:

    A-03  GCCMVS is installed or installable on TK5
          (`LISTC LEVEL(GCC)`, `LISTC LEVEL(PDPCLIB)`)
    A-04  JCC is installed or installable on TK5
          (`LISTC LEVEL(JCC)`)

so this runs exactly those commands on the running system rather than
paraphrasing them, and keeps the raw listing.  Both assumptions have read
"TBC at Gate G0" since the SRS was drafted, through a Gate G1, a Gate G2
and a Gate G4 that all used GCCMVS daily.  Usage is not a record.

WHY A LISTING IS NOT ENOUGH (D-238)
-----------------------------------
The owner's standard for G0 is "present and working".  A catalog entry
proves a dataset exists; it does not prove a compiler compiles.  So each
toolchain is also asked to build and run a program that prints its own
version -- the version string comes back from a binary the compiler
produced and the machine executed, which is a different and much stronger
claim than reading a version out of a filename.

The probe is deliberately the smallest C that can carry that evidence:
`__VERSION__`, the int width, and the byte order observed by shifting
rather than by casting (FR-LOD-05's rule, applied to the probe itself).
It uses no ONFLY header, so a failure here is the toolchain's and cannot
be the repository's.

THREE THINGS THAT ARE NOT OPTIONAL, EACH LEARNED THE HARD WAY
-------------------------------------------------------------
`REGION=8M` -- without it a job does not fail, it spins at 100% of a core
until cancelled (Gate G1, tools/mvsbld.py).

The `819/1047` codepage -- a Hercules restart silently returns it to
`default`, where ASCII '|' arrives as EBCDIC 0x6A and GCCMVS will not lex
it (VL-18, D-101).  tools/mvsub.py refuses to submit on any other page
(D-103), so this module sets it before submitting anything.

`DD DATA,DLM=` for C source, never `DD *` -- a C source opens with `/*`
in column 1, which is JES2's end-of-data delimiter (Gate G1).  The catalog
job below has no C in it and may use `DD *`; the compile jobs go through
tools/mvsbld.py, which already knows.

Run:
    python tools/mvsg0.py --cat        catalog inventory (A-03, A-04)
    python tools/mvsg0.py --gcc        GCCMVS builds and runs the probe
    python tools/mvsg0.py --jcc        JCC builds and runs the probe
    python tools/mvsg0.py --all
Exit status 0 when every requested job finished and reported.
"""
import io
import json
import re
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import mvsub                                                   # noqa: E402
import mvsbld                                                  # noqa: E402
import g0                                                      # noqa: E402

REGION = "8M"
USER = mvsbld.USER

# The three catalog levels A-03 and A-04 name, in their order.
LEVELS = ("GCC", "PDPCLIB", "JCC")


# The probe lives in tools/g0.py so that MVS and s390x build the
# same C and their answers can be compared line for line.
probe_source = g0.probe_source


def catalog_deck():
    """A job that runs A-03's and A-04's own commands, two ways.

    `LISTC` is a TSO command, so IKJEFT01 (the batch terminal monitor) is
    the literal reading of the assumptions.  IDCAMS `LISTCAT` is run
    beside it under COND=EVEN because the two do not necessarily see the
    same catalog on MVS 3.8j, and a gate record should say which one
    answered rather than leaving the reader to guess.
    """
    d = []
    d.append("//ONFG0CAT JOB (001),'ONFLY GATE G0',CLASS=A,MSGCLASS=A,")
    d.append("//             USER=%s,PASSWORD=CUL8TR," % USER)
    d.append("//             REGION=%s,TIME=1440,MSGLEVEL=(1,1)" % REGION)
    d.append("//*")
    d.append("//TSOLIST  EXEC PGM=IKJEFT01,DYNAMNBR=20")
    d.append("//SYSTSPRT DD SYSOUT=*")
    d.append("//SYSPRINT DD SYSOUT=*")
    d.append("//SYSTSIN  DD *")
    for lvl in LEVELS:
        d.append(" LISTC LEVEL(%s) ALL" % lvl)
    # Which library each toolchain's driver actually lives in, listed by
    # a TSO command rather than by IEHLIST.  IEHLIST needs a DD naming a
    # volume, and a volume this system does not have makes MVS stop and
    # ask the operator -- measured: `IEF238D ONFG0CAT - REPLY DEVICE NAME
    # OR 'CANCEL'`, with the job held until someone answers.  TK5's
    # volumes are TK5RES/TK5CAT/TK5001/TK5002/WORK0n/TSO00n, not TK4-'s
    # PUB000.  LISTDS needs no volume and cannot hang the job.
    for dsn in ("SYS2.PROCLIB", "SYS2.LINKLIB", "SYS2.JCLLIB",
                "SYS1.LINKLIB", "SYS2.CMDLIB"):
        d.append(" LISTDS '%s' MEMBERS" % dsn)
    d.append("/*")
    d.append("//*")
    # The procedures themselves, printed verbatim: only they say which
    # library actually holds each compiler.  JCCCLG names its STEPLIB
    # (JCC.LINKLIB); GCCCLG names none, so GCC must resolve from the
    # linklist, and LNKLST00 below says what that concatenation is.
    # Measured answer: GCC is in SYS2.LINKLIB after all, as an ALIAS of
    # GCC370 -- an alias line reads `GCC  ALIAS(GCC370)`, so a member
    # pattern anchored at end of line misses it, which is how reading
    # the listing by eye first concluded the module was not there.
    members = (("SYS2.PROCLIB", "GCCCLG"),
               ("SYS2.PROCLIB", "JCCCLG"),
               ("SYS2.PROCLIB", "COBUCLG"),
               # LNKLST00 is what makes `EXEC PGM=GCC` resolvable at
               # all, so the record names the concatenation rather than
               # leaving it to be inferred.
               ("SYS1.PARMLIB", "LNKLST00"),
               # The exit criterion says "TK5 Update 5 running", and the
               # running system does not announce its update level in the
               # IPL messages -- only "MVS 3.8j TK5".  $HISTORY is TK5's
               # own in-system changelog, so it is the one place the
               # level can be read from the machine rather than from the
               # name of the ZIP it was installed from (D-89).
               ("SYS2.JCLLIB", "$HISTORY"))
    for n, (dsn, member) in enumerate(members, 1):
        d.append("//PROC%d    EXEC PGM=IEBGENER,COND=EVEN" % n)
        d.append("//SYSPRINT DD SYSOUT=*")
        d.append("//SYSUT1   DD DSN=%s(%s),DISP=SHR" % (dsn, member))
        d.append("//SYSUT2   DD SYSOUT=*")
        d.append("//SYSIN    DD DUMMY")
        d.append("//*")
    d.append("//AMSLIST  EXEC PGM=IDCAMS,COND=EVEN")
    d.append("//SYSPRINT DD SYSOUT=*")
    d.append("//SYSIN    DD *")
    for lvl in LEVELS:
        d.append("  LISTCAT LEVEL(%s)" % lvl)
    d.append("/*")
    d.append("//")
    return d


def compile_deck(which):
    """A compile-link-go deck for GCCMVS or for JCC.

    GCCMVS goes through tools/mvsbld.py, which owns every trap in that
    path.  JCC has its own catalogued procedure and needs none of it.
    """
    if which == "gcc":
        return mvsbld.build("ONFG0GCC", "ONFLY G0 GCC",
                            [(probe_source(), "G0PROBE")])
    d = []
    d.append("//ONFG0JCC JOB (001),'ONFLY GATE G0',CLASS=A,MSGCLASS=A,")
    d.append("//             USER=%s,PASSWORD=CUL8TR," % USER)
    d.append("//             REGION=%s,TIME=1440,MSGLEVEL=(1,1)" % REGION)
    d.append("//*")
    d.append("//CLG      EXEC JCCCLG")
    d.append("//COMPILE.SYSIN DD DATA,DLM='ZZ'")
    d.extend(probe_source())
    d.append("ZZ")
    d.append("//")
    return d


def parse_catalog(out):
    """Turn the catalog job's printer output into the answer it contains.

    The raw listing is kept too, but a gate record that forces its reader
    to re-parse 2,500 lines of JES2 output is not a record.  Three things
    are extracted:

      levels     what `LISTC LEVEL(x)` said for each of A-03's and
                 A-04's levels -- including NOT FOUND, which is the
                 interesting answer for GCC
      libraries  each LISTDS'd library, its volume, and the members that
                 matter to ONFLY
      linklist   SYS1.PARMLIB(LNKLST00), which says which libraries
                 `EXEC PGM=GCC` can resolve from

    ALIAS lines are the reason this exists.  LISTDS prints an alias as
    `GCC  ALIAS(GCC370)`, not as a bare name, so a member pattern that
    anchors at end of line misses exactly the entry that answers A-03 --
    which is what happened when this was first read by eye.
    """
    lines = [l.rstrip() for l in (out or "").splitlines()]
    res = {"levels": {}, "libraries": {}, "linklist": []}

    # --- LISTC per level ------------------------------------------------
    for n, lvl in enumerate(LEVELS):
        start = None
        for i, l in enumerate(lines):
            if l.strip() == "LISTC LEVEL(%s) ALL" % lvl:
                start = i
                break
        if start is None:
            continue
        # The block ends at the next LISTC *or* at the start of the
        # IDCAMS step, whichever comes first.  Without the second bound
        # the last level ran to end of file and absorbed the whole
        # LISTCAT section: JCC then reported 15 datasets instead of 12
        # and inherited GCC's NOT FOUND line from the other utility.
        stop = len(lines)
        for i in range(start + 1, len(lines)):
            s = lines[i].strip()
            if s.startswith("LISTC LEVEL(") or s.startswith("LISTCAT LEVEL("):
                stop = i
                break
        blk = lines[start:stop]
        dsns = [l.split("-------", 1)[1].strip()
                for l in blk if l.startswith("NONVSAM -------")]
        notfound = [l.strip() for l in blk if "IDC3012I" in l]
        res["levels"][lvl] = {"datasets": sorted(set(dsns)),
                              "count": len(set(dsns)),
                              "not_found": notfound}

    # --- LISTDS per library ---------------------------------------------
    idx = [i for i, l in enumerate(lines) if l.strip().startswith("LISTDS ")]
    for n, i in enumerate(idx):
        end = idx[n + 1] if n + 1 < len(idx) else len(lines)
        blk = lines[i:end]
        dsn = lines[i].strip().split("'")[1]
        vol = ""
        for j, l in enumerate(blk):
            if l.strip() == "--VOLUMES--" and j + 1 < len(blk):
                vol = blk[j + 1].strip()
                break
        mem = []
        for l in blk:
            s = l.strip()
            m = re.match(r"^([A-Z@#$][A-Z0-9@#$]{0,7})"
                         r"(\s+ALIAS\(([A-Z0-9@#$]{1,8})\))?$", s)
            if m and l.startswith("  ") and s != vol:
                mem.append((m.group(1), m.group(3)))
        keep = [(a, b) for (a, b) in mem
                if a.startswith("GCC") or a.startswith("JCC")
                or a.startswith("COBU") or a == "IKFCBL00"]
        res["libraries"][dsn] = {
            "volume": vol,
            "members": len(mem),
            "toolchain": ["%s (alias of %s)" % (a, b) if b else a
                          for a, b in keep],
        }

    # --- LNKLST00 --------------------------------------------------------
    for i, l in enumerate(lines):
        if l.strip().startswith("SYS1.LINKLIB,"):
            for j in range(i, min(i + 20, len(lines))):
                s = lines[j].strip().rstrip(",")
                if not s:
                    break
                res["linklist"].append(s)
            break
    return res


def run_job(cards, jobname, timeout=600, codepage=True):
    """Submit, wait, and return what the printer holds for the job."""
    out = mvsub.run(cards, jobname, timeout=timeout)
    return out


def ensure_codepage():
    """Put Hercules on 819/1047 (D-101) and say what it was.

    A restart resets it to `default`, where ONFLY source cannot reach
    GCCMVS at all (VL-18).  This is executing D-101, not deciding it.
    """
    was = mvsub.current_codepage()
    if was == mvsub.REQUIRED_CP:
        return was, was
    g0.hercules_console("codepage %s" % mvsub.REQUIRED_CP)
    return was, mvsub.current_codepage()


def main(argv):
    args = argv[1:]
    if not args:
        sys.stderr.write(__doc__.split("Run:")[-1])
        return 2
    was, now = ensure_codepage()
    sys.stdout.write("mvsg0: codepage was %s, now %s\n" % (was, now))

    sec = g0.section_mvs()
    if "error" in sec:
        sys.stderr.write("mvsg0: %s\n" % sec["error"])
        return 1
    sec["codepage_before"] = was

    jobs = []
    if "--cat" in args or "--all" in args:
        jobs.append(("catalog", catalog_deck(), "ONFG0CAT", 600))
    if "--gcc" in args or "--all" in args:
        jobs.append(("gccmvs", compile_deck("gcc"), "ONFG0GCC", 900))
    if "--jcc" in args or "--all" in args:
        jobs.append(("jcc", compile_deck("jcc"), "ONFG0JCC", 900))

    # Keep whatever earlier runs recorded.  Each invocation gathers only
    # the jobs it was asked for, and replacing the whole section instead
    # of merging lost the catalog results the moment `--jcc` ran on its
    # own -- the gate record then silently held one third of its evidence.
    rc = 0
    sec["jobs"] = {}
    try:
        prev = json.loads(io.open(g0.OUT, encoding="utf-8").read())
        sec["jobs"].update(prev.get("mvs", {}).get("jobs", {}))
    except Exception:
        pass
    for name, cards, jobname, timeout in jobs:
        sys.stdout.write("\nmvsg0: submitting %s (%d cards)\n"
                         % (jobname, len(cards)))
        out = run_job(cards, jobname, timeout=timeout)
        ok = out is not None
        rc = rc or (0 if ok else 1)
        sec["jobs"][name] = {"jobname": jobname,
                             "cards": len(cards),
                             "finished": ok,
                             "summary": mvsub.summarise(out),
                             "output": out}
        for line in mvsub.summarise(out):
            sys.stdout.write("   %s\n" % line)
        if out is not None:
            for line in out.splitlines():
                if "ONFG0 " in line:
                    sys.stdout.write("   %s\n" % line.rstrip())

    # A gate record that makes its reader re-parse 2,500 lines of JES2
    # output is not a record, so the answer is stored beside the raw.
    sec["parsed"] = {}
    for name, job in sec["jobs"].items():
        if not job.get("output"):
            continue
        if name == "catalog":
            sec["parsed"]["catalog"] = parse_catalog(job["output"])
        probe = [l.strip() for l in job["output"].splitlines()
                 if l.strip().startswith("ONFG0 ")]
        if probe:
            sec["parsed"][name + "_probe"] = probe

    g0.merge("mvs", sec)
    sys.stdout.write("\nmvsg0: merged into %s\n" % g0.OUT)
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv))
