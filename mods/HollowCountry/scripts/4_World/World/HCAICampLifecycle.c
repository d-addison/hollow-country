// HC-16 / #143 -> LC-T408/413/416. Finite logical logistics, never native
// inventory. Schema 3 returns unspent logical allocations once and slowly
// replenishes capped logical reserves. No CE items or fake action receipts.
// Stages: -1 absent, 0 passing bivouac, 1 household, 2 stable camp, 3 hub.
// Engine inventory + journal continuation is a separate, refused experiment.
// Native scripts-1.30.164289: 1_Core/proto/EnScript.c:380,407 Count/Insert.
// 1_Core/proto/EnMath.c:553,566 Min/Max; EnConvert.c:27 int.MAX.

class HCAICampLife
{
    string Home;
    string Party;
    bool Allocated;
    // Retain identity and living population; only supply can be returned.
    bool Refunded;
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
    int ReserveAt;
    int Refunded;
}

class HCAICampRoutineView
{
    ref HCWorldHoldout Home;
    int Level;
    int Supply;
    int Population;
}

// Optional current operator timing, separate from the durable camp journal.
// Native EnSystem.c:397 FileExist; JsonFileLoader.c:69 LoadData. Bounded reads
// reuse HCProfileDefaults. No file means migrate historical shipped defaults.
class HCAICampRespawnConfig
{
    int RaidLockoutSeconds;
}

class HCAICampLifecycle
{
    static int HCConfiguredLockout()
    {
        string path = "$profile:HollowCountry/ai-camp-policy.json";
        if (!FileExist(path)) { return 0; }
        string text = HCProfileDefaults.ReadText(path);
        HCAICampRespawnConfig configured;
        string error;
        if (!JsonFileLoader<HCAICampRespawnConfig>.LoadData(text, configured, error) || !configured) { return -1; }
        if (!HCJsonFields.Has(text, "RaidLockoutSeconds")) { return -1; }
        if (!HCOperatorSettingsRegistry.HCValid("AICamps.RaidLockoutSeconds", configured.RaidLockoutSeconds)) { return -1; }
        return configured.RaidLockoutSeconds;
    }

    static bool HCReserveDue(HCAICampResources pool, int now, HCAICampPolicy policy)
    {
        if (!pool || !policy || now < 1 || now < pool.ReserveAt) { return false; }
        return pool.ReserveAt == 0 || now - pool.ReserveAt >= policy.ReserveDaySeconds;
    }

    static bool HCReplenish(HCAICampResources pool, array<ref HCAICampLife> homes, int now, HCAICampPolicy policy)
    {
        if (!pool || !homes || !policy || now < 1 || now < pool.ReserveAt) { return false; }
        // Fresh images establish an epoch; they receive no retrospective credit.
        if (pool.ReserveAt == 0) { pool.ReserveAt = now; return true; }
        int days = (now - pool.ReserveAt) / policy.ReserveDaySeconds;
        if (days < 1) { return false; }
        // Consume every elapsed whole day even at cap. Keep the fraction, and
        // clamp BEFORE multiplying to avoid overflow after very long downtime.
        pool.ReserveAt = now - (now - pool.ReserveAt) % policy.ReserveDaySeconds;
        int stockDays = Math.Min(days, policy.ReserveCap);
        pool.Stock = Math.Min(policy.ReserveCap, pool.Stock + stockDays * policy.ReserveRegenPerDay);
        int living = 0;
        foreach (HCAICampLife home : homes) { living += home.Population; }
        int populationCap = Math.Max(0, policy.ReservePopulationCap - living);
        int populationDays = Math.Min(days, policy.ReservePopulationCap);
        pool.Population = Math.Min(populationCap, pool.Population + populationDays * policy.ReservePopulationRegenPerDay);
        return true;
    }

