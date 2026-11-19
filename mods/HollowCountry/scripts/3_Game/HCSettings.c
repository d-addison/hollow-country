// JSON presence checks for already bounded, successfully parsed documents.
// JsonFileLoader zeroes absent scalars (boot 057); presence must distinguish
// absent keys from explicit operator false/0. Scan keys, never values/nested
// lookalikes. EnString.c:33 HexToInt, :86 ToAscii, :113 Substring,
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

// Original authored settings. Native JsonFileLoader<T>::LoadData/SaveFile and
// filesystem helpers verified against the installed 1.30 script snapshot.
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
    // Optional: JsonFileLoader absent ints are 0; progression resolves 0 to 128.
    int MaxFamiliarityRows;
    int TickIntervalMs = 1000;
    int MaxTickWorkItems = 32;
    int MaxActiveHordes = 2;
    int MaxActiveHordeMembers = 24;
    int MaxActiveInteriors = 12;
    int MaxPropsPerInterior = 5;
    int MaxFurnishedProps = 1500;
    int MaxBoundSearchSites = 256;
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
        error = "";
        if (SchemaVersion != 1) error = "Unsupported settings schema";
        else if (MaxFamiliarityRows < 0 || MaxFamiliarityRows > 128) error = "Familiarity row budget outside 0..128";
        else if (!HCClientPresentationSettings.HCValidMask(ClientPresentationMask)) error = "ClientPresentationMask outside 0..15";
        else if (TickIntervalMs < 500 || TickIntervalMs > 10000) error = "Tick interval outside 500..10000 ms";
        else if (MaxTickWorkItems < 1 || MaxTickWorkItems > 256) error = "Work budget outside 1..256";
        else if (MaxActiveHordes < 1 || MaxActiveHordes > 8) error = "Horde budget outside 1..8";
        else if (MaxActiveHordeMembers < 1 || MaxActiveHordeMembers > 64) error = "Member budget outside 1..64";
        else if (MaxActiveInteriors < 1 || MaxActiveInteriors > 32) error = "Interior budget outside 1..32";
        else if (MaxPropsPerInterior < 1 || MaxPropsPerInterior > 20) error = "Prop budget outside 1..20";
        else if (MaxFurnishedProps < 0 || MaxFurnishedProps > 2000) error = "Furnished prop budget outside 0..2000";
        else if (MaxBoundSearchSites < 1 || MaxBoundSearchSites > 1024) error = "Bound search site budget outside 1..1024";
        else if (InfectedBindRadius < 5 || InfectedBindRadius > 60) error = "Infected bind radius outside 5..60";
        else if (MaxBindQueriesPerTick < 1 || MaxBindQueriesPerTick > 8) error = "Bind query budget outside 1..8";
        else if (EnableSearch && !EnableInteriors) error = "Search requires interiors";
        else if ((EnableHordes || EnableAlertChains) && !EnableInfected) error = "Hordes/chains require infected";
        return error == "";
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
        return settings;
    }
}
