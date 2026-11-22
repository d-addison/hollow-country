// LC-T302. Native evidence in scripts-1.30.164289:
// 1_Core/proto/EnSystem.c:76,100 (UTC date/time), :397 (FileExist),
// :417,425,443,462 (OpenFile/ReadFile/CloseFile/FPrint), :525,528,531
// (MakeDirectory/DeleteFile/CopyFile); 3_Game/tools/JsonFileLoader.c:69,85
// (LoadData/MakeData); 1_Core/proto/EnString.c:113,199,240,448 (string access),
// 1_Core/proto/EnDebug.c:96 (Print). UTC delegates to the existing
// Groups/HCGroupService.c:76 HCGroupClock.Utc() calendar helper.
// There is NO native rename API in this snapshot. Verified temp -> backup ->
// copy promotion with a retained temp intent is fail-closed, NOT OS-atomic
// rename/fsync. Load finishes a verified interrupted promotion or drops a partial
// intent (RecoverIntent); any other interrupted pair quarantines.
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
    protected ref HCStagedSaveImage m_SaveImage = new HCStagedSaveImage;
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

    // Unlike Read(), preserve read failures separately from readable invalid JSON.
    // An empty/oversize file was read successfully and must fail DTO validation.
    static bool ReadChecked(string path, out string text)
    {
        text = "";
        FileHandle handle = OpenFile(path, FileMode.READ);
        if (!handle) { return false; }
        int count = ReadFile(handle, text, MAX_BYTES + 1);
        CloseFile(handle);
        return count >= 0 && count <= MAX_BYTES + 1 && count == text.Length();
    }

    protected static bool s_RawTested;
    protected static bool s_RawEnabled;
    protected static int s_CompareCalls;
    protected static int s_RejectCompareCalls;
    static const int HC_COMPARE_LIMIT = 128;

    static void HCResetCompareBudget() { s_CompareCalls = 0; }

    // Per-start allowance shared by boot/retries: 128 comparisons, each reading
    // at most 1 MiB plus one 4 KiB EOF probe per side. Exhaustion retains sources.
    static bool RawEqual(string left, string right)
    {
        if (!s_RawTested) { HCTestRawRead(); }
        if (s_CompareCalls >= HC_COMPARE_LIMIT) { return false; }
        s_CompareCalls++;
        if (s_RawEnabled)
        {
            return HCRawEqual(left, right);
        }
        string a;
        string b;
        if (!ReadChecked(left, a) || !ReadChecked(right, b)) { return false; }
        return a.Length() > 0 && a.Length() <= MAX_BYTES && a == b;
    }

    // Independent boot/retry budget: archive rejection cannot exhaust custody's
    // 128 comparisons and force a durable unverified-source relocation.
    static bool RejectRawEqual(string left, string right)
    {
        if (!s_RawTested) { HCTestRawRead(); }
        if (s_RejectCompareCalls >= HC_COMPARE_LIMIT) { return false; }
        s_RejectCompareCalls++;
        if (!s_RawEnabled) { return false; }
        return HCRawEqual(left, right);
    }

    // EnSystem.c:397/417/425: FileExist proves existence, not readability;
    // OpenFile returns 0 on failure, ReadFile reads raw bytes into int[] or
    // string and returns a byte count. Use raw one-byte reads so NUL never
    // passes through string IO; zero the receiving int before every byte so
    // neither packed-byte nor per-element array transfers retain prior bits.
    // Boot/retry only: at most 13 calls/bytes (12-byte cap plus EOF/size probe).
    static bool ReadCeilingChecked(string path, out string text)
    {
        text = "";
        FileHandle handle = OpenFile(path, FileMode.READ);
        if (!handle) { return false; }
        int rawByte[1];
        for (int offset = 0; offset < 13; offset++)
        {
            rawByte[0] = 0;
            int count = ReadFile(handle, rawByte, 1);
            if (count < 0 || count > 1) { CloseFile(handle); text = ""; return false; }
            if (count == 0) { CloseFile(handle); return true; }
            int value = rawByte[0];
            bool grammarByte = value == 124 || (value >= 48 && value <= 57);
            if (offset == 12 || !grammarByte) { CloseFile(handle); text = ""; return true; }
            text += value.AsciiToString();
        }
        CloseFile(handle);
        text = "";
        return true;
    }

    // EnSystem.c:425 leaves the array unit ambiguous. Allocate enough elements
    // even if length means elements; reject impossible return counts BEFORE
    // indexing. Zero bytes, errors and oversize images never prove equality.
    protected static bool HCRawEqual(string left, string right)
    {
        FileHandle a = OpenFile(left, FileMode.READ);
        if (!a) { return false; }
        FileHandle b = OpenFile(right, FileMode.READ);
        if (!b) { CloseFile(a); return false; }
        int x[4096];
        int y[4096];
        int total;
        bool equal;
        while (total <= MAX_BYTES)
        {
            int nx = ReadFile(a, x, 4096);
            int ny = ReadFile(b, y, 4096);
            if (nx < 0 || ny < 0 || nx > 4096 || ny > 4096 || nx != ny || total + nx > MAX_BYTES) { break; }
            if (nx == 0) { equal = total > 0; break; }
            bool different = false;
            for (int i = 0; i < nx && i < 4096; i++)
            {
                if (x[i] != y[i]) { different = true; break; }
            }
            if (different) { break; }
            total += nx;
        }
        CloseFile(a);
        CloseFile(b);
        return equal;
    }

    protected static bool HCRawCounts(string path)
    {
        FileHandle handle = OpenFile(path, FileMode.READ);
        if (!handle) { return false; }
        int buffer[4096];
        int first = ReadFile(handle, buffer, 4096);
        int second = ReadFile(handle, buffer, 4096);
        int eof = ReadFile(handle, buffer, 4096);
        CloseFile(handle);
        return first == 4096 && second == 904 && eof == 0;
    }

    // One-time native qualification before the first raw comparison. Fixtures
    // are disposable, actor-free profile files. EnConvert.c:44 AsciiToString.
    // A NUL that cannot be emitted/read exactly disables raw comparisons too.
    protected static void HCTestRawRead()
    {
        s_RawTested = true;
        string a = "$profile:HollowCountry/custody-read-selftest-a";
        string b = "$profile:HollowCountry/custody-read-selftest-b";
        string empty = "$profile:HollowCountry/custody-read-selftest-empty";
        FileHandle fa = OpenFile(a, FileMode.WRITE);
        FileHandle fb = OpenFile(b, FileMode.WRITE);
        FileHandle fe = OpenFile(empty, FileMode.WRITE);
        if (fa && fb && fe)
        {
            int nul;
            string zero = nul.AsciiToString();
            string block;
            for (int n = 0; n < 1000; n++) { block += "a"; }
            for (int chunk = 0; chunk < 5; chunk++)
            {
                string left = block;
                string right = block;
                if (chunk == 4 && block.Length() == 1000)
                {
                    left = block.Substring(0, 500) + zero + block.Substring(501, 499);
                    right = block.Substring(0, 500) + "b" + block.Substring(501, 499);
                }
                FPrint(fa, left);
                FPrint(fb, right);
            }
        }
        if (fa) { CloseFile(fa); }
        if (fb) { CloseFile(fb); }
        if (fe) { CloseFile(fe); }
        // The differing byte must survive beyond the first 4096-byte read.
        // Never enable the raw path when the NUL fixture was shortened.
        string fixture;
        FileHandle check = OpenFile(a, FileMode.READ);
        int length = -1;
        if (check) { length = ReadFile(check, fixture, 6000); CloseFile(check); }
        bool qualified = true;
        if (!fa) { qualified = false; }
        if (!fb) { qualified = false; }
        if (!fe) { qualified = false; }
        if (length != 5000) { qualified = false; }
        if (qualified) { qualified = HCRawCounts(a); }
        if (qualified) { qualified = HCRawCounts(b); }
        if (qualified) { qualified = HCRawEqual(a, a); }
        if (qualified) { qualified = !HCRawEqual(a, b); }
        if (qualified) { qualified = !HCRawEqual(empty, empty); }
        s_RawEnabled = qualified;
        DeleteFile(a);
        DeleteFile(b);
        DeleteFile(empty);
        if (!s_RawEnabled) { Print("[HC WorldStore] custody_raw_compare_disabled reason=native_selftest_failed string_fallback=true"); }
        else { Print("[HC WorldStore] custody_raw_compare_selftest pass=true"); }
    }

    // JSON serializer compatibility can ignore unknown fields. Since the DTOs
    // use no maps, allow only authored field names at ANY nesting depth. In
    // particular PlayerId/PlayerPosition/standing cannot be silently discarded.
    // This is a bounded key scan; native JsonFileLoader still parses the JSON.
    static bool KeysAllowed(string text)
    {
        string keys = "|Meta|SchemaVersion|Epoch|LastTick|BuildId|Places|Id|Name|Position|Facts|Kind|PlaceId|Severity|At|Expires|FactHead|Factions|Ethos|ProviderFaction|Strength|Territory|Hostile|Neutral|Alert|LastAlertDecay|LastRegrowth|Holdouts|FactionId|HouseClass|HousePos|CacheRef|Occupants|State|Since|ReoccupyAfter|Routine|Parties|Size|Route|Edge|Progress|Carry|Home|DailyTransfers|TransferDay|LastMoved|Materialized|SiteMemory|Event|MemoryHead|Leads|TargetPlaceId|Source|GroupId|TextId|Scenes|SiteId|ChainId|Stage|NoteId|Notes|SceneId|EntityRef|CreatedAt|Camps|FireRef|Tier|Members|LastLit|Flag|LastVisit|LastProbe|LastTheft|NeighboursLost|TheftRows|CampId|ContainerRef|ItemRef|PartyId|Phase|Salvage|WreckId|Remaining|Journal|Escalation|Day|PressureCaps|Maximum|";
        return HCJsonSchema.HCKeysAllowed(text, keys, MAX_BYTES, 0);
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

    // Finishes or drops a save interrupted by a crash or hard stop (#237). Each
    // HCStagedSaveImage.HCStepImage boundary leaves one of these on disk:
    //   write_tmp: partial intent, old primary and backup untouched -> drop intent;
    //   read_tmp/copy_backup: verified intent, old primary intact, backup maybe
    //     partial -> back up the old primary again, then promote the intent;
    //   copy_primary: verified intent, primary missing or partial, backup = old
    //     primary -> promote the intent;
    //   read_primary/clear_intent: primary already equals the intent -> clear it.
    // A verified intent only ever moves the world forward (same epoch, LastTick
    // not older); a dropped partial intent leaves the last completed save, as if
    // the crash came just before the save began. Anything else stays quarantined.
    protected bool RecoverIntent()
    {
        string intent = Read(m_Temp);
        HCWorldData next = Decode(intent);
        string primaryText = Read(m_Path);
        HCWorldData primary = Decode(primaryText);
        if (!next)
        {
            if (!primary && (FileExist(m_Path) || FileExist(m_Backup))) { return false; }
            if (!DeleteFile(m_Temp)) { return false; }
            Print("[HollowCountry] V2 world interrupted save recovered action=dropped_partial_intent");
            return true;
        }
        if (next.Meta.Epoch > HCWorldClock.UTC()) { return false; }
        if (primary)
        {
            if (primary.Meta.Epoch != next.Meta.Epoch || primary.Meta.LastTick > next.Meta.LastTick) { return false; }
            if (primaryText != intent)
            {
                if (FileExist(m_Backup) && !DeleteFile(m_Backup)) { return false; }
                if (!CopyFile(m_Path, m_Backup) || Read(m_Backup) != primaryText) { return false; }
                if (!DeleteFile(m_Path) || !CopyFile(m_Temp, m_Path)) { return false; }
            }
        }
        else
        {
            if (FileExist(m_Backup))
            {
                HCWorldData previous = Decode(Read(m_Backup));
                if (!previous || previous.Meta.Epoch != next.Meta.Epoch || previous.Meta.LastTick > next.Meta.LastTick) { return false; }
            }
            if (FileExist(m_Path) && !DeleteFile(m_Path)) { return false; }
            if (!CopyFile(m_Temp, m_Path)) { return false; }
        }
        if (Read(m_Path) != intent || !DeleteFile(m_Temp)) { return false; }
        Print("[HollowCountry] V2 world interrupted save recovered action=promoted_intent");
        return true;
    }

    bool Load()
    {
        m_Data = null;
        m_Fresh = false;
        if (!HCPersistenceDisposition.HCAdmitStore("world")) { m_Fault = true; return false; }
        m_Fault = false;
        if (!Prepare()) { return Fault(); }
        if (FileExist(m_Temp) && !RecoverIntent())
        {
            m_Fault = true;
            return HCPersistenceDisposition.HCQuarantine("world", "world_interrupted_pair");
        }
        if (!FileExist(m_Path) && FileExist(m_Backup))
        {
            m_Fault = true;
            return HCPersistenceDisposition.HCQuarantine("world", "world_interrupted_pair");
        }
        if (!FileExist(m_Path))
        {
            m_Data = HCWorldData.Fresh(HCWorldClock.UTC());
            m_Fresh = true;
            return m_Data != null;
        }
        if (!ReadCurrent())
        {
            m_Data = null;
            m_Fault = true;
            return HCPersistenceDisposition.HCQuarantine("world", "world_parse_or_schema_failure");
        }
        if (FileExist(m_Backup))
        {
            HCWorldData previous = Decode(Read(m_Backup));
            if (!previous || previous.Meta.Epoch != m_Data.Meta.Epoch || previous.Meta.LastTick > m_Data.Meta.LastTick)
            {
                m_Data = null;
                m_Fault = true;
                return HCPersistenceDisposition.HCQuarantine("world", "world_backup_damage_or_revision_regression");
            }
        }
        return true;
    }

    HCWorldData Data() { return m_Data; }
    bool Fresh() { return m_Fresh; }

    bool Fault()
    {
        m_Fault = true;
        HCRecoveryGate.HCClose("world");
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

    // Stages 0/1 encode/check prior: original files untouched. Stage 2 begins
    // the intent transaction; HCStagedSaveImage.HCStepImage documents each subsequent
    // crash boundary. Load recovers those boundaries (RecoverIntent); backup checks unchanged.
    // Disk stage boundaries: write_tmp/read_tmp retain old primary + intent;
    // copy_backup retains old primary/backup + intent; copy_primary/read_primary
    // retain new primary, old backup and intent; clear_intent admits new primary.
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
            HCSaveJob.HCOperation = "encode";
            if (!HCWorldData.Valid(data)) { return SaveFailed(); }
            m_PendText = Encode(data);
            if (m_PendText == "") { return SaveFailed(); }
            m_PendPrior = "";
            m_SaveStage = 1;
            return HCSaveJob.STEP_MORE;
        }
        if (m_SaveStage == 1)
        {
            HCSaveJob.HCOperation = "read_prior";
            // Only a validated paired primary can reach saving. Never automatically
            // restore a prior world or overwrite a backup after a load refusal.
            // Keep the exact validated prior image. The shared writer checks it
            // in its read_prior stage, before any backup/primary promotion.
            if (!m_Fresh && !m_KeepBackup) { m_PendPrior = m_VerifiedText; }
            // Preparing the expected image is O(1); spend this slice on the
            // writer's prior check so synchronous barriers still fit eight stages.
            m_SaveStage = 2;
        }
        if (m_SaveStage == 2)
        {
            if (!m_SaveImage.Begin(m_Path, m_PendText, MAX_BYTES, m_PendPrior != "", m_PendPrior != "", m_PendPrior)) { return SaveFailed(); }
            m_SaveStage = 3;
        }
        int result = m_SaveImage.HCStepImage();
        if (result == HCSaveJob.STEP_FAILED) { return SaveFailed(); }
        if (result == HCSaveJob.STEP_MORE) { return result; }
        m_Fresh = false;
        m_VerifiedText = m_PendText;
        m_SaveStage = 0;
        m_PendText = "";
        m_PendPrior = "";
        return HCSaveJob.STEP_DONE;
    }

    // Synchronous whole save: the same stages back to back (shutdown and barrier callers).
    bool Save(HCWorldData data)
    {
        if (m_Fault) { return false; }
        // Finish an older snapshot before serializing current barrier state.
        int remainingStages;
        while (SaveInFlight() && remainingStages < HCStagedSaveImage.HC_MAX_STAGES + 3)
        {
            remainingStages++;
            if (SaveStep(data) == HCSaveJob.STEP_FAILED) { return false; }
        }
        if (SaveInFlight())
        {
            Print("[HC Persistence] owner=HCWorldStore guard=save_remaining_stage_guard steps=" + remainingStages.ToString());
            SaveFailed();
            return false;
        }
        int result = HCSaveJob.STEP_MORE;
        int guard = 0;
        while (result == HCSaveJob.STEP_MORE && guard < HCStagedSaveImage.HC_MAX_STAGES + 3)
        {
            result = SaveStep(data);
            guard = guard + 1;
        }
        if (result == HCSaveJob.STEP_MORE)
        {
            Print("[HC Persistence] owner=HCWorldStore guard=save_stage_guard steps=" + guard.ToString());
            SaveFailed();
            return false;
        }
        return result == HCSaveJob.STEP_DONE;
    }
}

