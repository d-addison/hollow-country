// Optional mission policy DTOs, not an RPC protocol or enabled gameplay.
// Only a trusted server adapter may construct contexts and observations.
// ParticipantId must come from authenticated server identity, never client DTOs.
enum HCEventCode
{
    OK = 0,
    INVALID = 1,
    DENIED = 2,
    CONFLICT = 3,
    LIMIT = 4,
    NOT_FOUND = 5,
    EXPIRED = 6,
    BLOCKED = 7
}

enum HCEventStatus
{
    PROPOSED = 0,
    ANNOUNCED = 1,
    ACTIVE = 2,
    RESOLVING = 3,
    COMPLETED = 4,
    EXPIRED = 5,
    CANCELLED = 6
}

enum HCEventOp
{
    JOIN = 1,
    LEAVE = 2,
    ANNOUNCE = 3,
    ACTIVATE = 4,
    COMPLETE = 5,
    CANCEL = 6,
    EXPIRE = 7
}

class HCEventContext
{
    bool Server = false;
    string WorldName;
    string Session;
    // Trusted session-relative whole seconds, not Unix time.
    int Now = 0;
}

class HCEventDefinition
{
    int Version = 1;
    string Id;
    string WorldName;
    // A server adapter must qualify the actual objective observation.
    string ObjectiveTag;
    int Goal = 1;
    int MaxParticipants = 6;
    int ActorBudget = 0;
    int ItemBudget = 0;
    int LifetimeSeconds = 600;
    int RewardUnits = 0;
}

class HCEventRecord
{
    int Id = 0;
    int Revision = 1;
    int Status = 0;
    string Session;
    ref HCEventDefinition Definition;
    int Expires = 0;
    int Progress = 0;
    int LastObservation = 0;
    ref array<string> Participants = new array<string>();
}

class HCEventState
{
    int Version = 1;
    string WorldName;
    string Session;
    int LastNow = 0;
    int NextId = 1;
    ref array<string> Sessions = new array<string>();
    ref array<ref HCEventRecord> Records = new array<ref HCEventRecord>();
}

class HCEventRequest
{
    int Version = 1;
    int EventId = 0;
    int ExpectedRevision = 0;
    int Op = 0;
    string ParticipantId;
}

class HCEventObservation
{
    int Version = 1;
    bool ServerObserved = false;
    string WorldName;
    string Session;
    int EventId = 0;
    string ParticipantId;
    string ObjectiveTag;
    int Sequence = 0;
    int Units = 0;
}

// Cooperative shared progress, explicit join/leave, no ignore/abandon penalty.
// Budgets reserve capacity only: no actors/items are spawned or destroyed here.
// State is bounded in memory. No durable file recovery or reward claim proof.
// Restart cancels unfinished records; terminal IDs/session tombstones stay.
// A full registry refuses new events instead of recycling replay protection.
// Nonzero rewards block completion until a qualified durable CE adapter exists.
