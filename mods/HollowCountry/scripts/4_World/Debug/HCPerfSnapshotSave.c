// w45 #138: retain a detached document and the existing verified temp/backup/copy
// protocol, one stage per module tick. Never delete intent on a failed stage.
// Native scripts-1.30.164289: 3_Game/tools/JsonFileLoader.c:85 MakeData;
// 1_Core/proto/EnSystem.c:397 FileExist, :528 DeleteFile, :531 CopyFile;
// EnString.c:199 Length; EnConvert.c:30 ToString. HCGroupIO owns bounded IO.
class HCPerfSnapshotSave : HCSaveJob
{
    protected ref HCDebugDocument m_Data;
    protected int m_Phase;
    protected string m_Path;
    protected int m_Limit;
    protected string m_Layers;
    protected string m_Routes;
    protected string m_Operational;
    protected string m_Stats;
    protected string m_Text;
    protected int m_Bytes;

    void HCBind(string path, HCDebugDocument data, int limit)
    {
        m_Path = path;
        m_Data = data;
        m_Limit = limit;
        this.HCDirty = true;
    }
    override string HCName() { return "DebugSnapshot"; }
    int HCBytes() { return m_Bytes; }

    override int HCStep()
    {
        bool ok = false;
        if (m_Phase < 4) { ok = HCEncode(m_Phase); }
        if (m_Phase == 4) { ok = HCWriteIntent(); }
        if (m_Phase == 5) { ok = HCBackup(); }
        if (m_Phase == 6) { ok = HCPromote(); }
        if (m_Phase == 7) { ok = HCClean(); }
        if (!ok) { return STEP_FAILED; }
        m_Phase++;
        if (m_Phase >= 8) { return STEP_DONE; }
        return STEP_MORE;
    }

    protected bool HCEncode(int phase)
    {
        if (!m_Data) { return false; }
        string error;
        if (phase == 0) { return JsonFileLoader<map<string, ref array<ref HCDebugPoint>>>.MakeData(m_Data.layers, m_Layers, error, false); }
        if (phase == 1) { return JsonFileLoader<array<ref HCDebugRoute>>.MakeData(m_Data.routes, m_Routes, error, false); }
        if (phase == 2) { return JsonFileLoader<array<string>>.MakeData(m_Data.operational, m_Operational, error, false); }
        return JsonFileLoader<array<ref HCDebugLayerStat>>.MakeData(m_Data.layerStats, m_Stats, error, false);
    }

    protected bool HCWriteIntent()
    {
        m_Text = "{\"version\":1,\"time\":" + m_Data.time.ToString() + ",\"map\":\"chernarusplus\",\"layers\":" + m_Layers + ",\"routes\":" + m_Routes;
        m_Text += ",\"layerStats\":" + m_Stats + ",\"operational\":" + m_Operational;
        m_Text += ",\"contributors\":" + m_Data.contributors.ToString() + ",\"truncated\":" + m_Data.truncated.ToString();
        m_Text += ",\"operationalTruncated\":" + m_Data.operationalTruncated.ToString() + "}";
        m_Bytes = m_Text.Length();
        if (m_Bytes < 1 || m_Bytes > m_Limit) { return false; }
        return HCGroupIO.WriteNew(m_Path + ".tmp", m_Text, m_Limit);
    }

    protected bool HCBackup()
    {
        if (!FileExist(m_Path)) { return true; }
        string previous;
        string backedUp;
        string backup = m_Path + ".bak";
        if (!HCGroupIO.Read(m_Path, m_Limit, previous)) { return false; }
        if (FileExist(backup) && !DeleteFile(backup)) { return false; }
        if (!CopyFile(m_Path, backup)) { return false; }
        return HCGroupIO.Read(backup, m_Limit, backedUp) && backedUp == previous;
    }

    protected bool HCPromote()
    {
        if (FileExist(m_Path) && !DeleteFile(m_Path)) { return false; }
        if (!CopyFile(m_Path + ".tmp", m_Path)) { return false; }
        string actual;
        return HCGroupIO.Read(m_Path, m_Limit, actual) && actual == m_Text;
    }

    protected bool HCClean() { return DeleteFile(m_Path + ".tmp"); }
}
