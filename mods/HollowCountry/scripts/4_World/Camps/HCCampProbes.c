// HC-16 / #143 supersedes LC-T416's abstract raider combat and casualties.
// Eligibility remains a scheduling policy, not evidence of physical attackers.
// Native scripts-1.30.164289: 1_Core/proto/EnDebug.c:96 Print.
class HCCampProbes
{
    static bool Eligible(int tier, int day, int now, int last, bool hidden)
    {
        if (tier != 3 || day < 14 || hidden || now < 1 || now < last) { return false; }
        if (last > 0 && now - last < 259200) { return false; }
        return true;
    }

    static void Step(HCCampModule module, HCCampRecord camp, HCCampScan scan, bool burning, int now)
    {
        if (camp.ProbePhase > 0)
        {
            // Clear old abstract leases once; never turn them into casualties.
            camp.ProbePhase = 0;
            camp.ProbeUntil = 0;
            if (!module.Commit(now)) { return; }
        }
        if (!Eligible(camp.Tier, HCEscalationClock.Day(), now, camp.LastProbe, scan.Hidden(burning))) { return; }
        camp.LastProbe = now;
        if (!module.Commit(now)) { return; }
        Print("[HC Plan] HC-16 camp=" + camp.Id + " level=" + camp.Tier.ToString() + " supply=0 roles=0 state=refused refusal=PROBE_PARTY_NOT_OBSERVED runtime=PENDING");
    }
}
