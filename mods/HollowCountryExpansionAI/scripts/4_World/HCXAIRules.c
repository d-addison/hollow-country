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
        if (!site.Reviewed || site.Kind != "patrol" || site.Faction != "Guards" || site.NumberOfAI < 1 || site.NumberOfAIMax > HCAILimits.SIZE_CEILING) { return "checkpoint needs source review and configured Volunteer guards"; }
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
}
