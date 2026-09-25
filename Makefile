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
#
# -include generated/onf3enm.h forces the C-04 renames into every 3e
# translation unit (D-113, D-114).  It has to be -include rather than a
# line in a header, because it must be in effect before primitives.h is
# read: five of the names are upstream's own #ifndef feature tests.
SFFLAGS = -O2 -Wall -Wno-unused-function -include generated/onf3enm.h

# --- Platform selection (D-218) --------------------------------------------
# This is the ONLY part of the build that varies between platforms, which is
# why Phase D parameterised this file rather than copying it.  Everything
# below this block is shared, so an x86 rule change cannot drift from the
# s390x one: there is only one copy of it.
#
# Select with ONFPLAT.  The default reproduces the x86 Windows build exactly
# as it was before D-218, so an invocation that names no platform behaves
# identically to every result already in the repository.
#
#   x86w    x86-64 Windows, 32-bit mingw gcc   (the development host, D-29)
#   s390x   Linux on z/Architecture, native gcc (Phase D, D-215)
#             invoke as: make ONFPLAT=s390x CC=gcc PYTHON=python3
#
# NR-09 admissibility of the native backend is what these flags encode, and
# the two platforms need different spellings of the same three guarantees:
# IEEE binary64 with round-to-nearest-even, no FMA contraction, no fast-math.
ONFPLAT ?= x86w

ifeq ($(ONFPLAT),x86w)
# D-30: this host's gcc is 32-bit mingw32, where x87 extended precision is the
# default.  NR-09 forbids it, so the native backend is built with SSE2 forced,
# FMA contraction off and no fast-math.  A native build without these is not an
# admitted backend.
#
# ONF_FP_LITTLE selects the byte swap in engine/src/onffpn.c: that file builds
# the binary64 bit pattern in big-endian order first and swaps it into host
# order, so the mapping is stated rather than inherited (IR-NET-01).
NATFLAGS = -msse2 -mfpmath=sse -ffp-contract=off -DONF_FP_NATIVE -DONF_FP_LITTLE

else ifeq ($(ONFPLAT),s390x)
# z/Architecture has no x87 and no extended-precision accumulator, so there is
# nothing corresponding to -msse2 -mfpmath=sse to force: gcc's `double` on
# s390x is already IEEE binary64 in the BFP registers, not the S/360
# hexadecimal format.  -ffp-contract=off is still required -- s390x has a
# fused multiply-add (MADBR) that gcc will contract into without it, which
# NR-09 forbids because the MVS and soft backends cannot reproduce it.
#
# ONF_FP_LITTLE is deliberately NOT defined.  s390x is big-endian, so the
# big-endian byte array onffpn.c builds is already in host order and must not
# be swapped.  This is the one behavioural difference between the two
# platforms' native backends, and it is a compile-time switch rather than a
# run-time test so that a wrong answer here fails TU-02 immediately.
NATFLAGS = -ffp-contract=off -DONF_FP_NATIVE

else
$(error ONFPLAT is '$(ONFPLAT)'; expected one of: x86w s390x)
endif

# D-121, D-124: the SOFT2C backend, Berkeley SoftFloat 2c's bits32 build.
# This is the library MVS uses (D-105, NR-03), so a golden fingerprint
# produced with it on x86 is the only thing an MVS fingerprint can later be
# compared against on equal terms.  -include forces the C-04 renames into
# every unit that sees 2c's header (D-111).
SF2CFLAGS = -DONF_FP_SOFT2C $(SF2CINC) -include generated/onf2cnm.h

SF      = third_party/SoftFloat-3e/source
SP      = $(SF)/ARM-VFPv2-defaultNaN

# Release 2c, the MVS backend (D-105, NR-03).  Its bits32 build uses only
# 32-bit integers, which is the property GCCMVS forces (VL-19, VL-21).
SF2C    = third_party/SoftFloat-2c/softfloat/bits32

# The library ONFLY compiles is the DERIVED softfloat.c, not upstream's
# (D-123).  The three pieces of writable static state are gone from it, so
# the 2c backend matches the 3e backend's NFR-MNT-02 property.  Upstream's
# file is still the input to softfloat/derive2c.py and is never edited.
SF2CSRC = softfloat/c2c/softfloat.c

# -Isoftfloat/c2c first so milieu.h, softfloat.h and softfloat-specialize
# come from the derived configuration; -I$(SF2C) after it for
# softfloat-macros, which is vendored unmodified and has no ONFLY version.
SF2CINC = -Isoftfloat/c2c -I$(SF2C)

# Upstream 2c warns in float32_rem and float64_rem -- unused variables and one
# pointer-sign mismatch -- neither of which ONFLY compiles into anything it
# calls.  third_party is not edited (D-28, D-35), so -Werror cannot be used on
# it.  Everything else stays as strict as the rest of the build.
C2CFLAGS = -std=c89 -pedantic -Wall -O2

INC     = -Iengine/include -Igenerated

# The engine units tests/tstsyn.c links, backend excluded.  Named once
# because the same list goes to MVS in tools/mvssyn.py, and two copies
# of it would drift.
ENGSRC  = engine/src/onfdec.c engine/src/onfcrc.c engine/src/onffpc.c \
          engine/src/onfker.c engine/src/onfrnd.c engine/src/onfstm.c \
          engine/src/onffpr.c
SFINC   = -Isoftfloat -I$(SF)/include -I$(SP)

# The binary64 subset only (D-33).  The float128, extF80, f16 and f32 sources
# are not built; one of them, the chosen specialization's s_propagateNaNF128M.c,
# does not even compile upstream.  Gate G1's record must state this scope (D-36).
SFSRCS = \
  $(SF)/f64_add.c $(SF)/f64_sub.c $(SF)/f64_mul.c \
  $(SF)/f64_lt.c $(SF)/f64_le.c $(SF)/f64_eq.c \
  $(SF)/s_addMagsF64.c $(SF)/s_normSubnormalF64Sig.c $(SF)/s_normRoundPackToF64.c \
  $(SF)/s_countLeadingZeros8.c \
  $(SP)/s_f64UIToCommonNaN.c $(SP)/s_commonNaNToF64UI.c $(SP)/s_propagateNaNF64UI.c

# ONFLY-owned derived SoftFloat files (D-34, D-35, D-114).
# softfloat_raiseFlags.c and softfloat_state.c from upstream are deliberately
# NOT built.  Nor are s_shiftRightJam64.c, s_shortShiftRightJam64.c,
# s_countLeadingZeros32.c, s_countLeadingZeros64.c and s_mul64To128M.c: each
# of those five is guarded by `#ifndef <its own name>`, generated/onf3enm.h
# now defines those names, and upstream therefore omits the definitions
# (VL-27).  softfloat/onfprim.c carries the same bodies under C-04 compliant
# names, which is upstream's extension point used as designed.
ONFSF = softfloat/onfrpk.c softfloat/onfflag.c softfloat/onfsub.c \
        softfloat/onfprim.c

