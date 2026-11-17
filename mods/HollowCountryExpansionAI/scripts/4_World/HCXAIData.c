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
    // Closed alone may be a restart tombstone or a faulted intent. Legacy rows
    // default false: only observed clean retirement may make history reusable.
    bool Prunable = false;
}
class HCXAIJournalData
{
    int SchemaVersion = 1;
    ref array<ref HCXAIJournalRow> Rows = new array<ref HCXAIJournalRow>();
}
// HC sites (patrols, scavenger parties, holdouts) run as native eAIDynamicPatrol
// subclasses. Shipped policy JSON; positions come from stock vanilla map data.
class HCXAISiteLoot
{
    string ClassName;
    int Quantity = 1;
}
class HCXAISite
{
    string Id;
    string Kind;
    string Faction;
    string Loadout;
    int NumberOfAI = 2;
    int NumberOfAIMax = 3;
    string Behaviour = "LOOP";
    string Speed = "WALK";
    float ActivationRadius = 600;
    int DespawnSeconds = 600;
    int RespawnSeconds = 3600;
    ref array<vector> Waypoints = new array<vector>();
    string HouseClass;
    vector HousePosition;
    ref array<vector> LocalPoints = new array<vector>();
    string CacheClass;
    vector CacheLocal;
    int CacheCooldownSeconds = 0;
    ref array<ref HCXAISiteLoot> CacheLoot = new array<ref HCXAISiteLoot>();
}
class HCXAISitePolicy
{
    int SchemaVersion = 1;
    string WorldName = "chernarusplus";
    string BuildVersion = "1.30.164289";
    string ObserverPolicy = "native-eai";
    int MaxActiveAI = 24;
    int MaxActiveSites = 8;
    float MinPlayerDistance = 200;
    float LineOfSightRange = 1000;
    float MaxLegLength = 400;
    float CacheClearRadius = 300;
    ref array<ref HCXAISite> Sites = new array<ref HCXAISite>();
}
// Gathered natively at startup; never read from profile or RPC data.
class HCXAISiteAdmission
{
    string BuildVersion;
    string WorldName;
    string MissingAddons;
    bool SettingsLoaded = false;
    string Globals;
    string UnfairFaction;
    string MissingLoadout;
    string ObserverPolicy;
    bool Marker = false;
    bool OwnershipReconciled = false;
}
class HCXAIRouteRow
{
    string Key;
    string SiteId;
    bool Qualified = false;
    string Reason;
}
class HCXAIRouteCache
{
    int SchemaVersion = 1;
    ref array<ref HCXAIRouteRow> Rows = new array<ref HCXAIRouteRow>();
}
// One row per holdout site: State seeding (intent), seeded or looted.
class HCXAICacheRow
{
    string SiteId;
    int Lifecycle = 0;
    string ClassName;
    string State;
    int SeededAt = 0;
    int LootedAt = 0;
    int NextRefillAt = 0;
}
class HCXAICacheJournal
{
    int SchemaVersion = 1;
    ref array<ref HCXAICacheRow> Rows = new array<ref HCXAICacheRow>();
}
// Sites with live actors at the last save; a restart sweeps their "HC:" groups.
class HCXAIOwnedRow
{
    string SiteId;
    int Members = 0;
}
class HCXAIOwnership
{
    int SchemaVersion = 1;
    int Session = 0;
    ref array<ref HCXAIOwnedRow> Rows = new array<ref HCXAIOwnedRow>();
}