// Scheduler adapter for the materializer-owned custody transaction. The owner
// retains the snapshot and resumes provider callbacks only after commit.

class HCWorldCustodySaveJob : HCSaveJob
{
    HCWorldMaterializer Owner;
    override string HCName() { return "WorldCustody"; }
    override float HCInterval() { return 0; }
    override bool HCPendingCheckpoint() { return Owner && Owner.HCCustodyCheckpointPending(); }
    override int HCStep()
    {
        if (!Owner) { return STEP_FAILED; }
        return Owner.HCStepCustody();
    }
}

// Startup-only promotion shared by bounded stores. Callers validate complete
// images and revision order before passing nonempty text. No empty-state fallback.
class HCWorldIntentRecovery
{
    protected static bool s_RotationFailurePrinted;

    protected static string FileName(string path)
    {
        int slash = path.LastIndexOf("/");
        return path.Substring(slash + 1, path.Length() - slash - 1);
    }

    protected static bool RotationFailed(string source)
    {
        if (!s_RotationFailurePrinted)
        {
            s_RotationFailurePrinted = true;
            Print("[HC World] staged_rejection path=" + FileName(source) + " reason=rotation_unverified action=retain_source_retry_next_boot");
        }
        return false;
    }

    // Rejected bytes are non-authoritative. Callers establish safe retirement
    // (verified surviving image, or a provably uncommitted first-seed tear).
    // Never copy onto an occupied destination, including after interrupted copies.
    static bool Reject(string source, int limit)
    {
        string rejected = source + ".rejected";
        int free = -1;
        for (int slot = 0; slot < 8; slot++)
        {
            string candidate = source + ".rejected";
            if (slot > 0) { candidate += "." + slot.ToString(); }
            if (!FileExist(candidate))
            {
                if (free < 0) { free = slot; rejected = candidate; }
            }
            else if (HCWorldStore.RejectRawEqual(source, candidate))
            {
                Print("[HC World] staged_rejection path=" + FileName(source) + " reason=existing_raw_copy action=retire_source");
                return DeleteFile(source);
            }
        }
        if (free < 0)
        {
            // Bounded oldest-first rotation. A crash can lose an old archive,
            // but leaves the current source available to retry on the next boot.
            if (!DeleteFile(source + ".rejected")) { return false; }
            for (int rotate = 1; rotate < 8; rotate++)
            {
                string oldPath = source + ".rejected." + rotate.ToString();
                string newPath = source + ".rejected";
                int previous = rotate - 1;
                if (rotate > 1) { newPath += "." + previous.ToString(); }
                if (!CopyFile(oldPath, newPath)) { return RotationFailed(source); }
                if (!HCWorldStore.RejectRawEqual(oldPath, newPath)) { return RotationFailed(source); }
                if (!DeleteFile(oldPath)) { return false; }
            }
            rejected = source + ".rejected.7";
        }
        if (!CopyFile(source, rejected)) { return false; }
        bool equal = EqualText(source, rejected, limit);
        if (!equal) { equal = HCWorldStore.RejectRawEqual(source, rejected); }
        string reason = "verified_copy";
        if (!equal) { reason = "copy_unverified_non_authoritative"; }
        Print("[HC World] staged_rejection path=" + FileName(source) + " reason=" + reason + " action=retire_source");
        return DeleteFile(source);
    }

