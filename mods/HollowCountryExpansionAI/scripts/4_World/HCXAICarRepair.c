// S3 car repair (owner direction 2026-11-19): a mechanic-capable AI group walks
// to the nearest known damaged or incomplete native car within a config radius
// of its home and repairs it with REAL parts, then claims it so the convoy agent
// can read HCXAICarRepair.HCReadyCar(group). No spawn, no delete, no teleport,
// no player position, no blocked door. Parts move by native inventory calls.
//
// Knowledge: the server-side vehicle registry below (modded CarScript EEInit /
// EEDelete, native 3_Game/Entities/EntityAI.c:905 EEInit, :946 EEDelete). It is
// world memory of cars that exist near the camp (radius from config), never a
// player position. Perception-fed discovery is NOT built; see the report gap.
//
// Native scripts-1.30.164289 evidence:
// 3_Game/Vehicles/Car.c:335 WheelGetEntity, :345 WheelCount (null = empty slot);
// 3_Game/Vehicles/Transport.c:407 IsVitalSparkPlug, :412 IsVitalGlowPlug, :830
// NeedElectricitySourceDevice, :840 GetElectricitySourceDeviceType;
// 4_World/Entities/Vehicles/CarScript.c:24 ECarOperationalState, :1752
// CheckOperationalRequirements, :2206 IsVitalRadiator, :2437 GetBattery;
// 4_World/Entities/Core/Inherited/InventoryItem.c:194 CarWheel, :834 CarRadiator,
// :939 GlowPlug, :952 SparkPlug; Entities/ItemBase/VehicleBattery/CarBattery.c:1;
// 3_Game/Entities/EntityAI.c:1897 FindAttachmentBySlotName;
// 3_Game/Systems/Inventory/Inventory.c:127 EnumerateInventory, :167-175
// GetSlotId/GetSlotIdCount, :241 CanAddAttachment, :1013 TakeEntityToInventory;
// 3_Game/Systems/Inventory/InventoryLocation.c:71 GetSlot;
// Entities/ItemBase/Blowtorch.c:89-93 canister energy debit, :118-122
// canister lookup, :128 HasEnoughEnergyForRepair; ActionRepairVehiclePartBase.c:36-66
// health step (mirrored by HCXAICarRepairPolicy.HCEngineHealth);
// 3_Game/Entities/Object.c:215 IsPendingDeletion, :1171 GetHealthLevel, :1219 IsRuined;
// 1_Core/proto/EnMath.c:106 RandomFloatInclusive; EnSystem.c:397 FileExist.
// Expansion (read-only, installed ai_scripts.pbo, nothing copied):
// 4_World/DayZExpansion_AI/Classes/eAIGroup.c:213 AddWaypoint, :222 GetWaypoints,
// :241 ClearWaypoints, :251 SetWaypointBehaviour, :304 GetWaypointBehaviour,
// :695 GetID, :894 GetLeader, :1123 IsInCombat, :1139 GetMember, :1185 Count.
// Repo reuse: HCServer.HCTickWork budget, HCWorldClock.UTC, HCV2Admission,
// HCOperationalStatus/HCOperationalContributors, HCHoldouts.Cache stash crates
// (their EECargoOut hook is the custody notification, HCHoldouts.c:1005),
// HCCampTheft.SafeItem, HCLockTable.CampUnlocked, HCJsonFields.Has.
// Runtime acceptance is PENDING; admitted unverified per HCV2Admission.

modded class CarScript
{
    // Transient claim and cooldown state; deliberately absent from native storage.
    int m_HCCarClaimGroup;
    int m_HCCarClaimUntil;
    int m_HCCarAttempts;
    int m_HCCarNextAt;

    override void EEInit()
    {
        super.EEInit();
        HCXAICarRepair.HCRegister(this);
    }

    override void EEDelete(EntityAI parent)
    {
        HCXAICarRepair.HCUnregister(this);
        super.EEDelete(parent);
    }
}

class HCXAICarStep
{
    int Kind;
    EntityAI Item;
    EntityAI Occupant;
}

class HCXAICarJob
{
    eAIGroup Group;
    int GroupId = 0;
    CarScript Subject;
    ref array<ref HCXAICarStep> Steps = new array<ref HCXAICarStep>();
    int Index = 0;
    int Phase = 0;
    int Deadline = 0;
    int StepDue = 0;
    bool RouteSaved = false;
    ref array<vector> Route = new array<vector>();
    eAIWaypointBehavior Behaviour;
    ItemBase Tool;
}

class HCXAICarRepair
{
    static const int KIND_WHEEL = 0;
    static const int KIND_BATTERY = 1;
    static const int KIND_SPARK = 2;
    static const int KIND_RADIATOR = 3;
    static const int KIND_GLOW = 4;
    static const int KIND_ENGINE = 5;

