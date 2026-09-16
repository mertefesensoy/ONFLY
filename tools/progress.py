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
    every = 5.0
    for i, a in enumerate(argv):
        if a == "--watch" and i + 1 < len(argv):
            try:
                every = float(argv[i + 1])
            except ValueError:
                pass
    while True:
        text = "\n".join(render(read_all()))
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
