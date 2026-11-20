// Self-provisioned HCX defaults (owner report 2026-11-18: the Workshop install
// route has no deploy step, so a fresh server had no site policy ("sites off")
// and no HollowCountry_* loadouts ("loadout file missing"), and AI_ENCOUNTER
// waited for sites forever). The reviewed defaults ship inside this addon's PBO
// under HollowCountryExpansionAI/data/defaults/ (byte-identical to
// mission/hollow-country/ai; the full 528-site map policy since #236 and the
// matching 523-row locality catalogue). Operator files are never
// overwritten; a stale operator policy is only reported.
// Native evidence (scripts-1.30.164289): 1_Core/proto/EnSystem.c:397 FileExist,
// :528 DeleteFile, :531 CopyFile; 1_Core/proto/EnString.c:286 Contains;
// 3_Game/tools/JsonFileLoader.c:69 LoadData. Profile/PBO reads and writes reuse
// HollowCountry HCProfileDefaults (Core/HCProfileDefaults.c). The loadout folder
// is Expansion's EXPANSION_LOADOUT_FOLDER ($profile:ExpansionMod\Loadouts\, created
// by Expansion when its settings load); it is never created here.
class HCXAIDefaults
{
    protected static bool s_LoadoutsProbed;
    protected static int s_ProvisionedLoadouts;
    // Native EnScript.c:866/902/917 Get/Set/Contains. Boot snapshot after
    // Expansion settings are loaded; operator loadout edits require restart.
    protected static ref map<string, bool> s_LoadoutsPresent = new map<string, bool>();
    static bool HCLoadoutPresent(string name) { return s_LoadoutsPresent.Get(name); }
    protected static void HCProbeLoadout(string name)
    {
        s_LoadoutsPresent.Set(name, FileExist(EXPANSION_LOADOUT_FOLDER + name + ".json"));
    }

    static string Shipped()
    {
        return "HollowCountryExpansionAI/data/defaults/";
    }

    static string SitesFile()
    {
        return "expansion-ai-sites.json";
    }

    // Copies the shipped site policy to $profile:HollowCountry only when absent.
    static bool ProvisionSites()
    {
        return HCProfileDefaults.Ensure(HCXAIDefaults.SitesFile(), HCXAIDefaults.Shipped());
    }

    static bool ProvisionLocalities()
    {
        return HCProfileDefaults.Ensure("expansion-ai-localities.json", HCXAIDefaults.Shipped());
    }

    // Our own reviewed loadout names only: HollowCountry_<token>, no path parts.
    static bool LoadoutNameSafe(string name)
    {
        int length = name.Length();
        if (length < 15 || length > 64) { return false; }
        if (name.Substring(0, 14) != "HollowCountry_") { return false; }
        if (name.Contains("..") || name.Contains("/") || name.Contains("\\") || name.Contains(":") || name.Contains("|")) { return false; }
        return true;
    }

    // Copies one shipped loadout into Expansion's loadout folder when that file
    // is absent; temp, copy and readback, never overwriting an operator file.
    static bool ProvisionLoadout(string name)
    {
        if (!HCXAIDefaults.LoadoutNameSafe(name)) { return false; }
        string target = EXPANSION_LOADOUT_FOLDER + name + ".json";
        if (FileExist(target)) { return false; }
        string source = HCXAIDefaults.Shipped() + "loadouts/" + name + ".json";
        string text = HCProfileDefaults.ReadText(source);
        if (text == "")
        {
            Print("[HC Expansion AI] loadout default missing name=" + name + " source=" + source + "; loadout admission keeps its own diagnostic");
            return false;
        }
        string temporary = target + ".hcdefault.tmp";
        // The target was absent before this copy, so a copy that fails readback is removed and retried next boot.
        bool provCopied = false;
        bool provOk = HCProfileDefaults.WriteText(temporary, text);
        if (provOk) { provCopied = CopyFile(temporary, target); provOk = provCopied; }
        if (provOk) { provOk = HCProfileDefaults.ReadText(target) == text; }
        if (!provOk)
        {
            DeleteFile(temporary);
            if (provCopied) { DeleteFile(target); }
            Print("[HC Expansion AI] loadout default refused name=" + name + " reason=write_readback");
            return false;
        }
        DeleteFile(temporary);
        Print("[HC Expansion AI] loadout default provisioned name=" + name + " source=pbo; operator files are never overwritten; runtime=PENDING");
        return true;
    }