    // Work budget consumer: HCUnitBudget.HC_WORK_CARFIX (lead allocates 16).
    protected static ref HCXAICarRepairConfig s_Config;
    protected static ref array<CarScript> s_Cars;
    protected static ref array<ref HCXAICarJob> s_Jobs;
    protected static ref map<int, int> s_NextAt;
    protected static ref map<int, CarScript> s_Ready;
    protected static ref array<EntityAI> s_Reserved;
    protected static ref HCOperationalStatus s_Status;
    protected static bool s_Open;
    protected static int s_NextTick;
    protected static string s_Refusal;

    // Compiled defaults until HCOpen loads the mission file; also makes EEInit
    // registration safe before the adapter starts.
    static HCXAICarRepairConfig HCConfig()
    {
        if (!s_Config)
        {
            s_Config = new HCXAICarRepairConfig();
            s_Config.HCDefaultTools();
        }
        return s_Config;
    }

    protected static array<CarScript> HCCars()
    {
        if (!s_Cars) { s_Cars = new array<CarScript>(); }
        return s_Cars;
    }

    protected static array<ref HCXAICarJob> HCJobs()
    {
        if (!s_Jobs) { s_Jobs = new array<ref HCXAICarJob>(); }
        return s_Jobs;
    }

    protected static array<EntityAI> HCReserved()
    {
        if (!s_Reserved) { s_Reserved = new array<EntityAI>(); }
        return s_Reserved;
    }

    static HCOperationalStatus HCStatus()
    {
        if (!s_Status) { s_Status = new HCOperationalStatus(); }
        return s_Status;
    }

    static void HCRegister(CarScript car)
    {
        if (!GetGame() || !GetGame().IsServer()) { return; }
        HCXAICarRepairPolicy.HCRegistryAdd(HCCars(), car, HCConfig().MaxKnownCars);
    }

    static void HCUnregister(CarScript car)
    {
        if (!car || !s_Cars) { return; }
        int at = s_Cars.Find(car);
        if (at >= 0) { s_Cars.RemoveOrdered(at); }
    }

    // One line per change of reason. Never per tick, never ids or names.
    protected static void HCRefuse(string reason)
    {
        if (reason == s_Refusal) { return; }
        s_Refusal = reason;
        Print("[HC CarFix] refused reason=" + reason + " runtime=PENDING");
    }

    // Called once by the modded HCXAIAdapter.OnStart (guarded to the owning adapter).
    static void HCOpen(HCSettings settings)
    {
        s_Open = false;
        s_Refusal = "";
        s_NextTick = 0;
        HCStatus().HCPublish("off", "operator_disabled");
        if (!settings || !settings.EnableEncounters) { return; }
        if (!GetGame() || !GetGame().IsServer()) { return; }
        // Native EnSystem.c:397; independent operator opt-out.
        if (FileExist("$profile:HollowCountry/acceptance/ai_car_repair.disable"))
        {
            HCStatus().HCPublish("off", "operator_opt_out");
            return;
        }
        Print(HCV2Admission.Line("AICarRepair", true, "S3-CARFIX-NATIVE-PART-ATTACH", false));
        HCXAICarRepairConfig config = new HCXAICarRepairConfig();
        string encoded = HCWorldStore.Read("$mission:hollow-country/ai/car-repair.json");
        string error;
        bool parsed = true;
        if (encoded.Length() > 0)
        {
            parsed = JsonFileLoader<HCXAICarRepairConfig>.LoadData(encoded, config, error);
            if (parsed) { config.HCApplyDefaults(encoded); }
        }
        else
        {
            config.HCDefaultTools();
        }
        if (!parsed || !config.HCValid())
        {
            HCStatus().HCPublish("refused", "carfix_config_invalid");
            Print("[HC CarFix] refused reason=carfix_config_invalid runtime=PENDING");
            return;
        }
        s_Config = config;
        if (!config.Enabled)
        {
            HCStatus().HCPublish("off", "config_disabled");
            return;
        }
        s_NextAt = new map<int, int>();
        s_Ready = new map<int, CarScript>();
        s_Open = true;
        HCStatus().HCPublish("ready", "waiting_for_scheduler_offer");
        Print("[HC CarFix] ready radius=" + config.SearchRadiusMeters.ToString() + " active_cap=" + config.MaxActiveGroups.ToString() + " known=" + HCCars().Count().ToString() + " runtime=PENDING");
    }

    static void HCClose()
    {
        int index = HCJobs().Count() - 1;
        while (index >= 0)
        {
            HCEnd(HCJobs()[index], "carfix_stopped", false);
            index--;
        }
        s_Open = false;
        HCStatus().HCPublish("off", "server_stop_requested");
    }

