/*
 * onfplat.h - ONFLY platform configuration header.
 *
 * NFR-PRT-01: one engine source builds on every platform and this is the ONLY
 * header permitted to differ between platforms.  Everything here is either a
 * fixed-width integer typedef or a compile-time check on one.
 *
 * C-06: PDPCLIB is strictly C89 and ships no <stdint.h> or <stdbool.h>, so the
 * widths below are established by the project rather than imported.  NR-04
 * confines 64-bit integer types to SoftFloat and the float layer; engine logic
 * uses 32-bit integers only.
 *
 * NR-05: no float or double appears anywhere in the engine or the soft float
 * layer, and no floating-point literal appears in any of it.  Binary64 values
 * are carried as opaque bit patterns through the onf_fp API.
 */
#ifndef ONFPLAT_H
#define ONFPLAT_H

/* ------------------------------------------------------------------------
 * Integer types.
 *
 * C89 guarantees short >= 16 bits and long >= 32 bits, but says nothing exact.
 * The typedefs below state the project's intent; the assertions immediately
 * after them turn a wrong guess on a new platform into a compile error rather
 * than a wrong answer at run time (NR-11, TU-01).
 * ------------------------------------------------------------------------ */
typedef signed char    onf_i8;
typedef unsigned char  onf_u8;
typedef short          onf_i16;
typedef unsigned short onf_u16;
typedef int            onf_i32;
typedef unsigned int   onf_u32;

/* ------------------------------------------------------------------------
 * Compile-time width checks (NR-11).
 *
 * A negative array dimension is a constraint violation in C89, so every
 * conforming compiler must diagnose it.  This is the static-assert idiom
 * available before C11.  Message ONF904S covers the run-time counterpart for
 * platforms whose compiler somehow accepts these.
 * ------------------------------------------------------------------------ */
typedef char onf_assert_u8 [(sizeof(onf_u8)  == 1) ? 1 : -1];
typedef char onf_assert_i16[(sizeof(onf_i16) == 2) ? 1 : -1];
typedef char onf_assert_u16[(sizeof(onf_u16) == 2) ? 1 : -1];
typedef char onf_assert_i32[(sizeof(onf_i32) == 4) ? 1 : -1];
typedef char onf_assert_u32[(sizeof(onf_u32) == 4) ? 1 : -1];

/* CHAR_BIT is 8 on every ONFLY target.  Stated as a check rather than an
   assumption: the byte-shift decoders in generated/onfcom.c and the CRC
   depend on it. */
typedef char onf_assert_cbit[((unsigned char)0xFF == 255) ? 1 : -1];

/* ------------------------------------------------------------------------
 * Two's complement check.
 *
 * onfg32/onfg16 avoid signed overflow by construction (NR-11), but the engine
 * still assumes the platform represents negatives in two's complement, which
 * every ONFLY target does.  -1 as unsigned must be all ones.
 * ------------------------------------------------------------------------ */
typedef char onf_assert_twoc[(((onf_u32)-1) == 0xFFFFFFFFUL) ? 1 : -1];

/* ------------------------------------------------------------------------
 * Platform identification for the run manifest (NFR-OBS-01).
 *
 * ONF_PLATID is reported to SYSPRINT so that every recorded result names the
 * platform it actually ran on.  Keep it to 8 characters or fewer.
 *
 * ONF_ISMVS is set in exactly the branches that name MVS38J, and the two
 * machine-dependent sizes below key on it rather than on macros of their own
 * (D-572).  Before that, ONF_MAXPAY tested __MVS__ and __CMS__ alone, so a
 * JCC build, which predefines neither (D-291), printed PLATFORM MVS38J and
 * used a development host's bound.  One test, made once, cannot disagree
 * with itself.  CMS has shared the MVS branch since D-147; no ONFLY build has
 * targeted it.
 * ------------------------------------------------------------------------ */
