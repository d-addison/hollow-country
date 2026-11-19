// W69 native evidence: installed scripts-1.30.164289, read-only cache.
// 3_Game/Global/Game.c:703 CreateObjectEx, :930 GetObjectsAtPosition3D,
// :1120 IsServer; Entities/Object.c:287 GetPosition, :370 GetCollisionBox,
// :467 GetType, :517 IsAlive, :864 GetSelectionPositionMS, :873 ModelToWorld,
// :874 WorldToModel, :311 SetOrientation; Entities/EntityAI.c:885
// GetHierarchyParent, :1884 GetInventory, :2047 ServerTakeEntityToTargetAttachment.
// Systems/Inventory/{Inventory.c:138 GetCargo,Cargo.c:28/32 GetItemCount/GetItem}.
// 4_World/Entities/ItemBase/FireplaceBase.c:246-256 real kindling/fuel types,
// :269 m_IsBurning net-sync, :502 Synchronize, :1639 IsBurning, :1760 StartFire;
// :2384 HasAnyKindling. FireplaceBase/FireplaceIndoor.c:99 SetFirePointIndex,
// :104 CanPlaceFireplaceInSelectedSpot, :131 SetSmokePointPosition,
// :145-153 native chimney particles, :303 CanBeIgnitedBy, :332 OnIgnitedThis.
// Classes/UserActionsComponent/Actions/Continuous/ActionLightItemOnFire.c:103-134
// OnFinishProgressServer and real ignition item callbacks. ItemBase.c ignition
// virtuals: 3_Game/Entities/EntityAI.c:538 CanIgniteItem, :574 OnIgnitedTarget;
// :882 GetHierarchyRootPlayer. ItemBase/Matchbox.c:9 CanIgniteItem, :17
// OnIgnitedTarget consumes one real match. Entities/Object.c:305 GetOrientation,
// :1219 IsRuined; Inventory.c:205/220 AttachmentCount/GetAttachmentFromIndex;
// 3_Game/gameplay.c:368 PlayerIdentity.GetId; Entities/Man.c:21 GetIdentity.
// EntityAI.c:586/592 OnIgnitedTargetFailed/OnIgnitedThisFailed;
// 1_Core/proto/EnMath.c:553 Min; EnConvert.c:210 vector.DistanceSq;
// EnScript.c:380/385/407/470 Count/Clear/Insert/RemoveOrdered, :866/902/917
// map Get/Set/Contains; 3_Game/CE/CentralEconomy.c:28 ECE_KEEPHEIGHT.
// EnScript.c:897 GetKey (O(n), bounded by MaxHearths), :906 Remove.
// No Expansion calls or copied code.
// 3_Game/tools/JsonFileLoader.c:69 LoadData; 1_Core/proto/EnSystem.c:397 FileExist;
// EnDebug.c:96 Print. HCGroupIO bounds IO; HCJsonFields preserves missing defaults.
// Spec: no house fire presentation without a replicated burning hearth. Plan:
// observe native fires; bounded provenance registry; unseen funded occupant ignition.
// Tasks: source/tests here; native compile, persistence and two clients remain pending.
class HCHearthConfig
{
    bool Enabled = true;
    int MaxHearths = 64;
    int MaxObjects = 128;
    int MaxInventory = 64;
    int HearthsPerTick = 4;
    int HousesPerScan = 16;
    int MaxLit = 4;
    int MaxSmoke = 2;
    float QueryRadius = 30;
    float AnchorTolerance = 0.35;
    float ActorRange = 3;
    float ObserverRadius = 500;
    int AttemptSeconds = 60;
    protected static ref HCHearthConfig s_Config;
    static HCHearthConfig HCGet()
    {
        if (s_Config) { return s_Config; }
        HCOperatorSettingsRegistry.HCHearthInit();
        s_Config = new HCHearthConfig;
        string path = "$profile:HollowCountry/hearth-fires.json";
        if (!FileExist(path)) { return s_Config; }
        string text;
        string error;
        HCHearthConfig decoded;
        if (!HCGroupIO.Read(path, 4096, text) || !JsonFileLoader<HCHearthConfig>.LoadData(text, decoded, error) || !decoded)
        {
            Print("[HC Hearth] HC_HEARTH_CONFIG_DEFAULTS runtime=PENDING");
            return s_Config;
        }
        s_Config.HCApply(decoded, text);
        return s_Config;
    }
    void HCApply(HCHearthConfig decoded, string text)
    {
        if (HCJsonFields.Has(text, "Enabled")) { Enabled = decoded.Enabled; }
        if (HCJsonFields.Has(text, "MaxHearths") && HCOperatorSettingsRegistry.HCValid("HearthFires.MaxHearths", decoded.MaxHearths)) { MaxHearths = decoded.MaxHearths; }
        if (HCJsonFields.Has(text, "MaxObjects") && HCOperatorSettingsRegistry.HCValid("HearthFires.MaxObjects", decoded.MaxObjects)) { MaxObjects = decoded.MaxObjects; }
        if (HCJsonFields.Has(text, "MaxInventory") && HCOperatorSettingsRegistry.HCValid("HearthFires.MaxInventory", decoded.MaxInventory)) { MaxInventory = decoded.MaxInventory; }
        if (HCJsonFields.Has(text, "HearthsPerTick") && HCOperatorSettingsRegistry.HCValid("HearthFires.HearthsPerTick", decoded.HearthsPerTick)) { HearthsPerTick = decoded.HearthsPerTick; }
        if (HCJsonFields.Has(text, "HousesPerScan") && HCOperatorSettingsRegistry.HCValid("HearthFires.HousesPerScan", decoded.HousesPerScan)) { HousesPerScan = decoded.HousesPerScan; }
        if (HCJsonFields.Has(text, "MaxLit") && HCOperatorSettingsRegistry.HCValid("HearthFires.MaxLit", decoded.MaxLit)) { MaxLit = decoded.MaxLit; }
        if (HCJsonFields.Has(text, "MaxSmoke") && HCOperatorSettingsRegistry.HCValid("HearthFires.MaxSmoke", decoded.MaxSmoke)) { MaxSmoke = decoded.MaxSmoke; }
        if (HCJsonFields.Has(text, "QueryRadius") && HCOperatorSettingsRegistry.HCValid("HearthFires.QueryRadius", decoded.QueryRadius)) { QueryRadius = decoded.QueryRadius; }
        if (HCJsonFields.Has(text, "AnchorTolerance") && HCOperatorSettingsRegistry.HCValid("HearthFires.AnchorTolerance", decoded.AnchorTolerance)) { AnchorTolerance = decoded.AnchorTolerance; }
        if (HCJsonFields.Has(text, "ActorRange") && HCOperatorSettingsRegistry.HCValid("HearthFires.ActorRange", decoded.ActorRange)) { ActorRange = decoded.ActorRange; }
        if (HCJsonFields.Has(text, "ObserverRadius") && HCOperatorSettingsRegistry.HCValid("HearthFires.ObserverRadius", decoded.ObserverRadius)) { ObserverRadius = decoded.ObserverRadius; }
        if (HCJsonFields.Has(text, "AttemptSeconds") && HCOperatorSettingsRegistry.HCValid("HearthFires.AttemptSeconds", decoded.AttemptSeconds)) { AttemptSeconds = decoded.AttemptSeconds; }
    }
}

