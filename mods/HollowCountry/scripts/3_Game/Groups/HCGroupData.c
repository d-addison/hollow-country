// Wire DTOs and standalone validated settings. No native/Workshop asset copies.
class HCGroupSettings
{
    // Server admission signal for optional W5 client input; never client authority.
    bool HCTeamPingEnabled = false;
    int SchemaVersion = 1;
    bool Enabled = true;
    bool WorldIcons = true;
    bool MapIcons = true;
    bool RequireGPS = false;
    bool RequireLOS = false;
    bool RequireRadio = false;
    bool NavigationLayer = true;
    bool DiscoveryLayer = true;
    bool MissionLayer = true;
    // Share only recorded visits within the server-owned group; false opts out.
    bool ShareDiscovery = true;
    int MaxLOSRaysPerTick = 56;
    int MaxDiscoveries = 64;
    int MaxExplorers = 256;
    float DiscoveryIntervalSeconds = 5.0;
    float IconScale = 1.0;
    float LabelScale = 1.0;
    int MaxGroups = 32;
    int MaxMembers = 8;
    int MaxMarkers = 64;
    int MaxInvites = 64;
    int MaxRequestsPerSecond = 4;
    int MaxStoreBytes = 262144;
    int KeepRevisions = 8;
    int InviteSeconds = 120;
    int MarkerRetentionSeconds = 604800;
    float PositionIntervalSeconds = 2.0;
    float PositionStaleSeconds = 10.0;
    float MaxIconDistance = 1000.0;
}
// Native 1.30.164289: 1_Core/proto/EnDebug.c:96 Print. Presence
// distinguishes native missing-key zero-fill from the operator's explicit false.
class HCGroupSettingDefaults
{
    static void HCRestoreMissingDefaults(HCGroupSettings settings, string content)
    {
        if (HCJsonFields.Has(content, "ShareDiscovery")) { return; }
        HCGroupSettings declared = new HCGroupSettings;
        settings.ShareDiscovery = declared.ShareDiscovery;
        Print("[HC Groups] settings.json missing ShareDiscovery; declared default restored ShareDiscovery=true runtime=PENDING");
    }
}

class HCGroupRequest
{
    int Version = 3;
    int RequestId = 0;
    int Op = 0;
    int ExpectedRevision = 0;
    int EntityId = 0;
    int Role = 0;
    string Session;
    string TargetId;
    string Name;
    string Note;
    vector Position;
    int Color = -1;
    int Icon = 0;
    int TtlSeconds = 0;
}
class HCGroupMember
{
    int Role = 0;
    string Id;
    string Name;
    bool Online = false;
    bool Alive = false;
    bool HasPosition = false;
    vector Position;
    int SampleUtc = 0;
}
class HCGroupInvitation
{
    int Id = 0;
    int GroupId = 0;
    int ExpiresUtc = 0;
    string InviterId;
    string InviteeId;
    string GroupName;
}
class HCGroupMarker
{
    int Id = 0;
    int Color = -1;
    int Icon = 0;
    int ExpiresUtc = 0;
    string CreatorId;
    string Name;
    string Note;
    vector Position;
}
class HCGroupSnapshot
{
    int Version = 3;
    int Kind = 0;
    int RequestId = 0;
    // Session counter floor, not acknowledgment of the snapshot RequestId.
    int LastMutationId = 0;
    int Sequence = 0;
    int Revision = 0;
    int Epoch = 0;
    int GroupId = 0;
    string Session;
    string Name;
    string OwnerId;
    bool Enabled = false;
    ref HCGroupSettings Settings;
    ref array<ref HCGroupPlace> Places = new array<ref HCGroupPlace>();
    ref array<ref HCGroupMember> Members = new array<ref HCGroupMember>();
    ref array<ref HCGroupMember> Candidates = new array<ref HCGroupMember>();
    ref array<ref HCGroupInvitation> Invitations = new array<ref HCGroupInvitation>();
    ref array<ref HCGroupMarker> Markers = new array<ref HCGroupMarker>();
}
class HCGroupReply
{
    int Version = 3;
    int RequestId = 0;
    int LastMutationId = 0;
    int Code = 0;
    int Revision = 0;
    string Session;
}
// Durable membership belongs to an account, not a character or session. Invite
// records participate in in-memory transactions but are omitted from disk.
class HCGroupRecord
{
    int Id = 0;
    int Revision = 0;
    int Epoch = 0;
    string Name;
    string OwnerId;
    ref array<string> Members = new array<string>();
    // Additive v1 migration: owner stays OwnerId, absent Officers means all
    // other existing members remain ordinary members. No ACL is inferred.
    ref array<string> Officers = new array<string>();
    ref array<ref HCGroupMarker> Markers = new array<ref HCGroupMarker>();
    // V2 LC-T207 trail pins (server-owned, at most 48, "hc-found:" ids). Old
    // journals keep the empty initializer; dissolving a group removes its pins.
    ref array<string> HCTrailPlaceIds = new array<string>();
}
class HCGroupState
{
    int Version = 1;
    int Revision = 0;
    int NextId = 1;
    // Additive v1 field: old images deserialize to zero (unknown watermark).
    // The next successful mutation establishes it without resetting any ACL.
    int LastMutationUtc = 0;
    string WorldName;
    ref array<ref HCGroupExplorer> Explorers = new array<ref HCGroupExplorer>();
    ref array<ref HCGroupRecord> Groups = new array<ref HCGroupRecord>();
    ref array<ref HCGroupInvitation> Invitations = new array<ref HCGroupInvitation>();
}
class HCGroupReceipt
{
    int Version = 1;
    int Revision = 0;
    int Length = 0;
    int Hash = 0;
    string WorldName;
}

// Catalog is server-owned; only observed entries are ever sent to clients.
class HCGroupPlace
{
    string Id;
    string Name;
    vector Position;
    float Radius = 100.0;
    // V2 LC-T305 lead pin display expiry between FULL frames; never an actor position.
    int HCPinExpiresUtc = 0;
}
class HCGroupExplorer
{
    string Id;
    int LastSeenUtc = 0;
    ref array<string> PlaceIds = new array<string>();
    // Read-only migration input for pre-v3 journals. Cleared before saving.
    ref array<ref HCGroupPlace> Visits = new array<ref HCGroupPlace>();
}
class HCGroupPlaceCatalog
{
    int SchemaVersion = 1;
    ref array<ref HCGroupPlace> Places = new array<ref HCGroupPlace>();
}