#if defined(__MVS__) || defined(__CMS__)
#define ONF_PLATID "MVS38J"
#define ONF_ISMVS 1
#elif defined(__s390x__) || defined(__s390__)
#define ONF_PLATID "S390X"
#elif defined(_WIN32) || defined(__WIN32__)
#define ONF_PLATID "WIN32"
#elif defined(JCC)
/*
 * JCC (D-291).  Probed on TK5: it predefines no platform macro at all --
 * not __MVS__, not __370__, not __EBCDIC__ -- so the platform has to be
 * inferred from the compiler.
 *
 * That inference is sound HERE and nowhere in general: JCC is a
 * cross-compiler, and this branch is true only because the one target
 * ONFLY ever builds with it is MVS 3.8j on TK5 (A-04, Section 8.3
 * row 7).  Point JCC at another target and this line would lie.  It
 * follows the three branches above, which key on real platform macros,
 * so that any of those platforms is matched by its own macro first.
 */
#define ONF_PLATID "MVS38J"
#define ONF_ISMVS 1
#elif defined(__linux__) && defined(__x86_64__)
/*
 * Linux on x86-64 (P-41 E4, D-550), built with ONFPLAT=x86l.  Without
 * this branch the manifest printed UNKNOWN there, the D-291 failure.
 * It is placed after JCC's branch so that the chain every existing
 * target reads is unchanged: MVS, JCC, s390x and the x86w host all
 * resolve before reaching it, and JCC defines no __linux__.
 */
#define ONF_PLATID "X86LINUX"
#else
#define ONF_PLATID "UNKNOWN"
#endif

/* ------------------------------------------------------------------------
 * Largest payload ONFLYENG will allocate for, in bytes (D-147, D-231).
 *
 * This is a SANITY bound, not the memory limit.  The declared payload length
 * is read from a header FR-LOD-02 has not yet validated, so it cannot be
 * handed to malloc unchecked; FR-LOD-04's check against the configured
 * region runs afterwards and is what actually governs.
 *
 * It lives here, and not in engine/src/onflyeng.c, because it is the one
 * quantity in the engine whose right value genuinely depends on the machine
 * -- and NFR-PRT-01 makes this header the only file permitted to differ
 * between platforms.  A #if in the engine source would have forked it.
 *
 * MVS and CMS keep D-147's 64 MB unchanged.  There the guard is real: C-01
 * gives the region single-digit megabytes (TBD-14 measured 8M on TK5), so a
 * declared length of any size is a transport accident and an unchecked
 * allocation is the worst way to discover it.  Under JCC too since D-572:
 * until then this tested __MVS__ and __CMS__, which JCC does not define.
 *
 * Elsewhere the bound is 512 MB.  D-216 requires TX-01 and TX-02 to run
 * against the full MaleCNS network, whose payload is about 299 MB
 * (data/networks/MANIFEST.json: 299,515,264 bytes on disk), and 64 MB
 * refused to read it at all.  512 MB admits that network with room to spare
 * while still being far below a value that would exhaust a development host.
 * ------------------------------------------------------------------------ */
#ifdef ONF_ISMVS
#define ONF_MAXPAY 67108864L
#else
#define ONF_MAXPAY 536870912L
#endif

/* ------------------------------------------------------------------------
 * FR-LOD-04's configured limit, in bytes (D-567, D-568).
 *
 * ONFLYENG refuses with ONF105E, before allocating, a network whose decoded
 * form and simulation state need more than this; onfdec computes the need
 * from the header counts.  0 means no limit.
 *
 * On MVS 3.8j it is 8M, TBD-14's region (D-116), which is also the REGION=
 * every job that runs ONFLYENG asks for (tools/mvsbld.py).  It is what a
 * job may ask for, not what a program can obtain, so a network just under
 * it can still fail when it is allocated; the two networks TK5 runs need
 * 255,688 B (srext) and 1,104,340 B (path).
 *
 * Elsewhere there is none: D-216 decodes the full MaleCNS network on x86-64
 * and s390x, whose need is 330,443,656 B, and NFR-MEM-01 is a TK5
 * requirement.  The 0 is spelled as the literal it replaced, so a build
 * with no limit preprocesses to the text it did before.
 *
 * A build may set it with -DONF_MEMLIM=n.  That is how TE-08 runs through
 * the whole program: the Makefile's eng target builds ONFLYENG at the two
 * limits tests/run_dec.py's TE-08 cases name.  tests/run_plim.py checks
 * this block on every platform.
 * ------------------------------------------------------------------------ */
#ifndef ONF_MEMLIM
#ifdef ONF_ISMVS
#define ONF_MEMLIM 8388608L
#else
#define ONF_MEMLIM 0
#endif
#endif

#endif /* ONFPLAT_H */