    // One pass over the accepted policy (bounded catalog, each name once).
    static int ProvisionLoadouts(HCXAISitePolicy policy)
    {
        if (!policy || !policy.Sites) { return 0; }
        if (s_LoadoutsProbed) { return s_ProvisionedLoadouts; }
        s_LoadoutsProbed = true;
        // Provider-ready boot initialization only: never reprovision on later ticks.
        if (!FileExist(EXPANSION_LOADOUT_FOLDER))
        {
            Print("[HC Expansion AI] loadout defaults skipped: Expansion loadout folder absent");
            return 0;
        }
        int provisioned = 0;
        int visited = 0;
        string seen = "|";
        foreach (HCXAISite site : policy.Sites)
        {
            visited++;
            if (visited > HCXAISiteRules.HCMaxCatalogRows()) { break; }
            if (!site) { continue; }
            if (seen.Contains("|" + site.Loadout + "|")) { continue; }
            seen = seen + site.Loadout + "|";
            if (HCXAIDefaults.ProvisionLoadout(site.Loadout)) { provisioned++; }
            HCXAIDefaults.HCProbeLoadout(site.Loadout);
        }
        HCXAIDefaults.HCProbeLoadout("HollowCountry_Holdout");
        HCXAIDefaults.HCProbeLoadout("HollowCountry_Patrol");
        HCXAIDefaults.HCProbeLoadout("HollowCountry_Scavenger");
        s_ProvisionedLoadouts = provisioned;
        return provisioned;
    }

    static bool MatchesShipped()
    {
        string shipped = HCWorldStore.Read(HCXAIDefaults.Shipped() + HCXAIDefaults.SitesFile());
        if (shipped == "") { return false; }
        return HCWorldStore.Read(HCXAISiteDirector.POLICY) == shipped;
    }

    static int ShippedSiteCount()
    {
        string data = HCWorldStore.Read(HCXAIDefaults.Shipped() + HCXAIDefaults.SitesFile());
        if (data == "") { return 0; }
        string error;
        HCXAISitePolicy policy;
        if (!JsonFileLoader<HCXAISitePolicy>.LoadData(data, policy, error) || !policy || !policy.Sites) { return 0; }
        return policy.Sites.Count();
    }

