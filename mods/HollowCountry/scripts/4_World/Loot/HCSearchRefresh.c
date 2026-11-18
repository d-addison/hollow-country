// Owner revisit request (2026-11-17), EnableWorld; related LC-NFR-02/03/04.
// Search-state recovery only: old supply rows NEVER return to phase zero. Revisit
// uses HCSearchHouses.Bind -> Provider.Collect -> RegisterOwned -> journal -> Transfer.
// No interior assignment/history changes. No entities or inventory are made here.
// Native evidence: ~/.cache/hollow-country/native-scripts/scripts-1.30.164289/
// 1_Core/proto/EnSystem.c:76,100 UTC (through existing HCGroupClock.Utc);
//   :397 FileExist, :417 OpenFile, :425 ReadFile, :443 CloseFile, :462 FPrint,
//   :525 MakeDirectory, :528 DeleteFile, :531 CopyFile (through HCSearchJson).
// 3_Game/tools/JsonFileLoader.c:69 LoadData, :85 MakeData;
// 1_Core/proto/EnString.c:199 Length, :240 IndexOf, :448 Get;
// 1_Core/proto/EnScript.c:380 Count, :385 Clear, :394 Find, :407 Insert, :463 Remove,
//   :877 map.Find, :902 map.Set, :917 map.Contains;
// 1_Core/proto/EnConvert.c:30 int.ToString, :210 vector.DistanceSq;
// 1_Core/proto/EnDebug.c:96 Print; 3_Game/Global/Game.c:1120 IsServer;
// 4_World/Classes/UserActionsComponent/ActionTargets.c:142 ActionTarget.GetObject.
// No RenameFile is exposed by this snapshot. Fixed temp -> backup -> copy/readback
// -> remove temp implements a fail-closed commit barrier, NOT filesystem rename or
// fsync. A leftover temp/corrupt primary never falls back to older cooldowns.
// CE baseline inspected read-only: stock chernarusplus/db/globals.xml has respawn
// limits and LootSpawnAvoidance=100; types.xml has nominal/min/restock/lifetime.
// CE owns actual replacement supply; no per-house refill promise is inferred.
// Provisional caps: 32 records/minute, 4096 timers, existing 4096 supply journal rows.
// Native compile, persistence, real CE replacement and two-client acceptance PENDING.

class HCSearchRefreshPolicy
{
    // Bounded polynomial hash of the stable site id, independent of process RNG,
    // clock, enumeration order, native hash sign and signed-int overflow.
    static int Interval(string siteId)
    {
        string alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-:+/=";
        int hash = 0;
        int index = 0;
        while (index < siteId.Length())
        {
            hash = (hash * 31 + alphabet.IndexOf(siteId.Get(index)) + 1) % 172801;
            index++;
        }
        return 172800 + hash;
    }

    static bool Due(int searchedUtc, int nowUtc, int interval)
    {
        if (searchedUtc < 1 || nowUtc < searchedUtc) return false;
        return nowUtc - searchedUtc >= interval;
    }
}

class HCSearchRefreshRow
{
    string Scope;
    string SiteId;
    int SearchedUtc;
    bool Ready;
    // Once a pilot container enters the refresh path, its new finite rows own
    // subsequent actions. Never rewind its original immutable manifest/journal.
    bool Revisited;
}

class HCSearchRefreshState
{
    int Version = 1;
    int LastUtc;
    ref array<ref HCSearchRefreshRow> Rows = new array<ref HCSearchRefreshRow>;
}

class HCSearchRefreshStore
{
    static const string PATH = "$profile:HollowCountry/search-refresh.json";
    static const int MAX_BYTES = 8388608;
    protected bool m_Fault;

    bool Healthy() { return !m_Fault; }

    bool Fault()
    {
        m_Fault = true;
        Print("[HollowCountry] V2 loot refresh inactive: preserve search-refresh.json, .tmp and .bak; recovery required");
        return false;
    }

    HCSearchRefreshState Open()
    {
        if (!FileExist("$profile:HollowCountry") && !MakeDirectory("$profile:HollowCountry"))
        {
            Fault();
            return null;
        }
        if (FileExist(PATH + ".tmp") || (!FileExist(PATH) && FileExist(PATH + ".bak")))
        {
            Fault();
            return null;
        }
        HCSearchRefreshState state;
        if (FileExist(PATH))
        {
            if (!HCSearchJson<HCSearchRefreshState>.Load(PATH, MAX_BYTES, state)) Fault();
            if (m_Fault) return null;
            return state;
        }
        state = new HCSearchRefreshState;
        state.LastUtc = HCGroupClock.Utc();
        if (state.LastUtc < 1 || !Save(state)) return null;
        return state;
    }

