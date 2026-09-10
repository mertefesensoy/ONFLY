# ONFLY — Software Requirements Specification

*A fruit fly's brain, served as a CICS transaction — on the fly.*

| Field | Value |
|---|---|
| Document | ONFLY-SRS |
| Version | 0.1 — Draft for owner review |
| Date | 2026-09-10 |
| Owner | Mert Efe Şensoy |
| Status | Requirements baselined through the owner question rounds; phase ordering (Section 9) signed off by the owner 2026-09-10 (D-24) |
| Standard | Structure follows ISO/IEC/IEEE 29148 (requirements engineering) |
| Source of truth | This Markdown file in the repository. The .docx is an export. |

> **How to read this document.** Every requirement has an ID, a statement using "shall", and a verification method. Every decision made during the question rounds is recorded with its rationale in Appendix A (decision log). Everything not yet known is marked **TBC** (to be confirmed) or **TBD** (to be decided) and listed in Appendix B. What the verification program can and cannot prove is stated explicitly in Appendix D.

## 1. Introduction

### 1.1 Purpose

This document specifies the requirements for the ONFLY minimum viable product (MVP): a deterministic, connectome-constrained simulation of the *Drosophila melanogaster* sugar-to-feeding sensorimotor pathway, executed as a request/response workload on MVS 3.8j (TK5 on Hercules) and on Linux for s390x (QEMU), and architected so that the same engine can later run on z/OS (IBM Z Xplore) and behind IBM CICS transactions.

The document serves three readers: the owner and future collaborators (engineering baseline), agentic development tools that build from it (for example Claude Code), and IBM reviewers evaluating a request for project permissions (via the separate one-page summary).

### 1.2 Scope

**In scope for the MVP:**

- An x86 preparation pipeline that turns the MaleCNS v1.0 connectome into a calibrated, validated subcircuit network file.
- A portable C simulation engine (ONFLYENG) implementing a Shiu-style leaky integrate-and-fire model in IEEE 754 binary64 arithmetic.
- A software floating-point backend (Berkeley SoftFloat) so the engine runs on hardware without IEEE floating point, plus an optional native backend admitted only where bit-identity is proven.
- A COBOL driver (ONFLYDRV) and a three-step JCL batch pipeline on MVS 3.8j.
- A Linux s390x build of the same engine with a file adapter.
- A Python reference oracle and a verification program proving cross-platform determinism and scientific acceptance.

**Stretch goal (not required for MVP completion):** a direct COBOL-to-C CALL on MVS 3.8j through an assembler stub.

**Out of scope for the MVP:** CICS deployment (Phase 4), running the full brain on MVS, synaptic plasticity or learning, embodiment or motor simulation, real-time visualization, and any stimulus other than sugar (the WATR and BITR codes are reserved, see FR-BAT-05).

### 1.3 Product summary

ONFLY answers one kind of question: *"If this fly tastes sugar at rate R for T milliseconds, what do its feeding motor neurons do?"* A request carries a stimulus code, a stimulus rate, a duration and a random seed. The response carries spike counts and first-spike latencies for the readout neurons (MN9 in the MVP), a return code, and a canonical fingerprint. Identical requests must produce identical fingerprints on every supported platform — from a 1981 operating system under emulation to modern hardware.

### 1.4 Document conventions

| Convention | Meaning |
|---|---|
| shall / should / may | Mandatory / recommended / optional |
| FR-, IR-, NR-, SR-, ACC-, NFR- | Functional, interface, numerical, scientific, acceptance, non-functional requirement |
| Verification: T / A / I / D | Test / Analysis / Inspection / Demonstration |
| D-nn | Decision in Appendix A |
| TBC-nn / TBD-nn | Open item in Appendix B |
| VL-nn | Verification limit in Appendix D |
| ⊕ ⊗ | Correctly rounded IEEE 754 binary64 addition and multiplication (round to nearest, ties to even) |

## 2. Overall description

### 2.1 Product perspective

ONFLY is a new, self-contained system. It depends on published scientific data (the MaleCNS v1.0 connectome, released September 3, 2026 by HHMI Janelia and Google Research) and on a published model (Shiu et al., *Nature* 634:210–219, 2024), but on no running external service.

The end-to-end data flow for the MVP:

```
 x86 DEV HOST                              MVS 3.8j (TK5 / Hercules)
 ------------                              -------------------------
 MaleCNS v1.0 ──► PREP PIPELINE            //ONFLYJOB JOB
   (neuPrint)       - aggregate + sign     //STEP1  ONFLYDRV (COBOL, MODE=REQ)
                    - full-brain run          control cards ──► ONFREQ (requests)
                    - calibrate W_syn      //STEP2  ONFLYENG (C, GCCMVS)
                    - extract top-N           ONFNET + ONFREQ ──► ONFRSP
                    - emit network file    //STEP3  ONFLYDRV (COBOL, MODE=RPT)
        │                                     ONFRSP + ONFNAM ──► ONFRPT (report)
        ├── ONFNET  (binary, big-endian) ─────► transport (binary-transparent)
        ├── ONFNAM  (text names)  ────────────► transport (text mode)
        └── golden suite + oracle outputs

 LINUX s390x (QEMU): same ONFLYENG source + file adapter, same records,
                     same fingerprints.
```

### 2.2 Architecture overview

The engine follows a ports-and-adapters structure. The simulation core is pure: it performs no I/O, no dynamic allocation after initialization, and no platform calls. Everything platform-specific lives in adapters or in the float backend.

| Component | Role | Language |
|---|---|---|
| ONFLYENG core | Network decode, integrity checks, simulation kernel, response building | C (C89 + long long, see NR-04) |
| Float layer (onf_fp) | One API for binary64 operations; two backends: soft (SoftFloat) and native | C |
| Batch file adapter | Reads request records, writes response records (MVS and Linux) | C |
| COBOL-call adapter | Stretch goal: entry point callable from COBOL via assembler stub | C + S/370 assembler |
| CICS adapter | Future (Phase 4): LINK target with COMMAREA | C |
| ONFLYDRV | Builds requests from control cards; formats the printed report | COBOL (MVT/Enterprise intersection) |
| Layout generator | Single master definition generating the COBOL copybook, C header and Python struct formats | Python |
| Prep pipeline | Data retrieval, aggregation, calibration, extraction, file emission | Python |
| Oracle | Bit-exact reference of the kernel in plain Python floats | Python |

### 2.3 Platform matrix

| Platform | Role in ONFLY | Toolchain | Hazards this platform exposes |
|---|---|---|---|
| x86-64 development host | Prep pipeline, oracle, full-brain reference runs (native backend), layout generation | Python 3, gcc or clang | Reference only; x87 extended precision must not be used |
| TK5 (MVS 3.8j, Update 5) on SDL Hercules 4.9.1 | Reference legacy target for the MVP | GCCMVS + PDPCLIB (primary), JCC (cross-check), MVT COBOL (IKFCBL00) | EBCDIC, no IEEE floating point, 24-bit addressing, no Language Environment, 1968-era COBOL, 8-character external names |
| Linux s390x under QEMU | Big-endian target with a modern toolchain | gcc, strict warnings, sanitizers where supported | Byte order, strict C conformance; floating point is emulated by QEMU (VL-01) |
| z/OS on IBM Z Xplore | Phase 3 target | IBM compilers as available to the user ID (TBC) | Real hardware; no CICS resource definition available (D-23) |
| CICS TS region | Phase 4 target | Source TBD (TBD-13) | QR TCB blocking, runaway-task timeout, shared storage |

### 2.4 User classes

| User class | Needs |
|---|---|
| Owner / developer | A complete, unambiguous baseline to build and verify against |
| Agentic build tools | Stable requirement IDs, explicit acceptance criteria, normative algorithms (Appendix C) |
| Operator | Runnable JCL, clear return codes and messages (Appendix E) |
| IBM reviewers | A credible demo and a one-page summary; honest statement of limits |

### 2.5 Constraints

| ID | Constraint |
|---|---|
| C-01 | MVS 3.8j provides 24-bit addressing; the usable region is single-digit megabytes (exact value TBD-14). |
| C-02 | S/370 has no IEEE binary floating point; only hexadecimal floating point (HFP) exists in hardware. |
| C-03 | The MVS 3.8j COBOL compiler is the OS/360 MVT ANS COBOL compiler: no scope terminators (END-IF), no inline PERFORM, no COMP-5, restricted IF nesting, and only partial COPY support. |
| C-04 | C89 guarantees only 6 significant, case-insensitive characters for external identifiers; the MVS linkage editor accepts 8 uppercase characters. |
| C-05 | There is no Language Environment on MVS 3.8j; GCCMVS programs rely on PDPCLIB's own startup. |
| C-06 | PDPCLIB is strictly C89 and provides no `stdint.h` or `stdbool.h`. |
| C-07 | IBM Z Xplore does not allow the user to define CICS programs or transactions. |
| C-08 | "CICS" is an IBM trademark; it appears only descriptively (tagline, documentation), never in component names. |

### 2.6 Assumptions and dependencies

| ID | Assumption / dependency | Status |
|---|---|---|
| A-01 | MaleCNS v1.0 connectivity (neuron IDs, cell types, pairwise synapse counts, predicted neurotransmitters) is retrievable programmatically. | TBC in Phase 0 |
| A-02 | Shiu et al.'s model code is public and specifies integration method, event ordering and stimulation protocol. | TBC-01 |
| A-03 | GCCMVS is installed or installable on TK5 (`LISTC LEVEL(GCC)`, `LISTC LEVEL(PDPCLIB)`). | TBC at Gate G0 |
| A-04 | JCC is installed or installable on TK5 (`LISTC LEVEL(JCC)`). | TBC at Gate G0 |
| A-05 | GCCMVS synthesizes correct 64-bit integer arithmetic for `long long` on S/370. | Unverified; Gate G1 |
| A-06 | Berkeley SoftFloat 3e compiles as C89 + `long long` with project-supplied `stdint`/`stdbool` shims. | Unverified; Gate G1 |
| A-07 | At least one binary-transparent transport into TK5 exists (IND$FILE, AWS tape image, or card reader in raw mode). | Gate G2 |

