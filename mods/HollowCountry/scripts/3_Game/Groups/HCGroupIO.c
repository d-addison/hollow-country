// Snapshot-local membership index. Rebuild from the authoritative array before
// each operation; no stale ACL cache survives a mutation. Native snapshot
// scripts-1.30.164289: 1_Core/proto/EnScript.c:917,926 Contains/Insert.
class HCGroupStringIndex
{
    protected ref map<string, bool> m_Keys = new map<string, bool>;
    void HCGroupStringIndex(array<string> values)
    {
        foreach (string value : values) { m_Keys.Insert(value, true); }
    }
    bool Has(string value) { return m_Keys.Contains(value); }
    void Add(string value) { m_Keys.Insert(value, true); }
}

// Bounded profile file IO shared by 4_World modules. It lives in 3_Game so
// every 4_World file sees it regardless of compile order (DayZ 021 boot:
// 'Bad type HCGroupJson' from Groups/HCDeathPin.c compiled before HCGroupStore.c).
class HCGroupIO
{
    // The one cap for every bounded raw profile read/write here (8 MiB). Read it qualified
    // (HCGroupIO.HC_RAW_READ_CAP) inside static methods.
    static const int HC_RAW_READ_CAP = 8388608;

    static bool Read(string path, int limit, out string text)
    {
        if (!HCRecoveryGate.HCAllowRead(path)) { return false; }
        if (!HCReadRaw(path, limit, text)) { return false; }
        return HCRecoveryGate.HCReadImage(path, text);
    }

    // Verification-only port: bounded raw bytes, no DTO/gameplay admission.
    static bool HCReadRaw(string path, int limit, out string text)
    {
        if (limit < 1 || limit > HCGroupIO.HC_RAW_READ_CAP) { return false; }
        FileHandle handle = OpenFile(path, FileMode.READ);
        if (!handle) return false;
        int count = ReadFile(handle, text, limit + 1);
        CloseFile(handle);
        return count > 0 && count <= limit && text.Length() > 0 && text.Length() <= limit;
    }

    static bool WriteNew(string path, string text, int limit)
    {
        if (!HCRecoveryGate.HCAllowWrite(path)) { return false; }
        if (limit < 1 || limit > HCGroupIO.HC_RAW_READ_CAP) { return false; }
        if (FileExist(path)) return false;
        if (text.Length() < 1 || text.Length() > limit) return false;
        FileHandle handle = OpenFile(path, FileMode.WRITE);
        if (!handle) return false;
        FPrint(handle, text);
        CloseFile(handle);
        string actual;
        return HCGroupIO.Read(path, limit, actual) && actual == text;
    }
}

class HCGroupJson<Class T>
{
    static bool Load(string path, int limit, out T data)
    {
        string text;
        string error;
        return HCGroupIO.Read(path, limit, text) && JsonFileLoader<T>.LoadData(text, data, error);
    }

    static bool WriteNew(string path, T data, int limit)
    {
        string text;
        string error;
        return JsonFileLoader<T>.MakeData(data, text, error) && HCGroupIO.WriteNew(path, text, limit);
    }
}

// HC-28: per-store, session-local admission gates in the lowest script layer.
// Native scripts-1.30.164289: EnSystem.c:397,417,425,443,462 (IO above);
// EnString.c:199,240 Length/IndexOf; EnDebug.c:96 Print. No engine oracle.
class HCRecoveryGate
{
    protected static bool s_World;
    protected static bool s_Escalation;
    protected static bool s_Groups;
    protected static bool s_WorldDamaged;
    protected static bool s_EscalationDamaged;
    protected static bool s_GroupsDamaged;
    protected static int s_Generation;
    protected static int s_Quarantine;
    protected static string s_Reason = "not_loaded";

    static void HCReset()
    {
        s_World = false;
        s_Escalation = false;
        s_Groups = false;
        s_WorldDamaged = false;
        s_EscalationDamaged = false;
        s_GroupsDamaged = false;
        s_Generation = 0;
        s_Quarantine = 0;
        s_Reason = "not_loaded";
    }

    static void HCAdmit(int generation)
    {
        s_Generation = generation;
        s_World = true;
        s_Escalation = true;
        s_Groups = true;
        s_Reason = "files_validate_independently";
    }

    static bool HCReady(string name)
    {
        if (name == "world") { return s_World; }
        if (name == "escalation") { return s_Escalation; }
        if (name == "groups") { return s_Groups; }
        return false;
    }

    static void HCClose(string name)
    {
        if (name == "world") { s_World = false; }
        if (name == "escalation") { s_Escalation = false; }
        if (name == "groups") { s_Groups = false; }
    }

    static bool HCRefuse(string name, string reason)
    {
        HCClose(name);
        bool reported = true;
        if (name == "world") { reported = s_WorldDamaged; s_WorldDamaged = true; }
        if (name == "escalation") { reported = s_EscalationDamaged; s_EscalationDamaged = true; }
        if (name == "groups") { reported = s_GroupsDamaged; s_GroupsDamaged = true; }
        if (!reported)
        {
            s_Quarantine++;
            s_Reason = reason;
            Print("[HC Plan] HC-28 store=" + name + " recovery=quarantined reason=" + reason + " files=preserved runtime=PENDING");
        }
        return false;
    }

    static int HCGeneration() { return s_Generation; }
    static int HCQuarantined() { return s_Quarantine; }
    static string HCReason() { return s_Reason; }

    static string HCDisposition(string name)
    {
        if (name == "invitation" || name == "runtime_handle") { return "transient"; }
        if (name == "native_inventory" || name == "native_stash") { return "native"; }
        if (name == "world" || name == "escalation" || name == "groups") { return "durable"; }
        return "unknown_refused";
    }

    static string HCStoreFor(string path)
    {
        if (path.IndexOf("$profile:HollowCountry/Groups/state/") == 0) { return "groups"; }
        if (path.IndexOf("$profile:HollowCountry/world.json") == 0) { return "world"; }
        if (path.IndexOf("$profile:HollowCountry/escalation.json") == 0) { return "escalation"; }
        return "";
    }

    static bool HCAllowRead(string path)
    {
        string name = HCStoreFor(path);
        return name == "" || HCReady(name);
    }

    static bool HCAllowWrite(string path) { return HCAllowRead(path); }
    // Image/revision validation belongs to the actual store. Restore hashes
    // are checked once by HCLoad, never pinned across normal gameplay saves.
    static bool HCReadImage(string path, string text) { return HCAllowRead(path); }
}
