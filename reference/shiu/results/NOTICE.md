# Notice: the Shiu reference curve

`mn9-reference.csv` in this directory is the MN9 firing-rate curve ONFLY
calibrates and validates against (SRS SR-CAL-04, D-164). It was produced on
2026-09-12 by `reference/shiu/rerun.py`, which re-runs the Figure 1D protocol
of Shiu et al. (2024) with their published MIT code (`model.py`, `utils.py`)
on FlyWire connectome files from snapshot 630. Those FlyWire files are not in
this repository; their digests are in `MANIFEST.json` beside this file.

FlyWire's guidelines (https://flywire.ai/guidelines) state that its public
release data is under CC BY-NC 4.0, a non-commercial licence. That page names
release v783 and does not name snapshot 630 explicitly.

**Status: open.** ONFLY takes no position yet on whether this curve, the
files that embed its values, or the synaptic weight fitted to it, is adapted
material under FlyWire's terms (SRS D-515). Until that is decided, nothing
here relicenses FlyWire data, and the MIT licence in the repository's
`LICENSE` is not claimed for this directory. `THIRD_PARTY_NOTICES.md`,
section 6, lists every path this affects and the papers FlyWire asks users to
cite. This notice is not legal advice.
