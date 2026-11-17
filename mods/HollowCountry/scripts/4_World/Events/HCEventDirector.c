// Pure server-adapter policy. No hooks, RPCs, AI, inventory or native grants.
// Native 1.30 array Count/Find/Insert/Remove and string methods inspected.
// Callers must retain exclusive server ownership of all DTO references.
class HCEventDirector
{
    static bool TextValid(string value, int limit)
    {
        if (value.Length() > limit || value.Trim().Length() == 0)
        {
            return false;
        }
        if (value.Contains("\n") || value.Contains("\r") || value.Contains("\t"))
        {
            return false;
        }
        return true;
    }

    static bool DefinitionValid(HCEventDefinition definition, string world)
    {
        if (!definition || definition.Version != 1)
        {
            return false;
        }
        if (!TextValid(definition.Id, 64) || definition.WorldName != world)
        {
            return false;
        }
        if (!TextValid(definition.ObjectiveTag, 64))
        {
            return false;
        }
        if (definition.Goal < 1 || definition.Goal > 1000)
        {
            return false;
        }
        if (definition.MaxParticipants < 1 || definition.MaxParticipants > HCEventLimits.MAX_PARTICIPANTS)
        {
            return false;
        }
        if (definition.ActorBudget < 0 || definition.ActorBudget > 64)
        {
            return false;
        }
        if (definition.ItemBudget < 0 || definition.ItemBudget > 128)
        {
            return false;
        }
        if (definition.LifetimeSeconds < 1 || definition.LifetimeSeconds > 86400)
        {
            return false;
        }
        return definition.RewardUnits >= 0 && definition.RewardUnits <= 32;
    }

    static HCEventState Initialize(string world, string session)
    {
        if (!TextValid(world, 96) || !TextValid(session, 96))
        {
            return null;
        }
        HCEventState state = new HCEventState;
        state.WorldName = world;
        state.Session = session;
        state.Sessions.Insert(session);
        return state;
    }

    static bool Terminal(int status)
    {
        return status >= HCEventStatus.COMPLETED && status <= HCEventStatus.CANCELLED;
    }

    static HCEventRecord FindRecord(HCEventState state, int id)
    {
        // Only call after StateValid: never traverse an unchecked collection.
        foreach (HCEventRecord record : state.Records)
        {
            if (record.Id == id)
            {
                return record;
            }
        }
        return null;
    }
    static bool RecordValid(HCEventRecord record, HCEventState state)
    {
        if (!record || !DefinitionValid(record.Definition, state.WorldName))
        {
            return false;
        }
        if (!record.Participants || record.Participants.Count() > HCEventLimits.MAX_PARTICIPANTS)
        {
            return false;
        }
        if (record.Participants.Count() > record.Definition.MaxParticipants)
        {
            return false;
        }
        if (record.Revision < 1 || record.Revision > 1000000)
        {
            return false;
        }
        if (record.Status < 0 || record.Status > HCEventStatus.CANCELLED)
        {
            return false;
        }
        if (record.Revision == 1000000 && !Terminal(record.Status))
        {
            return false;
        }
        if (state.Sessions.Find(record.Session) < 0)
        {
            return false;
        }
        if (record.Session != state.Session && !Terminal(record.Status))
        {
            return false;
        }
        if (record.Expires < 1 || record.Expires > 1000086400)
        {
            return false;
        }
        if (record.Progress < 0 || record.Progress > record.Definition.Goal)
        {
            return false;
        }
        if (record.LastObservation < 0 || record.LastObservation > record.Progress)
        {
            return false;
        }
        if (record.Progress > 0 && record.LastObservation == 0)
        {
            return false;
        }
        if (record.Status <= HCEventStatus.ANNOUNCED && record.Progress != 0)
        {
            return false;
        }
        if (record.Status == HCEventStatus.ACTIVE && record.Progress == record.Definition.Goal)
        {
            return false;
        }
        if (record.Status == HCEventStatus.RESOLVING || record.Status == HCEventStatus.COMPLETED)
        {
            if (record.Progress != record.Definition.Goal)
            {
                return false;
            }
        }
        int memberIndex = 0;
        foreach (string member : record.Participants)
        {
            if (!TextValid(member, 96))
            {
                return false;
            }
            if (record.Participants.Find(member) != memberIndex)
            {
                return false;
            }
            memberIndex = memberIndex + 1;
        }
        return true;
    }

