# -*- coding: utf-8 -*-
"""Progress the owner can watch without asking (D-315).

THE PROBLEM THIS SOLVES, WHICH WAS NOT A MISSING DASHBOARD

`prep/extract.py` calls sys.stdout.flush() in five places and its logs
appear as it runs. `prep/acc4.py` and `prep/wsens.py` never flushed at
all, so when their output was redirected to a file Python block-buffered
roughly 8 KB and the file read **zero bytes until the process exited**.
A 6,971 s ACC-4 run and an 11,047 s W_syn probe were each invisible for
their entire duration, and the only way to tell they were alive was to
count `runnet.exe` processes.

Flushing fixes the log. It does not fix the harder half: a log is text
for a human to read, and "which W_syn point, how many runs, how long
left" should be answerable by a command rather than by squinting.

WHAT THIS IS

A tiny status file per job, and a reader for it.

  data/progress/<job>.json

written atomically -- to a temporary file in the same directory, then
os.replace(), which is atomic on Windows and POSIX alike. A reader can
therefore never observe a half-written file, which matters because the
whole point is that something else reads it *while* the writer runs.

Contract of Tracker:

  t = Tracker("wsens-d52", total=480, unit="runs")   # creates the file
  t.stage("W_syn 0.2600", total=120)                 # optional subdivision
  t.tick()                                           # +1 done, rewrites
  t.note(w_syn=0.26, rate=40)                        # arbitrary context
  t.finish("ok")                                     # terminal state

Every mutator rewrites the file. That is a few hundred bytes per tick
against a full-brain run costing tens of seconds, so the cost is noise.

Nothing depends on this: it is observability, not a requirement. If the
file cannot be written -- read-only tree, missing directory, anything --
Tracker degrades to silence rather than failing a job that was going to
take three hours. A progress file that kills the run it reports on would
be worse than none.

Usage
-----
    python tools/progress.py            # one shot, every known job
    python tools/progress.py --watch    # refresh until interrupted
    python tools/progress.py --watch 10 # every 10 s (default 5)
"""
import io
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DIR = os.path.join(ROOT, "data", "progress")


def _now():
    return time.time()


def _iso(t):
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t))


class Tracker(object):
    """One job's status file. Every mutator rewrites it atomically."""

    def __init__(self, job, total=None, unit="steps", meta=None):
        self.job = job
        self.path = os.path.join(DIR, "%s.json" % job)
        self.state = {
            "job": job, "pid": os.getpid(), "unit": unit,
            "started_at": _now(), "updated_at": _now(),
            "done": 0, "total": total, "status": "running",
            "stage": None, "stage_done": 0, "stage_total": None,
            "meta": meta or {}, "note": {},
        }
        self._write()

    # --- mutators ---------------------------------------------------
    def stage(self, name, total=None):
        self.state["stage"] = name
        self.state["stage_done"] = 0
        self.state["stage_total"] = total
        self._write()

    def tick(self, n=1):
        self.state["done"] += n
        self.state["stage_done"] += n
        self._write()

    def note(self, **kw):
        self.state["note"].update(kw)
        self._write()

    def log(self, text, keep=60):
        """Append one line to the job's own rolling log.

        This is the half a watcher cannot obtain from outside. The
        process table shows that a run started and finished; only the
        job knows what the run RETURNED. A job that logs its results
        here lets a watcher show the numbers as they arrive instead of
        just the churn.

        Bounded, because the file is rewritten in full on every tick and
        an unbounded log would make each write grow without limit over a
        480-run job.
        """
        lg = self.state.setdefault("log", [])
        lg.append("%s  %s" % (time.strftime("%H:%M:%S"), text))
        if len(lg) > keep:
            del lg[:len(lg) - keep]
        self._write()

    def finish(self, status="ok"):
        self.state["status"] = status
        self._write()

    # --- the atomic write -------------------------------------------
    def _write(self):
        self.state["updated_at"] = _now()
        try:
            if not os.path.isdir(DIR):
                os.makedirs(DIR)
            tmp = self.path + ".tmp"
            io.open(tmp, "w", encoding="utf-8").write(
                json.dumps(self.state, indent=1, sort_keys=True))
            os.replace(tmp, self.path)
        except Exception:
            # Deliberate. See the module docstring: observability must
            # never be able to fail the run it is reporting on.
            pass


# --- the reader -----------------------------------------------------
def _eta(st):
    """Seconds remaining, or None when it cannot honestly be estimated.

    Straight-line from the work already done. It is wrong whenever the
    units differ in cost -- which they do here, since a W_syn point also
    emits a 299 MB network -- so it is labelled an estimate and rounded
    coarsely rather than presented to the second.
    """
    done, total = st.get("done") or 0, st.get("total")
    if not total or done <= 0 or st.get("status") != "running":
        return None
    el = st["updated_at"] - st["started_at"]
    return el * (total - done) / float(done)


def _dur(s):
    if s is None:
        return "--"
    s = int(s)
    if s < 90:
        return "%d s" % s
    if s < 5400:
        return "%d min" % round(s / 60.0)
    return "%.1f h" % (s / 3600.0)