    // The role scheduler offers an idle group at its home. True when a job started.
    static bool HCOffer(eAIGroup group, vector home)
    {
        if (!s_Open || !group || !GetGame() || !GetGame().IsServer()) { return false; }
        HCXAICarRepairConfig config = HCConfig();
        if (!HCServer.HCTickWork().HCTakeFor(16, 1 + group.Count())) { return false; }
        int now = HCWorldClock.UTC();
        int groupId = group.GetID();
        int nextAt = 0;
        if (s_NextAt.Find(groupId, nextAt) == false) { nextAt = 0; }
        eAIBase leader = HCLeader(group);
        string reason = HCXAICarRepairPolicy.HCOfferRefusal(config.Enabled, HCJobs().Count(), config.MaxActiveGroups, now, nextAt, HCMechanic(group, config));
        if (reason == "" && (!leader || group.IsInCombat())) { reason = "carfix_group_unavailable"; }
        if (reason == "" && HCJobFor(groupId)) { reason = "carfix_group_busy"; }
        if (reason != "") { HCRefuse(reason); return false; }
        array<ref HCXAICarEntry> known = new array<ref HCXAICarEntry>();
        HCKnownCars(home, now, known);
        HCXAICarEntry pick = HCXAICarRepairPolicy.HCPickCar(known, home, config.SearchRadiusMeters, groupId, now, config.MaxAttemptsPerCar);
        s_NextAt.Set(groupId, now + config.CooldownSeconds);
        if (!pick || !pick.Subject) { HCRefuse("carfix_no_known_car"); return false; }
        HCXAICarJob job = new HCXAICarJob();
        job.Group = group;
        job.GroupId = groupId;
        job.Subject = pick.Subject;
        string plan = HCPlan(job, pick, leader, home);
        if (plan != "") { HCRefuse(plan); return false; }
        if (!HCTakeStash(job, leader)) { HCEnd(job, "carfix_stash_take_refused", false); return false; }
        if (!HCWalk(job, pick.Pos)) { HCEnd(job, "carfix_route_refused", false); return false; }
        pick.Subject.m_HCCarClaimGroup = groupId;
        pick.Subject.m_HCCarClaimUntil = now + config.ClaimSeconds;
        job.Deadline = now + HCXAICarRepairPolicy.HCWalkSeconds(vector.Distance(leader.GetPosition(), pick.Pos), config.WalkMetersPerSecond, config.WalkSlackSeconds);
        HCJobs().Insert(job);
        s_Refusal = "";
        HCStatus().HCPublish("ready", "job_active");
        Print("[HC CarFix] started steps=" + job.Steps.Count().ToString() + " type=" + pick.Subject.GetType() + " runtime=PENDING");
        return true;
    }

    // The car this group claimed and finished repairing, or null. Mechanical
    // readiness only: fuel is not a part and stays with the convoy agent.
    static CarScript HCReadyCar(eAIGroup group)
    {
        if (!s_Open || !group || !s_Ready) { return null; }
        int groupId = group.GetID();
        CarScript car = null;
        if (!s_Ready.Find(groupId, car) || !car) { return null; }
        if (car.IsPendingDeletion() || car.m_HCCarClaimGroup != groupId || car.m_HCCarClaimUntil <= HCWorldClock.UTC())
        {
            s_Ready.Remove(groupId);
            return null;
        }
        int state = car.CheckOperationalRequirements();
        state = state & (ECarOperationalState.RUINED | ECarOperationalState.NO_IGNITER | ECarOperationalState.NO_BATTERY);
        if (state != 0) { return null; }
        return car;
    }

    // The convoy agent (or an abort) gives the claim back.
    static void HCReleaseCar(eAIGroup group)
    {
        if (!group || !s_Ready) { return; }
        int groupId = group.GetID();
        CarScript car = null;
        if (s_Ready.Find(groupId, car) && car && car.m_HCCarClaimGroup == groupId) { car.m_HCCarClaimGroup = 0; car.m_HCCarClaimUntil = 0; }
        s_Ready.Remove(groupId);
    }

    // Bounded tick, called by the adapter adjunct. One shared unit per job step.
    static void HCTick()
    {
        if (!s_Open) { return; }
        int now = HCWorldClock.UTC();
        if (now < s_NextTick) { return; }
        s_NextTick = now + HCConfig().StepSeconds;
        int index = HCJobs().Count() - 1;
        while (index >= 0)
        {
            if (!HCServer.HCTickWork().HCTakeFor(16, 1)) { return; }
            HCStep(HCJobs()[index], now);
            index--;
        }
    }

