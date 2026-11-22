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
        string refused = "[HC AI Defaults] refused file=" + relative + " reason=";
        string shipped = HCProfileDefaults.ReadText(source);
        if (shipped == "") { Print(refused + "shipped_unreadable"); return false; }
        string target = "$profile:HollowCountry/" + relative;
        string originPath = target + ".hcdefault.origin";
        string profile = HCProfileDefaults.ReadText(target);
        string origin = HCProfileDefaults.ReadText(originPath);
        string backup = target + ".bak";
        string temporary = target + ".hcdefault.tmp";
        string priorPath = target + ".hcdefault.prior";
        string mode = "provenance";
        string staged = HCProfileDefaults.ReadText(temporary);
        bool hasTemporary = FileExist(temporary);
        // An old release's intent is not authority for the current shipped image.
        if (hasTemporary && staged != shipped)
        {
            if (!DeleteFile(temporary)) { Print(refused + "stale_tmp_delete"); return false; }
            hasTemporary = false;
            Print("[HC AI Defaults] recovered file=" + relative + " reason=stale_tmp_removed");
        }
        // Includes the old sequence's crash after tmp deletion but before origin.
        // No target recopy (nearly 1 MiB for sites) on an ordinary warm boot.
        if (profile == shipped)
        {
            bool originRepaired = origin != shipped;
            if (originRepaired && !HCProfileDefaults.WriteText(originPath, shipped)) { Print(refused + "origin_readback"); return false; }
            if (hasTemporary && !DeleteFile(temporary)) { Print(refused + "tmp_delete"); return false; }
            if (FileExist(priorPath) && !DeleteFile(priorPath)) { Print(refused + "prior_delete"); return false; }
            if (originRepaired || hasTemporary)
            {
                Print("[HC AI Defaults] adopted file=" + relative + " mode=resume_origin; runtime=PENDING");
            }
            return true;
        }
        // A completed current origin plus differing data is an operator edit,
        // even if an old release left a valid shipped temp alongside it.
        if (origin == shipped)
        {
            if (hasTemporary && !DeleteFile(temporary)) { Print(refused + "operator_tmp_delete"); return false; }
            Print(refused + "operator_modified");
            return true;
        }
        bool resume = false;
        if (hasTemporary)
        {
            string prior = HCProfileDefaults.ReadText(backup);
            string receipt = HCProfileDefaults.ReadText(priorPath);
            bool verifiedPrior = prior != "" && (prior == origin || prior == receipt);
            string legacy = HCProfileDefaults.ReadText(target + ".legacy.bak");
            bool verifiedLegacy = false;
            if (legacy != "")
            {
                verifiedLegacy = HCXAIRespawnDefaults.HCOlderSchema(legacy, shipped);
                if (!verifiedLegacy && localities) { verifiedLegacy = HCXAIRespawnDefaults.HCOlderLocalities(legacy, shipped); }
            }
            bool matchesBackup = verifiedPrior && profile == prior;
            if (verifiedLegacy && profile == legacy) { matchesBackup = true; }
            // One bounded O(n) comparison, never a per-character scan. A shipped
            // intent also witnesses the fresh (no prior profile/backup) path.
            bool torn = profile == "";
            if (torn && FileExist(target))
            {
                // ReadText also returns empty on unreadable/oversized input;
                // only an observed zero-byte target belongs to fresh recovery.
                FileHandle emptyHandle = OpenFile(target, FileMode.READ);
                if (!emptyHandle) { Print(refused + "profile_unreadable"); return false; }
                string emptyProbe;
                int emptyBytes = ReadFile(emptyHandle, emptyProbe, 1);
                CloseFile(emptyHandle);
                if (emptyBytes != 0) { Print(refused + "profile_not_empty"); return false; }
            }
            if (!torn && profile.Length() < shipped.Length())
            {
                torn = shipped.Substring(0, profile.Length()) == profile;
            }
            resume = torn || matchesBackup;
            if (!resume)
            {
                // Preserve operator data; a backup alone never authorizes it.
                if (!DeleteFile(temporary)) { Print(refused + "operator_tmp_delete"); return false; }
                Print(refused + "resume_target_modified");
                return true;
            }
            mode = "resume_interrupted";
        }
        if (!resume)
        {
            if (FileExist(target))
            {
                if (profile == "") { Print(refused + "profile_unreadable"); return false; }
                if (origin == "")
                {
                    bool older = HCXAIRespawnDefaults.HCOlderSchema(profile, shipped);
                    if (!older && localities) { older = HCXAIRespawnDefaults.HCOlderLocalities(profile, shipped); }
                    if (!older) { Print(refused + "operator_unprovenanced"); return true; }
                    backup = target + ".legacy.bak";
                    mode = "legacy_schema";
                }
                else if (profile != origin) { Print(refused + "operator_modified"); return true; }
                string saved = HCProfileDefaults.ReadText(backup);
                bool rebuildLegacy = false;
                // Older releases may already have made this exact backup. Do
                // not rely on CopyFile overwriting it, nor copy 1 MiB again.
                if (saved != profile)
                {
                    if (FileExist(backup))
                    {
                        // A torn legacy backup is replaceable only while its
                        // full verified source profile is still intact.
                        if (mode == "legacy_schema")
                        {
                            bool tornBackup = saved == "";
                            if (tornBackup)
                            {
                                FileHandle backupHandle = OpenFile(backup, FileMode.READ);
                                if (!backupHandle) { Print(refused + "legacy_backup_unreadable"); return false; }
                                string backupProbe;
                                int backupBytes = ReadFile(backupHandle, backupProbe, 1);
                                CloseFile(backupHandle);
                                if (backupBytes != 0) { Print(refused + "legacy_backup_not_empty"); return false; }
                            }
                            if (!tornBackup && saved.Length() < profile.Length())
                            {
                                tornBackup = profile.Substring(0, saved.Length()) == saved;
                            }
                            if (!tornBackup) { Print(refused + "legacy_backup_conflict"); return false; }
                            rebuildLegacy = true;
                        }
                        if (!DeleteFile(backup)) { Print(refused + "backup_delete"); return false; }
                    }
                    if (!CopyFile(target, backup)) { Print(refused + "backup_copy"); return false; }
                    if (HCProfileDefaults.ReadText(backup) != profile) { Print(refused + "backup_readback"); return false; }
                    if (rebuildLegacy) { Print("[HC AI Defaults] recovered file=" + relative + " reason=legacy_backup_rebuilt"); }
                }
                if (mode == "provenance" && !HCProfileDefaults.WriteText(priorPath, profile)) { Print(refused + "prior_readback"); return false; }
            }
            else if (!HCProfileDefaults.PrepareParents(relative)) { Print(refused + "directory"); return false; }
            // Durable intent follows verified backup (or an absent fresh target).
            if (!HCProfileDefaults.WriteText(temporary, shipped)) { Print(refused + "tmp_readback"); return false; }
        }
        // Never assume CopyFile can overwrite. The backup/intent survives both
        // a crash in the delete-copy gap and a torn copy/origin write.
        if (FileExist(target) && !DeleteFile(target)) { Print(refused + "target_delete"); return false; }
        if (!CopyFile(temporary, target)) { Print(refused + "target_copy"); return false; }
        if (HCProfileDefaults.ReadText(target) != shipped) { Print(refused + "target_readback"); return false; }
        if (!HCProfileDefaults.WriteText(originPath, shipped)) { Print(refused + "origin_readback"); return false; }
        if (!DeleteFile(temporary)) { Print(refused + "tmp_delete"); return false; }
        if (FileExist(priorPath) && !DeleteFile(priorPath)) { Print(refused + "prior_delete"); return false; }
        Print("[HC AI Defaults] adopted file=" + relative + " mode=" + mode + "; runtime=PENDING");
        return true;
    }
}
