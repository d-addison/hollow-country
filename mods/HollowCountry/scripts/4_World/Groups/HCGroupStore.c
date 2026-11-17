// Original bounded native persistence. Readback is not fsync or a promise about
// power loss. Immutable intent/image/commit triples; never load an older ACL
// when the highest discovered revision is incomplete, corrupt or incompatible.
class HCGroupIO
{
    static bool Read(string path, int limit, out string text)
    {
        FileHandle handle = OpenFile(path, FileMode.READ);
        if (!handle) return false;
        int count = ReadFile(handle, text, limit + 1);
        CloseFile(handle);
        return count > 0 && count <= limit && text.Length() > 0 && text.Length() <= limit;
    }

    static bool WriteNew(string path, string text, int limit)
    {
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

class HCGroupStore
{
    protected string m_Root = "$profile:HollowCountry/Groups/state";
    protected ref HCGroupSettings m_Settings;
    protected int m_Latest;
    protected bool m_Fault;

    bool Fault()
    {
        m_Fault = true;
        Print("[HC Groups] persistence fault; service disabled, preserve state for recovery");
        return false;
    }

    static HCGroupSettings LoadSettings()
    {
        string root = "$profile:HollowCountry/Groups";
        if (!FileExist(root) && !MakeDirectory(root)) return null;
        string path = root + "/settings.json";
        HCGroupSettings settings = new HCGroupSettings;
        if (FileExist(path))
        {
            if (!HCGroupJson<HCGroupSettings>.Load(path, 8192, settings)) return null;
        }
        else if (!HCGroupJson<HCGroupSettings>.WriteNew(path, settings, 8192)) return null;
        if (!HCGroupRules.SettingsValid(settings)) return null;
        return settings;
    }

    string PathFor(string prefix, int revision)
    {
        return m_Root + "/" + prefix + revision.ToString() + ".json";
    }

    int RevisionInName(string name, string prefix)
    {
        if (name.IndexOf(prefix) != 0 || name.Length() < prefix.Length() + 6) return 0;
        int number = name.Substring(prefix.Length(), name.Length() - prefix.Length() - 5).ToInt();
        if (number < 1 || number > 1000000000 || prefix + number.ToString() + ".json" != name) return 0;
        return number;
    }

    bool Open(HCGroupSettings settings, out HCGroupState state)
    {
        m_Settings = settings;
        if (!HCGroupRules.SettingsValid(settings)) return Fault();
        if (!FileExist(m_Root))
        {
            if (!MakeDirectory(m_Root)) return Fault();
            state = new HCGroupState;
            state.WorldName = GetGame().GetWorldName();
            state.Revision = 1;
            return Save(state);
        }
        string filename;
        FileAttr attr;
        FindFileHandle handle = FindFile(m_Root + "/*", filename, attr, FindFileFlags.DIRECTORIES);
        if (!handle) return Fault();
        int highestIntent = 0;
        int highestImage = 0;
        int highestCommit = 0;
        int count = 0;
        bool valid = true;
        bool found = filename != "";
        while (found)
        {
            if (filename != "." && filename != "..")
            {
                count++;
                int intent = RevisionInName(filename, "intent_");
                int image = RevisionInName(filename, "state_");
                int commit = RevisionInName(filename, "commit_");
                if (attr == FileAttr.DIRECTORY || count > 3 * (settings.KeepRevisions + 2) || (intent == 0 && image == 0 && commit == 0))
                {
                    valid = false;
                    break;
                }
                highestIntent = Math.Max(highestIntent, intent);
                highestImage = Math.Max(highestImage, image);
                highestCommit = Math.Max(highestCommit, commit);
            }
            found = FindNextFile(handle, filename, attr);
        }
        CloseFindFile(handle);
        if (!valid || highestIntent < 1 || highestIntent != highestImage || highestImage != highestCommit) return Fault();
        string imageText;
        if (!HCGroupIO.Read(PathFor("state_", highestImage), settings.MaxStoreBytes, imageText)) return Fault();
        string error;
        HCGroupReceipt receipt;
        HCGroupReceipt intentReceipt;
        if (!HCGroupJson<HCGroupReceipt>.Load(PathFor("commit_", highestCommit), 1024, receipt) || !HCGroupJson<HCGroupReceipt>.Load(PathFor("intent_", highestIntent), 1024, intentReceipt) || !receipt || !intentReceipt) return Fault();
        if (!JsonFileLoader<HCGroupState>.LoadData(imageText, state, error) || !HCGroupRules.StateValid(state, settings, GetGame().GetWorldName())) return Fault();
        if (receipt.Version != 1 || intentReceipt.Version != 1 || receipt.WorldName != state.WorldName || intentReceipt.WorldName != state.WorldName || intentReceipt.Revision != receipt.Revision || intentReceipt.Length != receipt.Length || intentReceipt.Hash != receipt.Hash) return Fault();
        if (!HCGroupRules.LatestComplete(highestIntent, highestImage, highestCommit, receipt.Revision, state.Revision, receipt.Length, imageText.Length(), receipt.Hash, imageText.Hash())) return Fault();
        HCGroupRules.MigrateExplorers(state);
        state.Invitations.Clear();
        m_Latest = state.Revision;
        return true;
    }

    bool Save(HCGroupState state)
    {
        if (m_Fault || !state || state.Revision != m_Latest + 1 || !HCGroupRules.StateValid(state, m_Settings, GetGame().GetWorldName())) return Fault();
        // Serialize a clone so invitations remain ephemeral on disk without
        // discarding pending invitation transactions from the live service.
        string text;
        string error;
        HCGroupState disk;
        if (!JsonFileLoader<HCGroupState>.MakeData(state, text, error) || text.Length() > m_Settings.MaxStoreBytes || !JsonFileLoader<HCGroupState>.LoadData(text, disk, error) || !disk) return Fault();
        disk.Invitations.Clear();
        if (!JsonFileLoader<HCGroupState>.MakeData(disk, text, error) || text.Length() > m_Settings.MaxStoreBytes) return Fault();
        HCGroupReceipt receipt = new HCGroupReceipt;
        receipt.Revision = state.Revision;
        receipt.WorldName = state.WorldName;
        receipt.Length = text.Length();
        receipt.Hash = text.Hash();
        if (!HCGroupJson<HCGroupReceipt>.WriteNew(PathFor("intent_", state.Revision), receipt, 1024)) return Fault();
        if (!HCGroupIO.WriteNew(PathFor("state_", state.Revision), text, m_Settings.MaxStoreBytes)) return Fault();
        if (!HCGroupJson<HCGroupReceipt>.WriteNew(PathFor("commit_", state.Revision), receipt, 1024)) return Fault();
        m_Latest = state.Revision;
        // Only exact owned old triples are pruned after a verified new commit.
        // Partial pruning leaves highest intact; any failure disables mutations.
        int old = m_Latest - m_Settings.KeepRevisions;
        if (old > 0)
        {
            string oldIntent = PathFor("intent_", old);
            string oldImage = PathFor("state_", old);
            string oldCommit = PathFor("commit_", old);
            if (FileExist(oldIntent) && !DeleteFile(oldIntent)) return Fault();
            if (FileExist(oldImage) && !DeleteFile(oldImage)) return Fault();
            if (FileExist(oldCommit) && !DeleteFile(oldCommit)) return Fault();
        }
        return true;
    }
}
