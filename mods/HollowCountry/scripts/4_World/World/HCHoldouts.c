// W5-PERF-5: catalog <=4 authored rows/tick (4 ms cooperative guard);
// One row starts per >=10s; native stages/body probes resume on following ticks.
// Catalog checkpoints coalesce, creation/spend/raid
// barriers retain synchronous verified saves. Native scripts-1.30.164289:
// 3_Game/Global/Game.c:914 GetTickTime; shared guard in HCWorkBudget.c.
// LC-T408, #102. Native evidence: installed scripts-1.30.164289:
// 1_Core/proto/EnSystem.c:397 FileExist, :525 MakeDirectory, :528 DeleteFile,
// :531 CopyFile; 3_Game/tools/JsonFileLoader.c:69 LoadData, :85 MakeData;
// 3_Game/Global/Game.c:703 CreateObjectEx, :930 GetObjectsAtPosition3D,
// :1333 IsBoxColliding; 3_Game/Entities/Object.c:287 GetPosition, :305 GetOrientation,
// :311 SetOrientation, :517 IsAlive, :873 ModelToWorld, :1219 IsRuined;
// 3_Game/Entities/EntityAI.c:885 GetHierarchyParent, :3374 GetPersistentID,
// :3377 SetLifetime, :3384 SetLifetimeMax; 3_Game/CE/CentralEconomy.c:9 ECE_SETUP,
// :17 ECE_CREATEPHYSICS, :28 ECE_KEEPHEIGHT (no nonpersistent/dynamic flags).
// 3_Game/Global/Game.c:1120 IsServer; gameplay.c:636 GetGame;
// 3_Game/Entities/EntityAI.c:1884 GetInventory; Inventory/Inventory.c:138 GetCargo;
// Inventory/Cargo.c:28 GetItemCount, :32 GetItem; 1_Core/proto/EnScript.c:380
// Count, :385 Clear, :394 Find, :407 Insert, :463 Remove, :902 map.Set,
// :917 map.Contains, :866 map.Get; EnString.c:199 Length, :240 IndexOf;
// EnConvert.c:30 int.ToString, :210 vector.DistanceSq; EnDebug.c:96 Print.
// 3_Game/Entities/EntityAI.c:1104 EEKilled(Object killer), :1248 EECargoOut(EntityAI item);
// 3_Game/Entities/Man.c:21 GetIdentity; 4_World/Entities/ItemBase/Gear/Camping/camping.c:17 WoodenCrate.
// HCV2ThreatStore/HCGroupIO perform bounded serialization/readback. No RenameFile
// exists: temp intent -> verified backup -> copy/readback promotion is fail-closed,
// NOT OS atomic rename/fsync or atomic with Hive. Interrupted saves stop the feature.
// Own catalog is bounded by AILimits.MaxHoldouts, using unique covered houses;
// actual placement, persistence, occupancy, pathing and lights remain UNOBSERVED.

class HCEncounterStore<Class T>
{
    protected ref HCV2ThreatStore<T> m_Writer = new HCV2ThreatStore<T>;
    protected string m_Path;
    protected bool m_Fault;
    // Raw image of the last successful file load; owners may check key presence
    // (native load zero-fills absent ints). Taken once, then cleared.
    protected string m_LoadedText;

    void HCEncounterStore(string name) { m_Path = "$profile:HollowCountry/" + name + ".json"; }
    bool Healthy() { return !m_Fault; }
    string HCTakeLoadedText()
    {
        string text = m_LoadedText;
        m_LoadedText = "";
        return text;
    }
    bool Fault()
    {
        if (!m_Fault) Print("[HollowCountry] V2 encounter store inactive: preserve " + m_Path + ", .tmp and .bak; recovery required");
        m_Fault = true;
        return false;
    }

    T Load(T fresh, string collection)
    {
        if (!HCV2ThreatStore<T>.CanOpen(m_Path)) { Fault(); return null; }
        T result;
        if (FileExist(m_Path))
        {
            string encoded = HCWorldStore.Read(m_Path);
            if (encoded.Length() > 262144 || encoded.IndexOf("\"Version\"") < 0 || encoded.IndexOf("\"" + collection + "\"") < 0) { Fault(); return null; }
            if (!HCV2ThreatStore<T>.Load(m_Path, 262144, result)) { Fault(); return null; }
            m_LoadedText = encoded;
            return result;
        }
        if (!Save(fresh)) return null;
        return fresh;
    }

    bool Save(T data)
    {
        if (m_Fault || !data) return false;
        if (!m_Writer.FinishSave() || !HCV2ThreatStore<T>.Save(m_Path, data, 262144)) return Fault();
        return true;
    }

    bool SaveInFlight() { return m_Writer.SaveInFlight(); }
    // Disk stage boundaries: write_tmp/read_tmp retain old primary + intent;
    // copy_backup retains old primary/backup + intent; copy_primary/read_primary
    // retain new primary, old backup and intent; clear_intent admits new primary.
    int SaveStep(T data)
    {
        if (m_Fault || !data) { return HCSaveJob.STEP_FAILED; }
        int result = m_Writer.SaveStep(m_Path, data, 262144);
        if (result == HCSaveJob.STEP_FAILED) { Fault(); }
        return result;
    }

}

class HCEncounterCache
{
    vector Position;
    vector Orientation;
    string EntityRef;
    // 0 unmade, 1 creation intent, 2 persistent link, 3 lost/quarantined.
    int Phase;
}

// One real, ordinary vanilla crate, never respawned after intent. Runtime handle
// is separate from the DTO; no inventory is serialized, copied or reconstructed.
class HCEncounterCacheIO
{
    EntityAI Handle;

    static bool Valid(HCEncounterCache row)
    {
        if (!row || row.Phase < 0 || row.Phase > 3 || !HCWorldLimits.Position(row.Position)) return false;
        if (row.EntityRef.Length() > 96 || (row.Phase == 2 && row.EntityRef == "")) return false;
        return HCInteriorRules.SaneVector(row.Orientation, 360);
    }

    bool Clear(HCEncounterCache row, Object structure)
    {
        array<Object> excluded = new array<Object>;
        if (structure) excluded.Insert(structure);
        // Room bounds/door keepouts are checked before excluding the building.
        return !GetGame().IsBoxColliding(row.Position + Vector(0, 0.22, 0), row.Orientation, "0.85 0.45 0.65", excluded);
    }

    void Create(HCEncounterCache row)
    {
        // Caller MUST persist Phase=1 first. No ECE_EQUIP flags or cargo creation.
        if (!row || row.Phase != 1 || Handle) return;
        Handle = EntityAI.Cast(GetGame().CreateObjectEx("WoodenCrate", row.Position, ECE_SETUP | ECE_KEEPHEIGHT | ECE_CREATEPHYSICS, RF_IGNORE));
        if (!Handle) { row.Phase = 3; return; }
        Handle.SetOrientation(row.Orientation);
        Handle.SetLifetimeMax(3888000);
        Handle.SetLifetime(3888000);
        LinkCache(row);
    }

