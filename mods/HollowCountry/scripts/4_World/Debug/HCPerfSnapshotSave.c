// w45 #138: retain a detached document and the existing verified temp/backup/copy
// protocol, resumable row encoding and separate assembly/write stages. Never delete intent on a failed stage.
// Native scripts-1.30.164289: 3_Game/tools/JsonFileLoader.c:85 MakeData;
// 1_Core/proto/EnSystem.c:397 FileExist, :528 DeleteFile, :531 CopyFile;
// EnScript.c:380/852 Count, :887/897 map GetElement/GetKey;
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
    protected int m_Row;
    protected int m_Layer;
    protected bool m_LayerOpen;

    void HCBind(string path, HCDebugDocument data, int limit)
    {
        m_Path = path;
        m_Data = data;
        m_Limit = limit;
        this.HCDirty = true;
    }
    override string HCName() { return "DebugSnapshot"; }
    int HCBytes() { return m_Bytes; }
    bool HCNeedsFlush() { return m_Phase >= 5; }

    override int HCStep()
    {
        bool ok = false;
        if (m_Phase < 4)
        {
            int encoded = HCEncode(m_Phase);
            if (encoded < 0) { return STEP_FAILED; }
            if (encoded == 0) { return STEP_MORE; }
            ok = true;
            m_Row = 0;
        }
        if (m_Phase == 4) { ok = HCWriteIntent(); }
        if (m_Phase == 5) { ok = HCBackup(); }
        if (m_Phase == 6) { ok = HCPromote(); }
        if (m_Phase == 7) { ok = HCClean(); }
        if (!ok) { return STEP_FAILED; }
        m_Phase++;
        if (m_Phase >= 8) { return STEP_DONE; }
        return STEP_MORE;
    }

    // A point, route (already capped to 64 vertices), string or stat is the
    // atomic native JSON unit. Encode returns -1 failed, 0 retained, 1 complete. Never re-encode a whole captured collection.
    protected int HCEncode(int phase)
    {
        if (!m_Data) { return -1; }
        if (phase == 0) { return HCEncodeLayer(); }
        string encoded;
        string error;
        if (phase == 1)
        {
            if (m_Row == 0) { m_Routes = "["; }
            if (m_Row < m_Data.routes.Count())
            {
                HCDebugRoute route = m_Data.routes[m_Row];
                if (!JsonFileLoader<HCDebugRoute>.MakeData(route, encoded, error, false)) { return -1; }
                if (m_Row > 0) { m_Routes += ","; }
                m_Routes += encoded;
                m_Row++;
                return 0;
            }
            m_Routes += "]";
        }
        if (phase == 2)
        {
            if (m_Row == 0) { m_Operational = "["; }
            if (m_Row < m_Data.operational.Count())
            {
                string operational = m_Data.operational[m_Row];
                encoded = HCQuote(operational);
                if (m_Row > 0) { m_Operational += ","; }
                m_Operational += encoded;
                m_Row++;
                return 0;
            }
            m_Operational += "]";
        }
        if (phase == 3)
        {
            if (m_Row == 0) { m_Stats = "["; }
            if (m_Row < m_Data.layerStats.Count())
            {
                HCDebugLayerStat stat = m_Data.layerStats[m_Row];
                if (!JsonFileLoader<HCDebugLayerStat>.MakeData(stat, encoded, error, false)) { return -1; }
                if (m_Row > 0) { m_Stats += ","; }
                m_Stats += encoded;
                m_Row++;
                return 0;
            }
            m_Stats += "]";
        }
        if (phase == 3 && !HCAssemble()) { return -1; }
        return 1;
    }

    // The native JsonSerializer writes class instances, not a bare string, so
    // keys and operational lines are quoted here. Short texts only.
    static string HCQuote(string text)
    {
        string quoted = "\"";
        int length = text.Length();
        for (int index = 0; index < length; index++)
        {
            string letter = text.Get(index);
            int code = letter.ToAscii();
            if (letter == "\"" || letter == "\\") { quoted += "\\" + letter; }
            else if (code >= 0 && code < 32) { quoted += " "; }
            else { quoted += letter; }
        }
        return quoted + "\"";
    }

    protected int HCEncodeLayer()
    {
        if (m_Layer == 0 && !m_LayerOpen) { m_Layers = "{"; }
        if (m_Layer >= m_Data.layers.Count())
        {
            m_Layers += "}";
            return 1;
        }
        string encoded;
        string error;
        if (!m_LayerOpen)
        {
            string key = m_Data.layers.GetKey(m_Layer);
            encoded = HCQuote(key);
            if (m_Layer > 0) { m_Layers += ","; }
            m_Layers += encoded + ":[";
            m_LayerOpen = true;
            m_Row = 0;
            return 0;
        }
        array<ref HCDebugPoint> points = m_Data.layers.GetElement(m_Layer);
        if (m_Row < points.Count())
        {
            HCDebugPoint point = points[m_Row];
            if (!JsonFileLoader<HCDebugPoint>.MakeData(point, encoded, error, false)) { return -1; }
            if (m_Row > 0) { m_Layers += ","; }
            m_Layers += encoded;
            m_Row++;
            return 0;
        }
        m_Layers += "]";
        m_Layer++;
        m_LayerOpen = false;
        return 0;
    }

    protected bool HCAssemble()
    {
        m_Text = "{\"version\":1,\"time\":" + m_Data.time.ToString() + ",\"map\":\"chernarusplus\",\"layers\":" + m_Layers + ",\"routes\":" + m_Routes;
        m_Text += ",\"layerStats\":" + m_Stats + ",\"operational\":" + m_Operational;
        m_Text += ",\"contributors\":" + m_Data.contributors.ToString() + ",\"truncated\":" + m_Data.truncated.ToString();
        m_Text += ",\"operationalTruncated\":" + m_Data.operationalTruncated.ToString() + "}";
        m_Bytes = m_Text.Length();
        return m_Bytes > 0 && m_Bytes <= m_Limit;
    }

    protected bool HCWriteIntent()
    {
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
