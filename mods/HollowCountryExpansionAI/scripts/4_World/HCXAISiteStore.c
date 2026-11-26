// Site persistence: schema-1 DTOs and filenames remain unchanged. Routine saves
// coalesce on HCSaveScheduler and transfer <=4096 bytes per image stage.
// SaveCaches is still the synchronous picker/inventory barrier, but it never aborts
// a staged image or touches its intent file: while an image (or its intent repair)
// is in flight the barrier refuses with the newest state requeued, and the staged
// job itself reaps a stale intent one native operation per stage.
// Ownership death/reconciliation barriers flush the same revision-aware writer.
// Installed native APIs: EnSystem.c OpenFile/ReadFile/CloseFile/DeleteFile;
// JsonFileLoader.c SaveFile/MakeData; EnScript.c map Get/Set/Find/Remove.
class HCXAILocalitySave : HCSaveJob
{
    static const string PATH = "$profile:HollowCountry/expansion-ai-locality-rotation.json";
    static const string INTENT = "$profile:HollowCountry/expansion-ai-locality-rotation.pending.json";
    static const string BACKUP = "$profile:HollowCountry/expansion-ai-locality-rotation.json.bak";
    static const string LEGACY_BACKUP = "$profile:HollowCountry/expansion-ai-locality-rotation.bak.json";
    ref HCXAILocalityRotation Data;
    bool Fault;
    // The cursor came from the backup (the primary was missing or unreadable): the owner
    // must write a fresh primary even though no row changed.
    bool Recovered;
    protected ref HCStagedSaveImage m_Image = new HCStagedSaveImage();
    protected int m_Revision;
    protected int m_SnapshotRevision;
    protected string m_Text;
    override string HCName() { return "HC-18-localities"; }
    // Coverage observations are not durability barriers (selection changes set HCUrgent), and the
    // image is a full rewrite of every locality row, so routine checkpoints wait five minutes.
    override float HCInterval() { return Math.Max(HCWorldRuntimeConfig.HCGet().SaveCoalesceSeconds, 300); }
    void HCChanged() { m_Revision++; HCDirty = true; }
    // A selection waits only for a selection checkpoint (urgent) or a write in flight. Routine-dirty
    // observations and refusals ride the next image and must not hold selection for a coalesce interval.
    bool HCSelectionBlocked() { return HCInFlight || (HCUrgent && HCDirty); }
    bool HCLoad(string world)
    {
        // Load deletes the intent and the primary when it restores from a backup.
        HCStagedSaveImage.HCForget(PATH);
        m_Image.HCForgetVerified();
        if (FileExist(INTENT))
        {
            Print("[HC Plan] HC-18 rotation interrupted cursor intent discarded; primary then backup runtime=PENDING");
            DeleteFile(INTENT);
        }
        if (this.HCRestore(PATH, world)) { return true; }
        if (this.HCRestore(BACKUP, world) || this.HCRestore(LEGACY_BACKUP, world))
        {
            Print("[HC Plan] HC-18 rotation cursor recovered from backup runtime=PENDING");
            Recovered = true;
            if (FileExist(PATH)) { DeleteFile(PATH); }
            return true;
        }
        if (!FileExist(PATH) && !FileExist(BACKUP) && !FileExist(LEGACY_BACKUP))
        {
            Data = new HCXAILocalityRotation();
            Data.WorldName = world;
            return true;
        }
        Fault = true;
        return false;
    }
    protected bool HCRestore(string path, string world)
    {
        if (!FileExist(path)) { return false; }
        if (!HCGroupIO.HCLooksWholeObject(path, HCWorldStore.MAX_BYTES)) { return false; }
        string text = HCWorldStore.Read(path);
        string error;
        if (!JsonFileLoader<HCXAILocalityRotation>.LoadData(text, Data, error) ||!Data || Data.SchemaVersion != 1 || Data.WorldName != world || !Data.Rows || Data.Rows.Count() > HCXAISiteRules.HCMaxCatalogRows() || Data.SelectionSerial < 0 || Data.NextId.Length() > 48) { return false; }
        map<string, bool> ids = new map<string, bool>();
        foreach (HCXAILocalityCoverage row : Data.Rows)
        {
            if (!row || !HCXAIRules.Token(row.LocalityId) || row.LocalityId.Length() > 48 || ids.Contains(row.LocalityId) || row.NextSite < 0 || row.LastSelected < 0 || row.LastSelected > Data.SelectionSerial || row.LastObserved < 0 || row.LastObserved > row.LastSelected || row.PendingSinceSerial < 0 || row.PendingSinceSerial > Data.SelectionSerial || row.RetryAt < 0 || row.Refusal.Length() > 192) { return false; }
            if (row.Pending && row.Refusal == "") { row.Refusal = "route_not_reviewed"; }
            ids.Set(row.LocalityId, true);
        }
        return true;
    }
    override int HCStep()
    {
        if (Fault || !Data) { return HCSaveJob.STEP_FAILED; }
        if (!m_Image.Active())
        {
            string error;
            if (!JsonFileLoader<HCXAILocalityRotation>.MakeData(Data, m_Text, error)) { Fault = true; return HCSaveJob.STEP_FAILED; }
            m_SnapshotRevision = m_Revision;
            MakeDirectory("$profile:HollowCountry");
            if (!m_Image.Begin(PATH, m_Text, HCWorldStore.MAX_BYTES, true, false, "", 0, INTENT)) { Fault = true; return HCSaveJob.STEP_FAILED; }
            m_Text = "";
            return HCSaveJob.STEP_MORE;
        }
        int result = m_Image.HCStepImage();
        if (result == HCSaveJob.STEP_FAILED) { Fault = true; }
        if (result == HCSaveJob.STEP_DONE && m_SnapshotRevision != m_Revision) { return HCSaveJob.STEP_MORE; }
        return result;
    }
}
class HCXAIRouteSave : HCSaveJob
{
    HCXAISiteDirector Owner;
    bool HCShutdown;
    override string HCName() { return "HCX-routes"; }
    protected ref HCStagedSaveImage m_Image = new HCStagedSaveImage();
    protected int m_Revision;
    protected int m_SnapshotRevision;
    protected ref HCXAIRouteCache m_Snapshot;
    protected int m_RowCursor;
    protected int m_EstimatedBytes;
    protected bool m_PreflightComplete;
    protected int m_DroppedRows;
    void HCChanged() { m_Revision++; HCDirty = true; }
    override int HCStep()
    {
        if (!Owner) { return STEP_FAILED; }
        if (!m_Image.Active())
        {
            if (!m_Snapshot)
            {
                m_Snapshot = new HCXAIRouteCache();
                m_SnapshotRevision = m_Revision;
                m_RowCursor = 0;
                m_EstimatedBytes = 256;
                m_PreflightComplete = false;
                m_DroppedRows = 0;
            }
            HCWorkBudget slice = new HCWorkBudget;
            slice.HCReset(16, Math.Min(HCPerfConfig.HCGet().SliceMs, 2));
            while (!m_PreflightComplete && m_RowCursor < Owner.HCRouteRowCount() && slice.HCContinue())
            {
                if (!HCShutdown && !Owner.HCTakeRouteCacheUnit()) { return STEP_MORE; }
                HCXAIRouteRow row = Owner.HCRouteRowAt(m_RowCursor);
                m_RowCursor++;
                int estimated = HCXAISiteRules.HCRouteRowBytes(row);
                if (estimated > HCWorldStore.MAX_BYTES - m_EstimatedBytes)
                {
                    m_DroppedRows++;
                    continue;
                }
                m_EstimatedBytes += estimated;
                m_Snapshot.Rows.Insert(row);
            }
            if (!m_PreflightComplete && m_RowCursor < Owner.HCRouteRowCount()) { return STEP_MORE; }
            m_PreflightComplete = true;
            if (!HCShutdown && !Owner.HCTakeRouteCacheUnit()) { return STEP_MORE; }
            string text;
            if (!Owner.HCRoutesText(m_Snapshot, text)) { return STEP_FAILED; }
            if (text.Length() > HCWorldStore.MAX_BYTES)
            {
                if (m_Snapshot.Rows.Count() == 0) { return STEP_FAILED; }
                m_Snapshot.Rows.Remove(m_Snapshot.Rows.Count() - 1);
                m_DroppedRows++;
                return STEP_MORE;
            }
            if (m_DroppedRows > 0) { Print("[HC Expansion AI] route cache save rows dropped=" + m_DroppedRows.ToString() + " reason=byte_budget"); }
            m_Snapshot = null;
            if (!m_Image.Begin(HCXAISiteDirector.ROUTES, text, HCWorldStore.MAX_BYTES, true, false)) { return STEP_FAILED; }
            return STEP_MORE;
        }
        int result = m_Image.HCStepImage();
        if (result == STEP_DONE && m_SnapshotRevision != m_Revision) { return STEP_MORE; }
        return result;
    }
}
// Prior scalar fields of a cache row, restored when a seed intent is refused so a
// never-persisted "seeding" state can never be read back as a looted cache.
class HCXAICacheRowMemo : Managed
{
    string ClassName;
    string State;
    int Lifecycle;
    int SeededAt;
    int LootedAt;
    int NextRefillAt;
    string CrateId;
    static HCXAICacheRowMemo Take(HCXAICacheRow row)
    {
        HCXAICacheRowMemo memo = new HCXAICacheRowMemo();
        memo.ClassName = row.ClassName;
        memo.State = row.State;
        memo.Lifecycle = row.Lifecycle;
        memo.SeededAt = row.SeededAt;
        memo.LootedAt = row.LootedAt;
        memo.NextRefillAt = row.NextRefillAt;
        memo.CrateId = row.HCPickerCrateId;
        return memo;
    }
    void Restore(HCXAICacheRow row)
    {
        row.ClassName = ClassName;
        row.State = State;
        row.Lifecycle = Lifecycle;
        row.SeededAt = SeededAt;
        row.LootedAt = LootedAt;
        row.NextRefillAt = NextRefillAt;
        row.HCPickerCrateId = CrateId;
    }
}
class HCXAICacheSave : HCSaveJob
{
    // Consecutive failed images/refusals before the job faults (a barrier rearms it).
    static const int MAX_REAPS = 2;
    HCXAISiteDirector Owner;
    protected ref HCStagedSaveImage m_Image = new HCStagedSaveImage();
    protected int m_Revision;
    protected int m_SnapshotRevision;
    // A stale intent is reaped by a staged remove image (probe, then delete: one
    // native operation per stage), never by the synchronous barrier.
    protected bool m_NeedReap;
    protected bool m_Reaping;
    protected int m_Reaps;
    // The primary may be touched (deleted, copied, or not yet read back): the verified
    // .tmp is then the newest image and is KEPT, never reaped (the next boot promotes
    // it when the primary is absent or torn). Cleared when the primary reads back
    // verified (phase 5) or the image completes.
    protected bool m_KeepTmp;
    override string HCName() { return "HCX-caches"; }
    void HCChanged() { m_Revision++; HCDirty = true; }
    // The synchronous barrier defers to a staged image in flight, an intent repair in
    // progress or a kept intent; a faulted job is rearmed (it reaps the stale
    // untouched-primary intent, then retries). True means "not now": the caller
    // requeues the newest state and refuses.
    bool HCBusy()
    {
        if (m_KeepTmp && !m_Image.Active()) { return true; }
        if (HCFaulted)
        {
            HCFaulted = false;
            m_Reaps = 0;
            m_Reaping = false;
            m_Image = new HCStagedSaveImage();
            m_NeedReap = !m_KeepTmp;
            this.HCChanged();
            return true;
        }
        return m_Image.Active() || m_NeedReap;
    }
    // The barrier wrote the newest in-memory image itself; nothing staged is pending.
    protected void HCBarrierCommitted()
    {
        HCDirty = false;
        HCInFlight = false;
        HCUrgent = false;
        m_KeepTmp = false;
        m_Revision++;
        m_SnapshotRevision = m_Revision;
        this.HCCommitted(GetGame().GetTickTime());
    }
    // One staged image stage; tracks whether the primary may have been touched. The
    // static stage name is cleared first so a stale name never reads as a touch.
    protected int HCImageStep()
    {
        HCSaveJob.HCOperation = "";
        int result = m_Image.HCStepImage();
        if (m_Reaping) { return result; }
        string operation = HCSaveJob.HCOperation;
        if (m_Image.HCReadyToClearIntent()) { m_KeepTmp = false; }
        else if (operation.IndexOf("copy_primary") == 0 || operation.IndexOf("read_primary") == 0) { m_KeepTmp = true; }
        return result;
    }
    // Synchronous barrier write of the newest in-memory image through the same staged
    // writer (verified tmp, backup rotation, primary readback, intent clear), so a
    // failure knows exactly whether the primary was touched. Caller checked HCBusy().
    bool HCBarrierWrite(string text)
    {
        m_SnapshotRevision = m_Revision;
        if (!m_Image.Begin(HCXAISiteDirector.CACHES, text, HCWorldStore.MAX_BYTES, true, false))
        {
            this.HCRepair("barrier_begin_refused");
            this.HCChanged();
            return false;
        }
        int result = STEP_MORE;
        int guard = 0;
        while (result == STEP_MORE && guard < HCStagedSaveImage.HC_MAX_STAGES)
        {
            result = this.HCImageStep();
            guard++;
        }
        if (result != STEP_DONE)
        {
            if (result == STEP_MORE)
            {
                // Native scripts-1.30.164289: 1_Core/proto/EnDebug.c:96 Print;
                // 1_Core/proto/EnConvert.c:30 int.ToString.
                Print("[HC Persistence] owner=HCXAICacheSave guard=save_stage_guard steps=" + guard.ToString());
            }
            this.HCRepair("barrier_stage_failed");
            this.HCChanged();
            return false;
        }
        this.HCBarrierCommitted();
        return true;
    }
    // A failed or refused image may have left its intent. Before the primary was
    // touched the intent is reaped and the image retried, a bounded number of times;
    // persistent failure faults the job (barrier rearm). After the primary was touched
    // the verified intent is the newest image: keep it and freeze (restart recovers it).
    protected int HCRepair(string reason)
    {
        m_Reaps++;
        m_Reaping = false;
        m_Image = new HCStagedSaveImage();
        if (m_KeepTmp)
        {
            Print("[HC Expansion AI] cache image failed reason=" + reason + " action=intent_kept_until_restart runtime=PENDING");
            return STEP_FAILED;
        }
        if (m_Reaps > MAX_REAPS)
        {
            Print("[HC Expansion AI] cache image failed reason=" + reason + " action=reaps_exhausted runtime=PENDING");
            return STEP_FAILED;
        }
        m_NeedReap = true;
        return STEP_MORE;
    }
    override int HCStep()
    {
        if (!Owner) { return STEP_FAILED; }
        if (!HCDirty) { return STEP_DONE; }
        if (!m_Image.Active())
        {
            // A kept intent is never reaped or begun over; restart recovers it.
            if (m_KeepTmp) { return STEP_FAILED; }
            if (m_NeedReap)
            {
                m_NeedReap = false;
                m_Reaping = true;
                if (!m_Image.BeginRemove(HCXAISiteDirector.CACHES + ".tmp")) { return this.HCRepair("reap_refused"); }
                return STEP_MORE;
            }
            string text;
            if (!Owner.HCCachesText(text)) { return STEP_FAILED; }
            m_SnapshotRevision = m_Revision;
            if (!m_Image.Begin(HCXAISiteDirector.CACHES, text, HCWorldStore.MAX_BYTES, true, false)) { return this.HCRepair("begin_refused"); }
            return STEP_MORE;
        }
        int result = this.HCImageStep();
        if (result == STEP_FAILED) { return this.HCRepair("stage_failed"); }
        if (result == STEP_DONE)
        {
            if (m_Reaping) { m_Reaping = false; return STEP_MORE; }
            m_Reaps = 0;
            m_KeepTmp = false;
            if (m_SnapshotRevision != m_Revision) { return STEP_MORE; }
        }
        return result;
    }
}
class HCXAIOwnedSave : HCSaveJob
{
    HCXAISiteDirector Owner;
    protected ref HCV2ThreatStore<HCXAIOwnership> m_Store = new HCV2ThreatStore<HCXAIOwnership>();
    protected int m_Revision;
    override string HCName() { return "HCX-owned"; }
    void HCChanged() { m_Revision++; HCDirty = true; }
    override int HCStep()
    {
        if (!Owner) { return STEP_FAILED; }
        int result = m_Store.SaveStep(HCXAISiteDirector.OWNED, Owner.HCOwnershipData(), HCWorldStore.MAX_BYTES, m_Revision);
        if (result != STEP_MORE) { Owner.HCOwnershipSaved(result == STEP_DONE); }
        return result;
    }
}
// Derived storage layer; the final director remains the sole modded extension point.
class HCXAISiteStorage : HCXAISiteBase
{
    protected float m_OwnedRetryAt;
    protected int m_OwnedFailures;
    protected int m_CacheSaveBusy;
    protected bool HCRetryOwned()
    {
        if (!m_OwnedSave || !m_OwnedSave.HCFaulted) { return m_OwnedSave != null; }
        float now = GetGame().GetTickTime();
        if (now < m_OwnedRetryAt) { return false; }
        m_OwnedRetryAt = now + 30;
        HCSaveScheduler.HCUnregister(m_OwnedSave);
        // Release the failed writer first: its image destructor also closes
        // handles if HCFlush hit its guard before terminal failure drained them.
        m_OwnedSave = null;
        // Recover before replacing the latched writer; never discard a verified intent.
        // Failure-only retry, <=one bounded store recovery per 30 seconds.
        HCV2ThreatStore<HCXAIOwnership>.HCRecoverInterrupted(OWNED);
        m_OwnedSave = new HCXAIOwnedSave();
        m_OwnedSave.Owner = HCXAISiteDirector.Cast(this);
        HCSaveScheduler.HCRegister(m_OwnedSave);
        m_OwnedSave.HCDue = now;
        m_OwnedSave.HCUrgent = true;
        if (m_OwnedFailures == 1 || m_OwnedFailures % 10 == 0) { Print("[HC Expansion AI] ownership retry writer rebuilt reason=retry_due runtime=PENDING"); }
        return true;
    }
    override protected bool HCStartLocalities()
    {
        if (!FileExist(LOCALITIES))
        {
            m_CoverageFault = "LOCALITY_CATALOG_MISSING_POLICY_QUEUE_RETAINED";
            Print("[HC Coverage] " + m_CoverageFault + " runtime=PENDING");
            m_Localities = new HCXAILocalityCatalog();
            m_Localities.WorldName = m_Policy.WorldName;
        }
        string error;
        if (FileExist(LOCALITIES))
        {
            string catalogText = HCWorldStore.Read(LOCALITIES);
            if (!JsonFileLoader<HCXAILocalityCatalog>.LoadData(catalogText, m_Localities, error) || !m_Localities) { m_LocalityStatus = "refused:catalog_unreadable"; return false; }
            if (!HCJsonFields.Has(catalogText, "Enabled")) { m_Localities.Enabled = true; }
        }
        if (!m_Policy.HCBindContent(m_Localities)) { m_LocalityStatus = "refused:hc43_content"; return false; }
        if (!FileExist(LOCALITIES) && !this.HCReconcileLocalitySites()) { return false; }
        string problem = HCXAISiteRules.HCLocalityProblem(m_Localities, m_Policy);
        if (problem != "") { m_LocalityStatus = "refused:" + problem; return false; }
        if (FileExist("$profile:HollowCountry/acceptance/locality-route-observer.disable")) { m_Localities.Enabled = false; }
        Print(HCV2Admission.Line("HC-18", m_Localities.Enabled, "locality-route-observer", false) + " runtime=PENDING");
        if (!HCV2Admission.Admitted(m_Localities.Enabled))
        {
            m_Localities = null;
            Print(this.HCLocalitySummary() + " refusal=operator_off legacy_sites_retained");
            return true;
        }
        if (!this.HCReconcileLocalitySites()) { m_LocalityStatus = "refused:catalog_drift_capacity"; return false; }
        if (m_LocalitiesWithoutSites > 0)
        {
            m_CoverageFault = "LOCALITY_AUTHORED_SITE_DATA_MISSING";
            Print("[HC Coverage] " + m_CoverageFault + " localities=" + m_LocalitiesWithoutSites.ToString() + " existing_routes_retained=1 runtime=PENDING");
        }
        m_LocalitySave = new HCXAILocalitySave();
        if (!m_LocalitySave.HCLoad(m_Localities.WorldName)) { m_LocalityStatus = "refused:rotation_quarantined"; return false; }
        // A restart with every locality already covered and a readable primary changes nothing:
        // no image is written (a full rewrite of every row is ~250 stages) until a row changes.
        bool seeded = m_LocalitySave.Recovered || !FileExist(HCXAILocalitySave.PATH);
        foreach (HCXAILocality locality : m_Localities.Localities)
        {
            if (HCXAISiteRules.HCCoverage(m_LocalitySave.Data, locality.Id)) { continue; }
            seeded = true;
            if (m_LocalitySave.Data.Rows.Count() >= HCXAISiteRules.HCMaxCatalogRows()) { m_LocalityStatus = "refused:coverage_history_full"; return false; }
            HCXAILocalityCoverage added = new HCXAILocalityCoverage();
            added.LocalityId = locality.Id;
            added.PendingSinceSerial = m_LocalitySave.Data.SelectionSerial;
            m_LocalitySave.Data.Rows.Insert(added);
        }
        if (m_LocalitySave.Data.NextId == "")
        {
            m_LocalitySave.Data.NextId = m_Localities.Localities[0].Id;
            seeded = true;
        }
        if (seeded)
        {
            m_LocalitySave.HCChanged();
            if (!HCSaveScheduler.HCFlush(m_LocalitySave)) { m_LocalityStatus = "refused:rotation_save"; return false; }
        }
        m_SiteLocalities.Clear();
        m_CoverageRows.Clear();
        for (int localityIndex = 0; localityIndex < m_Localities.Localities.Count(); localityIndex++)
        {
            HCXAILocality indexedLocality = m_Localities.Localities[localityIndex];
            foreach (string indexedSite : indexedLocality.SiteIds) { m_SiteLocalities.Set(indexedSite, localityIndex); }
        }
        foreach (HCXAILocalityCoverage indexedCoverage : m_LocalitySave.Data.Rows) { m_CoverageRows.Set(indexedCoverage.LocalityId, indexedCoverage); }
        m_LocalityStatus = "pending_provider";
        Print(this.HCLocalitySummary());
        return true;
    }
    override protected bool HCReconcileLocalitySites()
    {
        int unknown = 0;
        m_LocalitiesWithoutSites = 0;
        map<string, bool> policyIds = new map<string, bool>();
        foreach (HCXAISite candidate : m_Policy.Sites) { policyIds.Set(candidate.Id, true); }
        foreach (HCXAILocality locality : m_Localities.Localities)
        {
            int siteIndex = locality.SiteIds.Count() - 1;
            while (siteIndex >= 0)
            {
                if (!policyIds.Contains(locality.SiteIds[siteIndex])) { locality.SiteIds.RemoveOrdered(siteIndex); unknown++; }
                siteIndex--;
            }
            if (locality.SiteIds.Count() == 0) { m_LocalitiesWithoutSites++; }
        }
        if (unknown > 0) { Print("[HC Plan] HC-18 catalog_unknown_site skipped=" + unknown.ToString() + " operator policy retained runtime=PENDING"); }
        int syntheticIndex = 0;
        map<string, bool> mappedIds = new map<string, bool>();
        map<string, bool> localityIds = new map<string, bool>();
        foreach (HCXAILocality mappedLocality : m_Localities.Localities)
        {
            localityIds.Set(mappedLocality.Id, true);
            foreach (string mappedId : mappedLocality.SiteIds) { mappedIds.Set(mappedId, true); }
        }
        foreach (HCXAISite site : m_Policy.Sites)
        {
            if (mappedIds.Contains(site.Id)) { continue; }
            if (m_Localities.Localities.Count() >= HCXAISiteRules.HCMaxCatalogRows()) { return false; }
            string id = site.Id;
            bool collision = localityIds.Contains(id);
            while (collision)
            {
                id = "hc-unmapped-" + syntheticIndex.ToString();
                syntheticIndex++;
                collision = localityIds.Contains(id);
            }
            localityIds.Set(id, true);
            HCXAILocality added = new HCXAILocality();
            added.Id = id;
            added.Source = "operator site policy";
            added.SiteIds.Insert(site.Id);
            m_Localities.Localities.Insert(added);
        }
        return true;
    }
    override protected HCXAIRouteRow RouteRow(string siteId)
    {
        if (siteId.Length() >= 10 && siteId.Substring(0, 10) == "transient:") { return null; }
        return m_RouteRows.Get(siteId);
    }
    override protected void Remember(HCXAIRouteRow row)
    {
        if (row.SiteId.Length() >= 10 && row.SiteId.Substring(0, 10) == "transient:") { return; }
        int routeIndex;
        if (m_RouteIndices.Find(row.SiteId, routeIndex))
        {
            m_Routes.Rows[routeIndex] = row;
        }
        else
        {
            if (m_Routes.Rows.Count() >= HCXAISiteRules.HCMaxCatalogRows())
            {
                this.HCCacheVerdict(m_Routes.Rows[0].SiteId, false);
                this.HCRemoveRoute(m_Routes.Rows[0]);
            }
            m_RouteIndices.Set(row.SiteId, m_Routes.Rows.Count());
            m_Routes.Rows.Insert(row);
        }
        m_RouteRows.Set(row.SiteId, row);
        this.SaveRoutes();
        if (row.Qualified) { HCModuleReadiness.HCUse("optional-expansion-human-ai", "route_cache"); }
    }
    override bool RaidLocked(HCXAISite site, int now)
    {
        if (!m_Owned || now <= 0) { return true; }
        HCXAIOwnedRow raidRow = m_OwnedRows.Get(site.Id);
        if (!raidRow || raidRow.ClearedAt == 0) { return false; }
        if (now < raidRow.ClearedAt || m_RespawnOff) { return true; }
        return now - raidRow.ClearedAt < this.HCDeathDelay(site, raidRow);
    }
    override protected HCXAIOwnedRow OwnershipRow(string siteId)
    {
        HCXAIOwnedRow candidateRow = m_OwnedRows.Get(siteId);
        if (candidateRow) { return candidateRow; }
        if (m_Owned.Rows.Count() >= HCXAISiteRules.HCMaxCatalogRows()) { return null; }
        HCXAIOwnedRow createdRow = new HCXAIOwnedRow();
        createdRow.SiteId = siteId;
        m_Owned.Rows.Insert(createdRow);
        m_OwnedRows.Set(siteId, createdRow);
        return createdRow;
    }
    override void RecordDeath(eAIGroup killedGroup)
    {
        if (!killedGroup) { return; }
        foreach (HCXAISiteState killedState : m_States)
        {
            // The killed hook already armed persistent and transient patrols.
            if (!killedState.Patrol || !killedState.Patrol.HCMatchesGroup(killedGroup)) { continue; }
            if (killedState.Transient) { return; }
            this.RecordCleared(killedState.Patrol, true);
            return;
        }
    }
    override void RecordCleared(HCXAISitePatrol patrol, bool death = false)
    {
        if (!m_Owned || patrol.m_HCTransient) { return; }
        HCXAIOwnedRow clearedRow = this.OwnershipRow(patrol.m_HCSiteId);
        if (!clearedRow) { m_OwnedSaved = false; return; }
        if (!death && clearedRow.ClearedAt > 0) { return; }
        int clearedAt = HCXExpansionBridge.HCGetTimestamp();
        if (clearedAt < 1)
        {
            m_OwnershipClockFault = true;
            m_OwnedSaved = false;
            Print("[HC Expansion AI] ownership save refused: reason=death_epoch_unavailable; new spawns and cache seeds held until restart");
            return;
        }
        clearedRow.ClearedAt = clearedAt;
        clearedRow.PartialRaid = death && HCXExpansionBridge.HCHoldCountFinal(patrol.HCGroupHold()) > 1;
        this.SaveOwned();
        Print("[HC Expansion AI] site " + patrol.m_HCSiteId + " cleared-at=" + clearedRow.ClearedAt.ToString() + " saved=" + m_OwnedSaved.ToString());
    }
    override protected void StepCache()
    {
        int count = m_States.Count();
        int tries = 0;
        while (tries < count)
        {
            HCXAISiteState state = m_States[m_CacheCursor % count];
            m_CacheCursor++;
            tries++;
            if (state.Site.Kind != "holdout" || !state.Patrol || !state.HouseObject) { continue; }
            this.CacheStep(state);
            return;
        }
    }
    override protected void CacheStep(HCXAISiteState state)
    {
        HCXAISite site = state.Site;
        EntityAI crate = this.FindCrate(state);
        int items = 0;
        if (crate && crate.GetInventory() && crate.GetInventory().GetCargo()) { items = crate.GetInventory().GetCargo().GetItemCount(); }
        bool playerNear = false;
        this.HCRefreshPlayers();
        foreach (Man player : m_Players)
        {
            if (!player || !player.GetIdentity()) { continue; }
            if (vector.DistanceSq(player.GetPosition(), state.CacheWorld) < m_Policy.CacheClearRadius * m_Policy.CacheClearRadius) { playerNear = true; break; }
        }
        HCXAICacheRow row = this.CacheRow(site.Id);
        int now = HCXExpansionBridge.HCGetTimestamp();
        if (now < 1) { return; }
        bool present = false;
        if (crate) { present = true; }
        string action = HCXAISiteRules.CacheAction(row, present, items, now, playerNear);
        if (action == "seed" || action == "refill")
        {
            if (!m_OwnedSaved || this.RaidLocked(site, now)) { return; }
            if (row && row.LootedAt > 0 && now - row.LootedAt < 604800) { return; }
            this.SeedCache(state, row, now, crate);
            return;
        }
        if (action == "adopt")
        {
            row.State = "seeded";
            this.HCQueueCaches();
            Print("[HC Expansion AI] site " + site.Id + " cache adopted after an interrupted seed (no new items)");
            return;
        }
        if (action == "mark-looted")
        {
            row.State = "looted";
            row.LootedAt = now;
            int cacheCooldown = site.CacheCooldownSeconds;
            if (cacheCooldown < 604800) { cacheCooldown = 604800; }
            row.NextRefillAt = HCXAISiteRules.RefillAt(now, cacheCooldown);
            this.HCQueueCaches();
            Print("[HC Expansion AI] site " + site.Id + " cache looted or gone; refill not before " + row.NextRefillAt.ToString());
            return;
        }
        if (action == "refuse") { Print("[HC Expansion AI] site " + site.Id + " cache journal row in unknown state " + row.State); }
    }
    override protected EntityAI FindCrate(HCXAISiteState state)
    {
        array<Object> objects = new array<Object>();
        array<CargoBase> cargos = new array<CargoBase>();
        GetGame().GetObjectsAtPosition(state.CacheWorld, 1.5, objects, cargos);
        foreach (Object candidate : objects)
        {
            if (candidate && candidate.GetType() == state.Site.CacheClass) { return EntityAI.Cast(candidate); }
        }
        return null;
    }
    override protected HCXAICacheRow CacheRow(string siteId)
    {
        return m_CacheRows.Get(siteId);
    }
    // True while the save barrier cannot take a new intent. Seeding refuses BEFORE it
    // touches the row (a mutated "seeding" row that was never persisted would read back
    // as looted for seven days); the next visit retries. Counted in [HC Use].
    protected bool HCCacheSaveBusy(string key)
    {
        if (!m_CacheSave || !m_CacheSave.HCBusy()) { return false; }
        m_CacheSaveBusy++;
        HCModuleReadiness.HCUse("optional-expansion-human-ai", "cache_save_busy");
        if (m_CacheSaveBusy == 1 || m_CacheSaveBusy % 50 == 0)
        {
            Print("[HC Expansion AI] cache seed deferred key=" + key + " reason=cache_save_busy count=" + m_CacheSaveBusy.ToString() + " runtime=PENDING");
        }
        return true;
    }
    // Undo a refused seed: a row added for it is dropped, an existing one restored.
    protected void HCCacheSeedRevert(HCXAICacheRow row, HCXAICacheRowMemo memo, bool added)
    {
        if (added)
        {
            // HCXAICacheRow is not Managed and Rows holds its only ref: drop the raw index entry first,
            // because RemoveItem frees the row and row.SiteId must not be read afterwards.
            string siteId = row.SiteId;
            if (m_CacheRows.Get(siteId) == row) { m_CacheRows.Remove(siteId); }
            m_Caches.Rows.RemoveItem(row);
            return;
        }
        memo.Restore(row);
    }
    override void SeedCache(HCXAISiteState state, HCXAICacheRow row, int now, EntityAI crate)
    {
        HCXAISite site = state.Site;
        if (this.HCCacheSaveBusy(site.Id)) { return; }
        bool added = false;
        if (!row)
        {
            if (m_Caches.Rows.Count() >= HCXAISiteRules.HCMaxCatalogRows()) { return; }
            HCXAICacheRow newRow = new HCXAICacheRow();
            newRow.SiteId = site.Id;
            m_Caches.Rows.Insert(newRow);
            m_CacheRows.Set(site.Id, newRow);
            row = newRow;
            added = true;
        }
        HCXAICacheRowMemo memo = HCXAICacheRowMemo.Take(row);
        row.ClassName = site.CacheClass;
        row.State = "seeding";
        row.Lifecycle = row.Lifecycle + 1;
        row.SeededAt = now;
        row.LootedAt = 0;
        row.NextRefillAt = 0;
        if (!this.SaveCaches())
        {
            this.HCCacheSeedRevert(row, memo, added);
            Print("[HC Expansion AI] site " + site.Id + " cache intent not saved; row restored, nothing created reason=cache_intent_unsaved");
            return;
        }
        if (!crate)
        {
            crate = EntityAI.Cast(GetGame().CreateObjectEx(site.CacheClass, state.CacheWorld, ECE_SETUP | ECE_CREATEPHYSICS | ECE_KEEPHEIGHT | ECE_NOLIFETIME));
            if (crate) { crate.SetOrientation(state.CacheOrientation); HCGroundSnap.Snap(crate); }
        }
        if (!crate || !crate.GetInventory())
        {
            Print("[HC Expansion AI] site " + site.Id + " cache container could not be created; left as seeding reason=container_create_failed");
            return;
        }
        int created = 0;
        foreach (HCXAISiteLoot loot : site.CacheLoot)
        {
            int made = 0;
            while (made < loot.Quantity)
            {
                EntityAI item = crate.GetInventory().CreateEntityInCargo(loot.ClassName);
                made++;
                if (!item) { continue; }
                created++;
                Magazine ammo = Magazine.Cast(item);
                if (ammo) { ammo.ServerSetAmmoCount(ammo.GetAmmoMax() / 2); }
            }
        }
        row.State = "seeded";
        this.HCQueueCaches();
        vector at = state.CacheWorld;
        Print("[HC Expansion AI] site " + site.Id + " cache " + site.CacheClass + " seeded lifecycle " + row.Lifecycle.ToString() + " with " + created.ToString() + " items at " + at.ToString());
    }
    override bool SaveCaches()
    {
        if (!m_Caches || m_Caches.Rows.Count() > HCXAISiteRules.HCMaxCatalogRows()) { return false; }
        // A staged image owns the intent file until it commits; the barrier neither
        // aborts it nor probes/clears the intent. Requeue the newest state (the staged
        // job persists it after the image in flight) and refuse; callers retry.
        if (m_CacheSave && m_CacheSave.HCBusy()) { m_CacheSave.HCChanged(); return false; }
        foreach (HCXAICacheRow barrierRow : m_Caches.Rows)
        {
            if (!m_CacheRows.Contains(barrierRow.SiteId)) { m_CacheRows.Set(barrierRow.SiteId, barrierRow); }
        }
        // Same synchronous return/durability contract for picker and seeding.
        // Verified tmp + backup rotation + primary readback; never truncate the
        // primary in place. LoadCaches refuses backup-only rollback.
        if (!m_CacheSave) { return false; }
        string text;
        if (!this.HCCachesText(text)) { return false; }
        return m_CacheSave.HCBarrierWrite(text);
    }
    override bool SaveRoutes()
    {
        if (!HCXAISiteRules.HCRouteRowsValid(m_Routes) || !m_RouteSave) { return false; }
        m_RouteSave.HCChanged();
        return true;
    }
    override bool HCTakeRouteCacheUnit()
    {
        return HCServer.HCTickWork().HCTakeFor(HCUnitBudget.HC_WORK_AI_ROUTE_CACHE, 1);
    }
    override int HCRouteRowCount() { return m_Routes.Rows.Count(); }
    override HCXAIRouteRow HCRouteRowAt(int index) { return m_Routes.Rows[index]; }
    override bool HCRoutesText(HCXAIRouteCache snapshot, out string text)
    {
        if (!HCXAISiteRules.HCRouteRowsValid(snapshot)) { return false; }
        string error;
        return JsonFileLoader<HCXAIRouteCache>.MakeData(snapshot, text, error);
    }
    override protected void HCIndexRoutes()
    {
        m_RouteRows.Clear();
        m_RouteIndices.Clear();
        array<ref HCXAIRouteRow> indexed = new array<ref HCXAIRouteRow>();
        foreach (HCXAIRouteRow row : m_Routes.Rows)
        {
            // Legacy readers chose the first matching row. Keep that verdict
            // if an older profile contains duplicates, without a per-tick scan.
            if (m_RouteRows.Contains(row.SiteId)) { m_LegacyRoutesDirty = true; continue; }
            m_RouteRows.Set(row.SiteId, row);
            m_RouteIndices.Set(row.SiteId, indexed.Count());
            indexed.Insert(row);
        }
        m_Routes.Rows = indexed;
    }
    override protected void HCRemoveRoute(HCXAIRouteRow row)
    {
        // HCXAIRouteRow is not Managed and Rows may hold its only ref: the swap or Remove frees it.
        // Read the id and drop the raw map entries first; row must not be read afterwards.
        if (!row) { return; }
        string siteId = row.SiteId;
        int index;
        if (!m_RouteIndices.Find(siteId, index)) { return; }
        m_RouteRows.Remove(siteId);
        m_RouteIndices.Remove(siteId);
        row = null;
        int last = m_Routes.Rows.Count() - 1;
        if (index != last)
        {
            HCXAIRouteRow tail = m_Routes.Rows[last];
            m_RouteIndices.Set(tail.SiteId, index);
            m_Routes.Rows[index] = tail;
        }
        m_Routes.Rows.Remove(last);
    }
    override void HCQueueCaches()
    {
        if (m_CacheSave) { m_CacheSave.HCChanged(); }
    }
    override void HCQueueOwned()
    {
        // Spawn/despawn/member refreshes are staged: Members is informational;
        // Reconcile removes HC: groups after restart. Death barriers stay sync.
        if (!this.HCRetryOwned() || !this.HCUpdateMembers()) { return; }
        m_OwnedSave.HCChanged();
    }
    override protected bool HCUpdateMembers()
    {
        if (!m_Owned) { return false; }
        foreach (HCXAIOwnedRow resetRow : m_Owned.Rows) { resetRow.Members = 0; }
        foreach (HCXAISiteState state : m_States)
        {
            if (state.Transient || !state.Patrol || !HCXExpansionBridge.HCHoldAliveFinal(state.Patrol.HCGroupHold())) { continue; }
            HCXAIOwnedRow ownedRow = this.OwnershipRow(state.Site.Id);
            if (!ownedRow) { m_OwnedSaved = false; return false; }
            ownedRow.Members = HCXExpansionBridge.HCHoldCountFinal(state.Patrol.HCGroupHold());
        }
        return true;
    }
    override bool HCCachesText(out string text)
    {
        if (!m_Caches || !m_Caches.Rows || m_Caches.Rows.Count() > HCXAISiteRules.HCMaxCatalogRows()) { return false; }
        string error;
        return JsonFileLoader<HCXAICacheJournal>.MakeData(m_Caches, text, error);
    }
    override HCXAIOwnership HCOwnershipData() { return m_Owned; }
    override void HCOwnershipSaved(bool saved)
    {
        m_OwnedSaved = saved && !m_OwnershipClockFault;
        if (saved) { m_OwnedFailures = 0; }
        else
        {
            m_OwnedRetryAt = GetGame().GetTickTime() + 30;
            m_OwnedFailures++;
            if (m_OwnedFailures == 1 || m_OwnedFailures % 10 == 0)
            {
                Print("[HC Expansion AI] ownership save refused: reason=ownership_checkpoint_failed retries=" + m_OwnedFailures.ToString() + "; new spawns and cache seeds held");
            }
        }
    }
    override bool SaveOwned()
    {
        if (!this.HCUpdateMembers()) { this.HCOwnershipSaved(false); return false; }
        if (!this.HCRetryOwned()) { return false; }
        m_OwnedSave.HCChanged();
        int failuresBeforeFlush = m_OwnedFailures;
        m_OwnedSaved = HCSaveScheduler.HCFlush(m_OwnedSave) && !m_OwnershipClockFault;
        // HCFlush may abort at its stage guard without calling the owner.
        if (!m_OwnedSaved)
        {
            m_OwnedSave.HCFaulted = true;
            if (m_OwnedFailures == failuresBeforeFlush) { this.HCOwnershipSaved(false); }
        }
        if (!m_OwnedSaved) { m_OwnedRetryAt = GetGame().GetTickTime() + 30; }
        return m_OwnedSaved;
    }
}