    bool Save(HCSearchRefreshState state)
    {
        if (m_Fault || !state) return false;
        // Poison before the first write: even partial temp writes remain evidence.
        m_Fault = true;
        if (!HCSearchJson<HCSearchRefreshState>.WriteNew(PATH + ".tmp", state, MAX_BYTES)) return Fault();
        if (FileExist(PATH))
        {
            if (FileExist(PATH + ".bak") && !DeleteFile(PATH + ".bak")) return Fault();
            if (!CopyFile(PATH, PATH + ".bak")) return Fault();
            if (!DeleteFile(PATH)) return Fault();
        }
        if (!CopyFile(PATH + ".tmp", PATH)) return Fault();
        HCSearchRefreshState check;
        if (!HCSearchJson<HCSearchRefreshState>.Load(PATH, MAX_BYTES, check)) return Fault();
        string expectedText;
        string actualText;
        string error;
        if (!JsonFileLoader<HCSearchRefreshState>.MakeData(state, expectedText, error)) return Fault();
        if (!JsonFileLoader<HCSearchRefreshState>.MakeData(check, actualText, error) || expectedText != actualText) return Fault();
        if (!DeleteFile(PATH + ".tmp")) return Fault();
        m_Fault = false;
        return true;
    }
}

class HCSearchRefreshModule : HCModule
{
    static const int RECORDS_PER_MINUTE = 32;
    static const int MAX_RECORDS = 4096;
    protected static HCSearchRefreshModule s_Instance;
    protected HCSettings m_Settings;
    protected ref HCSearchRefreshStore m_Store;
    protected ref HCSearchRefreshState m_State;
    protected ref map<string, int> m_Index = new map<string, int>;
    protected ref HCSearchRefreshPilotHouses m_Pilot;
    protected int m_Next;
    protected int m_Pending;
    protected int m_Refreshed;
    protected float m_Minute;
    protected float m_Hour;

    override string GetName() { return "LootRefresh"; }
    override bool IsEnabled(HCSettings settings) { return settings && settings.EnableWorld; }

    static string Key(string scope, string siteId) { return scope + "/" + siteId; }

    bool Active()
    {
        return IsEnabled(m_Settings) && m_State && m_Store && m_Store.Healthy();
    }

    HCSearchRefreshRow FindRow(string scope, string siteId)
    {
        int index;
        if (!Active() || !m_Index.Find(Key(scope, siteId), index)) return null;
        return m_State.Rows[index];
    }

    bool Valid(int now)
    {
        if (!m_State || m_State.Version != 1 || !m_State.Rows || m_State.Rows.Count() > MAX_RECORDS) return false;
        if (m_State.LastUtc < 1 || now < m_State.LastUtc) return false;
        foreach (HCSearchRefreshRow row : m_State.Rows)
        {
            if (!row || !HCSearchRules.TextValid(row.Scope, 256) || !HCSearchRules.TextValid(row.SiteId, 768)) return false;
            if (row.SearchedUtc < 1 || row.SearchedUtc > m_State.LastUtc || (row.Ready && !row.Revisited)) return false;
            if (row.Ready && !HCSearchRefreshPolicy.Due(row.SearchedUtc, m_State.LastUtc, HCSearchRefreshPolicy.Interval(row.SiteId))) return false;
            string key = Key(row.Scope, row.SiteId);
            if (m_Index.Contains(key)) return false;
            m_Index.Set(key, m_Index.Count());
            if (!row.Ready) m_Pending++;
        }
        return true;
    }

    override void OnStart(HCSettings settings)
    {
        if (s_Instance || !GetGame() || !GetGame().IsServer() || !IsEnabled(settings)) return;
        m_Settings = settings;
        Print(HCV2Admission.Line("LootRefresh", true, "none", true));
        m_Store = new HCSearchRefreshStore;
        m_State = m_Store.Open();
        if (!Valid(HCGroupClock.Utc()))
        {
            m_Store.Fault();
            return;
        }
        m_Pilot = new HCSearchRefreshPilotHouses;
        m_Pilot.Start(settings);
        s_Instance = this;
    }

    // Called only on server search intent or lazy legacy-state enrollment. Legacy
    // rows had no wall clock: their conservative interval starts on first revisit.
    static void Mark(string scope, string siteId, bool onlyMissing = false)
    {
        if (s_Instance && s_Instance.Active()) s_Instance.RecordSearch(scope, siteId, onlyMissing);
    }

