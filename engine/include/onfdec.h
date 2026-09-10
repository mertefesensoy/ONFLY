/*
 * onfdec.h - network file integrity checks and decode (FR-LOD-01..05).
 *
 * FR-LOD-02 fixes the order of the checks: magic, byte-order sentinel, format
 * version, header CRC-32, declared payload length, payload CRC-32.  The first
 * failing check ends the step with the message and return code in Appendix E.
 * The order is not arbitrary -- it runs cheapest and most diagnostic first, so
 * that a file mangled by a text-mode transfer is reported as ONF102E (re-send
 * in binary) rather than as an opaque CRC failure.
 *
 * FR-LOD-05: every multi-byte field is decoded by explicit byte shift.  No
 * pointer cast is taken over the file buffer, so decoding does not depend on
 * host byte order or on the buffer's alignment.
 *
 * VL-08 applies: CRC-32 detects accidental corruption in transport, not
 * deliberate tampering.
 */
#ifndef ONFDEC_H
#define ONFDEC_H

#include "onfplat.h"
#include "onfker.h"

/*
 * Result codes.  The numeric value is the Appendix E message number, so a
 * caller maps a failure to its message and return code without a lookup table
 * that could fall out of step with the catalog.
 */
#define ONFD_OK       0     /* ONF001I */
#define ONFD_MAGIC  101     /* ONF101E  MAGIC CONSTANT MISMATCH        RC 12 */
#define ONFD_SENT   102     /* ONF102E  BYTE-ORDER SENTINEL MISMATCH   RC 12 */
#define ONFD_VER    103     /* ONF103E  UNSUPPORTED FORMAT VERSION     RC 12 */
#define ONFD_HCRC   104     /* ONF104E  HEADER CRC MISMATCH            RC 12 */
#define ONFD_MEM    105     /* ONF105E  NETWORK EXCEEDS MEMORY LIMIT   RC 12 */
#define ONFD_PLEN   106     /* ONF106E  PAYLOAD LENGTH INCONSISTENT    RC 12 */
#define ONFD_PCRC   107     /* ONF107E  PAYLOAD CRC MISMATCH           RC 12 */

/*
 * onfdec - verify a network file and populate a decoded view of it.
 *
 *   buf     the whole file as read, including any trailing zero padding from
 *           an FB dataset (IR-NET-08)
 *   len     bytes actually available in buf
 *   limit   memory budget in bytes for the decoded network plus simulation
 *           state; 0 means no limit.  FR-LOD-04 requires this to be checked
 *           from the header counts BEFORE anything is allocated.
 *   net     filled in on success; its array pointers point into buf, so buf
 *           must outlive net and must not be modified afterwards
 *   need    if not null, receives the computed memory requirement in bytes,
 *           whether or not the limit was exceeded, so a caller can report it
 *
 * Returns ONFD_OK or the first failing check's code.
 *
 * The engine trusts the header's declared payload length, never the dataset
 * size (FR-LOD-03, IR-NET-08): an FB dataset is padded to a record boundary,
 * so its size is almost always larger than the real payload.
 *
 * Side effects: none.  No allocation, no I/O, no static data.
 */
int onfdec(const onf_u8 *buf, onf_i32 len, onf_i32 limit,
           struct onfnet *net, onf_i32 *need);

#endif /* ONFDEC_H */
