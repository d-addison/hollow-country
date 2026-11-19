// JSON presence checks for already bounded, successfully parsed documents.
// JsonFileLoader zeroes absent int fields (observed in boot 057; only ints were
// observed, bool/float/string zero-fill is assumed by analogy and unobserved).
// Presence must distinguish absent keys from explicit operator false/0. Scan
// keys, never values/nested lookalikes. EnString.c:33 HexToInt, :86 ToAscii, :113 Substring,
// :199 Length, :448 Get, installed scripts-1.30.164289. No new file IO/API.
class HCJsonFields
{
    static bool KeyMatches(string text, int start, int stop, string key)
    {
        if (start < 0 || stop > text.Length() || start > stop) { return false; }
        int cursor = start;
        int keyIndex = 0;
        while (cursor < stop && keyIndex < key.Length())
        {
            string letter = text.Get(cursor);
            if (letter == "\\")
            {
                if (cursor + 5 >= stop || text.Get(cursor + 1) != "u") { return false; }
                string hexDigits = text.Substring(cursor + 2, 4);
                string expected = key.Get(keyIndex);
                if (hexDigits.HexToInt() != expected.ToAscii()) { return false; }
                cursor = cursor + 6;
            }
            else
            {
                if (letter != key.Get(keyIndex)) { return false; }
                cursor = cursor + 1;
            }
            keyIndex = keyIndex + 1;
        }
        return cursor == stop && keyIndex == key.Length();
    }

    static bool Check(string text, string key, int targetDepth, bool every, string selector = "")
    {
        int depth = 0;
        int cursor = 0;
        int length = text.Length();
        bool found = false;
        bool seen = false;
        bool selected = false;
        while (cursor < length)
        {
            string token = text.Get(cursor);
            if (token == "\"")
            {
                int start = cursor + 1;
                cursor = start;
                while (cursor < length && text.Get(cursor) != "\"")
                {
                    if (text.Get(cursor) == "\\") { cursor = cursor + 1; }
                    cursor = cursor + 1;
                }
                int after = cursor + 1;
                while (after < length && (text.Get(after) == " " || text.Get(after) == "\n" || text.Get(after) == "\r" || text.Get(after) == "\t")) { after = after + 1; }
                if (depth == targetDepth && after < length && text.Get(after) == ":" && KeyMatches(text, start, cursor, key))
                {
                    seen = true;
                    found = true;
                }
                if (depth == targetDepth && after < length && text.Get(after) == ":" && KeyMatches(text, start, cursor, selector)) { selected = true; }
            }
            else
            {
                if (token == "{" || token == "[")
                {
                    depth = depth + 1;
                    if (depth == targetDepth && token == "{") { seen = false; selected = false; }
                }
                if (token == "}" || token == "]")
                {
                    if (every && token == "}" && depth == targetDepth && !seen && (selector == "" || selected)) { return false; }
                    depth = depth - 1;
                }
            }
            cursor = cursor + 1;
        }
        if (every) { return true; }
        return found;
    }

    static bool Has(string text, string key) { return Check(text, key, 1, false); }
    static bool Every(string text, string key, int depth, string selector = "") { return Check(text, key, depth, true, selector); }
}

// Compiled registry mirror of tools/validate/shared_settings.json. The stdlib
// consistency gate checks every row, DTO default and validation binding. Keeping
// the table compiled avoids a new mission file/runtime IO dependency.
// Native scripts-1.30.164289: 1_Core/proto/EnScript.c:866,902 map Get/Set; EnDebug.c:96 Print.
class HCOperatorSettingRule
{
    string ValueKind;
    float DefaultValue;
    float Minimum;
    float Maximum;
    string Owner;

    void HCOperatorSettingRule(string kind, float defaultValue, float low, float high, string owner)
    {
        ValueKind = kind;
        DefaultValue = defaultValue;
        Minimum = low;
        Maximum = high;
        Owner = owner;
    }
}

class HCOperatorSettingsRegistry
{
    protected static ref map<string, ref HCOperatorSettingRule> s_Rules;

