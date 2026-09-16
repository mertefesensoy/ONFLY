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


def _worker_count():
    """Live `runnet` processes, or None if it cannot be determined.

    Matched on the process NAME.  Deliberately not `pgrep -f runnet`:
    -f matches whole command lines and the shell running the search
    contains the pattern, so it finds itself and reports a worker that
    is the search.  That produced a contradictory reading during the
    2026-09-15 lab shutdown; it is avoided here rather than rediscovered.
    """
    import subprocess as sp
    try:
        if os.name == "nt":
            out = sp.run(["tasklist", "/FI", "IMAGENAME eq runnet.exe",
                          "/NH"], stdout=sp.PIPE, stderr=sp.DEVNULL,
                         timeout=30).stdout.decode("ascii", "replace")
            return sum(1 for ln in out.splitlines()
                       if ln.strip().lower().startswith("runnet"))
        out = sp.run(["pgrep", "-c", "-x", "runnet"], stdout=sp.PIPE,
                     stderr=sp.DEVNULL, timeout=30).stdout
        return int(out.decode("ascii", "replace").strip() or 0)
    except Exception:
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
        pts = _known_points(label)
        idx = None
        if pts:
            try:
                idx = (pts.index(float(wtxt)) + 1, len(pts))
            except ValueError:
                idx = None
        out.append({"job": "wsens-%s" % label, "inferred": True,
                    "w_syn": wtxt, "point": idx, "since": since,
                    "workers": workers, "stale": _is_stale(since, workers)})
    return out


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
        lines.append("%-16s INFERRED -- no status file"
                     % it["job"])
        lines.append("    W_syn %s, %s" % (it["w_syn"], pt))
        lines.append("    at this point for %s"
                     % _dur(_now() - it["since"]))
        lines.append("    %s runnet workers alive on this HOST -- the "
                     "count is not attributable to one job"
                     % (it["workers"] if it["workers"] is not None
                        else "?"))
        lines.append("    read from the emitted network on disk and the "
                     "process table, not from the job")
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
        pt = ("point %d/%d" % it["point"]) if it["point"] else "point ?"
        out.append("%s: %s (W_syn %s), %s at this point, %s host workers,"
                   " INFERRED"
                   % (it["job"], pt, it["w_syn"],
                      _dur(_now() - it["since"]),
                      it["workers"] if it["workers"] is not None else "?"))
    return out or ["no jobs running"]


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
        lines.append("    last update %s" % _iso(st.get("updated_at", 0)))
    return lines


def main(argv):
    watch = "--watch" in argv
    brief = "--brief" in argv
    every = 5.0
    for i, a in enumerate(argv):
        if a == "--watch" and i + 1 < len(argv):
            try:
                every = float(argv[i + 1])
            except ValueError:
                pass
    while True:
        states = read_all()
        # Inference is a FALLBACK, not a supplement: a job that reports
        # for itself is not also guessed at, or the same run would be
        # listed twice saying two different things.
        reported = set(st.get("job") for st in states)
        items = [it for it in infer() if it["job"] not in reported]
        if brief:
            text = "\n".join(render_brief(states, items))
        else:
            lines = []
            if states:
                lines += render(states)
            if items:
                lines += render_inferred(items)
            if not lines:
                lines = ["progress: nothing running, and nothing on disk "
                         "to infer from"]
            text = "\n".join(lines)
        if watch:
            sys.stdout.write("\x1b[2J\x1b[H")
        sys.stdout.write(text + "\n")
        sys.stdout.flush()
        if not watch:
            return 0
        time.sleep(every)


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except KeyboardInterrupt:
        sys.exit(0)