## 3. Functional requirements

### 3.1 Preparation pipeline (x86)

| ID | Requirement | Verification |
|---|---|---|
| FR-PRP-01 | The pipeline shall retrieve MaleCNS v1.0 neuron identifiers, cell types, pairwise synapse counts and predicted neurotransmitters from an official source, and shall record the dataset version, source and retrieval date in a run manifest. | I — manifest review |
| FR-PRP-02 | The pipeline shall identify the sugar-sensing gustatory receptor neurons (stimulus set) and the MN9 motor neurons (readout set) by cell type. The mapping shall be written to a reviewed table and approved by the owner before calibration (TBC-03). | I |
| FR-PRP-03 | The pipeline shall aggregate synapses into directed neuron-pair counts and assign each pair a sign from the presynaptic neuron's predicted neurotransmitter, following Shiu et al.'s classification (TBC-04). | T — TP-01 |
| FR-PRP-04 | The pipeline shall run the full MaleCNS brain through the ONFLY engine on x86 (native backend, admitted per NR-09) for the stimulus protocol of SR-MOD-04. | D |
| FR-PRP-05 | The pipeline shall perform W_syn calibration per SR-CAL and subcircuit extraction per SR-EXT, and shall record every chosen value (W_syn, N, selected neuron list) in the manifest. | I |
| FR-PRP-06 | The pipeline shall compute every floating-point constant (propagator coefficients, weights, thresholds, clamp epsilon) once on x86 in binary64 and serialize the bit patterns. No target platform shall perform decimal-to-binary floating-point conversion. | I — NR-06 |
| FR-PRP-07 | The pipeline shall emit the network file (IR-NET), the names file (IR-NAM), the golden request suite (Section 8.4) with oracle outputs, and a manifest containing CRC-32 and SHA-256 digests of every artifact. | T — TP-02 |
| FR-PRP-08 | The pipeline shall emit transport artifacts for each candidate transport under evaluation (IND$FILE-ready binary, AWS tape image, raw card deck). After Gate G2, only the winning transport is required. | D — S2 |
| FR-PRP-09 | Given identical inputs and configuration, the pipeline shall produce byte-identical artifacts. | T — TP-03 |

### 3.2 Network load and integrity

| ID | Requirement | Verification |
|---|---|---|
| FR-LOD-01 | ONFLYENG shall load the network file once per job step (MVS, Linux) or once per region initialization (CICS, future), before processing any request. | I |
| FR-LOD-02 | Before any simulation, ONFLYENG shall verify, in order: magic constant, byte-order sentinel, format version, header CRC-32, declared payload length, and payload CRC-32. The first failing check shall end the step with the message and return code defined in Appendix E. | T — TE-01..06 |
| FR-LOD-03 | ONFLYENG shall reconstruct the network byte stream from fixed-length records and shall trust the header's declared length, not the dataset size (IR-NET-08). | T — TE-07 |
| FR-LOD-04 | ONFLYENG shall compute the memory needed for the decoded network and simulation state from header counts, and shall fail with ONF105E before allocation if it exceeds the configured limit. | T — TE-08 |
| FR-LOD-05 | ONFLYENG shall decode every multi-byte field with explicit byte shifts. Pointer casts over file buffers are prohibited. | I — code review, lint |

### 3.3 Simulation engine

| ID | Requirement | Verification |
|---|---|---|
| FR-SIM-01 | ONFLYENG shall implement the neuron and synapse model of SR-MOD-01 using the step algorithm of Appendix C. | T — golden suite |
| FR-SIM-02 | The timestep shall be read from the network header, both as a binary64 value (provenance) and as an integer number of microseconds (used for all reporting arithmetic). | I |
| FR-SIM-03 | Stimulus neurons shall be driven by per-timestep Bernoulli draws approximating a Poisson process at the requested rate, using the integer-only procedure of NR-12. | T — TU-05 |
| FR-SIM-04 | The pseudo-random generator shall be seeded from the request seed and consumed in the order specified in Appendix C, so that every platform draws the same sequence. | T — TU-04 |
| FR-SIM-05 | For each readout neuron, ONFLYENG shall report the spike count and the first-spike latency in integer microseconds (−1 if the neuron did not spike). | T |
| FR-SIM-06 | Simulated duration shall be taken from the request and bounded by the header's maximum (TBD-06). Out-of-range requests shall return ONF202E without simulating. | T — TE-10 |
| FR-SIM-07 | The simulation core shall perform no I/O and no dynamic allocation after initialization. | I |
| FR-SIM-08 | ONFLYENG shall abort the request with ONF903S if any state value becomes NaN or infinity (detected from exponent bits, not by float comparison). | T — TU-08 |
| FR-SIM-09 | ONFLYENG shall compute the response fingerprint per IR-COM-05. | T |

### 3.4 Batch pipeline and request/response

| ID | Requirement | Verification |
|---|---|---|
| FR-BAT-01 | The MVP shall run as one job of three steps: STEP1 ONFLYDRV in request mode (control cards → request dataset ONFREQ), STEP2 ONFLYENG (ONFNET + ONFREQ → ONFRSP), STEP3 ONFLYDRV in report mode (ONFRSP + ONFNAM → printed report). | D |
| FR-BAT-02 | Each step shall set a return code per IR-JCL-04, and later steps shall be conditioned on earlier return codes. | T — TE-11 |
| FR-BAT-03 | ONFLYDRV shall be a single COBOL source that compiles unchanged under MVT COBOL (MVS 3.8j) and, later, Enterprise COBOL (D-17). Mode is selected by a control card. | T on MVS; A via GnuCOBOL proxy (VL-02) |
| FR-BAT-04 | The report shall show, per request: the request echo, each readout neuron's name, spike count, first-spike latency and firing rate in Hz (one decimal), the return code with its message, and the response fingerprint in hexadecimal. | D |
| FR-BAT-05 | The stimulus codes shall be SUGR (implemented), WATR and BITR (reserved). A reserved code shall return ONF201W with no simulation. | T — TE-12 |
| FR-BAT-06 | The job that runs the full demonstration (all golden requests plus the report) shall be named BUZZ, mirroring the future CICS menu transaction. Single-stimulus jobs shall be named after their stimulus code (SUGR). | I |

### 3.5 Linux s390x adapter

| ID | Requirement | Verification |
|---|---|---|
| FR-LNX-01 | The Linux build shall read the same request records and write the same response records as the MVS build, using ordinary files. | T — TX-01 |
| FR-LNX-02 | The Linux build shall be produced from the same engine source; only the platform configuration header may differ. | I |

### 3.6 Stretch: direct COBOL CALL on MVS 3.8j

| ID | Requirement | Verification |
|---|---|---|
| FR-CAL-01 | *(Stretch.)* An S/370 assembler stub shall initialize the PDPCLIB runtime once and allow ONFLYDRV to CALL ONFLYENG with the COMMAREA layout, producing responses identical to the batch path. | T — TX-05 |

### 3.7 Future: CICS (informative, not MVP)

This subsection is informative. It records design obligations so that MVP decisions do not block Phase 4.

- **BUZZ** will be a menu transaction (BMS screen) that lets the user pick a stimulus, rate, duration and seed. **SUGR**, **WATR** and **BITR** will be direct transactions for each stimulus.
- ONFLYENG will be LINKed with the COMMAREA of IR-COM. It must therefore be reentrant and threadsafe, and be defined with CONCURRENCY(REQUIRED) so that CPU-heavy work runs on an open TCB rather than blocking the QR TCB.
- The network will be loaded once at region startup into shared storage and anchored for all tasks; transactions only read it.
- Request duration must stay under the region's runaway-task interval (ICVR; the default is 5 seconds unless the region configures otherwise).

## 4. External interface requirements

### 4.1 Network file (ONFNET)

| ID | Requirement | Verification |
|---|---|---|
| IR-NET-01 | The network file shall be a byte stream: a fixed header followed by a payload of aligned sections. All integers are big-endian two's complement or unsigned as stated; all floating-point values are IEEE 754 binary64, big-endian (sign and exponent byte first). | T — TU-06 |
| IR-NET-02 | The file shall contain no text. Neuron type names travel in the names file (IR-NAM). | I |
| IR-NET-03 | The magic constant shall be compared as an integer on every platform. Its value (proposed 0x4F4E4631) is final at format version 1.0 (TBD-09). | T — TE-01 |
| IR-NET-04 | The byte-order sentinel shall be 0x01020304. Any other decoded value shall fail with ONF102E. | T — TE-02 |
| IR-NET-05 | Payload sections shall start on 8-byte boundaries relative to the start of the file; padding bytes shall be zero. | T |
| IR-NET-06 | Within each source neuron's row, target indices shall be strictly ascending. This order is normative for floating-point accumulation (Appendix C). | T — TP-04 |
| IR-NET-07 | Header CRC-32 covers header bytes 0–159; payload CRC-32 covers exactly the declared payload length. The CRC is CRC-32/ISO-HDLC (the zlib polynomial), so Python's `zlib.crc32` is the reference. | T — TU-03 |
| IR-NET-08 | On MVS the file shall be stored as RECFM=FB, LRECL=80, zero-padded at the end. The header's declared length is authoritative. | T — TE-07 |

**Header layout (format version 1.0, draft):**