    protected static bool EqualText(string source, string rejected, int limit)
    {
        FileHandle left = OpenFile(source, FileMode.READ);
        if (!left) { return false; }
        FileHandle right = OpenFile(rejected, FileMode.READ);
        if (!right) { CloseFile(left); return false; }
        int total;
        bool equal;
        while (total <= limit)
        {
            string a = "";
            string b = "";
            int count = ReadFile(left, a, 4096);
            int copied = ReadFile(right, b, 4096);
            if (count < 0 || count > 4096 || count != copied || total + count > limit) { break; }
            if (count != a.Length() || copied != b.Length() || a != b) { break; }
            if (count == 0) { equal = true; break; }
            total += count;
        }
        CloseFile(left);
        CloseFile(right);
        return equal;
    }

    static bool Recover(string path, int limit, string intent, string primary, bool forward, bool keepBackup = true)
    {
        if (intent == "")
        {
            if (primary == "" || !Reject(path + ".tmp", limit)) { return false; }
            Print("[HC World] staged_recovery action=discard_unverifiable_or_stale path=" + path);
            return true;
        }
        if (!forward) { return false; }
        if (primary != intent)
        {
            if (primary != "" && keepBackup)
            {
                if (FileExist(path + ".bak") && !DeleteFile(path + ".bak")) { return false; }
                if (!CopyFile(path, path + ".bak")) { return false; }
                string backup;
                bool readBackup = HCGroupIO.HCReadRaw(path + ".bak", limit, backup);
                if (!readBackup || backup != primary) { return false; }
            }
            if (FileExist(path))
            {
                if (primary == "")
                {
                    if (!Reject(path, limit)) { return false; }
                }
                else if (!DeleteFile(path)) { return false; }
            }
            if (!CopyFile(path + ".tmp", path)) { return false; }
        }
        string check;
        bool readPrimary = HCGroupIO.HCReadRaw(path, limit, check);
        if (!readPrimary || check != intent) { return false; }
        bool retireBackup = !keepBackup && FileExist(path + ".bak");
        if (retireBackup && !DeleteFile(path + ".bak")) { return false; }
        if (!DeleteFile(path + ".tmp")) { return false; }
        Print("[HC World] staged_recovery action=promote_verified path=" + path);
        return true;
    }
}

