// Public mission map beacon: wire constants, server read model and the client
// store both map renderers read. The server alone decides what is public; the
// client validates every pushed snapshot and only ever displays it. There is no
// client request for this data.
// Native scripts-1.30.164289: 3_Game/gameplay.c:104-117 ScriptRPC/Send;
// 1_Core/proto/Serializer.c:57 Write/Read; 3_Game/Global/Game.c:914 GetTickTime;
// 1_Core/proto/EnDebug.c:96 Print; 1_Core/proto/EnMath.c:225 AbsFloat;
// 1_Core/proto/EnConvert.c:30 int.ToString; 1_Core/proto/EnString.c:171
// Length/ToLower. ID 4853803 had no match in mods/ or the native scripts.
// Wire (one reliable push, full snapshot, replaces the previous one):
//   int version, int sequence, int count (0..MAX_ROWS), then per row
//   string id, string kind, string title, string place, float x, float z,
//   float radius, int remainingSeconds.
enum HCBeaconWire
{
    VERSION = 1,
    RPC_PUBLIC = 4853803,
    MAX_ROWS = 16,
    MAX_TEXT = 64,
    MAX_REMAINING = 86400
}

// Server read model: one committed public mission as the runtime reports it.
class HCEventBeaconSource
{
    string Id;
    int Family = 0;
    bool Cache = false;
    vector Source;
    int Expires = 0;
}

class HCBeaconRow
{
    string Id;
    string Kind;
    string Title;
    string Place;
    float X = 0;
    float Z = 0;
    float Radius = 0;
    int RemainingSeconds = 0;
    // Client tick time when the snapshot arrived; the countdown is local.
    float ReceivedAt = 0;
}

class HCMissionBeaconStore
{
    protected static ref HCMissionBeaconStore s_Instance;
    protected ref array<ref HCBeaconRow> m_Rows = new array<ref HCBeaconRow>();
    protected int m_Version = 0;
    protected int m_Sequence = 0;
    protected string m_Refusal;
    protected string m_RefusalLogged;
    protected float m_LogWindow = -100;
    protected int m_LogCount = 0;

    static HCMissionBeaconStore Get()
    {
        if (!s_Instance) { s_Instance = new HCMissionBeaconStore; }
        return s_Instance;
    }

    // Bumps on every accepted snapshot and every expiry pruned by Poll.
    int Version() { return m_Version; }
    int Count() { return m_Rows.Count(); }
    string Refusal() { return m_Refusal; }
    HCBeaconRow At(int index)
    {
        if (index < 0 || index >= m_Rows.Count()) { return null; }
        return m_Rows[index];
    }

    void Clear()
    {
        if (m_Rows.Count() > 0) { m_Version = m_Version + 1; }
        m_Rows.Clear();
        m_Refusal = "";
        m_RefusalLogged = "";
    }

    int Remaining(HCBeaconRow row, float now)
    {
        if (!row) { return 0; }
        float elapsed = now - row.ReceivedAt;
        if (elapsed != elapsed || elapsed < 0) { elapsed = 0; }
        return row.RemainingSeconds - Math.Floor(elapsed);
    }

    // Drops rows whose server-supplied countdown ran out; a lost end push can
    // therefore never leave a stale zone on the map.
    int Poll(float now)
    {
        for (int index = m_Rows.Count() - 1; index >= 0; index--)
        {
            if (Remaining(m_Rows[index], now) <= 0)
            {
                m_Rows.RemoveOrdered(index);
                m_Version = m_Version + 1;
            }
        }
        return m_Version;
    }

    static bool TextValid(string text)
    {
        int length = text.Length();
        return length > 0 && length <= HCBeaconWire.MAX_TEXT;
    }

    static bool RowValid(HCBeaconRow row)
    {
        if (!row) { return false; }
        if (!TextValid(row.Id) || !TextValid(row.Kind) || !TextValid(row.Title) || !TextValid(row.Place)) { return false; }
        // NaN fails every comparison; coordinates stay inside the largest supported map.
        if (!(row.X >= 0 && row.X <= 50000 && row.Z >= 0 && row.Z <= 50000)) { return false; }
        if (!(row.Radius >= 50 && row.Radius <= 1500)) { return false; }
        return row.RemainingSeconds >= 1 && row.RemainingSeconds <= HCBeaconWire.MAX_REMAINING;
    }

    protected bool Refuse(string reason)
    {
        m_Refusal = reason;
        if (reason != m_RefusalLogged)
        {
            m_RefusalLogged = reason;
            Print("[HC Events] client mission snapshot refused reason=" + reason);
        }
        return false;
    }

    // Reads one full snapshot. Anything malformed is refused with a reason and
    // leaves the previous rows untouched; a version mismatch also clears them.
    bool Receive(ParamsReadContext ctx, float now)
    {
        int version;
        int sequence;
        int count;
        if (!ctx || !ctx.Read(version)) { return Refuse("short"); }
        if (version != HCBeaconWire.VERSION)
        {
            Clear();
            return Refuse("version");
        }
        if (!ctx.Read(sequence) || !ctx.Read(count)) { return Refuse("short"); }
        if (sequence < 0 || count < 0 || count > HCBeaconWire.MAX_ROWS) { return Refuse("bounds"); }
        array<ref HCBeaconRow> incoming = new array<ref HCBeaconRow>();
        for (int index = 0; index < count; index++)
        {
            HCBeaconRow row = new HCBeaconRow;
            if (!ctx.Read(row.Id) || !ctx.Read(row.Kind) || !ctx.Read(row.Title) || !ctx.Read(row.Place)) { return Refuse("short"); }
            if (!ctx.Read(row.X) || !ctx.Read(row.Z) || !ctx.Read(row.Radius) || !ctx.Read(row.RemainingSeconds)) { return Refuse("short"); }
            if (!RowValid(row)) { return Refuse("row"); }
            row.ReceivedAt = now;
            incoming.Insert(row);
        }
        m_Rows.Clear();
        foreach (HCBeaconRow accepted : incoming) { m_Rows.Insert(accepted); }
        m_Sequence = sequence;
        m_Refusal = "";
        m_RefusalLogged = "";
        m_Version = m_Version + 1;
        LogChange(now);
        return true;
    }

    // One line per accepted change; at most six per minute even if the server pushes faster.
    protected void LogChange(float now)
    {
        if (now < m_LogWindow || now - m_LogWindow >= 60)
        {
            m_LogWindow = now;
            m_LogCount = 0;
        }
        if (m_LogCount >= 6) { return; }
        m_LogCount = m_LogCount + 1;
        Print("[HC Events] client mission markers rows=" + m_Rows.Count().ToString() + " sequence=" + m_Sequence.ToString());
    }
}
