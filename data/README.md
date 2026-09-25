# Data in this repository

Everything under `data/` is a record: a measurement, a recording of a run, or
a manifest of an artifact. Records are not edited after the fact. When one is
superseded or reads differently today, the explanation is written here or in
the SRS, and the file itself stays as it was written.

## What is here

| Directory | Contents | Evidence for |
|---|---|---|
| `networks/` | The manifest of the network files, the subcircuit selection and the two names files | SR-EXT, IR-NET, IR-NAM |
| `calibration/` | Full-brain and subcircuit measurements on x86-64: calibration, extraction, the acceptance criteria and the seed study | SR-CAL, SR-EXT, ACC-1 to ACC-4 |
| `malecns/` | The manifest of the MaleCNS files retrieved: dataset, UUID, digests, date | FR-PRP-01 |
| `geom/` | Soma positions for the live view, from the dataset's annotations | Phase G |
| `phase-d/` | x86-64 and Linux s390x (under QEMU) request, response and golden records | TX-01, TX-02, ACC-5 rows 1 to 5 |
| `phase-e/` | MVS 3.8j (under the Hercules emulator) listings and records, GCCMVS and JCC | ACC-5 rows 6 and 7, ACC-6, ACC-7 |
| `g0/` | The Gate G0 environment inventory | Gate G0 |

**What is not here.** The two network binaries (`srext`, 171,768 bytes, and
`path`, 951,200 bytes) are listed in `.gitignore` and are not yet distributed,
so `make test` cannot run from a clone yet; `networks/MANIFEST.json` holds
their digests. No raw MaleCNS data and no FlyWire data is committed. Nothing
here comes from IBM Z hardware: the project does not have IBM Z access yet
(SRS VL-139).

## Licence and attribution

Most of this directory is derived from the MaleCNS v1.0 connectome, dataset
`male-cns:v1.0`, UUID `4b2087c0fbe046bfaf0d60bc970e3e5d`, by HHMI Janelia, the
MRC Laboratory of Molecular Biology, the University of Cambridge and Google
Research, licensed under CC BY 4.0
(https://creativecommons.org/licenses/by/4.0/). Cite: Berg, S. et al.,
"Sexual dimorphism in the complete Drosophila male central nervous system
connectome", *Cell* 189:5504-5526.e15 (2026), doi:10.1016/j.cell.2026.08.015.

**Modified by ONFLY:** neurons selected, synapse counts aggregated per pair
and signed, multiplied by a calibrated synaptic weight of 0.2969 mV, a
compensating-input table added, and the results encoded, simulated and
measured. No endorsement by the dataset's creators is implied.

ONFLY's own contribution to these files is released under CC BY 4.0 (SRS
D-516), with one open exception below.

**`calibration/` is not assumed to be CC BY.** Twelve of its files embed
values of the Shiu reference curve, which was produced from FlyWire data
whose status for ONFLY is open (SRS D-515): `acc1-candidate.json`,
`acc4.json`, `acc4-phg9.json`, `acc4-right.json`, `acc4-tpgrn.json`,
`search-log.json`, `search-log-rerun.json`, `seeds.json`,
`wsens-d52-s30.json`, `wsens-right-s30.json`, `wsens-tpgrn-s30.json` and
`wsens-tpgrn-s4.json`. The synaptic weight fitted to that curve multiplies
every edge weight of every network. `THIRD_PARTY_NOTICES.md`, section 6,
says what this means and what FlyWire asks users to cite. None of this is
legal advice.

## Records that read differently today

**`calibration/acc4.json` says `"pass": false`, and the SRS reports ACC-4
PASS. Both are right.** The file was written on 2026-09-15 by `python
prep/acc4.py --jobs 14` (SRS VL-97), under ACC-4 as it then read, which
failed a rate whose magnitude fell outside tolerance. On 2026-09-16 D-340 and
D-341 amended ACC-4 so that the shape of the curve is the criterion and the
magnitude is reported, not tested. The measurement did not move; the
criterion did. `python prep/acc4.py --reeval data/calibration/acc4.json`
re-evaluates the same record under the amended criterion and prints ACC-4
PASS with the magnitude deviations at 10 and 40 Hz still named (VL-112). The
file is kept as written, as SRS D-526 decided, so the pre-amendment verdict
stays on the record. Both amendments were made after the results were seen.

**The ACC-3 margin at 40 Hz is 0.85 Hz.** `calibration/acc3-srext.json`
records a tolerance of 1.435 Hz and a difference of 0.5833 Hz, a margin of
0.8517 Hz. The SRS gave 0.56 Hz until 2026-09-25 (D-526); the conclusion it
drew is unchanged, because either figure is below the reference mean's 1.5425
Hz standard error.