GENERATED = generated/onfcom.h generated/onfcom.c generated/ONFCOM.cpy generated/ONFSTM.cpy \
            generated/onfcom_py.py generated/onfnhd.h generated/ONFLYDRV.cbl

# TT-01's known-answer table (D-79).  Separate from $(GENERATED) because that
# list shares a single rule whose recipe is layout/generate.py; this one comes
# from tools/genint.py instead.
IVEC = generated/onfivec.h

.PHONY: all test generate lint liclint clean units layout fp kernel decode golden syn tt01 tt0132 tt02 c2c tf2 sfs shim testfloat c04 c04mvs col80 prep runner eng req sub mvsrun names fixtures fixtures-check

all: test

# --- Generated artifacts (IR-COM-01, D-18) ---------------------------------
# Never edit anything under generated/ or softfloat/onfsub.c by hand.
generate:
	$(PYTHON) layout/generate.py
	$(PYTHON) softfloat/derive.py
	$(PYTHON) tools/genint.py

# cobol/ONFLYDRV.cbl is the driver TEMPLATE: generate.py expands its COPY
# into generated/ONFLYDRV.cbl, the source that is actually compiled (D-161).
$(GENERATED): layout/master.py layout/generate.py cobol/ONFLYDRV.cbl
	$(PYTHON) layout/generate.py

softfloat/onfsub.c: softfloat/derive.py
	$(PYTHON) softfloat/derive.py

$(IVEC): tools/genint.py
	$(PYTHON) tools/genint.py

# --- NR-05 lint -------------------------------------------------------------
# Mandatory in every build: a stray double compiled by GCCMVS would silently be
# hexadecimal floating point.  engine/src/onffpn.c is the native backend and is
# excluded by design; it is the only file in ONFLY allowed to name `double`.
# --- 80-column lint (D-93) ------------------------------------------------
# Measured on the running TK5: an 85-character card submitted to the reader
# arrived as 80 characters, columns 81 onward discarded, with no error and
# no message.  Source that must reach MVS is held to 80 columns so that
# truncation cannot happen silently.  third_party/ is exempt and skipped:
# D-28 and D-35 commit it to byte-identity with upstream, so it needs a
# transport that preserves long lines instead.
col80: $(GENERATED) $(IVEC) softfloat/onfsub.c
	$(PYTHON) tools/lint_col80.py engine generated softfloat tests tools cobol cics

lint: $(GENERATED)
	$(PYTHON) tools/lint_nr05.py --exclude engine/src/onffpn.c \
	  engine generated softfloat tests tools

# --- licence lint (D-132) -------------------------------------------------
# INTERCOMM is non-commercial-only including derivative works (VL-38) and
# this repository is MIT (D-62); the two cannot both govern one file.  D-132
# removes the question by keeping INTERCOMM-derived material out of the tree
# entirely -- it lives under local/ or on TK5.  A rule kept only in prose is
# one that gets broken later by a pasted copybook that looks like ordinary
# COBOL in review, so it is checked instead of trusted.  No prerequisites:
# it reads the git index, not the build.
liclint:
	$(PYTHON) tools/lint_lic.py

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
fp: $(BUILD) softfloat/onfsub.c softfloat/onfprim.c $(SF2CSRC) generated/onf2cnm.h
	$(CC) $(SFFLAGS) $(INC) $(SFINC) -o $(BUILD)/tstfp_soft.exe \
	  tests/tstfp.c engine/src/onffpc.c engine/src/onffps.c engine/src/onfrnd.c \
	  $(SFSRCS) $(ONFSF)
	$(PYTHON) tests/run_fp.py $(BUILD)/tstfp_soft.exe
	$(CC) $(SFFLAGS) $(NATFLAGS) $(INC) -o $(BUILD)/tstfp_nat.exe \
	  tests/tstfp.c engine/src/onffpc.c engine/src/onffpn.c engine/src/onfrnd.c
	$(PYTHON) tests/run_fp.py $(BUILD)/tstfp_nat.exe
	$(CC) $(C2CFLAGS) $(SF2CFLAGS) $(INC) -o $(BUILD)/tstfp_2c.exe  \
	  tests/tstfp.c engine/src/onffpc.c engine/src/onffp2.c  \
	  engine/src/onfrnd.c $(SF2CSRC)
	$(PYTHON) tests/run_fp.py $(BUILD)/tstfp_2c.exe
	$(PYTHON) tools/cmpback.py $(BUILD)/tstfp_soft.exe  \
	  $(BUILD)/tstfp_nat.exe $(BUILD)/tstfp_2c.exe

# --- L2: the kernel against the Python oracle ------------------------------
# Runs the same synthetic network through both float backends and then compares
# the two builds byte for byte.  Together with the oracle itself that covers
# rows 1, 2 and 3 of the Section 8.3 determinism matrix -- the three x86 rows.
# Rows 4 to 8 need Linux s390x, MVS 3.8j and z/OS, none of which is available
# on this host.
kernel: $(BUILD) softfloat/onfsub.c $(SF2CSRC) generated/onf2cnm.h
	$(CC) $(SFFLAGS) $(INC) $(SFINC) -o $(BUILD)/tstker_soft.exe \
	  tests/tstker.c engine/src/onfker.c engine/src/onffpc.c \
	  engine/src/onffps.c engine/src/onfrnd.c engine/src/onfstm.c \
	  $(SFSRCS) $(ONFSF)
	$(PYTHON) tests/run_ker.py $(BUILD)/tstker_soft.exe
	$(CC) $(SFFLAGS) $(NATFLAGS) $(INC) -o $(BUILD)/tstker_nat.exe \
	  tests/tstker.c engine/src/onfker.c engine/src/onffpc.c \
	  engine/src/onffpn.c engine/src/onfrnd.c engine/src/onfstm.c
	$(PYTHON) tests/run_ker.py $(BUILD)/tstker_nat.exe
	$(CC) $(C2CFLAGS) $(SF2CFLAGS) $(INC) -o $(BUILD)/tstker_2c.exe  \
	  tests/tstker.c engine/src/onfker.c engine/src/onffpc.c  \
	  engine/src/onffp2.c engine/src/onfrnd.c engine/src/onfstm.c  \
	  $(SF2CSRC)
	$(PYTHON) tests/run_ker.py $(BUILD)/tstker_2c.exe
	$(PYTHON) tools/cmpback.py $(BUILD)/tstker_soft.exe  \
	  $(BUILD)/tstker_nat.exe $(BUILD)/tstker_2c.exe

