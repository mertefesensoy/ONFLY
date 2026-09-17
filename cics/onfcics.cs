// ONFLY: the EXEC CICS LINK target (Phase G, P-22 approved by D-396).
//
// WHAT THIS IS
//   Section 3.7 says "ONFLYENG will be LINKed with the COMMAREA of IR-COM".
//   On z/OS that LINK target is a C program.  Raincode's COBOL compiles to
//   .NET and cannot link a C89 object, so on this host the target is this
//   module, which is a thin shell over the same C89 engine: it P/Invokes
//   engine/src/onfcics.c, which drives engine/src/onfreq.c's shared request
//   sequence -- the very code the batch engine, the MVS driver and the golden
//   harness run.  Nothing here simulates anything.
//
// WHY IT IS LAYOUT-BLIND
//   This file names no field and no offset of the 412-byte record, and does
//   not even state its length: onfclen() reports it, out of the generated
//   header, out of layout/master.py.  IR-COM-01 says the layout is defined
//   once and generated; a hand-written C# view of it would be a third copy
//   beside the COBOL copybook and the C header, free to drift from both.  So
//   the module copies opaque bytes and lets the two generated sides agree.
//
// THE THREE THINGS MEASURED BEFORE THIS WAS WRITTEN (VL-117)
//   1. SetIsQIXModule() in the constructor is REQUIRED.  Without it the LINK
//      abends "Module ONFLYENG not compiled as a QIX module but called using
//      QIX LINK".  [RainCodeExport] alone is enough for a COBOL CALL and is
//      not enough for a LINK.  Do not delete it as dead code; it has no
//      caller and it is load-bearing.
//   2. The COMMAREA is parameter 0, arity 1.  There is no separate DFHEIBLK.
//   3. GetParameterAddress(...).Size reports the address-space slice -- it
//      was 257,448 on the probe, for a 16-byte record.  It is NEVER a length.
//      The length is onfclen(), and the C adapter checks it again.
using System;
using System.Runtime.InteropServices;
using RainCodeLegacyRuntime.Core;
using RainCodeLegacyRuntime.Module;
using RainCodeLegacyRuntime.Module.Attribute;

namespace Onfly.Cics
{
    [RainCodeExport("ONFLYENG")]
    public class ONFLYENG : BaseModule<ONFLYENG>
    {
        // The native engine.  Built by tools/cicsbld.py from the same sources
        // the batch engine is built from, with the native float backend --
        // admitted on x86 by NR-09.
        private const string ENGINE = "onflyeng";

        [DllImport(ENGINE, CallingConvention = System.Runtime.InteropServices.CallingConvention.Cdecl)]
        private static extern IntPtr onfcini(
            [MarshalAs(UnmanagedType.LPStr)] string netpath, out int rc);

        [DllImport(ENGINE, CallingConvention = System.Runtime.InteropServices.CallingConvention.Cdecl)]
        private static extern int onfcrun(IntPtr h, byte[] ca, int len);

        [DllImport(ENGINE, CallingConvention = System.Runtime.InteropServices.CallingConvention.Cdecl)]
        private static extern void onfcend(IntPtr h);

        [DllImport(ENGINE, CallingConvention = System.Runtime.InteropServices.CallingConvention.Cdecl)]
        private static extern int onfclen();

        // Section 3.7: "The network will be loaded once at region startup into
        // shared storage and anchored for all tasks; transactions only read
        // it."  This field is that anchor.  It is an INSTANCE field, not a
        // static: the module dictionary creates one module per run unit, so
        // one run unit holds one network, and two run units cannot share a
        // half-initialised one.
        private IntPtr anchor = IntPtr.Zero;
        private int anchorRc;

        // Where the network comes from.  IR-JCL-01 names the batch DD ONFNET;
        // the environment variable of the same name is this host's nearest
        // equivalent, and on a real region it would be region configuration.
        // There is deliberately NO default path: a transaction that silently
        // simulated some other network would be worse than one that refuses.
        private const string NETVAR = "ONFNET";

        public ONFLYENG()
        {
            // Finding 1 of VL-117.  Load-bearing; see the header comment.
            SetIsQIXModule();
        }

        private bool Anchor()
        {
            if (anchor != IntPtr.Zero)
            {
                return true;
            }
            string path = Environment.GetEnvironmentVariable(NETVAR);
            if (string.IsNullOrEmpty(path))
            {
                Console.WriteLine("ONF906S NETWORK DATASET UNREADABLE: "
                                  + NETVAR + " NOT SET");
                return false;
            }
            anchor = onfcini(path, out anchorRc);
            if (anchor == IntPtr.Zero)
            {
                // anchorRc is an ONF1nnE integrity code from onfdec/onfldp, or
                // an ONFC_* adapter code.  Reported as the number rather than
                // translated: Appendix E owns the texts, and a second copy of
                // them here could disagree with ONFLYDRV's.
                Console.WriteLine("ONF"
                                  + (anchorRc > 0 ? anchorRc.ToString("D3") : anchorRc.ToString())
                                  + "E NETWORK LOAD FAILED: " + path);
                return false;
            }
            Console.WriteLine("ONF001I NETWORK LOADED: " + path);
            return true;
        }

        protected override void Run(ExecutionContext ec, MemoryArea workMem,
                                    CallParameters parms)
        {
            if (!Anchor())
            {
                // No network: leave the COMMAREA exactly as it arrived.  The
                // transaction sees ONF-RC unchanged from what it set before
                // the LINK, which is why ONFCSUG sets it to a value the engine
                // never returns.
                return;
            }

            int len = onfclen();

            // Finding 3 of VL-117: the area's own Size is the address-space
            // slice.  len comes from the engine and nowhere else.
            MemoryArea area = parms.GetParameterAddress(ec, 0);

            byte[] rec = new byte[len];
            area.CopyTo(0, len, rec);

            int rc = onfcrun(anchor, rec, len);
            if (rc < 0)
            {
                // ONFC_EARG and friends.  The record is left untouched rather
                // than half-written: IR-JCL-03 makes the response portion a
                // function of the result, and there is no result.
                Console.WriteLine("ONF908S ENGINE REFUSED THE COMMAREA: " + rc);
                return;
            }

            MemoryArea.CopyFromBytesOffsetLength(rec, 0, len, area);
        }
    }
}
