/*
 * tstxfr.c - check the IR-TRN-02 transport test file after it arrives.
 *
 * IR-TRN-02 requires Spike S2 to evaluate each transport "using a test
 * file containing every byte value 0x00-0xFF plus a real network
 * file".  The network half is checked by ONFLYENG's verify-only mode
 * (IR-TRN-03), which already reported ONF003I on MVS (VL-50).  This is
 * the other half, and it needs its own checker because ONFLYENG knows
 * only the ONFNET format and this file is deliberately not that.
 *
 * WHY THE FILE CHECKS ITSELF
 * --------------------------
 * tools/mkaws.py writes 1024 bytes of body followed by a 4-byte
 * big-endian length and the 4-byte big-endian CRC-32 of the body.  So
 * this program needs to be told nothing: it reads what arrived, takes
 * the length and CRC from the file itself, and recomputes.  That
 * matters on tape, where IR-NET-08's FB blocking pads the dataset to a
 * record boundary -- 1032 bytes become 1040 -- so the trailer is NOT
 * at the end of what is read and a checker that assumed it was would
 * fail on a perfectly good transfer.
 *
 * WHY IT REPORTS FOUR SECTIONS SEPARATELY
 * ---------------------------------------
 * A CRC says only yes or no.  The body is four 256-byte sections, each
 * chosen so that a particular corruption shows up in one and not the
 * others:
 *
 *   ascending 0x00..0xFF   whether every value survived at all
 *   descending 0xFF..0x00  whether damage depends on position
 *   256 bytes of 0x40      EBCDIC blank; a transport that truncates
 *                          trailing blanks eats this and nothing else
 *   alternating 0x00/0xFF  high and low bits together, a pattern no
 *                          text conversion leaves alone
 *
 * So a failure names the mechanism instead of only its existence,
 * which is the difference between a finding and a mystery.
 *
 * Dialect: C89 (NR-04).  No floating point (NR-05).  Multi-byte fields
 * are assembled with explicit shifts, never a pointer cast, which is
 * FR-LOD-05's rule and the reason this is trustworthy on a big-endian
 * host it was not compiled on before.
 */
#include <stdio.h>

#include "onfplat.h"
#include "onfcrc.h"

#define ONF_TSTDD "DD:ONFTST"

#define SECTION 256
#define BODY    (4 * SECTION)
#define TRAILER 8
#define BUFSZ   4096

static onf_u8 buf[BUFSZ];

/* Four bytes, big-endian, by shifts only (FR-LOD-05). */
static onf_u32 be32(const onf_u8 *p)
{
    return ((onf_u32)p[0] << 24) | ((onf_u32)p[1] << 16)
         | ((onf_u32)p[2] << 8) | (onf_u32)p[3];
}

static int section_ok(const onf_u8 *p, int which)
{
    int i;

    for (i = 0; i < SECTION; i++) {
        onf_u8 want;

        if (which == 0) {
            want = (onf_u8)i;
        } else if (which == 1) {
            want = (onf_u8)(255 - i);
        } else if (which == 2) {
            want = (onf_u8)0x40;
        } else {
            want = (onf_u8)((i & 1) ? 0xFF : 0x00);
        }
        if (p[i] != want) {
            return i;               /* first differing offset */
        }
    }
    return -1;
}

int main(int argc, char **argv)
{
    static const char *names[4] = {
        "ASCENDING", "DESCENDING", "EBCDIC-BLANK", "ALTERNATING"
    };
    const char *path;
    FILE *f;
    onf_i32 len;
    onf_u32 want;
    onf_u32 got;
    onf_u32 declared;
    int bad;
    int i;

    path = (argc > 1) ? argv[1] : ONF_TSTDD;

    printf("# tstxfr IR-TRN-02 transport check\n");

    f = fopen(path, "rb");
    if (f == NULL) {
        printf("XFR901S CANNOT OPEN %s\n", path);
        return 16;
    }
    len = (onf_i32)fread(buf, 1, (size_t)BUFSZ, f);
    fclose(f);
    printf("XFR001I READ %ld BYTES FROM %s\n", (long)len, path);

    if (len < BODY + TRAILER) {
        printf("XFR902S SHORT: NEED AT LEAST %d BYTES\n",
               BODY + TRAILER);
        return 12;
    }

    /* The trailer sits immediately after the body, not at the end of
       the dataset: FB blocking pads beyond it (IR-NET-08). */
    declared = be32(buf + BODY);
    want = be32(buf + BODY + 4);
    got = onfcrc(buf, (onf_i32)BODY, 0UL);

    printf("XFR002I DECLARED LENGTH %lu, CRC %08lX\n",
           (unsigned long)declared, (unsigned long)want);
    printf("XFR003I COMPUTED CRC     %08lX\n", (unsigned long)got);

    bad = 0;
    for (i = 0; i < 4; i++) {
        int off = section_ok(buf + i * SECTION, i);

        if (off < 0) {
            printf("XFR004I %-13s OK\n", names[i]);
        } else {
            bad++;
            printf("XFR005E %-13s FIRST BAD AT +%d, GOT %02X\n",
                   names[i], off,
                   (unsigned)buf[i * SECTION + off]);
        }
    }

    if (declared != (onf_u32)BODY) {
        printf("XFR906E DECLARED LENGTH IS NOT %d\n", BODY);
        bad++;
    }
    if (got != want) {
        printf("XFR907E CRC MISMATCH\n");
        bad++;
    }

    if (bad == 0) {
        printf("XFR000I TRANSPORT OK: ALL 256 BYTE VALUES SURVIVED\n");
        return 0;
    }
    printf("XFR908E TRANSPORT DAMAGED THE FILE\n");
    return 12;
}
