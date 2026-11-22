// Hard wall veto for melee hits on infected and AI (Neon P2.4, owner decision Q2).
// Native scripts-1.30.164289 (relative paths):
// 3_Game/Entities/Object.c:1144 EEOnDamageCalculated (false = damage not applied),
// :238 GetBonePositionWS, :1159 GetDamageZonePos (world space);
// 3_Game/human.c:1417 GetBoneIndexByName; 3_Game/Global/DayZPhysics.c:211 RayCastBullet;
// 3_Game/Entities/Building.c:28-34,82 GetDoorIndex/IsDoorOpen/GetNearestDoorBySoundPos;
// 4_World/Entities/ManBase.c:10 IsControlledPlayer; 3_Game/Global/Game.c:1535 GetTime.
// The ray is the one vanilla client targeting already uses (MeleeTargeting.c:74,272-288),
// restricted to walls, doors and fences so terrain slopes never veto a crawler hit.
// Rules: only hits whose victim is an infected or an AI character are vetoed, never a
// real player; one trace per attack (cached for the same attacker/victim/zone); a hit
// that clips the attacker's or the victim's own doorway is allowed; a door that is open
// near the contact point is allowed. Infected attackers have no bone API, so only
// PlayerBase attackers (players and AI) are traced.
class HCMeleeWall
{
    // Doorway-threshold tolerances: contact this close to either end of the segment is
    // the jamb or frame the attacker or victim is standing in, not a wall between them.
    static const float START_TOLERANCE = 0.25;
    static const float END_TOLERANCE = 0.4;
    // A door's sound position is near its leaf; contact within this range of it is the door.
    static const float DOOR_RADIUS_SQ = 4.0;
    // One swing produces both the damage-calculated and the hit event within a frame.
    static const int CACHE_MS = 150;

    protected static Object s_Attacker;
    protected static Object s_Target;
    protected static string s_Zone;
    protected static int s_At;
    protected static bool s_Blocked;
    protected static int s_Checks;
    protected static int s_Vetoed;
    protected static int s_DoorPass;
    protected static int s_EdgePass;

    static void Reset()
    {
        s_Attacker = null;
        s_Target = null;
        s_Zone = "";
        s_At = 0;
        s_Blocked = false;
        s_Checks = 0;
        s_Vetoed = 0;
        s_DoorPass = 0;
        s_EdgePass = 0;
    }

    protected static int Increment(int count)
    {
        if (count < 2147483647) { count++; }
        return count;
    }

    // Real players are never vetoed as victims: a controlled or identified character.
    static bool RealPlayer(PlayerBase player)
    {
        if (!player) { return false; }
        return player.GetIdentity() != null || player.IsControlledPlayer();
    }

    // True when a close-combat hit by attacker on victim must be refused. Safe to call
    // from any EEOnDamageCalculated; it filters by itself.
    static bool Vetoes(Object victim, int damageType, EntityAI source, string zone, string ammo)
    {
        if (!victim || zone == "" || damageType != DT_CLOSE_COMBAT) { return false; }
        if (!GetGame().IsServer() || !HCMeleeModule.Active()) { return false; }
        if (HCMeleeAmmo.IsHC(ammo)) { return false; }
        if (!HCMeleeConfig.HCGet().WallVeto) { return false; }
        PlayerBase victimPlayer = PlayerBase.Cast(victim);
        if (victimPlayer && HCMeleeWall.RealPlayer(victimPlayer)) { return false; }
        PlayerBase attacker = HCMeleeTarget.Attacker(source);
        if (!attacker || attacker == victim) { return false; }
        if (!HCMeleeWall.Blocked(attacker, victim, zone)) { return false; }
        s_Vetoed = Increment(s_Vetoed);
        HCModuleReadiness.HCUse("Melee", "wall_veto");
        if (s_Vetoed <= HCMeleeConfig.HCGet().LogLimit)
        {
            string who = "ai";
            if (HCMeleeWall.RealPlayer(attacker)) { who = "player"; }
            Print("[HC Melee] wall_veto count=" + s_Vetoed.ToString() + " zone=" + zone + " attacker=" + who);
        }
        return true;
    }

