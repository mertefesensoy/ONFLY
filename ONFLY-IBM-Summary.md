# ONFLY

*A fruit fly's brain, served as a CICS transaction — on the fly.*

**Mert Efe Şensoy** · IBM Champion 2026 · IBM Z Student Ambassador and IBM Z Student Club President, TED University, Ankara · mertefesensoy.dev · github.com/mertefesensoy

## What it is

ONFLY runs part of a real animal's nervous system as a mainframe workload. It takes the complete male fruit fly connectome released by HHMI Janelia, the MRC Laboratory of Molecular Biology, the University of Cambridge and Google Research (MaleCNS v1.0, June 2026: over 166,000 neurons and 125 million synapses; primary paper in *Cell*, September 2026), extracts the circuit that turns a taste of sugar into a feeding response, and simulates it with the published model of Shiu et al. (*Nature*, 2024). Each simulation is a request and response: *"sugar at this rate for this long — what do the feeding motor neurons do?"*

## Why it matters for IBM Z

- **One engine across 45 years of the platform.** The same C engine and COBOL driver are being built to run on MVS 3.8j (1981) under Hercules and on Linux on s390x, and are designed to move to z/OS and behind CICS without rewriting the core.
- **Determinism as a feature.** Identical requests are required to produce identical fingerprints on every platform, and the verification plan tests exactly that. Floating point is implemented in software to IEEE 754, so results are bit-exact even on hardware with no IEEE floating point.
- **Transaction-shaped from day one.** The request/response record is a CICS COMMAREA. The engine is designed as a reentrant, threadsafe LINK target, with the network loaded once into shared storage.
- **Honest science.** Acceptance criteria are fixed in advance: the feeding response must appear with sugar and be exactly silent without it; the extracted circuit must stay within ±10% of the full-brain result; and the response curve must match the published model within ±25%.

## Status

Requirements are baselined (ONFLY-SRS v0.1, September 10, 2026). The MVP is being built in a home lab (MVS 3.8j TK5 on Hercules, and Linux s390x under QEMU). **Demonstration evidence: to be added when MVP acceptance passes.**

## Roadmap

1. **Lab MVP:** three-step JCL batch job ("BUZZ") on MVS 3.8j; identical results on Linux s390x.
2. **z/OS on IBM Z Xplore:** port and cross-platform determinism check on real IBM Z hardware.
3. **CICS:** a BUZZ menu transaction and per-stimulus transactions (SUGR, WATR, BITR).

## Request (draft — to be finalized)

1. Permission to run ONFLY batch workloads on IBM Z Xplore, with dataset space for the network file and test data.
2. Access to a CICS TS environment where program and transaction definitions are possible, for the CICS phase.

*Limits stated plainly: lab timings say nothing about IBM Z performance; agreement between a male connectome and a model calibrated on a female one shows consistency, not identity. CICS is an IBM trademark, used here descriptively.*
