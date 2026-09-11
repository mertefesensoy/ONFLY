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
| A-05 | GCCMVS synthesizes correct 64-bit integer arithmetic for `long long` on S/370. | **DISPROVED 2026-09-11 at Gate G1 — see VL-15.** 64-bit addition ends in an internal compiler error; multiply and divide produce assembler that Assembler XF rejects. Subtract, shifts, bitwise and, and assignment work. Measured on TK5 under Hercules 4.9.1 |
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
| SR-MOD-01 | Each neuron shall follow a leaky integrate-and-fire model with an exponentially decaying synaptic term, per Shiu et al. With u = v − V_rest: du/dt = (g − u) / τ_mbr and dg/dt = −g / τ_syn (the second form TBC-02). A spike from neuron j increases g of each target i by w_ji after the synaptic delay. When u > U_th the neuron spikes (strict, D-69), u is set to U_reset, g is reset to +0.0 (D-67), and the neuron is refractory for t_rfr; during refractoriness u is held and **g is frozen** (D-67). Stimulus neurons have no refractory period (D-68). | T — oracle comparison |
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
| D-47 | **Phase B is exited for x86.** Its Section 9.2 content — layout generator, float layer, kernel, oracle, golden-suite harness and native-backend admission — is complete and verified on this host. Spike S1 (the soft backend under GCCMVS) remains an open **Phase A / Gate G1** obligation, not a Phase B one | Phase B stays open until S1 runs; also amend Section 9 to give phases explicit exit criteria | Section 9 states exit criteria for gates only and gives phases content lists, so "exit" needed an owner ruling. The owner did **not** authorise amending Section 9, so its text is unchanged and this ambiguity persists for later phases |
| D-48 | Next work is **Phase C data retrieval**: the MaleCNS preparation pipeline, its run manifest, and the sugar/MN9 cell-type mapping | TT-01 (the 64-bit integer self-test); verify-only mode and the run manifest; stop and report | Phase C is the next phase in the D-24 ordering. FR-PRP-02 requires the cell-type mapping to be reviewed and approved by the owner before calibration (TBC-03), and TBC-01…TBC-06 will come to the owner as they are reached |
| D-49 | MaleCNS v1.0 is retrieved from the **public Google Cloud Storage flat-connectome files**, starting with `body-annotations` (14,483,314 bytes) and `body-neurotransmitters` (43,282,834 bytes); `connectome-weights` (1,051,241,946 bytes) follows once the cell-type mapping is approved | Download all three at once; the owner supplies the files | These files need no neuPrint account and no API token, so no credential is involved at any point. The two small files are enough to build the sugar/MN9 mapping table that FR-PRP-02 requires the owner to approve **before** calibration, so the gigabyte of connectivity is not fetched before the mapping it depends on exists. pyarrow 21.0.0 and pandas are already installed, so reading Feather adds no dependency |
| D-50 | The **MaleCNS data-terms half of TBC-12 is closed: the dataset is CC BY 4.0**, so ONFLY must carry attribution wherever the data or artifacts derived from it appear. TBC-12 remains open for the **repository's own licence** | Close TBC-12 entirely and choose a repository licence now; leave TBC-12 fully open | The licence is stated on male-cns.janelia.org. The repository licence is a separate choice and is the owner's to make |
| D-51 | `connectome-weights-male-cns-v1.0-minconf-0.5.feather` (1,051,241,946 bytes) is downloaded now, and the sugar-GRN set for TBC-03 is **derived from connectivity**: rank the labellar GRN types by synaptic drive onto the three Yao & Scott 2022 "Sugar SEL" neurons (GNG056, GNG540, GNG550) and present the owner a ranked table to approve under FR-PRP-02 | Owner names the LB types directly; stimulate the Sugar SEL neurons instead of the GRNs (an SRS deviation from SR-MOD-04); defer TBC-03 | MaleCNS labels no GRN as sugar-sensing, and all sixteen labellar-bristle types (LB1a…LB4b) are cholinergic, so neurotransmitter does not discriminate sugar from bitter. Connectivity is the only evidence in the dataset that can. This resolves the ordering problem D-49 created, where the mapping was waiting on connectivity that was itself waiting on the mapping |
| D-52 | **TBC-03 closed.** The sugar stimulus set is **PhG9 (4 neurons) + dorsal_tpGRN (10 neurons)**, 14 neurons in total. The readout set is **MN9 (2 neurons)** | Every gustatory type with non-zero drive (17 types, 122 neurons); labellar sugar GRNs named by the owner to match Shiu et al.; re-anchor on a different sugar marker first | These two types carry 1,110 of the 1,233 gustatory synapses onto the Yao & Scott 2022 Sugar SEL marker neurons, a roughly twentyfold gap to the next type. The set follows the dataset's own connectivity evidence rather than an assumption carried over from FlyWire. **It is pharyngeal and taste-peg, not labellar**, so it diverges from the neurons Shiu et al. stimulate; recorded against SR-MOD-04 as verification limit VL-12 |
| D-53 | This cycle's scope is **Phase C sign assignment (FR-PRP-03)** | TT-01; verify-only mode and the run manifest; network format v1.0 from real data | Next step in the D-24 ordering and the gateway to calibration, extraction and ACC-3/ACC-4. Fully runnable on this host with the data already retrieved |
| D-54 | **TBC-04 closed (part 1).** Neurotransmitter-to-sign mapping for SR-MOD-05: **acetylcholine +1; GABA, glutamate and histamine −1; dopamine, octopamine and serotonin excluded** | Glutamate as +1; monoamines included as +1; defer until confirmed against Shiu et al.'s code | Glutamate is treated as **inhibitory**, which is the *Drosophila*-specific case through GluCl channels rather than the vertebrate default; it affects 29,443 neurons, about 18% of those with a definite prediction, so the choice materially sets the network's excitation/inhibition balance. The 545 monoamine neurons are excluded because they are modulatory rather than fast synaptic, and a LIF model cannot represent modulation |
| D-55 | **TBC-04 closed (part 2).** Neurons with no definite neurotransmitter — 22,645 predicted "unclear" plus 24,561 absent from the table, 47,206 in total (22.3%) — have their **outgoing edges excluded**, and the excluded counts are recorded in the run manifest | Treat unclear as excitatory; keep them at weight zero; defer until the full-brain run shows the impact | A neuron whose sign is unknown contributes no signed weight, so nothing enters the model on a guess. The cost is real and must be measured rather than hidden: this removes roughly a fifth of possible sources, which will show up in the full-brain run and must be reported against ACC-3 |
| D-56 | The network is scoped to **annotated-neuron → annotated-neuron edges only**. This keeps 26,028,386 pairs and 125,365,933 synapses, **40.2%** of the connectome's synapses; the discarded fraction is recorded in the manifest and carried into ACC-3 as VL-13 | Keep any edge whose presynaptic body has a sign (92.7% of synapses, but anonymous postsynaptic nodes); widen the definition of neuron by re-retrieving annotations without the minconf-0.5 cut; measure first and decide later | A LIF node needs a cell type and a transmitter to be simulated at all, and a body absent from the annotation file has neither, so it cannot be a node. Measurement showed the loss comes from this restriction rather than from the sign filter: the sign filter alone costs 7.3% of synapses, while the neuron restriction costs 59.8%. Among annotated neurons D-55's exclusion costs only a further 1.2 points, from 40.2% to 39.0% |
| D-57 | **FR-PRP-03 is met.** Its stated verification method TP-01 passes (15 tests, exit 0) and TBC-04 is closed by D-54 and D-55. Phase C as a whole remains open | Hold FR-PRP-03 open until the signs are checked against Shiu et al.'s published code; hold it open until a real network file has been emitted | FR-PRP-03's verification method in the SRS is TP-01, and TP-01 passes. The owner noted that TBC-04 was closed by decision rather than by comparison with published code, which is recorded in the sign-assignment implementation note as an explicit limit |
| D-58 | Next work is **emitting a real network file from the signed connectivity (FR-PRP-07)**, so the engine runs on MaleCNS data rather than a synthetic network | Subcircuit extraction (SR-EXT); calibration setup (TBD-07, TBD-08); stop and report | SR-EXT-01 defines the MVP subcircuit from a full-brain run that needs W_syn calibrated first, so extraction cannot come before calibration; emitting a real network is the step that unblocks both |
| D-59 | FR-PRP-07 emits **two** networks: the **full scoped network** (184,099 neurons, 24,775,486 edges, ~300 MB) as the calibration reference and oracle O-2, and a **2-hop subcircuit** from the D-52 stimulus set (13,521 neurons, 1,704,385 edges, ~21 MB) as a fast working set | Full network only; 2-hop subcircuit only | SR-CAL-01 requires W_syn to be recalibrated on the full-brain model on x86 rather than on a subcircuit, so the full network is needed regardless; the 2-hop set makes iteration cheap and provably contains the whole sugar-to-MN9 pathway, since MN9 is first reached at hop 2 (hop 1 yields 604 neurons and does not reach it). Neither is the SR-EXT-01 subcircuit, which is defined by activity in a full-brain run and cannot be built until W_syn is calibrated; both are therefore provisional with respect to SR-EXT |
| D-60 | **G_EPS = 2^-1022**, the smallest normal binary64 (bit pattern 0x0010000000000000, approximately 2.2250738585072014e-308) | 1e-300, matching the synthetic kernel test fixture; 1e-30, pruning small synaptic traces aggressively | Derived from NR-08's stated purpose rather than chosen: a magnitude below the smallest normal *is* subnormal by definition, so this clamps exactly the subnormals and leaves every normal value untouched. The alternatives would silence normal values the model may legitimately carry, which would be a modelling change rather than numerical hygiene |
| D-61 | This cycle's scope is **FR-PRP-04, the full-brain run on x86** | Calibration setup (TBD-07, TBD-08, TBC-06); TT-01; verify-only mode and the run manifest | SR-CAL-01 requires W_syn to be calibrated on the full-brain model and SR-EXT-01 defines the MVP subcircuit by activity in that run, so both are blocked until it exists. Sizing shows it fits on this host: 630 MB peak, or 330 MB once the file buffer is released after loading |
| D-62 | **TBC-12 fully closed.** The repository is licensed **MIT** | Apache 2.0; three-clause BSD matching the vendored components; leave TBC-12 open | Short, widely understood, and compatible with the three-clause BSD of the vendored SoftFloat and TestFloat. The project's value is the demonstration rather than the code, so a permissive licence imposing nothing on reusers suits it. The MaleCNS data half was already closed by D-50 as CC BY 4.0, which requires attribution and is recorded separately in third_party and the data manifest |
| D-63 | FR-PRP-04's full-brain protocol for this session is **7 rates x 1 seed x 1000 ms**: the union of TBD-07's proposed calibration {20, 80, 160} and validation {10, 40, 120, 200} Hz sets, at D-37's provisional standard duration. About 25 minutes of compute | 7 rates x 3 seeds x 300 ms; one rate x 30 seeds x 1000 ms; settle TBD-06 and TBD-07 before running anything | Measured throughput on this host is 8.5 million neuron-steps per second, so the protocol SR-EXT-01 actually asks for -- all rates with all seeds -- is about 12.6 hours and cannot run in a session. One seed rather than the thirty TBD-06 proposes makes the resulting activity ranking **provisional**: it is not the SR-EXT-01 selection, and must not be used as one without re-running with the seed count TBD-06 finally fixes |
| D-64 | This cycle's scope is **confirming TBC-01, TBC-02 and TBC-05 against Shiu et al.'s published model code** at github.com/philshiu/Drosophila_brain_model (MIT), comparing `model.py` line by line against SRS Appendix C and the SR-MOD-02 parameter table, and bringing the differences to the owner to rule on | TBC-06 only (obtain the reference curve); TT-01; verify-only mode and the run manifest | Four open items are all defined as "confirm against Shiu et al." and this is that source. It unblocks calibration and ACC-4, and it is the only way to learn whether Appendix C's **draft** step ordering is actually correct — fitting a W_syn against the wrong kernel would produce a calibrated wrong answer |
| D-65 | **TBD-09 and TBD-10 stay open.** The magic constant is not frozen and the ONF prefix collision check is not performed yet | Close TBD-09 now at the proposed 0x4F4E4631; investigate TBD-10 now | The network format will still change as calibration and extraction settle the header's parameter values, so freezing v1.0 in one respect before the rest of it is ready would give the version a meaning it has not earned. IR-NET-03's proposed value keeps working in the meantime |
| D-66 | **TBC-02 closed.** Every SR-MOD-02 parameter is confirmed against Shiu et al.'s published `model.py`: V_th −45 mV, τ_mbr 20 ms, τ_syn 5 ms, t_rfr 2.2 ms, T_dly 1.8 ms, V_rest = V_reset = −52 mV, W_syn 0.275 mV, dt 0.1 ms, and the synaptic form dg/dt = −g/τ_syn. `method='linear'` confirms the **exact propagator** | Close but record dt as separately derived; keep open pending the paper's methods section | Confirmed against the implementation that produced the published results, not merely the paper text. The SR-MOD-02 table needed no change because it was already correct; only the TBC marking is removed. dt is Brian2's default rather than an explicit setting, which is recorded here rather than hidden |
| D-67 | **Appendix C amended (authorised):** the synaptic term **g is frozen while a neuron is refractory** and **reset to exactly +0.0 on every spike**, matching Shiu's `(unless refractory)` on dg/dt and `eq_rst: g = 0*mV` | Keep Appendix C as drafted and record a verification limit; adopt the spike reset only | SR-MOD-03 requires the integration method and within-step event ordering to match Shiu's published implementation, and ACC-4 compares against his reference. A kernel difference here would sit on top of the male/female and stimulus-set differences already in VL-06 and VL-12 |
| D-68 | **Appendix C amended (authorised):** stimulus neurons have **no refractory period**, matching Shiu's `rfc = 0` for Poisson targets. The forced-spike delivery of Appendix C is kept rather than adopting Shiu's 68.75 mV injection into v | Match Shiu fully by injecting w_syn × 250 into v; keep refractory gating on stimulus neurons | 68.75 mV against a 7 mV threshold gap means every Poisson event causes a spike, so the forced spike is behaviourally equivalent and avoids adding a voltage-injection path. The refractory gating is the part that genuinely differs: at 200 Hz with a 2.2 ms refractory period ONFLY would silently drop stimulus spikes Shiu's model delivers, biasing exactly the high-rate end ACC-4 tests |
| D-69 | **Appendix C amended (authorised):** the firing condition is **strict**, u > U_th, matching Shiu's `eq_th: v > v_th` | Keep u >= U_th and record a verification limit | One comparison operator removes a known kernel difference. The case bites only when the membrane potential lands exactly on threshold, which in binary64 is rare but reachable, and bit-exact reproducibility is ONFLY's premise |
| D-70 | The golden suite runs against the **real 2-hop MaleCNS network** instead of the synthetic 32-neuron fixture | Strengthen the synthetic network until its readouts spike; keep both suites; leave it and record a verification limit | The synthetic network never drove its readouts — all 80 output entries were `spk=0, lat=-1` — so every fingerprint depended only on request fields and eight constant entries. Four kernel semantics changed under D-67, D-68 and D-69 and **not one fingerprint moved**: ACC-5 as exercised could not detect a kernel change at all. The 2-hop network drives MN9 demonstrably, so fingerprints become sensitive to the kernel and ACC-5 means what it says |
| D-71 | **TBC-01 closed and Appendix C is now NORMATIVE, not draft** (authorised SRS text change). Every element TBC-01 names is settled: `method='linear'` confirms the exact propagator, and D-67, D-68 and D-69 fixed the ordering, stimulus and refractory semantics against Shiu's code | Close TBC-01 but leave Appendix C marked draft; keep TBC-01 open pending the paper's methods section | All four elements were read from the implementation that produced the published results and reconciled with the kernel. VL-07 no longer applies to the kernel semantics |
| D-72 | **SR-MOD-01 corrected (authorised SRS text change):** during refractoriness u is held and **g is frozen**, not "continues to evolve". The TBC-01 marker is removed | Correct it and also record the old wording; leave SR-MOD-01 as written | D-67 established the opposite of what SR-MOD-01 said. Leaving it would make Section 6.1 contradict the amended Appendix C about the same behaviour, and an implementer reading only Section 6.1 would build the wrong kernel — the same class of internal contradiction D-41 had to fix for G-12 |
| D-73 | **TBC-05 closed.** The stimulation protocol is: the D-52 neuron set (PhG9 + dorsal_tpGRN, 14 neurons), **both hemispheres**, trial duration 1000 ms confirmed by Shiu's `t_run`, delivery per D-68 | Close but restrict to one hemisphere; keep open pending the paper's methods section | The D-52 set already includes both left and right members and nothing in `model.py` restricts stimulation to one side, so closing on that basis records the bilateral choice explicitly rather than leaving it an accident of the selection |
| D-74 | The golden suite runs against a **path-restricted real network**: only neurons lying on a stimulus-to-MN9 path within the two-hop horizon, plus the stimulus and readout sets | Keep the 2-hop network but move `golden` out of the default test target; run the oracle on a subset of requests; accept the runtime | D-70 made fingerprints kernel-sensitive, which was the point, but the oracle must then simulate about 1.9 billion neuron-steps across the suite and a run exceeded 35 minutes without finishing. Most of the 13,521 two-hop neurons never influence MN9, so restricting to actual paths keeps real data and a spiking MN9 while making the suite affordable. A suite nobody can afford to run stops being run, which is how the blind-fixture problem survived unnoticed |
| D-75 | **D-74 amended.** The golden fixture is **stimulus neurons + their hop-1 successors + every presynaptic partner of MN9 + MN9**: 913 neurons, 72,852 edges | Keep D-74 literal (28 neurons); return to the 2-hop network; use candidate A with shortened durations | D-74 read literally gives 28 neurons and **MN9 never fires** — the fixture would have been as blind as the synthetic one it replaced, which is the exact failure D-70 was raised to fix. MN9 has 321 presynaptic partners and needs their summed input to reach threshold; the hop-1 neurons are what carry the stimulus to them. With both, MN9 fires 138 to 194 spikes and its latency falls from 44.6 ms to 26.2 ms as rate rises, so fingerprints are genuinely kernel-sensitive. 1.25 s per request in C. Durations stay at D-37 and D-42 values so the fingerprints remain comparable |
| D-76 | This cycle's scope is the **Gate G1 gap and the remaining x86 engine items**: TT-01, the 64-bit integer self-test (NR-04, NR-14, A-05), then verify-only mode (IR-TRN-03, TE-09) and the NFR-OBS-01 run manifest | Phase C calibration (SR-CAL-01..05); SR-EXT extraction machinery (SR-EXT-01..03, TP-06); Phase D big-endian under QEMU s390x | Gate G1's exit criterion is "TT-01 and TT-02 pass under GCCMVS" and **TT-01 did not exist at all** — it is the earliest unmet criterion in the D-24 ordering. Calibration is blocked behind TBC-06 (D-77), extraction is blocked behind calibration, and Phase D needs a QEMU toolchain this host does not have. Deferred three times before, by D-48, D-53 and D-61 |
| D-77 | **TBC-06 stays open.** The Shiu reference MN9 curve is not sourced this session and no calibration run is started | Digitise the published Shiu et al. (2024) figure and record the read-off uncertainty as a new verification limit; re-run Shiu's published code, which would also approve installing brian2 and downloading their female hemibrain dataset | `reference/shiu/model.py` is vendored but their connectome data is not, brian2 is not installed, and the paper's figure is not reachable offline from this session. A reference curve invented from any of those gaps would be a guess wearing the word "reference", which is the same class of defect D-70 was raised to fix. SR-CAL-05 forbids widening tolerances after the fact, so the reference must be real before it is used |
| D-78 | **ONFLYENG is created now, minimally.** A `main` that parses PARM, loads the network with the FR-LOD-02 checks, prints the ONF002I manifest, and in `PARM='VERIFY'` prints ONF003I and stops without simulating. The 412-byte request/response loop, ONF301I and the IR-JCL-04 ladder are **not** built yet | A full ONFLYENG main including the request loop and return-code ladder; library entry points with no program at all; TT-01 only, deferring ONFLYENG entirely to Phase E | IR-TRN-03 and NFR-OBS-01 both say "ONFLYENG shall", so neither can be satisfied by a library function — TE-09 has to exercise the mode the requirement names, not a function standing in for it. Building only that much keeps the driver, the JCL and the request loop in Phase E, which Section 9.2 makes dependent on Phase C and Phase D; both are unfinished, so pulling them forward would be building on a floor that is not poured |
| D-79 | **TT-01 is one vector table with two callers.** The known-answer vectors, generated on x86, live in one engine source; `tests/tstint.c` runs them as the TT-01 binary for Gate G1, and the same function is callable at engine startup to emit ONF901S with RC 16 | A standalone TT-01 binary only, leaving ONF901S an unimplemented catalog entry; a startup check only, with no dedicated L0 binary | NR-14 describes an L0 test suite and Appendix E describes a startup known-answer check, and the SRS never says whether they are the same vectors. One table answers both and makes drift between them impossible. A startup-only check would invert Section 8.1's rule that L0 passes before anything above it runs |
| D-80 | **The TT-02 reproducibility defect is fixed now.** `.gitignore`'s `build/` rule also matched `third_party/**/build/`, so upstream's vendored `build/Win32-MinGW/Makefile` files and TestFloat's `build/Win32-MinGW/platform.h` were never committed — 622 files tracked under `third_party/`, none of them under a `build/` directory. A narrow negation is added and those vendored files are committed | Copy them into the worktree untracked and record the defect as a follow-up; leave it broken this session and report TT-02 as NOT RUN | Those files are vendored upstream **source**, not build output, and without them `make testfloat` cannot run in a fresh clone: TT-02 was reproducible only in the single checkout where the zip was first extracted. TT-02 is half of Gate G1's exit criterion and D-76's whole subject is the other half, so a G1 test suite that no clone can rebuild is in scope rather than beside it |
| D-81 | **SRS text change authorised:** a new row is added to the Appendix E message catalog. A run without `PARM='VERIFY'` loads the network, prints the manifest, and then ends with **ONF905S, RC 16, "REQUEST PROCESSING NOT BUILT AT THIS ENGINE LEVEL"** | A non-VERIFY run loads, prints the manifest and ends RC 0; reuse the existing ONF904S rather than adding a catalog row | D-78 deliberately leaves the request loop to Phase E, so this engine level genuinely cannot process requests, and NFR-REL-01 forbids any abnormal outcome being silent — a job that simulates nothing and reports success is exactly that. ONF905S is the next free identifier in the existing severe block and RC 16 is IR-JCL-04's "environment or self-test failure", which is what a job submitted against the wrong engine level is. Reusing ONF904S was rejected because it means "integer width check failed" and would tell the operator something untrue |
| D-82 | **The two-step plan for this cycle is approved:** TT-01 first (generator, `onfitst`, the TT-01 binary, an independent Python re-computation, and a `tt01` target ordered before the L1 targets), then the minimal ONFLYENG of D-78, each step ending with its tests run and their output shown, then commit and push to origin | Change the plan; discuss the approach, ordering or requirement reading first | Section 8.1 requires L0 to pass before the levels above it, so TT-01 precedes the program that calls it. Pushing is directed by the owner's goal statement for this session, which overrides the skill's standing local-only rule |
| D-83 | **The C-04 lint skips compiler-generated clone symbols** — any name containing a `.`, such as GCC's `onfirun.part.0`, `*.isra.N` and `*.constprop.N` | Compile the lint's objects with `-fno-partial-inlining` so the clone never appears; restructure `onfirun` so the optimiser sees no partial-inlining opportunity | C-04 constrains **external identifiers** as the MVS linkage editor sees them. A `.part.0` clone is an optimiser-local symbol, is not a valid C identifier, and never reaches the linkage editor, so flagging it is a false positive rather than a caught defect — the lint already skips names *starting* with `.` on exactly that reasoning. Suppressing the clone with a build flag was rejected because the lint would then inspect a build that differs from the one that ships, and shaping the source around one compiler's heuristics at one optimisation level was rejected as brittle |
| D-84 | **TT-01 keeps its DIV and MOD groups and the divide-based cross-check, accepting that the engine now references `__udivdi3` and `__umoddi3` on MVS.** Gate G1 finds out whether GCCMVS and PDPCLIB supply them | Keep the full test in the TT-01 binary but run a reduced, division-free check at engine startup; drop DIV and MOD from TT-01 as an authorised NR-14 deviation | `softfloat/onfint.o` is the only object in the entire engine that references those helpers — SoftFloat's not-FAST_INT64 build genuinely avoids 64-bit division, and D-79's startup call is what pulls them in. NR-14 names divide among the operations the self-test must cover, so the TT-01 binary needs them regardless; splitting the two callers would undo the single-table property D-79 chose precisely to prevent drift. A missing libgcc helper is the kind of thing a gate exists to surface, and surfacing it at G1 costs far less than at Phase E. Recorded as VL-14 |
| D-85 | **SRS text change authorised:** Appendix E gains **ONF108E, RC 12, "NETWORK DATASET UNREADABLE"** for a network that cannot be read at all — absent, empty, or unopenable — before FR-LOD-02's content checks can run | Report it at RC 16 as an environment failure; leave it out of scope at this engine level and print a bare diagnostic | Every ONF1xx message covers a *content* failure, so nothing in the catalog fitted a dataset that never arrived, and NFR-REL-01 forbids a silent abnormal outcome while IR-MSG-01 forbids a diagnostic that is not an ONFnnns. RC 12 is IR-JCL-04's network integrity failure, which an absent network is; splitting load failures across two return codes would buy nothing |
| D-86 | **ONFLYENG locates the network from the second argument when one is given, and otherwise opens `DD:ONFNET`**, which is how PDPCLIB names a DD | The argument only, deferring all MVS dataset access to Phase E; `DD:ONFNET` only, matching IR-JCL-01 exactly | The fallback is already correct against IR-JCL-01's DD contract, so Phase E inherits a working path rather than a rewrite, while the argument form is what makes TE-09 verifiable on this host at all. `DD:ONFNET` only would have left verify-only mode unexercised in this session, which is the whole of what D-78 set out to deliver |
| D-87 | **This session's commits are pushed as a fast-forward onto `origin/main`** | Push the working branch and open a pull request for review first; push the branch with no pull request; do not push at all | Every earlier ONFLY commit sits on `main` in a linear history, `origin/main` was still at f6f5b31 and this work sits directly on top of it, so the push rewrites nothing and needs neither a force nor a merge. Asked rather than assumed because pushing is the one irreversible step in the plan and the skill's standing rule is local commits only |
| D-88 | **Gate G1 is to be closed properly: stand up the Hercules/TK5 lab, build under GCCMVS, and run TT-01 and TT-02 there.** This authorises installing that toolchain | Report PARTIAL now with G1 listed NOT RUN; take another x86 slice first and report PARTIAL after it | G1's exit criterion is "TT-01 and TT-02 pass **under GCCMVS**", and no amount of x86 work can satisfy it — this host has no Hercules, no TK5 and no MVS. Both other options left G1 at NOT RUN, differing only in how much x86 work sat beside it. Gate G0 (environment) and parts of Gate G2 (transport) are prerequisites and are therefore pulled into scope |
| D-89 | **The lab is installed outside the repository, at `C:\hercules-lab`.** Approved downloads: SDL Hercules 4.9.1 x64 (7.9 MB, github.com/SDL-Hercules-390/hyperion), TK5 base `mvs-tk5.zip` (475.2 MB) and `mvstk5-update5.zip` (334.2 MB), both from prince-webdesign.nl | Unpack it inside the repository tree behind a gitignore rule; fetch Hercules only and decide about TK5 afterwards; do not download at all | Gate G0 names TK5 Update 5 specifically, and D-02 makes TK5 the reference MVS environment. Keeping the lab outside the repository removes any path by which a multi-gigabyte DASD volume could be staged into git — the same class of mistake D-80 had to clean up — and lets the lab outlive worktree cleanup. Hercules ships as a zip rather than an installer, so nothing is written outside the folder it is unpacked into |
| D-90 | **Gate G1 is attempted in two stages: TT-01 under GCCMVS first and reported with its real output, then TT-02.** | Treat G1 as indivisible and report only when both halves have run; stop after Gate G0 with the environment recorded and no ONFLY code run on MVS | A-05 and risk R-01 are about *integer* arithmetic specifically, so a TT-01 result under GCCMVS is the single most valuable fact either half can produce, and it is reachable far sooner. TT-02 is Spike S1 in substance — it needs SoftFloat 3e to build under GCCMVS, which D-06 already plans a 2c fallback for — and its vectors currently arrive over a Unix pipe that MVS has no equivalent of, so it carries a redesign as well as a port |
| D-92 | **TT-01 runs under JCC first to prove the toolchain path, then GCCMVS is installed and Gate G1 is attempted properly.** JCC is installed on TK5 and supports `long long`; GCCMVS is not installed at all and must first be unpacked from `TK5.PAUL.GCCMVS.V323-85.ZIP` | Install GCCMVS first and hold strictly to D-03's ordering; skip JCC entirely for now | Running JCC first proves source transfer, compile, link, run and output retrieval end to end, so that a later GCCMVS failure is unambiguously the install rather than the plumbing. D-03 keeps GCCMVS primary and this changes nothing about that: Gate G1's exit criterion names GCCMVS and stays open until GCCMVS runs. JCC's `limits.h` defines LLONG_MAX, LLONG_MIN and ULLONG_MAX 0xffffffffffffffffLL, so the 64-bit type TT-01 needs is present |
| D-93 | **P-07 is closed. ONFLY-owned sources are held to 80 columns: `tools/genint.py` wraps its output, and a new lint fails any ONFLY source over 80 columns** | Wrap `generated/onfivec.h` only and add no lint; move sources in by a transport that preserves long lines instead | **Measured on the running TK5, not assumed**: an 85-character card submitted to the reader (`000C 3505 ... ascii trunc eof`) arrived as exactly 80 characters, columns 81-85 discarded, with no error, no warning and no message. Silent truncation of source is the precise failure class this project exists to rule out. The lint is the part that matters, because without it a long line reappears silently the next time one is written — the same way the blind golden fixture survived until D-70. Vendored `third_party/` is exempt: D-28 and D-35 commit it to byte-identity with upstream, so TT-02 will need the long-line transport separately |
| D-94 | **TT-01's MVS build uses separate PDS members and a real include path**, with an `ONFINCL` DD added to the compile step so `#include "onfint.h"` resolves to member ONFINT, the two translation units compiled separately and then linked. **A throwaway probe job verifies how JCC maps an include name onto an eight-character member before the layout is committed** | Amalgamate the five files into one source member so JCCCLG can compile it directly; go straight to separate members without the probe | An amalgamation would introduce a build-time transformation of the source, which a reviewer could fairly read as a second form of the engine source and so as a strain on NFR-PRT-01's "one engine source builds on every platform". Separate members keep it an ordinary build of the actual files, and the same shape carries over to GCCMVS and later to the engine proper. The probe removes the single genuine unknown — the include-name mapping — rather than leaving it to be discovered inside a larger failure |
| D-95 | **JCC has served its purpose under D-92 and work moves to GCCMVS.** GCCMVS is installed from `TK5.PAUL.GCCMVS.V323-85.ZIP` and TT-01 is run there. The two-translation-unit link under JCC is abandoned unfinished | Generate an MVS-only driver member so JCC compiles both units as one; keep probing JCC's linker; stop and report | D-92 gave JCC one job — prove the path — and it did: probe C compiled, linked and ran ONFLY-style C on MVS 3.8j and returned **2^32 as hi=00000001 lo=00000000** and **(2^32)^2 wrapping to 00000000 00000000**, which is exactly the construction `onfi2p32()` relies on. Gate G1's exit criterion names **GCCMVS**, so no amount of further JCC work can close it. JCC's `JCCC`, `JCCCL` and `JCCCLG` all take a single INFILE and its prelink chain left the same four runtime symbols unresolved whichever order the two objects were presented in; GCCMVS is a real GCC and links multiple objects conventionally |
| D-96 | **The 2026-09-11 session ends on the PARTIAL report.** Gate G1 is recorded FAILED with its evidence; the response to that failure — JCC as primary, a newer GCCMVS, or a TT-01 rewritten in 32-bit halves — is deferred to the next session. The Hercules/TK5 lab is **left running** at the owner's instruction | Close TBD-14's region limit first; write the NR-04 stdint/stdbool shims first; attempt Spike S1 now | The gate has a real, evidenced answer and a decision taken cold is worth more than one taken at the end of a long session. Everything is committed and pushed, the x86 suite is green, and VL-15 and VL-16 capture the findings, so the next session starts from a documented position rather than a reconstruction. Spike S1 was declined for now because it needs the NR-04 shims first and the addition defect makes a clean pass unlikely |
| D-97 | **The Gate G1 response begins with an optimisation-level probe.** The same minimal 64-bit addition that ICEd is compiled again under GCCMVS at `-O0`, `-O1` and `-O2` before any structural response is chosen | Rewrite TT-01 in 32-bit halves; make JCC the primary compiler (D-03 and the Gate G1 exit criterion would both need changing); fetch and install a newer GCCMVS | Every one of the Gate G1 probe jobs on 2026-09-11 compiled with `PARM='-S -ansi -pedantic-errors -Wno-long-long -o dd:out -'` — **no `-O` flag at all**, so GCC 3.2.3's default. "Unable to generate reloads" is a failure in GCC's *reload* pass, whose behaviour on old back ends differs materially by optimisation level, so the one variable never moved is the one the diagnosis most depends on. The probe costs a single job against a lab that is already running, while each of the other three responses commits either an SRS text change or a fresh toolchain install on evidence that has this hole in it |
| D-98 | **After the Gate G1 probe, the session takes the NR-04 `stdint.h` and `stdbool.h` shims.** An ordering choice only; it does not alter the D-24 phase ordering | Close TBD-14's TK5 region limit; attempt Spike S1 (SoftFloat 3e under GCCMVS) directly; stop after the Gate G1 work and report | NR-04 requires the project to supply these shims and the repository has none. PDPCLIB is C89 and SoftFloat 3e includes both headers, so the shims are the hard prerequisite for Spike S1 — the other half of Gate G1's exit criterion. TBD-14 unblocks nothing in the current chain, and Spike S1 cannot start without the shims |
| D-99 | **Hercules' codepage is switched from `default` to `819/037`** so that the card reader delivers `|` as the byte GCCMVS lexes. This authorises the configuration change to the running lab | Build a `cp_updt` user table correcting only the `|` entry and activate it with `codepage user`; switch the reader to raw mode and have `tools/mvsub.py` translate to EBCDIC itself (IR-TRN-02's third candidate); remove `|` from ONFLY's C | Measured on TK5 this session: the reader delivers ASCII `|` as EBCDIC **0x6A**, GCCMVS rejects 0x6A outright (`stray '\152'`, octal for 0x6A), and `|` is the **only** character of ``| ! ^ [ ] { } ~ # @ $ \ ` `` that it will not lex — ASCII `!` arrives at its normal 0x5A and is no stand-in. `|=` builds the comparison mask in `onficmu` and `onficms` and `||` guards every range check, so no ONFLY source reaches the compiler intact until this is fixed. CP037 is the classic MVS page and places `|` at 0x4F; the change is one runtime command, reversible with `codepage default`, and is **also the measurement** that settles whether 0x4F really is GCCMVS's `|`, which had not been measured. The user table was rejected as non-persistent — a lab that silently reacquires the fault after a restart — and the source change as hiding a transport fault inside the engine |
| D-100 | **`-O1` is the committed optimisation level for ONFLY's GCCMVS builds.** `tools/mvstt01.py` defaults to it and the level is recorded as a verification limit | Keep `-O1` experimental, passed per run, until Gate G1 passes end to end; measure further levels first (`-O1` plus individual `-f` options, or `-O2` with the failing passes disabled) | D-97's probe is unambiguous: of `-O0`, `-O1`, `-O2`, `-O3` and `-Os`, **`-O1` alone** compiles, assembles, links and runs a 64-bit addition correctly, and the two failures are **different** compiler defects — `-O0` dies in the reload pass ("unable to generate reloads", at 3590) while `-O2`, `-O3` and `-Os` die at 447. `-O1` is therefore not a preference but the only working setting, threading between two distinct bugs. That is also its cost, and it is recorded as VL-17 rather than left implicit: ONFLY's MVS builds are pinned to a level chosen to dodge compiler defects, not chosen for code quality |
| D-101 | **D-99 is amended: the codepage is `819/1047`, not `819/037`.** The lab runs `codepage 819/1047`, and the character probe is re-run to prove it before any further work | Build a `cp_updt` user table from `default` correcting only the `|` entry; revert to `default` and take IR-TRN-02's raw-reader candidate, with `tools/mvsub.py` owning the translation table; revert to `default` and stop at the finding, leaving the fix to be chosen cold next session | `819/037` was measured immediately after it was set and **traded one broken character for three**: `|` became acceptable, while `^`, `[` and `]` moved to 0xB0, 0xBA and 0xBB and were rejected. Array subscripts appear throughout ONFLY (`onfvgrp[op].vec[idx]`), so CP037 is unusable. The same two measurements together pin GCCMVS's source character set without assuming it: it accepts `|` at 0x4F, and it accepts `[`, `]` and `^` where `default` places them, which are IBM-1047's 0xAD, 0xBD and 0x5F. `819/1047` is the only available table that satisfies both at once, and 1047 is the page GCC and PDPCLIB target. Recorded as an amendment rather than a correction to D-99 because D-99's premise — that 0x4F is GCCMVS's `|` — was the thing that needed measuring and proved right; only the table chosen to deliver it was wrong |
| D-102 | **D-98 is superseded for this cycle: the 64-bit shift behaviour is measured before the NR-04 shims are written.** `tools/mvsgcc.py` gains a sweep of every left-shift count 0 to 63, constant and variable, and the 32x32-to-64 multiply that SoftFloat actually uses | Hold to D-98 and write the shims, then let Spike S1 produce the measurement from the real build; invoke NR-03 now and fall back to SoftFloat 2c; stop and report the findings | VL-19 proves GCCMVS's 64-bit left shift drops bit 63 for `a << 7`, and ONFLY's SoftFloat 3e build shifts 64-bit significands in exactly the paths that matter — `sigZ <<= 9`, `sigA <<= 9`, `sigA <<= 1` in `s_addMagsF64.c`, `<<10`, `<<11` and `sigZ <<= 1` in `f64_mul.c`, and the variable `a << (-dist & 63)` in `s_shiftRightJam64.c`. That makes Spike S1 a **predicted** silent failure, and NR-03's fallback to 2c would be invoked on a prediction rather than a measurement. A handful of probe jobs settles it either way, and a wrong result surfacing inside SoftFloat would be far harder to attribute than one surfacing in a probe. Twice already this session a measurement has changed the answer — the `-O` level and then the codepage — which is the argument for taking this one before committing work to either path |
| D-103 | **`tools/mvsub.py` refuses to submit when Hercules is not on codepage 819/1047.** The transport queries the Hercules console before sending a deck | Print a loud warning and submit anyway; record the precondition in documentation only and leave the tooling alone | VL-18 is a silent-failure class: a Hercules restart returns the codepage to `default`, `|` becomes unlexable again, and the next compile fails with a diagnostic that points at the source rather than at the configuration. This is the same shape as D-93 — the wrap fixed that day, the lint fixed every day after — and the same reasoning that rejected a warning there rejects one here, since a warning that can be scrolled past is how the blind golden fixture survived until D-70. The accepted cost is a dependency on the Hercules HTTP console being reachable, which every lab operation in this session already relies on |
| D-104 | **VL-20's prediction is measured before NR-03 is invoked on it.** The affected SoftFloat functions — `s_shiftRightJam64`, `s_shortShiftRightJam64`, `s_normSubnormalF64Sig` — are compiled under GCCMVS with known-answer vectors generated on x86, using the minimal NR-04 `stdint.h` and `stdbool.h` shims that D-98 already chose | Invoke NR-03 now and fall back to SoftFloat 2c; run the full Spike S1 with TT-02 under GCCMVS; try a newer GCCMVS first | VL-20 is analysis: the shift defect was measured in isolation and the call sites were read from the source, but SoftFloat has never been compiled under GCCMVS at all. NR-03 is a large, one-way step — a new vendored dependency and a different float library — and taking it on a prediction would repeat the pattern D-92 was decided on. The shims are required by NR-04 regardless of which library wins, so nothing done here is wasted. Twice in this session a measurement has overturned a prediction, once my own: the first operation matrix reported MUL and constant SHL as wrong and both proved correct once the probe's own scaffolding was fixed |
| D-105 | **NR-03 is invoked. Berkeley SoftFloat Release 2c is vendored as the soft backend for MVS.** Approved download: `SoftFloat-2c.zip`, 108,086 bytes, from `www.jhauser.us/arithmetic/` — the same author and canonical site D-28 took Release 3e from. It is committed under `third_party/` like 3e | Try a newer GCCMVS first, now that there are four specific defects to test it against; make JCC the primary compiler (SRS text changes to D-03 and the Gate G1 exit criterion); supply ONFLY-owned `@@UCMPDI`, `@@UDIVDI` and `@@UMODDI` and keep 3e | Gate G1 is answered and the answer is comprehensive: GCCMVS fails on 64-bit integers in **four independent ways** — internal compiler errors at 3590, 447, 902 and 6970; a silent wrong answer, the variable-count left shift zeroing bit 63 (VL-19); no runtime helpers in PDPCLIB, with `@@UCMPDI`, `@@UDIVDI` and `@@UMODDI` all unresolved (VL-21); and a code-generation bug asking for them through `=A()` where an external routine needs `=V()`. 2c implements binary64 in 32-bit integers only, which removes all four at once rather than one at a time — there is no 64-bit compare, divide or modulo to call, and no variable 64-bit shift to be wrong. Supplying the helpers was rejected on the measurement: it fixes one defect of four, leaving `s_shortShiftRightJam64.c` ICEing and the shift silently wrong. This is NR-03 and D-06 operating exactly as written, on measurement rather than prediction (D-104) |
| D-106 | **The SoftFloat 2c integration plan is approved.** In order: vendor 2c verbatim and record its provenance and licence in `third_party/MANIFEST.md`; write ONFLY's 2c configuration under `softfloat/c2c/` — a processor header **without** `BITS64`, plus `milieu.h`, `softfloat.h` and `softfloat-specialize` derived from upstream's templates by the substitutions upstream prescribes; then build 2c's `bits32` on x86 and **prove or disprove bit-identity with 3e** using TT-02's TestFloat vectors and `tools/cmpback.py`. The `onf_fp` backend and the MVS build come only after that result | Change the shape or ordering, for example proving 2c on MVS first or writing the backend before the identity check; discuss the approach and the risk to ACC-5 first | The identity check is the result that decides whether this swap is cheap or expensive, so it is front-loaded. Every ACC-5 fingerprint in the golden suite was computed with 3e; if 2c and 3e disagree on any of ONFLY's six binary64 operations, every fingerprint changes and that is a far larger decision than choosing a library. Building the backend first would mean discovering that after the expensive part rather than before it. 2c's `bits32` `float64` is a two-word struct rather than a scalar, so the backend is real work and is deliberately not started on an unproven premise |
| D-107 | **ONFLY's 2c build uses the ARM-VFPv2 default-NaN convention, matching D-31.** The `softfloat-specialize` file is written to that convention rather than taken from upstream's shipped 386 configuration | Use 2c's shipped 386-Win32-GCC conventions as-is; defer the choice, since VL-11 already excludes NaN cases from TT-02 and FR-SIM-08 aborts on NaN rather than propagating it | D-31 is an owner decision already on record and nothing has been measured that disturbs it. Keeping it means the 3e and 2c backends differ in as few respects as possible, so any disagreement the D-106 identity check finds is attributable to the arithmetic rather than to NaN policy — a mismatch under the shipped 386 conventions would have needed a second investigation to separate the two causes. The cost is a hand-written specialize file instead of a shipped one, which is small and follows D-35's precedent for ONFLY-owned SoftFloat pieces |

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
| ~~P-07~~ | Source line length on MVS | **CLOSED 2026-09-11 by D-93** — measured: the TK5 card reader truncates at 80 columns silently. ONFLY sources are held to 80 columns and linted; vendored `third_party/` is exempt and needs a different transport |

