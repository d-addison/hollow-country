// Native 1.30.164289: 4_World/Entities/ManBase/PlayerBase.c:6924 MessageStatus;
// 3_Game/Global/Game.c:703 CreateObjectEx;
// 3_Game/CE/CentralEconomy.c:30-33 NOLIFETIME/NOPERSISTENCY_WORLD flags.
// Trusted provider supplies reviewed context groups, not label-derived guesses.
// SourcePin must cover the source manifest AND these admissions in the external
// provenance review; script checks binding/syntax, not SHA-256 authenticity.
class HCInteriorSearchContext
{
    string InstanceId;
    string LayoutId;
    string History;
    string Room;
    string GroupId;
    string SourcePin;
    string EvidencePin;
    string MeasuredRecordSha256;
    ref array<string> Items = new array<string>;
}

class HCInteriorSearchSession
{
    HCInteriorSite Site;
    ActionData Owner;
    PlayerBase Actor;
    string ActorId;
}

class HCInteriorsModule : HCModule
{
    protected static HCInteriorsModule s_Instance;
    protected ref HCInteriorConfig m_Config;
    protected ref HCInteriorStore m_Store;
    protected ref HCInteriorManifest m_Manifest;
    protected ref array<Object> m_Objects = new array<Object>;
    protected ref array<ref HCInteriorSite> m_Sites = new array<ref HCInteriorSite>;
    protected int m_LockCursor;
    protected int m_NextCandidate;
    protected bool m_Ready;
    protected bool m_PlacementProof;
    protected bool m_SearchProof;
    protected int m_PropLimit;
    protected ref HCSearchEconomy m_Economy;
    protected bool m_SearchBound;
    // Last SearchGate/CanContinue refusal code (HCRefusal vocabulary); "" when admitted.
    protected string m_SearchRefusal;
    protected ref array<ref HCInteriorSearchSession> m_SearchSessions = new array<ref HCInteriorSearchSession>;

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

    // Native LoadData zero-fills a missing SlotId to 0, which would alias slot 0.
    // The raw text is re-read with the same bounds as HCInteriorJson.Load.
    static bool HCFieldsPresent(string text)
    {
        if (text.Length() < 2) return false;
        return HCJsonFields.Every(text, "SlotId", 3);
    }

    static string HCReadPilotText(string path)
    {
        FileHandle handle = OpenFile(path, FileMode.READ);
        if (!handle) return "";
        string text;
        int count = ReadFile(handle, text, 32769);
        CloseFile(handle);
        if (count <= 0 || count >= 32768 || text.Length() >= 32768) return "";
        return text;
    }

    bool Reject(string reason)
    {
        Print("[HC Interiors] disabled: " + reason);
        return false;
    }

    bool ValidateConfig(HCSettings settings)
    {
        if (!m_Config || m_Config.SchemaVersion != 1 || m_Config.MapName != "chernarusplus" || !HCBuildIdentity.Matches(m_Config.Build)) return Reject("config schema/map/build mismatch; migration is manual");
        if (m_Config.Epoch < 1 || m_Config.Epoch > 899999 || m_Config.Seed < 1 || m_Config.Seed > 1000000) return Reject("epoch or seed outside supported bounds");
        string world = GetGame().GetWorldName();
        world.ToLower();
        if (world != m_Config.MapName) return Reject("running map differs from manifest");
        if (!m_Config.Candidates || m_Config.Candidates.Count() < 1 || m_Config.Candidates.Count() > 12) return Reject("candidate count exceeds manifest bound or is empty");
        if (settings.HCSearchCap("MaxPropsPerInterior", settings.MaxPropsPerInterior) < 2) return Reject("prop budget below the two-prop minimum");
        m_PropLimit = Math.Min(settings.HCSearchCap("MaxPropsPerInterior", settings.MaxPropsPerInterior), 5);
        ref array<ref HCInteriorCandidate> sorted = new array<ref HCInteriorCandidate>;
        for (int slot = 0; slot < 12; slot++)
        {
            foreach (HCInteriorCandidate candidate : m_Config.Candidates)
            {
                if (!candidate || candidate.SlotId < 0 || candidate.SlotId >= 12 || candidate.Type != HCInteriorCatalog.BUILDING) return Reject("invalid stable slot or unsupported building class");
                if (!HCInteriorRules.SaneVector(candidate.Position, 20000) || !HCInteriorRules.SaneVector(candidate.Orientation, 360)) return Reject("nonfinite or out-of-bounds building transform");
                // Yaw-only pilot. No invented conversion of tilted local rotations.
                if (candidate.Orientation[1] != 0 || candidate.Orientation[2] != 0) return Reject("tilted building unsupported by yaw-only pilot");
                if (candidate.SlotId != slot) continue;
                foreach (HCInteriorCandidate previous : sorted)
                {
                    if (previous.SlotId == candidate.SlotId || previous.Key() == candidate.Key()) return Reject("duplicate slot/quantized building identity");
                }
                sorted.Insert(candidate);
            }
        }
        // SearchDensityScale < 1 can scale MaxActiveInteriors below the candidate count:
        // trim the stable-slot-ordered list (lowest slots stay) instead of rejecting the pilot.
        HCTrimCandidatesToCap(sorted, settings.HCSearchCap("MaxActiveInteriors", settings.MaxActiveInteriors));
        if (sorted.Count() < 1) return Reject("no candidates remain after validation");
        if (settings.MaxTickWorkItems < sorted.Count() * 2) return Reject("startup work exceeds core budgets");
        m_Config.Candidates = sorted;
        return true;
    }