| Offset | Size | Type | Field |
|---|---|---|---|
| 0 | 4 | u32 | Magic constant |
| 4 | 4 | u32 | Byte-order sentinel (0x01020304) |
| 8 | 2 | u16 | Format major version |
| 10 | 2 | u16 | Format minor version |
| 12 | 4 | u32 | Header length in bytes (164) |
| 16 | 4 | u32 | Flags (reserved, zero) |
| 20 | 4 | u32 | Neuron count N |
| 24 | 4 | u32 | Edge count E |
| 28 | 4 | u32 | Stimulus-set count S |
| 32 | 4 | u32 | Readout count R (≤ 32) |
| 36 | 4 | u32 | Timestep in microseconds (dt_us) |
| 40 | 4 | u32 | Synaptic delay in steps (D) |
| 44 | 4 | u32 | Refractory period in steps |
| 48 | 4 | u32 | Maximum simulated duration in ms |
| 52 | 4 | u32 | Integration method code (1 = exact propagator, 2 = forward Euler; provenance only, see Appendix C) |
| 56 | 8 | f64 | Timestep dt (provenance) |
| 64 | 8 | f64 | U_th = V_th − V_rest |
| 72 | 8 | f64 | U_reset = V_reset − V_rest |
| 80 | 8 | f64 | P11 (membrane-to-membrane coefficient) |
| 88 | 8 | f64 | P12 (synaptic-to-membrane coefficient) |
| 96 | 8 | f64 | P22 (synaptic decay coefficient) |
| 104 | 8 | f64 | G_EPS (subnormal clamp threshold, NR-08) |
| 112 | 8 | f64 | W_syn used (provenance) |
| 120 | 8 | f64 | V_rest (provenance, for reporting in mV) |
| 128 | 4 | u32 | Offset: neuron table |
| 132 | 4 | u32 | Offset: CSR row pointers |
| 136 | 4 | u32 | Offset: CSR target indices |
| 140 | 4 | u32 | Offset: weights |
| 144 | 4 | u32 | Offset: stimulus list |
| 148 | 4 | u32 | Offset: readout list |
| 152 | 4 | u32 | Payload length in bytes |
| 156 | 4 | u32 | Payload CRC-32 |
| 160 | 4 | u32 | Header CRC-32 (bytes 0–159) |

**Payload sections:**

| Section | Contents |
|---|---|
| Neuron table | N records of 8 bytes: type ID (u32), flags (u32; bit 0 = stimulus, bit 1 = readout) |
| CSR row pointers | N + 1 values (u32) |
| CSR target indices | E values (u32), strictly ascending within each row |
| Weights | E values (f64): synapse count × sign × W_syn, computed on x86 |
| Stimulus list | S neuron indices (u32), ascending |
| Readout list | R neuron indices (u32), ascending |

### 4.2 Names file (ONFNAM)

| ID | Requirement | Verification |
|---|---|---|
| IR-NAM-01 | The names file shall be text, RECFM=FB, LRECL=80: columns 1–5 type ID (zero-padded decimal), column 6 blank, columns 7–40 type name, left-aligned. | I |
| IR-NAM-02 | Type names shall use only A–Z, 0–9, underscore, hyphen and period. The prep pipeline shall uppercase names and replace any other character with an underscore, recording the original name in the manifest. | T — TP-05 |
| IR-NAM-03 | The names file shall be transferred in text mode so that ASCII-to-EBCDIC conversion happens in transport. | D — S2 |

### 4.3 COMMAREA and request/response records

The request and response records share one layout, the COMMAREA, so that the batch path (MVP) and the CICS path (Phase 4) use identical bytes. Record length is 412 bytes.

| ID | Requirement | Verification |
|---|---|---|
| IR-COM-01 | The layout shall be defined once in a master definition. The COBOL copybook, the C header (with size and offset assertions) and the Python struct format shall be generated from it; generated files shall never be edited by hand (D-18). If COPY fails under MVT COBOL, the generator shall inline the layout into the COBOL source. | I; T — TU-07 |
| IR-COM-02 | Binary fields shall use COMP (halfword or fullword binary) with documented value ranges that always fit the PIC digits, so that the TRUNC compiler option can never change a value. COMP-5 shall not be used (unsupported by MVT COBOL). | I |
| IR-COM-03 | Every field shall be naturally aligned (2-byte fields at even offsets, 4-byte fields at multiples of 4), so C and COBOL agree without packing directives. | T — TU-07 |
| IR-COM-04 | All binary fields shall be big-endian on every platform. The x86 build shall encode and decode them explicitly. | T |
| IR-COM-05 | The response fingerprint shall be the CRC-32 of a canonical byte string: the network payload CRC, then the numeric stimulus ID, seed, rate, duration, return code, output count and step count, then each output entry (ID, latency, spike count) for entries below the output count — each encoded as a big-endian 32-bit integer. Text fields are excluded, so the fingerprint is identical on ASCII and EBCDIC hosts. | T — TX-02 |
| IR-COM-06 | Response entries shall carry numeric readout identifiers, never names; ONFLYDRV maps identifiers to names from ONFNAM. | I |

**Layout (generated; shown here for review):**

| Offset | COBOL field | PIC / usage | C type | Range / meaning |
|---|---|---|---|---|
| 0 | ONF-STIM-CODE | X(8) | char[8] | 'SUGR', 'WATR', 'BITR', padded with spaces (host code page) |
| 8 | ONF-SEED | S9(9) COMP | int32 | 0 to 999,999,999 |
| 12 | ONF-STIM-RATE | S9(4) COMP | int16 | 0 to 9,999 Hz |
| 14 | ONF-SIM-MS | S9(4) COMP | int16 | 1 to header maximum |
| 16 | ONF-RC | S9(4) COMP | int16 | Return code (Appendix E) |
| 18 | ONF-OUT-COUNT | S9(4) COMP | int16 | 0 to 32 |
| 20 | ONF-FPRINT | X(4) | uint8[4] | CRC-32, big-endian bytes (IR-COM-05) |
| 24 | ONF-STEPS | S9(9) COMP | int32 | Timesteps simulated |
| 28 | ONF-OUT (occurs 32) | 12 bytes each | struct | See below |
| +0 | ONF-OUT-ID | S9(9) COMP | int32 | Readout neuron identifier |
| +4 | ONF-OUT-LAT-US | S9(9) COMP | int32 | First-spike latency in µs; −1 if none |
| +8 | ONF-OUT-SPIKES | S9(4) COMP | int16 | 0 to 9,999 |
| +10 | FILLER | X(2) | char[2] | Zero |

### 4.4 JCL step contracts

| ID | Requirement | Verification |
|---|---|---|
| IR-JCL-01 | DD names and dataset attributes shall be as tabled below. | I |
| IR-JCL-02 | Request mode of ONFLYDRV shall read control cards with fixed columns: 1–4 stimulus code, 6–9 rate in Hz, 11–14 duration in ms, 16–24 seed. An asterisk in column 1 marks a comment. | T — TE-13 |
| IR-JCL-03 | Request records shall carry the full 412-byte layout with the response portion zeroed; ONFLYENG shall overwrite only the response portion. | T |
| IR-JCL-04 | Step return codes: 0 all requests succeeded; 4 at least one warning; 8 at least one request error; 12 network integrity failure; 16 environment or self-test failure. STEP2 shall run only if STEP1 ended below 8; STEP3 shall run only if STEP2 ended below 12. | T — TE-11 |

| DD name | Step | Direction | Attributes | Contents |
|---|---|---|---|---|
| ONFCTL | STEP1 | Input | FB, LRECL=80 | Control cards |
| ONFREQ | STEP1 → STEP2 | Output → input | FB, LRECL=412 | Request records |
| ONFNET | STEP2 | Input | FB, LRECL=80 | Network file |
| ONFRSP | STEP2 → STEP3 | Output → input | FB, LRECL=412 | Response records |
| ONFNAM | STEP3 | Input | FB, LRECL=80 | Names file |
| SYSPRINT | All | Output | FBA, LRECL=133 | Messages and run manifest |
| ONFRPT | STEP3 | Output | FBA, LRECL=133 | Report |

### 4.5 Messages

| ID | Requirement | Verification |
|---|---|---|
| IR-MSG-01 | Every message shall have the form ONFnnns, where nnn is a number and s is the severity (I information, W warning, E error, S severe). The full catalog is Appendix E. | I |
| IR-MSG-02 | The ONF prefix shall be checked against IBM's registered component message prefixes before format version 1.0 (TBD-10). | I |

### 4.6 Transport into MVS

| ID | Requirement | Verification |
|---|---|---|
| IR-TRN-01 | The transport for ONFNET shall be binary-transparent: no code-page translation, no line-end insertion, no trailing-blank truncation. | T — S2 |
| IR-TRN-02 | Spike S2 shall evaluate IND$FILE binary transfer, an AWS tape image, and the card reader in raw mode, using a test file containing every byte value 0x00–0xFF plus a real network file, over at least ten transfers per method. | D — S2 |
| IR-TRN-03 | ONFLYENG shall offer a verify-only mode (PARM='VERIFY') that runs FR-LOD-02 checks and reports the result without simulating. | T — TE-09 |
| IR-TRN-04 | The winning transport shall be selected by, in order: integrity (10 of 10 transfers pass CRC), scriptability from the x86 host, and elapsed time. | I — Gate G2 record |

## 5. Numerical requirements

