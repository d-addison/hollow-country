// W5-PERF-3: <=1 chain/10s OR <=1 prop creation/tick, never both.
// Heartbeat saves coalesce through HCSaveScheduler; transition intents wait
// for their mutation to be durable. Preflight: one 40m query, <=256 objects/64 doors.
// Shared timer evidence: World/HCWorkBudget.c header (Game.c:914).
// LC-T309/310, #93/#94/#120. EnableEncounters admits source by preference;
// EXP-S3 is logged, never asserted accepted. No core registration edit required.
// Native scripts-1.30.164289: 3_Game/Global/Game.c:932 GetWorldName, :914
// GetTickTime, :1550 GetCallQueue; 3_Game/DayZGame.c:1233 queue implementation;
// 2_GameLib/tools.c:61 CallLater, :65 Remove.
// HCGroupClock (UTC), HCGroupIO and the v1 director are reused, not reimplemented.
// Common natives: 3_Game/Global/Game.c:1120 IsServer; 1_Core/proto/EnDebug.c:96 Print;
// EnScript.c:380 Count, :394 Find, :407 Insert, :463 Remove, :502 RemoveItem,
// :906 map.Remove; EnConvert.c:30 int.ToString;
// EnString.c:171 ToLower, :199 Length (1_Core/proto).
// Note placement reuses HCSceneKits.Preflight: Game.c:930 objects, :1176
// SurfaceY, :1196 SurfaceIsSea; Building.c:31/73 doors, Object.c:370 bounds;
// 1_Core/proto/EnMath3D.c:18 Vector. No new placement/physics API.
// 1_Core/proto/EnConvert.c:210 vector.DistanceSq (named-place selection).

// w28-debugmap #193: detached read-only lease row for the debug map. Plain data
// only (no object handles), so a reader can never mutate or retain scene state.
class HCDebugSceneLeaseRow
{
    string ChainId;
    int Stage;
    vector Anchor;
    bool Closing;
    bool Placed;
    int Objects;
    int DueAt;
    int ExpiresAt;
    bool Complete;
}

class HCScenesModule : HCModule
{
    protected ref HCWorldActivityCounters m_Activity = new HCWorldActivityCounters("work placed completed notes refused checkpoint budget not_due pacing preflight advertise failed");
    protected static ref HCScenesModule s_CleanupOwner;
    // Weak pointer to the running instance for read-only debug getters; cleared in OnStop.
    protected static HCScenesModule s_DebugOwner;
    // Chains scanned when matching a lease to its chain (reviewed catalogs are small).
    static const int HC_DEBUG_CHAIN_SCAN = 16;
    protected ref HCSceneChainStore m_Store;
    protected ref HCSceneChainState m_State;
    protected ref HCStorySchedule m_Stories;
    protected ref HCGapcodeStoryIndex m_StoryIndex;
    protected ref array<ref HCSceneLease> m_Leases = new array<ref HCSceneLease>();
    protected int m_Cursor;
    protected ref HCWorkBudget m_WorkBudget = new HCWorkBudget;
    protected ref HCSaveJob m_SaveJob;
    protected int m_StoryOfferPending;
    protected bool m_IndexPlacementTurn;
    protected int m_Placed;
    protected int m_Refused;
    // Last refusal per retained chain; release keys when a terminal row is released.
    protected ref map<string, string> m_PreflightReasons = new map<string, string>();
    protected ref array<string> m_AdvertiseRefusals = new array<string>();
    protected int m_LastNow;
    protected float m_WorkElapsed;
    protected bool m_Running;
    protected bool m_Stopping;
    protected bool m_AdmissionPrinted;
    protected bool m_SummaryPrinted;
    protected string m_Refusal;
    protected string m_Fault;
    protected ref HCOperationalStatus m_Operational = new HCOperationalStatus;

    override string GetName() { return "Scenes"; }

    // HC-62 readiness requires the loaded index and a source-qualified pair.
    // Selection/clearance is progress, not a readiness failure or native acceptance.
    override HCOperationalStatus HCGetOperationalStatus()
    {
        if (m_Fault != "")
        {
            m_Operational.HCPublish("degraded", m_Fault);
            return m_Operational;
        }
        if (m_Running && m_StoryIndex && !m_StoryIndex.HCOff() && !m_StoryIndex.HCReady())
        {
            m_Operational.HCPublish("degraded", m_StoryIndex.HCReason());
            return m_Operational;
        }
        string readyReason = "scene_store_open_schedule_running";
        if (m_Running && m_StoryIndex && m_StoryIndex.HCReady() && m_StoryIndex.HCReason() != "")
        {
            readyReason = m_StoryIndex.HCReason();
        }
        HCModuleReadiness.HCDerive(m_Operational, m_Running, m_Refusal, "", readyReason);
        return m_Operational;
    }
    override bool IsEnabled(HCSettings settings) { return settings && settings.EnableEncounters; }

