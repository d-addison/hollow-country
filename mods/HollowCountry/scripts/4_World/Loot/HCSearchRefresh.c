// W4 search limits: optional $profile:HollowCountry/search-limits.json, read once.
// Partial legacy configs migrate in memory: only present, valid keys replace defaults.
// State schemas retain their old read ceilings; lowering an admission cap never
// drops cooldowns, transfer records or replay barriers. Byte/bucket constants below
// are serialization/layout safety ceilings, not operator work/admission limits.
// Native 1.30.164289: EnSystem.c:397 FileExist; JsonFileLoader.c:69 LoadData;
// paths are 1_Core/proto/EnSystem.c and 3_Game/tools/JsonFileLoader.c.
// HCGroupIO and HCV2ThreatStore own bounded IO and verified commit barriers.
class HCSearchLimitsRegistry : HCOperatorSettingsRegistry
{
    protected static bool s_SearchRegistered;
    static void HCSearchInit()
    {
        HCInit();
        if (s_SearchRegistered) { return; }
        s_SearchRegistered = true;
        HCAdd("SearchLimits.RetryDelayMs", "int", 10000, 1000, 60000, "HCSearchLimits");
        HCAdd("SearchLimits.RetryAttempts", "int", 3, 1, 12, "HCSearchLimits");
        HCAdd("SearchLimits.RefreshRecordsPerMinute", "int", 32, 1, 32, "HCSearchLimits");
        HCAdd("SearchLimits.RefreshMaxRecords", "int", 4096, 1, 4096, "HCSearchLimits");
        HCAdd("SearchLimits.RefreshMinSeconds", "int", 172800, 60, 2592000, "HCSearchLimits");
        HCAdd("SearchLimits.RefreshJitterSeconds", "int", 172800, 0, 2592000, "HCSearchLimits");
        HCAdd("SearchLimits.JournalMaxEntries", "int", 4096, 1, 4096, "HCSearchLimits");
        HCAdd("SearchLimits.RetirementRecentEntries", "int", 2048, 1, 2048, "HCSearchLimits");
        HCAdd("SearchLimits.CompactRowsPerMinute", "int", 32, 1, 32, "HCSearchLimits");
        HCAdd("SearchLimits.LegacyFilesPerMinute", "int", 32, 1, 32, "HCSearchLimits");
    }
}

class HCSearchLimits
{
    int RetryDelayMs = 10000;
    int RetryAttempts = 3;
    int RefreshRecordsPerMinute = 32;
    int RefreshMaxRecords = 4096;
    int RefreshMinSeconds = 172800;
    int RefreshJitterSeconds = 172800;
    int JournalMaxEntries = 4096;
    int RetirementRecentEntries = 2048;
    int CompactRowsPerMinute = 32;
    int LegacyFilesPerMinute = 32;
    protected static ref HCSearchLimits s_Config;
    protected bool m_Healthy = true;

    bool Healthy() { return m_Healthy; }

    static HCSearchLimits HCGet()
    {
        if (s_Config) { return s_Config; }
        HCSearchLimitsRegistry.HCSearchInit();
        s_Config = new HCSearchLimits;
        string path = "$profile:HollowCountry/search-limits.json";
        if (!HCV2ThreatStore<HCSearchLimits>.CanOpen(path))
        {
            s_Config.m_Healthy = false;
        }
        else if (FileExist(path))
        {
            string text;
            string error;
            HCSearchLimits decoded;
            if (!HCGroupIO.Read(path, 4096, text) || !JsonFileLoader<HCSearchLimits>.LoadData(text, decoded, error) || !decoded)
            {
                s_Config.m_Healthy = false;
            }
            else { s_Config.HCApply(decoded, text); }
        }
        if (!s_Config.m_Healthy)
        {
            Print("[HC Search Limits] config refused; preserve search-limits.json and recovery evidence runtime=PENDING");
        }
        else
        {
            Print("[HC Search Limits] effective config loaded; missing keys use defaults runtime=PENDING");
        }
        return s_Config;
    }

