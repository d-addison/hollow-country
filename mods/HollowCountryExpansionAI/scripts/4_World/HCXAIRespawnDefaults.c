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
        map<string, bool> shippedKnown = new map<string, bool>();
        foreach (string knownKey : shippedSchema) { shippedKnown.Set(knownKey, true); }
        foreach (string profileKey : profileSchema)
        {
            if (!shippedKnown.Contains(profileKey)) { return false; }
        }
        foreach (string shippedKey : shippedKeys)
        {
            if (!HCJsonFields.Has(profile, shippedKey)) { return true; }
        }
        return false;
    }

    // An unprovenanced locality catalog that is a strict subset of the shipped
    // one (same settings; every locality present with the same Island/Source
    // and a subset of its SiteIds) is an older mod image, not operator data.
    static bool HCOlderLocalities(string profile, string shipped)
    {
        HCXAILocalityCatalog older;
        HCXAILocalityCatalog newer;
        string error;
        if (!JsonFileLoader<HCXAILocalityCatalog>.LoadData(profile, older, error) || !older || !older.Localities) { return false; }
        if (!JsonFileLoader<HCXAILocalityCatalog>.LoadData(shipped, newer, error) || !newer || !newer.Localities) { return false; }
        if (older.SchemaVersion != newer.SchemaVersion || older.Enabled != newer.Enabled || older.WorldName != newer.WorldName || older.PageSize != newer.PageSize) { return false; }
        if (older.AttemptsPerTick != newer.AttemptsPerTick || older.SelectionIntervalSeconds != newer.SelectionIntervalSeconds || older.OpportunitySeconds != newer.OpportunitySeconds || older.RetrySeconds != newer.RetrySeconds) { return false; }
        if (older.Localities.Count() < 1 || older.Localities.Count() > newer.Localities.Count()) { return false; }
        map<string, HCXAILocality> index = new map<string, HCXAILocality>();
        foreach (HCXAILocality shippedLocality : newer.Localities)
        {
            if (shippedLocality) { index.Set(shippedLocality.Id, shippedLocality); }
        }
        bool fewer = older.Localities.Count() < newer.Localities.Count();
        foreach (HCXAILocality locality : older.Localities)
        {
            if (!locality || !locality.SiteIds) { return false; }
            HCXAILocality match;
            if (!index.Find(locality.Id, match) || !match.SiteIds || match.Island != locality.Island || match.Source != locality.Source) { return false; }
            map<string, bool> matchSites = new map<string, bool>();
            foreach (string shippedSite : match.SiteIds) { matchSites.Set(shippedSite, true); }
            foreach (string siteId : locality.SiteIds)
            {
                if (!matchSites.Contains(siteId)) { return false; }
            }
            if (locality.SiteIds.Count() < match.SiteIds.Count()) { fewer = true; }
        }
        return fewer;
    }

    static bool HCEnsure(string relative, string source, bool localities = false)
    {
        if (!HCProfileDefaults.Valid(relative)) { return false; }
        string shipped = HCProfileDefaults.ReadText(source);
        if (shipped == "") { return false; }
        string target = "$profile:HollowCountry/" + relative;
        string originPath = target + ".hcdefault.origin";
        string profile = HCProfileDefaults.ReadText(target);
        string origin = HCProfileDefaults.ReadText(originPath);
        string backup = target + ".bak";
        string temporary = target + ".hcdefault.tmp";
        string priorPath = target + ".hcdefault.prior";
        string mode = "provenance";
        // A shipped temp is durable adoption intent, created only after the
        // prior profile backup passes readback. Never infer intent from a torn
        // target alone. Preserve prior provenance across a torn origin write.
        bool resume = false;
        if (HCProfileDefaults.ReadText(temporary) == shipped)
        {
            string prior = HCProfileDefaults.ReadText(backup);
            string receipt = HCProfileDefaults.ReadText(priorPath);
            if (prior != "" && (prior == origin || prior == receipt)) { resume = true; }
            if (!resume)
            {
                string legacy = HCProfileDefaults.ReadText(target + ".legacy.bak");
                if (legacy != "")
                {
                    resume = HCXAIRespawnDefaults.HCOlderSchema(legacy, shipped);
                    if (!resume && localities) { resume = HCXAIRespawnDefaults.HCOlderLocalities(legacy, shipped); }
                }
            }
        }
        if (resume)
        {
            mode = "resume_interrupted";
            if (!CopyFile(temporary, target) || HCProfileDefaults.ReadText(target) != shipped) { return false; }
            if (!HCProfileDefaults.WriteText(originPath, shipped)) { return false; }
            DeleteFile(temporary);
            DeleteFile(priorPath);
            Print("[HC AI Defaults] adopted file=" + relative + " mode=" + mode + "; runtime=PENDING");
            return true;
        }
        if (profile == shipped)
        {
            if (origin == shipped) { return true; }
            return HCProfileDefaults.WriteText(originPath, shipped);
        }
        if (FileExist(target))
        {
            if (profile == "") { return false; }
            if (origin == "")
            {
                bool older = HCXAIRespawnDefaults.HCOlderSchema(profile, shipped);
                if (!older && localities) { older = HCXAIRespawnDefaults.HCOlderLocalities(profile, shipped); }
                if (!older) { return true; }
                backup = target + ".legacy.bak";
                mode = "legacy_schema";
                if (FileExist(backup) && HCProfileDefaults.ReadText(backup) != profile) { return false; }
            }
            else if (profile != origin) { return true; }
            if (!CopyFile(target, backup) || HCProfileDefaults.ReadText(backup) != profile) { return false; }
            if (mode == "provenance" && !HCProfileDefaults.WriteText(priorPath, profile)) { return false; }
        }
        else if (!HCProfileDefaults.PrepareParents(relative)) { return false; }
        if (!HCProfileDefaults.WriteText(temporary, shipped)) { return false; }
        if (!CopyFile(temporary, target) || HCProfileDefaults.ReadText(target) != shipped) { return false; }
        if (!HCProfileDefaults.WriteText(originPath, shipped)) { return false; }
        DeleteFile(temporary);
        DeleteFile(priorPath);
        Print("[HC AI Defaults] adopted file=" + relative + " mode=" + mode + "; runtime=PENDING");
        return true;
    }
}
