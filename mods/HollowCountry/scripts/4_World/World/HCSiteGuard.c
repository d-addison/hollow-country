// W6 runtime site guard (4_World half; the 3_Game spawner half is Core/HCGroundObjectSpawner.c).
// Native evidence scripts-1.30.164289 (paths relative to the scripts root):
//   3_Game/Global/Game.c:1333 IsBoxColliding, :930 GetObjectsAtPosition3D, :1176 SurfaceY, :612 ConfigIsExisting,
//   :705 ObjectDelete; 3_Game/Global/World.c:135 ProcessMarkedObjectsForPathgraphUpdate;
//   4_World/Entities/EntityAI.c :646 IsEmpty, :791 DeleteSafe, :885 GetHierarchyParent, :905 EEInit, :946 EEDelete,
//   :1419 AfterStoreLoad; 4_World/Entities/ItemBase/BaseBuildingBase.c :408 EEDelete, :465 AfterStoreLoad (native
//   overrides, so the modded overrides below call super first); 3_Game/Entities/Object.c :523 IsMan, :577
//   IsInventoryItem, :595 IsTree, :601 IsRock, :613 IsBush, :642 IsBuilding, :686 IsTransport;
//   1_Core/proto/EnString.c :171 ToLower (in place), :240 IndexOf.
// The guard decides, after storage load, which composed sites spawn. It never deletes a player item: site
// pieces are non-persistent props the guard itself created, and fresh CE loot is only dropped in boxes of
// refused or retired sites (HCGroundCELoot.c). Decisions are staged through HCV2ThreatStore and fail closed.

// Optional profile file $profile:HollowCountry/sites-config.json. Every field is registry-gated (Sites.*).
class HCSiteConfig
{
    int DecideDelaySeconds = 60;
    int QuietWindowSeconds = 10;
    int BaseMarginM = 15;
    int UnitsPerGrant = 8;
    int PlayerClearM = 30;
    int OccupiedRetryBoots = 3;
    protected static ref HCSiteConfig s_Config;
    static HCSiteConfig HCGet()
    {
        if (s_Config) { return s_Config; }
        HCOperatorSettingsRegistry.HCSitesInit();
        s_Config = new HCSiteConfig;
        string path = "$profile:HollowCountry/sites-config.json";
        if (!FileExist(path)) { return s_Config; }
        string text;
        string error;
        HCSiteConfig decoded;
        if (!HCGroupIO.Read(path, 4096, text) || !HCJsonSchemaLoader<HCSiteConfig>.HCLoadData(text, decoded, error) || !decoded)
        {
            Print("[HC Sites] config defaults_restored runtime=PENDING");
            return s_Config;
        }
        s_Config.HCApply(decoded, text);
        return s_Config;
    }
    protected int HCRegistryInt(string key, int candidate, int current)
    {
        if (HCOperatorSettingsRegistry.HCValid("Sites." + key, candidate)) { return candidate; }
        return current;
    }
    void HCApply(HCSiteConfig decoded, string text)
    {
        DecideDelaySeconds = HCRegistryInt("DecideDelaySeconds", HCJsonSchema.HCApplyInt(text, "DecideDelaySeconds", decoded.DecideDelaySeconds, DecideDelaySeconds), DecideDelaySeconds);
        QuietWindowSeconds = HCRegistryInt("QuietWindowSeconds", HCJsonSchema.HCApplyInt(text, "QuietWindowSeconds", decoded.QuietWindowSeconds, QuietWindowSeconds), QuietWindowSeconds);
        BaseMarginM = HCRegistryInt("BaseMarginM", HCJsonSchema.HCApplyInt(text, "BaseMarginM", decoded.BaseMarginM, BaseMarginM), BaseMarginM);
        UnitsPerGrant = HCRegistryInt("UnitsPerGrant", HCJsonSchema.HCApplyInt(text, "UnitsPerGrant", decoded.UnitsPerGrant, UnitsPerGrant), UnitsPerGrant);
        PlayerClearM = HCRegistryInt("PlayerClearM", HCJsonSchema.HCApplyInt(text, "PlayerClearM", decoded.PlayerClearM, PlayerClearM), PlayerClearM);
        OccupiedRetryBoots = HCRegistryInt("OccupiedRetryBoots", HCJsonSchema.HCApplyInt(text, "OccupiedRetryBoots", decoded.OccupiedRetryBoots, OccupiedRetryBoots), OccupiedRetryBoots);
    }
}

// 2-D oriented box maths. Convention (an assumption the manifest writer must match): the box is rotated
// by yawDeg about its centre, and a point maps to box space as lx = dx*cos - dz*sin, lz = dx*sin + dz*cos.
class HCSiteGeo
{
    static bool InBox(float px, float pz, float cx, float cz, float hx, float hz, float yawDeg, float margin)
    {
        float rad = yawDeg * Math.DEG2RAD;
        float dx = px - cx;
        float dz = pz - cz;
        float cosine = Math.Cos(rad);
        float sine = Math.Sin(rad);
        float lx = dx * cosine - dz * sine;
        float lz = dx * sine + dz * cosine;
        return Math.AbsFloat(lx) <= hx + margin && Math.AbsFloat(lz) <= hz + margin;
    }

    static float Dist2D(float ax, float az, float bx, float bz)
    {
        float dx = ax - bx;
        float dz = az - bz;
        return Math.Sqrt(dx * dx + dz * dz);
    }

    static string Short(string text)
    {
        if (text.Length() <= 8) { return text; }
        return text.Substring(0, 8);
    }
}

// One loot box of the guard's CE-loot grid. Site "" is a retired-only box.
class HCSiteBox
{
    string Site;
    float X;
    float Z;
    float HX;
    float HZ;
    float Yaw;
}

// Bounded registries of player-buildable objects, kept by EEInit/EEDelete (no world scan). Tents and
// storage are already tracked by HCBasesContainers. The load clock lets the guard wait for the storage load.
class HCSiteBaseRegistry
{
    protected static ref array<BaseBuildingBase> s_Base = new array<BaseBuildingBase>;
    protected static ref array<UndergroundStash> s_Stash = new array<UndergroundStash>;
    protected static int s_Overflow;
    protected static int s_Loads;
    protected static float s_LastLoad = -1000;

    static void AddBase(BaseBuildingBase item)
    {
        if (!GetGame() || !GetGame().IsServer() || !item || s_Base.Find(item) >= 0) { return; }
        if (s_Base.Count() >= 4096) { s_Overflow++; return; }
        s_Base.Insert(item);
    }

    static void RemoveBase(BaseBuildingBase item)
    {
        int index = s_Base.Find(item);
        if (index >= 0) { s_Base.Remove(index); }
    }

    static void AddStash(UndergroundStash item)
    {
        if (!GetGame() || !GetGame().IsServer() || !item || s_Stash.Find(item) >= 0) { return; }
        if (s_Stash.Count() >= 4096) { s_Overflow++; return; }
        s_Stash.Insert(item);
    }

    static void RemoveStash(UndergroundStash item)
    {
        int index = s_Stash.Find(item);
        if (index >= 0) { s_Stash.Remove(index); }
    }

    // A watched object (base piece, stash, tent or storage) was restored from storage.
    static void Touch()
    {
        if (!GetGame() || !GetGame().IsServer()) { return; }
        s_Loads++;
        s_LastLoad = GetGame().GetTickTime();
    }

    static int BaseCount() { return s_Base.Count(); }
    static int StashCount() { return s_Stash.Count(); }
    static int Loads() { return s_Loads; }
    static int Overflow() { return s_Overflow; }
    static float LastLoad() { return s_LastLoad; }
    static BaseBuildingBase BaseAt(int index)
    {
        if (index < 0 || index >= s_Base.Count()) { return null; }
        return s_Base[index];
    }
    static UndergroundStash StashAt(int index)
    {
        if (index < 0 || index >= s_Stash.Count()) { return null; }
        return s_Stash[index];
    }
}

