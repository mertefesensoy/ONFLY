# -*- coding: utf-8 -*-
"""Re-run Shiu et al.'s Figure 1D protocol to produce the ONFLY reference
MN9 curve (SR-CAL-04, TBC-06 closed by D-164).

What this script is and is not
------------------------------
The physics is Shiu's, untouched: ``model.py`` and ``utils.py`` in this
directory are vendored verbatim from github.com/philshiu/Drosophila_brain_model
(MIT; digests in ``MANIFEST.json``).  Each trial is ``model.run_trial`` on the
FlyWire 630 completeness and connectivity files, exactly as ``figures.ipynb``
cell 5 drives it for Figure 1D: the 21 right-hemisphere labellar sugar GRNs as
Poisson inputs at rate r, ``t_run`` = 1000 ms, ``n_run`` = 30 trials, MN9 rate
= spikes / t_run averaged over trials (``utils.get_rate``).

What is ONFLY's here is the driver around it, and it differs from
``model.run_exp`` in exactly two ways, both recorded:

  1. Each trial is seeded (``brian2.seed(trial + 1)``) before ``run_trial`` so
     the reference is reproducible on this host.  Shiu's ``run_exp`` seeds
     nothing, so his published numbers are one draw of the same distribution.
  2. Only the rates TBD-07 needs are run (D-164, D-165), not all twenty.

The rate table is written for both MN9 neurons and for the D-170 quantity,
their mean.

Run (from the repository root, inside the brian2 venv):

    .venv/Scripts/python reference/shiu/rerun.py            # full protocol
    .venv/Scripts/python reference/shiu/rerun.py --probe    # 1 trial, 200 Hz
    .venv/Scripts/python reference/shiu/rerun.py --n-proc 3
"""
import argparse
import hashlib
import io
import json
import os
import platform
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import numpy as np                                        # noqa: E402
import pandas as pd                                       # noqa: E402
import brian2                                             # noqa: E402
from brian2 import Hz                                     # noqa: E402
from joblib import Parallel, delayed, parallel_backend    # noqa: E402

import model                                              # noqa: E402
import utils as utl                                       # noqa: E402

DATA = os.path.join(HERE, "data")
RESULTS = os.path.join(HERE, "results")
PATH_COMP = os.path.join(DATA, "2023_03_23_completeness_630_final.csv")
PATH_CON = os.path.join(DATA, "2023_03_23_connectivity_630_final.parquet")

# figures.ipynb, cell 4: "list of the labellar sugar-sensing gustatory receptor
# neurons on right hemisphere".  Copied verbatim.
NEU_SUGAR = [
    720575940624963786, 720575940630233916, 720575940637568838,
    720575940638202345, 720575940617000768, 720575940630797113,
    720575940632889389, 720575940621754367, 720575940621502051,
    720575940640649691, 720575940639332736, 720575940616885538,
    720575940639198653, 720575940620900446, 720575940617937543,
    720575940632425919, 720575940633143833, 720575940612670570,
    720575940628853239, 720575940629176663, 720575940611875570,
]

# figures.ipynb cells 8 and 17: MN9 left and right.
MN9 = {"left": 720575940660219265, "right": 720575940645521262}

# SR-CAL-02 as closed by D-165: calibration u validation, ascending.
RATES = [10, 20, 40, 60, 80, 120, 160, 200]


def sha256(path):
    h = hashlib.sha256()
    with io.open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def seeded_trial(trial, exc, params, target):
    """One Shiu trial, seeded.  Runs in a worker process."""
    brian2.prefs.codegen.target = target
    brian2.seed(trial + 1)
    return model.run_trial(exc, [], [], PATH_COMP, PATH_CON, params)


def rate_value(df, fly_id, col):
    """Rate of one neuron from a get_rate table; 0 if it never spiked."""
    if fly_id in df.index:
        return float(df.loc[fly_id, col])
    return 0.0


