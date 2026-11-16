// Bounded I/O. Readback is NOT fsync; see the hard search acceptance gate.
class HCInteriorJson<Class T>
{
    static bool Load(string path, out T data)
    {
        FileHandle handle = OpenFile(path, FileMode.READ);
        if (!handle) return false;
        string text;
        int count = ReadFile(handle, text, 32769);
        CloseFile(handle);
        if (count <= 0 || count >= 32768 || text.Length() >= 32768) return false;
        string error;
        return JsonFileLoader<T>.LoadData(text, data, error);
    }

    static bool WriteNew(string path, T data)
    {
        if (FileExist(path)) return false;
        string text;
        string error;
        if (!JsonFileLoader<T>.MakeData(data, text, error) || text.Length() >= 32768) return false;
        if (!JsonFileLoader<T>.SaveFile(path, data, error)) return false;
        T loaded;
        if (!Load(path, loaded)) return false;
        string check;
        if (!JsonFileLoader<T>.MakeData(loaded, check, error)) return false;
        return text == check;
    }
}

class HCInteriorStore
{
    protected string m_Root;
    protected bool m_Fault;

    bool Fail(string reason)
    {
        Print("[HC Interiors] persistence disabled: " + reason);
        m_Fault = true;
        return false;
    }

    int Quarantine(HCInteriorSite site, string reason)
    {
        Print("[HC Interiors] slot " + site.Slot.ToString() + " quarantined: " + reason);
        return 3;
    }

    // Immutable manifest: never fall back to an older allocation/depletion image.
    bool Open(HCInteriorConfig config, HCInteriorManifest expected)
    {
        m_Root = "$profile:HollowCountry/interiors_s1_e" + config.Epoch.ToString();
        bool existed = FileExist(m_Root);
        if (!existed)
        {
            if (!config.InitializeNewEpoch) return Fail("new epoch requires explicit initialization; no automatic refill");
            if (!MakeDirectory(m_Root)) return Fail("cannot create epoch directory");
            // A crash now leaves an incomplete root which cannot auto-initialize.
            if (!HCInteriorJson<HCInteriorManifest>.WriteNew(m_Root + "/manifest.json", expected)) return Fail("initial manifest write/readback failed; preserve incomplete root");
            if (!HCInteriorJson<HCInteriorManifest>.WriteNew(m_Root + "/manifest.backup.json", expected)) return Fail("initial manifest backup failed; preserve root");
        }
        HCInteriorManifest actual;
        if (!HCInteriorJson<HCInteriorManifest>.Load(m_Root + "/manifest.json", actual)) return Fail("missing/corrupt/oversized manifest; no backup rewind");
        string left;
        string right;
        string error;
        if (!JsonFileLoader<HCInteriorManifest>.MakeData(expected, left, error)) return Fail("expected manifest serialization failed");
        if (!JsonFileLoader<HCInteriorManifest>.MakeData(actual, right, error)) return Fail("loaded manifest serialization failed");
        if (left != right) Print("[HC Interiors] manifest changed: preserve state; explicit migration required");
        return left == right;
    }

    string ClaimPath(int slot)
    {
        return m_Root + "/claim_" + slot.ToString() + ".json";
    }

    int RecoverSite(HCInteriorSite site)
    {
        string path = ClaimPath(site.Slot);
        if (!FileExist(path))
        {
            // A completion without its reservation is a damaged ledger.
            if (FileExist(m_Root + "/result_" + site.Slot.ToString() + ".json")) return Quarantine(site, "completion exists without reservation");
            return HCInteriorRules.Recover(false, false, 0, 0);
        }
        HCInteriorClaim claim;
        bool parses = HCInteriorJson<HCInteriorClaim>.Load(path, claim);
        if (!parses || !claim || claim.SiteId != site.Id || claim.Item != site.Item) return Quarantine(site, "reservation corrupt or identity/allocation mismatch");
        if (claim.SchemaVersion != 1 || claim.Phase != 1) return Quarantine(site, "reservation schema/phase unsupported");
        HCInteriorClaim result;
        string resultPath = m_Root + "/result_" + site.Slot.ToString() + ".json";
        bool completed = HCInteriorJson<HCInteriorClaim>.Load(resultPath, result);
        if (completed && result && result.SiteId == site.Id && result.Item == site.Item && result.PlayerId == claim.PlayerId)
            return HCInteriorRules.Recover(true, true, result.SchemaVersion, result.Phase);
        // A reservation without an exact valid completion is never replayed.
        return Quarantine(site, "reservation has no exact valid completion; never reissue");
    }

    bool Reserve(HCInteriorSite site, string playerId)
    {
        if (m_Fault || !HCInteriorRules.Transition(site.Phase, 1)) return false;
        string path = ClaimPath(site.Slot);
        if (FileExist(path))
        {
            site.Phase = Quarantine(site, "reservation already exists; never retry output");
            return false;
        }
        site.Phase = 1; // In-memory exclusion BEFORE any potentially failing I/O.
        HCInteriorClaim claim = new HCInteriorClaim;
        claim.SchemaVersion = 1;
        claim.SiteId = site.Id;
        claim.Item = site.Item;
        claim.PlayerId = playerId;
        claim.Phase = 1;
        if (!HCInteriorJson<HCInteriorClaim>.WriteNew(path, claim))
        {
            site.Phase = 3;
            return Fail("reservation write/readback failed; all further claims disabled");
        }
        return true;
    }

    void Finish(HCInteriorSite site, string playerId, int phase)
    {
        if (!HCInteriorRules.Transition(site.Phase, phase))
        {
            site.Phase = 3;
            Fail("invalid completion state transition");
            return;
        }
        site.Phase = phase;
        HCInteriorClaim result = new HCInteriorClaim;
        result.SchemaVersion = 1;
        result.SiteId = site.Id;
        result.Item = site.Item;
        result.PlayerId = playerId;
        result.Phase = phase;
        if (!HCInteriorJson<HCInteriorClaim>.WriteNew(m_Root + "/result_" + site.Slot.ToString() + ".json", result)) Fail("completion write failed; reservation retained and all further claims disabled");
    }

    bool Healthy()
    {
        return !m_Fault;
    }
}