    // True when the attacker head to the victim's damage-zone line crosses a wall or closed
    // door. At most one trace per attack: the verdict is cached for the same triple.
    static bool Blocked(PlayerBase attacker, Object victim, string zone)
    {
        if (!attacker || !victim || zone == "") { return false; }
        int now = GetGame().GetTime();
        int age = now - s_At;
        if (s_Attacker == attacker && s_Target == victim && s_Zone == zone && age >= 0 && age <= CACHE_MS) { return s_Blocked; }
        bool blocked = HCMeleeWall.Trace(attacker, victim, zone);
        s_Attacker = attacker;
        s_Target = victim;
        s_Zone = zone;
        s_At = now;
        s_Blocked = blocked;
        return blocked;
    }

    protected static bool Trace(PlayerBase attacker, Object victim, string zone)
    {
        int headBone = attacker.GetBoneIndexByName("Head");
        if (headBone < 0) { return false; }
        vector head = attacker.GetBonePositionWS(headBone);
        vector zonePos = victim.GetDamageZonePos(zone);
        float segmentSq = vector.DistanceSq(head, zonePos);
        // Fail open on degenerate or non-finite probes and never trace an unbounded segment.
        if (!(segmentSq > 0) || !(segmentSq <= 10000)) { return false; }
        s_Checks = Increment(s_Checks);
        Object hitObject;
        vector hitPosition, hitNormal;
        float hitFraction;
        PhxInteractionLayers layers = PhxInteractionLayers.BUILDING | PhxInteractionLayers.DOOR | PhxInteractionLayers.FENCE;
        if (!DayZPhysics.RayCastBullet(head, zonePos, layers, attacker, hitObject, hitPosition, hitNormal, hitFraction)) { return false; }
        float segment = Math.Sqrt(segmentSq);
        float contact = vector.Distance(head, hitPosition);
        if (contact <= START_TOLERANCE || segment - contact <= END_TOLERANCE)
        {
            s_EdgePass = Increment(s_EdgePass);
            return false;
        }
        Building building = Building.Cast(hitObject);
        if (building && HCMeleeWall.DoorOpenAt(building, hitPosition))
        {
            s_DoorPass = Increment(s_DoorPass);
            return false;
        }
        return true;
    }

    // An open door near the contact point: the line passes the threshold, not a wall.
    protected static bool DoorOpenAt(Building building, vector position)
    {
        int index = building.GetNearestDoorBySoundPos(position);
        if (index < 0) { return false; }
        if (vector.DistanceSq(building.GetDoorSoundPos(index), position) > DOOR_RADIUS_SQ) { return false; }
        return building.IsDoorOpen(index) || building.IsDoorOpened(index);
    }

    static void Summary()
    {
        string line = "[HC Melee] wall_veto checks=" + s_Checks.ToString() + " vetoed=" + s_Vetoed.ToString();
        line += " door_open_pass=" + s_DoorPass.ToString() + " edge_pass=" + s_EdgePass.ToString();
        Print(line + " runtime=PENDING");
    }
}

// AI victims (identity-less characters) are protected by the same veto; real players never.
modded class PlayerBase
{
    override bool EEOnDamageCalculated(TotalDamageResult damageResult, int damageType, EntityAI source, int component, string dmgZone, string ammo, vector modelPos, float speedCoef)
    {
        bool allowed = super.EEOnDamageCalculated(damageResult, damageType, source, component, dmgZone, ammo, modelPos, speedCoef);
        if (!allowed) { return false; }
        if (HCMeleeWall.Vetoes(this, damageType, source, dmgZone, ammo)) { return false; }
        return true;
    }
}
