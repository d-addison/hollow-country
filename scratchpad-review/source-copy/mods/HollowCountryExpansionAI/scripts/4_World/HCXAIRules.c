// Caller bounds below are structural ceilings, not performance/balance defaults.
class HCXAIRules
{
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
    static bool MissionValid(HCXAIProfile p, HCXAIMission route)
    {
        if (!route || !HCXAIRules.Token(route.MissionId)) { return false; }
        if (route.ActorClass.Length() < 13 || route.ActorClass.Length() > 64) { return false; }
        if (route.ActorClass.Substring(0, 12) != "eAI_Survivor") { return false; }
        if (!HCXAIRules.Token(route.FactionName) || route.FactionName == "RANDOM") { return false; }
        if (!HCXAIRules.Hex(route.SurveySha256) || !HCXAIRules.Hex(route.LoadoutSha256)) { return false; }
        if (!HCXAIRules.PositionValid(route.Anchor, p.CoordinateBound)) { return false; }
        if (!route.Spawns || route.Spawns.Count() < 1 || route.Spawns.Count() > 8) { return false; }
        if (route.Spawns.Count() > p.MaxActors) { return false; }
        if (!route.Waypoints || route.Waypoints.Count() < 1 || route.Waypoints.Count() > 16) { return false; }
        if (!route.Equipment || route.Equipment.Count() < 1 || route.Equipment.Count() > 8) { return false; }
        if (route.Spawns.Count() * route.Equipment.Count() > p.MaxItems) { return false; }
        foreach (vector spawn : route.Spawns)
        {
            if (!HCXAIRules.PositionValid(spawn, p.CoordinateBound)) { return false; }
        }
        foreach (vector waypoint : route.Waypoints)
        {
            if (!HCXAIRules.PositionValid(waypoint, p.CoordinateBound)) { return false; }
        }
        int hands = 0;
        foreach (HCXAIEquipment item : route.Equipment)
        {
            if (!item || !HCXAIRules.Token(item.ClassName) || item.ClassName.Length() > 64) { return false; }
            if (item.AmmoCount < 0 || item.AmmoCount > 128) { return false; }
            if (!item.IsMagazine && item.AmmoCount != 0) { return false; }
            if (item.InHands) { hands++; }
        }
        return hands == 1;
    }
    static bool ProfileValid(HCXAIProfile p)
    {
        if (!p || p.SchemaVersion != 1 || !p.Enabled || !p.Experimental) { return false; }
        if (!p.AllowBuiltinStuckRecovery || !p.ProvisionalBounds) { return false; }
        if (p.SourceCommit != "d84d3c73694969eba2f969e9178a1914e2f1b31d" || p.ProviderVersion != "1.9.84") { return false; }
        if (p.BuildVersion != "1.30.164289") { return false; }
        if (p.NativeScriptsSha256 != "09012cdae8c4ae2d478ca90f3e2e3f01e435f0f6945a63b7cae290e3ccdea28a") { return false; }
        if (!HCXAIRules.Token(p.WorldName) || !HCXAIRules.Token(p.WorldSession)) { return false; }
        if (!HCXAIRules.Hex(p.WorldSha256) || !HCXAIRules.Hex(p.ArtifactSha256) || !HCXAIRules.Hex(p.DependencyInventorySha256)) { return false; }
        if (p.MaxGroups < 1 || p.MaxGroups > 8 || p.MaxActors < 1 || p.MaxActors > 32) { return false; }
        if (p.MaxItems < 1 || p.MaxItems > 128 || p.MaxTickWork < 1 || p.MaxTickWork > 8) { return false; }
        if (p.MaxLeaseHistory < p.MaxGroups || p.MaxLeaseHistory > 64) { return false; }
        if (p.MaxObservationAgeMs < 1 || p.MaxObservationAgeMs > 1000000) { return false; }
        if (p.MaxLeaseMs < 1 || p.MaxLeaseMs > 1000000000) { return false; }
        if (!HCXAIRules.Finite(p.CoordinateBound) || p.CoordinateBound <= 0 || p.CoordinateBound > 1000000) { return false; }
        if (!HCObserverTransitionGate.ValidPolicy(p.ObserverPolicy)) { return false; }
        if (!p.Missions || p.Missions.Count() < 1 || p.Missions.Count() > 8) { return false; }
        int index = 0;
        foreach (HCXAIMission route : p.Missions)
        {
            if (!HCXAIRules.MissionValid(p, route)) { return false; }
            int prior = 0;
            while (prior < index)
            {
                if (p.Missions[prior].MissionId == route.MissionId) { return false; }
                prior++;
            }
            index++;
        }
        return true;
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