def run_rate(rate_hz, params, n_proc, target, force):
    """Figure 1D at one rate: n_run seeded trials, spikes to parquet."""
    out = os.path.join(RESULTS, "data", "sugarR_%dHz.parquet" % rate_hz)
    if os.path.isfile(out) and not force:
        print("  %3d Hz: %s exists, skipped"
              % (rate_hz, os.path.basename(out)))
        return out, 0.0
    df_comp = pd.read_csv(PATH_COMP, index_col=0)
    flyid2i = {j: i for i, j in enumerate(df_comp.index)}
    i2flyid = {i: j for j, i in flyid2i.items()}
    exc = [flyid2i[n] for n in NEU_SUGAR]
    p = dict(params)
    p["r_poi"] = rate_hz * Hz
    t0 = time.time()
    with parallel_backend("loky", n_jobs=n_proc):
        res = Parallel()(delayed(seeded_trial)(k, exc, p, target)
                         for k in range(p["n_run"]))
    dt = time.time() - t0
    df = model.construct_dataframe(res, "sugarR_%dHz" % rate_hz, i2flyid)
    if not os.path.isdir(os.path.dirname(out)):
        os.makedirs(os.path.dirname(out))
    df.to_parquet(out, compression="brotli")
    print("  %3d Hz: %d trials, %d spikes, %.0f s"
          % (rate_hz, p["n_run"], len(df), dt))
    return out, dt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-proc", type=int, default=2,
                    help="parallel trials; each holds the whole network")
    ap.add_argument("--n-run", type=int, default=None, help="trials per rate")
    ap.add_argument("--rates", type=str, default=None, help="comma list, Hz")
    ap.add_argument("--target", default="numpy", help="brian2 codegen target")
    ap.add_argument("--probe", action="store_true",
                    help="timing probe: one trial at 200 Hz, nothing kept")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()

    params = dict(model.default_params)
    if a.n_run:
        params["n_run"] = a.n_run
    rates = [int(x) for x in a.rates.split(",")] if a.rates else list(RATES)

    print("brian2 %s numpy %s pandas %s python %s target=%s n_proc=%d"
          % (brian2.__version__, np.__version__, pd.__version__,
             platform.python_version(), a.target, a.n_proc))
    print("t_run=%s n_run=%d w_syn=%s f_poi=%s"
          % (params["t_run"], params["n_run"], params["w_syn"],
             params["f_poi"]))

    if a.probe:
        df_comp = pd.read_csv(PATH_COMP, index_col=0)
        flyid2i = {j: i for i, j in enumerate(df_comp.index)}
        exc = [flyid2i[n] for n in NEU_SUGAR]
        p = dict(params)
        p["r_poi"] = 200 * Hz
        t0 = time.time()
        spk = seeded_trial(0, exc, p, a.target)
        dt = time.time() - t0
        n_spk = sum(len(v) for v in spk.values())
        mn9 = {k: len(spk.get(flyid2i[v], [])) for k, v in MN9.items()}
        print("PROBE 200 Hz 1 trial: %.1f s, %d spiking neurons, %d spikes,"
              " MN9 %s" % (dt, len(spk), n_spk, mn9))
        return 0

    t_all = time.time()
    files, secs = [], {}
    for r in rates:
        f, dt = run_rate(r, params, a.n_proc, a.target, a.force)
        files.append(f)
        secs[r] = dt

    # utils.get_rate exactly as figures.ipynb cell 6 applies it.
    t_run = float(params["t_run"] / brian2.second)
    df_spike = utl.load_exps(files)
    df_rate, df_std = utl.get_rate(df_spike, t_run=t_run,
                                   n_run=params["n_run"])

    rows = []
    for r in rates:
        col = "sugarR_%dHz" % r
        left = rate_value(df_rate, MN9["left"], col)
        right = rate_value(df_rate, MN9["right"], col)
        rows.append({"rate_hz": r,
                     "mn9_left_hz": left,
                     "mn9_left_sd": rate_value(df_std, MN9["left"], col),
                     "mn9_right_hz": right,
                     "mn9_right_sd": rate_value(df_std, MN9["right"], col),
                     "mn9_mean_hz": (left + right) / 2.0})
    table = pd.DataFrame(rows)
    out_csv = os.path.join(RESULTS, "mn9-reference.csv")
    table.to_csv(out_csv, index=False, float_format="%.6f",
                 lineterminator="\n")
    print(table.to_string(index=False))

    man = {
        "what": "Shiu et al. 2024 Figure 1D protocol re-run "
                "(D-164, SR-CAL-04)",
        "source_code": "github.com/philshiu/Drosophila_brain_model, "
                       "model.py and utils.py vendored verbatim",
        "digests": {
            "model.py": sha256(os.path.join(HERE, "model.py")),
            "utils.py": sha256(os.path.join(HERE, "utils.py")),
            "connectivity": sha256(PATH_CON),
            "completeness": sha256(PATH_COMP),
            "mn9-reference.csv": sha256(out_csv),
        },
        "environment": {
            "python": platform.python_version(),
            "brian2": brian2.__version__,
            "numpy": np.__version__, "pandas": pd.__version__,
            "codegen_target": a.target, "platform": platform.platform(),
            "shiu_pinned": "python 3.10, brian2 2.5.1, numpy 1.24 "
                           "(environment.yml)",
        },
        "protocol": {
            "stimulus": "21 right-hemisphere labellar sugar GRNs "
                        "(figures.ipynb cell 4)",
            "rates_hz": rates, "t_run_s": t_run, "n_run": params["n_run"],
            "seeding": "brian2.seed(trial+1) per trial; "
                       "Shiu's run_exp seeds nothing",
            "mn9": MN9, "metric": "D-170: mean of left and right MN9 rates",
        },
        "elapsed_s": {str(k): round(v, 1) for k, v in secs.items()},
        "total_elapsed_s": round(time.time() - t_all, 1),
    }
    io.open(os.path.join(RESULTS, "MANIFEST.json"), "w", encoding="utf-8",
            newline="\n").write(json.dumps(man, indent=2, sort_keys=True)
                                + "\n")
    print("wrote %s" % out_csv.replace("\\", "/"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
