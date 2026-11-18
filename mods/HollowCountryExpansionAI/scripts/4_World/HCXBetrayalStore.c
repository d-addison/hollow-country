// HC-5/#139. Server-owned durable group/identity memory, no player object key.
// Native scripts-1.30.164289: 1_Core/proto/EnSystem.c:397 FileExist,
// :525 MakeDirectory, :528 DeleteFile, :531 CopyFile;
// 3_Game/tools/JsonFileLoader.c:85 MakeData. HCGroupIO/HCGroupJson supply bounded
// reads and write-new/readback. Verified pending/backup/copy protocol, NOT rename
// atomicity. Uncertainty quarantines; validated publication can clear a stale guard.
// This is a synchronous event durability barrier, not a routine save loop.
class HCXAIBetrayalRow
{
    string GroupKey;
    string UID;
    int AtUtc;
}
class HCXAIBetrayalData
{
    int SchemaVersion = 1;
    int LastUtc;
    ref array<ref HCXAIBetrayalRow> Rows = new array<ref HCXAIBetrayalRow>();
}
class HCXBetrayalIO
{
    static const string PATH = "$profile:HollowCountry/betrayal.json";
    static const string PENDING = "$profile:HollowCountry/betrayal.pending.json";
    static const int MAX_BYTES = 65536;

    bool Exists() { return FileExist(PATH); }
    bool Blocked() { return FileExist(PENDING) || (!FileExist(PATH) && FileExist(PATH + ".bak")); }
    // Called only after the store validates PATH (including clock and row bounds).
    // PATH is the committed snapshot; a leftover staging file is never replayed.
    bool Recover()
    {
        if (!FileExist(PENDING)) { return !Blocked(); }
        return FileExist(PATH) && DeleteFile(PENDING) && !FileExist(PENDING);
    }
    HCXAIBetrayalData Load()
    {
        HCXAIBetrayalData loaded;
        if (!HCGroupJson<HCXAIBetrayalData>.Load(PATH, MAX_BYTES, loaded)) { return null; }
        return loaded;
    }
    bool Save(HCXAIBetrayalData data)
    {
        if (Blocked()) { return false; }
        string expected;
        string error;
        string staged;
        string before;
        string backup;
        string published;
        if (!JsonFileLoader<HCXAIBetrayalData>.MakeData(data, expected, error) || expected.Length() > MAX_BYTES) { return false; }
        MakeDirectory("$profile:HollowCountry");
        if (!HCGroupIO.WriteNew(PENDING, expected, MAX_BYTES) || !HCGroupIO.Read(PENDING, MAX_BYTES, staged) || staged != expected) { return false; }
        if (FileExist(PATH))
        {
            if (!HCGroupIO.Read(PATH, MAX_BYTES, before) || !CopyFile(PATH, PATH + ".bak")) { return false; }
            if (!HCGroupIO.Read(PATH + ".bak", MAX_BYTES, backup) || backup != before) { return false; }
        }
        if (!CopyFile(PENDING, PATH) || !HCGroupIO.Read(PATH, MAX_BYTES, published) || published != expected) { return false; }
        return DeleteFile(PENDING) && !FileExist(PENDING);
    }
}
class HCXBetrayalStore
{
    protected ref HCXBetrayalIO m_IO = new HCXBetrayalIO();
    protected ref HCXAIBetrayalData m_Data;
    protected bool m_Healthy;
    protected bool m_Validated;
    // Limits come from the existing expansion-ai-sites.json policy. Hard limits
    // keep loading, validation and synchronous event persistence bounded.
    protected int m_MaxRows = 128;
    protected int m_TtlSeconds = 172800;

