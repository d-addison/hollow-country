// Immutable, bounded profile journals. Readback != fsync or inventory/storage
// atomicity. No overwrites, deletes, refill, fallback image or output replay.
class HCSearchJson<Class T>
{
    static bool Load(string path, int limit, out T value)
    {
        FileHandle handle = OpenFile(path, FileMode.READ);
        if (!handle) return false;
        string text;
        int count = ReadFile(handle, text, limit + 1);
        CloseFile(handle);
        if (count < 1 || count > limit || text.Length() > limit) return false;
        string error;
        return JsonFileLoader<T>.LoadData(text, value, error);
    }

    static bool WriteNew(string path, T value, int limit)
    {
        if (FileExist(path)) return false;
        string text;
        string error;
        if (!JsonFileLoader<T>.MakeData(value, text, error)) return false;
        if (text.Length() < 1 || text.Length() > limit) return false;
        FileHandle handle = OpenFile(path, FileMode.WRITE);
        if (!handle) return false;
        FPrint(handle, text);
        CloseFile(handle);
        T actual;
        if (!HCSearchJson<T>.Load(path, limit, actual)) return false;
        string check;
        return JsonFileLoader<T>.MakeData(actual, check, error) && text == check;
    }
}

class HCSearchEconomyStore
{
    protected string m_Root;
    protected ref HCSearchManifest m_Manifest;
    protected bool m_Fault;

    bool Fail(string reason)
    {
        m_Fault = true;
        Print("[HC Search Economy] journal inactive: " + reason);
        return false;
    }

    bool Healthy() { return m_Manifest && !m_Fault; }
    HCSearchManifest Snapshot() { return m_Manifest; }

    bool Open(HCSearchManifest expected, bool initializeNewEpoch)
    {
        if (m_Fault || m_Manifest || !GetGame().IsServer()) return false;
        if (!HCSearchRules.ManifestValid(expected)) return Fail("invalid manifest");
        string expectedText;
        string actualText;
        string error;
        if (!JsonFileLoader<HCSearchManifest>.MakeData(expected, expectedText, error)) return Fail("manifest serialization");
        if (expectedText.Length() > 8388608) return Fail("manifest byte/character budget");
        string parent = "$profile:HollowCountry";
        if (!FileExist(parent) && !MakeDirectory(parent)) return Fail("profile parent unavailable");
        parent = parent + "/SearchEconomy";
        if (!FileExist(parent) && !MakeDirectory(parent)) return Fail("search profile unavailable");
        m_Root = parent + "/epoch_" + expected.Epoch.ToString();
        string path = m_Root + "/manifest.json";
        if (!FileExist(m_Root))
        {
            if (!initializeNewEpoch) return Fail("new epoch requires explicit initialization; never auto-refill");
            if (!MakeDirectory(m_Root)) return Fail("new epoch directory failed");
            if (!HCSearchJson<HCSearchManifest>.WriteNew(path, expected, 8388608)) return Fail("initial manifest incomplete; preserve root");
        }
        if (!HCSearchJson<HCSearchManifest>.Load(path, 8388608, m_Manifest)) return Fail("manifest missing/corrupt; never initialize existing root");
        if (!HCSearchRules.ManifestValid(m_Manifest)) return Fail("stored manifest invalid");
        if (!JsonFileLoader<HCSearchManifest>.MakeData(m_Manifest, actualText, error)) return Fail("stored manifest serialization");
        if (actualText != expectedText) return Fail("world/build/source/allocation changed; migration required");
        return true;
    }

    string PathFor(int index, string kind)
    {
        if (!m_Manifest || index < 0 || index >= m_Manifest.Entries.Count()) return "";
        if (kind != "claim" && kind != "attempt" && kind != "result") return "";
        return m_Root + "/" + kind + "_" + index.ToString() + ".json";
    }

    bool Matches(HCSearchRecord record, int index)
    {
        if (!record || !m_Manifest || index < 0 || index >= m_Manifest.Entries.Count()) return false;
        if (record.Version != 1 || record.Epoch != m_Manifest.Epoch) return false;
        if (record.WorldName != m_Manifest.WorldName || record.Build != m_Manifest.Build) return false;
        if (record.SourceId != m_Manifest.SourceId || record.SourcePin != m_Manifest.SourcePin) return false;
        HCSearchEntry entry = m_Manifest.Entries[index];
        if (record.SiteId != entry.SiteId || record.SupplyId != entry.SupplyId) return false;
        return record.ItemClass == entry.ItemClass && HCSearchRules.TextValid(record.ActorId, 128);
    }

    HCSearchRecord LoadRecord(int index, string kind)
    {
        HCSearchRecord record;
        if (!HCSearchJson<HCSearchRecord>.Load(PathFor(index, kind), 8192, record)) return null;
        return record;
    }

    int Recover(int index)
    {
        string claimPath = PathFor(index, "claim");
        if (claimPath == "") return 3;
        bool claimExists = FileExist(claimPath);
        bool attemptExists = FileExist(PathFor(index, "attempt"));
        bool resultExists = FileExist(PathFor(index, "result"));
        if (!claimExists && !attemptExists && !resultExists) return 0;
        HCSearchRecord claim = LoadRecord(index, "claim");
        if (!claimExists || !Matches(claim, index) || claim.Phase != 1) return 3;
        if (attemptExists)
        {
            HCSearchRecord attempt = LoadRecord(index, "attempt");
            if (!Matches(attempt, index) || attempt.Phase != 1 || attempt.ActorId != claim.ActorId) return 3;
        }
        if (!resultExists) return 3;
        HCSearchRecord result = LoadRecord(index, "result");
        if (!Matches(result, index) || result.ActorId != claim.ActorId) return 3;
        if (result.Phase == 4) return 4; // Definitive no-transfer/cancel, still depleted.
        if (result.Phase == 2 && attemptExists) return 2;
        return 3;
    }

    bool Write(int index, string kind, HCSearchRecord record)
    {
        if (m_Fault || !Matches(record, index)) return Fail("invalid journal identity");
        string path = PathFor(index, kind);
        if (path == "") return Fail("invalid journal path");
        if (kind == "result")
        {
            if (record.Phase != 2 && record.Phase != 3 && record.Phase != 4) return Fail("invalid result phase");
        }
        else if (record.Phase != 1) return Fail("invalid intent phase");
        if (!HCSearchJson<HCSearchRecord>.WriteNew(path, record, 8192)) return Fail("write/readback failed; no retries");
        return true;
    }
}
