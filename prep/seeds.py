# -*- coding: utf-8 -*-
"""TBD-06: how many seeds per rate should the acceptance criteria use?

WHY THIS EXISTS
---------------
TBD-06's last open item is the seed count.  D-135 (2026-09-12) did not leave
it open for lack of an opinion; it left it open for lack of a measurement:

    Seeds per rate stays at 30, and the question is deliberately deferred
    UNTIL THE FIRST FULL ACCEPTANCE RUN HAS BEEN EXECUTED.  TBD-06 therefore
    remains open on this item alone.

That run has now happened (VL-98, VL-105, VL-112), so the condition D-135 set
is satisfied and the item is answerable on evidence.

D-135 framed the choice as compute time -- 30 seeds or 15, halving a suite.
Reading Section 6.4 as it now stands shows the seed count is also A BAR
HEIGHT, and in two directions at once:

  * ACC-4's SHAPE clause -- the criterion itself since D-341 -- allows a
    decrease between successive rates of at most ONE STANDARD ERROR of the
    earlier point, and SE = sd / sqrt(n).  More seeds is a STRICTER test.
  * ACC-1 requires a spike in at least 90% of seeds.  At n = 30 that is 27 of
    30; at n = 10 a single unlucky seed carries ten times the weight.
  * ACC-3's exclusion rule (D-202) tests sd against the mean.  sd does not
    shrink with n, so that clause should be insensitive to the seed count --
    a prediction this tool checks rather than assumes.

So a seed count picked without knowing which clauses move is a guess about
how high the bar is, not only about how long the suite takes.

WHAT IS MEASURED AND WHAT IS MODELLED
-------------------------------------
The distinction matters more than any number below, and every figure this
tool prints is labelled with which side of it the figure comes from.

  MEASURED, non-parametric.  The shipped `srext` subcircuit is re-run at the
  five D-165 validation rates with 200 seeds (D-352), keeping the PER-SEED
  MN9 rate that `prep/acc4.py:323` and `prep/extract.py:366` both compute and
  then discard.  ACC-1 is defined on this network -- "the MVS subcircuit" --
  so its clause is bootstrapped directly from real seeds with no distribution
  assumed.

  BOUNDED, semi-parametric.  ACC-3 compares the subcircuit mean against the
  FULL-BRAIN mean.  No per-seed full-brain values were ever kept, and D-351
  decided against spending two hours to re-run for them, so the full-brain
  half is drawn from N(m, sd/sqrt(n)) with acc4.json's recorded 30-seed sd.
  Because ACC-3 evaluates both halves ON THE SAME SEEDS, the honest
  dispersion is the sd of the PAIRED per-seed differences, which is smaller
  than the root-sum-of-squares whenever the halves are positively correlated
  -- and the shared stimulus draws make that likely.  Drawing them
  independently therefore OVERSTATES the variability.  That is the point:
  the bound can only ever recommend MORE seeds than are truly needed, never
  fewer, so a "stable" verdict from it is trustworthy and an "unstable" one
  is a reason to measure the paired difference, not a conclusion.

  MODELLED.  ACC-4 is evaluated on the full brain by `prep/acc4.py`, so its
  clauses have the same gap and are treated analytically from the recorded
  means and sds.  Every ACC-4 figure here is a normal-theory estimate.

HOW THE BOOTSTRAP WORKS
-----------------------
For each candidate n, draw n seeds with replacement from the S measured
seeds, B times, evaluate the clause on each draw, and report the fraction of
draws whose verdict differs from the verdict on the full measured sample.
That fraction is the probability the criterion flips on a reseed, which is
the quantity a seed count should be chosen to control.  No normality is
assumed, which matters at 10 Hz where the distribution is strongly skewed --
sd above mean is exactly the condition D-202 tests.

The resampling generator is seeded from a fixed constant recorded in the
output, so a re-run of this tool reproduces the table exactly.  That seed
governs this analysis only; the engine's PRNG is NR-13's xorshift32 and is
untouched.

Run (repository root, after `make fixtures` and `make runner`):

    python prep/seeds.py [--seeds 200] [--jobs 14]
    python prep/seeds.py --reeval          # re-analyse without re-running
"""
import argparse
import math
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import calibrate as cal                       # noqa: E402
import extract as ext                         # noqa: E402

NETWORK = os.path.join(ROOT, "data", "networks",
                       "onfnet-malecns-v1.0-srext.bin")
OUT = os.path.join(cal.CAL_DIR, "seeds.json")

