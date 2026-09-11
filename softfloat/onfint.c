/*
 * onfint.c - TT-01, the 64-bit integer known-answer self-test (NR-04, NR-14).
 *
 * See onfint.h for the threat model.  This file is about one problem: how to
 * check a compiler's 64-bit arithmetic using only that same compiler's 64-bit
 * arithmetic, without the check quietly agreeing with the bug.
 *
 * ------------------------------------------------------------------------
 * Construction and extraction use different operations on purpose
 * ------------------------------------------------------------------------
 * Every operand and expectation in generated/onfivec.h is a pair of 32-bit
 * halves, so the table itself needs no 64-bit literal.  Turning a pair into a
 * 64-bit value, and a 64-bit value back into a pair, are themselves 64-bit
 * operations -- the very things under test.  If both used shifts, a compiler
 * whose 64-bit shift were wrong could build wrong operands, extract them with
 * the same wrong shift, and agree with itself.
 *
 * So the three paths deliberately disagree about which instruction to lean on:
 *
 *   building a value       multiply by 2**32, then add the low half
 *   extracting the high    shift right by 32
 *   extracting it again    divide by 2**32
 *
 * A vector passes only when the shift path and the divide path produce the
 * same high half and that half matches the table.  For the two extractions to
 * conspire, a compiler's synthesized shift and its synthesized divide would
 * have to be wrong in exactly matching ways -- and those are the two hardest,
 * least alike routines in the whole of 64-bit synthesis.
 *
 * 2**32 itself is built without a shift, a multiply, or a 64-bit literal: it
 * is 0xFFFFFFFF widened and incremented.
 *
 * ------------------------------------------------------------------------
 * C89 and PDPCLIB
 * ------------------------------------------------------------------------
 * `long long` is the single extension NR-04 permits over C89, and this file
 * uses nothing else: no LL suffix, no <stdint.h>, no <limits.h>, no declared
 * value wider than 32 bits anywhere in the source text.  Declarations precede
 * statements in every block, as C89 requires.
 */
#include "onfint.h"
#include "onfivec.h"

/*
 * The one 64-bit type in this file.  NR-04 allows `long long` as provided by
 * each compiler; onfplat.h deliberately does not typedef a 64-bit integer,
 * because doing so there would invite engine logic to use one.
 */
typedef unsigned long long onfi_u64;
typedef long long onfi_i64;

/*
 * 2**32, built from a 32-bit constant by widening and adding one.
 *
 * Not a shift and not a multiply, so the two extraction paths below both rest
 * on something simpler than either of them.  Returned by a function rather
 * than held in a static, because NFR-MNT-02 forbids writable static data and
 * the engine links this file.
 */
static onfi_u64 onfi2p32(void)
{
    onfi_u64 v;

    v = (onfi_u64)0xFFFFFFFFU;
    v = v + (onfi_u64)1U;
    return v;
}

/* Assemble a 64-bit value from its halves, using multiply rather than shift. */
static onfi_u64 onfimk(onf_u32 hi, onf_u32 lo)
{
    onfi_u64 v;

    v = (onfi_u64)hi;
    v = v * onfi2p32();
    v = v + (onfi_u64)lo;
    return v;
}

/* The low 32 bits.  Masking only; no shift, no division. */
static onf_u32 onfilo(onfi_u64 v)
{
    return (onf_u32)(v & (onfi_u64)0xFFFFFFFFU);
}

/* The high 32 bits by shifting. */
static onf_u32 onfihs(onfi_u64 v)
{
    return (onf_u32)((v >> 32) & (onfi_u64)0xFFFFFFFFU);
}

/* The high 32 bits by dividing.  The independent second opinion. */
static onf_u32 onfihd(onfi_u64 v)
{
    return (onf_u32)((v / onfi2p32()) & (onfi_u64)0xFFFFFFFFU);
}

/*
 * Every relational operator, packed into one word.
 *
 * All six are evaluated rather than three plus their negations: a compiler
 * that synthesizes "<" correctly and ">=" as a wrong negation of it is a real
 * failure mode, and checking only half the operators would miss it.
 */
static onf_u32 onficmu(onfi_u64 a, onfi_u64 b)
{
    onf_u32 r;

    r = 0U;
    if (a <  b) { r |= ONFI_CMP_LT; }
    if (a <= b) { r |= ONFI_CMP_LE; }
    if (a == b) { r |= ONFI_CMP_EQ; }
    if (a >  b) { r |= ONFI_CMP_GT; }
    if (a >= b) { r |= ONFI_CMP_GE; }
    if (a != b) { r |= ONFI_CMP_NE; }
    return r;
}