## Appendix B. Open items

| ID | Item | Affects | Resolved in |
|---|---|---|---|
| ~~TBC-01~~ | Shiu et al.'s integration method, within-step event ordering, stimulus delivery and refractory semantics | SR-MOD-01, SR-MOD-03, Appendix C | **CLOSED 2026-09-11 by D-71** — confirmed against Shiu's model.py; Appendix C is now normative |
| ~~TBC-02~~ | Unconfirmed parameter values (V_th, τ_mbr, t_rfr, τ_syn, dt) and the exact form of the synaptic equation | SR-MOD-02 | **CLOSED 2026-09-11 by D-66** — all confirmed against Shiu et al.'s published model.py; the SR-MOD-02 table was already correct |
| ~~TBC-03~~ | MaleCNS cell types for the sugar-sensing neurons and MN9 | FR-PRP-02 | **CLOSED 2026-09-11 by D-52** — stimulus PhG9 + dorsal_tpGRN (14 neurons), readout MN9 (2 neurons) |
| ~~TBC-04~~ | Neurotransmitter-to-sign mapping as used by Shiu et al. | FR-PRP-03 | **CLOSED 2026-09-11 by D-54 and D-55** — ACh +1; GABA/glutamate/histamine −1; monoamines excluded; neurons without a definite prediction have their outgoing edges excluded |
| ~~TBC-05~~ | Stimulation protocol details (neuron set, hemisphere, trial duration) | SR-MOD-04 | **CLOSED 2026-09-11 by D-73** — D-52 neuron set, both hemispheres, 1000 ms |
| TBC-06 | Source of the Shiu reference curve (re-run of published code, or figures) | SR-CAL-04 | Phase C — **still open**. D-77 deliberately kept it open on 2026-09-11: neither source is reachable from this host, and no calibration run may start until it is closed |
| TBD-06 | Standard duration, maximum duration, seeds per rate (proposed 30) | FR-SIM-06, NFR-PERF-01, Section 6.4 | Gate G3 — **still open**. D-37 sets a provisional 1000 ms / 5000 ms for x86 Phase B only; these are not the final values |
| TBD-07 | Calibration and validation rate split (proposed {20, 80, 160} and {10, 40, 120, 200} Hz) | SR-CAL-02 | Before first calibration |
| TBD-08 | Absolute tolerance floors (proposed ±1 Hz and ±2 Hz) | ACC-3, ACC-4 | Before first calibration |
| TBD-09 | Final magic constant | IR-NET-03 | Format v1.0 |
| TBD-10 | ONF message prefix collision check | IR-MSG-02 | Format v1.0 |
| ~~TBD-11~~ | PRNG algorithm confirmation | NR-13 | **CLOSED 2026-09-10 by D-32** — xorshift32 13/17/5, update-then-return, seed 0 → 2463534242 |
| ~~TBC-12~~ | MaleCNS data terms; repository license | NFR-LIC-01 | **FULLY CLOSED** — data terms by D-50 (MaleCNS v1.0 is CC BY 4.0, attribution required); repository licence by D-62 (MIT) |
| TBD-13 | Source of a CICS environment | Phase G | Later |
| TBD-14 | Region limit on TK5 | C-01, NFR-MEM-01 | Gate G0 |
| ~~TBD-15~~ | Owner sign-off on phase ordering | Section 9 | **CLOSED 2026-09-10 by D-24** — ordering approved as written |
| ~~TBD-16~~ | SoftFloat NaN specialization | NR-02 | **CLOSED 2026-09-10 by D-31** — ARM-VFPv2-defaultNaN |

