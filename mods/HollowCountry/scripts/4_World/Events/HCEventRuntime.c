// Narrow journal status seam for runtime refusal wording; no journal mutation.
modded class HCEventJournal
{
    bool HCRuntimeFaulted() { return m_Fault; }
}

// Scalar/session header only; Records are encoded one row per scheduler step.
// Native MakeData escapes all variable strings; assembled punctuation is fixed.
// This remains the original schema-1 object, not a new on-disk page format.
class HCEventJournalDirectorHeader
{
    int Version;
    string WorldName;
    string Session;
    int LastNow;
    int NextId;
    int PrunedThrough;
    int SessionGeneration;
    ref array<string> Sessions;
}

// W5-PERF-4: <=1 run cleanup/expiry + <=64 subscribed observations + <=1
// terminal-subscription purge/tick; cursors survive yields. Expiry/CLOSED
// journal continuations use HCSaveScheduler; native calls cannot be preempted.
// Ingress refuses during announcements; shutdown drains durable continuations.
// Timing native evidence: World/HCWorkBudget.c (Game.c:914).
// Durable orchestrator. The caller owns a fresh trusted session and invokes
// Tick/Disconnect from server lifecycle hooks. No rewards or network ingress.
// Native 1.30.164289: 1_Core/proto/EnScript.c:380/385/394/407/463/470
// array Count/Clear/Find/Insert/Remove/RemoveOrdered; EnConvert.c:30 int.ToString;
// 3_Game/gameplay.c:636 GetGame; Global/Game.c:1120 IsServer;
// Entities/Object.c:517 IsAlive. Provider/store/director calls are HC adapters.
// Native logging: 1_Core/proto/EnDebug.c:96 Print.
class HCEventRuntime
{
    protected ref HCEventSettings m_Settings;
    protected ref HCEventRuntimeState m_State;
    protected ref HCEventPersistence m_Store;
    protected ref HCEventObjectiveProvider m_Observer;
    protected ref HCEventAIProvider m_AI;
    protected ref array<ref HCEventSubscription> m_Subscriptions = new array<ref HCEventSubscription>();
    protected ref map<ref HCEventSubscription, bool> m_PendingLeaves = new map<ref HCEventSubscription, bool>;
    protected bool m_Ready = false;
    protected bool m_Busy = false;
    protected bool m_StopRequested = false;
    protected int m_LastNow = 0;
    protected int m_Cursor = 0;
    protected int m_RunCursor;
    protected int m_PurgeCursor;
    protected ref HCWorkBudget m_WorkBudget;
    protected ref array<string> m_BlockedLogged = new array<string>();
    protected string m_RetentionBlockedLine;
    // At most one cooldown per retained current-session record (32).
    protected ref array<int> m_ReofferIds = new array<int>();
    protected ref array<int> m_ReofferAfter = new array<int>();
    protected string m_Refusal;
    // Fixed reasons, retained across Start retries for this runtime lifetime.
    protected int m_ObservationCloneRefusals;
    protected int m_ObservationRunRefusals;

    protected HCEventRun HCRunAt(HCEventRuntimeState state, int eventId)
    {
        if (!state || !state.Director || !state.Runs) { return null; }
        if (eventId <= state.Director.PrunedThrough) { return null; }
        int index = eventId - state.Director.PrunedThrough - 1;
        if (index < 0 || index >= state.Runs.Count()) { return null; }
        return state.Runs[eventId - state.Director.PrunedThrough - 1];
    }
    protected void HCObservationRefused(bool cloneMissing)
    {
        int count;
        string reason;
        if (cloneMissing)
        {
            if (m_ObservationCloneRefusals < 1000000000) { m_ObservationCloneRefusals++; }
            count = m_ObservationCloneRefusals;
            reason = "clone-unavailable";
        }
        else
        {
            if (m_ObservationRunRefusals < 1000000000) { m_ObservationRunRefusals++; }
            count = m_ObservationRunRefusals;
            reason = "clone-run-unavailable";
        }
        if (count == 1) { Print("[HC Events] observation refused reason=" + reason + " count=" + count.ToString()); }
    }
    protected ref HCEventRuntimeState m_PendingPublish;
    protected ref HCEventJournal m_PendingJournal;
    protected ref HCEventJournalSaveJob m_JournalJob;
    protected ref HCStepTimer m_TickSteps;
    protected int m_PendingExpiryId;
    protected int m_PendingExpiryAt;
    protected ref HCEventSubscription m_PendingLeave;
    protected ref array<int> m_SceneRetirements = new array<int>;

    protected ref array<int> m_FailedSceneRetirements = new array<int>;

    bool HCTakeSceneRetirementFailure(int id)
    {
        int index = m_FailedSceneRetirements.Find(id);
        if (index < 0) { return false; }
        m_FailedSceneRetirements.RemoveOrdered(index);
        return true;
    }
    protected void HCRefuseSceneRetirement(int id, string reason)
    {
        m_SceneRetirements.RemoveOrdered(0);
        // Combined pending/failure ownership is capped at the two scene leases.
        m_FailedSceneRetirements.Insert(id);
        Print("[HC Events] scene retirement abandoned reason=" + reason + "; Scenes release view and keep props");
    }

    // Two scene leases at most; retain cancellation ownership after retry-cap release.
    bool HCQueueSceneRetirement(int id)
    {
        if (!m_Ready || id < 1) { return false; }
        if (m_SceneRetirements.Find(id) >= 0) { return true; }
        if (m_SceneRetirements.Count() + m_FailedSceneRetirements.Count() >= 2) { return false; }
        m_SceneRetirements.Insert(id);
        return true;
    }
    bool HCAnnounceOwned() { return HCAnnouncePending() || m_AnnounceReceipt != ""; }
    protected void HCPublishRefused()
    {
        HCEventJournal journal = HCEventJournal.Cast(m_Store);
        if (journal && journal.HCRuntimeFaulted())
        {
            Print("[HC Events] journal fault; mutations disabled, cleanup remains pending");
        }
        else { Print("[HC Events] store limit or candidate refused; mutations disabled, cleanup remains pending"); }
    }
    protected void HCFinishLeave(HCEventSubscription leaving)
    {
        int eventId = leaving.EventId;
        HCEventRun leavingRun = HCRunAt(m_State, eventId);
        if (!leavingRun) { return; }
        PlayerBase player = leaving.Player;
        m_Subscriptions.RemoveItem(leaving);
        m_PendingLeaves.Remove(leaving);
        m_Busy = true;
        m_Observer.Forget(leavingRun.Lease, player);
        m_Busy = false;
    }

