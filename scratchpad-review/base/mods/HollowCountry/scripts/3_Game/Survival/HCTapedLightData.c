// Server-owned records only: not an RPC, eligibility claim or geometry catalog.
enum HCTapedLightCode
{
    OK = 0,
    INVALID = 1,
    DENIED = 2,
    BLOCKED = 3,
    CONFLICT = 4,
    QUARANTINED = 5,
    LIMIT = 6
}

enum HCTapedLightPhase
{
    INTENT = 1,
    TAPE_SPENT = 2,
    MOVE_INTENT = 3,
    MOUNTED = 4,
    REMOVED = 5,
    QUARANTINE = 6
}

class HCTapedLightBinding
{
    int Version = 1;
    string ManifestDigest;
    string MeasurementDigest;
    string GameBuild;
    string HostConfigRoot;
    string HostClass;
    string LightClass;
    string SlotName;
    string BatterySlotName;
    // Explicit qualified policy inputs, never inferred from class-name hints.
    float TapeUnits = 0;
    float MaxDistance = 0;
}

class HCTapedLightSnapshot
{
    string ActorId;
    string HostId;
    string LightId;
    string TapeId;
    string BatteryId;
    float HostHealth = 0;
    float LightHealth = 0;
    float TapeHealth = 0;
    float BatteryHealth = 0;
    float BatteryEnergy = 0;
    float LightEnergy = 0;
    float TapeQuantity = 0;
    bool LightOn = false;
    // 0 = actor-owned free light; 1 = exact bound attachment; 2 = actor hands.
    // Unrecognized custody is -1, never implicitly a usable free item.
    int Place = 0;
}

class HCTapedLightRecord
{
    int Version = 1;
    string RecordKey;
    string ActorId;
    string HostId;
    string LightId;
    bool Mounting = false;
    int Phase = 1;
    ref HCTapedLightBinding BindingData;
    ref HCTapedLightSnapshot BeforeData;
}

class HCTapedLightState
{
    int Version = 1;
    bool Ready = false;
    bool Busy = false;
    bool Quarantined = false;
    ref array<ref HCTapedLightRecord> Records = new array<ref HCTapedLightRecord>();
}