def _bar(done, total, width=24):
    if not total:
        return " " * width
    f = max(0.0, min(1.0, done / float(total)))
    n = int(round(f * width))
    return "#" * n + "." * (width - n)


# --- inference, for jobs with no tracker file (D-319) ----------------
#
# A job already in flight when this tool was written has no status file,
# and a Tracker whose write fails goes silent by design (D-315).  What
# is still observable from outside the process is the filesystem and the
# process table, and that is enough for a coarse but honest answer.
#
# Everything here is labelled INFERRED wherever it is shown.  It is a
# different kind of claim from a tick the job itself wrote, and the two
# must never be confused: a tick means "the job says so", an inference
# means "this is what the machine looks like".
CALDIR = os.path.join(ROOT, "data", "calibration")

# --- one process snapshot per refresh (D-335) ------------------------
#
# This file used to spawn a separate PowerShell subprocess for each
# thing it wanted: the runnet workers, the wsens/calibrate job and its
# arguments, the worker count, and the Hercules CPU. Four spawns every
# refresh, per open window, with two or three windows open against a job
# that was itself recycling sixteen worker processes continuously.
#
# On 2026-09-16 at 12:40:04 the Hercules HTTP server died with
# HHC01800E -- select() failing for want of socket buffer space -- and
# took the console with it, which stopped every MVS submission. That
# this tool caused it is NOT established and is not claimed. That the
# churn was real, unnecessary and mine is established, and one
# Get-CimInstance returns everything needed: command lines, creation
# times, and KernelModeTime/UserModeTime for the CPU figure.
#
# Cached for a short TTL so several consumers in one render share it.
_SNAP = {"at": 0.0, "procs": None}
_SNAP_TTL = 3.0


def _snapshot(force=False):
    """Every process this tool cares about, in one query.

    Returns a list of dicts: name, pid, argv, started (epoch), cpu (s).
    Empty on any failure -- the callers already treat "nothing found"
    as "cannot tell", which is the honest reading when the query fails.
    """
    now = _now()
    if (not force and _SNAP["procs"] is not None
            and now - _SNAP["at"] < _SNAP_TTL):
        return _SNAP["procs"]
    out = []
    try:
        import subprocess as sp
        if os.name == "nt":
            ps = (
                "Get-CimInstance Win32_Process | Where-Object { "
                "$_.Name -like 'runnet*' -or $_.Name -like 'hercules*' "
                "-or ($_.Name -like 'python*' -and ("
                "$_.CommandLine -like '*prep/wsens.py*' -or "
                "$_.CommandLine -like '*prep/calibrate.py*')) } | "
                "ForEach-Object { '{0}|{1}|{2}|{3}|{4}' -f "
                "$_.Name, $_.ProcessId, "
                "([DateTimeOffset]::new($_.CreationDate)"
                ".ToUnixTimeSeconds()), "
                "(($_.KernelModeTime + $_.UserModeTime)/10000000), "
                "$_.CommandLine }")
            txt = sp.run(["powershell", "-NoProfile", "-Command", ps],
                         stdout=sp.PIPE, stderr=sp.DEVNULL,
                         timeout=60).stdout.decode("utf-8", "replace")
            for line in txt.splitlines():
                f = line.split("|", 4)
                if len(f) < 5:
                    continue
                try:
                    out.append({"name": f[0], "pid": int(f[1]),
                                "started": float(f[2]),
                                "cpu": float(f[3]),
                                "argv": f[4].strip().split()})
                except ValueError:
                    continue
        else:
            for pid in os.listdir("/proc"):
                if not pid.isdigit():
                    continue
                try:
                    raw = io.open("/proc/%s/cmdline" % pid, "rb").read()
                    argv = [a.decode("utf-8", "replace")
                            for a in raw.split(b"\0") if a]
                    if not argv:
                        continue
                    base = os.path.basename(argv[0])
                    keep = ("runnet" in base or "hercules" in base
                            or any("wsens.py" in a or "calibrate.py" in a
                                   for a in argv))
                    if not keep:
                        continue
                    out.append({"name": base, "pid": int(pid),
                                "started": os.path.getmtime(
                                    "/proc/%s" % pid),
                                "cpu": 0.0, "argv": argv})
                except Exception:
                    continue
    except Exception:
        out = []
    _SNAP["at"], _SNAP["procs"] = now, out
    return out


def _worker_count():
    """Live `runnet` processes, from the shared snapshot (D-335).

    Was a PowerShell spawn of its own.  Still matched on the process
    NAME and never on a command line: `pgrep -f runnet` finds the shell
    running the search, because -f matches whole command lines and that
    shell contains the pattern.  It cost a contradictory reading during
    the 2026-09-15 lab shutdown.
    """
    procs = _snapshot()
    if not procs:
        return None
    return sum(1 for w in procs if w["name"].lower().startswith("runnet"))