    static bool StateValid(HCEventState state)
    {
        if (!state || state.Version != 1)
        {
            return false;
        }
        if (!TextValid(state.WorldName, 96) || !TextValid(state.Session, 96))
        {
            return false;
        }
        if (!state.Sessions || !state.Records)
        {
            return false;
        }
        // At most one session per retained record, plus the current session.
        if (state.Sessions.Count() < 1 || state.Sessions.Count() > 33)
        {
            return false;
        }
        if (state.Records.Count() > 32)
        {
            return false;
        }
        if (state.PrunedThrough < 0 || state.PrunedThrough > 1000000000 || state.NextId > 1000000001)
        {
            return false;
        }
        if (state.SessionGeneration < 0 || state.SessionGeneration > 1000000000)
        {
            return false;
        }
        if (state.NextId != state.PrunedThrough + state.Records.Count() + 1)
        {
            return false;
        }
        if (state.LastNow < 0 || state.LastNow > 1000000000)
        {
            return false;
        }
        int lastSession = state.Sessions.Count() - 1;
        if (state.Sessions[lastSession] != state.Session)
        {
            return false;
        }
        int sessionIndex = 0;
        foreach (string session : state.Sessions)
        {
            if (!TextValid(session, 96))
            {
                return false;
            }
            if (state.Sessions.Find(session) != sessionIndex)
            {
                return false;
            }
            sessionIndex = sessionIndex + 1;
        }
        int recordIndex = state.PrunedThrough + 1;
        int actors = 0;
        int items = 0;
        foreach (HCEventRecord record : state.Records)
        {
            if (!RecordValid(record, state))
            {
                return false;
            }
            if (record.Id != recordIndex)
            {
                return false;
            }
            recordIndex = recordIndex + 1;
            if (!Terminal(record.Status))
            {
                actors = actors + record.Definition.ActorBudget;
                items = items + record.Definition.ItemBudget;
            }
        }
        return actors <= 64 && items <= 128;
    }

    static bool ContextValid(HCEventState state, HCEventContext context)
    {
        if (!context || !context.Server)
        {
            return false;
        }
        if (!StateValid(state))
        {
            return false;
        }
        if (context.WorldName != state.WorldName || context.Session != state.Session)
        {
            return false;
        }
        return context.Now >= state.LastNow && context.Now <= 1000000000;
    }
    static int Propose(HCEventState state, HCEventContext context, HCEventDefinition definition)
    {
        if (!ContextValid(state, context))
        {
            return HCEventCode.DENIED;
        }
        if (!DefinitionValid(definition, state.WorldName))
        {
            return HCEventCode.INVALID;
        }
        if (state.Records.Count() >= 32 || state.NextId > 1000000000)
        {
            return HCEventCode.LIMIT;
        }
        int actors = definition.ActorBudget;
        int items = definition.ItemBudget;
        foreach (HCEventRecord existing : state.Records)
        {
            // Retain terminal IDs too: proposal replay cannot reactivate them.
            if (existing.Session == state.Session && existing.Definition.Id == definition.Id)
            {
                return HCEventCode.CONFLICT;
            }
            if (!Terminal(existing.Status))
            {
                actors = actors + existing.Definition.ActorBudget;
                items = items + existing.Definition.ItemBudget;
            }
        }
        if (actors > 64 || items > 128)
        {
            return HCEventCode.LIMIT;
        }
        if (context.Now > 1000000000 - definition.LifetimeSeconds)
        {
            return HCEventCode.LIMIT;
        }
        // Copy every definition field: later caller edits cannot change goals,
        // expiry, resource reservations or the reward eligibility decision.
        HCEventDefinition frozen = new HCEventDefinition;
        frozen.Id = definition.Id;
        frozen.WorldName = definition.WorldName;
        frozen.ObjectiveTag = definition.ObjectiveTag;
        frozen.Goal = definition.Goal;
        frozen.MaxParticipants = definition.MaxParticipants;
        frozen.ActorBudget = definition.ActorBudget;
        frozen.ItemBudget = definition.ItemBudget;
        frozen.LifetimeSeconds = definition.LifetimeSeconds;
        frozen.RewardUnits = definition.RewardUnits;
        HCEventRecord record = new HCEventRecord;
        record.Id = state.NextId;
        record.Session = state.Session;
        record.Definition = frozen;
        record.Expires = context.Now + frozen.LifetimeSeconds;
        state.Records.Insert(record);
        state.NextId = state.NextId + 1;
        state.LastNow = context.Now;
        return HCEventCode.OK;
    }

