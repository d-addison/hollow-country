// Fixed owned paths; bounded parsing and readback, no globbing, fallback, rename
// or claimed fsync. An interrupted overwrite leaves pending-<world>.json: next admission
// fails closed and preserves both files for operator recovery.
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

	HCEcologyCheckpoint Open(string worldName, string session)
	{
		if (m_Fault || !HCEcologyRuntimeRules.Token(worldName) || !HCEcologyRuntimeRules.Token(session)) { return null; }
		if (!FileExist("$profile:HollowCountry") && !MakeDirectory("$profile:HollowCountry")) { return null; }
		if (!FileExist(m_Root) && !MakeDirectory(m_Root)) { return null; }
		// Keyed by world: another map's checkpoint never blocks or is touched.
		string imagePath = m_Root + "/state-" + worldName + ".json";
		bool image = FileExist(imagePath);
		bool pending = FileExist(m_Root + "/pending-" + worldName + ".json");
		HCEcologyCheckpoint prior;
		bool valid = false;
		if (image)
		{
			prior = HCEcologyRuntimeIO.Decode(HCEcologyRuntimeIO.Read(imagePath, 2048));
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
		if (m_Fault || !HCEcologyRuntimeRules.CheckpointValid(state, m_World)) { return false; }
		if (state.SessionId != m_Session) { return false; }
		if (state.Revision != m_Revision + 1) { return false; }
		string text = HCEcologyRuntimeIO.Encode(state);
		if (text.Length() < 1 || text.Length() > 2048) { return false; }
		// Once an intent write is attempted, every failure poisons this store.
		// No live caller can overwrite a possibly interrupted transaction.
		string imagePath = m_Root + "/state-" + m_World + ".json";
		string pendingPath = m_Root + "/pending-" + m_World + ".json";
		m_Fault = true;
		if (!HCEcologyRuntimeIO.WriteNew(pendingPath, text, 2048)) { return false; }
		if (!HCEcologyRuntimeIO.Write(imagePath, text, 2048)) { return false; }
		string actual = HCEcologyRuntimeIO.Read(imagePath, 2048);
		if (actual != text) { return false; }
		if (!DeleteFile(pendingPath)) { return false; }
		m_Revision = state.Revision;
		m_Fault = false;
		return true;
	}
}