    override void OnStart(HCSettings settings)
    {
        if (!GetGame() || !GetGame().IsServer() || !IsEnabled(settings) || m_Running) { return; }
        m_Refusal = "";
        m_Fault = "";
        if (!m_AdmissionPrinted)
        {
            Print(HCV2Admission.Line("Scenes", true, "EXP-S3", HCV2Gates.Qualified("EXP-S3")));
            m_AdmissionPrinted = true;
        }
        if (s_CleanupOwner || m_Leases.Count() > 0)
        {
            Print("[HollowCountry] V2 scenes startup refused; prior observer-gated cleanup pending");
            m_Refusal = "prior_cleanup_pending";
            return;
        }
        string world;
        GetGame().GetWorldName(world);
        world.ToLower();
        if (world != "chernarusplus")
        {
            Print("[HollowCountry] V2 scenes refused; no reviewed sites for this world");
            m_Refusal = "no_reviewed_sites_for_world";
            return;
        }
        int now = Now();
        if (now < 1)
        {
            Print("[HollowCountry] V2 scenes refused; utc_clock_unavailable");
            m_Refusal = "utc_clock_unavailable";
            return;
        }
        m_Store = new HCSceneChainStore;
        m_State = m_Store.Open(now);
        if (!m_State)
        {
            // HCSceneChainStore.Open already logged the persistence cause (reason=...).
            Print("[HollowCountry] V2 scenes refused; store_unavailable");
            m_Refusal = "store_unavailable";
            return;
        }
        m_Stories = new HCStorySchedule;
        bool storiesStarted = m_Stories.HCStart(m_State, m_Store, HCStoryPolicy.HCLoadConfig(), now, true);
        if (!storiesStarted && m_Stories.HCReason() != "operator-off")
        {
            Print("[HollowCountry] V2 scenes refused; HC-19 " + m_Stories.HCReason());
            m_Stories = null;
            m_Refusal = "story_schedule_refused";
            return;
        }
        // HC-38 offers every retained chain once from the bound source. Bind it
        // only while HC-19 is ready: operator-off Stories must offer nothing.
        // HC-19 has already logged its own off reason; no second line here.
        if (storiesStarted) { HCSituationSource.HCBind(m_State, m_Store); }
        if (storiesStarted)
        {
            m_StoryIndex = new HCGapcodeStoryIndex;
            m_StoryIndex.HCStart();
            m_Stories.HCBindIndex(m_StoryIndex);
        }
        m_LastNow = now;
        m_Stopping = false;
        m_SaveJob = m_Store.HCCheckpointJob(m_State);
        m_Running = true;
        s_DebugOwner = this;
        if (!m_SummaryPrinted) { Summary(); }
    }

    int Now()
    {
        int utc = HCGroupClock.Utc();
        // Director bounds its clock to 1e9 seconds. Fixed UTC 2020 origin keeps
        // genuine wall-clock hours/days and includes server downtime.
        if (utc < 1577836801) { return -1; }
        return utc - 1577836800;
    }

    bool Commit(int now)
    {
        m_State.LastNow = now;
        if (m_Store.HCRequestCheckpoint(m_State) < 0)
        {
            m_Fault = "scene_save_failed";
            OnStop();
        }
        // The chain/event identity is retained. Next Work revalidates its site,
        // kit and director after the barrier mutation is durable.
        return false;
    }

    void SaveBarrierDone()
    {
        if (!m_SaveJob) { return; }
        // The barrier wrote the whole current state; a staged heartbeat is done.
        m_SaveJob.HCDirty = false;
        m_SaveJob.HCInFlight = false;
        m_SaveJob.HCDue = GetGame().GetTickTime() + 60;
    }