    protected static void HCAdd(string key, string kind, float defaultValue, float low, float high, string owner)
    {
        s_Rules.Set(key, new HCOperatorSettingRule(kind, defaultValue, low, high, owner));
    }

    static void HCInit()
    {
        if (s_Rules) { return; }
        s_Rules = new map<string, ref HCOperatorSettingRule>;
        // BEGIN GENERATED SETTINGS REGISTRY
        HCAdd("SchemaVersion", "int", 1, 1, 1, "HCSettings");
        HCAdd("EnableInteriors", "bool", 1, 0, 1, "HCSettings");
        HCAdd("EnableSearch", "bool", 1, 0, 1, "HCSettings");
        HCAdd("EnableCrafting", "bool", 1, 0, 1, "HCSettings");
        HCAdd("EnableInfected", "bool", 1, 0, 1, "HCSettings");
        HCAdd("EnableHordes", "bool", 1, 0, 1, "HCSettings");
        HCAdd("EnableAlertChains", "bool", 1, 0, 1, "HCSettings");
        HCAdd("EnableGroups", "bool", 1, 0, 1, "HCSettings");
        HCAdd("EnableAtmosphere", "bool", 1, 0, 1, "HCSettings");
        HCAdd("EnableGrade", "bool", 1, 0, 1, "HCSettings");
        HCAdd("ClientPresentationMask", "int", 15, 0, 15, "HCSettings");
        HCAdd("EnableAmbientLife", "bool", 1, 0, 1, "HCSettings");
        HCAdd("EnableSignsOfLife", "bool", 1, 0, 1, "HCSettings");
        HCAdd("EnableTravel", "bool", 1, 0, 1, "HCSettings");
        HCAdd("EnableWorld", "bool", 1, 0, 1, "HCSettings");
        HCAdd("EnableLeads", "bool", 1, 0, 1, "HCSettings");
        HCAdd("EnableCamps", "bool", 1, 0, 1, "HCSettings");
        HCAdd("EnableEncounters", "bool", 1, 0, 1, "HCSettings");
        HCAdd("EnableInfectedVariety", "bool", 1, 0, 1, "HCSettings");
        HCAdd("EnableDebugSnapshot", "bool", 1, 0, 1, "HCSettings");
        HCAdd("EnableAdminMap", "bool", 1, 0, 1, "HCSettings");
        HCAdd("EnableCampRespawn", "bool", 1, 0, 1, "HCSettings");
        HCAdd("EnableTeamPing", "bool", 1, 0, 1, "HCSettings");
        HCAdd("EnableVehicleFlip", "bool", 1, 0, 1, "HCSettings");
        HCAdd("EnableMealBuffs", "bool", 1, 0, 1, "HCSettings");
        HCAdd("EnableForage", "bool", 1, 0, 1, "HCSettings");
        HCAdd("EnableProgression", "bool", 1, 0, 1, "HCSettings");
        HCAdd("EnableGroupScaling", "bool", 1, 0, 1, "HCSettings");
        HCAdd("EnableTapedPackMounts", "bool", 0, 0, 1, "HCSettings");
        HCAdd("TickIntervalMs", "int", 1000, 500, 10000, "HCSettings");
        HCAdd("MaxTickWorkItems", "int", 32, 1, 256, "HCSettings");
        HCAdd("MaxActiveHordes", "int", 2, 1, 8, "HCSettings");
        HCAdd("MaxActiveHordeMembers", "int", 24, 1, 64, "HCSettings");
        HCAdd("MaxActiveInteriors", "int", 12, 1, 32, "HCSettings");
        HCAdd("MaxPropsPerInterior", "int", 5, 1, 20, "HCSettings");
        HCAdd("MaxFurnishedProps", "int", 1500, 0, 2000, "HCSettings");
        HCAdd("MaxBoundSearchSites", "int", 256, 1, 1024, "HCSettings");
        HCAdd("InfectedBindRadius", "int", 30, 5, 60, "HCSettings");
        HCAdd("MaxBindQueriesPerTick", "int", 2, 1, 8, "HCSettings");
        HCAdd("AILimits", "object", 0, 0, 0, "HCAILimits");
        HCAdd("AILimits.MaxLiveGroups", "int", 15, 1, 24, "HCAILimits");
        HCAdd("AILimits.MaxLiveAI", "int", 72, 1, 128, "HCAILimits");
        HCAdd("AILimits.OccupationMin", "int", 3, 1, 12, "HCAILimits");
        HCAdd("AILimits.OccupationMax", "int", 8, 1, 12, "HCAILimits");
        HCAdd("AILimits.HoldoutMin", "int", 3, 1, 12, "HCAILimits");
        HCAdd("AILimits.HoldoutMax", "int", 6, 1, 12, "HCAILimits");
        HCAdd("AILimits.PartyMin", "int", 2, 1, 12, "HCAILimits");
        HCAdd("AILimits.PartyMax", "int", 6, 1, 12, "HCAILimits");
        HCAdd("AILimits.PatrolMin", "int", 2, 1, 12, "HCAILimits");
        HCAdd("AILimits.PatrolMax", "int", 5, 1, 12, "HCAILimits");
        HCAdd("AILimits.CampMin", "int", 2, 1, 12, "HCAILimits");
        HCAdd("AILimits.CampMax", "int", 6, 1, 12, "HCAILimits");
        HCAdd("AILimits.MaxOccupiedPlaces", "int", 15, 1, 64, "HCAILimits");
        HCAdd("AILimits.MaxParties", "int", 24, 1, 128, "HCAILimits");
        HCAdd("AILimits.MaxMaterialized", "int", 15, 1, 24, "HCAILimits");
        HCAdd("AILimits.FactionStrengthMax", "int", 24, 1, 128, "HCAILimits");
        HCAdd("AILimits.MaxActiveSites", "int", 15, 1, 24, "HCAILimits");
        HCAdd("AILimits.MaxActiveAI", "int", 72, 1, 128, "HCAILimits");
        HCAdd("AILimits.MaxEncounters", "int", 15, 1, 24, "HCAILimits");
        HCAdd("AILimits.MaxHoldouts", "int", 48, 24, 128, "HCAILimits");
        HCAdd("AILimits.MaxCamps", "int", 32, 1, 128, "HCAILimits");
        HCAdd("AILimits.MaxCampItems", "int", 64, 1, 128, "HCAILimits");
        HCAdd("AILimits.WorldSeed", "int", 18473, 0, 1000003, "HCAILimits");
        HCAdd("AILimits.MaxObservedAI", "int", 1024, 1, 8192, "HCAILimits");
        HCAdd("MaxFamiliarityRows", "int", 0, 0, 128, "HCSettings");
        HCAdd("SearchDensityScale", "float", 0, 0.5, 2, "HCSettings");
        HCAdd("WildlifeProviders.Version", "int", 1, 1, 1, "HCWildlifeProviderConfig");
        HCAdd("WildlifeProviders.TickMs", "int", 5000, 1, 60000, "HCWildlifeProviderConfig");
        HCAdd("WildlifeProviders.WorkUnits", "int", 16, 1, 64, "HCWildlifeProviderConfig");
        HCAdd("WildlifeProviders.MaxCarcasses", "int", 2, 1, 8, "HCWildlifeProviderConfig");
        HCAdd("WildlifeProviders.MaxPairs", "int", 8, 1, 16, "HCWildlifeProviderConfig");
        HCAdd("WildlifeProviders.MaxPairChecksPerTick", "int", 32, 1, 64, "HCWildlifeProviderConfig");
        HCAdd("WildlifeProviders.PairLifetimeMs", "int", 10000, 1, 60000, "HCWildlifeProviderConfig");
        HCAdd("WildlifeProviders.PairCooldownMs", "int", 30000, 1, 60000, "HCWildlifeProviderConfig");
        HCAdd("WildlifeProviders.MaxPlayerChecks", "int", 16, 1, 64, "HCWildlifeProviderConfig");
        HCAdd("WildlifeProviders.MinPlayerDistanceM", "float", 200.0, 100, 1000, "HCWildlifeProviderConfig");
        HCAdd("WildlifeProviders.Enabled", "bool", 1, 0, 1, "HCWildlifeProviderConfig");
        HCAdd("WildlifeProviders.CarcassesEnabled", "bool", 1, 0, 1, "HCWildlifeProviderConfig");
        HCAdd("WildlifeProviders.TargetPairsEnabled", "bool", 1, 0, 1, "HCWildlifeProviderConfig");
        // END GENERATED SETTINGS REGISTRY
    }