    bool LinkCache(HCEncounterCache row)
    {
        if (row.Phase == 0 || row.Phase == 3) return false;
        if (!Handle && row.Phase == 2)
        {
            array<Object> objects = new array<Object>;
            array<CargoBase> cargos = new array<CargoBase>;
            GetGame().GetObjectsAtPosition3D(row.Position, 5, objects, cargos);
            if (objects.Count() > 256) return false;
            foreach (Object object : objects)
            {
                EntityAI candidate = EntityAI.Cast(object);
                if (candidate && candidate.GetType() == "WoodenCrate" && HCSearchSupplyRegistry.PersistentId(candidate) == row.EntityRef)
                {
                    if (Handle) { Handle = null; row.Phase = 3; return false; }
                    Handle = candidate;
                }
            }
        }
        // An unresolved creation intent across a crash is never recreated.
        if (!Handle || Handle.IsRuined() || Handle.GetHierarchyParent() || Handle.GetHierarchyRootPlayer())
        {
            row.Phase = 3;
            return false;
        }
        if (row.Phase == 1)
        {
            string persistentId = HCSearchSupplyRegistry.PersistentId(Handle);
            // Hive may assign its id later; retain this live handle until then.
            if (persistentId == "") return false;
            row.EntityRef = persistentId;
            row.Phase = 2;
        }
        if (HCSearchSupplyRegistry.PersistentId(Handle) != row.EntityRef) { row.Phase = 3; return false; }
        return true;
    }
}

class HCHoldoutRow
{
    ref HCWorldHoldout Ledger = new HCWorldHoldout;
    ref HCEncounterCache Cache = new HCEncounterCache;
    ref HCAICampLife Camp = new HCAICampLife;
    int StockAttempts;
    int StockDay;
    bool Published;
    ref array<string> Contents = new array<string>;
}

class HCHoldoutState
{
    int Version = 3;
    ref HCAICampPolicy CampPolicy = new HCAICampPolicy;
    ref HCAICampResources Resources = new HCAICampResources;
    string TemplatePin;
    ref array<ref HCHoldoutRow> Rows = new array<ref HCHoldoutRow>;
}

class HCHoldoutBody
{
    string HoldoutId;
    EntityAI Body;
}

class HCHoldouts : HCModule
{
    protected static HCHoldouts s_Instance;
    protected ref HCEncounterStore<HCHoldoutState> m_Store;
    protected ref HCHoldoutState m_State;
    protected ref array<ref HCEncounterCacheIO> m_Caches = new array<ref HCEncounterCacheIO>;
    protected ref array<ref HCHoldoutBody> m_Bodies = new array<ref HCHoldoutBody>;
    protected ref HCAICampDebug m_CampDebug;
    protected ref HCUnitBudget m_CampUnits = new HCUnitBudget;
    protected ref HCOperationalStatus m_Operational = new HCOperationalStatus;
    protected ref map<string, string> m_CampRefusals = new map<string, string>;
    // #190: one detached JSON snapshot per row for the routine view, rebuilt only
    // when the row's exposed ledger fields change. Bounded by the row count.
    protected ref array<ref HCWorldHoldout> m_ViewHomes = new array<ref HCWorldHoldout>;
    protected ref array<string> m_ViewKeys = new array<string>;
    protected int m_Next;
    protected int m_TickPhase;
    protected int m_TickMeasuredStage;
    protected int m_TickIndex;
    protected int m_BodyNext;
    protected Object m_TickStructure;
    protected bool m_CatalogWorked;
    protected float m_Elapsed;
    protected bool m_Ready;
    protected bool m_Dirty;
    protected int m_Reports;
    protected bool m_WaitReported;
    protected bool m_CatalogDirty;
    protected ref HCHoldoutSaveJob m_SaveJob;
    protected ref HCWorkBudget m_WorkBudget = new HCPerfSlices("Holdouts");
    // Runtime diagnostics only, bounded by AILimits.MaxHoldouts.
    protected ref map<string, string> m_PublishRefusals = new map<string, string>;

    static HCHoldouts Get() { if (s_Instance && s_Instance.m_Ready) { return s_Instance; } return null; }

    static void CargoRemoved(EntityAI container)
    {
        HCHoldouts module = HCHoldouts.Get();
        if (!module || !GetGame().IsServer()) return;
        if (HCHearthFires.HCSpending(container)) return;
        for (int cacheIndex = 0; cacheIndex < module.Count(); cacheIndex++)
        {
            HCHoldoutRow row = module.m_State.Rows[cacheIndex];
            if (module.m_Caches[cacheIndex].Handle == container && (row.Ledger.State == "OCCUPIED" || row.Ledger.State == "ALERT"))
            {
                module.HCRaidCamp(cacheIndex);
                return;
            }
        }
    }

    static void OccupantKilled(EntityAI body)
    {
        HCHoldouts module = HCHoldouts.Get();
        if (!module || !GetGame().IsServer()) return;
        for (int killedIndex = module.m_Bodies.Count() - 1; killedIndex >= 0; killedIndex--)
        {
            HCHoldoutBody binding = module.m_Bodies[killedIndex];
            if (binding.Body != body) continue;
            module.m_Bodies.Remove(killedIndex);
            for (int holdoutIndex = 0; holdoutIndex < module.Count(); holdoutIndex++)
            {
                if (module.m_State.Rows[holdoutIndex].Ledger.Id == binding.HoldoutId)
                {
                    HCAICampLifecycle.HCDeath(module.m_State.Rows[holdoutIndex].Camp);
                    module.m_Dirty = true;
                    module.HCRaidCamp(holdoutIndex);
                    module.SaveChanged();
                    return;
                }
            }
        }
    }
    override string GetName() { return "Holdouts"; }
    override HCOperationalStatus HCGetOperationalStatus() { return m_Operational; }
    override bool IsEnabled(HCSettings settings)
    {
        bool enabled = settings && settings.EnableEncounters;
        if (!enabled) { m_Operational.HCPublish("off", "encounters_disabled"); }
        return enabled;
    }
    int Count() { if (!m_State) { return 0; } return m_State.Rows.Count(); }