modded class BaseBuildingBase
{
    override void EEInit()
    {
        super.EEInit();
        HCSiteBaseRegistry.AddBase(this);
    }

    override void EEDelete(EntityAI parent)
    {
        HCSiteBaseRegistry.RemoveBase(this);
        super.EEDelete(parent);
    }

    override void AfterStoreLoad()
    {
        super.AfterStoreLoad();
        HCSiteBaseRegistry.Touch();
    }
}

modded class UndergroundStash
{
    override void EEInit()
    {
        super.EEInit();
        HCSiteBaseRegistry.AddStash(this);
    }

    override void EEDelete(EntityAI parent)
    {
        HCSiteBaseRegistry.RemoveStash(this);
        super.EEDelete(parent);
    }

    override void AfterStoreLoad()
    {
        super.AfterStoreLoad();
        HCSiteBaseRegistry.Touch();
    }
}

// Read-only position evidence from the Camps module (m_Data is protected there). Bounded copies.
modded class HCCampModule
{
    static bool HCSiteEvidence(array<vector> claims, array<vector> camps)
    {
        HCCampModule module = HCCampModule.Get();
        if (!module || !module.m_Data) { return false; }
        HCCampData data = module.m_Data;
        array<ref HCBuildingClaimRecord> claimRows = data.Claims;
        array<ref HCCampRecord> campRows = data.Camps;
        foreach (HCBuildingClaimRecord claim : claimRows)
        {
            if (claims.Count() >= 1024) { break; }
            claims.Insert(claim.Position);
        }
        foreach (HCCampRecord camp : campRows)
        {
            if (camps.Count() >= 1024) { break; }
            camps.Insert(camp.Position);
        }
        return true;
    }
}

class HCSiteSaveJob : HCSaveJob
{
    HCSiteGuard Owner;
    override string HCName() { return "Sites"; }
    override int HCStep()
    {
        if (!Owner) { return STEP_FAILED; }
        return Owner.HCStepSave();
    }
    override bool HCPendingCheckpoint() { return Owner && Owner.HCRevisionPending(); }
}

class HCSiteGuard : HCModule
{
    static const int PH_WAIT = 0;
    static const int PH_DECIDE = 1;
    static const int PH_GROUND = 2;
    static const int PH_SWEEP = 3;
    static const int PH_IDLE = 4;
    static const int ST_EVAL = 0;
    static const int ST_HARD = 1;
    static const int ST_CLASS = 2;
    static const int ST_SPAWN = 3;
    static const int LOOT_KEEP = 0;
    static const int LOOT_HOLD = 1;
    static const int LOOT_DROP = 2;

    protected static HCSiteGuard s_Instance;
    protected ref HCOperationalStatus m_Operational = new HCOperationalStatus;
    protected ref HCSiteConfig m_Config;
    protected HCSiteManifest m_Manifest;
    protected ref HCSiteState m_State;
    protected ref HCV2ThreatStore<HCSiteState> m_Writer = new HCV2ThreatStore<HCSiteState>;
    protected ref HCSiteSaveJob m_Job;
    protected ref HCWorkBudget m_Budget = new HCWorkBudget;
    protected bool m_Active;
    protected bool m_Composed;
    protected bool m_StateFresh;
    protected bool m_StateRecovered;
    protected bool m_Quarantined;
    protected bool m_PersistOff;
    protected int m_Revision;
    protected int m_Durable;
    protected int m_SaveFailures;
    protected float m_SaveRetryAt;
    protected int m_Phase;
    protected float m_StartTime;
    protected float m_NextPump;
    protected int m_MsMax;
    protected int m_PassAdmitted;
    protected int m_PassRefused;
    // Decision cursor.
    protected ref array<string> m_Pending = new array<string>;
    protected ref array<string> m_Waiting = new array<string>;
    protected ref array<float> m_WaitDue = new array<float>;
    protected ref map<string, int> m_Retries = new map<string, int>;
    protected ref map<string, bool> m_Attempted = new map<string, bool>;
    protected ref map<string, bool> m_Logged = new map<string, bool>;
    protected ref array<string> m_AdmittedNow = new array<string>;
    protected ref array<string> m_CountQueue = new array<string>;
    protected string m_CurSite;
    protected int m_CurStep;
    protected int m_CurPiece;
    protected int m_CurRow;
    protected bool m_CurPostponedLogged;
    protected ref array<Object> m_CurSpawned = new array<Object>;
    protected bool m_PassDone;
    // Registry evidence of the site being evaluated.
    protected ref array<vector> m_EvPos = new array<vector>;
    protected ref array<vector> m_WeakPos = new array<vector>;
    protected ref array<vector> m_NearVeh = new array<vector>;
    protected ref array<vector> m_ClaimPos = new array<vector>;
    protected ref array<vector> m_CampPos = new array<vector>;
    protected int m_FortIgnored;
    protected ref array<Object> m_Hits = new array<Object>;
    protected ref array<Object> m_Excl = new array<Object>;
    // Ground self-test and overlap re-check.
    protected int m_GSite;
    protected int m_GPiece;
    protected int m_GChecked;
    protected int m_GStale;
    protected float m_GMaxDy;
    protected string m_GFail;
    protected int m_OSite;
    protected int m_Overlaps;
    protected bool m_GroundDone;
    // Sweep.
    protected int m_SkipTry;
    protected float m_SweepRetryAt;
    protected int m_SweepTruncated;
    protected bool m_SweepStarted;
    protected ref array<Object> m_ObjA = new array<Object>;
    protected ref array<CargoBase> m_CargoA = new array<CargoBase>;
    protected int m_BoxesSinceSave;
    // CE loot grid and per-site loot status (0 hold, 1 keep, 2 drop).
    protected ref map<int, ref array<ref HCSiteBox>> m_Grid = new map<int, ref array<ref HCSiteBox>>;
    protected ref map<string, int> m_SiteStatus = new map<string, int>;
    protected bool m_GridOn;
    protected int m_RetiredDropped;
    protected int m_RetiredLogged;
    protected ref array<string> m_RetiredSample = new array<string>;
    protected float m_RetiredLogAt;

    override string GetName() { return "Sites"; }
    override HCOperationalStatus HCGetOperationalStatus() { return m_Operational; }

    // The module is enabled only when something is installed to act on: a manifest (compose) or a state file
    // (sweep-only). Neither means a plain server: print enabled=false reason=no_manifest and do nothing else.
    override bool IsEnabled(HCSettings settings)
    {
        if (!settings || !settings.EnableSites)
        {
            m_Operational.HCPublish("off", "disabled_by_setting");
            return false;
        }
        if (!FileExist(HCSiteFormat.MANIFEST_PATH) && !FileExist(HCSiteFormat.STATE_PATH) && !FileExist(HCSiteFormat.STATE_PATH + ".tmp") && !FileExist(HCSiteFormat.STATE_PATH + ".bak"))
        {
            m_Operational.HCPublish("off", "no_manifest");
            return false;
        }
        return true;
    }

    override void RegisterUses()
    {
        HCModuleReadiness.HCRegisterUse("Sites", "composed_sites");
        HCModuleReadiness.HCRegisterUse("Sites", "site_refusals");
        HCModuleReadiness.HCRegisterUse("Sites", "orphan_sweep");
    }

    static bool HCIsRefused(string siteId)
    {
        if (!s_Instance) { return false; }
        return s_Instance.StatusOf(siteId) == 2;
    }

    static bool HCIsAdmitted(string siteId)
    {
        if (!s_Instance) { return false; }
        return s_Instance.StatusOf(siteId) == 1;
    }

    protected int StatusOf(string siteId)
    {
        int status;
        if (m_SiteStatus.Find(siteId, status)) { return status; }
        return -1;
    }

    protected void Log(string text)
    {
        Print("[HC Sites] " + text);
    }

    // ---- start, state load and migration ---------------------------------------------------------------

