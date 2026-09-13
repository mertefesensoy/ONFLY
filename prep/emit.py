# -*- coding: utf-8 -*-
"""Emit ONFLY network files from the signed MaleCNS connectivity (FR-PRP-07).

Produces the two networks the owner chose in D-59:

  full   184,099 neurons, the calibration reference SR-CAL-01 requires and
         oracle O-2 for measuring ACC-3 truncation error later. Far too large
         for the 24-bit MVS region (C-01); an x86 reference by design.
  hop2   the 2-hop neighbourhood of the D-52 stimulus set, a fast working set.
         MN9 is first reached at hop 2 -- hop 1 yields 604 neurons and does not
         reach it -- so this provably contains the whole sugar-to-MN9 pathway.

Neither is the SR-EXT-01 subcircuit. That one is defined by activity in a
full-brain run and cannot be built until W_syn is calibrated, so both files here
are provisional with respect to SR-EXT.

Every constant comes from the SRS rather than from this file's judgement:

  dt 0.1 ms, T_dly 1.8 ms, t_rfr 2.2 ms, V_th -45 mV, V_rest -52 mV,
  tau_mbr 20 ms, tau_syn 5 ms      SR-MOD-02, all still TBC-02
  W_syn 0.2969 mV                  SR-MOD-02 as calibrated for MaleCNS by
                                   SR-CAL on 2026-09-12 (VL-63, D-173);
                                   the FlyWire origin was 0.275 mV
  G_EPS 2^-1022                    D-60
  maximum duration 1300 ms         D-138, measured on TK5 (TBD-06 closed)
  magic 0x4F4E4631                 IR-NET-03, final (TBD-09 closed, D-167)

The propagator coefficients are computed here on x86 in binary64 and shipped as
bit patterns; no target platform converts decimal to binary floating point
(FR-PRP-06, NR-06).

Run:  python prep/emit.py [full|hop2|both]
"""
import hashlib
import io
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "layout"))

import netwrite                              # noqa: E402
import signs                                 # noqa: E402
import sources                               # noqa: E402

OUT_DIR = os.path.join(ROOT, "data", "networks")
MAPPING = os.path.join(ROOT, "docs", "malecns-celltype-mapping.json")
MANIFEST = os.path.join(OUT_DIR, "MANIFEST.json")

# --- SR-MOD-02 (TBC-02: every one of these is unconfirmed) -----------------
DT_MS = 0.1
TAU_MBR_MS = 20.0
TAU_SYN_MS = 5.0
T_DLY_MS = 1.8
T_RFR_MS = 2.2
V_TH = -45.0
V_REST = -52.0
V_RESET = -52.0
W_SYN = 0.2969               # calibrated, VL-63 / D-173

# --- D-60 ------------------------------------------------------------------
G_EPS = 2.0 ** -1022          # smallest normal binary64; clamps exactly the
                              # subnormals and no normal value (NR-08)

# --- D-138: maximum simulated duration 1300 ms, measured on TK5 (TBD-06
# closed on this item; D-37's provisional 5000 ms superseded) --------------
MAX_MS = 1300

#: Integration method code for the header: 1 = exact propagator (IR-NET 4.1).
METHOD_EXACT = 1


def coefficients():
    """Exact-propagator coefficients for one timestep (SRS Appendix C).

    With u = v - V_rest, du/dt = (g - u)/tau_mbr and dg/dt = -g/tau_syn, one
    step of length dt is u' = P11*u + P12*g and g' = P22*g. Both exact
    integration and forward Euler reduce to that same linear update with
    different coefficients (SR-MOD-03), which is why the integration method
    changes constants and not code.
    """
    p11 = math.exp(-DT_MS / TAU_MBR_MS)
    p22 = math.exp(-DT_MS / TAU_SYN_MS)
    p12 = (TAU_SYN_MS / (TAU_SYN_MS - TAU_MBR_MS)
           * (math.exp(-DT_MS / TAU_SYN_MS) - math.exp(-DT_MS / TAU_MBR_MS)))
    return p11, p12, p22


