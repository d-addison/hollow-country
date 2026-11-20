// Strict bounded ASCII JSON for the template pack, checked with native string scans only.
// A per-character script cursor cost about 72 s of script time for the 1.4 MB pack, so the
// pack text is screened and censused in a few native calls per file instead:
// 1. Screen (before LoadData): 2..32767 bytes, one {...} document, optional trailing LF/CRLF,
//    no byte outside A-Z a-z 0-9 _ . - : + / = " , [ ] { }, no multibyte text, no "".
//    No backslash means no escapes, so a string can never contain a quote.
// 2. Census (after LoadData): the DTO fixes how many objects, arrays, commas and keys of
//    each name the text must hold. Exact counts refuse unknown, missing and duplicate keys,
//    lenient syntax and any , [ ] { } inside a string value.
// Native scripts-1.30.164289: 1_Core/proto/EnString.c:199 Length, :212 LengthUtf8,
// :240 IndexOf, :253 LastIndexOf, :271 IndexOfFrom, :113 Substring, :156 Replace
// (in place on pieces of at most 4096 characters), :86 ToAscii, :396 Split;
// EnConvert.c:44 int.AsciiToString; EnScript.c:380/394/400/407 Count/Find/Get/Insert.
class HCInteriorKeyCensus
{
    ref array<string> Patterns = new array<string>;
    ref array<int> Counts = new array<int>;
    int Objects;
    int Arrays;
    int Commas;
    int ExtraKeys;
    bool Failed;

    void HCKey(string keyName, int count)
    {
        string pattern = "\"" + keyName + "\":";
        int at = Patterns.Find(pattern);
        if (at < 0)
        {
            Patterns.Insert(pattern);
            Counts.Insert(count);
            return;
        }
        Counts.Set(at, Counts.Get(at) + count);
    }

    // count objects of one schema; every object holds each key of Keys(schema) once.
    void HCObjects(string schema, int count)
    {
        string keys = HCInteriorTemplatesStrict.Keys(schema);
        array<string> names = new array<string>();
        keys.Split(" ", names);
        if (count < 0 || names.Count() < 1)
        {
            Failed = true;
            return;
        }
        foreach (string keyName : names)
        {
            HCKey(HCInteriorTemplatesStrict.NativeKey(keyName), count);
        }
        Objects = Objects + count;
        Commas = Commas + count * (names.Count() - 1);
    }

    void HCList(int elements)
    {
        if (elements < 0)
        {
            Failed = true;
            return;
        }
        Arrays = Arrays + 1;
        if (elements > 0)
        {
            Commas = Commas + elements - 1;
        }
    }

    void HCFloats(array<float> values)
    {
        if (!values) { Failed = true; return; }
        HCList(values.Count());
    }

    void HCInts(array<int> values)
    {
        if (!values) { Failed = true; return; }
        HCList(values.Count());
    }

    void HCTexts(array<string> values)
    {
        if (!values) { Failed = true; return; }
        HCList(values.Count());
    }
}

// Lowercase hex check for many pins at once: values are joined and scanned natively.
class HCInteriorHexBatch
{
    protected string m_Text;
    protected bool m_Bad;

    void HCAdd(string value, int length)
    {
        if (value.Length() != length)
        {
            m_Bad = true;
            return;
        }
        m_Text = m_Text + value;
        // Flush below 1024 characters: HexText scans at most 1 KB per call.
        if (m_Text.Length() > HCInteriorTemplatesStrict.HEX_BATCH_CHARS - 64)
        {
            HCFlush();
        }
    }

    protected void HCFlush()
    {
        if (m_Text != "" && !HCInteriorTemplatesStrict.HexText(m_Text))
        {
            m_Bad = true;
        }
        m_Text = "";
    }

    bool HCValid()
    {
        HCFlush();
        return !m_Bad;
    }
}