    void HCSetStepTimer(HCStepTimer timer) { m_TickSteps = timer; }
    // BLOCKED plus HCAnnouncePending is a yield, not an admission failure.
    protected int m_AnnounceStage;
    protected bool m_StageNextAnnounce;
    protected bool m_AnnounceStaged;
    protected string m_AnnounceReceipt;
    protected string m_AnnounceReceiptSession;
    protected int m_AnnounceReceiptTicks;
    protected int m_AnnounceResult = HCEventCode.BLOCKED;
    protected int m_AnnounceRepeat;
    protected int m_AnnounceId;
    protected bool m_AnnounceStarted;
    protected ref HCEventMission m_AnnounceMission;
    protected ref HCEventContext m_AnnounceContext;
    protected ref HCEventRuntimeState m_AnnounceCandidate;
    bool HCAnnouncePending() { return m_AnnounceStage > 0; }
    bool HCPublishPending() { return m_PendingPublish != null || HCAnnouncePending(); }
    bool HCOperational() { return m_Ready; }
    bool HCCancelPending()
    {
        return m_Ready && !m_StopRequested && m_Settings && m_Settings.Enabled && (m_Busy || HCPublishPending());
    }
    protected void HCMeasured(string stage, int started)
    {
        if (m_TickSteps) { m_TickSteps.HCItem(stage, TickCount(started)); }
    }

    // Maintenance and announcements share one journal continuation. Other
    // mutations refuse throughout announcement ownership, including between saves.
    protected bool HCBeginPublish(HCEventRuntimeState candidate)
    {
        HCEventJournal journal = HCEventJournal.Cast(m_Store);
        if (!journal) { return Publish(candidate); }
        if (m_PendingPublish) { return false; }
        if (!candidate || candidate.Revision >= 999999999)
        {
            m_Ready = false;
            FaultCleanup();
            HCPublishRefused();
            return false;
        }
        candidate.Revision++;
        // Reject caller state before the journal can enter its faulted state.
        if (!HCEventRuntimePolicy.StateValid(candidate))
        {
            m_Ready = false;
            FaultCleanup();
            HCPublishRefused();
            return false;
        }
        if (!journal.HCBeginSave(candidate))
        {
            m_Ready = false;
            FaultCleanup();
            HCPublishRefused();
            return false;
        }
        m_PendingPublish = candidate;
        m_PendingJournal = journal;
        m_JournalJob = new HCEventJournalSaveJob;
        m_JournalJob.Result = HCSaveJob.STEP_MORE;
        m_JournalJob.Journal = journal;
        journal.HCSetSaveTimer(m_TickSteps);
        HCSaveScheduler.HCRegister(m_JournalJob);
        // These are durable continuations, not debounced routine snapshots.
        m_JournalJob.HCDirty = true;
        m_JournalJob.HCUrgent = true;
        m_JournalJob.HCDue = 0;
        return true;
    }

    protected bool HCAdvancePublish(bool drain = false)
    {
        if (!m_PendingPublish) { return true; }
        int started = TickCount(0);
        if (drain)
        {
            // Ingress/shutdown retain their existing durability barrier. Flush
            // advances the same job and cancels scheduler ownership on return.
            if (!HCSaveScheduler.HCFlush(m_JournalJob)) { m_JournalJob.Result = HCSaveJob.STEP_FAILED; }
            if (m_TickSteps) { m_TickSteps.HCDeferred(TickCount(started)); }
        }
        else { HCSaveScheduler.HCPumpFallback(m_JournalJob); }
        int result = m_JournalJob.Result;
        if (result == HCSaveJob.STEP_MORE) { return true; }
        HCSaveScheduler.HCUnregister(m_JournalJob);
        m_JournalJob = null;
        if (result == HCSaveJob.STEP_DONE)
        {
            m_State = m_PendingPublish;
            if (m_PendingLeave) { HCFinishLeave(m_PendingLeave); }
            if (m_PendingExpiryId > 0)
            {
                HCEventRecord expiryRecord = HCEventDirector.FindRecord(m_State.Director, m_PendingExpiryId);
                if (expiryRecord) { RememberCooldown(expiryRecord, m_PendingExpiryAt); }
            }
        }
        m_PendingPublish = null;
        m_PendingJournal = null;
        m_PendingExpiryId = 0;
        m_PendingLeave = null;
        if (result == HCSaveJob.STEP_FAILED)
        {
            m_Ready = false;
            FaultCleanup();
            HCPublishRefused();
            return false;
        }
        return true;
    }

    void ~HCEventRuntime()
    {
        HCSaveScheduler.HCUnregister(m_JournalJob);
    }

