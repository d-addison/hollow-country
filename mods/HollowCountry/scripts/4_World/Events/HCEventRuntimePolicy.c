class HCEventRuntimePolicy
{
    static bool PositionValid(vector position)
    {
        int axis = 0;
        while (axis < 3)
        {
            float number = position[axis];
            if (number != number || number < -1000000 || number > 1000000)
            {
                return false;
            }
            axis = axis + 1;
        }
        return true;
    }
    static bool SettingsValid(HCEventSettings settings)
    {
        if (!settings || settings.Version != 1)
        {
            return false;
        }
        if (settings.WorkPerTick < 1 || settings.WorkPerTick > 64)
        {
            return false;
        }
        if (settings.MaxRuns < 1 || settings.MaxRuns > 32)
        {
            return false;
        }
        if (settings.MaxSubscriptions < 1 || settings.MaxSubscriptions > 2880)
        {
            return false;
        }
        if (settings.MaxStoreBytes < 16384 || settings.MaxStoreBytes > 4194304)
        {
            return false;
        }
        if (!settings.Sites || settings.Sites.Count() > 8)
        {
            return false;
        }
        array<string> ids = new array<string>();
        foreach (HCEventSite site : settings.Sites)
        {
            if (!site || !HCEventDirector.TextValid(site.Id, 48) || !HCEventDirector.TextValid(site.WorldName, 96))
            {
                return false;
            }
            if (!PositionValid(site.Position) || !PositionValid(site.Destination) || site.ItemClass.Length() > 96)
            {
                return false;
            }
            if (site.ContainerClass.Length() > 96 || site.AnchorClass.Length() > 96 || site.DeliveryClass.Length() > 96 || site.SalvageClass.Length() > 96)
            {
                return false;
            }
            if (site.Provenance.Length() > 160 || site.SourceSha256.Length() > 64)
            {
                return false;
            }
            if (ids.Find(site.Id) >= 0)
            {
                return false;
            }
            ids.Insert(site.Id);
        }
        return true;
    }
    static bool MissionValid(HCEventMission mission, string world)
    {
        if (!mission || mission.Version != 1 || !mission.Reviewed)
        {
            return false;
        }
        if (!HCEventDirector.TextValid(mission.Id, 64) || !HCEventDirector.TextValid(mission.SiteId, 48))
        {
            return false;
        }
        if (!HCEventDirector.TextValid(world, 96) || mission.WorldName != world)
        {
            return false;
        }
        if (mission.Family < 1 || mission.Family > 7 || mission.RewardUnits != 0)
        {
            return false;
        }
        if (mission.RewardCache && mission.Family != HCEventFamily.RECOVERY)
        {
            return false;
        }
        if (!PositionValid(mission.Source) || !PositionValid(mission.Destination))
        {
            return false;
        }
        if (mission.Radius != mission.Radius || mission.Radius < 1 || mission.Radius > 1000)
        {
            return false;
        }
        if (mission.DwellSeconds < 1 || mission.DwellSeconds > 3600)
        {
            return false;
        }
        if (mission.Goal != 1 || mission.MaxParticipants < 1 || mission.MaxParticipants > HCEventLimits.MAX_PARTICIPANTS)
        {
            return false;
        }
        if (mission.LifetimeSeconds < mission.DwellSeconds || mission.LifetimeSeconds > 86400)
        {
            return false;
        }
        if (mission.Family == HCEventFamily.AI_ENCOUNTER)
        {
            return mission.ActorBudget > 0 && mission.ActorBudget <= 64;
        }
        if (mission.ActorBudget != 0)
        {
            return false;
        }
        // Empty additive fields in old schema-1 journals remain loadable.
        // Native Ready still requires the actual bound, matching container.
        if (mission.ContainerClass.Length() > 96 || mission.AnchorClass.Length() > 96)
        {
            return false;
        }
        if (mission.Family == HCEventFamily.PRESENCE)
        {
            return HCEventDirector.TextValid(mission.AnchorClass, 96);
        }
        if (mission.Family == HCEventFamily.INFECTED_CLEAR || mission.Family == HCEventFamily.INVESTIGATION)
        {
            return true;
        }
        if (!HCEventDirector.TextValid(mission.ItemClass, 96))
        {
            return false;
        }
        return true;
    }
    static HCEventDefinition Definition(HCEventMission mission)
    {
        HCEventDefinition definition = new HCEventDefinition;
        definition.Id = mission.Id;
        definition.WorldName = mission.WorldName;
        definition.ObjectiveTag = mission.SiteId;
        definition.Goal = mission.Goal;
        definition.MaxParticipants = mission.MaxParticipants;
        definition.ActorBudget = mission.ActorBudget;
        definition.LifetimeSeconds = mission.LifetimeSeconds;
        return definition;
    }
    static bool StateValid(HCEventRuntimeState state)
    {
        if (!state || state.Version != 1 || state.Revision < 0 || state.Revision >= 1000000000)
        {
            return false;
        }
        if (!HCEventDirector.StateValid(state.Director) || !state.Runs || state.Runs.Count() != state.Director.Records.Count())
        {
            return false;
        }
        int index = 0;
        foreach (HCEventRun run : state.Runs)
        {
            HCEventRecord record = state.Director.Records[index];
            if (!run || run.EventId != record.Id || !MissionValid(run.Objective, state.Director.WorldName))
            {
                return false;
            }
            if (run.Lease != record.Session + ":" + record.Id.ToString() || !run.ProviderIntent)
            {
                return false;
            }
            if (run.Phase < 0 || run.Phase > 3 || !run.Tokens || run.Tokens.Count() != record.Progress)
            {
                return false;
            }
            if (run.Objective.Id != record.Definition.Id || run.Objective.SiteId != record.Definition.ObjectiveTag)
            {
                return false;
            }
            if (run.Objective.Goal != record.Definition.Goal || record.Definition.RewardUnits != 0)
            {
                return false;
            }
            if (run.Objective.MaxParticipants != record.Definition.MaxParticipants || run.Objective.ActorBudget != record.Definition.ActorBudget)
            {
                return false;
            }
            if (run.Objective.LifetimeSeconds != record.Definition.LifetimeSeconds || record.Definition.ItemBudget != 0)
            {
                return false;
            }
            if (run.Phase >= HCEventRunPhase.CLEANUP && !HCEventDirector.Terminal(record.Status))
            {
                return false;
            }
            if (run.Phase < HCEventRunPhase.CLEANUP && HCEventDirector.Terminal(record.Status))
            {
                return false;
            }
            foreach (string token : run.Tokens)
            {
                if (!HCEventDirector.TextValid(token, 192))
                {
                    return false;
                }
            }
            index = index + 1;
        }
        return true;
    }
}
