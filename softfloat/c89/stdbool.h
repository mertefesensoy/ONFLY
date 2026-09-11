/*
 * stdbool.h - ONFLY's C89 shim for SoftFloat (NR-04, D-98, D-104).
 *
 * PDPCLIB supplies no <stdbool.h>; measured on TK5 on 2026-09-11,
 * `#include <stdbool.h>` ends in "stdbool.h: An error has occurred".
 * SoftFloat uses bool 617 times, true 24 and false 70, all as plain flags.
 *
 * WHY int AND NOT unsigned char
 * -----------------------------
 * C99's _Bool normalises any nonzero value to 1 on assignment.  A typedef
 * cannot do that, so `bool b = 2;` stores 2 here and 1 under a real
 * <stdbool.h>.  That difference is invisible to SoftFloat, which only ever
 * assigns the result of a comparison or the literals below, and only ever
 * tests for truth -- never compares two bools for equality, and never
 * stores one into a float payload.  int is chosen over a narrower type
 * because every such value in SoftFloat comes from a comparison, whose type
 * in C is already int, so no conversion happens at all.
 *
 * The assumption is checked rather than asserted: building the x86
 * SoftFloat suite with -Isoftfloat/c89 puts every translation unit through
 * this header, and TT-02 and the fp vectors must pass unchanged.
 */
#ifndef ONFLY_C89_STDBOOL_H
#define ONFLY_C89_STDBOOL_H

typedef int bool;

#define true    1
#define false   0

#define __bool_true_false_are_defined 1

#endif /* ONFLY_C89_STDBOOL_H */