VAL_RATES = ext.VAL_RATES                     # D-165: 10, 40, 60, 120, 200
SWEEP_SEEDS = 200                             # D-352
CANDIDATE_N = (5, 10, 15, 20, 30, 50, 100)
BOOTSTRAP_B = 10000
BOOTSTRAP_SEED = 20260916                     # analysis only, not NR-13

ACC1_FRAC = ext.ACC1_SEED_FRACTION            # 0.90
ACC3_REL = ext.REL_TOL                        # 0.10
ACC3_ABS = ext.ABS_FLOOR                      # 1.0, D-166
ONSET_HZ = 1.0                                # ACC-4 onset definition


# --- the measurement -------------------------------------------------------
def sweep(path, seeds, jobs):
    """Per-seed MN9 rate at every validation rate.  Returns {rate: [Hz]}.

    The rate is the mean over the two readout neurons of spikes per second,
    which is the D-170 quantity `prep/acc4.py` and `prep/extract.py` both
    compute.  It is recomputed here rather than imported so that this tool
    reproduces their arithmetic in the open, where the reproduction check
    below can catch a divergence.
    """
    results = {}

    def on_done(k, text):
        res = cal.parse_run(text)
        if res["rc"] != 0 or len(res["readouts"]) != 2:
            raise SystemExit("run %s failed:\n%s" % (k, text[-2000:]))
        results[k] = res

    todo = [(path, r, s) for r in VAL_RATES for s in seeds]
    t0 = time.time()
    ext.run_pool(todo, jobs, [], on_done)
    per_rate = {}
    for r in VAL_RATES:
        row = []
        for s in seeds:
            sp = [x["spikes"] for x in results[(path, r, s)]["readouts"]]
            row.append(sum(sp) * 1000.0 / cal.SIM_MS / len(sp))
        per_rate[r] = row
    return per_rate, time.time() - t0


def reproduction_check(per_rate, seeds):
    """The first 30 seeds must reproduce the recorded acceptance run exactly.

    The engine is deterministic given (network, rate, seed), so seeds 1..30 of
    this sweep are the same thirty runs `prep/extract.py --acc1` made for
    VL-105.  If they disagree, something has changed that this tool has no
    business analysing around, and it stops.
    """
    rec = ext.load_json(ext.ACC1OUT, None)
    if rec is None:
        return {"checked": False,
                "reason": "acc1-candidate.json absent; nothing to check"}
    n = len(rec["seeds"])
    if list(seeds[:n]) != list(rec["seeds"]):
        return {"checked": False,
                "reason": "recorded seeds %s.. differ from this sweep's"
                          % rec["seeds"][:3]}
    detail = {}
    for r in VAL_RATES:
        row = per_rate[r][:n]
        mean = sum(row) / len(row)
        spiking = sum(1 for v in row if v > 0.0)
        e = rec["per_rate"][str(r)]
        ok = (abs(mean - e["mean_hz"]) < 1e-12
              and spiking == e["seeds_with_mn9_spike"])
        detail[str(r)] = {"recorded_mean_hz": e["mean_hz"],
                          "resweep_mean_hz": mean,
                          "recorded_seeds_with_spike":
                              e["seeds_with_mn9_spike"],
                          "resweep_seeds_with_spike": spiking, "agrees": ok}
    return {"checked": True, "seeds": n, "source": "acc1-candidate.json",
            "per_rate": detail,
            "agrees": all(v["agrees"] for v in detail.values())}


# --- the clauses, each written once ---------------------------------------
def acc1_verdict(rates_hz, spiking, applies):
    """ACC-1 over one sample: >=90% of seeds spiking and a mean above zero.

    ``rates_hz`` and ``spiking`` have shape (rate, B, n): B independent samples
    of n seeds each, for every validation rate.  Returns a boolean array of
    length B.  A single sample is passed as B = 1.
    """
    ok = np.ones(rates_hz.shape[1], dtype=bool)
    for i, r in enumerate(VAL_RATES):
        if not applies[r]:
            continue                       # Shiu reference is zero: untested
        frac = spiking[i].mean(axis=1)
        mean = rates_hz[i].mean(axis=1)
        ok &= (frac >= ACC1_FRAC) & (mean > 0.0)
    return ok


def acc3_verdict(sub_mean, full_mean, excluded):
    """ACC-3 over one sample: every non-excluded rate within tolerance.

    ``sub_mean`` and ``full_mean`` are (len(VAL_RATES), B) arrays.  The
    tolerance follows the full-brain draw, because ACC-3's +-10% is 10% of the
    reference, not of a fixed constant.
    """
    ok = np.ones(sub_mean.shape[1], dtype=bool)
    for i, r in enumerate(VAL_RATES):
        if excluded[r]:
            continue                       # D-202: reported, never counted
        tol = np.maximum(ACC3_REL * full_mean[i], ACC3_ABS)
        ok &= np.abs(sub_mean[i] - full_mean[i]) <= tol
    return ok


