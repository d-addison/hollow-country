// Pure HC site decisions (no engine calls): policy and site validation, spawn
// budget and distance, despawn, holdout cache lifecycle and route legs. Each
// returns the first unmet requirement, or "" when it is met.
class HCXAISiteRules
{
    static bool Among(string value, string list)
    {
        if (value == "") { return false; }
        return list.Contains("|" + value + "|");
    }
    static bool LocalPointValid(vector point)
    {
        if (!HCXAIRules.PositionValid(point, 64)) { return false; }
        return Math.AbsFloat(point[0]) <= 30 && Math.AbsFloat(point[1]) <= 12 && Math.AbsFloat(point[2]) <= 30;
    }
    static string PolicyProblem(HCXAISitePolicy p)
    {
        if (!p) { return "missing policy"; }
        if (p.SchemaVersion != 1) { return "SchemaVersion must be 1"; }
        if (!HCXAIRules.Token(p.WorldName) || !HCXAIRules.Token(p.BuildVersion)) { return "WorldName and BuildVersion are required"; }
        if (p.ObserverPolicy != "native-eai") { return "observer policy must be native-eai (native eAI perception only)"; }
        if (p.MaxActiveAI < 1 || p.MaxActiveAI > 24) { return "MaxActiveAI must be 1..24"; }
        if (p.MaxActiveSites < 1 || p.MaxActiveSites > 8) { return "MaxActiveSites must be 1..8"; }
        if (!HCXAIRules.Finite(p.MinPlayerDistance) || p.MinPlayerDistance < 200 || p.MinPlayerDistance > 500) { return "MinPlayerDistance must be 200..500"; }
        if (!HCXAIRules.Finite(p.LineOfSightRange) || p.LineOfSightRange < 200 || p.LineOfSightRange > 1500) { return "LineOfSightRange must be 200..1500"; }
        if (!HCXAIRules.Finite(p.MaxLegLength) || p.MaxLegLength < 50 || p.MaxLegLength > 600) { return "MaxLegLength must be 50..600"; }
        if (!HCXAIRules.Finite(p.CacheClearRadius) || p.CacheClearRadius < 100 || p.CacheClearRadius > 1000) { return "CacheClearRadius must be 100..1000"; }
        if (!p.Sites || p.Sites.Count() < 1 || p.Sites.Count() > 64) { return "1..64 sites are required"; }
        int index = 0;
        while (index < p.Sites.Count())
        {
            HCXAISite site = p.Sites[index];
            string problem = HCXAISiteRules.SiteProblem(p, site);
            if (problem != "") { return "site " + index.ToString() + ": " + problem; }
            int other = 0;
            while (other < index)
            {
                if (p.Sites[other].Id == site.Id) { return "duplicate site id " + site.Id; }
                other++;
            }
            index++;
        }
        return "";
    }
    static string SiteProblem(HCXAISitePolicy p, HCXAISite s)
    {
        if (!s) { return "missing site"; }
        if (!HCXAIRules.Token(s.Id) || s.Id.Length() > 48) { return "site id must be 1..48 characters"; }
        if (!HCXAISiteRules.Among(s.Kind, "|patrol|scavenger|holdout|")) { return "unknown kind " + s.Kind; }
        string factions = "|Guards|East|West|";
        if (s.Kind == "scavenger") { factions = "|Raiders|"; }
        if (s.Kind == "holdout") { factions = "|Guards|"; }
        if (!HCXAISiteRules.Among(s.Faction, factions)) { return "faction " + s.Faction + " not allowed for " + s.Kind; }
        if (!HCXAIRules.Token(s.Loadout) || s.Loadout.Length() < 15 || s.Loadout.Substring(0, 14) != "HollowCountry_") { return "loadout must be one of our HollowCountry_* files"; }
        int most = 3;
        if (s.Kind == "patrol") { most = 4; }
        if (s.NumberOfAI < 2 || s.NumberOfAIMax < s.NumberOfAI || s.NumberOfAIMax > most) { return "group size must be 2.." + most.ToString(); }
        if (!HCXAISiteRules.Among(s.Behaviour, "|LOOP|ALTERNATE|")) { return "Behaviour must be LOOP or ALTERNATE"; }
        if (!HCXAISiteRules.Among(s.Speed, "|WALK|JOG|")) { return "Speed must be WALK or JOG"; }
        if (!HCXAIRules.Finite(s.ActivationRadius) || s.ActivationRadius < p.MinPlayerDistance + 50 || s.ActivationRadius > 1200) { return "ActivationRadius must be MinPlayerDistance + 50 .. 1200"; }
        if (s.DespawnSeconds < 60 || s.DespawnSeconds > 3600) { return "DespawnSeconds must be 60..3600"; }
        if (s.RespawnSeconds < 600 || s.RespawnSeconds > 86400) { return "RespawnSeconds must be 600..86400"; }
        if (s.Kind == "holdout") { return HCXAISiteRules.HoldoutProblem(s); }
        if (s.HouseClass != "" || s.CacheClass != "" || s.CacheLoot.Count() > 0 || s.LocalPoints.Count() > 0) { return "only holdouts own a house or a cache"; }
        if (!s.Waypoints || s.Waypoints.Count() < 2 || s.Waypoints.Count() > 8) { return "2..8 waypoints are required"; }
        int index = 0;
        while (index < s.Waypoints.Count())
        {
            vector point = s.Waypoints[index];
            if (!HCXAIRules.PositionValid(point, 16000) || point[0] < 0 || point[2] < 0) { return "waypoint " + index.ToString() + " is outside the world"; }
            if (index > 0)
            {
                vector previous = s.Waypoints[index - 1];
                float leg = vector.Distance(previous, point);
                if (leg < 5 || leg > p.MaxLegLength) { return "leg " + index.ToString() + " must be 5 m .. MaxLegLength"; }
            }
            index++;
        }
        if (s.Behaviour == "LOOP")
        {
            float closing = vector.Distance(s.Waypoints[0], s.Waypoints[s.Waypoints.Count() - 1]);
            if (closing > p.MaxLegLength) { return "closing leg of a LOOP exceeds MaxLegLength"; }
        }
        return "";
    }
    static string HoldoutProblem(HCXAISite s)
    {
        if (!HCXAIRules.Token(s.HouseClass) || s.HouseClass.Length() < 6 || s.HouseClass.Substring(0, 5) != "Land_") { return "holdout needs a vanilla Land_ house class"; }
        if (!HCXAIRules.PositionValid(s.HousePosition, 16000)) { return "house position is outside the world"; }
        if (s.Waypoints.Count() > 0) { return "holdout points are house-local LocalPoints, not Waypoints"; }
        if (!s.LocalPoints || s.LocalPoints.Count() < 2 || s.LocalPoints.Count() > 6) { return "2..6 house-local points are required"; }
        foreach (vector point : s.LocalPoints)
        {
            if (!HCXAISiteRules.LocalPointValid(point)) { return "house-local point is outside the house bounds"; }
        }
        if (!HCXAISiteRules.Among(s.CacheClass, "|WoodenCrate|SeaChest|")) { return "cache class must be WoodenCrate or SeaChest"; }
        if (!HCXAISiteRules.LocalPointValid(s.CacheLocal)) { return "cache position is outside the house bounds"; }
        if (!s.CacheLoot || s.CacheLoot.Count() < 1 || s.CacheLoot.Count() > 8) { return "cache loot table must hold 1..8 entries"; }
        foreach (HCXAISiteLoot loot : s.CacheLoot)
        {
            if (!loot || !HCXAIRules.Token(loot.ClassName) || loot.Quantity < 1 || loot.Quantity > 4) { return "cache loot entries need a class and a quantity 1..4"; }
        }
        if (s.CacheCooldownSeconds < 3600 || s.CacheCooldownSeconds > 604800) { return "cache cooldown must be 3600..604800 s"; }
        return "";
    }
    // activeSites/activeAI count the other HC sites with live groups; groupMax is
    // this site's largest group; nearest is the closest identity player.
    static string SpawnProblem(HCXAISitePolicy p, int activeAI, int activeSites, int groupMax, float nearest, bool seen)
    {
        if (activeSites >= p.MaxActiveSites) { return "site budget reached"; }
        if (activeAI + groupMax > p.MaxActiveAI) { return "AI budget reached"; }
        if (nearest < p.MinPlayerDistance) { return "player within MinPlayerDistance"; }
        if (seen) { return "spawn point in a player's line of sight"; }
        return "";
    }
    // Members 2..N spawn later at formation offsets; each must pass the anchor's
    // distance and sight rules at its own point (the budget was taken for the group).
    static string MemberSpawnProblem(HCXAISitePolicy p, float nearest, bool seen)
    {
        if (nearest < p.MinPlayerDistance) { return "player within MinPlayerDistance"; }
        if (seen) { return "spawn point in a player's line of sight"; }
        return "";
    }
    static bool DespawnAllowed(bool inCombat, bool forced)
    {
        return forced || !inCombat;
    }
    // seed | wait | adopt | mark-looted | none | refill | refuse
    static string CacheAction(HCXAICacheRow row, bool present, int items, int now, bool playerNear)
    {
        if (!row)
        {
            if (playerNear) { return "wait"; }
            return "seed";
        }
        if (row.State == "seeding")
        {
            if (present) { return "adopt"; }
            return "mark-looted";
        }
        if (row.State == "seeded")
        {
            if (present && items > 0) { return "none"; }
            return "mark-looted";
        }
        if (row.State == "looted")
        {
            if (now < row.NextRefillAt || playerNear) { return "wait"; }
            return "refill";
        }
        return "refuse";
    }
    static int RefillAt(int lootedAt, int cooldown)
    {
        return lootedAt + cooldown;
    }
    static string LegProblem(bool startSampled, bool endSampled, int points, float endGap, float pathLength, float straight)
    {
        if (!startSampled || !endSampled) { return "navmesh sample failed"; }
        if (points < 2) { return "no path"; }
        if (endGap > 2.5) { return "path ends short of the waypoint"; }
        if (pathLength > straight * 3 + 50) { return "detour too long"; }
        return "";
    }
    static string PointText(vector point)
    {
        float x = point[0];
        float y = point[1];
        float z = point[2];
        return "|" + x.ToString() + "," + y.ToString() + "," + z.ToString();
    }
    // Everything the qualified route depends on: outdoor waypoints, or for a
    // holdout the house class, its position, the house-local points and cache.
    static string RouteText(HCXAISite site, string build)
    {
        string text = build + "|" + site.Id + "|" + site.Kind + "|" + site.Behaviour;
        foreach (vector point : site.Waypoints)
        {
            text = text + HCXAISiteRules.PointText(point);
        }
        if (site.Kind != "holdout") { return text; }
        text = text + "|" + site.HouseClass + HCXAISiteRules.PointText(site.HousePosition);
        foreach (vector inner : site.LocalPoints)
        {
            text = text + HCXAISiteRules.PointText(inner);
        }
        return text + "|" + site.CacheClass + HCXAISiteRules.PointText(site.CacheLocal);
    }
    static string AdmissionProblem(HCXAISitePolicy p, HCXAISiteAdmission a)
    {
        if (!a) { return "no admission observation"; }
        if (a.BuildVersion != p.BuildVersion) { return "engine build " + a.BuildVersion + " is not the qualified " + p.BuildVersion; }
        if (a.WorldName != p.WorldName) { return "world " + a.WorldName + " is not " + p.WorldName; }
        if (a.MissingAddons != "") { return "missing CfgPatches " + a.MissingAddons; }
        if (!a.SettingsLoaded) { return "Expansion AI settings not loaded"; }
        if (a.Globals != "") { return "Expansion AI globals unfair (no recruiting, no unlimited reload, multipliers 1): " + a.Globals; }
        if (a.UnfairFaction != "") { return "faction " + a.UnfairFaction + " is invincible, observer, passive or has unlimited stamina"; }
        if (a.MissingLoadout != "") { return "loadout file missing: $profile:ExpansionMod/Loadouts/" + a.MissingLoadout + ".json"; }
        if (a.ObserverPolicy != "native-eai" || a.ObserverPolicy != p.ObserverPolicy) { return "observer policy must be native-eai"; }
        if (!a.Marker) { return "pve_patrols opt-in marker missing (HollowCountry/acceptance/pve_patrols.enable in the profile)"; }
        if (!a.OwnershipReconciled) { return "ownership journal not reconciled"; }
        return "";
    }
}
