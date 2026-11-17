// Durable orchestrator. The caller owns a fresh trusted session and invokes
// Tick/Disconnect from server lifecycle hooks. No rewards or network ingress.
class HCEventRuntime
{
    protected ref HCEventSettings m_Settings;
    protected ref HCEventRuntimeState m_State;
    protected ref HCEventPersistence m_Store;
    protected ref HCEventObjectiveProvider m_Observer;
    protected ref HCEventAIProvider m_AI;
    protected ref array<ref HCEventSubscription> m_Subscriptions = new array<ref HCEventSubscription>();
    protected bool m_Ready = false;
    protected bool m_Busy = false;
    protected bool m_StopRequested = false;
    protected int m_LastNow = 0;
    protected int m_Cursor = 0;

    bool Start(HCEventSettings settings, HCEventContext context, HCEventPersistence store, HCEventObjectiveProvider observer, HCEventAIProvider ai)
    {
        m_Ready = false;
        m_Busy = false;
        m_StopRequested = false;
        m_Subscriptions = new array<ref HCEventSubscription>();
        m_Cursor = 0;
        if (!HCEventRuntimePolicy.SettingsValid(settings) || !settings.Enabled || !context || !context.Server)
        {
            Print("[HC Events] disabled or invalid configuration/context");
            return false;
        }
        if (!store || !observer || !ai || context.Now < 0 || context.Now > 1000000000)
        {
            return false;
        }
        m_Settings = settings;
        m_Store = store;
        m_Observer = observer;
        m_AI = ai;
        HCEventRuntimeState state = store.Load(context.WorldName);
        if (!state || !HCEventRuntimePolicy.StateValid(state) || state.Director.WorldName != context.WorldName)
        {
            Print("[HC Events] persistence admission failed; preserve journal, no fallback");
            return false;
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
                return false;
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
                return false;
            }
            context.Session = m_State.Director.Session;
        }
        if (!HCEventDirector.ContextValid(m_State.Director, context))
        {
            return false;
        }
        // A process restart must use a fresh session. Rebinding a live state
        // without cancellation would retain persisted participants, not handles.
        foreach (HCEventRecord record : m_State.Director.Records)
        {
            if (!HCEventDirector.Terminal(record.Status))
            {
                Print("[HC Events] restored live session requires a fresh session token");
                return false;
            }
        }
        m_LastNow = context.Now;
        m_Ready = true;
        return true;
    }
    bool Allowed(HCEventContext context)
    {
        return m_Ready && !m_Busy && !m_StopRequested && m_Settings.Enabled && context && context.Now >= m_LastNow && HCEventDirector.ContextValid(m_State.Director, context);
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
            Print("[HC Events] journal fault; mutations disabled, cleanup remains pending");
            return false;
        }
        m_State = candidate;
        return true;
    }
    void FaultCleanup()
    {
        // Existing durable intent authorizes a best-effort stop even when the
        // next write failed. Never publish CLOSED or infer successful cleanup.
        if (!m_State)
        {
            return;
        }
        m_Busy = true;
        foreach (HCEventRun run : m_State.Runs)
        {
            if (run.ProviderIntent && run.Phase != HCEventRunPhase.CLOSED)
            {
                if (run.Objective.Family == HCEventFamily.AI_ENCOUNTER)
                {
                    m_AI.Stop(run.Lease);
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
        while (state.Runs.Count() >= m_Settings.MaxRuns)
        {
            if (state.Runs[0].Phase != HCEventRunPhase.CLOSED || !HCEventDirector.PruneFirst(state.Director))
            {
                int phase = state.Runs[0].Phase;
                Print("[HC Events] retention blocked by oldest run " + state.Runs[0].Lease + " phase " + phase.ToString() + "; new announcements refused until it closes");
                return false;
            }
            state.Runs.RemoveOrdered(0);
        }
        return true;
    }
    int Operation(HCEventRuntimeState state, int id, int op, string participant, HCEventContext context)
    {
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
    int Announce(HCEventMission mission, HCEventContext context)
    {
        if (!Allowed(context))
        {
            return HCEventCode.DENIED;
        }
        if (!HCEventRuntimePolicy.MissionValid(mission, context.WorldName))
        {
            return HCEventCode.INVALID;
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
            Print("[HC Events] mission blocked: required provider or reviewed target unavailable");
            return HCEventCode.BLOCKED;
        }
        HCEventRuntimeState candidate = m_Store.Clone(m_State);
        if (!candidate)
        {
            return HCEventCode.BLOCKED;
        }
        if (!Retain(candidate))
        {
            return HCEventCode.LIMIT;
        }
        int result = HCEventDirector.Propose(candidate.Director, context, HCEventRuntimePolicy.Definition(mission));
        if (result != HCEventCode.OK)
        {
            return result;
        }
        HCEventRun run = new HCEventRun;
        run.EventId = candidate.Director.NextId - 1;
        run.Lease = context.Session + ":" + run.EventId.ToString();
        run.Objective = mission;
        run.ProviderIntent = true;
        candidate.Runs.Insert(run);
        if (Operation(candidate, run.EventId, HCEventOp.ANNOUNCE, "", context) != HCEventCode.OK)
        {
            return HCEventCode.BLOCKED;
        }
        // Freeze caller-owned mission before persisting or invoking providers.
        candidate = m_Store.Clone(candidate);
        if (!Publish(candidate))
        {
            return HCEventCode.BLOCKED;
        }
        m_LastNow = context.Now;
        run = m_State.Runs[run.EventId - m_State.Director.PrunedThrough - 1];
        m_Busy = true;
        bool started = false;
        if (run.Objective.Family == HCEventFamily.AI_ENCOUNTER)
        {
            started = m_AI.Start(run.Lease, context.Session, run.Objective.Id, run.Objective.Source, run.Objective.ActorBudget);
        }
        else
        {
            started = m_Observer.Prepare(run.Lease, m_Store.Clone(m_State).Runs[run.EventId - m_State.Director.PrunedThrough - 1].Objective);
        }
        m_Busy = false;
        if (!started)
        {
            Cancel(run.EventId, context);
            return HCEventCode.BLOCKED;
        }
        candidate = m_Store.Clone(m_State);
        candidate.Runs[run.EventId - candidate.Director.PrunedThrough - 1].Phase = HCEventRunPhase.ACTIVE;
        if (!Publish(candidate))
        {
            return HCEventCode.BLOCKED;
        }
        return HCEventCode.OK;
    }
    bool HasMission(string missionId)
    {
        foreach (HCEventRecord record : m_State.Director.Records)
        {
            if (record.Session == m_State.Director.Session && record.Definition.Id == missionId) { return true; }
        }
        return false;
    }
    void ItemDelivered(ItemBase item, PlayerBase participant, EntityAI destination, HCEventContext context)
    {
        if (!Allowed(context) || !item) { return; }
        string identity = HCEventNativeObserver.Identity(participant);
        if (identity == "") { return; }
        foreach (HCEventSubscription sub : m_Subscriptions)
        {
            if (sub.Player == participant && sub.ParticipantId == identity)
            {
                HCEventRecord record = HCEventDirector.FindRecord(m_State.Director, sub.EventId);
                HCEventRun run = m_State.Runs[sub.EventId - m_State.Director.PrunedThrough - 1];
                if (record.Status == HCEventStatus.ACTIVE && context.Now < record.Expires && run.Objective.Family == HCEventFamily.DELIVERY)
                {
                    m_Observer.RecordDelivery(run.Lease, item, participant, destination);
                }
            }
        }
    }
    void InfectedKilled(ZombieBase infected, PlayerBase participant, HCEventContext context)
    {
        if (!Allowed(context) || !infected || infected.IsAlive()) { return; }
        string identity = HCEventNativeObserver.Identity(participant);
        if (identity == "") { return; }
        foreach (HCEventSubscription sub : m_Subscriptions)
        {
            if (sub.Player == participant && sub.ParticipantId == identity)
            {
                HCEventRecord record = HCEventDirector.FindRecord(m_State.Director, sub.EventId);
                HCEventRun run = m_State.Runs[sub.EventId - m_State.Director.PrunedThrough - 1];
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
        if (HCEventDirector.FindRecord(candidate.Director, id).Status == HCEventStatus.ANNOUNCED)
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
        if (!Allowed(context))
        {
            return HCEventCode.DENIED;
        }
        int index = Binding(id, player);
        if (index < 0)
        {
            return HCEventCode.DENIED;
        }
        HCEventSubscription sub = m_Subscriptions[index];
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
        m_Subscriptions.Remove(index);
        m_Busy = true;
        m_Observer.Forget(m_State.Runs[id - m_State.Director.PrunedThrough - 1].Lease, player);
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
            if (sub.Player == player)
            {
                Leave(sub.EventId, player, context);
            }
            index = index - 1;
        }
    }
    int Cancel(int id, HCEventContext context)
    {
        if (!Allowed(context))
        {
            return HCEventCode.DENIED;
        }
        HCEventRuntimeState candidate = m_Store.Clone(m_State);
        int result = Operation(candidate, id, HCEventOp.CANCEL, "", context);
        if (result != HCEventCode.OK)
        {
            return result;
        }
        candidate.Runs[id - candidate.Director.PrunedThrough - 1].Phase = HCEventRunPhase.CLEANUP;
        if (!Publish(candidate))
        {
            return HCEventCode.BLOCKED;
        }
        Cleanup(id);
        return HCEventCode.OK;
    }
    void Cleanup(int id)
    {
        HCEventRun run = m_State.Runs[id - m_State.Director.PrunedThrough - 1];
        if (run.Phase != HCEventRunPhase.CLEANUP)
        {
            return;
        }
        m_Busy = true;
        bool gone = false;
        if (run.Objective.Family == HCEventFamily.AI_ENCOUNTER)
        {
            m_AI.Stop(run.Lease);
            gone = m_AI.Gone(run.Lease);
        }
        else
        {
            gone = m_Observer.Release(run.Lease);
        }
        m_Busy = false;
        if (gone)
        {
            HCEventRuntimeState candidate = m_Store.Clone(m_State);
            candidate.Runs[id - candidate.Director.PrunedThrough - 1].Phase = HCEventRunPhase.CLOSED;
            Publish(candidate);
        }
    }
    void Observe(HCEventSubscription sub, HCEventContext context)
    {
        HCEventRecord record = HCEventDirector.FindRecord(m_State.Director, sub.EventId);
        HCEventRun run = m_State.Runs[sub.EventId - m_State.Director.PrunedThrough - 1];
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
        if (run.Objective.Family == HCEventFamily.AI_ENCOUNTER)
        {
            evidence = m_AI.Observe(run.Lease, sub.Player);
        }
        else
        {
            evidence = m_Observer.Observe(m_Store.Clone(m_State).Runs[sub.EventId - m_State.Director.PrunedThrough - 1], sub.Player, context.Now);
        }
        m_Busy = false;
        if (!evidence || !evidence.Observed || evidence.Lease != run.Lease || evidence.Session != record.Session)
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
        candidate.Runs[sub.EventId - candidate.Director.PrunedThrough - 1].Tokens.Insert(evidence.Token);
        if (Operation(candidate, sub.EventId, HCEventOp.COMPLETE, "", context) != HCEventCode.OK)
        {
            return;
        }
        candidate.Runs[sub.EventId - candidate.Director.PrunedThrough - 1].Phase = HCEventRunPhase.CLEANUP;
        Publish(candidate);
    }
    void Tick(HCEventContext context)
    {
        if (!Allowed(context))
        {
            return;
        }
        m_LastNow = context.Now;
        HCEventRuntimeState stable = m_State;
        int runIndex = 0;
        while (runIndex < stable.Runs.Count())
        {
            HCEventRun run = stable.Runs[runIndex];
            runIndex = runIndex + 1;
            if (!m_Ready)
            {
                return;
            }
            HCEventRecord record = HCEventDirector.FindRecord(m_State.Director, run.EventId);
            if (!HCEventDirector.Terminal(record.Status) && context.Now >= record.Expires)
            {
                HCEventRuntimeState candidate = m_Store.Clone(m_State);
                if (Operation(candidate, run.EventId, HCEventOp.EXPIRE, "", context) == HCEventCode.OK)
                {
                    candidate.Runs[run.EventId - candidate.Director.PrunedThrough - 1].Phase = HCEventRunPhase.CLEANUP;
                    Publish(candidate);
                }
            }
            if (m_Ready)
            {
                Cleanup(run.EventId);
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
            Observe(m_Subscriptions[m_Cursor], context);
            m_Cursor = m_Cursor + 1;
            work = work + 1;
        }
        PurgeTerminal();
    }
    void PurgeTerminal()
    {
        int index = m_Subscriptions.Count() - 1;
        while (index >= 0)
        {
            HCEventSubscription sub = m_Subscriptions[index];
            HCEventRecord record = HCEventDirector.FindRecord(m_State.Director, sub.EventId);
            if (!record || HCEventDirector.Terminal(record.Status))
            {
                m_Subscriptions.Remove(index);
            }
            index = index - 1;
        }
    }
    bool CleanupComplete()
    {
        if (!m_StopRequested || m_Busy || m_Ready)
        {
            return false;
        }
        if (m_State)
        {
            foreach (HCEventRun run : m_State.Runs)
            {
                if (run.Phase != HCEventRunPhase.CLOSED)
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
        m_StopRequested = true;
        m_Ready = false;
        m_Subscriptions.Clear();
        if (m_Busy)
        {
            return false;
        }
        if (!m_State)
        {
            return true;
        }
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
            if (!candidate)
            {
                FaultCleanup();
                return false;
            }
            bool changed = false;
            foreach (HCEventRun run : candidate.Runs)
            {
                HCEventRecord record = HCEventDirector.FindRecord(candidate.Director, run.EventId);
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
                Cleanup(pending.EventId);
            }
        }
        FaultCleanup();
        // Only durable CLOSED rows, written after Gone/Release confirmation,
        // allow the owner to discard this runtime. A stop request is not proof.
        return CleanupComplete();
    }
}