    static HCOperatorSettingRule HCFind(string key)
    {
        HCInit();
        return s_Rules.Get(key);
    }

    static bool HCValid(string key, float value)
    {
        HCOperatorSettingRule rule = HCFind(key);
        if (!rule) { return false; }
        if (key == "SearchDensityScale" && value == 0) { return true; }
        return value >= rule.Minimum && value <= rule.Maximum;
    }

    static float HCDefault(string key)
    {
        HCOperatorSettingRule rule = HCFind(key);
        if (!rule) { return 0; }
        return rule.DefaultValue;
    }

    static float HCMinimum(string key)
    {
        HCOperatorSettingRule rule = HCFind(key);
        if (!rule) { return 0; }
        return rule.Minimum;
    }

    static float HCMaximum(string key)
    {
        HCOperatorSettingRule rule = HCFind(key);
        if (!rule) { return 0; }
        return rule.Maximum;
    }
}

// Original authored settings. Native JsonFileLoader<T>::LoadData/SaveFile and
// filesystem helpers verified against the installed 1.30 script snapshot.
// New effective-value logs: 1_Core/proto/EnConvert.c:3,30,115 bool/int/float ToString.
class HCSettings
{
    static bool AcceptDocumentLength(int length)
    {
        return length > 0 && length <= 16384;
    }

