// Native 1.30.164289: 1_Core/proto/EnSystem.c:397 FileExist, :528 DeleteFile;
// :520-522 FindFile/FindNextFile/CloseFindFile (vanilla VideoPlayer.c:81-93);
// EnString.c:20/113 ToInt/Substring; discovery validates canonical names before use.
// 1_Core/proto/EnScript.c:394 array.Find, :389 array.Set, :463 array.Remove (swaps in the LAST element), :470 RemoveOrdered (FIFO); :852 map.Count.
// 1_Core/proto/EnString.c:199 Length, :240 IndexOf, :448 Get. Existing HCSearchJson owns JSON I/O.
// Sparse active slots retain indices; bounded FIFO/archive tombstones prevent regrant.
// HCSearchRetirementStore in HCSearchRefresh.c owns a maximum of 2048 exact
// tombstones and a fixed monotone archive. Legacy spent files migrate <=32/min.
// Per compaction: <=4096 row reindex, <=2048 recent-id checks, one bounded JSON
// commit; the caller permits <=32 compactions/minute, never per-frame work.
// A compact_<slot> intent survives interruption and finishes cleanup before restore.
// Lazy per-house search journal (contract section 8). Same immutable, bounded record
// discipline as HCSearchEconomyStore (no overwrite or replay of transfer records), but the row set grows as sites bind instead of being fixed by a manifest.
// Wave C: every write/delete runs on the shared HCSaveScheduler through HCSearchJournalJob
// (HCStagedSaveImage BeginNew/BeginRemove: one native call per stage after Begin's two existence
// probes, bytes identical to the former HCSearchJson.WriteNew). Entry/claim/attempt/result writes are synchronous durability
// barriers (queue + HCSaveScheduler.HCFlush, FIFO behind any queued cleanup); compact intent,
// compaction cleanup and legacy spent_* removal are routine staged work. Crash-point table:
// docs/INSTALL_ROLLBACK.md (Search house journal).
//   entry_<n>.json   the bound supply (Phase 0, ActorId "bind")
//   claim_<n>.json   intent before any move (Phase 1)
//   attempt_<n>.json second intent immediately before the single native move (Phase 1)
//   result_<n>.json  2 spent, 3 quarantined, 4 definite no-transfer
// At most 4,096 rows. The root is derived from the SourcePin, so a changed pack starts a
// new journal rather than reusing rows that name other supplies. Readback is not fsync or
// inventory atomicity. Runtime acceptance PENDING.
class HCSearchHouseRow
{
    string SiteId;
    string SupplyId;
    string ItemClass;
    // 0 available, 1 pending, 2 spent, 3 quarantined, 4 definite no-transfer.
    int Phase;
}

class HCSearchHouseJournal
{
    static const int MAX_ENTRIES = 4096;
    static const string BIND_ACTOR = "bind";
    protected string m_Root;
    protected string m_SourceId;
    protected string m_SourcePin;
    protected string m_WorldName;
    protected string m_Build;
    protected bool m_Open;
    protected bool m_Fault;
    protected string m_LastRefusal;
    protected ref array<ref HCSearchHouseRow> m_Rows = new array<ref HCSearchHouseRow>;
    protected ref map<string, int> m_Supplies = new map<string, int>;
    protected ref map<string, int> m_Sites = new map<string, int>;
    protected ref array<string> m_ReleasedSites = new array<string>;
    protected ref HCSearchRetirementStore m_Retired;
    protected ref HCSearchJournalJob m_Job;
    // Legacy spent_<supply>.json names, discovered once during recovery so SupplyKnown never probes the
    // filesystem. Static after recovery: only shrinks as PruneLegacy queues removals.
    static const int LEGACY_MAX = 65536;
    static const int RECORD_LIMIT = 8192;
    protected ref map<string, bool> m_LegacySpent = new map<string, bool>;
    protected int m_LegacyCount;
    protected bool m_LegacyOverflow;

    bool Fail(string reason)
    {
        m_Fault = true;
        HCRefuse(reason);
        return false;
    }

    void HCRefuse(string reason)
    {
        if (m_LastRefusal == reason) { return; }
        m_LastRefusal = reason;
        Print("[HC Search Houses] journal inactive: " + reason + " runtime=PENDING");
    }

    // Recovery owns the journal until every slot and settled-site index is rebuilt.
    // The clock normally ends a slice; the ceiling bounds cheap units too.
    static const int RESTORE_UNITS = 128;
    protected bool m_Recovered;
    protected bool m_RetirementChecked;
    protected int m_RestorePhase;
    protected int m_RestoreNext;
    protected int m_RestoreSteps;
    protected int m_RestoreMaxTicks;
    protected int m_RestoreTotalTicks;
    protected int m_RestoreScanned;
    protected int m_RestoreHighest = -1;
    protected int m_RestoreDiscovered;
    protected int m_RestoreRows;
    protected float m_RestoreOpened;
    protected int m_DiscoveryKind;
    protected bool m_FindOpen;
    protected FindFileHandle m_Find;
    protected string m_FindName;
    protected FileAttr m_FindAttr;
    protected ref map<string, bool> m_RestoreFiles = new map<string, bool>;
    protected ref array<string> m_SettledSites = new array<string>;
    protected ref array<bool> m_SettledFlags = new array<bool>;
    protected ref map<string, int> m_SettledAt = new map<string, int>;
    protected ref HCWorkBudget m_RestoreBudget = new HCWorkBudget;
    protected ref HCStartupHouseRecovery m_StartupRecovery;