# --- TE-01..TE-08: network integrity checks ------------------------------
# Each case corrupts exactly one thing and requires the engine to report the
# specific Appendix E condition, not merely to reject the file.  That
# distinction is what tells an operator to re-send in binary rather than to
# rebuild the network (NFR-REL-01).
decode: $(BUILD) $(GENERATED)
	$(CC) $(CFLAGS) $(NATFLAGS) $(INC) -o $(BUILD)/tstdec.exe \
	  tests/tstdec.c engine/src/onfdec.c engine/src/onfcrc.c \
	  engine/src/onffpc.c engine/src/onffpn.c engine/src/onfker.c \
	  engine/src/onfrnd.c engine/src/onfstm.c
	$(PYTHON) tests/run_dec.py $(BUILD)/tstdec.exe

# --- ACC-5: the golden request suite (SRS 8.4) ---------------------------
# Runs all thirteen golden requests through validate, simulate and
# fingerprint on both backends, checks every fingerprint against the
# oracle, then requires the two backends to agree.  That is rows 1, 2 and 3
# of the Section 8.3 determinism matrix.  Rows 4 to 8 need Linux s390x,
# MVS 3.8j and z/OS and cannot run on this host.
#
# The durations come from D-37 and D-42 and are PROVISIONAL: TBD-06 is open
# and Gate G3 fixes the real values.  Changing one changes every
# fingerprint, so these are not yet reference values.
golden: $(BUILD) $(GENERATED) softfloat/onfsub.c $(SF2CSRC) generated/onf2cnm.h
	$(CC) $(SFFLAGS) $(INC) $(SFINC) -o $(BUILD)/tstgld_soft.exe \
	  tests/tstgld.c engine/src/onfreq.c generated/onfcom.c \
	  engine/src/onfdec.c engine/src/onfcrc.c \
	  engine/src/onffpc.c engine/src/onffps.c engine/src/onfker.c \
	  engine/src/onfrnd.c engine/src/onfstm.c engine/src/onffpr.c \
	  $(SFSRCS) $(ONFSF)
	$(PYTHON) tests/run_gld.py $(BUILD)/tstgld_soft.exe
	$(CC) $(SFFLAGS) $(NATFLAGS) $(INC) -o $(BUILD)/tstgld_nat.exe \
	  tests/tstgld.c engine/src/onfreq.c generated/onfcom.c \
	  engine/src/onfdec.c engine/src/onfcrc.c \
	  engine/src/onffpc.c engine/src/onffpn.c engine/src/onfker.c \
	  engine/src/onfrnd.c engine/src/onfstm.c engine/src/onffpr.c
	$(PYTHON) tests/run_gld.py $(BUILD)/tstgld_nat.exe
	$(CC) $(C2CFLAGS) $(SF2CFLAGS) $(INC) -o $(BUILD)/tstgld_2c.exe  \
	  tests/tstgld.c engine/src/onfreq.c generated/onfcom.c \
	  engine/src/onfdec.c engine/src/onfcrc.c  \
	  engine/src/onffpc.c engine/src/onffp2.c engine/src/onfker.c  \
	  engine/src/onfrnd.c engine/src/onfstm.c engine/src/onffpr.c  \
	  $(SF2CSRC)
	$(PYTHON) tests/run_gld.py $(BUILD)/tstgld_2c.exe
	$(PYTHON) tools/cmpgld.py $(BUILD)/tstgld_soft.exe  \
	  $(BUILD)/tstgld_nat.exe $(BUILD)/tstgld_2c.exe
# FR-SIM-10 (D-366, D-367, D-368): the same nineteen requests driven in
# chunks must give byte-identical GOLD and GOUT lines.  D-369 fixes the
# sweep at K in {1, 7, 250, 100000} on all three backends and measures the
# cost at about 4.6 minutes.  The four are not arbitrary: 1 puts a boundary
# between every pair of steps; 7 divides neither 10,000 nor 13,000, so
# boundaries land unaligned and the last chunk is short; 250 divides 10,000
# but not G-09's 13,000; and 100000 exceeds every request in the suite, so
# onfcont clamps on the first call (D-367) and the driver loop ends after
# one iteration.
	$(PYTHON) tools/cmpchk.py $(BUILD)/tstgld_soft.exe \
	  $(BUILD)/tstgld_nat.exe $(BUILD)/tstgld_2c.exe \
	  --chunks 1,7,250,100000

# --- FR-LOD-02/04/05, FR-SIM-01 and IR-COM-05 over an EMBEDDED network ---
# The same path `golden` exercises -- decode, integrity-check, load,
# simulate, fingerprint -- but driven from a network compiled into the
# program.  That is what lets it run where no network file can go yet
# (D-121, D-122); `python tools/mvssyn.py` is the MVS half.
#
# All three backends, then a byte-for-byte comparison: a fingerprint that
# depended on which float library produced it would not be a fingerprint.
syn: $(BUILD) $(GENERATED) generated/onfsynt.h softfloat/onfsub.c \
     $(SF2CSRC) generated/onf2cnm.h
	$(PYTHON) tools/gensyn.py --check
	$(CC) $(SFFLAGS) $(INC) $(SFINC) -o $(BUILD)/tstsyn_soft.exe \
	  tests/tstsyn.c $(ENGSRC) generated/onfcom.c \
	  engine/src/onffps.c $(SFSRCS) $(ONFSF)
	$(PYTHON) tests/run_syn.py $(BUILD)/tstsyn_soft.exe
	$(CC) $(SFFLAGS) $(NATFLAGS) $(INC) -o $(BUILD)/tstsyn_nat.exe \
	  tests/tstsyn.c $(ENGSRC) generated/onfcom.c engine/src/onffpn.c
	$(PYTHON) tests/run_syn.py $(BUILD)/tstsyn_nat.exe
	$(CC) $(C2CFLAGS) $(SF2CFLAGS) $(INC) -o $(BUILD)/tstsyn_2c.exe \
	  tests/tstsyn.c $(ENGSRC) generated/onfcom.c \
	  engine/src/onffp2.c $(SF2CSRC)
	$(PYTHON) tests/run_syn.py $(BUILD)/tstsyn_2c.exe
	$(PYTHON) tools/cmpback.py $(BUILD)/tstsyn_soft.exe \
	  $(BUILD)/tstsyn_nat.exe $(BUILD)/tstsyn_2c.exe

# --- C-04: external identifier lengths -----------------------------------
# ONFLY's own externals must stay within 8 characters and be unique ignoring
# case.  The vendored SoftFloat names are far longer; that is a Gate G1
# question (D-45), so they are reported and not failed on.
c04: $(BUILD) $(GENERATED) $(IVEC) softfloat/onfsub.c
	$(PYTHON) tools/mkobjs.py $(BUILD)/obj \
	  $(CC) $(SFFLAGS) $(INC) $(SFINC) -- \
	  engine/src/onfcrc.c engine/src/onfrnd.c engine/src/onfstm.c \
	  engine/src/onffpc.c engine/src/onffps.c engine/src/onfker.c \
	  engine/src/onfdec.c engine/src/onffpr.c generated/onfcom.c \
	  engine/src/onfreq.c engine/src/onfcics.c \
	  softfloat/onfint.c \
	  $(SFSRCS) $(ONFSF)
	$(PYTHON) tools/lint_c04.py --enforce-all $(BUILD)/obj

