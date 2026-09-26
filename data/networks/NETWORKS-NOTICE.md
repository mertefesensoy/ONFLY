## Notice for the ONFLY network files

This notice travels with the two network files ONFLY distributes. The
network format carries no text (SRS IR-NET-02), so the notice cannot live
inside the files; it is kept beside them, in `data/README.md`, and it is
printed by `tools/fixtures.py` whenever it places a network.

| File | Bytes | SHA-256 |
|---|---|---|
| `onfnet-malecns-v1.0-srext.bin` | 171,768 | `bf09a3ad18a82b8ecc0dd2fd397d81e332f38c98a78325269f5c39d2b3b1f66d` |
| `onfnet-malecns-v1.0-path.bin` | 951,200 | `168627c833d7af0f33bd0ed8d2bd1fbb407fd3c4436e0f57558c772cbb8b28f9` |

1. **Source.** These files contain data derived from the MaleCNS v1.0
   connectome by HHMI Janelia, the MRC Laboratory of Molecular Biology, the
   University of Cambridge and Google Research, licensed under CC BY 4.0,
   https://creativecommons.org/licenses/by/4.0/.
2. **Citation.** Berg, S. et al., "Sexual dimorphism in the complete
   Drosophila male central nervous system connectome", *Cell*
   189:5504-5526.e15 (2026), doi:10.1016/j.cell.2026.08.015. This is the
   citation SRS Appendix G records (D-538); it is checked again against the
   dataset's own page before any release.
3. **Dataset.** `male-cns:v1.0`, UUID `4b2087c0fbe046bfaf0d60bc970e3e5d`,
   https://male-cns.janelia.org/.
4. **Modified by ONFLY.** Neurons were selected (501 in `srext`, 913 in
   `path`); synapse counts were aggregated per neuron pair and signed from
   the presynaptic neuron's predicted neurotransmitter; each count was
   multiplied by a calibrated synaptic weight, W_syn = 0.2969 mV; a
   compensating-input table was added; and the result was encoded in ONFLY
   network format 1.1.
5. **FlyWire.** W_syn was fitted to a reference curve produced by re-running
   Shiu et al.'s published code on FlyWire connectome data, which FlyWire's
   guidelines place under CC BY-NC 4.0. ONFLY takes no position yet on
   whether W_syn, and so these files, are adapted material under FlyWire's
   terms. The question is open (SRS D-515) and is decided before any
   release.
6. **No endorsement** by the dataset's creators is implied.
7. **Licence of ONFLY's contribution.** ONFLY's own contribution to these
   files is released under CC BY 4.0 (SRS D-516), subject to how point 5 is
   decided.

The two other networks the project builds, `hop2` and `full`, are not
distributed (SRS D-545); they are regenerated with `prep/emit.py` from the
MaleCNS data.