class HCHearthRecord
{
    FireplaceBase Fire;
    Object StructureHandle;
    string LitByKind;
    string LitById;
    int LitAt;
}

class HCHearthFires
{
    protected static ref array<ref HCHearthRecord> s_Lit = new array<ref HCHearthRecord>;
    protected static ref HCWorkBudget s_Budget = new HCPerfSlices("HearthFires");
    protected static string s_Refusal;
    protected static int s_Cursor;
    protected static int s_HoldoutCursor;
    protected static int s_AttemptCursor;
    protected static EntityAI s_Spending;
    protected static bool s_Running;
    protected static ref HCOperationalStatus s_Status = new HCOperationalStatus;
    protected static ref map<Object, int> s_Attempts = new map<Object, int>;

    static HCOperationalStatus HCGetOperationalStatus()
    {
        HCModuleReadiness.HCDerive(s_Status, s_Running, "", "", "hearth_observer_started");
        return s_Status;
    }
    static bool HCActive() { return s_Running; }
    static bool HCEnabled()
    {
        return HCHearthConfig.HCGet().Enabled && !FileExist("$profile:HollowCountry/acceptance/hearth-fires.disable");
    }
    static void HCStart()
    {
        s_Running = HCEnabled();
        string line = HCV2Admission.Line("HearthFires", s_Running, "EXP-A5", HCV2Gates.Qualified("EXP-A5"));
        HCOperationalStatus status = HCGetOperationalStatus();
        Print(line + " state=" + status.HCState() + " native_visuals=1 runtime=PENDING");
    }
    static void HCStop() { s_Running = false; s_Lit.Clear(); s_Attempts.Clear(); s_Cursor = 0; s_HoldoutCursor = 0; s_AttemptCursor = 0; s_Spending = null; s_Refusal = ""; }
    static bool HCRefuse(string reason)
    {
        if (s_Refusal != reason) { Print("[HC Hearth] refusal=" + reason + " runtime=PENDING"); }
        s_Refusal = reason;
        return false;
    }
    // Only synchronously bracketed native transfers bypass holdout raid detection.
    // All player removals keep the existing callback and snapshot checks.
    static bool HCSpending(EntityAI container) { return s_Spending && s_Spending == container; }
    static bool HCFuelReady(ItemBase kindling, ItemBase wood)
    {
        return kindling && wood;
    }
    static bool HCContains(Object house, Object fire)
    {
        if (!house || !fire) { return false; }
        vector limits[2];
        if (!house.GetCollisionBox(limits)) { return false; }
        vector point = house.WorldToModel(fire.GetPosition());
        return point[0] >= limits[0][0] && point[0] <= limits[1][0] && point[1] >= limits[0][1] && point[1] <= limits[1][1] && point[2] >= limits[0][2] && point[2] <= limits[1][2];
    }
    static bool HCMatches(Object house, FireplaceBase fire)
    {
        if (!house || !fire || !fire.IsBurning() || fire.GetHierarchyParent()) { return false; }
        vector anchor = house.GetSelectionPositionMS("fireplace_point1");
        float tolerance = HCHearthConfig.HCGet().AnchorTolerance;
        if (anchor != vector.Zero && vector.DistanceSq(house.ModelToWorld(anchor), fire.GetPosition()) <= tolerance * tolerance) { return true; }
        return HCContains(house, fire);
    }
    // Native query prefix is capped; overflow yields false negatives, never phantom fires.
    // Client uses only replicated FireplaceBase.IsBurning, no server RPC promises.
    static bool HCHasBurning(Object house)
    {
        if (!house || !HCHearthFires.HCEnabled()) { return false; }
        array<Object> objects = new array<Object>;
        array<CargoBase> cargos = new array<CargoBase>;
        HCHearthConfig config = HCHearthConfig.HCGet();
        GetGame().GetObjectsAtPosition3D(house.GetPosition(), config.QueryRadius, objects, cargos);
        int count = Math.Min(objects.Count(), config.MaxObjects);
        int index = 0;
        while (index < count)
        {
            FireplaceBase fire = FireplaceBase.Cast(objects[index]);
            index = index + 1;
            if (!HCMatches(house, fire)) { continue; }
            if (GetGame().IsServer()) { HCObserve(fire, house); }
            return true;
        }
        return false;
    }
    static void HCObserve(FireplaceBase fire, Object house)
    {
        if (!s_Running || !GetGame().IsServer() || !fire || !fire.IsBurning()) { return; }
        if (!house && !FireplaceIndoor.Cast(fire)) { return; }
        array<ref HCHearthRecord> records = s_Lit;
        foreach (HCHearthRecord existing : records)
        {
            if (existing.Fire != fire) { continue; }
            if (house) { existing.StructureHandle = house; }
            existing.LitByKind = fire.HCHearthLitKind;
            existing.LitById = fire.HCHearthLitId;
            existing.LitAt = fire.HCHearthLitAt;
            if (house && existing.LitByKind == "") { HCRefuse("HC_HEARTH_NATIVE_PROVENANCE_UNKNOWN"); }
            return;
        }
        if (s_Lit.Count() >= HCHearthConfig.HCGet().MaxHearths) { HCRefuse("HC_HEARTH_REGISTRY_CAP"); return; }
        HCHearthRecord row = new HCHearthRecord;
        row.Fire = fire;
        row.StructureHandle = house;
        row.LitByKind = fire.HCHearthLitKind;
        row.LitById = fire.HCHearthLitId;
        row.LitAt = fire.HCHearthLitAt;
        s_Lit.Insert(row);
        if (house && row.LitByKind == "") { HCRefuse("HC_HEARTH_NATIVE_PROVENANCE_UNKNOWN"); }
    }
    // Rotate without copying the map. Each inspected entry spends shared work;
    // removing the current key retains the cursor for its replacement. Fresh
    // cooldowns survive, including when the UTC clock is unavailable.
    static void HCReclaimAttempts()
    {
        int now = HCWorldClock.UTC();
        if (now < 1) { return; }
        int limit = HCHearthConfig.HCGet().HearthsPerTick;
        int examined = 0;
        s_Budget.HCReset(limit);
        while (s_Attempts.Count() > 0 && examined < limit)
        {
            if (!s_Budget.HCContinue() || !HCServer.HCTickWork().HCTakeFor(HCUnitBudget.HC_WORK_HEARTH, 1)) { return; }
            if (s_AttemptCursor >= s_Attempts.Count()) { s_AttemptCursor = 0; }
            Object house = s_Attempts.GetKey(s_AttemptCursor);
            if (now >= s_Attempts.Get(house)) { s_Attempts.Remove(house); }
            else { s_AttemptCursor = s_AttemptCursor + 1; }
            examined = examined + 1;
        }
    }