    void RecordSearch(string scope, string siteId, bool onlyMissing)
    {
        HCSearchRefreshRow row = FindRow(scope, siteId);
        if (row && onlyMissing) return;
        if (!HCSearchRules.TextValid(scope, 256) || !HCSearchRules.TextValid(siteId, 768)) return;
        int now = HCGroupClock.Utc();
        if (now < m_State.LastUtc) { m_Store.Fault(); return; }
        if (!row)
        {
            if (m_State.Rows.Count() >= MAX_RECORDS) return;
            row = new HCSearchRefreshRow;
            row.Scope = scope;
            row.SiteId = siteId;
            m_Index.Set(Key(scope, siteId), m_State.Rows.Count());
            m_State.Rows.Insert(row);
            m_Pending++;
        }
        else if (row.Ready) m_Pending++;
        row.SearchedUtc = now;
        row.Ready = false;
        m_State.LastUtc = now;
        m_Store.Save(m_State);
    }

    static bool Ready(string scope, string siteId)
    {
        if (!s_Instance) return false;
        HCSearchRefreshRow row = s_Instance.FindRow(scope, siteId);
        return row && row.Ready;
    }

    static bool Revisited(string scope, string siteId)
    {
        if (!s_Instance) return false;
        HCSearchRefreshRow row = s_Instance.FindRow(scope, siteId);
        return row && row.Revisited;
    }

    static HCSearchRefreshPilotHouses Pilot()
    {
        if (!s_Instance || !s_Instance.Active()) return null;
        return s_Instance.m_Pilot;
    }

    override void OnTick(float deltaTime)
    {
        if (!Active() || !(deltaTime > 0.0)) return;
        m_Minute += deltaTime;
        m_Hour += deltaTime;
        if (m_Minute >= 60.0)
        {
            // Discard excess dt rather than doing catch-up bursts. Cursor survives
            // batches; UTC still counts all real downtime between process boots.
            m_Minute = 0.0;
            int now = HCGroupClock.Utc();
            if (now < m_State.LastUtc) { m_Store.Fault(); return; }
            int limit = RECORDS_PER_MINUTE;
            if (limit > m_Settings.MaxTickWorkItems) limit = m_Settings.MaxTickWorkItems;
            if (limit > m_State.Rows.Count()) limit = m_State.Rows.Count();
            int processed;
            bool changed;
            while (processed < limit)
            {
                if (m_Next >= m_State.Rows.Count()) m_Next = 0;
                HCSearchRefreshRow row = m_State.Rows[m_Next];
                if (!row.Ready && HCSearchRefreshPolicy.Due(row.SearchedUtc, now, HCSearchRefreshPolicy.Interval(row.SiteId)))
                {
                    row.Ready = true;
                    row.Revisited = true;
                    m_Pending--;
                    m_Refreshed++;
                    changed = true;
                }
                m_Next++;
                processed++;
            }
            if (changed)
            {
                m_State.LastUtc = now;
                if (!m_Store.Save(m_State)) return;
            }
        }
        if (m_Hour >= 3600.0)
        {
            m_Hour = 0.0;
            Print("[HollowCountry] V2 loot refresh refreshed=" + m_Refreshed.ToString() + " pending=" + m_Pending.ToString());
            m_Refreshed = 0;
        }
    }

    override void OnStop()
    {
        if (m_Pilot) m_Pilot.Stop();
        if (s_Instance == this) s_Instance = null;
        m_Settings = null;
    }
}

// A scope pins a world and source pack, so changed template/measurement data never
// borrows another pack's cooldown. Supply journals themselves remain immutable.
modded class HCSearchHouseJournal
{
    string RefreshScope() { return m_WorldName + "/" + m_SourcePin; }

    bool RefreshHasHistory(string siteId)
    {
        foreach (HCSearchHouseRow history : m_Rows)
        {
            if (history.SiteId == siteId && history.Phase != 0) return true;
        }
        return false;
    }

    override bool Write(int index, string kind, string actorId, int phase)
    {
        HCSearchHouseRow row = Row(index);
        if (row && Healthy() && kind == "claim") HCSearchRefreshModule.Mark(RefreshScope(), row.SiteId);
        return super.Write(index, kind, actorId, phase);
    }
}

modded class HCSearchEconomy
{
    override bool Open(HCSearchManifest expected, HCSearchSupplyRegistry source, bool initializeNewEpoch)
    {
        if (!super.Open(expected, source, initializeNewEpoch)) return false;
        HCSearchRefreshPilotCatalog.PinOriginal(m_Manifest);
        return true;
    }

    override HCSearchRecord Record(int index, string actorId, int phase)
    {
        HCSearchRecord result = super.Record(index, actorId, phase);
        if (phase == 1) HCSearchRefreshModule.Mark(m_Manifest.WorldName + "/" + m_Manifest.SourcePin, result.SiteId);
        return result;
    }
}

