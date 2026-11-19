// #144 scavenging run: bounded house stage, combat abort and the narrow house port.
// One in-memory run per trip; house goods use additive HC-34 carry receipts.
// No spawn/delete/refund; the existing native custody path unloads at observed home.
// House goods come only through the shared search reservation (HCSearchHouses), reached
// through HCPickHousePort; the base port is unbound and names that refusal.
// Native scripts-1.30.164289: 3_Game/Global/Game.c:914 GetTickTime, :930
// GetObjectsAtPosition3D; 3_Game/Entities/Object.c:287 GetPosition, :467 GetType,
// :873 ModelToWorld; 1_Core/proto/EnConvert.c:210 DistanceSq; EnScript.c:380 Count,
// :407 Insert, :470 RemoveOrdered; EnDebug.c:96 Print. Expansion calls stay in the
// addon walk port (HCWalkTo/HCPartyMembers/HCPartyInCombat). Runtime acceptance PENDING.
class HCPickHouseTarget
{
    House Dwelling;
    int SiteId;
    vector Point;
    string Key;
}

// Port to the shared house reservation. Tokens are opaque to the picker.
class HCPickHousePort
{
    string HCRefusal() { return "PICKER_HOUSE_PORT_UNBOUND"; }
    Class HCReserve(PlayerBase actor, HCPickHouseTarget target, string actorId) { return null; }
    bool HCCommit(Class token) { return false; }
    void HCRelease(Class token) { }
    EntityAI HCItem(Class token) { return null; }
}

// One bounded native scan around the source for houses that have authored search sites.
class HCPickHouseScan
{
    static void HCFind(vector centre, float radius, int maxTargets, int maxObjects, array<ref HCPickHouseTarget> targets)
    {
        if (!GetGame() || !HCInteriorTemplates.Loaded()) { return; }
        array<Object> objects = new array<Object>();
        array<CargoBase> cargos = new array<CargoBase>();
        GetGame().GetObjectsAtPosition3D(centre, radius, objects, cargos);
        if (objects.Count() > maxObjects) { return; }
        for (int scanIndex = 0; scanIndex < objects.Count(); scanIndex++)
        {
            if (targets.Count() >= maxTargets) { return; }
            House building = House.Cast(objects[scanIndex]);
            if (!building) { continue; }
            HCInteriorTemplate layout = HCInteriorTemplates.Template(building.GetType());
            if (!layout || !layout.SearchSites) { continue; }
            HCPickHouseTarget target = HCPickHouseScan.HCFirstSite(building, layout);
            if (target) { targets.Insert(target); }
        }
    }

    // First authored site with a valid shape; one candidate per building.
    static HCPickHouseTarget HCFirstSite(House building, HCInteriorTemplate layout)
    {
        array<ref HCInteriorTemplateSearchSite> sites = layout.SearchSites;
        int inspected = 0;
        foreach (HCInteriorTemplateSearchSite site : sites)
        {
            inspected++;
            if (inspected > HCSearchHouses.MAX_SITES) { return null; }
            if (!HCSearchHouses.SiteShapeValid(site)) { continue; }
            HCPickHouseTarget target = new HCPickHouseTarget;
            target.Dwelling = building;
            target.SiteId = site.Id;
            target.Point = building.ModelToWorld(Vector(site.Center[0], site.Center[1], site.Center[2]));
            vector at = building.GetPosition();
            target.Key = building.GetType() + ":" + Math.Round(at[0]).ToString() + ":" + Math.Round(at[2]).ToString();
            return target;
        }
        return null;
    }
}

// Per-trip run state. Methods take the port as an argument: no back-reference cycle.
class HCPickRunner
{
    static const string HOLD = "HOLD";
    string TripKey;
    string Stage;
    float CombatSince = -1;
    int Searched;
    int Attempts;
    int CurrentIndex = -1;
    float StageAt;
    bool BackIssued;
    string GapLogged;
    Class HouseToken;
    ref array<ref HCPickHouseTarget> Targets = new array<ref HCPickHouseTarget>;
    ref array<string> Visited = new array<string>;

