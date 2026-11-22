// Human AI population policy; source/package only, runtime acceptance pending.
// Native snapshot 1.30.164289: EnString.c:199 Length, :240 IndexOf, :448 Get;
// EnScript.c:380 Count, :407 Insert, :470 RemoveOrdered; EnDebug.c:96 Print.
// All safety ceilings live here. Distances/work/loot/history are separate quotas.
class HCAILimits
{
    static const int GROUP_CEILING = 24;
    static const int AI_CEILING = 128;
    static const int SIZE_CEILING = 12;
    static const int WORLD_CEILING = 128;
    protected static ref HCAILimits s_Effective;
    // Raised-weapon caution ranges (metres), cached once from the loaded limits by Use().
    // HCStancePolicy.Evaluate reads these; defaults hold until settings load.
    static float CAUTION_RANGE = 30;
    static float CAUTION_HOSTILE_RANGE = 60;
    static float CAUTION_GUNFIRE_RANGE = 80;
    int MaxLiveGroups = 15;
    int MaxLiveAI = 72;
    int OccupationMin = 3;
    int OccupationMax = 8;
    int HoldoutMin = 3;
    int HoldoutMax = 6;
    int PartyMin = 2;
    int PartyMax = 6;
    int PatrolMin = 2;
    int PatrolMax = 5;
    int CampMin = 2;
    int CampMax = 6;
    int MaxOccupiedPlaces = 15;
    int MaxParties = 24;
    int MaxMaterialized = 15;
    int FactionStrengthMax = 24;
    int MaxActiveSites = 15;
    int MaxActiveAI = 72;
    int MaxEncounters = 15;
    int MaxObservedAI = 1024;
    int MaxHoldouts = 48;
    int MaxCamps = 32;
    int MaxCampItems = 64;
    int WorldSeed = 18473;
    int CautionRangeM = 30;
    int CautionHostileRangeM = 60;
    int CautionGunfireRangeM = 80;