    override void OnStart(HCSettings settings)
    {
        Print(HCV2Admission.Line("Holdouts", true, "EXP-L4", HCV2Gates.Qualified("EXP-L4")));
        m_Store = new HCEncounterStore<HCHoldoutState>("holdouts");
        // Schema 1 had free occupants. Never infer seed reserves or import them
        // repeatedly; preserve the old image for an explicit operator migration.
        string priorPath = "$profile:HollowCountry/holdouts.json";
        bool hasPrior = FileExist(priorPath);
        string priorImage;
        if (hasPrior) { priorImage = HCWorldStore.Read(priorPath); }
        if (hasPrior && priorImage.IndexOf("\"CampPolicy\"") < 0)
        {
            m_Operational.HCPublish("refused", "HC16_LEGACY_UNFUNDED_STATE");
            Print("[HC Plan] HC-16 camp=none level=-1 supply=0 roles=0 state=refused refusal=HC16_LEGACY_UNFUNDED_STATE runtime=PENDING");
            return;
        }
        m_State = m_Store.Load(new HCHoldoutState, "Rows");
        if (!m_State || m_State.Version != 3 || !m_State.Rows || m_State.Rows.Count() > HCAILimits.Get().MaxHoldouts) { HCRefuseState(); return; }
        // Schema 3 is an HC-written journal image. Missing/defaulted fields,
        // unknown fields or a truncated but parseable image must not seed a new
        // reserve. Preserve noncanonical edits for explicit recovery.
        string canonical;
        string encodeError;
        if (hasPrior)
        {
            if (!JsonFileLoader<HCHoldoutState>.MakeData(m_State, canonical, encodeError) || canonical != priorImage) { HCRefuseState(); return; }
        }
        if (!m_State.CampPolicy || !m_State.CampPolicy.HCValid() || !m_State.Resources) { HCRefuseState(); return; }
        if (m_State.Resources.Stock < 0 || m_State.Resources.Stock > m_State.CampPolicy.ReserveCap) { HCRefuseState(); return; }
        if (m_State.Resources.Population < 0 || m_State.Resources.Population > m_State.CampPolicy.ReservePopulationCap) { HCRefuseState(); return; }
        int now = HCWorldClock.UTC();
        if (now < 1 || m_State.Resources.ReserveAt < 0 || m_State.Resources.ReserveAt > now || m_State.Resources.Refunded < 0) { HCRefuseState(); return; }
        map<string, bool> ids = new map<string, bool>;
        int allocatedPopulation = m_State.Resources.Population;
        int occupied = 0;
        foreach (HCHoldoutRow row : m_State.Rows)
        {
            if (!row || !row.Ledger || !HCEncounterCacheIO.Valid(row.Cache) || ids.Contains(row.Ledger.Id) || !HCWorldLimits.Token(row.Ledger.Id) || !HCWorldLimits.Token(row.Ledger.HouseClass) || !HCWorldLimits.Position(row.Ledger.HousePos)) { HCRefuseState(); return; }
            if (row.Ledger.State != "DORMANT" && row.Ledger.State != "OCCUPIED" && row.Ledger.State != "ALERT" && row.Ledger.State != "RAIDED" && row.Ledger.State != "ABANDONED") { HCRefuseState(); return; }
            if (row.Ledger.Since < 0 || row.Ledger.ReoccupyAfter < 0 || row.Ledger.Occupants < 0 || row.Ledger.Occupants > HCAILimits.SIZE_CEILING || row.StockAttempts < 0 || row.StockAttempts > 3 || row.StockDay < 0 || !row.Contents || row.Contents.Count() > 32) { HCRefuseState(); return; }
            if (row.Ledger.State == "RAIDED" && row.Ledger.ReoccupyAfter - row.Ledger.Since < 60) { HCRefuseState(); return; }
            if (!HCAICampLifecycle.HCValidLife(row.Camp, m_State.CampPolicy) || row.Camp.Home != row.Ledger.Id) { HCRefuseState(); return; }
            if (row.Camp.Allocated)
            {
                if (row.Camp.Party != "holdout:" + row.Ledger.Id) { HCRefuseState(); return; }
                allocatedPopulation += row.Camp.Population;
            }
            if (row.Ledger.Occupants > 0 && (row.Camp.Level < 0 || row.Ledger.Occupants != row.Camp.Population)) { HCRefuseState(); return; }
            bool terminal = row.Ledger.State == "RAIDED" || row.Ledger.State == "ABANDONED";
            if (terminal && row.Camp.Allocated && !row.Camp.Refunded) { HCRefuseState(); return; }
            if (row.Camp.Refunded && (!terminal || row.Ledger.Occupants != 0)) { HCRefuseState(); return; }
            if (row.Camp.Allocated && m_State.Resources.ReserveAt == 0) { HCRefuseState(); return; }
            if (row.Ledger.State == "RAIDED" && row.Camp.ReoccupyAfter != row.Ledger.ReoccupyAfter) { HCRefuseState(); return; }
            ids.Set(row.Ledger.Id, true);
            if (row.Ledger.Occupants > 0)
            {
                if (!SiteAvailable(row)) { HCRefuseState(); return; }
                occupied++;
            }
            row.Published = false;
            m_Caches.Insert(new HCEncounterCacheIO);
        }
        if (allocatedPopulation > m_State.CampPolicy.ReservePopulationCap) { HCRefuseState(); return; }
        if (occupied > HCAILimits.Get().MaxOccupiedPlaces) { HCRefuseState(); return; }
        // Migrate only historical shipped lockouts. Custom operator timing is
        // retained. Validate the original canonical journal before changing it.
        HCAICampPolicy currentPolicy = new HCAICampPolicy;
        int oldLockout = m_State.CampPolicy.RaidLockoutSeconds;
        int configuredLockout = HCAICampLifecycle.HCConfiguredLockout();
        if (configuredLockout < 0)
        {
            m_Operational.HCPublish("refused", "HC16_respawn_config_invalid");
            Print("[HC Holdouts] respawn config refused file=ai-camp-policy.json; runtime=PENDING");
            return;
        }
        if (configuredLockout > 0 && configuredLockout != oldLockout)
        {
            m_State.CampPolicy.RaidLockoutSeconds = configuredLockout;
            m_Dirty = true;
        }
        else if (configuredLockout == 0 && (oldLockout == 604800 || oldLockout == 21600))
        {
            m_State.CampPolicy.RaidLockoutSeconds = currentPolicy.RaidLockoutSeconds;
            m_Dirty = true;
        }
        int deadlineLimit = now + m_State.CampPolicy.RaidLockoutSeconds;
        array<ref HCHoldoutRow> respawnRows = m_State.Rows;
        foreach (HCHoldoutRow respawnRow : respawnRows)
        {
            if (respawnRow.Camp.ReoccupyAfter > deadlineLimit || respawnRow.Ledger.ReoccupyAfter > deadlineLimit)
            {
                respawnRow.Camp.ReoccupyAfter = deadlineLimit;
                respawnRow.Ledger.ReoccupyAfter = deadlineLimit;
                respawnRow.Published = false;
                m_Dirty = true;
            }
        }
        if (m_Dirty) { Print("[HC Holdouts] respawn policy migrated/clamped; runtime=PENDING"); }
        s_Instance = this;
        m_SaveJob = new HCHoldoutSaveJob;
        m_SaveJob.Owner = this;
        HCSaveScheduler.HCRegister(m_SaveJob);
        m_Ready = true;
        if (settings && settings.EnableDebugSnapshot)
        {
            m_CampDebug = new HCAICampDebug;
            m_CampDebug.Owner = this;
            HCDebugSnapshot.HCRegister(m_CampDebug);
        }
        m_Operational.HCPublish("ready", "HC16_funded_store_ready_runtime_pending");
        string receipt = "[HC Plan] HC-16 camp=none level=-1 supply=" + m_State.Resources.Stock.ToString();
        receipt += " reserve=" + m_State.Resources.Stock.ToString() + " cap=" + m_State.CampPolicy.ReserveCap.ToString();
        receipt += " refunded=" + m_State.Resources.Refunded.ToString() + " roles=0 state=ready refusal=EAT_FIRE_REPAIR_UNPROVEN runtime=PENDING";
        Print("" + receipt);
        Print("[HollowCountry] V2 holdouts ready catalog/occupied caps from AILimits raid_lockout=" + m_State.CampPolicy.RaidLockoutSeconds.ToString() + "s; bodies require materializer runtime=PENDING");
        HCSyncLights();
    }

    protected void HCRefuseState()
    {
        m_Operational.HCPublish("refused", "HC16_invalid_or_unfunded_state");
        Print("[HC Plan] HC-16 camp=none level=-1 supply=0 roles=0 state=refused refusal=STATE_INVALID runtime=PENDING");
        Print("[HollowCountry] V2 holdouts refused: invalid holdouts.json state or lowered AILimits; preserve file, .tmp and .bak");
    }

    bool SaveChanged()
    {
        if (!m_Dirty && !m_Store.SaveInFlight()) { return true; }
        if (!m_Store.Save(m_State)) { m_Ready = false; m_Operational.HCPublish("refused", "HC16_store_uncertain"); HCSyncLights(); return false; }
        m_Dirty = false;
        m_CatalogDirty = false;
        if (m_SaveJob)
        {
            m_SaveJob.HCDirty = false;
            m_SaveJob.HCInFlight = false;
            m_SaveJob.HCDue = GetGame().GetTickTime() + 60;
        }
        return true;
    }

