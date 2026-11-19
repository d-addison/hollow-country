// W6 #60 measurement DTOs; authored candidates are NOT observed cellar classes.
// Native scripts-1.30.164289: 1_Core/proto/EnScript.c:380/394/407 array
// Count/Find/Insert; 3_Game/tools/JsonFileLoader.c:69/85 LoadData/MakeData.
// Owned arrays allocate only after the measurement marker admits the module.
class HCCellarSamplerInstance
{
    vector Position;
    float Yaw;
    bool Eligible;
    string Reason;
    bool GeometryMeasured;
    bool StairAnchorsValid;
    // Local review selection only; sampler never sets this. Not runtime acceptance.
    bool SliceSelected;
}

class HCCellarSamplerClass
{
    string BuildingClass;
    string Model;
    string SurveyTask;
    string Disposition = "pending";
    string Reason = "native_survey_pending";
    // Operator-surveyed local player-height points ON the actual stairs.
    // Default false: geometry probes cannot identify a staircase reliably.
    bool StairsMeasured;
    vector StairTop;
    vector StairBottom;
    vector BoxMin;
    vector BoxMax;
    int SampleCount;
    float Confidence;
    int AcceptedInstances;
    bool Inconsistent;
    ref array<ref HCCellarSamplerInstance> Instances = new array<ref HCCellarSamplerInstance>;
}

// HC-31: existing generator distances moved to authored configuration. Local
// room-scale extents, far below the ~1000m native network/hearing reference.
// No default guessed volume or automatic route recognition.
class HCCellarTriggerDefaults
{
    float StairEnvelopePaddingMeters;
    float BreadcrumbRadiusMeters;
}

class HCCellarSamplerData
{
    int SchemaVersion;
    string WorldName;
    bool Complete;
    string Method = "ground-floor-owner-rays-3x3-clearance-v1";
    int SkippedTiles;
    ref HCCellarTriggerDefaults TriggerDefaults;
    ref array<ref HCCellarSamplerClass> Classes;
}