def _running_jobs():
    """The wsens/calibrate processes alive now, from the snapshot.

    A job that left no status file has not left NO information: its own
    command line carries the W_syn list, the rates and the seed count,
    and the OS records when it started.  That is reading the job's own
    invocation, not guessing.

    Only real interpreters count.  The shell that LAUNCHED the job also
    matches on command line, because its own quotes the whole
    invocation, and its argv is a shell snapshot -- so --seeds would be
    read off the wrong process.  The snapshot filters by name.
    """
    return [{"started": pr["started"], "argv": pr["argv"]}
            for pr in _snapshot()
            if pr["name"].lower().startswith("python")]

def _workers():
    """What every live runnet worker is computing, from the snapshot.

    prep/acc4.py's run_many spawns one process per run,

        runnet <network> <rate_hz> <sim_ms> <seed>

    so the process table states exactly which (rate, seed) pairs are in
    flight and against which network.  The dispatch order is
    [(r, s) for r in rates for s in seeds], so the furthest-advanced
    worker gives the exact dispatch position within the W_syn point --
    no timing estimate is involved.
    """
    out = []
    for pr in _snapshot():
        if not pr["name"].lower().startswith("runnet"):
            continue
        parts = pr["argv"]
        if len(parts) < 5:
            continue
        try:
            seed, ms, rate = (int(parts[-1]), int(parts[-2]),
                              int(parts[-3]))
        except ValueError:
            continue
        stem = os.path.basename(parts[-4])
        if stem.startswith("net-") and stem.endswith(".bin"):
            stem = stem[len("net-"):-len(".bin")]
        label, wtxt = (stem.rsplit("-", 1) if "-" in stem
                       else ("calibration", stem))
        out.append({"pid": pr["pid"], "label": label, "w_syn": wtxt,
                    "rate": rate, "ms": ms, "seed": seed})
    return out

def _inside(label, par):
    """Exact dispatch position within the current W_syn point.

    Honest about the distinction it rests on. What the process table
    shows is what has been **dispatched**, not what has **completed**: a
    worker appears the moment it starts and vanishes when it exits, so
    the furthest-advanced worker marks the high-water mark of dispatch
    and the ones still alive have not finished. Completed is therefore
    reported as `dispatched - in flight`, which is exact, rather than as
    a percentage that blurs the two.
    """
    live = [w for w in _workers() if w["label"] == label]
    if not live or not par:
        return None
    rates, seeds = par["rates_list"], par["seeds"]
    pos = 0
    for w in live:
        try:
            idx = rates.index(w["rate"])
        except ValueError:
            continue
        pos = max(pos, idx * seeds + w["seed"])
    by_rate = {}
    for w in live:
        by_rate.setdefault(w["rate"], []).append(w["seed"])
    return {"live": live, "dispatched": pos, "in_flight": len(live),
            "done": max(pos - len(live), 0),
            "per_point": len(rates) * seeds, "by_rate": by_rate}


# --- MVS jobs on TK5 (D-327) ----------------------------------------
#
# The x86 side of this tool watches worker PROCESSES. There are none for
# an MVS job: `tools/mvsrun.py` submits a card deck through the reader
# and then polls, so from the host all that exists is one python process
# waiting. The work is inside Hercules.
#
# What Hercules does expose is its console log, and MVS narrates itself
# there in a fixed form -- every step completion is one IEFACTRT line
# carrying the step name, the program and the return code. That is a
# better progress signal than anything the x86 side has, because it
# reports outcomes and not merely activity.
MVS_JOBS = ("BUZZ", "SUGR", "ONFTX04", "ONFPRUN", "ONFERUN", "ONFJRUN")


def _tk5_log():
    root = os.environ.get("ONFLY_TK5", r"C:\hercules-lab\mvs-tk5")
    path = os.path.join(root, "log", "hardcopy.log")
    return path if os.path.isfile(path) else None


def mvs_jobs(tail_bytes=400000):
    """Any ONFLY job MVS has started and not yet ended.

    Read from the end of the console log, because it grows without bound
    and only the recent part can matter. A job is "running" when its
    $HASP373 START has been seen and no $HASP395 ENDED follows it.

    The log is opened with FileShare.ReadWrite semantics implicitly --
    Python's read mode does not lock -- which matters because Hercules
    holds the file open for writing the whole time.
    """
    path = _tk5_log()
    if not path:
        return []
    try:
        size = os.path.getsize(path)
        with io.open(path, "rb") as fh:
            if size > tail_bytes:
                fh.seek(size - tail_bytes)
            text = fh.read().decode("latin-1", "replace")
    except Exception:
        return []

    state = {}
    for line in text.splitlines():
        m = re.search(r"\$HASP373 (\S+)\s+STARTED", line)
        if m and m.group(1) in MVS_JOBS:
            state[m.group(1)] = {"job": m.group(1), "steps": [],
                                 "started_txt": _clock(line),
                                 "ended": False, "alloc": None}
            continue
        m = re.search(r"\$HASP395 (\S+)\s+ENDED", line)
        if m and m.group(1) in state:
            state[m.group(1)]["ended"] = True
            continue
        m = re.search(r"IEF236I ALLOC\. FOR (\S+)\s+(\S+)", line)
        if m and m.group(1) in state:
            state[m.group(1)]["alloc"] = m.group(2)
            continue
        # IEFACTRT: "<JOB>   <STEP>   <PROGRAM>   RC= nnnn"
        m = re.search(r"\s(\S+)\s+(\S+)\s+(\S+)\s+RC=\s*(\d+)\s*$", line)
        if m and m.group(1) in state:
            state[m.group(1)]["steps"].append(
                (m.group(2), m.group(3), int(m.group(4))))
    return [v for v in state.values() if not v["ended"]]