    string HCRecoveryScope() { return "main"; }

    bool Healthy() { return m_Open && !m_Fault && m_Recovered; }
    bool Recovering() { return m_Open && !m_Fault && !m_Recovered; }
    bool Faulted() { return m_Fault; }

    void HCStopRecovery()
    {
        if (m_FindOpen) { CloseFindFile(m_Find); m_FindOpen = false; }
        GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).Remove(HCRecoveryTick);
        if (m_StartupRecovery)
        {
            HCStartupPump.HCFinish(m_StartupRecovery);
            m_StartupRecovery.Journal = null;
        }
    }

    void HCRecoveryTick()
    {
        // Pump slices share its frame deadline; the 50 ms fallback runs only
        // after this owner's startup allowance ends (including pump opt-out).
        if (m_StartupRecovery && !m_StartupRecovery.Finished) { return; }
        HCRecoverSlice();
    }

    void HCRecoverSlice()
    {
        if (!Recovering()) { HCStopRecovery(); return; }
        int began = TickCount(0);
        m_RestoreBudget.HCReset(RESTORE_UNITS, HCStartupPump.HCSliceMs(1));
        while (Recovering() && m_RestoreBudget.HCContinue())
        {
            if (!Restore()) { break; }
        }
        int elapsed = TickCount(began);
        m_RestoreSteps++;
        m_RestoreMaxTicks = Math.Max(m_RestoreMaxTicks, elapsed);
        m_RestoreTotalTicks += elapsed;
        if (!Recovering())
        {
            HCStopRecovery();
            float rate = HCWorkBudget.HCTicksPerMs();
            string summary = "[HC Search Houses] recovery scope=" + HCRecoveryScope() + " pass=" + Healthy().ToString() + " slots_scanned=" + m_RestoreScanned.ToString();
            summary += " files=" + m_RestoreDiscovered.ToString() + " rows=" + m_RestoreRows.ToString() + " sites=" + m_Sites.Count().ToString();
            summary += " released_sites=" + m_ReleasedSites.Count().ToString() + " steps=" + m_RestoreSteps.ToString();
            summary += " ms_max=" + ((float)m_RestoreMaxTicks / rate).ToString() + " journal_recovery_ms=" + ((float)m_RestoreTotalTicks / rate).ToString();
            summary += " wall_s=" + Math.Max(0, GetGame().GetTickTime() - m_RestoreOpened).ToString();
            Print("" + summary);
        }
    }
    int Count() { return m_Rows.Count(); }
    int SiteCount() { return m_Sites.Count() - m_ReleasedSites.Count(); }
    HCSearchHouseRow Row(int index)
    {
        if (index < 0 || index >= m_Rows.Count()) return null;
        return m_Rows[index];
    }

    bool SiteBound(string siteId) { return m_Sites.Contains(siteId); }
    bool BindingReleased(string siteId) { return m_ReleasedSites.Find(siteId) >= 0; }
    bool SupplyKnown(string supplyId)
    {
        if (m_Supplies.Contains(supplyId)) { return true; }
        if (m_Retired && m_Retired.Contains(supplyId)) { return true; }
        // Legacy spent_* tombstones were indexed once by recovery: a map lookup, never a per-supply
        // filesystem probe. Past LEGACY_MAX names the index is incomplete, so an unindexed supply is
        // conservatively known (never regranted) until PruneLegacy drains the directory.
        if (TombstonePath(supplyId) == "") { return false; }
        if (m_LegacySpent.Contains(supplyId)) { return true; }
        return m_LegacyOverflow;
    }

    // PruneLegacy calls these. The archive already holds the id before a removal is queued, so
    // dropping the index entry never reopens replay.
    bool HCLegacyRemove(string path, string supplyId)
    {
        if (!m_Job) { return false; }
        // A busy routine queue defers the removal to a later minute; the barrier file stays in place.
        if (m_Job.HCQueued(path) || !m_Job.HCRoutineRoom(1)) { return true; }
        if (!m_Job.HCQueueRemove(path)) { return false; }
        m_LegacySpent.Remove(supplyId);
        return true;
    }

    void HCLegacyDrained()
    {
        m_LegacySpent.Clear();
        m_LegacyOverflow = false;
    }

    string TombstonePath(string supplyId)
    {
        if (!HCSearchRules.TextValid(supplyId, 64)) { return ""; }
        string alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-";
        HCTextWindow identity = new HCTextWindow(supplyId);
        int characterIndex = 0;
        while (characterIndex < identity.Length())
        {
            if (alphabet.IndexOf(identity.At(characterIndex)) < 0) { return ""; }
            characterIndex++;
        }
        return m_Root + "/spent_" + supplyId + ".json";
    }

    bool HasCapacity()
    {
        if (!HCSearchLimits.HCGet().Healthy()) { return false; }
        int liveEntries = m_Supplies.Count();
        if (liveEntries >= HCSearchLimits.HCGet().JournalMaxEntries) { return false; }
        if (m_Rows.Count() < MAX_ENTRIES) { return true; }
        array<ref HCSearchHouseRow> availableRows = m_Rows;
        foreach (HCSearchHouseRow available : availableRows)
        {
            if (!available) { return true; }
        }
        return false;
    }

    bool SiteSettled(string siteId)
    {
        bool found;
        array<ref HCSearchHouseRow> pendingRows = m_Rows;
        foreach (HCSearchHouseRow pending : pendingRows)
        {
            if (!pending || pending.SiteId != siteId) { continue; }
            if (pending.Phase < 2) { return false; }
            found = true;
        }
        return found;
    }

    void ReleaseSite(string siteId)
    {
        if (!SiteSettled(siteId) || m_ReleasedSites.Find(siteId) >= 0) { return; }
        m_ReleasedSites.Insert(siteId);
        Print("[HC Search Houses] spent binding released site=" + siteId);
    }

    bool Open(string sourceId, string sourcePin, string worldName, string build)
    {
        if (m_Open || m_Fault || !GetGame().IsServer()) return false;
        if (!HCSearchLimits.HCGet().Healthy()) { return Fail("search limits invalid"); }
        if (!HCSearchRules.TextValid(sourceId, 128) || !HCSearchRules.PinValid(sourcePin)) return Fail("invalid source id or pin");
        if (!HCSearchRules.TextValid(worldName, 128) || !HCSearchRules.TextValid(build, 64)) return Fail("invalid world or build");
        // PinValid above admits only 64-character pins; consult Length() here so the 16-character slice is locally bounded.
        if (sourcePin.Length() < 16) return Fail("invalid source id or pin");
        m_SourceId = sourceId;
        m_SourcePin = sourcePin;
        m_WorldName = worldName;
        m_Build = build;
        string parent = "$profile:HollowCountry";
        if (!FileExist(parent) && !MakeDirectory(parent)) return Fail("profile parent unavailable");
        parent = parent + "/SearchHouses";
        if (!FileExist(parent) && !MakeDirectory(parent)) return Fail("search houses profile unavailable");
        m_Root = parent + "/pin_" + sourcePin.Substring(0, 16);
        if (!FileExist(m_Root) && !MakeDirectory(m_Root)) return Fail("journal directory unavailable");
        m_Job = new HCSearchJournalJob;
        m_Job.Owner = this;
        m_Open = true;
        m_RestoreOpened = GetGame().GetTickTime();
        m_StartupRecovery = new HCStartupHouseRecovery;
        m_StartupRecovery.Journal = this;
        string recoveryOwner = "search_house_recovery";
        if (HCRecoveryScope() == "pilot") { recoveryOwner = "search_house_recovery_pilot"; }
        HCStartupPump.HCRegister(m_StartupRecovery, recoveryOwner);
        GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(HCRecoveryTick, 50, true);
        return true;
    }

    string PathFor(int index, string kind)
    {
        if (index < 0 || index >= MAX_ENTRIES) return "";
        bool transferKind = kind == "entry" || kind == "claim" || kind == "attempt";
        bool terminalKind = kind == "result" || kind == "compact";
        if (!transferKind && !terminalKind) { return ""; }
        return m_Root + "/" + kind + "_" + index.ToString() + ".json";
    }

    HCSearchRecord Record(string siteId, string supplyId, string itemClass, string actorId, int phase)
    {
        HCSearchRecord record = new HCSearchRecord;
        record.Version = 1;
        record.Epoch = 1;
        record.WorldName = m_WorldName;
        record.Build = m_Build;
        record.SourceId = m_SourceId;
        record.SourcePin = m_SourcePin;
        record.SiteId = siteId;
        record.SupplyId = supplyId;
        record.ItemClass = itemClass;
        record.ActorId = actorId;
        record.Phase = phase;
        return record;
    }

    bool Matches(HCSearchRecord record, HCSearchHouseRow row)
    {
        if (!record || !row || record.Version != 1 || record.Epoch != 1) return false;
        if (record.WorldName != m_WorldName || record.Build != m_Build) return false;
        if (record.SourceId != m_SourceId || record.SourcePin != m_SourcePin) return false;
        if (record.SiteId != row.SiteId || record.SupplyId != row.SupplyId || record.ItemClass != row.ItemClass) return false;
        return HCSearchRules.TextValid(record.ActorId, 128);
    }

    HCSearchRecord LoadRecord(int index, string kind)
    {
        HCSearchRecord record;
        if (!HCSearchJson<HCSearchRecord>.Load(PathFor(index, kind), 8192, record)) return null;
        return record;
    }

    // Same terminal semantics as HCSearchEconomyStore.Recover: any trace of an intent
    // without a matching successful result is spent for good.
    int Recover(int index, HCSearchHouseRow row)
    {
        bool claimExists = FileExist(PathFor(index, "claim"));
        bool attemptExists = FileExist(PathFor(index, "attempt"));
        bool resultExists = FileExist(PathFor(index, "result"));
        if (!claimExists && !attemptExists && !resultExists) return 0;
        HCSearchRecord claim = LoadRecord(index, "claim");
        if (!claimExists || !Matches(claim, row) || claim.Phase != 1) return 3;
        if (attemptExists)
        {
            HCSearchRecord attempt = LoadRecord(index, "attempt");
            if (!Matches(attempt, row) || attempt.Phase != 1 || attempt.ActorId != claim.ActorId) return 3;
        }
        if (!resultExists) return 3;
        HCSearchRecord result = LoadRecord(index, "result");
        if (!Matches(result, row) || result.ActorId != claim.ActorId) return 3;
        if (result.Phase == 4) return 4;
        if (result.Phase == 2 && attemptExists) return 2;
        return 3;
    }

    protected void Track(HCSearchHouseRow row)
    {
        int index = m_Rows.Find(null);
        if (index < 0)
        {
            index = m_Rows.Count();
            m_Rows.Insert(row);
        }
        else { m_Rows[index] = row; }
        int releasedIndex = m_ReleasedSites.Find(row.SiteId);
        if (releasedIndex >= 0) { m_ReleasedSites.Remove(releasedIndex); }
        m_Supplies.Set(row.SupplyId, index);
        int perSite = 0;
        m_Sites.Find(row.SiteId, perSite);
        m_Sites.Set(row.SiteId, perSite + 1);
    }

    bool EncodeRecord(HCSearchRecord record, out string text)
    {
        string error;
        if (!JsonFileLoader<HCSearchRecord>.MakeData(record, text, error)) { return false; }
        return text.Length() >= 1 && text.Length() <= RECORD_LIMIT;
    }

    // Durability barrier: the record is on disk and read back, or this returns false. Runs on the shared
    // scheduler job and drains any earlier queued cleanup first (FIFO), so a reused slot never meets a
    // stale file. Never retried; failure is a journal fault with the caller's reason.
    protected bool CommitRecord(string path, HCSearchRecord record, string reason)
    {
        string text;
        if (!m_Job || path == "" || !EncodeRecord(record, text)) { return Fail(reason); }
        // Routine producers stop at HCSearchJournalJob.ROUTINE_MAX, so a barrier normally finds room. A full
        // queue is drained first instead of faulting a player claim.
        if (!m_Job.HCRoom(1) && !HCSaveScheduler.HCFlush(m_Job)) { return Fail(reason); }
        if (!m_Job.HCQueueCreate(path, text)) { return Fail(reason); }
        if (!HCSaveScheduler.HCFlush(m_Job)) { return Fail(reason); }
        return true;
    }

    // Recovery-only synchronous removal of one exact file (torn intent or torn entry).
    protected bool HCRemoveNow(string path, string reason)
    {
        if (!m_Job || path == "" || !m_Job.HCQueueRemove(path)) { return Fail(reason); }
        if (!HCSaveScheduler.HCFlush(m_Job)) { return Fail(reason); }
        return true;
    }

    // Called by the job when a staged write/remove failed. Same fail-closed outcome as the former direct write.
    void HCJobFailed(string operation)
    {
        Fail("journal stage failed op=" + operation + "; no retries, preserve journal");
    }

    void HCPumpJob() { if (m_Job) { HCSaveScheduler.HCPumpFallback(m_Job); } }

    // Shutdown: finish queued cleanup before the owner lets go of the journal. The job stays registered
    // while idle (see HCDrained), so this explicit unregister releases its scheduler slot.
    void HCStopJob()
    {
        if (!m_Job) { return; }
        if (!m_Fault && !HCSaveScheduler.HCFlush(m_Job)) { m_Fault = true; }
        HCSaveScheduler.HCUnregister(m_Job);
        m_Job.Owner = null;
        m_Job = null;
    }

    bool CompactPending(int index) { return m_Job && m_Job.HCQueued(PathFor(index, "compact")); }

    // barrier=true (boot recovery, base Compact): cleanup finishes before return.
    // barrier=false (routine): the five removals are queued in order, compact intent last; a crash at any
    // point leaves compact_<n> in place, and boot recovery re-runs this same cleanup.
    bool FinishCompaction(int index, HCSearchRecord retired, bool barrier = true)
    {
        HCSearchHouseRow retiredRow = new HCSearchHouseRow;
        if (!retired) { return Fail("unreadable compact intent; preserve journal"); }
        retiredRow.SiteId = retired.SiteId;
        retiredRow.SupplyId = retired.SupplyId;
        retiredRow.ItemClass = retired.ItemClass;
        if (!Matches(retired, retiredRow) || retired.ActorId != "retired") { return Fail("compact identity changed"); }
        if (retired.Phase < 2 || retired.Phase > 4) { return Fail("nonterminal compact intent"); }
        if (TombstonePath(retired.SupplyId) == "") { return Fail("unsafe retired supply identity"); }
        if (!EnsureRetirement()) { return false; }
        if (!m_Job) { return Fail("journal writer unavailable; preserve journal"); }
        // A busy routine queue is not a fault: the routine caller retries once the scheduler has drained it.
        if (!barrier && !m_Job.HCRoutineRoom(5)) { return false; }
        if (barrier && !m_Job.HCRoom(5) && !HCSaveScheduler.HCFlush(m_Job)) { return Fail("compact cleanup failed"); }
        // Durable conservative identity barrier BEFORE destroying any transfer row.
        if (!m_Retired.Retire(retired.SupplyId)) { return Fail("retirement commit failed; preserve journal"); }
        if (!m_Job.HCQueueRemove(PathFor(index, "claim"))) { return Fail("compact claim cleanup failed"); }
        if (!m_Job.HCQueueRemove(PathFor(index, "attempt"))) { return Fail("compact attempt cleanup failed"); }
        if (!m_Job.HCQueueRemove(PathFor(index, "result"))) { return Fail("compact result cleanup failed"); }
        if (!m_Job.HCQueueRemove(PathFor(index, "entry"))) { return Fail("compact entry cleanup failed"); }
        if (!m_Job.HCQueueRemove(PathFor(index, "compact"))) { return Fail("compact intent cleanup failed"); }
        if (barrier && !HCSaveScheduler.HCFlush(m_Job)) { return Fail("compact cleanup failed"); }
        return true;
    }

    bool EnsureRetirement()
    {
        if (m_Retired) { return true; }
        m_Retired = new HCSearchRetirementStore;
        if (!m_Retired.Open(m_Root)) { return Fail("retirement archive unavailable; preserve journal"); }
        return true;
    }

    bool PruneLegacyTombstones(int limit)
    {
        if (!Healthy() || limit < 1 || limit > HCSearchLimits.HCGet().LegacyFilesPerMinute) { return false; }
        if (!EnsureRetirement()) { return false; }
        if (!m_Retired.PruneLegacy(this, limit)) { return Fail("legacy tombstone migration failed; preserve journal"); }
        return true;
    }

    void Reindex()
    {
        m_Supplies.Clear();
        m_Sites.Clear();
        int rowIndex = 0;
        int perSite;
        while (rowIndex < m_Rows.Count())
        {
            HCSearchHouseRow liveRow = m_Rows[rowIndex];
            if (liveRow)
            {
                m_Supplies.Set(liveRow.SupplyId, rowIndex);
                perSite = 0;
                m_Sites.Find(liveRow.SiteId, perSite);
                m_Sites.Set(liveRow.SiteId, perSite + 1);
            }
            rowIndex++;
        }
        int releasedIndex = m_ReleasedSites.Count() - 1;
        while (releasedIndex >= 0)
        {
            if (!m_Sites.Contains(m_ReleasedSites[releasedIndex])) { m_ReleasedSites.Remove(releasedIndex); }
            releasedIndex = releasedIndex - 1;
        }
    }

    // Discover the five legacy record kinds plus the legacy spent_* tombstone names, incrementally. No format
    // change: all sparse old records and orphan intents contribute to the discovered
    // high-water slot. Restore through that slot, then probe the remaining entry
    // paths too: discovery may have missed the highest file or every file.
    protected string HCDiscoveryKind()
    {
        if (m_DiscoveryKind == 0) { return "compact"; }
        if (m_DiscoveryKind == 1) { return "entry"; }
        if (m_DiscoveryKind == 2) { return "claim"; }
        if (m_DiscoveryKind == 3) { return "attempt"; }
        if (m_DiscoveryKind == 4) { return "result"; }
        return "spent";
    }

    protected void HCDiscoverRecord()
    {
        string kind = HCDiscoveryKind();
        if (!m_FindOpen)
        {
            m_FindName = "";
            m_Find = FindFile(m_Root + "/" + kind + "_*.json", m_FindName, m_FindAttr, FindFileFlags.DIRECTORIES);
            m_FindOpen = true;
        }
        else if (!FindNextFile(m_Find, m_FindName, m_FindAttr)) { m_FindName = ""; }
        if (m_FindName == "")
        {
            CloseFindFile(m_Find);
            m_FindOpen = false;
            m_DiscoveryKind++;
            if (m_DiscoveryKind == 6) { m_RestorePhase = 1; }
            return;
        }
        int prefix = kind.Length() + 1;
        if (kind == "spent")
        {
            // Legacy tombstone: spent_<supply>.json, indexed by supply id (names only, no file reads).
            int idLength = m_FindName.Length() - prefix - 5;
            if (idLength < 1 || idLength > 64) { return; }
            string legacyId = m_FindName.Substring(prefix, idLength);
            if (TombstonePath(legacyId) == "" || m_FindName != "spent_" + legacyId + ".json") { return; }
            m_LegacyCount++;
            if (m_LegacyCount > LEGACY_MAX) { m_LegacyOverflow = true; return; }
            m_LegacySpent.Set(legacyId, true);
            return;
        }
        int digits = m_FindName.Length() - prefix - 5;
        if (digits < 1 || digits > 4) { return; }
        int slot = m_FindName.Substring(prefix, digits).ToInt();
        if (slot < 0 || slot >= MAX_ENTRIES) { return; }
        if (m_FindName != kind + "_" + slot.ToString() + ".json") { return; }
        m_RestoreFiles.Set(m_FindName, true);
        m_RestoreDiscovered++;
        m_RestoreHighest = Math.Max(m_RestoreHighest, slot);
    }

    protected bool HCRestorePresent(int index, string kind)
    {
        return m_RestoreFiles.Contains(kind + "_" + index.ToString() + ".json");
    }

    // Recovery duplicate check. Past LEGACY_MAX names the in-memory index is incomplete and SupplyKnown
    // answers true for everything, which would flag every live entry; probe the exact tombstone instead.
    // The overflow path skips the virtual SupplyKnown override (the pilot journal's catalog check); that
    // is harmless while the pilot is retired.
    protected bool HCRestoreKnown(string supplyId)
    {
        if (!m_LegacyOverflow) { return SupplyKnown(supplyId); }
        if (m_Supplies.Contains(supplyId)) { return true; }
        if (m_Retired && m_Retired.Contains(supplyId)) { return true; }
        string tombstone = TombstonePath(supplyId);
        if (tombstone == "") { return false; }
        return m_LegacySpent.Contains(supplyId) || FileExist(tombstone);
    }

    // A bound entry that passes every check boot applies (phase 0, bind actor, identity, text limits),
    // or null. Never mutates the journal.
    protected HCSearchHouseRow HCValidEntryRow(HCSearchRecord candidate)
    {
        if (!candidate || candidate.Phase != 0 || candidate.ActorId != BIND_ACTOR) { return null; }
        HCSearchHouseRow validRow = new HCSearchHouseRow;
        validRow.SiteId = candidate.SiteId;
        validRow.SupplyId = candidate.SupplyId;
        validRow.ItemClass = candidate.ItemClass;
        bool textOk = HCSearchRules.TextValid(validRow.SiteId, 768) && HCSearchRules.TextValid(validRow.SupplyId, 64);
        if (!Matches(candidate, validRow) || !textOk || !HCSearchRules.TextValid(validRow.ItemClass, 128)) { return null; }
        return validRow;
    }

    protected bool HCRestoreSlot(int index)
    {
        // Search is refused and no compaction/binding writes run during recovery.
        // A directory miss must never silently turn a recorded entry into free stock.
        bool entryExists = FileExist(PathFor(index, "entry"));
        if (entryExists != HCRestorePresent(index, "entry")) { return Fail("entry discovery mismatch; preserve journal"); }
        bool tornIntent = false;
        if (HCRestorePresent(index, "compact"))
        {
            HCSearchRecord compactedRecord = LoadRecord(index, "compact");
            // A torn compact_<n> (crash while the intent was being created) is harmless when the entry is
            // intact: removals are queued only after the intent was read back, so nothing of the slot was
            // removed. Only an unreadable intent AND an unreadable or missing entry is preserved as a fault.
            // The entry must pass every boot check and its supply must not already be recorded: if the
            // supply is archived the intent was durable and merely failed to read, so compact_<n> is KEPT
            // (nothing deleted, the next boot retries) rather than turned into a permanent fault.
            HCSearchHouseRow intentRow;
            HCSearchRecord intentEntry;
            if (!compactedRecord && HCRestorePresent(index, "entry"))
            {
                intentEntry = LoadRecord(index, "entry");
                intentRow = HCValidEntryRow(intentEntry);
            }
            bool entryIntact = intentRow != null;
            if (entryIntact && HCRestoreKnown(intentRow.SupplyId)) { return Fail("compact intent unreadable and supply already recorded; preserve journal"); }
            if (compactedRecord || !entryIntact)
            {
                if (!FinishCompaction(index, compactedRecord)) { return false; }
                // Cleanup removed every transfer file for this slot. The directory
                // snapshot must never resurrect its now-retired entry.
                m_Rows.Insert(null);
                return true;
            }
            if (!HCRemoveNow(PathFor(index, "compact"), "torn compact intent cleanup failed; preserve journal")) { return false; }
            tornIntent = true;
            Print("[HC Search Houses] torn compact intent removed slot=" + index.ToString() + "; row restored as terminal");
        }
        if (!HCRestorePresent(index, "entry"))
        {
            bool orphanIntent = HCRestorePresent(index, "claim") || HCRestorePresent(index, "attempt");
            if (orphanIntent || HCRestorePresent(index, "result")) { return Fail("orphan transfer record; preserve journal"); }
            m_Rows.Insert(null);
            return true;
        }
        HCSearchRecord record = LoadRecord(index, "entry");
        if (!record)
        {
            // A torn entry with no claim, attempt or result was never handed out (the create is a barrier
            // and the claim follows it): drop it and treat the slot as free instead of faulting for good.
            // The directory snapshot can miss files, so probe each sibling by exact name before deleting.
            bool hasIntent = HCRestorePresent(index, "claim") || HCRestorePresent(index, "attempt") || HCRestorePresent(index, "result") || HCRestorePresent(index, "compact");
            if (!hasIntent) { hasIntent = FileExist(PathFor(index, "claim")) || FileExist(PathFor(index, "attempt")); }
            if (!hasIntent) { hasIntent = FileExist(PathFor(index, "result")) || FileExist(PathFor(index, "compact")); }
            if (hasIntent) { return Fail("stored entry unreadable; preserve journal"); }
            if (!HCRemoveNow(PathFor(index, "entry"), "torn entry cleanup failed; preserve journal")) { return false; }
            Print("[HC Search Houses] torn entry removed slot=" + index.ToString() + "; slot free, supply never handed out");
            m_Rows.Insert(null);
            return true;
        }
        if (record.Phase != 0 || record.ActorId != BIND_ACTOR) { return Fail("stored entry unreadable; preserve journal"); }
        HCSearchHouseRow row = HCValidEntryRow(record);
        if (!row) { return Fail("stored entry identity changed; migration required"); }
        if (HCRestoreKnown(row.SupplyId)) { return Fail("stored supply listed twice; preserve journal"); }
        row.Phase = Recover(index, row);
        // A compact intent exists only for a terminal row; no transfer files left means the intent was
        // complete after all, so the row is quarantined (spent for good), never available.
        if (tornIntent && row.Phase < 2) { row.Phase = 3; }
        m_Rows.Insert(row);
        m_RestoreRows++;
        m_Supplies.Set(row.SupplyId, index);
        return true;
    }

    // ONE discovery/slot/index/site operation per shared budget unit. During
    // restore no binding/compaction can run, so indexes are built once in order.
    protected bool Restore()
    {
        if (!m_RetirementChecked)
        {
            m_RetirementChecked = true;
            // Attribute the existing bounded archive read/validation to recovery
            // as well. Preserve refusal of partial archive commits on old saves.
            bool retiredExists = FileExist(m_Root + "/retired.json");
            bool retiredIntent = FileExist(m_Root + "/retired.json.tmp");
            bool retiredBackup = FileExist(m_Root + "/retired.json.bak");
            if (retiredExists || retiredIntent || retiredBackup) { return EnsureRetirement(); }
            return true;
        }
        if (m_RestorePhase == 0) { HCDiscoverRecord(); return true; }
        if (m_RestorePhase == 1)
        {
            if (m_RestoreNext < MAX_ENTRIES)
            {
                int slotIndex = m_RestoreNext;
                m_RestoreNext++;
                m_RestoreScanned++;
                if (slotIndex <= m_RestoreHighest) { return HCRestoreSlot(slotIndex); }
                // One existence probe per budget unit, without extending the
                // sparse row array. An undiscovered entry must never grant stock.
                if (FileExist(PathFor(slotIndex, "entry"))) { return Fail("discovery_incomplete; preserve journal"); }
                return true;
            }
            m_RestoreNext = 0;
            m_RestorePhase = 3;
            return true;
        }
        if (m_RestorePhase == 3)
        {
            if (m_RestoreNext < m_Rows.Count())
            {
                HCSearchHouseRow restored = m_Rows[m_RestoreNext];
                m_RestoreNext++;
                if (!restored) { return true; }
                int perSite = 0;
                m_Sites.Find(restored.SiteId, perSite);
                m_Sites.Set(restored.SiteId, perSite + 1);
                int siteAt = -1;
                if (!m_SettledAt.Find(restored.SiteId, siteAt))
                {
                    m_SettledAt.Set(restored.SiteId, m_SettledSites.Count());
                    m_SettledSites.Insert(restored.SiteId);
                    m_SettledFlags.Insert(restored.Phase >= 2);
                }
                else { m_SettledFlags[siteAt] = m_SettledFlags[siteAt] && restored.Phase >= 2; }
                return true;
            }
            m_RestoreNext = 0;
            m_RestorePhase = 4;
            return true;
        }
        if (m_RestoreNext < m_SettledSites.Count())
        {
            if (m_SettledFlags[m_RestoreNext]) { m_ReleasedSites.Insert(m_SettledSites[m_RestoreNext]); }
            m_RestoreNext++;
            return true;
        }
        m_Recovered = true;
        return true;
    }

    // Caller excludes sessions/transfers, forgets registry handles and checks refresh age.
    bool Compact(int index)
    {
        HCSearchHouseRow row = Row(index);
        if (!Healthy() || !row || row.Phase < 2) { return false; }
        string spentPath = TombstonePath(row.SupplyId);
        if (spentPath == "") { return Fail("unsafe compact supply identity"); }
        HCSearchRecord retired = Record(row.SiteId, row.SupplyId, row.ItemClass, "retired", row.Phase);
        // Intent precedes tombstone creation, so restart can finish either stage.
        if (!CommitRecord(PathFor(index, "compact"), retired, "compact intent write/readback failed")) { return false; }
        if (!FinishCompaction(index, retired)) { return false; }
        m_Rows[index] = null;
        Reindex();
        Print("[HC Search Houses] journal compacted terminal supply=" + row.SupplyId);
        return true;
    }

    // Journal a freshly observed supply. False means nothing was recorded and the caller
    // must not register or hand out that supply.
    bool Add(string siteId, string supplyId, string itemClass)
    {
        if (!Healthy() || !HasCapacity()) { return false; }
        if (!HCSearchRules.TextValid(siteId, 768) || !HCSearchRules.TextValid(supplyId, 64) || !HCSearchRules.TextValid(itemClass, 128)) return false;
        if (SupplyKnown(supplyId)) return false;
        HCSearchHouseRow row = new HCSearchHouseRow;
        row.SiteId = siteId;
        row.SupplyId = supplyId;
        row.ItemClass = itemClass;
        int index = m_Rows.Find(null);
        if (index < 0) { index = m_Rows.Count(); }
        string entryPath = PathFor(index, "entry");
        HCSearchRecord entryRecord = Record(siteId, supplyId, itemClass, BIND_ACTOR, 0);
        if (!CommitRecord(entryPath, entryRecord, "entry write/readback failed; no retries")) return false;
        Track(row);
        return true;
    }

    bool Write(int index, string kind, string actorId, int phase)
    {
        HCSearchHouseRow row = Row(index);
        if (!Healthy() || !row) return false;
        if (kind != "claim" && kind != "attempt" && kind != "result") return Fail("invalid journal kind");
        if (kind == "result")
        {
            if (phase != 2 && phase != 3 && phase != 4) return Fail("invalid result phase");
        }
        else if (phase != 1) return Fail("invalid intent phase");
        if (!HCSearchRules.TextValid(actorId, 128)) return Fail("invalid actor id");
        string writePath = PathFor(index, kind);
        HCSearchRecord writeRecord = Record(row.SiteId, row.SupplyId, row.ItemClass, actorId, phase);
        if (!CommitRecord(writePath, writeRecord, "write/readback failed; no retries")) return false;
        return true;
    }

    void SetPhase(int index, int phase)
    {
        HCSearchHouseRow row = Row(index);
        if (row) row.Phase = phase;
    }
}

