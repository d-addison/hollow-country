// #147 shared operator policy. No module slot or mission payload. Override all
// fields in $profile:HollowCountry/w38-situations.json; otherwise source defaults.
// Native scripts-1.30.164289: 1_Core/proto/EnSystem.c:397 FileExist;
// 3_Game/tools/JsonFileLoader.c:69 LoadData; EnDebug.c:96 Print.
// Reads reuse HCGroupIO's bounded file port. No file is written at runtime.
class HCW38SituationPolicy
{
    // Source defaults are the named configuration. Profile override may replace
    // all fields; zero-filled/missing ints fail validation rather than uncap work.
    int Version = 1;
    int ScanRows = 8;
    int MaxConcurrent = 1;
    int MaxThreats = 3;
    int MaxMembers = 6;
    int MaxRouteNodes = 32;
    int MaxIncidents = 64;
    int MaxIncidentItems = 16;
    int PhysicalScanObjects = 64;
    int PhysicalScanCargo = 16;
    // Additive police settings; older complete policies retain these defaults.
    int PoliceSlowRetrySeconds = 300;
    // Police stock container lifecycle (owner 2026-11-22); older policies keep these defaults.
    int RefillCooldownSeconds = 10800;
    int ContainerLifetimeSeconds = 604800;
    float RefillClearRadius = 50;
    ref array<string> PoliceRecoveryClasses = {"PersonalRadio", "Binoculars"};
    ref array<string> PoliceDeliveryClasses = {"PoliceCap"};
    ref array<string> PoliceSalvageClasses = {"Handcuffs", "HandcuffKeys"};
    float MaxRaidMeters = 600;
    float ShelterMeters = 20;
    string InfectedClass = "ZmbM_CitizenASkinny_Brown";
    string RoadSurface = "cp_asphalt1";

    protected static ref HCW38SituationPolicy s_Instance;
    protected static bool s_Loaded;
    protected static bool s_Logged;

    static HCW38SituationPolicy HCGet()
    {
        if (s_Loaded) { return s_Instance; }
        s_Loaded = true;
        HCW38SituationPolicy policy = new HCW38SituationPolicy;
        string path = "$profile:HollowCountry/w38-situations.json";
        if (FileExist(path))
        {
            string encoded;
            string error;
            if (!HCGroupIO.Read(path, 4096, encoded)) { HCInvalid(); return null; }
            if (!HCFields(encoded)) { HCInvalid(); return null; }
            HCW38SituationPolicy defaults = new HCW38SituationPolicy;
            if (!JsonFileLoader<HCW38SituationPolicy>.LoadData(encoded, policy, error)) { HCInvalid(); return null; }
            if (!HCJsonFields.Has(encoded, "PoliceSlowRetrySeconds")) { policy.PoliceSlowRetrySeconds = defaults.PoliceSlowRetrySeconds; }
            if (!HCJsonFields.Has(encoded, "RefillCooldownSeconds")) { policy.RefillCooldownSeconds = defaults.RefillCooldownSeconds; }
            if (!HCJsonFields.Has(encoded, "ContainerLifetimeSeconds")) { policy.ContainerLifetimeSeconds = defaults.ContainerLifetimeSeconds; }
            if (!HCJsonFields.Has(encoded, "RefillClearRadius")) { policy.RefillClearRadius = defaults.RefillClearRadius; }
            if (!HCJsonFields.Has(encoded, "PoliceRecoveryClasses")) { policy.PoliceRecoveryClasses = defaults.PoliceRecoveryClasses; }
            if (!HCJsonFields.Has(encoded, "PoliceDeliveryClasses")) { policy.PoliceDeliveryClasses = defaults.PoliceDeliveryClasses; }
            if (!HCJsonFields.Has(encoded, "PoliceSalvageClasses")) { policy.PoliceSalvageClasses = defaults.PoliceSalvageClasses; }
        }
        if (!HCValid(policy)) { HCInvalid(); return null; }
        s_Instance = policy;
        if (!HCOperatorSettingsRegistry.HCFind("W38Situations.Version"))
        {
            Print("[HC Situations] SITUATION_SETTINGS_REGISTRY_PENDING local_policy_validated runtime=PENDING");
        }
        return s_Instance;
    }

    static bool HCFields(string encoded)
    {
        if (!HCJsonFields.Has(encoded, "Version") || !HCJsonFields.Has(encoded, "ScanRows") || !HCJsonFields.Has(encoded, "MaxConcurrent") || !HCJsonFields.Has(encoded, "MaxThreats") || !HCJsonFields.Has(encoded, "MaxMembers") || !HCJsonFields.Has(encoded, "MaxRouteNodes") || !HCJsonFields.Has(encoded, "MaxIncidents")) { return false; }
        return HCJsonFields.Has(encoded, "MaxIncidentItems") && HCJsonFields.Has(encoded, "PhysicalScanObjects") && HCJsonFields.Has(encoded, "PhysicalScanCargo") && HCJsonFields.Has(encoded, "MaxRaidMeters") && HCJsonFields.Has(encoded, "ShelterMeters") && HCJsonFields.Has(encoded, "InfectedClass") && HCJsonFields.Has(encoded, "RoadSurface");
    }

    static void HCInvalid()
    {
        if (s_Logged) { return; }
        s_Logged = true;
        Print("[HC Situations] SITUATION_POLICY_INVALID runtime=PENDING");
    }