    void StoryStep(int now)
    {
        if (!m_Running || !m_Stories || !m_Stories.HCReady()) { return; }
        array<string> released = new array<string>();
        HCSceneChain candidate = m_Stories.HCCandidate();
        if (candidate && (candidate.Complete || candidate.Cancelled) && Cleanup(Lease(candidate.Id)))
        {
            released.Insert(candidate.Id);
            ReleaseRefusals(candidate.Id);
        }
        // Even an empty receipt advances the scheduler's bounded retained cursor.
        int nextSequence = 0;
        if (m_State.Stories) { nextSequence = m_State.Stories.NextSequence; }
        if (m_Stories.HCStep(now, released))
        {
            if (m_State.Stories && m_State.Stories.NextSequence != nextSequence)
            {
                m_StoryOfferPending = m_State.Stories.NextSequence - 1;
            }
            return;
        }
        if (m_Stories.HCReady()) { return; }
        m_Fault = "scene_story_" + m_Stories.HCReason();
        if (m_Stories.HCReason() == "save-failed")
        {
            m_Fault = "scene_story_save_failed";
            SaveBarrierDone();
        }
        m_Running = false;
        OnStop();
    }

    void ReleaseRefusals(string chainId)
    {
        m_PreflightReasons.Remove(chainId);
        // Reviewed plans have at most three stages; IDs never recur.
        m_AdvertiseRefusals.RemoveItem(chainId + ":0");
        m_AdvertiseRefusals.RemoveItem(chainId + ":1");
        m_AdvertiseRefusals.RemoveItem(chainId + ":2");
    }

    HCSceneLease Lease(string chainId)
    {
        foreach (HCSceneLease ownedLease : m_Leases)
        {
            if (ownedLease.ChainId == chainId) { return ownedLease; }
        }
        return null;
    }

    // Read-only debug seam (w28-debugmap). Only a running instance is exposed.
    static HCScenesModule HCDebugGet()
    {
        if (s_DebugOwner && s_DebugOwner.m_Running) { return s_DebugOwner; }
        return null;
    }

    // Only the instance that published itself may clear the pointer.
    protected void HCDebugRelease()
    {
        if (s_DebugOwner == this) { s_DebugOwner = null; }
    }

    int HCDebugLeaseCount() { return m_Leases.Count(); }

    HCDebugSceneLeaseRow HCDebugLease(int index)
    {
        if (index < 0 || index >= m_Leases.Count()) { return null; }
        HCSceneLease lease = m_Leases[index];
        if (!lease) { return null; }
        HCDebugSceneLeaseRow row = new HCDebugSceneLeaseRow;
        row.ChainId = lease.ChainId;
        row.Stage = lease.Stage;
        row.Anchor = lease.Anchor;
        row.Closing = lease.Closing;
        row.Placed = HCSceneKits.HCPlacementComplete(lease);
        row.Objects = lease.Objects.Count();
        if (!m_State) { return row; }
        int scan = m_State.Chains.Count();
        if (scan > HC_DEBUG_CHAIN_SCAN) { scan = HC_DEBUG_CHAIN_SCAN; }
        for (int chainIndex = 0; chainIndex < scan; chainIndex++)
        {
            HCSceneChain chain = m_State.Chains[chainIndex];
            if (chain.Id != lease.ChainId) { continue; }
            row.DueAt = chain.DueAt;
            row.ExpiresAt = chain.ExpiresAt;
            row.Complete = chain.Complete;
            return row;
        }
        return row;
    }

    bool SiteAvailable(vector anchor)
    {
        foreach (HCSceneLease siteLease : m_Leases)
        {
            if (siteLease.Anchor == anchor) { return false; }
        }
        return true;
    }

    // Offer the already-placed scene through the existing optional v1 UI when
    // that module is admitted. V2 scenery itself does not require v1 markers.
    void Advertise(HCSceneLease lease, HCSceneStageDefinition stage, HCEventSite site, int seconds)
    {
        HCEventModule events = HCEventModule.Get();
        if (seconds < stage.Objective.DwellSeconds) { return; }
        if (!events || !events.Runtime()) { AdvertiseRefused(lease, "event-module-unavailable"); return; }
        HCEventMission mission = HCEventReviewedSites.SceneMission(site, stage.Objective.Id, seconds);
        HCEventRuntime runtime = events.Runtime();
        HCEventContext context = events.Context();
        if (!context) { AdvertiseRefused(lease, "event-context-unavailable"); return; }
        if (!runtime.HasMission(mission.Id))
        {
            int announced = runtime.Announce(mission, context);
            if (announced != HCEventCode.OK) { AdvertiseRefused(lease, "announce-code-" + announced.ToString()); return; }
        }
        HCEventRuntimeState snapshot = runtime.Snapshot();
        foreach (HCEventRun run : snapshot.Runs)
        {
            if (run.Objective.Id == mission.Id)
            {
                lease.ViewEventId = run.EventId;
                lease.ViewSession = context.Session;
                Print("[HollowCountry] V2 scene advertised id=" + lease.ChainId + " stage=" + lease.Stage.ToString() + " event=" + lease.ViewEventId.ToString());
                return;
            }
        }
        AdvertiseRefused(lease, "missing-view-run");
    }

