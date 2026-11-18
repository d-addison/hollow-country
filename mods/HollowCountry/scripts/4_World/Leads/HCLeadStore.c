// Native evidence: ~/.cache/hollow-country/native-scripts/scripts-1.30.164289/
// 1_Core/proto/EnSystem.c:397,417,425,443,462,525,528,531 (files),
// 3_Game/tools/JsonFileLoader.c:69,85 (JSON). Reuses HCWorldStore.Read/Write.
// 1_Core/proto/EnString.c:240 (IndexOf), EnConvert.c:30 (int.ToString),
// EnScript.c:380,394,407,470,502 (bounded arrays), EnDebug.c:96 (Print).
// No native rename exists: verified temp intent -> backup -> copy promotion,
// matching HCWorldStore. Interrupted/corrupt loads suspend this feature;
// unknown physical notes keep their reservations, including offline inventory.
class HCLeadNote
{
    ref HCWorldNote Row = new HCWorldNote;
    ref HCWorldLead Lead = new HCWorldLead;
    int Expires;
    int Phase; // 0 reserved, 1 materialized; reservations are never replayed
}

class HCBodyStoryRow
{
    string Id;
    string SceneId;
    string PlaceId;
    vector Position; // authored scene/shelter prop anchor, never a lead target
    int CreatedAt;
    int Expires;
    int Phase; // 0 intent, 1 placed, 2 found; uncertain intents never replay
}

class HCRadioChannel
{
    string Faction;
    float Frequency;
    int LastSent;
    int Sequence;
}

class HCLeadData
{
    int SchemaVersion = 1;
    int LastWrite;
    int Serial;
    ref array<ref HCWorldLead> Leads = new array<ref HCWorldLead>();
    ref array<ref HCLeadNote> Notes = new array<ref HCLeadNote>();
    ref array<ref HCBodyStoryRow> Bodies = new array<ref HCBodyStoryRow>();
    ref array<ref HCRadioChannel> Channels = new array<ref HCRadioChannel>();
}

class HCLeadStore
{
    protected static ref HCLeadStore s_Instance;
    ref HCLeadData Data;
    protected bool m_Healthy;
    protected string m_Path = "$profile:HollowCountry/leads.json";

    static HCLeadStore Get() { return s_Instance; }
    bool Healthy() { return m_Healthy; }

    bool Valid(HCLeadData value)
    {
        if (!value || value.SchemaVersion != 1 || value.Serial < 0 || value.LastWrite < 0 || value.LastWrite > HCWorldClock.UTC()) { return false; }
        if (!value.Leads || !value.Notes || !value.Bodies || !value.Channels) { return false; }
        if (value.Leads.Count() > 64 || value.Notes.Count() > 10 || value.Bodies.Count() > 3 || (value.Channels.Count() != 0 && value.Channels.Count() != 5)) { return false; }
        array<string> ids = new array<string>();
        foreach (HCWorldLead leadRow : value.Leads)
        {
            if (!HCLeadPolicy.Valid(leadRow) || !HCWorldLimits.Token(leadRow.Id) || !HCWorldLimits.Token(leadRow.Source) || !HCWorldLimits.Token(leadRow.GroupId) || ids.Find(leadRow.Id) >= 0) { return false; }
            ids.Insert(leadRow.Id);
            int groupCount = 0;
            foreach (HCWorldLead groupRow : value.Leads)
            {
                if (groupRow.GroupId == leadRow.GroupId) { groupCount++; }
            }
            if (groupCount > 5) { return false; }
        }
        array<string> scenes = new array<string>();
        foreach (HCLeadNote noteRow : value.Notes)
        {
            if (!noteRow || !noteRow.Row || !HCLeadPolicy.Valid(noteRow.Lead)) { return false; }
            if (!HCWorldLimits.Token(noteRow.Row.Id) || !HCWorldLimits.Token(noteRow.Row.SceneId) || noteRow.Row.CreatedAt < 1 || noteRow.Expires <= noteRow.Row.CreatedAt || noteRow.Phase < 0 || noteRow.Phase > 1) { return false; }
            if (scenes.Find(noteRow.Row.SceneId) >= 0 || ids.Find(noteRow.Row.Id) >= 0) { return false; }
            scenes.Insert(noteRow.Row.SceneId);
            ids.Insert(noteRow.Row.Id);
        }
        foreach (HCBodyStoryRow bodyRow : value.Bodies)
        {
            if (!bodyRow || !HCWorldLimits.Token(bodyRow.Id) || !HCWorldLimits.Token(bodyRow.SceneId) || !HCLeadPolicy.KnownPlace(bodyRow.PlaceId) || !HCWorldLimits.Position(bodyRow.Position)) { return false; }
            if (bodyRow.CreatedAt < 1 || bodyRow.Expires <= bodyRow.CreatedAt || bodyRow.Phase < 0 || bodyRow.Phase > 2 || ids.Find(bodyRow.Id) >= 0) { return false; }
            ids.Insert(bodyRow.Id);
        }
        array<string> factions = new array<string>();
        foreach (HCRadioChannel channelRow : value.Channels)
        {
            if (!channelRow || HCRadioChatter.Frequency(channelRow.Faction) != channelRow.Frequency || channelRow.Frequency <= 0 || channelRow.LastSent < 0 || channelRow.LastSent > HCWorldClock.UTC() || channelRow.Sequence < 0 || factions.Find(channelRow.Faction) >= 0) { return false; }
            factions.Insert(channelRow.Faction);
        }
        return true;
    }