def _clock(line):
    m = re.search(r"\s(\d?\d\.\d\d\.\d\d)\s", line)
    return m.group(1).replace(".", ":") if m else "?"


_HERC = {"cpu": None, "at": None}


def herc_rate():
    """Fraction of one core Hercules has used since the last call.

    The liveness signal for an MVS job, because the obvious one is
    absent: an MVS STEP2 can run forty minutes without MVS printing a
    line, so a step list that has not changed looks exactly like a job
    that has died.  About one core means the simulation is running.

    The CPU figure comes from the shared snapshot's KernelModeTime plus
    UserModeTime (D-335), not from a PowerShell spawn of its own.  Same
    clock mvsprf.trust() certifies ACC-6 on, used here only to answer
    "is it doing anything", never to time anything.
    """
    now, cpu = _now(), None
    for pr in _snapshot():
        if pr["name"].lower().startswith("hercules"):
            cpu = pr["cpu"]
            break
    prev, prev_at = _HERC["cpu"], _HERC["at"]
    _HERC["cpu"], _HERC["at"] = cpu, now
    if cpu is None or prev is None or prev_at is None:
        return None
    span = now - prev_at
    return ((cpu - prev) / span) if span > 0.5 else None

def render_mvs(jobs):
    lines = []
    rate = herc_rate()
    for j in jobs:
        lines.append("%s on TK5 (MVS 3.8j under Hercules) -- started %s "
                     "guest time" % (j["job"], j["started_txt"]))
        if j["steps"]:
            lines.append("  steps finished:")
            for name, prog, rc in j["steps"]:
                flag = "ok " if rc == 0 else ("warn" if rc == 4
                                              else "ERR ")
                lines.append("    %s %-9s %-9s COND CODE %04d"
                             % (flag, name, prog, rc))
        worst = max([rc for _n, _p, rc in j["steps"]] or [0])
        if j["alloc"] and not any(s[0] == j["alloc"] for s in j["steps"]):
            lines.append("  now running: %s (allocated, not yet finished)"
                         % j["alloc"])
        lines.append("  %d step(s) done, worst COND CODE %04d so far"
                     % (len(j["steps"]), worst))
        if rate is None:
            lines.append("  (Hercules CPU not sampled yet -- the next "
                         "refresh will show whether it is computing)")
        elif rate >= 0.70:
            lines.append("  Hercules is using %.0f%% of a core, so the "
                         "step IS running" % (rate * 100.0))
            lines.append("  -- MVS prints nothing during a step, so a "
                         "still step list is normal.")
        else:
            lines.append("  *** Hercules is using only %.0f%% of a core. "
                         "The step may be stalled," % (rate * 100.0))
            lines.append("  or the host may have stopped executing the "
                         "guest.")
        lines.append("  read from the Hercules console log; MVS reports "
                     "each step as it completes,")
        lines.append("  so these are outcomes, not activity.")
    return lines


def render_mvs_brief(jobs):
    out = []
    for j in jobs:
        worst = max([rc for _n, _p, rc in j["steps"]] or [0])
        cur = j["alloc"] if (j["alloc"] and not any(
            s[0] == j["alloc"] for s in j["steps"])) else "?"
        out.append("%s on TK5: %d steps done, now in %s, worst COND CODE "
                   "%04d, started %s guest time"
                   % (j["job"], len(j["steps"]), cur, worst,
                      j["started_txt"]))
    return out


def _opt(argv, name):
    for i, a in enumerate(argv):
        if a == name and i + 1 < len(argv):
            return argv[i + 1]
        if a.startswith(name + "="):
            return a.split("=", 1)[1]
    return None


def _params(label):
    """Parameters of the running job for `label`, read from its argv."""
    for job in _running_jobs():
        argv = job["argv"]
        got = _opt(argv, "--variant") or "d52"
        if got != label:
            continue
        ws = _opt(argv, "--w-syn")
        rates = _opt(argv, "--rates") or "40,60,120"
        seeds = _opt(argv, "--seeds") or "4"
        if not ws:
            continue
        try:
            return {"w_syn": [float(x) for x in ws.split(",")],
                    "rates_list": [int(x) for x in rates.split(",")],
                    "rates": len(rates.split(",")),
                    "seeds": int(seeds), "started": job["started"]}
        except ValueError:
            continue
    return None


def _known_points(label):
    """The W_syn list a PREVIOUS run of this label used, or None.

    Only a completed run records its points, so this answers "point i of
    n" when one exists and declines to guess when none does.  Inferring
    n from a single file on disk would be inventing it.
    """
    for name in sorted(os.listdir(CALDIR)) if os.path.isdir(CALDIR) else []:
        if not (name.startswith("wsens-%s-" % label)
                and name.endswith(".json")):
            continue
        try:
            d = json.loads(io.open(os.path.join(CALDIR, name),
                                   encoding="utf-8").read())
            pts = [p["w_syn"] for p in d.get("points", [])]
            if pts:
                return sorted(pts)
        except Exception:
            continue
    return None


