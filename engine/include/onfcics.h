/*
 * onfcics.h - the CICS adapter: one network, many LINKed requests (D-395).
 *
 * Section 2.2's component table has always listed a "CICS adapter - LINK
 * target with COMMAREA - C".  This is that row, built for Phase G's first
 * component under P-22 (D-396).  It is an ADAPTER, beside the batch adapter
 * in engine/src/onflyeng.c and not above or below it: both of them read a
 * network, hold it, and drive engine/src/onfreq.c's shared request sequence
 * over 412-byte records.  What differs is only where the records come from.
 *
 * ------------------------------------------------------------------------
 * Why a handle, and not a file-scope pointer
 * ------------------------------------------------------------------------
 * A batch step is one task, so engine/src/onflyeng.c can keep the network in
 * locals and never think about it.  Section 3.7 requires the opposite of a
 * CICS program:
 *
 *     "It must therefore be reentrant and threadsafe, and be defined with
 *      CONCURRENCY(REQUIRED) ... The network will be loaded once at region
 *      startup into shared storage and anchored for all tasks; transactions
 *      only read it."
 *
 * A file-scope pointer would be a piece of task-shared mutable state whose
 * safety no test here could examine, because one rclrun run unit runs one
 * task (VL-117).  A handle costs one parameter and removes the question: the
 * anchor lives in the caller, which is exactly where CICS shared storage
 * lives.  onfcrun writes only through its ca argument and through the state
 * inside the handle it was given, so two handles never touch.
 *
 * ------------------------------------------------------------------------
 * What this does NOT do
 * ------------------------------------------------------------------------
 * It does not re-implement the request sequence.  onfcrun calls onfrq1, the
 * single copy D-224 established and D-383 split -- the same code the batch
 * engine, the MVS driver and tests/tstgld.c run.  A CICS-specific validation
 * order would be the second-implementation condition that produced D-289 and
 * then D-360, silently both times.
 *
 * It does no simulation of its own, performs no formatting, and knows nothing
 * about CICS: no EXEC statement, no terminal, no queue.  Those belong to the
 * COBOL transaction.  This file only turns a 412-byte COMMAREA into a request
 * and back into a response.
 */
#ifndef ONFCICS_H
#define ONFCICS_H

#include "onfplat.h"

/*
 * The anchor.  Opaque by design: the caller is a .NET module that must not
 * be able to reach inside, and on z/OS it would be storage obtained by
 * GETMAIN whose shape is nobody else's business.
 */
struct onfcic;

/*
 * onfcini - load and verify a network once, and return the anchor.
 *
 *   netpath  the network file (IR-NET), read whole
 *   rc       if not null, receives ONFD_OK or the first failing check's code
 *            from onfdec/onfldp -- the same ONF1nnE numbers Appendix E
 *            defines, so a caller can report the real reason rather than
 *            "load failed"
 *
 * Returns the anchor, or null on any failure.  On failure *rc names it:
 * ONFC_EFILE when the file could not be read at all, ONFC_EMEM when storage
 * could not be obtained, and otherwise an ONFD_* integrity code.
 *
 * Does I/O and allocates.  That is an adapter's job and is why this is not
 * in the simulation core (FR-SIM-07).
 */
struct onfcic *onfcini(const char *netpath, onf_i32 *rc);

/*
 * onfcrun - process one request in place, in the caller's COMMAREA.
 *
 *   h    an anchor from onfcini
 *   ca   the 412-byte COMMAREA, request on entry, response on return
 *   len  the length the LINK declared
 *
 * IR-JCL-03: only the response portion is written; offsets 0 to 15, the
 * request echo, come back exactly as they arrived.
 *
 * Returns the request's return code (ONFR_OK, ONFR_WARN, ONFR_ERR,
 * ONFR_SEV), or ONFC_EARG if h is null, ca is null, or len is not exactly
 * ONF_RECLEN.
 *
 * WHY len IS CHECKED AND NOT INFERRED.  Under Raincode the memory area the
 * LINK hands the module reports a Size of 257,448 -- the address-space slice,
 * not the record (VL-117, finding 4).  A caller that passed that as len, or
 * an adapter that asked the area how big it was, would read a quarter of a
 * megabyte for a 412-byte record.  The length therefore travels as an
 * argument and is checked against ONF_RECLEN exactly.
 *
 * No I/O.  No allocation.  All storage was obtained by onfcini.
 */
onf_i32 onfcrun(struct onfcic *h, onf_u8 *ca, onf_i32 len);

/*
 * onfcend - release an anchor.  Null is accepted and ignored.
 */
void onfcend(struct onfcic *h);

/*
 * onfclen - the COMMAREA length, ONF_RECLEN.
 *
 * It exists so that the .NET LINK target holds NO layout knowledge at all,
 * not even the record's length.  The alternative is a 412 hand-written in a
 * C# source file, which is a second statement of a generated fact and is
 * exactly what IR-COM-01 forbids: the length comes from layout/master.py,
 * through generated/onfcom.h, through here, and nobody restates it.
 */
onf_i32 onfclen(void);

/*
 * Adapter-level failures, kept clear of the ONFD_* (101..109) and ONFR_*
 * (0, 4, 8, 16) ranges so that a caller can tell which layer spoke.
 */
#define ONFC_EFILE (-1)         /* the network file could not be read */
#define ONFC_EMEM  (-2)         /* storage could not be obtained */
#define ONFC_EARG  (-3)         /* null handle, null COMMAREA, or bad length */

#endif /* ONFCICS_H */
