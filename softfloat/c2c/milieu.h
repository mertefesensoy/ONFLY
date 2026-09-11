/*
 * DERIVATIVE WORK.  This file is ONFLY's configuration of Berkeley
 * SoftFloat Release 2c, by John R. Hauser, generated from upstream's
 * milieu.h by softfloat/derive2c.py.  Do not edit it by hand:
 * edit the script.  The original template is in
 * third_party/SoftFloat-2c/softfloat/bits32/templates/ and is unmodified.
 *
 * Release 2c's legal notice, reproduced as its terms require:
 *
 *   THIS SOFTWARE IS DISTRIBUTED AS IS, FOR FREE.  Although reasonable
 *   effort has been made to avoid it, THIS SOFTWARE MAY CONTAIN FAULTS
 *   THAT WILL AT TIMES RESULT IN INCORRECT BEHAVIOR.  USE OF THIS
 *   SOFTWARE IS RESTRICTED TO PERSONS AND ORGANIZATIONS WHO CAN AND WILL
 *   TOLERATE ALL LOSSES, COSTS, OR OTHER PROBLEMS THEY INCUR DUE TO THE
 *   SOFTWARE WITHOUT RECOMPENSE FROM JOHN HAUSER OR THE INTERNATIONAL
 *   COMPUTER SCIENCE INSTITUTE, AND WHO FURTHERMORE EFFECTIVELY INDEMNIFY
 *   JOHN HAUSER AND THE INTERNATIONAL COMPUTER SCIENCE INSTITUTE
 *   (possibly via similar legal notice) AGAINST ALL LOSSES, COSTS, OR
 *   OTHER PROBLEMS INCURRED BY THEIR CUSTOMERS AND CLIENTS DUE TO THE
 *   SOFTWARE, OR INCURRED BY ANYONE DUE TO A DERIVATIVE WORK THEY CREATE
 *   USING ANY PART OF THE SOFTWARE.
 *
 *   The following are expressly permitted, even for commercial purposes:
 *   (1) distribution of SoftFloat in whole or in part, as long as this and
 *   other legal notices remain and are prominent, and provided also that,
 *   for a partial distribution, prominent notice is given that it is a
 *   subset of the original; and (2) inclusion or use of SoftFloat in whole
 *   or in part in a derivative work, provided that the use restrictions
 *   above are met and the minimal documentation requirements stated in the
 *   source code are satisfied.
 */

/*============================================================================

This C header file template is part of the Berkeley SoftFloat IEEE Floating-
Point Arithmetic Package, Release 2c, by John R. Hauser.

THIS SOFTWARE IS DISTRIBUTED AS IS, FOR FREE.  Although reasonable effort has
been made to avoid it, THIS SOFTWARE MAY CONTAIN FAULTS THAT WILL AT TIMES
RESULT IN INCORRECT BEHAVIOR.  USE OF THIS SOFTWARE IS RESTRICTED TO PERSONS
AND ORGANIZATIONS WHO CAN AND WILL TOLERATE ALL LOSSES, COSTS, OR OTHER
PROBLEMS THEY INCUR DUE TO THE SOFTWARE WITHOUT RECOMPENSE FROM JOHN HAUSER OR
THE INTERNATIONAL COMPUTER SCIENCE INSTITUTE, AND WHO FURTHERMORE EFFECTIVELY
INDEMNIFY JOHN HAUSER AND THE INTERNATIONAL COMPUTER SCIENCE INSTITUTE
(possibly via similar legal notice) AGAINST ALL LOSSES, COSTS, OR OTHER
PROBLEMS INCURRED BY THEIR CUSTOMERS AND CLIENTS DUE TO THE SOFTWARE, OR
INCURRED BY ANYONE DUE TO A DERIVATIVE WORK THEY CREATE USING ANY PART OF THE
SOFTWARE.

Derivative works require also that (1) the source code for the derivative work
includes prominent notice that the work is derivative, and (2) the source code
includes prominent notice of these three paragraphs for those parts of this
code that are retained.

=============================================================================*/

/*----------------------------------------------------------------------------
| Include common integer types and flags.
*----------------------------------------------------------------------------*/
#include "onfproc.h"

/*----------------------------------------------------------------------------
| Symbolic Boolean literals.
*----------------------------------------------------------------------------*/
enum {
    FALSE = 0,
    TRUE  = 1
};