// Journal file operations on the shared HCSaveScheduler. A bounded FIFO of exact-path operations:
// create-new (immutable record, BeginNew) or remove (BeginRemove, an absent file is already done).
// Exactly one HCStagedSaveImage operation is in flight; each scheduler stage performs ONE native call
// (open, <=4096-byte transfer, close, existence probe or delete; Begin adds two existence probes to the
// first stage). FIFO order is the ordering contract (pops use RemoveOrdered; array.Remove would move
// the LAST element into the gap):
// compaction removes a slot's claim, attempt, result, entry and finally compact_<n>, and a reused slot's
// new entry is queued behind those removals. Barriers drain this queue through HCSaveScheduler.HCFlush.
class HCSearchJournalJob : HCSaveJob
{
    // Hard ceiling, reached only by a barrier. Routine producers (compact intent, compaction removals,
    // legacy tombstone removals) stop at ROUTINE_MAX queued ops and ROUTINE_CREATES queued creates, so a
    // barrier that drains the whole queue inside a player action pays at most about 70 native calls
    // (a remove is 2, a create about 8) and a caller never meets a full queue.
    static const int MAX_OPS = 256;
    static const int ROUTINE_MAX = 16;
    static const int ROUTINE_CREATES = 3;
    HCSearchHouseJournal Owner;
    protected ref array<string> m_Paths = new array<string>;
    protected ref array<string> m_Texts = new array<string>;
    protected ref map<string, int> m_Queued = new map<string, int>;
    protected ref HCStagedSaveImage m_Image = new HCStagedSaveImage;
    protected int m_Creates;
    protected bool m_Registered;

