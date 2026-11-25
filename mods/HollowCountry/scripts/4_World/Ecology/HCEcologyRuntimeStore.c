// Fixed owned paths; bounded parsing and readback, no globbing or claimed fsync.
// Startup restores a verified predecessor, or a whole pending image when no
// backup exists. Invalid images and failed quarantine remain refused.
class HCEcologyRuntimeIO
{
	static string Read(string path, int limit)
	{
		FileHandle handle = OpenFile(path, FileMode.READ);
		if (!handle) { return ""; }
		string text;
		int count = ReadFile(handle, text, limit + 1);
		CloseFile(handle);
		if (count < 1 || count > limit || text.Length() > limit) { return ""; }
		return text;
	}

	static bool Write(string path, string text, int limit)
	{
		if (text.Length() < 1 || text.Length() > limit) { return false; }
		FileHandle handle = OpenFile(path, FileMode.WRITE);
		if (!handle) { return false; }
		FPrint(handle, text);
		CloseFile(handle);
		return Read(path, limit) == text;
	}


	static bool WriteNew(string path, string text, int limit)
	{
		if (FileExist(path)) { return false; }
		return Write(path, text, limit);
	}

	static string Encode(HCEcologyCheckpoint state)
	{
		string text;
		string error;
		if (!JsonFileLoader<HCEcologyCheckpoint>.MakeData(state, text, error)) { return ""; }
		if (text.Length() > 2048) { return ""; }
		return text;
	}

	static HCEcologyCheckpoint Decode(string text)
	{
		HCEcologyCheckpoint state;
		string error;
		if (text.Length() < 1 || text.Length() > 2048) { return null; }
		if (!JsonFileLoader<HCEcologyCheckpoint>.LoadData(text, state, error)) { return null; }
		// Samples/PathQueries default to -1; native load zero-fills absent ints (#177).
		if (!HCJsonFields.Has(text, "Samples") || !HCJsonFields.Has(text, "PathQueries")) { return null; }
		return state;
	}

	static HCEcologyRuntimeSettings Settings()
	{
		if (!FileExist("$profile:HollowCountry") && !MakeDirectory("$profile:HollowCountry")) { return null; }
		string root = "$profile:HollowCountry/Ecology";
		if (!FileExist(root) && !MakeDirectory(root)) { return null; }
		string path = root + "/settings.json";
		HCEcologyRuntimeSettings settings = new HCEcologyRuntimeSettings;
		string error;
		string text;
		if (FileExist(path))
		{
			text = Read(path, 2048);
			if (text.Length() < 1) { return null; }
			if (!JsonFileLoader<HCEcologyRuntimeSettings>.LoadData(text, settings, error)) { return null; }
		}
		else
		{
			if (!JsonFileLoader<HCEcologyRuntimeSettings>.MakeData(settings, text, error)) { return null; }
			if (!WriteNew(path, text, 2048)) { return null; }
		}
		if (!HCEcologyRuntimeRules.SettingsValid(settings)) { return null; }
		return settings;
	}
}

class HCEcologyRuntimeStore
{
	protected string m_Root = "$profile:HollowCountry/Ecology";
	protected string m_World;
	protected string m_Session;
	protected int m_Revision;
	protected bool m_Fault;
	protected int m_SavePhase;
	protected int m_SaveRevision;
	protected string m_SaveText;
    protected string m_CommittedText;
    protected ref HCStagedSaveImage m_SaveImage;

	// HC-29: six scalar fields, encoded at <=2048 bytes. No live entity
	// snapshot, rename/fsync claim or unsupported asynchronous engine IO.
	// EnSystem.c:397/417/425/443/462/528; JsonFileLoader.c:85 MakeData.
	bool HCBeginSave(HCEcologyCheckpoint state)
	{
		if (m_Fault || m_SavePhase != 0 || !HCEcologyRuntimeRules.CheckpointValid(state, m_World)) { return false; }
		if (state.SessionId != m_Session || state.Revision != m_Revision + 1) { return false; }
		m_SaveText = HCEcologyRuntimeIO.Encode(state);
		if (m_SaveText.Length() < 1 || m_SaveText.Length() > 2048) { return false; }
		m_SaveRevision = state.Revision;
		m_SavePhase = 1;
		return true;
	}

	int HCPhase() { return m_SavePhase; }

