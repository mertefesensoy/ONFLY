# -*- coding: utf-8 -*-
"""The Phase G live view: three coupled panels (D-345, P-21 Stage 4).

WHAT THIS IS
------------
A fly tastes sugar, and you watch it decide to eat.  The 14 sugar-sensing
GRNs fire, the signal crosses the subesophageal zone, and the MN9 motor
neurons that drive proboscis extension spike.  501 real neurons at real soma
positions, inside a faint cloud of the whole annotated CNS.

Three panels share one clock (D-345):

    anatomy   neurons at soma positions; a spike lights one and it decays
    raster    neuron index against time, filling left to right
    MN9       membrane potential climbing toward threshold, with u_th drawn

The third is the one that shows *why* a spike happens rather than only that
it did.

WHY IT IS LIVE, AND NOT A REPLAY
--------------------------------
D-128 ruled out both alternatives: one request per frame, and a recorded
trace played back afterwards.  So this launches ONFLYENG itself and follows
the ONFSTM dataset AS IT IS WRITTEN -- the engine flushes after every chunk
(IR-STM-04) and this reads whatever has arrived.  It never waits for the
process to exit.

That is measured rather than asserted: the run reports when the first frame
was drawn and when the engine exited, and the first number is smaller.

WHAT IS DRAWN IS WHAT WAS COMPUTED
----------------------------------
Nothing here re-simulates anything.  Every spike and every membrane value
comes from the engine's own stream, and tests/test_strm.py (TU-11) checks
that those agree with the response records and, for the membrane, with the
oracle bit for bit.  A picture is not evidence; that test is what makes this
picture mean something.

HONESTY IN THE DRAWING
----------------------
  * 19 of 501 soma positions are imputed (D-384) and are drawn as hollow
    rings, never as measured dots.  All 14 stimulus neurons are among them:
    GRN cell bodies are peripheral and outside the imaged volume, so they are
    shown where their axon terminals are.
  * Positions are somata, not neurites.  This is where the cells sit, not
    what they look like.
  * Stimulus and readout neurons carry distinct MARKERS and text labels, so
    colour is never the only encoding.
  * The projection is the one prep/geom.py measured from independent labels
    (somaNeuromere, somaSide), not an assumed axis order.

Run:
    python tools/liveview.py --engine build/onflyeng_nat.exe
    python tools/liveview.py --engine build/onflyeng_nat.exe --save out.gif
    python tools/liveview.py --rate 40 --ms 60 --k 5 --order index

The two clips D-388 records, both reproducible with one command each:

    make clips
"""
import json
import os
import subprocess
import struct
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import goldfp                                      # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

GEOM = os.path.join(ROOT, "data", "geom", "srext-geom.json")
BACKDROP = os.path.join(ROOT, "data", "geom", "backdrop.csv")
NETDIR = os.path.join(ROOT, "data", "networks")
NETFILE = os.path.join(NETDIR, "onfnet-malecns-v1.0-srext.bin")

#: D-376.  10,000 steps at dt=100us in chunks of 50 is 200 frames.
K_DEMO = 50

#: How fast a lit neuron fades, per frame.  Long enough to see a wave cross
#: the SEZ, short enough that the anatomy panel does not saturate.
DECAY = 0.55


class ViewError(Exception):
    pass


def load_geometry():
    if not os.path.exists(GEOM):
        raise ViewError("no geometry at %s\n  run: python prep/geom.py"
                        % GEOM)
    doc = json.loads(open(GEOM, "r").read())
    cloud = []
    if os.path.exists(BACKDROP):
        for line in open(BACKDROP, "r"):
            if line.startswith("#") or line.startswith("bodyId"):
                continue
            parts = line.split(",")
            if len(parts) == 4:
                cloud.append((int(parts[1]), int(parts[2]),
                              int(parts[3])))
    return doc, cloud


def project(doc, points):
    """Anatomical (horizontal, vertical) for a list of (x, y, z).

    The axes come from prep/geom.py's measurement, not from an assumed order,
    and the vertical is flipped when the brain is at the low end so that the
    brain is drawn above the nerve cord."""
    p = doc["projection"]
    axis = {"x": 0, "y": 1, "z": 2}
    h, v = axis[p["side_axis"]], axis[p["body_axis"]]
    sign = -1.0 if p["brain_at_low_end"] else 1.0
    return ([pt[h] for pt in points],
            [sign * pt[v] for pt in points])


