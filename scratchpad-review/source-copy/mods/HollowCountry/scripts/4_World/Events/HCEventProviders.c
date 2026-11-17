// Injection ports for trusted server integration, not RPC entry points.
class HCEventPersistence
{
    HCEventRuntimeState Load(string world) { return null; }
    HCEventRuntimeState Clone(HCEventRuntimeState state)
    {
        string data;
        string error;
        HCEventRuntimeState clone;
        if (!JsonFileLoader<HCEventRuntimeState>.MakeData(state, data, error)) return null;
        if (!JsonFileLoader<HCEventRuntimeState>.LoadData(data, clone, error)) return null;
        return clone;
    }
    bool Save(HCEventRuntimeState state) { return false; }
}
class HCEventObjectiveProvider
{
    bool Ready(HCEventMission mission) { return false; }
    bool Prepare(string lease, HCEventMission mission) { return false; }
    HCEventObjectiveEvidence Observe(HCEventRun run, PlayerBase participant, int now) { return null; }
    bool Release(string lease) { return false; }
    void Forget(string lease, PlayerBase participant) {}
}
// Optional provider owns every actor it starts. Stop is a request; only Gone
// confirms actual absence. A failed/partial Start still has a durable lease.
class HCEventAIProvider
{
    bool Ready(string world) { return false; }
    bool Start(string lease, string session, string missionId, vector anchor, int actorCap) { return false; }
    HCEventObjectiveEvidence Observe(string lease, PlayerBase participant) { return null; }
    bool Stop(string lease) { return false; }
    bool Gone(string lease) { return false; }
}
class HCEventSubscription
{
    int EventId;
    string ParticipantId;
    PlayerBase Player;
}