    static HCAILimits Get()
    {
        if (!s_Effective) { s_Effective = new HCAILimits; }
        return s_Effective;
    }
    static void Use(HCAILimits limits)
    {
        s_Effective = limits;
        HCWorldLimits.HOLDOUTS = limits.MaxHoldouts;
        HCWorldLimits.PARTIES = limits.MaxParties;
        HCAILimits.CAUTION_RANGE = limits.CautionRangeM;
        HCAILimits.CAUTION_HOSTILE_RANGE = limits.CautionHostileRangeM;
        HCAILimits.CAUTION_GUNFIRE_RANGE = limits.CautionGunfireRangeM;
        limits.Log();
    }
    static int Value(string key, int value, int low, int high)
    {
        if (value >= low && value <= high) { return value; }
        int clamped = low;
        if (value > high) { clamped = high; }
        Print("[HC AI] invalid AILimits." + key + " value=" + value.ToString() + " clamped=" + clamped.ToString());
        return clamped;
    }
    void Validate()
    {
        MaxLiveGroups = HCAILimits.Value("MaxLiveGroups", MaxLiveGroups, 1, 24);
        MaxLiveAI = HCAILimits.Value("MaxLiveAI", MaxLiveAI, 1, 128);
        OccupationMin = HCAILimits.Value("OccupationMin", OccupationMin, 1, 12);
        OccupationMax = HCAILimits.Value("OccupationMax", OccupationMax, 1, 12);
        HoldoutMin = HCAILimits.Value("HoldoutMin", HoldoutMin, 1, 12);
        HoldoutMax = HCAILimits.Value("HoldoutMax", HoldoutMax, 1, 12);
        PartyMin = HCAILimits.Value("PartyMin", PartyMin, 1, 12);
        PartyMax = HCAILimits.Value("PartyMax", PartyMax, 1, 12);
        PatrolMin = HCAILimits.Value("PatrolMin", PatrolMin, 1, 12);
        PatrolMax = HCAILimits.Value("PatrolMax", PatrolMax, 1, 12);
        CampMin = HCAILimits.Value("CampMin", CampMin, 1, 12);
        CampMax = HCAILimits.Value("CampMax", CampMax, 1, 12);
        MaxOccupiedPlaces = HCAILimits.Value("MaxOccupiedPlaces", MaxOccupiedPlaces, 1, 64);
        MaxParties = HCAILimits.Value("MaxParties", MaxParties, 1, 128);
        MaxMaterialized = HCAILimits.Value("MaxMaterialized", MaxMaterialized, 1, 24);
        FactionStrengthMax = HCAILimits.Value("FactionStrengthMax", FactionStrengthMax, 1, 128);
        MaxActiveSites = HCAILimits.Value("MaxActiveSites", MaxActiveSites, 1, 24);
        MaxActiveAI = HCAILimits.Value("MaxActiveAI", MaxActiveAI, 1, 128);
        MaxEncounters = HCAILimits.Value("MaxEncounters", MaxEncounters, 1, 24);
        MaxObservedAI = HCAILimits.Value("MaxObservedAI", MaxObservedAI, 1, 8192);
        MaxHoldouts = HCAILimits.Value("MaxHoldouts", MaxHoldouts, 24, 128);
        MaxCamps = HCAILimits.Value("MaxCamps", MaxCamps, 1, 128);
        MaxCampItems = HCAILimits.Value("MaxCampItems", MaxCampItems, 1, 128);
        WorldSeed = HCAILimits.Value("WorldSeed", WorldSeed, 0, 1000003);
        // Older operator files lack these keys; a zero-filled read restores the default.
        if (CautionRangeM == 0) { CautionRangeM = 30; }
        if (CautionHostileRangeM == 0) { CautionHostileRangeM = 60; }
        if (CautionGunfireRangeM == 0) { CautionGunfireRangeM = 80; }
        CautionRangeM = HCAILimits.Value("CautionRangeM", CautionRangeM, 1, 100);
        CautionHostileRangeM = HCAILimits.Value("CautionHostileRangeM", CautionHostileRangeM, 1, 100);
        CautionGunfireRangeM = HCAILimits.Value("CautionGunfireRangeM", CautionGunfireRangeM, 1, 100);
        if (OccupationMin > OccupationMax)
        {
            Print("[HC AI] invalid AILimits.OccupationMin / AILimits.OccupationMax reversed; defaults restored");
            OccupationMin = 3;
            OccupationMax = 8;
        }
        if (HoldoutMin > HoldoutMax)
        {
            Print("[HC AI] invalid AILimits.HoldoutMin / AILimits.HoldoutMax reversed; defaults restored");
            HoldoutMin = 3;
            HoldoutMax = 6;
        }
        if (PartyMin > PartyMax)
        {
            Print("[HC AI] invalid AILimits.PartyMin / AILimits.PartyMax reversed; defaults restored");
            PartyMin = 2;
            PartyMax = 6;
        }
        if (PatrolMin > PatrolMax)
        {
            Print("[HC AI] invalid AILimits.PatrolMin / AILimits.PatrolMax reversed; defaults restored");
            PatrolMin = 2;
            PatrolMax = 5;
        }
        if (CampMin > CampMax)
        {
            Print("[HC AI] invalid AILimits.CampMin / AILimits.CampMax reversed; defaults restored");
            CampMin = 2;
            CampMax = 6;
        }
    }
    void Log()
    {
        Print("[HC AI] limits groups=" + MaxLiveGroups.ToString() + " ai=" + MaxLiveAI.ToString() + " occupation=" + OccupationMin.ToString() + "-" + OccupationMax.ToString() + " holdout=" + HoldoutMin.ToString() + "-" + HoldoutMax.ToString() + " party=" + PartyMin.ToString() + "-" + PartyMax.ToString() + " patrol=" + PatrolMin.ToString() + "-" + PatrolMax.ToString() + " camp=" + CampMin.ToString() + "-" + CampMax.ToString() + " occupied=" + MaxOccupiedPlaces.ToString() + " parties=" + MaxParties.ToString() + " materialized=" + MaxMaterialized.ToString() + " strength=" + FactionStrengthMax.ToString() + " sites=" + MaxActiveSites.ToString() + " site_ai=" + MaxActiveAI.ToString() + " encounters=" + MaxEncounters.ToString() + " holdouts=" + MaxHoldouts.ToString() + " camps=" + MaxCamps.ToString() + " camp_items=" + MaxCampItems.ToString() + " observed_ai=" + MaxObservedAI.ToString() + " seed=" + WorldSeed.ToString() + " provisional=1 runtime=PENDING");
    }
    static int Minimum(string kind)
    {
        if (kind == "occupation") { return Get().OccupationMin; }
        if (kind == "holdout" || kind == "HOLDOUT") { return Get().HoldoutMin; }
        if (kind == "patrol" || kind == "PATROL") { return Get().PatrolMin; }
        if (kind == "camp" || kind == "VISITOR") { return Get().CampMin; }
        return Get().PartyMin;
    }
    static int Maximum(string kind)
    {
        if (kind == "occupation") { return Get().OccupationMax; }
        if (kind == "holdout" || kind == "HOLDOUT") { return Get().HoldoutMax; }
        if (kind == "patrol" || kind == "PATROL") { return Get().PatrolMax; }
        if (kind == "camp" || kind == "VISITOR") { return Get().CampMax; }
        return Get().PartyMax;
    }
    // Explicit world seed, bounded hash arithmetic; independent of player count,
    // process RNG and creation order. Never redraw a surviving group's population.
    static int GroupSize(int seed, string rowId, string kind)
    {
        int hash = seed % 1000003;
        string alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-.:/";
        HCTextWindow rowText = new HCTextWindow(rowId);
        for (int index = 0; index < rowText.Length(); index++)
        {
            hash = (hash * 31 + alphabet.IndexOf(rowText.At(index)) + 1) % 1000003;
        }
        int low = Minimum(kind);
        return low + hash % (Maximum(kind) - low + 1);
    }
}

