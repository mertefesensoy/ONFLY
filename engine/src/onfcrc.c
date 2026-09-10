/*
 * onfcrc.c - CRC-32/ISO-HDLC, bit at a time (IR-NET-07).
 *
 * Why bitwise rather than a 256-entry lookup table.  NFR-MNT-02 forbids
 * writable static data so that the engine is reentrant for the future CICS
 * path, which rules out building a table lazily at first use.  A const table
 * would satisfy that rule, but it costs 1 KB of storage in a 24-bit region
 * (C-01) and has to be generated and kept in step with the polynomial.  The
 * bitwise form has no state at all, is trivially auditable against the
 * parameters, and matches oracle O-4's crc32_bitwise line for line.
 *
 * The cost is roughly eight times more work per byte.  That is paid once per
 * job step over the network file (FR-LOD-01) and over about forty bytes per
 * response fingerprint, neither of which is in the simulation inner loop, so
 * it does not bear on NFR-PERF-01.  Spike S3 measures where the time actually
 * goes; if the network CRC turns out to matter there, a generated const table
 * is the answer and this comment is the reason it was not done up front.
 *
 * All arithmetic is on unsigned 32-bit values, so every shift is applied to a
 * non-negative value and no signed overflow is possible (NR-11).
 */
#include "onfcrc.h"

/* Reflected form of polynomial 0x04C11DB7, for the least-significant-bit-first
   algorithm that CRC-32/ISO-HDLC specifies (refin and refout both true). */
#define ONF_CRCPOLY 0xEDB88320UL

/* Initial register value and final XOR, both all ones for this CRC. */
#define ONF_CRCINIT 0xFFFFFFFFUL

onf_u32 onfcrc(const onf_u8 *data, onf_i32 len, onf_u32 crc)
{
    onf_u32 reg;
    onf_i32 i;
    int bit;

    /* Undo the previous call's final XOR so that a running value resumes
       exactly where it left off; crc == 0 therefore starts a fresh CRC. */
    reg = crc ^ ONF_CRCINIT;

    for (i = 0; i < len; i++) {
        reg ^= (onf_u32)data[i];
        for (bit = 0; bit < 8; bit++) {
            if (reg & 1UL) {
                reg = (reg >> 1) ^ ONF_CRCPOLY;
            } else {
                reg = reg >> 1;
            }
        }
    }

    return reg ^ ONF_CRCINIT;
}
