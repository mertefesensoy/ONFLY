/*
 * onfcrc.h - CRC-32/ISO-HDLC (IR-NET-07, IR-COM-05).
 *
 * The same CRC serves three purposes: the network header check, the network
 * payload check (FR-LOD-02) and the response fingerprint (IR-COM-05).  It is
 * the zlib polynomial, so Python's zlib.crc32 is the reference oracle (O-4).
 *
 * VL-08 applies: this detects accidental corruption in transport, not
 * deliberate tampering.
 */
#ifndef ONFCRC_H
#define ONFCRC_H

#include "onfplat.h"

/*
 * onfcrc - CRC-32/ISO-HDLC over a byte range.
 *
 *   data  bytes to checksum; not modified
 *   len   number of bytes, must be >= 0
 *   crc   running value from a previous call, or 0 to start fresh
 *
 * Returns the CRC as an unsigned 32-bit value.  No side effects, no static
 * state, so it is reentrant (NFR-MNT-02).
 *
 * Streaming contract: onfcrc(b, n, onfcrc(a, m, 0)) equals the CRC of the
 * concatenation of a and b.  The network payload is checksummed in record-sized
 * pieces as it is reassembled (FR-LOD-03), so this property is relied upon.
 */
onf_u32 onfcrc(const onf_u8 *data, onf_i32 len, onf_u32 crc);

#endif /* ONFCRC_H */
