// Native supply provider for the search economy. SOURCE of finite supply: loot the
// stock Central Economy ALREADY placed in the world (ground or building proxy cargo)
// inside reviewed per-site volumes. This class never creates, deletes, splits,
// re-quantities, re-lifetimes or moves an entity: it only observes with
// GetObjectsAtPosition3D and hands same-entity handles to HCSearchSupplyRegistry.
// CEApi spawners are DIAG-only force-spawns and script creation has no documented
// CE-accounting contract, so search-time creation is deliberately NOT a fallback:
// unavailable/absent supply is an honest refusal. Nothing here is engine proof.
class HCSearchSiteVolume
{
    string SiteId;
    vector Center;
    float Radius;
    ref array<string> Classes = new array<string>;
}

// Work budget for ONE Prepare, shared by every volume. GetObjectsAtPosition3D has no
// result-count argument (3_Game/Global/Game.c:930), so the native call itself cannot
// be bounded; only the script walk over its result can. Exhaustion is an incomplete
// scan: absence can then not be proven, so Prepare refuses instead of guessing.
class HCSearchScanBudget
{
    int ObjectsLeft = 32768;
    int ContainersLeft = 4096;
    int SlotsLeft = 32768;
    bool Overflow;
    string Reason;
}

class HCSearchSupplyPlan
{
    ref HCSearchSupplyRegistry Registry;
    ref HCSearchManifest Manifest;
    // true only for a first-ever epoch; false = bound from the stored manifest.
    bool InitializeNewEpoch;
}

class HCSearchSupplyProvider
{
    HCSearchSupplyPlan Refuse(HCSearchSupplyRegistry registry, string reason)
    {
        if (registry) registry.Retire();
        Print("[HC Search Supply] refused: " + reason);
        return null;
    }

    // A plan that will not be bound to an economy (for example the caller gave up after
    // Prepare) must hand its handles back. A registry already bound to an economy is
    // owned by that economy and is only ever retired by its Stop.
    void Abandon(HCSearchSupplyPlan plan)
    {
        if (!plan || !plan.Registry) return;
        if (!plan.Registry.Owning()) plan.Registry.Retire();
    }

    bool VolumesValid(array<ref HCSearchSiteVolume> volumes)
    {
        if (!volumes || volumes.Count() < 1 || volumes.Count() > 4096) return false;
        map<string, bool> sites = new map<string, bool>;
        foreach (HCSearchSiteVolume volume : volumes)
        {
            if (!volume || !HCSearchRules.TextValid(volume.SiteId, 768) || sites.Contains(volume.SiteId)) return false;
            sites.Set(volume.SiteId, true);
            if (!(volume.Radius > 0.0 && volume.Radius <= 8.0)) return false;
            if (!volume.Classes || volume.Classes.Count() < 1 || volume.Classes.Count() > 256) return false;
            foreach (string itemClass : volume.Classes)
            {
                if (!HCSearchRules.TextValid(itemClass, 128)) return false;
            }
        }
        return true;
    }

    bool NoPlayers()
    {
        array<Man> players = new array<Man>;
        GetGame().GetPlayers(players);
        return players.Count() == 0;
    }

    string RecordId(string supplyId)
    {
        return "native_" + supplyId;
    }

    bool Eligible(HCSearchSiteVolume volume, EntityAI item)
    {
        if (!HCSearchSupplyRegistry.CandidateValid(item) || volume.Classes.Find(item.GetType()) < 0) return false;
        if (HCSearchSupplyRegistry.PersistentId(item) == "") return false;
        return vector.DistanceSq(volume.Center, item.GetPosition()) <= volume.Radius * volume.Radius;
    }

    // True when the scan of this volume is finished (match found or overflow).
    // Discovery (wantedId empty) gathers every eligible candidate and flags overflow at
    // the 65th instead of silently truncating. Rebind (wantedId set) gathers ONLY the
    // stored persistent id + class, so unrelated crowding can never hide it.
    bool Accept(HCSearchSiteVolume volume, HCSearchScanBudget budget, string wantedId, string wantedClass, EntityAI item, array<EntityAI> output)
    {
        if (!item || output.Find(item) >= 0 || !Eligible(volume, item)) return false;
        if (wantedId != "")
        {
            if (HCSearchSupplyRegistry.PersistentId(item) != wantedId || item.GetType() != wantedClass) return false;
            output.Insert(item);
            return true;
        }
        if (output.Count() >= 64)
        {
            budget.Overflow = true;
            budget.Reason = "more than 64 eligible candidates in one reviewed volume";
            return true;
        }
        output.Insert(item);
        return false;
    }