    void HCApply(HCSearchLimits decoded, string text)
    {
        if (HCJsonFields.Has(text, "RetryDelayMs"))
        {
            if (HCOperatorSettingsRegistry.HCValid("SearchLimits.RetryDelayMs", decoded.RetryDelayMs)) { RetryDelayMs = decoded.RetryDelayMs; }
            else { m_Healthy = false; }
        }
        if (HCJsonFields.Has(text, "RetryAttempts"))
        {
            if (HCOperatorSettingsRegistry.HCValid("SearchLimits.RetryAttempts", decoded.RetryAttempts)) { RetryAttempts = decoded.RetryAttempts; }
            else { m_Healthy = false; }
        }
        if (HCJsonFields.Has(text, "RefreshRecordsPerMinute"))
        {
            if (HCOperatorSettingsRegistry.HCValid("SearchLimits.RefreshRecordsPerMinute", decoded.RefreshRecordsPerMinute)) { RefreshRecordsPerMinute = decoded.RefreshRecordsPerMinute; }
            else { m_Healthy = false; }
        }
        if (HCJsonFields.Has(text, "RefreshMaxRecords"))
        {
            if (HCOperatorSettingsRegistry.HCValid("SearchLimits.RefreshMaxRecords", decoded.RefreshMaxRecords)) { RefreshMaxRecords = decoded.RefreshMaxRecords; }
            else { m_Healthy = false; }
        }
        if (HCJsonFields.Has(text, "RefreshMinSeconds"))
        {
            if (HCOperatorSettingsRegistry.HCValid("SearchLimits.RefreshMinSeconds", decoded.RefreshMinSeconds)) { RefreshMinSeconds = decoded.RefreshMinSeconds; }
            else { m_Healthy = false; }
        }
        if (HCJsonFields.Has(text, "RefreshJitterSeconds"))
        {
            if (HCOperatorSettingsRegistry.HCValid("SearchLimits.RefreshJitterSeconds", decoded.RefreshJitterSeconds)) { RefreshJitterSeconds = decoded.RefreshJitterSeconds; }
            else { m_Healthy = false; }
        }
        if (HCJsonFields.Has(text, "JournalMaxEntries"))
        {
            if (HCOperatorSettingsRegistry.HCValid("SearchLimits.JournalMaxEntries", decoded.JournalMaxEntries)) { JournalMaxEntries = decoded.JournalMaxEntries; }
            else { m_Healthy = false; }
        }
        if (HCJsonFields.Has(text, "RetirementRecentEntries"))
        {
            if (HCOperatorSettingsRegistry.HCValid("SearchLimits.RetirementRecentEntries", decoded.RetirementRecentEntries)) { RetirementRecentEntries = decoded.RetirementRecentEntries; }
            else { m_Healthy = false; }
        }
        if (HCJsonFields.Has(text, "CompactRowsPerMinute"))
        {
            if (HCOperatorSettingsRegistry.HCValid("SearchLimits.CompactRowsPerMinute", decoded.CompactRowsPerMinute)) { CompactRowsPerMinute = decoded.CompactRowsPerMinute; }
            else { m_Healthy = false; }
        }
        if (HCJsonFields.Has(text, "LegacyFilesPerMinute"))
        {
            if (HCOperatorSettingsRegistry.HCValid("SearchLimits.LegacyFilesPerMinute", decoded.LegacyFilesPerMinute)) { LegacyFilesPerMinute = decoded.LegacyFilesPerMinute; }
            else { m_Healthy = false; }
        }
    }
}

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

// W5 retirement: <=2048 recent identities plus 2048 monotone bit buckets.
// Oldest exact identity is archived BEFORE eviction. Collisions refuse fresh
// supplies; they never grant an old supply again. No inventory is created here.
// Store delegates to HCV2ThreatStore (verified temp/backup/readback barrier).
// Native scripts-1.30.164289: 1_Core/proto/EnScript.c:380 Count, :407 Insert,
// :463 Remove; EnString.c:199 Length, :240 IndexOf, :448 Get;
// EnScript.c:852 map.Count, :857 map.Clear, :902 map.Set, :906 map.Remove, :917 map.Contains;
// EnSystem.c:520 FindFile, :521 FindNextFile, :522 CloseFindFile, :528 DeleteFile.
// Migration examines <=32 legacy files per minute; no directory scan per tick.
class HCSearchRetirementEntry
{
    string SupplyId;
    int Fingerprint;
}

class HCSearchRetirementState
{
    // Required sentinels prevent missing JSON fields from silently losing recent
    // replay barriers after their immutable transfer files have been removed.
    int Version;
    int RecentCount = -1;
    ref array<ref HCSearchRetirementEntry> Recent = new array<ref HCSearchRetirementEntry>;
    ref array<int> Archive = new array<int>;
}