class HCInteriorTemplatesStrict
{
    static const int PIECE_CHARS = 4096;
    static const int PIECE_SEARCH = 3584;
    // Codes 1..127 outside the pack alphabet: 127 - 75 allowed codes.
    static const int LOW_SAMPLES = 52;
    // Codes 1..127 outside 0-9 a-f.
    static const int NON_HEX_SAMPLES = 111;
    static const int HEX_BATCH_CHARS = 1024;
    protected static ref array<string> s_Forbidden;
    protected static int s_LowForbidden;
    protected static ref array<string> s_NonHex;
    // One diagnostic line for the first census refusal of a boot.
    protected static bool s_CensusLogged;

    static string Keys(string schema)
    {
        if (schema == "pack-index")
        {
            return "SchemaVersion Kind WorldName Build PackId SourcePin Frame Provisional IndexFiles";
        }
        if (schema == "pack-page")
        {
            return "SchemaVersion Chunk SourcePins ClassFiles TemplateFiles FurnishFiles GroupFiles";
        }
        if (schema == "pack-source")
        {
            return "Name Sha256";
        }
        if (schema == "index")
        {
            return "SchemaVersion Kind WorldName Build PackId SourcePin Frame Provisional Sources ClassFiles TemplateFiles FurnishFiles GroupFiles";
        }
        if (schema == "file")
        {
            return "File Sha256";
        }
        if (schema == "template-file")
        {
            return "File BuildingClass Sha256";
        }
        if (schema == "classes")
        {
            return "SchemaVersion Chunk Rows";
        }
        if (schema == "class-row")
        {
            return "BuildingClass Rooms Furniture Search";
        }
        if (schema == "furnish")
        {
            return "SchemaVersion Chunk Rows";
        }
        if (schema == "furnish-row")
        {
            return "Slot BuildingClass Position Yaw Props History";
        }
        if (schema == "groups")
        {
            return "SchemaVersion Chunk Groups";
        }
        if (schema == "group")
        {
            return "Id Usages Container Categories Tags Items";
        }
        if (schema == "template")
        {
            return "SchemaVersion BuildingClass TemplateId Box Evidence Rooms KeepOuts PropSlots SearchSites";
        }
        if (schema == "box")
        {
            return "Min Max";
        }
        if (schema == "evidence")
        {
            return "Kind RunId Sha256";
        }
        if (schema == "room")
        {
            return "Id Label Min Max Anchor FloorY Cells";
        }
        if (schema == "keepout")
        {
            return "Kind Index Min Max";
        }
        if (schema == "prop")
        {
            return "Id Room Type Position Orientation Bounds History";
        }
        if (schema == "site")
        {
            return "Id Room Center Radius Source Points Groups";
        }
        return "";
    }

    // Slot is a native type name and a loaded dependency declares a type File, so the DTOs
    // read these two authored keys as SlotId and FileName.
    static string NativeKey(string key)
    {
        if (key == "File")
        {
            return "FileName";
        }
        if (key == "Slot")
        {
            return "SlotId";
        }
        return key;
    }

    static bool PackCode(int code)
    {
        if ((code >= 48 && code <= 57) || (code >= 65 && code <= 90) || (code >= 97 && code <= 122))
        {
            return true;
        }
        return code == 34 || code == 43 || code == 44 || code == 45 || code == 46 || code == 47 || code == 58 || code == 61 || code == 91 || code == 93 || code == 95 || code == 123 || code == 125;
    }

    // One-character samples. A sample is used only when AsciiToString gave back exactly
    // that byte; the low (1..127) sample count is checked so a short list refuses the pack.
    protected static void HCSamples()
    {
        if (s_Forbidden)
        {
            return;
        }
        s_Forbidden = new array<string>();
        s_NonHex = new array<string>();
        s_LowForbidden = 0;
        int code = 1;
        while (code < 256)
        {
            string sample = code.AsciiToString();
            int back = -1;
            if (sample.Length() == 1)
            {
                back = sample.ToAscii();
            }
            if (back == code || back == code - 256)
            {
                if (!PackCode(code))
                {
                    s_Forbidden.Insert(sample);
                    if (code < 128)
                    {
                        s_LowForbidden = s_LowForbidden + 1;
                    }
                }
                bool hexDigit = (code >= 48 && code <= 57) || (code >= 97 && code <= 102);
                if (code < 128 && !hexDigit)
                {
                    s_NonHex.Insert(sample);
                }
            }
            code = code + 1;
        }
    }