    static void HCTick()
    {
        if (!s_Running) { return; }
        HCReclaimAttempts();
        s_Budget.HCReset(HCHearthConfig.HCGet().HearthsPerTick);
        int examined = 0;
        while (s_Lit.Count() > 0 && examined < HCHearthConfig.HCGet().HearthsPerTick)
        {
            if (!s_Budget.HCContinue() || !HCServer.HCTickWork().HCTakeFor(HCUnitBudget.HC_WORK_HEARTH, 1)) { return; }
            if (s_Cursor >= s_Lit.Count()) { s_Cursor = 0; }
            HCHearthRecord row = s_Lit[s_Cursor];
            if (!row.Fire || !row.Fire.IsBurning()) { s_Lit.RemoveOrdered(s_Cursor); }
            else
            {
                if (!row.StructureHandle) { row.StructureHandle = HCResolveHouse(row.Fire); }
                if (row.StructureHandle && row.LitByKind == "") { HCRefuse("HC_HEARTH_NATIVE_PROVENANCE_UNKNOWN"); }
                s_Cursor = s_Cursor + 1;
            }
            examined = examined + 1;
        }
        HCHoldouts holdouts = HCHoldouts.Get();
        if (!holdouts || holdouts.Count() == 0 || !HCServer.HCTickWork().HCTakeFor(HCUnitBudget.HC_WORK_HEARTH, 1)) { return; }
        if (s_HoldoutCursor >= holdouts.Count()) { s_HoldoutCursor = 0; }
        int holdoutIndex = s_HoldoutCursor;
        s_HoldoutCursor = s_HoldoutCursor + 1;
        holdouts.HCHearthLight(holdoutIndex);
    }

