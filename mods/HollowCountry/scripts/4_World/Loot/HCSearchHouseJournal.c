// Native 1.30.164289: 1_Core/proto/EnSystem.c:397 FileExist, :528 DeleteFile;
// :520-522 FindFile/FindNextFile/CloseFindFile (vanilla VideoPlayer.c:81-93);
// EnString.c:20/113 ToInt/Substring; discovery validates canonical names before use.
// 1_Core/proto/EnScript.c:394 array.Find, :389 array.Set, :463 array.Remove; :852 map.Count.
// 1_Core/proto/EnString.c:199 Length, :240 IndexOf, :448 Get. Existing HCSearchJson owns JSON I/O.
// Sparse active slots retain indices; bounded FIFO/archive tombstones prevent regrant.
// HCSearchRetirementStore in HCSearchRefresh.c owns a maximum of 2048 exact
// tombstones and a fixed monotone archive. Legacy spent files migrate <=32/min.
// Per compaction: <=4096 row reindex, <=2048 recent-id checks, one bounded JSON
// commit; the caller permits <=32 compactions/minute, never per-frame work.
// A compact_<slot> intent survives interruption and finishes cleanup before restore.
// Lazy per-house search journal (contract section 8). Same immutable, bounded record
// discipline as HCSearchEconomyStore (HCSearchJson.WriteNew, no overwrite or replay of transfer records), but the row set grows as sites bind instead of being fixed by a manifest.
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
    static const int RESTORE_UNITS = 8;
    protected bool m_Recovered;
    protected bool m_RetirementChecked;
    protected int m_RestorePhase;
    protected int m_RestoreNext;
    protected int m_RestoreSteps;
    protected int m_RestoreMaxTicks;
    protected int m_RestoreTotalTicks;
    protected int m_RestoreScanned;
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
            string summary = "[HC Search Houses] recovery pass=" + Healthy().ToString() + " slots_scanned=" + m_RestoreScanned.ToString() + " steps=" + m_RestoreSteps.ToString();
            summary += " ms_max=" + ((float)m_RestoreMaxTicks / rate).ToString() + " journal_recovery_ms=" + ((float)m_RestoreTotalTicks / rate).ToString();
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
        // One validated existence probe, independent of legacy directory size.
        string legacyPath = TombstonePath(supplyId);
        return legacyPath != "" && FileExist(legacyPath);
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
        m_Open = true;
        m_StartupRecovery = new HCStartupHouseRecovery;
        m_StartupRecovery.Journal = this;
        HCStartupPump.HCRegister(m_StartupRecovery, "search_house_recovery");
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

    bool DeleteIfPresent(string path)
    {
        if (!FileExist(path)) { return true; }
        return DeleteFile(path);
    }

    bool FinishCompaction(int index, HCSearchRecord retired)
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
        // Durable conservative identity barrier BEFORE destroying any transfer row.
        if (!m_Retired.Retire(retired.SupplyId)) { return Fail("retirement commit failed; preserve journal"); }
        if (!DeleteIfPresent(PathFor(index, "claim"))) { return Fail("compact claim cleanup failed"); }
        if (!DeleteIfPresent(PathFor(index, "attempt"))) { return Fail("compact attempt cleanup failed"); }
        if (!DeleteIfPresent(PathFor(index, "result"))) { return Fail("compact result cleanup failed"); }
        if (!DeleteIfPresent(PathFor(index, "entry"))) { return Fail("compact entry cleanup failed"); }
        if (!DeleteIfPresent(PathFor(index, "compact"))) { return Fail("compact intent cleanup failed"); }
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

    // Discover only the five legacy record kinds, incrementally. No format
    // change/high-water assumption: sparse old journals and orphan intents are
    // still inspected all the way to MAX_ENTRIES. Empty slots need no FileExist.
    protected string HCDiscoveryKind()
    {
        if (m_DiscoveryKind == 0) { return "compact"; }
        if (m_DiscoveryKind == 1) { return "entry"; }
        if (m_DiscoveryKind == 2) { return "claim"; }
        if (m_DiscoveryKind == 3) { return "attempt"; }
        return "result";
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
            if (m_DiscoveryKind == 5) { m_RestorePhase = 1; }
            return;
        }
        int prefix = kind.Length() + 1;
        int digits = m_FindName.Length() - prefix - 5;
        if (digits < 1 || digits > 4) { return; }
        int slot = m_FindName.Substring(prefix, digits).ToInt();
        if (slot < 0 || slot >= MAX_ENTRIES) { return; }
        if (m_FindName != kind + "_" + slot.ToString() + ".json") { return; }
        m_RestoreFiles.Set(m_FindName, true);
    }

    protected bool HCRestorePresent(int index, string kind)
    {
        return m_RestoreFiles.Contains(kind + "_" + index.ToString() + ".json");
    }

    protected bool HCRestoreSlot(int index)
    {
        if (HCRestorePresent(index, "compact"))
        {
            HCSearchRecord compactedRecord = LoadRecord(index, "compact");
            if (!FinishCompaction(index, compactedRecord)) { return false; }
            // Cleanup removed every transfer file for this slot. The directory
            // snapshot must never resurrect its now-retired entry.
            m_Rows.Insert(null);
            return true;
        }
        if (!HCRestorePresent(index, "entry"))
        {
            bool orphanIntent = HCRestorePresent(index, "claim") || HCRestorePresent(index, "attempt");
            if (orphanIntent || HCRestorePresent(index, "result")) { return Fail("orphan transfer record; preserve journal"); }
            m_Rows.Insert(null);
            return true;
        }
        HCSearchRecord record = LoadRecord(index, "entry");
        if (!record || record.Phase != 0 || record.ActorId != BIND_ACTOR) { return Fail("stored entry unreadable; preserve journal"); }
        HCSearchHouseRow row = new HCSearchHouseRow;
        row.SiteId = record.SiteId;
        row.SupplyId = record.SupplyId;
        row.ItemClass = record.ItemClass;
        bool validText = HCSearchRules.TextValid(row.SiteId, 768) && HCSearchRules.TextValid(row.SupplyId, 64);
        if (!Matches(record, row) || !validText || !HCSearchRules.TextValid(row.ItemClass, 128)) { return Fail("stored entry identity changed; migration required"); }
        if (SupplyKnown(row.SupplyId)) { return Fail("stored supply listed twice; preserve journal"); }
        row.Phase = Recover(index, row);
        m_Rows.Insert(row);
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
                return HCRestoreSlot(slotIndex);
            }
            m_RestorePhase = 2;
            return true;
        }
        if (m_RestorePhase == 2)
        {
            int last = m_Rows.Count() - 1;
            if (last >= 0 && !m_Rows[last]) { m_Rows.Remove(last); return true; }
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
        if (!HCSearchJson<HCSearchRecord>.WriteNew(PathFor(index, "compact"), retired, 8192)) { return Fail("compact intent write/readback failed"); }
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
        if (!HCSearchJson<HCSearchRecord>.WriteNew(entryPath, entryRecord, 8192)) return Fail("entry write/readback failed; no retries");
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
        if (!HCSearchJson<HCSearchRecord>.WriteNew(writePath, writeRecord, 8192)) return Fail("write/readback failed; no retries");
        return true;
    }

    void SetPhase(int index, int phase)
    {
        HCSearchHouseRow row = Row(index);
        if (row) row.Phase = phase;
    }
}