modded class HCSearchHouses
{
    override int Prepare(HCSearchHouseSlot slot, HCSearchHouseHit hit, PlayerBase player)
    {
        if (m_Journal && m_Journal.Healthy())
        {
            string scope = m_Journal.RefreshScope();
            if (m_Journal.RefreshHasHistory(hit.SiteId)) HCSearchRefreshModule.Mark(scope, hit.SiteId, true);
            if (HCSearchRefreshModule.Ready(scope, hit.SiteId) && !SessionOfSite(hit.SiteId))
            {
                // Bind ignores old SupplyKnown ids, including ambiguous/failed moves.
                // Append only real newly observed supplies; leave all old rows intact.
                int listed = slot.Sites.Find(hit.SiteId);
                if (listed >= 0) slot.Sites.Remove(listed);
                if (Bind(slot, hit))
                {
                    HCSearchRefreshModule.Mark(scope, hit.SiteId);
                    return OpenRow(hit.SiteId, player);
                }
            }
        }
        return super.Prepare(slot, hit, player);
    }
}

// The legacy pilot's immutable one-supply manifest is not rewritten. Its reviewed
// volume/context is handed to the same lazy finite-supply path after the cooldown.
class HCSearchRefreshPilotSite
{
    HCInteriorSite Site;
    ref HCSearchSiteVolume Volume;
    ref HCInteriorSearchContext Context;
}

class HCSearchRefreshPilotCatalog
{
    protected static ref array<ref HCSearchRefreshPilotSite> s_Sites = new array<ref HCSearchRefreshPilotSite>;
    protected static ref array<string> s_OriginalSupplies = new array<string>;

    static void Clear()
    {
        s_Sites.Clear();
        s_OriginalSupplies.Clear();
    }

    static void PinOriginal(HCSearchManifest manifest)
    {
        s_OriginalSupplies.Clear();
        foreach (HCSearchEntry entry : manifest.Entries)
        {
            if (entry.SupplyId != "") s_OriginalSupplies.Insert(entry.SupplyId);
        }
    }

    static bool OriginalSupply(string supplyId) { return s_OriginalSupplies.Find(supplyId) >= 0; }

    static void Remember(HCInteriorSite site, HCSearchSiteVolume volume, HCInteriorSearchContext context)
    {
        if (!site || !volume || !context || s_Sites.Count() >= 12) return;
        HCSearchRefreshPilotSite record = new HCSearchRefreshPilotSite;
        record.Site = site;
        record.Volume = volume;
        record.Context = context;
        s_Sites.Insert(record);
    }

    static HCSearchRefreshPilotSite Find(string siteId)
    {
        foreach (HCSearchRefreshPilotSite row : s_Sites)
        {
            if (row.Site && row.Site.Id == siteId) return row;
        }
        return null;
    }
}

modded class HCSearchBinding
{
    override bool BuildInputs()
    {
        if (!super.BuildInputs()) return false;
        HCSearchRefreshPilotCatalog.Clear();
        int index;
        while (index < m_Volumes.Count())
        {
            foreach (HCInteriorSite site : m_Sites)
            {
                if (site.Id == m_Volumes[index].SiteId) HCSearchRefreshPilotCatalog.Remember(site, m_Volumes[index], m_Contexts[index]);
            }
            index++;
        }
        return true;
    }

    override void OnStop()
    {
        HCSearchRefreshPilotCatalog.Clear();
        super.OnStop();
    }
}

// Separate lazy registry/journal for pilot volumes. It needs the measured pin,
// not a template pack: legacy-only installations must not require templates.
class HCSearchRefreshPilotJournal : HCSearchHouseJournal
{
    override bool SupplyKnown(string supplyId)
    {
        // The original manifest stays authoritative even if its spent item was
        // absent at boot and is later dropped back into the reviewed volume.
        return super.SupplyKnown(supplyId) || HCSearchRefreshPilotCatalog.OriginalSupply(supplyId);
    }
}

class HCSearchRefreshPilotHouses : HCSearchHouses
{
    protected string m_PilotPin;

    override HCSearchHouseHit Resolve(PlayerBase player, ActionTarget target)
    {
        HCInteriorsModule interiors = HCInteriorsModule.Get();
        if (!interiors || !Gate(player)) return null;
        return interiors.ResolveRefreshPilot(player, target);
    }

