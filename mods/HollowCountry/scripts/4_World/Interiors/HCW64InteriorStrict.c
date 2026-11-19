// #138: retained strict JSON traversal. Same schema/scalar checks and span key
// rewrites as HCInteriorTemplatesStrict.Value, but containers resume per token.
// Native scripts-1.30.164289: 1_Core/proto/EnScript.c:380/385/394/407/470
// Count/Clear/Find/Insert/RemoveOrdered; EnString.c:199 Length, :448 Get, :113 Substring, :396 Split.
// EnScript.c:866/902 map.Get/Set; EnMath.c:553 Min.
// Native LoadData/read and a single scalar token remain non-preemptible.
class HCW64InteriorFrame
{
    string Schema;
    int Phase;
    int Count;
    bool List;
    ref array<string> Required = new array<string>;
    ref array<string> Seen = new array<string>;
}

class HCW64InteriorStrict
{
    protected ref HCInteriorTemplateCursor m_Cursor = new HCInteriorTemplateCursor;
    protected ref array<ref HCW64InteriorFrame> m_Frames = new array<ref HCW64InteriorFrame>;
    protected bool m_Done;
    protected bool m_Failed;
    protected string m_Result;

    void HCStart(string content, string schema)
    {
        m_Cursor = new HCInteriorTemplateCursor;
        m_Cursor.Content = content;
        m_Frames.Clear();
        m_Done = false;
        m_Failed = content.Length() < 1 || content.Length() > 32767;
        m_Result = "";
        HCPush(schema);
    }

    void HCPush(string schema)
    {
        HCW64InteriorFrame frame = new HCW64InteriorFrame;
        frame.Schema = schema;
        frame.List = schema.Length() > 1 && schema.Get(0) == "@";
        m_Frames.Insert(frame);
    }

    bool HCFinishFrame()
    {
        m_Frames.RemoveOrdered(m_Frames.Count() - 1);
        if (m_Frames.Count() > 0) { return true; }
        HCInteriorTemplatesStrict.Space(m_Cursor);
        if (m_Cursor.Failed || m_Cursor.Index != m_Cursor.Content.Length()) { return false; }
        int remaining = m_Cursor.Content.Length() - m_Cursor.CopyFrom;
        m_Result = m_Cursor.NativeText + HCInteriorTemplatesStrict.CopyText(m_Cursor.Content, m_Cursor.CopyFrom, remaining);
        m_Done = true;
        return true;
    }

    bool HCVisit()
    {
        HCW64InteriorFrame frame = m_Frames[m_Frames.Count() - 1];
        string schema = frame.Schema;
        if (frame.Phase == 0)
        {
            m_Cursor.Nodes = m_Cursor.Nodes + 1;
            if (m_Frames.Count() > 13 || m_Cursor.Nodes > 16384) { return false; }
            if (schema == "text" || schema == "number" || schema == "integer" || schema == "boolean")
            {
                // Value charges its scalar node; do not count that node twice.
                m_Cursor.Nodes = m_Cursor.Nodes - 1;
                if (!HCInteriorTemplatesStrict.Value(m_Cursor, schema, m_Frames.Count() - 1)) { return false; }
                return HCFinishFrame();
            }
            if (frame.List)
            {
                if (!HCInteriorTemplatesStrict.Take(m_Cursor, 91)) { return false; }
                HCInteriorTemplatesStrict.Space(m_Cursor);
                if (HCInteriorTemplatesStrict.Code(m_Cursor) == 93)
                {
                    m_Cursor.Index = m_Cursor.Index + 1;
                    return HCFinishFrame();
                }
            }
            else
            {
                string keys = HCInteriorTemplatesStrict.Keys(schema);
                if ((keys.Length() == 0 && schema != "sources") || !HCInteriorTemplatesStrict.Take(m_Cursor, 123)) { return false; }
                keys.Split(" ", frame.Required);
            }
            frame.Phase = 1;
            return true;
        }
        if (frame.Phase == 1)
        {
            if (frame.List)
            {
                if (frame.Count >= HCInteriorTemplatesStrict.ArrayCap(schema)) { return false; }
                frame.Count = frame.Count + 1;
                frame.Phase = 2;
                int childLength = schema.Length() - 1;
                string child = schema.Substring(1, childLength);
                HCPush(child);
                return true;
            }
            int fieldCap = frame.Required.Count();
            if (schema == "sources") { fieldCap = 520; }
            if (frame.Count >= fieldCap) { return false; }
            HCInteriorTemplatesStrict.Space(m_Cursor);
            int keyBegin = m_Cursor.Index + 1;
            string key = HCInteriorTemplatesStrict.StringToken(m_Cursor, true);
            if (m_Cursor.Failed || frame.Seen.Find(key) >= 0) { return false; }
            if (schema == "sources")
            {
                if (!HCInteriorTemplatesStrict.SourceName(key)) { return false; }
            }
            else
            {
                if (frame.Required.Find(key) < 0) { return false; }
            }
            frame.Seen.Insert(key);
            string nativeKey = "";
            if (schema == "furnish-row" && key == "Slot") { nativeKey = "SlotId"; }
            if ((schema == "file" || schema == "template-file") && key == "File") { nativeKey = "FileName"; }
            if (nativeKey != "")
            {
                int prefixLength = keyBegin - m_Cursor.CopyFrom;
                string prefixText = HCInteriorTemplatesStrict.CopyText(m_Cursor.Content, m_Cursor.CopyFrom, prefixLength);
                m_Cursor.NativeText = m_Cursor.NativeText + prefixText + nativeKey;
                m_Cursor.CopyFrom = keyBegin + key.Length();
            }
            if (!HCInteriorTemplatesStrict.Take(m_Cursor, 58)) { return false; }
            frame.Count = frame.Count + 1;
            frame.Phase = 2;
            HCPush(HCInteriorTemplatesStrict.Child(schema, key));
            return true;
        }
        HCInteriorTemplatesStrict.Space(m_Cursor);
        int closing = 125;
        if (frame.List) { closing = 93; }
        if (HCInteriorTemplatesStrict.Code(m_Cursor) == closing)
        {
            m_Cursor.Index = m_Cursor.Index + 1;
            if (!frame.List)
            {
                if (schema == "sources") { if (frame.Count < 8) { return false; } }
                else { if (frame.Count != frame.Required.Count()) { return false; } }
            }
            return HCFinishFrame();
        }
        if (!HCInteriorTemplatesStrict.Take(m_Cursor, 44)) { return false; }
        frame.Phase = 1;
        return true;
    }

