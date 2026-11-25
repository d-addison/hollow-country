// W5-PERF-5: catalog <=1 authored row/tick (4 ms cooperative guard);
// One row starts per >=1s; native stages/body probes resume on following ticks.
// Empty body/stock/content stages fall through; heavy cache work yields between operations.
// Catalog checkpoints coalesce; cache barriers resume across ticks, while
// spend/raid barriers also resume only after a staged verified save. Native scripts-1.30.164289:
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
    protected ref HCStagedSaveImage m_Writer = new HCStagedSaveImage;
    protected string m_SaveText;
    protected string m_CommittedText;
    protected bool m_Prepared;
    protected ref HCStepTimer m_SaveTimer;
    protected string m_Path;
    protected bool m_Fault;
    // Raw image of the last successful file load; owners may check key presence
    // (native load zero-fills absent ints). Taken once, then cleared.
    protected string m_LoadedText;

    void HCEncounterStore(string name)
    {
        m_Path = "$profile:HollowCountry/" + name + ".json";
        if (name == "holdouts") { m_SaveTimer = new HCStepTimer("HoldoutsSave"); }
    }
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
            string encoded;
            if (!HCGroupIO.HCReadRaw(m_Path, 262144, encoded)) { Fault(); return null; }
            if (encoded.Length() > 262144 || encoded.IndexOf("\"Version\"") < 0 || encoded.IndexOf("\"" + collection + "\"") < 0) { Fault(); return null; }
            if (!HCV2ThreatStore<T>.Load(m_Path, 262144, result)) { Fault(); return null; }
            m_LoadedText = encoded;
            m_CommittedText = encoded;
            return result;
        }
        if (!Save(fresh)) return null;
        return fresh;
    }

    bool Save(T data)
    {
        if (m_Fault || !data) { return false; }
        // Finish the frozen snapshot before encoding any newer callback state.
        if (SaveInFlight())
        {
            if (!HCFinish(data)) { return false; }
        }
        return HCFinish(data);
    }

    protected bool HCFinish(T data)
    {
        int result = HCSaveJob.STEP_MORE;
        int steps = 0;
        while (result == HCSaveJob.STEP_MORE && steps < HCStagedSaveImage.HC_MAX_STAGES + 2)
        {
            result = SaveStep(data);
            steps++;
        }
        if (result == HCSaveJob.STEP_MORE)
        {
            Print("[HC Persistence] owner=HCEncounterStore guard=save_stage_guard steps=" + steps.ToString());
        }
        if (result != HCSaveJob.STEP_DONE) { return Fault(); }
        return true;
    }

    bool SaveInFlight() { return m_Prepared || m_Writer.Active(); }

    // Encoding and Begin admission have separate budgets. Once admitted, the
    // shared writer owns bounded chunks, verified backup and primary promotion.
    int SaveStep(T data)
    {
        if (m_Fault || !data) { return HCSaveJob.STEP_FAILED; }
        if (!SaveInFlight())
        {
            HCSaveJob.HCOperation = "encode";
            string error;
            int encodeStarted = TickCount(0);
            bool encoded = JsonFileLoader<T>.MakeData(data, m_SaveText, error);
            int encodeTicks = TickCount(encodeStarted);
            if (m_SaveTimer)
            {
                m_SaveTimer.HCItem("holdouts_encode", encodeTicks);
                m_SaveTimer.HCEndTick(encodeTicks);
            }
            if (!encoded) { Fault(); return HCSaveJob.STEP_FAILED; }
            if (m_SaveText.Length() < 1 || m_SaveText.Length() > 262144) { Fault(); return HCSaveJob.STEP_FAILED; }
            m_Prepared = true;
            return HCSaveJob.STEP_MORE;
        }
        if (m_Prepared)
        {
            HCSaveJob.HCOperation = "admit";
            if (!m_Writer.Begin(m_Path, m_SaveText, 262144, true, true, m_CommittedText)) { Fault(); return HCSaveJob.STEP_FAILED; }
            m_Prepared = false;
            return HCSaveJob.STEP_MORE;
        }
        int result = m_Writer.HCStepBoundedImage();
        if (result == HCSaveJob.STEP_DONE) { m_CommittedText = m_SaveText; m_SaveText = ""; }
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

// One real, ordinary vanilla crate per saved intent. Holdouts may retire a lost
// link and journal a new empty crate after lockout; inventory is never rebuilt.
// Runtime handle is separate from the DTO; shared IO never retries an intent.
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
        HCGroundSnap.Snap(Handle);
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
    protected ref map<string, bool> m_FixtureRows = new map<string, bool>;
    protected int m_Next;
    protected int m_TickPhase;
    protected int m_TickMeasuredStage;
    protected ref HCStepTimer m_TickSteps = new HCStepTimer("Holdouts");
    protected bool m_MeasuringTick;
    protected ref HCWorkBudget m_SpotWork = new HCWorkBudget;
    protected bool m_CampReserveSaved;
    protected bool m_CampFoundedPending;
    protected bool m_CampCommitPending;
    protected int m_TickAfterRaid;
    protected int m_TickAfterSave = 4;
    protected int m_TickStockSite;
    protected int m_TickIndex;
    protected int m_BodyNext;
    protected Object m_TickStructure;
    // Staged structure lookup (phase 2): one resolve-cursor step per admitted tick, kept across ticks.
    protected ref HCInteriorResolveCursor m_TickResolve;
    // Last resolved structure per holdout, for the hearth path (weak: a deleted object reads null).
    protected ref map<int, Object> m_StructureSeen = new map<int, Object>;
    protected bool m_CatalogWorked;
    protected float m_Elapsed;
    protected bool m_Ready;
    protected bool m_Dirty;
    protected int m_Reports;
    protected float m_SummaryElapsed;
    protected int m_RowsSteppedWindow;
    protected int m_RowsCompletedWindow;
    protected int m_FoundedWindow;
    protected int m_RecoveryAttemptsWindow;
    protected int m_StructureBlockedWindow;
    protected int m_SpotNoTemplateWindow;
    protected int m_SpotNoFitWindow;
    protected int m_SpotCollidingWindow;
    protected int m_SpotBudgetWindow;
    // Runtime-only search: <=16 rooms x (9 original + 9 rotated points).
    protected int m_SpotCandidate;
    protected bool m_SpotHadFit;
    protected int m_ObserverBlockedWindow;
    protected bool m_WaitReported;
    protected bool m_CatalogDirty;
    protected bool m_Reconciled;
    protected string m_ReconcileWait;
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
    override void RegisterUses()
    {
        super.RegisterUses();
        HCModuleReadiness.HCRegisterUse("Holdouts", "holdout_reconcile");
    }
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
        m_Reconciled = false;
        m_ReconcileWait = "";
        m_CatalogCursor = 0;
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
        // False in a cooperative tick means pending, never a store failure.
        // The caller must yield to phase 12 before any dependent side effect.
        if (m_MeasuringTick) { return false; }
        // Admin occupancy commands and native spend/raid callbacks require a
        // committed image before publishing/replying. Tick work yields above;
        // retain this synchronous durability barrier until callers can resume.
        bool saved = m_Store.Save(m_State);
        if (!saved) { m_Ready = false; m_Operational.HCPublish("refused", "HC16_store_uncertain"); HCSyncLights(); return false; }
        m_Dirty = false;
        m_CatalogDirty = false;
        if (m_SaveJob)
        {
            m_SaveJob.HCDirty = false;
            m_SaveJob.HCInFlight = false;
            m_SaveJob.HCUrgent = false;
            m_SaveJob.HCDue = GetGame().GetTickTime() + 60;
        }
        return true;
    }

    // #271/#285: Published is a detached world-view retry flag, reset for ALL
    // rows on every boot. It needs no checkpoint or simulation wait. Actual
    // stock intents, founding and reserve/spend transitions use phase 12.
    // Catalog discovery uses the shared staged save job. Tick-owned cache and
    // result barriers request urgent scheduler continuations; callbacks/shutdown
    // retain synchronous SaveChanged().

    int HCStepCatalog()
    {
        if (!m_Ready) { return HCSaveJob.STEP_FAILED; }
        if (!m_Dirty && !m_Store.SaveInFlight()) { return HCSaveJob.STEP_DONE; }
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
            if (m_CatalogDirty) { Print("[HollowCountry] V2 holdouts catalog houses=" + Count().ToString() + "/" + HCAILimits.Get().MaxHoldouts.ToString()); }
            m_CatalogDirty = false;
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
            row.Published = world.UpsertHoldout(row.Ledger);
            if (row.Published)
            {
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
        bool fixture = m_FixtureRows.Count() > 0 && m_FixtureRows.Contains(row.Ledger.Id);
        if (fixture) { line += " fixture=1"; }
        Print(line + " refusal=" + refusal + " runtime=PENDING");
        if (state == "ready" && refusal == "EAT_FIRE_REPAIR_UNPROVEN")
        {
            if (fixture) { HCModuleReadiness.HCUseFixture("Holdouts", "camp_committed"); }
            else { HCModuleReadiness.HCUse("Holdouts", "camp_committed"); }
            if (fixture) { m_FixtureRows.Remove(row.Ledger.Id); }
        }
    }

    bool HCStepCamp(int index, int now)
    {
        m_CampReserveSaved = false;
        if (!m_Ready || !m_State || index < 0 || index >= Count() || now < 1) { return false; }
        HCHoldoutRow row = m_State.Rows[index];
        if (now < row.Ledger.Since) { return false; }
        HCAICampPolicy policy = m_State.CampPolicy;
        // Scalar reserve update on the existing bounded step, before site/cache
        // gates. An unresolved cache cannot stop the world's logical recovery.
        if (HCAICampLifecycle.HCReserveDue(m_State.Resources, now, policy))
        {
            array<ref HCAICampLife> reserveHomes = HCCampHomes();
            if (HCAICampLifecycle.HCReplenish(m_State.Resources, reserveHomes, now, policy))
            {
                m_Dirty = true;
                // Save the replenished reserve before attempting a founding debit.
                if (m_MeasuringTick) { m_CampReserveSaved = true; return false; }
                if (!SaveChanged()) { return false; }
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
            // Finite stock/recruits are an expected wait, reported together by
            // HCReportWindow rather than one refusal per dormant catalog row.
            if (m_State.Resources.Stock < policy.CampAllocation || m_State.Resources.Population < population - row.Camp.Population) { return false; }
            array<ref HCAICampLife> foundingHomes = HCCampHomes();
            if (!HCAICampLifecycle.HCFound(row.Camp, m_State.Resources, foundingHomes, "holdout:" + row.Ledger.Id, population, now, policy))
            {
                if (m_CampRefusals.Get(row.Ledger.Id) != "FOUNDING_INVARIANT_REFUSED")
                {
                    m_CampRefusals.Set(row.Ledger.Id, "FOUNDING_INVARIANT_REFUSED");
                    HCLogCamp(row, "refused", "FOUNDING_INVARIANT_REFUSED");
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
        m_CampFoundedPending = priorState != "OCCUPIED" && priorState != "ALERT" && row.Ledger.State == "OCCUPIED";
        // Phase 15 logs only this committed transition, not unrelated dirt.
        m_CampCommitPending = true;
        if (!SaveChanged()) { return false; }
        m_CampCommitPending = false;
        if (m_CampFoundedPending) { m_FoundedWindow++; }
        m_CampFoundedPending = false;
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
            if (owner.m_Dirty || owner.m_Store.SaveInFlight()) { return false; }
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
        if (m_Dirty || m_Store.SaveInFlight()) { return null; }
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
    // Queue only an already allocated funded camp with a naturally due step.
    // Existing tick stages retain cache/site/loot/cap and persistence barriers.
    bool HCFixtureDue(vector pos, bool apply, out string reason)
    {
        reason = "holdout-owner-busy-or-unavailable";
        if (!m_Ready || !m_State || m_Dirty || m_Store.SaveInFlight() || m_TickPhase != 0) { return false; }
        int now = HCWorldClock.UTC();
        int selected = -1;
        float best = 0;
        m_WorkBudget.HCReset(Count());
        for (int i = 0; i < Count(); i++)
        {
            if (!m_WorkBudget.HCContinue()) { reason = "holdout-selection-budget"; return false; }
            HCHoldoutRow row = m_State.Rows[i];
            HCAICampLife camp = row.Camp;
            HCAICampPolicy policy = m_State.CampPolicy;
            if (!camp.Allocated || camp.Refunded || camp.Level < 0 || camp.Population < 1 || camp.Supply < 1) { continue; }
            if (row.Ledger.State != "OCCUPIED" && row.Ledger.State != "ALERT") { continue; }
            if (now < 1 || now < row.Ledger.Since || now < camp.LastStage || now < camp.LastUpkeep || now < camp.ReoccupyAfter || now < row.Ledger.ReoccupyAfter) { continue; }
            bool upkeep = now - camp.LastUpkeep >= policy.UpkeepSeconds;
            bool growth = camp.Level < 3 && now - camp.LastStage >= policy.GrowthSeconds && camp.Supply >= HCAICampLifecycle.HCCost(camp.Level + 1, policy);
            bool alert = row.Ledger.State == "ALERT" && now - row.Ledger.Since >= 3600;
            if (!upkeep && !growth && !alert) { continue; }
            if (!SiteAvailable(row) || row.Cache.Phase != 2) { continue; }
            float distance = vector.DistanceSq(pos, row.Ledger.HousePos);
            if (selected < 0 || distance < best) { best = distance; selected = i; }
        }
        reason = "no-due-funded-row";
        if (selected < 0) { return false; }
        if (apply)
        {
            m_FixtureRows.Set(m_State.Rows[selected].Ledger.Id, true);
            m_Next = selected;
        }
        reason = "due-funded-row-queued-normal-occupancy";
        return true;
    }

    bool HCAdvanceOccupancy(int index, int now)
    {
        return HCStepCamp(index, now);
    }

    // W69 narrow port: only this holdout's materialized living occupant may
    // spend its actual crate fuel. Visibility/fuel/ignition checks live in the owner.
    void HCHearthLight(int index)
    {
        if (!m_Ready || m_Dirty || m_Store.SaveInFlight() || index < 0 || index >= Count() || LootRemoved(index)) { return; }
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

    // Synthetic furnishing row for the holdout's house (SlotId -1: never enters the catalog bindings).
    protected HCInteriorFurnishRow HCStructurePose(int index)
    {
        HCInteriorFurnishRow pose = new HCInteriorFurnishRow;
        pose.SlotId = -1;
        pose.BuildingClass = m_State.Rows[index].Ledger.HouseClass;
        vector position = m_State.Rows[index].Ledger.HousePos;
        pose.Position.Insert(position[0]); pose.Position.Insert(position[1]); pose.Position.Insert(position[2]);
        return pose;
    }

    // One admitted resolve-cursor step. The house lookup is a native sphere whose cost is the
    // building's proxy count (soak 176: 15.7 ms in structure_lookup), so it is never made in one
    // call here: the shared cursor takes rays first, refuses known-heavy classes without a sphere
    // and waits for the startup pump. False = still resolving, call again next tick; true =
    // finished, `structure` is the house or null (refused or missing).
    protected bool HCStructureStep(int index, out Object structure)
    {
        structure = null;
        if (index < 0 || index >= Count()) { return true; }
        if (!m_TickResolve) { m_TickResolve = new HCInteriorBoundedResolveCursor; }
        HCInteriorFurnishRow pose = HCStructurePose(index);
        if (!m_TickResolve.HCStep(pose)) { return false; }
        structure = m_TickResolve.HCHouse();
        m_TickResolve = null;
        if (structure) { m_StructureSeen.Set(index, structure); }
        return true;
    }

    // Hearth path: reuse the house phase 2 last resolved; fall back to the one-call lookup only
    // when none is known (the first fire before any rows step, or the object was deleted).
    Object Structure(int index)
    {
        if (index < 0 || index >= Count()) return null;
        Object seen = m_StructureSeen.Get(index);
        if (seen) return seen;
        HCInteriorFurnishRow pose = HCStructurePose(index);
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

    // Stable room order, then four inset corners, centre, and four edge midpoints.
    // Preserve the original low-corner inset and floor height. The complete crate
    // footprint and all door/stair/CE keepouts still veto each candidate.
    protected vector HCCacheCandidate(HCInteriorTemplateRoom room, int candidate, bool rotated)
    {
        float insetX = 0.55;
        float insetZ = 0.45;
        if (rotated) { insetX = 0.45; insetZ = 0.55; }
        float lowX = room.Min[0] + insetX;
        float highX = room.Max[0] - insetX;
        float lowZ = room.Min[2] + insetZ;
        float highZ = room.Max[2] - insetZ;
        float midX = (room.Min[0] + room.Max[0]) * 0.5;
        float midZ = (room.Min[2] + room.Max[2]) * 0.5;
        float spotX = lowX;
        float spotZ = lowZ;
        switch (candidate)
        {
            case 1: spotX = highX; break;
            case 2: spotZ = highZ; break;
            case 3: spotX = highX; spotZ = highZ; break;
            case 4: spotX = midX; spotZ = midZ; break;
            case 5: spotX = midX; break;
            case 6: spotX = midX; spotZ = highZ; break;
            case 7: spotZ = midZ; break;
            case 8: spotX = highX; spotZ = midZ; break;
        }
        return Vector(spotX, room.FloorY + 0.03, spotZ);
    }

    protected bool HCCacheFits(HCInteriorTemplate layout, HCInteriorTemplateRoom room, vector spot, bool rotated)
    {
        float halfX = 0.45;
        float halfZ = 0.35;
        if (rotated) { halfX = 0.35; halfZ = 0.45; }
        array<float> minimum = {spot[0] - halfX, spot[1], spot[2] - halfZ};
        array<float> maximum = {spot[0] + halfX, spot[1] + 0.5, spot[2] + halfZ};
        if (!HCInteriorTemplates.Inside(minimum, room.Min, room.Max) || !HCInteriorTemplates.Inside(maximum, room.Min, room.Max)) return false;
        // Admitted templates contain at most 32 keepouts; never skip one.
        if (!layout.KeepOuts || layout.KeepOuts.Count() > 32) return false;
        for (int keepIndex = 0; keepIndex < layout.KeepOuts.Count() && keepIndex < 32; keepIndex++)
        {
            HCInteriorTemplateKeepOut keepout = layout.KeepOuts[keepIndex];
            if (HCInteriorTemplates.Intersects(minimum, maximum, keepout.Min, keepout.Max, 0.6)) return false;
        }
        return true;
    }

    // 1 found, 0 exhausted/refused, -1 budget spent (retain row stage/cursor).
    // Exactly one refusal/continuation counter per unsuccessful call. Colliding
    // means at least one geometrically fitting candidate existed but all collided.
    int CacheSpot(Object structure, HCHoldoutRow row)
    {
        int templateStart = TickCount(0);
        HCInteriorTemplate layout = HCInteriorTemplates.Template(row.Ledger.HouseClass);
        if (m_MeasuringTick) { m_TickSteps.HCItem("interior_template", TickCount(templateStart)); }
        if (!layout || !layout.Rooms) { m_SpotNoTemplateWindow++; return 0; }
        int probes = 0;
        HCEncounterCacheIO probe = new HCEncounterCacheIO;
        // Guard geometry/keepout work as well as the eight native probes. The
        // cursor advances only after admission, including across orientations.
        m_SpotWork.HCReset(288, HCPerfConfig.HCGet().SliceMs);
        for (int examined = 0; examined < 288; examined++)
        {
            int roomIndex = m_SpotCandidate / 18;
            if (roomIndex >= layout.Rooms.Count() || roomIndex >= 16) break;
            if (probes >= 8 || !m_SpotWork.HCContinue()) { m_SpotBudgetWindow++; return -1; }
            bool rotated = (m_SpotCandidate % 18) >= 9;
            int candidate = m_SpotCandidate % 9;
            m_SpotCandidate++;
            HCInteriorTemplateRoom room = layout.Rooms[roomIndex];
            vector spot = HCCacheCandidate(room, candidate, rotated);
            if (!HCCacheFits(layout, room, spot, rotated)) continue;
            m_SpotHadFit = true;
            row.Cache.Position = structure.ModelToWorld(spot);
            vector cacheOrientation = structure.GetOrientation();
            if (rotated)
            {
                cacheOrientation[0] = cacheOrientation[0] + 90;
                if (cacheOrientation[0] > 180) { cacheOrientation[0] = cacheOrientation[0] - 360; }
            }
            row.Cache.Orientation = cacheOrientation;
            probes++;
            int probeStart = TickCount(0);
            bool clear = probe.Clear(row.Cache, structure);
            if (m_MeasuringTick) { m_TickSteps.HCItem("collision_probe", TickCount(probeStart)); }
            if (clear) return 1;
        }
        if (m_SpotHadFit) { m_SpotCollidingWindow++; }
        else { m_SpotNoFitWindow++; }
        return 0;
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
            row.Published = false;
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
        // The tick's final continuation publishes only rows marked unpublished.
        row.Published = false;
        m_Dirty = true;
        if (!SaveChanged()) { return; }
        // A tick publishes at its final continuation, after this one barrier.
        if (!m_MeasuringTick)
        {
            PublishState(row);
            if (!SaveChanged()) { return; }
        }
        HCLogRaid(row);
    }

    protected void HCLogRaid(HCHoldoutRow row)
    {
        int raidLockout = m_State.CampPolicy.RaidLockoutSeconds;
        string line = "[HollowCountry] V2 holdout raided id=" + row.Ledger.Id + " lockout=" + raidLockout.ToString() + "s runtime=PENDING";
        if (m_FixtureRows.Contains(row.Ledger.Id)) { line += " fixture=1"; }
        Print("" + line);
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

    // One bounded state census per five minutes. Counts describe logical
    // state, not live AI; progress includes rows blocked by house resolution.
    protected void HCReportWindow(float deltaTime, bool firstDecision = false)
    {
        m_SummaryElapsed += deltaTime;
        if (!firstDecision && m_SummaryElapsed < 300) { return; }
        m_SummaryElapsed = 0;
        int dormant = 0;
        int occupied = 0;
        int raided = 0;
        int abandoned = 0;
        int phase0 = 0;
        int phase1 = 0;
        int phase2 = 0;
        int phase3 = 0;
        int living = 0;
        array<ref HCHoldoutRow> summaryRows;
        if (m_State && m_State.Rows) { summaryRows = m_State.Rows; }
        int summaryCount;
        if (summaryRows) { summaryCount = summaryRows.Count(); }
        for (int summaryIndex = 0; summaryRows && summaryIndex < summaryRows.Count() && summaryIndex < HCAILimits.Get().MaxHoldouts; summaryIndex++)
        {
            HCHoldoutRow summaryRow = summaryRows[summaryIndex];
            if (!summaryRow || !summaryRow.Ledger || !summaryRow.Cache) { continue; }
            if (summaryRow.Camp && summaryRow.Camp.Allocated) { living += summaryRow.Camp.Population; }
            if (summaryRow.Ledger.State == "DORMANT") { dormant++; }
            else if (summaryRow.Ledger.State == "OCCUPIED" || summaryRow.Ledger.State == "ALERT") { occupied++; }
            else if (summaryRow.Ledger.State == "RAIDED") { raided++; }
            else if (summaryRow.Ledger.State == "ABANDONED") { abandoned++; }
            if (summaryRow.Cache.Phase == 0) { phase0++; }
            else if (summaryRow.Cache.Phase == 1) { phase1++; }
            else if (summaryRow.Cache.Phase == 2) { phase2++; }
            else if (summaryRow.Cache.Phase == 3) { phase3++; }
        }
        // One additional bounded logical census per report, no site/entity
        // probes. Forecast assumes no competing debit, death or refund; cache,
        // observer, occupancy and save gates still decide actual founding.
        int waiting = 0;
        int fundingPossible = -1;
        int populationBlocked = 0;
        int reserve = 0;
        int reservePopulation = 0;
        int reserveAt = 0;
        int nextReplenish = -1;
        int now = HCWorldClock.UTC();
        if (m_Ready && m_State && m_State.Resources && m_State.CampPolicy)
        {
            HCAICampResources pool = m_State.Resources;
            HCAICampPolicy policy = m_State.CampPolicy;
            reserve = pool.Stock;
            reservePopulation = pool.Population;
            reserveAt = pool.ReserveAt;
            nextReplenish = HCAICampLifecycle.HCNextReplenishSeconds(pool, now, policy);
            for (int waitIndex = 0; summaryRows && waitIndex < summaryRows.Count() && waitIndex < HCAILimits.Get().MaxHoldouts; waitIndex++)
            {
                HCHoldoutRow waitingRow = summaryRows[waitIndex];
                if (!waitingRow || !waitingRow.Camp || !waitingRow.Ledger) { continue; }
                if (waitingRow.Camp.Allocated && !waitingRow.Camp.Refunded) { continue; }
                waiting++;
                int population = HCAILimits.GroupSize(HCAILimits.Get().WorldSeed, waitingRow.Ledger.Id, "holdout");
                if (waitingRow.Camp.Population > 0) { population = waitingRow.Camp.Population; }
                int delay = HCAICampLifecycle.HCFundingWaitSeconds(pool, living, population - waitingRow.Camp.Population, now, policy);
                if (delay < 0) { populationBlocked++; continue; }
                // Subtract UTC ints before Math.Max's native float conversion.
                delay = Math.Max(delay, waitingRow.Camp.ReoccupyAfter - now);
                delay = Math.Max(delay, waitingRow.Ledger.ReoccupyAfter - now);
                if (fundingPossible < 0 || delay < fundingPossible) { fundingPossible = delay; }
            }
        }
        array<ref HCInteriorFurnishRow> authored = HCInteriorTemplates.FurnishRows();
        int catalogPending;
        if (authored && m_CatalogCursor < authored.Count() && summaryCount < HCAILimits.Get().MaxHoldouts) { catalogPending = authored.Count() - m_CatalogCursor; }
        string reason = "row_rotation";
        if (!m_Ready) { reason = m_Operational.HCReason(); }
        else if (!HCWorldModule.Get()) { reason = "world_unavailable"; }
        else if (!HCInteriorTemplates.Loaded()) { reason = "templates_loading"; }
        else if (m_CatalogDirty) { reason = "catalog_checkpoint"; }
        else if (catalogPending > 0) { reason = "catalog_discovery"; }
        else if (summaryCount == 0) { reason = "no_covered_houses"; }
        string receiptKind = "summary";
        if (firstDecision) { receiptKind = "first_decision"; }
        int pending = dormant + raided + abandoned;
        string line = "[HC Holdouts] " + receiptKind + " dormant=" + dormant.ToString() + " occupied=" + occupied.ToString();
        line += " raided=" + raided.ToString() + " abandoned=" + abandoned.ToString() + " founded_window=" + m_FoundedWindow.ToString();
        line += " cache_phase0=" + phase0.ToString() + " cache_phase1=" + phase1.ToString() + " cache_phase2=" + phase2.ToString() + " cache_phase3=" + phase3.ToString();
        line += " rows_stepped_window=" + m_RowsSteppedWindow.ToString() + " rows_completed_window=" + m_RowsCompletedWindow.ToString();
        line += " recovery_attempts_window=" + m_RecoveryAttemptsWindow.ToString() + " structure_blocked_window=" + m_StructureBlockedWindow.ToString();
        int spotBlocked = m_SpotNoTemplateWindow + m_SpotNoFitWindow + m_SpotCollidingWindow + m_SpotBudgetWindow;
        line += " spot_blocked_window=" + spotBlocked.ToString() + " observer_blocked_window=" + m_ObserverBlockedWindow.ToString();
        line += " spot_no_template=" + m_SpotNoTemplateWindow.ToString() + " spot_no_fit=" + m_SpotNoFitWindow.ToString();
        line += " spot_colliding=" + m_SpotCollidingWindow.ToString() + " spot_budget=" + m_SpotBudgetWindow.ToString();
        line += " founded=" + occupied.ToString() + " pending=" + pending.ToString() + " tick_phase=" + m_TickPhase.ToString();
        line += " catalog_pending_rows=" + catalogPending.ToString() + " catalog_cursor=" + m_CatalogCursor.ToString();
        line += " reserve=" + reserve.ToString() + " next_replenish_s=" + nextReplenish.ToString() + " waiting=" + waiting.ToString();
        line += " reserve_population=" + reservePopulation.ToString() + " allocated_population=" + living.ToString() + " reserve_at=" + reserveAt.ToString();
        line += " funding_possible_s=" + fundingPossible.ToString() + " population_blocked=" + populationBlocked.ToString();
        string fundingState = "available";
        if (!m_Ready) { fundingState = "unavailable"; }
        else if (waiting == 0) { fundingState = "no_waiting_camps"; }
        else if (fundingPossible < 0) { fundingState = "population_capacity"; }
        else if (nextReplenish == 0) { fundingState = "replenish_due"; }
        else if (fundingPossible > 0) { fundingState = "scheduled_wait"; }
        line += " funding_state=" + fundingState;
        line += " funding_forecast=logical_no_competing_debits";
        line += " ready=" + m_Ready.ToString() + " reason=" + reason;
        Print(line + " runtime=PENDING");
        m_RowsSteppedWindow = 0;
        m_RowsCompletedWindow = 0;
        m_FoundedWindow = 0;
        m_RecoveryAttemptsWindow = 0;
        m_StructureBlockedWindow = 0;
        m_SpotNoTemplateWindow = 0;
        m_SpotNoFitWindow = 0;
        m_SpotCollidingWindow = 0;
        m_SpotBudgetWindow = 0;
        m_ObserverBlockedWindow = 0;
    }

    // Membership is exclusively the authoritative ledger, including unauthored
    // live rows retained by MigrateTemplatePin. Never use authored slot ids.
    bool HCLiveHoldout(string id)
    {
        if (!m_Ready || !m_State) { return false; }
        foreach (HCHoldoutRow row : m_State.Rows)
        {
            if (row.Ledger.Id == id) { return true; }
        }
        return false;
    }

    string HCReconcileCatalogReason()
    {
        if (!m_Ready || !m_State || !m_Store) { return "catalog_unavailable"; }
        if (!HCInteriorTemplates.Loaded()) { return "catalog_filling"; }
        if (m_State.TemplatePin != "" && m_State.TemplatePin != HCInteriorTemplates.SourcePin()) { return "catalog_filling"; }
        array<ref HCInteriorFurnishRow> authored = HCInteriorTemplates.FurnishRows();
        if (!authored || (m_CatalogCursor < authored.Count() && Count() < HCAILimits.Get().MaxHoldouts)) { return "catalog_filling"; }
        if (m_CatalogDirty || m_Dirty || m_Store.SaveInFlight()) { return "catalog_filling"; }
        return "";
    }

    protected void HCReconcileWorld(HCWorldModule world)
    {
        if (m_Reconciled) { return; }
        string reason = HCReconcileCatalogReason();
        if (reason != "")
        {
            if (m_ReconcileWait != reason)
            {
                Print("[HC World] holdout reconcile stale=0 reused=0 dropped_occupants=0 retired=0 refused=" + reason);
                m_ReconcileWait = reason;
            }
            return;
        }
        // Native scripts-1.30.164289: 1_Core/proto/EnScript.c:407 array
        // Insert, :902 map.Set. One bounded ledger map pass, no native probes.
        map<string, bool> ids = new map<string, bool>;
        array<ref HCWorldHoldout> live = new array<ref HCWorldHoldout>;
        foreach (HCHoldoutRow row : m_State.Rows)
        {
            ids.Set(row.Ledger.Id, true);
            live.Insert(row.Ledger);
        }
        world.HCReconcileHoldouts(live, ids);
        m_Reconciled = true;
    }

    override void OnTick(float deltaTime)
    {
        m_TickMeasuredStage = 0;
        HCReportWindow(deltaTime);
        HCWorldModule censusWorld = HCWorldModule.Get();
        if (!censusWorld) { return; }
        if (!m_Ready) { HCReconcileWorld(censusWorld); return; }
        m_Elapsed += deltaTime;
        if (!HCInteriorTemplates.Loaded())
        {
            if (!m_WaitReported) Print("[HollowCountry] V2 holdouts waiting for authored covered template houses");
            m_WaitReported = true;
            HCReconcileWorld(censusWorld);
            return;
        }
        if (m_State.TemplatePin != "" && m_State.TemplatePin != HCInteriorTemplates.SourcePin()) { MigrateTemplatePin(); return; }
        FillCatalog();
        HCReconcileWorld(censusWorld);
        if (m_CatalogDirty)
        {
            // The scheduler owns routine catalog saves. Without routine dispatch,
            // advance only one stage through the scheduler fallback.
            if (!HCPerfConfig.HCGet().EnableSharedSaves || !HCSaveScheduler.HCRegistered(m_SaveJob))
            {
                m_SaveJob.HCUrgent = true;
                HCSaveScheduler.HCPumpFallback(m_SaveJob);
            }
            m_WorkBudget.HCDeferred(GetName(), 1);
            return;
        }
        // Discovery and simulation never receive independent slices in one tick.
        if (m_CatalogWorked) { return; }
        if (!m_Ready || Count() == 0) { return; }
        if (m_TickPhase == 0)
        {
            if (m_Elapsed < 1) { return; }
            m_Elapsed = 0;
            if (m_Next >= Count()) m_Next = 0;
            m_SpotCandidate = 0;
            m_SpotHadFit = false;
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
        // Callbacks can dirty any row between continuations. Do not expose a
        // newer image or start another side effect until that image is durable.
        if (m_TickPhase != 10 && m_TickPhase != 12 && (m_Dirty || m_Store.SaveInFlight()))
        {
            m_TickAfterSave = m_TickPhase;
            m_TickPhase = 12;
            m_TickMeasuredStage = 12;
        }
        // One save-image stage or one materialization operation per admitted
        // tick. Never create before the complete intent has been verified.
        if (m_TickPhase == 10 || m_TickPhase == 12)
        {
            if (m_Dirty || m_Store.SaveInFlight())
            {
                m_SaveJob.HCDirty = true;
                m_SaveJob.HCUrgent = true;
                HCSaveScheduler.HCPumpFallback(m_SaveJob);
                return;
            }
            if (m_TickPhase == 10) { m_TickPhase = 11; }
            else { m_TickPhase = m_TickAfterSave; }
            return;
        }
        // Repair a cross-store interrupted publish even when a house/cache
        // cannot currently resolve. Local durable state is authoritative.
        if (m_TickPhase == 1)
        {
            m_RowsSteppedWindow++;
            if (!row.Published)
            {
                PublishState(row);
            }
            m_TickPhase = 2;
            return;
        }
        if (m_TickPhase == 2)
        {
            if (!HCStructureStep(index, m_TickStructure)) { return; }
            if (!m_TickStructure) { m_StructureBlockedWindow++; m_TickPhase = 0; return; }
            m_TickPhase = 3;
            return;
        }
        Object structure = m_TickStructure;
        if (!structure) { m_TickPhase = 0; return; }
        if (m_TickPhase == 3)
        {
            bool unoccupied = row.Ledger.Occupants == 0 && (row.Ledger.State == "DORMANT" || row.Ledger.State == "ABANDONED" || row.Ledger.State == "RAIDED");
            if (row.Cache.Phase == 3 && unoccupied && now >= row.Ledger.ReoccupyAfter && now >= row.Camp.ReoccupyAfter)
            {
                // Retire the old link, including any carried/ruined live handle.
                // Never delete it, transfer cargo, reset stock attempts or spend
                // founding reserves here. An occupied lost cache raids in stage 4.
                row.Cache.Phase = 0;
                row.Cache.EntityRef = "";
                row.Ledger.CacheRef = "";
                row.Contents.Clear();
                row.Published = false;
                m_Caches[index] = new HCEncounterCacheIO;
                m_Dirty = true;
                // Count retired-link recovery attempts, not usable replacements.
                // Placement, creation and durable linking may still fail.
                m_RecoveryAttemptsWindow++;
                m_TickAfterSave = 3;
                m_TickPhase = 12;
                return;
            }
            if (row.Cache.Phase == 0)
            {
                if (!HCObserverTransitionGate.CanTransition(row.Ledger.HousePos, 500)) { m_ObserverBlockedWindow++; }
                else
                {
                    int spotResult = CacheSpot(structure, row);
                    if (spotResult < 0) { return; }
                    if (spotResult > 0)
                    {
                        if (!HCObserverTransitionGate.CanTransition(row.Cache.Position, 500)) { m_ObserverBlockedWindow++; }
                        else
                        {
                            row.Cache.Phase = 1;
                            m_Dirty = true;
                            m_TickPhase = 10;
                            return;
                        }
                    }
                }
            }
            if (row.Ledger.CacheRef != row.Cache.EntityRef)
            {
                row.Ledger.CacheRef = row.Cache.EntityRef;
                row.Published = false;
                m_Dirty = true;
            }
            m_TickAfterSave = 4;
            if (m_Dirty || m_Store.SaveInFlight()) { m_TickPhase = 12; }
            else { m_TickPhase = 4; }
            return;
        }
        if (m_TickPhase == 11)
        {
            if (!HCObserverTransitionGate.CanTransition(row.Cache.Position, 500))
            {
                // No crate was created. Clear the durable intent through the
                // result barrier and rotate, rather than pinning on an observer.
                m_ObserverBlockedWindow++;
                row.Cache.Phase = 0;
            }
            else { m_Caches[index].Create(row.Cache); }
            if (row.Ledger.CacheRef != row.Cache.EntityRef)
            {
                row.Ledger.CacheRef = row.Cache.EntityRef;
                row.Published = false;
            }
            m_Dirty = true;
            m_TickAfterSave = 4;
            m_TickPhase = 12;
            return;
        }
        if (m_TickPhase == 4)
        {
            int cachePhase = row.Cache.Phase;
            string cacheRef = row.Cache.EntityRef;
            if (row.Cache.Phase != 0) m_Caches[index].LinkCache(row.Cache);
            if (cachePhase != row.Cache.Phase || cacheRef != row.Cache.EntityRef) m_Dirty = true;
            if (row.Ledger.CacheRef != row.Cache.EntityRef)
            {
                row.Ledger.CacheRef = row.Cache.EntityRef;
                row.Published = false;
                m_Dirty = true;
            }
            if ((row.Ledger.State == "OCCUPIED" || row.Ledger.State == "ALERT") && (row.Cache.Phase == 3 || LootRemoved(index)))
            {
                m_TickPhase = 14;
                return;
            }
            m_TickAfterSave = 5;
            if (m_Dirty || m_Store.SaveInFlight()) { m_TickPhase = 12; }
            else { m_TickPhase = 5; }
            return;
        }
        if (m_TickPhase == 14)
        {
            HCRaidCamp(index);
            m_TickAfterRaid = 5;
            m_TickAfterSave = 16;
            m_TickPhase = 12;
            return;
        }
        if (m_TickPhase == 5)
        {
            string previousState = row.Ledger.State;
            HCAdvanceOccupancy(index, now);
            if (!m_Ready) { return; }
            if (m_CampReserveSaved) { m_TickAfterSave = 5; m_TickPhase = 12; return; }
            if (m_Dirty || m_Store.SaveInFlight()) { m_TickAfterSave = 15; m_TickPhase = 12; return; }
            if (m_FixtureRows.Count() > 0) { m_FixtureRows.Remove(row.Ledger.Id); }
            m_BodyNext = m_Bodies.Count() - 1;
            m_TickPhase = 6;
            // With no bodies or occupied inventory work, finish bookkeeping
            // here. Never run another row or another native probe in this tick.
            if (row.Ledger.State != previousState || m_BodyNext >= 0 || row.Ledger.State == "OCCUPIED" || row.Ledger.State == "ALERT") { return; }
        }
        if (m_TickPhase == 15)
        {
            if (m_CampFoundedPending) { m_FoundedWindow++; }
            m_CampFoundedPending = false;
            if (m_CampCommitPending) { HCLogCamp(row, "ready", "EAT_FIRE_REPAIR_UNPROVEN"); }
            m_CampCommitPending = false;
            m_BodyNext = m_Bodies.Count() - 1;
            m_TickPhase = 6;
            return;
        }
        if (m_TickPhase == 16)
        {
            HCLogRaid(row);
            m_TickPhase = m_TickAfterRaid;
            return;
        }
        if (m_TickPhase == 6)
        {
            m_TickMeasuredStage = 6;
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
                bool wasRaided = row.Ledger.State == "RAIDED";
                HCRaidCamp(index);
                m_TickAfterRaid = 6;
                m_TickAfterSave = 6;
                if (!wasRaided) { m_TickAfterSave = 16; }
                m_TickPhase = 12;
                return;
            }
            m_TickPhase = 7;
        }
        if (m_TickPhase == 7)
        {
            m_TickMeasuredStage = 7;
            if (row.Ledger.State == "OCCUPIED" || row.Ledger.State == "ALERT")
            {
                HCSearchHouses houses = HCSearchBinding.Houses();
                // Three lifetime attempts, one per real day. No replenishment on raid.
                // HC-34: the remote house hop is refused; do not burn attempts or save for it.
                if (houses && houses.V2VisitAvailable() && Cache(index) && row.StockAttempts < 3 && HCEscalationClock.Day() >= row.StockDay && HCObserverTransitionGate.CanTransition(row.Cache.Position, 500))
                {
                    m_TickStockSite = row.StockAttempts;
                    row.StockAttempts++;
                    row.StockDay = HCEscalationClock.Day() + 1;
                    m_Dirty = true;
                    m_TickAfterSave = 13;
                    m_TickPhase = 12;
                    return;
                }
            }
            if (m_Dirty || m_Store.SaveInFlight()) { m_TickAfterSave = 8; m_TickPhase = 12; return; }
            m_TickPhase = 8;
            if (row.Ledger.State == "OCCUPIED" || row.Ledger.State == "ALERT") { return; }
        }
        if (m_TickPhase == 13)
        {
            HCSearchHouses stockHouses = HCSearchBinding.Houses();
            if (stockHouses && Cache(index) && HCObserverTransitionGate.CanTransition(row.Cache.Position, 500))
            {
                int stockPhase = stockHouses.V2Visit(structure, Cache(index), row.Ledger.Id, m_TickStockSite);
                if (stockPhase == 3) { row.StockAttempts = 3; m_Dirty = true; }
                if (m_Reports < 12)
                {
                    m_Reports++;
                    Print("[HollowCountry] V2 holdout stock id=" + row.Ledger.Id + " phase=" + stockPhase.ToString());
                }
            }
            m_TickAfterSave = 8;
            if (m_Dirty || m_Store.SaveInFlight()) { m_TickPhase = 12; }
            else { m_TickPhase = 8; }
            return;
        }
        if (m_TickPhase == 8)
        {
            m_TickMeasuredStage = 8;
            if (row.Ledger.State == "OCCUPIED" || row.Ledger.State == "ALERT") SnapshotContents(index);
            if (m_Dirty || m_Store.SaveInFlight()) { m_TickAfterSave = 9; m_TickPhase = 12; return; }
            m_TickPhase = 9;
            if (row.Ledger.State == "OCCUPIED" || row.Ledger.State == "ALERT") { return; }
        }
        m_TickMeasuredStage = 9;
        if (row.Ledger.CacheRef != row.Cache.EntityRef)
        {
            row.Ledger.CacheRef = row.Cache.EntityRef;
            row.Published = false;
            m_Dirty = true;
        }
        if (m_Dirty || m_Store.SaveInFlight()) { m_TickAfterSave = 9; m_TickPhase = 12; return; }
        HCWorldModule world = HCWorldModule.Get();
        if (world && !row.Published)
        {
            PublishState(row);
        }
        m_RowsCompletedWindow++;
        m_TickPhase = 0;
        m_TickStructure = null;
        m_TickResolve = null;
    }


    override void OnStop()
    {
        m_TickPhase = 0;
        m_TickStructure = null;
        m_TickResolve = null;
        // Flush changes marked by native callbacks since the last tick; a faulted store stays unwritten.
        if (m_Ready && m_State) { SaveChanged(); }
        HCSaveScheduler.HCUnregister(m_SaveJob);
        HCDebugSnapshot.HCUnregister(m_CampDebug);
        m_CampDebug = null;
        m_Ready = false;
        m_Operational.HCPublish("off", "stopped");
        Print("[HC Plan] HC-16 camp=none level=-1 supply=0 roles=0 state=off runtime=PENDING");
        // Native 3_Game/gameplay.c:117 ScriptRPC.Send: no light publication at finish.
        if (HCServer.HCMissionFinishing()) { HCServer.HCTeardownRPCSkipped++; }
        else { HCSyncLights(); }
        m_Bodies.Clear();
        m_CampRefusals.Clear();
        m_FixtureRows.Clear();
        m_ViewHomes.Clear();
        m_ViewKeys.Clear();
        if (s_Instance == this) s_Instance = null;
    }
}

// Native EnSystem.c:106 TickCount; EnDebug.c:96 Print; EnMath.c:553 Min. Measure every
// continuation, including catalog and no-op ticks, with the shared step timer.
modded class HCHoldouts
{
    protected string HCTickStageName(int phase)
    {
        switch (phase)
        {
            case 0: return "catalog";
            case 1: return "publish";
            case 2: return "structure_lookup";
            case 3: return "cache_fit";
            case 4: return "cache_link";
            case 5: return "camp";
            case 6: return "bodies";
            case 7: return "stock_commit";
            case 8: return "contents";
            case 9: return "publish_commit";
            case 10: return "cache_intent_save";
            case 11: return "cache_materializer";
            case 12: return "result_save";
            case 13: return "stock_materializer";
            case 14: return "raid_commit";
            case 15: return "camp_commit";
            case 16: return "raid_complete";
        }
        return "maintenance";
    }

    protected int HCTickStageIndex(int phase)
    {
        if (phase == 10 || phase == 12) { return 7; }
        if (phase == 11 || phase == 4) { return 4; }
        if (phase == 13) { return 6; }
        if (phase == 14 || phase == 15 || phase == 16) { return 5; }
        if (phase == 8) { return 6; }
        if (phase == 9) { return 1; }
        return Math.Min(phase, 6);
    }

    override void OnStart(HCSettings settings)
    {
        super.OnStart(settings);
        m_SummaryElapsed = 0;
        HCReportWindow(0, true);
        m_TickSteps = new HCStepTimer("Holdouts");
        m_TickSteps.HCDefine("catalog");
        m_TickSteps.HCDefine("publish");
        m_TickSteps.HCDefine("resolve");
        m_TickSteps.HCDefine("cache_fit");
        m_TickSteps.HCDefine("cache_io");
        m_TickSteps.HCDefine("camp");
        m_TickSteps.HCDefine("stock_contents");
        m_TickSteps.HCDefine("save");
        Print("[HC PerfControl] Holdouts heavy_operations_per_tick=1 cache_probes_per_step=8 cache_orientations=2 save_steps_per_tick=1 cooperative_only=1 runtime=PENDING");
    }
    override void OnTick(float deltaTime)
    {
        int tickStart = TickCount(0);
        m_MeasuringTick = true;
        super.OnTick(deltaTime);
        m_MeasuringTick = false;
        int elapsedTicks = TickCount(tickStart);
        m_TickSteps.HCAdd(HCTickStageIndex(m_TickMeasuredStage), elapsedTicks);
        string stageItem = HCTickStageName(m_TickMeasuredStage);
        if (m_TickMeasuredStage == 2) { stageItem = stageItem + ":" + HCInteriorTemplatePlacement.HCLastType(); }
        m_TickSteps.HCItem(stageItem, elapsedTicks);
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
