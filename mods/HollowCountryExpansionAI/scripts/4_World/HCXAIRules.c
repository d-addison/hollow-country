// Caller bounds below are structural ceilings, not performance/balance defaults.
class HCXAIRules
{
    // LC-T403. Every live caller refuses and logs the first failed assertion.
    static string ProviderProblem(bool finiteAmmo, bool recruitFriendly, bool recruitGuards, bool providerPatrolsOff)
    {
        if (!finiteAmmo) { return "finite ammunition required: unlimited reload mask set"; }
        if (recruitFriendly || recruitGuards) { return "recruiting must be off"; }
        if (!providerPatrolsOff) { return "provider patrols must be off"; }
        return "";
    }
    // Provider receives only this site's qualified authored route. There is no
    // player argument and no observed-player-position field in this boundary.
    static string PatrolProblem(ExpansionAIDynamicSpawnBase config, array<vector> qualified)
    {
        if (!config || config.UnlimitedReload != 0 || config.LootingBehaviour != "NONE") { return "finite ammo and looting NONE required"; }
        if (!qualified || !config.Waypoints || qualified.Count() < 2 || qualified.Count() > 128 || config.Waypoints.Count() != qualified.Count()) { return "provider route must be the qualified static route; no player positions"; }
        int pointIndex = 0;
        while (pointIndex < qualified.Count())
        {
            if (config.Waypoints[pointIndex] != qualified[pointIndex]) { return "provider route differs from qualified static route; no player positions"; }
            pointIndex++;
        }
        return "";
    }
    static string CheckpointProblem(HCXAISite site)
    {
        if (!site.Checkpoint) { return ""; }
        if (!site.Reviewed || site.Kind != "patrol" || site.Faction != "Guards" || site.NumberOfAI != 2 || site.NumberOfAIMax > 3) { return "checkpoint needs source review and 2..3 Volunteer guards"; }
        if (!HCXAIRules.PositionValid(site.CheckpointProp, 16000) || site.CheckpointProp[0] < 1 || site.CheckpointProp[2] < 1) { return "checkpoint prop outside world"; }
        if (!site.Waypoints || site.Waypoints.Count() < 3 || vector.Distance(site.CheckpointProp, site.Waypoints[0]) > 60) { return "checkpoint prop must be near its reviewed route"; }
        return "";
    }
    static bool Finite(float value)
    {
        return value == value && value - value == 0;
    }
    static bool Token(string value)
    {
        return value.Length() > 0 && value.Length() <= 128;
    }
    static bool Hex(string value)
    {
        if (value.Length() != 64) { return false; }
        string alphabet = "0123456789abcdef";
        int index = 0;
        while (index < 64)
        {
            if (!alphabet.Contains(value.Substring(index, 1))) { return false; }
            index++;
        }
        return true;
    }
    static bool PositionValid(vector position, float bound)
    {
        int axis = 0;
        while (axis < 3)
        {
            float value = position[axis];
            if (!HCXAIRules.Finite(value) || value < -bound || value > bound) { return false; }
            axis++;
        }
        return true;
    }
    // First unmet route requirement, or "" when the route is admissible.
    static string MissionProblem(HCXAIProfile p, HCXAIMission route)
    {
        if (!route) { return "null mission"; }
        if (!HCXAIRules.Token(route.MissionId) || !HCXAIRules.Token(route.SiteId)) { return "mission MissionId/SiteId missing"; }
        string id = "mission " + route.MissionId + ": ";
        if (route.MissionId != route.SiteId + "-5") { return id + "MissionId must be SiteId-5"; }
        if (route.ActorClass.Length() < 13 || route.ActorClass.Length() > 64) { return id + "ActorClass length"; }
        if (route.ActorClass.Substring(0, 12) != "eAI_Survivor") { return id + "ActorClass must be eAI_Survivor*"; }
        if (!HCXAIRules.Token(route.FactionName) || route.FactionName == "RANDOM") { return id + "FactionName"; }
        if (!HCXAIRules.Hex(route.SurveySha256) || !HCXAIRules.Hex(route.LoadoutSha256)) { return id + "SurveySha256/LoadoutSha256 need observed 64-hex route survey and loadout digests"; }
        if (!HCXAIRules.PositionValid(route.Anchor, p.CoordinateBound)) { return id + "Anchor out of bounds"; }
        if (!route.Spawns || route.Spawns.Count() < 1 || route.Spawns.Count() > 8) { return id + "Spawns count 1..8"; }
        if (route.GroupSize != route.Spawns.Count()) { return id + "GroupSize must equal Spawns count"; }
        if (route.Spawns.Count() > p.MaxActors) { return id + "Spawns exceed MaxActors"; }
        if (!route.Waypoints || route.Waypoints.Count() < 1 || route.Waypoints.Count() > 16) { return id + "Waypoints count 1..16"; }
        if (!route.Equipment || route.Equipment.Count() < 1 || route.Equipment.Count() > 8) { return id + "Equipment count 1..8"; }
        if (route.Spawns.Count() * route.Equipment.Count() > p.MaxItems) { return id + "items exceed MaxItems"; }
        foreach (vector spawn : route.Spawns)
        {
            if (!HCXAIRules.PositionValid(spawn, p.CoordinateBound)) { return id + "spawn out of bounds"; }
        }
        foreach (vector waypoint : route.Waypoints)
        {
            if (!HCXAIRules.PositionValid(waypoint, p.CoordinateBound)) { return id + "waypoint out of bounds"; }
        }
        int hands = 0;
        foreach (HCXAIEquipment item : route.Equipment)
        {
            if (!item || !HCXAIRules.Token(item.ClassName) || item.ClassName.Length() > 64) { return id + "equipment ClassName"; }
            if (item.AmmoCount < 0 || item.AmmoCount > 128) { return id + "equipment AmmoCount 0..128"; }
            if (!item.IsMagazine && item.AmmoCount != 0) { return id + "AmmoCount only on magazines"; }
            if (item.InHands) { hands++; }
        }
        if (hands != 1) { return id + "exactly one InHands item"; }
        return "";
    }
    static bool MissionValid(HCXAIProfile p, HCXAIMission route)
    {
        return HCXAIRules.MissionProblem(p, route) == "";
    }
    // First unmet operator-policy requirement, or "" when the policy is admissible.
    static string ProfileProblem(HCXAIProfile p)
    {
        if (!p) { return "policy file missing or unreadable"; }
        if (p.SchemaVersion != 1 || !p.Enabled || !p.Experimental) { return "SchemaVersion 1, Enabled and Experimental required"; }
        if (!p.AllowBuiltinStuckRecovery || !p.ProvisionalBounds) { return "AllowBuiltinStuckRecovery and ProvisionalBounds required"; }
        if (p.SourceCommit != "d84d3c73694969eba2f969e9178a1914e2f1b31d" || p.ProviderVersion != "1.9.84") { return "SourceCommit/ProviderVersion pin mismatch"; }
        if (!HCBuildIdentity.Matches(p.BuildVersion)) { return "BuildVersion pin mismatch"; }
        if (p.NativeScriptsSha256 != "09012cdae8c4ae2d478ca90f3e2e3f01e435f0f6945a63b7cae290e3ccdea28a") { return "NativeScriptsSha256 pin mismatch"; }
        if (!HCXAIRules.Token(p.WorldName) || !HCXAIRules.Token(p.WorldSession)) { return "WorldName/WorldSession missing"; }
        if (!HCXAIRules.Hex(p.WorldSha256) || !HCXAIRules.Hex(p.ArtifactSha256) || !HCXAIRules.Hex(p.DependencyInventorySha256)) { return "WorldSha256/ArtifactSha256/DependencyInventorySha256 need observed 64-hex digests"; }
        if (p.MaxGroups < 1 || p.MaxGroups > 8 || p.MaxActors < 1 || p.MaxActors > 32) { return "MaxGroups 1..8 / MaxActors 1..32"; }
        if (p.MaxItems < 1 || p.MaxItems > 128 || p.MaxTickWork < 1 || p.MaxTickWork > 8) { return "MaxItems 1..128 / MaxTickWork 1..8"; }
        if (p.MaxLeaseHistory < p.MaxGroups || p.MaxLeaseHistory > 64) { return "MaxLeaseHistory MaxGroups..64"; }
        if (p.MaxObservationAgeMs < 1 || p.MaxObservationAgeMs > 1000000) { return "MaxObservationAgeMs 1..1000000"; }
        if (p.MaxLeaseMs < 1 || p.MaxLeaseMs > 1000000000) { return "MaxLeaseMs 1..1000000000"; }
        if (!HCXAIRules.Finite(p.CoordinateBound) || p.CoordinateBound <= 0 || p.CoordinateBound > 1000000) { return "CoordinateBound 0..1000000"; }
        if (!HCObserverTransitionGate.ValidPolicy(p.ObserverPolicy)) { return "ObserverPolicy invalid"; }
        if (!p.Missions || p.Missions.Count() < 1 || p.Missions.Count() > 8) { return "Missions count 1..8"; }
        int index = 0;
        foreach (HCXAIMission route : p.Missions)
        {
            string problem = HCXAIRules.MissionProblem(p, route);
            if (problem != "") { return problem; }
            int prior = 0;
            while (prior < index)
            {
                if (p.Missions[prior].MissionId == route.MissionId) { return "duplicate MissionId " + route.MissionId; }
                prior++;
            }
            index++;
        }
        return "";
    }
    static bool ProfileValid(HCXAIProfile p)
    {
        return HCXAIRules.ProfileProblem(p) == "";
    }
    static string Join(string list, string item)
    {
        if (list == "") { return item; }
        return list + "," + item;
    }
    // Names every false trusted-verification flag; "" when all six are set.
    static string ReceiptGaps(HCXAIAdmission r)
    {
        if (!r) { return "no receipt"; }
        string gaps = "";
        if (!r.ArtifactBytesVerified) { gaps = HCXAIRules.Join(gaps, "ArtifactBytesVerified"); }
        if (!r.DependencyClosureVerified) { gaps = HCXAIRules.Join(gaps, "DependencyClosureVerified"); }
        if (!r.ObserverProviderQualified) { gaps = HCXAIRules.Join(gaps, "ObserverProviderQualified"); }
        if (!r.RoutesQualified) { gaps = HCXAIRules.Join(gaps, "RoutesQualified"); }
        if (!r.InventoryLedgerQualified) { gaps = HCXAIRules.Join(gaps, "InventoryLedgerQualified"); }
        if (!r.OwnershipReconciled) { gaps = HCXAIRules.Join(gaps, "OwnershipReconciled"); }
        return gaps;
    }
    static bool ReceiptValid(HCXAIProfile p, HCXAIAdmission r, int now)
    {
        if (!r || now < 0 || r.ObservedAtMs < 0 || r.ObservedAtMs > now) { return false; }
        if (r.Sequence <= 0 || r.Sequence > 1000000 || now - r.ObservedAtMs > p.MaxObservationAgeMs) { return false; }
        if (!r.ArtifactBytesVerified || !r.DependencyClosureVerified || !r.ObserverProviderQualified) { return false; }
        if (!r.RoutesQualified || !r.InventoryLedgerQualified || !r.OwnershipReconciled) { return false; }
        if (r.SourceCommit != p.SourceCommit || r.BuildVersion != p.BuildVersion) { return false; }
        if (r.NativeScriptsSha256 != p.NativeScriptsSha256 || r.WorldName != p.WorldName) { return false; }
        if (r.WorldSession != p.WorldSession || r.WorldSha256 != p.WorldSha256) { return false; }
        return r.ArtifactSha256 == p.ArtifactSha256 && r.DependencyInventorySha256 == p.DependencyInventorySha256;
    }
}