    // Lowercase hex only; callers check the length. High bytes are refused by Length()
    // against LengthUtf8() for multibyte text and by the screen for pack text.
    static bool HexText(string value)
    {
        if (value.Length() > 1024)
        {
            return false;
        }
        HCSamples();
        if (s_NonHex.Count() != NON_HEX_SAMPLES || value.Length() != value.LengthUtf8())
        {
            return false;
        }
        foreach (string sample : s_NonHex)
        {
            if (value.IndexOf(sample) >= 0)
            {
                return false;
            }
        }
        return true;
    }

    static bool Hex(string value, int length)
    {
        return value.Length() == length && HexText(value);
    }

    // With a batch, the 32 hex digits join it and the caller checks the batch once.
    static bool SourceName(string key, HCInteriorHexBatch batch = null)
    {
        if (key == "mapgroupproto" || key == "mapgrouppos" || key == "types" || key == "cfgspawnabletypes" || key == "cfglimitsdefinition" || key == "generator" || key == "search-generator")
        {
            return true;
        }
        if (key.Length() != 39 || key.Substring(0, 7) != "census-")
        {
            return false;
        }
        string digits = key.Substring(7, 32);
        if (batch)
        {
            batch.HCAdd(digits, 32);
            return true;
        }
        return Hex(digits, 32);
    }

    // Same result as HCSearchRules.TextValid for text that passed Screen and Census: those
    // leave only A-Z a-z 0-9 _ . - : + / = in a string value, so only the length is open.
    static bool Text(string value, int limit)
    {
        int length = value.Length();
        return length >= 1 && length <= limit && limit <= 768;
    }

    // Enforce Substring returns at most 8191 characters (observed under Wine, diag-json-1: a 25 KB
    // class chunk reached LoadData as exactly 8191), so every copy of authored text goes in pieces.
    static string CopyText(string text, int start, int length)
    {
        if (start < 0 || length < 0 || start + length > text.Length())
        {
            return "";
        }
        string result = "";
        int done = 0;
        int piece = 0;
        while (done < length)
        {
            piece = length - done;
            if (piece > 4096)
            {
                piece = 4096;
            }
            result = result + text.Substring(start + done, piece);
            done = done + piece;
        }
        return result;
    }

    // Length of the next piece, ending just after a comma. No key pattern ("Name": or ":)
    // contains a comma, so none is ever split between two pieces. -1 when no cut fits.
    static int PieceSize(string text, int start, int length)
    {
        int size = length - start;
        if (size <= PIECE_CHARS)
        {
            return size;
        }
        // Build 099 refused every multi-piece page; IndexOfFrom is not observed natively,
        // so search a bounded window with Substring + IndexOf (both observed on this pack).
        if (start + PIECE_CHARS > text.Length())
        {
            return -1;
        }
        string window = text.Substring(start + PIECE_SEARCH, PIECE_CHARS - PIECE_SEARCH);
        int offset = window.IndexOf(",");
        if (offset < 0)
        {
            return -1;
        }
        return PIECE_SEARCH + offset + 1;
    }

