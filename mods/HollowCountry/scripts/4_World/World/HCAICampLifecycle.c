// HC-16 / #143 -> LC-T408/413/416. Finite logical logistics, never native
// inventory. Founding reserves are authored ONCE in holdouts schema 2; no CE
// item creation, replenishment, recruitment or fake eating/repair receipts.
// Stages: -1 absent, 0 passing bivouac, 1 household, 2 stable camp, 3 hub.
// Engine inventory + journal continuation is a separate, refused experiment.
// Native scripts-1.30.164289: 1_Core/proto/EnScript.c:380,407 Count/Insert.
class HCAICampPolicy
{
    int FoundingStock = 48;
    int FoundingPopulation = 12;
    int CampAllocation = 24;
    int BivouacCost = 1;
    int HouseholdCost = 2;
    int StableCost = 4;
    int HubCost = 8;
    int GrowthSeconds = 3600;
    int UpkeepSeconds = 86400;
    int RaidLockoutSeconds = 604800;
    int RoleSeconds = 120;
    // Existing holdout BindOccupant envelope (30 m), 3% of the approximately
    // 1000 m vanilla network bubble / rifle hearing range. Not a perception boost.
    int RoutineRangeMeters = 30;
    // Installed eAIBase.OverrideTargetPosition default, local arrival only.
    int ArrivalToleranceMeters = 1;

    bool HCValid()
    {
        if (FoundingStock < 1 || FoundingStock > 256 || FoundingPopulation < 1 || FoundingPopulation > 128) { return false; }
        if (CampAllocation < 1 || CampAllocation > FoundingStock) { return false; }
        if (BivouacCost < 1 || HouseholdCost < 1 || StableCost < 1 || HubCost < 1) { return false; }
        if (BivouacCost + HouseholdCost + StableCost + HubCost > CampAllocation) { return false; }
        if (GrowthSeconds < 60 || UpkeepSeconds < 3600 || RaidLockoutSeconds != 604800) { return false; }
        if (GrowthSeconds > 604800 || UpkeepSeconds > 604800 || RaidLockoutSeconds > 2592000) { return false; }
        return RoleSeconds >= 60 && RoleSeconds <= 3600 && RoutineRangeMeters >= 1 && RoutineRangeMeters <= 30 && ArrivalToleranceMeters == 1;
    }
}

class HCAICampLife
{
    string Home;
    string Party;
    bool Allocated;
    int Population;
    int Supply;
    int Level = -1;
    int LastStage;
    int LastUpkeep;
    int ReoccupyAfter;
}

class HCAICampResources
{
    int Stock = 48;
    int Population = 12;
}

class HCAICampRoutineView
{
    ref HCWorldHoldout Home;
    int Level;
    int Supply;
    int Population;
}

class HCAICampLifecycle
{
    static int HCCost(int level, HCAICampPolicy policy)
    {
        if (level == 0) { return policy.BivouacCost; }
        if (level == 1) { return policy.HouseholdCost; }
        if (level == 2) { return policy.StableCost; }
        if (level == 3) { return policy.HubCost; }
        return 0;
    }

    static bool HCFound(HCAICampLife camp, HCAICampResources pool, array<ref HCAICampLife> homes, string party, int population, int now, HCAICampPolicy policy)
    {
        if (!camp || !pool || !homes || !policy || camp.Allocated || camp.Home == "" || party == "") { return false; }
        if (population < 1 || population > HCAILimits.SIZE_CEILING || now < 1) { return false; }
        if (pool.Stock < policy.CampAllocation || pool.Population < population) { return false; }
        foreach (HCAICampLife other : homes)
        {
            // Abandoned/dead homes retain their identity and allocation history.
            if (other != camp && other.Allocated && (other.Home == camp.Home || other.Party == party)) { return false; }
        }
        pool.Stock = pool.Stock - policy.CampAllocation;
        pool.Population = pool.Population - population;
        camp.Supply = policy.CampAllocation;
        camp.Population = population;
        camp.Party = party;
        camp.Allocated = true;
        camp.LastUpkeep = now;
        return true;
    }

    static bool HCGrow(HCAICampLife camp, int now, HCAICampPolicy policy)
    {
        if (!camp || !policy || !camp.Allocated || camp.Population < 1 || camp.Level >= 3) { return false; }
        if (now < 1 || now < camp.ReoccupyAfter || now < camp.LastStage) { return false; }
        if (camp.Level >= 0 && now - camp.LastStage < policy.GrowthSeconds) { return false; }
        int cost = HCCost(camp.Level + 1, policy);
        if (cost < 1 || camp.Supply < cost) { return false; }
        camp.Supply = camp.Supply - cost;
        camp.Level = camp.Level + 1;
        camp.LastStage = now;
        return true;
    }

    static bool HCUpkeep(HCAICampLife camp, int now, HCAICampPolicy policy)
    {
        if (!camp || !policy || !camp.Allocated || camp.Level < 0 || now < camp.LastUpkeep) { return false; }
        if (now - camp.LastUpkeep < policy.UpkeepSeconds) { return false; }
        // One interval per bounded step; retain overdue time, never refund it.
        camp.LastUpkeep = camp.LastUpkeep + policy.UpkeepSeconds;
        if (camp.Supply > 0) { camp.Supply = camp.Supply - 1; }
        else { camp.Level = camp.Level - 1; }
        return true;
    }

    static void HCRaid(HCAICampLife camp, int now, HCAICampPolicy policy)
    {
        if (!camp || !policy) { return; }
        camp.Level = -1;
        camp.ReoccupyAfter = now + policy.RaidLockoutSeconds;
        // Theft, absence and pressure are not evidence of death. No refund.
    }

    static bool HCDeath(HCAICampLife camp)
    {
        if (!camp || !camp.Allocated || camp.Population < 1) { return false; }
        camp.Population = camp.Population - 1;
        if (camp.Population == 0) { camp.Level = -1; }
        return true;
    }

    static bool HCValidLife(HCAICampLife camp, HCAICampPolicy policy)
    {
        if (!camp || !policy || camp.Level < -1 || camp.Level > 3) { return false; }
        if (camp.Population < 0 || camp.Population > HCAILimits.SIZE_CEILING || camp.Supply < 0 || camp.Supply > policy.CampAllocation) { return false; }
        if (camp.LastStage < 0 || camp.LastUpkeep < 0 || camp.ReoccupyAfter < 0) { return false; }
        if (!camp.Allocated) { return camp.Population == 0 && camp.Supply == 0 && camp.Level == -1 && camp.Party == ""; }
        return camp.Party != "" && (camp.Level < 0 || camp.Population > 0);
    }
}

// Existing snapshot service owns scheduling/serialization. This optional page
// emits <=16 logical camp points with a retained cursor; never scans entities
// or reports an unobserved actor/action as materialized.
class HCAICampDebug : HCDebugContributor
{
    HCHoldouts Owner;
    protected int m_Cursor;

    override void HCDescribe(HCDebugSnapshot snapshot)
    {
        if (!Owner || HCHoldouts.Get() != Owner || Owner.Count() == 0) { return; }
        int count = Math.Min(16, Owner.Count());
        for (int pointIndex = 0; pointIndex < count; pointIndex++)
        {
            m_Cursor = m_Cursor % Owner.Count();
            Owner.HCDescribeCamp(snapshot, m_Cursor);
            m_Cursor++;
        }
    }
}