| ID | Requirement | Verification |
|---|---|---|
| NR-01 | All simulation state and constants shall be IEEE 754 binary64 values, operated on only through the ONFLY float API (onf_fp), in round-to-nearest-ties-to-even mode. | I |
| NR-02 | The soft backend shall be Berkeley SoftFloat Release 3e, built with its "not FAST_INT64" configuration, which minimizes 64-bit integer use. The NaN specialization is TBD-16; NaNs are never expected (FR-SIM-08). | T — Gate G1 |
| NR-03 | If Gate G1 fails on GCCMVS, the soft backend shall fall back to SoftFloat Release 2c, which implements binary64 using only 32-bit integers (D-06). | Gate G1 record |
| NR-04 | The C dialect shall be C89 plus `long long` as provided by each compiler. The project shall supply `stdint.h` and `stdbool.h` shims for SoftFloat. 64-bit integer types shall appear only in SoftFloat and the float layer; engine logic shall use 32-bit integers. | I — build scripts, lint |
| NR-05 | The engine and the soft float layer shall contain no `float` or `double` types and no floating-point literals. A build-time lint shall enforce this; a stray `double` compiled by GCCMVS would silently be HFP. | T — lint in every build |
| NR-06 | No target platform shall convert between decimal text and binary floating point. All constants arrive as binary64 bit patterns (FR-PRP-06); all reported quantities are integers. | I |
| NR-07 | The sequence of floating-point operations in Appendix C is normative. Implementations shall not reassociate, fuse or reorder operations. | T — golden suite |
| NR-08 | After each synaptic update, a synaptic value whose magnitude is below G_EPS shall be set to exactly +0.0. This removes subnormal arithmetic, and any host difference in subnormal handling, from the kernel. | T — TU-09 |
| NR-09 | A native backend is admissible on a host only if all of the following hold: IEEE binary64 hardware or emulation with round-to-nearest-even; fused multiply-add contraction disabled (`-ffp-contract=off` for gcc and clang; `FLOAT(IEEE,NOMAF)` for IBM XL C); no fast-math options; no x87 extended precision (SSE2 on x86-64); no flush-to-zero or denormals-are-zero modes; only addition, subtraction, multiplication, division, comparison and exact int32↔binary64 conversion are used (no `libm`). Admission additionally requires passing the TestFloat vectors for the used operations and byte-identical golden-suite fingerprints versus the soft backend on that host. | T — TX-03 |
| NR-10 | The rounding mode shall never be changed, and no logic shall depend on floating-point exception flags. | I |
| NR-11 | Integer arithmetic rules: `int` shall be verified as 32 bits at compile time; signed overflow shall be prevented by range checks, never relied upon; right shifts and divisions shall be applied only to non-negative values; the PRNG and CRC shall use unsigned 32-bit arithmetic. | I; T — TU-01 |
| NR-12 | Stimulus draws shall use integer arithmetic only: draw a 32-bit value r; if r ≥ 4,294,000,000, discard it and draw again; the stimulus neuron spikes if (r mod 1,000,000) < rate_hz × dt_us. This is exactly uniform and requires rate_hz × dt_us ≤ 1,000,000. | T — TU-05 |
| NR-13 | The PRNG shall be xorshift32 (Marsaglia, shifts 13, 17, 5), with a request seed of 0 mapped to a fixed non-zero constant (algorithm confirmation TBD-11). | T — TU-04 |
| NR-14 | On every compiler and platform, a 64-bit integer self-test suite (multiply, divide, shifts, carries, comparisons; vectors generated on x86) and the TestFloat vector suite for the used operations shall pass before any engine test runs. | T — TT-01, TT-02 |

## 6. Scientific fidelity and acceptance

### 6.1 Model

| ID | Requirement | Verification |
|---|---|---|
| SR-MOD-01 | Each neuron shall follow a leaky integrate-and-fire model with an exponentially decaying synaptic term, per Shiu et al. With u = v − V_rest: du/dt = (g − u) / τ_mbr and dg/dt = −g / τ_syn (the second form TBC-02). A spike from neuron j increases g of each target i by w_ji after the synaptic delay. When u ≥ U_th the neuron spikes, u is set to U_reset, and the neuron is refractory for t_rfr (during refractoriness u is held and g continues to evolve, TBC-01). | T — oracle comparison |
| SR-MOD-02 | Parameter values shall be as tabled below. Values marked TBC shall be confirmed against the paper's methods and published code before calibration. | I |
| SR-MOD-03 | The integration method and the within-step event ordering shall match Shiu et al.'s published implementation (TBC-01). Both exact integration and forward Euler reduce to the same linear update with different coefficients P11, P12, P22 (Appendix C), so the method changes constants, not code. | A |
| SR-MOD-04 | The stimulation protocol (which sugar neurons, which hemisphere, Poisson rates spanning 10–200 Hz, trial duration) shall match Shiu et al. (TBC-05). | I |
| SR-MOD-05 | Connection weight shall be synapse count × sign × W_syn, with sign +1 for excitatory and −1 for inhibitory presynaptic neurons. | T — TP-01 |

| Parameter | Symbol | Value | Status |
|---|---|---|---|
| Resting potential | V_rest | −52 mV | Verified (Shiu et al.) |
| Reset potential | V_reset | −52 mV | Verified |
| Synaptic delay | T_dly | 1.8 ms | Verified |
| Synaptic weight per synapse | W_syn | 0.275 mV (free parameter; recalibrated for MaleCNS, SR-CAL) | Verified for FlyWire |
| Threshold | V_th | −45 mV | TBC-02 |
| Membrane time constant | τ_mbr | 20 ms | TBC-02 |
| Refractory period | t_rfr | 2.2 ms | TBC-02 |
| Synaptic time constant | τ_syn | 5 ms | TBC-02 |
| Timestep | dt | 0.1 ms | TBC-02 |

### 6.2 Calibration

| ID | Requirement | Verification |
|---|---|---|
| SR-CAL-01 | W_syn shall be recalibrated for MaleCNS on the full-brain model on x86, not on the subcircuit. | I — manifest |
| SR-CAL-02 | The sugar rates used for calibration and for validation shall be disjoint and fixed in the manifest before the first calibration run. Proposed: calibration {20, 80, 160} Hz; validation {10, 40, 120, 200} Hz (TBD-07). | I |
| SR-CAL-03 | Calibration shall minimize the mean relative error between ONFLY's mean MN9 rate and the Shiu reference at the calibration rates, using a deterministic bracketed search over W_syn. The search log shall be kept. | I |
| SR-CAL-04 | The Shiu reference curve shall be obtained by re-running Shiu et al.'s published code where possible, otherwise from the published figures (TBC-06). The source shall be recorded. | I |
| SR-CAL-05 | If no W_syn satisfies ACC-4 on the validation rates, the result shall be reported as a finding (risk R-03). Tolerances shall not be widened after the fact. | I |

### 6.3 Subcircuit extraction

| ID | Requirement | Verification |
|---|---|---|
| SR-EXT-01 | The subcircuit shall contain the N most active neurons by total spike count in the full-brain run (calibrated W_syn, all calibration and validation rates, all seeds), plus every stimulus and readout neuron. Ties shall be broken by ascending neuron identifier. | T — TP-06 |
| SR-EXT-02 | The subcircuit shall contain every MaleCNS connection among the selected neurons, with unchanged weights. | T |
| SR-EXT-03 | N shall be the smallest value in the sequence 250, 500, 1000, 2000, 4000 that satisfies ACC-3, NFR-MEM-01 and NFR-PERF-01. If none does, the conflict shall be escalated to the owner. | A — Phase 0 record |

### 6.4 Acceptance criteria

Unless stated otherwise, each criterion is evaluated over the validation rates with 30 seeds per rate (seed count TBD-06).

| ID | Criterion |
|---|---|
| ACC-1 | **Feeding, qualitative.** At every validation rate where the Shiu reference MN9 rate is above zero, the MVS subcircuit produces at least one MN9 spike in at least 90% of seeds, and a mean MN9 rate above zero. |
| ACC-2 | **Silence, exact.** A request with rate 0 produces zero spikes in every neuron, on every platform and backend. Because the model has no other noise source, this is a deterministic check. |
| ACC-3 | **Truncation fidelity.** At every validation rate, the subcircuit's mean MN9 rate is within ±10% of the full-brain MaleCNS run with the same seeds, or within an absolute floor (proposed ±1 Hz, TBD-08), whichever is larger. |
| ACC-4 | **Agreement with Shiu.** Shape: the MN9 rate does not decrease between successive validation rates by more than one standard error, and the onset rate (lowest rate with mean above 1 Hz) is within one sampled rate of the reference. Magnitude: each validation point is within ±25% of the reference, or within an absolute floor (proposed ±2 Hz, TBD-08), whichever is larger. |
| ACC-5 | **Determinism.** Every golden-suite request yields the same fingerprint on every combination listed in Section 8.3. |
| ACC-6 | **Performance.** NFR-PERF-01 is met on the TK5 reference host. |
| ACC-7 | **Demonstration.** The BUZZ job runs end-to-end on TK5 with return code 0 and a readable report. |

**The MVP is complete when ACC-1 through ACC-7 all pass**, with results recorded against the manifest of the network version used.

## 7. Non-functional requirements

| ID | Requirement | Verification |
|---|---|---|
| NFR-PERF-01 | One request at the standard duration (TBD-06) shall complete in at most 5 minutes of wall-clock time on the TK5 reference host. Spike S3 confirms or revises N and the standard duration. | T — S3, TX-04 |
| NFR-PERF-02 | Every performance measurement shall record the host CPU, the Hercules version and configuration, and the Hercules-reported MIPS rate. | I |
| NFR-MEM-01 | The decoded network and simulation state shall fit within the configured region limit on TK5 (TBD-14). The prep pipeline shall estimate the requirement from N and E before emitting a network. | T — TE-08 |
| NFR-PRT-01 | One engine source shall build on every platform; only the platform configuration header may differ. | I |
| NFR-REL-01 | No abnormal outcome shall be silent: each produces an ONF message and a defined return code. | T — error-path tests |
| NFR-MNT-01 | Record layouts shall be generated from the master definition (IR-COM-01). | I |
| NFR-MNT-02 | The engine shall contain no writable static data, so that it is reentrant for the future CICS path. | I; build with RENT where supported |
| NFR-OBS-01 | At the start of every run, ONFLYENG shall print a manifest to SYSPRINT: engine version, float backend (SOFT or NATIVE), compiler identification, network format version, network CRCs, dt, N and E. | D |
| NFR-LIC-01 | Third-party components and their licenses shall be tracked in the repository: SoftFloat and TestFloat (license text to be recorded, TBC), PDPCLIB (public domain), GCCMVS (GPL compiler; compiled programs are not encumbered), and the MaleCNS data terms (TBC-12). | I |
| NFR-BRD-01 | "CICS" and other IBM marks shall be used only descriptively (C-08). | I |

