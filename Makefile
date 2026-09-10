# ONFLY x86 development build (D-29).
#
# Run with:  mingw32-make test
#
# Portability note.  Recipes avoid shell built-ins and use python for file
# operations, because mingw32-make picks cmd.exe or sh.exe depending on what is
# on PATH, and `rm`/`mkdir -p` are not available in both.  python is a hard
# dependency of this project anyway: it is the oracle (O-1) and the layout
# generator (D-18).
#
# This Makefile builds the x86 development host only.  MVS builds are driven by
# JCL and the Linux s390x build has its own configuration; NFR-PRT-01 keeps one
# engine source across all of them, with only the platform header differing.

PYTHON  = python
CC      = gcc

BUILD   = build

# C89 plus long long (NR-04), warnings as errors.  The engine and the tests are
# held to -pedantic so that a construct GCCMVS would reject fails here first.
CFLAGS  = -std=c89 -pedantic -Wall -Wextra -Werror -O2

# SoftFloat's own sources predate C89 pedantry in places and use C99 types via
# stdint.h, so they are compiled without -pedantic.  This is not a relaxation of
# NR-04 for ONFLY code: only third_party/ and the derived files are built this
# way, and the NR-05 lint still covers the derived files.
#
# -Wno-unused-function: platform.h sets INLINE to `static` for portability, so
# every translation unit gets a private copy of the small helpers in
# specialize.h, including the float128 and extF80 ones ONFLY never compiles
# (D-33).  Those are genuinely unused and warn on every file.  Silencing this
# one warning keeps the build output readable, which matters because the MVS
# build's real diagnostics must not be lost in a wall of known noise.
SFFLAGS = -O2 -Wall -Wno-unused-function

# D-30: this host's gcc is 32-bit mingw32, where x87 extended precision is the
# default.  NR-09 forbids it, so the native backend is built with SSE2 forced,
# FMA contraction off and no fast-math.  A native build without these is not an
# admitted backend.
NATFLAGS = -msse2 -mfpmath=sse -ffp-contract=off -DONF_FP_NATIVE -DONF_FP_LITTLE

SF      = third_party/SoftFloat-3e/source
SP      = $(SF)/ARM-VFPv2-defaultNaN

INC     = -Iengine/include -Igenerated
SFINC   = -Isoftfloat -I$(SF)/include -I$(SP)

# The binary64 subset only (D-33).  The float128, extF80, f16 and f32 sources
# are not built; one of them, the chosen specialization's s_propagateNaNF128M.c,
# does not even compile upstream.  Gate G1's record must state this scope (D-36).
SFSRCS = \
  $(SF)/f64_add.c $(SF)/f64_sub.c $(SF)/f64_mul.c \
  $(SF)/f64_lt.c $(SF)/f64_le.c $(SF)/f64_eq.c \
  $(SF)/s_addMagsF64.c $(SF)/s_normSubnormalF64Sig.c $(SF)/s_normRoundPackToF64.c \
  $(SF)/s_shiftRightJam64.c $(SF)/s_shortShiftRightJam64.c \
  $(SF)/s_countLeadingZeros8.c $(SF)/s_countLeadingZeros32.c \
  $(SF)/s_countLeadingZeros64.c $(SF)/s_mul64To128M.c \
  $(SP)/s_f64UIToCommonNaN.c $(SP)/s_commonNaNToF64UI.c $(SP)/s_propagateNaNF64UI.c

# ONFLY-owned derived SoftFloat files (D-34, D-35).  softfloat_raiseFlags.c and
# softfloat_state.c from upstream are deliberately NOT built.
ONFSF = softfloat/onfrpk.c softfloat/onfflag.c softfloat/onfsub.c

GENERATED = generated/onfcom.h generated/onfcom.c generated/ONFCOM.cpy \
            generated/onfcom_py.py generated/onfnhd.h

.PHONY: all test generate lint clean units layout fp kernel decode

all: test

# --- Generated artifacts (IR-COM-01, D-18) ---------------------------------
# Never edit anything under generated/ or softfloat/onfsub.c by hand.
generate:
	$(PYTHON) layout/generate.py
	$(PYTHON) softfloat/derive.py

$(GENERATED): layout/master.py layout/generate.py
	$(PYTHON) layout/generate.py

softfloat/onfsub.c: softfloat/derive.py
	$(PYTHON) softfloat/derive.py

# --- NR-05 lint -------------------------------------------------------------
# Mandatory in every build: a stray double compiled by GCCMVS would silently be
# hexadecimal floating point.  engine/src/onffpn.c is the native backend and is
# excluded by design; it is the only file in ONFLY allowed to name `double`.
lint: $(GENERATED)
	$(PYTHON) tools/lint_nr05.py --exclude engine/src/onffpn.c \
	  engine generated softfloat tests