def two_hop(pre, post, seeds):
    """Body ids reachable from ``seeds`` in at most two forward hops."""
    order = np.argsort(pre, kind="stable")
    pre_s, post_s = pre[order], post[order]
    seen = set(int(x) for x in seeds)
    frontier = np.asarray(seeds)
    for _ in range(2):
        lo = np.searchsorted(pre_s, frontier, "left")
        hi = np.searchsorted(pre_s, frontier, "right")
        if not len(frontier):
            break
        nxt = np.unique(np.concatenate(
            [post_s[a:b] for a, b in zip(lo, hi)])) if len(frontier) else []
        new = np.array([x for x in nxt if int(x) not in seen], dtype=pre.dtype)
        seen.update(int(x) for x in new)
        frontier = new
    return np.sort(np.fromiter(seen, dtype=pre.dtype, count=len(seen)))


def path_restricted(pre, post, stim, read):
    """Neurons on a stimulus-to-readout path within the two-hop horizon (D-74).

    MN9 is first reached at hop 2, so the path set is the stimulus neurons, the
    hop-1 neurons that are themselves presynaptic to a readout neuron, and the
    readouts.  Most hop-1 neurons are not: of 590 downstream of the stimulus
    set, only 12 reach MN9.

    The point is a network small enough for the Python oracle to run the whole
    golden suite, while still being real data in which MN9 actually spikes --
    so ACC-5's fingerprints stay sensitive to the kernel.
    """
    order = np.argsort(pre, kind="stable")
    pre_s, post_s = pre[order], post[order]
    lo = np.searchsorted(pre_s, stim, "left")
    hi = np.searchsorted(pre_s, stim, "right")
    hop1 = np.setdiff1d(
        np.unique(np.concatenate([post_s[a:b] for a, b in zip(lo, hi)])), stim)

    rorder = np.argsort(post, kind="stable")
    post_r, pre_r = post[rorder], pre[rorder]
    rlo = np.searchsorted(post_r, np.sort(read), "left")
    rhi = np.searchsorted(post_r, np.sort(read), "right")
    into_read = np.unique(
        np.concatenate([pre_r[a:b] for a, b in zip(rlo, rhi)]))

    # D-75 amends D-74.  Taking only the hop-1 neurons that reach a readout
    # ("on a path") gives 28 neurons in which MN9 NEVER FIRES: it has 321
    # presynaptic partners and needs their summed input to cross threshold.
    # The fixture is therefore stimulus + every hop-1 successor + every
    # presynaptic partner of the readouts + the readouts: 913 neurons, in which
    # MN9 fires and fingerprints are sensitive to the kernel.
    return np.unique(np.concatenate([stim, hop1, into_read, read]))