    void AdvertiseRefused(HCSceneLease lease, string reason)
    {
        m_Activity.HCRefuse("advertise", reason);
        string key = lease.ChainId + ":" + lease.Stage.ToString();
        if (m_AdvertiseRefusals.Find(key) >= 0 || m_AdvertiseRefusals.Count() >= 12) { return; }
        m_AdvertiseRefusals.Insert(key);
        Print("[HollowCountry] V2 scene advertise refused id=" + lease.ChainId + " stage=" + lease.Stage.ToString() + " reason=" + reason + "; retry pending");
    }

    // Re-run the established clearance check after waiting for a note receipt.
    static bool HCNotePlacementAllowed(string sceneId, vector position)
    {
        if (!s_DebugOwner || !s_DebugOwner.m_Running) { return false; }
        HCSceneLease lease = s_DebugOwner.Lease(sceneId);
        if (!lease || lease.Closing || !HCSceneKits.Healthy(lease)) { return false; }
        for (int index = 0; index < s_DebugOwner.m_State.Chains.Count(); index++)
        {
            HCSceneChain chain = s_DebugOwner.m_State.Chains[index];
            if (chain.Id != sceneId || chain.Complete || chain.Cancelled) { continue; }
            HCEventSite site = HCSceneChains.HCPlanSite(s_DebugOwner.m_State.Catalog.Chains[index]);
            HCSceneKit kit = new HCSceneKit;
            kit.Id = "scene-paper";
            HCSceneKits.Add(kit, "Paper", 0, 7, 0, 0.3);
            array<vector> positions;
            int variant;
            if (!site || !HCSceneKits.Preflight(kit, site, positions, variant) || positions.Count() < 1) { return false; }
            return vector.DistanceSq(position, positions[0]) < 0.01;
        }
        return false;
    }

    static bool SceneNote(HCNoteLedger notes, HCWorldLead lead, string sceneId, string placeId, vector position, int now)
    {
        if (!notes || !HCLeadPolicy.PrepareSceneLead(lead, sceneId, placeId, now)) { return false; }
        return notes.Create(sceneId, position, lead) != null;
    }

    void PublishSceneStory(HCSceneChain chain, HCEventSite site)
    {
        HCWorldModule world = HCWorldModule.Get();
        // A static named-place fallback also works when the world ledger is off.
        HCWorldData catalog = HCWorldData.Fresh(1);
        HCWorldPlace nearest;
        float best = 500000000;
        foreach (HCWorldPlace candidate : catalog.Places)
        {
            float distance = vector.DistanceSq(candidate.Position, site.Position);
            if (distance < best) { best = distance; nearest = candidate; }
        }
        if (!nearest) { return; }
        string placeId = nearest.Id;
        if (world) { world.AddFact("scene_started", placeId, 0); }
        HCNoteLedger notes = HCNoteLedger.Get();
        if (!notes || notes.Scene(chain.Id)) { return; }
        HCLeadModule leads = HCLeadModule.Get();
        HCWorldLead lead;
        if (leads) { lead = leads.Select(); }
        if (!lead) { lead = new HCWorldLead; }
        // The same native clearance checks as scenery, including all already
        // placed kit buildings, protect the door/access strip and ground slope.
        HCSceneKit noteKit = new HCSceneKit;
        noteKit.Id = "scene-paper";
        HCSceneKits.Add(noteKit, "Paper", 0, 7, 0, 0.3);
        array<vector> notePositions;
        int noteVariant;
        if (!HCSceneKits.Preflight(noteKit, site, notePositions, noteVariant))
        {
            PreflightRefused(chain.Id, "note-" + HCSceneKits.Refusal());
            return;
        }
        vector notePosition = notePositions[0];
        if (SceneNote(notes, lead, chain.Id, placeId, notePosition, HCWorldClock.UTC()))
        {
            m_Activity.HCHit("notes");
            Print("[HollowCountry] V2 scene note created id=" + chain.Id + " place=" + placeId + " source=" + lead.Source);
        }
    }