// Independent exclusive lease ceiling. Never roll this file back to .bak.
// Partial intent + valid primary is safe: IDs are exposed only after Finish.
// First-seed tears reseed; invalid ceilings block only when custody is older.
class HCWorldLeaseCeiling
{
    static const string PATH = "$profile:HollowCountry/ai-custody.lease-ceiling";
    protected int m_Ceiling;
    protected int m_Pending;
    protected bool m_NeedsReseed;
    protected bool m_BackupLowerBound;
    protected bool m_CleanupReady;
    protected static bool s_IntentReadFailurePrinted;
    protected string m_Text;
    protected ref HCStagedSaveImage m_Image = new HCStagedSaveImage;

    protected int Decode(string text)
    {
        if (text.Length() < 3 || text.Length() > 12) { return 0; }
        string number = text.Substring(1, text.Length() - 2);
        int value = number.ToInt();
        if (value < 1 || text != "|" + value.ToString() + "|") { return 0; }
        return value;
    }

    bool Load(bool allowReseed)
    {
        m_NeedsReseed = false;
        m_BackupLowerBound = false;
        string primary;
        bool primaryRead = HCGroupIO.HCReadRaw(PATH, 12, primary);
        if (!primaryRead) { primary = ""; }
        int floor = Decode(primary);
        if (FileExist(PATH + ".tmp"))
        {
            string intent;
            bool intentRead = HCWorldStore.ReadCeilingChecked(PATH + ".tmp", intent);
            if (!intentRead)
            {
                if (!s_IntentReadFailurePrinted)
                {
                    s_IntentReadFailurePrinted = true;
                    Print("[HC World] custody_lease_ceiling_intent_unreadable action=retain_retry");
                }
                return false;
            }
            int next = Decode(intent);
            if (next == 0 || next < floor) { intent = ""; }
            if (floor == 0) { primary = ""; }
            bool firstSeed = intent == "" && floor == 0;
            if (FileExist(PATH)) { firstSeed = false; }
            if (FileExist(PATH + ".bak")) { firstSeed = false; }
            if (firstSeed)
            {
                // read_tmp must verify before the writer can remove a primary.
                // No primary/backup + torn intent is therefore a first-seed tear.
                if (!HCWorldIntentRecovery.Reject(PATH + ".tmp", 12)) { return false; }
                bool rejectedPrimary = FileExist(PATH + ".rejected");
                for (int rejectedSlot = 1; rejectedSlot < 8; rejectedSlot++)
                {
                    if (FileExist(PATH + ".rejected." + rejectedSlot.ToString())) { rejectedPrimary = true; }
                }
                string tearReason = "custody_lease_ceiling_first_seed_torn";
                if (rejectedPrimary) { tearReason = "custody_lease_ceiling_torn_after_primary_rejection"; }
                Print("[HC World] " + tearReason + " action=reseed");
                HCModuleReadiness.HCUse("Materializer", tearReason);
            }
            else
            {
                if (intent == "" && floor == 0)
                {
                    if (!allowReseed)
                    {
                        Print("[HC World] custody_lease_ceiling_invalid reason=older_custody_unverified_ceiling");
                        return false;
                    }
                    if (!HCWorldIntentRecovery.Reject(PATH + ".tmp", 12)) { return false; }
                }
                else
                {
                    if (!HCWorldIntentRecovery.Recover(PATH, 12, intent, primary, true, false)) { return false; }
                    primary = "";
                    primaryRead = HCGroupIO.HCReadRaw(PATH, 12, primary);
                    if (!primaryRead) { return false; }
                    floor = Decode(primary);
                }
            }
        }
        bool ceilingHistory = FileExist(PATH);
        if (FileExist(PATH + ".bak")) { ceilingHistory = true; }
        if (floor == 0 && ceilingHistory)
        {
            if (!allowReseed)
            {
                Print("[HC World] custody_lease_ceiling_invalid reason=older_custody_unverified_ceiling");
                return false;
            }
            m_NeedsReseed = true;
            string backup;
            bool backupRead = HCGroupIO.HCReadRaw(PATH + ".bak", 12, backup);
            if (backupRead) { floor = Decode(backup); }
            if (floor > 0)
            {
                m_BackupLowerBound = true;
                Print("[HC World] custody_lease_ceiling_backup_lower_bound next_lease=" + floor.ToString());
            }
            if (FileExist(PATH) && !HCWorldIntentRecovery.Reject(PATH, 12)) { return false; }
            // Keep a verified backup lower bound until a new ceiling commits.
            // Otherwise a crash between rejection and reseed could lose it.
            if (floor == 0 && FileExist(PATH + ".bak"))
            {
                if (!HCWorldIntentRecovery.Reject(PATH + ".bak", 12)) { return false; }
            }
            primary = "";
            Print("[HC World] custody_lease_ceiling_torn action=reseed_from_verified_custody");
            HCModuleReadiness.HCUse("Materializer", "custody_lease_ceiling_torn");
        }
        if (floor > 0 && !m_NeedsReseed)
        {
            if (FileExist(PATH + ".bak") && !DeleteFile(PATH + ".bak")) { return false; }
        }
        m_Ceiling = floor;
        m_Text = primary;
        return true;
    }