def acc3_campaign(sub_rates, full, excluded):
    """ACC-3 if the WHOLE campaign were re-seeded, bracketed not guessed.

    There are two different questions hiding inside "is ACC-3 stable", and they
    have very different answers, so this tool answers both rather than picking
    one.

      (a) RE-EVALUATION.  `prep/extract.py --acc3-file` reads the full-brain
          reference from the RECORDED acc4.json and re-runs only the
          subcircuit.  The only thing that varies is the subcircuit's mean, and
          its per-seed spread is measured here directly.  This is what
          re-running the criterion today actually does, and it is bootstrapped
          non-parametrically elsewhere in this module.

      (b) RE-MEASUREMENT.  If the full brain were re-run too -- a fresh
          scientific campaign -- the reference moves as well, and its per-seed
          spread is the larger of the two by far.

    For (b) the per-seed difference d = sub - full is what matters, and

        var(d) = s_sub^2 + s_full^2 - 2 * rho * s_sub * s_full

    where rho is a correlation nobody measured, because the full brain's
    per-seed values were never kept (D-351).  Three points on that curve:

        rho = +1   sd(d) = |s_full - s_sub|              the minimum
        rho =  0   sd(d) = sqrt(s_sub^2 + s_full^2)      D-351's bound
        rho = -1   sd(d) = s_full + s_sub                the maximum

    This reports the first two.  That is a bracket over rho in [0, 1], NOT
    over every arithmetically possible rho: an anticorrelation would be worse
    still.  The restriction is deliberate and is the content of D-351 --
    the same seed drives the same fourteen stimulus neurons in both networks,
    because SR-EXT-01 keeps every stimulus and readout neuron in the
    subcircuit, so a seed that delivers a strong stimulus burst raises both
    means.  rho < 0 would mean a seed that excites the full brain quietens its
    own subcircuit, which the construction makes implausible.

    Reported this way the answer does not rest on the unmeasured number: when
    s_full is several times s_sub the two ends are close together, and the
    verdict is then the same anywhere in the bracket -- a much stronger
    statement than either end alone.

    The tolerance is held at 10% of the recorded reference mean rather than
    following the draw; its own sampling wobble is an order below the
    difference's and folding it in would obscure the bracket.
    """
    rows = {}
    for i, r in enumerate(VAL_RATES):
        s_sub = float(np.std(sub_rates[i], ddof=1))
        e = full["per_rate"][str(r)]
        s_full, m_full = e["onfly_sd_hz"], e["onfly_mean_hz"]
        m_sub = float(np.mean(sub_rates[i]))
        tol = max(ACC3_REL * m_full, ACC3_ABS)
        mu = m_sub - m_full
        hi = math.sqrt(s_sub ** 2 + s_full ** 2)      # independent
        lo = abs(s_full - s_sub)                      # perfectly correlated
        e = {"excluded": excluded[r], "sub_mean_hz": m_sub,
             "sub_sd_hz": s_sub, "full_mean_hz": m_full,
             "full_sd_hz": s_full, "tolerance_hz": tol,
             "difference_hz": mu, "margin_hz": tol - abs(mu),
             "diff_sd_independent_hz": hi, "diff_sd_correlated_hz": lo}
        e["per_n"] = {str(n): {"p_pass_" + name: _p_pass(e, n, name)
                               for name in ("bound", "floor")}
                      for n in CANDIDATE_N}
        rows[str(r)] = e
    # The criterion is the conjunction over the rates it tests.
    joint = {}
    tested = [r for r in VAL_RATES if not excluded[r]]
    for n in CANDIDATE_N:
        for name in ("bound", "floor"):
            p = 1.0
            for r in tested:
                p *= rows[str(r)]["per_n"][str(n)]["p_pass_" + name]
            joint.setdefault(str(n), {})["p_pass_" + name] = p

    # How many seeds would make the re-measurement reproducible?  Scanned
    # rather than solved, because the joint probability is a product over
    # rates and the per-rate form is a difference of two normal CDFs.  The
    # scan is capped: a requirement past the cap is reported as such rather
    # than as a number, because "> 20000 seeds" is the honest answer and a
    # clipped figure would read like an achievable target.
    def p_at(r, n, name):
        return _p_pass(rows[str(r)], n, name)

    cap = 20000
    need = {}
    for target in (0.90, 0.95, 0.99):
        entry = {}
        for name in ("bound", "floor"):
            per_rate_need = {}
            for r in tested:
                k = next((n for n in range(1, cap + 1)
                          if p_at(r, n, name) >= target), None)
                per_rate_need[str(r)] = k
            k = next((n for n in range(1, cap + 1)
                      if _joint(rows, tested, n, name) >= target), None)
            entry[name] = {"per_rate": per_rate_need, "joint": k}
        need["%.2f" % target] = entry
    return {"per_rate": rows, "joint": joint, "rates_tested": tested,
            "seeds_needed": need, "scan_cap": cap}


