// LC-T401 HCX / EXP-L2. Installed Expansion addons/ai_scripts.pbo:
// 1_Core/DayZExpansion_AI/eAIRegisterFaction.c:6-21 attribute registration;
// 3_Game/DayZExpansion_AI/Factions/eAIFaction.c:94-107,124-167 extension/factory;
// 4_World/DayZExpansion_AI/Factions/eAIFactionInfected.c:1-2 registers in World.
// Original HC classes only; provider sources are neither copied nor replaced.
// IDs are reconciliation ports for the core ledger, never HCWorld types.
class HCXFactions
{
    // HC-37 finite boundary mapping for the server outcome adapter. Unknown
    // provider factions never acquire a ledger identity or become opponents.
    // No change to native targeting, HC-5 surrender/warning/betrayal priority.
    static string HCWorldId(string id)
    {
        if (id == "Locals") { return "locals"; }
        if (id == "Volunteers") { return "volunteers"; }
        if (id == "Scavengers") { return "scavengers"; }
        if (id == "Raiders") { return "raiders"; }
        if (id == "Travellers") { return "travellers"; }
        return "";
    }

    static bool HCEncounterPair(string left, string right)
    {
        if (!Known(left) || !Known(right)) { return false; }
        return Relation(left, right) == -1;
    }

    static bool Known(string id)
    {
        return id == "Locals" || id == "Volunteers" || id == "Scavengers" || id == "Raiders" || id == "Travellers";
    }
    // Symmetric static matrix, ordered Locals/Volunteers/Scavengers/Raiders/Travellers:
    // Locals      +1 +1  0 -1  0
    // Volunteers  +1 +1  0 -1  0
    // Scavengers   0  0 +1 -1  0
    // Raiders     -1 -1 -1 +1 -1
    // Travellers   0  0  0 -1 +1
    static int Relation(string from, string to)
    {
        if (!HCXFactions.Known(from) || !HCXFactions.Known(to)) { return 0; }
        if (from == to) { return 1; }
        if (from == "Raiders" || to == "Raiders") { return -1; }
        if (from == "Locals" && to == "Volunteers") { return 1; }
        if (from == "Volunteers" && to == "Locals") { return 1; }
        return 0;
    }
    static string Id(eAIFaction faction)
    {
        HCXFaction localFaction = HCXFaction.Cast(faction);
        if (!localFaction) { return ""; }
        return localFaction.Id();
    }
    static string SiteFaction(HCXAISite site)
    {
        if (!HCXAIQualification.EncountersEnabled()) { return site.Faction; }
        return EncounterFaction(site);
    }
    // The provider faction a site runs under once encounters are armed.
    static string EncounterFaction(HCXAISite site)
    {
        if (site.ContentRole) { return site.ContentRole.ProviderFaction; }
        if (site.Kind == "scavenger") { return "HCScavengers"; }
        if (site.Kind == "holdout") { return "HCLocals"; }
        return "HCVolunteers";
    }
}
class HCXFaction : eAIFaction
{
    void HCXFaction()
    {
        m_IsGuard = true;
        m_DisableWeaponPickup = true;
    }
    string Id() { return ""; }
    override bool IsFriendly(notnull eAIFaction other)
    {
        string otherId = HCXFactions.Id(other);
        if (otherId == "") { return other.IsGuard() || other.IsPassive(); }
        return HCXFactions.Relation(Id(), otherId) >= 0;
    }
    override string GetDisplayName() { return Id(); }
}
[eAIRegisterFaction(eAIFactionHCLocals)]
class eAIFactionHCLocals : HCXFaction
{
    override string Id() { return "Locals"; }
    override string GetDisplayName() { return "Zimovniki"; }
}
[eAIRegisterFaction(eAIFactionHCVolunteers)]
class eAIFactionHCVolunteers : HCXFaction
{
    override string Id() { return "Volunteers"; }
    override string GetDisplayName() { return "Dobrovoltsy"; }
}
[eAIRegisterFaction(eAIFactionHCScavengers)]
class eAIFactionHCScavengers : HCXFaction
{
    override string Id() { return "Scavengers"; }
    override string GetDisplayName() { return "Sborshchiki"; }
}
[eAIRegisterFaction(eAIFactionHCRaiders)]
class eAIFactionHCRaiders : HCXFaction
{
    void eAIFactionHCRaiders() { m_IsGuard = false; }
    override string Id() { return "Raiders"; }
    override string GetDisplayName() { return "Volki"; }
}
[eAIRegisterFaction(eAIFactionHCTravellers)]
class eAIFactionHCTravellers : HCXFaction
{
    override string Id() { return "Travellers"; }
    override string GetDisplayName() { return "Travellers"; }
}