def build_network(arrays, nodes, stim_bodies, read_bodies, label,
                  w_syn=W_SYN, max_ms=MAX_MS,
                  gain_exc=None, gain_inh=None,
                  bias_rates=None, bias_rows=None):
    """Assemble one network file from a node subset.

    ``w_syn`` defaults to the module constant; prep/calibrate.py passes each
    SR-CAL-03 candidate through here so that a calibration network is built
    by exactly the code that builds the shipped one.

    ``gain_exc`` and ``gain_inh`` (D-186, D-187, D-188) are the weight
    compensation hook.  Each is either None or an array of one multiplier
    per kept neuron, in ascending body-id order -- the same order as
    ``np.sort(nodes)`` -- applied to the retained excitatory and inhibitory
    edges whose TARGET is that neuron.  They exist so that a truncated
    network can restore the expected synaptic drive that the dropped
    presynaptic neurons used to supply.

    A gain other than 1.0 is a deviation from SR-EXT-02, which requires the
    subcircuit to keep its connections "with unchanged weights".  D-187
    authorises it for the compared constructions; nothing calls this with a
    gain unless the caller is building one of them, and those networks live
    under data/calibration/, not data/networks/ (D-189).  No file-format
    change is involved: IR-NET-01's weight section is already f64.

    ``bias_rates`` and ``bias_rows`` carry the format v1.1 compensating-input
    table (D-190, D-191, IR-NET-09) straight through to netwrite.build, which
    checks its invariants.  Both None emits ``nbias`` = 0, which is what a
    network that drops nothing -- the full brain -- must carry.
    """
    pre, post = arrays["body_pre"], arrays["body_post"]
    sw = arrays["signed_weight"]

    keep = np.isin(pre, nodes) & np.isin(post, nodes)
    p, q, s = pre[keep], post[keep], sw[keep]

    # Contiguous indices, ascending by body id so the mapping is reproducible
    # and independent of edge order.
    nodes = np.sort(nodes)
    idx_pre = np.searchsorted(nodes, p)
    idx_post = np.searchsorted(nodes, q)

    # CSR requires rows grouped and targets ascending within a row (IR-NET-06).
    # Sorting by (pre, post) delivers both at once.
    order = np.lexsort((idx_post, idx_pre))
    idx_pre, idx_post, s = idx_pre[order], idx_post[order], s[order]

    n = len(nodes)
    rowptr = np.zeros(n + 1, dtype=np.int64)
    counts = np.bincount(idx_pre, minlength=n)
    rowptr[1:] = np.cumsum(counts)

    # SR-MOD-05: weight = synapse count x sign x W_syn.  The count already
    # carries its sign from prep/signs.py; W_syn is applied here and only here.
    weight = s.astype(np.float64) * w_syn

    # D-187 compensation, if the caller asked for it.  The multiplier is
    # chosen by the TARGET neuron and the SIGN of the edge, so it is indexed
    # by idx_post -- which is already the position of that neuron in the
    # sorted node list, the order gain_exc and gain_inh are given in.
    if gain_exc is not None or gain_inh is not None:
        ge = np.ones(n) if gain_exc is None else np.asarray(gain_exc,
                                                            dtype=np.float64)
        gi = np.ones(n) if gain_inh is None else np.asarray(gain_inh,
                                                            dtype=np.float64)
        if len(ge) != n or len(gi) != n:
            raise ValueError("gain arrays must have one entry per kept "
                             "neuron (%d), got %d and %d"
                             % (n, len(ge), len(gi)))
        weight = weight * np.where(s > 0, ge[idx_post], gi[idx_post])

    p11, p12, p22 = coefficients()
    blob = netwrite.build(
        n=n,
        rowptr=rowptr.tolist(),
        target=idx_post,
        weight=weight,
        stim=np.searchsorted(nodes, np.sort(stim_bodies)),
        readout=np.searchsorted(nodes, np.sort(read_bodies)),
        dt_us=int(round(DT_MS * 1000)),
        delay=int(round(T_DLY_MS / DT_MS)),
        refract=int(round(T_RFR_MS / DT_MS)),
        max_ms=max_ms,
        u_th=V_TH - V_REST,
        u_reset=V_RESET - V_REST,
        p11=p11, p12=p12, p22=p22,
        g_eps=G_EPS, w_syn=w_syn, v_rest=V_REST,
        method=METHOD_EXACT,
        bias_rates=bias_rates, bias_rows=bias_rows)
    print("  %-6s n=%-7d e=%-9d %10d bytes" % (label, n, len(idx_post), len(blob)))
    return blob, n, len(idx_post)