    static Object HCResolveHouse(FireplaceBase fire)
    {
        array<Object> nearby = new array<Object>;
        array<CargoBase> cargos = new array<CargoBase>;
        HCHearthConfig config = HCHearthConfig.HCGet();
        GetGame().GetObjectsAtPosition3D(fire.GetPosition(), config.QueryRadius, nearby, cargos);
        int count = Math.Min(nearby.Count(), config.MaxObjects);
        for (int index = 0; index < count; index++)
        {
            Object candidate = nearby[index];
            if (Building.Cast(candidate) && HCMatches(candidate, fire)) { return candidate; }
        }
        return null;
    }

    static FireplaceIndoor HCFindIndoor(vector position)
    {
        array<Object> nearby = new array<Object>;
        array<CargoBase> cargos = new array<CargoBase>;
        HCHearthConfig config = HCHearthConfig.HCGet();
        GetGame().GetObjectsAtPosition3D(position, config.AnchorTolerance, nearby, cargos);
        if (nearby.Count() > config.MaxObjects) { return null; }
        foreach (Object candidate : nearby)
        {
            FireplaceIndoor indoor = FireplaceIndoor.Cast(candidate);
            if (indoor && !indoor.GetHierarchyParent() && vector.DistanceSq(indoor.GetPosition(), position) <= config.AnchorTolerance * config.AnchorTolerance) { return indoor; }
        }
        return null;
    }

