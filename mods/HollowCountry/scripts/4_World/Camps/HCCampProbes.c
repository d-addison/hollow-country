// LC-T416 / EXP-L1, EXP-L2 (admission EXP-L7 on parent module).
// Native evidence scripts-1.30.164289: 1_Core/proto/EnDebug.c:96 Print;
// 1_Core/proto/EnConvert.c:30 int.ToString.
// clocks and pressure delegate to existing HCEscalationClock. Abstract only:
// warnings, local signs as text, world facts; no bodies or structure damage.
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
            // Two abstract raiders retreat when faced by >=3 group members,
            // concealed lights-out camp, lost tier, or the bounded lease ending.
            if (module.NearMembers(camp, 80) >= 3 || scan.Hidden(burning) || camp.Tier != 3 || now >= camp.ProbeUntil)
            {
                camp.ProbePhase = 0;
                camp.ProbeUntil = 0;
                if (!module.Commit(now)) { return; }
                module.Tell(camp, "The raiders' warning has ended; the probing party has withdrawn.");
                module.Fact(camp, "camp_probe_retreat", 1);
                Print("[HollowCountry] V2 camps probe-retreat camp=" + camp.Id + " abstract=1");
                return;
            }
            if (camp.ProbePhase == 1 && now - camp.LastProbe >= 60)
            {
                camp.ProbePhase = 2;
                if (!module.Commit(now)) { return; }
                module.Tell(camp, "Signs of two raiders casing the camp have been reported. Keep watch.");
                module.Fact(camp, "camp_probe_signs", 1);
                Print("[HollowCountry] V2 camps probe-signs camp=" + camp.Id + " abstract=1");
                // Abstract casualties occur only after the warning and only
                // while unattended; never remove/kill any native entity.
                if (module.NearMembers(camp, 80) == 0 && HCEscalationClock.Pressure("raiders") >= 0.7)
                {
                    HCCampVisitors.LoseNeighbours(module, camp, now);
                }
            }
            return;
        }
        if (!Eligible(camp.Tier, HCEscalationClock.Day(), now, camp.LastProbe, scan.Hidden(burning))) { return; }
        camp.LastProbe = now;
        camp.ProbeUntil = now + 1200;
        camp.ProbePhase = 1;
        if (!module.Commit(now)) { return; }
        // Warning always precedes signs, casualties or any future materializer.
        module.Tell(camp, "Warning: two Volki have been reported approaching the camp. They will withdraw from a larger group.");
        module.Fact(camp, "camp_probe_warning", 1);
        Print("[HollowCountry] V2 camps probe-warning camp=" + camp.Id + " day=" + HCEscalationClock.Day().ToString() + " abstract=1");
    }
}