    override void OnStart(HCSettings settings)
    {
        if (!GetGame().IsServer() || m_Active || s_Instance)
        {
            Log("start skipped reason=not_server_or_active");
            return;
        }
        m_Config = HCSiteConfig.HCGet();
        m_StartTime = GetGame().GetTickTime();
        if (!ObjectSpawnerHandler.HCSiteView) { ObjectSpawnerHandler.HCSiteLoadViews(); }
        bool present = ObjectSpawnerHandler.HCSiteManifestPresent;
        if (present && !ObjectSpawnerHandler.HCSiteManifestOk)
        {
            m_Operational.HCPublish("refused", "manifest_invalid");
            Log("mode=refused reason=manifest_invalid");
            return;
        }
        m_Manifest = ObjectSpawnerHandler.HCSiteManifestData;
        m_Composed = present;
        LoadState();
        if (m_Composed) { PrepareComposed(); }
        else { PrepareSweepOnly(); }
        BuildGrid();
        Log("state recovered=" + m_StateRecovered.ToString() + " quarantined=" + m_Quarantined.ToString() + " persist=" + (!m_PersistOff).ToString());
        m_Job = new HCSiteSaveJob;
        m_Job.Owner = this;
        if (!m_PersistOff)
        {
            HCSaveScheduler.HCRegister(m_Job);
            Touch(true);
        }
        string reason = "decisions_pending";
        if (!m_Composed) { reason = "sweep_only"; }
        else if (m_PersistOff) { reason = "state_degraded"; }
        else if (HasSettledDecision()) { reason = "decisions_loaded"; }
        string readyState = "ready";
        if (m_PersistOff) { readyState = "degraded"; }
        m_Operational.HCPublish(readyState, reason);
        m_Phase = HCSiteGuard.PH_WAIT;
        m_Active = true;
        s_Instance = this;
    }

    protected bool HasSettledDecision()
    {
        array<ref HCSiteDecision> list = m_State.Decisions;
        foreach (HCSiteDecision decision : list)
        {
            if (decision.State != 0) { return true; }
        }
        return false;
    }

    protected void FreshState()
    {
        m_State = new HCSiteState;
        m_State.Version = 1;
        m_State.WorldName = HCSiteFormat.WorldName();
        m_State.LayerSet = "";
        m_State.Boots = 0;
    }

    // CanOpen runs the shared crash recovery once (.tmp promote/clear, .bak restore). A state that still
    // cannot be opened or fails the shape checks is quarantined (copied, then removed): first-boot semantics.
    protected void LoadState()
    {
        string path = HCSiteFormat.STATE_PATH;
        bool hadAny = FileExist(path) || FileExist(path + ".tmp") || FileExist(path + ".bak");
        m_StateFresh = !hadAny;
        if (!hadAny) { FreshState(); return; }
        bool tmpBefore = FileExist(path + ".tmp");
        bool bakOnly = !FileExist(path) && FileExist(path + ".bak");
        bool open = HCV2ThreatStore<HCSiteState>.CanOpen(path);
        if (!open && FileExist(path + ".tmp") && FileExist(path))
        {
            if (HCStagedSaveImage.HCClearCompletedIntent(path, 262144, "sites")) { open = HCV2ThreatStore<HCSiteState>.CanOpen(path); }
        }
        if (open && !FileExist(path)) { FreshState(); m_StateFresh = true; return; }
        HCSiteState loaded;
        bool good = false;
        if (open)
        {
            good = HCGroupIO.HCLooksWholeObject(path, HCSiteFormat.STATE_BYTES) && HCV2ThreatStore<HCSiteState>.Load(path, HCSiteFormat.STATE_BYTES, loaded) && HCSiteFormat.StateValid(loaded);
        }
        if (good)
        {
            m_State = loaded;
            m_StateRecovered = tmpBefore || bakOnly;
            return;
        }
        Quarantine();
    }

    protected bool ArchiveFile(string file, string tag, string stamp)
    {
        if (!FileExist(file)) { return true; }
        return HCPersistenceDisposition.HCArchive(file, ".corrupt-" + stamp + "-" + tag, HCGroupIO.HC_RAW_READ_CAP, true);
    }

    protected void Quarantine()
    {
        m_Quarantined = true;
        string path = HCSiteFormat.STATE_PATH;
        string stamp = HCGroupClock.Utc().ToString();
        bool archived = ArchiveFile(path, "p", stamp);
        if (archived) { archived = ArchiveFile(path + ".tmp", "t", stamp); }
        if (archived) { archived = ArchiveFile(path + ".bak", "b", stamp); }
        FreshState();
        m_StateFresh = true;
        if (!archived)
        {
            // Never overwrite what could not be copied: decisions stay in memory for this session.
            m_PersistOff = true;
            return;
        }
        if (FileExist(path)) { DeleteFile(path); }
        if (FileExist(path + ".tmp")) { DeleteFile(path + ".tmp"); }
        if (FileExist(path + ".bak")) { DeleteFile(path + ".bak"); }
        HCStagedSaveImage.HCForget(path);
    }

    protected void CopyBoxes(array<ref array<float>> source, array<ref array<float>> into, int cap)
    {
        foreach (array<float> row : source)
        {
            if (into.Count() >= cap) { break; }
            array<float> copy = new array<float>;
            for (int index = 0; index < row.Count(); index++) { copy.Insert(row[index]); }
            into.Insert(copy);
        }
    }

    // Starts a sweep of the boxes of a layer set that is no longer installed. An unfinished earlier sweep keeps
    // its remaining boxes (state cap 400 boxes).
    protected void StartSweepFrom(string from, array<ref array<float>> oldBoxes)
    {
        HCSiteSweep previous = m_State.Sweep;
        ref array<ref array<float>> merged = new array<ref array<float>>;
        if (previous && !previous.Done && previous.From != "legacy")
        {
            array<ref array<float>> carried = previous.Boxes;
            for (int index = previous.Cursor; index < carried.Count(); index++) { merged.Insert(carried[index]); }
            array<int> missed = previous.Skipped;
            foreach (int skipped : missed)
            {
                if (skipped < previous.Cursor && skipped < carried.Count()) { merged.Insert(carried[skipped]); }
            }
        }
        CopyBoxes(oldBoxes, merged, HCSiteFormat.MAX_STATE_BOXES);
        HCSiteSweep sweep = new HCSiteSweep;
        sweep.From = from;
        sweep.Boxes = merged;
        sweep.Total = merged.Count();
        sweep.Done = sweep.Total == 0;
        m_State.Sweep = sweep;
    }

    protected void PrepareComposed()
    {
        HCSiteManifest manifest = m_Manifest;
        if (m_StateFresh)
        {
            m_State.LayerSet = manifest.LayerSet;
            m_State.Boots = 1;
            // No earlier state: the previous (pre-guard) composed rows are the manifest's retired boxes.
            m_State.Sweep = new HCSiteSweep;
            m_State.Sweep.From = "legacy";
            m_State.Sweep.Total = manifest.Retired.Count();
            m_State.Sweep.Done = m_State.Sweep.Total == 0;
        }
        else
        {
            m_State.Boots++;
            if (m_State.LayerSet != manifest.LayerSet)
            {
                string oldSet = m_State.LayerSet;
                Log("layer_set changed from=" + HCSiteGeo.Short(oldSet) + " to=" + HCSiteGeo.Short(manifest.LayerSet));
                m_State.PrevLayerSet = oldSet;
                if (oldSet != "") { StartSweepFrom(oldSet, m_State.LootBoxes); }
                m_State.Decisions.Clear();
                m_State.LayerSet = manifest.LayerSet;
            }
            HCSiteSweep sweep = m_State.Sweep;
            if (sweep.From == "legacy")
            {
                sweep.Total = manifest.Retired.Count();
                if (sweep.Cursor > sweep.Total) { sweep.Cursor = sweep.Total; }
            }
            if (sweep.Total == 0) { sweep.Done = true; }
        }
        // Decisions in manifest order, only for manifest sites.
        ref array<ref HCSiteDecision> ordered = new array<ref HCSiteDecision>;
        array<ref HCSiteManifestSite> sites = manifest.Sites;
        foreach (HCSiteManifestSite site : sites)
        {
            HCSiteDecision decision = FindDecision(site.Id);
            if (!decision)
            {
                decision = new HCSiteDecision;
                decision.Site = site.Id;
            }
            if (decision.State == 2 && decision.Reason == "occupied" && decision.Attempts < m_Config.OccupiedRetryBoots) { decision.State = 0; }
            ordered.Insert(decision);
        }
        m_State.Decisions = ordered;
        m_State.LootBoxes.Clear();
        foreach (HCSiteManifestSite lootSite : sites) { CopyBoxes(lootSite.Loot, m_State.LootBoxes, HCSiteFormat.MAX_STATE_BOXES); }
    }