def scan_existing():
    """Digest every network file already present, so the manifest is complete."""
    import zlib
    found = {}
    if not os.path.isdir(OUT_DIR):
        return found
    for name in sorted(os.listdir(OUT_DIR)):
        if not name.endswith(".bin"):
            continue
        label = name.replace("onfnet-malecns-v1.0-", "").replace(".bin", "")
        blob = io.open(os.path.join(OUT_DIR, name), "rb").read()
        n = int.from_bytes(blob[20:24], "big")
        e = int.from_bytes(blob[24:28], "big")
        found[label] = {
            "file": name, "neurons": n, "edges": e, "bytes": len(blob),
            "sha256": hashlib.sha256(blob).hexdigest(),
            "crc32": "%08X" % (zlib.crc32(blob) & 0xFFFFFFFF),
        }
    return found


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "both"
    if not os.path.isdir(OUT_DIR):
        os.makedirs(OUT_DIR)

    mapping = json.load(io.open(MAPPING, encoding="utf-8"))
    stim_bodies = np.array(mapping["stimulus_set"]["bodyIds"], dtype=np.int64)
    read_bodies = np.array(mapping["readout"]["bodyIds"], dtype=np.int64)

    print("applying D-54, D-55 and D-56 ...")
    arrays, stats = signs.build_signs(verbose=False)
    pre, post = arrays["body_pre"], arrays["body_post"]
    print("  signed connectivity: %d pairs, %d synapses"
          % (len(pre), stats["synapses_kept"]))

    targets = {}
    if which in ("full", "both"):
        targets["full"] = np.union1d(np.unique(pre), np.unique(post))
    if which in ("hop2", "both"):
        hop = two_hop(pre, post, stim_bodies)
        targets["hop2"] = np.union1d(hop, read_bodies)
    if which in ("path", "both"):
        targets["path"] = path_restricted(pre, post, stim_bodies, read_bodies)

    # The manifest describes what is on disk, not merely what this run emitted.
    # Running `emit.py full` must not erase the record of a network already
    # written: a manifest that silently forgets an artifact is worse than none,
    # because it is trusted.
    entries = scan_existing()
    for label in sorted(targets):
        nodes = targets[label]
        for name, ids in (("stimulus", stim_bodies), ("readout", read_bodies)):
            missing = [int(b) for b in ids if b not in set(nodes.tolist())]
            if missing:
                raise SystemExit(
                    "%s: %s neurons absent from the node set: %s. The network "
                    "would have no %s, which is not a network worth emitting."
                    % (label, name, missing, name))
        blob, n, e = build_network(arrays, nodes, stim_bodies, read_bodies, label)
        path = os.path.join(OUT_DIR, "onfnet-malecns-v1.0-%s.bin" % label)
        io.open(path, "wb").write(blob)
        entries[label] = {
            "file": os.path.basename(path),
            "neurons": int(n), "edges": int(e), "bytes": len(blob),
            "sha256": hashlib.sha256(blob).hexdigest(),
            "crc32": "%08X" % (__import__("zlib").crc32(blob) & 0xFFFFFFFF),
        }

    p11, p12, p22 = coefficients()
    man = {
        "dataset": sources.DATASET,
        "dataset_uuid": sources.DATASET_UUID,
        "decisions": ["D-52", "D-54", "D-55", "D-56", "D-59", "D-60", "D-138",
                      "D-167", "D-173", "D-175"],
        "parameters": {
            "dt_ms": DT_MS, "tau_mbr_ms": TAU_MBR_MS, "tau_syn_ms": TAU_SYN_MS,
            "t_dly_ms": T_DLY_MS, "t_rfr_ms": T_RFR_MS,
            "V_th": V_TH, "V_rest": V_REST, "V_reset": V_RESET,
            "W_syn": W_SYN, "G_EPS": G_EPS, "max_ms": MAX_MS,
            "p11": p11, "p12": p12, "p22": p22,
            "status": "SR-MOD-02 values confirmed (TBC-02 closed by D-66); "
                      "W_syn calibrated for MaleCNS (SR-CAL, VL-63, D-173); "
                      "max_ms 1300 per D-138; magic final per D-167",
        },
        "stimulus_types": mapping["stimulus_set"]["types"],
        "readout_type": mapping["readout"]["type"],
        "networks": entries,
        "limits": ["VL-12", "VL-13"],
        "not_the_srext_subcircuit": (
            "SR-EXT-01 defines the MVP subcircuit by activity in a full-brain "
            "run, which needs W_syn calibrated first. Both files are "
            "provisional with respect to SR-EXT."),
    }
    io.open(MANIFEST, "w", encoding="utf-8", newline="\n").write(
        json.dumps(man, indent=2, sort_keys=True) + "\n")
    print("wrote %s" % MANIFEST.replace("\\", "/"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