# --- C-04 on the objects that actually go to MVS (D-111) ------------------
# The lint above reports vendored collisions and passes, which is exactly
# how SoftFloat 2c got as far as Assembler XF before anyone noticed that
# eighteen of its float64_* names truncate to FLOAT64@ (VL-25).  Here
# nothing is exempt, because the MVS linkage editor exempts nothing.
#
# This compiles the 2c unit the way tools/mvs2c.py presents it to GCCMVS --
# same source, same rename prologue -- so a name that would be rejected on
# MVS is rejected here first, without a lab job.
c04mvs: $(BUILD) $(GENERATED) generated/onf2cnm.h $(SF2CSRC)
	$(PYTHON) tools/mkobjs.py $(BUILD)/obj2c \
	  $(CC) $(C2CFLAGS) $(SF2CFLAGS) $(INC) -- \
	  $(SF2CSRC) engine/src/onffp2.c engine/src/onffpc.c \
	  engine/src/onfcrc.c engine/src/onfrnd.c engine/src/onfstm.c \
	  engine/src/onfker.c engine/src/onfdec.c engine/src/onffpr.c
	$(PYTHON) tools/lint_c04.py --enforce-all $(BUILD)/obj2c

# --- TT-02: Berkeley TestFloat vectors (NR-14, and one NR-09 condition) ---
# Needs testfloat_gen, which needs a complete softfloat.a.  That library is
# built with the 8086 specialization because ARM-VFPv2-defaultNaN cannot
# build one (D-46); NaN cases are excluded and declared as VL-11.
TFDIR = third_party/TestFloat-3e/build/Win32-MinGW
SFLIBDIR = third_party/SoftFloat-3e/build/Win32-MinGW

ifeq ($(ONFPLAT),x86w)
TFGEN = $(TFDIR)/testfloat_gen.exe

# Not a prerequisite of tt02 or c2c on this platform: testfloat_gen.exe is a
# build output and therefore gitignored, so a bare checkout does not have one
# and `make testfloat` is the documented step that produces it.  Naming it as
# a prerequisite would turn a missing generator into "No rule to make target"
# instead of the clear failure run_tt02.py already gives.
TFPREREQ =

testfloat:
	cd $(SFLIBDIR) && mingw32-make
	cd $(TFDIR) && mingw32-make testfloat_gen.exe

else
# D-225: the generator is built OUT OF TREE for this platform.
#
# third_party/ ships only a Win32-MinGW build, and D-28 and D-35 commit
# third_party/ to byte-identity with the published archives, so a new build
# directory cannot be added there.  Both vendored Makefiles declare
# SOURCE_DIR, SPECIALIZE_TYPE and PLATFORM with `?=` and put -I. -- the build
# directory -- first on the include path, which is upstream's own mechanism
# for a new platform: a build directory containing nothing but a platform.h.
# tools/tfgprep.py creates those two directories under $(BUILD) and supplies
# softfloat/tfgen/platform.h; the vendored Makefiles are then run with -C
# pointed at them and their variables overridden on the command line.  No
# source list is copied out of third_party, so none can drift from upstream.
#
# SPECIALIZE_TYPE stays 8086 for the same reason as on x86 (D-46): the
# ARM-VFPv2-defaultNaN specialization cannot build a complete library, NaN
# cases are excluded, and VL-11 records that limit.  Using the same
# specialization on both platforms is also what makes the two TT-02 runs
# comparable rather than merely both green.
TFROOT = $(CURDIR)/third_party
TFSFB  = $(BUILD)/tfsf
TFTFB  = $(BUILD)/tftf
TFGEN  = $(TFTFB)/testfloat_gen.exe
TFPREREQ = $(TFGEN)

# $(abspath ...) rather than $(CURDIR)/...: BUILD may already be absolute --
# the s390x runs pass BUILD=/tmp/b390 so that object files stay off the 9p
# share -- and prefixing CURDIR onto an absolute path yields /onfly//tmp/...,
# which make reports only as "No rule to make target" at the final link.
$(TFGEN):
	$(PYTHON) tools/tfgprep.py $(TFSFB) $(TFTFB)
	$(MAKE) -C $(TFSFB) \
	  -f $(TFROOT)/SoftFloat-3e/build/Win32-MinGW/Makefile \
	  SOURCE_DIR=$(TFROOT)/SoftFloat-3e/source \
	  SPECIALIZE_TYPE=8086
	$(MAKE) -C $(TFTFB) \
	  -f $(TFROOT)/TestFloat-3e/build/Win32-MinGW/Makefile \
	  SOURCE_DIR=$(TFROOT)/TestFloat-3e/source \
	  SOFTFLOAT_DIR=$(TFROOT)/SoftFloat-3e \
	  SOFTFLOAT_LIB=$(abspath $(TFSFB))/softfloat.a \
	  testfloat_gen.exe

testfloat: $(TFGEN)
endif

# --- TT-01: the 64-bit integer self-test (NR-04, NR-14, A-05) -------------
# Level L0 of Section 8.1, and the earliest thing in the whole plan: every
# level above it assumes the compiler's 64-bit arithmetic is right.  S/370 has
# no 64-bit integer instructions, so GCCMVS must synthesise all of it, and
# assumption A-05 says so while recording itself Unverified.  Gate G1 settles
# it; this is half of that gate's exit criterion.
#
# Built from softfloat/onfint.c alone, with no SoftFloat source and no float
# layer.  Risk R-01's mitigation is that "TT-01 isolates integer bugs from
# float bugs", which only holds if TT-01 still runs when SoftFloat does not.
#
# -Wno-long-long is the one relaxation, and it is exactly NR-04's: the dialect
# is "C89 plus long long", and -pedantic otherwise rejects the second half of
# that sentence.  Everything else stays strict, so a construct GCCMVS would
# refuse still fails here first.
tt01: $(BUILD) $(IVEC)
	$(CC) $(CFLAGS) -Wno-long-long $(INC) -Isoftfloat \
	  -o $(BUILD)/tstint.exe tests/tstint.c softfloat/onfint.c
	$(PYTHON) tests/run_tt01.py $(BUILD)/tstint.exe

