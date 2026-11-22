// Native scripts-1.30.164289: 1_Core/proto/EnScript.c:917/926 map.Contains/Insert.
// LC-T310 / #94, EXP-S3. Timed environmental stages, no artificial player IDs.
// Native scripts-1.30.164289: 1_Core/proto/EnSystem.c:397 FileExist, :525
// MakeDirectory, :528 DeleteFile, :531 CopyFile. No rename API exists in this
// installed script snapshot. HCGroupIO supplies bounded read/write/readback;
// HCGroupClock.Utc supplies bracketed UTC via EnSystem.c:76,100. JSON uses
// 3_Game/tools/JsonFileLoader.c:69 LoadData, :85 MakeData.
// Save is a fail-closed transaction: verified temp -> backup -> install ->
// readback -> remove intent. This is logically atomic admission, NOT a filesystem
// atomic rename/fsync guarantee. Interrupted writes never load backup or reset.
// Common natives: 3_Game/Global/Game.c:1120 IsServer; 1_Core/proto/EnDebug.c:96 Print;
// EnScript.c:380 Count, :394 Find, :407 Insert, :463 Remove; EnConvert.c:30 int.ToString;
// EnString.c:171 ToLower, :199 Length (1_Core/proto).

class HCSceneStageDefinition
{
    string Kit;
    int HoldSeconds = 21600;
    int DelaySeconds = 21600;
    ref HCEventMission Objective;
}

class HCSceneChainDefinition
{
    string Id;
    string SiteId;
    // HC-42: immutable source pair and full anchor, saved before materialization.
    string IndexedCandidate;
    ref HCEventSite IndexedSite;
    ref array<ref HCSceneStageDefinition> Stages = new array<ref HCSceneStageDefinition>();
}

class HCSceneCatalog
{
    int Version = 1;
    ref array<ref HCSceneChainDefinition> Chains = new array<ref HCSceneChainDefinition>();
}

class HCSceneChain
{
    string Id;
    // HC-19: zero only in unmigrated v1 state; old IDs and plans remain pinned.
    int StorySequence;
    int Stage;
    int DueAt;
    int ExpiresAt;
    int BeganAt;
    int EventId;
    bool Cancelled;
    bool Complete;
    ref HCEventState Director;
}

class HCSceneChainState
{
    int Version = 1;
    string WorldName;
    int Revision;
    int LastNow;
    // Empty progress is unmigrated v1; never serialize null into the native loader.
    ref HCStoryProgress Stories = new HCStoryProgress;
    // Pin the complete authored plan: edits to mission data cannot shorten a
    // running stage, revive a cancelled chain or silently replace its kit/site.
    ref HCSceneCatalog Catalog;
    ref array<ref HCSceneChain> Chains = new array<ref HCSceneChain>();
}

class HCSceneChains
{
    static bool HCFieldsPresent(string text)
    {
        return HCJsonFields.Every(text, "DelaySeconds", 5);
    }

    // Pause unfinished stages after a >5 minute scheduler/server gap. Keep the
    // active director deadline and BeganAt aligned with the shifted schedule.
    static int ResumeAfterGap(HCSceneChainState state, int now)
    {
        int gap = now - state.LastNow;
        if (gap <= 300) { return 0; }
        foreach (HCSceneChain pending : state.Chains)
        {
            if (pending.Cancelled || pending.Complete) { continue; }
            if (pending.DueAt > 999300000 - gap || pending.ExpiresAt > 1000086400 - gap) { return -1; }
        }
        foreach (HCSceneChain chain : state.Chains)
        {
            if (chain.Cancelled || chain.Complete) { continue; }
            HCEventRecord record = null;
            if (chain.EventId > 0) { record = HCEventDirector.FindRecord(chain.Director, chain.EventId); }
            if (record && HCEventDirector.Terminal(record.Status)) { continue; }
            chain.DueAt = chain.DueAt + gap;
            chain.ExpiresAt = chain.ExpiresAt + gap;
            if (record)
            {
                chain.BeganAt = chain.BeganAt + gap;
                record.Expires = chain.ExpiresAt;
            }
        }
        state.LastNow = now;
        return gap;
    }

    static bool StageFailed(int now, int expires, int status)
    {
        // Values are HCEventStatus: completed=4, expired=5, cancelled=6.
        // A finished stage may wait for unobserved cleanup past its deadline.
        if (status == 4) { return false; }
        return status == 5 || status == 6 || now >= expires;
    }