    // Reason of the last refused Start (cleared at each Start). Start runs once
    // per module start, so each refusal logs one line; no player identity.
    string Refusal() { return m_Refusal; }
    bool HCRefuse(string reason)
    {
        m_Refusal = reason;
        Print("[HC Events] runtime start refused reason=" + reason);
        return false;
    }
    bool Start(HCEventSettings settings, HCEventContext context, HCEventPersistence store, HCEventObjectiveProvider observer, HCEventAIProvider ai)
    {
        m_Ready = false;
        m_Busy = false;
        m_StopRequested = false;
        m_AnnounceStage = 0;
        m_StageNextAnnounce = false;
        m_AnnounceStaged = false;
        m_AnnounceReceipt = "";
        m_AnnounceReceiptSession = "";
        m_AnnounceReceiptTicks = 0;
        m_AnnounceResult = HCEventCode.BLOCKED;
        m_AnnounceRepeat = 0;
        m_AnnounceId = 0;
        m_AnnounceStarted = false;
        m_AnnounceMission = null;
        m_AnnounceContext = null;
        m_AnnounceCandidate = null;
        m_PendingPublish = null;
        m_PendingJournal = null;
        m_PendingExpiryId = 0;
        m_PendingLeaves.Clear();
        m_PendingLeave = null;
        m_SceneRetirements.Clear();
        m_FailedSceneRetirements.Clear();
        m_Subscriptions = new array<ref HCEventSubscription>();
        m_BlockedLogged = new array<string>();
        m_RetentionBlockedLine = "";
        m_ReofferIds = new array<int>();
        m_ReofferAfter = new array<int>();
        m_Refusal = "";
        m_Cursor = 0;
        m_RunCursor = 0;
        m_PurgeCursor = 0;
        m_WorkBudget = new HCWorkBudget;
        if (!HCEventRuntimePolicy.SettingsValid(settings) || !settings.Enabled || !context || !context.Server)
        {
            return HCRefuse("settings_or_context_invalid");
        }
        if (!store || !observer || !ai || context.Now < 0 || context.Now > 1000000000)
        {
            return HCRefuse("dependency_missing_or_clock_range");
        }
        m_Settings = settings;
        m_Store = store;
        m_Observer = observer;
        m_AI = ai;
        HCEventRuntimeState state = store.Load(context.WorldName);
        if (!state || !HCEventRuntimePolicy.StateValid(state) || state.Director.WorldName != context.WorldName)
        {
            return HCRefuse("persistence_admission_failed");
        }
        m_State = state;
        if (state.Director.Session != context.Session)
        {
            HCEventContext previous = new HCEventContext;
            previous.Server = true;
            previous.WorldName = state.Director.WorldName;
            previous.Session = state.Director.Session;
            previous.Now = state.Director.LastNow;
            state = m_Store.Clone(state);
            if (!state || HCEventDirector.Restart(state.Director, previous, context.Session) != HCEventCode.OK)
            {
                return HCRefuse("session_restart_rejected");
            }
            foreach (HCEventRun run : state.Runs)
            {
                if (run.Phase != HCEventRunPhase.CLOSED)
                {
                    run.Phase = HCEventRunPhase.CLEANUP;
                }
            }
            if (!Publish(state))
            {
                return HCRefuse("restart_state_not_persisted");
            }
            context.Session = m_State.Director.Session;
        }
        if (!HCEventDirector.ContextValid(m_State.Director, context))
        {
            return HCRefuse("context_rejected");
        }
        // A process restart must use a fresh session. Rebinding a live state
        // without cancellation would retain persisted participants, not handles.
        foreach (HCEventRecord record : m_State.Director.Records)
        {
            if (!HCEventDirector.Terminal(record.Status))
            {
                return HCRefuse("restored_live_session");
            }
        }
        // Complete durable restart cleanup before the caller's first roster pass.
        // Unconfirmed provider cleanup stays pending and cannot be pruned.
        HCEventRuntimeState restored = m_State;
        int closed = 0;
        foreach (HCEventRun restoredRun : restored.Runs)
        {
            if (restoredRun.Phase == HCEventRunPhase.CLEANUP)
            {
                if (!Cleanup(restoredRun.EventId)) { return HCRefuse("startup_cleanup_unconfirmed"); }
                HCEventRun closedRun = HCRunAt(m_State, restoredRun.EventId);
                if (!closedRun) { return HCRefuse("startup_cleanup_run_unavailable"); }
                if (closedRun.Phase == HCEventRunPhase.CLOSED)
                {
                    closed = closed + 1;
                }
                else
                {
                    Print("[HC Events] startup cleanup pending; " + restoredRun.Lease);
                }
            }
        }
        if (closed > 0) { Print("[HC Events] startup cleanup closed " + closed.ToString() + " retained runs before roster; observation_clone_refusals=" + m_ObservationCloneRefusals.ToString() + " observation_run_refusals=" + m_ObservationRunRefusals.ToString()); }
        m_LastNow = context.Now;
        m_Ready = true;
        return true;
    }
    // Observations read the last committed state while an announce owns its candidate.
    bool HCReadAllowed(HCEventContext context)
    {
        return m_Ready && !m_Busy && !m_StopRequested && m_State && m_State.Director && m_State.Runs && m_Settings.Enabled && context && context.Now >= m_LastNow && HCEventDirector.ContextValid(m_State.Director, context);
    }
    bool Allowed(HCEventContext context)
    {
        if (HCAnnouncePending()) { return false; }
        // Refuse before any mutation. Callers return BLOCKED/false and may retry;
        // player ingress must never drain hundreds of journal stages in one tick.
        // The scheduler retains an active large job until it completes: an
        // urgent journal can wait behind that job (up to its bounded stage count,
        // e.g. <=10,304 stages at 8 MiB). BLOCKED lasts through that wait plus
        // journal commit; callers retry without mutating or losing an action.
        if (m_PendingPublish) { return false; }
        return HCReadAllowed(context);
    }
    bool Publish(HCEventRuntimeState candidate)
    {
        if (!candidate || candidate.Revision >= 999999999)
        {
            m_Ready = false;
            return false;
        }
        candidate.Revision = candidate.Revision + 1;
        if (!HCEventRuntimePolicy.StateValid(candidate) || !m_Store.Save(candidate))
        {
            m_Ready = false;
            FaultCleanup();
            HCPublishRefused();
            return false;
        }
        m_State = candidate;
        return true;
    }
    void FaultCleanup()
    {
        // Existing durable intent authorizes a best-effort stop even when the
        // next write failed. Never publish CLOSED or infer successful cleanup.
        if (!m_State || !m_State.Director || !m_State.Runs)
        {
            return;
        }
        m_Busy = true;
        foreach (HCEventRun run : m_State.Runs)
        {
            if (!run) { continue; }
            if (run.ProviderIntent && run.Phase != HCEventRunPhase.CLOSED)
            {
                if (run.Objective.Family == HCEventFamily.AI_ENCOUNTER)
                {
                    HCEventRecord aiRecord = HCEventDirector.FindRecord(m_State.Director, run.EventId);
                    if (!aiRecord) { continue; }
                    int aiGeneration = aiRecord.Expires - aiRecord.Definition.LifetimeSeconds;
                    string aiLease = run.Lease + ":" + aiGeneration.ToString();
                    m_AI.Stop(aiLease);
                }
                else
                {
                    m_Observer.Release(run.Lease);
                }
            }
        }
        m_Busy = false;
    }
    HCEventRuntimeState Snapshot()
    {
        return m_Store.Clone(m_State);
    }
    int Revision()
    {
        return m_State.Revision;
    }
    int PublicEventId(int slot)
    {
        // Wire IDs remain 1..32 for the existing client. No current-session
        // record is pruned, so these slots remain stable for this session.
        int current = 0;
        foreach (HCEventRecord record : m_State.Director.Records)
        {
            if (record.Session == m_State.Director.Session)
            {
                current = current + 1;
                if (current == slot)
                {
                    return record.Id;
                }
            }
        }
        return 0;
    }
    bool Retain(HCEventRuntimeState state)
    {
        if (!state || !state.Director || !state.Runs) { return false; }
        while (state.Runs.Count() >= m_Settings.MaxRuns)
        {
            if (!state.Runs[0]) { return false; }
            if (state.Runs[0].Phase != HCEventRunPhase.CLOSED || !HCEventDirector.PruneFirst(state.Director))
            {
                int phase = state.Runs[0].Phase;
                // Roster refresh retries every few seconds; print each distinct blocker once.
                string blocked = "[HC Events] retention blocked by oldest run " + state.Runs[0].Lease + " phase " + phase.ToString() + "; new announcements refused until it closes";
                if (blocked != m_RetentionBlockedLine)
                {
                    m_RetentionBlockedLine = blocked;
                    Print("" + blocked);
                    return false;
                }
                return false;
            }
            state.Runs.RemoveOrdered(0);
        }
        return true;
    }
    int Operation(HCEventRuntimeState state, int id, int op, string participant, HCEventContext context)
    {
        HCEventRun operationRun = HCRunAt(state, id);
        if (!operationRun) { return HCEventCode.NOT_FOUND; }
        HCEventRecord record = HCEventDirector.FindRecord(state.Director, id);
        if (!record)
        {
            return HCEventCode.NOT_FOUND;
        }
        HCEventRequest request = new HCEventRequest;
        request.EventId = id;
        request.ExpectedRevision = record.Revision;
        request.Op = op;
        request.ParticipantId = participant;
        return HCEventDirector.Command(state.Director, context, request);
    }
    // All live callers yield through the same durable announcement slot.
    int HCAnnounceStaged(HCEventMission mission, HCEventContext context)
    {
        if (HCPublishPending() || HCAnnounceOwned()) { return HCEventCode.BLOCKED; }
        m_StageNextAnnounce = true;
        int result = Announce(mission, context);
        m_StageNextAnnounce = false;
        return result;
    }
    int Announce(HCEventMission mission, HCEventContext context)
    {
        // A durable completion is a receipt, independent of current admission gates.
        if (mission && context && m_AnnounceReceipt != "" && m_AnnounceReceipt == mission.Id && m_AnnounceReceiptSession == context.Session)
        {
            m_AnnounceReceipt = "";
            m_AnnounceReceiptSession = "";
            m_AnnounceReceiptTicks = 0;
            return m_AnnounceResult;
        }
        if (HCAnnounceOwned()) { return HCEventCode.BLOCKED; }
        if (!Allowed(context))
        {
            if (m_PendingPublish) { return HCEventCode.BLOCKED; }
            return HCEventCode.DENIED;
        }
        if (!HCEventRuntimePolicy.MissionValid(mission, context.WorldName))
        {
            return HCEventCode.INVALID;
        }
        int repeatId = 0;
        foreach (HCEventRecord existingRecord : m_State.Director.Records)
        {
            if (existingRecord.Session == context.Session && existingRecord.Definition.Id == mission.Id)
            {
                if (!CanReoffer(existingRecord, context.Now)) { return HCEventCode.CONFLICT; }
                repeatId = existingRecord.Id;
            }
        }
        int reservedActors = mission.ActorBudget;
        foreach (HCEventRun existing : m_State.Runs)
        {
            if (existing.Phase != HCEventRunPhase.CLOSED)
            {
                reservedActors = reservedActors + existing.Objective.ActorBudget;
            }
        }
        if (reservedActors > 64)
        {
            return HCEventCode.LIMIT;
        }
        m_Busy = true;
        bool ready = false;
        if (mission.Family == HCEventFamily.AI_ENCOUNTER)
        {
            ready = m_AI.Ready(context.WorldName);
        }
        else
        {
            ready = m_Observer.Ready(mission);
        }
        m_Busy = false;
        if (!ready)
        {
            // Roster refresh retries every few seconds: log once per mission per session.
            if (m_BlockedLogged.Count() < 64 && m_BlockedLogged.Find(mission.Id) < 0)
            {
                m_BlockedLogged.Insert(mission.Id);
                Print("[HC Events] mission blocked: required provider or reviewed target unavailable; " + mission.Id);
            }
            return HCEventCode.BLOCKED;
        }
        int freezeStarted = TickCount(0);
        m_AnnounceMission = m_Store.CloneMission(mission);
        HCMeasured("announce_freeze", freezeStarted);
        if (!m_AnnounceMission) { return HCEventCode.BLOCKED; }
        m_AnnounceContext = new HCEventContext;
        m_AnnounceContext.Server = context.Server;
        m_AnnounceContext.WorldName = context.WorldName;
        m_AnnounceContext.Session = context.Session;
        m_AnnounceContext.Now = context.Now;
        m_AnnounceRepeat = repeatId;
        m_AnnounceStarted = false;
        m_AnnounceResult = HCEventCode.BLOCKED;
        m_AnnounceStaged = m_StageNextAnnounce;
        m_AnnounceStage = 1;
        if (!m_AnnounceStaged)
        {
            while (HCAnnouncePending()) { HCAdvanceAnnounce(true); }
            return m_AnnounceResult;
        }
        return HCEventCode.BLOCKED;
    }
    // Failed completions never invoke modded Announce hooks. Successful ones
    // consume through Announce before admission gates, retaining the durable-OK hook.
    int HCTakeAnnounceResult(HCEventMission mission, HCEventContext context)
    {
        if (!mission || !context || m_AnnounceReceipt == "" || m_AnnounceReceipt != mission.Id || m_AnnounceReceiptSession != context.Session) { return HCEventCode.DENIED; }
        if (m_AnnounceResult == HCEventCode.OK) { return Announce(mission, context); }
        int result = m_AnnounceResult;
        m_AnnounceReceipt = "";
        m_AnnounceReceiptSession = "";
        m_AnnounceReceiptTicks = 0;
        return result;
    }
    protected int HCAnnounceOperation(HCEventRuntimeState candidate, HCEventMission mission, HCEventContext context, int repeatId)
    {
        if (!candidate || !candidate.Director || !candidate.Runs) { return HCEventCode.BLOCKED; }
        HCEventRun run;
        if (repeatId > 0)
        {
            // Reuse the stable wire slot, rather than pruning current-session
            // tombstones or changing the director's duplicate proposal policy.
            if (context.Now > 1000000000 - mission.LifetimeSeconds) { return HCEventCode.LIMIT; }
            PurgeTerminal();
            run = HCRunAt(candidate, repeatId);
            if (!run) { return HCEventCode.NOT_FOUND; }
            HCEventRecord repeated = HCEventDirector.FindRecord(candidate.Director, repeatId);
            if (!repeated) { return HCEventCode.NOT_FOUND; }
            repeated.Definition = HCEventRuntimePolicy.Definition(mission);
            repeated.Revision = repeated.Revision + 1;
            repeated.Status = HCEventStatus.PROPOSED;
            repeated.Expires = context.Now + mission.LifetimeSeconds;
            repeated.Progress = 0;
            repeated.LastObservation = 0;
            repeated.Participants.Clear();
            run.Objective = mission;
            run.Phase = HCEventRunPhase.PREPARED;
            run.Tokens.Clear();
        }
        else
        {
            if (!Retain(candidate)) { return HCEventCode.LIMIT; }
            HCEventDefinition definition = HCEventRuntimePolicy.Definition(mission);
            int result = HCEventDirector.Propose(candidate.Director, context, definition);
            if (result != HCEventCode.OK) { return result; }
            run = new HCEventRun;
            run.EventId = candidate.Director.NextId - 1;
            run.Lease = context.Session + ":" + run.EventId.ToString();
            run.Objective = mission;
            run.ProviderIntent = true;
            candidate.Runs.Insert(run);
        }
        if (Operation(candidate, run.EventId, HCEventOp.ANNOUNCE, "", context) != HCEventCode.OK)
        {
            return HCEventCode.BLOCKED;
        }
        m_AnnounceId = run.EventId;
        return HCEventCode.OK;
    }
    protected void HCFinishAnnounce(int result)
    {
        m_AnnounceResult = result;
        if (m_AnnounceStaged && !m_StopRequested)
        {
            m_AnnounceReceiptTicks = 0;
            m_AnnounceReceipt = m_AnnounceMission.Id;
            m_AnnounceReceiptSession = m_AnnounceContext.Session;
        }
        m_AnnounceStage = 0;
        m_AnnounceCandidate = null;
        m_AnnounceMission = null;
        m_AnnounceContext = null;
    }
    // One clone/operation/provider step per tick. Journal work is scheduler-owned.
    // No candidate becomes visible before commit readback.
    protected void HCAdvanceAnnounce(bool drain = false)
    {
        int started = TickCount(0);
        if (m_AnnounceStage == 1)
        {
            m_AnnounceCandidate = m_Store.Clone(m_State);
            HCMeasured("announce_clone", started);
            if (!m_AnnounceCandidate) { HCFinishAnnounce(HCEventCode.BLOCKED); return; }
            m_AnnounceStage = 2;
        }
        else if (m_AnnounceStage == 2)
        {
            int result = HCAnnounceOperation(m_AnnounceCandidate, m_AnnounceMission, m_AnnounceContext, m_AnnounceRepeat);
            HCMeasured("announce_op", started);
            if (result != HCEventCode.OK) { HCFinishAnnounce(result); return; }
            m_AnnounceStage = 3;
        }
        else if (m_AnnounceStage == 3 || m_AnnounceStage == 7)
        {
            if (!HCBeginPublish(m_AnnounceCandidate))
            {
                HCFinishAnnounce(HCEventCode.BLOCKED);
                return;
            }
            m_AnnounceCandidate = null;
            m_AnnounceStage++;
            HCMeasured("announce_save", started);
        }
        else if (m_AnnounceStage == 4 || m_AnnounceStage == 8)
        {
            if (!HCAdvancePublish(drain)) { HCFinishAnnounce(HCEventCode.BLOCKED); return; }
            if (m_PendingPublish) { return; }
            if (m_AnnounceStage == 8)
            {
                if (m_AnnounceStarted)
                {
                    if (m_AnnounceRepeat > 0) { Print("[HC Events] mission re-announced after cooldown; " + m_AnnounceMission.Id); }
                    HCFinishAnnounce(HCEventCode.OK);
                }
                else { HCFinishAnnounce(HCEventCode.BLOCKED); }
                return;
            }
            if (m_AnnounceRepeat > 0)
            {
                int cooldownIndex = m_ReofferIds.Find(m_AnnounceRepeat);
                if (cooldownIndex >= 0)
                {
                    m_ReofferIds.Remove(cooldownIndex);
                    m_ReofferAfter.Remove(cooldownIndex);
                }
            }
            m_LastNow = m_AnnounceContext.Now;
            m_AnnounceStage = 5;
        }
        else if (m_AnnounceStage == 5)
        {
            HCEventRun run = HCRunAt(m_State, m_AnnounceId);
            if (!run) { HCFinishAnnounce(HCEventCode.BLOCKED); return; }
            m_Busy = true;
            if (m_StopRequested) { m_AnnounceStarted = false; }
            else if (run.Objective.Family == HCEventFamily.AI_ENCOUNTER)
            {
                HCEventRecord aiRecord = HCEventDirector.FindRecord(m_State.Director, run.EventId);
                if (!aiRecord) { m_Busy = false; HCFinishAnnounce(HCEventCode.BLOCKED); return; }
                int generation = aiRecord.Expires - aiRecord.Definition.LifetimeSeconds;
                string lease = run.Lease + ":" + generation.ToString();
                m_AnnounceStarted = m_AI.Start(lease, m_AnnounceContext.Session, run.Objective.Id, run.Objective.Source, run.Objective.ActorBudget);
            }
            else
            {
                HCEventMission frozen = m_Store.CloneMission(run.Objective);
                if (frozen) { m_AnnounceStarted = m_Observer.Prepare(run.Lease, frozen); }
            }
            m_Busy = false;
            HCMeasured("announce_prepare", started);
            m_AnnounceStage = 6;
        }
        else if (m_AnnounceStage == 6)
        {
            m_AnnounceCandidate = m_Store.Clone(m_State);
            HCMeasured("announce_clone", started);
            if (!m_AnnounceCandidate)
            {
                m_Ready = false;
                FaultCleanup();
                HCPublishRefused();
                HCFinishAnnounce(HCEventCode.BLOCKED);
                return;
            }
            HCEventRun nextRun = HCRunAt(m_AnnounceCandidate, m_AnnounceId);
            if (!nextRun)
            {
                m_Ready = false;
                FaultCleanup();
                HCPublishRefused();
                HCFinishAnnounce(HCEventCode.BLOCKED);
                return;
            }
            if (m_AnnounceStarted) { nextRun.Phase = HCEventRunPhase.ACTIVE; }
            else
            {
                if (Operation(m_AnnounceCandidate, m_AnnounceId, HCEventOp.CANCEL, "", m_AnnounceContext) != HCEventCode.OK)
                {
                    m_Ready = false;
                    FaultCleanup();
                    HCPublishRefused();
                    HCFinishAnnounce(HCEventCode.BLOCKED);
                    return;
                }
                nextRun.Phase = HCEventRunPhase.CLEANUP;
            }
            m_AnnounceStage = 7;
        }
    }
    void RememberCooldown(HCEventRecord record, int now)
    {
        if (!record || record.Session != m_State.Director.Session) { return; }
        bool repeatable = record.Status == HCEventStatus.COMPLETED || record.Status == HCEventStatus.EXPIRED;
        if (!repeatable || m_ReofferIds.Find(record.Id) >= 0 || m_ReofferIds.Count() >= 32) { return; }
        m_ReofferIds.Insert(record.Id);
        m_ReofferAfter.Insert(now + 7200);
    }
    bool CanReoffer(HCEventRecord record, int now)
    {
        if (!record) { return false; }
        bool repeatable = record.Status == HCEventStatus.COMPLETED || record.Status == HCEventStatus.EXPIRED;
        if (!repeatable || record.Revision >= 999998) { return false; }
        HCEventRun run = HCRunAt(m_State, record.Id);
        if (!run) { return false; }
        if (run.Phase != HCEventRunPhase.CLOSED) { return false; }
        int cooldownIndex = m_ReofferIds.Find(record.Id);
        if (cooldownIndex < 0) { return false; }
        return now >= m_ReofferAfter[cooldownIndex];
    }
    int HCMissionEventId(string missionId)
    {
        foreach (HCEventRecord record : m_State.Director.Records)
        {
            if (record.Session == m_State.Director.Session && record.Definition.Id == missionId) { return record.Id; }
        }
        return 0;
    }
    // Read only the last committed record; never clone for a view status check.
    int HCCommittedEventStatus(int id)
    {
        HCEventRecord record = HCEventDirector.FindRecord(m_State.Director, id);
        if (!record) { return -1; }
        return record.Status;
    }
    bool HasMission(string missionId)
    {
        foreach (HCEventRecord record : m_State.Director.Records)
        {
            if (record.Session == m_State.Director.Session && record.Definition.Id == missionId)
            {
                return !CanReoffer(record, m_LastNow);
            }
        }
        return false;
    }
    void ItemDelivered(ItemBase item, PlayerBase participant, EntityAI destination, HCEventContext context)
    {
        if (!HCReadAllowed(context) || !item) { return; }
        string identity = HCEventNativeObserver.Identity(participant);
        if (identity == "") { return; }
        foreach (HCEventSubscription sub : m_Subscriptions)
        {
            if (sub.Player == participant && sub.ParticipantId == identity && !m_PendingLeaves.Contains(sub))
            {
                HCEventRun run = HCRunAt(m_State, sub.EventId);
                if (!run) { return; }
                HCEventRecord record = HCEventDirector.FindRecord(m_State.Director, sub.EventId);
                if (!record) { return; }
                if (record.Status == HCEventStatus.ACTIVE && context.Now < record.Expires && run.Objective.Family == HCEventFamily.DELIVERY)
                {
                    m_Observer.RecordDelivery(run.Lease, item, participant, destination);
                }
            }
        }
    }
    void InfectedKilled(ZombieBase infected, PlayerBase participant, HCEventContext context)
    {
        if (!HCReadAllowed(context) || !infected || infected.IsAlive()) { return; }
        string identity = HCEventNativeObserver.Identity(participant);
        if (identity == "") { return; }
        foreach (HCEventSubscription sub : m_Subscriptions)
        {
            if (sub.Player == participant && sub.ParticipantId == identity && !m_PendingLeaves.Contains(sub))
            {
                HCEventRun run = HCRunAt(m_State, sub.EventId);
                if (!run) { return; }
                HCEventRecord record = HCEventDirector.FindRecord(m_State.Director, sub.EventId);
                if (!record) { return; }
                if (record.Status == HCEventStatus.ACTIVE && context.Now < record.Expires && run.Objective.Family == HCEventFamily.INFECTED_CLEAR)
                {
                    m_Observer.RecordKill(run.Lease, infected, identity);
                }
            }
        }
    }
    int Binding(int id, PlayerBase player)
    {
        int index = 0;
        foreach (HCEventSubscription sub : m_Subscriptions)
        {
            if (sub.EventId == id && sub.Player == player)
            {
                return index;
            }
            index = index + 1;
        }
        return -1;
    }
    int Join(int id, PlayerBase player, HCEventContext context)
    {
        if (!Allowed(context))
        {
            if (m_PendingPublish) { return HCEventCode.BLOCKED; }
            return HCEventCode.DENIED;
        }
        string identity = HCEventNativeObserver.Identity(player);
        if (identity == "")
        {
            return HCEventCode.DENIED;
        }
        if (m_Subscriptions.Count() >= m_Settings.MaxSubscriptions)
        {
            return HCEventCode.LIMIT;
        }
        HCEventRuntimeState candidate = m_Store.Clone(m_State);
        int result = Operation(candidate, id, HCEventOp.JOIN, identity, context);
        if (result != HCEventCode.OK)
        {
            return result;
        }
        HCEventRecord joinedRecord = HCEventDirector.FindRecord(candidate.Director, id);
        if (!joinedRecord) { return HCEventCode.NOT_FOUND; }
        if (joinedRecord.Status == HCEventStatus.ANNOUNCED)
        {
            if (Operation(candidate, id, HCEventOp.ACTIVATE, "", context) != HCEventCode.OK)
            {
                return HCEventCode.BLOCKED;
            }
        }
        if (!Publish(candidate))
        {
            return HCEventCode.BLOCKED;
        }
        HCEventSubscription sub = new HCEventSubscription;
        sub.EventId = id;
        sub.Player = player;
        sub.ParticipantId = identity;
        m_Subscriptions.Insert(sub);
        m_LastNow = context.Now;
        return HCEventCode.OK;
    }
    int Leave(int id, PlayerBase player, HCEventContext context)
    {
        if (!HCReadAllowed(context))
        {
            return HCEventCode.DENIED;
        }
        int index = Binding(id, player);
        if (index < 0)
        {
            return HCEventCode.DENIED;
        }
        HCEventSubscription sub = m_Subscriptions[index];
        if (HCPublishPending())
        {
            // At most MaxSubscriptions retained requests, with duplicates coalesced.
            // Do not publish over the announcement's private candidate.
            if (!m_PendingLeaves.Contains(sub)) { m_PendingLeaves.Insert(sub, true); }
            return HCEventCode.OK;
        }
        HCEventRuntimeState candidate = m_Store.Clone(m_State);
        int result = Operation(candidate, id, HCEventOp.LEAVE, sub.ParticipantId, context);
        if (result != HCEventCode.OK)
        {
            return result;
        }
        if (!Publish(candidate))
        {
            return HCEventCode.BLOCKED;
        }
        HCEventRun departedRun = HCRunAt(m_State, id);
        if (!departedRun) { return HCEventCode.NOT_FOUND; }
        m_Subscriptions.Remove(index);
        m_Busy = true;
        m_Observer.Forget(departedRun.Lease, player);
        m_Busy = false;
        m_LastNow = context.Now;
        return HCEventCode.OK;
    }
    void Disconnect(PlayerBase player, HCEventContext context)
    {
        int index = m_Subscriptions.Count() - 1;
        while (index >= 0)
        {
            HCEventSubscription sub = m_Subscriptions[index];
            if (sub.Player == player) { Leave(sub.EventId, player, context); }
            index = index - 1;
        }
    }
    int Cancel(int id, HCEventContext context)
    {
        if (!Allowed(context))
        {
            if (m_PendingPublish) { return HCEventCode.BLOCKED; }
            return HCEventCode.DENIED;
        }
        HCEventRuntimeState candidate = m_Store.Clone(m_State);
        int result = Operation(candidate, id, HCEventOp.CANCEL, "", context);
        if (result != HCEventCode.OK)
        {
            return result;
        }
        HCEventRun cancelledRun = HCRunAt(candidate, id);
        if (!cancelledRun) { return HCEventCode.NOT_FOUND; }
        cancelledRun.Phase = HCEventRunPhase.CLEANUP;
        if (!Publish(candidate))
        {
            return HCEventCode.BLOCKED;
        }
        Cleanup(id);
        return HCEventCode.OK;
    }
    bool Cleanup(int id, bool staged = false)
    {
        if (HCAnnouncePending()) { return false; }
        HCEventRun run = HCRunAt(m_State, id);
        if (!run) { return false; }
        if (run.Phase != HCEventRunPhase.CLEANUP)
        {
            return true;
        }
        m_Busy = true;
        bool gone = false;
        if (run.Objective.Family == HCEventFamily.AI_ENCOUNTER)
        {
            HCEventRecord aiRecord = HCEventDirector.FindRecord(m_State.Director, run.EventId);
            if (!aiRecord) { m_Busy = false; return false; }
            int aiGeneration = aiRecord.Expires - aiRecord.Definition.LifetimeSeconds;
            string aiLease = run.Lease + ":" + aiGeneration.ToString();
            m_AI.Stop(aiLease);
            gone = m_AI.Gone(aiLease);
        }
        else
        {
            gone = m_Observer.Release(run.Lease);
        }
        m_Busy = false;
        if (gone)
        {
            HCEventRuntimeState candidate = m_Store.Clone(m_State);
            HCEventRun closingRun = HCRunAt(candidate, id);
            if (!closingRun) { return false; }
            closingRun.Phase = HCEventRunPhase.CLOSED;
            if (staged) { return HCBeginPublish(candidate); }
            return Publish(candidate);
        }
        return true;
    }
    void Observe(HCEventSubscription sub, HCEventContext context)
    {
        if (HCAnnouncePending() || !sub) { return; }
        HCEventRun run = HCRunAt(m_State, sub.EventId);
        if (!run) { return; }
        HCEventRecord record = HCEventDirector.FindRecord(m_State.Director, sub.EventId);
        if (!record) { return; }
        if (record.Status != HCEventStatus.ACTIVE || run.Phase != HCEventRunPhase.ACTIVE)
        {
            return;
        }
        if (HCEventNativeObserver.Identity(sub.Player) != sub.ParticipantId)
        {
            Leave(sub.EventId, sub.Player, context);
            return;
        }
        m_Busy = true;
        HCEventObjectiveEvidence evidence;
        string expectedLease = run.Lease;
        if (run.Objective.Family == HCEventFamily.AI_ENCOUNTER)
        {
            int aiGeneration = record.Expires - record.Definition.LifetimeSeconds;
            expectedLease = run.Lease + ":" + aiGeneration.ToString();
            evidence = m_AI.Observe(expectedLease, sub.Player);
        }
        else
        {
            HCEventRuntimeState observedState = m_Store.Clone(m_State);
            if (!observedState || !observedState.Director || !observedState.Runs)
            {
                m_Busy = false;
                HCObservationRefused(true);
                return;
            }
            HCEventRun observedRun = HCRunAt(observedState, sub.EventId);
            if (!observedRun)
            {
                m_Busy = false;
                HCObservationRefused(false);
                return;
            }
            evidence = m_Observer.Observe(observedRun, sub.Player, context.Now);
        }
        m_Busy = false;
        if (!evidence || !evidence.Observed || evidence.Lease != expectedLease || evidence.Session != record.Session)
        {
            return;
        }
        if (evidence.ParticipantId != sub.ParticipantId || evidence.Sequence != record.LastObservation + 1)
        {
            return;
        }
        if (!HCEventDirector.TextValid(evidence.Token, 192) || run.Tokens.Find(evidence.Token) >= 0)
        {
            return;
        }
        HCEventRuntimeState candidate = m_Store.Clone(m_State);
        HCEventRun completingRun = HCRunAt(candidate, sub.EventId);
        if (!completingRun) { return; }
        HCEventObservation observation = new HCEventObservation;
        observation.ServerObserved = true;
        observation.WorldName = context.WorldName;
        observation.Session = context.Session;
        observation.EventId = sub.EventId;
        observation.ParticipantId = sub.ParticipantId;
        observation.ObjectiveTag = record.Definition.ObjectiveTag;
        observation.Sequence = evidence.Sequence;
        observation.Units = 1;
        if (HCEventDirector.Observe(candidate.Director, context, observation) != HCEventCode.OK)
        {
            return;
        }
        completingRun.Tokens.Insert(evidence.Token);
        if (Operation(candidate, sub.EventId, HCEventOp.COMPLETE, "", context) != HCEventCode.OK)
        {
            return;
        }
        completingRun.Phase = HCEventRunPhase.CLEANUP;
        if (Publish(candidate))
        {
            HCEventRecord completedRecord = HCEventDirector.FindRecord(m_State.Director, sub.EventId);
            if (completedRecord) { RememberCooldown(completedRecord, context.Now); }
        }
    }
    void Tick(HCEventContext context)
    {
        // One shared four-millisecond slice, retained across all maintenance
        // stages in this tick. No second slice after completing a journal.
        m_WorkBudget.HCReset(m_Settings.WorkPerTick + 1);
        if (m_AnnounceReceipt != "")
        {
            m_AnnounceReceiptTicks++;
            if (m_AnnounceReceiptTicks >= 120)
            {
                m_AnnounceReceipt = "";
                m_AnnounceReceiptSession = "";
                m_AnnounceReceiptTicks = 0;
                Print("[HC Events] announcement receipt timed out; slot released after 120 ticks");
            }
        }
        if (HCAnnouncePending())
        {
            HCAdvanceAnnounce();
            if (HCAnnouncePending()) { m_WorkBudget.HCDeferred("Events", 1); }
            return;
        }
        if (m_PendingPublish)
        {
            HCAdvancePublish();
            if (m_PendingPublish) { m_WorkBudget.HCDeferred("Events", 1); }
            return;
        }
        if (!Allowed(context))
        {
            return;
        }
        if (m_SceneRetirements.Count() > 0)
        {
            int retiring = m_SceneRetirements[0];
            HCEventRecord retiringRecord = HCEventDirector.FindRecord(m_State.Director, retiring);
            if (!retiringRecord) { HCRefuseSceneRetirement(retiring, "record-missing"); return; }
            if (HCEventDirector.Terminal(retiringRecord.Status)) { m_SceneRetirements.RemoveOrdered(0); return; }
            int retireStarted = TickCount(0);
            HCEventRuntimeState retirement = m_Store.Clone(m_State);
            HCMeasured("retire_clone", retireStarted);
            if (!retirement) { HCRefuseSceneRetirement(retiring, "clone-refused"); return; }
            int retireResult = Operation(retirement, retiring, HCEventOp.CANCEL, "", context);
            if (retireResult != HCEventCode.OK) { HCRefuseSceneRetirement(retiring, "cancel-code-" + retireResult.ToString()); return; }
            HCEventRun retiringRun = HCRunAt(retirement, retiring);
            if (!retiringRun) { HCRefuseSceneRetirement(retiring, "run-missing"); return; }
            retiringRun.Phase = HCEventRunPhase.CLEANUP;
            if (HCBeginPublish(retirement)) { m_SceneRetirements.RemoveOrdered(0); m_LastNow = context.Now; }
            else { HCRefuseSceneRetirement(retiring, "publish-refused"); }
            return;
        }
        if (m_PendingLeaves.Count() > 0)
        {
            HCEventSubscription leaving = m_PendingLeaves.GetKey(0);
            if (Binding(leaving.EventId, leaving.Player) < 0) { m_PendingLeaves.Remove(leaving); return; }
            int leaveStarted = TickCount(0);
            HCEventRuntimeState departure = m_Store.Clone(m_State);
            HCMeasured("leave_clone", leaveStarted);
            if (!departure) { return; }
            int leaveResult = Operation(departure, leaving.EventId, HCEventOp.LEAVE, leaving.ParticipantId, context);
            if (leaveResult != HCEventCode.OK) { m_PendingLeaves.Remove(leaving); return; }
            if (HCBeginPublish(departure))
            {
                if (m_PendingPublish) { m_PendingLeave = leaving; }
                else { HCFinishLeave(leaving); }
                m_LastNow = context.Now;
            }
            return;
        }
        m_LastNow = context.Now;
        HCEventRuntimeState stable = m_State;
        int runWork = 0;
        while (runWork < 1 && stable.Runs.Count() > 0 && m_WorkBudget.HCContinue())
        {
            if (m_RunCursor >= stable.Runs.Count()) { m_RunCursor = 0; }
            HCEventRun run = stable.Runs[m_RunCursor];
            m_RunCursor = m_RunCursor + 1;
            runWork = runWork + 1;
            if (!m_Ready)
            {
                return;
            }
            if (!run) { return; }
            HCEventRecord record = HCEventDirector.FindRecord(m_State.Director, run.EventId);
            if (!record) { return; }
            if (!HCEventDirector.Terminal(record.Status) && context.Now >= record.Expires)
            {
                int expiryStarted = TickCount(0);
                HCEventRuntimeState candidate = m_Store.Clone(m_State);
                HCMeasured("expiry_clone", expiryStarted);
                if (Operation(candidate, run.EventId, HCEventOp.EXPIRE, "", context) == HCEventCode.OK)
                {
                    HCEventRun expiringRun = HCRunAt(candidate, run.EventId);
                    if (!expiringRun) { return; }
                    expiringRun.Phase = HCEventRunPhase.CLEANUP;
                    if (HCBeginPublish(candidate) && m_PendingPublish)
                    {
                        m_PendingExpiryId = run.EventId;
                        m_PendingExpiryAt = context.Now;
                        // Revisit this row for cleanup after commit, preserving
                        // expiry-before-release without another full run sweep.
                        m_RunCursor = m_RunCursor - 1;
                    }
                    // Release only on a future tick, after durable expiry.
                    return;
                }
            }
            if (m_Ready)
            {
                HCEventRecord cooldownRecord = HCEventDirector.FindRecord(m_State.Director, run.EventId);
                if (!cooldownRecord) { return; }
                RememberCooldown(cooldownRecord, context.Now);
                int cleanupStarted = TickCount(0);
                Cleanup(run.EventId, true);
                HCMeasured("cleanup_prepare", cleanupStarted);
                if (m_PendingPublish) { return; }
            }
        }
        int work = 0;
        int count = m_Subscriptions.Count();
        while (m_Ready && m_Subscriptions.Count() > 0 && work < m_Settings.WorkPerTick && work < count)
        {
            if (m_Cursor >= m_Subscriptions.Count())
            {
                m_Cursor = 0;
            }
            if (!m_WorkBudget.HCContinue()) { break; }
            Observe(m_Subscriptions[m_Cursor], context);
            m_Cursor = m_Cursor + 1;
            work = work + 1;
        }
        PurgeTerminal();
        m_WorkBudget.HCDeferred("Events", stable.Runs.Count() - runWork + count - work);
    }
    void PurgeTerminal()
    {
        if (m_Subscriptions.Count() == 0) { return; }
        if (m_PurgeCursor >= m_Subscriptions.Count()) { m_PurgeCursor = 0; }
        int index = m_PurgeCursor;
        HCEventSubscription sub = m_Subscriptions[index];
        HCEventRecord record = HCEventDirector.FindRecord(m_State.Director, sub.EventId);
        if (!record || HCEventDirector.Terminal(record.Status)) { m_Subscriptions.Remove(index); }
        else { m_PurgeCursor = m_PurgeCursor + 1; }
    }
    bool CleanupComplete()
    {
        if (!m_StopRequested || m_Busy || m_Ready)
        {
            return false;
        }
        if (m_State)
        {
            if (!m_State.Director || !m_State.Runs) { return false; }
            foreach (HCEventRun run : m_State.Runs)
            {
                if (!run || run.Phase != HCEventRunPhase.CLOSED)
                {
                    return false;
                }
            }
        }
        return true;
    }
    bool Stop(HCEventContext context)
    {
        // Reentrant/provider-busy shutdown still revokes admission immediately.
        // Retain state/providers until a later non-busy retry confirms closure.
        // Shutdown is an existing synchronous barrier, never discard an intent.
        m_StopRequested = true;
        if (!m_Busy)
        {
            while (HCAnnouncePending()) { HCAdvanceAnnounce(true); }
            if (m_PendingPublish) { HCAdvancePublish(true); }
        }
        // Drain may create a receipt; stopped/quarantined owners must not retain it.
        m_AnnounceReceipt = "";
        m_AnnounceReceiptSession = "";
        m_AnnounceReceiptTicks = 0;
        m_AnnounceResult = HCEventCode.BLOCKED;
        m_Ready = false;
        m_Subscriptions.Clear();
        m_PendingLeaves.Clear();
        m_PendingLeave = null;
        m_SceneRetirements.Clear();
        m_FailedSceneRetirements.Clear();
        if (m_Busy)
        {
            return false;
        }
        if (!m_State)
        {
            return true;
        }
        if (!m_State.Director || !m_State.Runs) { return false; }
        if (!GetGame() || !GetGame().IsServer())
        {
            return CleanupComplete();
        }
        HCEventContext cleanup = new HCEventContext;
        cleanup.Server = true;
        cleanup.WorldName = m_State.Director.WorldName;
        cleanup.Session = m_State.Director.Session;
        cleanup.Now = m_State.Director.LastNow;
        if (HCEventDirector.ContextValid(m_State.Director, cleanup))
        {
            HCEventRuntimeState candidate = m_Store.Clone(m_State);
            if (!candidate || !candidate.Director || !candidate.Runs)
            {
                FaultCleanup();
                return false;
            }
            bool changed = false;
            foreach (HCEventRun run : candidate.Runs)
            {
                if (!run) { FaultCleanup(); return false; }
                HCEventRecord record = HCEventDirector.FindRecord(candidate.Director, run.EventId);
                if (!record) { FaultCleanup(); return false; }
                if (!HCEventDirector.Terminal(record.Status))
                {
                    if (Operation(candidate, run.EventId, HCEventOp.CANCEL, "", cleanup) != HCEventCode.OK)
                    {
                        FaultCleanup();
                        return false;
                    }
                    run.Phase = HCEventRunPhase.CLEANUP;
                    changed = true;
                }
            }
            if (changed && !Publish(candidate))
            {
                return false;
            }
            foreach (HCEventRun pending : m_State.Runs)
            {
                if (!pending) { return false; }
                Cleanup(pending.EventId);
            }
        }
        FaultCleanup();
        // Only durable CLOSED rows, written after Gone/Release confirmation,
        // allow the owner to discard this runtime. A stop request is not proof.
        return CleanupComplete();
    }
}