    protected void PrepareSweepOnly()
    {
        if (m_State.LayerSet == "") { return; }
        string oldSet = m_State.LayerSet;
        Log("mode=sweep_only from=" + HCSiteGeo.Short(oldSet));
        m_State.PrevLayerSet = oldSet;
        StartSweepFrom(oldSet, m_State.LootBoxes);
        m_State.Decisions.Clear();
        m_State.LootBoxes.Clear();
        m_State.LayerSet = "";
    }

    protected HCSiteDecision FindDecision(string siteId)
    {
        array<ref HCSiteDecision> list = m_State.Decisions;
        foreach (HCSiteDecision decision : list)
        {
            if (decision.Site == siteId) { return decision; }
        }
        return null;
    }

    protected HCSiteManifestSite FindSite(string siteId)
    {
        array<ref HCSiteManifestSite> sites = m_Manifest.Sites;
        foreach (HCSiteManifestSite site : sites)
        {
            if (site.Id == siteId) { return site; }
        }
        return null;
    }

    // ---- CE loot grid (HCGroundCELoot asks HCLootVerdict) ----------------------------------------------

    protected void GridInsert(string siteId, array<float> row)
    {
        HCSiteBox box = new HCSiteBox;
        box.Site = siteId;
        box.X = row[0];
        box.Z = row[1];
        box.HX = row[2];
        box.HZ = row[3];
        box.Yaw = row[4];
        float reach = Math.Sqrt(box.HX * box.HX + box.HZ * box.HZ);
        int minX = Math.Floor((box.X - reach) / 100);
        int maxX = Math.Floor((box.X + reach) / 100);
        int minZ = Math.Floor((box.Z - reach) / 100);
        int maxZ = Math.Floor((box.Z + reach) / 100);
        for (int cellX = minX; cellX <= maxX; cellX++)
        {
            for (int cellZ = minZ; cellZ <= maxZ; cellZ++)
            {
                int key = (cellX + 1) * 1024 + (cellZ + 1);
                array<ref HCSiteBox> cell;
                if (!m_Grid.Find(key, cell))
                {
                    cell = new array<ref HCSiteBox>;
                    m_Grid.Set(key, cell);
                }
                cell.Insert(box);
            }
        }
    }

    protected void BuildGrid()
    {
        m_Grid.Clear();
        m_SiteStatus.Clear();
        m_GridOn = false;
        if (!m_Composed) { return; }
        array<ref HCSiteManifestSite> sites = m_Manifest.Sites;
        foreach (HCSiteManifestSite site : sites)
        {
            int status = 0;
            HCSiteDecision decision = FindDecision(site.Id);
            if (decision && decision.State == 1) { status = 1; }
            if (decision && decision.State == 2) { status = 2; }
            m_SiteStatus.Set(site.Id, status);
            array<ref array<float>> loot = site.Loot;
            foreach (array<float> box : loot) { GridInsert(site.Id, box); }
        }
        array<ref array<float>> retired = m_Manifest.Retired;
        foreach (array<float> old : retired) { GridInsert("", old); }
        m_GridOn = true;
    }

    // KEEP: normal correction. HOLD: an undecided site's box, re-examined later. DROP: a refused site's box or a
    // retired-only box (fresh CE loot only; the caller never passes a player item).
    static int HCLootVerdict(ItemBase item)
    {
        if (!s_Instance || !item) { return HCSiteGuard.LOOT_KEEP; }
        return s_Instance.Verdict(item);
    }

    protected int Verdict(ItemBase item)
    {
        if (!m_Active || !m_GridOn) { return HCSiteGuard.LOOT_KEEP; }
        vector pos = item.GetPosition();
        int key = (Math.Floor(pos[0] / 100) + 1) * 1024 + (Math.Floor(pos[2] / 100) + 1);
        array<ref HCSiteBox> cell;
        if (!m_Grid.Find(key, cell)) { return HCSiteGuard.LOOT_KEEP; }
        bool keep = false;
        bool hold = false;
        bool drop = false;
        bool retiredOnly = false;
        for (int index = 0; index < cell.Count(); index++)
        {
            HCSiteBox box = cell[index];
            if (!HCSiteGeo.InBox(pos[0], pos[2], box.X, box.Z, box.HX, box.HZ, box.Yaw, 0)) { continue; }
            if (box.Site == "") { retiredOnly = true; continue; }
            int status = StatusOf(box.Site);
            if (status == 1) { keep = true; }
            else if (status == 0) { hold = true; }
            else if (status == 2) { drop = true; }
        }
        if (keep) { return HCSiteGuard.LOOT_KEEP; }
        if (hold) { return HCSiteGuard.LOOT_HOLD; }
        if (drop) { return HCSiteGuard.LOOT_DROP; }
        if (retiredOnly)
        {
            m_RetiredDropped++;
            if (m_RetiredSample.Count() < 8 && m_RetiredSample.Find(item.GetType()) < 0) { m_RetiredSample.Insert(item.GetType()); }
            return HCSiteGuard.LOOT_DROP;
        }
        return HCSiteGuard.LOOT_KEEP;
    }

    // ---- save ------------------------------------------------------------------------------------------

    protected void Touch(bool urgent)
    {
        m_Revision++;
        if (m_PersistOff || !m_Job) { return; }
        m_Job.HCDirty = true;
        if (urgent || !HCPerfConfig.HCGet().EnableSharedSaves || !HCSaveScheduler.HCRegistered(m_Job)) { m_Job.HCUrgent = true; }
    }

    bool HCRevisionPending()
    {
        return m_Active && !m_PersistOff && m_Revision > m_Durable;
    }

    int HCStepSave()
    {
        if (!m_State || m_PersistOff) { return HCSaveJob.STEP_DONE; }
        int result = m_Writer.SaveStep(HCSiteFormat.STATE_PATH, m_State, HCSiteFormat.STATE_BYTES, m_Revision);
        if (result == HCSaveJob.STEP_DONE) { m_Durable = m_Writer.HCSnapshotRevision(); }
        return result;
    }

    // A failed job is dropped by the scheduler: a retry needs a new writer and job, at most once per 30 s, and
    // three failures publish degraded (decisions stay in memory; the next boot re-decides, nothing is lost).
    protected void WatchSave(float now)
    {
        if (!m_Job || m_PersistOff) { return; }
        if (!m_Job.HCFaulted) { return; }
        if (now < m_SaveRetryAt) { return; }
        m_SaveFailures++;
        Log("save failed attempts=" + m_SaveFailures.ToString());
        m_SaveRetryAt = now + 30;
        HCSaveScheduler.HCUnregister(m_Job);
        if (m_SaveFailures >= 3)
        {
            m_Operational.HCPublish("degraded", "save_failed");
            m_Job = null;
            return;
        }
        HCV2ThreatStore<HCSiteState>.HCRecoverInterrupted(HCSiteFormat.STATE_PATH);
        m_Writer = new HCV2ThreatStore<HCSiteState>;
        m_Job = new HCSiteSaveJob;
        m_Job.Owner = this;
        HCSaveScheduler.HCRegister(m_Job);
        m_Job.HCDirty = true;
        m_Job.HCUrgent = true;
    }

    // ---- gate and pump ---------------------------------------------------------------------------------