    HCLeadData Decode(string text)
    {
        HCLeadData value;
        string error;
        // Field initializers must never turn a truncated/empty JSON object into
        // a fresh ledger and silently release physical-note reservations.
        if (text.IndexOf("\"SchemaVersion\"") < 0 || text.IndexOf("\"LastWrite\"") < 0 || text.IndexOf("\"Serial\"") < 0 || text.IndexOf("\"Leads\"") < 0 || text.IndexOf("\"Notes\"") < 0 || text.IndexOf("\"Bodies\"") < 0 || text.IndexOf("\"Channels\"") < 0) { return null; }
        if (text == "" || !JsonFileLoader<HCLeadData>.LoadData(text, value, error) || !Valid(value)) { return null; }
        return value;
    }

    bool Open()
    {
        s_Instance = this;
        if (HCWorldClock.UTC() < 1 || (!FileExist("$profile:HollowCountry") && !MakeDirectory("$profile:HollowCountry"))) { return Fault(); }
        if (FileExist(m_Path + ".tmp")) { return Fault(); }
        if (FileExist(m_Path))
        {
            Data = Decode(HCWorldStore.Read(m_Path));
            if (!Data) { return Fault(); }
        }
        else
        {
            // A lone backup is an uncertain deletion, never permission to reset caps.
            if (FileExist(m_Path + ".bak")) { return Fault(); }
            Data = new HCLeadData;
        }
        m_Healthy = true;
        return Save();
    }

    bool Fault()
    {
        m_Healthy = false;
        Print("[HollowCountry] V2 leads persistence fault; feature suspended; files and reservations preserved");
        return false;
    }

    bool Save()
    {
        if (!m_Healthy || !Valid(Data)) { return Fault(); }
        Data.LastWrite = HCWorldClock.UTC();
        string text;
        string error;
        if (!JsonFileLoader<HCLeadData>.MakeData(Data, text, error)) { return Fault(); }
        string prior;
        if (FileExist(m_Path))
        {
            prior = HCWorldStore.Read(m_Path);
            if (!Decode(prior)) { return Fault(); }
        }
        if (!HCWorldStore.Write(m_Path + ".tmp", text)) { return Fault(); }
        if (prior != "")
        {
            if (FileExist(m_Path + ".bak") && !DeleteFile(m_Path + ".bak")) { return Fault(); }
            if (!CopyFile(m_Path, m_Path + ".bak") || HCWorldStore.Read(m_Path + ".bak") != prior) { return Fault(); }
        }
        if (FileExist(m_Path) && !DeleteFile(m_Path)) { return Fault(); }
        if (!CopyFile(m_Path + ".tmp", m_Path) || HCWorldStore.Read(m_Path) != text || !DeleteFile(m_Path + ".tmp")) { return Fault(); }
        return true;
    }

    string NextId(string kind)
    {
        if (!m_Healthy || Data.Serial >= 2000000000) { return ""; }
        Data.Serial++;
        return kind + "-" + Data.Serial.ToString();
    }
}
