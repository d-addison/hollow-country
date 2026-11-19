// S3 car repair: pure policy and config for HCXAICarRepair. No spawn, no
// teleport, no player position here. Native evidence, scripts-1.30.164289:
// 4_World/Entities/Vehicles/CarScript.c:1752 CheckOperationalRequirements
// (RUINED engine, NO_BATTERY, NO_IGNITER; NO_FUEL stays a fuel concern, not a part);
// 4_World/Classes/UserActionsComponent/Actions/Continuous/ActionRepairVehiclePartBase.c:36-66
// AdjustVehicleHealthServer (one level per step, clamped at WORN, band base plus jitter);
// ActionRepairCarEngine.c:41-48 (a RUINED Engine zone is not repairable by the action);
// 3_Game/Systems/Inventory/Inventory.c:276 FindFreeLocationFor, :1100
// TakeEntityAsTargetAttachmentEx (an occupied slot combines instead of replacing),
// :1223 DropEntity, 3_Game/Systems/Inventory/InventoryLocation.c:71 GetSlot.
// Offline tests never establish DayZ behavior; runtime acceptance is PENDING.

// Runtime-only description of one known car. Never serialized.
class HCXAICarEntry
{
    CarScript Subject;
    vector Pos;
    int WheelNeed = 0;
    int PartMask = 0;
    int EngineSteps = 0;
    bool Unrepairable = false;
    int ClaimGroup = 0;
    int ClaimUntil = 0;
    int Attempts = 0;
    int NextAt = 0;
}

// Mission data file ai/car-repair.json. Every tunable lives here, validated.
class HCXAICarRepairConfig
{
    int Version = 1;
    bool Enabled = true;
    float SearchRadiusMeters = 600.0;
    int MaxActiveGroups = 2;
    int MaxKnownCars = 512;
    int CooldownSeconds = 900;
    int ClaimSeconds = 1800;
    int WorkSecondsPerStep = 20;
    float WorkRangeMeters = 4.0;
    float StashRangeMeters = 15.0;
    float WalkMetersPerSecond = 1.6;
    int WalkSlackSeconds = 120;
    int MaxAttemptsPerCar = 3;
    int MaxScanItems = 96;
    int StepSeconds = 2;
    int MaxRouteNodes = 64;
    ref array<string> MechanicToolClasses = new array<string>();

    // JsonFileLoader zero-fills absent fields; restore the documented default.
    void HCApplyDefaults(string encoded)
    {
        if (!HCJsonFields.Has(encoded, "Enabled")) { Enabled = true; }
        if (!HCJsonFields.Has(encoded, "SearchRadiusMeters")) { SearchRadiusMeters = 600.0; }
        if (!HCJsonFields.Has(encoded, "MaxActiveGroups")) { MaxActiveGroups = 2; }
        if (!HCJsonFields.Has(encoded, "MaxKnownCars")) { MaxKnownCars = 512; }
        if (!HCJsonFields.Has(encoded, "CooldownSeconds")) { CooldownSeconds = 900; }
        if (!HCJsonFields.Has(encoded, "ClaimSeconds")) { ClaimSeconds = 1800; }
        if (!HCJsonFields.Has(encoded, "WorkSecondsPerStep")) { WorkSecondsPerStep = 20; }
        if (!HCJsonFields.Has(encoded, "WorkRangeMeters")) { WorkRangeMeters = 4.0; }
        if (!HCJsonFields.Has(encoded, "StashRangeMeters")) { StashRangeMeters = 15.0; }
        if (!HCJsonFields.Has(encoded, "WalkMetersPerSecond")) { WalkMetersPerSecond = 1.6; }
        if (!HCJsonFields.Has(encoded, "WalkSlackSeconds")) { WalkSlackSeconds = 120; }
        if (!HCJsonFields.Has(encoded, "MaxAttemptsPerCar")) { MaxAttemptsPerCar = 3; }
        if (!HCJsonFields.Has(encoded, "MaxScanItems")) { MaxScanItems = 96; }
        if (!HCJsonFields.Has(encoded, "StepSeconds")) { StepSeconds = 2; }
        if (!HCJsonFields.Has(encoded, "MaxRouteNodes")) { MaxRouteNodes = 64; }
        if (!HCJsonFields.Has(encoded, "MechanicToolClasses")) { MechanicToolClasses.Clear(); this.HCDefaultTools(); }
    }