    // Body length (text without one trailing LF or CRLF), or -1 when the screen refuses.
    static int Screen(string raw)
    {
        int length = raw.Length();
        if (length < 2 || length > 32767 || raw.LengthUtf8() != length)
        {
            return -1;
        }
        HCSamples();
        if (s_LowForbidden != LOW_SAMPLES)
        {
            return -1;
        }
        int lineCode = 10;
        int returnCode = 13;
        string lineFeed = lineCode.AsciiToString();
        string carriage = returnCode.AsciiToString();
        int body = length;
        if (raw.LastIndexOf(lineFeed) == length - 1)
        {
            body = length - 1;
            if (raw.LastIndexOf(carriage) == body - 1)
            {
                body = body - 1;
            }
        }
        if (body < 2 || raw.IndexOf("{") != 0 || raw.LastIndexOf("}") != body - 1 || raw.IndexOf("\"\"") >= 0)
        {
            return -1;
        }
        // No authored value is null; LoadData would turn a null scalar into a default.
        if (raw.IndexOf(":null") >= 0 || raw.IndexOf(",null") >= 0 || raw.IndexOf("[null") >= 0)
        {
            return -1;
        }
        foreach (string sample : s_Forbidden)
        {
            if (!Absent(raw, sample, body))
            {
                return -1;
            }
        }
        return body;
    }

    // One native scan: sample does not occur before position body.
    static bool Absent(string text, string sample, int body)
    {
        int at = text.IndexOf(sample);
        return at < 0 || at >= body;
    }

    // Replace one authored key with its DTO name, piece by piece.
    static string Rename(string text, string authored, string nativeKey)
    {
        int length = text.Length();
        string result = "";
        int start = 0;
        while (start < length)
        {
            int size = PieceSize(text, start, length);
            if (size < 1)
            {
                return "";
            }
            if (size > 4096) { size = 4096; }
            string piece = text.Substring(start, size);
            piece.Replace(authored, nativeKey);
            result = result + piece;
            start = start + size;
        }
        return result;
    }

    // Screened text ready for LoadData, or "" when refused. The census after LoadData
    // completes the strict check.
    static string NativeText(string content, string schema)
    {
        if (Keys(schema) == "" || Screen(content) < 0)
        {
            return "";
        }
        string authored = "";
        string nativeKey = "";
        if (schema == "pack-index" || schema == "pack-page" || schema == "index")
        {
            authored = "\"File\":";
            nativeKey = "\"FileName\":";
        }
        if (schema == "furnish")
        {
            authored = "\"Slot\":";
            nativeKey = "\"SlotId\":";
        }
        if (authored == "")
        {
            return content;
        }
        // An authored DTO name would alias the renamed key.
        if (content.IndexOf(nativeKey) >= 0)
        {
            return "";
        }
        return Rename(content, authored, nativeKey);
    }

    // Latched: one line for the first census refusal of a boot.
    static void CensusRefused(string detail)
    {
        if (s_CensusLogged)
        {
            return;
        }
        s_CensusLogged = true;
        Print("[HC Interiors] census refused " + detail);
    }

    // Exact key, object, array and comma counts of a LoadData text against its DTO census.
    static bool Census(string text, HCInteriorKeyCensus census)
    {
        if (!census || census.Failed)
        {
            return false;
        }
        int names = census.Patterns.Count();
        array<int> found = new array<int>();
        int fill = 0;
        while (fill < names)
        {
            found.Insert(0);
            fill = fill + 1;
        }
        int extra = 0;
        int commas = 0;
        int opens = 0;
        int closes = 0;
        int listOpens = 0;
        int listCloses = 0;
        int length = text.Length();
        int start = 0;
        while (start < length)
        {
            int size = PieceSize(text, start, length);
            if (size < 1)
            {
                return false;
            }
            if (size > 4096) { size = 4096; }
            string piece = text.Substring(start, size);
            string work = piece;
            int at = 0;
            while (at < names)
            {
                found.Set(at, found.Get(at) + work.Replace(census.Patterns.Get(at), ""));
                at = at + 1;
            }
            extra = extra + work.Replace("\":", "");
            work = piece;
            commas = commas + work.Replace(",", "");
            opens = opens + work.Replace("{", "");
            closes = closes + work.Replace("}", "");
            listOpens = listOpens + work.Replace("[", "");
            listCloses = listCloses + work.Replace("]", "");
            start = start + size;
        }
        if (extra != census.ExtraKeys || commas != census.Commas || opens != census.Objects || closes != census.Objects || listOpens != census.Arrays || listCloses != census.Arrays)
        {
            string line = "length=" + length.ToString() + " extra=" + extra.ToString() + "/" + census.ExtraKeys.ToString();
            line = line + " commas=" + commas.ToString() + "/" + census.Commas.ToString() + " objects=" + opens.ToString() + "," + closes.ToString() + "/" + census.Objects.ToString();
            CensusRefused(line + " arrays=" + listOpens.ToString() + "," + listCloses.ToString() + "/" + census.Arrays.ToString());
            return false;
        }
        int check = 0;
        while (check < names)
        {
            int foundCount = found.Get(check);
            int expectedCount = census.Counts.Get(check);
            if (foundCount != expectedCount)
            {
                CensusRefused("key=" + census.Patterns.Get(check) + " found=" + foundCount.ToString() + " expected=" + expectedCount.ToString());
                return false;
            }
            check = check + 1;
        }
        return true;
    }

