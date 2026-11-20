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
    // Native EnScript.c:866/902 map Get/Set; journal snapshot loaded by Open.
    protected ref map<int, bool> m_Held = new map<int, bool>;
    protected string m_Root;
    protected bool m_Fault;
    protected string m_LastRefusal;
    protected ref HCInteriorSearchPool m_Pool;

    bool Fail(string reason)
    {
        Print("[HC Interiors] persistence disabled: " + reason);
        m_Fault = true;
        return false;
    }

    // A grant refusal that is not a new fault: logged once per reason change, never a player id.
    bool Refuse(string reason)
    {
        if (m_LastRefusal != reason)
        {
            m_LastRefusal = reason;
            Print("[HC Interiors] grant refused: " + reason);
        }
        return false;
    }

    string Refusal() { return m_LastRefusal; }

    int Quarantine(HCInteriorSite site, string reason)
    {
        Print("[HC Interiors] slot " + site.SlotId.ToString() + " quarantined: " + reason);
        return 3;
    }

    bool FaultSite(HCInteriorSite site, string reason)
    {
        if (site)
        {
            site.Phase = 3;
            if (m_Pool) m_Pool.Reconcile(site, 3);
        }
        return Fail(reason);
    }

    // Immutable manifest: never fall back to an older allocation/depletion image.
    bool Open(HCInteriorConfig config, HCInteriorManifest expected)
    {
        if (m_Fault || !config || !expected) return false;
        if (expected.Epoch != config.Epoch || expected.MapName != config.MapName || !HCBuildIdentity.SameBuild(expected.Build, config.Build) || expected.Seed != config.Seed) return Fail("manifest/config world/build/epoch/seed mismatch");
        m_Pool = new HCInteriorSearchPool;
        if (!m_Pool.Open(expected)) return Fail("invalid or over-budget allocation manifest");
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
        // Admitted build aliases are one identity. Normalise the in-memory images only for this
        // exact comparison; the stored manifest file is never rewritten.
        expected.Build = HCBuildIdentity.Normalize(expected.Build);
        actual.Build = HCBuildIdentity.Normalize(actual.Build);
        string left;
        string right;
        string error;
        if (!JsonFileLoader<HCInteriorManifest>.MakeData(expected, left, error)) return Fail("expected manifest serialization failed");
        if (!JsonFileLoader<HCInteriorManifest>.MakeData(actual, right, error)) return Fail("loaded manifest serialization failed");
        if (left != right) return Fail("manifest changed; layout/identity changes require a separate reviewed migration");
        if (!OpenJournal(config, expected, !existed)) return false;
        if (!ReconcileAll()) return false;
        return left == right;
    }

    // Sidecar upgrades the journal, never replaces the layout/loot image. The old
    // schema-1 paths and claims remain authoritative inputs. A torn sidecar stops
    // startup; neither backup replay nor an automatic repair can erase depletion.
    bool OpenJournal(HCInteriorConfig config, HCInteriorManifest manifest, bool fresh)
    {
        string path = m_Root + "/journal-v2.json";
        HCInteriorJournalIdentity expected = new HCInteriorJournalIdentity;
        expected.SchemaVersion = 2;
        expected.SourceSchema = 1;
        expected.Manifest = manifest;
        if (!FileExist(path))
        {
            if (!HCInteriorRules.MigrationAllowed(manifest.SchemaVersion, 2, fresh || config.MigrateLegacyJournal, true)) return Fail("legacy journal requires explicit MigrateLegacyJournal; no automatic upgrade");
            if (!HCInteriorJson<HCInteriorJournalIdentity>.WriteNew(path, expected)) return Fail("journal migration write/readback failed; preserve all source state");
        }
        HCInteriorJournalIdentity actual;
        if (!HCInteriorJson<HCInteriorJournalIdentity>.Load(path, actual) || !actual) return Fail("journal identity corrupt/oversized; no migration replay");
        if (!HCInteriorRules.JournalVersionAccepted(actual.SchemaVersion, actual.SourceSchema) || !actual.Manifest) return Fail("journal version unsupported; no downgrade");
        // Same alias rule for the embedded manifest; the journal file keeps its stored spelling.
        expected.Manifest.Build = HCBuildIdentity.Normalize(expected.Manifest.Build);
        actual.Manifest.Build = HCBuildIdentity.Normalize(actual.Manifest.Build);
        string left;
        string right;
        string error;
        if (!JsonFileLoader<HCInteriorJournalIdentity>.MakeData(expected, left, error) || !JsonFileLoader<HCInteriorJournalIdentity>.MakeData(actual, right, error)) return Fail("journal identity serialization failed");
        if (left != right) return Fail("journal allocation binding changed; preserve orphan allocations");
        return true;
    }

    string ClaimPath(int slot)
    {
        return m_Root + "/claim_" + slot.ToString() + ".json";
    }

    string AttemptPath(int slot)
    {
        return m_Root + "/attempt_" + slot.ToString() + ".json";
    }

    string ResultPath(int slot)
    {
        return m_Root + "/result_" + slot.ToString() + ".json";
    }

    bool MatchesClaim(HCInteriorClaim claim, HCInteriorSite site)
    {
        return claim && site && claim.SiteId == site.Id && claim.Item == site.Item && claim.PlayerId != "" && claim.PlayerId.Length() <= 256;
    }

    // Includes unavailable buildings, not just successfully spawned search props.
    // Fixed 12 slots, <=48 reads, each <32 KiB, once on startup. Orphan files are
    // preserved and disable the pool, rather than freeing an unknown allocation.
    bool ReconcileAll()
    {
        for (int slot = 0; slot < 12; slot++)
        {
            m_Held.Set(slot, FileExist(HoldPath(slot)));
            HCInteriorAllocation entry = m_Pool.FindSlot(slot);
            if (!entry)
            {
                if (FileExist(ClaimPath(slot)) || FileExist(AttemptPath(slot)) || FileExist(ResultPath(slot)) || FileExist(HoldPath(slot))) return Fail("orphan journal at unassigned slot " + slot.ToString());
                continue;
            }
            HCInteriorSite site = new HCInteriorSite;
            site.SlotId = slot;
            site.Id = entry.SiteId;
            site.Item = entry.Item;
            site.Phase = ReadRecoverySite(site);
        }
        return true;
    }

    HCInteriorSupplyCount Supply(string item)
    {
        if (!m_Pool || !HCInteriorCatalog.ItemAllowed(item)) return null;
        HCInteriorSupplyCount count = m_Pool.Count(item);
        count.Frozen = m_Fault;
        return count;
    }

    string HoldPath(int slot)
    {
        return m_Root + "/hold_" + slot.ToString() + ".json";
    }

    bool IsHeld(int slot)
    {
        return m_Held.Get(slot);
    }

    // Permanent per-epoch retirement. No reclaimed escrow or automatic prop
    // adoption; an operator can inspect the original state without a stale rewind.
    bool HoldSlot(int slot, string reason)
    {
        HCInteriorAllocation entry = m_Pool.FindSlot(slot);
        if (!entry) return Fail("hold has no registered allocation");
        HCInteriorSite site = new HCInteriorSite;
        site.SlotId = slot;
        site.Id = entry.SiteId;
        site.Item = entry.Item;
        site.Phase = 3;
        m_Pool.Reconcile(site, 3);
        Print("[HC Interiors] slot " + slot.ToString() + " permanently held this epoch: " + reason);
        if (IsHeld(slot)) return true;
        HCInteriorClaim hold = new HCInteriorClaim;
        hold.SchemaVersion = 2;
        hold.SiteId = site.Id;
        hold.Item = site.Item;
        hold.Phase = 3;
        hold.PlayerId = "SERVER_HOLD:" + reason;
        m_Held.Set(slot, true); // Exclude before the durability barrier, including failure.
        if (!HCInteriorJson<HCInteriorClaim>.WriteNew(HoldPath(slot), hold)) return Fail("orphan hold write/readback failed; preserve state");
        return true;
    }

    int RecoverSite(HCInteriorSite site)
    {
        // Open reconciles every allocation before placement. Pool tracks all later transitions.
        if (!site || !m_Pool || !m_Pool.Matches(site)) return 3;
        HCInteriorAllocation entry = m_Pool.FindSlot(site.SlotId);
        return entry.Phase;
    }

    protected int ReadRecoverySite(HCInteriorSite site)
    {
        if (!site)
        {
            Fail("null recovery site");
            return 3;
        }
        if (!m_Pool || !m_Pool.Matches(site)) return Quarantine(site, "site has no exact shared allocation");
        if (IsHeld(site.SlotId)) return m_Pool.Reconcile(site, Quarantine(site, "persistent orphan/placement hold; no automatic release"));
        bool claimExists = FileExist(ClaimPath(site.SlotId));
        bool attemptExists = FileExist(AttemptPath(site.SlotId));
        bool resultExists = FileExist(ResultPath(site.SlotId));
        HCInteriorClaim claim;
        HCInteriorClaim attempt;
        HCInteriorClaim result;
        bool validClaim;
        bool validAttempt;
        bool validResult;
        int schema;
        int phase;
        if (claimExists && HCInteriorJson<HCInteriorClaim>.Load(ClaimPath(site.SlotId), claim) && MatchesClaim(claim, site))
        {
            schema = claim.SchemaVersion;
            validClaim = (schema == 1 || schema == 2) && claim.Phase == 1;
            if (attemptExists && HCInteriorJson<HCInteriorClaim>.Load(AttemptPath(site.SlotId), attempt) && MatchesClaim(attempt, site))
                validAttempt = attempt.SchemaVersion == schema && attempt.Phase == 1 && attempt.PlayerId == claim.PlayerId;
            if (resultExists && HCInteriorJson<HCInteriorClaim>.Load(ResultPath(site.SlotId), result) && MatchesClaim(result, site))
            {
                phase = result.Phase;
                validResult = result.SchemaVersion == schema && result.PlayerId == claim.PlayerId && (phase == 2 || phase == 3);
            }
        }
        int recovered = HCInteriorRules.RecoverJournal(claimExists, validClaim, attemptExists, validAttempt, resultExists, validResult, schema, phase);
        if (recovered == 3) Quarantine(site, "orphan/torn/interrupted journal; allocation retained, no output replay");
        return m_Pool.Reconcile(site, recovered);
    }

    bool Reserve(HCInteriorSite site, string playerId)
    {
        if (m_Fault || !site || !m_Pool || !HCInteriorRules.Transition(site.Phase, 1) || playerId == "" || playerId.Length() > 256) return false;
        string path = ClaimPath(site.SlotId);
        if (FileExist(path) || FileExist(ResultPath(site.SlotId)) || FileExist(AttemptPath(site.SlotId)) || IsHeld(site.SlotId))
        {
            site.Phase = Quarantine(site, "reservation already exists; never retry output");
            m_Pool.Reconcile(site, 3);
            return false;
        }
        if (!m_Pool.TryReserve(site)) return false;
        site.Phase = 1; // In-memory exclusion BEFORE any potentially failing I/O.
        HCInteriorClaim claim = new HCInteriorClaim;
        claim.SchemaVersion = 2;
        claim.SiteId = site.Id;
        claim.Item = site.Item;
        claim.PlayerId = playerId;
        claim.Phase = 1;
        if (!HCInteriorJson<HCInteriorClaim>.WriteNew(path, claim))
        {
            site.Phase = 3;
            m_Pool.Reconcile(site, 3);
            return Fail("reservation write/readback failed; all further claims disabled");
        }
        return true;
    }

    // Separate at-most-once attempt marker. File readback does not prove durable
    // commit; no attempt (including a null native return) is ever retried.
    bool BeginGrant(HCInteriorSite site, string playerId)
    {
        if (m_Fault) return Refuse("store faulted; no grant");
        if (!site || !m_Pool || !m_Pool.Reserved(site)) return Refuse("no reserved site for this grant");
        HCInteriorClaim claim;
        if (!HCInteriorJson<HCInteriorClaim>.Load(ClaimPath(site.SlotId), claim) || !MatchesClaim(claim, site) || claim.SchemaVersion != 2 || claim.Phase != 1 || claim.PlayerId != playerId) return FaultSite(site, "grant has no exact reservation");
        if (FileExist(AttemptPath(site.SlotId)) || FileExist(ResultPath(site.SlotId))) return FaultSite(site, "grant already attempted or completed; never retry");
        if (!HCInteriorJson<HCInteriorClaim>.WriteNew(AttemptPath(site.SlotId), claim))
        {
            site.Phase = 3;
            m_Pool.Reconcile(site, 3);
            return Fail("grant attempt write/readback failed; never issue output");
        }
        // A success ends the refusal run, so the next refusal reason is logged again.
        m_LastRefusal = "";
        return true;
    }

    bool Finish(HCInteriorSite site, string playerId, int phase, EntityAI output = null)
    {
        if (!site || !m_Pool || !m_Pool.Matches(site)) return Fail("completion has no exact shared allocation");
        if (m_Fault || !m_Pool.Reserved(site) || !HCInteriorRules.Transition(site.Phase, phase))
        {
            site.Phase = 3;
            m_Pool.Reconcile(site, 3);
            return Fail("invalid completion state transition");
        }
        HCInteriorClaim claim;
        HCInteriorClaim attempt;
        if (!HCInteriorJson<HCInteriorClaim>.Load(ClaimPath(site.SlotId), claim) || !HCInteriorJson<HCInteriorClaim>.Load(AttemptPath(site.SlotId), attempt)) return FaultSite(site, "completion missing reservation/attempt");
        if (!MatchesClaim(claim, site) || !MatchesClaim(attempt, site) || claim.PlayerId != playerId || attempt.PlayerId != playerId || claim.SchemaVersion != 2 || attempt.SchemaVersion != 2 || claim.Phase != 1 || attempt.Phase != 1) return FaultSite(site, "completion identity/actor/schema mismatch");
        if (phase == 2 && site.Item != "" && (!output || output.GetType() != site.Item)) return FaultSite(site, "successful nonempty completion has no matching output");
        site.Phase = phase;
        m_Pool.Reconcile(site, phase);
        HCInteriorClaim result = new HCInteriorClaim;
        result.SchemaVersion = 2;
        result.SiteId = site.Id;
        result.Item = site.Item;
        result.PlayerId = playerId;
        result.Phase = phase;
        if (output)
        {
            int a;
            int b;
            int c;
            int d;
            output.GetPersistentID(a, b, c, d);
            result.OutputA = a;
            result.OutputB = b;
            result.OutputC = c;
            result.OutputD = d;
        }
        if (!HCInteriorJson<HCInteriorClaim>.WriteNew(ResultPath(site.SlotId), result))
        {
            site.Phase = 3;
            m_Pool.Reconcile(site, 3);
            return Fail("completion write failed; reservation retained and all further claims disabled");
        }
        return true;
    }

    bool Healthy()
    {
        return !m_Fault;
    }
}