def start_engine(engine, netpath, rate, ms, seed, k, tmp):
    """Launch ONFLYENG on one request and return (process, stream path)."""
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import mkreq
    reqpath = os.path.join(tmp, "live.req")
    with open(reqpath, "wb") as fh:
        fh.write(mkreq.pack("SUGR", rate, ms, seed))
    rsppath = os.path.join(tmp, "live.rsp")
    stmpath = os.path.join(tmp, "live.stm")
    argv = [os.path.abspath(engine), "STREAM=%d" % k, netpath,
            reqpath, rsppath, stmpath]
    proc = subprocess.Popen(argv, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT)
    return proc, stmpath, rsppath


class Tail(object):
    """Complete lines from a file that is still being written.

    A partial line is held back until its newline arrives.  Without that the
    viewer would occasionally parse half a chunk, which would not crash --
    it would draw something subtly wrong, which is worse."""

    def __init__(self, path):
        self.path = path
        self.fh = None
        self.buf = ""

    def lines(self):
        if self.fh is None:
            if not os.path.exists(self.path):
                return []
            self.fh = open(self.path, "r")
        self.buf += self.fh.read()
        if "\n" not in self.buf:
            return []
        parts = self.buf.split("\n")
        self.buf = parts.pop()
        return parts

    def close(self):
        if self.fh is not None:
            self.fh.close()
            self.fh = None


def unpack_f64(word):
    return struct.unpack(">d", bytes.fromhex(word))[0]


