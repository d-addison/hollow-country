// #149/#150 spec -> phase selection / historical clues / actual contact receipts.
// Source work only: animal goals, consumption, crow attraction and interaction
// enforcement remain unavailable; no behaviour-slot override or teleport.
// Native scripts-1.30.164289 (installed, read only):
// 2_GameLib/gameLib.c:4 GetGame; 1_Core/proto/EnDebug.c:96 Print;
// 1_Core/proto/EnConvert.c:30 int.ToString.
// 3_Game/Global/Game.c:1093 GetMission, :1535 GetTime; gameplay.c:742 GetWorldData;
// Object.c:287 GetPosition, :215 IsPendingDeletion, :517 IsAlive, :511 IsKindOf;
// EntityAI.c:1143 EEHitBy; DamageSystem.c:3 TotalDamageResult.GetDamage;
// DayZAnimal.c:832 EEHitBy; 4_World/Entities/ManBase/PlayerBase.c:1255 EEHitBy;
// 1_Core/proto/EnScript.c:380/385/399/407/470 Count/Clear/Get/Insert/RemoveOrdered,
// :94 Cast. No Expansion calls. HC ports retain their own native citations.
// Runtime state uses ONE existing HCWorldIncidents registry for clues. Local
// contact receipts store actual damage callbacks only, not AI targets or rights.

class HCWildlifeRoute
{
    string Id;
    string Species;
    int Phase;
    vector Position;
    float RadiusM;
    string Role;
    string Source;
}

class HCWildlifeRoutes
{
    static bool HCPhaseValid(int phase) { return phase >= 0 && phase <= 3; }

    static bool HCValidRoute(HCWildlifeRoute route)
    {
        if (!route || !HCEcologyRuntimeRules.Token(route.Id) || !HCPhaseValid(route.Phase)) { return false; }
        if (route.Species != "Animal_CervusElaphus" && route.Species != "Animal_CanisLupus") { return false; }
        if (!HCEcologyRuntimeRules.PositionValid(route.Position)) { return false; }
        if (!(route.RadiusM > 0) || route.RadiusM > 2000) { return false; }
        return route.Role == "Graze" || route.Role == "Rest" || route.Role == "Water" || route.Role == "HuntingGround";
    }

    // No fallback spring when the authoritative weather owner is off/paused.
    static int HCPhase()
    {
        if (!HCEcologyNative.Authority()) { return -1; }
        Mission mission = GetGame().GetMission();
        if (!mission) { return -1; }
        ChernarusPlusData data = ChernarusPlusData.Cast(mission.GetWorldData());
        if (!data) { return -1; }
        return data.HCSeasonPhaseCode();
    }

    static HCWildlifeRoute HCSelect(array<ref HCWildlifeRoute> routes, string species, int phase)
    {
        if (!routes || !HCPhaseValid(phase)) { return null; }
        foreach (HCWildlifeRoute route : routes)
        {
            if (route && route.Species == species && route.Phase == phase) { return route; }
        }
        return null;
    }

    static bool HCConfigValid(HCWildlifeProviderConfig config)
    {
        if (!config || !config.Routes || config.Routes.Count() < 1 || config.Routes.Count() > 32) { return false; }
        if (config.ClueLifetimeSeconds < 1 || config.ClueLifetimeSeconds > 3600) { return false; }
        // A zero sight range prevents unsupported animal perception claims.
        // Future consumers need an inspected animal perception port first.
        array<string> keys = new array<string>;
        array<ref HCWildlifeRoute> routes = config.Routes;
        foreach (HCWildlifeRoute row : routes)
        {
            if (!HCValidRoute(row) || row.Source == "") { return false; }
            string key = row.Species + ":" + row.Phase.ToString();
            if (keys.Find(key) >= 0) { return false; }
            keys.Insert(key);
        }
        return keys.Count() == 8;
    }
}

class HCWildlifeContact
{
    // Weak session-only handles. Native ownership and eligibility never change.
    EntityAI Attacker;
    EntityAI Victim;
    int StartedAt;
    int EndsAt;
    int RetryAt;
}