    static bool LoadBounded(string path, out HCSettings settings, out string error)
    {
        FileHandle handle = OpenFile(path, FileMode.READ);
        if (!handle)
        {
            error = "Cannot open settings file";
            return false;
        }
        string content;
        ReadFile(handle, content, 16385);
        CloseFile(handle);
        if (!AcceptDocumentLength(content.Length()))
        {
            error = "Settings document must contain 1..16384 bytes";
            return false;
        }
        if (!JsonFileLoader<HCSettings>.LoadData(content, settings, error) || !settings) { return false; }
        HCApplyLegacy(content, settings);
        return true;
    }

    int SchemaVersion = 1;
    bool EnableInteriors = true;
    bool EnableSearch = true;
    bool EnableCrafting = true;
    bool EnableInfected = true;
    bool EnableHordes = true;
    bool EnableAlertChains = true;
    bool EnableGroups = true;
    bool EnableAtmosphere = true;
    // V2 preferences: HCApplyLegacy explicitly restores absent additive keys.
    // Explicit false/0 stays authoritative; qualification remains independent.
    bool EnableGrade = true;
    int ClientPresentationMask = 15;
    bool EnableAmbientLife = true;
    bool EnableSignsOfLife = true;
    bool EnableTravel = true;
    bool EnableWorld = true;
    bool EnableLeads = true;
    bool EnableCamps = true;
    bool EnableEncounters = true;
    // W5 preferences (#121-#131): additive and default on; each module still gates itself.
    bool EnableInfectedVariety = true;
    bool EnableDebugSnapshot = true;
    bool EnableAdminMap = true;
    bool EnableCampRespawn = true;
    bool EnableTeamPing = true;
    bool EnableVehicleFlip = true;
    bool EnableMealBuffs = true;
    bool EnableForage = true;
    bool EnableProgression = true;
    bool EnableGroupScaling = true;
    // Default false: JsonFileLoader zero-fills a missing bool to false (assumed by analogy to the observed int zero-fill), which is the safe closed value.
    bool EnableTapedPackMounts = false;
    // Optional: JsonFileLoader absent ints are 0; progression resolves 0 to 128.
    int MaxFamiliarityRows = 0;
    int TickIntervalMs = 1000;
    int MaxTickWorkItems = 32;
    int MaxActiveHordes = 2;
    int MaxActiveHordeMembers = 24;
    int MaxActiveInteriors = 12;
    int MaxPropsPerInterior = 5;
    int MaxFurnishedProps = 1500;
    int MaxBoundSearchSites = 256;
    // 0 is the legacy/missing-key identity scale; yield and distances are unchanged.
    float SearchDensityScale = 0;
    int InfectedBindRadius = 30;
    int MaxBindQueriesPerTick = 2;

