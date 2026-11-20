// Shared fields/accessors only; no gameplay method is overridden here.
modded class ZombieBase
{
    int m_HCMeleeArmHitsL;
    int m_HCMeleeArmHitsR;
    bool m_HCMeleeArmWeakL;
    bool m_HCMeleeArmWeakR;
    float m_HCMeleeCooldownSeen;
    float m_HCMeleePoiseWindowStart;
    int m_HCMeleePoiseCount;
    bool m_HCMeleeCounterPending;

    int HCMeleeWeakArms()
    {
        int count;
        if (m_HCMeleeArmWeakL) { count++; }
        if (m_HCMeleeArmWeakR) { count++; }
        return count;
    }

    // bool resolves the brief's contradictory void/"returns true" declaration.
    // Exactly one transition per arm; counters stop growing once it is weak.
    bool HCMeleeMarkArmHit(bool left, bool heavy, int lightHitsNeeded)
    {
        if (left)
        {
            if (m_HCMeleeArmWeakL) { return false; }
            m_HCMeleeArmHitsL++;
            if (!heavy && m_HCMeleeArmHitsL < lightHitsNeeded) { return false; }
            m_HCMeleeArmWeakL = true;
            return true;
        }
        if (m_HCMeleeArmWeakR) { return false; }
        m_HCMeleeArmHitsR++;
        if (!heavy && m_HCMeleeArmHitsR < lightHitsNeeded) { return false; }
        m_HCMeleeArmWeakR = true;
        return true;
    }
}

modded class PlayerBase
{
    float m_HCMeleeImmuneUntil;
    ZombieBase m_HCMeleeBlockedBy;
    float m_HCMeleeBlockedAt;

    void HCMeleeRecordBlock(ZombieBase z, float now)
    {
        m_HCMeleeBlockedBy = z;
        m_HCMeleeBlockedAt = now;
    }

    bool HCMeleeConsumeCounter(ZombieBase z, float now, float window)
    {
        if (!z || z != m_HCMeleeBlockedBy) { return false; }
        float elapsed = now - m_HCMeleeBlockedAt;
        m_HCMeleeBlockedBy = null;
        m_HCMeleeBlockedAt = 0;
        return elapsed >= 0 && elapsed <= window;
    }
}

// Native scripts-1.30.164289: 3_Game/Global/Game.c:524,539,612
// ConfigGetFloat/ConfigGetInt/ConfigIsExisting; 1_Core/proto/EnString.c:240
// IndexOf; EnScript.c:880,902 map Find/Set. Only existing melee ammo is cached.
class HCMeleeAmmoData
{
    bool Heavy;
    float Health;
}

class HCMeleeAmmo
{
    protected static ref map<string, ref HCMeleeAmmoData> s_Ammo = new map<string, ref HCMeleeAmmoData>;

    static bool IsHC(string ammo) { return ammo.IndexOf("HCMelee") == 0; }
    static bool IsBlockedInfectedAmmo(string ammo) { return ammo == "Dummy_Light" || ammo == "MeleeZombie"; }

    protected static HCMeleeAmmoData HCData(string ammo)
    {
        HCMeleeAmmoData cached;
        if (s_Ammo.Find(ammo, cached)) { return cached; }
        if (ammo.IndexOf("Melee") != 0 && !HCMeleeAmmo.IsHC(ammo) && ammo != "Dummy_Light") { return null; }
        string path = "CfgAmmo " + ammo;
        if (!GetGame().ConfigIsExisting(path)) { return null; }
        cached = new HCMeleeAmmoData;
        cached.Heavy = GetGame().ConfigGetInt(path + " hitAnimation") == 1;
        cached.Health = GetGame().ConfigGetFloat(path + " DamageApplied Health damage");
        s_Ammo.Set(ammo, cached);
        return cached;
    }

    static bool IsHeavy(string ammo)
    {
        HCMeleeAmmoData data = HCMeleeAmmo.HCData(ammo);
        return data && data.Heavy;
    }

    static float HealthDamage(string ammo)
    {
        HCMeleeAmmoData data = HCMeleeAmmo.HCData(ammo);
        if (!data) { return 0; }
        return data.Health;
    }
}