    override string HCName() { return "SearchJournal"; }
    override bool HCPendingCheckpoint() { return m_Paths.Count() > 0; }

    bool HCQueued(string path) { return m_Queued.Contains(path); }
    bool HCRoom(int count) { return m_Paths.Count() + count <= MAX_OPS; }
    bool HCRoutineRoom(int count) { return m_Paths.Count() + count <= ROUTINE_MAX; }
    bool HCRoutineCreateRoom() { return m_Creates < ROUTINE_CREATES && HCRoutineRoom(1); }

    protected bool HCEnqueue(string path, string text)
    {
        if (path == "" || path.Length() > 256 || !HCRoom(1)) { return false; }
        m_Paths.Insert(path);
        m_Texts.Insert(text);
        int queued = 0;
        m_Queued.Find(path, queued);
        m_Queued.Set(path, queued + 1);
        if (text != "") { m_Creates++; }
        HCDirty = true;
        HCUrgent = true;
        // Registered once, on the first write, and kept for the journal's life: later enqueue/drain churn
        // never touches the scheduler's SaveJobLimit, so it cannot latch save_job_capacity. A refused
        // registration still advances through HCPumpFallback.
        if (!m_Registered)
        {
            m_Registered = true;
            HCSaveScheduler.HCRegister(this);
        }
        return true;
    }