    static bool CancelExpired(HCSceneChain chain, int now, int status)
    {
        if (!StageFailed(now, chain.ExpiresAt, status)) { return false; }
        Cancel(chain, now);
        return true;
    }

    static HCEventSite Site(string siteId)
    {
        array<ref HCEventSite> sites = HCEventReviewedSites.Curated();
        foreach (HCEventSite site : sites)
        {
            if (site.Id == siteId) { return site; }
        }
        return null;
    }

    static HCEventSite HCPlanSite(HCSceneChainDefinition plan)
    {
        if (!plan) { return null; }
        if (plan.IndexedCandidate != "")
        {
            if (!HCGapcodeStoryIndex.HCPinnedSite(plan.IndexedSite) || plan.IndexedSite.Id != plan.SiteId) { return null; }
            return plan.IndexedSite;
        }
        // Pre-HC-42 saves have no IndexedSite key; a zero-filled object from the
        // native loader is not a pin. Only a named site on a plain plan refuses.
        if (plan.IndexedSite && plan.IndexedSite.Id != "") { return null; }
        return Site(plan.SiteId);
    }

    static HCEventContext Context(HCSceneChain chain, int now)
    {
        HCEventContext context = new HCEventContext;
        context.Server = GetGame() && GetGame().IsServer();
        context.WorldName = chain.Director.WorldName;
        context.Session = chain.Director.Session;
        context.Now = now;
        return context;
    }

    static HCSceneChainDefinition Plan(string id, string siteId, string first, string second, string third)
    {
        HCSceneChainDefinition plan = new HCSceneChainDefinition;
        plan.Id = id;
        plan.SiteId = siteId;
        array<string> kinds = new array<string>();
        kinds.Insert(first);
        kinds.Insert(second);
        kinds.Insert(third);
        for (int index = 0; index < kinds.Count(); index++)
        {
            HCSceneStageDefinition stage = new HCSceneStageDefinition;
            stage.Kit = kinds[index];
            if (index == 0) { stage.DelaySeconds = 0; }
            HCEventSite objectiveSite = Site(siteId);
            stage.Objective = HCEventReviewedSites.SceneMission(objectiveSite, id + "-" + kinds[index], 43200);
            plan.Stages.Insert(stage);
        }
        return plan;
    }

    static HCSceneCatalog Defaults()
    {
        HCSceneCatalog catalog = new HCSceneCatalog;
        catalog.Chains.Insert(Plan("scene-kamenka", "kamenka-supply-cache", "convoy-roadside", "survivor-distress-camp", "supply-drop-remains"));
        catalog.Chains.Insert(Plan("scene-staroye", "staroye-traffic-cache", "quarantine-checkpoint", "evacuation-point", "last-stand"));
        catalog.Chains.Insert(Plan("scene-kumyrna", "kumyrna-ambush-cache", "convoy-wreck", "survivor-distress-camp", "evacuation-point"));
        // First two finish around hour 30. Leave the third a fresh independent
        // window at hour 36, rather than exhausting its lifetime in a queue.
        catalog.Chains[2].Stages[0].DelaySeconds = 129600;
        // Reuse a reviewed site only after the existing three planned windows
        // (third ends around hour 66). Runtime also waits for any old site lease,
        // including observer-gated cleanup. A missed deadline still cancels.
        catalog.Chains.Insert(Plan("scene-relief-route", "kamenka-supply-cache", "supply-drop-opened", "quarantine-cordon", "survivor-cold-camp"));
        catalog.Chains[3].Stages[0].DelaySeconds = 259200;
        return catalog;
    }