    // 0 complete, 1 retained continuation, 2 refused. One shared deadline for
    // every token in this slice; never restart/re-read a file after yielding.
    int HCStep(HCWorkBudget budget)
    {
        while (!m_Done && !m_Failed && budget.HCContinue())
        {
            if (!HCVisit()) { m_Failed = true; }
        }
        if (m_Failed) { return 2; }
        if (m_Done) { return 0; }
        return 1;
    }

    string HCResult() { return m_Result; }
}

// File IO, strict tokens and DTO validation occur in separate retained slices.
// No partial catalog is exposed: the existing reader alone publishes Loaded().
class HCW64InteriorLoad
{
    protected static ref HCW64InteriorStrict s_Parser;
    protected static string s_File;
    protected static ref HCWorkBudget s_Tokens = new HCWorkBudget;

    static void HCReset() { s_Parser = null; s_File = ""; }

    static int HCPrepare(HCWorkBudget budget)
    {
        string nextFile = HCInteriorTemplates.HCNextLeaf();
        if (nextFile == "") { return 0; }
        HCInteriorPackJob job = HCInteriorTemplates.HCPackJob();
        if (!s_Parser)
        {
            if (!budget.HCContinue()) { return 1; }
            if (job.LeafFiles >= 610) { HCInteriorTemplates.Refuse("file_cap"); return 2; }
            string raw = HCInteriorPackIndex.HCRead(job, nextFile);
            if (raw == "") { HCInteriorTemplates.Refuse(job.Reason); return 2; }
            if (job.Ready) { job.LeafFiles = job.LeafFiles + 1; }
            s_File = nextFile;
            s_Parser = new HCW64InteriorStrict;
            string schema = "pack-page";
            if (job.Ready) { schema = job.Schemas.Get(nextFile); }
            s_Parser.HCStart(raw, schema);
            return 1;
        }
        if (s_File != nextFile) { HCInteriorTemplates.Refuse("slice_file_changed"); HCReset(); return 2; }
        if (job.Pins.Get("__prepared_file") != nextFile)
        {
            s_Tokens.HCReset(HCInteriorTemplates.TEMPLATE_CHECKS_PER_STEP, HCPerfConfig.HCGet().SliceMs);
            int result = s_Parser.HCStep(s_Tokens);
            if (result == 2) { HCInteriorTemplates.Refuse("chunk_strict:" + nextFile); HCReset(); return 2; }
            if (result == 1) { return 1; }
            job.Pins.Set("__prepared_file", nextFile);
            job.Pins.Set("__prepared_text", s_Parser.HCResult());
            return 1;
        }
        return 0;
    }

    static void HCConsumed()
    {
        HCInteriorPackJob job = HCInteriorTemplates.HCPackJob();
        if (job.Pins.Get("__prepared_file") == "")
        {
            job.Pins.Set("__prepared_text", "");
            HCReset();
        }
    }
}

// At most one leaf/transition after the outer preparation gate. Operators may
// increase placement steps independently; a pack file remains the atomic DTO unit.
class HCW64InteriorPackBudget : HCWorkBudget
{
    override void HCReset(int limit, float milliseconds = 4)
    {
        super.HCReset(1, Math.Min(milliseconds, HCPerfConfig.HCGet().SliceMs));
    }
}