    int HCStepCatalog()
    {
        if (!m_Ready) { return HCSaveJob.STEP_FAILED; }
        bool starting = !m_Store.SaveInFlight();
        int result = m_Store.SaveStep(m_State);
        if (starting && result == HCSaveJob.STEP_MORE) { m_Dirty = false; }
        if (result == HCSaveJob.STEP_FAILED)
        {
            m_Ready = false;
            m_Operational.HCPublish("refused", "HC16_store_uncertain");
            HCSyncLights();
        }
        if (result == HCSaveJob.STEP_DONE)
        {
            // A newer mutation needs another snapshot before reporting completion.
            if (m_Dirty) { return HCSaveJob.STEP_MORE; }
            m_CatalogDirty = false;
            Print("[HollowCountry] V2 holdouts catalog houses=" + Count().ToString() + "/" + HCAILimits.Get().MaxHoldouts.ToString());
        }
        return result;
    }

    bool HCFlushCatalog()
    {
        if (!m_Ready) { return false; }
        if (!SaveChanged()) { return false; }
        Print("[HollowCountry] V2 holdouts catalog houses=" + Count().ToString() + "/" + HCAILimits.Get().MaxHoldouts.ToString());
        return true;
    }

    bool SiteAvailable(HCHoldoutRow candidate)
    {
        foreach (HCHoldoutRow occupiedSite : m_State.Rows)
        {
            if (!occupiedSite || !occupiedSite.Ledger) return false;
            if (occupiedSite == candidate || occupiedSite.Ledger.Occupants == 0) continue;
            if (occupiedSite.Ledger.Id == candidate.Ledger.Id || vector.DistanceSq(occupiedSite.Ledger.HousePos, candidate.Ledger.HousePos) <= 1) return false;
        }
        return true;
    }

    // Every durable transition refreshes the detached world copy, including
    // ALERT, ABANDONED and the first occupancy after the raid lockout.
    void PublishState(HCHoldoutRow row)
    {
        HCWorldModule world = HCWorldModule.Get();
        string reason = "world unavailable";
        if (world)
        {
            row.Ledger.CacheRef = row.Cache.EntityRef;
            bool wasPublished = row.Published;
            row.Published = world.UpsertHoldout(row.Ledger);
            if (row.Published)
            {
                if (!wasPublished) { m_Dirty = true; }
                m_PublishRefusals.Set(row.Ledger.Id, "");
                world.AddHoldoutFact(row.Ledger);
                HCSyncLights();
                return;
            }
            reason = world.HoldoutRefusal();
        }
        if (m_PublishRefusals.Get(row.Ledger.Id) != reason)
        {
            m_PublishRefusals.Set(row.Ledger.Id, reason);
            Print("[HollowCountry] V2 holdout publish refused id=" + row.Ledger.Id + " reason=" + reason);
        }
    }

    array<ref HCAICampLife> HCCampHomes()
    {
        array<ref HCAICampLife> homes = new array<ref HCAICampLife>();
        foreach (HCHoldoutRow homeRow : m_State.Rows) { homes.Insert(homeRow.Camp); }
        return homes;
    }

    void HCDescribeCamp(HCDebugSnapshot snapshot, int index)
    {
        if (!m_Ready || index < 0 || index >= Count()) { return; }
        HCHoldoutRow row = m_State.Rows[index];
        string detail = "logical level=" + row.Camp.Level.ToString() + " supply=" + row.Camp.Supply.ToString();
        detail += " population=" + row.Camp.Population.ToString() + " runtime=PENDING";
        snapshot.AddPoint("ai-camps", row.Ledger.Id, row.Ledger.HousePos, row.Ledger.State, detail);
    }

    void HCLogCamp(HCHoldoutRow row, string state, string refusal)
    {
        if (state == "ready") { m_CampRefusals.Set(row.Ledger.Id, ""); }
        string line = "[HC Plan] HC-16 camp=" + row.Ledger.Id + " level=" + row.Camp.Level.ToString();
        line += " supply=" + row.Camp.Supply.ToString() + " roles=0 state=" + state;
        Print(line + " refusal=" + refusal + " runtime=PENDING");
    }

    bool HCStepCamp(int index, int now)
    {
        if (!m_Ready || !m_State || index < 0 || index >= Count() || now < 1) { return false; }
        HCHoldoutRow row = m_State.Rows[index];
        if (now < row.Ledger.Since) { return false; }
        HCAICampPolicy policy = m_State.CampPolicy;
        // Scalar reserve update on the existing bounded step, before site/cache
        // gates. An unresolved cache cannot stop the world's logical recovery.
        if (HCAICampLifecycle.HCReserveDue(m_State.Resources, now, policy))
        {
            if (HCAICampLifecycle.HCReplenish(m_State.Resources, HCCampHomes(), now, policy))
            {
                m_Dirty = true;
                if (!SaveChanged()) { m_Ready = false; return false; }
            }
        }
        if (now < m_State.Resources.ReserveAt) { m_Ready = false; HCRefuseState(); return false; }
        if (!SiteAvailable(row) || !Cache(index)) { return false; }
        if (now < row.Ledger.ReoccupyAfter) { return false; }
        string priorState = row.Ledger.State;
        bool clearAlert = priorState == "ALERT" && now - row.Ledger.Since >= 3600;
        bool changed = clearAlert;
        if (!row.Camp.Allocated || row.Camp.Refunded)
        {
            if (Occupied() >= HCAILimits.Get().MaxOccupiedPlaces) { return false; }
            int population = HCAILimits.GroupSize(HCAILimits.Get().WorldSeed, row.Ledger.Id, "holdout");
            if (row.Camp.Population > 0) { population = row.Camp.Population; }
            if (!HCAICampLifecycle.HCFound(row.Camp, m_State.Resources, HCCampHomes(), "holdout:" + row.Ledger.Id, population, now, policy))
            {
                if (m_CampRefusals.Get(row.Ledger.Id) != "FOUNDING_RESERVE_EXHAUSTED")
                {
                    m_CampRefusals.Set(row.Ledger.Id, "FOUNDING_RESERVE_EXHAUSTED");
                    HCLogCamp(row, "refused", "FOUNDING_RESERVE_EXHAUSTED");
                }
                return false;
            }
            changed = true;
        }
        if (row.Ledger.Occupants == 0 && Occupied() >= HCAILimits.Get().MaxOccupiedPlaces) { return false; }
        bool upkeep = HCAICampLifecycle.HCUpkeep(row.Camp, now, policy);
        if (upkeep) { changed = true; }
        else if (HCAICampLifecycle.HCGrow(row.Camp, now, policy)) { changed = true; }
        if (!changed) { return false; }
        if (row.Camp.Level < 0)
        {
            row.Ledger.State = "ABANDONED";
            row.Ledger.Occupants = 0;
            row.Ledger.Routine = "SUPPLY_EXHAUSTED";
            row.Camp.ReoccupyAfter = now + policy.RaidLockoutSeconds;
            row.Ledger.ReoccupyAfter = row.Camp.ReoccupyAfter;
            HCAICampLifecycle.HCRefund(row.Camp, m_State.Resources, policy);
        }
        else
        {
            if (priorState != "ALERT" || clearAlert) { row.Ledger.State = "OCCUPIED"; }
            row.Ledger.Occupants = row.Camp.Population;
            row.Ledger.Routine = "FUNDED_CAMP";
        }
        if (row.Ledger.State != priorState) { row.Ledger.Since = now; }
        row.Published = false;
        m_Dirty = true;
        // One verified image owns debit/refund, stage and population. Uncertain
        // IO closes the feature; materializer never receives the changed image.
        if (!SaveChanged()) { m_Ready = false; return false; }
        HCLogCamp(row, "ready", "EAT_FIRE_REPAIR_UNPROVEN");
        return true;
    }

    void HCRaidCamp(int index)
    {
        Raid(index);
        // A later real death during lockout still commits its population debit.
        SaveChanged();
    }