class HCSearchRetirementPolicy
{
    static const int MAX_RECENT = 2048;
    static const int BUCKETS = 2048;

    static int Fingerprint(string supplyId)
    {
        string alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-";
        int hash = 0;
        int characterIndex = 0;
        while (characterIndex < supplyId.Length())
        {
            hash = (hash * 31 + alphabet.IndexOf(supplyId.Get(characterIndex)) + 1) % 59392;
            characterIndex++;
        }
        return hash;
    }

    static bool ArchiveContains(HCSearchRetirementState state, int fingerprint)
    {
        int bucket = fingerprint % HCSearchRetirementPolicy.BUCKETS;
        int mask = 1 << (fingerprint % 29);
        return (state.Archive[bucket] & mask) != 0;
    }

    static bool Contains(HCSearchRetirementState state, string supplyId, int fingerprint)
    {
        if (ArchiveContains(state, fingerprint)) { return true; }
        array<ref HCSearchRetirementEntry> recentRows = state.Recent;
        foreach (HCSearchRetirementEntry recent : recentRows)
        {
            if (recent.SupplyId == supplyId) { return true; }
        }
        return false;
    }

    static void Retain(HCSearchRetirementState state, string supplyId, int fingerprint)
    {
        if (Contains(state, supplyId, fingerprint)) { return; }
        while (state.Recent.Count() >= HCSearchLimits.HCGet().RetirementRecentEntries)
        {
            HCSearchRetirementEntry oldest = state.Recent[0];
            int bucket = oldest.Fingerprint % HCSearchRetirementPolicy.BUCKETS;
            int mask = 1 << (oldest.Fingerprint % 29);
            int archived = state.Archive[bucket] | mask;
            state.Archive[bucket] = archived;
            state.Recent.Remove(0);
        }
        HCSearchRetirementEntry entry = new HCSearchRetirementEntry;
        entry.SupplyId = supplyId;
        entry.Fingerprint = fingerprint;
        state.Recent.Insert(entry);
    }
}

class HCSearchRetirementStore
{
    static const int MAX_BYTES = 524288;

    // A missing RecentCount zero-fills to 0 and would pass the Recent.Count() equality below
    // for an empty list, so presence is read from the raw text instead.
    static bool HCFieldsPresent(string text)
    {
        return HCJsonFields.Has(text, "RecentCount");
    }

    protected string m_Path;
    protected string m_Root;
    protected ref HCSearchRetirementState m_Data;
    // Hot supply admission uses a bounded hash-map lookup, not a FIFO scan.
    protected ref map<string, bool> m_RecentIds = new map<string, bool>;
    protected bool m_EvictionLogged;

    bool Open(string root)
    {
        m_Root = root;
        m_Path = root + "/retired.json";
        if (!HCV2ThreatStore<HCSearchRetirementState>.CanOpen(m_Path)) { return false; }
        if (FileExist(m_Path))
        {
            if (!HCV2ThreatStore<HCSearchRetirementState>.Load(m_Path, MAX_BYTES, m_Data)) { return false; }
            string image;
            if (!HCGroupIO.Read(m_Path, MAX_BYTES, image) || !HCSearchRetirementStore.HCFieldsPresent(image))
            {
                Print("[HC Search] retired.json refused: RecentCount missing or unreadable; no replay barrier is rewound");
                return false;
            }
        }
        else
        {
            m_Data = new HCSearchRetirementState;
            m_Data.Version = 1;
            m_Data.RecentCount = 0;
            while (m_Data.Archive.Count() < HCSearchRetirementPolicy.BUCKETS) { m_Data.Archive.Insert(0); }
            if (!HCV2ThreatStore<HCSearchRetirementState>.Save(m_Path, m_Data, MAX_BYTES)) { return false; }
        }
        if (!m_Data || m_Data.Version != 1 || !m_Data.Recent || !m_Data.Archive) { return false; }
        if (m_Data.Recent.Count() > HCSearchRetirementPolicy.MAX_RECENT) { return false; }
        if (m_Data.RecentCount != m_Data.Recent.Count()) { return false; }
        if (m_Data.Archive.Count() != HCSearchRetirementPolicy.BUCKETS) { return false; }
        array<int> archivedRows = m_Data.Archive;
        foreach (int archived : archivedRows)
        {
            if (archived < 0 || archived > 536870911) { return false; }
        }
        array<ref HCSearchRetirementEntry> entryRows = m_Data.Recent;
        foreach (HCSearchRetirementEntry entry : entryRows)
        {
            if (!entry || !HCSearchRules.TextValid(entry.SupplyId, 64)) { return false; }
            if (entry.Fingerprint != HCSearchRetirementPolicy.Fingerprint(entry.SupplyId)) { return false; }
            if (m_RecentIds.Contains(entry.SupplyId)) { return false; }
            m_RecentIds.Set(entry.SupplyId, true);
        }
        return true;
    }

