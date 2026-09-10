/*
 * tstcom.c - TU-07 and TU-01: generated layout and big-endian accessors.
 *
 * What this proves, and only this:
 *   TU-01  the integer width and two's complement assertions in onfplat.h hold
 *          on the compiler that built this binary (NR-11).
 *   TU-07  the generated record layout has the size and offsets the master
 *          definition declares, and the generated accessors encode and decode
 *          big-endian values correctly (IR-COM-01, IR-COM-03, IR-COM-04).
 *
 * Including onfcom.h is itself part of the test: every compile-time assertion
 * in onfplat.h and onfcom.h fires during translation, so a layout drift or a
 * wrong integer width fails the build rather than this program.
 *
 * The edge cases below are the point.  INT32_MIN and -1 are exactly where an
 * implementation that leans on signed overflow, or on a pointer cast over the
 * buffer, stops being portable (NR-11, FR-LOD-05).
 */
#include <stdio.h>
#include <string.h>

#include "onfcom.h"

static int failures = 0;
static int checks = 0;

static void ck32(const char *what, onf_i32 value, onf_u8 b0, onf_u8 b1,
                 onf_u8 b2, onf_u8 b3)
{
    onf_u8 buf[ONF_RECLEN];
    onf_i32 back;
    int ok;

    memset(buf, 0xAA, sizeof buf);          /* poison, so a short write shows */
    onfp32(buf, 0, value);
    ok = (buf[0] == b0 && buf[1] == b1 && buf[2] == b2 && buf[3] == b3);
    back = onfg32(buf, 0);
    ok = ok && (back == value);
    ok = ok && (buf[4] == 0xAA);            /* wrote exactly 4 bytes */

    checks++;
    if (!ok) {
        failures++;
        printf("  FAIL i32 %-12s value=%ld bytes=%02X %02X %02X %02X "
               "back=%ld (want %02X %02X %02X %02X)\n",
               what, (long)value, buf[0], buf[1], buf[2], buf[3], (long)back,
               b0, b1, b2, b3);
    }
}

static void ck16(const char *what, onf_i16 value, onf_u8 b0, onf_u8 b1)
{
    onf_u8 buf[ONF_RECLEN];
    onf_i16 back;
    int ok;

    memset(buf, 0xAA, sizeof buf);
    onfp16(buf, 0, value);
    ok = (buf[0] == b0 && buf[1] == b1);
    back = onfg16(buf, 0);
    ok = ok && (back == value);
    ok = ok && (buf[2] == 0xAA);

    checks++;
    if (!ok) {
        failures++;
        printf("  FAIL i16 %-12s value=%d bytes=%02X %02X back=%d "
               "(want %02X %02X)\n",
               what, (int)value, buf[0], buf[1], (int)back, b0, b1);
    }
}

static void ckint(const char *what, long got, long want)
{
    checks++;
    if (got != want) {
        failures++;
        printf("  FAIL %-24s got %ld want %ld\n", what, got, want);
    }
}