> **Performance note (estimate, not a measurement).** For 2,000 neurons, 1,000 ms simulated at 0.1 ms steps, about four soft-float operations per neuron-step and roughly 200 emulated instructions per operation, one request costs on the order of 10^10 instructions. At tens of MIPS under Hercules that is several minutes — close to the 5-minute budget. This is why Spike S3 runs before N and the standard duration are frozen.

## 8. Verification

### 8.1 Strategy

Verification runs bottom-up. A level may start only when the level below it passes on the platform concerned.

| Level | What it proves | Tests |
|---|---|---|
| L0 Toolchain | The compiler produces correct 64-bit integer and binary64 arithmetic | TT-01, TT-02 |
| L1 Units | CRC, PRNG, stimulus draws, decoder, layouts, float API each match their oracle | TU-01 … TU-09 |
| L2 Engine | The kernel matches the Python oracle bit-for-bit on the golden suite | Golden suite, TX-02 |
| L3 Cross-platform | Every platform and backend produces identical fingerprints | TX-01, TX-02, TX-03 |
| L4 Science | The model reproduces the feeding response within tolerance | TS-01 … TS-04 |
| L5 End-to-end | The BUZZ job runs on TK5 within budget | TX-04, ACC-7 |

### 8.2 Oracles

| ID | Oracle | Answers |
|---|---|---|
| O-1 | Python kernel using plain Python floats, explicit left-to-right loops, no `sum()` (since Python 3.12 it uses compensated summation) and no NumPy reductions | "Is the code right?" — bit-exact |
| O-2 | Full-brain MaleCNS run on x86 with the ONFLY engine | "Did truncation change the answer?" (ACC-3) |
| O-3 | Shiu et al. reference curve (SR-CAL-04) | "Is this still the fly?" (ACC-4) |
| O-4 | Python `zlib.crc32` | CRC correctness |
| O-5 | Berkeley TestFloat-generated vectors | Float library correctness on each compiler |

### 8.3 Determinism matrix

ACC-5 is satisfied when each golden request produces the same fingerprint in every row:

| Row | Platform | Backend | Compiler |
|---|---|---|---|
| 1 | x86-64 | Oracle (Python) | — |
| 2 | x86-64 | Native | gcc or clang |
| 3 | x86-64 | Soft | gcc or clang |
| 4 | Linux s390x (QEMU) | Soft | gcc |
| 5 | Linux s390x (QEMU) | Native | gcc |
| 6 | TK5 MVS 3.8j | Soft | GCCMVS |
| 7 | TK5 MVS 3.8j | Soft | JCC (engine-only if JCC cannot build SoftFloat 3e, VL-03) |
| 8 | z/OS (Phase 3) | Soft and native | IBM compiler, TBC |

### 8.4 Golden request suite

| ID | Stimulus | Rate (Hz) | Duration | Seed | Purpose |
|---|---|---|---|---|---|
| G-01 | SUGR | 0 | Standard | 1 | Silence (ACC-2) |
| G-02 | SUGR | 10 | Standard | 1 | Validation rate |
| G-03 | SUGR | 40 | Standard | 1 | Validation rate |
| G-04 | SUGR | 120 | Standard | 1 | Validation rate |
| G-05 | SUGR | 200 | Standard | 1 | Validation rate |
| G-06 | SUGR | 200 | Standard | 999999999 | Maximum seed |
| G-07 | SUGR | 9999 | Short | 7 | Maximum rate; exercises the draw procedure's upper bound |
| G-08 | SUGR | 120 | 1 ms | 7 | Minimum duration |
| G-09 | SUGR | 120 | Header maximum | 7 | Maximum duration |
| G-10 | SUGR | 120 | Standard | 0 | Seed-zero mapping (NR-13) |
| G-11 | WATR | 120 | Standard | 1 | Reserved stimulus, ONF201W |
| G-12 | XXXX | 120 | Standard | 1 | Unknown stimulus, ONF203E (corrected from ONF202E by D-41) |
| G-13 | SUGR | −1 | Standard | 1 | Out-of-range rate, ONF202E |

### 8.5 Test catalog

| Test | Description | Requirements |
|---|---|---|
| TT-01 | 64-bit integer self-test (vectors from x86) | NR-04, NR-14, A-05 |
| TT-02 | TestFloat vectors for the used operations | NR-02, NR-09, NR-14 |
| TU-01 | Compile-time integer width assertions | NR-11 |
| TU-02 | Float API operations on random operands versus the oracle | NR-01 |
| TU-03 | CRC-32 known-answer vectors versus zlib | IR-NET-07 |
| TU-04 | PRNG sequence versus the oracle, including seed 0 | NR-13, FR-SIM-04 |
| TU-05 | Stimulus draws versus the oracle, including the rejection path | NR-12, FR-SIM-03 |
| TU-06 | Decoder round-trip of every field type | IR-NET-01, FR-LOD-05 |
| TU-07 | Generated layout: size and offset assertions in C; sentinel values round-tripped through ONFLYDRV and ONFLYENG | IR-COM-01, IR-COM-03 |
| TU-08 | NaN and infinity detection from exponent bits | FR-SIM-08 |
| TU-09 | Subnormal clamp | NR-08 |
| TP-01 | Sign and weight assignment | FR-PRP-03, SR-MOD-05 |
| TP-02 | Artifact digests match the manifest | FR-PRP-07 |
| TP-03 | Pipeline reproducibility (two runs, byte-identical outputs) | FR-PRP-09 |
| TP-04 | CSR target ordering | IR-NET-06 |
| TP-05 | Name sanitization | IR-NAM-02 |
| TP-06 | Extraction determinism and tie-breaking | SR-EXT-01 |
| TE-01 … TE-06 | Corrupt magic, sentinel, version, header CRC, length, payload CRC | FR-LOD-02 |
| TE-07 | Zero-padded FB dataset handling | FR-LOD-03, IR-NET-08 |
| TE-08 | Network exceeding the memory limit | FR-LOD-04, NFR-MEM-01 |
| TE-09 | Verify-only mode | IR-TRN-03 |
| TE-10 | Duration out of range | FR-SIM-06 |
| TE-11 | Return codes and step conditioning | FR-BAT-02, IR-JCL-04 |
| TE-12 | Reserved stimulus codes | FR-BAT-05 |
| TE-13 | Control-card parsing, comments and malformed cards | IR-JCL-02 |
| TX-01 | Linux s390x and MVS response records are identical | FR-LNX-01 |
| TX-02 | Fingerprints identical across the determinism matrix | ACC-5, IR-COM-05 |
| TX-03 | Native backend admission on each host | NR-09 |
| TX-04 | Performance measurement on the TK5 reference host | NFR-PERF-01, ACC-6 |
| TX-05 | *(Stretch)* Direct CALL path equals batch path | FR-CAL-01 |
| TS-01 … TS-04 | Scientific acceptance evaluations | ACC-1 … ACC-4 |

## 9. Gates and phases

> **Status: signed off by the owner on 2026-09-10 (D-24); TBD-15 closed.** The gates and phases below are committed as written. The spikes in Phase A are independent of one another and can run in parallel.

### 9.1 Gates

| Gate | Question it answers | Exit criterion | If it fails |
|---|---|---|---|
| G0 Environment | Is every lab platform ready? | TK5 Update 5 running; GCCMVS and JCC inventory recorded; Linux s390x with gcc under QEMU; x86 Python environment | Install missing components |
| G1 SoftFloat port (Spike S1) | Can GCCMVS build and run SoftFloat 3e correctly? | TT-01 and TT-02 pass under GCCMVS | Switch to SoftFloat 2c (D-06); record JCC scope (VL-03) |
| G2 Transport (Spike S2) | Which transport moves binary into TK5 safely? | IR-TRN-02 and IR-TRN-04 satisfied | If none passes, escalate to owner |
| G3 Performance (Spike S3) | How large can N and the duration be within 5 minutes? | Measured time per neuron-step on TK5; N maximum and standard duration fixed | Reduce N or duration; escalate if ACC-3 then fails |
| G4 COBOL (Spike S4) | Does COPY work in MVT COBOL, and does the driver skeleton pass the proxy? | Generated copybook compiles via COPY or inlining; skeleton passes GnuCOBOL IBM-dialect check | Inline layouts via the generator |

### 9.2 Phases

| Phase | Content | Depends on |
|---|---|---|
| A — Foundations | G0; spikes S1–S4 | — |
| B — Engine and oracle (x86) | Layout generator, float layer, kernel, oracle, golden-suite harness, native backend admission on x86 | A (S1 for the soft backend) |
| C — Science (x86) | Data retrieval; confirmation of TBC-01…TBC-06 against Shiu et al.; full-brain runs; calibration; extraction; ACC-3 and ACC-4; network format v1.0 | B |
| D — Big-endian | Linux s390x build; TX-01, TX-02 on a synthetic network, then on v1.0 | B |
| E — MVS MVP | GCCMVS build; ONFLYDRV; JCL; BUZZ demonstration; ACC-1 … ACC-7 | C, D, G2, G4 |
| F — z/OS (later) | Port to IBM Z Xplore; determinism row 8 | E; permissions granted |
| G — CICS (later) | BUZZ menu and stimulus transactions (Section 3.7) | F; CICS environment (TBD-13) |

The permissions request is made with the Phase E demonstration in hand. The direct-CALL stretch goal may be attempted any time after Phase E.

## 10. Risks