    // Called only by the optional provider's real EEKilled bridge. Remove a
    // pre-bound handle first so the PlayerBase super callback cannot debit it
    // twice. Even an actor killed before its first routine step is accounted.
    void HCPartyKilled(HCAIPartyIdentity identity, EntityAI body)
    {
        HCWorldModule world = HCWorldModule.Get();
        if (!m_Ready || !world || !body || !GetGame().IsServer() || !HCAIPartyIdentity.HCValid(identity)) { return; }
        if (identity.HCGeneration() != world.Epoch()) { return; }
        for (int killedHome = 0; killedHome < Count(); killedHome++)
        {
            HCHoldoutRow row = m_State.Rows[killedHome];
            if (identity.HCPartyId() != row.Camp.Party || identity.HCCampId() != "camp:" + row.Ledger.Id) { continue; }
            if (identity.HCHomeId() != row.Ledger.PlaceId || identity.HCRouteId() != "stationary:" + row.Ledger.Id || identity.HCCargoId() != "cargo:" + row.Ledger.Id) { return; }
            ReleaseOccupant(body);
            if (!HCAICampLifecycle.HCDeath(row.Camp)) { return; }
            m_Dirty = true;
            HCRaidCamp(killedHome);
            return;
        }
    }

    bool HCOwnsOccupant(string id, EntityAI body)
    {
        foreach (HCHoldoutBody binding : m_Bodies)
        {
            if (binding.HoldoutId == id && binding.Body == body) { return true; }
        }
        return false;
    }

    HCAICampPolicy HCRoutinePolicy() { return m_State.CampPolicy; }

    // Lead integration: gate HCWorldModule.MaterializerRow with this after its
    // existing holdout validation. A stale world copy/legacy profile is never
    // proof of a funded camp; this getter performs no save, load or allocation.
    static bool HCAllowsMaterializer(HCWorldHoldout proposal)
    {
        HCHoldouts owner = HCHoldouts.Get();
        if (!owner || !proposal) { return false; }
        for (int admissionIndex = 0; admissionIndex < owner.Count(); admissionIndex++)
        {
            HCHoldoutRow row = owner.m_State.Rows[admissionIndex];
            if (row.Ledger.Id != proposal.Id) { continue; }
            if (!row.Published || !row.Camp.Allocated || row.Camp.Level < 0 || row.Camp.Population < 1) { return false; }
            if (row.Ledger.State != "OCCUPIED" && row.Ledger.State != "ALERT") { return false; }
            if (proposal.Occupants != row.Camp.Population || proposal.HousePos != row.Ledger.HousePos || proposal.CacheRef != row.Cache.EntityRef) { return false; }
            return owner.Cache(admissionIndex) != null;
        }
        return false;
    }

    protected string HCHomeKey(HCWorldHoldout ledger)
    {
        string key = ledger.Id + "|" + ledger.PlaceId + "|" + ledger.FactionId + "|" + ledger.HouseClass + "|" + ledger.CacheRef;
        key += "|" + ledger.State + "|" + ledger.Routine + "|" + ledger.Occupants.ToString() + "|" + ledger.Since.ToString();
        key += "|" + ledger.ReoccupyAfter.ToString() + "|" + ledger.HousePos.ToString();
        return key;
    }

    // Row-change keyed cache over Snapshot(). A failed snapshot is not cached.
    protected HCWorldHoldout HCCachedHome(int index)
    {
        string key = HCHomeKey(m_State.Rows[index].Ledger);
        while (m_ViewHomes.Count() <= index)
        {
            m_ViewHomes.Insert(null);
            m_ViewKeys.Insert("");
        }
        if (m_ViewHomes[index] && m_ViewKeys[index] == key) { return m_ViewHomes[index]; }
        HCWorldHoldout built = Snapshot(index);
        m_ViewHomes.Set(index, built);
        if (built) { m_ViewKeys.Set(index, key); }
        else { m_ViewKeys.Set(index, ""); }
        return built;
    }

    // Detached view bound to HC-10's current immutable materializer identity.
    // Does not allocate a second party, move a house or create a provider lease.
    HCAICampRoutineView HCRoutineView(HCAIPartyIdentity identity)
    {
        HCWorldModule world = HCWorldModule.Get();
        if (!m_Ready || !world || !HCAIPartyIdentity.HCValid(identity) || identity.HCGeneration() != world.Epoch()) { return null; }
        for (int viewIndex = 0; viewIndex < Count(); viewIndex++)
        {
            HCHoldoutRow row = m_State.Rows[viewIndex];
            if (!row.Camp.Allocated || row.Camp.Level < 0 || row.Camp.Population < 1) { continue; }
            if (row.Ledger.State != "OCCUPIED" && row.Ledger.State != "ALERT") { continue; }
            if (identity.HCPartyId() != row.Camp.Party || identity.HCCampId() != "camp:" + row.Ledger.Id) { continue; }
            if (identity.HCHomeId() != row.Ledger.PlaceId || identity.HCRouteId() != "stationary:" + row.Ledger.Id || identity.HCCargoId() != "cargo:" + row.Ledger.Id) { return null; }
            HCAICampRoutineView view = new HCAICampRoutineView;
            // Shared detached copy: callers read it and never write through it.
            view.Home = HCCachedHome(viewIndex);
            if (!view.Home) { return null; }
            view.Level = row.Camp.Level;
            view.Supply = row.Camp.Supply;
            view.Population = row.Camp.Population;
            return view;
        }
        return null;
    }

    // Existing admin and tick entry points share the same funding barrier.
    bool HCAdvanceOccupancy(int index, int now)
    {
        return HCStepCamp(index, now);
    }

    // W69 narrow port: only this holdout's materialized living occupant may
    // spend its actual crate fuel. Visibility/fuel/ignition checks live in the owner.
    void HCHearthLight(int index)
    {
        if (!m_Ready || index < 0 || index >= Count() || LootRemoved(index)) { return; }
        HCHoldoutRow hearthRow = m_State.Rows[index];
        if (hearthRow.Ledger.State != "OCCUPIED" && hearthRow.Ledger.State != "ALERT") { return; }
        array<ref HCHoldoutBody> hearthBodies = m_Bodies;
        foreach (HCHoldoutBody hearthBody : hearthBodies)
        {
            if (hearthBody.HoldoutId != hearthRow.Ledger.Id || !hearthBody.Body || !hearthBody.Body.IsAlive()) { continue; }
            HCHearthFires.HCLight(Structure(index), hearthBody.Body, Cache(index), "holdout", hearthRow.Ledger.Id);
            SnapshotContents(index);
            SaveChanged();
            return;
        }
    }

    void HCSyncLights()
    {
        array<vector> positions = new array<vector>;
        if (m_Ready && m_State)
        {
            foreach (HCHoldoutRow litRow : m_State.Rows)
            {
                if (positions.Count() >= HCAILimits.Get().MaxHoldouts) { break; }
                bool inhabited = litRow.Ledger.State == "OCCUPIED" || litRow.Ledger.State == "ALERT";
                if (inhabited) { positions.Insert(litRow.Ledger.HousePos); }
            }
        }
        HCSignsHoldoutRPC.Publish(positions);
    }

