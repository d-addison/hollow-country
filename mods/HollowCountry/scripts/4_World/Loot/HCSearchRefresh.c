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
    // Retired with the interiors pilot (2026-11-22), no longer registered or read. They are
    // declared only so an old search-limits.json that still carries them decodes; HCApply
    // logs and ignores them (any value, no range check) and never lets them refuse the file.
    int RetryDelayMs;
    int RetryAttempts;
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

    protected void HCRetiredKey(string text, string key)
    {
        if (HCJsonFields.Has(text, key)) { Print("[HC Search Limits] retired key ignored key=" + key + " (no effect; safe to remove from search-limits.json)"); }
    }

    void HCApply(HCSearchLimits decoded, string text)
    {
        HCRetiredKey(text, "RetryDelayMs");
        HCRetiredKey(text, "RetryAttempts");
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
        HCTextWindow identity = new HCTextWindow(supplyId);
        int characterIndex = 0;
        while (characterIndex < identity.Length())
        {
            hash = (hash * 31 + alphabet.IndexOf(identity.At(characterIndex)) + 1) % 59392;
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
            // Ordered: array.Remove would move the newest entry into slot 0 and retire it first.
            state.Recent.RemoveOrdered(0);
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
    protected ref HCSearchRetirementSaveJob m_SaveJob;
    protected ref HCV2ThreatStore<HCSearchRetirementState> m_Writer = new HCV2ThreatStore<HCSearchRetirementState>;
    protected int m_Revision;
    protected int m_SnapshotRevision;
    protected int m_CommittedRevision;
    protected bool m_Fault;
    protected int m_EmptyLegacyScans;

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
            m_Revision++;
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
        m_SaveJob = new HCSearchRetirementSaveJob;
        m_SaveJob.Owner = this;
        HCSaveScheduler.HCRegister(m_SaveJob);
        m_SaveJob.HCDirty = HCPendingCheckpoint();
        m_SaveJob.HCUrgent = m_SaveJob.HCDirty;
        return true;
    }

    bool HCPendingCheckpoint() { return m_Revision != m_CommittedRevision; }
    bool Faulted() { return m_Fault; }
    void HCPump() { HCSaveScheduler.HCPumpFallback(m_SaveJob); }
    void Stop()
    {
        if (!m_SaveJob) { return; }
        if (!m_Fault && !HCSaveScheduler.HCFlush(m_SaveJob)) { m_Fault = true; }
        HCSaveScheduler.HCUnregister(m_SaveJob);
        m_SaveJob.Owner = null;
        m_SaveJob = null;
    }
    int HCStepRetirement()
    {
        if (m_Fault) { return HCSaveJob.STEP_FAILED; }
        if (!m_Writer.SaveInFlight()) { m_SnapshotRevision = m_Revision; }
        int result = m_Writer.SaveStep(m_Path, m_Data, MAX_BYTES);
        if (result == HCSaveJob.STEP_FAILED) { m_Fault = true; }
        if (result == HCSaveJob.STEP_DONE) { m_CommittedRevision = m_SnapshotRevision; }
        return result;
    }

    bool Contains(string supplyId)
    {
        if (m_RecentIds.Contains(supplyId)) { return true; }
        return HCSearchRetirementPolicy.ArchiveContains(m_Data, HCSearchRetirementPolicy.Fingerprint(supplyId));
    }

    // Boot recovery remains a durability barrier. Tick compaction calls
    // HCQueueRetirement first and resumes only when that image has committed.
    bool Retire(string supplyId)
    {
        if (!HCQueueRetirement(supplyId)) { return false; }
        return HCSaveScheduler.HCFlush(m_SaveJob);
    }

    bool HCQueueRetirement(string supplyId)
    {
        if (m_Fault || !m_SaveJob) { return false; }
        if (Contains(supplyId)) { return true; }
        bool evicted = m_Data.Recent.Count() >= HCSearchLimits.HCGet().RetirementRecentEntries;
        HCSearchRetirementPolicy.Retain(m_Data, supplyId, HCSearchRetirementPolicy.Fingerprint(supplyId));
        m_Data.RecentCount = m_Data.Recent.Count();
        m_Revision++;
        m_SaveJob.HCDirty = true;
        m_SaveJob.HCUrgent = true;
        m_SaveJob.HCDue = GetGame().GetTickTime();
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
    // 5_Mission/GUI/NewUI/VideoPlayer.c:81 pattern). Queue a bounded batch into
    // one retirement image; only delete barriers from an already committed image.
    bool PruneLegacy(HCSearchHouseJournal journal, int limit)
    {
        string legacyName;
        FileAttr legacyAttributes;
        FindFileHandle handle = FindFile(m_Root + "/spent_*.json", legacyName, legacyAttributes, FindFileFlags.DIRECTORIES);
        bool more = legacyName != "";
        // No spent_* file remains: the recovery index of legacy names is obsolete. One empty scan can be a
        // transient native failure, so the index is dropped only after two consecutive empty scans.
        if (more) { m_EmptyLegacyScans = 0; }
        else
        {
            m_EmptyLegacyScans++;
            if (m_EmptyLegacyScans >= 2) { journal.HCLegacyDrained(); }
        }
        bool ok = true;
        int examined = 0;
        HCUnitBudget legacyWork = HCServer.HCTickWork();
        while (more && examined < limit)
        {
            if (!legacyWork.HCTakeFor(HCUnitBudget.HC_WORK_SEARCH_RETIREMENT, 1)) { break; }
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
            // Re-checked per file: an id queued earlier in this loop (or an eviction bit it set) is in memory
            // only until its image commits and must not authorize a removal.
            bool durable = !HCPendingCheckpoint() && Contains(legacy.SupplyId);
            if (!HCQueueRetirement(legacy.SupplyId)) { ok = false; break; }
            // Queued ids share an image; keep their legacy barriers until readback. The removal itself is a
            // staged journal-job operation, never a delete in this tick.
            if (durable && !journal.HCLegacyRemove(legacyPath, legacy.SupplyId)) { ok = false; break; }
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
        HCTextWindow identity = new HCTextWindow(siteId);
        int index = 0;
        while (index < identity.Length())
        {
            hash = (hash * 31 + alphabet.IndexOf(identity.At(index)) + 1) % (jitterSeconds + 1);
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
    // Durable routing history: set when a timer first becomes ready again. Persisted rows
    // from earlier releases may carry it (and a "pilot" scope); both stay inert.
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
    // 4096 rows: <=1024 ASCII identity bytes + <=256 JSON/scalar bytes
    // per row, plus <=256 header bytes: <=5,243,136 bytes. Reserve 6 MiB.
    // Two worst-case images require <18,688 shared stages, so shutdown uses
    // the shared large-image barrier (default 33,088), not the 4096 guard.
    static const int MAX_BYTES = 6291456;
    protected bool m_Fault;
    protected ref HCStagedSaveImage m_Image = new HCStagedSaveImage;
    protected int m_ImageRevision;
    protected int m_SavedRevision;

    int SavedRevision() { return m_SavedRevision; }

    // Keep the original .tmp/.bak admission protocol. Mutations during a write
    // refresh its intent before it can admit an obsolete Ready/revisit snapshot.
    int CheckpointStep(HCSearchRefreshState state, int revision)
    {
        if (m_Fault || !state) { return HCSaveJob.STEP_FAILED; }
        if (state.LastUtc > HCGroupClock.Utc()) { Fault(); return HCSaveJob.STEP_FAILED; }
        if (!m_Image.Active() || (m_Image.HCReadyToClearIntent() && m_ImageRevision != revision))
        {
            HCSaveJob.HCOperation = "encode";
            string text;
            string error;
            if (!JsonFileLoader<HCSearchRefreshState>.MakeData(state, text, error)) { Fault(); return HCSaveJob.STEP_FAILED; }
            bool encoded;
            if (m_Image.Active()) { encoded = m_Image.HCRefreshIntent(text); }
            else { encoded = m_Image.Begin(PATH, text, MAX_BYTES); }
            if (!encoded) { Fault(); return HCSaveJob.STEP_FAILED; }
            m_ImageRevision = revision;
            return HCSaveJob.STEP_MORE;
        }
        int result = m_Image.HCStepImage();
        if (result == HCSaveJob.STEP_FAILED) { Fault(); }
        if (result == HCSaveJob.STEP_DONE) { m_SavedRevision = m_ImageRevision; }
        return result;
    }


    bool Healthy() { return !m_Fault; }

    bool Fault()
    {
        m_Fault = true;
        Print("[HollowCountry] V2 loot refresh inactive: preserve search-refresh.json, .tmp and .bak; recovery required");
        return false;
    }

    // Validate a whole canonical image before it can authorize recovery. Legacy
    // IntervalSeconds=0 is admitted unchanged; module enrollment fills it later.
    // Recovery compares durable image clocks with each other, never wall time.
    protected HCSearchRefreshState Decode(string text)
    {
        if (text == "" || text.Length() > MAX_BYTES) { return null; }
        HCSearchRefreshState state;
        string error;
        string canonical;
        if (!JsonFileLoader<HCSearchRefreshState>.LoadData(text, state, error) || !state) { return null; }
        if (!JsonFileLoader<HCSearchRefreshState>.MakeData(state, canonical, error) || canonical != text) { return null; }
        if (state.Version != 1 || !state.Rows || state.Rows.Count() > HCSearchRefreshModule.MAX_RECORDS || state.LastUtc < 1) { return null; }
        map<string, bool> keys = new map<string, bool>;
        foreach (HCSearchRefreshRow row : state.Rows)
        {
            if (!row || !HCSearchRules.TextValid(row.Scope, 256) || !HCSearchRules.TextValid(row.SiteId, 768)) { return null; }
            if (row.SearchedUtc < 1 || row.SearchedUtc > state.LastUtc || (row.Ready && !row.Revisited)) { return null; }
            int interval = row.IntervalSeconds;
            if (interval == 0) { interval = HCSearchRefreshPolicy.HCLegacyInterval(row.SiteId); }
            if (interval < 60 || interval > 5184000) { return null; }
            if (row.Ready && !HCSearchRefreshPolicy.Due(row.SearchedUtc, state.LastUtc, interval)) { return null; }
            string key = HCSearchRefreshModule.Key(row.Scope, row.SiteId);
            if (keys.Contains(key)) { return null; }
            keys.Set(key, true);
        }
        return state;
    }

    protected static bool s_RecoveryUnavailablePrinted;

    // EnSystem.c:397/417/425. An existing file that cannot be opened or read is
    // unavailable, never empty: HCReadRaw folds both into false/"" and an
    // unreadable intent would be archived as unverifiable. Empty or oversize
    // content that was read stays "" (invalid) for the caller's Decode.
    protected bool ReadRecoveryFile(string path, out string text)
    {
        text = "";
        if (!FileExist(path)) { return true; }
        FileHandle handle = OpenFile(path, FileMode.READ);
        if (!handle) { return false; }
        int count = ReadFile(handle, text, MAX_BYTES + 1);
        CloseFile(handle);
        if (count < 0) { text = ""; return false; }
        if (count < 1 || count > MAX_BYTES || text.Length() < 1 || text.Length() > MAX_BYTES) { text = ""; }
        return true;
    }

    protected bool RecoverIntent()
    {
        // Recovery promotes, restores or discards the primary outside the image writer.
        HCStagedSaveImage.HCForget(PATH);
        string primaryText;
        string intentText;
        if (!ReadRecoveryFile(PATH, primaryText) || !ReadRecoveryFile(PATH + ".tmp", intentText))
        {
            // Keep primary, intent and backup untouched; Open() faults and the next boot retries.
            if (!s_RecoveryUnavailablePrinted)
            {
                s_RecoveryUnavailablePrinted = true;
                Print("[HC Search Refresh] intent_read_unavailable file=search-refresh.json action=retain_retry_next_boot");
            }
            return false;
        }
        HCSearchRefreshState primary = Decode(primaryText);
        HCSearchRefreshState intent = Decode(intentText);
        if (!primary) { primaryText = ""; }
        if (!intent) { intentText = ""; }
        // A verified primary wins over an older intent. Equal-UTC intents may
        // contain a later search or Ready change within the same second.
        if (primary && intent && intent.LastUtc < primary.LastUtc) { intentText = ""; }
        if (!primary && intent && FileExist(PATH + ".bak"))
        {
            string backupText;
            if (!ReadRecoveryFile(PATH + ".bak", backupText)) { return false; }
            HCSearchRefreshState backup = Decode(backupText);
            if (!backup || backup.LastUtc > intent.LastUtc) { return false; }
        }
        return HCWorldIntentRecovery.Recover(PATH, MAX_BYTES, intentText, primaryText, true);
    }

    HCSearchRefreshState Open()
    {
        if (!FileExist("$profile:HollowCountry") && !MakeDirectory("$profile:HollowCountry"))
        {
            Fault();
            return null;
        }
        bool recovered = true;
        if (FileExist(PATH + ".tmp")) { recovered = RecoverIntent(); }
        if (!recovered || (!FileExist(PATH) && FileExist(PATH + ".bak")))
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
        if (state.LastUtc > HCGroupClock.Utc()) return Fault();
        // Poison before the first write: even partial temp writes remain evidence.
        m_Fault = true;
        // This synchronous replace rewrites the primary outside the image writer.
        HCStagedSaveImage.HCForget(PATH);
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
    protected ref HCActivityCounters m_Activity = new HCActivityCounters("attempts timer_writes checked waiting refreshed bind_attempts bound bind_refused", "[HC Search Refresh]");

    static void HCRecordAttempt()
    {
        if (s_Instance && s_Instance.Active()) s_Instance.m_Activity.Add("attempts");
    }

    static void HCRecordBinding(bool bound)
    {
        if (!s_Instance || !s_Instance.Active()) return;
        s_Instance.m_Activity.Add("bind_attempts");
        if (bound) s_Instance.m_Activity.Add("bound");
        else s_Instance.m_Activity.Add("bind_refused");
    }

    static const int RECORDS_PER_MINUTE = 32;
    static const int MAX_RECORDS = 4096;
    protected static HCSearchRefreshModule s_Instance;
    protected HCSettings m_Settings;
    protected ref HCSearchRefreshStore m_Store;
    protected ref HCSearchRefreshSaveJob m_SaveJob;
    protected int m_CheckpointRevision;
    // Session-only authorization: reset cooldown must commit before fresh binding.
    protected ref map<string, int> m_RefreshReservations = new map<string, int>;

    bool HCRequestCheckpoint(bool barrier = false)
    {
        if (!Active() || !m_SaveJob) { return false; }
        m_CheckpointRevision++;
        m_SaveJob.HCDirty = true;
        if (barrier) { m_SaveJob.HCUrgent = true; m_SaveJob.HCDue = GetGame().GetTickTime(); }
        return true;
    }

    bool HCCheckpointPending() { return m_SaveJob && (m_SaveJob.HCDirty || m_SaveJob.HCInFlight); }

    int HCCheckpointStep()
    {
        if (!Active()) { return HCSaveJob.STEP_FAILED; }
        return m_Store.CheckpointStep(m_State, m_CheckpointRevision);
    }

    static bool HCRefreshReserved(string scope, string siteId)
    {
        return s_Instance && s_Instance.m_RefreshReservations.Contains(Key(scope, siteId));
    }

    static bool HCReserveRefresh(string scope, string siteId)
    {
        if (!s_Instance || !s_Instance.Active()) { return false; }
        string key = Key(scope, siteId);
        int revision;
        if (s_Instance.m_RefreshReservations.Find(key, revision))
        {
            return !s_Instance.HCCheckpointPending() && s_Instance.m_Store.SavedRevision() >= revision;
        }
        if (!Ready(scope, siteId)) { return false; }
        s_Instance.RecordSearch(scope, siteId, false);
        s_Instance.m_RefreshReservations.Set(key, s_Instance.m_CheckpointRevision);
        return false;
    }

    protected ref HCSearchRefreshState m_State;
    protected ref map<string, int> m_Index = new map<string, int>;
    protected int m_Next;
    protected int m_Pending;
    protected int m_LastWaitSeconds;
    protected float m_Minute;
    // Rows still owed to the current minute's batch (shared-budget resume) and whether it changed any.
    protected int m_BatchLeft;
    protected bool m_BatchChanged;
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
        return IsEnabled(m_Settings) && m_State && m_State.Rows && m_Store && m_Store.Healthy();
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
        m_SaveJob = new HCSearchRefreshSaveJob;
        m_SaveJob.Owner = this;
        HCSaveScheduler.HCRegister(m_SaveJob);
        s_Instance = this;
    }

    // Called only on server search intent or lazy legacy-state enrollment. Legacy
    // rows had no wall clock: their conservative interval starts on first revisit.
    static void Mark(string scope, string siteId, bool onlyMissing = false)
    {
        if (!s_Instance || !s_Instance.Active()) { return; }
        string key = Key(scope, siteId);
        int revision;
        if (!onlyMissing && s_Instance.m_RefreshReservations.Find(key, revision))
        {
            // Successful binding consumes the already committed timer reset.
            s_Instance.m_RefreshReservations.Remove(key);
            return;
        }
        s_Instance.RecordSearch(scope, siteId, onlyMissing);
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
        m_Activity.Add("timer_writes");
        row.SearchedUtc = now;
        row.IntervalSeconds = HCSearchRefreshPolicy.Interval(siteId);
        row.Ready = false;
        m_State.LastUtc = now;
        HCRequestCheckpoint(true);
    }

    static bool Ready(string scope, string siteId)
    {
        if (!s_Instance) return false;
        HCSearchRefreshRow row = s_Instance.FindRow(scope, siteId);
        return row && row.Ready && !s_Instance.HCCheckpointPending();
    }

    // Only after all active transfer rows for a ready site have been compacted.
    // The immutable per-supply tombstones belong to the journal, not this timer.
    // Keep Revisited rows in the persisted ledger: clearing the route can strand
    // a site after compaction/restart. At MAX_RECORDS new timer enrollment refuses.
    static void ForgetCompacted(string scope, string siteId)
    {
        if (!s_Instance || !s_Instance.Active()) { return; }
        HCSearchRefreshRow expired = s_Instance.FindRow(scope, siteId);
        if (!expired || !expired.Ready || expired.Revisited) { return; }
        s_Instance.RemoveReadyTimer(expired);
        s_Instance.HCRequestCheckpoint();
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

    protected void HCReportActivity(bool force = false)
    {
        int timers = -1;
        string stateFault = m_Refusal;
        if (stateFault == "") stateFault = "none";
        if (!m_State) stateFault = "refresh_state_missing";
        else if (!m_State.Rows) stateFault = "refresh_rows_missing";
        else timers = m_State.Rows.Count();
        m_Activity.Report("pending=" + m_Pending.ToString() + " timers=" + timers.ToString() + " last_wait_s=" + m_LastWaitSeconds.ToString() + " checkpoint_pending=" + HCCheckpointPending().ToString() + " healthy=" + Active().ToString() + " state_fault=" + stateFault, force);
    }

    override void OnTick(float deltaTime)
    {
        HCReportActivity();
        if (!Active() || !(deltaTime > 0.0)) return;
        HCSaveScheduler.HCPumpFallback(m_SaveJob);
        HCSearchHouses retirementOwner = HCSearchBinding.Houses();
        if (retirementOwner) { retirementOwner.HCPumpRetirement(); }
        m_Minute += deltaTime;
        HCReached.Mark("search_refresh.tick");
        if (m_Minute >= 60.0 && m_BatchLeft < 1)
        {
            // Discard excess dt rather than doing catch-up bursts. Cursor survives
            // batches; UTC still counts all real downtime between process boots.
            m_Minute = 0.0;
            HCSearchHouses compactOwner = HCSearchBinding.Houses();
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
                m_Activity.Add("checked");
                if (!row.Ready && !HCSearchRefreshPolicy.Due(row.SearchedUtc, now, row.IntervalSeconds))
                {
                    m_Activity.Add("waiting");
                    m_LastWaitSeconds = row.IntervalSeconds - (now - row.SearchedUtc);
                }
                if (!row.Ready && HCSearchRefreshPolicy.Due(row.SearchedUtc, now, row.IntervalSeconds))
                {
                    row.Ready = true;
                    row.Revisited = true;
                    m_Pending--;
                    if (m_Pending == 0) m_LastWaitSeconds = 0;
                    m_Activity.Add("refreshed");
                    HCModuleReadiness.HCUse("LootRefresh", "timer_rearmed");
                    m_BatchChanged = true;
                }
                m_Next++;
                m_BatchLeft = m_BatchLeft - 1;
            }
            if (m_BatchLeft < 1 && m_BatchChanged)
            {
                m_BatchChanged = false;
                m_State.LastUtc = now;
                if (!HCRequestCheckpoint()) return;
            }
        }
    }

    override void OnStop()
    {
        HCReportActivity(true);
        if (m_SaveJob)
        {
            // Same shared large-image barrier used by custody; explicit lower
            // operator limits still fail loudly and leave intent for recovery.
            if (!HCSaveScheduler.HCFlush(m_SaveJob, true)) { m_Store.Fault(); }
            HCSaveScheduler.HCUnregister(m_SaveJob);
            m_SaveJob.Owner = null;
            m_SaveJob = null;
        }
        m_RefreshReservations.Clear();
        if (s_Instance == this) s_Instance = null;
        m_BatchLeft = 0;
        m_BatchChanged = false;
        m_Settings = null;
    }
}

class HCSearchRefreshSaveJob : HCSaveJob
{
    HCSearchRefreshModule Owner;
    override string HCName() { return "SearchRefresh"; }
    override int HCStep()
    {
        if (!Owner) { return HCSaveJob.STEP_FAILED; }
        return Owner.HCCheckpointStep();
    }
}

// A scope pins a world and source pack, so changed template/measurement data never
// borrows another pack's cooldown. Supply journals themselves remain immutable.
modded class HCSearchHouseJournal
{
    protected ref array<int> m_HCCompactIndices = new array<int>;
    protected int m_HCCompactCursor;

    int HCPendingCompactIndex()
    {
        if (m_HCCompactIndices.Count() == 0) { return -1; }
        if (m_HCCompactCursor >= m_HCCompactIndices.Count()) { m_HCCompactCursor = 0; }
        return m_HCCompactIndices[m_HCCompactCursor];
    }
    void HCAdvanceCompact() { m_HCCompactCursor++; }
    bool HCRetirementPending() { return m_Retired && m_Retired.HCPendingCheckpoint(); }
    void HCPumpRetirement()
    {
        HCPumpJob();
        if (m_Retired) { m_Retired.HCPump(); }
    }
    void HCStopRetirement()
    {
        if (m_Retired) { m_Retired.Stop(); }
        HCStopJob();
    }

    override bool Compact(int index)
    {
        HCSearchHouseRow row = Row(index);
        if (!Healthy() || !row || row.Phase < 2) { return false; }
        if (!EnsureRetirement()) { return false; }
        if (m_Retired.Faulted()) { return Fail("retirement checkpoint failed; preserve journal"); }
        int pendingSlot = m_HCCompactIndices.Find(index);
        if (pendingSlot < 0)
        {
            if (m_HCCompactIndices.Count() >= HCSearchLimits.HCGet().CompactRowsPerMinute) { return false; }
            if (TombstonePath(row.SupplyId) == "") { return Fail("unsafe compact supply identity"); }
            if (!m_Job) { return Fail("journal writer unavailable; preserve journal"); }
            // A busy routine queue is not a fault: compaction retries on a later tick.
            // The routine queue is capped (ROUTINE_MAX, a few creates), so a barrier never pays for a backlog;
            // the five cleanup removals are admitted separately by FinishCompaction.
            if (!m_Job.HCRoutineCreateRoom()) { return false; }
            HCSearchRecord intent = Record(row.SiteId, row.SupplyId, row.ItemClass, "retired", row.Phase);
            string intentText;
            if (!EncodeRecord(intent, intentText) || !m_Job.HCQueueCreate(PathFor(index, "compact"), intentText)) { return Fail("compact intent write/readback failed"); }
            m_HCCompactIndices.Insert(index);
            return false;
        }
        // The intent is staged by the shared scheduler. Retirement and cleanup wait until it is durable, so
        // an archive entry can never exist without a compact intent that lets boot finish the slot.
        if (CompactPending(index)) { return false; }
        if (!m_Retired.HCQueueRetirement(row.SupplyId)) { return Fail("retirement queue failed; preserve journal"); }
        // A pending result is cooperative, never a journal fault. The durable
        // compact intent lets boot recovery finish if the process stops here.
        if (m_Retired.HCPendingCheckpoint()) { return false; }
        HCSearchRecord retired = LoadRecord(index, "compact");
        if (!FinishCompaction(index, retired, false)) { return false; }
        m_Rows[index] = null;
        m_HCCompactIndices.RemoveItem(index);
        Reindex();
        return true;
    }

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

modded class HCSearchHouses
{
    protected int m_CompactNext;

    void HCPumpRetirement()
    {
        if (!m_Journal) { return; }
        m_Journal.HCPumpRetirement();
        if (m_Busy || m_Sessions.Count() > 0 || !m_Journal.Healthy() || m_Journal.HCRetirementPending()) { return; }
        int index = m_Journal.HCPendingCompactIndex();
        if (index < 0) { return; }
        // At most one continuation per tick, rotating past a changed admission gate.
        m_Journal.HCAdvanceCompact();
        HCSearchHouseRow row = m_Journal.Row(index);
        if (!row) { return; }
        string scope = m_Journal.RefreshScope();
        if (!HCSearchRefreshModule.Ready(scope, row.SiteId) || !m_Journal.BindingReleased(row.SiteId) || SiteResident(row.SiteId)) { return; }
        HCUnitBudget work = HCServer.HCTickWork();
        if (!work.HCTakeFor(HCUnitBudget.HC_WORK_SEARCH_COMPACT, 1)) { return; }
        if (m_Journal.Compact(index) && !m_Journal.SiteBound(row.SiteId)) { HCSearchRefreshModule.ForgetCompacted(scope, row.SiteId); }
    }
    override void Stop()
    {
        if (m_Journal) { m_Journal.HCStopRetirement(); }
        super.Stop();
    }

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
        if (m_Journal.HCPendingCompactIndex() < 0 && !m_Journal.PruneLegacyTombstones(legacyLimit)) { return; }
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
                if (!m_Journal.Compact(compactIndex))
                {
                    if (!m_Journal.Healthy()) { return; }
                    continue;
                }
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
            if (HCRefreshPreparationAllowed(hit, player) && HCSearchRefreshModule.HCReserveRefresh(scope, hit.SiteId))
            {
                // Bind ignores old SupplyKnown ids, including ambiguous/failed moves.
                // Append only real newly observed supplies; leave all old rows intact.
                int listed = slot.Sites.Find(hit.SiteId);
                if (listed >= 0) slot.Sites.Remove(listed);
                bool rebound = Bind(slot, hit);
                HCSearchRefreshModule.HCRecordBinding(rebound);
                if (rebound)
                {
                    HCSearchRefreshModule.Mark(scope, hit.SiteId);
                    return OpenRow(hit.SiteId, player);
                }
            }
            // Do not fall through to base Bind while the reset is still staged.
            if (HCSearchRefreshModule.HCRefreshReserved(scope, hit.SiteId)) { return -1; }
        }
        return super.Prepare(slot, hit, player);
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

class HCSearchRetirementSaveJob : HCSaveJob
{
    HCSearchRetirementStore Owner;
    override string HCName() { return "SearchRetirement"; }
    override bool HCPendingCheckpoint() { return Owner && Owner.HCPendingCheckpoint(); }
    override int HCStep()
    {
        if (!Owner) { return STEP_FAILED; }
        return Owner.HCStepRetirement();
    }
}
