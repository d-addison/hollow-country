// Fixed private profile directory, owned immutable triples, bounded enumeration.
// Readback does not promise fsync/power-loss atomicity. Incomplete highest
// revision can be discarded only after the immediately prior commit validates.
class HCEventJournalIO
{
    protected string m_Root = "$profile:HollowCountry/Events/state";
    protected string m_Refusal;
    // Names the directory in the refusal line; subclasses set their own (reward ledger).
    protected string m_Label = "journal directory";
    // Last directory refusal; the log line prints once per reason change (Names/Start are boot-time).
    string Refusal() { return m_Refusal; }
    bool HCRefuse(string reason)
    {
        if (m_Refusal != reason)
        {
            m_Refusal = reason;
            Print("[HC Events] " + m_Label + " refused reason=" + reason);
        }
        return false;
    }
    bool Ensure()
    {
        if (!FileExist("$profile:HollowCountry") && !MakeDirectory("$profile:HollowCountry")) { return HCRefuse("profile_directory_unavailable"); }
        if (!FileExist("$profile:HollowCountry/Events") && !MakeDirectory("$profile:HollowCountry/Events")) { return HCRefuse("events_directory_unavailable"); }
        if (!FileExist(m_Root) && !MakeDirectory(m_Root)) { return HCRefuse("state_directory_unavailable"); }
        return true;
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
    string HCPath(string name) { return m_Root + "/" + name; }
    bool Exists(string name) { return FileExist(m_Root + "/" + name); }
    // Optional retained read supplies one <=4096-byte verification chunk.
    // Synchronous callers retain their existing read contract.
    protected FileHandle m_ReadHandle;
    protected bool m_ReadOpen;
    protected int m_ReadCount;
    int HCReadCount() { return m_ReadCount; }
    void HCCloseRead()
    {
        if (m_ReadOpen) { CloseFile(m_ReadHandle); m_ReadOpen = false; }
    }
    string Read(string name, int limit, bool retained = false)
    {
        string text;
        FileHandle handle;
        if (retained && m_ReadOpen) { handle = m_ReadHandle; }
        else { handle = OpenFile(m_Root + "/" + name, FileMode.READ); }
        m_ReadCount = -1;
        if (!handle) return "";
        int count = ReadFile(handle, text, limit + 1);
        m_ReadCount = count;
        if (retained && count > 0)
        {
            m_ReadHandle = handle;
            m_ReadOpen = true;
        }
        else
        {
            CloseFile(handle);
            m_ReadOpen = false;
        }
        if (count < 1 || text.Length() != count || (!retained && count > limit)) return "";
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
    // Copy every surviving top-revision file before deleting any of them.
    // A separate attempt directory preserves earlier crashes of a reused revision.
    protected string m_TornDirectory;
    string HCTornDirectory() { return m_TornDirectory; }
    bool PreserveTorn(array<string> names, int revision)
    {
        string root = "$profile:HollowCountry/Events/torn";
        if (!FileExist(root) && !MakeDirectory(root)) { return false; }
        string target;
        int attempt = 0;
        while (attempt < 1024)
        {
            target = root + "/" + revision.ToString() + "-" + attempt.ToString();
            if (!FileExist(target)) { break; }
            attempt++;
        }
        if (attempt >= 1024 || !MakeDirectory(target)) { return false; }
        foreach (string name : names)
        {
            if (!Exists(name)) { continue; }
            // Verify raw bytes, including an empty torn file, before any delete.
            string original = Read(name, 4194304);
            int originalCount = HCReadCount();
            if (originalCount < 0 || originalCount > 4194304 || original.Length() != originalCount) { return false; }
            string copy = target + "/" + name;
            if (!CopyFile(HCPath(name), copy) || !FileExist(copy)) { return false; }
            FileHandle handle = OpenFile(copy, FileMode.READ);
            if (!handle) { return false; }
            string actual;
            actual = "";
            int count = ReadFile(handle, actual, 4194305);
            CloseFile(handle);
            if (count != originalCount || actual != original) { return false; }
        }
        foreach (string obsolete : names)
        {
            if (Exists(obsolete) && !Remove(obsolete)) { return false; }
        }
        m_TornDirectory = "Events/torn/" + revision.ToString() + "-" + attempt.ToString();
        return true;
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
        int commitCount = m_IO.HCReadCount();
        if (m_IO.Exists(Name("commit-", latest)) && (commitCount < 0 || commitCount > 2048 || commit.Length() != commitCount)) { Fault(); return null; }
        // Only an absent commit or a strict prefix of its intent is torn.
        // Present, complete but mismatched receipts/images must fault in HCLoadRevision.
        bool torn = !m_IO.Exists(Name("commit-", latest));
        if (!torn && commit.Length() < intent.Length() && (commit == "" || intent.IndexOf(commit) == 0)) { torn = true; }
        int loaded = latest;
        if (torn) { loaded--; }
        if (loaded < 1) { Fault(); return null; }
        HCEventRuntimeState state = HCLoadRevision(loaded, world);
        if (!state) { Fault(); return null; }
        if (torn)
        {
            array<string> names = new array<string>;
            names.Insert(Name("intent-", latest));
            names.Insert(Name("image-", latest));
            names.Insert(Name("commit-", latest));
            if (!m_IO.PreserveTorn(names, latest)) { Fault(); return null; }
            Print("[HC Events] journal recovered torn_revision=" + latest.ToString() + " loaded=" + loaded.ToString() + " preserved=" + m_IO.HCTornDirectory());
        }
        m_Latest = loaded;
        // Normalize legacy eight-revision journals too. Seven retained triples
        // plus all three new files = 24 entries, even before prune stages 10..12.
        // A crash during pruning only removes old files; it cannot raise this bound.
        array<string> retained = m_IO.Names();
        if (!retained) { Fault(); return null; }
        foreach (string retainedName : retained)
        {
            int revision = RevisionInName(retainedName, "intent-");
            if (revision == 0) { revision = RevisionInName(retainedName, "image-"); }
            if (revision == 0) { revision = RevisionInName(retainedName, "commit-"); }
            if (revision > 0 && revision <= loaded - 7 && !m_IO.Remove(retainedName)) { Fault(); return null; }
        }
        return state;
    }
    // No recursive fallback: the predecessor must pass every original check.
    protected HCEventRuntimeState HCLoadRevision(int revision, string world)
    {
        string intent = m_IO.Read(Name("intent-", revision), 2048);
        string commit = m_IO.Read(Name("commit-", revision), 2048);
        if (intent == "" || intent != commit) { return null; }
        HCEventJournalReceipt receipt = m_Codec.Receipt(intent);
        if (!receipt || receipt.Version != 1 || receipt.Revision != revision || receipt.WorldName != world) { return null; }
        string image = m_IO.Read(Name("image-", revision), m_Settings.MaxStoreBytes);
        if (image == "" || receipt.Length != image.Length() || receipt.Hash != m_Codec.Digest(image)) { return null; }
        HCEventRuntimeState state = m_Codec.Decode(image);
        if (!HCEventRuntimePolicy.StateValid(state) || state.Revision != revision || state.Director.WorldName != world)
        {
            Print("[HC Events] journal schema/state admission failed; preserve image, no reset or fallback");
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
    // Maintenance continuation: no revision becomes visible before commit readback.
    // Existing mutation/ingress barriers can drain this same continuation synchronously.
    protected ref HCEventRuntimeState m_Pending;
    protected ref HCStagedSaveImage m_Writer;
    protected int m_SaveStage = -1;
    protected string m_NextImage;
    protected string m_NextReceipt;
    protected bool m_CheckOpen;
    protected int m_CheckOffset;
    string HCStageName()
    {
        if (m_SaveStage == 0) { return "journal_validate"; }
        if (m_SaveStage == 1) { return "journal_inventory"; }
        if (m_SaveStage == 2) { return "journal_prior_image"; }
        if (m_SaveStage == 3) { return "journal_prior_intent"; }
        if (m_SaveStage == 4) { return "journal_prior_commit"; }
        if (m_SaveStage == 5) { return "journal_encode"; }
        if (m_SaveStage == 6) { return "journal_receipt"; }
        if (m_SaveStage == 7) { return "journal_write_intent"; }
        if (m_SaveStage == 8) { return "journal_write_image"; }
        if (m_SaveStage == 9) { return "journal_write_commit"; }
        if (m_SaveStage == 10) { return "journal_prune_intent"; }
        if (m_SaveStage == 11) { return "journal_prune_image"; }
        if (m_SaveStage == 12) { return "journal_prune_commit"; }
        return "journal_publish";
    }

    bool HCBeginSave(HCEventRuntimeState state)
    {
        if (m_Fault || m_SaveStage >= 0 || !state) { return false; }
        m_Pending = state;
        m_SaveStage = 0;
        return true;
    }

    protected int HCStageFault()
    {
        m_IO.HCCloseRead();
        m_CheckOpen = false;
        m_Writer = null;
        m_Pending = null;
        m_SaveStage = -1;
        Fault();
        return HCSaveJob.STEP_FAILED;
    }

    // One <=4096-byte read/compare per call, including open/close at ends.
    protected int HCCheckPrior(string name, string expected)
    {
        if (!m_CheckOpen) { m_CheckOpen = true; m_CheckOffset = 0; }
        string piece = m_IO.Read(name, HCStagedSaveImage.HC_CHUNK_BYTES - 1, true);
        int count = m_IO.HCReadCount();
        if (count < 0 || count != piece.Length() || m_CheckOffset + count > expected.Length()) { return HCSaveJob.STEP_FAILED; }
        if (count == 0)
        {
            if (m_CheckOffset != expected.Length() || m_CheckOffset < 1) { return HCSaveJob.STEP_FAILED; }
            m_CheckOpen = false;
            return HCSaveJob.STEP_DONE;
        }
        if (piece != expected.Substring(m_CheckOffset, count)) { return HCSaveJob.STEP_FAILED; }
        m_CheckOffset += count;
        return HCSaveJob.STEP_MORE;
    }

    int HCStepSave()
    {
        if (m_Fault || m_SaveStage < 0 || !m_Pending) { return HCStageFault(); }
        int result = HCSaveJob.STEP_DONE;
        if (m_SaveStage == 0)
        {
            if (!HCEventRuntimePolicy.StateValid(m_Pending) || m_Pending.Director.WorldName != m_World || m_Pending.Revision != m_Latest + 1) { return HCStageFault(); }
        }
        else if (m_SaveStage == 1)
        {
            if (Highest() != m_Latest) { return HCStageFault(); }
        }
        else if (m_SaveStage >= 2 && m_SaveStage <= 4 && m_Latest > 0)
        {
            string prefix = "image-";
            string expected = m_Image;
            if (m_SaveStage == 3) { prefix = "intent-"; expected = m_Receipt; }
            if (m_SaveStage == 4) { prefix = "commit-"; expected = m_Receipt; }
            result = HCCheckPrior(Name(prefix, m_Latest), expected);
        }
        else if (m_SaveStage == 5)
        {
            m_NextImage = m_Codec.Encode(m_Pending);
            if (m_NextImage.Length() < 1 || m_NextImage.Length() > m_Settings.MaxStoreBytes) { return HCStageFault(); }
        }
        else if (m_SaveStage == 6)
        {
            HCEventJournalReceipt receipt = new HCEventJournalReceipt;
            receipt.Revision = m_Pending.Revision;
            receipt.WorldName = m_World;
            receipt.Length = m_NextImage.Length();
            receipt.Hash = m_Codec.Digest(m_NextImage);
            m_NextReceipt = m_Codec.EncodeReceipt(receipt);
        }
        else if (m_SaveStage >= 7 && m_SaveStage <= 9)
        {
            if (!m_Writer)
            {
                string writePrefix = "intent-";
                string text = m_NextReceipt;
                int limit = 2048;
                if (m_SaveStage == 8) { writePrefix = "image-"; text = m_NextImage; limit = m_Settings.MaxStoreBytes; }
                if (m_SaveStage == 9) { writePrefix = "commit-"; }
                m_Writer = new HCStagedSaveImage;
                if (!m_Writer.BeginNew(m_IO.HCPath(Name(writePrefix, m_Pending.Revision)), text, limit)) { return HCStageFault(); }
                return HCSaveJob.STEP_MORE;
            }
            result = m_Writer.HCStepImage();
            if (result == HCSaveJob.STEP_DONE) { m_Writer = null; }
        }
        else if (m_SaveStage >= 10 && m_SaveStage <= 12)
        {
            int old = m_Pending.Revision - 7;
            if (old > 0)
            {
                string oldPrefix = "intent-";
                if (m_SaveStage == 11) { oldPrefix = "image-"; }
                if (m_SaveStage == 12) { oldPrefix = "commit-"; }
                string obsolete = Name(oldPrefix, old);
                if (m_IO.Exists(obsolete) && !m_IO.Remove(obsolete)) { return HCStageFault(); }
            }
        }
        else if (m_SaveStage == 13)
        {
            m_Latest = m_Pending.Revision;
            m_Image = m_NextImage;
            m_Receipt = m_NextReceipt;
            m_NextImage = "";
            m_NextReceipt = "";
            m_Pending = null;
            m_SaveStage = -1;
            return HCSaveJob.STEP_DONE;
        }
        if (result == HCSaveJob.STEP_FAILED) { return HCStageFault(); }
        if (result == HCSaveJob.STEP_DONE) { m_SaveStage++; }
        return HCSaveJob.STEP_MORE;
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
        // Exactly seven committed revisions; skip absent owned filenames.
        int old = m_Latest - 7;
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