    protected static HCXAICarJob HCJobFor(int groupId)
    {
        array<ref HCXAICarJob> jobs = HCJobs();
        foreach (HCXAICarJob job : jobs)
        {
            if (job && job.GroupId == groupId) { return job; }
        }
        return null;
    }

    protected static eAIBase HCLeader(eAIGroup group)
    {
        int index = 0;
        while (index < group.Count())
        {
            eAIBase member = eAIBase.Cast(group.GetMember(index));
            if (member && member.IsAlive() && !member.IsUnconscious()) { return member; }
            index++;
        }
        return null;
    }

    // Mechanic capable: a living member carries one of the configured tool classes.
    protected static bool HCMechanic(eAIGroup group, HCXAICarRepairConfig config)
    {
        array<EntityAI> items = new array<EntityAI>();
        int index = 0;
        while (index < group.Count())
        {
            eAIBase member = eAIBase.Cast(group.GetMember(index));
            index++;
            if (!member || !member.IsAlive()) { continue; }
            items.Clear();
            member.GetInventory().EnumerateInventory(InventoryTraversalType.PREORDER, items);
            int scanned = 0;
            array<string> tools = config.MechanicToolClasses;
            foreach (EntityAI item : items)
            {
                scanned++;
                if (scanned > config.MaxScanItems) { break; }
                foreach (string tool : tools)
                {
                    if (item && item.IsKindOf(tool)) { return true; }
                }
            }
        }
        return false;
    }

    // Registry rows near home only; the policy re-filters by radius.
    protected static void HCKnownCars(vector home, int now, array<ref HCXAICarEntry> known)
    {
        HCXAICarRepairConfig config = HCConfig();
        float limit = config.SearchRadiusMeters * config.SearchRadiusMeters;
        int index = 0;
        while (index < HCCars().Count())
        {
            CarScript car = HCCars()[index];
            index++;
            if (!car || car.IsPendingDeletion()) { continue; }
            vector at = car.GetPosition();
            if (vector.DistanceSq(at, home) > limit) { continue; }
            known.Insert(HCSnapshot(car));
        }
    }

    protected static HCXAICarEntry HCSnapshot(CarScript car)
    {
        HCXAICarEntry entry = new HCXAICarEntry();
        entry.Subject = car;
        entry.Pos = car.GetPosition();
        entry.ClaimGroup = car.m_HCCarClaimGroup;
        entry.ClaimUntil = car.m_HCCarClaimUntil;
        entry.Attempts = car.m_HCCarAttempts;
        entry.NextAt = car.m_HCCarNextAt;
        int level = car.GetHealthLevel("Engine");
        // ActionRepairCarEngine.c: a RUINED Engine zone is not repairable.
        if (car.IsRuined() || level >= GameConstants.STATE_RUINED) { entry.Unrepairable = true; return entry; }
        if (level > GameConstants.STATE_WORN) { entry.EngineSteps = level - GameConstants.STATE_WORN; }
        int wheelCount = car.WheelCount();
        int wheelIndex = 0;
        while (wheelIndex < wheelCount)
        {
            EntityAI wheel = car.WheelGetEntity(wheelIndex);
            if (!wheel || wheel.IsRuined()) { entry.WheelNeed++; }
            wheelIndex++;
        }
        if (car.NeedElectricitySourceDevice() && HCBroken(car.GetBattery())) { entry.PartMask = entry.PartMask | HCXAICarRepairPolicy.PART_BATTERY; }
        if (car.IsVitalSparkPlug() && HCBroken(car.FindAttachmentBySlotName("SparkPlug"))) { entry.PartMask = entry.PartMask | HCXAICarRepairPolicy.PART_SPARK; }
        if (car.IsVitalGlowPlug() && HCBroken(car.FindAttachmentBySlotName("GlowPlug"))) { entry.PartMask = entry.PartMask | HCXAICarRepairPolicy.PART_GLOW; }
        if (car.IsVitalRadiator() && HCBroken(car.FindAttachmentBySlotName("CarRadiator"))) { entry.PartMask = entry.PartMask | HCXAICarRepairPolicy.PART_RADIATOR; }
        return entry;
    }

    protected static bool HCBroken(EntityAI part)
    {
        if (!part) { return true; }
        return part.IsRuined();
    }

    protected static int HCKindOf(CarScript car, EntityAI item)
    {
        if (!item || item.IsRuined()) { return -1; }
        if (CarWheel.Cast(item)) { return HCXAICarRepair.KIND_WHEEL; }
        if (SparkPlug.Cast(item)) { return HCXAICarRepair.KIND_SPARK; }
        if (GlowPlug.Cast(item)) { return HCXAICarRepair.KIND_GLOW; }
        if (CarRadiator.Cast(item)) { return HCXAICarRepair.KIND_RADIATOR; }
        string batteryType = car.GetElectricitySourceDeviceType();
        if (batteryType != "" && item.IsKindOf(batteryType)) { return HCXAICarRepair.KIND_BATTERY; }
        return -1;
    }