    // Observation only: ground objects plus building proxy cargo within the volume,
    // inside the per-Prepare object/container/slot budget.
    void Collect(HCSearchSiteVolume volume, HCSearchScanBudget budget, string wantedId, string wantedClass, array<EntityAI> output)
    {
        array<Object> objects = new array<Object>;
        array<CargoBase> cargos = new array<CargoBase>;
        GetGame().GetObjectsAtPosition3D(volume.Center, volume.Radius, objects, cargos);
        foreach (Object found : objects)
        {
            if (budget.ObjectsLeft < 1)
            {
                budget.Overflow = true;
                budget.Reason = "object budget exhausted";
                return;
            }
            budget.ObjectsLeft = budget.ObjectsLeft - 1;
            if (Accept(volume, budget, wantedId, wantedClass, EntityAI.Cast(found), output)) return;
        }
        foreach (CargoBase cargo : cargos)
        {
            if (budget.ContainersLeft < 1)
            {
                budget.Overflow = true;
                budget.Reason = "container budget exhausted";
                return;
            }
            budget.ContainersLeft = budget.ContainersLeft - 1;
            if (!cargo || !cargo.IsProxyCargo()) continue;
            int count = cargo.GetItemCount();
            int limit = count;
            if (limit > 256) limit = 256;
            int slot = 0;
            while (slot < limit)
            {
                // Every visited slot is debited BEFORE it is read, so a match deep in a
                // cargo costs exactly what a miss does and nothing bypasses the budget.
                if (budget.SlotsLeft < 1)
                {
                    budget.Overflow = true;
                    budget.Reason = "cargo slot budget exhausted";
                    return;
                }
                budget.SlotsLeft = budget.SlotsLeft - 1;
                if (Accept(volume, budget, wantedId, wantedClass, cargo.GetItem(slot), output)) return;
                slot++;
            }
            if (limit < count)
            {
                budget.Overflow = true;
                budget.Reason = "more than 256 slots in one cargo";
                return;
            }
        }
    }

    // Existing epoch: the stored manifest is the only truth. Rebind exact handles by
    // persistent id + class; consumed/missing/changed items simply stay unbound, but
    // ONLY after a complete scan: budget overflow is a refusal, never "absent".
    bool BindStored(HCSearchSupplyRegistry registry, HCSearchEntry entry, HCSearchSiteVolume volume, HCSearchScanBudget budget)
    {
        array<EntityAI> candidates = new array<EntityAI>;
        Collect(volume, budget, entry.SupplyId, entry.ItemClass, candidates);
        if (candidates.Count() < 1) return false;
        return registry.RegisterOwned(candidates[0], RecordId(entry.SupplyId));
    }

    HCSearchManifest Rebind(HCSearchSupplyRegistry registry, string root, int epoch, string worldName, string build, string sourceId, string sourcePin, array<ref HCSearchSiteVolume> volumes, HCSearchScanBudget budget)
    {
        HCSearchManifest stored;
        if (!HCSearchJson<HCSearchManifest>.Load(root + "/manifest.json", 8388608, stored))
        {
            Refuse(registry, "stored manifest missing/corrupt; never reinitialize or rescan an existing epoch");
            return null;
        }
        if (!HCSearchRules.ManifestValid(stored) || stored.Epoch != epoch || stored.WorldName != worldName || stored.Build != build || stored.SourceId != sourceId || stored.SourcePin != sourcePin)
        {
            Refuse(registry, "stored epoch identity changed; migration required");
            return null;
        }
        if (stored.Entries.Count() != volumes.Count())
        {
            Refuse(registry, "reviewed site set changed; migration required");
            return null;
        }
        int index;
        while (index < stored.Entries.Count())
        {
            if (stored.Entries[index].SiteId != volumes[index].SiteId)
            {
                Refuse(registry, "reviewed site order/identity changed; migration required");
                return null;
            }
            index++;
        }
        int bound;
        index = 0;
        while (index < stored.Entries.Count())
        {
            if (stored.Entries[index].SupplyId != "" && BindStored(registry, stored.Entries[index], volumes[index], budget)) bound++;
            if (budget.Overflow)
            {
                Refuse(registry, "scan incomplete (" + budget.Reason + "); stored supply presence cannot be proven");
                return null;
            }
            index++;
        }
        Print("[HC Search Supply] rebound " + bound.ToString() + " of the stored native supplies; absent ones stay unavailable, never recreated");
        return stored;
    }

