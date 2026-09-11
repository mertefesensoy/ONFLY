/*
 * tstc2c.c - run Berkeley TestFloat vectors through SoftFloat 2c (D-106).
 *
 * D-105 invokes NR-03 and vendors Release 2c because Gate G1 measured that
 * GCCMVS cannot build Release 3e (VL-19, VL-21).  D-106 front-loads the one
 * question that decides whether the swap is cheap: does 2c compute the same
 * binary64 results as 3e?  Every ACC-5 fingerprint in the golden suite was
 * produced with 3e, so a disagreement on any of ONFLY's six operations
 * changes every fingerprint.
 *
 * This is deliberately checked against TestFloat's own reference rather than
 * against 3e directly.  Two libraries agreeing with an independent oracle is
 * a stronger statement than two libraries agreeing with each other, and it
 * is the check NR-14 already requires for "every compiler and platform".
 * Agreement with 3e then follows, because tstflt.c checks 3e against the
 * same vectors.
 *
 * The command line, the input format and the summary line are deliberately
 * identical to tests/tstflt.c, so tests/run_tt02.py's per-operation runner
 * drives this binary unchanged:
 *
 *   arithmetic   <a:16 hex> <b:16 hex> <expected:16 hex> <flags:2 hex>
 *   comparison   <a:16 hex> <b:16 hex> <0|1> <flags:2 hex>
 *
 * usage: tstc2c <add|sub|mul|lt|le|eq>  < vectors
 *
 * The same two exclusions apply, for the same reasons as in tstflt.c: NaN
 * cases (VL-11, D-46) and exception flags (NR-10, D-34).  Here the flags are
 * not merely ignored, they are discarded at the source: softfloat/derive2c.py
 * makes float_raise a no-op, which is what D-34 requires of the 3e path too.
 *
 * NR-05: no float or double appears in this file.  A 16-hex-digit value is
 * read as two 32-bit halves, which is also the shape 2c's float64 has, so
 * no 64-bit integer type is needed anywhere (NR-04) -- that being the whole
 * reason 2c is here.
 */
#include <stdio.h>
#include <string.h>

#include "milieu.h"
#include "softfloat.h"

#define OP_ADD 1
#define OP_SUB 2
#define OP_MUL 3
#define OP_LT  4
#define OP_LE  5
#define OP_EQ  6

/* Parse 8 hex characters into an unsigned 32-bit value. */
static bits32 hex8(const char *p)
{
    bits32 v;
    int i;

    v = 0UL;
    for (i = 0; i < 8; i++) {
        char c = p[i];
        bits32 d;

        if (c >= '0' && c <= '9') {
            d = (bits32)(c - '0');
        } else if (c >= 'A' && c <= 'F') {
            d = (bits32)(c - 'A' + 10);
        } else if (c >= 'a' && c <= 'f') {
            d = (bits32)(c - 'a' + 10);
        } else {
            d = 0UL;
        }
        v = (v << 4) | d;
    }
    return v;
}

static float64 mkf64(bits32 hi, bits32 lo)
{
    float64 z;

    z.high = hi;
    z.low = lo;
    return z;
}

/* Exponent all ones and a non-zero significand.  Infinity is NOT a NaN and
   is deliberately not excluded: it is represented identically under both
   specializations, so those cases are real checks. */
static int is_nan(float64 v)
{
    if ((v.high & 0x7FF00000UL) != 0x7FF00000UL) {
        return 0;
    }
    return ((v.high & 0x000FFFFFUL) != 0UL || v.low != 0UL) ? 1 : 0;
}

int main(int argc, char **argv)
{
    char line[256];
    float64 a, b, want, got;
    long total, checked, skipped, bad;
    int op;

    if (argc < 2) {
        fprintf(stderr, "usage: tstc2c <add|sub|mul|lt|le|eq>\n");
        return 2;
    }
    if (strcmp(argv[1], "add") == 0)      op = OP_ADD;
    else if (strcmp(argv[1], "sub") == 0) op = OP_SUB;
    else if (strcmp(argv[1], "mul") == 0) op = OP_MUL;
    else if (strcmp(argv[1], "lt") == 0)  op = OP_LT;
    else if (strcmp(argv[1], "le") == 0)  op = OP_LE;
    else if (strcmp(argv[1], "eq") == 0)  op = OP_EQ;
    else {
        fprintf(stderr, "unknown operation %s\n", argv[1]);
        return 2;
    }

    total = checked = skipped = bad = 0;

    while (fgets(line, (int)sizeof line, stdin) != NULL) {
        int cmp_expected, cmp_got;

        if (strlen(line) < 36) {
            continue;
        }
        total++;

        a = mkf64(hex8(line), hex8(line + 8));
        b = mkf64(hex8(line + 17), hex8(line + 25));

        if (op == OP_LT || op == OP_LE || op == OP_EQ) {
            if (is_nan(a) || is_nan(b)) {
                skipped++;
                continue;
            }
            cmp_expected = (line[34] == '1') ? 1 : 0;
            if (op == OP_LT) {
                cmp_got = float64_lt(a, b) ? 1 : 0;
            } else if (op == OP_LE) {
                cmp_got = float64_le(a, b) ? 1 : 0;
            } else {
                cmp_got = float64_eq(a, b) ? 1 : 0;
            }
            checked++;
            if (cmp_got != cmp_expected) {
                bad++;
                if (bad <= 10) {
                    printf("MISMATCH %s a=%08lX:%08lX b=%08lX:%08lX "
                           "got=%d want=%d\n", argv[1],
                           (unsigned long)a.high, (unsigned long)a.low,
                           (unsigned long)b.high, (unsigned long)b.low,
                           cmp_got, cmp_expected);
                }
            }
            continue;
        }

        want = mkf64(hex8(line + 34), hex8(line + 42));
        if (is_nan(a) || is_nan(b) || is_nan(want)) {
            skipped++;
            continue;
        }

        if (op == OP_ADD) {
            got = float64_add(a, b);
        } else if (op == OP_SUB) {
            got = float64_sub(a, b);
        } else {
            got = float64_mul(a, b);
        }
        checked++;
        if (got.high != want.high || got.low != want.low) {
            bad++;
            if (bad <= 10) {
                printf("MISMATCH %s a=%08lX:%08lX b=%08lX:%08lX "
                       "got=%08lX:%08lX want=%08lX:%08lX\n", argv[1],
                       (unsigned long)a.high, (unsigned long)a.low,
                       (unsigned long)b.high, (unsigned long)b.low,
                       (unsigned long)got.high, (unsigned long)got.low,
                       (unsigned long)want.high, (unsigned long)want.low);
            }
        }
    }

    printf("TT02 op=%s backend=%s total=%ld checked=%ld skipped_nan=%ld "
           "mismatch=%ld\n", argv[1], "SOFT2C", total, checked, skipped, bad);
    return (bad == 0) ? 0 : 1;
}
