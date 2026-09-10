# -*- coding: utf-8 -*-
"""MaleCNS v1.0 data sources (FR-PRP-01, decisions D-49 and D-51).

FR-PRP-01 requires the pipeline to retrieve MaleCNS v1.0 neuron identifiers,
cell types, pairwise synapse counts and predicted neurotransmitters from an
official source, and to record the dataset version, source and retrieval date
in a run manifest.

Why these files and not the neuPrint API. The published route is
``neuprint-python``, which requires creating an account and holding an API
token. The flat-connectome files below are served publicly from Google Cloud
Storage by the same project, need no account and no credential of any kind, and
carry the same v1.0 release. Nothing in this pipeline ever handles a secret.

The dataset identity is fixed by the neuPrint metadata endpoint rather than by
the file names, because a file name is not a version: ``male-cns:v1.0`` has
uuid 4b2087c0fbe046bfaf0d60bc970e3e5d.

Licence: CC BY 4.0 (D-50, closing the data-terms half of TBC-12). Attribution
is required wherever the data or artifacts derived from it appear.
"""

BASE = ("https://storage.googleapis.com/flyem-male-cns/v1.0"
        "/connectome-data/flat-connectome")

#: Dataset identity as reported by https://neuprint-cns.janelia.org/api/dbmeta/datasets
DATASET = "male-cns:v1.0"
DATASET_UUID = "4b2087c0fbe046bfaf0d60bc970e3e5d"
DATASET_LICENCE = "CC BY 4.0"
DATASET_CITE = ("Sexual dimorphism in the complete connectome of the "
                "Drosophila male central nervous system. Cell (2026). "
                "doi:10.1016/j.cell.2026.08.015")

#: key -> (filename, expected bytes, what FR-PRP-01 element it supplies)
FILES = {
    "annotations": (
        "body-annotations-male-cns-v1.0-minconf-0.5.feather",
        14483314,
        "neuron identifiers and cell types",
    ),
    "neurotransmitters": (
        "body-neurotransmitters-male-cns-v1.0.feather",
        43282834,
        "predicted neurotransmitters",
    ),
    "weights": (
        "connectome-weights-male-cns-v1.0-minconf-0.5.feather",
        1051241946,
        "pairwise synapse counts",
    ),
}

#: Files not retrieved, recorded so the omission is deliberate rather than an
#: oversight.  syn-points is 13.1 GB of individual synapse locations; ONFLY
#: needs aggregated pair counts only (FR-PRP-03).
NOT_RETRIEVED = {
    "body-stats-male-cns-v1.0-minconf-0.5.feather":
        "778,062,826 bytes; per-body statistics ONFLY does not use",
    "syn-points-male-cns-v1.0-minconf-0.5.feather":
        "13,061,489,098 bytes; individual synapse locations, superseded by "
        "aggregated pair counts (FR-PRP-03)",
    "syn-partners-male-cns-v1.0-minconf-0.5.feather":
        "per-synapse partner table, superseded by aggregated pair counts",
    "tbar-neurotransmitters-male-cns-v1.0.feather":
        "per-tbar predictions, superseded by the per-body consensus",
}


def url(key):
    """Return the download URL for a key in FILES."""
    return "%s/%s" % (BASE, FILES[key][0])
