// LC-T302. Native evidence in scripts-1.30.164289:
// 1_Core/proto/EnSystem.c:76,100 (UTC date/time), :397 (FileExist),
// :417,425,443,462 (OpenFile/ReadFile/CloseFile/FPrint), :525,528,531
// (MakeDirectory/DeleteFile/CopyFile); 3_Game/tools/JsonFileLoader.c:69,85
// (LoadData/MakeData); 1_Core/proto/EnString.c:113,199,240,448 (string access),
// 1_Core/proto/EnDebug.c:96 (Print). UTC delegates to the existing
// Groups/HCGroupService.c:76 HCGroupClock.Utc() calendar helper.
// There is NO native rename API in this snapshot. Verified temp -> backup ->
// copy promotion with a retained temp intent is fail-closed, NOT OS-atomic
// rename/fsync. Interrupted promotion starts fresh and never rolls back loot.
class HCWorldClock
{
    static int UTC()
    {
        // Reuse the project's bracketed, overflow-safe UTC calendar and
        // monotonic watermark. Allow room for the longest scheduled expiry.
        int now = HCGroupClock.Utc();
        if (now < 1 || now > 2146878847) { return 0; }
        return now;
    }

    static int Day(HCWorldData data, int now)
    {
        if (!data || !data.Meta || now <= data.Meta.Epoch) { return 0; }
        return (now - data.Meta.Epoch) / HCWorldLimits.DAY;
    }
}

class HCWorldStore
{
    static const int MAX_BYTES = 1048576;
    protected string m_Path = "$profile:HollowCountry/world.json";
    protected string m_Temp = "$profile:HollowCountry/world.json.tmp";
    protected string m_Backup = "$profile:HollowCountry/world.json.bak";
    protected ref HCWorldData m_Data;
    protected bool m_KeepBackup;
    protected bool m_Fresh;
    protected bool m_Fault;
    protected string m_VerifiedText;
    protected int m_SaveStage;
    protected string m_PendText;
    protected string m_PendPrior;

    bool Prepare()
    {
        return FileExist("$profile:HollowCountry") || MakeDirectory("$profile:HollowCountry");
    }

    static string Read(string path)
    {
        FileHandle handle = OpenFile(path, FileMode.READ);
        if (!handle) { return ""; }
        string text;
        int count = ReadFile(handle, text, MAX_BYTES + 1);
        CloseFile(handle);
        if (count < 1 || count > MAX_BYTES || text.Length() < 1 || text.Length() > MAX_BYTES) { return ""; }
        return text;
    }

    static bool Write(string path, string text)
    {
        if (text.Length() < 1 || text.Length() > MAX_BYTES) { return false; }
        FileHandle handle = OpenFile(path, FileMode.WRITE);
        if (!handle) { return false; }
        FPrint(handle, text);
        CloseFile(handle);
        return Read(path) == text;
    }