tt02: $(BUILD) softfloat/onfsub.c $(SF2CSRC) generated/onf2cnm.h $(TFPREREQ)
	$(CC) $(SFFLAGS) $(INC) $(SFINC) -o $(BUILD)/tstflt_soft.exe \
	  tests/tstflt.c engine/src/onffpc.c engine/src/onffps.c \
	  $(SFSRCS) $(ONFSF)
	$(CC) $(SFFLAGS) $(NATFLAGS) $(INC) -o $(BUILD)/tstflt_nat.exe \
	  tests/tstflt.c engine/src/onffpc.c engine/src/onffpn.c
	$(CC) $(C2CFLAGS) $(SF2CFLAGS) $(INC) -o $(BUILD)/tstflt_2c.exe \
	  tests/tstflt.c engine/src/onffpc.c engine/src/onffp2.c $(SF2CSRC)
	$(PYTHON) tests/run_tt02.py $(BUILD)/tstflt_soft.exe \
	  $(BUILD)/tstflt_nat.exe $(BUILD)/tstflt_2c.exe $(TFGEN)

# --- TT-01/32: the 32-bit integer self-test (D-118, NR-14) ---------------
# NR-14 requires an integer self-test for each width the platform's engine
# actually uses.  Under NR-03 the MVS engine is SoftFloat 2c and uses no
# 64-bit integer, so 32 bits is the width that matters there; the 64-bit
# TT-01 above still covers x86 and the s390x and z/OS paths.  The MVS half
# is `python tools/mvs32.py`, and it is only meaningful against this.
# TT-01/32's driver now links the suite from softfloat/onfi32.c (D-142),
# which is the same code ONFLYENG runs at startup on a 2c platform.  One
# implementation, two callers: the test and the program cannot prove
# different things.
tt0132: $(BUILD) generated/onf32v.h
	$(CC) $(CFLAGS) -Igenerated -Isoftfloat -o $(BUILD)/tst32.exe \
	  tests/tst32.c softfloat/onfi32.c
	$(BUILD)/tst32.exe | tail -1

generated/onf32v.h: tools/gen32v.py
	$(PYTHON) tools/gen32v.py

# --- TT-02's shipped table, x86 side (D-112, D-115) ----------------------
# The same TestFloat vectors that run on MVS, run here.  The MVS result is
# only meaningful against an x86 result from the identical table: a
# mismatch there with agreement here is a platform difference, which is
# what TT-02 is for.  `make tt02` still runs the full 260,376-case stream;
# this is the 4,500-vector sample MVS can hold (VL-29).
tf2: $(BUILD) generated/onf2cnm.h generated/onftfv.h
	$(CC) $(C2CFLAGS) $(SF2CINC) -Igenerated 	  -include generated/onf2cnm.h 	  -o $(BUILD)/tsttf2.exe tests/tsttf2.c $(SF2CSRC)
	$(BUILD)/tsttf2.exe | tail -1

generated/onftfv.h: tools/gentf2.py
	$(PYTHON) tools/gentf2.py --per-op 750

# --- D-106: SoftFloat 2c against TestFloat --------------------------------
# The question that decides whether NR-03's fallback is cheap or expensive.
# Every ACC-5 fingerprint was computed with 3e, so if 2c disagrees on any of
# ONFLY's six operations then every fingerprint changes.
#
# 2c is checked against TestFloat's reference rather than against 3e
# directly: two libraries agreeing with an independent oracle is a stronger
# statement than two agreeing with each other, and `tt02` runs 3e through
# the same vectors, so agreement between them follows from both passing.
#
# derive2c.py --check runs first because the configuration files under
# softfloat/c2c are generated.  A hand edit there would silently change what
# is being tested, which is the failure class D-70 exists to rule out.
# -include applies the C-04 renames (D-111) to the vendored unit without
# editing it.  They are used on x86 as well as MVS deliberately: a
# mechanism exercised only on the platform that is hard to test is a
# mechanism nobody has tested.
c2c: $(BUILD) generated/onf2cnm.h generated/onf2cv.h $(TFPREREQ)
	$(PYTHON) softfloat/derive2c.py --check
	$(PYTHON) tools/gen2cnm.py --check
	$(PYTHON) tools/gen2cv.py --check
	$(CC) $(C2CFLAGS) $(SF2CINC) -include generated/onf2cnm.h \
	  -o $(BUILD)/tstc2c.exe tests/tstc2c.c $(SF2CSRC)
	$(PYTHON) tests/run_c2c.py $(BUILD)/tstc2c.exe $(TFGEN)
	$(CC) $(C2CFLAGS) $(SF2CINC) -Igenerated \
	  -include generated/onf2cnm.h \
	  -o $(BUILD)/tst2c.exe tests/tst2c.c $(SF2CSRC)
	$(BUILD)/tst2c.exe | tail -1

generated/onf3enm.h: tools/gen3enm.py
	$(PYTHON) tools/gen3enm.py

softfloat/onfprim.c: softfloat/derive3e.py generated/onf3enm.h
	$(PYTHON) softfloat/derive3e.py

generated/onf2cnm.h: tools/gen2cnm.py
	$(PYTHON) tools/gen2cnm.py

# A complete ONFNET image as a C array (D-121, D-122).  It exists because
# tstdec and tstgld both open a FILE, and no file can reach MVS until
# Gate G2 picks a binary-transparent transport -- so the decoder, the
# integrity checks and the fingerprint had never run on a big-endian
# EBCDIC host.  Generated from the same network run_dec.py already uses.
generated/onfsynt.h: tools/gensyn.py tests/run_dec.py
	$(PYTHON) tools/gensyn.py

# The derived SoftFloat 2c configuration and library (D-106, D-123).  All
# four files come out of one script, so any of them is a valid target for
# it; softfloat.c is named because it is the one the builds compile.
$(SF2CSRC): softfloat/derive2c.py $(SF2C)/softfloat.c
	$(PYTHON) softfloat/derive2c.py

generated/onf2cv.h: tools/gen2cv.py
	$(PYTHON) tools/gen2cv.py

# --- D-104: SoftFloat's variable 64-bit shifts, x86 reference -------------
# The x86 half of the D-104 measurement.  The MVS half is
# `python tools/mvssfs.py`, which submits this same source together with the
# same two vendored SoftFloat units.  The comparison only means anything if
# the reference is regenerated rather than remembered, so it runs here.
#
# -Isoftfloat/c89 is deliberately NOT passed: this target uses the host's
# real <stdint.h>, which is what makes it a reference for an MVS build that
# has to use ONFLY's shim.  The shim is exercised by `shim` below.
#
# Every result must be 1, and tstsfs exits nonzero if any is not.
sfs: $(BUILD)
	$(CC) $(CFLAGS) -Wno-long-long -Isoftfloat $(SFINC) \
	  -o $(BUILD)/tstsfs.exe tests/tstsfs.c \
	  $(SF)/s_shiftRightJam64.c $(SF)/s_shortShiftRightJam64.c
	$(BUILD)/tstsfs.exe | tail -1