    protected bool PlayerWithin(float x, float z, float range)
    {
        array<Man> players = HCPerfPlayers.HCGet();
        foreach (Man player : players)
        {
            if (!player || !player.IsAlive()) { continue; }
            vector at = player.GetPosition();
            if (HCSiteGeo.Dist2D(at[0], at[2], x, z) <= range) { return true; }
        }
        return false;
    }

    // C2: no event reports "storage load finished", so the pass starts once the mission is old enough AND no
    // watched object restored from storage for the quiet window; at five times the delay it starts regardless.
    protected string GateReason(float now)
    {
        float age = now - m_StartTime;
        if (age < m_Config.DecideDelaySeconds) { return ""; }
        if (now - HCSiteBaseRegistry.LastLoad() >= m_Config.QuietWindowSeconds) { return "quiet"; }
        if (age >= m_Config.DecideDelaySeconds * 5) { return "forced"; }
        return "";
    }

    override void OnTick(float deltaTime)
    {
        if (!m_Active) { return; }
        float now = GetGame().GetTickTime();
        if (now < m_NextPump) { return; }
        m_NextPump = now + 0.1;
        int startTicks = TickCount(0);
        if (m_Job) { HCSaveScheduler.HCPumpFallback(m_Job); }
        WatchSave(now);
        LogRetired(now);
        DrainCountQueue();
        m_Budget.HCReset(m_Config.UnitsPerGrant, HCPerfConfig.HCGet().SliceMs);
        if (m_Phase == HCSiteGuard.PH_WAIT) { PumpWait(now); }
        if (m_Phase == HCSiteGuard.PH_DECIDE) { PumpDecide(now); }
        else if (m_Phase >= HCSiteGuard.PH_GROUND && (m_CurSite != "" || m_Waiting.Count() > 0)) { PumpDecide(now); }
        if (m_Phase == HCSiteGuard.PH_GROUND) { PumpGround(); }
        if (m_Phase == HCSiteGuard.PH_SWEEP) { PumpSweep(now); }
        float perTick = HCWorkBudget.HCTicksPerMs();
        if (perTick > 0)
        {
            int usedTicks = TickCount(startTicks);
            int usedMs = Math.Ceil(usedTicks / perTick);
            if (usedMs > m_MsMax) { m_MsMax = usedMs; }
        }
    }

    protected void PumpWait(float now)
    {
        string gate = GateReason(now);
        if (gate == "") { return; }
        if (!m_Composed)
        {
            m_Phase = HCSiteGuard.PH_SWEEP;
            return;
        }
        StartPass(now, gate);
        m_Phase = HCSiteGuard.PH_DECIDE;
    }

    protected void DrainCountQueue()
    {
        int drained = 0;
        while (m_CountQueue.Count() > 0 && drained < 8)
        {
            string siteId = m_CountQueue[0];
            m_CountQueue.RemoveOrdered(0);
            drained++;
            HCSiteManifestSite site = FindSite(siteId);
            if (!site) { continue; }
            m_PassAdmitted++;
            Log("spawned site=" + siteId + " parts=" + site.Parts.ToString());
            HCModuleReadiness.HCUse("Sites", "composed_sites");
        }
    }

    protected void LogRetired(float now)
    {
        if (m_RetiredDropped <= m_RetiredLogged || now < m_RetiredLogAt) { return; }
        m_RetiredLogAt = now + 300;
        m_RetiredLogged = m_RetiredDropped;
        string sample = "";
        foreach (string typeName : m_RetiredSample)
        {
            if (sample != "") { sample += ","; }
            sample += typeName;
        }
        Log("retired_rows_active count=" + m_RetiredDropped.ToString() + " sample=" + sample);
    }

    protected void StartPass(float now, string gate)
    {
        int ageSeconds = Math.Floor(now - m_StartTime);
        m_ClaimPos.Clear();
        m_CampPos.Clear();
        HCCampModule.HCSiteEvidence(m_ClaimPos, m_CampPos);
        Log("decide_start mission_age_s=" + ageSeconds.ToString() + " gate=" + gate + " store_loads=" + HCSiteBaseRegistry.Loads().ToString() + " bases=" + HCSiteBaseRegistry.BaseCount().ToString() + " claims=" + m_ClaimPos.Count().ToString() + " camps=" + m_CampPos.Count().ToString() + " storage=" + HCBasesContainers.HCCount().ToString());
        m_Pending.Clear();
        array<ref HCSiteManifestSite> sites = m_Manifest.Sites;
        foreach (HCSiteManifestSite site : sites)
        {
            HCSiteDecision decision = FindDecision(site.Id);
            if (!decision) { continue; }
            bool invalid = ObjectSpawnerHandler.HCSiteInvalid.Contains(site.Id);
            bool hasRows = ObjectSpawnerHandler.HCSiteDeferred.Contains(site.Id);
            if (decision.State == 2)
            {
                FreeRows(site.Id);
                continue;
            }
            if (decision.State == 1 && !invalid && !hasRows)
            {
                string failedClass;
                if (ObjectSpawnerHandler.HCSiteCreateFailed.Find(site.Id, failedClass))
                {
                    m_SiteStatus.Set(site.Id, 2);
                    if (m_GFail == "") { m_GFail = "class_refused " + failedClass; }
                    continue;
                }
                m_CountQueue.Insert(site.Id);
                continue;
            }
            m_Pending.Insert(site.Id);
        }
    }

    protected void FreeRows(string siteId)
    {
        ObjectSpawnerHandler.HCSiteDeferred.Remove(siteId);
        ObjectSpawnerHandler.HCSiteDeferredGround.Remove(siteId);
    }

    protected void EndPass()
    {
        m_PassDone = true;
        Log("pass_done admitted=" + m_PassAdmitted.ToString() + " refused=" + m_PassRefused.ToString() + " pending=" + m_Waiting.Count().ToString() + " ms_max=" + m_MsMax.ToString());
        m_Phase = HCSiteGuard.PH_GROUND;
    }

    protected void PumpDecide(float now)
    {
        while (m_Budget.HCContinue())
        {
            int result = StepDecide(now);
            if (result == 1) { return; }
            if (result == 2)
            {
                if (m_Phase == HCSiteGuard.PH_DECIDE) { EndPass(); }
                return;
            }
        }
        m_Budget.HCDeferred("Sites", m_Pending.Count());
    }

    // ---- per-site decision -----------------------------------------------------------------------------

    protected void RequeueWaiting(float now)
    {
        int index = 0;
        while (index < m_Waiting.Count())
        {
            if (m_WaitDue[index] <= now)
            {
                m_Pending.Insert(m_Waiting[index]);
                m_Waiting.RemoveOrdered(index);
                m_WaitDue.RemoveOrdered(index);
            }
            else { index++; }
        }
    }

    // 0 progress, 1 nothing to do right now, 2 queue empty.
    protected int StepDecide(float now)
    {
        if (m_CurSite == "")
        {
            if (m_Pending.Count() == 0) { RequeueWaiting(now); }
            if (m_Pending.Count() == 0) { return 2; }
            m_CurSite = m_Pending[0];
            m_Pending.RemoveOrdered(0);
            BeginSite();
        }
        HCSiteManifestSite site = FindSite(m_CurSite);
        HCSiteDecision decision = FindDecision(m_CurSite);
        if (!site || !decision)
        {
            m_CurSite = "";
            return 0;
        }
        if (m_CurStep == HCSiteGuard.ST_EVAL) { return StepEval(now, site, decision); }
        if (m_CurStep == HCSiteGuard.ST_HARD) { return StepHard(now, site, decision); }
        if (m_CurStep == HCSiteGuard.ST_CLASS) { return StepClass(site, decision); }
        return StepSpawn(site, decision);
    }

