// No startup/action/RPC hooks. Caller retains action ownership, elapsed time,
// target/range/LOS/session validation. Preference enabled; prerequisites required.
class HCSearchEntry
{
    string SiteId;
    string SupplyId;
    string ItemClass;
}

class HCSearchManifest
{
    int Version;
    int Epoch;
    string WorldName;
    string Build;
    string SourceId;
    // External SHA-256 of REAL source provenance manifest. Syntax/binding only
    // in script; neither this string nor GetEconomyProfile proves CE origin.
    string SourcePin;
    ref array<ref HCSearchEntry> Entries = new array<ref HCSearchEntry>;
}

class HCSearchRecord
{
    int Version;
    int Epoch;
    int Phase;
    string WorldName;
    string Build;
    string SourceId;
    string SourcePin;
    string SiteId;
    string SupplyId;
    string ItemClass;
    string ActorId;
}

// 0 available; 1 pending; 2 spent/empty; 3 quarantined; 4 definite no-transfer.
// All nonzero states terminal on recovery. Negative results: -1 unknown site,
// -2 disabled/unready, -3 busy, -4 denied/no room/source stale.
class HCSearchEconomy
{
    protected static HCSearchEconomy s_Active;
    protected bool m_Enabled = true;
    protected bool m_Ready;
    protected bool m_Busy;
    protected ref HCSearchManifest m_Manifest;
    protected ref HCSearchEconomyStore m_Store;
    protected ref HCSearchSupplyRegistry m_Source;
    protected ref array<int> m_Phases = new array<int>;

    void SetEnabled(bool enabled) { m_Enabled = enabled; }

    bool Fail(string reason)
    {
        m_Ready = false;
        Print("[HC Search Economy] inactive: " + reason);
        return false;
    }

    bool Open(HCSearchManifest expected, HCSearchSupplyRegistry source, bool initializeNewEpoch)
    {
        if (s_Active || m_Store || !GetGame().IsServer()) return Fail("duplicate service or not server");
        if (!HCSearchRules.ManifestValid(expected)) return Fail("invalid bounded allocation manifest");
        if (!source || !source.ReadyFor(expected)) return Fail("missing exact pinned native source registry");
        m_Store = new HCSearchEconomyStore;
        if (!m_Store.Open(expected, initializeNewEpoch)) return Fail("manifest/journal unavailable; preserve state");
        m_Manifest = m_Store.Snapshot();
        m_Source = source;
        source.Seal();
        int index;
        while (index < m_Manifest.Entries.Count())
        {
            m_Phases.Insert(m_Store.Recover(index));
            index++;
        }
        if (!m_Store.Healthy()) return Fail("journal recovery failed; no output replay");
        s_Active = this;
        m_Ready = true;
        Print("[HC Search Economy] finite registry bound; stock CE provenance/qualification remains a separate gate");
        return true;
    }

    void Stop()
    {
        m_Ready = false;
        if (s_Active == this) s_Active = null;
    }

    int Index(string siteId)
    {
        int index;
        while (index < m_Manifest.Entries.Count())
        {
            if (m_Manifest.Entries[index].SiteId == siteId) return index;
            index++;
        }
        return -1;
    }

    bool Live(PlayerBase actor)
    {
        if (!actor || !actor.IsAlive() || actor.IsUnconscious()) return false;
        if (!actor.GetIdentity()) return false;
        return HCSearchRules.TextValid(actor.GetIdentity().GetId(), 128);
    }

    bool CanGrant(string siteId, PlayerBase actor)
    {
        if (!GetGame().IsServer() || !m_Enabled || !m_Ready || m_Busy) return false;
        if (!m_Store.Healthy() || !m_Source.ReadyFor(m_Manifest) || !Live(actor)) return false;
        int index = Index(siteId);
        if (index < 0 || m_Phases[index] != 0) return false;
        HCSearchEntry entry = m_Manifest.Entries[index];
        if (entry.SupplyId == "") return true;
        return m_Source.CanTransfer(entry, actor);
    }

    bool StillAuthorized(PlayerBase actor, string actorId)
    {
        if (!m_Ready || !m_Enabled || !m_Store.Healthy()) return false;
        if (!m_Source.ReadyFor(m_Manifest) || !Live(actor)) return false;
        return actor.GetIdentity().GetId() == actorId;
    }

    HCSearchRecord Record(int index, string actorId, int phase)
    {
        HCSearchEntry entry = m_Manifest.Entries[index];
        HCSearchRecord record = new HCSearchRecord;
        record.Version = 1;
        record.Epoch = m_Manifest.Epoch;
        record.WorldName = m_Manifest.WorldName;
        record.Build = m_Manifest.Build;
        record.SourceId = m_Manifest.SourceId;
        record.SourcePin = m_Manifest.SourcePin;
        record.SiteId = entry.SiteId;
        record.SupplyId = entry.SupplyId;
        record.ItemClass = entry.ItemClass;
        record.ActorId = actorId;
        record.Phase = phase;
        return record;
    }

    int Finish(int index, string actorId, int phase)
    {
        if (phase != 2 && phase != 4) phase = 3;
        m_Phases[index] = phase;
        if (!m_Store.Write(index, "result", Record(index, actorId, phase)))
        {
            m_Phases[index] = 3;
            Fail("result write/readback failed; never repeat transfer");
            phase = 3;
        }
        m_Busy = false;
        return phase;
    }

    int Grant(string siteId, PlayerBase actor)
    {
        if (!GetGame().IsServer() || !m_Enabled || !m_Ready) return -2;
        if (m_Busy) return -3;
        int index = Index(siteId);
        if (index < 0) return -1;
        if (m_Phases[index] != 0) return m_Phases[index];
        if (!CanGrant(siteId, actor)) return -4;
        string actorId = actor.GetIdentity().GetId();
        m_Busy = true;
        m_Phases[index] = 1;
        if (!m_Store.Write(index, "claim", Record(index, actorId, 1)))
        {
            m_Phases[index] = 3;
            Fail("claim write/readback failed; source retained");
            m_Busy = false;
            return 3;
        }
        if (!StillAuthorized(actor, actorId)) return Finish(index, actorId, 4);
        if (!m_Store.Write(index, "attempt", Record(index, actorId, 1)))
        {
            m_Phases[index] = 3;
            Fail("attempt write/readback failed; never issue output");
            m_Busy = false;
            return 3;
        }
        if (!StillAuthorized(actor, actorId)) return Finish(index, actorId, 4);
        HCSearchEntry entry = m_Manifest.Entries[index];
        if (entry.SupplyId == "") return Finish(index, actorId, 2);
        // Native port moves SAME entity: no creation/split/debit/refund/replay.
        int phase = m_Source.Transfer(entry, actor);
        return Finish(index, actorId, phase);
    }
}