    // A part fits an empty slot when the car accepts it; it fits an occupied
    // (ruined) slot when that slot id is one of the item's own slots.
    protected static bool HCFits(CarScript car, EntityAI item, EntityAI occupant)
    {
        if (!occupant) { return car.GetInventory().CanAddAttachment(item); }
        InventoryLocation where = new InventoryLocation();
        if (!occupant.GetInventory().GetCurrentInventoryLocation(where)) { return false; }
        int slot = where.GetSlot();
        int count = item.GetInventory().GetSlotIdCount();
        int index = 0;
        while (index < count)
        {
            if (item.GetInventory().GetSlotId(index) == slot) { return true; }
            index++;
        }
        return false;
    }

    protected static EntityAI HCFindPart(CarScript car, int kind, EntityAI occupant, array<EntityAI> carried, array<EntityAI> stashed, array<EntityAI> used)
    {
        foreach (EntityAI candidate : carried)
        {
            if (HCUsable(car, kind, occupant, candidate, used)) { return candidate; }
        }
        foreach (EntityAI stocked : stashed)
        {
            if (HCUsable(car, kind, occupant, stocked, used)) { return stocked; }
        }
        return null;
    }

    protected static bool HCUsable(CarScript car, int kind, EntityAI occupant, EntityAI item, array<EntityAI> used)
    {
        if (!item || HCKindOf(car, item) != kind) { return false; }
        if (used.Find(item) >= 0 || HCReserved().Find(item) >= 0) { return false; }
        return HCFits(car, item, occupant);
    }

    protected static void HCAddStep(HCXAICarJob job, int kind, EntityAI item, EntityAI occupant, array<EntityAI> used)
    {
        HCXAICarStep step = new HCXAICarStep();
        step.Kind = kind;
        step.Item = item;
        step.Occupant = occupant;
        job.Steps.Insert(step);
        if (item) { used.Insert(item); }
    }

    protected static void HCCollect(eAIGroup group, eAIBase leader, vector home, array<EntityAI> carried, array<EntityAI> stashed)
    {
        HCXAICarRepairConfig config = HCConfig();
        array<EntityAI> items = new array<EntityAI>();
        int index = 0;
        while (index < group.Count())
        {
            eAIBase member = eAIBase.Cast(group.GetMember(index));
            index++;
            if (!member || !member.IsAlive()) { continue; }
            items.Clear();
            member.GetInventory().EnumerateInventory(InventoryTraversalType.PREORDER, items);
            int scanned = 0;
            foreach (EntityAI item : items)
            {
                scanned++;
                if (scanned > config.MaxScanItems) { break; }
                if (item) { carried.Insert(item); }
            }
        }
        HCHoldouts holdouts = HCHoldouts.Get();
        if (!holdouts) { return; }
        float range = config.StashRangeMeters * config.StashRangeMeters;
        int cacheIndex = 0;
        while (cacheIndex < holdouts.Count())
        {
            EntityAI crate = holdouts.Cache(cacheIndex);
            cacheIndex++;
            if (!crate || vector.DistanceSq(crate.GetPosition(), home) > range) { continue; }
            if (vector.DistanceSq(crate.GetPosition(), leader.GetPosition()) > range) { continue; }
            if (!HCLockTable.CampUnlocked(ItemBase.Cast(crate)) || !crate.GetInventory() || !crate.GetInventory().GetCargo()) { continue; }
            CargoBase cargo = crate.GetInventory().GetCargo();
            int total = cargo.GetItemCount();
            if (total > config.MaxScanItems) { total = config.MaxScanItems; }
            int cargoIndex = 0;
            while (cargoIndex < total)
            {
                EntityAI stock = cargo.GetItem(cargoIndex);
                cargoIndex++;
                if (HCCampTheft.SafeItem(stock)) { stashed.Insert(stock); }
            }
        }
    }