    // First-ever epoch: observe what the stock CE already placed, one distinct entity
    // per site at most, then freeze it in the manifest. Never writes an all-empty epoch.
    HCSearchManifest Discover(HCSearchSupplyRegistry registry, int epoch, string worldName, string build, string sourceId, string sourcePin, array<ref HCSearchSiteVolume> volumes, HCSearchScanBudget budget)
    {
        HCSearchManifest manifest = new HCSearchManifest;
        manifest.Version = 1;
        manifest.Epoch = epoch;
        manifest.WorldName = worldName;
        manifest.Build = build;
        manifest.SourceId = sourceId;
        manifest.SourcePin = sourcePin;
        map<string, bool> assigned = new map<string, bool>;
        int found;
        foreach (HCSearchSiteVolume volume : volumes)
        {
            HCSearchEntry entry = new HCSearchEntry;
            entry.SiteId = volume.SiteId;
            array<EntityAI> candidates = new array<EntityAI>;
            Collect(volume, budget, "", "", candidates);
            if (budget.Overflow)
            {
                Refuse(registry, "scan incomplete (" + budget.Reason + "); narrow the reviewed volume or classes");
                return null;
            }
            foreach (EntityAI candidate : candidates)
            {
                string supplyId = HCSearchSupplyRegistry.PersistentId(candidate);
                if (entry.SupplyId != "" || supplyId == "" || assigned.Contains(supplyId)) continue;
                if (!registry.RegisterOwned(candidate, RecordId(supplyId))) continue;
                assigned.Set(supplyId, true);
                entry.SupplyId = supplyId;
                entry.ItemClass = candidate.GetType();
                found++;
            }
            manifest.Entries.Insert(entry);
        }
        if (found < 1)
        {
            Refuse(registry, "no native supply observed in reviewed volumes; CE may not have populated yet");
            return null;
        }
        if (!HCSearchRules.ManifestValid(manifest))
        {
            Refuse(registry, "discovered manifest invalid");
            return null;
        }
        return manifest;
    }

    // Trusted server-only. Returns null (and releases handles) on ANY doubt; the
    // caller then never binds an economy, so searching stays honestly refused.
    HCSearchSupplyPlan Prepare(int epoch, string sourceId, string sourcePin, array<ref HCSearchSiteVolume> volumes, bool allowNewEpoch)
    {
        if (!GetGame().IsServer() || !GetCEApi()) return Refuse(null, "not a CE-enabled server");
        if (epoch < 1 || epoch > 1000000 || !HCSearchRules.TextValid(sourceId, 128) || !HCSearchRules.PinValid(sourcePin)) return Refuse(null, "invalid epoch or source pin");
        if (!VolumesValid(volumes)) return Refuse(null, "invalid reviewed site volumes");
        string build;
        GetGame().GetVersion(build);
        string worldName = GetGame().GetWorldName();
        string root = "$profile:HollowCountry/SearchEconomy/epoch_" + epoch.ToString();
        bool existing = FileExist(root);
        if (!existing && !allowNewEpoch) return Refuse(null, "new epoch requires explicit initialization; never auto-refill");
        if (!existing && !NoPlayers()) return Refuse(null, "new epoch discovery requires no connected players");
        HCSearchSupplyRegistry registry = new HCSearchSupplyRegistry;
        if (!registry.BindSource(sourceId, sourcePin, worldName, build)) return Refuse(registry, "source binding refused");
        HCSearchSupplyPlan plan = new HCSearchSupplyPlan;
        plan.Registry = registry;
        HCSearchScanBudget budget = new HCSearchScanBudget;
        if (existing) plan.Manifest = Rebind(registry, root, epoch, worldName, build, sourceId, sourcePin, volumes, budget);
        if (!existing)
        {
            plan.InitializeNewEpoch = true;
            plan.Manifest = Discover(registry, epoch, worldName, build, sourceId, sourcePin, volumes, budget);
        }
        if (!plan.Manifest) return null;
        return plan;
    }
}