    void RetireView(HCSceneLease lease)
    {
        if (!lease || lease.ViewEventId == 0) { return; }
        HCEventModule events = HCEventModule.Get();
        if (!events || !events.Runtime()) { return; }
        HCEventContext context = events.Context();
        if (context.Session != lease.ViewSession) { lease.ViewEventId = 0; return; }
        if (events.Runtime().HCPublishPending()) { return; }
        HCEventRuntimeState snapshot = events.Runtime().Snapshot();
        HCEventRecord record = HCEventDirector.FindRecord(snapshot.Director, lease.ViewEventId);
        if (record && !HCEventDirector.Terminal(record.Status))
        {
            if (events.Runtime().Cancel(record.Id, context) != HCEventCode.OK) { return; }
        }
        lease.ViewEventId = 0;
    }

    bool Cleanup(HCSceneLease lease)
    {
        if (!lease) { return true; }
        lease.Closing = true;
        RetireView(lease);
        // Keep ownership for the existing Work/CleanupStopped tick to retry.
        if (lease.ViewEventId != 0) { return false; }
        if (!HCSceneKits.Remove(lease)) { return false; }
        int index = m_Leases.Find(lease);
        if (index >= 0) { m_Leases.Remove(index); }
        return true;
    }

    // One line whenever a chain's refusal reason changes, never once per retry.
    void PreflightRefused(string chainId, string reason)
    {
        m_Activity.HCRefuse("preflight", reason);
        string previous;
        if (m_PreflightReasons.Find(chainId, previous) && previous == reason) { return; }
        if (m_PreflightReasons.Count() >= 16 && !m_PreflightReasons.Contains(chainId)) { return; }
        m_PreflightReasons.Set(chainId, reason);
        Print("[HollowCountry] V2 scene preflight refused id=" + chainId + " reason=" + reason);
    }

    string HCPacingIdentity(HCSceneChain chain)
    {
        return "scene:" + chain.Id + ":" + chain.Stage.ToString();
    }

    void Fail(HCSceneChain chain, int now, string reason)
    {
        m_Activity.HCRefuse("failed", reason);
        HCEventModule.HCCancelSituation(HCPacingIdentity(chain));
        HCEventModule.HCEndedSituation(HCPacingIdentity(chain));
        HCSceneChains.Cancel(chain, now);
        m_Refused = m_Refused + 1;
        if (!Commit(now)) { return; }
        Print("[HollowCountry] V2 scene chain cancelled id=" + chain.Id + " stage=" + chain.Stage.ToString() + " reason=" + reason);
    }