    // Returns how many trailing candidates were dropped. Order is stable-slot order, so the
    // result is deterministic. Native EnScript.c:470 array.RemoveOrdered keeps the remaining order.
    int HCTrimCandidatesToCap(array<ref HCInteriorCandidate> sorted, int cap)
    {
        int before = sorted.Count();
        while (sorted.Count() > cap && sorted.Count() > 0)
        {
            sorted.RemoveOrdered(sorted.Count() - 1);
        }
        int kept = sorted.Count();
        int dropped = before - kept;
        if (dropped > 0)
        {
            Print("[HC Interiors] density trimmed legacy pilot candidates kept=" + kept.ToString() + " dropped=" + dropped.ToString() + " cap=" + cap.ToString() + " runtime=PENDING");
        }
        return dropped;
    }

    HCInteriorManifest AllocateManifest()
    {
        HCInteriorManifest manifest = new HCInteriorManifest;
        manifest.SchemaVersion = 1;
        manifest.CatalogVersion = HCInteriorCatalog.VERSION;
        manifest.MapName = m_Config.MapName;
        // Only the canonical spelling is ever written; admitted aliases are checked via HCBuildIdentity.
        manifest.Build = HCBuildIdentity.Canonical();
        manifest.Epoch = m_Config.Epoch;
        manifest.Seed = m_Config.Seed;
        foreach (HCInteriorCandidate candidate : m_Config.Candidates)
        {
            int choice = HCInteriorRules.Layout(HCInteriorRules.Quantize(candidate.Position[0]), HCInteriorRules.Quantize(candidate.Position[1]), HCInteriorRules.Quantize(candidate.Position[2]), HCInteriorRules.Yaw(candidate.Orientation[0]), m_Config.Seed);
            HCInteriorLayout layout = HCInteriorCatalog.GetFor(choice, candidate, m_Config.DiagnosticPlacementTrial);
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
            assignment.SlotId = candidate.SlotId;
            assignment.InstanceId = candidate.Id(m_Config.Epoch);
            assignment.LayoutId = layout.Id;
            assignment.History = layout.History;
            assignment.MeasuredRecordSha256 = HCInteriorMeasuredCatalog.MeasuredDigest(candidate);
            if (HCInteriorMeasuredCatalog.MeasuredRequested() && assignment.MeasuredRecordSha256 == "")
            {
                Reject("measured binding changed during manifest construction");
                return null;
            }
            // Layout state allocates NOTHING. Search supply belongs exclusively
            // to the separately pinned same-handle economy/provider manifest.
            manifest.Assignments.Insert(assignment);
        }
        return manifest;
    }

