// Bounded profile file IO shared by 4_World modules. It lives in 3_Game so
// every 4_World file sees it regardless of compile order (DayZ 021 boot:
// 'Bad type HCGroupJson' from Groups/HCDeathPin.c compiled before HCGroupStore.c).
class HCGroupIO
{
    static bool Read(string path, int limit, out string text)
    {
        if (!HCRecoveryGate.HCAllowRead(path)) { return false; }
        if (!HCReadRaw(path, limit, text)) { return false; }
        return HCRecoveryGate.HCReadImage(path, text);
    }

    // Verification-only port: bounded raw bytes, no DTO/gameplay admission.
    static bool HCReadRaw(string path, int limit, out string text)
    {
        if (limit < 1 || limit > 1048576) { return false; }
        FileHandle handle = OpenFile(path, FileMode.READ);
        if (!handle) return false;
        int count = ReadFile(handle, text, limit + 1);
        CloseFile(handle);
        return count > 0 && count <= limit && text.Length() > 0 && text.Length() <= limit;
    }

    static bool WriteNew(string path, string text, int limit)
    {
        if (!HCRecoveryGate.HCAllowWrite(path)) { return false; }
        if (limit < 1 || limit > 1048576) { return false; }
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

// HC-28: lowest-layer durable/transient/native policy; 3_Game must not see
// 4_World recovery DTOs. HCPersistenceDisposition fills this bounded gate before
// admission. Existing group intent/image/commit revision validation is retained.
// Native scripts-1.30.164289: 1_Core/proto/EnSystem.c:397,417,425,443,462
// FileExist/OpenFile/ReadFile/CloseFile/FPrint (above); EnString.c:199,240
// Length/IndexOf and :223 Hash; EnDebug.c:96 Print. Readback is not fsync.
class HCRecoveryGate
{
    protected static bool s_Admitted;
    protected static int s_Generation;
    protected static int s_Quarantine;
    protected static string s_Reason = "not_loaded";
    protected static string s_GroupPath;
    protected static int s_GroupLength;
    protected static int s_GroupHash;
    protected static bool s_GroupOpened;

    static void HCReset()
    {
        s_Admitted = false;
        s_Generation = 0;
        s_Quarantine = 3;
        s_Reason = "not_loaded";
        s_GroupPath = "";
        s_GroupLength = 0;
        s_GroupHash = 0;
        s_GroupOpened = false;
    }

    static void HCAdmit(int generation, string groupPath, int length, int checksum)
    {
        s_Generation = generation;
        s_GroupPath = groupPath;
        s_GroupLength = length;
        s_GroupHash = checksum;
        s_GroupOpened = false;
        s_Admitted = true;
        s_Quarantine = 0;
        s_Reason = "operator_paired_restore";
    }

    static bool HCRefuse(string reason)
    {
        // Latch the first refusal and emit once; later feature failures must
        // not obscure the native mismatch or create a per-tick log flood.
        if (!s_Admitted && s_Reason != "not_loaded") { return false; }
        // Fixed three high-risk stores, not a growing list of corrupt files.
        s_Admitted = false;
        s_Quarantine = 3;
        s_Reason = reason;
        Print("[HC Plan] HC-28 generation=" + s_Generation.ToString() + " recovery=quarantined quarantine=3 state=refused reason=" + s_Reason + " runtime=PENDING");
        return false;
    }

    static bool HCReady() { return s_Admitted; }
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

    static bool HCProtected(string path)
    {
        return path.IndexOf("$profile:HollowCountry/Groups/state/") == 0 || path.IndexOf("$profile:HollowCountry/world.json") == 0 || path.IndexOf("$profile:HollowCountry/escalation.json") == 0;
    }

    static bool HCAllowRead(string path)
    {
        if (!HCProtected(path)) { return true; }
        return s_Admitted;
    }

    static bool HCAllowWrite(string path)
    {
        if (!HCProtected(path)) { return true; }
        if (!s_Admitted) { return false; }
        // Missing group directory must never silently mint revision 1. Existing
        // highest state has to pass the paired baseline before any group write.
        if (path.IndexOf("$profile:HollowCountry/Groups/state/") == 0 && !s_GroupOpened) { return HCRefuse("group_baseline_not_opened"); }
        return true;
    }

    static bool HCReadImage(string path, string text)
    {
        if (!HCProtected(path)) { return true; }
        if (!s_Admitted) { return false; }
        if (path.IndexOf("$profile:HollowCountry/Groups/state/state_") == 0 && !s_GroupOpened)
        {
            if (path != s_GroupPath || text.Length() != s_GroupLength || text.Hash() != s_GroupHash) { return HCRefuse("group_generation_mismatch"); }
            s_GroupOpened = true;
        }
        return true;
    }
}