| ID | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R-01 | GCCMVS or JCC generates incorrect 64-bit integer code | Medium | High | Gate G1 first; TT-01 isolates integer bugs from float bugs; SoftFloat 2c fallback |
| R-02 | Hercules is too slow for a useful N and duration | Medium | Medium | Spike S3 before freezing N; N sequence in SR-EXT-03 |
| R-03 | MaleCNS cannot be calibrated to match Shiu within ±25% because of dataset differences | Medium | Medium | Report as a scientific finding; ACC-1 to ACC-3 remain meaningful; owner decides |
| R-04 | MVT COBOL limitations (COPY, IF nesting) | High | Low | Spike S4; generator inlining; flat control flow |
| R-05 | Shiu et al.'s implementation details differ from the paper text | Medium | Medium | Code review in Phase C; deviations recorded as decisions |
| R-06 | The 24-bit region is too small | Low | Medium | NFR-MEM-01 estimate before emitting a network |
| R-07 | Silent corruption in transport | Medium | High | CRC gate on every run; verify-only mode |
| R-08 | Wrong cell-type mapping for sugar neurons or MN9 | Medium | High | Owner-reviewed mapping table (FR-PRP-02) |
| R-09 | No CICS environment becomes available | Medium | Low for MVP | MVP is independent of CICS (D-08, D-23) |
| R-10 | Scope creep | Medium | Medium | Out-of-scope list (Section 1.2) |

## Appendix A. Decision log

### A.1 Owner decisions

Each decision below was made by the owner during the requirements question rounds.

| ID | Decision | Alternatives considered | Rationale |
|---|---|---|---|
| D-01 | Build a working MVP in the owner's lab (TK5 + QEMU s390x) before moving to IBM Z Xplore; request project permissions with the MVP in hand | Start directly on Xplore | The lab is stricter than z/OS, so passing there de-risks the port; a working demo strengthens the permissions request |
| D-02 | TK5 is the reference MVS environment | TK4- | Actively maintained, current SDL Hercules, 3390 DASD, large preinstalled toolset |
| D-03 | GCCMVS is the primary C compiler; JCC provides a cross-check | GCCMVS only; JCC only | Real GCC front end with a strictly C89 runtime; a second compiler exposes undefined behavior |
| D-04 | Software IEEE floating point | Fixed-point integer; native float per platform (HFP on MVS) | Bit-exact results everywhere; the oracle is plain floating-point code; no quantization analysis. Accepted costs: a dependency and slower arithmetic |
| D-05 | Engine state in IEEE binary64 | binary32 | Plain Python floats serve as the oracle; matches the float64 reference model |
| D-06 | SoftFloat Release 3e; fall back to 2c if GCCMVS cannot build 3e | SoftFloat 2c from the start | Current release; the 64-bit integer risk is contained by Gate G1 |
| D-07 | A native IEEE backend is allowed on hosts where bit-identity is proven | Soft backend everywhere | Speed on capable hosts (notably full-brain runs on x86) without giving up determinism |
| D-08 | Multi-step JCL for the MVP; direct COBOL CALL as a stretch goal | Direct CALL required; JCL only | Avoids interlanguage risk without Language Environment; keeps the CALL path open |
| D-09 | Binary, explicitly big-endian network interchange | 80-column card-image text | Natural for binary64 values; the transport risk is handled by CRC gates |
| D-10 | Spike all three transports and pick the winner | Choose one up front | Evidence over assumption |
| D-11 | Shiu-style LIF with integration matched to Shiu's published code | Exact integration regardless; simpler LIF without delay | The only published, behavior-validated reference for the milestone |
| D-12 | Calibrate W_syn on part of the sugar curve; validate on the rest | Keep 0.275 mV; calibrate and validate on the same curve | Avoids circular validation |
| D-13 | Subcircuit = top-N most active neurons from a full-brain run | All neurons within k hops; only sugar→MN9 path neurons | Selects what actually participates; truncation error is measured, not assumed |
| D-14 | Acceptance is both qualitative and quantitative | Either alone | Qualitative proves behavior; quantitative proves fidelity |
| D-15 | Tolerances: ±25% plus curve shape versus Shiu; ±10% subcircuit versus full brain | Tighter (±10% / ±5%); shape only versus Shiu | Honest looseness across datasets; tightness within one dataset and engine |
| D-16 | Performance budget: at most 5 minutes per request on Hercules, confirmed by a spike | 1 minute; no budget | Realistic for batch; bounds N and duration |
| D-17 | One COBOL driver written in the MVT COBOL / Enterprise COBOL intersection | Separate drivers per compiler | One codebase |
| D-19 | C engine with a COBOL driver | All COBOL; C only | Right language for each job, and authentic mixed-language mainframe practice |
| D-20 | First milestone: the sugar→feeding subcircuit | Central brain; full MaleCNS | Small, published, behaviorally validated |
| D-21 | Project name ONFLY; "CICS" only in the tagline; BUZZ menu transaction plus per-stimulus transactions (SUGR, WATR, BITR) | FLYTRAN; "CICS" in the name | Keeps the pun, respects IBM trademarks, and names match an MVP that does not yet use CICS |
| D-22 | SRS as Markdown in the repository with a .docx export; engineering audience plus a one-page IBM summary | Either format alone; single audience | The repository copy is also the build specification for agentic tools |
| D-23 | The "fly as a transaction" (CICS) direction; since Xplore allows no CICS resource definition, the design is batch-first with CICS as a later adapter | Start with other Z layers (Linux on Z benchmark, on-chip AI accelerator, vector assembly) | Strongest demonstration of what Z is for; CICS-shaped design costs nothing in the MVP |
| D-24 | Phase ordering of Section 9 (gates G0–G4, phases A→B→C→D→E→F→G) is approved exactly as drafted; TBD-15 is closed | Approve with Phase B allowed to fully precede Phase A; defer and discuss the ordering first | Owner signed off the drafted ordering unchanged on 2026-09-10 |
| D-25 | Session scope 2026-09-10: Phase B on x86 **including** the SoftFloat backend and the onf_fp float layer | Phase B core only (layout generator, oracle, unit tests); Gate G0 environment inventory only | Owner selected the larger scope knowing, as stated in the question, that building SoftFloat on x86 with gcc proves nothing about GCCMVS and does **not** discharge Spike S1 or Gate G1, which remain open |
| D-26 | The repository is initialised under git and pushed to the existing public GitHub repository https://github.com/mertefesensoy/ONFLY immediately | Commit locally and hold the push until a licence is chosen; choose the licence first, then push | No MaleCNS data is involved in Phase B, so TBC-12 (repository licence and MaleCNS data terms) may be settled before Phase C |
| D-27 | ONFLY-SRS.md and ONFLY-SRS.docx move from the repository root into docs/ | Keep both at the repository root | Matches the paths referenced by the engineering goal and sits alongside docs/implementations/ |
| D-18 | Record layouts are generated from a single master definition (IR-COM-01); generated files are never edited by hand | Hand-maintained COBOL copybook, C header and Python struct kept in step by review | Confirmed by the owner on 2026-09-10, promoted from proposal A.2 to an owner decision. Stops the three layouts from drifting and handles MVT COBOL's COPY limitations |
| D-28 | Berkeley SoftFloat 3e and TestFloat 3e are downloaded from the upstream site www.jhauser.us over HTTPS and vendored under third_party/, with the SHA-256 of each archive and the licence text recorded (NFR-LIC-01) | SoftFloat only, deferring TestFloat; git submodule of the ucb-bar GitHub mirror; owner supplies the archives | The released archives are auditable by digest, unlike the mirror, which publishes no release tags. Taking TestFloat in the same step unblocks TT-02 and oracle O-5 |
| D-29 | The x86 build is driven by a Makefile run with mingw32-make | A Python build script; plain shell scripts | mingw32-make is already installed, so nothing new is required, and the same Makefile shape carries to the Linux s390x target. MVS builds are driven by JCL regardless |
| D-30 | The native backend is pursued on this host with x87 disabled: -msse2 -mfpmath=sse -ffp-contract=off. NR-09 admission still requires TestFloat vectors and byte-identical golden fingerprints against the soft backend | Soft backend only until a true x86-64 toolchain exists; pursue admission and also amend the Section 2.3 platform matrix | The host gcc is 32-bit mingw32, where x87 extended precision is the default and is prohibited by NR-09; forcing SSE2 yields true binary64. The owner did **not** authorise amending the platform matrix, so Section 2.3 is unchanged and this host is not a listed platform |
| D-31 | TBD-16 closed: the soft backend is built with the **ARM-VFPv2-defaultNaN** specialization | 8086 (the upstream default for the Win32 non-FAST_INT64 build); 8086-SSE; ARM-VFPv2 | Default-NaN mode never propagates operand payloads, so no result can depend on operand order or on which NaN arrived first. NaNs are never expected (FR-SIM-08 aborts on them), so this governs only already-defective states, but it is the most deterministic option and determinism is the project's premise |
| D-32 | TBD-11 closed: the PRNG is xorshift32 with shifts 13, 17, 5, **updating the state and returning the new state**; a request seed of 0 maps to **2463534242 (0x92D68CA2)** | Seed-zero constant 0x9E3779B9 or 1; returning the old state before updating | 2463534242 is Marsaglia's own published seed in reference 9, so the constant is traceable to the source the SRS already cites rather than invented here. Update-then-return is the canonical form, so an independent reimplementation agrees by default. Golden request G-10 exercises the seed-zero path |
| D-33 | Only the binary64 subset of SoftFloat 3e is compiled; the float128, extF80, f16 and f32 sources are not built | Patch the vendored source; switch back to the 8086 specialization; report upstream and pause | The chosen ARM-VFPv2-defaultNaN specialization ships a genuine compile defect: a stray semicolon inside the `if` condition of `source/ARM-VFPv2-defaultNaN/s_propagateNaNF128M.c`. It is float128 code and the binary64 core contains no reference to it. Not compiling it keeps third_party byte-identical to the digests recorded in D-28, cuts code size for the 24-bit region (C-01, NFR-MEM-01) and narrows what Gate G1 must prove under GCCMVS (VL-03) |
| D-34 | The soft backend is built flags-free: no writable static data, so NFR-MNT-02 holds structurally rather than by convention | Accept SoftFloat's three mutable globals and record a verification limit; defer the question to Phase G | SoftFloat 3e defines `softfloat_roundingMode`, `softfloat_detectTininess` and `softfloat_exceptionFlags` as plain mutable globals — `THREAD_LOCAL` is `#define`d to nothing — and the binary64 rounding path writes the flags on every inexact result. The owner required these removed rather than tolerated, so that the engine is genuinely reentrant for the CICS path (Section 3.7, CONCURRENCY(REQUIRED)) |
| D-35 | The single file that touches SoftFloat's global state, `s_roundPackToF64.c`, is carried as an ONFLY-owned derived copy under the BSD licence with attribution; `third_party/` is never edited | Patch third_party in place; macro shim keeping one global byte | Keeps the vendored tree byte-identical to the SHA-256 digests recorded in D-28. The derived copy hard-wires round-to-nearest-ties-to-even, which makes NR-10 structurally unviolable rather than merely required, and removes the inexact-flag write. Being ONFLY code, it must pass the TestFloat vectors (TT-02) like any other part of the float layer |
| D-36 | Confirmed (promoted from proposal P-07): the Gate G1 record shall state exactly which SoftFloat components were built and tested under GCCMVS, because ONFLY compiles only the binary64 subset | Leave as an unconfirmed proposal in A.2 | Gate G1's scope is now narrower than "SoftFloat 3e builds under GCCMVS". Without this, a future reader would over-read what G1 proved. Extends VL-03 to the soft backend itself |
| D-37 | The Phase B golden-suite harness uses a **provisional** standard duration of 1000 ms and maximum duration of 5000 ms. TBD-06 stays **open**; Gate G3 still fixes the real values | Provisional 200 ms / 1000 ms; close TBD-06 now at these values; run no golden suite in Phase B | 1000 ms is the figure the Section 7 performance note already reasons about, so S3's measurements will be directly comparable. Recorded as provisional for x86 Phase B only: no result, document or report may quote these as final, because Gate G3 measures Hercules and that measurement has not been made |
| D-38 | Next increment inside Phase B is the network file format, decoder and integrity checks (IR-NET-01..08, FR-LOD-01..05, TE-01..07) | Response fingerprint first; stop building and consolidate documentation | It is the largest remaining piece of Phase B, is fully specified in the SRS, and needs no open item resolved to begin |
| D-39 | Numeric stimulus IDs for the response fingerprint (IR-COM-05): **SUGR = 1, WATR = 2, BITR = 3, unrecognised code = 0** | SUGR=0/WATR=1/BITR=2; derive the number from the code's own bytes | IR-COM-05 requires a *numeric* stimulus ID but no section of the SRS assigned one; FR-BAT-05 names the codes only as text. Deriving it from the code bytes was rejected outright because the same code has different bytes on ASCII and EBCDIC hosts, which is the very reason IR-COM-05 excludes text. Reserving 0 for an unrecognised code means a zeroed or truncated request record cannot masquerade as a valid SUGR request. Once golden fingerprints are recorded this mapping is effectively frozen |
| D-40 | Implement the response fingerprint (IR-COM-05) and the golden-suite harness (SRS 8.4) now, completing Phase B's content list apart from full NR-09 admission | Fingerprint only; record D-39 and stop | The golden suite is the last outstanding item of Phase B in Section 9.2 |
| D-41 | Appendix E governs: golden request G-12 (unknown stimulus code) expects **ONF203E**, not ONF202E. The owner authorised correcting the Section 8.4 table text | Treat ONF202E as covering both and mark ONF203E unused; leave both texts alone and log an open item | Section 8.4 and Appendix E contradicted each other. ONF203E is defined as UNKNOWN STIMULUS CODE and exists for exactly this case, while ONF202E is REQUEST FIELD OUT OF RANGE and is already exercised by G-13's out-of-range rate. This is the only SRS requirement text changed in this session, and only under this authorisation |
| D-42 | Golden request G-07's duration, written in Section 8.4 only as "Short", is a **provisional** 100 ms for the x86 Phase B harness | Provisional 10 ms; make it the same as the standard duration | 100 ms is one tenth of D-37's provisional standard. It runs 1000 steps at dt = 0.1 ms, so the 9999 Hz draw path and its NR-12 upper bound are genuinely exercised, while the maximum-rate case does not dominate suite runtime. Provisional alongside D-37; Gate G3 still settles it, and TBD-06 stays open |
| D-43 | Confirmed (promoted from proposal P-08): **ONF-RC carries Appendix E's RC column** (0, 4, 8, 12, 16), not the message number. The message identity is reported separately to SYSPRINT | ONF-RC carries the message number (201, 202, 203); carry both, adding a field to the COMMAREA | Section 4.3 says only "Return code (Appendix E)" and Appendix E has both a message column and an RC column. The RC column is the one headed "return code" and matches IR-JCL-04's step codes. Carrying both was rejected because the 412-byte layout has no spare aligned field. The thirteen golden fingerprints already recorded stay valid under this reading |
| D-44 | Build TestFloat 3e and run TT-02 for the operations ONFLY actually uses, on both float backends | TT-01 (the 64-bit integer self-test) first; both TT-01 and TT-02 | TT-02 is the remaining NR-09 admission condition and completes Phase B's Section 9.2 content on x86. TT-01's value is realised only when a GCCMVS build runs it, which cannot happen on this host |
| D-45 | Add a build-time lint reporting every external identifier longer than 8 characters, or colliding case-insensitively, across ONFLY code and the compiled SoftFloat subset (C-04) | Leave the question entirely to Gate G1; research how GCCMVS handles long externals first | The lint cannot fix GCCMVS, but it converts an unknown into a precise, sized list before Gate G1 starts, and it guards ONFLY's own names against regressing past 8 characters |
| D-46 | TT-02 runs TestFloat vectors whose reference is built against the **8086** SoftFloat specialization, with cases whose operands or expected result are NaN **excluded**; the exclusion is recorded as verification limit VL-11 | Use TestFloat operands but the Python oracle as reference; run the full vectors including NaN cases; defer TT-02 to Gate G1 | TestFloat needs a complete softfloat.a, which ARM-VFPv2-defaultNaN (D-31) cannot build because of the upstream f128 defect recorded in D-33. The 8086 build succeeds, and the two specializations differ **only** in NaN-handling files — every differing file is a NaN or specialize file, with the arithmetic cores shared verbatim. ONFLY aborts on any NaN (FR-SIM-08), so the excluded cases are ones the engine never reaches |

