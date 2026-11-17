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
        return JsonFileLoader<HCSettings>.LoadData(content, settings, error);
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

    bool Validate(out string error)
    {
        error = "";
        if (SchemaVersion != 1) error = "Unsupported settings schema";
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