    bool Configure(int maxRows, int ttlSeconds)
    {
        if (maxRows < 1 || maxRows > 128 || ttlSeconds < 1 || ttlSeconds > 2592000) { return false; }
        m_MaxRows = maxRows;
        m_TtlSeconds = ttlSeconds;
        return true;
    }
    bool Healthy() { return m_Healthy; }
    int Count()
    {
        if (!m_Data || !m_Data.Rows) { return 0; }
        return m_Data.Rows.Count();
    }
    bool ValidKey(string key) { return key != "" && key.Length() <= 128; }
    bool Validate(int nowUtc)
    {
        if (!m_Data || m_Data.SchemaVersion != 1 || !m_Data.Rows || m_Data.Rows.Count() > 128 || m_Data.LastUtc < 0 || m_Data.LastUtc > nowUtc) { return false; }
        foreach (HCXAIBetrayalRow row : m_Data.Rows)
        {
            if (!row || !this.ValidKey(row.GroupKey) || !this.ValidKey(row.UID) || row.AtUtc < 1 || row.AtUtc > m_Data.LastUtc) { return false; }
            int matches = 0;
            foreach (HCXAIBetrayalRow other : m_Data.Rows)
            {
                if (other && other.GroupKey == row.GroupKey && other.UID == row.UID) { matches++; }
            }
            if (matches != 1) { return false; }
        }
        return true;
    }
    // Returns whether rows changed; never writes on a read or an unchanged open.
    bool Prune(int nowUtc, int keepRows)
    {
        bool changed = false;
        int index = m_Data.Rows.Count() - 1;
        while (index >= 0)
        {
            if (nowUtc - m_Data.Rows[index].AtUtc >= m_TtlSeconds)
            {
                m_Data.Rows.RemoveOrdered(index);
                changed = true;
            }
            index--;
        }
        while (m_Data.Rows.Count() > keepRows)
        {
            int oldest = 0;
            int scan = 1;
            while (scan < m_Data.Rows.Count())
            {
                if (m_Data.Rows[scan].AtUtc < m_Data.Rows[oldest].AtUtc) { oldest = scan; }
                scan++;
            }
            m_Data.Rows.RemoveOrdered(oldest);
            changed = true;
        }
        return changed;
    }
    bool Persist(int nowUtc)
    {
        m_Data.LastUtc = nowUtc;
        if (!m_IO.Save(m_Data)) { m_Healthy = false; return false; }
        return true;
    }
    bool Open(int nowUtc)
    {
        m_Healthy = false;
        m_Validated = false;
        m_Data = null;
        if (nowUtc < 1 || !m_IO) { return false; }
        if (m_IO.Exists()) { m_Data = m_IO.Load(); }
        else
        {
            if (m_IO.Blocked()) { return false; }
            m_Data = new HCXAIBetrayalData();
        }
        if (!this.Validate(nowUtc)) { return false; }
        if (!m_IO.Recover())
        {
            Print("[HC Plan] HC-5 betrayal recovery refused: back up betrayal*.json; validate/restore betrayal.json then remove betrayal.pending.json manually; runtime=PENDING");
            return false;
        }
        m_Validated = true;
        m_Healthy = true;
        if (this.Prune(nowUtc, m_MaxRows)) { return this.Persist(nowUtc); }
        return true;
    }
    bool Has(string groupKey, string uid)
    {
        if (!m_Validated || !m_Data || !m_Data.Rows) { return false; }
        int nowUtc = HCGroupClock.Utc();
        if (nowUtc < 1 || nowUtc < m_Data.LastUtc) { return false; }
        foreach (HCXAIBetrayalRow row : m_Data.Rows)
        {
            if (row.GroupKey == groupKey && row.UID == uid && nowUtc - row.AtUtc < m_TtlSeconds) { return true; }
        }
        return false;
    }
    bool Remember(string groupKey, string uid, int nowUtc)
    {
        if (!m_Healthy) { return false; }
        // Invalid/unconfigured group names skip this event, never poison signals.
        if (!this.ValidKey(groupKey) || !this.ValidKey(uid)) { return false; }
        if (nowUtc < 1 || nowUtc < m_Data.LastUtc) { m_Healthy = false; return false; }
        bool changed = this.Prune(nowUtc, m_MaxRows);
        foreach (HCXAIBetrayalRow row : m_Data.Rows)
        {
            if (row.GroupKey == groupKey && row.UID == uid)
            {
                if (changed) { return this.Persist(nowUtc); }
                return true;
            }
        }
        this.Prune(nowUtc, m_MaxRows - 1);
        HCXAIBetrayalRow receipt = new HCXAIBetrayalRow();
        receipt.GroupKey = groupKey;
        receipt.UID = uid;
        receipt.AtUtc = nowUtc;
        m_Data.Rows.Insert(receipt);
        return this.Persist(nowUtc);
    }
}
