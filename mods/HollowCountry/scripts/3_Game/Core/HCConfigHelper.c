// Presence- and type-guarded config reads. Installed 1.30.164289 Game.c:539
// ConfigGetInt, :546 ConfigGetType, :524 ConfigGetFloat, :449 ConfigGetText,
// :558 ConfigGetTextArray, :612 ConfigIsExisting. An unguarded ConfigGet* on a
// missing or mistyped path logs `No entry` / `error value`; every read here
// checks ConfigIsExisting and ConfigGetType first and returns the caller's
// fallback instead. Callers pass a fallback equal to their documented default,
// so a missing entry never silently zeroes a setting.
// Not wrapped, so callers keep the raw native with their own guard: child iteration
// (ConfigGetChildrenCount/ChildName/BaseName), ConfigGetTextRaw/Out, vector and
// int/float arrays, and inventorySlot/attachments reads, whose entries may be a
// scalar string or an array and are validated natively by the taped-light and
// wreck-salvage gates (a CT_ARRAY-only reader would change their result).
class HCConfigHelper
{
    // Longest accepted path and text value; refuses runaway dynamic strings.
    static const int MAX_PATH = 256;
    static const int MAX_ARRAY = 256;

    static bool Has(string path)
    {
        if (!GetGame() || path == "" || path.Length() > MAX_PATH) { return false; }
        return GetGame().ConfigIsExisting(path);
    }

    // CT_INT, CT_FLOAT, CT_STRING, CT_ARRAY, CT_CLASS or CT_OTHER; -1 when the path is absent.
    static int TypeOf(string path)
    {
        if (!Has(path)) { return -1; }
        return GetGame().ConfigGetType(path);
    }

    static int GetInt(string path, int fallback)
    {
        if (TypeOf(path) != CT_INT) { return fallback; }
        return GetGame().ConfigGetInt(path);
    }

    // Accepts integer entries too: config authors write `1;` for float fields.
    static float GetFloat(string path, float fallback)
    {
        int type = TypeOf(path);
        if (type == CT_FLOAT) { return GetGame().ConfigGetFloat(path); }
        if (type == CT_INT) { return GetGame().ConfigGetInt(path); }
        return fallback;
    }

    static string GetText(string path, string fallback)
    {
        if (TypeOf(path) != CT_STRING) { return fallback; }
        string value;
        if (!GetGame().ConfigGetText(path, value)) { return fallback; }
        return value;
    }

    // Fills `values` (cleared first) and returns true only for a real array
    // entry within MAX_ARRAY elements; otherwise `values` stays empty.
    static bool GetTextArray(string path, out TStringArray values)
    {
        if (!values) { values = new TStringArray; }
        values.Clear();
        if (TypeOf(path) != CT_ARRAY) { return false; }
        TStringArray raw = new TStringArray;
        GetGame().ConfigGetTextArray(path, raw);
        if (raw.Count() > MAX_ARRAY) { return false; }
        values.Copy(raw);
        return true;
    }
}