    protected void BeginSite()
    {
        m_CurStep = HCSiteGuard.ST_EVAL;
        m_CurPiece = 0;
        m_CurRow = 0;
        m_CurSpawned.Clear();
        HCSiteDecision decision = FindDecision(m_CurSite);
        if (!decision)
        {
            Log("decide site=" + m_CurSite + " decision_missing");
            return;
        }
        bool invalid = ObjectSpawnerHandler.HCSiteInvalid.Contains(m_CurSite);
        // An admitted site that only needs its deferred rows spawned (state-unknown recovery) skips the checks.
        if (decision.State == 1 && !invalid) { m_CurStep = HCSiteGuard.ST_CLASS; }
        if (!m_Logged.Contains(m_CurSite))
        {
            m_Logged.Set(m_CurSite, true);
            Log("decide site=" + m_CurSite + " prev=" + decision.State.ToString() + " attempts=" + decision.Attempts.ToString());
        }
    }

    protected int Refuse(HCSiteManifestSite site, HCSiteDecision decision, string reason)
    {
        foreach (Object piece : m_CurSpawned)
        {
            if (piece) { GetGame().ObjectDelete(piece); }
        }
        m_CurSpawned.Clear();
        decision.State = 2;
        decision.Reason = reason;
        Touch(true);
        m_SiteStatus.Set(site.Id, 2);
        m_PassRefused++;
        Log("refused site=" + site.Id + " reason=" + reason);
        HCModuleReadiness.HCUse("Sites", "site_refusals");
        FreeRows(site.Id);
        m_CurSite = "";
        return 0;
    }

    protected int Postpone(HCSiteManifestSite site, string reason, float delay, float now)
    {
        m_Waiting.Insert(site.Id);
        m_WaitDue.Insert(now + delay);
        string key = site.Id + ":" + reason;
        if (!m_Logged.Contains(key))
        {
            m_Logged.Set(key, true);
            Log("postponed site=" + site.Id + " reason=" + reason);
        }
        m_CurSite = "";
        return 0;
    }

    protected int StepEval(float now, HCSiteManifestSite site, HCSiteDecision decision)
    {
        string invalidReason;
        if (ObjectSpawnerHandler.HCSiteInvalid.Find(site.Id, invalidReason)) { return Refuse(site, decision, invalidReason); }
        if (PlayerWithin(site.Centre[0], site.Centre[2], site.Radius + 5)) { return Postpone(site, "player_near", 30, now); }
        string reason = RegistryReason(site, now);
        if (reason != "") { return Refuse(site, decision, reason); }
        if (m_FortIgnored > 0) { Log("fort_ignored site=" + site.Id + " count=" + m_FortIgnored.ToString()); }
        CollectVehicles(site);
        m_CurStep = HCSiteGuard.ST_HARD;
        m_CurPiece = 0;
        return 0;
    }

    // Registry evidence only (no world scan): claims, camps, storage, stashes and base pieces. Weak pieces (fence,
    // watchtower: the AI fortification kit places them) inside the fortification ring of the site and away from
    // every strong piece are ignored.
    protected string RegistryReason(HCSiteManifestSite site, float now)
    {
        float cx = site.Centre[0];
        float cz = site.Centre[2];
        float radius = site.Radius;
        float margin = m_Config.BaseMarginM;
        float reach = radius + margin;
        float outer = radius + site.FortRing + margin;
        m_FortIgnored = 0;
        m_EvPos.Clear();
        m_WeakPos.Clear();
        for (int step = 0; step < 9; step++)
        {
            float px = cx;
            float pz = cz;
            if (step > 0)
            {
                float angle = (step - 1) * 45 * Math.DEG2RAD;
                px = cx + Math.Cos(angle) * radius * 0.8;
                pz = cz + Math.Sin(angle) * radius * 0.8;
            }
            if (HCBuildingClaim.HCClaimCoversAt(Vector(px, GetGame().SurfaceY(px, pz), pz))) { return "claim"; }
        }
        foreach (vector claimAt : m_ClaimPos)
        {
            float claimDist = HCSiteGeo.Dist2D(claimAt[0], claimAt[2], cx, cz);
            if (claimDist <= reach) { return "claim"; }
            if (claimDist <= outer) { m_EvPos.Insert(claimAt); }
        }
        foreach (vector campAt : m_CampPos)
        {
            float campDist = HCSiteGeo.Dist2D(campAt[0], campAt[2], cx, cz);
            if (campDist <= reach) { return "camp"; }
            if (campDist <= outer) { m_EvPos.Insert(campAt); }
        }
        int storageCount = HCBasesContainers.HCCount();
        for (int storageIndex = 0; storageIndex < storageCount; storageIndex++)
        {
            ItemBase container = HCBasesContainers.HCAt(storageIndex);
            if (!container || container.GetHierarchyParent()) { continue; }
            vector storageAt = container.GetPosition();
            float storageDist = HCSiteGeo.Dist2D(storageAt[0], storageAt[2], cx, cz);
            if (storageDist <= reach) { return "storage"; }
            if (storageDist <= outer) { m_EvPos.Insert(storageAt); }
        }
        int stashCount = HCSiteBaseRegistry.StashCount();
        for (int stashIndex = 0; stashIndex < stashCount; stashIndex++)
        {
            UndergroundStash stash = HCSiteBaseRegistry.StashAt(stashIndex);
            if (!stash) { continue; }
            vector stashAt = stash.GetPosition();
            float stashDist = HCSiteGeo.Dist2D(stashAt[0], stashAt[2], cx, cz);
            if (stashDist <= reach) { return "storage"; }
            if (stashDist <= outer) { m_EvPos.Insert(stashAt); }
        }
        int baseCount = HCSiteBaseRegistry.BaseCount();
        for (int baseIndex = 0; baseIndex < baseCount; baseIndex++)
        {
            BaseBuildingBase piece = HCSiteBaseRegistry.BaseAt(baseIndex);
            if (!piece) { continue; }
            vector pieceAt = piece.GetPosition();
            float pieceDist = HCSiteGeo.Dist2D(pieceAt[0], pieceAt[2], cx, cz);
            if (pieceDist > outer) { continue; }
            if (Fence.Cast(piece) || Watchtower.Cast(piece))
            {
                if (m_WeakPos.Count() < 512) { m_WeakPos.Insert(pieceAt); }
                continue;
            }
            if (pieceDist <= reach) { return "player_base"; }
            m_EvPos.Insert(pieceAt);
        }
        foreach (vector weakAt : m_WeakPos)
        {
            float weakDist = HCSiteGeo.Dist2D(weakAt[0], weakAt[2], cx, cz);
            if (weakDist <= radius + site.FortRing && !StrongNear(weakAt, margin))
            {
                m_FortIgnored++;
                continue;
            }
            if (weakDist <= reach) { return "player_base"; }
        }
        return "";
    }

    protected bool StrongNear(vector at, float range)
    {
        foreach (vector evidence : m_EvPos)
        {
            if (HCSiteGeo.Dist2D(evidence[0], evidence[2], at[0], at[2]) <= range) { return true; }
        }
        return false;
    }

    protected void CollectVehicles(HCSiteManifestSite site)
    {
        m_NearVeh.Clear();
        array<Transport> cars = HCAdminVehicleRegistry.Vehicles;
        foreach (Transport car : cars)
        {
            if (!car || m_NearVeh.Count() >= 16) { continue; }
            vector at = car.GetPosition();
            if (HCSiteGeo.Dist2D(at[0], at[2], site.Centre[0], site.Centre[2]) <= site.Radius + 30) { m_NearVeh.Insert(at); }
        }
    }

    protected int ReasonRank(string reason)
    {
        if (reason == "player_base") { return 0; }
        if (reason == "storage") { return 1; }
        if (reason == "occupied") { return 2; }
        if (reason == "vehicle") { return 3; }
        return 4;
    }