# --- NR-04: the C89 shims are exercised, not merely shipped ---------------
# The shims are only USED on a platform that lacks its own headers, so on
# x86 they would otherwise be files nobody ever compiles.  Putting
# softfloat/c89 first on the include path forces every SoftFloat
# translation unit through them, and the result must be bit-identical to
# the ordinary build: a shim that changed one rounding decision would show
# up here rather than as a one-platform fingerprint mismatch much later.
#
# `fp` is a prerequisite because cmpback.py compares against
# build/tstfp_soft.exe, which only `fp` builds; `test` names shim before
# fp, so on a fresh build directory the comparison had nothing to compare
# against (found on the first `make test` in a clean worktree, 2026-09-12).
shim: $(BUILD) softfloat/onfsub.c fp
	$(CC) $(SFFLAGS) -Isoftfloat/c89 $(INC) $(SFINC) \
	  -o $(BUILD)/tstfp_shim.exe \
	  tests/tstfp.c engine/src/onffpc.c engine/src/onffps.c \
	  engine/src/onfrnd.c $(SFSRCS) $(ONFSF)
	$(PYTHON) tests/run_fp.py $(BUILD)/tstfp_shim.exe
	$(PYTHON) tools/cmpback.py $(BUILD)/tstfp_soft.exe \
	  $(BUILD)/tstfp_shim.exe

# --- TP-01: sign and weight assignment (FR-PRP-03, SR-MOD-05) ------------
# Unit tests run on a small fixture so a failure points at one rule; two
# further tests check the mapping's vocabulary against the real MaleCNS
# data and skip cleanly when that data has not been retrieved.
#
# TP-07 joins it (D-187): emit.build_network grew an optional weight-gain
# hook for the compared truncation constructions, and the one thing that
# must never happen is for that hook to act when no caller asked for it --
# every network file and every ACC-5 fingerprint would move silently.  Its
# fixture is hand-built, so like the first half of TP-01 it needs no
# MaleCNS data and runs on a bare checkout.
#
# TP-08 joins them (D-190, D-191): the v1.1 compensating-input table's row
# selection and its rate 0 invariant.  The tie rule is the one place the C
# kernel and the Python oracle could silently disagree, and a non-zero rate 0
# row would break ACC-2 on every platform at once, so both are pinned here
# on a hand-built fixture rather than left to the integration tests.
#
# TP-09 joins them (D-355): prep/seeds.py, the TBD-06 seed-sensitivity tool,
# has to evaluate ACC-1 and ACC-3 over resampled ARRAYS, which the list-shaped
# implementations in prep/extract.py cannot do -- so two implementations of
# one criterion exist.  That is the exact condition that produced D-289, where
# --acc3-file predated D-202's amendment and printed FAIL while every rate
# ACC-3 actually tests passed.  test_seeds.py ties the array form to the
# recorded artefacts the list form produced, VL-105 and VL-98.  It reads only
# committed JSON, so it needs no network fixture and no engine build.
prep:
	$(PYTHON) tests/test_signs.py
	$(PYTHON) tests/test_gain.py
	$(PYTHON) tests/test_bias.py
	$(PYTHON) tests/test_fixt.py
	$(PYTHON) tests/test_varnt.py
	$(PYTHON) tests/test_chunk.py
	$(PYTHON) tests/test_disc.py
	$(PYTHON) tests/test_seeds.py
# D-385: the committed geometry sidecar must keep describing the
# shipped network index for index.  prep/geom.py itself needs the
# gitignored annotations feather; this does not.
	$(PYTHON) tests/test_geom.py
# D-455: the shipped network's acceptance note is prose no code reads,
# so a revert of it would be silent.  prep/extract.py's admission step
# rewrites networks.srext wholesale and would drop D-452's correction;
# this holds the manifest, the generator's own string and prep/netman.py
# to each other.  Pure Python, no connectome, under a second.
	$(PYTHON) tests/test_netman.py

# --- TE-09: ONFLYENG, verify-only mode and the run manifest ---------------
# The minimal engine level of D-78: the self-test, the FR-LOD-02 load checks,
# the NFR-OBS-01 manifest, and IR-TRN-03's PARM='VERIFY'.  No request loop --
# Section 9.2 puts that in Phase E, which depends on Phase C and Phase D.
#
# Built on both backends, because NFR-OBS-01 requires the manifest to name the
# backend and a manifest that named the wrong one would be worse than none.
#
# onflyeng.c is compiled on its own with the strict ONFLY flags and only then
# linked against the SoftFloat set, which SFFLAGS builds without -pedantic.
# Compiling them in one invocation, as the golden target does, would quietly
# relax -pedantic -Werror on ONFLY's own code as well.
# D-221 links the kernel, the PRNG, the stimulus draw and the shared request
# module into ONFLYENG, because STEP2 now simulates.  D-228 therefore also
# builds a second binary per backend with -DONF_NOREQ, the request loop
# compiled out, so that TE-09's structural argument -- `nm` proves onfrun
# absent, so it cannot have been called -- still has a binary it holds for.
# That variant is also the only build that can emit ONF905S (D-227).
ENGREQ = engine/src/onfdec.c engine/src/onfcrc.c engine/src/onffpc.c \
         engine/src/onffpr.c engine/src/onfker.c engine/src/onfrnd.c \
         engine/src/onfstm.c engine/src/onfreq.c generated/onfcom.c
ENGVFY = engine/src/onfdec.c engine/src/onfcrc.c engine/src/onffpc.c \
         engine/src/onffpr.c