def _p_pass(e, n, name):
    """P(|d| <= tol) at seed count n, for one rate, at one end of the bracket.

    Written once and used by both the per-n table and the scan for the seed
    count a target probability needs, so the two can never disagree about what
    the criterion is.
    """
    sd = (e["diff_sd_independent_hz"] if name == "bound"
          else e["diff_sd_correlated_hz"])
    se = sd / math.sqrt(float(n))
    if se <= 0.0:
        return 1.0 if abs(e["difference_hz"]) <= e["tolerance_hz"] else 0.0
    return (phi((e["tolerance_hz"] - e["difference_hz"]) / se)
            - phi((-e["tolerance_hz"] - e["difference_hz"]) / se))


def _joint(rows, tested, n, name):
    p = 1.0
    for r in tested:
        p *= _p_pass(rows[str(r)], n, name)
    return p


# --- ACC-4, analytic (no per-seed full-brain values exist) ----------------
def phi(z):
    """Standard normal CDF, via erf, to avoid a scipy dependency."""
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def acc4_analysis(full):
    """ACC-4's two clauses as a function of n, from the recorded means and sds.

    SHAPE.  The clause allows drop_i = m_i - m_{i+1} to be at most
    SE_i(n) = sd_i / sqrt(n).  Treating both sample means as normal and
    independent, the drop has standard error sqrt(sd_i^2 + sd_{i+1}^2)/sqrt(n),
    so the failure probability is

        P(fail) = 1 - Phi( z ),    z = (sd_i + |drop_i| * sqrt(n))
                                       / sqrt(sd_i^2 + sd_{i+1}^2)

    when the curve rises (drop_i < 0).  Both the bar and the noise shrink as
    n^(-1/2) while the TRUE drop stays fixed, so z GROWS with sqrt(n): on a
    genuinely rising curve more seeds makes the shape clause EASIER, not
    harder, even though the bar itself is getting lower.  That is worth
    stating plainly, because the opposite is the natural guess.

    ONSET.  The onset is the lowest validation rate whose mean exceeds 1 Hz,
    and the clause allows it to differ from the reference's onset by at most
    one sampled rate.  With the reference onset at 40 Hz (index 1), an ONFLY
    onset at 10, 40 or 60 Hz all pass; only an onset at 120 Hz or above fails,
    which needs all three of the 10, 40 and 60 Hz means to fall to 1 Hz.
    """
    m = [full["per_rate"][str(r)]["onfly_mean_hz"] for r in VAL_RATES]
    sd = [full["per_rate"][str(r)]["onfly_sd_hz"] for r in VAL_RATES]
    ref = [full["per_rate"][str(r)]["reference_hz"] for r in VAL_RATES]

    def onset_index(curve):
        for i, v in enumerate(curve):
            if v > ONSET_HZ:
                return i
        return None

    ref_onset = onset_index(ref)
    obs_onset = onset_index(m)

    out = {"means_hz": m, "sds_hz": sd, "reference_hz": ref,
           "onset_index_onfly": obs_onset, "onset_index_reference": ref_onset,
           "per_n": {}}
    for n in CANDIDATE_N:
        rn = math.sqrt(float(n))
        pairs = []
        worst = 0.0
        for i in range(len(VAL_RATES) - 1):
            drop = m[i] - m[i + 1]
            se_bar = sd[i] / rn
            se_drop = math.sqrt(sd[i] ** 2 + sd[i + 1] ** 2) / rn
            z = (se_bar - drop) / se_drop
            p = 1.0 - phi(z)
            worst = max(worst, p)
            pairs.append({"from_hz": VAL_RATES[i], "to_hz": VAL_RATES[i + 1],
                          "drop_hz": drop, "bar_se_hz": se_bar,
                          "drop_se_hz": se_drop, "z": z, "p_fail": p})
        # Onset: every rate whose index is <= ref_onset + 1 must be at or
        # below 1 Hz before the onset can move far enough to fail.
        p_all_low = 1.0
        for i in range(0, min(len(VAL_RATES), (ref_onset or 0) + 2)):
            p_all_low *= phi((ONSET_HZ - m[i]) / (sd[i] / rn))
        out["per_n"][str(n)] = {"shape_pairs": pairs,
                                "p_shape_fail": worst,
                                "p_onset_fail": p_all_low}
    return out