    // Native scripts-1.30.164289: 3_Game/tools/JsonFileLoader.c:69 LoadData,
    // :85 MakeData. Compare typed values so JSON whitespace is not site drift.
    protected static string PolicyDifferences()
    {
        HCXAISitePolicy profile;
        HCXAISitePolicy shipped;
        string error;
        string profileData = HCWorldStore.Read(HCXAISiteDirector.POLICY);
        string shippedData = HCWorldStore.Read(HCXAIDefaults.Shipped() + HCXAIDefaults.SitesFile());
        if (!JsonFileLoader<HCXAISitePolicy>.LoadData(profileData, profile, error) || !profile) { return "comparison=profile_unreadable"; }
        if (!JsonFileLoader<HCXAISitePolicy>.LoadData(shippedData, shipped, error) || !shipped) { return "comparison=shipped_unreadable"; }
        if (!profile.Sites || !shipped.Sites) { return "comparison=sites_unreadable"; }
        if (profile.Sites.Count() > HCXAISiteRules.HCMaxCatalogRows() || shipped.Sites.Count() > HCXAISiteRules.HCMaxCatalogRows()) { return "comparison=sites_row_budget"; }
        if (profile.BuildVersion != shipped.BuildVersion)
        {
            Print("[HC Expansion AI] sites policy build stamp differs: profile=" + profile.BuildVersion + " shipped=" + shipped.BuildVersion);
        }
        string keys = "";
        int count = 0;
        HCXAIDefaults.DriftKey(profile.SchemaVersion != shipped.SchemaVersion, "SchemaVersion", keys, count);
        HCXAIDefaults.DriftKey(profile.WorldName != shipped.WorldName, "WorldName", keys, count);
        HCXAIDefaults.DriftKey(profile.BuildVersion != shipped.BuildVersion, "BuildVersion", keys, count);
        HCXAIDefaults.DriftKey(profile.ObserverPolicy != shipped.ObserverPolicy, "ObserverPolicy", keys, count);
        HCXAIDefaults.DriftKey(profile.MaxActiveAI != shipped.MaxActiveAI, "MaxActiveAI", keys, count);
        HCXAIDefaults.DriftKey(profile.MaxActiveSites != shipped.MaxActiveSites, "MaxActiveSites", keys, count);
        HCXAIDefaults.DriftKey(profile.MinPlayerDistance != shipped.MinPlayerDistance, "MinPlayerDistance", keys, count);
        HCXAIDefaults.DriftKey(profile.LineOfSightRange != shipped.LineOfSightRange, "LineOfSightRange", keys, count);
        HCXAIDefaults.DriftKey(profile.MaxLegLength != shipped.MaxLegLength, "MaxLegLength", keys, count);
        HCXAIDefaults.DriftKey(profile.CacheClearRadius != shipped.CacheClearRadius, "CacheClearRadius", keys, count);
        HCXAIDefaults.DriftKey(profile.AIRespawnSeconds != shipped.AIRespawnSeconds, "AIRespawnSeconds", keys, count);
        HCXAIDefaults.DriftKey(profile.PatrolRespawnSeconds != shipped.PatrolRespawnSeconds, "PatrolRespawnSeconds", keys, count);
        HCXAIDefaults.DriftKey(profile.HoldoutRespawnSeconds != shipped.HoldoutRespawnSeconds, "HoldoutRespawnSeconds", keys, count);
        HCXAIDefaults.DriftKey(profile.MilitaryRespawnSeconds != shipped.MilitaryRespawnSeconds, "MilitaryRespawnSeconds", keys, count);
        HCXAIDefaults.DriftKey(profile.MemberReplaceSeconds != shipped.MemberReplaceSeconds, "MemberReplaceSeconds", keys, count);
        HCXAIDefaults.DriftKey(profile.RaidCooldownFloorSeconds != shipped.RaidCooldownFloorSeconds, "RaidCooldownFloorSeconds", keys, count);
        HCXAIDefaults.DriftKey(profile.ActivationRadiusScale != shipped.ActivationRadiusScale, "ActivationRadiusScale", keys, count);
        HCXAIDefaults.DriftKey(profile.BetrayalRetentionSeconds != shipped.BetrayalRetentionSeconds, "BetrayalRetentionSeconds", keys, count);
        HCXAIDefaults.DriftKey(profile.MaxBetrayalRows != shipped.MaxBetrayalRows, "MaxBetrayalRows", keys, count);
        HCXAIDefaults.DriftKey(profile.MaxSignalWorkPerSecond != shipped.MaxSignalWorkPerSecond, "MaxSignalWorkPerSecond", keys, count);
        string profileSites;
        string shippedSites;
        if (!JsonFileLoader<array<ref HCXAISite>>.MakeData(profile.Sites, profileSites, error, false)) { return "comparison=sites_unreadable"; }
        if (!JsonFileLoader<array<ref HCXAISite>>.MakeData(shipped.Sites, shippedSites, error, false)) { return "comparison=sites_unreadable"; }
        string sites = "same";
        if (profileSites != shippedSites) { sites = "different"; }
        if (keys == "") { keys = "none"; }
        return "policy_keys=" + keys + " differing_key_count=" + count.ToString() + " site_list=" + sites;
    }

    protected static void DriftKey(bool differs, string key, inout string keys, inout int count)
    {
        if (!differs) { return; }
        if (count < 3)
        {
            if (keys != "") { keys = keys + ","; }
            keys = keys + key;
        }
        count++;
    }

    // "" when the operator policy is the shipped default; otherwise one line
    // naming the drift. The operator file is kept either way.
    static string PolicyDrift(bool identical, int profileSites, int shippedSites)
    {
        if (identical) { return ""; }
        if (shippedSites < 1) { return "[HC Expansion AI] sites policy shipped default unreadable; operator file kept"; }
        return "[HC Expansion AI] sites policy differs from shipped default: " + HCXAIDefaults.PolicyDifferences() + "; profile sites=" + profileSites.ToString() + " shipped sites=" + shippedSites.ToString() + "; operator file kept; delete it to adopt the shipped default";
    }
}
