// LC-T413 / EXP-L8. Abstract visitors only; no AI bodies or generated props.
// Native evidence scripts-1.30.164289: 3_Game/Global/Game.c:931 GetWorld;
// 3_Game/Global/World.c:28 GetDate. Notifications/UTC/persistence use HCCampModule.
// 1_Core/proto/EnDebug.c:96 Print; 1_Core/proto/EnConvert.c:30 int.ToString.
class HCCampVisitors
{
    static bool Dusk()
    {
        int year;
        int month;
        int day;
        int hour;
        int minute;
        GetGame().GetWorld().GetDate(year, month, day, hour, minute);
        return hour >= 17 && hour < 21;
    }

    static void Step(HCCampModule module, HCCampRecord camp, HCCampScan scan, bool burning, int now)
    {
        string signal = scan.Signal(burning);
        if (signal != camp.Signal)
        {
            camp.Signal = signal;
            if (now - camp.LastSignal >= 1800)
            {
                camp.LastSignal = now;
                if (!module.Commit(now)) { return; }
                Print("[HollowCountry] V2 camps signal camp=" + camp.Id + " state=" + signal);
                if (signal == "tripwire" && camp.Neighbours > 0)
                {
                    module.Tell(camp, "Your neighbours point out the armed tripwire near camp.");
                }
            }
        }
        if (camp.Tier < 1 || !Dusk() || scan.Hidden(burning) || scan.Flag == "closed" || scan.Flag == "caution") { return; }
        int interval = 86400;
        if (signal == "signal-fire" || signal == "megaphone" || signal == "chemlight-trail") { interval = 43200; }
        if (camp.LastVisit > 0 && now - camp.LastVisit < interval) { return; }
        camp.LastVisit = now;
        bool settle = camp.Tier >= 2 && !camp.NeighboursSettled && !camp.NeighboursLost;
        if (settle) { camp.Neighbours = HCAILimits.GroupSize(HCAILimits.Get().WorldSeed, camp.Id, "camp"); camp.NeighboursSettled = true; }
        if (!module.Commit(now)) { return; }
        module.Fact(camp, "camp_visitor", 0);
        string message = "At dusk, travellers have passed nearby, leaving signs of a brief stop.";
        if (signal == "chemlight-trail") { message = "At dusk, travellers followed the lit chemlights past camp."; }
        if (settle) { message = "Refugees have settled nearby. Their presence is known through messages and signs of life."; }
        module.Tell(camp, message);
        Print("[HollowCountry] V2 camps visitor camp=" + camp.Id + " neighbours=" + camp.Neighbours.ToString() + " abstract=1");
    }

    // Server-only casualty seam for a future leased-body bridge, also used by
    // an announced abstract raid. Loss is permanent for this group this wipe.
    static void LoseNeighbours(HCCampModule module, HCCampRecord camp, int now)
    {
        if (camp.NeighboursLost || camp.Neighbours < 1) { return; }
        camp.Neighbours = 0;
        camp.NeighboursLost = true;
        if (!module.Commit(now)) { return; }
        module.Fact(camp, "camp_neighbours_lost", 2);
        module.Tell(camp, "The refugees nearby did not survive the raid. No replacement group will settle here.");
        Print("[HollowCountry] V2 camps neighbours-lost camp=" + camp.Id + " permanent=1 abstract=1");
    }
}
