// Respawn2: preserve exact shipped bytes as provenance (no hash collision or
// invented engine hash API). Only unchanged mod-written profiles auto-upgrade.
// Reuses HCProfileDefaults bounded IO and temp/readback; recovery images stay.
// Native scripts-1.30.164289/1_Core/proto/EnSystem.c:397 FileExist,
// :528 DeleteFile, :531 CopyFile; EnString.c:113 Substring, :199 Length,
// :448 Get; EnScript.c:380 Count, :394 Find, :407 Insert; EnDebug.c:96 Print.
// Native 3_Game/tools/JsonFileLoader.c:69 LoadData. Missing SchemaVersion
// zero-fills; an invalid/unknown schema never authorizes legacy replacement.
class HCXAIRespawnSchema
{
    int SchemaVersion;
}
class HCXAIRespawnDefaults
{
    // Top-level schema only. Escaped keys are conservatively kept for an
    // operator, never interpreted as permission to overwrite their file.
    static array<string> HCKeys(string text, bool allDepths = false)
    {
        array<string> names = new array<string>();
        // Windowed reads: the shipped site policy is near 1 MB (boot 084 hang).
        HCTextWindow window = new HCTextWindow(text);
        int length = window.Length();
        int cursor = 0;
        int depth = 0;
        while (cursor < length)
        {
            string token = window.At(cursor);
            if (token == "\"")
            {
                int start = cursor + 1;
                cursor = start;
                bool escaped = false;
                while (cursor < length && window.At(cursor) != "\"")
                {
                    if (window.At(cursor) == "\\") { escaped = true; cursor++; }
                    cursor++;
                }
                if (cursor >= length) { return null; }
                int after = cursor + 1;
                while (after < length && (window.At(after) == " " || window.At(after) == "\n" || window.At(after) == "\r" || window.At(after) == "\t")) { after++; }
                if ((depth == 1 || allDepths) && after < length && window.At(after) == ":")
                {
                    if (escaped) { return null; }
                    string keyName = window.Range(start, cursor - start);
                    if (names.Find(keyName) < 0) { names.Insert(keyName); }
                }
            }
            else if (token == "{" || token == "[") { depth++; }
            else if (token == "}" || token == "]") { depth--; }
            if (depth < 0) { return null; }
            cursor++;
        }
        if (depth != 0 || names.Count() == 0) { return null; }
        return names;
    }

    static int HCVersion(string text)
    {
        HCXAIRespawnSchema schema;
        string error;
        if (!JsonFileLoader<HCXAIRespawnSchema>.LoadData(text, schema, error) || !schema) { return -1; }
        return schema.SchemaVersion;
    }

    static bool HCOlderSchema(string profile, string shipped)
    {
        int profileVersion = HCXAIRespawnDefaults.HCVersion(profile);
        int shippedVersion = HCXAIRespawnDefaults.HCVersion(shipped);
        if (profileVersion < 1 || shippedVersion < profileVersion) { return false; }
        array<string> profileKeys = HCXAIRespawnDefaults.HCKeys(profile);
        array<string> shippedKeys = HCXAIRespawnDefaults.HCKeys(shipped);
        if (!profileKeys || !shippedKeys) { return false; }
        // Unknown keys at ANY depth mean operator/newer-schema authority,
        // even when a top-level shipped field is missing.
        array<string> profileSchema = HCXAIRespawnDefaults.HCKeys(profile, true);
        array<string> shippedSchema = HCXAIRespawnDefaults.HCKeys(shipped, true);
        if (!profileSchema || !shippedSchema) { return false; }
        foreach (string profileKey : profileSchema)
        {
            if (shippedSchema.Find(profileKey) < 0) { return false; }
        }
        foreach (string shippedKey : shippedKeys)
        {
            if (!HCJsonFields.Has(profile, shippedKey)) { return true; }
        }
        return false;
    }

    static bool HCEnsure(string relative, string source)
    {
        if (!HCProfileDefaults.Valid(relative)) { return false; }
        string shipped = HCProfileDefaults.ReadText(source);
        if (shipped == "") { return false; }
        string target = "$profile:HollowCountry/" + relative;
        string originPath = target + ".hcdefault.origin";
        string profile = HCProfileDefaults.ReadText(target);
        string origin = HCProfileDefaults.ReadText(originPath);
        if (profile == shipped)
        {
            if (origin == shipped) { return true; }
            return HCProfileDefaults.WriteText(originPath, shipped);
        }
        string backup = target + ".bak";
        string mode = "provenance";
        if (FileExist(target))
        {
            if (profile == "") { return false; }
            if (origin == "")
            {
                if (!HCXAIRespawnDefaults.HCOlderSchema(profile, shipped)) { return true; }
                backup = target + ".legacy.bak";
                mode = "legacy_schema";
                if (FileExist(backup) && HCProfileDefaults.ReadText(backup) != profile) { return false; }
            }
            else if (profile != origin) { return true; }
            if (!CopyFile(target, backup) || HCProfileDefaults.ReadText(backup) != profile) { return false; }
        }
        else if (!HCProfileDefaults.PrepareParents(relative)) { return false; }
        string temporary = target + ".hcdefault.tmp";
        if (!HCProfileDefaults.WriteText(temporary, shipped)) { return false; }
        if (!CopyFile(temporary, target) || HCProfileDefaults.ReadText(target) != shipped) { return false; }
        DeleteFile(temporary);
        if (!HCProfileDefaults.WriteText(originPath, shipped)) { return false; }
        Print("[HC AI Defaults] adopted file=" + relative + " mode=" + mode + "; runtime=PENDING");
        return true;
    }
}