    // Catalog comes from authored template-pack world rows, never a world scan.
    // One authored row per tick; first 24 distinct covered houses are retained.
    protected int m_CatalogCursor;
    void FillCatalog()
    {
        m_CatalogWorked = false;
        HCWorldModule world = HCWorldModule.Get();
        array<ref HCInteriorFurnishRow> authored = HCInteriorTemplates.FurnishRows();
        if (!world || !authored || m_State.Rows.Count() >= HCAILimits.Get().MaxHoldouts) return;
        bool changed = false;
        m_WorkBudget.HCReset(1);
        for (int catalogWork = 0; catalogWork < 1; catalogWork++)
        {
            if (m_CatalogCursor >= authored.Count() || m_State.Rows.Count() >= HCAILimits.Get().MaxHoldouts) { break; }
            if (!m_WorkBudget.HCContinue()) { break; }
            m_CatalogWorked = true;
            HCInteriorFurnishRow site = authored[m_CatalogCursor];
            m_CatalogCursor++;
            HCInteriorTemplateClassRow classRow = HCInteriorTemplates.ClassRow(site.BuildingClass);
            HCInteriorTemplate layout = HCInteriorTemplates.Template(site.BuildingClass);
            if (!classRow || classRow.Search != "covered" || !layout || layout.Rooms.Count() < 1) continue;
            vector position = HCInteriorTemplates.AsVector(site.Position);
            string id = "hc-house-" + site.SlotId.ToString();
            bool known = false;
            foreach (HCHoldoutRow existing : m_State.Rows) { if (existing.Ledger.Id == id || existing.Ledger.HousePos == position) known = true; }
            if (known) continue;
            HCHoldoutRow row = new HCHoldoutRow;
            row.Ledger.Id = id;
            row.Ledger.HouseClass = site.BuildingClass;
            row.Ledger.HousePos = position;
            row.Ledger.PlaceId = world.NearestPlace(position);
            if (row.Ledger.PlaceId == "") { continue; }
            row.Ledger.PlaceId.ToLower();
            row.Ledger.FactionId = "locals";
            row.Ledger.Since = HCWorldClock.UTC();
            row.Camp.Home = id;
            row.StockDay = HCEscalationClock.Day();
            row.Cache.Position = position;
            row.Cache.Orientation = Vector(site.Yaw, 0, 0);
            m_State.Rows.Insert(row);
            m_Caches.Insert(new HCEncounterCacheIO);
            changed = true;
        }
        if (changed)
        {
            m_State.TemplatePin = HCInteriorTemplates.SourcePin();
            m_Dirty = true;
            m_CatalogDirty = true;
            m_SaveJob.HCDirty = true;
            // Operator-off shared dispatch keeps this owner's durable path.
            if (!HCPerfConfig.HCGet().EnableSharedSaves) { HCFlushCatalog(); }
        }
    }

    // Authored snapshot for a later materializer/lead owner, never a mutable
    // reference into this module's persistent state.
    HCWorldHoldout Snapshot(int index)
    {
        if (!m_Ready || index < 0 || index >= Count()) return null;
        HCWorldHoldout copy;
        string encoded;
        string error;
        if (!JsonFileLoader<HCWorldHoldout>.MakeData(m_State.Rows[index].Ledger, encoded, error)) return null;
        if (!JsonFileLoader<HCWorldHoldout>.LoadData(encoded, copy, error)) return null;
        return copy;
    }

    string PlaceId(int index)
    {
        if (index < 0 || index >= Count()) return "";
        return m_State.Rows[index].Ledger.PlaceId;
    }

    Object Structure(int index)
    {
        if (index < 0 || index >= Count()) return null;
        HCInteriorFurnishRow pose = new HCInteriorFurnishRow;
        pose.BuildingClass = m_State.Rows[index].Ledger.HouseClass;
        vector position = m_State.Rows[index].Ledger.HousePos;
        pose.Position.Insert(position[0]); pose.Position.Insert(position[1]); pose.Position.Insert(position[2]);
        return HCInteriorTemplatePlacement.Resolve(pose);
    }

    string CacheId(int index)
    {
        if (index < 0 || index >= Count()) return "";
        return m_State.Rows[index].Ledger.Id;
    }

    EntityAI Cache(int index)
    {
        if (index < 0 || index >= Count() || m_State.Rows[index].Cache.Phase != 2) return null;
        EntityAI handle = m_Caches[index].Handle;
        if (!handle || handle.IsRuined() || handle.GetHierarchyParent() || handle.GetHierarchyRootPlayer()) return null;
        return handle;
    }

    int Occupied()
    {
        int occupied = 0;
        foreach (HCHoldoutRow row : m_State.Rows) { if (row.Ledger.State == "OCCUPIED" || row.Ledger.State == "ALERT") occupied++; }
        return occupied;
    }

    // Small crate footprint in an authored room corner, outside every keepout
    // including 0.6 m around doors. Refuse when room geometry cannot contain it.
    bool CacheSpot(Object structure, HCHoldoutRow row)
    {
        HCInteriorTemplate layout = HCInteriorTemplates.Template(row.Ledger.HouseClass);
        if (!layout) return false;
        int examined = 0;
        foreach (HCInteriorTemplateRoom room : layout.Rooms)
        {
            examined++;
            if (examined > 16) break;
            vector spot = Vector(room.Min[0] + 0.55, room.FloorY + 0.03, room.Min[2] + 0.45);
            array<float> minimum = {spot[0] - 0.45, spot[1], spot[2] - 0.35};
            array<float> maximum = {spot[0] + 0.45, spot[1] + 0.5, spot[2] + 0.35};
            if (!HCInteriorTemplates.Inside(minimum, room.Min, room.Max) || !HCInteriorTemplates.Inside(maximum, room.Min, room.Max)) continue;
            bool clear = true;
            foreach (HCInteriorTemplateKeepOut keepout : layout.KeepOuts)
            {
                if (HCInteriorTemplates.Intersects(minimum, maximum, keepout.Min, keepout.Max, 0.6)) clear = false;
            }
            if (!clear) continue;
            row.Cache.Position = structure.ModelToWorld(spot);
            row.Cache.Orientation = structure.GetOrientation();
            HCEncounterCacheIO probe = new HCEncounterCacheIO;
            if (probe.Clear(row.Cache, structure)) return true;
        }
        return false;
    }

    // Materializer integration: bind only its admitted ordinary, killable body.
    // No immunity, equipment changes, loot controller or body creation here.
    bool BindOccupant(string id, EntityAI body)
    {
        if (!m_Ready || !body || !body.IsMan() || !body.IsAlive() || m_Bodies.Count() >= HCAILimits.Get().MaxLiveAI) return false;
        PlayerBase human = PlayerBase.Cast(body);
        if (human && human.GetIdentity()) return false;
        int boundCount = 0;
        foreach (HCHoldoutBody bound : m_Bodies)
        {
            if (bound.Body == body) return false;
            if (bound.HoldoutId == id && bound.Body && bound.Body.IsAlive()) boundCount++;
        }
        foreach (HCHoldoutRow row : m_State.Rows)
        {
            if (row.Ledger.Id != id || (row.Ledger.State != "OCCUPIED" && row.Ledger.State != "ALERT")) continue;
            if (boundCount >= row.Ledger.Occupants || vector.DistanceSq(body.GetPosition(), row.Ledger.HousePos) > 900) return false;
            HCHoldoutBody binding = new HCHoldoutBody;
            binding.HoldoutId = id;
            binding.Body = body;
            m_Bodies.Insert(binding);
            return true;
        }
        return false;
    }

    // Provider must release a living lease BEFORE deleting it. Null handles are
    // not proof of death and are never counted as kills.
    void ReleaseOccupant(EntityAI body)
    {
        for (int releaseIndex = m_Bodies.Count() - 1; releaseIndex >= 0; releaseIndex--)
        {
            if (m_Bodies[releaseIndex].Body == body) m_Bodies.Remove(releaseIndex);
        }
    }

