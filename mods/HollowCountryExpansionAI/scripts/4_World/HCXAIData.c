// Original HC DTOs. No provider implementation or assets are included.
class HCXAIEquipment
{
    string ClassName;
    bool InHands = false;
    bool IsMagazine = false;
    int AmmoCount = 0;
}
class HCXAIMission
{
    string MissionId;
    string SiteId;
    int GroupSize = 0;
    string ActorClass;
    string FactionName;
    vector Anchor;
    string SurveySha256;
    string LoadoutSha256;
    ref array<vector> Spawns = new array<vector>();
    ref array<vector> Waypoints = new array<vector>();
    ref array<ref HCXAIEquipment> Equipment = new array<ref HCXAIEquipment>();
}
class HCXAIProfile
{
    int SchemaVersion = 1;
    bool Enabled = true;
    bool Experimental = true;
    bool AllowBuiltinStuckRecovery = true;
    bool ProvisionalBounds = true;
    string SourceCommit = "d84d3c73694969eba2f969e9178a1914e2f1b31d";
    string ProviderVersion = "1.9.84";
    string BuildVersion = "1.30.164289";
    string NativeScriptsSha256 = "09012cdae8c4ae2d478ca90f3e2e3f01e435f0f6945a63b7cae290e3ccdea28a";
    string WorldName;
    string WorldSession;
    string WorldSha256;
    string ArtifactSha256;
    string DependencyInventorySha256;
    int MaxGroups = 0;
    int MaxActors = 0;
    int MaxItems = 0;
    int MaxTickWork = 0;
    int MaxLeaseHistory = 0;
    int MaxObservationAgeMs = 0;
    int MaxLeaseMs = 0;
    float CoordinateBound = 0;
    ref HCObserverTransitionPolicy ObserverPolicy = new HCObserverTransitionPolicy();
    ref array<ref HCXAIMission> Missions = new array<ref HCXAIMission>();
}
// Obtained only from the installed trusted server hook, never profile/RPC JSON.
class HCXAIAdmission
{
    string SourceCommit;
    string BuildVersion;
    string NativeScriptsSha256;
    string WorldName;
    string WorldSession;
    string WorldSha256;
    string ArtifactSha256;
    string DependencyInventorySha256;
    int Sequence = 0;
    int ObservedAtMs = -1;
    bool ArtifactBytesVerified = false;
    bool DependencyClosureVerified = false;
    bool ObserverProviderQualified = false;
    bool RoutesQualified = false;
    bool InventoryLedgerQualified = false;
    bool OwnershipReconciled = false;
}
class HCXAIActorSlot
{
    Object Handle;
    bool Attempted = false;
    bool DeleteRequested = false;
    bool DeleteObserved = false;
    bool Gone = false;
    bool DeathObserved = false;
    ref HCObserverTransitionState SpawnGate = new HCObserverTransitionState();
    ref HCObserverTransitionState RetireGate = new HCObserverTransitionState();
}
class HCXAIKill
{
    string ParticipantId;
    string Token;
}
class HCXAILease
{
    string Id;
    string Session;
    string MissionId;
    vector Anchor;
    int RequestedCap = 0;
    int StartedAtMs = 0;
    int ActorReservation = 0;
    int ItemReservation = 0;
    int Cursor = 0;
    int Sequence = 0;
    string ReceiptToken;
    string ReceiptParticipant;
    bool Busy = false;
    bool IntentConfirmed = false;
    bool Retiring = false;
    bool Failed = false;
    bool Released = false;
    eAIGroup Group;
    ref HCXAIMission Objective;
    ref array<ref HCXAIActorSlot> Slots = new array<ref HCXAIActorSlot>();
    ref array<ref HCXAIKill> Kills = new array<ref HCXAIKill>();
}
// Metadata only: never serialize native actors, groups or inventories.
class HCXAIJournalRow
{
    string Id;
    string WorldSession;
    string Session;
    string MissionId;
    bool Closed = false;
}
class HCXAIJournalData
{
    int SchemaVersion = 1;
    ref array<ref HCXAIJournalRow> Rows = new array<ref HCXAIJournalRow>();
}