    static bool RootCensus(string text, HCInteriorPackRoot header)
    {
        if (!header || !header.IndexFiles)
        {
            return false;
        }
        HCInteriorKeyCensus census = new HCInteriorKeyCensus;
        census.HCObjects("pack-index", 1);
        census.HCObjects("file", header.IndexFiles.Count());
        census.HCList(header.IndexFiles.Count());
        return Census(text, census);
    }

    static bool PageCensus(string text, HCInteriorPackPage page)
    {
        if (!page || !page.SourcePins || !page.ClassFiles || !page.TemplateFiles || !page.FurnishFiles || !page.GroupFiles)
        {
            return false;
        }
        HCInteriorKeyCensus census = new HCInteriorKeyCensus;
        census.HCObjects("pack-page", 1);
        census.HCObjects("pack-source", page.SourcePins.Count());
        census.HCObjects("file", page.ClassFiles.Count() + page.FurnishFiles.Count() + page.GroupFiles.Count());
        census.HCObjects("template-file", page.TemplateFiles.Count());
        census.HCList(page.SourcePins.Count());
        census.HCList(page.ClassFiles.Count());
        census.HCList(page.TemplateFiles.Count());
        census.HCList(page.FurnishFiles.Count());
        census.HCList(page.GroupFiles.Count());
        return Census(text, census);
    }

    // Legacy schema-2 index: Sources is an object whose keys are source names. The map
    // keeps one entry per name, so a repeated name leaves an extra key and is refused.
    static bool IndexCensus(string text, HCInteriorTemplateIndex index)
    {
        if (!index || !index.Sources || !index.ClassFiles || !index.TemplateFiles || !index.FurnishFiles || !index.GroupFiles)
        {
            return false;
        }
        HCInteriorKeyCensus census = new HCInteriorKeyCensus;
        census.HCObjects("index", 1);
        int sources = index.Sources.Count();
        census.Objects = census.Objects + 1;
        census.ExtraKeys = sources;
        if (sources > 0)
        {
            census.Commas = census.Commas + sources - 1;
        }
        census.HCObjects("file", index.ClassFiles.Count() + index.FurnishFiles.Count() + index.GroupFiles.Count());
        census.HCObjects("template-file", index.TemplateFiles.Count());
        census.HCList(index.ClassFiles.Count());
        census.HCList(index.TemplateFiles.Count());
        census.HCList(index.FurnishFiles.Count());
        census.HCList(index.GroupFiles.Count());
        return Census(text, census);
    }

    static bool ClassesCensus(string text, HCInteriorTemplateClasses classes)
    {
        if (!classes || !classes.Rows)
        {
            return false;
        }
        HCInteriorKeyCensus census = new HCInteriorKeyCensus;
        census.HCObjects("classes", 1);
        census.HCObjects("class-row", classes.Rows.Count());
        census.HCList(classes.Rows.Count());
        return Census(text, census);
    }