def infer():
    """Coarse progress for candidate runs that left no status file.

    A W_syn point emits `net-<label>-<w>.bin` and deletes it when the
    point is done (prep/calibrate.py emit_candidate), so exactly one
    exists while a point is running and its name says which point.
    """
    out = []
    if not os.path.isdir(CALDIR):
        return out
    # Queried once.  It is a host-wide count and cannot be attributed to
    # a particular job anyway, so asking per candidate would be slower
    # and no more informative.
    workers = _worker_count()

    # A JOB is a process, not a file.  Keying this off the network on
    # disk alone reported "no jobs running" in the gap between two W_syn
    # points -- the previous network is deleted as soon as its runs
    # finish and the next takes about 76 s to emit -- so a four-hour run
    # looked finished twice an hour.  Saying nothing is running while
    # something is, is the worst thing this tool can do, so the process
    # list is the spine and the file only says which point.
    on_disk = {}
    for name in sorted(os.listdir(CALDIR)):
        if name.startswith("net-") and name.endswith(".bin"):
            stem = name[len("net-"):-len(".bin")]
            lab, wt = (stem.rsplit("-", 1) if "-" in stem
                       else ("calibration", stem))
            on_disk[lab] = (wt, os.path.join(CALDIR, name))

    seen = set()
    for job in _running_jobs():
        label = _opt(job["argv"], "--variant") or "d52"
        seen.add(label)
        par = _params(label)
        wtxt, path = on_disk.get(label, (None, None))
        since = None
        if path:
            try:
                since = os.path.getmtime(path)
            except OSError:
                since = None
        idx = None
        if wtxt and par:
            try:
                idx = (par["w_syn"].index(float(wtxt)) + 1,
                       len(par["w_syn"]))
            except ValueError:
                idx = None
        out.append({"job": "wsens-%s" % label, "inferred": True,
                    "w_syn": wtxt, "point": idx,
                    "since": since if since else job["started"],
                    "between": wtxt is None, "params": par,
                    "workers": workers, "stale": False})

    for name in sorted(os.listdir(CALDIR)):
        if not (name.startswith("net-") and name.endswith(".bin")):
            continue
        stem = name[len("net-"):-len(".bin")]
        if "-" in stem:
            label, wtxt = stem.rsplit("-", 1)
        else:
            label, wtxt = "calibration", stem
        path = os.path.join(CALDIR, name)
        try:
            since = os.path.getmtime(path)
        except OSError:
            continue
        # Only files with no running job reach here: those are leftovers.
        if label in seen:
            continue
        out.append({"job": "wsens-%s" % label, "inferred": True,
                    "w_syn": wtxt, "point": None, "since": since,
                    "between": False, "params": None,
                    "workers": workers, "stale": True})
    return out


def _shape(it):
    """Plain-English progress for an inferred job.

    Returns (sentence, detail) where detail may be "".

    Honest about the one thing it cannot know: how far through the
    CURRENT point the job is. Points completed are known exactly, from
    the W_syn list and which network is on disk. Within a point, nothing
    outside the process can see how many of its runs are done -- so
    until one point has finished there is no measured rate to project
    from, and the tool says so rather than inventing a percentage.
    """
    par, idx = it.get("params"), it.get("point")
    if not par or not idx:
        return ("still working", "")
    i, n = idx
    per_point = par["rates"] * par["seeds"]
    total = per_point * n
    done_points = i - 1
    elapsed = _now() - par["started"]
    if done_points <= 0:
        return ("on the first of %d points, %d runs each (%d in total)"
                % (n, per_point, total),
                "no point has finished yet, so there is nothing measured "
                "to estimate the finish from")
    rate = elapsed / float(done_points)          # seconds per point
    left = rate * (n - done_points) - (_now() - it["since"])
    pct = 100.0 * done_points / n
    return ("%d of %d points done (%.0f%% of %d runs)"
            % (done_points, n, pct, total),
            "about %s left, measured from the %s each finished point has "
            "taken" % (_dur(max(left, 0)), _dur(rate)))


# The longest W_syn point ever measured is 2,777 s (VL-103, 30 seeds at
# --jobs 16).  Three times that is comfortably beyond any real point and
# well short of "left over from yesterday".
STALE_AFTER_S = 3 * 2777


def _is_stale(since, workers):
    """Is this file a leftover rather than a point in progress?

    Two independent signs, either of which is enough:

      * no `runnet` process is alive anywhere, so nothing is running;
      * the file is older than any W_syn point has ever taken.

    This check exists because the first version of infer() did not have
    it and reported a 299 MB network ACC-4 abandoned 15.8 hours earlier
    as a job that was 15.8 hours into its current point.  Presenting a
    leftover as live work is worse than reporting nothing: it is the one
    failure mode that would make this tool untrustworthy, since the
    reader has no way to tell the two apart from the output.
    """
    if workers == 0:
        return True
    return (_now() - since) > STALE_AFTER_S


