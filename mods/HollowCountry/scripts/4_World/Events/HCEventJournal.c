// Fixed private profile directory, owned immutable triples, bounded enumeration.
// Readback does not promise fsync/power-loss atomicity. Incomplete highest
// revision fails closed; recovery is an explicit operator operation offline.
class HCEventJournalIO
{
    protected string m_Root = "$profile:HollowCountry/Events/state";
    bool Ensure()
    {
        if (!FileExist("$profile:HollowCountry") && !MakeDirectory("$profile:HollowCountry")) return false;
        if (!FileExist("$profile:HollowCountry/Events") && !MakeDirectory("$profile:HollowCountry/Events")) return false;
        return FileExist(m_Root) || MakeDirectory(m_Root);
    }
    array<string> Names()
    {
        if (!Ensure()) return null;
        array<string> names = new array<string>();
        string name;
        FileAttr attributes;
        FindFileHandle handle = FindFile(m_Root + "/*", name, attributes, FindFileFlags.ALL);
        if (!handle) return names;
        bool more = name != "";
        while (more)
        {
            if (name != "." && name != "..")
            {
                if (attributes == FileAttr.DIRECTORY || names.Count() >= 27)
                {
                    CloseFindFile(handle);
                    return null;
                }
                names.Insert(name);
            }
            more = FindNextFile(handle, name, attributes);
        }
        CloseFindFile(handle);
        return names;
    }
    bool Exists(string name) { return FileExist(m_Root + "/" + name); }
    string Read(string name, int limit)
    {
        string text;
        FileHandle handle = OpenFile(m_Root + "/" + name, FileMode.READ);
        if (!handle) return "";
        int count = ReadFile(handle, text, limit + 1);
        CloseFile(handle);
        if (count < 1 || count > limit || text.Length() > limit) return "";
        return text;
    }
    bool WriteNew(string name, string text, int limit)
    {
        if (Exists(name) || text.Length() < 1 || text.Length() > limit) return false;
        FileHandle handle = OpenFile(m_Root + "/" + name, FileMode.WRITE);
        if (!handle) return false;
        FPrint(handle, text);
        CloseFile(handle);
        return Read(name, limit) == text;
    }
    bool Remove(string name) { return DeleteFile(m_Root + "/" + name); }
}
class HCEventCodec
{
    string Encode(HCEventRuntimeState state)
    {
        string text;
        string error;
        if (!JsonFileLoader<HCEventRuntimeState>.MakeData(state, text, error, false)) return "";
        return text;
    }
    HCEventRuntimeState Decode(string text)
    {
        HCEventRuntimeState state;
        string error;
        if (!JsonFileLoader<HCEventRuntimeState>.LoadData(text, state, error)) return null;
        return state;
    }
    string EncodeReceipt(HCEventJournalReceipt receipt)
    {
        string text;
        string error;
        if (!JsonFileLoader<HCEventJournalReceipt>.MakeData(receipt, text, error, false)) return "";
        return text;
    }
    HCEventJournalReceipt Receipt(string text)
    {
        HCEventJournalReceipt receipt;
        string error;
        if (!JsonFileLoader<HCEventJournalReceipt>.LoadData(text, receipt, error)) return null;
        return receipt;
    }
    int Digest(string text) { return text.Hash(); }
}
class HCEventJournal : HCEventPersistence
{
    protected ref HCEventJournalIO m_IO;
    protected ref HCEventCodec m_Codec;
    protected ref HCEventSettings m_Settings;
    protected int m_Latest = 0;
    protected string m_Image;
    protected string m_Receipt;
    protected string m_World;
    protected bool m_Fault = false;