    // Shared port: holdout/camp/situation callers must supply their actual bound
    // occupant, physical stash and stable party id. No logical stock becomes fuel.
    static bool HCLight(Object house, EntityAI actor, EntityAI stash, string kind, string actorId)
    {
        if (!HCHearthFires.s_Running || !GetGame().IsServer()) { return false; }
        if (!house || !actor || !actor.IsAlive() || !stash || actorId == "") { return HCRefuse("HC_HEARTH_NO_OCCUPANT"); }
        if (kind != "holdout" && kind != "camp" && kind != "situation") { return HCRefuse("HC_HEARTH_BAD_PROVENANCE"); }
        HCHearthConfig config = HCHearthConfig.HCGet();
        int now = HCWorldClock.UTC();
        if (now < 1) { return HCRefuse("HC_HEARTH_CLOCK_INVALID"); }
        if (HCHearthFires.s_Attempts.Contains(house) && now < HCHearthFires.s_Attempts.Get(house)) { return false; }
        if (!HCHearthFires.s_Attempts.Contains(house) && HCHearthFires.s_Attempts.Count() >= config.MaxHearths) { return HCRefuse("HC_HEARTH_ATTEMPT_CAP"); }
        HCHearthFires.s_Attempts.Set(house, now + config.AttemptSeconds);
        HCHearthFires.s_Budget.HCReset(1);
        if (HCHearthFires.s_Lit.Count() >= config.MaxHearths) { return HCRefuse("HC_HEARTH_REGISTRY_CAP"); }
        vector anchor = house.GetSelectionPositionMS("fireplace_point1");
        vector outlet = house.GetSelectionPositionMS("fireplace_smoke1");
        if (anchor == vector.Zero || outlet == vector.Zero) { return HCRefuse("HC_HEARTH_NO_ANCHOR"); }
        vector position = house.ModelToWorld(anchor);
        if (vector.DistanceSq(actor.GetPosition(), position) > config.ActorRange * config.ActorRange) { return HCRefuse("HC_HEARTH_OCCUPANT_TOO_FAR"); }
        if (vector.DistanceSq(stash.GetPosition(), position) > config.QueryRadius * config.QueryRadius || stash.GetHierarchyRootPlayer()) { return HCRefuse("HC_HEARTH_STASH_UNAVAILABLE"); }
        if (!HCObserverTransitionGate.CanTransition(position, config.ObserverRadius)) { return HCRefuse("HC_HEARTH_OBSERVED"); }
        if (!HCHearthFires.s_Budget.HCContinue() || !HCServer.HCTickWork().HCTakeFor(HCUnitBudget.HC_WORK_HEARTH, 1)) { return false; }
        FireplaceIndoor fire = HCFindIndoor(position);
        if (fire && fire.IsBurning()) { HCObserve(fire, house); return true; }
        CargoBase cargo = stash.GetInventory().GetCargo();
        if (!cargo || cargo.GetItemCount() > config.MaxInventory) { return HCRefuse("HC_HEARTH_NO_FUEL"); }
        ItemBase kindling;
        ItemBase wood;
        ItemBase igniter;
        int fuelIndex = 0;
        while (fuelIndex < cargo.GetItemCount())
        {
            ItemBase item = ItemBase.Cast(cargo.GetItem(fuelIndex));
            fuelIndex = fuelIndex + 1;
            if (!item || item.IsRuined()) { continue; }
            string itemKind = item.GetType();
            if (!kindling && (itemKind == "Paper" || itemKind == "Bark_Birch" || itemKind == "Bark_Oak")) { kindling = item; }
            if (!wood && (itemKind == "Firewood" || itemKind == "WoodenStick")) { wood = item; }
            if (!igniter && itemKind == "Matchbox") { igniter = item; }
        }
        // Resume partial native transfers without recreating or discarding loot.
        if (fire)
        {
            int attachedCount = fire.GetInventory().AttachmentCount();
            if (attachedCount > config.MaxInventory) { return HCRefuse("HC_HEARTH_ATTACHMENT_CAP"); }
            int attachedIndex = 0;
            while (attachedIndex < attachedCount)
            {
                ItemBase attached = ItemBase.Cast(fire.GetInventory().GetAttachmentFromIndex(attachedIndex));
                attachedIndex = attachedIndex + 1;
                if (!attached || attached.IsRuined()) { continue; }
                string attachedKind = attached.GetType();
                if (attachedKind == "Paper" || attachedKind == "Bark_Birch" || attachedKind == "Bark_Oak") { kindling = attached; }
                if (attachedKind == "Firewood" || attachedKind == "WoodenStick") { wood = attached; }
            }
        }
        if (!HCFuelReady(kindling, wood)) { return HCRefuse("HC_HEARTH_NO_FUEL"); }
        if (!igniter || !igniter.CanIgniteItem(null)) { return HCRefuse("HC_HEARTH_NO_IGNITER"); }
        vector freePosition;
        vector rotationPoint;
        if (!fire)
        {
            if (!FireplaceIndoor.CanPlaceFireplaceInSelectedSpot(house, 1, freePosition, rotationPoint)) { return HCRefuse("HC_HEARTH_OCCUPIED"); }
            // Only the empty container is created. Original fuel identities move
            // through native inventory; burning consumes the attached stacks.
            fire = FireplaceIndoor.Cast(GetGame().CreateObjectEx("FireplaceIndoor", position, ECE_KEEPHEIGHT));
            if (!fire) { return HCRefuse("HC_HEARTH_CREATE_FAILED"); }
            fire.SetFirePointIndex(1);
            fire.SetSmokePointPosition(house.ModelToWorld(outlet));
            fire.SetOrientation(house.GetOrientation());
            fire.Synchronize();
        }
        HCHearthFires.s_Spending = stash;
        bool movedKindling = kindling.GetHierarchyParent() == fire;
        if (!movedKindling) { movedKindling = stash.ServerTakeEntityToTargetAttachment(fire, kindling); }
        bool movedWood = wood.GetHierarchyParent() == fire;
        if (movedKindling && !movedWood) { movedWood = stash.ServerTakeEntityToTargetAttachment(fire, wood); }
        HCHearthFires.s_Spending = null;
        if (!movedKindling) { return HCRefuse("HC_HEARTH_KINDLING_TRANSFER_FAILED"); }
        if (!movedWood) { return HCRefuse("HC_HEARTH_WOOD_TRANSFER_FAILED"); }
        if (!fire.CanBeIgnitedBy(igniter)) { return HCRefuse("HC_HEARTH_CANNOT_IGNITE"); }
        if (!fire.IsThisIgnitionSuccessful(igniter))
        {
            igniter.OnIgnitedTargetFailed(fire);
            fire.OnIgnitedThisFailed(igniter);
            return HCRefuse("HC_HEARTH_IGNITION_FAILED");
        }
        fire.HCHearthLitKind = kind;
        fire.HCHearthLitId = actorId;
        fire.HCHearthLitAt = HCWorldClock.UTC();
        igniter.OnIgnitedTarget(fire);
        fire.OnIgnitedThis(igniter);
        if (!fire.IsBurning()) { return HCRefuse("HC_HEARTH_NOT_BURNING"); }
        HCObserve(fire, house);
        HCHearthFires.s_Refusal = "";
        Print("[HC Hearth] HC_HEARTH_LIT kind=" + kind + " id=" + actorId + " at=" + fire.HCHearthLitAt.ToString() + " runtime=PENDING");
        return true;
    }
}