// Native scripts-1.30.164289, relative paths:
// 3_Game/Entities/EntityAI.c:882 GetHierarchyRootPlayer;
// 3_Game/Entities/Man.c:83 GetEntityInHands; InventoryItem.c:24 GetMeleeCombatData;
// 3_Game/dayzplayer.c:1288 GetMeleeCombatData; gameplay.c:162,168
// GetModesCount/GetModeRange; 4_World/Entities/DayZPlayerImplement.c:247
// GetMeleeCombat; DayZPlayerImplementMeleeCombat.c:141,187 GetHitType/GetWeaponMode.
// 3_Game/Entities/Object.c:287,467,873,1159 GetPosition/GetType/ModelToWorld/GetDamageZonePos;
// 1_Core/proto/EnConvert.c:210 vector.DistanceSq.
// GetDamageZonePos returns WORLD space: native melee compares it directly to
// GetBonePositionWS at DayZPlayerImplementMeleeCombat.c:338,359; FlashGrenade.c
// (4_World/Entities/Grenade_Base):13,28 compares it to the explosion world position.
class HCMeleeTarget
{
    // Fixed installed type/mode domain, no entity or caller-supplied keys.
    protected static ref map<string, float> s_Ranges = new map<string, float>;
    protected static ref map<string, float> s_HeadArmour = new map<string, float>;

    static PlayerBase Attacker(EntityAI source)
    {
        if (!source) { return null; }
        PlayerBase player = PlayerBase.Cast(source);
        if (player) { return player; }
        return PlayerBase.Cast(source.GetHierarchyRootPlayer());
    }

    protected static float HCRange(PlayerBase attacker)
    {
        InventoryItem weapon = InventoryItem.Cast(attacker.GetEntityInHands());
        string type = attacker.GetType();
        MeleeCombatData data = attacker.GetMeleeCombatData();
        int mode;
        DayZPlayerImplementMeleeCombat combat = attacker.GetMeleeCombat();
        if (!combat) { return 0; }
        mode = combat.GetWeaponMode();
        if (weapon)
        {
            type = weapon.GetType();
            data = weapon.GetMeleeCombatData();
        }
        if (!data || mode < 0 || mode >= data.GetModesCount()) { return 0; }
        string key = type + ":" + mode.ToString();
        float range;
        if (!s_Ranges.Find(key, range))
        {
            range = data.GetModeRange(mode);
            s_Ranges.Set(key, range);
        }
        return range;
    }

    static bool Plausible(PlayerBase attacker, ZombieBase z, string zone, vector modelPos)
    {
        if (!attacker || !z || zone == "") { return false; }
        DayZPlayerImplementMeleeCombat combat = attacker.GetMeleeCombat();
        if (!combat) { return false; }
        bool sprint = combat.GetHitType() == EMeleeHitType.SPRINT;
        float range = HCMeleeTarget.HCRange(attacker);
        if (range <= 0) { return false; }
        float extender = 0.65;
        if (sprint) { extender = 1.35; }
        HCMeleeSettings settings = HCMeleeConfig.HCGet();
        float limit = range + extender + settings.PlausibilityTolerance;
        // Written as <= then negated so invalid/non-finite positions fail closed.
        if (!(vector.DistanceSq(attacker.GetPosition(), z.GetPosition()) <= limit * limit)) { return false; }
        vector hitWorld = z.ModelToWorld(modelPos);
        vector zoneWorld = z.GetDamageZonePos(zone);
        return vector.DistanceSq(hitWorld, zoneWorld) <= settings.ZoneTolerance * settings.ZoneTolerance;
    }

    static float HeadArmour(ZombieBase z)
    {
        if (!z) { return 1; }
        string type = z.GetType();
        float coefficient;
        if (s_HeadArmour.Find(type, coefficient)) { return coefficient; }
        string path = "CfgVehicles " + type + " DamageSystem DamageZones Head ArmorType Melee Health damage";
        coefficient = 1;
        if (GetGame().ConfigIsExisting(path)) { coefficient = GetGame().ConfigGetFloat(path); }
        s_HeadArmour.Set(type, coefficient);
        return coefficient;
    }
}