def render_inferred(items):
    lines = []
    for it in items:
        pt = ("point %d of %d" % it["point"]) if it["point"] \
            else "point (total unknown)"
        if it["stale"]:
            lines.append("%-16s LEFTOVER -- not running" % it["job"])
            lines.append("    net-...-%s.bin, last written %s ago; no "
                         "W_syn point has ever taken that long"
                         % (it["w_syn"], _dur(_now() - it["since"])))
            lines.append("    299 MB; safe to delete once no run wants it")
            continue
        par = it.get("params")
        label = it["job"][len("wsens-"):]
        ins = _inside(label, par)
        if it.get("between"):
            lines.append("%s -- between W_syn points, emitting the next "
                         "network (about 76 s), running %s"
                         % (it["job"],
                            _dur(_now() - (par["started"] if par
                                           else it["since"]))))
            if par:
                lines.append("  started %s" % _iso(par["started"]))
            continue
        lines.append("%s -- W_syn %s, %s, running %s"
                     % (it["job"], it["w_syn"], pt,
                        _dur(_now() - (par["started"] if par
                                       else it["since"]))))
        if ins:
            i, n = it["point"] if it["point"] else (1, 1)
            total = ins["per_point"] * n
            gdone = (i - 1) * ins["per_point"] + ins["done"]
            lines.append("")
            lines.append("  inside this point (%d runs):" % ins["per_point"])
            for rate in sorted(ins["by_rate"]):
                seeds = sorted(ins["by_rate"][rate])
                bar = _bar(max(seeds), par["seeds"], 20)
                lines.append("    %5d Hz  %s  seeds %s"
                             % (rate, bar,
                                ", ".join(str(x) for x in seeds)))
            ratesl = par["rates_list"]
            cur = max(ins["by_rate"])
            lines.append("    rate %d Hz is %d of %d for this point"
                         % (cur, ratesl.index(cur) + 1, len(ratesl)))
            lines.append("    %d dispatched, %d finished, %d still "
                         "computing"
                         % (ins["dispatched"], ins["done"],
                            ins["in_flight"]))
            lines.append("")
            lines.append("  whole run: %s %d of %d runs finished"
                         % (_bar(gdone, total, 24), gdone, total))
        else:
            lines.append("  no workers are running for this job right now")
        if par:
            lines.append("  started %s" % _iso(par["started"]))
        lines.append("  read from the process table: every worker is one "
                     "`runnet <net> <rate> <ms> <seed>`,")
        lines.append("  so 'dispatched' is exact and 'finished' is "
                     "dispatched minus those still alive.")
    return lines


def render_brief(states, items):
    """One line per job, for a status bar or a watch loop."""
    out = []
    for st in states:
        done, total = st.get("done") or 0, st.get("total")
        pct = ("%d%%" % round(100.0 * done / total)) if total else "?%"
        out.append("%s: %s %s/%s, %s elapsed, eta %s%s"
                   % (st.get("job", "?"), pct, done,
                      total if total is not None else "?",
                      _dur(st["updated_at"] - st["started_at"]),
                      _dur(_eta(st)),
                      "" if st.get("status") == "running"
                      else " [%s]" % st.get("status")))
    for it in items:
        if it["stale"]:
            out.append("%s: LEFTOVER net-...-%s.bin, %s old, not running"
                       % (it["job"], it["w_syn"],
                          _dur(_now() - it["since"])))
            continue
        # One line, so it says position, elapsed and what is left -- and
        # nothing else.  The long explanation belongs in the full form.
        par = it.get("params")
        el = _now() - (par["started"] if par else it["since"])
        label = it["job"][len("wsens-"):]
        ins = _inside(label, par) if par else None
        if it["point"] and par and ins:
            i, n = it["point"]
            total = ins["per_point"] * n
            done = (i - 1) * ins["per_point"] + ins["done"]
            cur = max(ins["by_rate"])
            # Projected from RUNS finished, not from points finished, so
            # there is an estimate within the first point instead of
            # after it.
            left = (_dur(el * (total - done) / float(done))
                    if done > 0 else "unknown")
            out.append("%s: %d of %d runs done (%.0f%%), point %d of %d "
                       "at W_syn %s, now on %d Hz seeds %s, %s elapsed, "
                       "about %s left"
                       % (it["job"], done, total, 100.0 * done / total,
                          i, n, it["w_syn"], cur,
                          "-".join(str(x) for x in
                                   (min(ins["by_rate"][cur]),
                                    max(ins["by_rate"][cur]))),
                          _dur(el), left))
        elif it.get("between"):  # noqa: E501 - kept adjacent to its twin
            out.append("%s: between W_syn points, emitting the next "
                       "network, %s elapsed" % (it["job"], _dur(el)))
        else:
            out.append("%s: W_syn %s, %s elapsed, no workers running"
                       % (it["job"], it["w_syn"], _dur(el)))
    # No placeholder here.  MVS lines are appended by the caller, and a
    # "no jobs running" emitted from this side printed directly above a
    # TK5 job that was plainly running.  The caller decides when there is
    # genuinely nothing, because only the caller sees every source.
    return out