    static int Command(HCEventState state, HCEventContext context, HCEventRequest request)
    {
        if (!ContextValid(state, context))
        {
            return HCEventCode.DENIED;
        }
        if (!request || request.Version != 1)
        {
            return HCEventCode.INVALID;
        }
        HCEventRecord record = FindRecord(state, request.EventId);
        if (!record)
        {
            return HCEventCode.NOT_FOUND;
        }
        if (record.Session != context.Session)
        {
            return HCEventCode.DENIED;
        }
        if (request.ExpectedRevision != record.Revision || Terminal(record.Status))
        {
            return HCEventCode.CONFLICT;
        }
        if (record.Revision >= 1000000)
        {
            return HCEventCode.LIMIT;
        }
        // Reserve the final revision for cancellation/expiry/restart.
        if (record.Revision >= 999999)
        {
            if (request.Op != HCEventOp.CANCEL && request.Op != HCEventOp.EXPIRE)
            {
                return HCEventCode.LIMIT;
            }
        }
        int result = ApplyOperation(record, request, context.Now);
        if (result != HCEventCode.OK)
        {
            return result;
        }
        record.Revision = record.Revision + 1;
        state.LastNow = context.Now;
        return HCEventCode.OK;
    }
    protected static int ApplyOperation(HCEventRecord record, HCEventRequest request, int now)
    {
        if (request.Op == HCEventOp.CANCEL)
        {
            record.Status = HCEventStatus.CANCELLED;
            return HCEventCode.OK;
        }
        if (request.Op == HCEventOp.EXPIRE)
        {
            if (now < record.Expires)
            {
                return HCEventCode.CONFLICT;
            }
            record.Status = HCEventStatus.EXPIRED;
            return HCEventCode.OK;
        }
        if (now >= record.Expires)
        {
            return HCEventCode.EXPIRED;
        }
        if (request.Op == HCEventOp.JOIN)
        {
            if (record.Status != HCEventStatus.ANNOUNCED && record.Status != HCEventStatus.ACTIVE)
            {
                return HCEventCode.CONFLICT;
            }
            if (!TextValid(request.ParticipantId, 96))
            {
                return HCEventCode.INVALID;
            }
            if (record.Participants.Find(request.ParticipantId) >= 0)
            {
                return HCEventCode.CONFLICT;
            }
            if (record.Participants.Count() >= record.Definition.MaxParticipants)
            {
                return HCEventCode.LIMIT;
            }
            record.Participants.Insert(request.ParticipantId);
            return HCEventCode.OK;
        }
        if (request.Op == HCEventOp.LEAVE)
        {
            if (!TextValid(request.ParticipantId, 96))
            {
                return HCEventCode.INVALID;
            }
            int memberIndex = record.Participants.Find(request.ParticipantId);
            if (memberIndex < 0)
            {
                return HCEventCode.NOT_FOUND;
            }
            record.Participants.Remove(memberIndex);
            return HCEventCode.OK;
        }
        if (request.Op == HCEventOp.ANNOUNCE)
        {
            if (record.Status != HCEventStatus.PROPOSED)
            {
                return HCEventCode.CONFLICT;
            }
            record.Status = HCEventStatus.ANNOUNCED;
            return HCEventCode.OK;
        }
        if (request.Op == HCEventOp.ACTIVATE)
        {
            if (record.Status != HCEventStatus.ANNOUNCED || record.Participants.Count() == 0)
            {
                return HCEventCode.CONFLICT;
            }
            record.Status = HCEventStatus.ACTIVE;
            return HCEventCode.OK;
        }
        if (request.Op == HCEventOp.COMPLETE)
        {
            if (record.Status != HCEventStatus.RESOLVING)
            {
                return HCEventCode.CONFLICT;
            }
            // No capability is implied by a configured reward count.
            // A future durable CE adapter needs its own crash/replay contract.
            if (record.Definition.RewardUnits > 0)
            {
                return HCEventCode.BLOCKED;
            }
            record.Status = HCEventStatus.COMPLETED;
            return HCEventCode.OK;
        }
        return HCEventCode.INVALID;
    }