    ref HCAILimits AILimits = new HCAILimits;

    static void HCApplyLegacy(string content, HCSettings settings)
    {
        HCSettings defaults = new HCSettings;
        if (!HCJsonFields.Has(content, "EnableGrade")) { settings.EnableGrade = defaults.EnableGrade; }
        if (!HCJsonFields.Has(content, "ClientPresentationMask")) { settings.ClientPresentationMask = defaults.ClientPresentationMask; }
        if (!HCJsonFields.Has(content, "EnableAmbientLife")) { settings.EnableAmbientLife = defaults.EnableAmbientLife; }
        if (!HCJsonFields.Has(content, "EnableSignsOfLife")) { settings.EnableSignsOfLife = defaults.EnableSignsOfLife; }
        if (!HCJsonFields.Has(content, "EnableTravel")) { settings.EnableTravel = defaults.EnableTravel; }
        if (!HCJsonFields.Has(content, "EnableWorld")) { settings.EnableWorld = defaults.EnableWorld; }
        if (!HCJsonFields.Has(content, "EnableLeads")) { settings.EnableLeads = defaults.EnableLeads; }
        if (!HCJsonFields.Has(content, "EnableCamps")) { settings.EnableCamps = defaults.EnableCamps; }
        if (!HCJsonFields.Has(content, "EnableEncounters")) { settings.EnableEncounters = defaults.EnableEncounters; }
        if (!HCJsonFields.Has(content, "EnableInfectedVariety")) { settings.EnableInfectedVariety = defaults.EnableInfectedVariety; }
        if (!HCJsonFields.Has(content, "EnableDebugSnapshot")) { settings.EnableDebugSnapshot = defaults.EnableDebugSnapshot; }
        if (!HCJsonFields.Has(content, "EnableAdminMap")) { settings.EnableAdminMap = defaults.EnableAdminMap; }
        if (!HCJsonFields.Has(content, "EnableCampRespawn")) { settings.EnableCampRespawn = defaults.EnableCampRespawn; }
        if (!HCJsonFields.Has(content, "EnableTeamPing")) { settings.EnableTeamPing = defaults.EnableTeamPing; }
        if (!HCJsonFields.Has(content, "EnableVehicleFlip")) { settings.EnableVehicleFlip = defaults.EnableVehicleFlip; }
        if (!HCJsonFields.Has(content, "EnableMealBuffs")) { settings.EnableMealBuffs = defaults.EnableMealBuffs; }
        if (!HCJsonFields.Has(content, "EnableForage")) { settings.EnableForage = defaults.EnableForage; }
        if (!HCJsonFields.Has(content, "EnableProgression")) { settings.EnableProgression = defaults.EnableProgression; }
        if (!HCJsonFields.Has(content, "EnableGroupScaling")) { settings.EnableGroupScaling = defaults.EnableGroupScaling; }
        if (!HCJsonFields.Has(content, "EnableTapedPackMounts")) { settings.EnableTapedPackMounts = defaults.EnableTapedPackMounts; }
        if (!HCJsonFields.Has(content, "AILimits")) { settings.AILimits = defaults.AILimits; }
        if (!HCJsonFields.Has(content, "MaxFurnishedProps")) { settings.MaxFurnishedProps = defaults.MaxFurnishedProps; }
    }