    // The scheduler owns each open, chunk, close and promotion separately.
    // Keep the legacy pending name and JSON schema, and a verified old backup.
    int HCStepSave()
    {
        if (m_SavePhase != 1 || m_Fault) { return HCSaveJob.STEP_FAILED; }
        if (!m_SaveImage)
        {
            m_SaveImage = new HCStagedSaveImage;
            string imagePath = m_Root + "/state-" + m_World + ".json";
            string pendingPath = m_Root + "/pending-" + m_World + ".json";
            if (!m_SaveImage.Begin(imagePath, m_SaveText, 2048, true, true, m_CommittedText, HCStagedSaveImage.HC_IMAGE_REPLACE, pendingPath))
            {
                m_Fault = true;
                m_SavePhase = -1;
                m_SaveImage = null;
                return HCSaveJob.STEP_FAILED;
            }
            return HCSaveJob.STEP_MORE;
        }
        int result = m_SaveImage.HCStepBoundedImage();
        if (result == HCSaveJob.STEP_FAILED)
        {
            m_Fault = true;
            m_SavePhase = -1;
            m_SaveImage = null;
            Print("[HC Ecology] checkpoint IO refused; preserve pending/state/backup runtime=PENDING");
        }
        if (result == HCSaveJob.STEP_DONE)
        {
            m_Revision = m_SaveRevision;
            m_CommittedText = m_SaveText;
            m_SaveText = "";
            m_SavePhase = 0;
            m_SaveImage = null;
        }
        return result;
    }

    // Boot only. A whole pending image was verified before primary promotion.
    // If promotion started, the verified backup must be its exact predecessor.
    // No-backup table: whole intent + absent/torn primary -> verified promotion;
    // torn intent + absent primary -> archive once/empty (absent_primary); both torn -> operator;
    // whole primary wins through the existing primary/Revision checks below.
    // Existing backups retain the verified-predecessor rules unchanged.
    protected bool HCRecoverPrior(string imagePath, string pendingPath, string world)
    {
        // Promotion, retirement and backup restore rewrite the primary outside the image writer.
        HCStagedSaveImage.HCForget(imagePath);
        string pendingText = HCEcologyRuntimeIO.Read(pendingPath, 2048);
        HCEcologyCheckpoint intent = HCEcologyRuntimeIO.Decode(pendingText);
        string primaryText = HCEcologyRuntimeIO.Read(imagePath, 2048);
        HCEcologyCheckpoint primary = HCEcologyRuntimeIO.Decode(primaryText);
        bool primaryValid = HCEcologyRuntimeRules.CheckpointValid(primary, world);
        if (!primaryValid && !FileExist(imagePath + ".bak"))
        {
            if (HCEcologyRuntimeRules.CheckpointValid(intent, world))
            {
                bool promoted = HCV2ThreatStore<HCEcologyCheckpoint>.HCPromoteWholePending(imagePath, pendingPath, 2048);
                if (promoted)
                {
                    HCEcologyCheckpoint readback = HCEcologyRuntimeIO.Decode(HCEcologyRuntimeIO.Read(imagePath, 2048));
                    promoted = HCEcologyRuntimeRules.CheckpointValid(readback, world);
                    if (promoted) { promoted = readback.Revision == intent.Revision; }
                }
                if (!promoted)
                {
                    Print("[HC Ecology] action=left_for_operator reason=pending_promotion_failed runtime=PENDING");
                    return false;
                }
                if (!DeleteFile(pendingPath) || FileExist(pendingPath))
                {
                    Print("[HC Ecology] action=left_for_operator reason=pending_clear_failed runtime=PENDING");
                    return false;
                }
                Print("[HC Ecology] action=promoted_whole_pending reason=no_predecessor runtime=PENDING");
                return true;
            }
            if (FileExist(imagePath))
            {
                Print("[HC Ecology] action=left_for_operator reason=no_whole_image runtime=PENDING");
                return false;
            }
            bool retired = HCV2ThreatStore<HCEcologyCheckpoint>.HCRetireFirstPending(imagePath, pendingPath, 2048);
            if (retired) { Print("[HC Ecology] action=archived_first_pending reason=absent_primary runtime=PENDING"); }
            else { Print("[HC Ecology] action=left_for_operator reason=first_pending_retirement_failed runtime=PENDING"); }
            return retired;
        }
        if (!HCEcologyRuntimeRules.CheckpointValid(intent, world))
        {
            if (primaryValid) { Print("[HC Ecology] action=retained_verified_primary reason=pending_unverified runtime=PENDING"); }
            return primaryValid;
        }
        // Legacy writer had no backup: a fully promoted pending revision is
        // already authoritative even if it crashed before deleting the intent.
        if (primaryValid && (primaryText == pendingText || primary.Revision == intent.Revision))
        {
            Print("[HC Ecology] recovery=retained_primary reason=pending_revision_committed runtime=PENDING");
            return true;
        }
        if (primaryValid && primary.Revision == intent.Revision - 1)
        {
            Print("[HC Ecology] recovery=retained_primary reason=verified_predecessor runtime=PENDING");
            return true;
        }
        if (primaryValid)
        {
            Print("[HC Ecology] action=retained_verified_primary reason=unexpected_revision runtime=PENDING");
            return true; // Open quarantines pending; never roll back a valid image.
        }
        string backupText = HCEcologyRuntimeIO.Read(imagePath + ".bak", 2048);
        HCEcologyCheckpoint backup = HCEcologyRuntimeIO.Decode(backupText);
        if (!HCEcologyRuntimeRules.CheckpointValid(backup, world) || backup.Revision != intent.Revision - 1) { return false; }
        if (FileExist(imagePath))
        {
            if (!HCV2ThreatStore<HCEcologyCheckpoint>.HCArchiveFirstPending(imagePath, 2048)) { return false; }
            if (!DeleteFile(imagePath)) { return false; }
        }
        if (!CopyFile(imagePath + ".bak", imagePath)) { return false; }
        bool restored = HCEcologyRuntimeIO.Read(imagePath, 2048) == backupText;
        if (restored) { Print("[HC Ecology] recovery=restored_backup reason=verified_predecessor runtime=PENDING"); }
        return restored;
    }