### A.2 Design decisions proposed in this draft

These were introduced by the architect while writing the specification. They are subject to owner review and are listed separately so that proposals are never mistaken for owner decisions.

| ID | Proposal | Reason |
|---|---|---|
| P-01 | Responses carry numeric readout identifiers; the fingerprint excludes text fields (IR-COM-05, IR-COM-06) | Text differs between ASCII and EBCDIC hosts; numbers do not |
| P-02 | Integer-only stimulus draws with rejection sampling (NR-12) | Exactly uniform and needs no floating point |
| P-03 | Subnormal clamp on the synaptic term (NR-08) | Removes the one place where host floating-point modes could differ |
| P-04 | One linear update kernel for both integration methods (Appendix C) | The method changes constants, not code |
| P-05 | Absolute tolerance floors alongside relative tolerances (ACC-3, ACC-4) | Relative tolerances become meaningless near zero firing rates |
| P-06 | Verify-only mode (IR-TRN-03) | Makes transport spikes and operational checks cheap |

## Appendix B. Open items

| ID | Item | Affects | Resolved in |
|---|---|---|---|
| TBC-01 | Shiu et al.'s integration method, within-step event ordering, stimulus delivery and refractory semantics | SR-MOD-01, SR-MOD-03, Appendix C | Phase C |
| TBC-02 | Unconfirmed parameter values (V_th, τ_mbr, t_rfr, τ_syn, dt) and the exact form of the synaptic equation | SR-MOD-02 | Phase C |
| TBC-03 | MaleCNS cell types for the sugar-sensing neurons and MN9 | FR-PRP-02 | Phase C |
| TBC-04 | Neurotransmitter-to-sign mapping as used by Shiu et al. | FR-PRP-03 | Phase C |
| TBC-05 | Stimulation protocol details (neuron set, hemisphere, trial duration) | SR-MOD-04 | Phase C |
| TBC-06 | Source of the Shiu reference curve (re-run of published code, or figures) | SR-CAL-04 | Phase C |
| TBD-06 | Standard duration, maximum duration, seeds per rate (proposed 30) | FR-SIM-06, NFR-PERF-01, Section 6.4 | Gate G3 — **still open**. D-37 sets a provisional 1000 ms / 5000 ms for x86 Phase B only; these are not the final values |
| TBD-07 | Calibration and validation rate split (proposed {20, 80, 160} and {10, 40, 120, 200} Hz) | SR-CAL-02 | Before first calibration |
| TBD-08 | Absolute tolerance floors (proposed ±1 Hz and ±2 Hz) | ACC-3, ACC-4 | Before first calibration |
| TBD-09 | Final magic constant | IR-NET-03 | Format v1.0 |
| TBD-10 | ONF message prefix collision check | IR-MSG-02 | Format v1.0 |
| ~~TBD-11~~ | PRNG algorithm confirmation | NR-13 | **CLOSED 2026-09-10 by D-32** — xorshift32 13/17/5, update-then-return, seed 0 → 2463534242 |
| TBC-12 | MaleCNS data terms; repository license | NFR-LIC-01 | Before publishing |
| TBD-13 | Source of a CICS environment | Phase G | Later |
| TBD-14 | Region limit on TK5 | C-01, NFR-MEM-01 | Gate G0 |
| ~~TBD-15~~ | Owner sign-off on phase ordering | Section 9 | **CLOSED 2026-09-10 by D-24** — ordering approved as written |
| ~~TBD-16~~ | SoftFloat NaN specialization | NR-02 | **CLOSED 2026-09-10 by D-31** — ARM-VFPv2-defaultNaN |