def d202_analysis(full, sub_rates):
    """D-202's exclusion rule against the seed count -- and what rides on it.

    The rule compares the reference's sd with its mean.  A sample sd estimates
    a population quantity that does NOT shrink as n grows -- only its own
    uncertainty does -- so the excluded SET should not systematically move
    with the seed count.  What the seed count changes is how RELIABLY the
    classification is made, and that matters here more than it looks, because
    the exclusion is load-bearing:

        at 10 Hz the subcircuit produces ~0.02 Hz against a reference of
        3.67 Hz and a tolerance of 1.0 Hz, so if that rate were ever TESTED
        rather than excluded, ACC-3 would fail outright.

    So the honest statement is not "the exclusion is stable" but "ACC-3's PASS
    rests on a classification made from a ratio of 1.15, and more seeds
    RESOLVES that classification rather than improving it": if the population
    ratio really is above 1, more seeds makes the exclusion certain; if it is
    below 1, more seeds makes ACC-3 fail with certainty.  A seed count cannot
    choose which.

    The estimate.  For a normal sample the mean and the sample sd are
    independent, with m ~ N(mu, sigma^2/n) and s concentrating about sigma
    with relative standard deviation 1/sqrt(2(n-1)).  To first order

        log(s/m) ~ N( log(sigma/mu),  1/(2(n-1)) + (sigma/mu)^2 / n )

    and P(not excluded) = P(s/m < 1) follows by plugging in the measured
    ratio.  MODELLED, and normality is a poor fit at exactly the rate this
    matters for -- 10 Hz is strongly skewed, which is what makes its sd
    exceed its mean in the first place -- so the figure is an indication of
    where the risk lies, not a calibrated probability.  The structural point
    does not depend on it.
    """
    rows = {}
    for i, r in enumerate(VAL_RATES):
        e = full["per_rate"][str(r)]
        m, s = e["onfly_mean_hz"], e["onfly_sd_hz"]
        ratio = (s / m) if m > 0 else None
        tol = max(ACC3_REL * m, ACC3_ABS)
        sub_m = float(np.mean(sub_rates[i]))
        per_n = {}
        if ratio is not None and ratio > 0.0:
            for n in CANDIDATE_N:
                if n < 2:
                    continue
                var = 1.0 / (2.0 * (n - 1)) + ratio ** 2 / float(n)
                z = (0.0 - math.log(ratio)) / math.sqrt(var)
                per_n[str(n)] = {"p_not_excluded": phi(z)}
        rows[str(r)] = {"mean_hz": m, "sd_hz": s, "sd_over_mean": ratio,
                        "excluded": ext.acc3_excluded(full, r),
                        "subcircuit_mean_hz": sub_m,
                        "tolerance_hz": tol,
                        "would_pass_if_tested": abs(sub_m - m) <= tol,
                        "p_not_excluded_per_n": per_n}
    return rows


