// ZoneGuards owns its scoped settings; HCSettings remains unchanged.
modded class HCOperatorSettingsRegistry
{
    protected static bool s_HCZonesRegistered;
    static void HCZoneGuardsInit()
    {
        HCInit();
        if (s_HCZonesRegistered) { return; }
        s_HCZonesRegistered = true;
        HCAdd("HCZoneGuards.Disabled", "bool", 0, 0, 1, "HCXZoneGuardsConfig");
        HCAdd("HCZoneGuards.CooldownDays", "int", 2, 1, 30, "HCXZoneGuardsConfig");
        HCAdd("HCZoneGuards.MaxChangesPerDay", "int", 2, 1, 2, "HCXZoneGuardsConfig");
        HCAdd("HCZoneGuards.MaxZones", "int", 128, 1, 128, "HCXZoneGuardsConfig");
        HCAdd("HCZoneGuards.MaxOverrunMembers", "int", 6, 3, 6, "HCXZoneGuardsConfig");
    }
}
class HCXZoneGuardsConfig
{
    bool Disabled;
    int CooldownDays = 2;
    int MaxChangesPerDay = 2;
    int MaxZones = 128;
    int MaxOverrunMembers = 6;

    static HCXZoneGuardsConfig Load()
    {
        HCOperatorSettingsRegistry.HCZoneGuardsInit();
        string path = "$profile:HollowCountry/hollow-country-zones.json";
        HCXZoneGuardsConfig config = new HCXZoneGuardsConfig;
        if (FileExist(path))
        {
            string raw = HCWorldStore.Read(path);
            string error;
            if (raw == "" || !JsonFileLoader<HCXZoneGuardsConfig>.LoadData(raw, config, error) || !config) { return null; }
            if (!HCJsonFields.Has(raw, "CooldownDays")) { config.CooldownDays = 2; }
            if (!HCJsonFields.Has(raw, "MaxChangesPerDay")) { config.MaxChangesPerDay = 2; }
            if (!HCJsonFields.Has(raw, "MaxZones")) { config.MaxZones = 128; }
            if (!HCJsonFields.Has(raw, "MaxOverrunMembers")) { config.MaxOverrunMembers = 6; }
        }
        if (!HCOperatorSettingsRegistry.HCValid("HCZoneGuards.CooldownDays", config.CooldownDays) || !HCOperatorSettingsRegistry.HCValid("HCZoneGuards.MaxChangesPerDay", config.MaxChangesPerDay) || !HCOperatorSettingsRegistry.HCValid("HCZoneGuards.MaxZones", config.MaxZones) || !HCOperatorSettingsRegistry.HCValid("HCZoneGuards.MaxOverrunMembers", config.MaxOverrunMembers)) { return null; }
        return config;
    }
}
class HCXZoneGuardsZone
{
    string id;
    string area;
    vector center;
    float radius_m;
    int tier;
    ref array<string> sites = new array<string>;
    ref array<vector> guard_slots = new array<vector>;
    string default_state;
}
class HCXZoneGuardsCatalog
{
    ref array<ref HCXZoneGuardsZone> zones = new array<ref HCXZoneGuardsZone>;
}
class HCXZoneGuardsRow
{
    string Id;
    string State;
    int ChangedDay;
    // A durable full-wipe receipt is recorded by the existing native death hook.
    bool Wiped;
}
class HCXZoneGuardsJournal
{
    int Version = 1;
    int LastDay = -1;
    int ChangedToday;
    int Cursor;
    ref array<ref HCXZoneGuardsRow> Rows = new array<ref HCXZoneGuardsRow>;
}
class HCXZoneGuardsSave : HCSaveJob
{
    ref HCXZoneGuardsJournal Data;
    protected ref HCV2ThreatStore<HCXZoneGuardsJournal> m_Writer = new HCV2ThreatStore<HCXZoneGuardsJournal>;
    bool Fault;
    override string HCName() { return "zone_guards"; }
    override int HCStep()
    {
        int result = m_Writer.SaveStep("$profile:HollowCountry/zone-guards-state.json", Data, 65536);
        if (result == STEP_FAILED) { Fault = true; }
        return result;
    }
}