    // JSON serializer compatibility can ignore unknown fields. Since the DTOs
    // use no maps, allow only authored field names at ANY nesting depth. In
    // particular PlayerId/PlayerPosition/standing cannot be silently discarded.
    // This is a bounded key scan; native JsonFileLoader still parses the JSON.
    static bool KeysAllowed(string text)
    {
        string keys = "|Meta|SchemaVersion|Epoch|LastTick|BuildId|Places|Id|Name|Position|Facts|Kind|PlaceId|Severity|At|Expires|FactHead|Factions|Ethos|ProviderFaction|Strength|Territory|Hostile|Neutral|Alert|LastAlertDecay|LastRegrowth|Holdouts|FactionId|HouseClass|HousePos|CacheRef|Occupants|State|Since|ReoccupyAfter|Routine|Parties|Size|Route|Edge|Progress|Carry|Home|DailyTransfers|TransferDay|LastMoved|Materialized|SiteMemory|Event|MemoryHead|Leads|TargetPlaceId|Source|GroupId|TextId|Scenes|SiteId|ChainId|Stage|NoteId|Notes|SceneId|EntityRef|CreatedAt|Camps|FireRef|Tier|Members|LastLit|Flag|LastVisit|LastProbe|LastTheft|NeighboursLost|TheftRows|CampId|ContainerRef|ItemRef|PartyId|Phase|Salvage|WreckId|Remaining|Journal|Escalation|Day|PressureCaps|Maximum|";
        bool quoted;
        bool escaped;
        int start;
        for (int keyIndex = 0; keyIndex < text.Length(); keyIndex++)
        {
            string character = text.Get(keyIndex);
            if (quoted)
            {
                if (escaped) { escaped = false; continue; }
                if (character == "\\") { escaped = true; continue; }
                if (character != "\"") { continue; }
                quoted = false;
                int after = keyIndex + 1;
                while (after < text.Length() && (text.Get(after) == " " || text.Get(after) == "\n" || text.Get(after) == "\r" || text.Get(after) == "\t")) { after++; }
                if (after < text.Length() && text.Get(after) == ":")
                {
                    string key = text.Substring(start, keyIndex - start);
                    if (key.Length() < 1 || keys.IndexOf("|" + key + "|") < 0) { return false; }
                }
            }
            else
            {
                if (character == "\"") { quoted = true; start = keyIndex + 1; }
            }
        }
        return !quoted;
    }

    static bool Migrate(HCWorldData data)
    {
        // Schema remains compatible: existing place IDs/indices never change.
        if (!data || !data.Meta || data.Meta.SchemaVersion != HCWorldLimits.SCHEMA) { return false; }
        if (!HCWorldData.Valid(data)) { return false; }
        HCWorldData.ExtendPlaces(data);
        return true;
    }

    static HCWorldData Decode(string text)
    {
        if (text.Length() < 1 || text.Length() > MAX_BYTES || !KeysAllowed(text)) { return null; }
        // Migrate validates the full input, then appends only validated places.
        // Repeating the same whole-ledger validation here doubles startup work.
        HCWorldData decoded;
        string error;
        if (!JsonFileLoader<HCWorldData>.LoadData(text, decoded, error) || !Migrate(decoded)) { return null; }
        return decoded;
    }

    bool ReadCurrent()
    {
        string text = Read(m_Path);
        HCWorldData current = Decode(text);
        if (!current || current.Meta.Epoch > HCWorldClock.UTC()) { return false; }
        m_Data = current;
        m_VerifiedText = text;
        return true;
    }

    bool Load()
    {
        m_Data = HCWorldData.Fresh(HCWorldClock.UTC());
        if (m_Data.Meta.Epoch < 1) { return false; }
        if (!Prepare()) { return false; }
        bool pending = FileExist(m_Temp);
        bool image = FileExist(m_Path);
        if (pending || (image && !ReadCurrent()))
        {
            m_KeepBackup = true;
            m_Fresh = true;
            // Review P1: keep the rejected primary and any interrupted temp image
            // aside before a fresh world may ever be saved over them. If they
            // cannot be preserved, run memory-only and never write.
            if (!Preserve(m_Path) || !Preserve(m_Temp))
            {
                m_Fault = true;
                Print("[HollowCountry] V2 world load rejected; rejected image could not be preserved; running memory-only, writes suspended");
                return true;
            }
            Print("[HollowCountry] V2 world load rejected; fresh world; rejected image kept as world.json.rejected, backup preserved");
            return true;
        }
        if (!image)
        {
            m_KeepBackup = FileExist(m_Backup);
            m_Fresh = true;
        }
        return true;
    }

    // Copy a rejected file to <file>.rejected (replacing an older one) and, for
    // the temp image, remove it so the next save starts clean. Missing is fine.
    protected bool Preserve(string file)
    {
        if (!FileExist(file)) { return true; }
        string kept = file + ".rejected";
        string original = Read(file);
        if (FileExist(kept) && !DeleteFile(kept)) { return false; }
        if (!CopyFile(file, kept) || Read(kept) != original) { return false; }
        if (file == m_Temp && !DeleteFile(m_Temp)) { return false; }
        return true;
    }

