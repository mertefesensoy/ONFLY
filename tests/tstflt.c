/*
 * tstflt.c - TT-02: run Berkeley TestFloat vectors through the onf_fp API.
 *
 * NR-14 requires the TestFloat vector suite for the used operations to pass on
 * every compiler and platform before any engine test runs.  This is that check
 * for the operations SRS Appendix C actually uses: addition, subtraction,
 * multiplication, and the ordered comparisons.
 *
 * Vectors arrive on stdin in TestFloat's own format, one case per line:
 *   arithmetic   <a:16 hex> <b:16 hex> <expected:16 hex> <flags:2 hex>
 *   comparison   <a:16 hex> <b:16 hex> <0|1> <flags:2 hex>
 *
 * usage: tstflt <add|sub|mul|lt|le|eq>  < vectors
 *
 * Two deliberate exclusions, both declared rather than silent:
 *
 *   NaN cases (VL-11, decision D-46).  TestFloat's reference is built against
 *   the 8086 specialization because ARM-VFPv2-defaultNaN cannot build a
 *   complete library (the upstream f128 defect, D-33).  The two share their
 *   arithmetic cores verbatim and differ only in NaN handling, so a case whose
 *   operands or expected result is NaN would compare a defaultNaN engine
 *   against an 8086 reference and report a difference that is by design.
 *   ONFLY aborts on any NaN before it can propagate (FR-SIM-08), so these are
 *   cases the engine never reaches.  They are counted and reported.
 *
 *   Exception flags.  NR-10 forbids any logic depending on them and D-34
 *   removed the storage they would accumulate into, so the flags column is
 *   parsed and ignored.  TT-02 here proves results, not flags.
 *
 * NR-05: no float or double appears in this file.  A 16-hex-digit value is
 * read as two 32-bit halves, which is also why no 64-bit integer type is
 * needed (NR-04).
 */
#include <stdio.h>
#include <string.h>

#include "onffp.h"

#define OP_ADD 1
#define OP_SUB 2
#define OP_MUL 3
#define OP_LT  4
#define OP_LE  5
#define OP_EQ  6

/* Parse 8 hex characters into an unsigned 32-bit value. */
static onf_u32 hex8(const char *p)
{
    onf_u32 v;
    int i;

    v = 0UL;
    for (i = 0; i < 8; i++) {
        char c = p[i];
        onf_u32 d;

        if (c >= '0' && c <= '9') {
            d = (onf_u32)(c - '0');
        } else if (c >= 'A' && c <= 'F') {
            d = (onf_u32)(c - 'A' + 10);
        } else if (c >= 'a' && c <= 'f') {
            d = (onf_u32)(c - 'a' + 10);
        } else {
            d = 0UL;
        }
        v = (v << 4) | d;
    }
    return v;
}

/* True when the value is a NaN: exponent all ones and a non-zero significand.
   Infinity is finite-signalling here on purpose -- infinity is representable
   identically under both specializations, so those cases are NOT excluded. */
static int is_nan(onf_f64 v)
{
    if ((v.hi & 0x7FF00000UL) != 0x7FF00000UL) {
        return 0;
    }
    return ((v.hi & 0x000FFFFFUL) != 0UL || v.lo != 0UL) ? 1 : 0;
}

int main(int argc, char **argv)
{
    char line[256];
    onf_f64 a, b, want, got;
    long total, checked, skipped, bad;
    int op;

    if (argc < 2) {
        fprintf(stderr, "usage: tstflt <add|sub|mul|lt|le|eq>\n");
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

        a = onffbit(hex8(line), hex8(line + 8));
        b = onffbit(hex8(line + 17), hex8(line + 25));

        if (op == OP_LT || op == OP_LE || op == OP_EQ) {
            /* Comparisons: operands may be NaN but the expected answer is a
               plain 0 or 1, so only the operands need excluding. */
            if (is_nan(a) || is_nan(b)) {
                skipped++;
                continue;
            }
            cmp_expected = (line[34] == '1') ? 1 : 0;
            if (op == OP_LT) {
                cmp_got = onfflt(a, b);
            } else if (op == OP_LE) {
                cmp_got = onffle(a, b);
            } else {
                /* Equality is not offered by onf_fp: Appendix C never compares
                   for equality, so exposing it would widen the NR-09 admission
                   burden for no benefit.  It is derived here from the two
                   ordered comparisons, which is exactly a <= b and b <= a. */
                cmp_got = (onffle(a, b) && onffle(b, a)) ? 1 : 0;
            }
            checked++;
            if (cmp_got != cmp_expected) {
                bad++;
                if (bad <= 5) {
                    printf("MISMATCH %s a=%08lX:%08lX b=%08lX:%08lX "
                           "got=%d want=%d\n", argv[1],
                           (unsigned long)a.hi, (unsigned long)a.lo,
                           (unsigned long)b.hi, (unsigned long)b.lo,
                           cmp_got, cmp_expected);
                }
            }
            continue;
        }

        want = onffbit(hex8(line + 34), hex8(line + 42));
        if (is_nan(a) || is_nan(b) || is_nan(want)) {
            skipped++;
            continue;
        }

        if (op == OP_ADD) {
            got = onffadd(a, b);
        } else if (op == OP_SUB) {
            got = onffsub(a, b);
        } else {
            got = onffmul(a, b);
        }

        checked++;
        if (got.hi != want.hi || got.lo != want.lo) {
            bad++;
            if (bad <= 5) {
                printf("MISMATCH %s a=%08lX:%08lX b=%08lX:%08lX "
                       "got=%08lX:%08lX want=%08lX:%08lX\n", argv[1],
                       (unsigned long)a.hi, (unsigned long)a.lo,
                       (unsigned long)b.hi, (unsigned long)b.lo,
                       (unsigned long)got.hi, (unsigned long)got.lo,
                       (unsigned long)want.hi, (unsigned long)want.lo);
            }
        }
    }

    printf("TT02 op=%s backend=%s total=%ld checked=%ld skipped_nan=%ld "
           "mismatch=%ld\n", argv[1], ONF_FPID, total, checked, skipped, bad);
    return bad ? 1 : 0;
}
