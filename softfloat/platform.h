/*
 * platform.h - ONFLY's build configuration for Berkeley SoftFloat 3e.
 *
 * SoftFloat's designed customisation point is a per-build platform.h; this is
 * ONFLY's, so nothing under third_party/ is edited and the vendored tree stays
 * byte-identical to the SHA-256 digests recorded in decision D-28.
 *
 * Three things are configured here, each for a stated requirement:
 *
 *  1. SOFTFLOAT_FAST_INT64 is deliberately NOT defined (NR-02).  That selects
 *     the "not FAST_INT64" build, which minimises 64-bit integer use -- the
 *     point being that S/370 has no 64-bit integers and GCCMVS must synthesise
 *     them (A-05, risk R-01).
 *
 *  2. softfloat_raiseFlags is neutralised (D-34).  SoftFloat keeps three plain
 *     mutable globals -- THREAD_LOCAL is #defined to nothing in softfloat.h --
 *     and NFR-MNT-02 forbids writable static data so the engine is reentrant
 *     for the CICS path (Section 3.7, CONCURRENCY(REQUIRED)).  NR-10 already
 *     forbids depending on exception flags, so discarding them removes state
 *     ONFLY must never read anyway.  This macro removes every raiseFlags call
 *     in the binary64 path; the one remaining direct write lives in
 *     s_roundPackToF64.c, which D-35 replaces with softfloat/onfrpk.c.
 *
 *  3. No compiler builtins and no opts-GCC.h.  Upstream's Win32-MinGW config
 *     sets SOFTFLOAT_BUILTIN_CLZ and pulls in GCC-specific options.  ONFLY does
 *     not, because one configuration has to serve GCCMVS and JCC as well
 *     (NFR-PRT-01, D-03), and a count-leading-zeros builtin is not something
 *     either can be assumed to provide.
 */
#ifndef ONFLY_SOFTFLOAT_PLATFORM_H
#define ONFLY_SOFTFLOAT_PLATFORM_H

/* ---------------------------------------------------------------------------
 * Byte order.  SoftFloat needs exactly one of these defined.  The detection
 * mirrors engine/include/onfplat.h so the two cannot disagree.
 * ------------------------------------------------------------------------ */
#if defined(__MVS__) || defined(__CMS__) || defined(__s390x__) || defined(__s390__)
#define BIGENDIAN 1
#else
#define LITTLEENDIAN 1
#endif

/* ---------------------------------------------------------------------------
 * Inline policy.  C89 has no `inline`, and GCCMVS is an old GCC whose
 * `extern inline` follows GNU rather than C99 semantics.  `static` is the one
 * spelling that behaves identically everywhere ONFLY builds.  The cost is a
 * private copy of each small primitive per translation unit, which the
 * optimiser removes.
 * ------------------------------------------------------------------------ */
#define INLINE static

/* ---------------------------------------------------------------------------
 * D-34: discarding exception flags.
 *
 * Note for anyone tempted to do this with a macro here: you cannot.
 * softfloat.h declares `void softfloat_raiseFlags( uint_fast8_t );`, and a
 * function-like macro of the same name mangles that declaration into a syntax
 * error.  The same trap applies to softfloat_roundingMode and
 * softfloat_exceptionFlags, which softfloat.h declares as extern variables.
 *
 * The flags are discarded at link time instead: softfloat/onfflag.c supplies a
 * no-op softfloat_raiseFlags and the specialization's own
 * softfloat_raiseFlags.c is simply not compiled.  A no-op function holds no
 * state, which is the whole point (NFR-MNT-02).
 * ------------------------------------------------------------------------ */

#endif /* ONFLY_SOFTFLOAT_PLATFORM_H */