class HCAIReservation
{
    string Id;
    int Actors;
}

// One server process, one ledger for materializer, authored sites and adapter.
// Reserve full deferred groups before external side effects. Unknown custody is
// retained even above a newly lowered limit; no timeout releases possible bodies.
class HCAIBudget
{
    protected static ref array<ref HCAIReservation> s_Rows = new array<ref HCAIReservation>;
    protected static bool s_Blocked;
    static int Actors()
    {
        int total = 0;
        foreach (HCAIReservation row : s_Rows) { total += row.Actors; }
        return total;
    }
    static int Groups() { return s_Rows.Count(); }
    static bool Fits(int actors)
    {
        return !s_Blocked && actors >= 1 && actors <= HCAILimits.SIZE_CEILING && Groups() < HCAILimits.Get().MaxLiveGroups && Actors() <= HCAILimits.Get().MaxLiveAI - actors;
    }
    static bool TryReserve(string id, int actors)
    {
        if (s_Blocked) { return false; }
        foreach (HCAIReservation prior : s_Rows)
        {
            if (prior.Id == id) { return prior.Actors == actors; }
        }
        if (!Fits(actors)) { return false; }
        HCAIReservation row = new HCAIReservation;
        row.Id = id;
        row.Actors = actors;
        s_Rows.Insert(row);
        return true;
    }
    static void Restore(string id, int actors)
    {
        foreach (HCAIReservation prior : s_Rows) { if (prior.Id == id) { return; } }
        HCAIReservation row = new HCAIReservation;
        row.Id = id;
        row.Actors = actors;
        s_Rows.Insert(row);
        if (Groups() > HCAILimits.Get().MaxLiveGroups || Actors() > HCAILimits.Get().MaxLiveAI)
        {
            Print("[HC AI] custody exceeds configured budget; retained; new AI refused");
        }
    }
    static void Block() { s_Blocked = true; }
    static void Release(string id)
    {
        for (int index = 0; index < s_Rows.Count(); index++)
        {
            if (s_Rows[index].Id == id) { s_Rows.RemoveOrdered(index); return; }
        }
    }
}
