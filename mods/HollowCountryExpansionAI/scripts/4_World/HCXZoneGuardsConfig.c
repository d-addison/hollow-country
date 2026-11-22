// Parsed through the shared HCJsonSchema loader; HCApply* keeps missing-field defaults.
// ZoneGuards settings keys register in HollowCountry 3_Game
// (AI/HCZoneGuardsSettingsRegistry.c): a modded class must share its base's script module.
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
            HCXZoneGuardsConfig decoded;
            if (raw == "" || !HCJsonSchemaLoader<HCXZoneGuardsConfig>.HCLoadData(raw, decoded, error) || !decoded) { return null; }
            config.Disabled = HCJsonSchema.HCApplyBool(raw, "Disabled", decoded.Disabled, config.Disabled);
            config.CooldownDays = HCJsonSchema.HCApplyInt(raw, "CooldownDays", decoded.CooldownDays, config.CooldownDays);
            config.MaxChangesPerDay = HCJsonSchema.HCApplyInt(raw, "MaxChangesPerDay", decoded.MaxChangesPerDay, config.MaxChangesPerDay);
            config.MaxZones = HCJsonSchema.HCApplyInt(raw, "MaxZones", decoded.MaxZones, config.MaxZones);
            config.MaxOverrunMembers = HCJsonSchema.HCApplyInt(raw, "MaxOverrunMembers", decoded.MaxOverrunMembers, config.MaxOverrunMembers);
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