$(BUILD):
	$(PYTHON) -c "import os; os.path.isdir('$(BUILD)') or os.makedirs('$(BUILD)')"

# --- TU-01, TU-07: layout and accessors ------------------------------------
layout: $(BUILD) $(GENERATED)
	$(CC) $(CFLAGS) $(INC) -o $(BUILD)/tstcom.exe tests/tstcom.c generated/onfcom.c
	$(BUILD)/tstcom.exe

# --- TU-03, TU-04, TU-05: CRC, PRNG, stimulus against the oracle -----------
units: $(BUILD)
	$(CC) $(CFLAGS) $(INC) -o $(BUILD)/tstunit.exe tests/tstunit.c \
	  engine/src/onfcrc.c engine/src/onfrnd.c engine/src/onfstm.c
	$(PYTHON) tests/run_units.py $(BUILD)/tstunit.exe

# --- TU-02: float API against the oracle, both backends --------------------
# The soft backend is the reference (D-04).  The native build additionally
# demonstrates NR-09's bit-identity condition on this host; NR-09 admission is
# NOT complete until TestFloat vectors (TT-02) and golden-suite fingerprints
# also pass.
fp: $(BUILD) softfloat/onfsub.c
	$(CC) $(SFFLAGS) $(INC) $(SFINC) -o $(BUILD)/tstfp_soft.exe \
	  tests/tstfp.c engine/src/onffpc.c engine/src/onffps.c engine/src/onfrnd.c \
	  $(SFSRCS) $(ONFSF)
	$(PYTHON) tests/run_fp.py $(BUILD)/tstfp_soft.exe
	$(CC) $(SFFLAGS) $(NATFLAGS) $(INC) -o $(BUILD)/tstfp_nat.exe \
	  tests/tstfp.c engine/src/onffpc.c engine/src/onffpn.c engine/src/onfrnd.c
	$(PYTHON) tests/run_fp.py $(BUILD)/tstfp_nat.exe
	$(PYTHON) tools/cmpback.py $(BUILD)/tstfp_soft.exe $(BUILD)/tstfp_nat.exe

# --- L2: the kernel against the Python oracle ------------------------------
# Runs the same synthetic network through both float backends and then compares
# the two builds byte for byte.  Together with the oracle itself that covers
# rows 1, 2 and 3 of the Section 8.3 determinism matrix -- the three x86 rows.
# Rows 4 to 8 need Linux s390x, MVS 3.8j and z/OS, none of which is available
# on this host.
kernel: $(BUILD) softfloat/onfsub.c
	$(CC) $(SFFLAGS) $(INC) $(SFINC) -o $(BUILD)/tstker_soft.exe \
	  tests/tstker.c engine/src/onfker.c engine/src/onffpc.c \
	  engine/src/onffps.c engine/src/onfrnd.c engine/src/onfstm.c \
	  $(SFSRCS) $(ONFSF)
	$(PYTHON) tests/run_ker.py $(BUILD)/tstker_soft.exe
	$(CC) $(SFFLAGS) $(NATFLAGS) $(INC) -o $(BUILD)/tstker_nat.exe \
	  tests/tstker.c engine/src/onfker.c engine/src/onffpc.c \
	  engine/src/onffpn.c engine/src/onfrnd.c engine/src/onfstm.c
	$(PYTHON) tests/run_ker.py $(BUILD)/tstker_nat.exe
	$(PYTHON) tools/cmpback.py $(BUILD)/tstker_soft.exe $(BUILD)/tstker_nat.exe

# --- TE-01..TE-08: network integrity checks ------------------------------
# Each case corrupts exactly one thing and requires the engine to report the
# specific Appendix E condition, not merely to reject the file.  That
# distinction is what tells an operator to re-send in binary rather than to
# rebuild the network (NFR-REL-01).
decode: $(BUILD) $(GENERATED)
	$(CC) $(CFLAGS) $(INC) -o $(BUILD)/tstdec.exe tests/tstdec.c \
	  engine/src/onfdec.c engine/src/onfcrc.c engine/src/onffpc.c
	$(PYTHON) tests/run_dec.py $(BUILD)/tstdec.exe

test: lint layout units fp kernel decode
	@echo "ONFLY: lint + TU-01..TU-07 + kernel + TE-01..TE-08 all passed"

clean:
	$(PYTHON) -c "import shutil,os; shutil.rmtree('$(BUILD)', ignore_errors=True)"
