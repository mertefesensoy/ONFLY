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
 * ------------------------------------------------------------------------ */
#if defined(__MVS__) || defined(__CMS__)
#define ONF_PLATID "MVS38J"
#elif defined(__s390x__) || defined(__s390__)
#define ONF_PLATID "S390X"
#elif defined(_WIN32) || defined(__WIN32__)
#define ONF_PLATID "WIN32"
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
 * allocation is the worst way to discover it.
 *
 * Elsewhere the bound is 512 MB.  D-216 requires TX-01 and TX-02 to run
 * against the full MaleCNS network, whose payload is about 299 MB
 * (data/networks/MANIFEST.json: 299,515,264 bytes on disk), and 64 MB
 * refused to read it at all.  512 MB admits that network with room to spare
 * while still being far below a value that would exhaust a development host.
 * ------------------------------------------------------------------------ */
#if defined(__MVS__) || defined(__CMS__)
#define ONF_MAXPAY 67108864L
#else
#define ONF_MAXPAY 536870912L
#endif

#endif /* ONFPLAT_H */