    int HCAbort() { return m_Image.HCAbort(); }

    int Ceiling() { return m_Ceiling; }
    bool NeedsReseed() { return m_NeedsReseed || m_Ceiling == 0; }

    // Called only by the custody save job, before its image can commit or a
    // provider can claim. One shared writer stage per call; no tick-time drain.
    int AdvanceStep(int nextLease)
    {
        if (m_CleanupReady)
        {
            // The new primary has verified. One final bounded scheduler stage
            // retires the lower-bound backup, never before the ceiling commits.
            if (FileExist(PATH + ".bak") && !DeleteFile(PATH + ".bak")) { return HCSaveJob.STEP_FAILED; }
            m_CleanupReady = false;
            m_BackupLowerBound = false;
            return HCSaveJob.STEP_DONE;
        }
        if (!m_Image.Active())
        {
            if (nextLease <= m_Ceiling && !m_NeedsReseed) { return HCSaveJob.STEP_DONE; }
            m_Pending = nextLease;
            if (m_Pending <= 2147482623) { m_Pending += 1024; }
            else { m_Pending = 2147483647; }
            if (!m_Image.Begin(PATH, "|" + m_Pending.ToString() + "|", 12, false, true, m_Text)) { return HCSaveJob.STEP_FAILED; }
            return HCSaveJob.STEP_MORE;
        }
        int result = m_Image.HCStepImage();
        if (result == HCSaveJob.STEP_DONE)
        {
            m_Ceiling = m_Pending;
            m_Text = "|" + m_Pending.ToString() + "|";
            m_Image = new HCStagedSaveImage;
            m_NeedsReseed = false;
            if (m_BackupLowerBound)
            {
                m_CleanupReady = true;
                return HCSaveJob.STEP_MORE;
            }
        }
        return result;
    }
}
