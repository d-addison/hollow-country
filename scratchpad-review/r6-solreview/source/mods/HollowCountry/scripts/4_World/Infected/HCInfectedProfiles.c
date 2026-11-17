// Preference-controlled personality policies using existing appearance/stance only.
// No health/damage, sensory, locomotion, sound or door capability is changed.
class HCInfectedProfiles
{
    // Exact aliases of the inspected snapshot; future suffixes need qualification.
    static bool NativeBuildSupported(string build)
    {
        return build == "1.30.164289" || build == "1.30.164289.70";
    }

    // Preference is not evidence that the experimental attack filter is safe.
    // Requires an accepted native wall-hit/queued-attack regression first.
    static bool ContactGuardQualified()
    {
        return false;
    }

    static string DescriptorName(int variant)
    {
        if (variant == 0) return "ordinary_wanderer";
        if (variant == 1) return "reactive_infected";
        if (variant == 2) return "persistent_searcher";
        if (variant == 3) return "careful_stalker";
        if (variant == 4) return "forceful_heavy";
        if (variant == 5) return "group_responder";
        if (variant == 6) return "injured_crawler";
        return "unavailable";
    }

    static bool ValidateMap(array<int> configured, bool enabled)
    {
        if (!configured) return false;
        int count = configured.Count();
        if (count == 0) return !enabled;
        if (count != 4) return false;
        foreach (int choice : configured)
        {
            if (HCInfectedPolicy.ResolveVariant(choice) < 0)
                return false;
        }
        return true;
    }

    static int ConfiguredVariant(ZombieBase infected, HCInfectedConfig config)
    {
        if (!infected || !config || !config.EnableVariantPolicies)
            return -1;
        if (!ValidateMap(config.CivilianVariants, true) || !ValidateMap(config.MilitaryVariants, true))
            return -1;
        int stance = infected.HCIndividualStance();
        if (stance < 0 || stance > 3) return -1;
        if (infected.IsZombieMilitary())
            return config.MilitaryVariants[stance];
        return config.CivilianVariants[stance];
    }
}