    HCWorldData Data() { return m_Data; }
    bool Fresh() { return m_Fresh; }

    bool Fault()
    {
        m_Fault = true;
        Print("[HollowCountry] V2 world save failed; files preserved; writes suspended");
        return false;
    }

    // JSON serialization of the validated ledger; "" when the serializer or the size cap refuses.
    static string Encode(HCWorldData data)
    {
        string text;
        string error;
        if (!JsonFileLoader<HCWorldData>.MakeData(data, text, error) || text.Length() > MAX_BYTES) { return ""; }
        return text;
    }

    bool SaveInFlight() { return m_SaveStage != 0; }

    protected int SaveFailed()
    {
        m_SaveStage = 0;
        m_PendText = "";
        m_PendPrior = "";
        Fault();
        return HCSaveJob.STEP_FAILED;
    }

    // Issue #138: one bounded stage of a checkpoint per call (HCSaveScheduler runs one stage per tick).
    //   stage 0: validate + serialize the SNAPSHOT (no file I/O).
    //   stage 1: read the primary image and compare it with the exact verified image (no write).
    //   stage 2: the unchanged commit sequence, in ONE call, because the temp image is the durability
    //            intent: a crash with it present is rejected on the next load, so it is never left
    //            standing across ticks.
    // Same files, same order, same fault handling as the former whole-store Save.
    int SaveStep(HCWorldData data)
    {
        if (m_Fault)
        {
            m_SaveStage = 0;
            m_PendText = "";
            m_PendPrior = "";
            return HCSaveJob.STEP_FAILED;
        }
        if (m_SaveStage == 0)
        {
            if (!HCWorldData.Valid(data)) { return SaveFailed(); }
            m_PendText = Encode(data);
            if (m_PendText == "") { return SaveFailed(); }
            m_PendPrior = "";
            m_SaveStage = 1;
            return HCSaveJob.STEP_MORE;
        }
        if (m_SaveStage == 1)
        {
            // Load marks corrupt/interrupted state fresh. Never copy that primary
            // over a good backup, and never automatically restore a prior world.
            if (!m_Fresh && !m_KeepBackup && FileExist(m_Path))
            {
                m_PendPrior = Read(m_Path);
                // Compare with the exact image validated on load/last write. This
                // preserves external-edit refusal without reparsing every old key
                // and every DTO during each checkpoint (W5-PERF-2).
                if (m_PendPrior == "" || m_PendPrior != m_VerifiedText) { return SaveFailed(); }
            }
            m_SaveStage = 2;
            return HCSaveJob.STEP_MORE;
        }
        string text = m_PendText;
        string prior = m_PendPrior;
        m_SaveStage = 0;
        m_PendText = "";
        m_PendPrior = "";
        if (!Write(m_Temp, text)) { return SaveFailed(); }
        if (prior != "")
        {
            if (FileExist(m_Backup) && !DeleteFile(m_Backup)) { return SaveFailed(); }
            if (!CopyFile(m_Path, m_Backup) || Read(m_Backup) != prior) { return SaveFailed(); }
        }
        // No guessed rename call: intent remains until copy and readback pass.
        // A crash at any point below makes the next load reject the image.
        if (FileExist(m_Path) && !DeleteFile(m_Path)) { return SaveFailed(); }
        if (!CopyFile(m_Temp, m_Path) || Read(m_Path) != text) { return SaveFailed(); }
        if (!DeleteFile(m_Temp)) { return SaveFailed(); }
        m_Fresh = false;
        m_VerifiedText = text;
        return HCSaveJob.STEP_DONE;
    }

    // Synchronous whole save: the same stages back to back (shutdown and barrier callers).
    bool Save(HCWorldData data)
    {
        if (m_Fault) { return false; }
        m_SaveStage = 0;
        int result = HCSaveJob.STEP_MORE;
        int guard = 0;
        while (result == HCSaveJob.STEP_MORE && guard < 4)
        {
            result = SaveStep(data);
            guard = guard + 1;
        }
        return result == HCSaveJob.STEP_DONE;
    }
}