int main(void)
{
    onf_u8 rec[ONF_RECLEN];
    int k;

    printf("tstcom: TU-01/TU-07 on platform %s\n", ONF_PLATID);

    /* --- TU-01: integer widths (the typedefs above already asserted these at
       compile time; restated here so the run-time report is self-contained) */
    ckint("sizeof onf_i16", (long)sizeof(onf_i16), 2L);
    ckint("sizeof onf_i32", (long)sizeof(onf_i32), 4L);
    ckint("sizeof onf_u32", (long)sizeof(onf_u32), 4L);

    /* --- TU-07: record geometry --- */
    ckint("ONF_RECLEN", (long)ONF_RECLEN, 412L);
    ckint("ONF_HEADLEN", (long)ONF_HEADLEN, 28L);
    ckint("ONF_MAXOUT", (long)ONF_MAXOUT, 32L);
    ckint("ONF_OUTLEN", (long)ONF_OUTLEN, 12L);
    ckint("sizeof struct onfcom", (long)sizeof(struct onfcom), 412L);
    ckint("sizeof struct onfout", (long)sizeof(struct onfout), 12L);

    /* --- TU-07: declared offsets match SRS section 4.3 --- */
    ckint("off stimcode", (long)ONF_O_STIMCODE, 0L);
    ckint("off seed", (long)ONF_O_SEED, 8L);
    ckint("off stimrate", (long)ONF_O_STIMRATE, 12L);
    ckint("off simms", (long)ONF_O_SIMMS, 14L);
    ckint("off rc", (long)ONF_O_RC, 16L);
    ckint("off outcount", (long)ONF_O_OUTCOUNT, 18L);
    ckint("off fprint", (long)ONF_O_FPRINT, 20L);
    ckint("off steps", (long)ONF_O_STEPS, 24L);
    ckint("off out.id", (long)ONF_OE_ID, 0L);
    ckint("off out.latus", (long)ONF_OE_LATUS, 4L);
    ckint("off out.spikes", (long)ONF_OE_SPIKES, 8L);
    ckint("off out.filler", (long)ONF_OE_FILLER, 10L);

    /* --- IR-COM-03: every OUT entry lands on a 4-byte boundary --- */
    for (k = 0; k < ONF_MAXOUT; k++) {
        long base = (long)(ONF_HEADLEN + k * ONF_OUTLEN);
        checks++;
        if (base % 4 != 0) {
            failures++;
            printf("  FAIL out entry %d starts at %ld, not a multiple of 4\n",
                   k, base);
        }
    }

    /* --- TU-07: big-endian 32-bit round trip, edge cases first --- */
    ck32("zero",      0L,           0x00, 0x00, 0x00, 0x00);
    ck32("one",       1L,           0x00, 0x00, 0x00, 0x01);
    ck32("minus one", -1L,          0xFF, 0xFF, 0xFF, 0xFF);
    ck32("int32 max", 2147483647L,  0x7F, 0xFF, 0xFF, 0xFF);
    ck32("int32 min", -2147483647L - 1L, 0x80, 0x00, 0x00, 0x00);
    ck32("seed max",  999999999L,   0x3B, 0x9A, 0xC9, 0xFF);
    ck32("no latency", -1L,         0xFF, 0xFF, 0xFF, 0xFF);
    ck32("byte order", 0x01020304L, 0x01, 0x02, 0x03, 0x04);

    /* --- TU-07: big-endian 16-bit round trip --- */
    ck16("zero",      0,      0x00, 0x00);
    ck16("one",       1,      0x00, 0x01);
    ck16("minus one", -1,     0xFF, 0xFF);
    ck16("int16 max", 32767,  0x7F, 0xFF);
    ck16("int16 min", -32768, 0x80, 0x00);
    ck16("rate max",  9999,   0x27, 0x0F);

    /* --- A whole record written through the accessors, then read back at the
       declared offsets.  This is the check that catches an offset that is
       self-consistent but wrong. --- */
    memset(rec, 0, sizeof rec);
    memcpy(rec + ONF_O_STIMCODE, "SUGR    ", 8);
    onfp32(rec, ONF_O_SEED, 999999999L);
    onfp16(rec, ONF_O_STIMRATE, 9999);
    onfp16(rec, ONF_O_SIMMS, 1000);
    onfp16(rec, ONF_O_RC, 0);
    onfp16(rec, ONF_O_OUTCOUNT, ONF_MAXOUT);
    onfp32(rec, ONF_O_STEPS, 10000L);
    for (k = 0; k < ONF_MAXOUT; k++) {
        onf_i32 base = ONF_HEADLEN + k * ONF_OUTLEN;
        onfp32(rec, base + ONF_OE_ID, 100000L + k);
        onfp32(rec, base + ONF_OE_LATUS, (k == 0) ? -1L : (long)(k * 1800));
        onfp16(rec, base + ONF_OE_SPIKES, (onf_i16)(k * 3));
    }

    ckint("rt seed", (long)onfg32(rec, ONF_O_SEED), 999999999L);
    ckint("rt stimrate", (long)onfg16(rec, ONF_O_STIMRATE), 9999L);
    ckint("rt simms", (long)onfg16(rec, ONF_O_SIMMS), 1000L);
    ckint("rt outcount", (long)onfg16(rec, ONF_O_OUTCOUNT), 32L);
    ckint("rt steps", (long)onfg32(rec, ONF_O_STEPS), 10000L);
    ckint("rt stimcode", (long)memcmp(rec + ONF_O_STIMCODE, "SUGR    ", 8), 0L);
    for (k = 0; k < ONF_MAXOUT; k++) {
        onf_i32 base = ONF_HEADLEN + k * ONF_OUTLEN;
        ckint("rt out.id", (long)onfg32(rec, base + ONF_OE_ID), 100000L + k);
        ckint("rt out.latus", (long)onfg32(rec, base + ONF_OE_LATUS),
              (k == 0) ? -1L : (long)(k * 1800));
        ckint("rt out.spikes", (long)onfg16(rec, base + ONF_OE_SPIKES),
              (long)(k * 3));
    }

    /* The last OUT entry must end exactly at the record length; one byte past
       it is outside the record. */
    ckint("last entry end",
          (long)(ONF_HEADLEN + (ONF_MAXOUT - 1) * ONF_OUTLEN + ONF_OUTLEN),
          (long)ONF_RECLEN);

    printf("tstcom: %d checks, %d failures\n", checks, failures);
    return failures ? 1 : 0;
}