# --- putting it together ---------------------------------------------------
def analyse(per_rate, full, seeds):
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    S = len(seeds)
    rates = np.array([per_rate[str(r)] for r in VAL_RATES], dtype=float)
    spiking = (rates > 0.0).astype(float)
    applies = {r: full["per_rate"][str(r)]["reference_hz"] > 0.0
               for r in VAL_RATES}
    excluded = {r: ext.acc3_excluded(full, r) for r in VAL_RATES}
    fm = np.array([full["per_rate"][str(r)]["onfly_mean_hz"]
                   for r in VAL_RATES], dtype=float)

    # Reference verdicts: the criterion evaluated on everything measured.
    ref_acc1 = bool(acc1_verdict(rates[:, None, :], spiking[:, None, :],
                                 applies)[0])
    ref_acc3 = bool(acc3_verdict(rates.mean(axis=1)[:, None],
                                 fm[:, None], excluded)[0])

    per_n = {}
    for n in CANDIDATE_N:
        idx = rng.integers(0, S, size=(BOOTSTRAP_B, n))
        rs = rates[:, idx]                      # (rate, B, n)
        sp = spiking[:, idx]
        a1 = acc1_verdict(rs, sp, applies)
        sub_mean = rs.mean(axis=2)              # (rate, B)
        # ACC-3 with the reference held at its RECORDED value, which is what
        # re-evaluating the criterion does today: `--acc3-file` reads
        # acc4.json and re-runs only the subcircuit.  Non-parametric and
        # entirely measured.  The other question -- the whole campaign
        # re-seeded -- is bracketed analytically in acc3_campaign().
        a3 = acc3_verdict(sub_mean, np.repeat(fm[:, None], BOOTSTRAP_B, 1),
                          excluded)
        rate_rows = {}
        for i, r in enumerate(VAL_RATES):
            tol = max(ACC3_REL * fm[i], ACC3_ABS)
            within = np.abs(sub_mean[i] - fm[i]) <= tol
            rate_rows[str(r)] = {
                "sub_mean_se_hz": float(sub_mean[i].std(ddof=1)),
                "acc3_within_tolerance_frac": float(within.mean()),
                "excluded": excluded[r],
                "acc1_seed_fraction_mean": float(sp[i].mean()),
                "acc1_worst_seed_fraction": float(sp[i].mean(axis=1).min()),
            }
        per_n[str(n)] = {
            "acc1_pass_frac": float(a1.mean()),
            "acc1_flip_frac": float((a1 != ref_acc1).mean()),
            "acc3_fixedref_pass_frac": float(a3.mean()),
            "acc3_fixedref_flip_frac": float((a3 != ref_acc3).mean()),
            "per_rate": rate_rows,
        }
    return {"reference_verdicts": {"acc1": ref_acc1, "acc3": ref_acc3},
            "measured_seeds": S, "bootstrap_B": BOOTSTRAP_B,
            "bootstrap_seed": BOOTSTRAP_SEED,
            "candidate_n": list(CANDIDATE_N), "per_n": per_n,
            "acc3_campaign": acc3_campaign(rates, full, excluded),
            "acc4": acc4_analysis(full), "d202": d202_analysis(full, rates),
            "full_brain_sd_source": ("acc4.json, 30 seeds; no per-seed "
                                     "full-brain values exist (D-351)")}


def full_brain_cost(full, analysis):
    """What each candidate seed count would cost on the full brain.

    Scaled linearly from the recorded acc4 run, which is the only measurement
    of that cost there is.  Linearity is the right model here because the runs
    are independent and the pool is saturated at either size; it is still an
    extrapolation and the report says so.  The subcircuit's own cost is not
    projected -- it is minutes at any count considered.
    """
    runs = len(VAL_RATES) * full["seeds"] + 1        # +1 for the rate-0 run
    per_run = float(full["elapsed_s"]) / runs
    wanted = set(CANDIDATE_N)
    for target in analysis["acc3_campaign"]["seeds_needed"].values():
        for case in target.values():
            if case["joint"] is not None:
                wanted.add(case["joint"])
    out = []
    for n in sorted(wanted):
        out.append((n, (len(VAL_RATES) * n + 1) * per_run / 3600.0))
    return {"recorded_seeds": full["seeds"], "recorded_runs": runs,
            "recorded_elapsed_s": full["elapsed_s"],
            "seconds_per_run": per_run, "projected_hours": out,
            "basis": "linear scaling of data/calibration/acc4.json; an "
                     "extrapolation, not a measurement"}


