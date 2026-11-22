// Presence-checked default fill for successfully parsed, bounded JSON DTOs.
// Explicit 0/false survive; missing fields take the owner's constructor defaults.
// No reflection or file IO: owners validate the merged DTO before accepting it.
class HCJsonSchema
{
    // Bounded allow-list scan over a text window; the DTO parser remains the
    // syntax authority. targetDepth=0 checks keys at every nesting depth;
    // targetDepth=1 restricts only root members. Escaped authored keys use the
    // same Unicode-aware matcher as presence checks; values are never keys.
    static bool HCKeysAllowed(string text, string keys, int maxBytes, int targetDepth = 1)
    {
        if (text.Length() < 1 || text.Length() > maxBytes || maxBytes < 1 || targetDepth < 0) { return false; }
        array<string> allowed = new array<string>;
        keys.Split("|", allowed);
        if (allowed.Count() < 1 || allowed.Count() > 256) { return false; }
        map<string, bool> authored = new map<string, bool>;
        foreach (string authoredKey : allowed)
        {
            if (authoredKey != "") { authored.Set(authoredKey, true); }
        }
        HCTextWindow window = new HCTextWindow(text);
        int depth;
        int cursor;
        while (cursor < window.Length())
        {
            string token = window.At(cursor);
            if (token == "\"")
            {
                int start = cursor + 1;
                bool keyEscaped = false;
                cursor = start;
                while (cursor < window.Length() && window.At(cursor) != "\"")
                {
                    if (window.At(cursor) == "\\") { keyEscaped = true; cursor++; }
                    cursor++;
                }
                if (cursor >= window.Length()) { return false; }
                int after = cursor + 1;
                while (after < window.Length() && window.HCWhitespace(after)) { after++; }
                if (window.At(after) == ":" && (targetDepth == 0 || depth == targetDepth))
                {
                    // Authored keys are <=64 decoded characters (six raw bytes
                    // per Unicode escape); refuse before any candidate copy.
                    if (cursor - start > 384) { return false; }
                    // Common serializer output uses plain keys: one bounded
                    // window copy + O(1) lookup, no matcher object per candidate.
                    if (!keyEscaped)
                    {
                        if (!authored.Contains(window.Range(start, cursor - start))) { return false; }
                    }
                    else
                    {
                        bool matched = false;
                        foreach (string key : allowed)
                        {
                            if (key != "" && HCJsonFields.KeyMatchesAt(window, start, cursor, key)) { matched = true; break; }
                        }
                        if (!matched) { return false; }
                    }
                }
            }
            else if (token == "{" || token == "[") { depth++; }
            else if (token == "}" || token == "]") { depth--; if (depth < 0) { return false; } }
            cursor++;
        }
        return depth == 0;
    }

    static int HCApplyInt(string text, string key, int value, int fallback)
    {
        if (HCJsonFields.Has(text, key)) { return value; }
        return fallback;
    }

    static float HCApplyFloat(string text, string key, float value, float fallback)
    {
        if (HCJsonFields.Has(text, key)) { return value; }
        return fallback;
    }

    static bool HCApplyBool(string text, string key, bool value, bool fallback)
    {
        if (HCJsonFields.Has(text, key)) { return value; }
        return fallback;
    }
}

// Native 3_Game/tools/JsonFileLoader.c:69. Parse first, then pass fields through
// HCApply* with a separate default DTO; failed deserialization is never admitted.
class HCJsonSchemaLoader<Class T> : HCJsonSchema
{
    static bool HCLoadData(string text, out T data, out string error)
    {
        return JsonFileLoader<T>.LoadData(text, data, error);
    }
}

// Shared array scanner over the existing 1 KiB text window. Input MUST already
// have passed JsonFileLoader.LoadData. Ranges exclude the surrounding brackets;
// callers retain cursor and process at most their own per-tick item allowance.
// Native EnString.c:113 Substring, :199 Length, :448 Get (via HCTextWindow).
modded class HCTextWindow
{
    bool HCWhitespace(int index)
    {
        string token = At(index);
        return token == " " || token == "\n" || token == "\r" || token == "\t";
    }

    // Find a root object's array member, ignoring nested keys and quoted values.
    bool HCArrayRange(string key, out int start, out int stop)
    {
        start = -1;
        stop = -1;
        int depth;
        int cursor;
        while (cursor < Length())
        {
            string token = At(cursor);
            if (token == "\"")
            {
                int first = cursor + 1;
                cursor = first;
                while (cursor < Length() && At(cursor) != "\"")
                {
                    if (At(cursor) == "\\") { cursor++; }
                    cursor++;
                }
                if (cursor >= Length()) { return false; }
                int after = cursor + 1;
                while (after < Length() && HCWhitespace(after)) { after++; }
                if (depth == 1 && At(after) == ":" && HCJsonFields.KeyMatchesAt(this, first, cursor, key))
                {
                    after++;
                    while (after < Length() && HCWhitespace(after)) { after++; }
                    if (At(after) != "[") { return false; }
                    start = after + 1;
                    int end = after;
                    string value;
                    if (!HCNextArrayValue(end, Length(), value, Length(), false)) { return false; }
                    stop = end - 1;
                    return true;
                }
            }
            else if (token == "{" || token == "[") { depth++; }
            else if (token == "}" || token == "]") { depth--; }
            cursor++;
        }
        return false;
    }

    // Also accepts a cursor pointing at an entire array (used by HCArrayRange).
    // Returns false on end/refusal; cursor stays unchanged on refusal. maxBytes
    // bounds copies; scanning remains proportional to the supplied value size.
    bool HCNextArrayValue(inout int cursor, int stop, out string value, int maxBytes = 8388608, bool copyValue = true)
    {
        value = "";
        if (cursor < 0 || stop < cursor || stop > m_Text.Length() || maxBytes < 1) { return false; }
        int index = cursor;
        while (index < stop && HCWhitespace(index)) { index++; }
        if (At(index) == ",")
        {
            index++;
            while (index < stop && HCWhitespace(index)) { index++; }
        }
        int first = index;
        int depth;
        bool quoted;
        bool escaped;
        while (index < stop)
        {
            string token = At(index);
            if (!quoted && depth == 0 && (token == "," || token == "]" || token == "}")) { break; }
            if (quoted)
            {
                if (escaped) { escaped = false; }
                else if (token == "\\") { escaped = true; }
                else if (token == "\"") { quoted = false; }
            }
            else if (token == "\"") { quoted = true; }
            else if (token == "[" || token == "{") { depth++; }
            else if (token == "]" || token == "}") { depth--; }
            index++;
            if (index - first > maxBytes) { return false; }
            if (!quoted && depth == 0) { if (token == "]" || token == "}" || token == "\"") { break; } }
        }
        int end = index;
        while (end > first && HCWhitespace(end - 1)) { end--; }
        if (quoted || depth != 0 || end <= first) { return false; }
        if (copyValue) { value = m_Text.Substring(first, end - first); }
        cursor = index;
        return true;
    }
}
