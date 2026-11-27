// Setup fixture: only the isolated soak profile writes this marker. Fresh characters only;
// persistence logins use the separate ready path. Native missionServer.c:549 exact signature;
// :573/:589 pass pos to CreateCharacter before equipment. Hook before stock CustomMission,
// which overrides CreateCharacter without super, so a base CreateCharacter hook is bypassed.
#ifdef SERVER
modded class MissionServer
{
    // Native Global/Game.c:1196-1197 sea/pond; :1176 SurfaceY.
    // Global/DayZPhysics.c:199 RaycastRV includes ignore and geometry intersection type.
    // There is no character yet, so null ignore excludes no entity: the future player cannot hit.
    protected string HCInitialSpawnFailure(vector point)
    {
        if (GetGame().SurfaceIsSea(point[0], point[2]) || GetGame().SurfaceIsPond(point[0], point[2])) { return "water"; }
        ref array<vector> offsets = {"0 0 4", "4 0 0", "0 0 -4", "-4 0 0"};
        float low = point[1];
        float high = point[1];
        foreach (vector offset : offsets)
        {
            float height = GetGame().SurfaceY(point[0] + offset[0], point[2] + offset[2]);
            if (height < low) { low = height; }
            if (height > high) { high = height; }
        }
        if (high - low > 2.0) { return "slope"; }
        ref array<vector> bearings = {"0 0 16", "16 0 0", "0 0 -16", "-16 0 0"};
        vector chest = point + Vector(0, 1.2, 0);
        foreach (vector bearing : bearings)
        {
            vector finish = chest + bearing;
            // Match client calibration's terrain-following chest-height ray.
            finish[1] = GetGame().SurfaceY(finish[0], finish[2]) + 1.2;
            vector contact;
            vector normal;
            int component;
            if (DayZPhysics.RaycastRV(chest, finish, contact, normal, component, null, null, null, false, false, ObjIntersectGeom)) { return "blocked"; }
        }
        return "none";
    }

    protected vector HCInitialSpawnPosition()
    {
        // Fixed west/northwest field shortlist, nearest bands first. Runtime checks, not a
        // surveyed guarantee; all within 1.5 km of the old central-Chernogorsk fixture.
        ref array<vector> candidates = {
            "5500 0 2800", "5400 0 2800", "5300 0 2800", "5200 0 2800",
            "5500 0 3000", "5400 0 3000", "5300 0 3000", "5200 0 3000",
            "5500 0 3200", "5400 0 3200", "5300 0 3200", "5200 0 3200"
        };
        string firstFailure = "none";
        int checked = 0;
        foreach (vector candidate : candidates)
        {
            checked++;
            candidate[1] = GetGame().SurfaceY(candidate[0], candidate[2]);
            string failure = HCInitialSpawnFailure(candidate);
            if (failure == "none")
            {
                Print("[HC Driver] spawn fixture=1 initial=1 at=<" + candidate[0].ToString() + "," + candidate[2].ToString() + "> candidate=" + checked.ToString() + " checked=" + checked.ToString());
                return candidate;
            }
            if (firstFailure == "none") { firstFailure = failure; }
        }
        Print("[HC Driver] spawn fixture=1 initial=1 at=<6500,2500> candidate=fallback reason=" + firstFailure + " checked=" + checked.ToString());
        return Vector(6500, GetGame().SurfaceY(6500, 2500), 2500);
    }

    override PlayerBase OnClientNewEvent(PlayerIdentity identity, vector pos, ParamsReadContext ctx)
    {
        if (FileExist("$profile:HollowCountry/autoplayer-initial-spawn"))
        {
            pos = HCInitialSpawnPosition();
        }
        // No heading write: native missionServer.c:499-502 and Game.c:332 expose no yaw
        // argument at creation; Object.c:311 would instead mutate an existing entity.
        return super.OnClientNewEvent(identity, pos, ctx);
    }
}
#endif
