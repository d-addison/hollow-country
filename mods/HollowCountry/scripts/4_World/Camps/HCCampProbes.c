// HC-16 / #143 supersedes LC-T416's abstract raider combat and casualties.
// Eligibility remains a scheduling policy, not evidence of physical attackers.
// Native scripts-1.30.164289: 1_Core/proto/EnDebug.c:96 Print;
// EnSystem.c:397 FileExist. No engine/Expansion actor request is invented.
class HCCampProbes
{
    protected static string s_Refusal;
    protected static bool s_AdmissionPrinted;
    protected static bool s_Enabled;

    static bool HCEnabled()
    {
        if (!s_AdmissionPrinted)
        {
            s_Enabled = !FileExist("$profile:HollowCountry/acceptance/camp_probes.disable");
            Print(HCV2Admission.Line("CampProbes", s_Enabled, "HC-16-PROBE", false) + " runtime=PENDING");
            s_AdmissionPrinted = true;
        }
        return s_Enabled;
    }

    static void HCStart()
    {
        if (HCEnabled())
        {
            HCBaseRaid.HCEnabled();
            if (!HCBaseRaid.HCGet()) { HCRefuse("PROBE_PLAYER_BASE_DISPATCH_UNAVAILABLE"); }
        }
    }

    static void HCRefuse(string reason)
    {
        if (s_Refusal == reason) { return; }
        s_Refusal = reason;
        Print("[HC Plan] HC-16 probes=dispatch_pending reason=" + reason + " runtime=PENDING");
    }

    static bool Eligible(int tier, int day, int now, int last, bool hidden)
    {
        if (tier != 3 || day < 14 || hidden || now < 1 || now < last) { return false; }
        if (last > 0 && now - last < 259200) { return false; }
        return true;
    }

    static void Step(HCCampModule module, HCCampRecord camp, HCCampScan scan, bool burning, int now)
    {
        if (!HCEnabled()) { return; }
        if (camp.ProbePhase > 0)
        {
            // Clear old abstract leases once; never turn them into casualties.
            camp.ProbePhase = 0;
            camp.ProbeUntil = 0;
            if (!module.Commit(now)) { return; }
        }
        if (!Eligible(camp.Tier, HCEscalationClock.Day(), now, camp.LastProbe, scan.Hidden(burning))) { return; }
        HCBaseRaid.HCWarn(module, camp, scan, now);
    }
}