    static int Observe(HCEventState state, HCEventContext context, HCEventObservation observation)
    {
        if (!ContextValid(state, context))
        {
            return HCEventCode.DENIED;
        }
        if (!observation || observation.Version != 1)
        {
            return HCEventCode.INVALID;
        }
        if (!observation.ServerObserved)
        {
            return HCEventCode.DENIED;
        }
        if (observation.WorldName != state.WorldName || observation.Session != state.Session)
        {
            return HCEventCode.DENIED;
        }
        HCEventRecord record = FindRecord(state, observation.EventId);
        if (!record)
        {
            return HCEventCode.NOT_FOUND;
        }
        if (record.Session != state.Session)
        {
            return HCEventCode.DENIED;
        }
        if (record.Status != HCEventStatus.ACTIVE)
        {
            return HCEventCode.CONFLICT;
        }
        if (context.Now >= record.Expires)
        {
            return HCEventCode.EXPIRED;
        }
        if (!TextValid(observation.ParticipantId, 96))
        {
            return HCEventCode.INVALID;
        }
        if (record.Participants.Find(observation.ParticipantId) < 0)
        {
            return HCEventCode.DENIED;
        }
        if (observation.ObjectiveTag != record.Definition.ObjectiveTag)
        {
            return HCEventCode.INVALID;
        }
        if (observation.Sequence != record.LastObservation + 1)
        {
            return HCEventCode.CONFLICT;
        }
        int remaining = record.Definition.Goal - record.Progress;
        if (observation.Units < 1 || observation.Units > remaining)
        {
            return HCEventCode.INVALID;
        }
        if (record.Revision >= 999999)
        {
            return HCEventCode.LIMIT;
        }
        record.Progress = record.Progress + observation.Units;
        record.LastObservation = observation.Sequence;
        if (record.Progress == record.Definition.Goal)
        {
            record.Status = HCEventStatus.RESOLVING;
        }
        record.Revision = record.Revision + 1;
        state.LastNow = context.Now;
        return HCEventCode.OK;
    }
    static void CompactSessions(HCEventState state)
    {
        array<string> retained = new array<string>();
        foreach (string session : state.Sessions)
        {
            bool needed = session == state.Session;
            foreach (HCEventRecord record : state.Records)
            {
                if (record.Session == session)
                {
                    needed = true;
                }
            }
            if (needed)
            {
                retained.Insert(session);
            }
        }
        state.Sessions = retained;
    }
    static bool PruneFirst(HCEventState state)
    {
        // Runtime must additionally confirm the corresponding run is CLOSED.
        // Never remove current-session duplicate tombstones or live records.
        if (!StateValid(state) || state.Records.Count() == 0)
        {
            return false;
        }
        HCEventRecord oldest = state.Records[0];
        if (!Terminal(oldest.Status) || oldest.Session == state.Session)
        {
            return false;
        }
        state.PrunedThrough = oldest.Id;
        state.Records.RemoveOrdered(0);
        CompactSessions(state);
        return true;
    }
    static int Restart(HCEventState state, HCEventContext context, string newSession)
    {
        if (!ContextValid(state, context))
        {
            return HCEventCode.DENIED;
        }
        if (!TextValid(newSession, 96))
        {
            return HCEventCode.INVALID;
        }
        if (state.Sessions.Find(newSession) >= 0)
        {
            return HCEventCode.CONFLICT;
        }
        if (state.SessionGeneration >= 1000000000)
        {
            return HCEventCode.LIMIT;
        }
        int generation = state.SessionGeneration + 1;
        string canonical = generation.ToString() + ":" + newSession;
        if (!TextValid(canonical, 96) || state.Sessions.Find(canonical) >= 0)
        {
            return HCEventCode.INVALID;
        }
        // This is an in-memory lifecycle restart, not disk crash recovery.
        // No native entities exist here; cancellation releases reservations.
        foreach (HCEventRecord record : state.Records)
        {
            if (!Terminal(record.Status))
            {
                record.Status = HCEventStatus.CANCELLED;
                record.Revision = record.Revision + 1;
            }
        }
        state.SessionGeneration = generation;
        state.Sessions.Insert(canonical);
        state.Session = canonical;
        CompactSessions(state);
        state.LastNow = 0;
        return HCEventCode.OK;
    }
}