## Appendix C. Normative simulation kernel (draft)

> **Status: draft.** The step ordering below is normative once TBC-01 is resolved against Shiu et al.'s code. Until then it is the working hypothesis used by the oracle and the engine alike. ⊕ and ⊗ are correctly rounded binary64 operations evaluated strictly left to right.

**Coefficients (computed on x86, shipped as bit patterns).** With u = v − V_rest, du/dt = (g − u)/τ_mbr and dg/dt = −g/τ_syn, one step of length dt is u′ = P11·u + P12·g and g′ = P22·g, where:

| Method | P11 | P12 | P22 |
|---|---|---|---|
| Exact propagator (τ_syn ≠ τ_mbr) | e^(−dt/τ_mbr) | τ_syn / (τ_syn − τ_mbr) · (e^(−dt/τ_syn) − e^(−dt/τ_mbr)) | e^(−dt/τ_syn) |
| Forward Euler | 1 − dt/τ_mbr | dt/τ_mbr | 1 − dt/τ_syn |

**State.** For each neuron i: u[i], g[i] (binary64), rfr[i] (int32 refractory steps remaining), spikes[i] and first[i] (int32). A ring buffer ring[0..D−1][0..N−1] (binary64) holds delayed synaptic input. All binary64 state starts at +0.0; rfr starts at 0; first starts at −1. The PRNG is seeded from the request (NR-13).

**For each step t = 0, 1, …, T−1:**

```
1. ARRIVALS
   slot = t mod D
   for i = 0 .. N-1 (ascending):
       g[i] = g[i] (+) ring[slot][i]
       ring[slot][i] = +0.0

2. STIMULUS DRAWS
   for each stimulus neuron s (ascending index):
       draw per NR-12 (exactly one accepted draw per neuron per step,
       whether or not s is refractory)
       force[s] = (draw produced a spike)

3. INTEGRATE, DETECT, EMIT
   for i = 0 .. N-1 (ascending):
       if rfr[i] > 0:
           rfr[i] = rfr[i] - 1
           g[i]   = P22 (x) g[i]                # u held at U_reset
           was_refractory = true
       else:
           a      = P11 (x) u[i]
           b      = P12 (x) g[i]
           u[i]   = a (+) b
           g[i]   = P22 (x) g[i]
           was_refractory = false
       if |g[i]| < G_EPS: g[i] = +0.0         # NR-08
       if not was_refractory and (u[i] >= U_th or force[i]):
           u[i]   = U_reset
           rfr[i] = REFRACTORY_STEPS
           spikes[i] = spikes[i] + 1
           if first[i] < 0: first[i] = (t + 1) * dt_us
           for each target k of i (ascending, CSR order):
               ring[(t + D) mod D][k] = ring[(t + D) mod D][k] (+) w(i,k)
       force[i] = false
```

Because slot (t + D) mod D equals the slot consumed at the start of step t, spikes emitted at step t arrive at the start of step t + D. D must be at least 1.

**After the last step:** fill the response from the readout neurons (spikes, first), set the step count, and compute the fingerprint per IR-COM-05.

## Appendix D. Verification limits register

| ID | Limit |
|---|---|
| VL-01 | QEMU emulates s390x floating point in software. A native backend admitted under QEMU is not yet proven on real s390x hardware; that proof arrives only in Phase F. |
| VL-02 | Enterprise COBOL compatibility of ONFLYDRV is checked only by a GnuCOBOL IBM-dialect proxy until Phase F. A proxy pass is not proof. |
| VL-03 | If JCC cannot compile SoftFloat 3e, the JCC cross-check covers only the components JCC can build; the Gate G1 record states exactly which. |
| VL-04 | Hercules performance says nothing about real IBM Z performance. All timing figures are lab figures. |
| VL-05 | Fingerprint agreement proves cross-platform consistency, not scientific correctness. Correctness rests on ACC-1 to ACC-4. |
| VL-06 | ACC-4 compares a male connectome with a model calibrated on a female connectome. Agreement shows consistency, not identity. |
| VL-07 | Parameters marked TBC are unverified until Phase C. |
| VL-08 | CRC-32 detects accidental corruption, not deliberate tampering. SHA-256 digests are kept in the x86 manifest only. |
| VL-09 | The performance figure in Section 7 is an arithmetic estimate, not a measurement. |
| VL-10 | No CICS behavior is verified in the MVP. Section 3.7 records design intent only. |
| VL-11 | TT-02's reference is built against the 8086 SoftFloat specialization, not the ARM-VFPv2-defaultNaN one the engine uses (D-46), because the latter cannot build a complete library. The two share their arithmetic cores verbatim and differ only in NaN handling, so cases whose operands or expected result are NaN are excluded from TT-02. TT-02 therefore proves nothing about NaN behaviour; FR-SIM-08 aborts on NaN instead. |

## Appendix E. Message catalog

| Message | RC | Text | Meaning and action |
|---|---|---|---|
| ONF001I | 0 | NETWORK LOADED N=n E=n CRC=x | Integrity checks passed |
| ONF002I | 0 | RUN MANIFEST … | Start-of-run manifest (NFR-OBS-01) |
| ONF003I | 0 | VERIFY-ONLY: NETWORK OK | Verify-only mode succeeded |
| ONF101E | 12 | MAGIC CONSTANT MISMATCH | Not an ONFLY network, or corrupted |
| ONF102E | 12 | BYTE-ORDER SENTINEL MISMATCH | Transport swapped or translated bytes; re-transfer in binary |
| ONF103E | 12 | UNSUPPORTED FORMAT VERSION v.m | Engine and network versions differ |
| ONF104E | 12 | HEADER CRC MISMATCH | Header corrupted in transport |
| ONF105E | 12 | NETWORK EXCEEDS MEMORY LIMIT | Reduce N, or raise the region |
| ONF106E | 12 | PAYLOAD LENGTH INCONSISTENT | Truncated transfer |
| ONF107E | 12 | PAYLOAD CRC MISMATCH | Payload corrupted in transport |
| ONF201W | 4 | STIMULUS CODE RESERVED, NOT SIMULATED | WATR and BITR are reserved in the MVP |
| ONF202E | 8 | REQUEST FIELD OUT OF RANGE: field | Correct the request |
| ONF203E | 8 | UNKNOWN STIMULUS CODE | Correct the request |
| ONF301I | 0 | REQUEST n COMPLETE FP=x | Request succeeded; fingerprint shown |
| ONF302I | — | STEP SUMMARY: n OK, n WARN, n ERROR | End-of-step summary |
| ONF401E | 8 | CONTROL CARD INVALID AT CARD n | ONFLYDRV request mode |
| ONF901S | 16 | 64-BIT INTEGER SELF-TEST FAILED | Startup known-answer check; compiler or runtime defect |
| ONF902S | 16 | FLOAT SELF-TEST FAILED | Startup known-answer check; float layer defect |
| ONF903S | 16 | NON-FINITE STATE VALUE, REQUEST ABORTED | Engine defect; report with the request |
| ONF904S | 16 | INTEGER WIDTH CHECK FAILED | Platform configuration defect |

## Appendix F. Glossary

| Term | Meaning |
|---|---|
| AWS tape image | A file format Hercules uses to emulate a tape volume |
| binary64 | The IEEE 754 64-bit floating-point format ("double precision") |
| CICS | IBM's transaction server for z/OS (IBM trademark) |
| COMMAREA | The communication area passed between CICS programs; here also the batch record layout |
| CSR | Compressed sparse row: a row-pointer array plus a target-index array |
| GRN | Gustatory receptor neuron (taste-sensing neuron) |
| HFP | Hexadecimal floating point, the only floating point in S/370 hardware |
| ICVR | CICS runaway-task interval |
| IND$FILE | File transfer program used over a 3270 terminal session |
| LE | IBM Language Environment, the common runtime absent from MVS 3.8j |
| LIF | Leaky integrate-and-fire neuron model |
| MaleCNS v1.0 | The complete male fruit fly central nervous system connectome (2026) |
| MN9 | A proboscis motor neuron; the feeding readout used by Shiu et al. |
| MVT COBOL | The OS/360 ANS COBOL compiler (IKFCBL00) available on MVS 3.8j |
| PDPCLIB | Public-domain C89 runtime library used with GCCMVS |
| QR TCB | CICS's single quasi-reentrant task control block |
| RENT | Reentrant program attribute |
| SoftFloat / TestFloat | John Hauser's IEEE floating-point software library and its test suite |
| TK5 | MVS 3.8j Tur(n)key 5 distribution by Rob Prins |
| W_syn | Voltage contribution per synapse; the model's free parameter |

## Appendix G. References

1. Januszewski, M. and Jain, V. "A connectomics milestone: Mapping the complete male fruit fly brain." Google Research blog, September 3, 2026.
2. "Sexual dimorphism in the complete connectome of the *Drosophila* male central nervous system." *Cell* (2026). doi:10.1016/j.cell.2026.08.015
3. MaleCNS dataset: https://male-cns.janelia.org/ and https://www.janelia.org/project-team/flyem/male-cns-connectome
4. Shiu, P. K. et al. "A *Drosophila* computational brain model reveals sensorimotor processing." *Nature* 634, 210–219 (2024).
5. Hauser, J. R. Berkeley SoftFloat and TestFloat. http://www.jhauser.us/arithmetic/SoftFloat.html
6. GCCMVS: https://gccmvs.sourceforge.net/ — PDPCLIB: https://pdos.sourceforge.net
7. JCC (maintained by mvslovers): https://github.com/mvslovers/jcc
8. MVS 3.8j Tur(n)key 5: https://www.prince-webdesign.nl/tk5
9. Marsaglia, G. "Xorshift RNGs." *Journal of Statistical Software* 8(14), 2003.
10. ISO/IEC/IEEE 29148:2018, Systems and software engineering — Life cycle processes — Requirements engineering.
11. IEEE 754-2019, IEEE Standard for Floating-Point Arithmetic.