## Appendix C. Normative simulation kernel (draft)

> **Status: NORMATIVE** (D-71). The step ordering below was reconciled against Shiu et al.'s published `model.py` in the 2026-09-11 session; TBC-01 is closed. Amendments D-67, D-68 and D-69 are marked inline. ⊕ and ⊗ are correctly rounded binary64 operations evaluated strictly left to right.

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
           # D-67: g is FROZEN while refractory, matching Shiu's
           # "(unless refractory)" on dg/dt.  u is held at U_reset.
           was_refractory = true
       else:
           a      = P11 (x) u[i]
           b      = P12 (x) g[i]
           u[i]   = a (+) b
           g[i]   = P22 (x) g[i]
           was_refractory = false
       if |g[i]| < G_EPS: g[i] = +0.0         # NR-08
       # D-69: the threshold is STRICT, matching Shiu's eq_th 'v > v_th'.
       if not was_refractory and (u[i] > U_th or force[i]):
           u[i]   = U_reset
           g[i]   = +0.0            # D-67: g is reset on every spike,
                                    # matching Shiu's eq_rst 'g = 0*mV'
           # D-68: stimulus neurons have NO refractory period, matching
           # Shiu's 'rfc = 0' for Poisson targets.
           rfr[i] = 0 if i is a stimulus neuron else REFRACTORY_STEPS
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
| VL-13 | The network scoped under D-56 contains **40.2% of the MaleCNS connectome's synapses** (125,365,933 of 311,833,243). The remaining 59.8% involve at least one body absent from the body-annotations file — fragments, orphans, or bodies below its minconf-0.5 confidence cut — and cannot be simulated because they have no cell type and no predicted transmitter. Applying D-54 and D-55 on top leaves 39.0%. Any ACC-3 truncation-fidelity result is therefore measured against a full-brain reference that is itself already this restricted, and the figure must not be read as a whole-connectome simulation. |
| VL-12 | The sugar stimulus set approved in D-52 is **pharyngeal and taste-peg** (PhG9, dorsal_tpGRN), selected from MaleCNS connectivity onto the Yao & Scott 2022 Sugar SEL neurons. Shiu et al. stimulate **labellar** sugar GRNs on FlyWire. The two protocols therefore excite different sensory populations, so ACC-4's comparison against the Shiu reference carries this difference on top of the male/female difference already noted in VL-06. The evidence is also thinner than the ranking suggests: gustatory input is only 8.3% of the marker neurons' total input, and PhG9 sends only 2.64% of its output to them. |
| VL-11 | TT-02's reference is built against the 8086 SoftFloat specialization, not the ARM-VFPv2-defaultNaN one the engine uses (D-46), because the latter cannot build a complete library. The two share their arithmetic cores verbatim and differ only in NaN handling, so cases whose operands or expected result are NaN are excluded from TT-02. TT-02 therefore proves nothing about NaN behaviour; FR-SIM-08 aborts on NaN instead. |
| VL-14 | TT-01 is proven on x86 only. On MVS the engine's startup self-test (D-79) references `__udivdi3` and `__umoddi3`, GCC's synthesised 64-bit division helpers, which no other engine object needs; whether GCCMVS and PDPCLIB supply them is unverified until Gate G1 (D-84). A TT-01 pass on x86 therefore says nothing about whether ONFLYENG will even link on MVS. **Answered on 2026-09-11 by VL-21: they are not supplied.** |
| VL-15 | **Gate G1 measurement, 2026-09-11, on TK5 MVS 3.8j under Hercules 4.9.1: GCCMVS cannot build ONFLY's 64-bit integer code.** A twelve-line source with no includes, containing only `v = (u64)0xFFFFFFFFU; v = v + (u64)1U;`, ends in `unable to generate reloads` and `Internal compiler error in ?, at 3590`. Per-operation probes, one job each: **add ICEs**; **multiply and divide compile but Assembler XF rejects the generated code (IFOX00 RC 8)**; subtract, both shifts, bitwise and, and assignment compile, link and run. JCC compiled and ran the identical construct correctly, returning 2^32 as hi=00000001 lo=00000000. Assumption **A-05 is disproved** and risk **R-01 has materialised**; this is not a wrong answer but a failure to build. |
| VL-16 | **The GCCMVS 64-bit addition defect is universal in form, and the engine's chosen mitigation survives it.** Four shapes of 64-bit addition were each compiled in their own job on TK5 on 2026-09-11 — `a + b`, `r += b`, `a + (u64)1U`, and the same split across two statements — and **all four ICE**. The 32-bit-halves form with a hand-propagated carry, which is how SoftFloat's not-FAST_INT64 build adds, **compiled, linked, ran and was correct**: 0xFFFFFFFF + 1 returned hi=00000001 lo=00000000. NR-02 and D-06 chose that build precisely because S/370 has no 64-bit integers, and this measurement shows the choice is load-bearing rather than merely prudent. It does **not** show that SoftFloat 3e itself builds under GCCMVS: that is Spike S1 and has not been attempted. It does show that TT-01 as written cannot be built by GCCMVS at all, since `onfi2p32` adds — the test meant to detect bad 64-bit code generation cannot be compiled by the compiler it was written to test. |
| VL-17 | **The GCCMVS optimisation level is decisive, and ONFLY is pinned to `-O1` (D-100).** Measured on TK5 on 2026-09-11, one job per level, on the identical twelve-line 64-bit addition of VL-15: `-O0` ICEs in the reload pass (`unable to generate reloads`, at 3590); `-O2`, `-O3` and `-Os` ICE at a different place (at 447); **`-O1` alone compiles, assembles, links, runs and returns 2^32 correctly**. Every measurement in VL-15 and VL-16 was taken with no `-O` flag, that is at the default level, and is therefore a statement about `-O0` rather than about GCCMVS as such. `-O1` is not chosen for code quality: it is the only level that threads between two distinct compiler defects, and any future GCCMVS or flag change invalidates every MVS result taken under it. |
| VL-18 | **ONFLY C source cannot reach GCCMVS through the card reader on Hercules' `default` codepage.** Measured on TK5 on 2026-09-11: ASCII `|` is delivered as EBCDIC 0x6A and GCCMVS rejects it outright (`stray '\152'`, octal for 0x6A); it is the only character of ``| ! ^ [ ] { } ~ # @ $ \ ` `` that it will not lex, and ASCII `!` arrives at its normal 0x5A so it is no substitute. `819/037` fixed `|` and broke three others — `^`, `[` and `]` moved to 0xB0, 0xBA and 0xBB and were rejected — which rules CP037 out, since array subscripts appear throughout the engine. Under **`819/1047`** all thirteen characters lex (D-101). The two failed pages together pin GCCMVS's source character set to IBM-1047 by measurement rather than assumption. **Every MVS compile result in this register is conditional on the codepage in force**, which is host configuration and is not carried in the repository: a lab restart returns Hercules to `default` and silently reintroduces this fault. |
| VL-19 | **GCCMVS at `-O1`, 64-bit operations, measured one job each on TK5 on 2026-09-11** with a = 0x0123456789ABCDEF, b = 0x00000000FEDCBA98, every result compared against the value computed on x86 and the operand itself printed back and checked inside each job. **Correct:** MUL (64×64), SHL by a *constant* count, SHR, SUB, AND, OR, and the 32×32→64 widening multiply that `s_mul64To128M.c` relies on. **DIV and MOD** compile but Assembler XF rejects the generated code (IFOX00 RC 8), as at the default level. **ADD** ICEs at 6970 in a realistic shape even though VL-17's minimal shape passes, so the addition defect is context-dependent rather than cured. **The one silent wrong answer is the variable-count left shift:** sweeping `a << n` for n = 0…63 with n a variable, **32 of the 64 counts are wrong**, and they are exactly the 32 for which the result's bit 63 should be set — `a` has exactly 32 bits set. **GCCMVS's variable 64-bit left shift always writes zero into bit 63.** The same counts as compile-time constants — including 1, 9, 10 and 11, the counts SoftFloat 3e actually uses — are all correct. **Withdrawn:** the first version of this entry reported MUL returning zero and `a << 7` dropping bit 63. Both were artifacts of the probe, not of the compiler: it built its operand with `(a << 32) + lo`, and 64-bit `+` is itself defective here, so the scaffolding shared a defect with its subject. With the operand built by OR and verified in-job, both operations are correct. The lesson is recorded rather than quietly fixed, because a probe that can produce a false positive of exactly the kind it is hunting is the same failure class as the blind golden fixture of D-70. |
| VL-20 | **SoftFloat 3e, as ONFLY builds it, depends on the one GCCMVS operation that is silently wrong.** VL-19 measured that a variable-count 64-bit left shift always writes zero into bit 63, while constant counts are correct. Every variable-count 64-bit left shift in ONFLY's actual build was then enumerated: `s_normSubnormalF64Sig.c:48` (`sig<<shiftDist`), `s_normRoundPackToF64.c:51` and `:54` (`sig<<(shiftDist - 10)` and `sig<<shiftDist`), `s_shiftRightJam64.c:46` (`a<<(-dist & 63)`, whose value feeds the sticky bit), `s_shortShiftRightJam64.c:45` (`((uint_fast64_t) 1<<dist) - 1`, where losing bit 63 at dist = 63 turns the mask from 0x7FFF…F into 0xFFFF…F) and ONFLY's own `softfloat/onfsub.c:120` (`sigDiff<<shiftDist`). These are the normalisation, rounding and sticky-bit paths — the places where a dropped top bit changes a result rather than merely a flag. The prediction is therefore that a SoftFloat 3e built by GCCMVS would compute wrong binary64 results **with no diagnostic at any stage**, which is the worst available outcome for a project whose premise is bit-exact reproducibility. **This was analysis, not measurement:** the shift defect was measured in isolation and the call sites were read from the source. **Superseded on 2026-09-11 by VL-21, which measured it and found the prediction wrong in the direction that matters: SoftFloat 3e does not reach the point of computing anything.** Neither affected function can be built — `s_shiftRightJam64.c` compiles and Assembler XF rejects the output, `s_shortShiftRightJam64.c` ICEs — so the failure is loud rather than silent. The shift-site enumeration above stands and remains the reason those sites matter if a compiler is ever found that builds them. NR-03 and D-06 anticipate exactly this case, SoftFloat 2c implementing binary64 in 32-bit integers only. |
| VL-21 | **Measured on TK5 on 2026-09-11 (D-104): SoftFloat 3e cannot be built by GCCMVS, and the reason is a missing runtime, not a wrong answer.** ONFLY's NR-04 shims were written and the vendored sources submitted unmodified. `tests/tstsfs.c` compiled and assembled clean (RC 0), so **the shims work on MVS** and `<stdint.h>` resolves from the VB/255 library. Of the two SoftFloat units: `s_shortShiftRightJam64.c` **ICEs at 6970**, and `s_shiftRightJam64.c` **compiles** and is then rejected by Assembler XF with `IFO188 @@UCMPDI IS AN UNDEFINED SYMBOL`. Two separate defects sit behind that one message. First, **PDPCLIB supplies none of the 64-bit helpers GCCMVS calls**: a minimal assembly declaring `@@UCMPDI` (unsigned 64-bit compare, `__ucmpdi2`), `@@UDIVDI` (`__udivdi3`) and `@@UMODDI` (`__umoddi3`) EXTRN and linked against PDPCLIB.NCALIB left **all three unresolved** (IEW0132). This answers VL-14 and D-84 definitively: they are not supplied. Second, **GCCMVS emits `L 15,=A(@@UCMPDI)`**, an A-type address constant, where an external routine needs `=V(...)` or an EXTRN — so the failure surfaces at assembly time as an undefined symbol instead of cleanly at link time as an unresolved reference. The consequence is decisive for the gate: `a != 0` on a `uint64_t` compiles into a call to `@@UCMPDI`, that expression is pervasive in SoftFloat, and there is nothing to link it to. The DIV and MOD rejections in VL-19 are the same defect with `@@UDIVDI` and `@@UMODDI`. |
| VL-22 | **SoftFloat 2c's `bits32` build agrees with TestFloat on all six operations ONFLY uses (D-106).** Measured on x86-64 Windows 11, MinGW gcc, `make c2c`: **260,376 cases checked, 0 mismatches** — add 43,396, sub 43,396, mul 43,390, lt 43,398, le 43,398, eq 43,398, with 18,408 NaN cases excluded per VL-11. `make tt02` runs Release 3e through the **same** generator and vectors and also passes, so the two libraries agree with the same independent oracle. That is the basis for expecting ACC-5 fingerprints to survive the NR-03 fallback. **What this does not prove.** It is agreement on TestFloat's level-1 vector set, not a proof of bit-identity on every input: TestFloat samples the interesting cases (boundaries, subnormals, rounding ties, cancellations) rather than enumerating 2^128 operand pairs, so this is very strong evidence and not a theorem. **No golden-suite fingerprint has been recomputed with 2c** — that needs an `onf_fp` backend, which does not exist, and 2c's `float64` is a two-word struct rather than a scalar so the backend is real work. **Nothing here was measured on MVS:** 2c has never been compiled by GCCMVS, so the reason it was chosen is still unverified on the platform it was chosen for. Two configuration facts are recorded because they are easy to mistake for defects: 2c's shipped `float_detect_tininess = float_tininess_after_rounding` was **kept**, since it gates only `float_raise(float_flag_underflow)` and never the returned value, and ONFLY discards flags (D-34, NR-10); and `float_raise` itself is generated as a no-op, which is D-34 applied to 2c exactly as it was to 3e. |

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
| ONF108E | 12 | NETWORK DATASET UNREADABLE | The network could not be read at all: absent, empty, or unopenable. Check the ONFNET DD or the supplied path. Added by D-85 |
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
| ONF905S | 16 | REQUEST PROCESSING NOT BUILT AT THIS ENGINE LEVEL | The engine was built without the request loop (D-78). Verify-only runs are unaffected; submit requests against a Phase E engine. Added by D-81 |

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