    static bool GroupsCensus(string text, HCInteriorTemplateGroups groups)
    {
        if (!groups || !groups.Groups)
        {
            return false;
        }
        HCInteriorKeyCensus census = new HCInteriorKeyCensus;
        census.HCObjects("groups", 1);
        census.HCObjects("group", groups.Groups.Count());
        census.HCList(groups.Groups.Count());
        foreach (HCInteriorSearchGroup groupRow : groups.Groups)
        {
            if (!groupRow)
            {
                return false;
            }
            census.HCTexts(groupRow.Usages);
            census.HCTexts(groupRow.Categories);
            census.HCTexts(groupRow.Tags);
            census.HCTexts(groupRow.Items);
        }
        return Census(text, census);
    }

    static bool FurnishCensus(string text, HCInteriorTemplateFurnish furnish)
    {
        if (!furnish || !furnish.Rows)
        {
            return false;
        }
        HCInteriorKeyCensus census = new HCInteriorKeyCensus;
        census.HCObjects("furnish", 1);
        census.HCObjects("furnish-row", furnish.Rows.Count());
        census.HCList(furnish.Rows.Count());
        foreach (HCInteriorFurnishRow row : furnish.Rows)
        {
            if (!row)
            {
                return false;
            }
            census.HCFloats(row.Position);
            census.HCInts(row.Props);
        }
        return Census(text, census);
    }

    static bool TemplateCensus(string text, HCInteriorTemplate templateRow)
    {
        if (!templateRow || !templateRow.Box || !templateRow.Evidence || !templateRow.Rooms || !templateRow.KeepOuts || !templateRow.PropSlots || !templateRow.SearchSites)
        {
            return false;
        }
        HCInteriorKeyCensus census = new HCInteriorKeyCensus;
        census.HCObjects("template", 1);
        census.HCObjects("box", 1 + templateRow.PropSlots.Count());
        census.HCFloats(templateRow.Box.Min);
        census.HCFloats(templateRow.Box.Max);
        census.HCObjects("evidence", templateRow.Evidence.Count());
        census.HCList(templateRow.Evidence.Count());
        census.HCObjects("room", templateRow.Rooms.Count());
        census.HCList(templateRow.Rooms.Count());
        foreach (HCInteriorTemplateRoom roomRow : templateRow.Rooms)
        {
            if (!roomRow)
            {
                return false;
            }
            census.HCFloats(roomRow.Min);
            census.HCFloats(roomRow.Max);
            census.HCFloats(roomRow.Anchor);
        }
        census.HCObjects("keepout", templateRow.KeepOuts.Count());
        census.HCList(templateRow.KeepOuts.Count());
        foreach (HCInteriorTemplateKeepOut keepOut : templateRow.KeepOuts)
        {
            if (!keepOut)
            {
                return false;
            }
            census.HCFloats(keepOut.Min);
            census.HCFloats(keepOut.Max);
        }
        census.HCObjects("prop", templateRow.PropSlots.Count());
        census.HCList(templateRow.PropSlots.Count());
        foreach (HCInteriorTemplatePropSlot propRow : templateRow.PropSlots)
        {
            if (!propRow || !propRow.Bounds)
            {
                return false;
            }
            census.HCFloats(propRow.Position);
            census.HCFloats(propRow.Orientation);
            census.HCFloats(propRow.Bounds.Min);
            census.HCFloats(propRow.Bounds.Max);
            census.HCTexts(propRow.History);
        }
        census.HCObjects("site", templateRow.SearchSites.Count());
        census.HCList(templateRow.SearchSites.Count());
        foreach (HCInteriorTemplateSearchSite siteRow : templateRow.SearchSites)
        {
            if (!siteRow)
            {
                return false;
            }
            census.HCFloats(siteRow.Center);
            census.HCInts(siteRow.Points);
            census.HCTexts(siteRow.Groups);
        }
        return Census(text, census);
    }
}