    bool LootRemoved(int index)
    {
        EntityAI cache = Cache(index);
        if (!cache || !cache.GetInventory() || !cache.GetInventory().GetCargo()) return false;
        CargoBase cargo = cache.GetInventory().GetCargo();
        if (cargo.GetItemCount() > 32) return false;
        // Native EnScript.c:877/902/917: hash membership for cargo ids.
        map<string, bool> present = new map<string, bool>;
        for (int itemIndex = 0; itemIndex < cargo.GetItemCount(); itemIndex++)
            present.Set(HCSearchSupplyRegistry.PersistentId(cargo.GetItem(itemIndex)), true);
        foreach (string prior : m_State.Rows[index].Contents) { if (!present.Contains(prior)) return true; }
        return false;
    }

    void SnapshotContents(int index)
    {
        EntityAI cache = Cache(index);
        if (!cache || !cache.GetInventory() || !cache.GetInventory().GetCargo()) return;
        CargoBase cargo = cache.GetInventory().GetCargo();
        if (cargo.GetItemCount() > 32) return;
        array<string> contents = new array<string>;
        for (int itemIndex = 0; itemIndex < cargo.GetItemCount(); itemIndex++)
        {
            string id = HCSearchSupplyRegistry.PersistentId(cargo.GetItem(itemIndex));
            if (id != "") contents.Insert(id);
        }
        bool changed = contents.Count() != m_State.Rows[index].Contents.Count();
        if (!changed)
        {
            for (int compareIndex = 0; compareIndex < contents.Count(); compareIndex++)
                if (contents[compareIndex] != m_State.Rows[index].Contents[compareIndex]) changed = true;
        }
        if (!changed) return;
        m_State.Rows[index].Contents = contents;
        m_Dirty = true;
    }

    // Called by the encounter/stance owner only for a local observed threat.
    bool Alert(string id)
    {
        if (!m_Ready) return false;
        foreach (HCHoldoutRow row : m_State.Rows)
        {
            if (row.Ledger.Id != id || row.Ledger.State != "OCCUPIED") continue;
            row.Ledger.State = "ALERT";
            row.Ledger.Since = HCWorldClock.UTC();
            m_Dirty = true;
            if (!SaveChanged()) return false;
            PublishState(row);
            return SaveChanged();
        }
        return false;
    }

    void Raid(int index)
    {
        HCHoldoutRow row = m_State.Rows[index];
        if (row.Ledger.State == "RAIDED") { return; }
        row.Ledger.State = "RAIDED";
        row.Ledger.Occupants = 0;
        row.Ledger.Since = HCWorldClock.UTC();
        HCAICampLifecycle.HCRaid(row.Camp, row.Ledger.Since, m_State.CampPolicy);
        HCAICampLifecycle.HCRefund(row.Camp, m_State.Resources, m_State.CampPolicy);
        row.Ledger.ReoccupyAfter = row.Camp.ReoccupyAfter;
        row.Ledger.Routine = "LOCKOUT";
        row.Contents.Clear();
        m_Dirty = true;
        if (!SaveChanged()) { return; }
        PublishState(row);
        if (!SaveChanged()) { return; }
        int raidLockout = m_State.CampPolicy.RaidLockoutSeconds;
        Print("[HollowCountry] V2 holdout raided id=" + row.Ledger.Id + " lockout=" + raidLockout.ToString() + "s runtime=PENDING");
    }

    // A release with a new interior template pack must not stop holdouts for
    // good (boot 095 after the #227 door census). Rows keep their house and
    // their placed cache; the layout is read again only to choose a new cache
    // spot, and CacheSpot already refuses a house without a covered layout. So
    // re-pin the ledger to the new pack, report houses it no longer covers, and
    // save once. Bounded by MaxHoldouts rows; runs once per pack change.
    protected void MigrateTemplatePin()
    {
        int uncovered = 0;
        foreach (HCHoldoutRow pinned : m_State.Rows)
        {
            HCInteriorTemplateClassRow coverage = HCInteriorTemplates.ClassRow(pinned.Ledger.HouseClass);
            HCInteriorTemplate rooms = HCInteriorTemplates.Template(pinned.Ledger.HouseClass);
            if (!coverage || coverage.Search != "covered" || !rooms || rooms.Rooms.Count() < 1) { uncovered++; }
        }
        m_State.TemplatePin = HCInteriorTemplates.SourcePin();
        m_Dirty = true;
        m_CatalogDirty = true;
        m_SaveJob.HCDirty = true;
        if (!HCPerfConfig.HCGet().EnableSharedSaves) { HCFlushCatalog(); }
        Print("[HollowCountry] V2 holdouts template pack changed; ledger re-pinned rows=" + m_State.Rows.Count().ToString() + " uncovered=" + uncovered.ToString());
    }

