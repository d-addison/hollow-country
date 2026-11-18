// W5-PERF-4: <=1 run cleanup/expiry + <=64 subscribed observations + <=1
// terminal-subscription purge/tick; cursors survive yields. 4 ms cooperative
// guard between jobs; synchronous journal/provider calls cannot be preempted.
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
    protected bool m_Ready = false;
    protected bool m_Busy = false;
    protected bool m_StopRequested = false;
    protected int m_LastNow = 0;
    protected int m_Cursor = 0;
    protected int m_RunCursor;
    protected int m_PurgeCursor;
    protected ref HCWorkBudget m_WorkBudget;
    protected ref array<string> m_BlockedLogged = new array<string>();
    // At most one cooldown per retained current-session record (32).
    protected ref array<int> m_ReofferIds = new array<int>();
    protected ref array<int> m_ReofferAfter = new array<int>();

    bool Start(HCEventSettings settings, HCEventContext context, HCEventPersistence store, HCEventObjectiveProvider observer, HCEventAIProvider ai)
    {
        m_Ready = false;
        m_Busy = false;
        m_StopRequested = false;
        m_Subscriptions = new array<ref HCEventSubscription>();
        m_BlockedLogged = new array<string>();
        m_ReofferIds = new array<int>();
        m_ReofferAfter = new array<int>();
        m_Cursor = 0;
        m_RunCursor = 0;
        m_PurgeCursor = 0;
        m_WorkBudget = new HCWorkBudget;
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
        // Complete durable restart cleanup before the caller's first roster pass.
        // Unconfirmed provider cleanup stays pending and cannot be pruned.
        HCEventRuntimeState restored = m_State;
        int closed = 0;
        foreach (HCEventRun restoredRun : restored.Runs)
        {
            if (restoredRun.Phase == HCEventRunPhase.CLEANUP)
            {
                if (!Cleanup(restoredRun.EventId)) { return false; }
                if (m_State.Runs[restoredRun.EventId - m_State.Director.PrunedThrough - 1].Phase == HCEventRunPhase.CLOSED)
                {
                    closed = closed + 1;
                }
                else
                {
                    Print("[HC Events] startup cleanup pending; " + restoredRun.Lease);
                }
            }
        }
        if (closed > 0) { Print("[HC Events] startup cleanup closed " + closed.ToString() + " retained runs before roster"); }
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
                    HCEventRecord aiRecord = HCEventDirector.FindRecord(m_State.Director, run.EventId);
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
        HCEventRuntimeState candidate = m_Store.Clone(m_State);
        if (!candidate)
        {
            return HCEventCode.BLOCKED;
        }
        HCEventRun run;
        if (repeatId > 0)
        {
            // Reuse the stable wire slot, rather than pruning current-session
            // tombstones or changing the director's duplicate proposal policy.
            if (context.Now > 1000000000 - mission.LifetimeSeconds) { return HCEventCode.LIMIT; }
            PurgeTerminal();
            HCEventRecord repeated = HCEventDirector.FindRecord(candidate.Director, repeatId);
            repeated.Definition = HCEventRuntimePolicy.Definition(mission);
            repeated.Revision = repeated.Revision + 1;
            repeated.Status = HCEventStatus.PROPOSED;
            repeated.Expires = context.Now + mission.LifetimeSeconds;
            repeated.Progress = 0;
            repeated.LastObservation = 0;
            repeated.Participants.Clear();
            run = candidate.Runs[repeatId - candidate.Director.PrunedThrough - 1];
            run.Objective = mission;
            run.Phase = HCEventRunPhase.PREPARED;
            run.Tokens.Clear();
        }
        else
        {
            if (!Retain(candidate)) { return HCEventCode.LIMIT; }
            int result = HCEventDirector.Propose(candidate.Director, context, HCEventRuntimePolicy.Definition(mission));
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
        // Freeze caller-owned mission before persisting or invoking providers.
        candidate = m_Store.Clone(candidate);
        if (!Publish(candidate))
        {
            return HCEventCode.BLOCKED;
        }
        if (repeatId > 0)
        {
            int cooldownIndex = m_ReofferIds.Find(repeatId);
            m_ReofferIds.Remove(cooldownIndex);
            m_ReofferAfter.Remove(cooldownIndex);
        }
        m_LastNow = context.Now;
        run = m_State.Runs[run.EventId - m_State.Director.PrunedThrough - 1];
        m_Busy = true;
        bool started = false;
        if (run.Objective.Family == HCEventFamily.AI_ENCOUNTER)
        {
            // The stable event slot can repeat, but the AI journal consumes lease
            // IDs. The persisted proposal time increases on every re-offer.
            HCEventRecord aiRecord = HCEventDirector.FindRecord(m_State.Director, run.EventId);
            int aiGeneration = aiRecord.Expires - aiRecord.Definition.LifetimeSeconds;
            string aiLease = run.Lease + ":" + aiGeneration.ToString();
            started = m_AI.Start(aiLease, context.Session, run.Objective.Id, run.Objective.Source, run.Objective.ActorBudget);
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
        if (repeatId > 0) { Print("[HC Events] mission re-announced after cooldown; " + mission.Id); }
        return HCEventCode.OK;
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
        bool repeatable = record.Status == HCEventStatus.COMPLETED || record.Status == HCEventStatus.EXPIRED;
        if (!repeatable || record.Revision >= 999998) { return false; }
        HCEventRun run = m_State.Runs[record.Id - m_State.Director.PrunedThrough - 1];
        if (run.Phase != HCEventRunPhase.CLOSED) { return false; }
        int cooldownIndex = m_ReofferIds.Find(record.Id);
        if (cooldownIndex < 0) { return false; }
        return now >= m_ReofferAfter[cooldownIndex];
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
            if (sub.Player == player) { Leave(sub.EventId, player, context); }
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
    bool Cleanup(int id)
    {
        HCEventRun run = m_State.Runs[id - m_State.Director.PrunedThrough - 1];
        if (run.Phase != HCEventRunPhase.CLEANUP)
        {
            return true;
        }
        m_Busy = true;
        bool gone = false;
        if (run.Objective.Family == HCEventFamily.AI_ENCOUNTER)
        {
            HCEventRecord aiRecord = HCEventDirector.FindRecord(m_State.Director, run.EventId);
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
            candidate.Runs[id - candidate.Director.PrunedThrough - 1].Phase = HCEventRunPhase.CLOSED;
            return Publish(candidate);
        }
        return true;
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
        string expectedLease = run.Lease;
        if (run.Objective.Family == HCEventFamily.AI_ENCOUNTER)
        {
            int aiGeneration = record.Expires - record.Definition.LifetimeSeconds;
            expectedLease = run.Lease + ":" + aiGeneration.ToString();
            evidence = m_AI.Observe(expectedLease, sub.Player);
        }
        else
        {
            evidence = m_Observer.Observe(m_Store.Clone(m_State).Runs[sub.EventId - m_State.Director.PrunedThrough - 1], sub.Player, context.Now);
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
        if (Publish(candidate))
        {
            RememberCooldown(HCEventDirector.FindRecord(m_State.Director, sub.EventId), context.Now);
        }
    }
    void Tick(HCEventContext context)
    {
        if (!Allowed(context))
        {
            return;
        }
        m_LastNow = context.Now;
        HCEventRuntimeState stable = m_State;
        m_WorkBudget.HCReset(m_Settings.WorkPerTick + 1);
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
                RememberCooldown(HCEventDirector.FindRecord(m_State.Director, run.EventId), context.Now);
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
