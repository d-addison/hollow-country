class HCInteriorsModule : HCModule
{
    protected static HCInteriorsModule s_Instance;
    protected ref HCInteriorConfig m_Config;
    protected ref HCInteriorStore m_Store;
    protected ref HCInteriorManifest m_Manifest;
    protected ref array<Object> m_Objects = new array<Object>;
    protected ref array<ref HCInteriorSite> m_Sites = new array<ref HCInteriorSite>;
    protected int m_NextCandidate;
    protected bool m_Ready;
    protected bool m_PlacementProof;
    protected bool m_SearchProof;
    protected int m_PropLimit;

    static HCInteriorsModule Get()
    {
        return s_Instance;
    }

    override string GetName()
    {
        return "Interiors";
    }

    override bool IsEnabled(HCSettings settings)
    {
        return settings && settings.EnableInteriors;
    }

    bool Reject(string reason)
    {
        Print("[HC Interiors] disabled: " + reason);
        return false;
    }

    bool ValidateConfig(HCSettings settings)
    {
        if (!m_Config || m_Config.SchemaVersion != 1 || m_Config.World != "chernarusplus" || m_Config.Build != "1.30.164289") return Reject("config schema/map/build mismatch; migration is manual");
        if (m_Config.Epoch < 1 || m_Config.Epoch > 899999 || m_Config.Seed < 1 || m_Config.Seed > 1000000) return Reject("epoch or seed outside supported bounds");
        string world = GetGame().GetWorldName();
        world.ToLower();
        if (world != m_Config.World) return Reject("running map differs from manifest");
        if (!m_Config.Candidates || m_Config.Candidates.Count() < 1 || m_Config.Candidates.Count() > 12 || m_Config.Candidates.Count() > settings.MaxActiveInteriors) return Reject("candidate count exceeds manifest/core bounds or is empty");
        if (settings.MaxTickWorkItems < m_Config.Candidates.Count() * 2 || settings.MaxPropsPerInterior < 2) return Reject("startup/prop work exceeds core budgets");
        m_PropLimit = Math.Min(settings.MaxPropsPerInterior, 5);
        ref array<ref HCInteriorCandidate> sorted = new array<ref HCInteriorCandidate>;
        for (int slot = 0; slot < 12; slot++)
        {
            foreach (HCInteriorCandidate candidate : m_Config.Candidates)
            {
                if (!candidate || candidate.Slot < 0 || candidate.Slot >= 12 || candidate.Type != HCInteriorCatalog.BUILDING) return Reject("invalid stable slot or unsupported building class");
                if (!HCInteriorRules.SaneVector(candidate.Position, 20000) || !HCInteriorRules.SaneVector(candidate.Orientation, 360)) return Reject("nonfinite or out-of-bounds building transform");
                // Yaw-only pilot. No invented conversion of tilted local rotations.
                if (candidate.Orientation[1] != 0 || candidate.Orientation[2] != 0) return Reject("tilted building unsupported by yaw-only pilot");
                if (candidate.Slot != slot) continue;
                foreach (HCInteriorCandidate previous : sorted)
                {
                    if (previous.Slot == candidate.Slot || previous.Key() == candidate.Key()) return Reject("duplicate slot/quantized building identity");
                }
                sorted.Insert(candidate);
            }
        }
        m_Config.Candidates = sorted;
        return sorted.Count() > 0;
    }

    HCInteriorManifest AllocateManifest()
    {
        HCInteriorManifest manifest = new HCInteriorManifest;
        manifest.SchemaVersion = 1;
        manifest.CatalogVersion = HCInteriorCatalog.VERSION;
        manifest.World = m_Config.World;
        manifest.Build = m_Config.Build;
        manifest.Epoch = m_Config.Epoch;
        manifest.Seed = m_Config.Seed;
        int rags;
        int batteries;
        foreach (HCInteriorCandidate candidate : m_Config.Candidates)
        {
            int choice = HCInteriorRules.Layout(HCInteriorRules.Quantize(candidate.Position[0]), HCInteriorRules.Quantize(candidate.Position[1]), HCInteriorRules.Quantize(candidate.Position[2]), HCInteriorRules.Yaw(candidate.Orientation[0]), m_Config.Seed);
            HCInteriorLayout layout = HCInteriorCatalog.Get(choice);
            if (!layout || layout.Props.Count() > m_PropLimit)
            {
                Reject("layout missing or over prop budget");
                return null;
            }
            foreach (HCInteriorProp prop : layout.Props)
            {
                if (!GetGame().ConfigIsExisting("CfgVehicles " + prop.Type))
                {
                    Reject("native prop config missing: " + prop.Type);
                    return null;
                }
            }
            HCInteriorAssignment assignment = new HCInteriorAssignment;
            assignment.Slot = candidate.Slot;
            assignment.InstanceId = candidate.Id(m_Config.Epoch);
            assignment.LayoutId = layout.Id;
            assignment.History = layout.History;
            // Supplementary escrow only, NOT a replacement for CE accounting.
            // Explicit no-result and finite per-epoch quotas; never replenish.
            int allocation = HCInteriorRules.Allocation(choice, rags, batteries);
            if (allocation == 1)
            {
                assignment.Item = "Rag";
                rags++;
            }
            else if (allocation == 2)
            {
                assignment.Item = "Battery9V";
                batteries++;
            }
            if (!HCInteriorCatalog.ItemAllowed(assignment.Item))
            {
                Reject("allocation outside item allowlist");
                return null;
            }
            if (assignment.Item != "" && !GetGame().ConfigIsExisting("CfgVehicles " + assignment.Item))
            {
                Reject("native allocated item config missing: " + assignment.Item);
                return null;
            }
            manifest.Assignments.Insert(assignment);
        }
        return manifest;
    }

    override void OnStart(HCSettings settings)
    {
        if (!GetGame().IsServer() || !IsEnabled(settings) || s_Instance) return;
        #ifdef DIAG_DEVELOPER
        if (!HCInteriorSelfTests.Run())
        {
            Print("[HC Interiors] algorithm self-tests failed; disabled");
            return;
        }
        #endif
        if (!HCInteriorJson<HCInteriorConfig>.Load("$profile:HollowCountry/interiors.json", m_Config) || !ValidateConfig(settings))
        {
            Print("[HC Interiors] missing/invalid manifest configuration; disabled");
            return;
        }
        m_PlacementProof = HCInteriorRules.PlacementAccepted();
        m_SearchProof = HCInteriorRules.SearchAccepted();
        #ifdef DIAG_DEVELOPER
        // Explicit diagnostic-only experiment switches. Never production approval.
        m_PlacementProof = m_PlacementProof || m_Config.DiagnosticPlacementTrial;
        m_SearchProof = m_SearchProof || m_Config.DiagnosticSearchTrial;
        #endif
        if (!m_SearchProof) Print("[HC Interiors] search disabled: durable commit/CE/two-client proof pending");
        if (!m_PlacementProof)
        {
            Print("[HC Interiors] placement disabled: collision/nav/replication proof pending");
            return;
        }
        m_Manifest = AllocateManifest();
        if (!m_Manifest) return;
        if (!FileExist("$profile:HollowCountry") && !MakeDirectory("$profile:HollowCountry"))
        {
            Reject("cannot create profile state directory");
            return;
        }
        m_Store = new HCInteriorStore;
        if (!m_Store.Open(m_Config, m_Manifest))
        {
            Print("[HC Interiors] state missing, changed or corrupt; preserve it for manual recovery");
            return;
        }
        m_NextCandidate = 0;
        // Bounded synchronous startup, <=24 props. Never furnish on live ticks.
        // Native mission/client ordering still requires runtime observation.
        while (m_NextCandidate < m_Config.Candidates.Count())
        {
            PlaceCandidate(m_NextCandidate);
            m_NextCandidate++;
        }
        m_Ready = true;
        s_Instance = this;
    }

    // Fixed manifest, one small native spatial query per building. No player scan.
    Object ResolveBuilding(HCInteriorCandidate candidate)
    {
        array<Object> objects = new array<Object>;
        array<CargoBase> cargos = new array<CargoBase>;
        GetGame().GetObjectsAtPosition3D(candidate.Position, 0.75, objects, cargos);
        if (objects.Count() > 256) return null;
        Object found;
        foreach (Object object : objects)
        {
            if (!object || object.GetType() != candidate.Type) continue;
            if (HCInteriorRules.TransformKey(object.GetPosition(), object.GetOrientation()) != HCInteriorRules.TransformKey(candidate.Position, candidate.Orientation)) continue;
            if (found) return null; // identity collision: never depend on query order
            found = object;
        }
        return found;
    }

    bool Vacant(vector point, string type)
    {
        array<Object> objects = new array<Object>;
        array<CargoBase> cargos = new array<CargoBase>;
        GetGame().GetObjectsAtPosition3D(point, 0.75, objects, cargos);
        if (objects.Count() > 256) return false;
        foreach (Object object : objects)
        {
            if (object && object.GetType() == type && vector.DistanceSq(object.GetPosition(), point) < 0.0625) return false;
        }
        return true;
    }

    void PlaceCandidate(int index)
    {
        HCInteriorCandidate candidate = m_Config.Candidates[index];
        HCInteriorAssignment assignment = m_Manifest.Assignments[index];
        Object building = ResolveBuilding(candidate);
        if (!building)
        {
            Print("[HC Interiors] unresolved/ambiguous building slot " + candidate.Slot.ToString());
            return;
        }
        int choice = HCInteriorRules.Layout(HCInteriorRules.Quantize(candidate.Position[0]), HCInteriorRules.Quantize(candidate.Position[1]), HCInteriorRules.Quantize(candidate.Position[2]), HCInteriorRules.Yaw(candidate.Orientation[0]), m_Config.Seed);
        HCInteriorLayout layout = HCInteriorCatalog.Get(choice);
        foreach (HCInteriorProp check : layout.Props)
        {
            if (!Vacant(building.ModelToWorld(check.Position), check.Type))
            {
                Print("[HC Interiors] possible orphan/native prop; slot quarantined " + candidate.Slot.ToString());
                return;
            }
        }
        array<Object> created = new array<Object>;
        HCInteriorSite site;
        foreach (HCInteriorProp prop : layout.Props)
        {
            int flags = ECE_SETUP | ECE_KEEPHEIGHT | ECE_CREATEPHYSICS | ECE_UPDATEPATHGRAPH | ECE_NOLIFETIME | ECE_DYNAMIC_PERSISTENCY;
            Object object = GetGame().CreateObjectEx(prop.Type, building.ModelToWorld(prop.Position), flags, RF_IGNORE);
            if (!object)
            {
                foreach (Object partial : created) GetGame().ObjectDelete(partial);
                Print("[HC Interiors] partial layout rolled back; no search site");
                return;
            }
            vector orientation = prop.Orientation;
            orientation[0] = orientation[0] + building.GetOrientation()[0];
            object.SetOrientation(orientation);
            created.Insert(object);
            if (prop.Searchable)
            {
                site = new HCInteriorSite;
                site.Id = assignment.InstanceId + "_storage_v1";
                site.Slot = candidate.Slot;
                site.Target = object;
                site.Point = object.ModelToWorld(prop.SearchPoint);
                site.Item = assignment.Item;
                site.Phase = m_Store.RecoverSite(site);
            }
        }
        foreach (Object owned : created) m_Objects.Insert(owned);
        if (site) m_Sites.Insert(site);
    }

    override void OnTick(float deltaTime)
    {
        if (!m_Ready || !GetGame().IsServer()) return;
        HCSettings settings = HCServer.Get().GetSettings();
        if (!IsEnabled(settings))
        {
            OnStop();
            return;
        }
        // <=12 locks; no per-frame/world enumeration, writes or reactivation.
        foreach (HCInteriorSite site : m_Sites)
        {
            if (site.Owner && GetGame().GetTickTime() > site.Deadline) site.Owner = null;
        }
    }

    HCInteriorSite FindSite(Object target)
    {
        foreach (HCInteriorSite site : m_Sites)
        {
            if (site.Target == target) return site;
        }
        return null;
    }

    bool ValidateTarget(PlayerBase player, ActionTarget target, HCInteriorSite site)
    {
        if (!player || !player.IsAlive() || player.IsUnconscious() || !player.GetIdentity() || !target || !site || !site.Target) return false;
        if (player.GetHumanInventory().GetEntityInHands()) return false;
        if (target.GetObject() != site.Target || target.GetParent() || target.GetComponentIndex() < 0) return false;
        if (!HCInteriorCatalog.SearchType(site.Target.GetType())) return false;
        vector head = MiscGameplayFunctions.GetPlayerHeadPosition(player);
        if (vector.DistanceSq(head, site.Point) > 3.24 || vector.DistanceSq(player.GetPosition(), site.Point) > 6.25) return false;
        vector contact;
        vector normal;
        int component;
        set<Object> hits = new set<Object>;
        // Server-owned endpoint; nearest view-geometry contact must be this prop.
        if (!DayZPhysics.RaycastRV(head, site.Point, contact, normal, component, hits, null, player, true, false, ObjIntersectView)) return false;
        if (hits.Count() != 1 || hits[0] != site.Target || component != target.GetComponentIndex()) return false;
        return vector.DistanceSq(contact, site.Point) <= 0.25;
    }

    bool SearchGate(PlayerBase player, HCInteriorSite site)
    {
        HCSettings settings = HCServer.Get().GetSettings();
        bool ready = m_Ready && m_Store && m_Store.Healthy();
        return HCInteriorRules.MaySearch(GetGame().IsServer(), settings.EnableInteriors, settings.EnableSearch, m_SearchProof, ready, player && player.IsAlive(), site && site.Phase == 0);
    }

    bool CanStart(PlayerBase player, ActionTarget target)
    {
        if (!target) return false;
        HCInteriorSite site = FindSite(target.GetObject());
        return SearchGate(player, site) && !site.Owner && ValidateTarget(player, target, site);
    }

    bool CanContinue(ActionData data)
    {
        HCInteriorActionData action = HCInteriorActionData.Cast(data);
        if (!action || !action.Site) return false;
        return SearchGate(data.m_Player, action.Site) && action.Site.Owner == data && GetGame().GetTickTime() >= action.Site.StartedAt && GetGame().GetTickTime() <= action.Site.Deadline && ValidateTarget(data.m_Player, data.m_Target, action.Site);
    }

    void BeginSearch(ActionData data)
    {
        HCInteriorActionData action = HCInteriorActionData.Cast(data);
        if (!action || !CanStart(data.m_Player, data.m_Target)) return;
        HCInteriorSite site = FindSite(data.m_Target.GetObject());
        site.Owner = data;
        site.StartedAt = GetGame().GetTickTime();
        site.Deadline = site.StartedAt + 15.0;
        action.Site = site;
    }

    void CommitSearch(ActionData data)
    {
        if (!GetGame().IsServer() || !CanContinue(data)) return;
        HCInteriorActionData action = HCInteriorActionData.Cast(data);
        HCInteriorSite site = action.Site;
        if (GetGame().GetTickTime() - site.StartedAt < 6.0) return;
        if (!HCInteriorCatalog.ItemAllowed(site.Item)) return;
        if (site.Item != "")
        {
            InventoryLocation location = new InventoryLocation;
            if (!data.m_Player.GetInventory().FindFirstFreeLocationForNewEntity(site.Item, FindInventoryLocationType.CARGO | FindInventoryLocationType.ATTACHMENT, location))
            {
                data.m_Player.MessageStatus("Not enough inventory space.");
                return;
            }
        }
        string playerId = data.m_Player.GetIdentity().GetId();
        if (!m_Store.Reserve(site, playerId))
        {
            site.Phase = 3;
            return;
        }
        if (site.Item == "")
        {
            m_Store.Finish(site, playerId, 2);
            data.m_Player.MessageStatus("The storage is empty.");
            return;
        }
        // No ground fallback, retry, rollback to AVAILABLE or delete of player loot.
        EntityAI output = data.m_Player.GetInventory().CreateInInventory(site.Item);
        if (!output)
        {
            m_Store.Finish(site, playerId, 3);
            data.m_Player.MessageStatus("Search failed; this storage is unavailable.");
            return;
        }
        // Allocated unit count is one, not a native default multi-unit stack.
        ItemBase item = ItemBase.Cast(output);
        if (item && item.HasQuantity()) item.SetQuantity(1);
        m_Store.Finish(site, playerId, 2);
        data.m_Player.MessageStatus("Found supplies.");
    }

    void EndSearch(ActionData data)
    {
        HCInteriorActionData action = HCInteriorActionData.Cast(data);
        if (!action || !action.Site) return;
        if (action.Site.Owner == data) action.Site.Owner = null;
        action.Site = null;
    }

    override void OnStop()
    {
        m_Ready = false;
        foreach (HCInteriorSite site : m_Sites) site.Owner = null;
        m_Sites.Clear();
        // Owned nonpersistent decorations only. Never remove generated/player items.
        foreach (Object object : m_Objects)
        {
            if (object) GetGame().ObjectDelete(object);
        }
        m_Objects.Clear();
        if (s_Instance == this) s_Instance = null;
    }
}

modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        Register(new HCInteriorsModule);
    }
}
