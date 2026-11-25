// Respawn2: preserve exact shipped bytes as provenance (no hash collision or
// invented engine hash API). Only unchanged mod-written profiles auto-upgrade.
// Reuses HCProfileDefaults bounded IO and temp/readback; recovery images stay.
// Native scripts-1.30.164289/1_Core/proto/EnSystem.c:397 FileExist,
// :528 DeleteFile, :531 CopyFile; EnString.c:113 Substring, :199 Length,
// :448 Get; EnScript.c:380 Count, :394 Find, :399 Get, :407 Insert; EnDebug.c:96 Print.
// Native 3_Game/tools/JsonFileLoader.c:69 LoadData. Missing SchemaVersion
// zero-fills; an invalid/unknown schema never authorizes legacy replacement.
// Native 2_GameLib/tools.c:61/65 CallLater/Remove;
// 3_Game/Global/Game.c:914 GetTickTime, :1550 GetCallQueue.
class HCXAIRespawnSchema
{
    int SchemaVersion;
}
// Disposable negative-verdict receipt, never authority to replace a profile.
// A torn receipt is just a miss: the reader requires every byte to match its
// versioned envelope and BOTH current inputs. No origin/prior receipt changes.
// Native EnSystem.c:417 OpenFile, :462 FPrint, :443 CloseFile (snapshot above).
class HCXAIRespawnSchemaCacheJob : HCSaveJob
{
    string Path;
    string Profile;
    string Shipped;
    bool Verdict;
    string Image;
    bool Terminal;
    bool Released;
    protected FileHandle m_Handle;
    protected bool m_Open;
    protected int m_Stage;
    protected int m_Offset;

    override string HCName() { return "AIProfileSchemaCache"; }

    void ~HCXAIRespawnSchemaCacheJob()
    {
        if (m_Open) { CloseFile(m_Handle); }
    }

    override int HCStep()
    {
        if (Terminal) { return STEP_DONE; }
        if (m_Stage == 0)
        {
            HCOperation = "schema_cache_open";
            m_Handle = OpenFile(Path + ".hcdefault.schema", FileMode.WRITE);
            if (!m_Handle)
            {
                Print("[HC AI Defaults] older_schema_cache reason=cache_open_failed retry=next_boot runtime=PENDING");
                Terminal = true;
                Image = "";
                return STEP_DONE;
            }
            m_Open = true;
            m_Stage = 1;
            return STEP_MORE;
        }
        if (m_Stage == 1)
        {
            HCOperation = "schema_cache_write";
            int length = Image.Length() - m_Offset;
            if (length > 4096) { length = 4096; }
            string piece = Image.Substring(m_Offset, length);
            if (piece.Length() != length)
            {
                Print("[HC AI Defaults] older_schema_cache reason=cache_chunk_failed retry=next_boot runtime=PENDING");
                m_Stage = 2;
                return STEP_MORE;
            }
            FPrint(m_Handle, piece);
            m_Offset = m_Offset + length;
            if (m_Offset >= Image.Length()) { m_Stage = 2; }
            return STEP_MORE;
        }
        HCOperation = "schema_cache_close";
        CloseFile(m_Handle);
        m_Open = false;
        Image = "";
        Terminal = true;
        // FPrint has no result. Full byte equality on the NEXT lookup is the
        // verification boundary; an incomplete cache can never grant migration.
        return STEP_DONE;
    }
}

class HCXAIRespawnDefaults
{
    protected static ref array<ref HCXAIRespawnSchemaCacheJob> s_SchemaMemos = new array<ref HCXAIRespawnSchemaCacheJob>;
    protected static ref HCWorkBudget s_CacheBudget = new HCWorkBudget;
    protected static int s_CacheCursor;
    protected static int s_CacheWrites;
    protected static bool s_BootReceiptScheduled;
    protected static int s_SchemaScans;
    protected static int s_SchemaHits;

    protected static void HCSchemaBootReceipt()
    {
        string verdict = "cached";
        if (s_SchemaScans > 0) { verdict = "scanned"; }
        Print("[HC AI Defaults] older_schema verdict=" + verdict + " scans=" + s_SchemaScans.ToString() + " hits=" + s_SchemaHits.ToString() + " key=exact_content reason=native_file_metadata_unavailable runtime=PENDING");
    }

    // Snapshot EnSystem.c:397-531 has no file size/mtime API. Exact bytes are
    // the invalidation key, including shipped bytes so an addon update misses.
    // This still reads on a warm boot; it skips JSON decode and key scans only.
    // Bump the envelope version whenever HCScanOlderSchema semantics change.
    protected static string HCSchemaImage(string profile, string shipped)
    {
        string image = "HC_OLDER_SCHEMA_V1_FALSE\n";
        image += profile.Length().ToString() + "\n";
        image += shipped.Length().ToString() + "\n";
        image += profile;
        image += shipped;
        return image;
    }