    override HCInteriorSearchContext BuildContext(HCSearchHouseHit hit)
    {
        HCSearchRefreshPilotSite row = HCSearchRefreshPilotCatalog.Find(hit.SiteId);
        if (!row) return null;
        return row.Context;
    }

    override HCSearchSiteVolume BuildVolume(HCSearchHouseHit hit)
    {
        HCSearchRefreshPilotSite row = HCSearchRefreshPilotCatalog.Find(hit.SiteId);
        if (!row) return null;
        return row.Volume;
    }

    void SetPin(string pin) { m_PilotPin = pin; }

    override bool OpenJournal()
    {
        if (m_Journal) return m_Journal.Healthy();
        if (m_Fault || !HCSearchRules.PinValid(m_PilotPin)) return false;
        HCSearchHouseJournal journal = new HCSearchRefreshPilotJournal;
        if (!journal.Open("stock-ce-measured-refresh-v2", m_PilotPin, HCBuildIdentity.CanonicalWorld(GetGame().GetWorldName()), HCBuildIdentity.Canonical()))
        {
            m_Fault = true;
            return false;
        }
        m_Journal = journal;
        return true;
    }

    override bool EnsureJournal()
    {
        if (!OpenJournal()) return false;
        if (m_Registry) return true;
        if (m_Fault) return false;
        HCSearchSupplyRegistry registry = new HCSearchSupplyRegistry;
        if (!registry.BindLazySource("stock-ce-measured-refresh-v2", m_PilotPin, HCBuildIdentity.CanonicalWorld(GetGame().GetWorldName()), HCBuildIdentity.Canonical()))
        {
            m_Fault = true;
            return false;
        }
        m_Registry = registry;
        return true;
    }
}

modded class HCInteriorsModule
{
    HCSearchHouseHit ResolveRefreshPilot(PlayerBase player, ActionTarget target)
    {
        HCSearchRefreshPilotHouses service = HCSearchRefreshModule.Pilot();
        if (!service || !target || !m_Ready || !m_SearchProof || !m_Store || !m_Store.Healthy() || !m_Economy || !m_Economy.Serving()) return null;
        HCInteriorSite site = FindSite(target.GetObject());
        if (!site || site.Owner || site.Phase == 0 || !ValidateTarget(player, target, site)) return null;
        HCSearchRefreshPilotSite reviewed = HCSearchRefreshPilotCatalog.Find(site.Id);
        if (!reviewed || reviewed.Site != site) return null;
        string scope = HCBuildIdentity.CanonicalWorld(GetGame().GetWorldName()) + "/" + reviewed.Context.SourcePin;
        HCSearchRefreshModule.Mark(scope, site.Id, true);
        if (!HCSearchRefreshModule.Revisited(scope, site.Id)) return null;
        service.SetPin(reviewed.Context.SourcePin);
        HCSearchHouseHit hit = new HCSearchHouseHit;
        hit.Structure = site.Target;
        hit.InstanceId = reviewed.Context.InstanceId;
        hit.SiteId = site.Id;
        hit.Center = reviewed.Volume.Center;
        hit.Radius = reviewed.Volume.Radius;
        return hit;
    }

    override bool CanStart(PlayerBase player, ActionTarget target)
    {
        HCSearchRefreshPilotHouses service = HCSearchRefreshModule.Pilot();
        if (service && ResolveRefreshPilot(player, target)) return service.CanStart(player, target);
        return super.CanStart(player, target);
    }

    override void BeginSearch(ActionData data)
    {
        HCSearchRefreshPilotHouses service = HCSearchRefreshModule.Pilot();
        if (service && data && ResolveRefreshPilot(data.m_Player, data.m_Target))
        {
            service.Begin(data);
            return;
        }
        super.BeginSearch(data);
    }

    override bool CanContinue(ActionData data)
    {
        HCSearchRefreshPilotHouses service = HCSearchRefreshModule.Pilot();
        if (service && service.OwnsAction(data)) return service.CanContinue(data);
        return super.CanContinue(data);
    }

    override void CommitSearch(ActionData data)
    {
        HCSearchRefreshPilotHouses service = HCSearchRefreshModule.Pilot();
        if (service && service.OwnsAction(data))
        {
            service.Commit(data);
            return;
        }
        super.CommitSearch(data);
    }

    override void EndSearch(ActionData data)
    {
        HCSearchRefreshPilotHouses service = HCSearchRefreshModule.Pilot();
        if (service && service.OwnsAction(data))
        {
            service.End(data);
            return;
        }
        super.EndSearch(data);
    }
}

modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        Register(new HCSearchRefreshModule);
    }
}