def run(args):
    import matplotlib
    if args["save"]:
        matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D

    doc, cloud = load_geometry()
    rows = doc["neurons"]
    n = len(rows)
    pts = [(r["x"], r["y"], r["z"]) for r in rows]
    gx, gy = project(doc, pts)
    cx, cy = project(doc, cloud) if cloud else ([], [])

    stim = [r["index"] for r in rows if r["role"] == "stimulus"]
    readout = [r["index"] for r in rows if r["role"] == "readout"]
    imputed = [r["index"] for r in rows if r["placed"]]

    tmp = tempfile.mkdtemp(prefix="onfly-live-")
    t0 = time.time()
    follow = args["follow"] is not None
    if follow:
        # Nothing is launched.  The producer is elsewhere -- a TK5 job under
        # tools/mvsstm.py -- and this only reads what arrives.
        proc, stmpath, rsppath = None, args["follow"], None
    else:
        proc, stmpath, rsppath = start_engine(
            args["engine"], args["network"], args["rate"], args["ms"],
            args["seed"], args["k"], tmp)

    fig = plt.figure(figsize=(12.0, 6.4))
    fig.patch.set_facecolor("#0b0d12")
    # The fingerprint panel appears only when a stream is being followed.
    # An x86 run has nothing to compare itself against, and adding an empty
    # panel to it would change the two clips D-388 records.
    if follow:
        ax_a = fig.add_axes([0.02, 0.26, 0.40, 0.64])
        ax_f = fig.add_axes([0.02, 0.04, 0.40, 0.18])
    else:
        ax_a = fig.add_axes([0.02, 0.06, 0.40, 0.84])
        ax_f = None
    ax_r = fig.add_axes([0.48, 0.52, 0.50, 0.38])
    ax_m = fig.add_axes([0.48, 0.09, 0.50, 0.33])

    for ax in (ax_a, ax_r, ax_m):
        ax.set_facecolor("#0b0d12")
        for spine in ax.spines.values():
            spine.set_color("#2a3040")
        ax.tick_params(colors="#7f8aa3", labelsize=8)
        ax.xaxis.label.set_color("#9aa7c0")
        ax.yaxis.label.set_color("#9aa7c0")

    # --- anatomy -------------------------------------------------------
    if cx:
        ax_a.scatter(cx, cy, s=0.6, c="#1b2233", linewidths=0,
                     rasterized=True)
    base = ax_a.scatter(gx, gy, s=7, c="#33496a", linewidths=0, zorder=3)
    glow = ax_a.scatter(gx, gy, s=[0] * n, c="#ffd166", linewidths=0,
                        zorder=4)
    ax_a.scatter([gx[i] for i in imputed], [gy[i] for i in imputed],
                 s=30, facecolors="none", edgecolors="#6b7a99",
                 linewidths=0.7, zorder=5)
    ax_a.scatter([gx[i] for i in stim], [gy[i] for i in stim],
                 s=70, marker="^", facecolors="none",
                 edgecolors="#4cc9f0", linewidths=1.3, zorder=6)
    ax_a.scatter([gx[i] for i in readout], [gy[i] for i in readout],
                 s=150, marker="*", facecolors="none",
                 edgecolors="#f72585", linewidths=1.4, zorder=6)
    # A key rather than annotations on the points: the GRNs and MN9 both sit
    # in the SEZ, a few thousand units apart, so leader text placed at the
    # markers always collides at this scale.
    key = [Line2D([], [], linestyle="none", marker="^", markersize=8,
                  markerfacecolor="none", markeredgecolor="#4cc9f0",
                  label="sugar sensors (14, imputed)"),
           Line2D([], [], linestyle="none", marker="*", markersize=12,
                  markerfacecolor="none", markeredgecolor="#f72585",
                  label="MN9 readout (2)"),
           Line2D([], [], linestyle="none", marker="o", markersize=6,
                  markerfacecolor="#ffd166", markeredgecolor="none",
                  label="spiking now")]
    leg_a = ax_a.legend(handles=key, loc="upper right", fontsize=8,
                        facecolor="#11151f", edgecolor="#2a3040",
                        labelspacing=0.7, borderpad=0.7)
    for t in leg_a.get_texts():
        t.set_color("#9aa7c0")
    ax_a.set_xticks([])
    ax_a.set_yticks([])
    ax_a.set_title("MaleCNS v1.0 - 501 neurons at soma positions",
                   color="#d6deee", fontsize=10, pad=8)
    ax_a.text(0.01, 0.01,
              "somata, not neurites - %d of %d positions imputed (hollow)"
              % (len(imputed), n),
              transform=ax_a.transAxes, color="#5d6a85", fontsize=7.5)

    # --- raster --------------------------------------------------------
    # Which row a neuron occupies.  P-21 drew the raster against neuron
    # INDEX; D-387 changed the default to the measured body axis, brain at
    # top, because index order is an artefact of SR-EXT-03's extraction and
    # means nothing anatomically -- sorted down the body the same spikes read
    # as a wave crossing the animal.  --order index restores the other.
    # The axis is prep/geom.py's measurement, not an assumption.
    if args["order"] == "body":
        # Ascending, NOT descending: the projected vertical already has
        # the brain at the high end, and matplotlib draws slot 0 at the
        # bottom -- so sorting ascending is what puts the brain at the
        # top, which is what the axis label claims.
        order = sorted(range(n), key=lambda i: (gy[i], i))
        row = [0] * n
        for slot, i in enumerate(order):
            row[i] = slot
        ylab = "soma position  (brain at top, VNC below)"
    else:
        row = list(range(n))
        ylab = "neuron index"
    ax_r.set_xlim(0, args["ms"])
    ax_r.set_ylim(-2, n + 2)
    ax_r.set_ylabel(ylab, fontsize=9)
    ax_r.set_title("spike raster", color="#d6deee", fontsize=10, pad=6)
    for i in readout:
        ax_r.axhline(row[i], color="#f72585", linewidth=0.5, alpha=0.35)
    rast = ax_r.scatter([], [], s=1.1, c="#ffd166", linewidths=0,
                        alpha=0.55)
    rx, ry = [], []

    # --- MN9 trace -----------------------------------------------------
    ax_m.set_xlim(0, args["ms"])
    ax_m.set_xlabel("simulated time (ms)", fontsize=9)
    ax_m.set_ylabel("MN9 membrane (mV)", fontsize=9)
    ax_m.set_title("why it fires", color="#d6deee", fontsize=10, pad=6)
    traces, tx, ty = None, [], None
    thresh_line = None

    writer = None
    if args["save"]:
        from matplotlib.animation import PillowWriter
        writer = PillowWriter(fps=args["fps"])
        writer.setup(fig, args["save"], dpi=args["dpi"])

    # --- fingerprint panel (P-25 §3.4) ---------------------------------
    # The only part of this picture that is evidence rather than
    # illustration.  The x86 column is SRS Section 8.4's recorded value out
    # of tools/goldfp.py; the other column is the ONFSE fingerprint of the
    # stream being followed.  Nothing here is recomputed at draw time, and a
    # disagreement is DRAWN, in red, rather than dropped.
    fp_rows = []
    fp_text = None
    if ax_f is not None:
        ax_f.set_facecolor("#0b0d12")
        ax_f.set_xticks([])
        ax_f.set_yticks([])
        for spine in ax_f.spines.values():
            spine.set_color("#2a3040")
        ax_f.set_title("IR-COM-05 fingerprint  -  x86-64 golden against "
                       "this run", color="#d6deee", fontsize=10, pad=6)
        fp_text = ax_f.text(0.03, 0.88, "", transform=ax_f.transAxes,
                            color="#9aa7c0", fontsize=8.5, va="top",
                            family="monospace")

    def redraw_fp():
        if fp_text is None:
            return
        lines = ["%-5s %-6s %-9s %-9s %s"
                 % ("req", "rate", "golden", "this run", "verdict")]
        for r in fp_rows:
            lines.append("%-5s %-6s %-9s %-9s %s"
                         % (r["id"], r["rate"], r["gold"], r["fp"],
                            r["verdict"]))
        fp_text.set_text("\n".join(lines))
        bad = any(r["verdict"] != "AGREE" for r in fp_rows)
        fp_text.set_color("#ff5d5d" if bad else "#8ce99a")

    redraw_fp()

    tail = Tail(stmpath)
    head = None
    ro = []
    lit = [0.0] * n
    ucols = 0
    frames = 0
    saved = 0
    first_frame_at = None
    done = False
    nreq = 0
    last_data = time.time()

    while not done:
        got = tail.lines()
        if not got:
            if follow:
                # No process to poll.  The producer is a job elsewhere, so
                # the only two ways out are the request count being reached
                # and silence for longer than the caller allowed.
                if time.time() - last_data > args["timeout"]:
                    print("liveview: no new data for %d s, giving up after "
                          "%d of %d requests"
                          % (args["timeout"], nreq, args["requests"]))
                    break
                time.sleep(0.05)
                continue
            if proc.poll() is not None and not os.path.exists(stmpath):
                break
            time.sleep(0.004)
            continue
        last_data = time.time()
        for line in got:
            f = line.split()
            if not f:
                continue
            if f[0] == "ONFSH":
                head = {"n": int(f[2]), "nr": int(f[3]),
                        "dtus": int(f[4]), "k": int(f[5]),
                        "steps": int(f[6]), "seed": int(f[7]),
                        "rate": int(f[8])}
                # D-407: a followed stream carries five requests, so each
                # ONFSH starts a fresh picture rather than drawing the next
                # request on top of the last one's raster and trace.
                if traces is not None:
                    for tr in traces:
                        tr.remove()
                    lit = [0.0] * n
                    del ro[:]
                    ucols = 0
                    del rx[:]
                    del ry[:]
                    tx = []
                    ax_r.set_xlim(0, head["steps"] * head["dtus"] / 1000.0)
                    ax_m.set_xlim(0, head["steps"] * head["dtus"] / 1000.0)
                ty = [[] for _ in range(head["nr"])]
                traces = [ax_m.plot([], [], linewidth=1.2,
                                    color=c)[0]
                          for c in ("#f72585", "#b5179e")[:head["nr"]]]
            elif f[0] == "ONFSR":
                # D-413: ONFSR repeats until nr indices have arrived, so
                # this extends rather than replaces, and the labels are
                # only set once the line is complete.
                ro.extend(int(x) for x in f[1:])
                if len(ro) < head["nr"]:
                    continue
                for j, idx in enumerate(ro):
                    traces[j].set_label("neuron %d" % idx)
                leg = ax_m.legend(loc="upper left", fontsize=8,
                                  facecolor="#11151f",
                                  edgecolor="#2a3040")
                for t in leg.get_texts():
                    t.set_color("#9aa7c0")
            elif f[0] == "ONFSC" or f[0] == "ONFSD":
                # D-406.  ONFSD continues the ONFSC above it with the same
                # chunk and step, so the only differences are where the
                # pairs start and that the decay belongs to the chunk, not
                # to each of its lines -- applying it twice would dim a
                # spike that arrived on a continuation.
                step = int(f[2])
                ms = step * head["dtus"] / 1000.0
                if f[0] == "ONFSC":
                    for i in range(n):
                        lit[i] *= DECAY
                    pairs = f[4:]
                else:
                    pairs = f[3:]
                for a in range(0, len(pairs), 2):
                    idx, delta = int(pairs[a]), int(pairs[a + 1])
                    lit[idx] = min(1.0, lit[idx] + 0.60 * delta)
                    rx.append(ms)
                    ry.append(row[idx])
            elif f[0] == "ONFSU":
                # D-412: ONFSU repeats until nr columns have arrived.  The
                # frame is drawn when the LINE is complete, not when the
                # tag is seen, or a wrapped membrane line would draw two
                # frames for one chunk and the clock would run double.
                step = int(f[2])
                ms = step * head["dtus"] / 1000.0
                if ucols == 0:
                    tx.append(ms)
                for j, word in enumerate(f[3:]):
                    ty[ucols + j].append(unpack_f64(word))
                ucols += len(f[3:])
                if ucols < head["nr"]:
                    continue
                ucols = 0
                if thresh_line is None:
                    thresh_line = ax_m.axhline(
                        args["uth"], color="#ff9f1c", linewidth=0.9,
                        linestyle="--")
                    ax_m.text(args["ms"] * 0.985, args["uth"],
                              " threshold", color="#ff9f1c", fontsize=8,
                              ha="right", va="bottom")

                # One frame per chunk: ONFSU closes the chunk ONFSC opened.
                glow.set_sizes([9 + 85.0 * v for v in lit])
                glow.set_alpha(None)
                glow.set_color([(1.0, 0.82, 0.40, min(1.0, v))
                                for v in lit])
                if rx:
                    rast.set_offsets(list(zip(rx, ry)))
                for j, tr in enumerate(traces):
                    tr.set_data(tx, ty[j])
                lo = min(min(t) for t in ty if t)
                hi = max(max(t) for t in ty if t)
                pad = max(0.5, 0.12 * (hi - lo))
                ax_m.set_ylim(min(lo - pad, -0.5),
                              max(hi + pad, args["uth"] * 1.15))
                fig.suptitle(
                    "ONFLY  -  SUGR %d Hz, seed %d, K=%d  -  t = %6.1f ms"
                    % (head["rate"], head["seed"], head["k"], ms),
                    color="#e8eefc", fontsize=12, x=0.5, y=0.975)
                frames += 1
                if first_frame_at is None:
                    first_frame_at = time.time() - t0
                if writer is not None:
                    # --every thins the RECORDING, never the simulation:
                    # every chunk is still received and drawn, so the clip
                    # stays a record of the run rather than a coarser run.
                    if frames % args["every"] == 0:
                        writer.grab_frame(facecolor=fig.get_facecolor())
                        saved += 1
                else:
                    plt.pause(0.001)
            elif f[0] == "ONFSE":
                nreq += 1
                if ax_f is not None:
                    rate = head["rate"] if head else -1
                    gold = goldfp.SREXT.get(rate)
                    fp = f[3]
                    fp_rows.append({
                        "id": goldfp.SREXT_ID.get(rate, "-"),
                        "rate": str(rate),
                        "gold": gold or "-",
                        "fp": fp,
                        "verdict": ("AGREE" if gold == fp
                                    else "no golden" if gold is None
                                    else "DIFFERS"),
                    })
                    redraw_fp()
                    if writer is not None:
                        # Hold the completed request on screen for a beat,
                        # so the panel is readable in the recording rather
                        # than flashing past between requests.
                        for _ in range(args["fps"]):
                            writer.grab_frame(
                                facecolor=fig.get_facecolor())
                            saved += 1
                if nreq >= args["requests"]:
                    done = True

    if follow:
        rc, engine_exit_at = 0, time.time() - t0
    else:
        rc = proc.wait()
        engine_exit_at = time.time() - t0
    if writer is not None:
        writer.finish()

    print("liveview: %d chunks received, %d frames drawn, %d recorded"
          % (frames, frames, saved if args["save"] else frames))
    if follow:
        # The liveness claim for a followed stream is NOT this file's to
        # make.  This process only knows when bytes reached it, which says
        # nothing about whether the producer had finished writing them.
        # tools/mvsstm.py owns that measurement, because it is the thing
        # that can see the job's END banner.
        print("liveview: followed %s, %d of %d requests seen in %.1f s"
              % (stmpath, nreq, args["requests"], engine_exit_at))
        for r in fp_rows:
            print("liveview:   %-5s rate %-5s golden %s  this run %s  %s"
                  % (r["id"], r["rate"], r["gold"], r["fp"], r["verdict"]))
        if fp_rows and all(r["verdict"] == "AGREE" for r in fp_rows):
            print("liveview: every fingerprint matches Section 8.4")
        elif fp_rows:
            print("liveview: WARNING a fingerprint DIFFERS from Section 8.4")
    else:
        print("liveview: first frame at +%.2f s, engine exited at +%.2f s "
              "(rc %d)" % (first_frame_at or -1.0, engine_exit_at, rc))
        if first_frame_at is not None and first_frame_at < engine_exit_at:
            print("liveview: frames were drawn while the engine was still "
                  "running -- this is the live path of D-128, not a replay")
        else:
            print("liveview: WARNING no frame preceded the engine's exit")
    if args["save"]:
        print("liveview: wrote %s (%d bytes)"
              % (args["save"], os.path.getsize(args["save"])))
    else:
        import matplotlib.pyplot as _plt
        _plt.show()

    # The tail keeps ONFSTM open, and Windows will not delete a file that is.
    tail.close()
    for name in os.listdir(tmp):
        os.remove(os.path.join(tmp, name))
    os.rmdir(tmp)
    return 0 if frames > 0 else 1