def report(doc):
    a = doc["analysis"]
    print("")
    print("TBD-06 seed sensitivity -- %s, %d seeds, bootstrap B=%d"
          % (os.path.basename(doc["network"]), a["measured_seeds"],
             a["bootstrap_B"]))
    print("platform: %s" % doc["platform"])
    print("")
    print("MEASURED per-seed dispersion of the subcircuit (non-parametric):")
    print("%8s %12s %12s %10s" % ("rate", "mean Hz", "sd Hz", "sd/mean"))
    for r in VAL_RATES:
        row = doc["per_rate"][str(r)]
        m = sum(row) / len(row)
        sd = (sum((v - m) ** 2 for v in row) / (len(row) - 1)) ** 0.5
        print("%8d %12.4f %12.4f %10s"
              % (r, m, sd, "%.3f" % (sd / m) if m > 0 else "n/a"))
    print("")
    print("D-202 exclusion, full-brain reference (sd does NOT shrink with n):")
    print("%8s %12s %12s %10s %10s %14s"
          % ("rate", "mean Hz", "sd Hz", "sd/mean", "excluded",
             "if tested"))
    for r in VAL_RATES:
        e = a["d202"][str(r)]
        print("%8d %12.4f %12.4f %10.3f %10s %14s"
              % (r, e["mean_hz"], e["sd_hz"], e["sd_over_mean"],
                 "YES" if e["excluded"] else "no",
                 "ACC-3 PASS" if e["would_pass_if_tested"] else "ACC-3 FAIL"))
    load_bearing = [r for r in VAL_RATES
                    if a["d202"][str(r)]["excluded"]
                    and not a["d202"][str(r)]["would_pass_if_tested"]]
    if load_bearing:
        print("   LOAD-BEARING: ACC-3's PASS depends on %s Hz staying"
              % ", ".join(str(r) for r in load_bearing))
        print("   excluded -- tested, %s would fail the criterion."
              % ("it" if len(load_bearing) == 1 else "they"))
        print("   P(a re-measured campaign does NOT exclude it), normal"
              " theory, skewed data:")
        line = "      " + "".join("%10s" % ("n=%d" % n)
                                  for n in a["candidate_n"])
        print(line)
        for r in load_bearing:
            e = a["d202"][str(r)]["p_not_excluded_per_n"]
            print("%5dHz" % r + "".join(
                "%9.1f%%" % (100 * e[str(n)]["p_not_excluded"])
                if str(n) in e else "%10s" % "-"
                for n in a["candidate_n"]))
    print("")
    print("A. RE-EVALUATION -- reference held at its recorded value, which is")
    print("   what re-running the criterion does today.  ACC-1 and ACC-3 are")
    print("   MEASURED: a non-parametric bootstrap over real seeds.  ACC-4 is")
    print("   MODELLED: normal theory from acc4.json's means and sds, because")
    print("   no per-seed full-brain values exist (D-351).")
    print("")
    print("%6s %13s %13s %13s %13s"
          % ("n", "ACC-1 flip", "ACC-3 flip", "ACC-4 shape p", "ACC-4 onset p"))
    for n in a["candidate_n"]:
        e = a["per_n"][str(n)]
        f = a["acc4"]["per_n"][str(n)]
        print("%6d %12.2f%% %12.2f%% %13.2e %13.2e"
              % (n, 100 * e["acc1_flip_frac"],
                 100 * e["acc3_fixedref_flip_frac"],
                 f["p_shape_fail"], f["p_onset_fail"]))
    print("")
    print("   ACC-3 per rate, fraction of resamples inside tolerance:")
    hdr = "%6s" % "n"
    for r in VAL_RATES:
        hdr += "%12s" % ("%d Hz%s" % (r, "*" if a["d202"][str(r)]["excluded"]
                                      else ""))
    print(hdr)
    for n in a["candidate_n"]:
        line = "%6d" % n
        for r in VAL_RATES:
            v = a["per_n"][str(n)]["per_rate"][str(r)]
            line += "%11.1f%%" % (100 * v["acc3_within_tolerance_frac"])
        print(line)
    print("   * excluded from ACC-3 by D-202 and reported, not tested")
    print("")
    c = a["acc3_campaign"]
    print("B. RE-MEASUREMENT -- the full brain re-run too, so the reference")
    print("   moves as well.  MODELLED, and BRACKETED rather than assumed: the")
    print("   per-seed difference's sd is |s_full - s_sub| at correlation +1")
    print("   and sqrt(s_sub^2 + s_full^2) at correlation 0, which is D-351's")
    print("   bound.  The bracket spans correlation 0 to 1, not every possible")
    print("   value: the same seed drives the same stimulus neurons in both")
    print("   networks, so a NEGATIVE correlation -- which would be worse")
    print("   still, at s_full + s_sub -- is implausible by construction.")
    print("")
    print("%8s %10s %10s %10s %10s %12s %12s"
          % ("rate", "sub sd", "full sd", "diff", "tol", "sd(d) floor",
             "sd(d) bound"))
    for r in VAL_RATES:
        e = c["per_rate"][str(r)]
        print("%8s %10.3f %10.3f %10.3f %10.3f %12.3f %12.3f"
              % ("%d%s" % (r, "*" if e["excluded"] else ""), e["sub_sd_hz"],
                 e["full_sd_hz"], e["difference_hz"], e["tolerance_hz"],
                 e["diff_sd_correlated_hz"], e["diff_sd_independent_hz"]))
    print("")
    print("   P(ACC-3 passes) if the whole campaign were re-seeded, over the")
    print("   rates it tests (%s Hz):"
          % ", ".join(str(r) for r in c["rates_tested"]))
    print("%6s %16s %16s" % ("n", "best case", "D-351 bound"))
    for n in a["candidate_n"]:
        j = c["joint"][str(n)]
        print("%6d %15.1f%% %15.1f%%"
              % (n, 100 * j["p_pass_floor"], 100 * j["p_pass_bound"]))
    print("")
    print("   Seeds needed for that probability (cap %d; '>cap' means no"
          % c["scan_cap"])
    print("   attainable count, not a large one):")
    hdr = "%10s %10s" % ("target", "case")
    for r in c["rates_tested"]:
        hdr += "%10s" % ("%d Hz" % r)
    hdr += "%12s" % "all rates"
    print(hdr)

    def cell(v):
        return "%10s" % (">cap" if v is None else v)

    for target in sorted(c["seeds_needed"]):
        for name in ("floor", "bound"):
            e = c["seeds_needed"][target][name]
            line = "%10s %10s" % (target, "best" if name == "floor"
                                  else "bound")
            for r in c["rates_tested"]:
                line += cell(e["per_rate"][str(r)])
            line += "%12s" % (">cap" if e["joint"] is None else e["joint"])
            print(line)
    cost = doc.get("full_brain_cost")
    if cost:
        print("")
        print("   Full-brain compute those counts imply, scaling the recorded"
              " %d-seed run" % cost["recorded_seeds"])
        print("   (%d s for %d runs, x86-64 this host):"
              % (cost["recorded_elapsed_s"], cost["recorded_runs"]))
        for n, hours in cost["projected_hours"]:
            print("      %5d seeds -> %6.1f h" % (n, hours))
    print("")
    ch = doc["reproduction_check"]
    if ch.get("checked"):
        print("reproduction of the recorded %d-seed run (%s): %s"
              % (ch["seeds"], ch["source"],
                 "EXACT" if ch["agrees"] else "DISAGREES"))
    else:
        print("reproduction check skipped: %s" % ch["reason"])


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--seeds", type=int, default=SWEEP_SEEDS,
                   help="seeds to measure (default %d, D-352)" % SWEEP_SEEDS)
    p.add_argument("--jobs", type=int, default=14)
    p.add_argument("--network", default=NETWORK)
    p.add_argument("--reeval", action="store_true",
                   help="re-analyse the stored sweep without re-running")
    a = p.parse_args()

    full = ext.load_json(ext.ACC4, None)
    if full is None:
        raise SystemExit("need data/calibration/acc4.json for the full-brain "
                         "reference")

    if a.reeval:
        doc = ext.load_json(OUT, None)
        if doc is None:
            raise SystemExit("no %s to re-analyse" % OUT)
        per_rate = {int(k): v for k, v in doc["per_rate"].items()}
        seeds = doc["seeds"]
        elapsed = doc.get("sweep_elapsed_s", 0)
    else:
        if not os.path.isfile(a.network):
            raise SystemExit("no such network: %s (run `make fixtures`)"
                             % a.network)
        if not os.path.isfile(cal.RUNNET):
            raise SystemExit("no %s (run `make runner`)" % cal.RUNNET)
        seeds = list(range(1, a.seeds + 1))
        print("sweeping %s: %d rates x %d seeds at %d ms"
              % (os.path.basename(a.network), len(VAL_RATES), len(seeds),
                 cal.SIM_MS))
        per_rate, elapsed = sweep(a.network, seeds, a.jobs)
        print("sweep done in %d s" % round(elapsed))

    check = reproduction_check(per_rate, seeds)
    if check.get("checked") and not check["agrees"]:
        rows = sorted(check["per_rate"].items(),
                      key=lambda kv: int(kv[0]))
        for r, e in rows:
            print("%6s Hz recorded %.6f / %d  resweep %.6f / %d  %s"
                  % (r, e["recorded_mean_hz"], e["recorded_seeds_with_spike"],
                     e["resweep_mean_hz"], e["resweep_seeds_with_spike"],
                     "ok" if e["agrees"] else "DIFFERS"))
        raise SystemExit("the first 30 seeds do not reproduce the recorded "
                         "acceptance run; stopping rather than analysing "
                         "around a changed engine")

    doc = {
        "decisions": ["D-135", "D-165", "D-166", "D-202", "D-341", "D-351",
                      "D-352"],
        "closes": "TBD-06 (seeds per rate)",
        "network": a.network.replace("\\", "/"),
        "sim_ms": cal.SIM_MS,
        "seeds": seeds,
        "per_rate": {str(r): per_rate[r] for r in VAL_RATES},
        "sweep_elapsed_s": round(elapsed),
        "reproduction_check": check,
        "full_brain_source": "data/calibration/acc4.json (30 seeds, recorded)",
        "platform": ("x86-64 Windows 11, mingw32 gcc 6.3.0, NATIVE backend "
                     "(build/runnet.exe); analysis in CPython with numpy"),
    }
    doc["analysis"] = analyse(doc["per_rate"], full, seeds)
    doc["full_brain_cost"] = full_brain_cost(full, doc["analysis"])
    ext.save_json(OUT, doc)
    report(doc)
    print("")
    print("wrote %s" % OUT.replace("\\", "/"))


if __name__ == "__main__":
    main()