    void Work(int now)
    {
        m_Activity.HCHit("work");
        int paused = HCSceneChains.ResumeAfterGap(m_State, now);
        if (paused < 0) { Print("[HollowCountry] V2 scenes stopped; downtime exceeds clock bounds"); OnStop(); return; }
        if (paused > 0)
        {
            if (!Commit(now)) { return; }
            Print("[HollowCountry] V2 scene deadlines shifted downtime=" + paused.ToString());
        }
        if (m_State.Chains.Count() < 1) { return; }
        if (m_Cursor >= m_State.Chains.Count()) { m_Cursor = 0; }
        int selected = m_Cursor;
        m_Cursor = m_Cursor + 1;
        HCSceneChain chain = m_State.Chains[selected];
        HCSceneChainDefinition plan = m_State.Catalog.Chains[selected];
        HCSceneStageDefinition stage = plan.Stages[chain.Stage];
        HCSceneLease lease = Lease(chain.Id);
        if (chain.Cancelled || chain.Complete)
        {
            HCEventModule.HCCancelSituation(HCPacingIdentity(chain));
            HCEventModule.HCEndedSituation(HCPacingIdentity(chain));
            Cleanup(lease);
            return;
        }
        int status = HCEventStatus.ANNOUNCED;
        HCEventRecord record;
        if (chain.EventId > 0)
        {
            record = HCEventDirector.FindRecord(chain.Director, chain.EventId);
            if (!record) { Fail(chain, now, "missing-director-record"); return; }
            status = record.Status;
        }
        if (HCSceneChains.CancelExpired(chain, now, status))
        {
            Fail(chain, now, "stage-expired-or-failed");
            return;
        }
        if (status == HCEventStatus.COMPLETED)
        {
            if (!Cleanup(lease)) { return; }
            // Work runs only after the barrier is durable. Count the observed
            // completed stage once, before its identity advances or closes.
            m_Activity.HCHit("completed");
            Print("[HollowCountry] V2 scene stage complete id=" + chain.Id + " stage=" + chain.Stage.ToString());
            // End this stage's active pacing before the identity moves on.
            HCEventModule.HCEndedSituation(HCPacingIdentity(chain));
            if (chain.Stage + 1 >= plan.Stages.Count())
            {
                chain.Complete = true;
            }
            else
            {
                chain.Stage = chain.Stage + 1;
                HCSceneChains.Schedule(chain, plan.Stages[chain.Stage], now);
            }
            Commit(now);
            return;
        }
        if (now < chain.DueAt) { m_Activity.HCHit("not_due"); return; }
        if (!lease)
        {
            if (m_Leases.Count() >= 2) { HCEventModule.HCCancelSituation(HCPacingIdentity(chain)); m_Refused = m_Refused + 1; PreflightRefused(chain.Id, "lease-cap"); return; }
            HCEventSite site = HCSceneChains.HCPlanSite(plan);
            if (!site) { Fail(chain, now, "missing-reviewed-site"); return; }
            // A later chain may reuse this reviewed anchor, but never while an
            // earlier lease (even a closing/partially removed one) still owns it.
            if (!SiteAvailable(site.Position)) { HCEventModule.HCCancelSituation(HCPacingIdentity(chain)); m_Refused = m_Refused + 1; PreflightRefused(chain.Id, "site-unavailable"); return; }
            HCSceneKit kit = HCSceneKits.Find(stage.Kit);
            array<vector> positions;
            int variant;
            if (!HCSceneKits.Preflight(kit, site, positions, variant))
            {
                HCEventModule.HCCancelSituation(HCPacingIdentity(chain));
                m_Refused = m_Refused + 1;
                PreflightRefused(chain.Id, HCSceneKits.Refusal());
                return;
            }
            // Pacing precedes the existing durable Begin intent and native
            // placement. Blocked stages retain their original expiry and skip
            // through CancelExpired; disabled Events uses the owner rules.
            if (!HCEventModule.HCPaceSituation(HCPacingIdentity(chain), site.Position, chain.ExpiresAt - now)) { m_Activity.HCRefuse("pacing"); return; }
            if (chain.EventId == 0)
            {
                if (!HCSceneChains.Begin(chain, stage, now)) { Fail(chain, now, "director-refused"); return; }
                if (!Commit(now)) { return; }
            }
            // Record owned handles before the first native create. Partial kits
            // are cancelled and retained for observer-gated cleanup, never replaced.
            lease = new HCSceneLease;
            lease.ChainId = chain.Id;
            lease.Stage = chain.Stage;
            lease.Anchor = site.Position;
            lease.StoryPublished = false;
            lease.PlacementVariant = variant;
            m_Leases.Insert(lease);
            bool placed = HCSceneKits.Place(lease, kit, positions, variant);
            if (!placed) { Fail(chain, now, "placement-failed"); return; }
        }
        if (!HCSceneKits.HCPlacementComplete(lease)) { return; }
        if (!HCSceneKits.Healthy(lease)) { Fail(chain, now, "partial-or-missing-lease"); return; }
        if (!lease.StoryPublished)
        {
            HCEventModule.HCStartedSituation(HCPacingIdentity(chain));
            lease.StoryPublished = true;
            m_Placed = m_Placed + lease.Objects.Count();
            m_Activity.HCHit("placed");
            HCModuleReadiness.HCUse("Scenes", "scene_placed");
            Print("[HollowCountry] V2 scene placed id=" + chain.Id + " stage=" + chain.Stage.ToString() + " kit=" + stage.Kit + " layout=" + lease.PlacementVariant.ToString());
            PublishSceneStory(chain, HCSceneChains.HCPlanSite(plan));
            if (chain.Stage == 0 && (!m_Stories || !m_Stories.HCReady()))
            {
                HCWildlifeScenes.HCStoryOff(chain.Id);
            }
            m_PreflightReasons.Remove(chain.Id);
        }
        if (now - chain.BeganAt >= stage.HoldSeconds)
        {
            int result = HCEventDirector.SceneElapsed(chain.Director, HCSceneChains.Context(chain, now), chain.EventId, chain.BeganAt, stage.HoldSeconds);
            if (result != HCEventCode.OK) { Fail(chain, now, "director-stage-failed"); return; }
            if (!Commit(now)) { return; }
        }
    }

