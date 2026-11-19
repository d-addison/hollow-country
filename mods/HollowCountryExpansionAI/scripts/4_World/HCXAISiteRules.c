// Pure HC site decisions (no engine calls): policy and site validation, spawn
// budget and distance, despawn, holdout cache lifecycle and route legs. Each
// returns the first unmet requirement, or "" when it is met.
// W5 #125: constant work, no allocations. Native scripts-1.30.164289/
// 1_Core/proto/EnMath.c:413 Math.Round(float). Limits remain in director ledger.
class HCXAISiteRules
{
    // Catalog cardinality is independent of native actor/group budgets. Files
    // also have a bounded byte read; excess input is refused, never truncated.
    static int HCMaxCatalogRows() { return 1024; }
    static int HCDefaultAttemptsPerTick() { return 1; }
    static int HCDefaultSelectionIntervalSeconds() { return 30; }
    static int HCDefaultOpportunitySeconds() { return 3600; }
    static int HCDefaultRetrySeconds() { return 300; }
    static int HCPageSize(HCXAILocalityCatalog catalog, int cap)
    {
        // Legacy PageSize is retained as a readable field, but cannot shrink
        // coverage below the live shared cap. Rotation supplies fairness only.
        return cap;
    }
    static int HCAttemptsPerTick(HCXAILocalityCatalog catalog)
    {
        if (catalog.AttemptsPerTick == 0) { return HCXAISiteRules.HCDefaultAttemptsPerTick(); }
        return catalog.AttemptsPerTick;
    }
    static int HCOpportunitySeconds(HCXAILocalityCatalog catalog)
    {
        if (catalog.OpportunitySeconds == 0) { return HCXAISiteRules.HCDefaultOpportunitySeconds(); }
        return catalog.OpportunitySeconds;
    }
    static int HCSelectionIntervalSeconds(HCXAILocalityCatalog catalog)
    {
        if (catalog.SelectionIntervalSeconds == 0) { return HCXAISiteRules.HCDefaultSelectionIntervalSeconds(); }
        return catalog.SelectionIntervalSeconds;
    }
    static int HCRetrySeconds(HCXAILocalityCatalog catalog)
    {
        if (catalog.RetrySeconds == 0) { return HCXAISiteRules.HCDefaultRetrySeconds(); }
        return catalog.RetrySeconds;
    }
    static HCXAILocalityCoverage HCCoverage(HCXAILocalityRotation rotation, string id)
    {
        foreach (HCXAILocalityCoverage row : rotation.Rows)
        {
            if (row.LocalityId == id) { return row; }
        }
        return null;
    }
    // One cursor step, bounded by HCMaxCatalogRows. Persist NextId BEFORE geometry or
    // provider work. A refused row stays pending but cannot pin the cursor.
    static int HCNextLocality(HCXAILocalityCatalog catalog, HCXAILocalityRotation rotation)
    {
        int index = 0;
        int found = 0;
        while (index < catalog.Localities.Count())
        {
            if (catalog.Localities[index].Id == rotation.NextId) { found = index; break; }
            index++;
        }
        int next = (found + 1) % catalog.Localities.Count();
        rotation.NextId = catalog.Localities[next].Id;
        return found;
    }
    static string HCOldestPending(HCXAILocalityRotation rotation)
    {
        string oldest;
        int pendingSince = 2147483647;
        foreach (HCXAILocalityCoverage row : rotation.Rows)
        {
            if (row.Pending && row.PendingSinceSerial < pendingSince)
            {
                oldest = row.LocalityId;
                pendingSince = row.PendingSinceSerial;
            }
        }
        return oldest;
    }
    static string HCLocalityProblem(HCXAILocalityCatalog catalog, HCXAISitePolicy policy)
    {
        if (!catalog || catalog.SchemaVersion != 1 || catalog.WorldName != policy.WorldName) { return "catalog_schema_or_world"; }
        if (!catalog.Localities || catalog.Localities.Count() < 1 || catalog.Localities.Count() > HCXAISiteRules.HCMaxCatalogRows()) { return "catalog_row_budget"; }
        if (catalog.PageSize < 0 || catalog.PageSize > 64 || catalog.AttemptsPerTick < 0 || catalog.AttemptsPerTick > 4) { return "catalog_work_budget"; }
        if (catalog.SelectionIntervalSeconds < 0 || catalog.SelectionIntervalSeconds > 3600 || catalog.OpportunitySeconds < 0 || catalog.OpportunitySeconds > 86400 || catalog.RetrySeconds < 0 || catalog.RetrySeconds > 86400) { return "catalog_time_budget"; }
        array<string> ids = new array<string>();
        array<string> sites = new array<string>();
        foreach (HCXAILocality locality : catalog.Localities)
        {
            if (!locality || !HCXAIRules.Token(locality.Id) || locality.Id.Length() > 48 || ids.Find(locality.Id) >= 0) { return "catalog_locality_id"; }
            ids.Insert(locality.Id);
            if (!locality.SiteIds || locality.SiteIds.Count() > 8) { return "catalog_site_budget"; }
            foreach (string siteId : locality.SiteIds)
            {
                if (sites.Find(siteId) >= 0) { return "catalog_duplicate_site"; }
                sites.Insert(siteId);
            }
        }
        // Operator policy drift is reconciled by the director, never refused.
        return "";
    }
    // One operator-tuned group curve for infected and AI groups (Infected variety GroupScaling).
    static float HCGroupFactor(int players)
    {
        return HCInfectedVarietyPolicy.GroupScale(players);
    }
    static int HCGroupMembers(int authored, float factor)
    {
        int members = Math.Round(authored * factor);
        if (members < 1) { return 1; }
        if (members > HCAILimits.SIZE_CEILING) { return HCAILimits.SIZE_CEILING; }
        return members;
    }
    static bool Among(string value, string list)
    {
        if (value == "") { return false; }
        return list.Contains("|" + value + "|");
    }
    // Owner tuning: worse aim and less awareness than stock Expansion (ExpansionAISettings.Defaults:
    // accuracy 0.35..0.95, threat 1000 m, noise 500 m, flanking 200 m). Applied per site patrol on the
    // ExpansionAISpawnBase fields (ExpansionAIPatrolBase.c:35-39); a value <= 0 would fall back to the
    // global setting in eAIDynamicPatrol, so each is > 0. Feel in play is pending a client session.
    static float AccuracyMin(string kind)
    {
        if (kind == "scavenger") { return 0.10; }
        return 0.20;
    }
    static float AccuracyMax(string kind)
    {
        if (kind == "scavenger") { return 0.30; }
        return 0.45;
    }
    static float ThreatDistance(string kind)
    {
        if (kind == "scavenger") { return 200; }
        if (kind == "holdout") { return 250; }
        return 300;
    }
    static float NoiseDistance(string kind)
    {
        if (kind == "scavenger") { return 100; }
        if (kind == "holdout") { return 120; }
        return 150;
    }
    static float FlankDistance(string kind)
    {
        if (kind == "holdout") { return 20; }
        if (kind == "scavenger") { return 30; }
        return 50;
    }
    static bool LocalPointValid(vector point)
    {
        if (!HCXAIRules.PositionValid(point, 64)) { return false; }
        return Math.AbsFloat(point[0]) <= 30 && Math.AbsFloat(point[1]) <= 12 && Math.AbsFloat(point[2]) <= 30;
    }
    static bool HCRespawnTimerValid(int seconds)
    {
        return seconds == 0 || (seconds >= 60 && seconds <= 604800);
    }
    static string PolicyProblem(HCXAISitePolicy p)
    {
        if (!p) { return "missing policy"; }
        if (p.SchemaVersion != 1) { return "SchemaVersion must be 1"; }
        if (!HCXAIRules.Token(p.WorldName) || !HCXAIRules.Token(p.BuildVersion)) { return "WorldName and BuildVersion are required"; }
        if (p.ObserverPolicy != "native-eai") { return "observer policy must be native-eai (native eAI perception only)"; }
        if (p.MaxActiveAI < 1 || p.MaxActiveAI > HCAILimits.AI_CEILING) { return "MaxActiveAI must be within AI safety ceiling"; }
        if (p.MaxActiveSites < 1 || p.MaxActiveSites > HCAILimits.GROUP_CEILING) { return "MaxActiveSites must be within group safety ceiling"; }
        if (!HCXAIRules.Finite(p.MinPlayerDistance) || p.MinPlayerDistance < 200 || p.MinPlayerDistance >= HCPerceptionRing.HCSpawnMax()) { return "MinPlayerDistance must be at least 200 and below perception SpawnMax"; }
        if (!HCXAIRules.Finite(p.LineOfSightRange) || p.LineOfSightRange < 200 || p.LineOfSightRange > 1500) { return "LineOfSightRange must be 200..1500"; }
        if (!HCXAIRules.Finite(p.MaxLegLength) || p.MaxLegLength < 50 || p.MaxLegLength > 600) { return "MaxLegLength must be 50..600"; }
        if (!HCXAIRules.Finite(p.CacheClearRadius) || p.CacheClearRadius < 100 || p.CacheClearRadius > 1000) { return "CacheClearRadius must be 100..1000"; }
        if (!HCXAISiteRules.HCRespawnTimerValid(p.AIRespawnSeconds) || !HCXAISiteRules.HCRespawnTimerValid(p.PatrolRespawnSeconds) || !HCXAISiteRules.HCRespawnTimerValid(p.HoldoutRespawnSeconds)) { return "invalid respawn policy timer (0 or 60..604800)"; }
        if (!HCXAISiteRules.HCRespawnTimerValid(p.MilitaryRespawnSeconds) || !HCXAISiteRules.HCRespawnTimerValid(p.MemberReplaceSeconds)) { return "invalid replacement policy timer (0 or 60..604800)"; }
        if (p.RaidCooldownFloorSeconds != 0 && (p.RaidCooldownFloorSeconds < 1800 || p.RaidCooldownFloorSeconds > 604800)) { return "RaidCooldownFloorSeconds must be 0 or 1800..604800"; }
        if (!HCXAIRules.Finite(p.ActivationRadiusScale) || (p.ActivationRadiusScale != 0 && (p.ActivationRadiusScale < 0.5 || p.ActivationRadiusScale > 2.0))) { return "ActivationRadiusScale must be 0 or 0.5..2.0"; }
        if (!p.Sites || p.Sites.Count() < 1 || p.Sites.Count() > HCXAISiteRules.HCMaxCatalogRows()) { return "site catalog row budget exceeded"; }
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
        int most = HCAILimits.SIZE_CEILING;
        if (s.NumberOfAI < 1 || s.NumberOfAIMax < s.NumberOfAI || s.NumberOfAIMax > most) { return "group size must be 1.." + most.ToString(); }
        if (!HCXAISiteRules.Among(s.Behaviour, "|LOOP|ALTERNATE|")) { return "Behaviour must be LOOP or ALTERNATE"; }
        if (!HCXAISiteRules.Among(s.Speed, "|WALK|JOG|")) { return "Speed must be WALK or JOG"; }
        if (!HCXAIRules.Finite(s.ActivationRadius) || s.ActivationRadius <= 0 || s.ActivationRadius > HCPerceptionRing.HCCeiling()) { return "ActivationRadius must be positive and within perception ceiling (effective radius includes spawn ring)"; }
        if (s.DespawnSeconds < 60 || s.DespawnSeconds > 3600) { return "DespawnSeconds must be 60..3600"; }
        if (s.RespawnSeconds < 60 || s.RespawnSeconds > 604800) { return "RespawnSeconds must be 60..604800"; }
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
        if (activeSites >= HCAILimits.Get().MaxActiveSites) { return "site budget reached"; }
        if (activeAI + groupMax > HCAILimits.Get().MaxActiveAI) { return "AI budget reached"; }
        if (nearest < p.MinPlayerDistance || !HCPerceptionRing.HCOutside(nearest)) { return "player within perception spawn ring or MinPlayerDistance"; }
        if (seen) { return "spawn point in a player's line of sight"; }
        return "";
    }
    // Members 2..N spawn later at formation offsets; each must pass the anchor's
    // distance and sight rules at its own point (the budget was taken for the group).
    static string MemberSpawnProblem(HCXAISitePolicy p, float nearest, bool seen)
    {
        if (nearest < p.MinPlayerDistance || !HCPerceptionRing.HCOutside(nearest)) { return "player within perception spawn ring or MinPlayerDistance"; }
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
    // Snap only a valid, affordable returned path. The original 2.5 m gap
    // still accepts an unchanged target; wider tolerances use the reached end.
    // Holdouts retain one FindPath per attempt, never an outdoor chain.
    static string ChainAction(string kind, int steps, int points, float endGap, float advance, float totalLength, float straight)
    {
        if (points < 2) { return "no path"; }
        if (totalLength > straight * 3 + 50) { return "detour too long"; }
        if (endGap <= 2.5) { return ""; }
        float snapLimit = 4.0;
        if (kind == "holdout") { snapLimit = 3.5; }
        if (endGap <= snapLimit) { return "snap"; }
        if (kind == "holdout") { return "path ends short of the waypoint"; }
        if (advance < 0.5) { return "path chain stalled"; }
        if (steps >= 16) { return "path chain step limit"; }
        return "continue";
    }
    static int RouteMinimum(string kind)
    {
        if (kind == "holdout") { return 2; }
        return 3;
    }
    // Installed Expansion AIenums.c exposes ONCE; ExpansionAISpawnBase's
    // GetBehaviour resolves it directly. An open route must not return along
    // a closing leg (or reversed legs) that we never qualified.
    static string PatrolBehaviour(string authored, bool openRoute)
    {
        if (openRoute) { return "ONCE"; }
        return authored;
    }
    // A snapped or reached leg end is a new patrol point only when it lies more
    // than 0.5 m from the last kept point; a stall that never left that point
    // is a skip, not a duplicate waypoint.
    static bool SnapKeeps(vector lastKept, vector legEnd)
    {
        return vector.Distance(lastKept, legEnd) > 0.5;
    }
    // AI_ENCOUNTER: shortest distance from the event anchor to the patrol's
    // qualified points; 100000 when the route has none.
    static float RouteGap(array<vector> points, vector anchor)
    {
        float best = 100000;
        foreach (vector point : points)
        {
            float gap = vector.Distance(point, anchor);
            if (gap < best) { best = gap; }
        }
        return best;
    }
    // The patrol's native trigger radius (HCXAISites patrol config MaxDistRadius
    // for a reviewed, non-transient site): ActivationRadius, raised to 600 m.
    // Encounters bind against this same radius, never a wider one. Invalid
    // (non-positive) radii stay 0 so EncounterProblem refuses them.
    static float EncounterRadius(float activationRadius)
    {
        if (activationRadius <= 0) { return 0; }
        if (activationRadius < 600) { return 600; }
        return activationRadius;
    }
    // A player at the anchor must be inside the patrol's own ActivationRadius
    // of its route; the bound is the site's, never widened for the event.
    static string EncounterProblem(bool qualified, bool patrolled, bool bound, float gap, float activationRadius)
    {
        if (!qualified) { return "route not qualified"; }
        if (!patrolled) { return "no native patrol"; }
        if (bound) { return "site already bound to an open encounter"; }
        if (activationRadius <= 0 || gap > activationRadius) { return "route outside ActivationRadius"; }
        return "";
    }
    // Per-process encounter session: the ownership session (previous + 1,
    // persisted by orphan reconciliation) and the process start timestamp.
    static string EncounterToken(int ownedSession, int timestamp)
    {
        if (ownedSession < 1 || timestamp < 1) { return ""; }
        return "xai-" + ownedSession.ToString() + "-" + timestamp.ToString();
    }
    // The journal has no generated geometry or effective behaviour. Rebuild
    // every success, including holdouts, so snaps/skips survive no shortcut.
    static bool ReuseQualifiedRoute(string kind)
    {
        return false;
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
        string text = "chain-v4|" + build + "|" + site.Id + "|" + site.Kind + "|" + site.Behaviour;
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
        if (!HCBuildIdentity.SameBuild(a.BuildVersion, p.BuildVersion, "xai_site")) { return "engine build " + a.BuildVersion + " is not the qualified " + p.BuildVersion; }
        if (a.WorldName != p.WorldName) { return "world " + a.WorldName + " is not " + p.WorldName; }
        if (a.MissingAddons != "") { return "missing CfgPatches " + a.MissingAddons; }
        if (!a.SettingsLoaded) { return "Expansion AI settings not loaded"; }
        if (a.Globals != "") { return "Expansion AI globals unfair (no recruiting, no unlimited reload, multipliers 1): " + a.Globals; }
        if (a.UnfairFaction != "") { return "faction " + a.UnfairFaction + " is invincible, observer, passive or has unlimited stamina"; }
        if (a.MissingLoadout != "") { return "loadout file missing: $profile:ExpansionMod/Loadouts/" + a.MissingLoadout + ".json"; }
        if (a.ObserverPolicy != "native-eai" || a.ObserverPolicy != p.ObserverPolicy) { return "observer policy must be native-eai"; }
        if (!a.Marker) { return "pve_patrols turned off by the operator (HollowCountry/acceptance/pve_patrols.disable in the profile)"; }
        if (!a.OwnershipReconciled) { return "ownership journal not reconciled"; }
        return "";
    }
}