    static array<string> PoliceClasses(int family)
    {
        HCW38SituationPolicy policy = HCGet();
        if (!policy) { return null; }
        if (family == HCEventFamily.RECOVERY) { return policy.PoliceRecoveryClasses; }
        if (family == HCEventFamily.DELIVERY) { return policy.PoliceDeliveryClasses; }
        if (family == HCEventFamily.STATIC_SALVAGE) { return policy.PoliceSalvageClasses; }
        return null;
    }

    static bool PoliceClassesValid(array<string> classes)
    {
        if (!classes || classes.Count() < 1 || classes.Count() > 8) { return false; }
        foreach (string name : classes)
        {
            if (!HCEventDirector.TextValid(name, 96)) { return false; }
        }
        return true;
    }

    static bool HCValid(HCW38SituationPolicy policy)
    {
        // JsonFileLoader zero-fills absent values. Every nonzero field below
        // has an explicit guard; partial/zero/NaN policies never uncap work.
        if (!policy || policy.Version != 1 || policy.ScanRows < 1 || policy.ScanRows > 32) { return false; }
        if (policy.PoliceSlowRetrySeconds < 60 || policy.PoliceSlowRetrySeconds > 3600) { return false; }
        if (policy.RefillCooldownSeconds < 600 || policy.RefillCooldownSeconds > 604800) { return false; }
        if (policy.ContainerLifetimeSeconds < 3600 || policy.ContainerLifetimeSeconds > 2592000) { return false; }
        if (policy.RefillClearRadius != policy.RefillClearRadius || policy.RefillClearRadius < 10 || policy.RefillClearRadius > 200) { return false; }
        if (!PoliceClassesValid(policy.PoliceRecoveryClasses) || !PoliceClassesValid(policy.PoliceDeliveryClasses) || !PoliceClassesValid(policy.PoliceSalvageClasses)) { return false; }
        if (policy.MaxConcurrent != 1 || policy.MaxThreats < 1 || policy.MaxThreats > 6) { return false; }
        if (policy.MaxMembers < 1 || policy.MaxMembers > 6 || policy.MaxRouteNodes < 2 || policy.MaxRouteNodes > 64) { return false; }
        if (policy.MaxIncidents < 1 || policy.MaxIncidents > 64 || policy.MaxIncidentItems < 1 || policy.MaxIncidentItems > 16) { return false; }
        if (policy.PhysicalScanObjects < 1 || policy.PhysicalScanObjects > 128 || policy.PhysicalScanCargo < 1 || policy.PhysicalScanCargo > 64) { return false; }
        if (policy.MaxRaidMeters != policy.MaxRaidMeters || policy.ShelterMeters != policy.ShelterMeters) { return false; }
        if (policy.MaxRaidMeters < 1 || policy.MaxRaidMeters > 1000 || policy.ShelterMeters < 1 || policy.ShelterMeters > 50) { return false; }
        if (HCOperatorSettingsRegistry.HCFind("W38Situations.Version"))
        {
            if (!HCRegistryValid(policy)) { return false; }
        }
        return policy.InfectedClass == "ZmbM_CitizenASkinny_Brown" && policy.RoadSurface != "";
    }

    static bool HCRegistryValid(HCW38SituationPolicy policy)
    {
        if (!HCOperatorSettingsRegistry.HCValid("W38Situations.Version", policy.Version)) { return false; }
        if (!HCOperatorSettingsRegistry.HCValid("W38Situations.ScanRows", policy.ScanRows)) { return false; }
        if (!HCOperatorSettingsRegistry.HCValid("W38Situations.MaxConcurrent", policy.MaxConcurrent)) { return false; }
        if (!HCOperatorSettingsRegistry.HCValid("W38Situations.MaxThreats", policy.MaxThreats)) { return false; }
        if (!HCOperatorSettingsRegistry.HCValid("W38Situations.MaxMembers", policy.MaxMembers)) { return false; }
        if (!HCOperatorSettingsRegistry.HCValid("W38Situations.MaxRouteNodes", policy.MaxRouteNodes)) { return false; }
        if (!HCOperatorSettingsRegistry.HCValid("W38Situations.MaxIncidents", policy.MaxIncidents)) { return false; }
        if (!HCOperatorSettingsRegistry.HCValid("W38Situations.MaxIncidentItems", policy.MaxIncidentItems)) { return false; }
        if (!HCOperatorSettingsRegistry.HCValid("W38Situations.PhysicalScanObjects", policy.PhysicalScanObjects)) { return false; }
        if (!HCOperatorSettingsRegistry.HCValid("W38Situations.PhysicalScanCargo", policy.PhysicalScanCargo)) { return false; }
        if (!HCOperatorSettingsRegistry.HCValid("W38Situations.PoliceSlowRetrySeconds", policy.PoliceSlowRetrySeconds)) { return false; }
        if (!HCOperatorSettingsRegistry.HCValid("W38Situations.RefillCooldownSeconds", policy.RefillCooldownSeconds)) { return false; }
        if (!HCOperatorSettingsRegistry.HCValid("W38Situations.ContainerLifetimeSeconds", policy.ContainerLifetimeSeconds)) { return false; }
        if (!HCOperatorSettingsRegistry.HCValid("W38Situations.RefillClearRadius", policy.RefillClearRadius)) { return false; }
        if (!HCOperatorSettingsRegistry.HCValid("W38Situations.MaxRaidMeters", policy.MaxRaidMeters)) { return false; }
        if (!HCOperatorSettingsRegistry.HCValid("W38Situations.ShelterMeters", policy.ShelterMeters)) { return false; }
        return true;
    }
}