    override void OnTick(float deltaTime)
    {
        if (!GetGame() || !GetGame().IsServer()) { return; }
        if (m_Activity.HCDue(deltaTime))
        {
            int activeScenes;
            foreach (HCSceneLease activityLease : m_Leases)
            {
                if (!activityLease.Closing) { activeScenes++; }
            }
            int activityChains;
            if (m_State && m_State.Chains) { activityChains = m_State.Chains.Count(); }
            m_Activity.HCLog("[HollowCountry] V2 scenes", " active=" + activeScenes.ToString() + " chains=" + activityChains.ToString() + " running=" + m_Running.ToString());
        }
        if (!m_Running) { return; }
        // Keep one due slot while a barrier or placement owns the tick. Reset
        // only when Work runs, so a long wait cannot lose the slot or cause a burst.
        m_WorkElapsed = m_WorkElapsed + deltaTime;
        if (m_WorkElapsed > 10) { m_WorkElapsed = 10; }
        m_Store.HCPumpCheckpoint();
        if (!m_Store.HCCheckpointHealthy()) { m_Fault = "scene_save_failed"; OnStop(); return; }
        if (m_Store.HCBarrierPending())
        {
            m_Activity.HCRefuse("checkpoint");
            // Only a non-durable barrier blocks native work. Routine saves
            // never take this branch. Advance one budgeted HC-42 batch OR candidate
            // preflight: it only changes temporary selection/diagnostic caches.
            // Native clearance reads create no objects or saved-state mutations.
            // This branch returns before any prop creation or chain/save work.
            if (m_StoryIndex && m_Stories && m_Stories.HCReady()) { m_StoryIndex.HCStep(this); }
            return;
        }
        if (m_StoryOfferPending > 0)
        {
            HCWildlifeScenes wildlife = HCEcologyRuntimeModule.HCWildlife();
            foreach (HCSceneChain arrived : m_State.Chains)
            {
                if (arrived.StorySequence != m_StoryOfferPending) { continue; }
                HCEventModule.HCStoryArrived(arrived);
                if (wildlife) { wildlife.HCOffer(arrived, m_State); }
                break;
            }
            m_StoryOfferPending = 0;
            // Offers may queue their own durable receipt in the shared store.
            if (m_Store.HCBarrierPending()) { return; }
        }
        m_WorkBudget.HCReset(1);
        foreach (HCSceneLease buildingLease : m_Leases)
        {
            if (HCSceneKits.HCPlacementComplete(buildingLease)) { continue; }
            HCReached.Mark("scenes.placement_lease");
            // Review hardening: a lease whose kit failed to place waits for its Fail pass; never dereference it.
            if (!buildingLease.PlacementKit) { continue; }
            // #275: a placement queue must not starve the read-only pair cursor.
            // Alternate one index slice with one prop; never combine preflight
            // and object creation in the same tick. Stop taking these turns
            // once a candidate is cached, so placement retains every tick.
            if (m_StoryIndex && m_Stories && m_Stories.HCReady() && m_StoryIndex.HCNeedsStep())
            {
                m_IndexPlacementTurn = !m_IndexPlacementTurn;
                if (m_IndexPlacementTurn) { m_StoryIndex.HCStep(this); return; }
            }
            if (!m_WorkBudget.HCContinue()) { m_Activity.HCRefuse("budget"); m_WorkBudget.HCDeferred(GetName(), 1); return; }
            HCSceneKits.HCPlaceOne(buildingLease);
            int pendingProps = buildingLease.PlacementKit.Props.Count() - buildingLease.Objects.Count();
            m_WorkBudget.HCDeferred(GetName(), pendingProps);
            return;
        }
        // Loading/selection shares the scenes slice and never runs on a prop
        // creation tick or the chain/save slot. No index work when Stories is off.
        if (m_WorkElapsed < 10 && m_StoryIndex && m_Stories && m_Stories.HCReady()) { m_StoryIndex.HCStep(this); }
        if (m_WorkElapsed >= 10)
        {
            m_WorkElapsed = 0;
            int now = Now();
            if (now < m_LastNow || now < m_State.LastNow || now > 999000000)
            {
                Print("[HollowCountry] V2 scenes stopped; invalid or rewound UTC clock");
                OnStop();
                return;
            }
            m_LastNow = now;
            // One chain per ten seconds; at most two live kits of <=8 props.
            int revision = m_State.Revision;
            Work(now);
            // ResumeAfterGap must see the old heartbeat before HCCommit writes
            // LastNow. A Work barrier owns this slot until its mutation is durable.
            if (m_Running && !m_Store.HCBarrierPending() && m_State.Revision == revision) { StoryStep(now); }
            // Persist a heartbeat even while every chain is waiting; otherwise
            // an ordinary long stage would be mistaken for server downtime.
            if (m_Running && now - m_State.LastNow >= 60) { m_State.LastNow = now; m_Store.HCRequestCheckpoint(m_State, false); }
        }
    }

