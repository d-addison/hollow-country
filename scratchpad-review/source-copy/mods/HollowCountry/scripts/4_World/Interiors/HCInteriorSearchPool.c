// One finite precommitted supplementary pool, shared by every registered site.
// CE is not debited here: production remains gated on an observed CE bridge.
class HCInteriorJournalIdentity
{
    int SchemaVersion;
    int SourceSchema;
    ref HCInteriorManifest Manifest;
}

class HCInteriorAllocation
{
    int SlotId;
    string SiteId;
    string Item;
    int Phase;
}

class HCInteriorSupplyCount
{
    bool Frozen;
    int Allocated;
    int Available;
    int Reserved;
    int Spent;
    int Quarantined;
}

class HCInteriorSearchPool
{
    protected ref array<ref HCInteriorAllocation> m_Entries = new array<ref HCInteriorAllocation>;
    protected bool m_Opened;

    // O(12^2) at startup only. No caller can add an allocation after this step.
    bool Open(HCInteriorManifest manifest)
    {
        if (m_Opened) return false;
        m_Opened = true;
        m_Entries.Clear();
        if (!manifest || manifest.SchemaVersion != 1 || !manifest.Assignments) return false;
        int rags;
        int batteries;
        if (manifest.Assignments.Count() < 1 || manifest.Assignments.Count() > 12) return false;
        foreach (HCInteriorAssignment assignment : manifest.Assignments)
        {
            if (!assignment || assignment.SlotId < 0 || assignment.SlotId >= 12 || assignment.InstanceId == "" || assignment.InstanceId.Length() > 512 || !HCInteriorCatalog.ItemAllowed(assignment.Item)) return false;
            if (assignment.Item == "Rag") rags++;
            if (assignment.Item == "Battery9V") batteries++;
            HCInteriorAllocation entry = new HCInteriorAllocation;
            entry.SlotId = assignment.SlotId;
            entry.SiteId = assignment.InstanceId + "_storage_v1";
            entry.Item = assignment.Item;
            foreach (HCInteriorAllocation previous : m_Entries)
            {
                if (previous.SlotId == entry.SlotId || previous.SiteId == entry.SiteId) return false;
            }
            m_Entries.Insert(entry);
        }
        return HCInteriorRules.PoolWithinBounds(m_Entries.Count(), rags, batteries);
    }

    HCInteriorAllocation FindSlot(int slot)
    {
        foreach (HCInteriorAllocation entry : m_Entries)
        {
            if (entry.SlotId == slot) return entry;
        }
        return null;
    }

    bool Matches(HCInteriorSite site)
    {
        if (!site) return false;
        HCInteriorAllocation entry = FindSlot(site.SlotId);
        return entry && entry.SiteId == site.Id && entry.Item == site.Item;
    }

    bool TryReserve(HCInteriorSite site)
    {
        if (!Matches(site)) return false;
        HCInteriorAllocation entry = FindSlot(site.SlotId);
        if (site.Phase != 0 || entry.Phase != 0) return false;
        entry.Phase = 1; // Exclude all consumers BEFORE file or inventory work.
        return true;
    }

    bool Reserved(HCInteriorSite site)
    {
        if (!Matches(site)) return false;
        HCInteriorAllocation entry = FindSlot(site.SlotId);
        return site.Phase == 1 && entry.Phase == 1;
    }

    int Reconcile(HCInteriorSite site, int phase)
    {
        if (!Matches(site)) return 3;
        HCInteriorAllocation entry = FindSlot(site.SlotId);
        entry.Phase = HCInteriorRules.ReconcilePhase(entry.Phase, phase);
        return entry.Phase;
    }

    // Returns a new summary, never a mutable allocation. Missing buildings and
    // retired/uncertain sites retain their escrow; there is no refund/reissue API.
    HCInteriorSupplyCount Count(string item)
    {
        HCInteriorSupplyCount count = new HCInteriorSupplyCount;
        foreach (HCInteriorAllocation entry : m_Entries)
        {
            if (entry.Item != item) continue;
            count.Allocated++;
            if (entry.Phase == 0) count.Available++;
            if (entry.Phase == 1) count.Reserved++;
            if (entry.Phase == 2) count.Spent++;
            if (entry.Phase == 3) count.Quarantined++;
        }
        return count;
    }
}