def read_all():
    out = []
    if not os.path.isdir(DIR):
        return out
    for name in sorted(os.listdir(DIR)):
        if not name.endswith(".json"):
            continue
        try:
            out.append(json.loads(io.open(
                os.path.join(DIR, name), encoding="utf-8").read()))
        except Exception:
            # A file being replaced, or a truncated one. Skip it this
            # pass rather than crash the watcher; the next pass will
            # read the completed replacement.
            continue
    return out


def render(states):
    if not states:
        return ["progress: no jobs have reported (data/progress is empty)"]
    lines = []
    for st in states:
        done, total = st.get("done") or 0, st.get("total")
        pct = ("%3d%%" % round(100.0 * done / total)) if total else "  ? "
        alive = (_now() - st.get("updated_at", 0)) < 300
        status = st.get("status", "?")
        if status == "running" and not alive:
            status = "running?"          # no tick in 5 minutes
        lines.append("%-16s %s %s  %s/%s %s"
                     % (st.get("job", "?"), _bar(done, total), pct, done,
                        total if total is not None else "?",
                        st.get("unit", "")))
        lines.append("    status %-9s elapsed %-7s eta %-7s pid %s"
                     % (status, _dur(st["updated_at"] - st["started_at"]),
                        _dur(_eta(st)), st.get("pid", "?")))
        if st.get("stage"):
            sd, stt = st.get("stage_done") or 0, st.get("stage_total")
            lines.append("    stage  %s  %s/%s"
                         % (st["stage"], sd,
                            stt if stt is not None else "?"))
        if st.get("note"):
            lines.append("    %s" % "  ".join(
                "%s=%s" % (k, v) for k, v in sorted(st["note"].items())))
        if st.get("log"):
            lines.append("    what each run returned:")
            for ln in st["log"][-14:]:
                lines.append("      %s" % ln)
        lines.append("    last update %s" % _iso(st.get("updated_at", 0)))
    return lines


BANNER = "=" * 66

# --- the live event log ---------------------------------------------
#
# A summary says how far along a job is. It does not let you watch it
# work. This does: every poll diffs the set of live workers against the
# previous one, so a run appearing is a start and a run vanishing is a
# finish, and each is stamped with the wall-clock time it happened.
#
# The one thing it CANNOT show for an already-running job is the MN9
# numbers each run produced. Those go from the worker's stdout straight
# into the parent's memory and are written only when the whole job ends
# -- so for a job already in flight there is nowhere to read them from.
# A job started after this exists records them through the tracker.
EVENTS = []
EVENT_MAX = 400


def _event(text):
    EVENTS.append((_now(), text))
    if len(EVENTS) > EVENT_MAX:
        del EVENTS[:len(EVENTS) - EVENT_MAX]


def poll_events(prev):
    """Diff the live worker set and log what changed.

    `prev` maps pid -> (label, rate, seed, first_seen). Returns the new
    map. Durations are measured from when this watcher first saw the
    worker, so a run already in flight when the watcher started is
    reported as "(started before watching)" rather than given a wrong
    duration.
    """
    cur = {}
    for w in _workers():
        key = w["pid"]
        if key in prev:
            cur[key] = prev[key]
        else:
            cur[key] = (w["label"], w["rate"], w["seed"], _now())
            _event("start   %-10s %5d Hz  seed %3d"
                   % (w["label"], w["rate"], w["seed"]))
    for pid, (label, rate, seed, t0) in prev.items():
        if pid not in cur:
            _event("FINISH  %-10s %5d Hz  seed %3d   after %s"
                   % (label, rate, seed, _dur(_now() - t0)))
    return cur


def render_events(n=14):
    if not EVENTS:
        return ["  (no run has started or finished since watching began)"]
    return ["  %s  %s" % (time.strftime("%H:%M:%S", time.localtime(t)),
                          text)
            for t, text in EVENTS[-n:]]


def _finished_banner(seen, started):
    """What the watcher prints when the job it was watching is gone.

    The window is NOT closed and the watcher does not vanish: a tracker
    that disappears at the moment the result arrives is a tracker you
    have to have been looking at. It prints, then stops, and the shell
    it was spawned in is started with -NoExit so the text survives.
    """
    lines = [BANNER, "JOB FINISHED", BANNER]
    for job in sorted(seen):
        lines.append("  %s" % job)
    if started:
        lines.append("  watched for %s, ended %s"
                     % (_dur(_now() - started), _iso(_now())))
    # Name the results file if the run wrote one, so the next step does
    # not begin with hunting for it.
    if os.path.isdir(CALDIR):
        recent = []
        for name in sorted(os.listdir(CALDIR)):
            if not (name.startswith("wsens-") and name.endswith(".json")):
                continue
            path = os.path.join(CALDIR, name)
            try:
                age = _now() - os.path.getmtime(path)
            except OSError:
                continue
            if age < 3600:
                recent.append((age, name))
        for age, name in sorted(recent):
            lines.append("  wrote data/calibration/%s (%s ago)"
                         % (name, _dur(age)))
    lines.append("")
    lines.append("  This window stays open. Close it when you are done.")
    lines.append(BANNER)
    return lines