    bool Validate(out string error)
    {
        // Additive section: old settings keep defaults; invalid tuning logs a
        // key-specific fallback without rejecting unrelated feature settings.
        if (!AILimits) { Print("[HC AI] invalid AILimits null; defaults restored"); AILimits = new HCAILimits; }
        AILimits.Validate();
        HCAILimits.Use(AILimits);
        if (!HCOperatorSettingsRegistry.HCValid("SearchDensityScale", SearchDensityScale))
        {
            Print("[HC Settings] invalid SearchDensityScale value=" + SearchDensityScale.ToString() + "; default=0 effective=1 runtime=PENDING");
            SearchDensityScale = HCOperatorSettingsRegistry.HCDefault("SearchDensityScale");
        }
        error = "";
        if (!HCOperatorSettingsRegistry.HCValid("SchemaVersion", SchemaVersion)) error = "Unsupported settings schema";
        else if (!HCOperatorSettingsRegistry.HCValid("MaxFamiliarityRows", MaxFamiliarityRows)) error = "Familiarity row budget outside 0..128";
        else if (!HCOperatorSettingsRegistry.HCValid("ClientPresentationMask", ClientPresentationMask)) error = "ClientPresentationMask outside 0..15";
        else if (!HCOperatorSettingsRegistry.HCValid("TickIntervalMs", TickIntervalMs)) error = "Tick interval outside 500..10000 ms";
        else if (!HCOperatorSettingsRegistry.HCValid("MaxTickWorkItems", MaxTickWorkItems)) error = "Work budget outside 1..256";
        else if (!HCOperatorSettingsRegistry.HCValid("MaxActiveHordes", MaxActiveHordes)) error = "Horde budget outside 1..8";
        else if (!HCOperatorSettingsRegistry.HCValid("MaxActiveHordeMembers", MaxActiveHordeMembers)) error = "Member budget outside 1..64";
        else if (!HCOperatorSettingsRegistry.HCValid("MaxActiveInteriors", MaxActiveInteriors)) error = "Interior budget outside 1..32";
        else if (!HCOperatorSettingsRegistry.HCValid("MaxPropsPerInterior", MaxPropsPerInterior)) error = "Prop budget outside 1..20";
        else if (!HCOperatorSettingsRegistry.HCValid("MaxFurnishedProps", MaxFurnishedProps)) error = "Furnished prop budget outside 0..2000";
        else if (!HCOperatorSettingsRegistry.HCValid("MaxBoundSearchSites", MaxBoundSearchSites)) error = "Bound search site budget outside 1..1024";
        else if (!HCOperatorSettingsRegistry.HCValid("InfectedBindRadius", InfectedBindRadius)) error = "Infected bind radius outside 5..60";
        else if (!HCOperatorSettingsRegistry.HCValid("MaxBindQueriesPerTick", MaxBindQueriesPerTick)) error = "Bind query budget outside 1..8";
        else if (EnableSearch && !EnableInteriors) error = "Search requires interiors";
        else if ((EnableHordes || EnableAlertChains) && !EnableInfected) error = "Hordes/chains require infected";
        return error == "";
    }

    float HCEffectiveSearchDensity()
    {
        if (SearchDensityScale == 0) { return 1.0; }
        return SearchDensityScale;
    }

    // Integer budgets round down; retain a nonzero minimum except for the
    // explicit MaxFurnishedProps=0 veto. Native EnMath.c:427 Floor.
    int HCSearchCap(string key, int configured)
    {
        int scaled = Math.Floor(configured * HCEffectiveSearchDensity());
        int low = HCOperatorSettingsRegistry.HCMinimum(key);
        int high = HCOperatorSettingsRegistry.HCMaximum(key);
        if (scaled < low) { return low; }
        if (scaled > high) { return high; }
        return scaled;
    }

