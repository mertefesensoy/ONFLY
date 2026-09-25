# tools/

The programs that build, check, submit and compare ONFLY's runs. Each file's
docstring states what it does, which requirement or decision it serves, and
what it cannot show. The groups below are a map, not a specification.

| Group | Files | Purpose |
|---|---|---|
| Lints | `lint_*.py` | Checks run by `make test`: no floating-point types in the engine (`lint_nr05.py`), 80-column sources (`lint_col80.py`), eight-character external names (`lint_c04.py`), no INTERCOMM-derived material (`lint_lic.py`), no program name in public text (`lint_name.py`), and the third-party notices register (`lint_ntc.py`) |
| Generators | `gen*.py` | Write files under `generated/`; see `generated/README.md` |
| Comparisons | `cmp*.py`, `goldfp.py` | Compare fingerprints and records between backends, chunk sizes and platforms; `goldfp.py` holds the Section 8.4 golden fingerprints in one place |
| Networks | `fixtures.py`, `runnet.c`, `fullbrain.sh` | Place and verify the network files the suite runs on; run one request against a network, the full-brain reference runner |
| Requests and transport | `mkreq.py`, `mkaws.py`, `mkasl.py`, `g2ind.py` | Control cards into request records; the tape images and transfer checks of Gate G2 |
| Emulated MVS lab | `mvs*.py`, `g0.py` | Build decks, submit jobs to MVS 3.8j under Hercules (TK5) and collect what they print; `g0.py` is the Gate G0 inventory. They need your own TK5 system; `tests/run_mvs*.py` check what they produce without one |
| 3270 | `tn3270.py`, `tso3270.py`, `ic3270.py` | Drive a 3270 terminal emulator against the emulated MVS lab |
| Transaction and live view | `cicsbld.py`, `rcprobe.py`, `liveview.py` | Build and run the `EXEC CICS` transaction under Raincode on Windows, and its probes; draw the live view from a streamed run |
| Other | `mkobjs.py`, `tfgprep.py`, `row7amend.py`, `progress.py` | A compile helper, the TestFloat generator's build directories, the row 7 amender, and a progress display; see each docstring |

Nothing here runs on IBM Z hardware: the project does not have IBM Z access
yet (SRS VL-139).