    // Issue #138 round 2: one stage of the heartbeat save per scheduler tick (serialize | verify current
    // | refresh backup | commit). The snapshot (with LastNow) is taken by the first stage.
    int HCStepRoutine()
    {
        if (!m_Running || !m_State) { return HCSaveJob.STEP_FAILED; }
        if (!m_Store.SaveInFlight()) { m_State.LastNow = m_LastNow; }
        int result = m_Store.SaveStep(m_State);
        if (result != HCSaveJob.STEP_FAILED) { return result; }
        m_Fault = "scene_heartbeat_save_failed";
        // Clear the job BEFORE OnStop: its HCFlush must not step a faulted save again.
        m_SaveJob.HCDirty = false;
        m_SaveJob.HCInFlight = false;
        OnStop();
        Print("[HollowCountry] V2 scenes heartbeat save failed; preserve store; cleanup pending");
        return HCSaveJob.STEP_FAILED;
    }

    void Summary()
    {
        int active = 0;
        int chains = 0;
        foreach (HCSceneLease lease : m_Leases)
        {
            if (!lease.Closing) { active = active + 1; }
        }
        if (m_State)
        {
            foreach (HCSceneChain chain : m_State.Chains)
            {
                if (!chain.Cancelled && !chain.Complete) { chains = chains + 1; }
            }
        }
        Print("[HollowCountry] V2 scenes active=" + active.ToString() + " chains=" + chains.ToString() + " placed=" + m_Placed.ToString() + " refused=" + m_Refused.ToString());
        m_SummaryPrinted = true;
    }

    // HCServer may drop stopped modules; keep ownership and a bounded queue
    // retry until all native references disappear. Never delete in front of players.
    void CleanupStopped()
    {
        if (!GetGame() || !GetGame().IsServer()) { return; }
        if (m_Leases.Count() > 0) { Cleanup(m_Leases[0]); }
        if (m_Leases.Count() == 0)
        {
            GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).Remove(CleanupStopped);
            if (s_CleanupOwner == this) { s_CleanupOwner = null; }
        }
    }

    override void OnStop()
    {
        if (m_Stopping) { return; }
        m_Stopping = true;
        if (m_State)
        {
            foreach (HCSceneChain stoppingChain : m_State.Chains) { HCEventModule.HCCancelSituation(HCPacingIdentity(stoppingChain)); }
        }
        HCSituationSource.HCClear(m_State);
        if (m_StoryIndex) { m_StoryIndex.HCStop(); }
        if (m_Stories) { m_Stories.HCStop(); }
        if (m_SaveJob)
        {
            // Finish the older snapshot before flushing current state at shutdown.
            if (m_SaveJob.HCInFlight && m_Store)
            {
                HCSaveScheduler.HCFlush(m_SaveJob);
                m_SaveJob.HCInFlight = false;
                m_SaveJob.HCDirty = true;
            }
            HCSaveScheduler.HCFlush(m_SaveJob);
            HCSaveScheduler.HCUnregister(m_SaveJob);
        }
        m_Running = false;
        HCDebugRelease();
        if (!GetGame() || !GetGame().IsServer() || m_Leases.Count() == 0) { return; }
        s_CleanupOwner = this;
        GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).Remove(CleanupStopped);
        GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(CleanupStopped, 10000, true);
    }
}

modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        Register(new HCScenesModule);
    }
}