    protected string HitReason(Object hit)
    {
        if (!hit) { return ""; }
        if (hit.IsMan()) { return "occupied"; }
        BaseBuildingBase piece = BaseBuildingBase.Cast(hit);
        if (piece)
        {
            if (Fence.Cast(hit) || Watchtower.Cast(hit)) { return ""; }
            return "player_base";
        }
        if (UndergroundStash.Cast(hit) || TentBase.Cast(hit) || WoodenCrate.Cast(hit) || SeaChest.Cast(hit) || Barrel_ColorBase.Cast(hit)) { return "storage"; }
        if (hit.IsTransport()) { return "vehicle"; }
        ItemBase item = ItemBase.Cast(hit);
        if (item && !item.GetHierarchyParent()) { return "occupied_item"; }
        return "";
    }

    // One hard piece: [x, surveyY, z, halfX, halfY, halfZ, yawDeg, cornerSpread]. The query box is the piece
    // shrunk by 0.2 m, raised 0.3 m so terrain and the site's own surface never count.
    protected string HardReason(array<float> row)
    {
        float surveyY = row[1];
        if (surveyY <= 0) { return "survey_missing"; }
        float ground = GetGame().SurfaceY(row[0], row[2]);
        if (Math.AbsFloat(surveyY - ground) > 3) { return "survey_missing"; }
        vector centre = Vector(row[0], surveyY + row[4] + 0.3, row[2]);
        vector edges = Vector(2 * Math.Max(row[3] - 0.2, 0.1), 2 * Math.Max(row[4] - 0.2, 0.1), 2 * Math.Max(row[5] - 0.2, 0.1));
        vector orient = Vector(row[6], 0, 0);
        m_Hits.Clear();
        GetGame().IsBoxColliding(centre, orient, edges, m_Excl, m_Hits);
        string reason = "";
        int limit = Math.Min(m_Hits.Count(), 64);
        for (int hitIndex = 0; hitIndex < limit; hitIndex++)
        {
            string found = HitReason(m_Hits[hitIndex]);
            if (found == "") { continue; }
            if (reason == "" || ReasonRank(found) < ReasonRank(reason)) { reason = found; }
        }
        if (reason != "") { return reason; }
        foreach (vector carAt : m_NearVeh)
        {
            if (HCSiteGeo.InBox(carAt[0], carAt[2], row[0], row[2], row[3], row[5], row[6], 1)) { return "vehicle"; }
        }
        return "";
    }

    protected int StepHard(float now, HCSiteManifestSite site, HCSiteDecision decision)
    {
        array<ref array<float>> hard = site.Hard;
        int allowance = 8;
        while (allowance > 0 && m_CurPiece < hard.Count())
        {
            allowance--;
            array<float> row = hard[m_CurPiece];
            m_CurPiece++;
            string verdict = HardReason(row);
            if (verdict == "") { continue; }
            if (verdict == "survey_missing" || verdict == "player_base" || verdict == "storage") { return Refuse(site, decision, verdict); }
            return Occupied(site, decision, verdict, now);
        }
        if (m_CurPiece >= hard.Count())
        {
            m_CurStep = HCSiteGuard.ST_CLASS;
            m_CurPiece = 0;
            m_CurRow = 0;
        }
        return 0;
    }

    // Occupied, occupied_item and vehicle: the attempt counts once per boot, the site retries in session every
    // 60 s (three times), and the refusal turns sticky once the attempts reach OccupiedRetryBoots.
    protected int Occupied(HCSiteManifestSite site, HCSiteDecision decision, string reason, float now)
    {
        if (!m_Attempted.Contains(site.Id))
        {
            m_Attempted.Set(site.Id, true);
            decision.Attempts++;
            Touch(false);
        }
        if (decision.Attempts >= m_Config.OccupiedRetryBoots) { return Refuse(site, decision, "occupied"); }
        int tries = 0;
        m_Retries.Find(site.Id, tries);
        if (tries >= 3)
        {
            // Left undecided for this boot (the next boot counts another attempt); its loot box is dropped
            // meanwhile so nothing queues up for a site that is not standing.
            m_SiteStatus.Set(site.Id, 2);
            Log("postponed site=" + site.Id + " reason=" + reason + " parked=1");
            m_CurSite = "";
            return 0;
        }
        m_Retries.Set(site.Id, tries + 1);
        return Postpone(site, reason, 60, now);
    }

    protected int StepClass(HCSiteManifestSite site, HCSiteDecision decision)
    {
        array<ref ITEM_SpawnerObject> rows;
        if (!ObjectSpawnerHandler.HCSiteDeferred.Find(site.Id, rows)) { return Refuse(site, decision, "manifest_mismatch"); }
        int allowance = 8;
        while (allowance > 0 && m_CurRow < rows.Count())
        {
            allowance--;
            ITEM_SpawnerObject row = rows[m_CurRow];
            m_CurRow++;
            if (row.name.Contains("/") || row.name.Contains("\\")) { continue; }
            if (!GetGame().ConfigIsExisting("CfgVehicles " + row.name))
            {
                Log("class_refused site=" + site.Id + " class=" + row.name);
                return Refuse(site, decision, "class_refused");
            }
        }
        if (m_CurRow >= rows.Count())
        {
            m_CurStep = HCSiteGuard.ST_SPAWN;
            m_CurRow = 0;
        }
        return 0;
    }

    protected int StepSpawn(HCSiteManifestSite site, HCSiteDecision decision)
    {
        array<ref ITEM_SpawnerObject> rows;
        array<ref HCGroundRowJson> grounds;
        if (!ObjectSpawnerHandler.HCSiteDeferred.Find(site.Id, rows) || !ObjectSpawnerHandler.HCSiteDeferredGround.Find(site.Id, grounds)) { return Refuse(site, decision, "manifest_mismatch"); }
        if (m_CurRow < rows.Count())
        {
            ITEM_SpawnerObject row = rows[m_CurRow];
            if (PlayerWithin(row.pos[0], row.pos[2], 6)) { return 1; }
            HCGroundRowJson ground = null;
            if (m_CurRow < grounds.Count()) { ground = grounds[m_CurRow]; }
            Object placed = ObjectSpawnerHandler.HCSpawnDeferred(row, ground);
            if (ObjectSpawnerHandler.HCLastResult == 1)
            {
                Log("class_refused site=" + site.Id + " class=" + row.name);
                return Refuse(site, decision, "class_refused");
            }
            if (placed && m_CurSpawned.Count() < HCSiteFormat.MAX_PARTS) { m_CurSpawned.Insert(placed); }
            m_CurRow++;
            return 0;
        }
        GetGame().GetWorld().ProcessMarkedObjectsForPathgraphUpdate();
        // Admission is persisted only after the whole site stands: a crash earlier leaves it undecided.
        decision.State = 1;
        decision.Reason = "";
        Touch(true);
        m_SiteStatus.Set(site.Id, 1);
        m_PassAdmitted++;
        m_AdmittedNow.Insert(site.Id);
        Log("spawned site=" + site.Id + " parts=" + site.Parts.ToString());
        HCModuleReadiness.HCUse("Sites", "composed_sites");
        FreeRows(site.Id);
        m_CurSpawned.Clear();
        m_CurSite = "";
        return 0;
    }

    // ---- self-tests -------------------------------------------------------------------------------------

    protected void PumpGround()
    {
        while (m_Budget.HCContinue())
        {
            if (!m_GroundDone)
            {
                StepGround();
                continue;
            }
            if (StepClear()) { m_Phase = HCSiteGuard.PH_SWEEP; return; }
        }
    }