    static bool HCRefund(HCAICampLife camp, HCAICampResources pool, HCAICampPolicy policy)
    {
        if (!camp || !pool || !policy || !camp.Allocated || camp.Refunded || camp.Level >= 0) { return false; }
        int returned = Math.Min(camp.Supply, policy.ReserveCap - pool.Stock);
        pool.Stock += returned;
        // Diagnostic lifetime total stops before overflow. It never funds camps.
        if (pool.Refunded <= int.MAX - returned) { pool.Refunded += returned; }
        camp.Supply = 0;
        camp.Refunded = true;
        return true;
    }

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
        if (!camp || !pool || !homes || !policy || camp.Home == "" || party == "") { return false; }
        if (camp.Allocated && !camp.Refunded) { return false; }
        if (population < 1 || population > HCAILimits.SIZE_CEILING || now < 1) { return false; }
        if (now < camp.ReoccupyAfter || population < camp.Population) { return false; }
        int recruits = population - camp.Population;
        if (pool.Stock < policy.CampAllocation || pool.Population < recruits) { return false; }
        foreach (HCAICampLife other : homes)
        {
            // Terminal homes retain identity; they cannot fund a second home.
            if (other != camp && other.Allocated && (other.Home == camp.Home || other.Party == party)) { return false; }
        }
        pool.Stock = pool.Stock - policy.CampAllocation;
        pool.Population = pool.Population - recruits;
        camp.Supply = policy.CampAllocation;
        camp.Population = population;
        camp.Party = party;
        camp.Allocated = true;
        camp.Refunded = false;
        camp.LastUpkeep = now;
        return true;
    }

    static bool HCGrow(HCAICampLife camp, int now, HCAICampPolicy policy)
    {
        if (!camp || !policy || !camp.Allocated || camp.Population < 1 || camp.Level >= 3) { return false; }
        if (camp.Refunded) { return false; }
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
        if (camp.Refunded) { return false; }
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
        // Theft, absence and pressure are not evidence of death. The owner
        // refunds only unspent supply in the same verified terminal image.
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
        if (!camp.Allocated) { return !camp.Refunded && camp.Population == 0 && camp.Supply == 0 && camp.Level == -1 && camp.Party == ""; }
        if (camp.Refunded && (camp.Supply != 0 || camp.Level != -1)) { return false; }
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

class HCAICampPolicy
{
    int FoundingStock = 48;
    int FoundingPopulation = 12;
    int CampAllocation = 24;
    // Shared HCWorldClock uses UTC world days, not the accelerated sky date.
    // Two seed camps, then one allocation / two days up to six reserves.
    // Existing AILimits still owns occupied places and materialized actors.
    int ReserveCap = 144;
    int ReserveRegenPerDay = 12;
    int ReserveDaySeconds = 86400;
    int ReservePopulationCap = 36;
    int ReservePopulationRegenPerDay = 3;
    int BivouacCost = 1;
    int HouseholdCost = 2;
    int StableCost = 4;
    int HubCost = 8;
    int GrowthSeconds = 3600;
    int UpkeepSeconds = 86400;
    int RaidLockoutSeconds = 1800;
    int RoleSeconds = 120;
    // Existing holdout BindOccupant envelope (30 m), 3% of the approximately
    // 1000 m vanilla network bubble / rifle hearing range. Not a perception boost.
    int RoutineRangeMeters = 30;
    // Installed eAIBase.OverrideTargetPosition default, local arrival only.
    int ArrivalToleranceMeters = 1;

    bool HCValid()
    {
        if (!HCOperatorSettingsRegistry.HCValid("AICamps.FoundingStock", FoundingStock) || FoundingStock < 1 || FoundingStock > 256) { return false; }
        if (!HCOperatorSettingsRegistry.HCValid("AICamps.FoundingPopulation", FoundingPopulation) || FoundingPopulation < 1 || FoundingPopulation > 128) { return false; }
        if (!HCOperatorSettingsRegistry.HCValid("AICamps.CampAllocation", CampAllocation) || CampAllocation < 1 || CampAllocation > 256) { return false; }
        if (!HCOperatorSettingsRegistry.HCValid("AICamps.ReserveCap", ReserveCap) || ReserveCap < 1 || ReserveCap > 256) { return false; }
        if (!HCOperatorSettingsRegistry.HCValid("AICamps.ReserveRegenPerDay", ReserveRegenPerDay) || ReserveRegenPerDay < 1 || ReserveRegenPerDay > 256) { return false; }
        if (!HCOperatorSettingsRegistry.HCValid("AICamps.ReserveDaySeconds", ReserveDaySeconds) || ReserveDaySeconds < 3600 || ReserveDaySeconds > 604800) { return false; }
        if (!HCOperatorSettingsRegistry.HCValid("AICamps.ReservePopulationCap", ReservePopulationCap) || ReservePopulationCap < 1 || ReservePopulationCap > 128) { return false; }
        if (!HCOperatorSettingsRegistry.HCValid("AICamps.ReservePopulationRegenPerDay", ReservePopulationRegenPerDay) || ReservePopulationRegenPerDay < 1 || ReservePopulationRegenPerDay > 128) { return false; }
        if (!HCOperatorSettingsRegistry.HCValid("AICamps.BivouacCost", BivouacCost) || BivouacCost < 1 || BivouacCost > 256) { return false; }
        if (!HCOperatorSettingsRegistry.HCValid("AICamps.HouseholdCost", HouseholdCost) || HouseholdCost < 1 || HouseholdCost > 256) { return false; }
        if (!HCOperatorSettingsRegistry.HCValid("AICamps.StableCost", StableCost) || StableCost < 1 || StableCost > 256) { return false; }
        if (!HCOperatorSettingsRegistry.HCValid("AICamps.HubCost", HubCost) || HubCost < 1 || HubCost > 256) { return false; }
        if (!HCOperatorSettingsRegistry.HCValid("AICamps.GrowthSeconds", GrowthSeconds) || GrowthSeconds < 60 || GrowthSeconds > 604800) { return false; }
        if (!HCOperatorSettingsRegistry.HCValid("AICamps.UpkeepSeconds", UpkeepSeconds) || UpkeepSeconds < 3600 || UpkeepSeconds > 604800) { return false; }
        if (!HCOperatorSettingsRegistry.HCValid("AICamps.RaidLockoutSeconds", RaidLockoutSeconds) || RaidLockoutSeconds < 60 || RaidLockoutSeconds > 604800) { return false; }
        if (!HCOperatorSettingsRegistry.HCValid("AICamps.RoleSeconds", RoleSeconds) || RoleSeconds < 60 || RoleSeconds > 3600) { return false; }
        if (!HCOperatorSettingsRegistry.HCValid("AICamps.RoutineRangeMeters", RoutineRangeMeters) || RoutineRangeMeters < 1 || RoutineRangeMeters > 30) { return false; }
        if (!HCOperatorSettingsRegistry.HCValid("AICamps.ArrivalToleranceMeters", ArrivalToleranceMeters) || ArrivalToleranceMeters != 1) { return false; }
        if (FoundingStock < 1 || FoundingStock > 256 || FoundingPopulation < 1 || FoundingPopulation > 128) { return false; }
        if (CampAllocation < 1 || CampAllocation > FoundingStock) { return false; }
        if (ReserveCap < FoundingStock || ReserveCap > 256 || ReserveRegenPerDay < 1 || ReserveRegenPerDay > ReserveCap) { return false; }
        if (ReserveDaySeconds < 3600 || ReserveDaySeconds > 604800) { return false; }
        if (ReservePopulationCap < FoundingPopulation || ReservePopulationCap > 128) { return false; }
        if (ReservePopulationRegenPerDay < 1 || ReservePopulationRegenPerDay > ReservePopulationCap) { return false; }
        if (BivouacCost < 1 || HouseholdCost < 1 || StableCost < 1 || HubCost < 1) { return false; }
        if (BivouacCost + HouseholdCost + StableCost + HubCost > CampAllocation) { return false; }
        if (GrowthSeconds < 60 || UpkeepSeconds < 3600 || RaidLockoutSeconds < 60) { return false; }
        if (GrowthSeconds > 604800 || UpkeepSeconds > 604800 || RaidLockoutSeconds > 604800) { return false; }
        return RoleSeconds >= 60 && RoleSeconds <= 3600 && RoutineRangeMeters >= 1 && RoutineRangeMeters <= 30 && ArrivalToleranceMeters == 1;
    }
}
