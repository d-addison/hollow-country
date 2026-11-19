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
    static const string DEFAULT_DISPOSITION = "pending";
    static const string DEFAULT_REASON = "native_survey_pending";
    string BuildingClass;
    string Model;
    string SurveyTask;
    string Disposition = DEFAULT_DISPOSITION;
    string Reason = DEFAULT_REASON;
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

    // Native LoadData zero-fills a missing key to "", not the initializer. A
    // missing diagnostic restores the declared pending state, which grants nothing;
    // an explicit authored value is kept.
    void HCRestoreDeclaredDefaults()
    {
        if (Disposition == "") { Disposition = DEFAULT_DISPOSITION; }
        if (Reason == "") { Reason = DEFAULT_REASON; }
    }
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
    static const string DEFAULT_METHOD = "ground-floor-owner-rays-3x3-clearance-v1";
    int SchemaVersion;
    string WorldName;
    bool Complete;
    string Method = DEFAULT_METHOD;
    int SkippedTiles;
    ref HCCellarTriggerDefaults TriggerDefaults;
    ref array<ref HCCellarSamplerClass> Classes;

    // Authored seeds omit Method; native zero-fill would stamp the output with "".
    void HCRestoreDeclaredMethod()
    {
        if (Method == "") { Method = DEFAULT_METHOD; }
    }
}