    static bool CatalogValid(HCSceneCatalog catalog, bool retained = false)
    {
        // Authored input stays capped at four. Retained state also contains the
        // bounded arrival window and may be empty after cleanup receipts.
        int limit = 4;
        if (retained) { limit = HCStoryPolicy.MAX_RETAINED; }
        if (!catalog || catalog.Version != 1 || !catalog.Chains || (!retained && catalog.Chains.Count() < 1) || catalog.Chains.Count() > limit) { return false; }
        map<string, bool> ids = new map<string, bool>();
        foreach (HCSceneChainDefinition plan : catalog.Chains)
        {
            if (!plan || !HCEventDirector.TextValid(plan.Id, 32) || ids.Contains(plan.Id)) { return false; }
            HCEventSite site = HCPlanSite(plan);
            if (!HCSceneKits.Reviewed(site) || !plan.Stages || plan.Stages.Count() < 1 || plan.Stages.Count() > 3) { return false; }
            if (plan.IndexedCandidate == "" && plan.Stages.Count() < 2) { return false; }
            if (plan.IndexedCandidate != "" && plan.Stages.Count() != 1) { return false; }
            ids.Insert(plan.Id, true);
            map<string, bool> missions = new map<string, bool>();
            foreach (HCSceneStageDefinition stage : plan.Stages)
            {
                if (!stage || !HCSceneKits.Find(stage.Kit) || stage.HoldSeconds < 3600 || stage.HoldSeconds > 43200 || stage.DelaySeconds < 0 || stage.DelaySeconds > 259200) { return false; }
                HCEventMission mission = stage.Objective;
                if (!HCEventRuntimePolicy.MissionValid(mission, site.WorldName)) { return false; }
                if (mission.SiteId != site.Id || vector.DistanceSq(mission.Source, site.Position) > 0.25 || vector.DistanceSq(mission.Destination, site.Position) > 0.25 || mission.Family != HCEventFamily.INVESTIGATION) { return false; }
                if (mission.ActorBudget != 0 || mission.RewardUnits != 0 || mission.RewardCache || mission.ItemClass != "" || mission.ContainerClass != "") { return false; }
                if (mission.Id != plan.Id + "-" + stage.Kit || missions.Contains(mission.Id) || mission.LifetimeSeconds <= stage.HoldSeconds) { return false; }
                missions.Insert(mission.Id, true);
            }
        }
        return true;
    }

    static HCSceneCatalog LoadCatalog()
    {
        string path = "$mission:hollow-country/events/scene-chains.json";
        if (!FileExist(path)) { return Defaults(); }
        string text;
        string error;
        HCSceneCatalog catalog;
        if (!HCGroupIO.Read(path, 32768, text) || !JsonFileLoader<HCSceneCatalog>.LoadData(text, catalog, error)) { return null; }
        if (!HCFieldsPresent(text)) { Print("[HC Scenes] state=refused reason=missing_DelaySeconds runtime=PENDING"); return null; }
        if (!CatalogValid(catalog)) { return null; }
        return catalog;
    }

    static HCSceneChainState Fresh(HCSceneCatalog catalog, int now)
    {
        if (!CatalogValid(catalog) || now < 1 || now > 999000000) { return null; }
        HCSceneChainState state = new HCSceneChainState;
        state.WorldName = "chernarusplus";
        state.LastNow = now;
        state.Catalog = catalog;
        foreach (HCSceneChainDefinition plan : catalog.Chains)
        {
            HCSceneChain chain = new HCSceneChain;
            chain.Id = plan.Id;
            chain.Director = HCEventDirector.Initialize(state.WorldName, plan.Id);
            Schedule(chain, plan.Stages[0], now);
            state.Chains.Insert(chain);
        }
        return state;
    }

    static void Schedule(HCSceneChain chain, HCSceneStageDefinition stage, int now)
    {
        chain.DueAt = now + stage.DelaySeconds;
        chain.ExpiresAt = chain.DueAt + stage.Objective.LifetimeSeconds;
        chain.EventId = 0;
        chain.BeganAt = 0;
    }

