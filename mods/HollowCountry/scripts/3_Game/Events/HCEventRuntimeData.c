// Original server-owned mission configuration. Preferences are enabled; reviewed
// sites and qualified providers are prerequisites, never implied by this flag.
enum HCEventFamily
{
    RECOVERY = 1,
    DELIVERY = 2,
    INVESTIGATION = 3,
    STATIC_SALVAGE = 4,
    AI_ENCOUNTER = 5,
    PRESENCE = 6,
    INFECTED_CLEAR = 7
}
enum HCEventRunPhase
{
    PREPARED = 0,
    ACTIVE = 1,
    CLEANUP = 2,
    CLOSED = 3
}
class HCEventSettings
{
    int Version = 1;
    bool Enabled = true;
    int WorkPerTick = 8;
    int MaxRuns = 32;
    int MaxSubscriptions = 192;
    int MaxStoreBytes = 1048576;
    ref array<ref HCEventSite> Sites = new array<ref HCEventSite>();
}
class HCEventSite
{
    string Id;
    string WorldName;
    bool Reviewed = false;
    vector Position;
    vector Destination;
    string ItemClass;
    string DeliveryClass;
    string SalvageClass;
    string ContainerClass;
    string AnchorClass;
    // Server-created reward cache for this site's RECOVERY assignment (needs events_sites.enable).
    bool RewardCache = false;
    // Source review is not a field survey or runtime geometry acceptance.
    bool Surveyed = false;
    string Provenance;
    string SourceSha256;
}
class HCEventMission
{
    int Version = 1;
    string Id;
    string SiteId;
    string WorldName;
    bool Reviewed = false;
    int Family = 1;
    vector Source;
    vector Destination;
    float Radius = 15;
    int DwellSeconds = 10;
    string ItemClass;
    int Goal = 1;
    int MaxParticipants = 6;
    int ActorBudget = 0;
    int LifetimeSeconds = 1800;
    int RewardUnits = 0;
    string ContainerClass;
    string AnchorClass;
    bool RewardCache = false;
}
class HCEventRun
{
    int EventId = 0;
    string Lease;
    ref HCEventMission Objective;
    int Phase = 0;
    bool ProviderIntent = false;
    ref array<string> Tokens = new array<string>();
}
class HCEventRuntimeState
{
    int Version = 1;
    int Revision = 0;
    ref HCEventState Director;
    ref array<ref HCEventRun> Runs = new array<ref HCEventRun>();
}
class HCEventObjectiveEvidence
{
    bool Observed = false;
    string Lease;
    string Session;
    string ParticipantId;
    int Sequence = 0;
    string Token;
}
class HCEventJournalReceipt
{
    int Version = 1;
    int Revision = 0;
    string WorldName;
    int Length = 0;
    int Hash = 0;
}
