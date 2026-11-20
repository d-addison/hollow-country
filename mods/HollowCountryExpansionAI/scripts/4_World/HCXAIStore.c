// Native bounded file/serialization adapters; no qualification is inferred here.
class HCXAIStore
{
    protected static bool s_JournalPrimed;
    protected static bool s_JournalUncertain;
    protected static ref HCXAIJournalData s_BootJournal;
    // Called by the site director's Start before encounters can tick. A failed
    // boot read stays refused; never retry a disk read from lease maintenance.
    static void HCPrimeJournal()
    {
        if (s_JournalPrimed) { return; }
        s_JournalPrimed = true;
        s_BootJournal = HCXAIStore.HCReadBootJournal();
    }

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
        if (s_JournalUncertain) { return null; }
        return s_BootJournal;
    }
    protected static HCXAIJournalData HCReadBootJournal()
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
    // Begin/Prune/End consume this bool as a durability receipt. Queuing here
    // would release reservations or admit creation before persistence. Staging
    // requires continuations in HCXAIJournal/HCXAIEncounters (outside this batch).
    static bool SaveJournal(HCXAIJournalData journal)
    {
        if (!GetGame() || !GetGame().IsServer() || !journal || !journal.Rows || journal.Rows.Count() > 64) { return false; }
        string path = "$profile:HollowCountry/expansion-ai-leases.json";
        string pending = "$profile:HollowCountry/expansion-ai-leases.pending.json";
        if (FileExist(pending)) { s_JournalUncertain = true; return false; }
        string expected;
        string actual;
        string error;
        if (!JsonFileLoader<HCXAIJournalData>.MakeData(journal, expected, error) || expected.Length() > 65536) { return false; }
        MakeDirectory("$profile:HollowCountry");
        // Verify staging before touching committed bytes. Keep the guard on every
        // failure, including uncertain copy/readback, for explicit reconciliation.
        s_JournalUncertain = true;
        if (!JsonFileLoader<HCXAIJournalData>.SaveFile(pending, journal, error)) { return false; }
        HCXAIJournalData staged = HCXAIStore.ReadJournal(pending);
        if (!staged || !JsonFileLoader<HCXAIJournalData>.MakeData(staged, actual, error) || actual != expected) { return false; }
        if (!CopyFile(pending, path)) { return false; }
        HCXAIJournalData observed = HCXAIStore.ReadJournal(path);
        if (!observed || !JsonFileLoader<HCXAIJournalData>.MakeData(observed, actual, error)) { return false; }
        if (actual != expected || !DeleteFile(pending)) { return false; }
        if (FileExist(pending)) { return false; }
        s_JournalUncertain = false;
        s_BootJournal = journal;
        return true;
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