def spawn_window():
    """Open a terminal in this worktree, watching until the job ends.

    Deliberately a SEPARATE window rather than a background thread: the
    point is a thing the owner can look at without asking anyone, and it
    has to outlive whatever shell launched the job.

    -NoExit keeps the shell alive after the watcher stops, so the
    JOB FINISHED banner is still on screen hours later.
    """
    import subprocess as sp
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(here)
    inner = ("cd '%s'; python tools/progress.py --watch 15 --until-done"
             % root.replace("'", "''"))
    try:
        if os.name == "nt":
            sp.Popen(["powershell", "-NoProfile", "-Command",
                      "Start-Process", "powershell",
                      "-ArgumentList", "'-NoExit','-NoProfile',"
                      "'-Command',\"%s\"" % inner.replace('"', '`"')])
        else:
            # No single answer on POSIX; try the common terminals and
            # say so plainly if none is present rather than failing
            # silently.
            for term in ("x-terminal-emulator", "gnome-terminal",
                         "xterm"):
                try:
                    sp.Popen([term, "-e", "bash", "-lc",
                              "cd '%s' && python3 tools/progress.py "
                              "--watch 15 --until-done; exec bash"
                              % root])
                    break
                except OSError:
                    continue
            else:
                print("no terminal emulator found; run this yourself:")
                print("  cd '%s' && python tools/progress.py "
                      "--watch 15 --until-done" % root)
                return 1
        print("progress window opened, watching until the job finishes")
        return 0
    except Exception as exc:
        print("could not open a window: %s" % exc)
        print("run this yourself:")
        print("  cd '%s'" % root)
        print("  python tools/progress.py --watch 15 --until-done")
        return 1


def main(argv):
    if "--window" in argv:
        return spawn_window()
    watch = "--watch" in argv
    until_done = "--until-done" in argv
    if until_done:
        watch = True
    brief = "--brief" in argv
    every = 5.0
    for i, a in enumerate(argv):
        if a == "--watch" and i + 1 < len(argv):
            try:
                every = float(argv[i + 1])
            except ValueError:
                pass
    seen, watch_started = set(), _now()
    prev_workers = {}
    while True:
        prev_workers = poll_events(prev_workers)
        states = read_all()
        # Inference is a FALLBACK, not a supplement: a job that reports
        # for itself is not also guessed at, or the same run would be
        # listed twice saying two different things.
        # A job that reports for itself must not ALSO be inferred.
        #
        # Exact-name matching was not enough: a tracked job is filed as
        # `wsens-right-s30` (the seed count is part of the name, D-315)
        # while inference derives `wsens-right` from the network on disk,
        # so the same run appeared twice under two names saying two
        # different things -- one of them with no ETA.  Matching on the
        # prefix is what makes them one job.
        reported = set(st.get("job") or "" for st in states)
        items = [it for it in infer()
                 if not any(r == it["job"] or r.startswith(it["job"] + "-")
                            for r in reported)]
        mvs = mvs_jobs()
        if brief:
            rows = render_brief(states, items) + render_mvs_brief(mvs)
            text = "\n".join(rows or ["no jobs running"])
        else:
            lines = []
            if states:
                lines += render(states)
            if items:
                lines += render_inferred(items)
            if mvs:
                if lines:
                    lines.append("")
                lines += render_mvs(mvs)
            if not lines:
                lines = ["progress: nothing running, and nothing on disk "
                         "to infer from"]
            # The run log is x86-only: it is built by diffing `runnet`
            # worker processes, and an MVS job has none.  Showing it for
            # a TK5-only screen printed "(no run has started or finished
            # since watching began)" under a job that was using 100% of
            # a core -- which reads as nothing happening.  An empty
            # section that is empty BY CONSTRUCTION is worse than no
            # section, so it appears only when there is x86 work for it
            # to describe.
            if watch and (states or items or EVENTS):
                lines.append("")
                lines.append("  live run log (each line is one "
                             "full-brain run on x86):")
                lines += render_events()
            text = "\n".join(lines)
        # A job counts as "seen" only while it is genuinely working: a
        # tracker whose status file says finished, or a leftover file on
        # disk, must not make the watcher wait for something that has
        # already ended.
        live = set()
        for st in states:
            if st.get("status") == "running":
                live.add(st.get("job"))
        for it in items:
            if not it.get("stale"):
                live.add(it.get("job"))
        for j in mvs:
            live.add("%s (TK5)" % j["job"])
        seen |= live

        if watch:
            sys.stdout.write("\x1b[2J\x1b[H")
        sys.stdout.write(text + "\n")
        sys.stdout.flush()
        if not watch:
            return 0
        if until_done and seen and not live:
            sys.stdout.write("\n"
                             + "\n".join(_finished_banner(seen,
                                                          watch_started))
                             + "\n")
            sys.stdout.flush()
            return 0
        time.sleep(every)


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except KeyboardInterrupt:
        sys.exit(0)