    protected void StepGround()
    {
        array<ref HCSiteManifestSite> sites = m_Manifest.Sites;
        if (m_GSite >= sites.Count())
        {
            m_GroundDone = true;
            string detail = m_GStale.ToString() + "/" + m_GChecked.ToString() + " max_dy=" + (Math.Round(m_GMaxDy * 100) / 100).ToString();
            if (m_GFail != "") { detail = detail + " fail=" + m_GFail; }
            HCCoreSelfTest.Receipt("sites_ground", m_GStale == 0 && m_GFail == "", detail);
            return;
        }
        HCSiteManifestSite site = sites[m_GSite];
        HCSiteDecision decision = FindDecision(site.Id);
        if (!decision || decision.State != 1)
        {
            if (decision && decision.State == 2 && m_GFail == "" && (decision.Reason == "survey_missing" || decision.Reason == "class_refused")) { m_GFail = decision.Reason; }
            m_GSite++;
            m_GPiece = 0;
            return;
        }
        array<ref array<float>> hard = site.Hard;
        int allowance = 8;
        while (allowance > 0 && m_GPiece < hard.Count())
        {
            allowance--;
            array<float> row = hard[m_GPiece];
            m_GPiece++;
            float delta = Math.AbsFloat(GetGame().SurfaceY(row[0], row[2]) - row[1]);
            m_GChecked++;
            if (delta > m_GMaxDy) { m_GMaxDy = delta; }
            if (delta > row[7] + 0.25) { m_GStale++; }
        }
        if (m_GPiece >= hard.Count())
        {
            m_GSite++;
            m_GPiece = 0;
        }
    }

    // True when the overlap re-check and its receipt are done.
    protected bool StepClear()
    {
        if (m_OSite < m_AdmittedNow.Count())
        {
            HCSiteManifestSite site = FindSite(m_AdmittedNow[m_OSite]);
            m_OSite++;
            if (site)
            {
                string overlap = RegistryReason(site, GetGame().GetTickTime());
                if (overlap != "")
                {
                    m_Overlaps++;
                    Log("overlap site=" + site.Id + " reason=" + overlap);
                }
            }
            return false;
        }
        int refused = 0;
        array<ref HCSiteDecision> decisions = m_State.Decisions;
        foreach (HCSiteDecision decision : decisions)
        {
            if (decision.State == 2) { refused++; }
        }
        string stateName = "ok";
        if (m_StateRecovered) { stateName = "recovered"; }
        if (m_Quarantined) { stateName = "quarantined"; }
        string detail = "refused=" + refused.ToString() + " overlaps=" + m_Overlaps.ToString() + " state=" + stateName;
        HCCoreSelfTest.Receipt("sites_clear", m_Overlaps == 0 && !m_Quarantined, detail);
        return true;
    }

    // ---- orphan sweep -----------------------------------------------------------------------------------

    protected void PumpSweep(float now)
    {
        while (m_Budget.HCContinue())
        {
            int result = StepSweep(now);
            if (result == 1) { return; }
            if (result == 2)
            {
                m_Phase = HCSiteGuard.PH_IDLE;
                return;
            }
        }
    }

    protected array<ref array<float>> SweepSource()
    {
        HCSiteSweep sweep = m_State.Sweep;
        if (sweep.From == "legacy")
        {
            if (m_Composed) { return m_Manifest.Retired; }
            return null;
        }
        return sweep.Boxes;
    }

    protected int FinishSweep(HCSiteSweep sweep)
    {
        sweep.Done = true;
        Log("sweep from=" + HCSiteGeo.Short(sweep.From) + " boxes=" + sweep.Total.ToString() + " snapped=" + sweep.Snapped.ToString() + " kept=" + sweep.Kept.ToString() + " skipped=0");
        Touch(true);
        return 2;
    }

    // One retired box per unit. Items are only ever settled onto the surface below (drop-only), never deleted.
    protected int StepSweep(float now)
    {
        HCSiteSweep sweep = m_State.Sweep;
        if (sweep.Done) { return 2; }
        array<ref array<float>> source = SweepSource();
        if (!source)
        {
            sweep.Total = 0;
            sweep.Cursor = 0;
            sweep.Skipped.Clear();
            return FinishSweep(sweep);
        }
        if (sweep.Total > source.Count()) { sweep.Total = source.Count(); }
        if (sweep.Cursor > sweep.Total) { sweep.Cursor = sweep.Total; }
        if (!m_SweepStarted)
        {
            m_SweepStarted = true;
            if (sweep.Cursor > 0 || sweep.Skipped.Count() > 0) { Log("sweep resume from=" + HCSiteGeo.Short(sweep.From) + " cursor=" + sweep.Cursor.ToString() + " boxes=" + sweep.Total.ToString()); }
        }
        int index = -1;
        bool revisit = false;
        if (sweep.Cursor < sweep.Total) { index = sweep.Cursor; }
        else if (sweep.Skipped.Count() > 0)
        {
            if (m_SkipTry >= 5)
            {
                if (m_SweepTruncated == 0)
                {
                    m_SweepTruncated = 1;
                    Log("sweep from=" + HCSiteGeo.Short(sweep.From) + " boxes=" + sweep.Total.ToString() + " snapped=" + sweep.Snapped.ToString() + " kept=" + sweep.Kept.ToString() + " skipped=" + sweep.Skipped.Count().ToString());
                }
                return 2;
            }
            if (now < m_SweepRetryAt) { return 1; }
            index = sweep.Skipped[0];
            revisit = true;
        }
        else { return FinishSweep(sweep); }
        if (index >= source.Count())
        {
            sweep.Skipped.RemoveOrdered(0);
            return 0;
        }
        array<float> row = source[index];
        if (PlayerWithin(row[0], row[1], m_Config.PlayerClearM))
        {
            m_SweepRetryAt = now + 120;
            if (revisit)
            {
                m_SkipTry++;
                return 1;
            }
            Log("sweep skip box=" + index.ToString() + " reason=player_near");
            sweep.Skipped.Insert(index);
            sweep.Cursor++;
            Touch(false);
            return 0;
        }
        SweepBox(row, sweep);
        if (revisit)
        {
            sweep.Skipped.RemoveOrdered(0);
            m_SkipTry = 0;
        }
        else { sweep.Cursor++; }
        m_BoxesSinceSave++;
        bool urgent = m_BoxesSinceSave >= 16;
        if (urgent) { m_BoxesSinceSave = 0; }
        Touch(urgent);
        HCModuleReadiness.HCUse("Sites", "orphan_sweep");
        return 0;
    }

    protected void SweepBox(array<float> row, HCSiteSweep sweep)
    {
        float halfDiag = Math.Sqrt(row[2] * row[2] + row[3] * row[3]);
        vector centre = Vector(row[0], GetGame().SurfaceY(row[0], row[1]) + 4, row[1]);
        m_ObjA.Clear();
        m_CargoA.Clear();
        GetGame().GetObjectsAtPosition3D(centre, halfDiag + 4, m_ObjA, m_CargoA);
        int count = Math.Min(m_ObjA.Count(), 256);
        for (int objIndex = 0; objIndex < count; objIndex++)
        {
            ItemBase item = ItemBase.Cast(m_ObjA[objIndex]);
            if (!item) { continue; }
            vector at = item.GetPosition();
            if (!HCSiteGeo.InBox(at[0], at[2], row[0], row[1], row[2], row[3], row[4], 0)) { continue; }
            if (item.GetHierarchyParent() || item.IsPendingDeletion() || !item.IsEmpty() || BaseBuildingBase.Cast(item) || TentBase.Cast(item) || UndergroundStash.Cast(item))
            {
                sweep.Kept++;
                continue;
            }
            if (HCGroundSnap.Settle(item, 25, 0.3)) { sweep.Snapped++; }
            else { sweep.Kept++; }
        }
        m_ObjA.Clear();
    }

    // ---- stop -------------------------------------------------------------------------------------------

    override void OnStop()
    {
        if (!m_Active) { return; }
        m_Active = false;
        int pending = m_Pending.Count() + m_Waiting.Count();
        if (m_CurSite != "") { pending++; }
        bool flushed = true;
        if (m_Job && !m_PersistOff)
        {
            if (m_Revision > m_Durable) { m_Job.HCDirty = true; }
            flushed = HCSaveScheduler.HCFlush(m_Job);
            HCSaveScheduler.HCUnregister(m_Job);
        }
        Log("stop pending=" + pending.ToString() + " flushed=" + flushed.ToString());
        m_Operational.HCPublish("off", "stopped");
        if (s_Instance == this) { s_Instance = null; }
    }
}

modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        Register(new HCSiteGuard());
    }
}