    // Existing legacy Item values bind old journals only. Never create their
    // outputs or replace a changed/missing image with a fresh allocation.
    bool PreserveLegacyManifest(HCInteriorManifest expected, HCInteriorManifest actual)
    {
        if (!expected || !actual || !expected.Assignments || !actual.Assignments) return false;
        if (expected.SchemaVersion != actual.SchemaVersion || expected.CatalogVersion != actual.CatalogVersion || expected.MapName != actual.MapName || !HCBuildIdentity.SameBuild(expected.Build, actual.Build) || expected.Epoch != actual.Epoch || expected.Seed != actual.Seed) return false;
        if (expected.Assignments.Count() < 1 || expected.Assignments.Count() > 12 || expected.Assignments.Count() != actual.Assignments.Count()) return false;
        int index;
        foreach (HCInteriorAssignment current : expected.Assignments)
        {
            HCInteriorAssignment previous = actual.Assignments[index];
            if (!current || !previous || current.SlotId != previous.SlotId || current.InstanceId != previous.InstanceId || current.LayoutId != previous.LayoutId || current.History != previous.History || current.MeasuredRecordSha256 != previous.MeasuredRecordSha256) return false;
            // The old store validates old quotas and item names on Open().
            current.Item = previous.Item;
            index++;
        }
        return true;
    }

    bool RestoreLayoutManifest()
    {
        string root = "$profile:HollowCountry/interiors_s1_e" + m_Config.Epoch.ToString();
        if (!FileExist(root)) return true;
        HCInteriorManifest previous;
        if (!HCInteriorJson<HCInteriorManifest>.Load(root + "/manifest.json", previous)) return Reject("legacy layout state unavailable; no allocation/depletion rewind");
        if (!PreserveLegacyManifest(m_Manifest, previous)) return Reject("legacy layout identity changed; explicit reviewed migration required");
        return true;
    }

    bool SearchBindingValid(HCSearchManifest manifest, array<ref HCInteriorSearchContext> contexts)
    {
        if (!m_Config || !m_Manifest || !m_Manifest.Assignments || !HCSearchRules.ManifestValid(manifest) || !contexts) return false;
        int count = m_Manifest.Assignments.Count();
        if (count < 1 || count > 12 || manifest.Entries.Count() != count || contexts.Count() != count) return false;
        if (manifest.Epoch != m_Config.Epoch || manifest.WorldName != m_Config.MapName || !HCInteriorMeasuredCatalog.MeasuredBuildMatches(manifest.Build, m_Config.Build)) return false;
        int index;
        foreach (HCInteriorAssignment assignment : m_Manifest.Assignments)
        {
            HCSearchEntry entry = manifest.Entries[index];
            HCInteriorSearchContext context = contexts[index];
            if (!assignment || !entry || !context) return false;
            if (entry.SiteId != assignment.InstanceId + "_storage_v1" || context.InstanceId != assignment.InstanceId || context.LayoutId != assignment.LayoutId || context.History != assignment.History || context.MeasuredRecordSha256 != assignment.MeasuredRecordSha256) return false;
            if (context.SourcePin != manifest.SourcePin || !HCSearchRules.PinValid(context.EvidencePin) || !HCSearchRules.TextValid(context.GroupId, 128) || !HCSearchRules.TextValid(context.Room, 128)) return false;
            if (!context.Items || context.Items.Count() < 1 || context.Items.Count() > 4096) return false;
            foreach (string itemClass : context.Items)
            {
                if (!HCSearchRules.TextValid(itemClass, 128)) return false;
            }
            if (entry.ItemClass != "" && context.Items.Find(entry.ItemClass) < 0) return false;
            index++;
        }
        return true;
    }