    override void OnTick(float deltaTime)
    {
        m_TickMeasuredStage = 0;
        if (!m_Ready || !HCWorldModule.Get()) return;
        m_Elapsed += deltaTime;
        if (!HCInteriorTemplates.Loaded())
        {
            if (!m_WaitReported) Print("[HollowCountry] V2 holdouts waiting for authored covered template houses");
            m_WaitReported = true;
            return;
        }
        if (m_State.TemplatePin != "" && m_State.TemplatePin != HCInteriorTemplates.SourcePin()) { MigrateTemplatePin(); return; }
        FillCatalog();
        if (m_CatalogDirty) { m_WorkBudget.HCDeferred(GetName(), 1); return; }
        // Discovery and simulation never receive independent slices in one tick.
        if (m_CatalogWorked) { return; }
        if (!m_Ready || Count() == 0) { return; }
        if (m_TickPhase == 0)
        {
            if (m_Elapsed < 10) { return; }
            m_Elapsed = 0;
            if (m_Next >= Count()) m_Next = 0;
            m_TickIndex = m_Next;
            m_Next++;
            m_TickPhase = 1;
        }
        m_CampUnits.HCReset(1);
        m_WorkBudget.HCReset(1);
        if (!m_CampUnits.HCTake(1) || !m_WorkBudget.HCContinue()) { return; }
        m_TickMeasuredStage = m_TickPhase;
        int index = m_TickIndex;
        HCHoldoutRow row = m_State.Rows[index];
        HCReached.Mark("holdouts.row");
        int now = HCWorldClock.UTC();
        if (now < row.Ledger.Since || now < 1) { m_Ready = false; m_Operational.HCPublish("refused", "HC16_clock_rollback"); HCSyncLights(); return; }
        // Repair a cross-store interrupted publish even when a house/cache
        // cannot currently resolve. Local durable state is authoritative.
        if (m_TickPhase == 1)
        {
            if (!row.Published)
            {
                PublishState(row);
                if (!SaveChanged()) { return; }
            }
            m_TickPhase = 2;
            return;
        }
        if (m_TickPhase == 2)
        {
            m_TickStructure = Structure(index);
            if (!m_TickStructure) { m_TickPhase = 0; return; }
            m_TickPhase = 3;
            return;
        }
        Object structure = m_TickStructure;
        if (!structure) { m_TickPhase = 0; return; }
        if (m_TickPhase == 3)
        {
            if (row.Cache.Phase == 0 && HCObserverTransitionGate.CanTransition(row.Ledger.HousePos, 500) && CacheSpot(structure, row) && HCObserverTransitionGate.CanTransition(row.Cache.Position, 500))
            {
                row.Cache.Phase = 1;
                m_Dirty = true;
                if (!SaveChanged()) { return; }
                m_Caches[index].Create(row.Cache);
                m_Dirty = true;
            }
            // Cache creation keeps its original intent/result save barriers.
            if (!SaveChanged()) { return; }
            m_TickPhase = 4;
            return;
        }
        if (m_TickPhase == 4)
        {
            int cachePhase = row.Cache.Phase;
            string cacheRef = row.Cache.EntityRef;
            if (row.Cache.Phase != 0) m_Caches[index].LinkCache(row.Cache);
            if (cachePhase != row.Cache.Phase || cacheRef != row.Cache.EntityRef) m_Dirty = true;
            if ((row.Ledger.State == "OCCUPIED" || row.Ledger.State == "ALERT") && LootRemoved(index)) HCRaidCamp(index);
            if (row.Cache.Phase == 3 && (row.Ledger.State == "OCCUPIED" || row.Ledger.State == "ALERT")) HCRaidCamp(index);
            if (!m_Ready) return;
            if (!SaveChanged()) { return; }
            m_TickPhase = 5;
            return;
        }
        if (m_TickPhase == 5)
        {
            string previousState = row.Ledger.State;
            HCStepCamp(index, now);
            if (!m_Ready) { return; }
            if (row.Ledger.State != previousState)
            {
                m_Dirty = true;
                if (!SaveChanged()) { return; }
                PublishState(row);
            }
            m_BodyNext = m_Bodies.Count() - 1;
            m_TickPhase = 6;
            return;
        }
        if (m_TickPhase == 6)
        {
            // Native callbacks may shrink the binding list between continuations.
            if (m_BodyNext >= m_Bodies.Count()) { m_BodyNext = m_Bodies.Count() - 1; }
            if (m_BodyNext >= 0)
            {
                int bodyIndex = m_BodyNext;
                m_BodyNext = m_BodyNext - 1;
                HCHoldoutBody binding = m_Bodies[bodyIndex];
                if (binding.HoldoutId != row.Ledger.Id) { return; }
                if (!binding.Body) { m_Bodies.Remove(bodyIndex); return; }
                if (binding.Body.IsAlive()) { return; }
                m_Bodies.Remove(bodyIndex);
                HCAICampLifecycle.HCDeath(row.Camp);
                m_Dirty = true;
                HCRaidCamp(index);
                SaveChanged();
                return;
            }
            m_TickPhase = 7;
            return;
        }
        if (m_TickPhase == 7)
        {
            if (row.Ledger.State == "OCCUPIED" || row.Ledger.State == "ALERT")
            {
                HCSearchHouses houses = HCSearchBinding.Houses();
                // Three lifetime attempts, one per real day. No replenishment on raid.
                // HC-34: the remote house hop is refused; do not burn attempts or save for it.
                if (houses && houses.V2VisitAvailable() && Cache(index) && row.StockAttempts < 3 && HCEscalationClock.Day() >= row.StockDay && HCObserverTransitionGate.CanTransition(row.Cache.Position, 500))
                {
                    int siteNumber = row.StockAttempts;
                    row.StockAttempts++;
                    row.StockDay = HCEscalationClock.Day() + 1;
                    m_Dirty = true;
                    if (!SaveChanged()) { return; }
                    int phase = houses.V2Visit(structure, Cache(index), row.Ledger.Id, siteNumber);
                    if (phase == 3) { row.StockAttempts = 3; m_Dirty = true; }
                    if (m_Reports < 12)
                    {
                        m_Reports++;
                        Print("[HollowCountry] V2 holdout stock id=" + row.Ledger.Id + " phase=" + phase.ToString());
                    }
                }
            }
            if (!SaveChanged()) { return; }
            m_TickPhase = 8;
            return;
        }
        if (m_TickPhase == 8)
        {
            if (row.Ledger.State == "OCCUPIED" || row.Ledger.State == "ALERT") SnapshotContents(index);
            if (!SaveChanged()) { return; }
            m_TickPhase = 9;
            return;
        }
        if (row.Ledger.CacheRef != row.Cache.EntityRef)
        {
            row.Ledger.CacheRef = row.Cache.EntityRef;
            row.Published = false;
            m_Dirty = true;
        }
        HCWorldModule world = HCWorldModule.Get();
        if (world && !row.Published)
        {
            PublishState(row);
            if (row.Published) m_Dirty = true;
        }
        SaveChanged();
        m_TickPhase = 0;
        m_TickStructure = null;
    }


    override void OnStop()
    {
        m_TickPhase = 0;
        m_TickStructure = null;
        // Flush changes marked by native callbacks since the last tick; a faulted store stays unwritten.
        if (m_Ready && m_State) { SaveChanged(); }
        HCSaveScheduler.HCUnregister(m_SaveJob);
        HCDebugSnapshot.HCUnregister(m_CampDebug);
        m_CampDebug = null;
        m_Ready = false;
        m_Operational.HCPublish("off", "stopped");
        Print("[HC Plan] HC-16 camp=none level=-1 supply=0 roles=0 state=off runtime=PENDING");
        HCSyncLights();
        m_Bodies.Clear();
        m_CampRefusals.Clear();
        m_ViewHomes.Clear();
        m_ViewKeys.Clear();
        if (s_Instance == this) s_Instance = null;
    }
}

// Native EnSystem.c:106 TickCount; EnDebug.c:96 Print; EnMath.c:553 Min. Measure every
// continuation, including catalog and no-op ticks, with the shared step timer.
modded class HCHoldouts
{
    protected ref HCStepTimer m_TickSteps = new HCStepTimer("Holdouts");
    override void OnStart(HCSettings settings)
    {
        super.OnStart(settings);
        m_TickSteps = new HCStepTimer("Holdouts");
        m_TickSteps.HCDefine("catalog");
        m_TickSteps.HCDefine("publish");
        m_TickSteps.HCDefine("resolve");
        m_TickSteps.HCDefine("cache_create");
        m_TickSteps.HCDefine("cache_link");
        m_TickSteps.HCDefine("camp");
        m_TickSteps.HCDefine("bodies");
        m_TickSteps.HCDefine("stock_commit");
        Print("[HC PerfControl] Holdouts resumable row stages admitted; runtime=PENDING");
    }
    override void OnTick(float deltaTime)
    {
        int tickStart = TickCount(0);
        int continuation = Math.Min(m_TickPhase, HCStepTimer.MAX_STEPS - 1);
        int catalogBefore = m_CatalogCursor;
        super.OnTick(deltaTime);
        int elapsedTicks = TickCount(tickStart);
        m_TickSteps.HCAdd(Math.Min(m_TickMeasuredStage, HCStepTimer.MAX_STEPS - 1), elapsedTicks);
        if (continuation > 0 || m_TickPhase > 0 || catalogBefore != m_CatalogCursor)
        {
            m_TickSteps.HCItem("holdout_stage", elapsedTicks);
        }
        m_TickSteps.HCEndTick(elapsedTicks);
    }
}

// Native server callbacks supplement the restart snapshots. Foreign crates and
// unbound players/AI pass straight through; ordinary inventory and corpse loot
// remain engine-owned. No custom action, immunity or player RPC is involved.
modded class WoodenCrate
{
    override void EECargoOut(EntityAI item)
    {
        super.EECargoOut(item);
        HCDeadDrops.CargoRemoved(this, item);
        HCHoldouts.CargoRemoved(this);
    }
}

modded class PlayerBase
{
    override void EEKilled(Object killer)
    {
        HCHoldouts.OccupantKilled(this);
        super.EEKilled(killer);
    }
}

class HCHoldoutSaveJob : HCSaveJob
{
    override string HCName() { return "Holdouts"; }
    HCHoldouts Owner;
    override int HCStep()
    {
        if (!Owner) { return STEP_FAILED; }
        return Owner.HCStepCatalog();
    }
}

modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        Register(new HCHoldouts);
    }
}