    static bool StateValid(HCSceneChainState state)
    {
        if (!state || state.Version != 1 || state.WorldName != "chernarusplus" || state.Revision < 0 || state.Revision > 999999999 || state.LastNow < 1 || state.LastNow > 999000000) { return false; }
        if (!HCStoryPolicy.HCValid(state)) { return false; }
        if (!CatalogValid(state.Catalog, state.Stories != null) || !state.Chains || state.Chains.Count() != state.Catalog.Chains.Count()) { return false; }
        for (int index = 0; index < state.Chains.Count(); index++)
        {
            HCSceneChain chain = state.Chains[index];
            HCSceneChainDefinition plan = state.Catalog.Chains[index];
            if (!chain || chain.Id != plan.Id || chain.Stage < 0 || chain.Stage >= plan.Stages.Count() || (chain.Cancelled && chain.Complete)) { return false; }
            if (!HCEventDirector.StateValid(chain.Director) || chain.Director.WorldName != state.WorldName || chain.Director.Session != plan.Id || chain.Director.LastNow > state.LastNow) { return false; }
            if (chain.Director.Records.Count() > plan.Stages.Count() || chain.DueAt < 1 || chain.DueAt > 999300000 || chain.ExpiresAt - chain.DueAt != plan.Stages[chain.Stage].Objective.LifetimeSeconds) { return false; }
            if (chain.EventId < 0 || chain.BeganAt < 0 || chain.BeganAt > state.LastNow || (chain.Director.Records.Count() != chain.Stage + 1 && chain.Director.Records.Count() != chain.Stage)) { return false; }
            HCEventRecord active;
            if (chain.EventId == 0)
            {
                if (chain.BeganAt != 0 || chain.Director.Records.Count() != chain.Stage) { return false; }
            }
            else
            {
                active = HCEventDirector.FindRecord(chain.Director, chain.EventId);
                if (!active || chain.EventId != chain.Stage + 1 || chain.EventId != chain.Director.NextId - 1 || active.Expires != chain.ExpiresAt || chain.BeganAt < chain.DueAt) { return false; }
                if (active.Definition.Id != plan.Stages[chain.Stage].Objective.Id || active.Definition.Goal != 1 || chain.BeganAt >= chain.ExpiresAt) { return false; }
                if (chain.Cancelled && !HCEventDirector.Terminal(active.Status)) { return false; }
            }
            if (chain.Complete && (chain.Stage != plan.Stages.Count() - 1 || chain.EventId == 0)) { return false; }
            if (chain.Complete && active.Status != HCEventStatus.COMPLETED) { return false; }
            for (int recordIndex = 0; recordIndex < chain.Director.Records.Count(); recordIndex++)
            {
                HCEventRecord record = chain.Director.Records[recordIndex];
                HCSceneStageDefinition definition = plan.Stages[recordIndex];
                if (record.Definition.Id != definition.Objective.Id || record.Definition.ObjectiveTag != "scene-duration" || record.Definition.RewardUnits != 0 || record.Definition.ActorBudget != 0 || record.Definition.ItemBudget != 0 || record.Participants.Count() != 0) { return false; }
                if (recordIndex < chain.Stage && record.Status != HCEventStatus.COMPLETED) { return false; }
            }
        }
        return true;
    }

    static bool Begin(HCSceneChain chain, HCSceneStageDefinition stage, int now)
    {
        HCEventContext context = Context(chain, now);
        HCEventDefinition definition = HCEventRuntimePolicy.Definition(stage.Objective);
        definition.ObjectiveTag = "scene-duration";
        // The schedule owns the independent absolute deadline, including time
        // spent waiting on observer clearance or an active-scene budget slot.
        definition.LifetimeSeconds = chain.ExpiresAt - now;
        if (HCEventDirector.Propose(chain.Director, context, definition) != HCEventCode.OK) { return false; }
        chain.EventId = chain.Director.NextId - 1;
        chain.BeganAt = now;
        return Operation(chain, HCEventOp.ANNOUNCE, now) == HCEventCode.OK;
    }

    static int Operation(HCSceneChain chain, int op, int now)
    {
        HCEventRecord record = HCEventDirector.FindRecord(chain.Director, chain.EventId);
        if (!record) { return HCEventCode.NOT_FOUND; }
        HCEventRequest request = new HCEventRequest;
        request.EventId = record.Id;
        request.ExpectedRevision = record.Revision;
        request.Op = op;
        HCEventContext context = Context(chain, now);
        return HCEventDirector.Command(chain.Director, context, request);
    }

    static void Cancel(HCSceneChain chain, int now)
    {
        chain.Cancelled = true;
        if (chain.EventId == 0) { return; }
        HCEventRecord record = HCEventDirector.FindRecord(chain.Director, chain.EventId);
        if (!record || HCEventDirector.Terminal(record.Status)) { return; }
        int op = HCEventOp.CANCEL;
        if (now >= record.Expires) { op = HCEventOp.EXPIRE; }
        Operation(chain, op, now);
    }
}

class HCSceneChainStore
{
    protected string m_Path = "$profile:HollowCountry/scene-chains.json";
    protected bool m_Fault;
    protected string m_Image;
    protected int m_Revision;
    protected ref HCStagedSaveImage m_SaveImage = new HCStagedSaveImage;
    protected int m_SaveStage;
    protected string m_PendText;
    protected int m_PendRevision;

    bool Fault(string reason = "save")
    {
        m_Fault = true;
        Print("[HollowCountry] V2 scenes persistence refused; preserve scene-chains.json/.tmp/.bak for recovery reason=" + reason);
        return false;
    }