    bool Contains(string supplyId)
    {
        if (m_RecentIds.Contains(supplyId)) { return true; }
        return HCSearchRetirementPolicy.ArchiveContains(m_Data, HCSearchRetirementPolicy.Fingerprint(supplyId));
    }

    bool Retire(string supplyId)
    {
        if (Contains(supplyId)) { return true; }
        bool evicted = m_Data.Recent.Count() >= HCSearchLimits.HCGet().RetirementRecentEntries;
        HCSearchRetirementPolicy.Retain(m_Data, supplyId, HCSearchRetirementPolicy.Fingerprint(supplyId));
        m_Data.RecentCount = m_Data.Recent.Count();
        if (!HCV2ThreatStore<HCSearchRetirementState>.Save(m_Path, m_Data, MAX_BYTES)) { return false; }
        if (evicted)
        {
            m_RecentIds.Clear();
            array<ref HCSearchRetirementEntry> retainedEntries = m_Data.Recent;
            foreach (HCSearchRetirementEntry retainedEntry : retainedEntries) { m_RecentIds.Set(retainedEntry.SupplyId, true); }
        }
        m_RecentIds.Set(supplyId, true);
        if (evicted && !m_EvictionLogged)
        {
            Print("[HC Search Houses] tombstone configured FIFO oldest archived; conservative replay barrier retained");
            m_EvictionLogged = true;
        }
        return true;
    }

    // The find handle is a local opened and closed within each call (vanilla
    // 5_Mission/GUI/NewUI/VideoPlayer.c:81 pattern): every pruned file is retired and
    // deleted before the next one, so each call re-enumerates only what remains.
    bool PruneLegacy(HCSearchHouseJournal journal, int limit)
    {
        string legacyName;
        FileAttr legacyAttributes;
        FindFileHandle handle = FindFile(m_Root + "/spent_*.json", legacyName, legacyAttributes, FindFileFlags.DIRECTORIES);
        bool more = legacyName != "";
        bool ok = true;
        int examined = 0;
        HCUnitBudget legacyWork = HCServer.HCTickWork();
        while (more && examined < limit)
        {
            if (!legacyWork.HCTakeFor(HCUnitBudget.HC_WORK_SEARCH_COMPACT, 1)) { break; }
            examined++;
            string legacyPath = m_Root + "/" + legacyName;
            HCSearchRecord legacy;
            if (!HCSearchJson<HCSearchRecord>.Load(legacyPath, 8192, legacy)) { ok = false; break; }
            HCSearchHouseRow row = new HCSearchHouseRow;
            row.SiteId = legacy.SiteId;
            row.SupplyId = legacy.SupplyId;
            row.ItemClass = legacy.ItemClass;
            if (!journal.Matches(legacy, row) || legacy.ActorId != "retired") { ok = false; break; }
            if (legacy.Phase < 2 || legacy.Phase > 4) { ok = false; break; }
            if (journal.TombstonePath(legacy.SupplyId) != legacyPath) { ok = false; break; }
            // Archive readback precedes deletion. An interruption retains both
            // barriers, or a poisoned .tmp that rejects the next journal open.
            if (!Retire(legacy.SupplyId) || !DeleteFile(legacyPath)) { ok = false; break; }
            more = FindNextFile(handle, legacyName, legacyAttributes);
        }
        CloseFindFile(handle);
        return ok;
    }
}

class HCSearchRefreshPolicy
{
    // Bounded polynomial hash of the stable site id, independent of process RNG,
    // clock, enumeration order, native hash sign and signed-int overflow.
    static int Interval(string siteId)
    {
        HCSearchLimits limits = HCSearchLimits.HCGet();
        return HCIntervalFor(siteId, limits.RefreshMinSeconds, limits.RefreshJitterSeconds);
    }

