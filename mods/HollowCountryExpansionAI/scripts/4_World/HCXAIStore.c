// Native bounded file/serialization adapters; no qualification is inferred here.
class HCXAIStore
{
    static string NativeBuild()
    {
        string version;
        GetGame().GetVersion(version);
        return HCBuildIdentity.Normalize(version);
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
    static HCXAIJournalData LoadJournal()
    {
        string path = "$profile:HollowCountry/expansion-ai-leases.json";
        // No atomic rename is exposed by the pinned native file API. A retained
        // staging file guards interrupted/uncertain publication: refuse admission
        // rather than treating a missing or partly copied journal as empty.
        if (FileExist("$profile:HollowCountry/expansion-ai-leases.pending.json")) { return null; }
        if (!FileExist(path)) { return new HCXAIJournalData(); }
        return HCXAIStore.ReadJournal(path);
    }
    static HCXAIJournalData ReadJournal(string path)
    {
        FileHandle handle = OpenFile(path, FileMode.READ);
        if (!handle) { return null; }
        string data;
        int count = ReadFile(handle, data, 65537);
        CloseFile(handle);
        if (count < 1 || count > 65536) { return null; }
        string error;
        HCXAIJournalData journal;
        if (!JsonFileLoader<HCXAIJournalData>.LoadData(data, journal, error)) { return null; }
        return journal;
    }
    static bool SaveJournal(HCXAIJournalData journal)
    {
        if (!GetGame() || !GetGame().IsServer() || !journal || !journal.Rows || journal.Rows.Count() > 64) { return false; }
        string path = "$profile:HollowCountry/expansion-ai-leases.json";
        string pending = "$profile:HollowCountry/expansion-ai-leases.pending.json";
        if (FileExist(pending)) { return false; }
        string expected;
        string actual;
        string error;
        if (!JsonFileLoader<HCXAIJournalData>.MakeData(journal, expected, error) || expected.Length() > 65536) { return false; }
        MakeDirectory("$profile:HollowCountry");
        // Verify staging before touching committed bytes. Keep the guard on every
        // failure, including uncertain copy/readback, for explicit reconciliation.
        if (!JsonFileLoader<HCXAIJournalData>.SaveFile(pending, journal, error)) { return false; }
        HCXAIJournalData staged = HCXAIStore.ReadJournal(pending);
        if (!staged || !JsonFileLoader<HCXAIJournalData>.MakeData(staged, actual, error) || actual != expected) { return false; }
        if (!CopyFile(pending, path)) { return false; }
        HCXAIJournalData observed = HCXAIStore.ReadJournal(path);
        if (!observed || !JsonFileLoader<HCXAIJournalData>.MakeData(observed, actual, error)) { return false; }
        if (actual != expected || !DeleteFile(pending)) { return false; }
        return !FileExist(pending);
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