	HCEcologyCheckpoint Open(string worldName, string session)
	{
		if (m_Fault || !HCEcologyRuntimeRules.Token(worldName) || !HCEcologyRuntimeRules.Token(session)) { return null; }
		if (!FileExist("$profile:HollowCountry") && !MakeDirectory("$profile:HollowCountry")) { return null; }
		if (!FileExist(m_Root) && !MakeDirectory(m_Root)) { return null; }
		// Keyed by world: another map's checkpoint never blocks or is touched.
		string imagePath = m_Root + "/state-" + worldName + ".json";
		string pendingName = "pending-" + worldName + ".json";
		string pendingPath = m_Root + "/" + pendingName;
		// Open recovers and quarantines around the primary outside the image writer.
		HCStagedSaveImage.HCForget(imagePath);
		bool pending = FileExist(pendingPath);
		if (pending)
		{
            if (!HCRecoverPrior(imagePath, pendingPath, worldName))
            {
                Print("[HC Ecology] state=refused reason=no_verified_predecessor_or_recovery_io runtime=PENDING");
                m_Fault = true;
                return null;
            }
            pending = FileExist(pendingPath);
        }
        if (pending)
        {
			// HC-28 logical rename: verified archive before removing the active name.
			// No native rename exists. EnSystem.c:528/531 DeleteFile/CopyFile;
			// HCGroupClock.Utc uses EnSystem.c:76/100 UTC time/date.
			int now = HCGroupClock.Utc();
			string suffix = ".quarantined-" + now.ToString();
			string pendingText = HCEcologyRuntimeIO.Read(pendingPath, 2048);
			string pendingReason = "leftover_pending";
			if (pendingText.Trim().Length() == 0) { pendingReason = "leftover_pending_empty"; }
			bool archived = false;
			if (now > 0) { archived = HCPersistenceDisposition.HCArchive(pendingPath, suffix, 2048, true); }
			if (!archived || !DeleteFile(pendingPath) || FileExist(pendingPath))
			{
				m_Fault = true;
				Print("[HC Ecology] state=refused reason=pending_quarantine_failed runtime=PENDING");
				return null;
			}
			pending = false;
			Print("[HC Ecology] recovery=quarantined reason=" + pendingReason + " path=" + pendingName + suffix + " runtime=PENDING");
			HCPersistenceDisposition.HCPruneArchives(pendingPath, ".quarantined-");
		}
		bool image = FileExist(imagePath);
		HCEcologyCheckpoint prior;
		bool valid = false;
		if (image)
		{
			m_CommittedText = HCEcologyRuntimeIO.Read(imagePath, 2048);
            prior = HCEcologyRuntimeIO.Decode(m_CommittedText);
			valid = HCEcologyRuntimeRules.CheckpointValid(prior, worldName);
		}
		if (!HCEcologyRuntimeRules.CheckpointAdmission(pending, image, valid))
		{
			m_Fault = true;
			Print("[HC Ecology] checkpoint rejected; preserve pending/state files for recovery");
			return null;
		}
		m_World = worldName;
		m_Session = session;
		HCEcologyCheckpoint fresh = new HCEcologyCheckpoint;
		fresh.Version = 1;
		fresh.WorldName = worldName;
		fresh.SessionId = session;
		fresh.Samples = 0;
		fresh.PathQueries = 0;
		if (prior)
		{
			if (prior.SessionId == session || prior.Revision >= 1000000000) { return null; }
			fresh.Samples = prior.Samples;
			fresh.PathQueries = prior.PathQueries;
			m_Revision = prior.Revision;
		}
		fresh.Revision = m_Revision + 1;
		if (!Save(fresh)) { return null; }
		return fresh;
	}

	bool Save(HCEcologyCheckpoint state)
	{
        // Startup/shutdown only; routine saves use the scheduler continuation.
        if (!HCBeginSave(state)) { return false; }
        int result = HCSaveJob.STEP_MORE;
        int steps = 0;
        while (result == HCSaveJob.STEP_MORE && steps < HCStagedSaveImage.HC_MAX_STAGES + 2)
        {
            result = HCStepSave();
            steps++;
        }
        if (result == HCSaveJob.STEP_MORE)
        {
            // Native scripts-1.30.164289: 1_Core/proto/EnDebug.c:96 Print;
            // 1_Core/proto/EnConvert.c:30 int.ToString.
            Print("[HC Persistence] owner=HCEcologyRuntimeStore guard=save_stage_guard steps=" + steps.ToString());
            m_Fault = true;
            m_SavePhase = -1;
        }
        return result == HCSaveJob.STEP_DONE;
    }
}