    // All-or-nothing plan. Returns the refusal reason, "" when fully covered.
    protected static string HCPlan(HCXAICarJob job, HCXAICarEntry entry, eAIBase leader, vector home)
    {
        CarScript car = job.Subject;
        array<EntityAI> carried = new array<EntityAI>();
        array<EntityAI> stashed = new array<EntityAI>();
        array<EntityAI> used = new array<EntityAI>();
        HCCollect(job.Group, leader, home, carried, stashed);
        int haveWheels = 0;
        int haveMask = 0;
        int wheelCount = car.WheelCount();
        int wheelIndex = 0;
        while (wheelIndex < wheelCount)
        {
            EntityAI wheel = car.WheelGetEntity(wheelIndex);
            wheelIndex++;
            if (wheel && !wheel.IsRuined()) { continue; }
            EntityAI wheelPart = HCFindPart(car, HCXAICarRepair.KIND_WHEEL, wheel, carried, stashed, used);
            if (!wheelPart) { continue; }
            HCAddStep(job, HCXAICarRepair.KIND_WHEEL, wheelPart, wheel, used);
            haveWheels++;
        }
        haveMask = haveMask | HCPlanPart(job, entry, HCXAICarRepairPolicy.PART_BATTERY, HCXAICarRepair.KIND_BATTERY, car.GetBattery(), carried, stashed, used);
        haveMask = haveMask | HCPlanPart(job, entry, HCXAICarRepairPolicy.PART_SPARK, HCXAICarRepair.KIND_SPARK, car.FindAttachmentBySlotName("SparkPlug"), carried, stashed, used);
        haveMask = haveMask | HCPlanPart(job, entry, HCXAICarRepairPolicy.PART_GLOW, HCXAICarRepair.KIND_GLOW, car.FindAttachmentBySlotName("GlowPlug"), carried, stashed, used);
        haveMask = haveMask | HCPlanPart(job, entry, HCXAICarRepairPolicy.PART_RADIATOR, HCXAICarRepair.KIND_RADIATOR, car.FindAttachmentBySlotName("CarRadiator"), carried, stashed, used);
        bool haveTool = false;
        if (entry.EngineSteps > 0)
        {
            job.Tool = HCFindTorch(carried, entry.EngineSteps * HCConfig().WorkSecondsPerStep);
            haveTool = job.Tool != null;
        }
        string reason = HCXAICarRepairPolicy.HCCoverage(entry.WheelNeed, entry.PartMask, entry.EngineSteps, haveWheels, haveMask, haveTool);
        if (reason != "") { return reason; }
        int engineStep = 0;
        while (engineStep < entry.EngineSteps)
        {
            HCAddStep(job, HCXAICarRepair.KIND_ENGINE, null, null, used);
            engineStep++;
        }
        foreach (EntityAI reserved : used) { HCReserved().Insert(reserved); }
        return "";
    }

    // Returns the policy mask bit when a usable part was assigned, else 0.
    protected static int HCPlanPart(HCXAICarJob job, HCXAICarEntry entry, int bit, int kind, EntityAI occupant, array<EntityAI> carried, array<EntityAI> stashed, array<EntityAI> used)
    {
        if ((entry.PartMask & bit) == 0) { return 0; }
        EntityAI part = HCFindPart(job.Subject, kind, occupant, carried, stashed, used);
        if (!part) { return 0; }
        HCAddStep(job, kind, part, occupant, used);
        return bit;
    }

    protected static ItemBase HCFindTorch(array<EntityAI> carried, int seconds)
    {
        foreach (EntityAI candidate : carried)
        {
            Blowtorch torch = Blowtorch.Cast(candidate);
            if (torch && !torch.IsRuined() && torch.HasEnoughEnergyForRepair(seconds)) { return torch; }
        }
        return null;
    }

    // Stash parts physically move into the leader's inventory before the walk.
    // The crate's EECargoOut hook (HCHoldouts.c:1005) is the existing custody
    // notification; nothing is created or deleted.
    protected static bool HCTakeStash(HCXAICarJob job, eAIBase leader)
    {
        array<ref HCXAICarStep> planned = job.Steps;
        foreach (HCXAICarStep step : planned)
        {
            if (!step.Item || step.Item.GetHierarchyRootPlayer()) { continue; }
            if (!leader.GetInventory().TakeEntityToInventory(InventoryMode.SERVER, FindInventoryLocationType.ANY, step.Item)) { return false; }
            if (step.Item.GetHierarchyRootPlayer() != leader) { return false; }
        }
        return true;
    }

    // Real walking: the existing group waypoint port, prior patrol restored on end.
    protected static bool HCWalk(HCXAICarJob job, vector goal)
    {
        eAIGroup group = job.Group;
        array<vector> previous = group.GetWaypoints();
        if (previous && previous.Count() > HCConfig().MaxRouteNodes) { return false; }
        if (previous)
        {
            array<vector> saved = previous;
            foreach (vector node : saved) { job.Route.Insert(node); }
        }
        job.Behaviour = group.GetWaypointBehaviour();
        job.RouteSaved = true;
        group.ClearWaypoints();
        group.AddWaypoint(goal);
        group.SetWaypointBehaviour(eAIWaypointBehavior.ONCE);
        return true;
    }