    bool HCQueueCreate(string path, string text)
    {
        if (text.Length() < 1 || text.Length() > HCSearchHouseJournal.RECORD_LIMIT) { return false; }
        return HCEnqueue(path, text);
    }

    bool HCQueueRemove(string path) { return HCEnqueue(path, ""); }

    protected int HCFailStep(string operation)
    {
        if (Owner) { Owner.HCJobFailed(operation); }
        return STEP_FAILED;
    }

    protected void HCPopHead()
    {
        string path = m_Paths[0];
        int queued = 0;
        m_Queued.Find(path, queued);
        if (queued > 1) { m_Queued.Set(path, queued - 1); }
        else { m_Queued.Remove(path); }
        if (m_Texts[0] != "" && m_Creates > 0) { m_Creates--; }
        // Ordered removal: array.Remove would move the LAST element into slot 0 and break FIFO.
        m_Paths.RemoveOrdered(0);
        m_Texts.RemoveOrdered(0);
    }

    // The job stays registered while idle (a clean job is skipped by the scheduler), so a drain never
    // reorders the scheduler's job list mid-tick.
    protected int HCDrained() { return STEP_DONE; }

    override int HCStep()
    {
        if (m_Paths.Count() == 0) { return HCDrained(); }
        string operation = "create";
        if (m_Texts[0] == "") { operation = "remove"; }
        if (!m_Image.Active())
        {
            bool began;
            if (operation == "remove") { began = m_Image.BeginRemove(m_Paths[0]); }
            else { began = m_Image.BeginNew(m_Paths[0], m_Texts[0], HCSearchHouseJournal.RECORD_LIMIT); }
            if (!began) { return HCFailStep(operation + "_begin"); }
        }
        int result = m_Image.HCStepImage();
        if (result == STEP_FAILED) { return HCFailStep(operation); }
        if (result == STEP_DONE)
        {
            HCPopHead();
            if (m_Paths.Count() == 0) { return HCDrained(); }
        }
        return STEP_MORE;
    }
}
