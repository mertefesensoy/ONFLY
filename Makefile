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

# D-30: this host's gcc is 32-bit mingw32, where x87 extended precision is the
# default.  NR-09 forbids it, so the native backend is built with SSE2 forced,
# FMA contraction off and no fast-math.  A native build without these is not an
# admitted backend.
NATFLAGS = -msse2 -mfpmath=sse -ffp-contract=off -DONF_FP_NATIVE -DONF_FP_LITTLE

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

GENERATED = generated/onfcom.h generated/onfcom.c generated/ONFCOM.cpy \
            generated/onfcom_py.py generated/onfnhd.h

# TT-01's known-answer table (D-79).  Separate from $(GENERATED) because that
# list shares a single rule whose recipe is layout/generate.py; this one comes
# from tools/genint.py instead.
IVEC = generated/onfivec.h

.PHONY: all test generate lint liclint clean units layout fp kernel decode golden syn tt01 tt0132 tt02 c2c tf2 sfs shim testfloat c04 c04mvs col80 prep runner eng

all: test

# --- Generated artifacts (IR-COM-01, D-18) ---------------------------------
# Never edit anything under generated/ or softfloat/onfsub.c by hand.
generate:
	$(PYTHON) layout/generate.py
	$(PYTHON) softfloat/derive.py
	$(PYTHON) tools/genint.py

$(GENERATED): layout/master.py layout/generate.py
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
	$(PYTHON) tools/lint_col80.py engine generated softfloat tests tools

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
	  tests/tstgld.c engine/src/onfdec.c engine/src/onfcrc.c \
	  engine/src/onffpc.c engine/src/onffps.c engine/src/onfker.c \
	  engine/src/onfrnd.c engine/src/onfstm.c engine/src/onffpr.c \
	  $(SFSRCS) $(ONFSF)
	$(PYTHON) tests/run_gld.py $(BUILD)/tstgld_soft.exe
	$(CC) $(SFFLAGS) $(NATFLAGS) $(INC) -o $(BUILD)/tstgld_nat.exe \
	  tests/tstgld.c engine/src/onfdec.c engine/src/onfcrc.c \
	  engine/src/onffpc.c engine/src/onffpn.c engine/src/onfker.c \
	  engine/src/onfrnd.c engine/src/onfstm.c engine/src/onffpr.c
	$(PYTHON) tests/run_gld.py $(BUILD)/tstgld_nat.exe
	$(CC) $(C2CFLAGS) $(SF2CFLAGS) $(INC) -o $(BUILD)/tstgld_2c.exe  \
	  tests/tstgld.c engine/src/onfdec.c engine/src/onfcrc.c  \
	  engine/src/onffpc.c engine/src/onffp2.c engine/src/onfker.c  \
	  engine/src/onfrnd.c engine/src/onfstm.c engine/src/onffpr.c  \
	  $(SF2CSRC)
	$(PYTHON) tests/run_gld.py $(BUILD)/tstgld_2c.exe
	$(PYTHON) tools/cmpgld.py $(BUILD)/tstgld_soft.exe  \
	  $(BUILD)/tstgld_nat.exe $(BUILD)/tstgld_2c.exe

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
TFGEN = $(TFDIR)/testfloat_gen.exe

testfloat:
	cd $(SFLIBDIR) && mingw32-make
	cd $(TFDIR) && mingw32-make testfloat_gen.exe

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

tt02: $(BUILD) softfloat/onfsub.c $(SF2CSRC) generated/onf2cnm.h
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
c2c: $(BUILD) generated/onf2cnm.h generated/onf2cv.h
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
shim: $(BUILD) softfloat/onfsub.c
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
prep:
	$(PYTHON) tests/test_signs.py

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
eng: $(BUILD) $(GENERATED) $(IVEC) softfloat/onfsub.c
	$(CC) $(CFLAGS) $(INC) -Isoftfloat -c \
	  -o $(BUILD)/onflyeng.o engine/src/onflyeng.c
	$(CC) $(SFFLAGS) $(INC) $(SFINC) -o $(BUILD)/onflyeng_soft.exe \
	  $(BUILD)/onflyeng.o engine/src/onfdec.c engine/src/onfcrc.c \
	  engine/src/onffpc.c engine/src/onffps.c engine/src/onffpr.c \
	  softfloat/onfint.c $(SFSRCS) $(ONFSF)
	$(PYTHON) tests/run_eng.py $(BUILD)/onflyeng_soft.exe
	$(CC) $(CFLAGS) $(NATFLAGS) $(INC) -Isoftfloat -c \
	  -o $(BUILD)/onflyengn.o engine/src/onflyeng.c
	$(CC) $(SFFLAGS) $(NATFLAGS) $(INC) -o $(BUILD)/onflyeng_nat.exe \
	  $(BUILD)/onflyengn.o engine/src/onfdec.c engine/src/onfcrc.c \
	  engine/src/onffpc.c engine/src/onffpn.c engine/src/onffpr.c \
	  softfloat/onfint.c
	$(PYTHON) tests/run_eng.py $(BUILD)/onflyeng_nat.exe

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

# Section 8.1 runs bottom-up: "A level may start only when the level below it
# passes on the platform concerned."  So the L0 toolchain tests, TT-01 and
# TT-02, come before the L1 unit tests and everything above them.
test: lint liclint col80 c04 c04mvs tt01 tt02 c2c sfs shim layout units fp kernel syn \
      decode eng golden prep
	@echo "ONFLY: NR-05 + licence + col80 + C-04 + C-04/MVS lints, TT-01, TT-02, SoftFloat 2c vs TestFloat and its known answers, D-104 shift reference, NR-04 shims, TU-01..TU-07, kernel, the embedded-network engine path, TE-01..TE-09, ACC-5 golden suite and TP-01 all passed on SOFT3E, SOFT2C and NATIVE"

clean:
	$(PYTHON) -c "import shutil,os; shutil.rmtree('$(BUILD)', ignore_errors=True)"