    // Native CarScript.c:2535-2537 spawns Wrench, LugWrench, Screwdriver as car tools.
    void HCDefaultTools()
    {
        if (MechanicToolClasses.Count() > 0) { return; }
        MechanicToolClasses.Insert("Wrench");
        MechanicToolClasses.Insert("LugWrench");
    }

    bool HCValid()
    {
        if (this.Version != 1) { return false; }
        if (this.SearchRadiusMeters < 50.0 || this.SearchRadiusMeters > 3000.0) { return false; }
        if (this.MaxActiveGroups < 1 || this.MaxActiveGroups > 8) { return false; }
        if (this.MaxKnownCars < 8 || this.MaxKnownCars > 2048) { return false; }
        if (this.CooldownSeconds < 60 || this.CooldownSeconds > 7200) { return false; }
        if (this.ClaimSeconds < 120 || this.ClaimSeconds > 14400) { return false; }
        if (this.WorkSecondsPerStep < 5 || this.WorkSecondsPerStep > 120) { return false; }
        if (this.WorkRangeMeters < 2.0 || this.WorkRangeMeters > 8.0) { return false; }
        if (this.StashRangeMeters < 3.0 || this.StashRangeMeters > 40.0) { return false; }
        if (this.WalkMetersPerSecond < 0.5 || this.WalkMetersPerSecond > 5.0) { return false; }
        if (this.WalkSlackSeconds < 30 || this.WalkSlackSeconds > 900) { return false; }
        if (this.MaxAttemptsPerCar < 1 || this.MaxAttemptsPerCar > 10) { return false; }
        if (this.MaxScanItems < 16 || this.MaxScanItems > 256) { return false; }
        if (this.StepSeconds < 1 || this.StepSeconds > 10) { return false; }
        if (this.MaxRouteNodes < 4 || this.MaxRouteNodes > 256) { return false; }
        if (this.MechanicToolClasses.Count() < 1 || this.MechanicToolClasses.Count() > 8) { return false; }
        return true;
    }
}

class HCXAICarRepairPolicy
{
    static const int PART_BATTERY = 1;
    static const int PART_SPARK = 2;
    static const int PART_RADIATOR = 4;
    static const int PART_GLOW = 8;

    // First failing reason, "" when a group may be offered work.
    static string HCOfferRefusal(bool enabled, int active, int maxActive, int now, int nextAt, bool mechanic)
    {
        if (!enabled) { return "carfix_disabled"; }
        if (!mechanic) { return "carfix_no_mechanic"; }
        if (now < nextAt) { return "carfix_cooldown"; }
        if (active >= maxActive) { return "carfix_cap"; }
        return "";
    }

    static bool HCClaimFree(int claimGroup, int claimUntil, int groupId, int now)
    {
        if (claimGroup == 0 || claimGroup == groupId || claimUntil <= now) { return true; }
        return false;
    }

    // Wheels needing a part, one unit per missing/ruined part, one per engine step.
    static int HCNeedCount(HCXAICarEntry entry)
    {
        int total = entry.WheelNeed + entry.EngineSteps;
        int mask = entry.PartMask;
        while (mask > 0)
        {
            total = total + (mask & 1);
            mask = mask >> 1;
        }
        return total;
    }