    protected static bool HCSchemaReceiptMatches(string path, string expected)
    {
        // Native EnSystem.c:417/425/443. Two <=1 MiB inputs plus <=64
        // envelope bytes; bounded probe rejects trailing data as well as tears.
        FileHandle handle = OpenFile(path + ".hcdefault.schema", FileMode.READ);
        if (!handle) { return false; }
        string image;
        int count = ReadFile(handle, image, 2097217);
        CloseFile(handle);
        return count == expected.Length() && image == expected;
    }

    protected static HCXAIRespawnSchemaCacheJob HCSchemaMemo(string path, string profile, string shipped)
    {
        // At most eight profile/legacy inputs; no eviction or retry loop.
        for (int index = 0; index < 8; index++)
        {
            if (index >= s_SchemaMemos.Count()) { break; }
            HCXAIRespawnSchemaCacheJob memo = s_SchemaMemos.Get(index);
            if (memo.Path == path && memo.Profile == profile && memo.Shipped == shipped) { return memo; }
        }
        return null;
    }

    protected static void HCStepSchemaCaches()
    {
        s_CacheBudget.HCReset(1);
        if (!s_CacheBudget.HCContinue() || s_SchemaMemos.Count() == 0) { return; }
        if (s_CacheCursor >= s_SchemaMemos.Count()) { s_CacheCursor = 0; }
        HCXAIRespawnSchemaCacheJob memo = s_SchemaMemos.Get(s_CacheCursor);
        s_CacheCursor++;
        HCSaveScheduler.HCPumpFallback(memo);
        if (memo.Terminal && !memo.Released)
        {
            HCSaveScheduler.HCUnregister(memo);
            memo.Released = true;
            s_CacheWrites--;
        }
        if (s_CacheWrites == 0)
        {
            GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).Remove(HCXAIRespawnDefaults.HCStepSchemaCaches);
        }
    }

    static bool HCOlderSchema(string profile, string shipped, string path)
    {
        HCXAIRespawnSchemaCacheJob memo = HCSchemaMemo(path, profile, shipped);
        if (memo) { s_SchemaHits++; return memo.Verdict; }
        string image = HCSchemaImage(profile, shipped);
        bool cached = HCSchemaReceiptMatches(path, image);
        bool verdict = false;
        if (cached) { s_SchemaHits++; }
        else { s_SchemaScans++; verdict = HCScanOlderSchema(profile, shipped); }
        if (s_SchemaMemos.Count() >= 8) { return verdict; }
        memo = new HCXAIRespawnSchemaCacheJob;
        memo.Path = path;
        memo.Profile = profile;
        memo.Shipped = shipped;
        memo.Verdict = verdict;
        s_SchemaMemos.Insert(memo);
        // Persist only negative verdicts. A disposable receipt can suppress an
        // unnecessary scan, but can NEVER authorize replacing an operator file.
        // Positive results are memoized in memory; migration retains its own
        // existing origin/prior/backup protocol and warms via origin equality.
        if (!cached && !verdict)
        {
            memo.Image = image;
            HCSaveScheduler.HCRegister(memo);
            memo.HCDirty = true;
            memo.HCUrgent = true;
            memo.HCDue = GetGame().GetTickTime();
            s_CacheWrites++;
            GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).Remove(HCXAIRespawnDefaults.HCStepSchemaCaches);
            GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(HCXAIRespawnDefaults.HCStepSchemaCaches, 1000, true);
        }
        return verdict;
    }

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

    protected static bool HCScanOlderSchema(string profile, string shipped)
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
        if (!s_BootReceiptScheduled)
        {
            s_BootReceiptScheduled = true;
            // All four provisioning calls run on this startup stack. One deferred
            // line reports whether ANY required schema lookup actually scanned.
            GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(HCXAIRespawnDefaults.HCSchemaBootReceipt, 1, false);
        }
        string refused = "[HC AI Defaults] refused file=" + relative + " reason=";
        string shipped = HCProfileDefaults.ReadText(source);
        if (shipped == "") { Print(refused + "shipped_unreadable"); return false; }
        string target = "$profile:HollowCountry/" + relative;
        string originPath = target + ".hcdefault.origin";
        string profile = HCProfileDefaults.ReadText(target, false);
        string origin = HCProfileDefaults.ReadText(originPath);
        string backup = target + ".hcdefault.bak";
        string temporary = target + ".hcdefault.tmp";
        string priorPath = target + ".hcdefault.prior";
        string mode = "provenance";
        string staged = HCProfileDefaults.ReadText(temporary);
        bool hasTemporary = FileExist(temporary);
        // Empty ReadText can also mean oversized/unreadable. An open failure
        // must keep our intent: a transient sharing lock cannot retire the only
        // witness authorizing repair of a torn target on a later boot.
        if (profile == "" && FileExist(target))
        {
            FileHandle probeHandle = OpenFile(target, FileMode.READ);
            string probe;
            int probeBytes = -1;
            if (probeHandle)
            {
                probeBytes = ReadFile(probeHandle, probe, 1);
                CloseFile(probeHandle);
            }
            if (probeBytes < 0)
            {
                Print(refused + "profile_unreadable");
                return false;
            }
            if (probeBytes > 0)
            {
                if (hasTemporary && !DeleteFile(temporary)) { Print(refused + "tmp_delete"); return false; }
                Print(refused + "profile_too_large");
                return false;
            }
        }
        // A stale complete intent still witnesses an absent/empty target or a
        // strict prefix torn from that image, even after shipped bytes change.
        bool staleTorn = false;
        if (hasTemporary && staged != shipped)
        {
            staleTorn = profile == "";
            if (!staleTorn && profile.Length() < staged.Length())
            {
                staleTorn = staged.Substring(0, profile.Length()) == profile;
            }
            if (!staleTorn)
            {
                if (!DeleteFile(temporary)) { Print(refused + "stale_tmp_delete"); return false; }
                hasTemporary = false;
                Print("[HC AI Defaults] recovered file=" + relative + " reason=stale_tmp_removed");
            }
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
        if (origin == shipped && FileExist(target) && !staleTorn)
        {
            if (hasTemporary && !DeleteFile(temporary)) { Print(refused + "operator_tmp_delete"); return false; }
            Print(refused + "operator_modified");
            return true;
        }
        bool resume = staleTorn;
        if (hasTemporary)
        {
            // One bounded bulk compare; do not scan schemas for torn targets.
            bool torn = profile == "";
            if (!torn && profile.Length() < shipped.Length())
            {
                torn = shipped.Substring(0, profile.Length()) == profile;
            }
            bool matchesBackup = false;
            if (!torn && !staleTorn)
            {
                string prior = HCProfileDefaults.ReadText(backup);
                string receipt = HCProfileDefaults.ReadText(priorPath);
                bool verifiedPrior = prior != "" && (prior == origin || prior == receipt);
                if (!verifiedPrior)
                {
                    // Read compatibility only: never rewrite an operator .bak.
                    prior = HCProfileDefaults.ReadText(target + ".bak");
                    verifiedPrior = prior != "" && (prior == origin || prior == receipt);
                }
                matchesBackup = verifiedPrior && profile == prior;
                if (!matchesBackup)
                {
                    string legacy = HCProfileDefaults.ReadText(target + ".legacy.bak");
                    if (legacy != "" && profile == legacy)
                    {
                        matchesBackup = HCXAIRespawnDefaults.HCOlderSchema(legacy, shipped, target + ".legacy.bak");
                        if (!matchesBackup && localities) { matchesBackup = HCXAIRespawnDefaults.HCOlderLocalities(legacy, shipped); }
                    }
                }
            }
            resume = resume || torn || matchesBackup;
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
                if (profile == "") { Print(refused + "profile_empty_unprovenanced"); return false; }
                if (origin == "")
                {
                    bool older = HCXAIRespawnDefaults.HCOlderSchema(profile, shipped, target);
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
            else
            {
                if (!HCProfileDefaults.PrepareParents(relative)) { Print(refused + "directory"); return false; }
                mode = "fresh";
            }
            // Durable intent follows verified backup (or an absent fresh target).
            if (!HCProfileDefaults.WriteText(temporary, shipped)) { Print(refused + "tmp_readback"); return false; }
        }
        // Never assume CopyFile can overwrite. The backup/intent survives both
        // a crash in the delete-copy gap and a torn copy/origin write.
        if (FileExist(target) && !DeleteFile(target)) { Print(refused + "target_delete"); return false; }
        // Keep the old intent intact until its torn target is gone. A crash
        // while refreshing intent then leaves an absent, recoverable target.
        if (staleTorn)
        {
            if (!HCProfileDefaults.WriteText(temporary, shipped)) { Print(refused + "tmp_readback"); return false; }
            Print("[HC AI Defaults] recovered file=" + relative + " reason=stale_tmp_torn");
        }
        // A deleted profile can retain a current completed origin. Retire it
        // before copying again: otherwise a crash here would make our own torn
        // fresh/resumed target look like a completed adoption's operator edit.
        if (origin == shipped && FileExist(originPath))
        {
            if (!DeleteFile(originPath)) { Print(refused + "origin_delete"); return false; }
        }
        if (!CopyFile(temporary, target)) { Print(refused + "target_copy"); return false; }
        if (HCProfileDefaults.ReadText(target) != shipped) { Print(refused + "target_readback"); return false; }
        if (!HCProfileDefaults.WriteText(originPath, shipped)) { Print(refused + "origin_readback"); return false; }
        if (!DeleteFile(temporary)) { Print(refused + "tmp_delete"); return false; }
        if (FileExist(priorPath) && !DeleteFile(priorPath)) { Print(refused + "prior_delete"); return false; }
        Print("[HC AI Defaults] adopted file=" + relative + " mode=" + mode + "; runtime=PENDING");
        return true;
    }
}
