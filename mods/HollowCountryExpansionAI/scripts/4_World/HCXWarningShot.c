// Original HC adapter. No Expansion implementation copied.
// Native scripts-1.30.164289, 4_World/Entities/Core/Inherited/Weapon.c:
// :35 GetCurrentMuzzle; :57 CanFire(int); :58 Fire(int, pos, dir, speed);
// :150 GetChamberAmmoTypeName; :74 IsChamberEmpty; :79 IsChamberFiredOut; :11 Synchronize.
// 4_World/Entities/Firearms/Weapon_Base.c:667 RandomizeFSMState rebuilds
// state from actual chambers/magazine, including fired-out state (:693-699).
// 3_Game/Global/Game.c:1176 SurfaceY; Global/DayZPhysics.c:199 RaycastRV;
// 3_Game/Entities/Object.c:287 GetPosition; 1_Core/proto/EnConvert.c:
// :153 Normalize, :156 Normalized, :233 Direction.
// Installed ai_scripts.pbo/4_World/DayZExpansion_AI/Entities/Weapons/Firearms/
// Weapon_Base.c:60 eAI_Fire, :157 delegates to native Fire with explicit vectors.
// eAIBase.c:1189 eAI_FireWeaponOnClient requests native client shot presentation.
// This path deliberately bypasses that provider's player-target ballistics.
class HCXWarningShot
{
    static bool Fire(eAIBase actor, PlayerBase player, Weapon_Base weapon)
    {
        vector origin = actor.GetPosition() + Vector(0, 1.6, 0);
        vector approach = player.GetPosition() - origin;
        approach[1] = 0;
        approach.Normalize();
        vector side = Vector(-approach[2], 0, approach[0]);
        vector point = player.GetPosition() + side * 12;
        point[1] = GetGame().SurfaceY(point[0], point[2]);
        // Downhill/steep-uphill/building contacts refuse rather than firing over
        // terrain or through an object. No alternate-side search or retry loop.
        if (origin[1] - point[1] < 1 || origin[1] - point[1] > 8)
        {
            Print("[HollowCountry] Stance warning_shot fallback=unsafe_terrain");
            return false;
        }
        vector hit;
        vector normal;
        int component;
        set<Object> objects = new set<Object>();
        bool blocked = DayZPhysics.RaycastRV(origin, point + Vector(0, -0.25, 0), hit, normal, component, objects, null, actor);
        if (!blocked || objects.Count() > 0 || vector.Distance(hit, point) > 1)
        {
            Print("[HollowCountry] Stance warning_shot fallback=obstructed");
            return false;
        }
        int muzzle = weapon.GetCurrentMuzzle();
        if (!weapon.CanFire(muzzle) || weapon.IsChamberEmpty(muzzle) || weapon.IsChamberFiredOut(muzzle)) { return false; }
        // Refuse explosive/projectile launchers rather than trusting a miss
        // offset to protect the player from splash damage. Native Game.c:524
        // ConfigGetFloat; EnString.c:240 IndexOf. Ordinary bullets only.
        string ammo = weapon.GetChamberAmmoTypeName(muzzle);
        string configPath = "CfgAmmo " + ammo;
        if (ammo.IndexOf("Bullet_") != 0 || GetGame().ConfigGetFloat(configPath + " indirectHit") > 0 || GetGame().ConfigGetFloat(configPath + " indirectHitRange") > 0)
        {
            Print("[HollowCountry] Stance warning_shot fallback=unsafe_ammunition");
            return false;
        }
        vector direction = vector.Direction(origin, point).Normalized();
        // Start the round clear of the shooter's own body.
        origin = origin + direction * 0.6;
        // One native discharge consumes the existing chambered cartridge. Never
        // spawn, remove, replenish or copy ammunition. No queued burst/auto fire.
        bool fired = weapon.Fire(muzzle, origin, direction, direction);
        if (fired)
        {
            // Use the observed provider presentation RPC; authority for the round
            // and its trajectory remains this server's native Fire call.
            // Shot id 0: the provider packs muzzle and shot id into one int and its
            // client id check is disabled, so a large id would only corrupt the muzzle.
            actor.eAI_FireWeaponOnClient(muzzle, 0);
            weapon.RandomizeFSMState();
            weapon.Synchronize();
            Print("[HollowCountry] Stance warning_shot fired offset=12m runtime=PENDING");
            HCReached.Mark("ai.warning_shot");
        }
        else { Print("[HollowCountry] Stance warning_shot fallback=native_fire_refused"); }
        return fired;
    }
}