    HCSceneChainState Open(int now)
    {
        if (!FileExist("$profile:HollowCountry") && !MakeDirectory("$profile:HollowCountry")) { Fault("directory"); return null; }
        if (FileExist(m_Path + ".tmp")) { Fault("tmp"); return null; }
        // Pre-HC-19 has no Stories key. Restore ONLY that absent object after
        // native scalar zero-fill, never a present partial/corrupt history.
        HCSceneChainState state = new HCSceneChainState;
        if (FileExist(m_Path))
        {
            string error;
            if (!HCGroupIO.Read(m_Path, 65536, m_Image) || !JsonFileLoader<HCSceneChainState>.LoadData(m_Image, state, error)) { Fault("read"); return null; }
            if (!HCJsonFields.Every(m_Image, "DelaySeconds", 6, "Kit")) { Fault("missing_DelaySeconds"); return null; }
            if (state && !HCJsonFields.Has(m_Image, "Stories")) { state.Stories = new HCStoryProgress; }
            if (!HCSceneChains.StateValid(state))
            {
                // Name the failing part so a refused upgrade is diagnosable from one boot.
                bool catalogOk = state.Catalog && HCSceneChains.CatalogValid(state.Catalog, state.Stories != null);
                Fault("state_invalid catalog=" + catalogOk.ToString() + " stories=" + HCStoryPolicy.HCValid(state).ToString());
                return null;
            }
            if (now < state.LastNow) { Fault("clock"); return null; }
            m_Revision = state.Revision;
            return state;
        }
        // A missing current image with a surviving backup is not a new world.
        if (FileExist(m_Path + ".bak")) { Fault("backup_only"); return null; }
        HCSceneCatalog catalog = HCSceneChains.LoadCatalog();
        state = HCSceneChains.Fresh(catalog, now);
        if (!state) { Fault("fresh"); return null; }
        if (!Save(state)) { return null; }
        return state;
    }

    protected ref HCSceneCheckpointJob m_Checkpoint;
    protected ref HCSceneChainState m_CheckpointState;
    protected int m_Mutations;
    protected int m_SnapshotMutations;
    protected int m_DurableMutations;
    // Shared by chain, story and offer writers. Routine heartbeats can stay
    // dirty/in flight after this mutation is durable without blocking Scenes.
    protected int m_BarrierMutation;

    HCSaveJob HCCheckpointJob(HCSceneChainState state)
    {
        if (!m_Checkpoint)
        {
            m_CheckpointState = state;
            m_Checkpoint = new HCSceneCheckpointJob;
            m_Checkpoint.Owner = this;
            HCSaveScheduler.HCRegister(m_Checkpoint);
        }
        return m_Checkpoint;
    }

    int HCRequestCheckpoint(HCSceneChainState state, bool barrier = true)
    {
        HCSaveJob job = HCCheckpointJob(state);
        if (m_Fault || job.HCFaulted || m_CheckpointState != state) { return -1; }
        m_Mutations++;
        job.HCDirty = true;
        if (barrier)
        {
            m_BarrierMutation = m_Mutations;
            job.HCUrgent = true;
            job.HCDue = GetGame().GetTickTime();
        }
        return m_Mutations;
    }

    bool HCCheckpointPending() { return m_Checkpoint && (m_Checkpoint.HCDirty || m_Checkpoint.HCInFlight); }
    bool HCDurable(int mutation) { return !m_Fault && mutation >= 0 && m_DurableMutations >= mutation; }
    bool HCBarrierPending() { return !HCDurable(m_BarrierMutation); }
    void HCPumpCheckpoint() { HCSaveScheduler.HCPumpFallback(m_Checkpoint); }
    bool HCFlushCheckpoint() { return HCSaveScheduler.HCFlush(m_Checkpoint); }
    bool HCCheckpointHealthy() { return !m_Fault && (!m_Checkpoint || !m_Checkpoint.HCFaulted); }

    int HCStepCheckpoint()
    {
        if (!m_CheckpointState) { return HCSaveJob.STEP_FAILED; }
        return SaveStep(m_CheckpointState);
    }

    bool SaveInFlight() { return m_SaveStage != 0; }

    // Only pre-intent snapshots may be abandoned. Once intent work begins,
    // callers must finish the checkpoint before a newer barrier save.
    void SaveAbandon()
    {
        if (m_SaveImage.Active()) { return; }
        m_SaveStage = 0;
        m_PendText = "";
    }