    void HCEventJournal(HCEventSettings settings)
    {
        m_Settings = settings;
        m_IO = new HCEventJournalIO;
        m_Codec = new HCEventCodec;
    }
    bool Fault()
    {
        m_Fault = true;
        Print("[HC Events] immutable journal fault; preserve files, explicit recovery required");
        return false;
    }
    string Name(string prefix, int revision)
    {
        return prefix + revision.ToString() + ".json";
    }
    int RevisionInName(string name, string prefix)
    {
        int start = prefix.Length();
        int count = name.Length() - start - 5;
        if (name.IndexOf(prefix) != 0 || count < 1 || count > 9)
        {
            return 0;
        }
        string number = name.Substring(start, count);
        int revision = number.ToInt();
        if (revision < 1 || revision >= 1000000000 || Name(prefix, revision) != name)
        {
            return 0;
        }
        return revision;
    }
    int Highest()
    {
        array<string> names = m_IO.Names();
        if (!names || names.Count() > 27)
        {
            Fault();
            return -1;
        }
        int highest = 0;
        foreach (string name : names)
        {
            int revision = RevisionInName(name, "intent-");
            if (revision == 0)
            {
                revision = RevisionInName(name, "image-");
            }
            if (revision == 0)
            {
                revision = RevisionInName(name, "commit-");
            }
            if (revision == 0)
            {
                Fault();
                return -1;
            }
            highest = Math.Max(highest, revision);
        }
        return highest;
    }
    override HCEventRuntimeState Load(string world)
    {
        if (m_Fault || !HCEventRuntimePolicy.SettingsValid(m_Settings) || !HCEventDirector.TextValid(world, 96))
        {
            return null;
        }
        m_World = world;
        int latest = Highest();
        if (latest < 0)
        {
            return null;
        }
        m_Latest = latest;
        if (latest == 0)
        {
            m_Image = "";
            m_Receipt = "";
            HCEventRuntimeState fresh = new HCEventRuntimeState;
            fresh.Director = HCEventDirector.Initialize(world, "empty-journal");
            return fresh;
        }
        string intent = m_IO.Read(Name("intent-", latest), 2048);
        string commit = m_IO.Read(Name("commit-", latest), 2048);
        string image = m_IO.Read(Name("image-", latest), m_Settings.MaxStoreBytes);
        HCEventJournalReceipt receipt = m_Codec.Receipt(intent);
        HCEventRuntimeState state = m_Codec.Decode(image);
        if (intent == "" || intent != commit || !receipt || receipt.Version != 1)
        {
            Fault();
            return null;
        }
        if (receipt.Revision != latest || receipt.WorldName != world || receipt.Length != image.Length() || receipt.Hash != m_Codec.Digest(image))
        {
            Fault();
            return null;
        }
        if (!HCEventRuntimePolicy.StateValid(state) || state.Revision != latest || state.Director.WorldName != world)
        {
            Fault();
            return null;
        }
        m_Image = image;
        m_Receipt = intent;
        return state;
    }
    override HCEventRuntimeState Clone(HCEventRuntimeState state)
    {
        if (!state)
        {
            return null;
        }
        return m_Codec.Decode(m_Codec.Encode(state));
    }
    override bool Save(HCEventRuntimeState state)
    {
        if (m_Fault || !HCEventRuntimePolicy.StateValid(state) || state.Director.WorldName != m_World)
        {
            return false;
        }
        if (state.Revision != m_Latest + 1 || Highest() != m_Latest)
        {
            return Fault();
        }
        if (m_Latest > 0 && m_IO.Read(Name("image-", m_Latest), m_Settings.MaxStoreBytes) != m_Image)
        {
            return Fault();
        }
        if (m_Latest > 0)
        {
            if (m_IO.Read(Name("intent-", m_Latest), 2048) != m_Receipt || m_IO.Read(Name("commit-", m_Latest), 2048) != m_Receipt)
            {
                return Fault();
            }
        }
        string image = m_Codec.Encode(state);
        if (image.Length() < 1 || image.Length() > m_Settings.MaxStoreBytes)
        {
            return false;
        }
        HCEventJournalReceipt receipt = new HCEventJournalReceipt;
        receipt.Revision = state.Revision;
        receipt.WorldName = m_World;
        receipt.Length = image.Length();
        receipt.Hash = m_Codec.Digest(image);
        string intent = m_Codec.EncodeReceipt(receipt);
        if (!m_IO.WriteNew(Name("intent-", state.Revision), intent, 2048))
        {
            return Fault();
        }
        if (!m_IO.WriteNew(Name("image-", state.Revision), image, m_Settings.MaxStoreBytes))
        {
            return Fault();
        }
        if (!m_IO.WriteNew(Name("commit-", state.Revision), intent, 2048))
        {
            return Fault();
        }
        m_Latest = state.Revision;
        m_Image = image;
        m_Receipt = intent;
        // Exactly eight committed revisions; skip absent owned filenames.
        int old = m_Latest - 8;
        if (old > 0)
        {
            array<string> prefixes = new array<string>();
            prefixes.Insert("intent-");
            prefixes.Insert("image-");
            prefixes.Insert("commit-");
            foreach (string prefix : prefixes)
            {
                string name = Name(prefix, old);
                if (m_IO.Exists(name) && !m_IO.Remove(name))
                {
                    return Fault();
                }
            }
        }
        return true;
    }
}