class HCXAISiteStore
{
    static string ReadBounded(string path)
    {
        if (!FileExist(path)) { return ""; }
        FileHandle handle = OpenFile(path, FileMode.READ);
        if (!handle) { return ""; }
        string data;
        int count = ReadFile(handle, data, 65537);
        CloseFile(handle);
        if (count < 1 || count > 65536) { return ""; }
        return data;
    }
    static HCXAISitePolicy LoadPolicy()
    {
        string data = HCWorldStore.Read(HCXAISiteDirector.POLICY);
        if (data == "") { return null; }
        string error;
        HCXAISitePolicy policy;
        if (!JsonFileLoader<HCXAISitePolicy>.LoadData(data, policy, error) || !policy) { return null; }
        if (!HCJsonFields.Has(data, "AIRespawnSeconds")) { policy.AIRespawnSeconds = 900; }
        if (!HCJsonFields.Has(data, "MemberReplaceSeconds")) { policy.MemberReplaceSeconds = 600; }
        policy.MaxActiveAI = HCAILimits.Get().MaxActiveAI;
        policy.MaxActiveSites = HCAILimits.Get().MaxActiveSites;
        return policy;
    }
    static string HCWholeCacheText(string path)
    {
        if (!HCGroupIO.HCLooksWholeObject(path, HCWorldStore.MAX_BYTES)) { return ""; }
        string data = HCWorldStore.Read(path);
        array<string> stack = new array<string>;
        bool quoted = false;
        bool escaped = false;
        bool ended = false;
        for (int offset = 0; offset < data.Length(); offset += 4096)
        {
            int length = Math.Min(4096, data.Length() - offset);
            string piece = data.Substring(offset, length);
            for (int index = 0; index < piece.Length(); index++)
            {
                string character = piece.Substring(index, 1);
                if (quoted)
                {
                    if (escaped) { escaped = false; }
                    else if (character == "\\") { escaped = true; }
                    else if (character == "\"") { quoted = false; }
                    continue;
                }
                if (character == " " || character == "\n" || character == "\r" || character == "\t") { continue; }
                if (ended) { return ""; }
                if (character == "\"") { quoted = true; }
                else if (character == "{" || character == "[")
                {
                    if (stack.Count() >= 128) { return ""; }
                    stack.Insert(character);
                }
                else if (character == "}" || character == "]")
                {
                    int depth = stack.Count();
                    if (depth < 1) { return ""; }
                    string open = stack[depth - 1];
                    if ((character == "}" && open != "{") || (character == "]" && open != "[")) { return ""; }
                    stack.Remove(depth - 1);
                    ended = stack.Count() == 0;
                }
            }
        }
        if (quoted || stack.Count() != 0 || !ended) { return ""; }
        return data;
    }
    protected static bool s_HCRoutesRefused;
    protected static bool s_HCCachesRefused;
    static void HCRoutesRefused(string reason)
    {
        if (s_HCRoutesRefused) { return; }
        s_HCRoutesRefused = true;
        Print("[HC XAI] routes refused reason=" + reason);
    }
    static void HCCachesRefused(string reason)
    {
        if (s_HCCachesRefused) { return; }
        s_HCCachesRefused = true;
        Print("[HC XAI] caches refused reason=" + reason);
    }
    static bool HCPreserveRoute(string path, out string preserved)
    {
        preserved = "none";
        if (!FileExist(path)) { return true; }
        for (int attempt = 0; attempt < 8; attempt++)
        {
            string target = path + ".torn-" + attempt.ToString();
            if (FileExist(target)) { continue; }
            FileHandle original = OpenFile(path, FileMode.READ);
            if (!original) { return false; }
            string expected;
            expected = "";
            int expectedCount = ReadFile(original, expected, HCWorldStore.MAX_BYTES + 1);
            CloseFile(original);
            if (expectedCount < 0 || expectedCount > HCWorldStore.MAX_BYTES || expected.Length() != expectedCount) { return false; }
            if (!CopyFile(path, target) || !FileExist(target)) { return false; }
            FileHandle copy = OpenFile(target, FileMode.READ);
            if (!copy) { return false; }
            string actual;
            actual = "";
            int count = ReadFile(copy, actual, HCWorldStore.MAX_BYTES + 1);
            CloseFile(copy);
            if (count != expectedCount || actual != expected) { return false; }
            if (target.Length() > 256) { return false; }
            int slash = target.LastIndexOf("/");
            preserved = target.Substring(slash + 1, target.Length() - slash - 1);
            return true;
        }
        return false;
    }
    static HCXAIRouteCache LoadRoutes()
    {
        string path = HCXAISiteDirector.ROUTES;
        // Promotion, preservation and reset below rewrite the primary outside the image writer, so
        // every writer's verified memo for it is retired before any of them can run.
        HCStagedSaveImage.HCForget(path);
        for (int candidate = 0; candidate < 3; candidate++)
        {
            HCXAIRouteCache routes;
            string error;
            routes = null;
            error = "";
            string source = path;
            string label = "primary";
            if (candidate == 1) { source = path + ".tmp"; label = "tmp"; }
            if (candidate == 2) { source = path + ".bak"; label = "bak"; }
            string data = HCWholeCacheText(source);
            if (data == "") { continue; }
            if (!JsonFileLoader<HCXAIRouteCache>.LoadData(data, routes, error) || !HCXAISiteRules.HCRouteRowsValid(routes)) { continue; }
            if (candidate > 0)
            {
                string preserved = "";
                if (!HCPreserveRoute(path, preserved)) { HCRoutesRefused("preserve_failed"); return null; }
                if (FileExist(path) && !DeleteFile(path)) { HCRoutesRefused("delete_failed"); return null; }
                if (!CopyFile(source, path) || HCWholeCacheText(path) != data) { HCRoutesRefused("promote_failed"); return null; }
                if (FileExist(path + ".tmp") && !DeleteFile(path + ".tmp")) { HCRoutesRefused("tmp_delete_failed"); return null; }
                Print("[HC XAI] routes recovered source=" + label + " preserved=" + preserved);
            }
            else if (FileExist(path + ".tmp") && !DeleteFile(path + ".tmp")) { HCRoutesRefused("tmp_delete_failed"); return null; }
            return routes;
        }
        if (FileExist(path) || FileExist(path + ".tmp") || FileExist(path + ".bak"))
        {
            string kept = "none";
            if (FileExist(path))
            {
                if (!HCPreserveRoute(path, kept)) { HCRoutesRefused("preserve_failed"); return null; }
                if (!DeleteFile(path)) { HCRoutesRefused("delete_failed"); return null; }
            }
            if (FileExist(path + ".tmp") && !DeleteFile(path + ".tmp")) { HCRoutesRefused("tmp_delete_failed"); return null; }
            Print("[HC XAI] routes reset reason=no_valid_image preserved=" + kept);
        }
        return new HCXAIRouteCache();
    }
    static HCXAICacheJournal LoadCaches()
    {
        string path = HCXAISiteDirector.CACHES;
        // A whole verified intent is the newest image: promote it when the primary is
        // absent or torn, before the core recovery could roll back to the older backup.
        string pending = path + ".tmp";
        if (FileExist(pending) && !HCV2ThreatStore<HCXAICacheJournal>.HCWholeImage(path) && HCV2ThreatStore<HCXAICacheJournal>.HCWholeImage(pending))
        {
            if (!HCV2ThreatStore<HCXAICacheJournal>.HCPromoteWholePending(path, pending, HCGroupIO.HC_RAW_READ_CAP))
            {
                HCCachesRefused("pending_promote_failed");
                return null;
            }
            if (!DeleteFile(pending) || FileExist(pending))
            {
                HCCachesRefused("pending_clear_failed");
                return null;
            }
            Print("[HC Expansion AI] caches recovered action=promoted_whole_pending reason=primary_missing_or_torn runtime=PENDING");
        }
        // A backup is the PRIOR committed image, never proof of latest loot
        // state. Refuse backup-only rollback (including legacy sync tears).
        // Recovery may promote a whole newer intent; never refill from old bak.
        if (!HCV2ThreatStore<HCXAICacheJournal>.HCWholeImage(path) && !HCV2ThreatStore<HCXAICacheJournal>.HCWholeImage(path + ".tmp") && FileExist(path + ".bak"))
        {
            HCCachesRefused("backup_only_rollback");
            return null;
        }
        if (!HCV2ThreatStore<HCXAICacheJournal>.CanOpen(path)) { HCCachesRefused("recovery"); return null; }
        if (!FileExist(path))
        {
            return new HCXAICacheJournal();
        }
        string data = HCWholeCacheText(path);
        if (data == "") { HCCachesRefused("structural_or_size"); return null; }
        string error;
        HCXAICacheJournal caches;
        if (!JsonFileLoader<HCXAICacheJournal>.LoadData(data, caches, error) || !caches) { HCCachesRefused("invalid_json"); return null; }
        if (caches.SchemaVersion != 1) { HCCachesRefused("schema"); return null; }
        if (!caches.Rows || caches.Rows.Count() > HCXAISiteRules.HCMaxCatalogRows()) { HCCachesRefused("rows"); return null; }
        return caches;
    }
    static HCXAIOwnership LoadOwned()
    {
        if (!HCV2ThreatStore<HCXAIOwnership>.CanOpen(HCXAISiteDirector.OWNED)) { return null; }
        if (!FileExist(HCXAISiteDirector.OWNED)) { return new HCXAIOwnership(); }
        string data = HCWorldStore.Read(HCXAISiteDirector.OWNED);
        if (data == "") { return null; }
        string error;
        HCXAIOwnership journal;
        if (!JsonFileLoader<HCXAIOwnership>.LoadData(data, journal, error) || !journal || journal.SchemaVersion != 1 || !journal.Rows || journal.Rows.Count() > HCXAISiteRules.HCMaxCatalogRows()) { return null; }
        foreach (HCXAIOwnedRow checkedRow : journal.Rows)
        {
            if (!checkedRow || checkedRow.ClearedAt < 0 || checkedRow.Members < 0) { return null; }
        }
        return journal;
    }
}