    // Nearest repairable, unclaimed, not cooling car inside the config radius of home.
    static HCXAICarEntry HCPickCar(array<ref HCXAICarEntry> cars, vector home, float radius, int groupId, int now, int maxAttempts)
    {
        HCXAICarEntry best = null;
        float bestDistance = radius * radius;
        foreach (HCXAICarEntry entry : cars)
        {
            if (!entry) { continue; }
            if (entry.Unrepairable || entry.Attempts >= maxAttempts || entry.NextAt > now) { continue; }
            if (HCXAICarRepairPolicy.HCNeedCount(entry) < 1) { continue; }
            if (!HCXAICarRepairPolicy.HCClaimFree(entry.ClaimGroup, entry.ClaimUntil, groupId, now)) { continue; }
            float distance = vector.DistanceSq(entry.Pos, home);
            if (distance > bestDistance) { continue; }
            best = entry;
            bestDistance = distance;
        }
        return best;
    }

    // All-or-nothing: partial repairs would leave an unusable half-fixed car claimed.
    static string HCCoverage(int needWheels, int needMask, int engineSteps, int haveWheels, int haveMask, bool haveTool)
    {
        if (haveWheels < needWheels) { return "carfix_no_wheels"; }
        if ((haveMask & needMask) != needMask) { return "carfix_no_parts"; }
        if (engineSteps > 0 && !haveTool) { return "carfix_no_tool"; }
        return "";
    }

    // ActionRepairVehiclePartBase.c:48 lowers the level by one, clamped at WORN.
    static int HCEngineNextLevel(int level)
    {
        int lowered = level - 1;
        if (lowered < GameConstants.STATE_WORN) { lowered = GameConstants.STATE_WORN; }
        if (lowered > GameConstants.STATE_RUINED) { lowered = GameConstants.STATE_RUINED; }
        return lowered;
    }

    // ActionRepairVehiclePartBase.c:50-62 band base plus a caller-supplied jitter.
    static float HCEngineHealth(float zoneMax, int newLevel, float jitter)
    {
        if (newLevel == GameConstants.STATE_BADLY_DAMAGED) { return zoneMax * GameConstants.DAMAGE_RUINED_VALUE + jitter; }
        if (newLevel == GameConstants.STATE_DAMAGED) { return zoneMax * GameConstants.DAMAGE_BADLY_DAMAGED_VALUE + jitter; }
        if (newLevel == GameConstants.STATE_WORN) { return zoneMax * GameConstants.DAMAGE_DAMAGED_VALUE + jitter; }
        return -1.0;
    }

    // Real walking budget: distance at a config speed plus slack. Timeout aborts; never a teleport.
    static int HCWalkSeconds(float distance, float metersPerSecond, int slackSeconds)
    {
        if (metersPerSecond <= 0.0) { return slackSeconds; }
        int seconds = distance / metersPerSecond;
        return seconds + slackSeconds;
    }

    static bool HCRegistryAdd(array<CarScript> list, CarScript car, int cap)
    {
        if (!car) { return false; }
        if (list.Find(car) >= 0) { return true; }
        if (list.Count() >= cap) { return false; }
        list.Insert(car);
        return true;
    }

    // Move one carried part into the car. 0 ok, 1 bad arguments, 2 the ruined
    // occupant could not be detached, 3 no compatible free slot, 4 the native
    // take refused, 5 readback shows the part did not arrive. The occupant is
    // dropped (kept in the world), never deleted; a refused step leaves the
    // new part with its carrier, so nothing is lost or duplicated.
    static int HCAttach(EntityAI car, EntityAI item, EntityAI occupant)
    {
        if (!car || !item) { return 1; }
        if (occupant)
        {
            if (!car.GetInventory().DropEntity(InventoryMode.SERVER, car, occupant)) { return 2; }
        }
        InventoryLocation loc = new InventoryLocation();
        if (!car.GetInventory().FindFreeLocationFor(item, FindInventoryLocationType.ATTACHMENT, loc)) { return 3; }
        if (!car.GetInventory().TakeEntityAsTargetAttachmentEx(InventoryMode.SERVER, car, item, loc.GetSlot())) { return 4; }
        if (item.GetHierarchyParent() != car) { return 5; }
        return 0;
    }
}
