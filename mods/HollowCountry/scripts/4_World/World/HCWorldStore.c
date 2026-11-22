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
        return count >= 0 && count == text.Length();
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
        if (SaveInFlight()) { return false; }
        int result = HCSaveJob.STEP_MORE;
        int guard = 0;
        while (result == HCSaveJob.STEP_MORE && guard < HCStagedSaveImage.HC_MAX_STAGES + 3)
        {
            result = SaveStep(data);
            guard = guard + 1;
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