static onf_u32 onficms(onfi_i64 a, onfi_i64 b)
{
    onf_u32 r;

    r = 0U;
    if (a <  b) { r |= ONFI_CMP_LT; }
    if (a <= b) { r |= ONFI_CMP_LE; }
    if (a == b) { r |= ONFI_CMP_EQ; }
    if (a >  b) { r |= ONFI_CMP_GT; }
    if (a >= b) { r |= ONFI_CMP_GE; }
    if (a != b) { r |= ONFI_CMP_NE; }
    return r;
}

const char *onfignm(int op)
{
    if (op < 0 || op >= ONFI_NOPS) {
        return "?";
    }
    return onfvgrp[op].name;
}

int onfignc(int op)
{
    if (op < 0 || op >= ONFI_NOPS) {
        return 0;
    }
    return (int)onfvgrp[op].count;
}

int onfirun(int op, int idx, onf_u32 *rhi, onf_u32 *rlo)
{
    const struct onfiv *v;
    onfi_u64 a;
    onfi_u64 b;
    onfi_u64 r;
    onfi_i64 sa;
    onfi_i64 sb;
    onf_u32 hs;
    onf_u32 hd;
    int iscmp;

    if (op < 0 || op >= ONFI_NOPS) {
        return ONFI_RANGE;
    }
    if (idx < 0 || (onf_u32)idx >= onfvgrp[op].count) {
        return ONFI_RANGE;
    }

    v = &onfvgrp[op].vec[idx];
    a = onfimk(v->ahi, v->alo);
    b = onfimk(v->bhi, v->blo);
    r = (onfi_u64)0U;
    iscmp = 0;

    switch (op) {
    case ONFI_OP_MUL:
        r = a * b;
        break;
    case ONFI_OP_DIV:
        r = a / b;
        break;
    case ONFI_OP_MOD:
        r = a % b;
        break;
    case ONFI_OP_SHL:
        /* NR-11: the value is unsigned and the generator holds every count
           in 0..63, so no shift here is undefined or on a negative value. */
        r = a << v->blo;
        break;
    case ONFI_OP_SHR:
        r = a >> v->blo;
        break;
    case ONFI_OP_ADD:
        r = a + b;
        break;
    case ONFI_OP_SUB:
        r = a - b;
        break;
    case ONFI_OP_CMPU:
        iscmp = 1;
        r = (onfi_u64)onficmu(a, b);
        break;
    case ONFI_OP_CMPS:
        iscmp = 1;
        sa = (onfi_i64)a;
        sb = (onfi_i64)b;
        /* C89 leaves the unsigned-to-signed conversion of a value above the
           signed maximum implementation-defined rather than undefined.  Every
           ONFLY target is two's complement, so the round trip back must be
           exact; checking it turns that assumption into a tested condition
           instead of a silent one. */
        if ((onfi_u64)sa != a || (onfi_u64)sb != b) {
            *rhi = 0U;
            *rlo = 0U;
            return ONFI_SIGNED;
        }
        r = (onfi_u64)onficms(sa, sb);
        break;
    default:
        return ONFI_RANGE;
    }

    hs = onfihs(r);
    hd = onfihd(r);
    *rhi = hs;
    *rlo = onfilo(r);

    /* A comparison result is a small word, so its high half is zero either
       way and the two extractions prove nothing there. */
    if (!iscmp && hs != hd) {
        return ONFI_SPLIT;
    }
    return ONFI_OK;
}

int onfitst(void)
{
    int op;
    int idx;
    int rc;
    onf_u32 rhi;
    onf_u32 rlo;
    const struct onfiv *v;

    for (op = 0; op < ONFI_NOPS; op++) {
        for (idx = 0; (onf_u32)idx < onfvgrp[op].count; idx++) {
            rhi = 0U;
            rlo = 0U;
            rc = onfirun(op, idx, &rhi, &rlo);
            if (rc != ONFI_OK) {
                return op * 1000 + idx + 1;
            }
            v = &onfvgrp[op].vec[idx];
            if (rhi != v->rhi || rlo != v->rlo) {
                return op * 1000 + idx + 1;
            }
        }
    }
    return 0;
}