    void HCLogEffective()
    {
        Print("[HC Settings] effective SchemaVersion=" + SchemaVersion.ToString());
        Print("[HC Settings] effective EnableInteriors=" + EnableInteriors.ToString());
        Print("[HC Settings] effective EnableSearch=" + EnableSearch.ToString());
        Print("[HC Settings] effective EnableCrafting=" + EnableCrafting.ToString());
        Print("[HC Settings] effective EnableInfected=" + EnableInfected.ToString());
        Print("[HC Settings] effective EnableHordes=" + EnableHordes.ToString());
        Print("[HC Settings] effective EnableAlertChains=" + EnableAlertChains.ToString());
        Print("[HC Settings] effective EnableGroups=" + EnableGroups.ToString());
        Print("[HC Settings] effective EnableAtmosphere=" + EnableAtmosphere.ToString());
        Print("[HC Settings] effective EnableGrade=" + EnableGrade.ToString());
        Print("[HC Settings] effective ClientPresentationMask=" + ClientPresentationMask.ToString());
        Print("[HC Settings] effective EnableAmbientLife=" + EnableAmbientLife.ToString());
        Print("[HC Settings] effective EnableSignsOfLife=" + EnableSignsOfLife.ToString());
        Print("[HC Settings] effective EnableTravel=" + EnableTravel.ToString());
        Print("[HC Settings] effective EnableWorld=" + EnableWorld.ToString());
        Print("[HC Settings] effective EnableLeads=" + EnableLeads.ToString());
        Print("[HC Settings] effective EnableCamps=" + EnableCamps.ToString());
        Print("[HC Settings] effective EnableEncounters=" + EnableEncounters.ToString());
        Print("[HC Settings] effective EnableInfectedVariety=" + EnableInfectedVariety.ToString());
        Print("[HC Settings] effective EnableDebugSnapshot=" + EnableDebugSnapshot.ToString());
        Print("[HC Settings] effective EnableAdminMap=" + EnableAdminMap.ToString());
        Print("[HC Settings] effective EnableCampRespawn=" + EnableCampRespawn.ToString());
        Print("[HC Settings] effective EnableTeamPing=" + EnableTeamPing.ToString());
        Print("[HC Settings] effective EnableVehicleFlip=" + EnableVehicleFlip.ToString());
        Print("[HC Settings] effective EnableMealBuffs=" + EnableMealBuffs.ToString());
        Print("[HC Settings] effective EnableForage=" + EnableForage.ToString());
        Print("[HC Settings] effective EnableProgression=" + EnableProgression.ToString());
        Print("[HC Settings] effective EnableGroupScaling=" + EnableGroupScaling.ToString());
        Print("[HC Settings] effective EnableTapedPackMounts=" + EnableTapedPackMounts.ToString());
        Print("[HC Settings] effective TickIntervalMs=" + TickIntervalMs.ToString());
        Print("[HC Settings] effective MaxTickWorkItems=" + MaxTickWorkItems.ToString());
        Print("[HC Settings] effective MaxActiveHordes=" + MaxActiveHordes.ToString());
        Print("[HC Settings] effective MaxActiveHordeMembers=" + MaxActiveHordeMembers.ToString());
        float effectiveMaxActiveInteriors = HCSearchCap("MaxActiveInteriors", MaxActiveInteriors);
        Print("[HC Settings] effective MaxActiveInteriors=" + effectiveMaxActiveInteriors.ToString());
        float effectiveMaxPropsPerInterior = HCSearchCap("MaxPropsPerInterior", MaxPropsPerInterior);
        Print("[HC Settings] effective MaxPropsPerInterior=" + effectiveMaxPropsPerInterior.ToString());
        float effectiveMaxFurnishedProps = HCSearchCap("MaxFurnishedProps", MaxFurnishedProps);
        Print("[HC Settings] effective MaxFurnishedProps=" + effectiveMaxFurnishedProps.ToString());
        float effectiveMaxBoundSearchSites = HCSearchCap("MaxBoundSearchSites", MaxBoundSearchSites);
        Print("[HC Settings] effective MaxBoundSearchSites=" + effectiveMaxBoundSearchSites.ToString());
        Print("[HC Settings] effective InfectedBindRadius=" + InfectedBindRadius.ToString());
        Print("[HC Settings] effective MaxBindQueriesPerTick=" + MaxBindQueriesPerTick.ToString());
        Print("[HC Settings] effective AILimits.MaxLiveGroups=" + AILimits.MaxLiveGroups.ToString());
        Print("[HC Settings] effective AILimits.MaxLiveAI=" + AILimits.MaxLiveAI.ToString());
        Print("[HC Settings] effective AILimits.OccupationMin=" + AILimits.OccupationMin.ToString());
        Print("[HC Settings] effective AILimits.OccupationMax=" + AILimits.OccupationMax.ToString());
        Print("[HC Settings] effective AILimits.HoldoutMin=" + AILimits.HoldoutMin.ToString());
        Print("[HC Settings] effective AILimits.HoldoutMax=" + AILimits.HoldoutMax.ToString());
        Print("[HC Settings] effective AILimits.PartyMin=" + AILimits.PartyMin.ToString());
        Print("[HC Settings] effective AILimits.PartyMax=" + AILimits.PartyMax.ToString());
        Print("[HC Settings] effective AILimits.PatrolMin=" + AILimits.PatrolMin.ToString());
        Print("[HC Settings] effective AILimits.PatrolMax=" + AILimits.PatrolMax.ToString());
        Print("[HC Settings] effective AILimits.CampMin=" + AILimits.CampMin.ToString());
        Print("[HC Settings] effective AILimits.CampMax=" + AILimits.CampMax.ToString());
        Print("[HC Settings] effective AILimits.MaxOccupiedPlaces=" + AILimits.MaxOccupiedPlaces.ToString());
        Print("[HC Settings] effective AILimits.MaxParties=" + AILimits.MaxParties.ToString());
        Print("[HC Settings] effective AILimits.MaxMaterialized=" + AILimits.MaxMaterialized.ToString());
        Print("[HC Settings] effective AILimits.FactionStrengthMax=" + AILimits.FactionStrengthMax.ToString());
        Print("[HC Settings] effective AILimits.MaxActiveSites=" + AILimits.MaxActiveSites.ToString());
        Print("[HC Settings] effective AILimits.MaxActiveAI=" + AILimits.MaxActiveAI.ToString());
        Print("[HC Settings] effective AILimits.MaxEncounters=" + AILimits.MaxEncounters.ToString());
        Print("[HC Settings] effective AILimits.MaxHoldouts=" + AILimits.MaxHoldouts.ToString());
        Print("[HC Settings] effective AILimits.MaxCamps=" + AILimits.MaxCamps.ToString());
        Print("[HC Settings] effective AILimits.MaxCampItems=" + AILimits.MaxCampItems.ToString());
        Print("[HC Settings] effective AILimits.WorldSeed=" + AILimits.WorldSeed.ToString());
        Print("[HC Settings] effective AILimits.MaxObservedAI=" + AILimits.MaxObservedAI.ToString());
        Print("[HC Settings] effective MaxFamiliarityRows=" + MaxFamiliarityRows.ToString());
        float effectiveSearchDensityScale = HCEffectiveSearchDensity();
        Print("[HC Settings] effective SearchDensityScale=" + effectiveSearchDensityScale.ToString());
    }

    static HCSettings LoadFromProfile()
    {
        string root = "$profile:HollowCountry";
        if (!FileExist(root) && !MakeDirectory(root))
        {
            Print("[HollowCountry] Cannot create settings directory; features disabled");
            return null;
        }
        string path = root + "/settings.json";
        HCSettings settings = new HCSettings();
        string error;
        if (FileExist(path))
        {
            if (!LoadBounded(path, settings, error) || !settings)
            {
                Print("[HollowCountry] Invalid settings; original file preserved; features disabled: " + error);
                return null;
            }
        }
        else if (!JsonFileLoader<HCSettings>.SaveFile(path, settings, error))
        {
            Print("[HollowCountry] Cannot save default settings; features disabled: " + error);
            return null;
        }
        if (!settings.Validate(error))
        {
            Print("[HollowCountry] Settings rejected; original file preserved: " + error);
            return null;
        }
        settings.HCLogEffective();
        return settings;
    }
}