def main(argv):
    args = {"engine": os.path.join(ROOT, "build", "onflyeng_nat.exe"),
            "network": NETFILE, "rate": 200, "ms": 1000, "seed": 1,
            "k": K_DEMO, "save": None, "fps": 20, "dpi": 72,
            "every": 1, "order": "body",
            # D-408 / P-25 §3.3.  --follow names a stream SOMEONE ELSE is
            # writing, so no engine is launched here at all.  That is what
            # lets tools/mvsstm.py drive TK5 without this file knowing how,
            # and lets this file draw without knowing who produced the run.
            "follow": None, "requests": 1, "timeout": 900,
            "uth": 7.0}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("--engine", "--network", "--save", "--order", "--follow"):
            args[a[2:]] = argv[i + 1]
            i += 2
        elif a in ("--rate", "--ms", "--seed", "--k", "--fps", "--dpi",
                   "--every", "--requests", "--timeout"):
            args[a[2:]] = int(argv[i + 1])
            i += 2
        elif a == "--help":
            sys.stdout.write(__doc__.rsplit("Run:", 1)[-1])
            return 0
        else:
            sys.stderr.write("liveview: unknown argument %r\n" % a)
            return 2
    if args["order"] not in ("body", "index"):
        # Rejected rather than ignored.  A typo that silently fell back to
        # index order would produce a picture whose own axis label was a
        # lie, which is the failure mode this whole file is arranged
        # against.
        sys.stderr.write("liveview: --order must be 'body' or 'index', "
                         "not %r\n" % args["order"])
        return 2
    if args["follow"] is None and not os.path.exists(args["engine"]):
        sys.stderr.write("liveview: no engine at %s\n"
                         "  build one with: mingw32-make eng\n"
                         % args["engine"])
        return 2
    if args["follow"] is not None and args["save"] is None:
        # Rejected rather than defaulted.  A followed stream is written by
        # a job on another machine and there is nothing to wait for
        # interactively; a window that opened and closed would look like a
        # failure.  --save makes the run produce something that outlives it.
        sys.stderr.write("liveview: --follow needs --save FILE.gif\n")
        return 2
    try:
        # u_th comes from the network header, never from a constant here.
        sys.path.insert(0, os.path.join(ROOT, "layout"))
        import netread
        args["uth"] = netread.read(args["network"])["u_th"]
        return run(args)
    except ViewError as exc:
        sys.stderr.write("liveview: %s\n" % exc)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