    // Trusted server-only post-start seam. A real world-spawner/CE-proxy owner
    // must provide existing native handles and reviewed provenance/context data.
    // No automatic CE bridge, origin inference, refills or proof override.
    bool BindSearchEconomy(HCSearchSupplyRegistry source, HCSearchManifest manifest, array<ref HCInteriorSearchContext> contexts, bool initializeNewEpoch)
    {
        if (!GetGame().IsServer() || !m_Ready || !m_Store || !m_Store.Healthy() || m_SearchBound || m_Economy) return Reject("search provider bind refused: inactive, already bound, or unhealthy layout state");
        if (!SearchBindingValid(manifest, contexts) || !source || !source.ReadyFor(manifest)) return Reject("search provider bind refused: source/context/instance/class/provenance mismatch");
        m_SearchBound = true; // Failed journal Open may leave files: never retry.
        HCSearchEconomy economy = new HCSearchEconomy;
        if (!economy.Open(manifest, source, initializeNewEpoch)) return Reject("search economy refused journal/source; preserve incomplete state");
        m_Economy = economy;
        Print("[HC Interiors] finite native supply/context bound; CE provenance and runtime qualification still required");
        return true;
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
        // Optional legacy pilot. The template override reports its own admission.
        if (!FileExist("$profile:HollowCountry/interiors.json"))
        {
            Print("[HC Interiors] legacy pilot off: interiors.json absent (optional); no pilot search or placement");
            return;
        }
        if (!HCInteriorJson<HCInteriorConfig>.Load("$profile:HollowCountry/interiors.json", m_Config) || !HCFieldsPresent(HCReadPilotText("$profile:HollowCountry/interiors.json")) || !ValidateConfig(settings))
        {
            Print("[HC Interiors] invalid legacy pilot configuration; pilot disabled");
            return;
        }
        Print("[HC Interiors] legacy pilot search awaits trusted native supply/context binding; no supplementary grant fallback");
        HCInteriorMeasuredCatalog.MeasuredEnsureLoaded();
        m_PlacementProof = HCInteriorRules.PlacementAdmitted();
        m_SearchProof = HCInteriorRules.SearchAdmitted();
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
        if (!m_Manifest)
        {
            Print("[HC Interiors] placement disabled: layout manifest unavailable (see the refusal above)");
            return;
        }
        if (!RestoreLayoutManifest())
        {
            Print("[HC Interiors] placement disabled: layout state not restored; preserved for manual recovery");
            return;
        }
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
        HCSearchBinding.PlacementComplete(this, m_Config, m_Manifest, m_Sites);
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

    int InspectProp(vector point, vector orientation, string type, out Object reusable)
    {
        reusable = null;
        array<Object> objects = new array<Object>;
        array<CargoBase> cargos = new array<CargoBase>;
        GetGame().GetObjectsAtPosition3D(point, 0.75, objects, cargos);
        if (objects.Count() > 256) return 3;
        int matches;
        int ownedCount;
        bool exact = true;
        foreach (Object object : objects)
        {
            if (!object || object.GetType() != type || vector.DistanceSq(object.GetPosition(), point) >= 0.0625) continue;
            matches++;
            if (m_Objects.Find(object) >= 0)
            {
                ownedCount++;
                reusable = object;
            }
            if (HCInteriorRules.TransformKey(object.GetPosition(), object.GetOrientation()) != HCInteriorRules.TransformKey(point, orientation)) exact = false;
        }
        int decision = HCInteriorRules.OrphanDecision(true, matches, ownedCount, exact);
        if (decision != 1) reusable = null;
        return decision;
    }

    void PlaceCandidate(int index)
    {
        if (!m_Store || !m_Store.Healthy()) return;
        HCInteriorCandidate candidate = m_Config.Candidates[index];
        HCInteriorAssignment assignment = m_Manifest.Assignments[index];
        if (m_Store.IsHeld(candidate.SlotId)) return;
        Object building = ResolveBuilding(candidate);
        if (!building)
        {
            Print("[HC Interiors] unresolved/ambiguous building slot " + candidate.SlotId.ToString());
            m_Store.HoldSlot(candidate.SlotId, "unresolved-building");
            return;
        }
        int choice = HCInteriorRules.Layout(HCInteriorRules.Quantize(candidate.Position[0]), HCInteriorRules.Quantize(candidate.Position[1]), HCInteriorRules.Quantize(candidate.Position[2]), HCInteriorRules.Yaw(candidate.Orientation[0]), m_Config.Seed);
        HCInteriorLayout layout = HCInteriorCatalog.GetFor(choice, candidate, m_Config.DiagnosticPlacementTrial);
        if (!layout || layout.Id != assignment.LayoutId || layout.History != assignment.History || HCInteriorMeasuredCatalog.MeasuredDigest(candidate) != assignment.MeasuredRecordSha256)
        {
            m_Store.HoldSlot(candidate.SlotId, "changed-measured-binding");
            return;
        }
        array<Object> reusableProps = new array<Object>;
        foreach (HCInteriorProp check : layout.Props)
        {
            vector checkOrientation = check.Orientation;
            checkOrientation[0] = checkOrientation[0] + building.GetOrientation()[0];
            Object reusable;
            if (InspectProp(building.ModelToWorld(check.Position), checkOrientation, check.Type, reusable) == 3)
            {
                Print("[HC Interiors] possible orphan/native prop; slot quarantined " + candidate.SlotId.ToString());
                m_Store.HoldSlot(candidate.SlotId, "foreign-or-ambiguous-prop");
                return;
            }
            reusableProps.Insert(reusable);
        }
        array<Object> created = new array<Object>;
        HCInteriorSite site;
        int propIndex;
        foreach (HCInteriorProp prop : layout.Props)
        {
            int flags = ECE_SETUP | ECE_KEEPHEIGHT | ECE_CREATEPHYSICS | ECE_UPDATEPATHGRAPH | ECE_NOLIFETIME | ECE_NOPERSISTENCY_WORLD;
            Object object = reusableProps[propIndex];
            propIndex++;
            if (!object)
            {
                object = GetGame().CreateObjectEx(prop.Type, building.ModelToWorld(prop.Position), flags, RF_IGNORE);
                if (object) created.Insert(object);
            }
            if (!object)
            {
                m_Store.HoldSlot(candidate.SlotId, "partial-placement");
                foreach (Object partial : created) GetGame().ObjectDelete(partial);
                Print("[HC Interiors] partial layout rolled back; no search site");
                return;
            }
            vector orientation = prop.Orientation;
            orientation[0] = orientation[0] + building.GetOrientation()[0];
            object.SetOrientation(orientation);
            if (prop.Searchable)
            {
                site = new HCInteriorSite;
                site.Id = assignment.InstanceId + "_storage_v1";
                site.SlotId = candidate.SlotId;
                site.Target = object;
                site.Point = object.ModelToWorld(prop.SearchPoint);
                site.Item = assignment.Item;
                site.Phase = m_Store.RecoverSite(site);
            }
        }
        foreach (Object ownedObject : created) m_Objects.Insert(ownedObject);
        HCInteriorPathgraph.Schedule(created);
        if (site && !FindSite(site.Target)) m_Sites.Insert(site);
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
        // Wave 13 (#138): each site visit takes one unit of the shared core-tick budget. The lock
        // cursor resumes at the first unvisited site next tick, one lap at most per tick, so a
        // refused request never skips or repeats a site (the shared budget forces one per tick).
        HCUnitBudget sharedWork = HCServer.HCTickWork();
        int siteCount = m_Sites.Count();
        int visited = 0;
        while (visited < siteCount)
        {
            if (m_LockCursor >= siteCount) m_LockCursor = 0;
            if (!sharedWork.HCTakeFor(HCUnitBudget.HC_WORK_INTERIORS, 1)) break;
            HCInteriorSite lockSite = m_Sites[m_LockCursor];
            m_LockCursor++;
            visited++;
            ExpireLock(lockSite);
        }
    }

    // The one lock-expiry path (#195): clears the owner of a lock whose deadline has passed; true when it
    // did. The tick loop above and CanStart both call it, so an expired lock never blocks a new search
    // while the budgeted cursor has not reached its site yet.
    bool ExpireLock(HCInteriorSite lockSite)
    {
        if (lockSite.Owner && GetGame().GetTickTime() > lockSite.Deadline)
        {
            lockSite.Owner = null;
            return true;
        }
        return false;
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
        m_SearchRefusal = HCRefusal.SERVICE;
        if (!settings) return false;
        bool ready = m_Ready && m_Store && m_Store.Healthy() && m_Economy;
        if (!HCInteriorRules.MaySearch(GetGame().IsServer(), settings.EnableInteriors, settings.EnableSearch, m_SearchProof, ready, player && player.IsAlive(), site && site.Phase == 0)) return false;
        if (!m_Economy.CanGrant(site.Id, player))
        {
            m_SearchRefusal = HCRefusal.SUPPLY;
            return false;
        }
        m_SearchRefusal = "";
        return true;
    }

    string SearchRefusal() { return m_SearchRefusal; }

    bool CanStart(PlayerBase player, ActionTarget target)
    {
        Object subject;
        if (target) subject = target.GetObject();
        HCInteriorSite site = FindSite(subject);
        if (!SearchGate(player, site))
        {
            // SearchGate left the specific code; the player text stays the service one.
            string why = m_SearchRefusal;
            if (why == "") why = HCRefusal.SERVICE;
            HCRefusalReport.RefusalMessage(player, why, subject, "Search unavailable: the search service is not ready on this server.");
            return false;
        }
        ExpireLock(site);
        if (site.Owner)
        {
            HCRefusalReport.RefusalMessage(player, HCRefusal.BUSY, subject, "Someone is already searching here.");
            return false;
        }
        if (!ValidateTarget(player, target, site))
        {
            HCRefusalReport.RefusalMessage(player, HCRefusal.NO_SITE, subject, "Nothing to search at this spot.");
            return false;
        }
        return true;
    }

    bool CanContinue(ActionData data)
    {
        HCInteriorActionData action = HCInteriorActionData.Cast(data);
        m_SearchRefusal = HCRefusal.SESSION;
        if (!action || !action.Site) return false;
        // SearchGate sets its own code when it refuses.
        if (!SearchGate(data.m_Player, action.Site)) return false;
        m_SearchRefusal = HCRefusal.SESSION;
        bool sessionOk = action.Site.Owner == data && SessionValid(data, action.Site);
        if (!sessionOk) return false;
        float now = GetGame().GetTickTime();
        // Written as an inclusive window so a NaN clock refuses.
        if (!(now >= action.Site.StartedAt && now <= action.Site.Deadline)) return false;
        if (!ValidateTarget(data.m_Player, data.m_Target, action.Site))
        {
            m_SearchRefusal = HCRefusal.NO_SITE;
            return false;
        }
        m_SearchRefusal = "";
        return true;
    }

    HCInteriorSearchSession SearchSession(HCInteriorSite site)
    {
        foreach (HCInteriorSearchSession session : m_SearchSessions)
        {
            if (session.Site == site) return session;
        }
        return null;
    }

    bool SessionValid(ActionData data, HCInteriorSite site)
    {
        HCInteriorSearchSession session = SearchSession(site);
        if (!data || !data.m_Player || !session || session.Owner != data || session.Actor != data.m_Player) return false;
        if (!data.m_Player.GetIdentity() || data.m_Player.GetIdentity().GetPlayer() != data.m_Player) return false;
        return session.ActorId != "" && session.ActorId == data.m_Player.GetIdentity().GetId();
    }

    bool SetSession(ActionData data, HCInteriorSite site)
    {
        if (!data || !data.m_Player || !data.m_Player.GetIdentity() || !site) return false;
        if (data.m_Player.GetIdentity().GetPlayer() != data.m_Player) return false;
        string actorId = data.m_Player.GetIdentity().GetId();
        if (!HCSearchRules.TextValid(actorId, 128)) return false;
        HCInteriorSearchSession session = SearchSession(site);
        if (!session)
        {
            if (m_SearchSessions.Count() >= 12) return false;
            session = new HCInteriorSearchSession;
            session.Site = site;
            m_SearchSessions.Insert(session);
        }
        session.Owner = data;
        session.Actor = data.m_Player;
        session.ActorId = actorId;
        return true;
    }

    void BeginSearch(ActionData data)
    {
        HCInteriorActionData action = HCInteriorActionData.Cast(data);
        if (!action)
        {
            HCRefusalReport.ActionRefusalMessage(data, HCRefusal.SESSION, "Search stopped; target or session changed.");
            return;
        }
        if (CanStart(data.m_Player, data.m_Target))
        {
            HCInteriorSite site = FindSite(data.m_Target.GetObject());
            if (!SetSession(data, site))
            {
                HCRefusalReport.ActionRefusalMessage(data, HCRefusal.CAPACITY, "Too many searches in progress; try again shortly.");
                return;
            }
            site.Owner = data;
            site.StartedAt = GetGame().GetTickTime();
            site.Deadline = site.StartedAt + 15.0;
            action.Site = site;
        }
    }

    void CommitSearch(ActionData data)
    {
        if (!GetGame().IsServer()) { return; }
        if (!CanContinue(data))
        {
            if (data && data.m_Player) { HCRefusalReport.ActionRefusalMessage(data, HCRefusal.SESSION, "Search stopped; target or session changed."); }
            return;
        }
        HCInteriorActionData action = HCInteriorActionData.Cast(data);
        HCInteriorSite site = action.Site;
        if (GetGame().GetTickTime() - site.StartedAt < 5.5)
        {
            HCRefusalReport.ActionRefusalMessage(data, HCRefusal.TOO_EARLY, "Search stopped; action completed too early. Please try again.");
            return;
        }
        // Target/capacity checks may cross native callbacks. The same captured
        // player session must still own the action immediately before admission.
        if (!SearchGate(data.m_Player, site) || !SessionValid(data, site))
        {
            HCRefusalReport.ActionRefusalMessage(data, HCRefusal.SUPPLY, "Search unavailable: supply, inventory or service changed.");
            return;
        }
        site.Phase = 1; // Exclude reentry BEFORE adapter I/O/native callbacks.
        int result = m_Economy.Grant(site.Id, data.m_Player);
        if (result < 0)
        {
            // Adapter negatives guarantee no admitted inventory attempt.
            site.Phase = 0;
            HCRefusalReport.ActionRefusalMessage(data, HCRefusal.SUPPLY, "Search unavailable: supply, inventory or service changed.");
            return;
        }
        site.Phase = 3;
        if (result == 2) site.Phase = 2;
        // No success claim inferred from legacy Item or a stale result image.
        if (result == 2)
        {
            data.m_Player.MessageStatus("Search complete.");
        }
        else
        {
            HCRefusalReport.ActionRefusalMessage(data, HCRefusal.STORAGE, "Search stopped; this storage is unavailable.");
        }
    }

    void EndSearch(ActionData data)
    {
        HCInteriorActionData action = HCInteriorActionData.Cast(data);
        if (!action || !action.Site) return;
        HCInteriorSearchSession session = SearchSession(action.Site);
        if (session && session.Owner == data)
        {
            session.Owner = null;
            session.Actor = null;
            session.ActorId = "";
        }
        if (action.Site.Owner == data) action.Site.Owner = null;
        action.Site = null;
    }

    override void OnStop()
    {
        m_Ready = false;
        // Cancel 100 ms updates before deleting owned props. Installed native 1.30.164289:
        // 3_Game/Global/Game.c:1550 GetCallQueue; 2_GameLib/tools.c:65 ScriptCallQueue.Remove(func).
        // Remove matches every queued call of a target, so only the HC-owned
        // target is removed: vanilla tents, fireplaces and base building queue
        // UpdatePathgraphRegionByObject themselves and must keep their updates.
        if (GetGame())
        {
            GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).Remove(HCInteriorTemplatePlacement.HCTimedPathgraph);
        }
        if (m_Economy) m_Economy.Stop();
        m_SearchSessions.Clear();
        HCInteriorMeasuredCatalog.MeasuredClear();
        foreach (HCInteriorSite site : m_Sites) site.Owner = null;
        m_Sites.Clear();
        m_LockCursor = 0;
        // Owned nonpersistent decorations only. Never remove generated/player items.
        foreach (Object object : m_Objects)
        {
            if (object) GetGame().ObjectDelete(object);
        }
        m_Objects.Clear();
        if (s_Instance == this) s_Instance = null;
        // Only an installed (successfully opened) economy may be released after
        // ALL cleanup callbacks complete. A failed Open has no m_Economy and
        // keeps m_SearchBound sticky; partial journal files must not be retried.
        // Binding remains gated on a later successful OnStart and fresh inputs.
        if (m_Economy)
        {
            m_Economy = null;
            m_SearchBound = false;
        }
    }
}

modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        // The binder must be registered first: Interiors places inside its own OnStart and calls the binder hook there.
        Register(new HCSearchBinding);
        Register(new HCInteriorsModule);
    }
}