class HCWildlifeInteractions
{
    protected ref HCWildlifeProviderConfig m_Config;
    protected ref array<ref HCWildlifeContact> m_Contacts = new array<ref HCWildlifeContact>;
    protected int m_ContactCursor;

    void HCConfigure(HCWildlifeProviderConfig config) { m_Config = config; }
    void HCClear() { m_Contacts.Clear(); m_ContactCursor = 0; }

    // True = receipt admitted, NEVER permission for a native attack. Repeated
    // callbacks cannot renew a lease or skip its cooldown; no unseen target
    // inference. MaxPairs bounds bookkeeping, not the engine's combat count.
    bool HCContact(EntityAI attacker, EntityAI victim, int nowMs)
    {
        if (!attacker || !victim || attacker == victim || nowMs < 0) { return false; }
        if (nowMs > 2147483647 - m_Config.PairLifetimeMs - m_Config.PairCooldownMs) { return false; }
        array<ref HCWildlifeContact> contacts = m_Contacts;
        foreach (HCWildlifeContact existing : contacts)
        {
            if (existing.Attacker != attacker || existing.Victim != victim) { continue; }
            if (nowMs < existing.StartedAt) { return false; }
            if (nowMs < existing.EndsAt) { return true; }
            if (nowMs < existing.RetryAt) { return false; }
            existing.StartedAt = nowMs;
            existing.EndsAt = nowMs + m_Config.PairLifetimeMs;
            existing.RetryAt = existing.EndsAt + m_Config.PairCooldownMs;
            return true;
        }
        if (m_Contacts.Count() >= m_Config.MaxPairs) { return false; }
        HCWildlifeContact contact = new HCWildlifeContact;
        contact.Attacker = attacker;
        contact.Victim = victim;
        contact.StartedAt = nowMs;
        contact.EndsAt = nowMs + m_Config.PairLifetimeMs;
        contact.RetryAt = contact.EndsAt + m_Config.PairCooldownMs;
        m_Contacts.Insert(contact);
        return true;
    }

    // One caller-charged finite slice. Retain cooldown receipts to prevent
    // repeated damage from reopening a pair at the active lease boundary.
    void HCSweep(int nowMs)
    {
        int checked = 0;
        int total = m_Contacts.Count();
        while (checked < total && checked < m_Config.MaxPairChecksPerTick && m_Contacts.Count() > 0)
        {
            if (m_ContactCursor >= m_Contacts.Count()) { m_ContactCursor = 0; }
            HCWildlifeContact contact = m_Contacts.Get(m_ContactCursor);
            checked = checked + 1;
            if (!contact.Attacker || !contact.Victim || nowMs < contact.StartedAt || nowMs >= contact.RetryAt)
            {
                m_Contacts.RemoveOrdered(m_ContactCursor);
                continue;
            }
            m_ContactCursor = m_ContactCursor + 1;
        }
    }
}

// Existing provider owns all start/stop/tick state; no new module or timer.
// Historical blood points never retain a living player's handle. Carcass
// points are short-lived snapshots, not live targets, loot rights or refills.

modded class AnimalBase
{
    override void EEHitBy(TotalDamageResult damageResult, int damageType, EntityAI source, int component, string dmgZone, string ammo, vector modelPos, float speedCoef)
    {
        super.EEHitBy(damageResult, damageType, source, component, dmgZone, ammo, modelPos, speedCoef);
        HCWildlifeProviders.HCRecordDamage(this, source, damageResult, dmgZone);
    }
}

modded class PlayerBase
{
    override void EEHitBy(TotalDamageResult damageResult, int damageType, EntityAI source, int component, string dmgZone, string ammo, vector modelPos, float speedCoef)
    {
        super.EEHitBy(damageResult, damageType, source, component, dmgZone, ammo, modelPos, speedCoef);
        HCWildlifeProviders.HCRecordDamage(this, source, damageResult, dmgZone);
    }
}
