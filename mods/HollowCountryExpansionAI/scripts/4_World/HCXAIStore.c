// Native bounded file/serialization adapters; no qualification is inferred here.
class HCXAIStore
{
    static string NativeBuild()
    {
        string version;
        GetGame().GetVersion(version);
        if (version == "1.30.164289.70") { return "1.30.164289"; }
        return version;
    }
    static HCXAIProfile Freeze(HCXAIProfile profile)
    {
        string data;
        string error;
        HCXAIProfile frozen;
        if (!JsonFileLoader<HCXAIProfile>.MakeData(profile, data, error) || data.Length() > 32768) { return null; }
        if (!JsonFileLoader<HCXAIProfile>.LoadData(data, frozen, error)) { return null; }
        return frozen;
    }
    static HCXAIProfile Load()
    {
        string path = "$profile:HollowCountry/expansion-ai.json";
        string error;
        MakeDirectory("$profile:HollowCountry");
        if (!FileExist(path))
        {
            HCXAIProfile template = new HCXAIProfile();
            if (!JsonFileLoader<HCXAIProfile>.SaveFile(path, template, error))
            {
                Print("[HC Expansion AI] enabled preference; template write failed");
            }
            else
            {
                Print("[HC Expansion AI] enabled preference template created; pinned prerequisites and explicit budgets required");
            }
            return null;
        }
        FileHandle handle = OpenFile(path, FileMode.READ);
        if (!handle) { return null; }
        string data;
        int count = ReadFile(handle, data, 32769);
        CloseFile(handle);
        if (count < 1 || count > 32768) { return null; }
        HCXAIProfile profile;
        if (!JsonFileLoader<HCXAIProfile>.LoadData(data, profile, error)) { return null; }
        return profile;
    }
}
