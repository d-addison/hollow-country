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
}

class HCCellarSamplerClass
{
    string BuildingClass;
    string Model;
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

class HCCellarSamplerData
{
    int SchemaVersion;
    string WorldName;
    bool Complete;
    string Method = "ground-floor-owner-rays-3x3-clearance-v1";
    ref array<ref HCCellarSamplerClass> Classes;
}