    protected static void HCRestoreRoute(HCXAICarJob job)
    {
        if (!job.RouteSaved || !job.Group) { return; }
        job.RouteSaved = false;
        job.Group.ClearWaypoints();
        array<vector> route = job.Route;
        foreach (vector point : route) { job.Group.AddWaypoint(point); }
        job.Group.SetWaypointBehaviour(job.Behaviour);
    }

    protected static void HCStep(HCXAICarJob job, int now)
    {
        eAIBase leader = null;
        if (job.Group) { leader = HCLeader(job.Group); }
        if (!leader) { HCEnd(job, "carfix_group_lost", false); return; }
        if (!job.Subject || job.Subject.IsPendingDeletion()) { HCEnd(job, "carfix_car_lost", false); return; }
        if (job.Group.IsInCombat()) { HCEnd(job, "carfix_combat", false); return; }
        if (job.Subject.m_HCCarClaimGroup != job.GroupId) { HCEnd(job, "carfix_claim_lost", false); return; }
        HCXAICarRepairConfig config = HCConfig();
        if (job.Phase == 0)
        {
            float reach = config.WorkRangeMeters * config.WorkRangeMeters;
            if (vector.DistanceSq(leader.GetPosition(), job.Subject.GetPosition()) <= reach)
            {
                job.Phase = 1;
                job.StepDue = now + config.WorkSecondsPerStep;
                return;
            }
            if (now > job.Deadline) { HCEnd(job, "carfix_walk_timeout", false); }
            return;
        }
        if (now < job.StepDue) { return; }
        string failure = HCCommit(job, config, leader);
        if (failure == "carfix_pause_worker")
        {
            HCRewalk(job, leader, now);
            return;
        }
        if (failure != "") { HCEnd(job, failure, false); return; }
        job.Index++;
        job.StepDue = now + config.WorkSecondsPerStep;
        if (job.Index >= job.Steps.Count()) { HCEnd(job, "", true); }
    }

    // The worker left the car: back to walking with a fresh real-walk budget.
    protected static void HCRewalk(HCXAICarJob job, eAIBase leader, int now)
    {
        HCXAICarRepairConfig config = HCConfig();
        vector goal = job.Subject.GetPosition();
        job.Phase = 0;
        job.Deadline = now + HCXAICarRepairPolicy.HCWalkSeconds(vector.Distance(leader.GetPosition(), goal), config.WalkMetersPerSecond, config.WalkSlackSeconds);
        job.Group.ClearWaypoints();
        job.Group.AddWaypoint(goal);
        job.Group.SetWaypointBehaviour(eAIWaypointBehavior.ONCE);
    }

    // Custody and proximity revalidated before every commit: the carrier must be
    // a living member of this job's group, the worker and the carrier must both
    // stand within working range of the car as it is NOW.
    protected static string HCCarrierGate(HCXAICarJob job, EntityAI item, eAIBase leader, float reachSq)
    {
        eAIBase carrier = eAIBase.Cast(item.GetHierarchyRootPlayer());
        bool member = carrier && carrier.IsAlive() && carrier.GetGroup() == job.Group;
        float workerSq = vector.DistanceSq(leader.GetPosition(), job.Subject.GetPosition());
        float carrierSq = reachSq + 1.0;
        if (carrier) { carrierSq = vector.DistanceSq(carrier.GetPosition(), job.Subject.GetPosition()); }
        return HCXAICarRepairPolicy.HCCommitGate(member, workerSq, carrierSq, reachSq);
    }

    // One timed step: a real attach, or one engine health step. "" on success.
    protected static string HCCommit(HCXAICarJob job, HCXAICarRepairConfig config, eAIBase leader)
    {
        HCXAICarStep step = job.Steps[job.Index];
        float reachSq = config.WorkRangeMeters * config.WorkRangeMeters;
        if (step.Kind == HCXAICarRepair.KIND_ENGINE) { return HCEngineStep(job, config, leader); }
        if (!step.Item || step.Item.IsRuined()) { return "carfix_part_lost"; }
        string gate = HCCarrierGate(job, step.Item, leader, reachSq);
        if (gate != "") { return gate; }
        if (step.Occupant && step.Occupant.GetHierarchyParent() != job.Subject) { return "carfix_slot_changed"; }
        int result = HCXAICarRepairPolicy.HCAttach(job.Subject, step.Item, step.Occupant);
        if (result != 0) { return "carfix_attach_" + result.ToString(); }
        return "";
    }

