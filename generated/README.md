# generated/

Every file in this directory except this README is written by a program.
**Never edit one by hand** (SRS IR-COM-01, D-18): change the generator and
run it again. The build checks several of them against their generators, and
a hand edit is lost on the next run.

They are committed on purpose. MVS 3.8j has no Python, so the MVS build reads
these files exactly as they are; generating them there is not possible.

| File | Generator | What it is |
|---|---|---|
| `ONFCOM.cpy`, `onfcom.h`, `onfcom.c`, `onfcom_py.py` | `layout/generate.py` | The 412-byte request and response record, in COBOL, C and Python, from one master definition, `layout/master.py` |
| `ONFLYDRV.cbl` | `layout/generate.py` | The COBOL driver, with the record layout inlined, because MVT COBOL's COPY is not usable here (Gate G4) |
| `ONFSTM.cpy`, `onfnhd.h` | `layout/generate.py` | The stream and network-header layouts, from `layout/master.py` |
| `onf3enm.h`, `onf2cnm.h` | `tools/gen3enm.py`, `tools/gen2cnm.py` | Short external names for SoftFloat 3e and 2c, which the MVS linkage editor needs (C-04) |
| `onfivec.h`, `onf32v.h` | `tools/genint.py`, `tools/gen32v.py` | Known-answer vectors for the 64-bit and 32-bit integer self-tests |
| `onf2cv.h` | `tools/gen2cv.py` | Known-answer vectors for SoftFloat 2c |
| `onftfv.h` | `tools/gentf2.py` | A sample of TestFloat 3e's test cases, for the MVS float self-test; see `THIRD_PARTY_NOTICES.md`, section 2 |
| `onfsynt.h` | `tools/gensyn.py` | A small synthetic network as a C array, for platforms no network file has reached |

Each file's own header names its generator and the decisions behind it.