    static string Encode(HCSceneChainState state)
    {
        string text;
        string error;
        if (!JsonFileLoader<HCSceneChainState>.MakeData(state, text, error) || text.Length() > 65536) { return ""; }
        return text;
    }

    protected string ReadImage(string path)
    {
        string text;
        if (!HCGroupIO.Read(path, 65536, text)) { return ""; }
        return text;
    }

    protected int SaveFailed()
    {
        m_SaveStage = 0;
        m_PendText = "";
        Fault();
        return HCSaveJob.STEP_FAILED;
    }

    // Stages 0/1 encode/check prior leave original files untouched. Stage 2
    // starts HCStagedSaveImage.HCStepImage (per-stage crash states documented there).
    // Open still refuses every surviving .tmp and backup-only primary loss.
    // Disk stage boundaries: write_tmp/read_tmp retain old primary + intent;
    // copy_backup retains old primary/backup + intent; copy_primary/read_primary
    // retain new primary, old backup and intent; clear_intent admits new primary.
    int SaveStep(HCSceneChainState state)
    {
        if (m_Fault)
        {
            m_SaveStage = 0;
            m_PendText = "";
            return HCSaveJob.STEP_FAILED;
        }
        if (m_SaveStage == 0)
        {
            HCSaveJob.HCOperation = "encode";
            if (!HCSceneChains.StateValid(state) || state.Revision != m_Revision || m_Revision >= 999999998) { return SaveFailed(); }
            state.Revision = m_Revision + 1;
            string encoded = Encode(state);
            state.Revision = m_Revision;
            if (encoded == "") { return SaveFailed(); }
            m_PendText = encoded;
            m_SnapshotMutations = m_Mutations;
            m_PendRevision = m_Revision + 1;
            m_SaveStage = 1;
            return HCSaveJob.STEP_MORE;
        }
        if (m_SaveStage == 1)
        {
            // Open/last commit retain the exact validated primary. The shared
            // writer verifies it in chunks before touching the next intent.
            m_SaveStage = 2;
        }
        if (m_SaveStage == 2)
        {
            if (!m_SaveImage.Begin(m_Path, m_PendText, 65536, m_Image != "", m_Image != "", m_Image)) { return SaveFailed(); }
            m_SaveStage = 3;
        }
        if (m_SaveImage.HCReadyToClearIntent() && m_SnapshotMutations != m_Mutations)
        {
            // All three scene writers share this intent. Never admit an older
            // snapshot over a newer story/actor reservation.
            if (!HCSceneChains.StateValid(state)) { return SaveFailed(); }
            state.Revision = m_PendRevision;
            string refreshed = Encode(state);
            state.Revision = m_Revision;
            if (refreshed == "" || !m_SaveImage.HCRefreshIntent(refreshed)) { return SaveFailed(); }
            m_PendText = refreshed;
            m_SnapshotMutations = m_Mutations;
            return HCSaveJob.STEP_MORE;
        }
        int result = m_SaveImage.HCStepImage();
        if (result == HCSaveJob.STEP_FAILED) { return SaveFailed(); }
        if (result == HCSaveJob.STEP_MORE) { return result; }
        state.Revision = m_PendRevision;
        m_Revision = m_PendRevision;
        m_Image = m_PendText;
        m_DurableMutations = m_SnapshotMutations;
        m_SaveStage = 0;
        m_PendText = "";
        return HCSaveJob.STEP_DONE;
    }

    // Synchronous whole save (Open, transition barriers, shutdown): the same stages back to back.
    bool Save(HCSceneChainState state)
    {
        if (m_Fault) { return Fault(); }
        int remainingStages;
        while (SaveInFlight() && remainingStages < HCStagedSaveImage.HC_MAX_STAGES + 3)
        {
            remainingStages++;
            if (SaveStep(state) == HCSaveJob.STEP_FAILED) { return false; }
        }
        if (SaveInFlight()) { return false; }
        int result = HCSaveJob.STEP_MORE;
        int guard = 0;
        while (result == HCSaveJob.STEP_MORE && guard < HCStagedSaveImage.HC_MAX_STAGES + 3)
        {
            result = SaveStep(state);
            guard = guard + 1;
        }
        return result == HCSaveJob.STEP_DONE;
    }
}

class HCSceneCheckpointJob : HCSaveJob
{
    HCSceneChainStore Owner;
    override string HCName() { return "Scenes"; }
    override int HCStep()
    {
        if (!Owner) { return HCSaveJob.STEP_FAILED; }
        return Owner.HCStepCheckpoint();
    }
}
