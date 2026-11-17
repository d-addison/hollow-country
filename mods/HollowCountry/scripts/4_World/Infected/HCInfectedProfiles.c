// Preference-controlled personality policies using existing appearance/stance only.
// No health/damage, sensory, locomotion, sound or door capability is changed.
class HCInfectedProfiles
{
    // Delegates to the one shared matcher; future suffixes need qualification there.
    static bool NativeBuildSupported(string build)
    {
        return HCBuildIdentity.Matches(build);
    }

    protected static bool s_ContactGuardChecked;
    protected static bool s_ContactGuardOptIn;

    // Preference is not evidence that the experimental attack filter is safe.
    // Requires an accepted native wall-hit/queued-attack regression first.
    static bool ContactGuardQualified()
    {
        return false;
    }

    // Local acceptance only: a server operator may create this marker so the
    // owner's local server run can exercise the experimental invocation filter.
    // It stays server-only, is probed once per process and is never persisted.
    static bool ContactGuardOptIn()
    {
        return FileExist("$profile:HollowCountry/acceptance/infected_contact_guard.enable");
    }

    static bool ContactGuardAdmitted()
    {
        if (ContactGuardQualified())
            return true;
        if (!GetGame() || !GetGame().IsServer())
            return false;
        if (!s_ContactGuardChecked)
        {
            s_ContactGuardChecked = true;
            s_ContactGuardOptIn = ContactGuardOptIn();
            if (s_ContactGuardOptIn)
                Print("[HC Infected] contact guard EXPERIMENTAL local acceptance opt-in (infected_contact_guard.enable), wall-hit runtime acceptance PENDING");
        }
        return s_ContactGuardOptIn;
    }

    static string DescriptorName(int variant)
    {
        // Injury is a native overlay, not an operator-selectable base policy.
        if (variant == 6) return RequestedDescriptorName(variant);
        return RequestedDescriptorName(HCInfectedPolicy.ResolveVariant(variant));
    }

    // Proposed/requested labels for diagnostics only, never granted capability.
    static string RequestedDescriptorName(int variant)
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

    // false: config syntax, preserving unsupported requests and empty templates.
    // true: a nonempty map whose every requested attention policy is supported.
    // Neither result is a native runtime qualification receipt.
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
            if (enabled && HCInfectedPolicy.VariantDisposition(choice) != "supported")
                return false;
        }
        return true;
    }

    static int ConfiguredVariant(ZombieBase infected, HCInfectedConfig config)
    {
        if (!infected || !config || !config.EnableVariantPolicies)
            return -1;
        if (!ValidateMap(config.CivilianVariants, false) || !ValidateMap(config.MilitaryVariants, false))
            return -1;
        // Keep empty-map native fallback; nonempty mixed maps retain requested
        // IDs so the separate resolution/disposition cannot erase operator intent.
        if (config.CivilianVariants.Count() != 4 || config.MilitaryVariants.Count() != 4)
            return -1;
        int stance = infected.HCIndividualStance();
        if (stance < 0 || stance > 3) return -1;
        if (infected.IsZombieMilitary())
            return config.MilitaryVariants[stance];
        return config.CivilianVariants[stance];
    }

    // Startup-only: Module calls once after config validation. At most two log
    // records (one per unsupported kind), with counts across both four-slot maps.
    // No static latch survives module restarts and no per-actor logging is used.
    static void LogUnsupportedSubstitutions(HCInfectedConfig config)
    {
        if (!config || !config.EnableVariantPolicies) return;
        if (!ValidateMap(config.CivilianVariants, false) || !ValidateMap(config.MilitaryVariants, false)) return;
        if (config.CivilianVariants.Count() != 4 || config.MilitaryVariants.Count() != 4) return;
        LogUnsupportedChoice(config, 3);
        LogUnsupportedChoice(config, 4);
    }

    static int CountChoice(array<int> configured, int requested)
    {
        if (!configured || configured.Count() != 4) return 0;
        int count = 0;
        foreach (int choice : configured)
        {
            if (choice == requested)
                count++;
        }
        return count;
    }

    static void LogUnsupportedChoice(HCInfectedConfig config, int requested)
    {
        if (HCInfectedPolicy.VariantDisposition(requested) != "unsupported_substituted_native") return;
        int count = CountChoice(config.CivilianVariants, requested) + CountChoice(config.MilitaryVariants, requested);
        if (count == 0) return;
        int resolved = HCInfectedPolicy.ResolveVariant(requested);
        string message = "[HC Infected] variant requested=" + requested.ToString() + " name=" + RequestedDescriptorName(requested);
        message = message + " disposition=" + HCInfectedPolicy.VariantDisposition(requested) + " reason=" + HCInfectedPolicy.VariantReason(requested);
        message = message + " resolved=" + resolved.ToString() + " actual=" + DescriptorName(resolved) + " count=" + count.ToString();
        Print(message);
    }
}
