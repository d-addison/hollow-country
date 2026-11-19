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
    // HC-52: exact authored pair identity survives journal copy/readback.
    // Empty/false retains the HC-7 weapon journal format; never a wearable grant.
    string PairId;
    bool CrossSlot = false;
    // Explicit qualified policy inputs, never inferred from class-name hints.
    float TapeUnits = 0;
    float MaxDistance = 0;
    // v1 keeps the weapon in hands and returns the existing light to cargo.
    bool ReturnToCargo = false;
}

// Server settings owner supplies this section; JSON is preference, not evidence.
// Missing fields preserve the closed default. No client/RPC setter exists.
class HCTapedLightMountSettings
{
    bool crossSlotLights = false;
    ref TStringArray permittedPairIds = new TStringArray;
}

// HC-52 loader DTOs for lights/backpack-mounts.json (#58). Only the closed
// preference defaults are read; every other manifest key is review data. Ints
// keep a zero initializer, so a missing field loads as 0 and is refused; the
// loader also requires HCJsonFields presence first. The file never qualifies.
class HCTapedPackSettingsContract
{
    bool DefaultCrossSlotLights = false;
    ref TStringArray DefaultPermittedPairIds = new TStringArray;
    int MaxPermittedPairIds;
    // Read cap for lights/pair-receipts.json; 0 (missing) is refused.
    int MaxReceiptBytes;
    // Upper bound the manifest accepts for MaxReceiptBytes; 0 (missing) is refused.
    int MaxReceiptBytesCeiling;
}

class HCTapedPackManifest
{
    int SchemaVersion;
    bool Qualified = false;
    ref HCTapedPackSettingsContract SettingsContract = new HCTapedPackSettingsContract;
}

// Per-pair client-check receipt (lights/pair-receipts.json, mission-authored,
// operator reviewed). A receipt is necessary, never sufficient: the operator
// setting and the HCTapedPackCatalog gate must also admit the pair. Fields keep
// zero initializers; the loader requires HCJsonFields presence for each first.
class HCTapedPairReceipt
{
    string PairId;
    bool Checked = false;
    string CheckDate;
    string Note;
}

class HCTapedPairReceipts
{
    int SchemaVersion;
    ref array<ref HCTapedPairReceipt> Receipts = new array<ref HCTapedPairReceipt>();
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