    // Historical version-1 timers used these exact bounds. Preserve their due
    // decisions when migrating; newly searched sites take current operator policy.
    static int HCLegacyInterval(string siteId) { return HCIntervalFor(siteId, 172800, 172800); }

    static int HCIntervalFor(string siteId, int minimumSeconds, int jitterSeconds)
    {
        string alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-:+/=";
        int hash = 0;
        int index = 0;
        while (index < siteId.Length())
        {
            hash = (hash * 31 + alphabet.IndexOf(siteId.Get(index)) + 1) % (jitterSeconds + 1);
            index++;
        }
        return minimumSeconds + hash;
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
    int IntervalSeconds;
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
    // Rows still owed to the current minute's batch (shared-budget resume) and whether it changed any.
    protected int m_BatchLeft;
    protected bool m_BatchChanged;
    protected float m_Hour;
    protected bool m_CompactPilot;
    protected string m_Refusal;
    protected ref HCOperationalStatus m_Operational = new HCOperationalStatus;

    override string GetName() { return "LootRefresh"; }

    // Wave 16: started = this module is the registered instance (state loaded and valid); a store that
    // faulted after start is a real degradation, an invalid state at start is a refusal.
    override HCOperationalStatus HCGetOperationalStatus()
    {
        bool started = false;
        string fault = "";
        if (s_Instance == this) { started = true; }
        if (started && m_Store && !m_Store.Healthy()) { fault = "refresh_store_fault"; }
        HCModuleReadiness.HCDerive(m_Operational, started, m_Refusal, fault, "refresh_state_loaded");
        return m_Operational;
    }
    override bool IsEnabled(HCSettings settings) { return settings && settings.EnableWorld && settings.EnableSearch; }

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
        array<ref HCSearchRefreshRow> rowRows = m_State.Rows;
        foreach (HCSearchRefreshRow row : rowRows)
        {
            if (!row || !HCSearchRules.TextValid(row.Scope, 256) || !HCSearchRules.TextValid(row.SiteId, 768)) return false;
            if (row.SearchedUtc < 1 || row.SearchedUtc > m_State.LastUtc || (row.Ready && !row.Revisited)) return false;
            if (row.IntervalSeconds == 0) { row.IntervalSeconds = HCSearchRefreshPolicy.HCLegacyInterval(row.SiteId); }
            if (row.IntervalSeconds < 60 || row.IntervalSeconds > 5184000) { return false; }
            if (row.Ready && !HCSearchRefreshPolicy.Due(row.SearchedUtc, m_State.LastUtc, row.IntervalSeconds)) { return false; }
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
        if (!HCSearchLimits.HCGet().Healthy()) { m_Refusal = "search_limits_invalid"; return; }
        m_Settings = settings;
        m_Refusal = "";
        Print(HCV2Admission.Line("LootRefresh", true, "search_refresh", false) + " runtime=PENDING");
        Print("[HC Search Refresh] bounded refresh and alternating journal maintenance scheduled runtime=PENDING");
        m_Store = new HCSearchRefreshStore;
        m_State = m_Store.Open();
        if (!Valid(HCGroupClock.Utc()))
        {
            m_Refusal = "refresh_state_invalid";
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
            if (m_State.Rows.Count() >= HCSearchLimits.HCGet().RefreshMaxRecords) { return; }
            row = new HCSearchRefreshRow;
            row.Scope = scope;
            row.SiteId = siteId;
            m_Index.Set(Key(scope, siteId), m_State.Rows.Count());
            m_State.Rows.Insert(row);
            m_Pending++;
        }
        else if (row.Ready) m_Pending++;
        row.SearchedUtc = now;
        row.IntervalSeconds = HCSearchRefreshPolicy.Interval(siteId);
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

    bool RecycleReadyTimer()
    {
        int readyIndex = m_State.Rows.Count() - 1;
        while (readyIndex >= 0)
        {
            HCSearchRefreshRow readyRow = m_State.Rows[readyIndex];
            if (readyRow.Ready && !readyRow.Revisited)
            {
                // Revisited is durable pilot routing history, not disposable timer
                // metadata. Never evict it to make room; the fixed cap fails closed.
                RemoveReadyTimer(readyRow);
                Print("[HC Search Houses] expired refresh timer recycled");
                return true;
            }
            readyIndex = readyIndex - 1;
        }
        return false;
    }

    // Only after all active transfer rows for a ready site have been compacted.
    // The immutable per-supply tombstones belong to the journal, not this timer.
    // Keep Revisited rows in the persisted ledger: clearing the route can strand
    // a pilot after compaction/restart. At MAX_RECORDS new timer enrollment refuses.
    static void ForgetCompacted(string scope, string siteId)
    {
        if (!s_Instance || !s_Instance.Active()) { return; }
        HCSearchRefreshRow expired = s_Instance.FindRow(scope, siteId);
        if (!expired || !expired.Ready || expired.Revisited) { return; }
        s_Instance.RemoveReadyTimer(expired);
        s_Instance.m_Store.Save(s_Instance.m_State);
    }

    void RemoveReadyTimer(HCSearchRefreshRow expired)
    {
        int expiredIndex = m_State.Rows.Find(expired);
        if (expiredIndex < 0 || !expired.Ready || expired.Revisited) { return; }
        m_State.Rows.Remove(expiredIndex);
        m_Index.Clear();
        int timerIndex = 0;
        array<ref HCSearchRefreshRow> remainingRows = m_State.Rows;
        foreach (HCSearchRefreshRow remaining : remainingRows)
        {
            m_Index.Set(Key(remaining.Scope, remaining.SiteId), timerIndex);
            timerIndex++;
        }
        m_Next = 0;
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
        HCReached.Mark("search_refresh.tick");
        m_Hour += deltaTime;
        if (m_Minute >= 60.0 && m_BatchLeft < 1)
        {
            // Discard excess dt rather than doing catch-up bursts. Cursor survives
            // batches; UTC still counts all real downtime between process boots.
            m_Minute = 0.0;
            // Retirement previously had no caller. Alternate owners so a busy
            // house journal cannot starve the pilot's replay-safe cleanup.
            HCSearchHouses compactOwner = HCSearchBinding.Houses();
            if (m_CompactPilot || !compactOwner) { compactOwner = m_Pilot; }
            m_CompactPilot = !m_CompactPilot;
            if (compactOwner) { compactOwner.CompactSettled(); }
            if (HCGroupClock.Utc() < m_State.LastUtc) { m_Store.Fault(); return; }
            int limit = HCSearchLimits.HCGet().RefreshRecordsPerMinute;
            if (limit > m_Settings.MaxTickWorkItems) limit = m_Settings.MaxTickWorkItems;
            if (limit > m_State.Rows.Count()) limit = m_State.Rows.Count();
            m_BatchLeft = limit;
            m_BatchChanged = false;
        }
        if (m_BatchLeft > 0)
        {
            // Wave 13 (#138): the minute's rows are owed, not skipped. Each row takes one unit of the
            // shared core-tick budget; a refused request leaves m_Next and m_BatchLeft where they are
            // and the next tick continues (the shared budget forces one row per tick, so the batch
            // always finishes). The batch is saved once, when its last row is done.
            int now = HCGroupClock.Utc();
            if (now < m_State.LastUtc) { m_Store.Fault(); return; }
            HCUnitBudget sharedWork = HCServer.HCTickWork();
            while (m_BatchLeft > 0)
            {
                // Rows may be compacted away between ticks of one batch: never index an empty list.
                if (m_State.Rows.Count() < 1) { m_BatchLeft = 0; break; }
                if (m_Next >= m_State.Rows.Count()) m_Next = 0;
                if (!sharedWork.HCTakeFor(HCUnitBudget.HC_WORK_SEARCH_REFRESH, 1)) break;
                HCSearchRefreshRow row = m_State.Rows[m_Next];
                if (!row.Ready && HCSearchRefreshPolicy.Due(row.SearchedUtc, now, row.IntervalSeconds))
                {
                    row.Ready = true;
                    row.Revisited = true;
                    m_Pending--;
                    m_Refreshed++;
                    m_BatchChanged = true;
                }
                m_Next++;
                m_BatchLeft = m_BatchLeft - 1;
            }
            if (m_BatchLeft < 1 && m_BatchChanged)
            {
                m_BatchChanged = false;
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
        m_BatchLeft = 0;
        m_BatchChanged = false;
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
        array<ref HCSearchHouseRow> historyRows = m_Rows;
        foreach (HCSearchHouseRow history : historyRows)
        {
            if (history && history.SiteId == siteId && history.Phase != 0) { return true; }
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
    protected int m_CompactNext;

    // <=32 inspected slots per minute, no index movement and no session invalidation.
    void CompactSettled()
    {
        if (m_Busy || m_Sessions.Count() > 0 || !m_Journal || !m_Journal.Healthy()) { return; }
        int examined = 0;
        HCSearchLimits limits = HCSearchLimits.HCGet();
        int limit = limits.CompactRowsPerMinute;
        if (limit > m_Settings.MaxTickWorkItems) { limit = m_Settings.MaxTickWorkItems; }
        int legacyLimit = limits.LegacyFilesPerMinute;
        if (legacyLimit > m_Settings.MaxTickWorkItems) { legacyLimit = m_Settings.MaxTickWorkItems; }
        if (!m_Journal.PruneLegacyTombstones(legacyLimit)) { return; }
        if (limit > m_Journal.Count()) { limit = m_Journal.Count(); }
        // Wave 13 (#138): each inspected row takes one shared core-tick unit; a refused request keeps
        // m_CompactNext and the next minute resumes there.
        HCUnitBudget sharedWork = HCServer.HCTickWork();
        while (examined < limit)
        {
            if (m_CompactNext >= m_Journal.Count()) { m_CompactNext = 0; }
            if (!sharedWork.HCTakeFor(HCUnitBudget.HC_WORK_SEARCH_COMPACT, 1)) { break; }
            int compactIndex = m_CompactNext;
            m_CompactNext++;
            examined++;
            HCSearchHouseRow candidate = m_Journal.Row(compactIndex);
            if (!candidate || candidate.Phase < 2) { continue; }
            string scope = m_Journal.RefreshScope();
            string compactSite = candidate.SiteId;
            HCSearchRefreshModule.Mark(scope, compactSite, true);
            if (!HCSearchRefreshModule.Ready(scope, compactSite)) { continue; }
            if (m_Journal.BindingReleased(compactSite) && !SiteResident(compactSite))
            {
                if (m_Registry && !m_Registry.Forget(candidate.SupplyId)) { return; }
                if (!m_Journal.Compact(compactIndex)) { return; }
                if (!m_Journal.SiteBound(compactSite)) { HCSearchRefreshModule.ForgetCompacted(scope, compactSite); }
            }
        }
    }

    bool SiteResident(string siteId)
    {
        array<ref HCSearchHouseSlot> activeSlotRows = m_Slots;
        foreach (HCSearchHouseSlot activeSlot : activeSlotRows)
        {
            if (activeSlot.Sites.Find(siteId) >= 0) { return true; }
        }
        array<ref HCSearchHouseSlot> detachedSlotRows = m_DetachedSlots;
        foreach (HCSearchHouseSlot detachedSlot : detachedSlotRows)
        {
            if (detachedSlot.Sites.Find(siteId) >= 0) { return true; }
        }
        return false;
    }

    override int Prepare(HCSearchHouseSlot slot, HCSearchHouseHit hit, PlayerBase player)
    {
        if (m_Journal && m_Journal.Healthy())
        {
            string scope = m_Journal.RefreshScope();
            if (m_Journal.RefreshHasHistory(hit.SiteId)) HCSearchRefreshModule.Mark(scope, hit.SiteId, true);
            if (HCSearchRefreshModule.Ready(scope, hit.SiteId) && HCRefreshPreparationAllowed(hit, player))
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
        array<ref HCSearchEntry> entryRows = manifest.Entries;
        foreach (HCSearchEntry entry : entryRows)
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
            array<ref HCInteriorSite> siteRows = m_Sites;
            foreach (HCInteriorSite site : siteRows)
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
            Print("[HC Search Refresh] pilot journal refused; pilot house search stays refused");
            return false;
        }
        m_Journal = journal;
        return true;
    }

    override bool EnsureJournal()
    {
        if (!OpenJournal())
        {
            m_Refusal = HCRefusal.STORAGE;
            return false;
        }
        if (m_Registry) return true;
        if (m_Fault)
        {
            m_Refusal = HCRefusal.STORAGE;
            return false;
        }
        HCSearchSupplyRegistry registry = new HCSearchSupplyRegistry;
        if (!registry.BindLazySource("stock-ce-measured-refresh-v2", m_PilotPin, HCBuildIdentity.CanonicalWorld(GetGame().GetWorldName()), HCBuildIdentity.Canonical()))
        {
            m_Fault = true;
            Print("[HC Search Refresh] pilot registry refused; pilot house search stays refused");
            m_Refusal = HCRefusal.STORAGE;
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