eng: $(BUILD) $(GENERATED) $(IVEC) softfloat/onfsub.c $(SF2CSRC) \
     generated/onf2cnm.h
	$(CC) $(CFLAGS) $(INC) -Isoftfloat -c \
	  -o $(BUILD)/onflyeng.o engine/src/onflyeng.c
	$(CC) $(SFFLAGS) $(INC) $(SFINC) -o $(BUILD)/onflyeng_soft.exe \
	  $(BUILD)/onflyeng.o $(ENGREQ) engine/src/onffps.c \
	  softfloat/onfint.c $(SFSRCS) $(ONFSF)
	$(CC) $(CFLAGS) -DONF_NOREQ $(INC) -Isoftfloat -c \
	  -o $(BUILD)/onflyengv.o engine/src/onflyeng.c
	$(CC) $(SFFLAGS) $(INC) $(SFINC) -o $(BUILD)/onflyengv_soft.exe \
	  $(BUILD)/onflyengv.o $(ENGVFY) engine/src/onffps.c \
	  softfloat/onfint.c $(SFSRCS) $(ONFSF)
	$(PYTHON) tests/run_eng.py $(BUILD)/onflyeng_soft.exe \
	  $(BUILD)/onflyengv_soft.exe
	$(CC) $(CFLAGS) $(NATFLAGS) $(INC) -Isoftfloat -c \
	  -o $(BUILD)/onflyengn.o engine/src/onflyeng.c
	$(CC) $(SFFLAGS) $(NATFLAGS) $(INC) -o $(BUILD)/onflyeng_nat.exe \
	  $(BUILD)/onflyengn.o $(ENGREQ) engine/src/onffpn.c \
	  softfloat/onfint.c
	$(CC) $(CFLAGS) $(NATFLAGS) -DONF_NOREQ $(INC) -Isoftfloat -c \
	  -o $(BUILD)/onflyengnv.o engine/src/onflyeng.c
	$(CC) $(SFFLAGS) $(NATFLAGS) $(INC) -o $(BUILD)/onflyengv_nat.exe \
	  $(BUILD)/onflyengnv.o $(ENGVFY) engine/src/onffpn.c \
	  softfloat/onfint.c
	$(PYTHON) tests/run_eng.py $(BUILD)/onflyeng_nat.exe \
	  $(BUILD)/onflyengv_nat.exe
	$(CC) $(C2CFLAGS) $(SF2CFLAGS) $(INC) -Isoftfloat -c \
	  -o $(BUILD)/onflyeng2.o engine/src/onflyeng.c
	$(CC) $(C2CFLAGS) $(SF2CFLAGS) $(INC) -o $(BUILD)/onflyeng_2c.exe \
	  $(BUILD)/onflyeng2.o $(ENGREQ) engine/src/onffp2.c \
	  softfloat/onfi32.c $(SF2CSRC)
	$(CC) $(C2CFLAGS) $(SF2CFLAGS) -DONF_NOREQ $(INC) -Isoftfloat -c \
	  -o $(BUILD)/onflyeng2v.o engine/src/onflyeng.c
	$(CC) $(C2CFLAGS) $(SF2CFLAGS) $(INC) -o $(BUILD)/onflyengv_2c.exe \
	  $(BUILD)/onflyeng2v.o $(ENGVFY) engine/src/onffp2.c \
	  softfloat/onfi32.c $(SF2CSRC)
	$(PYTHON) tests/run_eng.py $(BUILD)/onflyeng_2c.exe \
	  $(BUILD)/onflyengv_2c.exe

# --- FR-BAT-01 STEP2 and TX-01: the request/response loop (D-221) ----------
# Drives the Section 8.4 suite through ONFREQ -> ONFLYENG -> ONFRSP on every
# backend, checks each response record against the oracle, and requires the
# three backends to produce byte-identical ONFRSP files.  D-220 puts SOFT2C
# here as well as SOFT3E and NATIVE: it is the library MVS uses and had never
# run the record path at all.
req: eng
	$(PYTHON) tests/run_req.py $(BUILD)/onflyeng_soft.exe \
	  $(BUILD)/onflyeng_nat.exe $(BUILD)/onflyeng_2c.exe
	$(PYTHON) tests/test_txcmp.py
# TU-11 (IR-STM-01..04), added by D-380.  Two guards, and they prove
# different things: the ONFRSP dataset must be byte-identical with and
# without STREAM= -- which is the ACC-5 claim, not a feature -- and the
# stream's own counts must agree with the response, which is the only check
# that can tell the real run from a plausible animation beside it.  Measured
# at about 25 s over the three backends on this host.
	$(PYTHON) tests/test_strm.py $(BUILD)/onflyeng_soft.exe \
	  $(BUILD)/onflyeng_nat.exe $(BUILD)/onflyeng_2c.exe

# --- Gate G4: ONFLYDRV through the GnuCOBOL IBM-dialect proxy (VL-02) ------
# D-152 installs GnuCOBOL on this host; D-156 keeps this target OUT of
# `test`, because a bare checkout has no cobc and must stay runnable.
# tests/run_cob.py prints a skip line and exits 0 when no cobc is found.
# The MVT COBOL half of the gate is tools/mvscob.py, on TK5.
cob: $(BUILD) $(GENERATED)
	$(PYTHON) tests/run_cob.py

# --- Phase G, first component: the EXEC CICS transaction (D-394) -----------
# D-130 puts ONFLY's transaction source in real `EXEC CICS`, verified against
# Raincode on this host.  This builds the whole chain -- the engine as a
# 64-bit shared library, the .NET LINK target, the byte-identity driver, the
# BUZZ mapset, both transactions -- and then runs P-22's V3 and V4.
#
# Deliberately OUT of `test`, by the same rule D-156 set for the GnuCOBOL
# proxy: a bare checkout has neither Raincode nor the .NET SDK and must stay
# buildable.  tools/cicsbld.py prints which piece is missing and exits 0.
#
# Depends on `eng` because V4's comparand is the batch engine's own ONFRSP:
# the claim is that the CICS path does not change the answer, and there is
# nothing to compare against without it.
cics: $(BUILD) $(GENERATED) eng
	$(PYTHON) tools/cicsbld.py $(BUILD)/cics

# --- FR-PRP-04: the full-brain runner --------------------------------------
# Built as part of the project rather than by hand, so it cannot drift from
# the engine it exercises.  Not part of `test`: a full-brain run takes
# minutes, and the engine itself is already covered by the kernel and golden
# suites.  Driven by tools/fullbrain.sh for the D-63 protocol.
runner: $(BUILD) $(GENERATED)
	$(CC) $(CFLAGS) $(NATFLAGS) $(INC) -o $(BUILD)/runnet.exe \
	  tools/runnet.c engine/src/onfdec.c engine/src/onfcrc.c \
	  engine/src/onffpc.c engine/src/onffpn.c engine/src/onfker.c \
	  engine/src/onfrnd.c engine/src/onfstm.c

# D-204: the same runner on the two soft backends, so a candidate MVS
# subcircuit can be run on every float backend this host has rather than on
# the native one alone.  ACC-2 claims "every platform and backend" and the
# v1.1 compensating table had only ever been decoded by the native build;
# these two are what let that claim be tested instead of assumed.
runners: $(BUILD) $(GENERATED) runner
	$(CC) $(SFFLAGS) $(INC) $(SFINC) -o $(BUILD)/runnet_soft.exe \
	  tools/runnet.c engine/src/onfdec.c engine/src/onfcrc.c \
	  engine/src/onffpc.c engine/src/onffps.c engine/src/onfker.c \
	  engine/src/onfrnd.c engine/src/onfstm.c $(SFSRCS) $(ONFSF)
	$(CC) $(C2CFLAGS) $(SF2CFLAGS) $(INC) -o $(BUILD)/runnet_2c.exe \
	  tools/runnet.c engine/src/onfdec.c engine/src/onfcrc.c \
	  engine/src/onffpc.c engine/src/onffp2.c engine/src/onfker.c \
	  engine/src/onfrnd.c engine/src/onfstm.c $(SF2CSRC)