modded class FireplaceBase
{
    string HCHearthLitKind;
    string HCHearthLitId;
    int HCHearthLitAt;
    override void StartFire(bool force_start = false)
    {
        bool wasBurning = IsBurning();
        super.StartFire(force_start);
        if (!wasBurning && IsBurning()) { HCHearthFires.HCObserve(this, null); }
    }
}

// Record only a successful native player ignition; never infer a nearby player
// lit a pre-existing fire. Unknown/restarted native fires remain explicitly unknown.
modded class ActionLightItemOnFire
{
    override void OnFinishProgressServer(ActionData action_data)
    {
        FireplaceBase targetFire;
        if (action_data.m_Target) { targetFire = FireplaceBase.Cast(action_data.m_Target.GetObject()); }
        if (!targetFire) { targetFire = FireplaceBase.Cast(action_data.m_MainItem); }
        bool wasBurning = false;
        if (targetFire) { wasBurning = targetFire.IsBurning(); }
        super.OnFinishProgressServer(action_data);
        if (targetFire && !wasBurning && targetFire.IsBurning() && HCHearthFires.HCActive())
        {
            PlayerIdentity identity = action_data.m_Player.GetIdentity();
            if (identity)
            {
                targetFire.HCHearthLitKind = "player";
                targetFire.HCHearthLitId = identity.GetId();
                targetFire.HCHearthLitAt = HCWorldClock.UTC();
                HCHearthFires.HCObserve(targetFire, null);
                Print("[HC Hearth] HC_HEARTH_LIT kind=player runtime=PENDING");
            }
        }
    }
}