    void HCReset(HCScavengeInventory port)
    {
        HCDropToken(port);
        TripKey = "";
        Stage = "";
        CombatSince = -1;
        Searched = 0;
        Attempts = 0;
        CurrentIndex = -1;
        StageAt = 0;
        BackIssued = false;
        Targets.Clear();
        Visited.Clear();
    }

    void HCDropToken(HCScavengeInventory port)
    {
        if (HouseToken && port && port.Houses) { port.Houses.HCRelease(HouseToken); }
        HouseToken = null;
    }

    // "" proceed with the normal leg, HOLD = do nothing this tick, else the abort reason.
    string HCRun(HCScavengeInventory port, bool returning, HCScavengeState row)
    {
        HCPickerSurvey survey = port.Survey;
        if (!survey || !row) { return ""; }
        string key = row.LeaseId + ":" + row.Generation.ToString();
        if (key != TripKey)
        {
            HCReset(port);
            TripKey = key;
            if (!HCPickPolicy.Enabled()) { Stage = "off"; }
        }
        if (Stage == "off") { return ""; }
        int now = HCWorldClock.UTC();
        float tick = GetGame().GetTickTime();
        string reason = HCAbort(port, survey, tick);
        if (reason != "")
        {
            string clue = "COMBAT";
            if (reason == "RUN_ABORT_PARTY_BROKEN") { clue = "LOSS"; }
            return HCEnd(port, survey, row, reason, clue, now);
        }
        // No new movement or transfer step while the party is fighting.
        if (port.HCPartyInCombat()) { return HCPickRunner.HOLD; }
        if (returning)
        {
            HCDropToken(port);
            return port.HCCarryUnload(row);
        }
        string staged = HCHouseStage(port, survey, row, tick);
        if (staged != "" && staged != HCPickRunner.HOLD) { return HCEnd(port, survey, row, staged, "", now); }
        return staged;
    }

    string HCAbort(HCScavengeInventory port, HCPickerSurvey survey, float tick)
    {
        int members = port.HCPartyMembers();
        if (members >= 0 && members < survey.RunMinMembers) { return "RUN_ABORT_PARTY_BROKEN"; }
        if (!port.HCPartyInCombat())
        {
            CombatSince = -1;
            return "";
        }
        if (CombatSince < 0) { CombatSince = tick; }
        if (tick - CombatSince >= survey.RunCombatAbortSeconds) { return "RUN_ABORT_COMBAT"; }
        return "";
    }

    // The trip is lost by HCStep; cargo stays where it is and the patrol is restored.
    string HCEnd(HCScavengeInventory port, HCPickerSurvey survey, HCScavengeState row, string reason, string clue, int now)
    {
        HCDropToken(port);
        Stage = "off";
        if (clue != "" && port.Danger) { port.Danger.HCNote(row.RouteId, clue, now, survey.RunDangerClueSeconds, survey.RunDangerMaxClues); }
        Print("[HC Pickers] run end party=" + row.PartyId + " route=" + row.RouteId + " reason=" + reason + " houses=" + Searched.ToString() + " runtime=PENDING");
        return reason;
    }

    string HCHouseStage(HCScavengeInventory port, HCPickerSurvey survey, HCScavengeState row, float tick)
    {
        if (Stage == "done") { return ""; }
        if (Stage == "")
        {
            // The first leg to the source is the existing walk; houses start there.
            if (!port.HCAtSource()) { return ""; }
            if (survey.RunMaxHousesPerRun < 1) { Stage = "done"; return ""; }
            string gap = port.Houses.HCRefusal();
            if (gap != "")
            {
                HCGap(gap);
                Stage = "done";
                return "";
            }
            if (!HCServer.HCTickWork().HCTake(1)) { return HCPickRunner.HOLD; }
            Targets.Clear();
            HCPickHouseScan.HCFind(port.Source.GetPosition(), survey.RunHouseSearchRadiusMeters, survey.RunMaxHouseCandidates, survey.MaxScannedObjects, Targets);
            Stage = "pick";
        }
        // A reservation and commit need the current lease and a live carrier.
        if (!port.HCLive() || !port.HCPartyCurrent(row)) { return "RUN_ABORT_LEASE"; }
        if (Stage == "pick") { return HCPickNext(port, survey, tick); }
        if (Stage == "walk") { return HCWalkStep(port, survey, tick); }
        if (Stage == "search") { return HCSearchStep(port, survey, row, tick); }
        if (Stage == "back") { return HCBackStep(port, survey, tick); }
        return "";
    }

