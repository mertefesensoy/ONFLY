/*
 * platform.h - ONFLY build configuration for the out-of-tree TestFloat
 * generator and the stock SoftFloat library it links against (D-225).
 *
 * ------------------------------------------------------------------------
 * What this file is for, and what it is NOT
 * ------------------------------------------------------------------------
 * NR-14 requires the TestFloat vector suite to pass on every platform, but
 * third_party/ ships only a Win32-MinGW build of testfloat_gen, and D-28 and
 * D-35 commit third_party/ to byte-identity with the published archives, so
 * a new build directory cannot be added there.
 *
 * Both vendored Makefiles declare SOURCE_DIR, SPECIALIZE_TYPE and PLATFORM
 * with `?=` and place -I. -- the build directory -- first on the include
 * path.  That is upstream's own mechanism for supporting a new platform: a
 * build directory containing nothing but a platform.h.  ONFLY supplies that
 * directory here, outside third_party/, and drives the vendored Makefiles
 * from it.  No source list is copied, so none can drift.
 *
 * This is NOT softfloat/platform.h.  That file configures the SoftFloat
 * library ONFLY *ships* -- flags discarded (D-34), INLINE forced to static
 * for GCCMVS and JCC (NFR-PRT-01), no compiler builtins.  This one
 * configures the stock library that acts as TestFloat's REFERENCE.  A
 * reference that had been modified to match the implementation under test
 * would prove nothing, so the two must stay separate and must not be
 * merged later for tidiness.
 *
 * SOFTFLOAT_BUILTIN_CLZ and opts-GCC.h are omitted deliberately, matching
 * softfloat/platform.h's reasoning: one configuration has to serve every
 * compiler ONFLY builds under, and neither is universally available.  They
 * are an optimisation only and change no result.
 */
#ifndef ONFLY_TFGEN_PLATFORM_H
#define ONFLY_TFGEN_PLATFORM_H

/* ---------------------------------------------------------------------------
 * Byte order.  SoftFloat and TestFloat each need exactly one of these.  The
 * detection mirrors engine/include/onfplat.h and softfloat/platform.h so that
 * the three cannot disagree -- a reference library built little-endian on a
 * big-endian host would fail in ways that look like arithmetic bugs.
 * ------------------------------------------------------------------------ */
#if defined(__MVS__) || defined(__CMS__) \
 || defined(__s390x__) || defined(__s390__)
#define BIGENDIAN 1
#else
#define LITTLEENDIAN 1
#endif

/* ---------------------------------------------------------------------------
 * Inline policy.  Upstream's own spelling, kept as upstream wrote it: this
 * code is the reference, so it is configured the way its author intended
 * rather than the way ONFLY's shipped copy is.
 * ------------------------------------------------------------------------ */
#ifdef __GNUC_STDC_INLINE__
#define INLINE inline
#else
#define INLINE extern inline
#endif

#endif /* ONFLY_TFGEN_PLATFORM_H */