# Section 8.1 runs bottom-up: "A level may start only when the level below it
# passes on the platform concerned."  So the L0 toolchain tests, TT-01 and
# TT-02, come before the L1 unit tests and everything above them.
test: lint liclint col80 c04 c04mvs sub mvsrun mvsjcc ic3270 names tt01 tt02 c2c sfs shim layout units fp kernel syn \
      decode eng req golden prep
	@echo "ONFLY: NR-05 + licence + col80 + C-04 + C-04/MVS lints, TT-01, TT-02, SoftFloat 2c vs TestFloat and its known answers, D-104 shift reference, NR-04 shims, TU-01..TU-07, kernel, the embedded-network engine path, TE-01..TE-13, the FR-BAT-01 STEP2 request loop, ACC-5 golden suite and TP-01 all passed on SOFT3E, SOFT2C and NATIVE; plus IR-NAM-01..03 over the emitted names files, and the Phase E MVS decks and recordings -- TX-01 under D-261 and ACC-5 row 6 for all nineteen Section 8.4 requests, and ACC-5 row 7 for all nineteen Section 8.4 requests JCC built and ran; plus the streamed fixture digests, D-202's ACC-3 exclusion rule, and TP-09 holding the TBD-06 seed tool to the recorded ACC-1 and ACC-3 verdicts; plus the 3270 transaction path off-lab -- the script protocol, the region and build decks, and the three facts VL-129 paid for"

# D-249.  `summarise()` in tools/mvsub.py turns a few thousand lines of
# JES2 output into the handful a person reads -- and, through the gate
# tooling, into the lines a gate record keeps.  A bare `ABEND` in its
# alternation reported the SYS2.JCLLIB member names JOBABEND and
# ABEND0C1 as abends during Gate G0.  Pure Python; nothing to build.
sub:
	$(PYTHON) tests/run_sub.py

# Phase E slice 1 (D-255, D-258).  tools/mvsrun.py is submitted to TK5,
# so almost nothing in it can be tested here -- but everything that
# would WASTE a mainframe run can be: column limits, delimiter
# collisions, C-04 member names, the link order, IR-JCL-01's DD names
# on the GO step, and the assertion that the control cards pack to
# exactly the bytes data/phase-d/x86w/req-srext.bin holds, which is
# what bounds the risk the owner accepted in D-260.  It also pins the
# two additive changes this slice made -- mvsbld.build(post=...) and
# the keyword arguments on mvscob.deck() -- against altering any
# existing caller's deck.  Pure Python; no cobc, no Hercules.
#
# D-312 adds tests/test_trust.py beside it: ACC-6's external-clock guard.
# Its failure mode is silence -- an unreadable Hercules process would let
# an unguarded implementation certify nothing while appearing to certify
# -- so what is pinned is that it REFUSES, on a sleep and on a clock it
# cannot read.  Synthetic numbers only; no Hercules, milliseconds.
mvsrun:
	$(PYTHON) tests/run_mvsrun.py
	$(PYTHON) tests/test_trust.py

# Phase E slice 4 (D-281 ... D-286).  ACC-5's row 7 is the same platform
# and backend as row 6 through a DIFFERENT compiler, and it is only
# evidence if it links the same thirteen translation units in the same
# order and reads the same network.  Both are properties of a deck, so
# both are checked here rather than discovered after an 8,390-card
# submission.  It also pins D-286's consequence: if row 6's ONFNET DD
# ever drifted back to the card reader, the two rows would differ in
# transport as well as compiler and nothing would say so.  Pure Python;
# no Hercules.
#
# D-458 ... D-465 widened it to BOTH halves of the suite.  The tool used
# to refuse --net, and the refusal named what it guarded: the wrong
# network under the right job name.  That refusal is gone, so what
# stands in its place is here -- the deck for each network asserted to
# name its own job, its own request and response datasets and its own
# ONFNET, mvsjcc.check_names() shown to REFUSE a crossed-over one, and
# BOTH recordings required to be present and to match the Section 8.4
# fingerprints.  Requiring both is the point: a test that skipped a
# missing recording would let the `path` half rot out of the repository
# exactly as silently as it was absent before D-458 (D-464).
mvsjcc:
	$(PYTHON) tests/run_mvsjcc.py

# Phase G slice 1 (D-424 ... D-428, VL-129).  tools/ic3270.py drives a
# real terminal emulator against a real mainframe and tools/mvsicom.py
# starts and stops a real region, so what they DO can only be judged on
# TK5.  What is judged here is the script protocol, the region deck's
# column limits, and the three facts VL-129 paid for and that look like
# details: the verb must be comma-terminated, the logon is APPLID= and
# not APPLID(...), and a device must be named because TK5 gives 00C0 to
# TSO.  Each of those, if lost, costs an hour on a running mainframe
# and gives a symptom that points somewhere else.  Pure Python; no
# Hercules, no emulator, no network.
ic3270:
	$(PYTHON) tests/run_ic3270.py

# D-267 ... D-269.  FR-PRP-07 has always required the pipeline to emit
# a names file (IR-NAM) and none existed until 2026-09-15, which is
# why FR-BAT-04's report could not be written: IR-COM-06 forbids the
# response from carrying names, so ONFLYDRV has to map the numeric
# identifier through ONFNAM.
#
# The test reads the COMMITTED files rather than regenerating them.
# Regenerating needs pandas, pyarrow and a 14.5 MB gitignored feather
# (tools/fixtures.py --malecns annotations); a bare checkout must
# still be able to prove that what it holds is well formed.  The one
# case that does regenerate prints a skip line and passes when those
# prerequisites are absent, the pattern D-233 set.
names:
	$(PYTHON) tests/run_names.py

# D-249.  data/networks/*.bin is gitignored (322 MB), so a fresh clone or
# worktree starts without it and the first symptom is ONF103E raised four
# frames deep inside run_req.  This links the networks in from the main
# checkout or a sibling worktree, verifying every candidate against
# MANIFEST.json -- bytes, CRC-32 and SHA-256 -- before linking it and
# again afterwards.
#
# Deliberately NOT a prerequisite of `test`: it reaches outside this
# checkout, and a test target must not do that on its own.  Run it when
# `test` complains, or `fixtures-check` to diagnose without changing
# anything.
# D-388, D-389: the two recorded clips of the Phase G live view, both from
# real engine streams.  `short` is the explainer -- 60 ms at K=5, where the
# arrival, the propagation and MN9 crossing threshold at 25.8 ms are all
# visible.  `standard` is the D-73 duration at the D-376 chunk size, which is
# what says the explainer is a real standard request and not a shrunken one.
# Neither is built by `make test`: they need an engine and take about 20 s.
clips: eng
	$(PYTHON) tools/liveview.py --engine $(BUILD)/onflyeng_nat.exe 	  --rate 40 --ms 60 --k 5 --fps 12 	  --save docs/media/onfly-live-short.gif
	$(PYTHON) tools/liveview.py --engine $(BUILD)/onflyeng_nat.exe 	  --rate 40 --ms 1000 --k 50 --every 2 --fps 10 	  --save docs/media/onfly-live-standard.gif

fixtures:
	$(PYTHON) tools/fixtures.py

fixtures-check:
	$(PYTHON) tools/fixtures.py --check

clean:
	$(PYTHON) -c "import shutil,os; shutil.rmtree('$(BUILD)', ignore_errors=True)"