    void HCGap(string gap)
    {
        if (GapLogged == gap) { return; }
        GapLogged = gap;
        Print("[HC Pickers] run houses=skipped reason=" + gap + " runtime=PENDING");
    }

    int HCNearest(HCScavengeInventory port)
    {
        int best = -1;
        float bestGap = 0;
        for (int index = 0; index < Targets.Count(); index++)
        {
            if (Visited.Find(Targets[index].Key) >= 0) { continue; }
            float gap = vector.DistanceSq(port.Actor.GetPosition(), Targets[index].Point);
            if (best < 0 || gap < bestGap)
            {
                best = index;
                bestGap = gap;
            }
        }
        return best;
    }

    string HCPickNext(HCScavengeInventory port, HCPickerSurvey survey, float tick)
    {
        int next = -1;
        if (Searched < survey.RunMaxHousesPerRun && Attempts < survey.RunMaxHouseAttempts) { next = HCNearest(port); }
        if (next < 0) { return HCGoBack(port, tick); }
        HCPickHouseTarget target = Targets[next];
        Visited.Insert(target.Key);
        Attempts++;
        // A refused walk skips this house; Attempts and Visited bound the loop.
        if (!port.HCWalkTo(target.Point)) { return HCPickRunner.HOLD; }
        CurrentIndex = next;
        Stage = "walk";
        StageAt = tick;
        return HCPickRunner.HOLD;
    }

    string HCWalkStep(HCScavengeInventory port, HCPickerSurvey survey, float tick)
    {
        HCPickHouseTarget target = Targets[CurrentIndex];
        float reach = survey.ArrivalRangeMeters;
        if (vector.DistanceSq(port.Actor.GetPosition(), target.Point) > reach * reach)
        {
            if (tick - StageAt > survey.RunHouseWalkSeconds) { Stage = "pick"; }
            return HCPickRunner.HOLD;
        }
        HouseToken = port.Houses.HCReserve(port.Actor, target, port.HCActorKey());
        Stage = "pick";
        if (HouseToken)
        {
            Stage = "search";
            StageAt = tick;
        }
        return HCPickRunner.HOLD;
    }

    string HCSearchStep(HCScavengeInventory port, HCPickerSurvey survey, HCScavengeState row, float tick)
    {
        if (tick - StageAt < survey.RunHouseSearchSeconds) { return HCPickRunner.HOLD; }
        HCPickHouseTarget target = Targets[CurrentIndex];
        EntityAI goods = port.Houses.HCItem(HouseToken);
        if (!port.HCCarryPrepare(goods, row))
        {
            HCDropToken(port);
            return HCGoBack(port, tick);
        }
        bool committed = port.Houses.HCCommit(HouseToken);
        bool recorded = port.HCCarryResult(committed, row);
        string goodsClass = "";
        if (committed && goods) { goodsClass = goods.GetType(); }
        HCDropToken(port);
        if (!recorded) { return "RUN_ABORT_HOUSE_JOURNAL"; }
        string outcome = "refused";
        if (committed)
        {
            Searched++;
            outcome = "searched";
        }
        Print("[HC Pickers] run house=" + target.Key + " outcome=" + outcome + " item=" + goodsClass + " runtime=PENDING");
        Stage = "pick";
        return HCPickRunner.HOLD;
    }

    string HCGoBack(HCScavengeInventory port, float tick)
    {
        Stage = "back";
        StageAt = tick;
        BackIssued = false;
        return HCPickRunner.HOLD;
    }

    string HCBackStep(HCScavengeInventory port, HCPickerSurvey survey, float tick)
    {
        if (port.HCAtSource())
        {
            Stage = "done";
            return "";
        }
        if (tick - StageAt > survey.RunHouseWalkSeconds) { return "RUN_ABORT_BACK_TIMEOUT"; }
        if (!BackIssued) { BackIssued = port.HCWalkTo(port.Source.GetPosition()); }
        return HCPickRunner.HOLD;
    }
}