    protected static string HCEngineStep(HCXAICarJob job, HCXAICarRepairConfig config, eAIBase leader)
    {
        Blowtorch torch = Blowtorch.Cast(job.Tool);
        if (!torch || torch.IsRuined() || !torch.HasEnoughEnergyForRepair(config.WorkSecondsPerStep)) { return "carfix_tool_empty"; }
        string toolGate = HCCarrierGate(job, torch, leader, config.WorkRangeMeters * config.WorkRangeMeters);
        if (toolGate != "") { return toolGate; }
        int level = job.Subject.GetHealthLevel("Engine");
        if (level >= GameConstants.STATE_RUINED) { return "carfix_engine_ruined"; }
        int lowered = HCXAICarRepairPolicy.HCEngineNextLevel(level);
        float zoneMax = job.Subject.GetMaxHealth("Engine", "");
        float jitter = Math.RandomFloatInclusive(zoneMax * 0.05, zoneMax * 0.15);
        float health = HCXAICarRepairPolicy.HCEngineHealth(zoneMax, lowered, jitter);
        if (health < 0 || lowered >= level) { return ""; }
        job.Subject.SetHealth("Engine", "", health);
        // Blowtorch.c:89-93: the canister pays the working time.
        if (torch.GetInventory().AttachmentCount() > 0)
        {
            EntityAI canister = torch.GetInventory().GetAttachmentFromIndex(0);
            if (canister && canister.GetCompEM() && torch.GetCompEM())
            {
                canister.GetCompEM().AddEnergy(-1 * (torch.GetCompEM().GetEnergyUsage() * config.WorkSecondsPerStep));
            }
        }
        return "";
    }

    // Ends a job: route restored, reservations dropped, claim kept only on success.
    protected static void HCEnd(HCXAICarJob job, string reason, bool success)
    {
        if (!job) { return; }
        HCXAICarRepairConfig config = HCConfig();
        HCRestoreRoute(job);
        array<ref HCXAICarStep> ended = job.Steps;
        foreach (HCXAICarStep step : ended)
        {
            if (!step.Item) { continue; }
            int at = HCReserved().Find(step.Item);
            if (at >= 0) { HCReserved().RemoveOrdered(at); }
        }
        int now = HCWorldClock.UTC();
        if (s_NextAt) { s_NextAt.Set(job.GroupId, now + config.CooldownSeconds); }
        if (job.Subject)
        {
            if (success)
            {
                job.Subject.m_HCCarClaimUntil = now + config.ClaimSeconds;
                if (s_Ready) { s_Ready.Set(job.GroupId, job.Subject); }
            }
            else if (job.Subject.m_HCCarClaimGroup == job.GroupId)
            {
                job.Subject.m_HCCarClaimGroup = 0;
                job.Subject.m_HCCarClaimUntil = 0;
                job.Subject.m_HCCarAttempts++;
                job.Subject.m_HCCarNextAt = now + config.CooldownSeconds;
            }
        }
        int jobIndex = HCJobs().Find(job);
        if (jobIndex >= 0) { HCJobs().RemoveOrdered(jobIndex); }
        if (success)
        {
            Print("[HC CarFix] repaired steps=" + job.Steps.Count().ToString() + " runtime=PENDING");
            HCStatus().HCPublish("ready", "last_repair_complete");
            return;
        }
        HCRefuse(reason);
        HCStatus().HCPublish("ready", "last_" + reason);
    }
}

// Lifecycle adjunct on the same owner-guarded install point HCXAIScavengeAdapter
// uses. No module slot, no new unit-budget consumer id.
modded class HCXAIAdapter
{
    protected ref HCOperationalOwner m_HCCarFixOwner;
    protected bool m_HCCarFixRequested;

    override void OnStart(HCSettings settings)
    {
        super.OnStart(settings);
        if (GetGame() && GetGame().IsServer() && HCXAIService.Adapter() == this)
        {
            m_HCCarFixRequested = settings && settings.EnableEncounters;
            HCXAICarRepair.HCOpen(settings);
            m_HCCarFixOwner = HCOperationalContributors.HCRegisterOwner("hc-ai-carfix");
            HCObserveCarFix();
        }
    }

    override void OnTick(float deltaTime)
    {
        super.OnTick(deltaTime);
        if (HCXAIService.Adapter() != this) { return; }
        HCXAICarRepair.HCTick();
        HCObserveCarFix();
    }

    override void OnStop()
    {
        if (HCXAIService.Adapter() == this) { HCXAICarRepair.HCClose(); }
        super.OnStop();
    }

    protected void HCObserveCarFix()
    {
        if (m_HCCarFixOwner) { m_HCCarFixOwner.HCObserve(m_HCCarFixRequested, HCXAICarRepair.HCStatus(), GetGame().GetTickTime()); }
    }
}
