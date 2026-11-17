// W1.2 (#15/#42): trusted post-placement observation/binding, never a loot spawner.
// Native snapshot 1.30.164289 (paths relative to the installed native cache):
//   3_Game/gameplay.c:636 GetGame
//   3_Game/Global/Game.c:1120 IsServer; :1550 GetCallQueue
//   2_GameLib/tools.c:61 CallLater(func, delay, repeat); :65 Remove(func)
//   3_Game/Entities/Object.c:287 GetPosition; :305 GetOrientation; :467 GetType;
//     :873 ModelToWorld(vector modelPos)
//   1_Core/proto/EnConvert.c:210 vector.DistanceSq; :30 int.ToString
//   1_Core/proto/EnScript.c:380 Count; :385 Clear; :394 Find; :407 Insert
//   1_Core/proto/EnDebug.c:96 Print; 3_Game/tools/tools.c:8 CALL_CATEGORY_SYSTEM
// No native CE-ready event is assumed: delayed Prepare observes existing supply,
// retries a fixed number of times, then refuses. Runtime acceptance stays pending.
class HCSearchBindingReview
{
    ref HCSearchSiteVolume Volume;
    ref HCInteriorSearchContext Context;
}

// Keep the measured record private to its catalog. Export only fresh binding DTOs;
// do not extend the config/assignment/measurement schema or guess from layout names.
modded class HCInteriorMeasuredCatalog
{
    static HCSearchBindingReview SearchBindingReview(HCInteriorCandidate candidate, HCInteriorAssignment assignment, HCInteriorSite site)
    {
        if (!MeasuredLive(candidate) || !assignment || !site || !site.Target) return null;
        if (assignment.MeasuredRecordSha256 != s_Binding.RecordSha256 || !HCSearchRules.PinValid(s_Binding.RecordSha256)) return null;
        if (site.SlotId != assignment.SlotId || site.Id != assignment.InstanceId + "_storage_v1") return null;
        HCInteriorMeasuredCatalogLayout selected;
        foreach (HCInteriorMeasuredCatalogLayout measuredLayout : s_Binding.Record.Layouts)
        {
            if (measuredLayout.Id == assignment.LayoutId) selected = measuredLayout;
        }
        if (!selected || selected.History != assignment.History || !selected.Survey || !selected.Survey.Props || selected.Survey.Props.Count() < 1 || !selected.Props || selected.Props.Count() < 1) return null;
        // The admitted schema binds storage to prop zero; other props are decoration.
        HCInteriorMeasuredCatalogProp storage = selected.Props[0];
        HCInteriorMeasuredCatalogMeasuredProp measuredStorage = selected.Survey.Props[0];
        if (!storage || !storage.Searchable || !measuredStorage || measuredStorage.Index != 0 || !MeasuredBox(measuredStorage.Bounds)) return null;
        HCInteriorMeasuredCatalogRule rule = MeasuredRule(s_Binding.Record.Policy, selected.Id);
        if (!rule || rule.History != assignment.History || rule.Room != measuredStorage.Room || rule.Storage != "added-searchable-prop" || !rule.ItemGroups || rule.ItemGroups.Count() < 1) return null;
        if (site.Target.GetType() != storage.Type || vector.DistanceSq(site.Target.GetPosition(), s_Binding.HouseObject.ModelToWorld(MeasuredAsVector(storage.Position))) != 0) return null;
        vector expectedOrientation = MeasuredAsVector(storage.Orientation);
        expectedOrientation[0] = expectedOrientation[0] + s_Binding.Orientation[0];
        // Reuse placement's canonical yaw rule; equivalent wrapped angles match.
        vector actualOrientation = site.Target.GetOrientation();
        if (HCInteriorRules.Yaw(actualOrientation[0]) != HCInteriorRules.Yaw(expectedOrientation[0]) || actualOrientation[1] != expectedOrientation[1] || actualOrientation[2] != expectedOrientation[2]) return null;
        if (vector.DistanceSq(site.Point, site.Target.ModelToWorld(MeasuredAsVector(storage.SearchPoint))) != 0) return null;

        HCSearchBindingReview review = new HCSearchBindingReview;
        review.Volume = new HCSearchSiteVolume;
        review.Context = new HCInteriorSearchContext;
        review.Volume.SiteId = site.Id;
        // The record supplies building-local storage bounds, not a CE scan radius.
        // Use the INSCRIBED sphere: never widen observation beyond reviewed bounds.
        // The current catalog admits yaw-only house transforms, preserving radius.
        vector center = "0 0 0";
        float radius = 8.0;
        int axis;
        while (axis < 3)
        {
            float low = measuredStorage.Bounds.Min[axis];
            float high = measuredStorage.Bounds.Max[axis];
            center[axis] = (low + high) * 0.5;
            float halfExtent = (high - low) * 0.5;
            if (!(halfExtent > 0.0) || halfExtent > 8.0) return null;
            if (halfExtent < radius) radius = halfExtent;
            axis++;
        }
        review.Volume.Center = s_Binding.HouseObject.ModelToWorld(center);
        review.Volume.Radius = radius;
        review.Context.InstanceId = assignment.InstanceId;
        review.Context.LayoutId = assignment.LayoutId;
        review.Context.History = assignment.History;
        review.Context.MeasuredRecordSha256 = assignment.MeasuredRecordSha256;
        review.Context.Room = rule.Room;
        // The externally trusted full record digest covers geometry, observations
        // and item policy. This is an asserted pin, never native SHA verification
        // or a claim that proximity alone establishes stock-CE provenance.
        review.Context.SourcePin = s_Binding.RecordSha256;
        review.Context.EvidencePin = s_Binding.RecordSha256;
        foreach (string groupId : rule.ItemGroups)
        {
            HCInteriorMeasuredCatalogGroup group = MeasuredGroup(s_Binding.Record.Policy, groupId);
            if (!group || !group.Items || group.Items.Count() < 1) return null;
            if (review.Context.GroupId != "") review.Context.GroupId = review.Context.GroupId + "+";
            review.Context.GroupId = review.Context.GroupId + groupId;
            foreach (string itemClass : group.Items)
            {
                if (!HCSearchRules.TextValid(itemClass, 128)) return null;
                if (review.Context.Items.Find(itemClass) >= 0) continue;
                review.Context.Items.Insert(itemClass);
                review.Volume.Classes.Insert(itemClass);
            }
        }
        if (!HCSearchRules.TextValid(review.Context.GroupId, 128) || !HCSearchRules.TextValid(review.Context.Room, 128) || review.Context.Items.Count() < 1 || review.Context.Items.Count() > 256) return null;
        return review;
    }
}

// Core integration: Register(new HCSearchBinding); in HCModuleRegistry.RegisterModules
// before the interior module is started. This gives mission finish an OnStop owner.
class HCSearchBinding : HCModule
{
    static const int RETRY_MS = 10000;
    static const int MAX_ATTEMPTS = 3;
    static const string SOURCE_ID = "stock-ce-measured-interiors-v1";
    protected static HCSearchBinding s_Instance;
    protected bool m_Started;
    protected bool m_Stopped;
    protected bool m_Claimed;
    protected bool m_Done;
    protected int m_Attempts;
    protected HCInteriorsModule m_Owner;
    protected ref HCSettings m_Settings;
    protected ref HCInteriorConfig m_Config;
    protected ref HCInteriorManifest m_Manifest;
    protected ref array<ref HCInteriorSite> m_Sites;
    protected ref HCSearchSupplyProvider m_Provider;
    protected ref array<ref HCSearchSiteVolume> m_Volumes = new array<ref HCSearchSiteVolume>;
    protected ref array<ref HCInteriorSearchContext> m_Contexts = new array<ref HCInteriorSearchContext>;

    override string GetName()
    {
        return "SearchBinding";
    }

    override bool IsEnabled(HCSettings settings)
    {
        return settings && settings.EnableInteriors && settings.EnableSearch;
    }

    override void OnStart(HCSettings settings)
    {
        if (m_Started || m_Stopped || !GetGame() || !GetGame().IsServer() || !IsEnabled(settings) || !HCInteriorRules.SearchAdmitted()) return;
        if (s_Instance && s_Instance != this) return;
        m_Started = true;
        m_Settings = settings;
        m_Provider = new HCSearchSupplyProvider;
        s_Instance = this;
    }

    // Called once by interiors after its synchronous placement pass and readiness.
    // DiagnosticSearchTrial cannot bypass the independent SearchAdmitted marker.
    static void PlacementComplete(HCInteriorsModule owner, HCInteriorConfig config, HCInteriorManifest manifest, array<ref HCInteriorSite> sites)
    {
        if (!GetGame() || !GetGame().IsServer() || !HCInteriorRules.SearchAdmitted()) return;
        if (!s_Instance)
        {
            Print("[HC Search Binding] unavailable: register/start SearchBinding before Interiors; search remains refused");
            return;
        }
        s_Instance.Begin(owner, config, manifest, sites);
    }

    void Begin(HCInteriorsModule owner, HCInteriorConfig config, HCInteriorManifest manifest, array<ref HCInteriorSite> sites)
    {
        if (!m_Started || m_Stopped || m_Claimed || m_Done || !IsEnabled(m_Settings)) return;
        m_Claimed = true;
        m_Owner = owner;
        m_Config = config;
        m_Manifest = manifest;
        m_Sites = sites;
        // First observation is post-start, never inside the placement pass.
        GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(Attempt, RETRY_MS, false);
    }

    bool BuildInputs()
    {
        m_Volumes.Clear();
        m_Contexts.Clear();
        if (!m_Config || !m_Manifest || !m_Config.Candidates || !m_Manifest.Assignments || !m_Sites || m_Manifest.Epoch != m_Config.Epoch) return false;
        int count = m_Manifest.Assignments.Count();
        if (count < 1 || count > 12 || m_Config.Candidates.Count() != count || m_Sites.Count() != count) return false;
        int index;
        foreach (HCInteriorAssignment assignment : m_Manifest.Assignments)
        {
            HCInteriorCandidate candidate = m_Config.Candidates[index];
            if (!candidate || !assignment || assignment.SlotId != candidate.SlotId || assignment.InstanceId != candidate.Id(m_Config.Epoch)) return false;
            HCInteriorSite placed;
            foreach (HCInteriorSite site : m_Sites)
            {
                if (!site || site.SlotId != assignment.SlotId || site.Id != assignment.InstanceId + "_storage_v1") continue;
                if (placed) return false;
                placed = site;
            }
            HCSearchBindingReview review = HCInteriorMeasuredCatalog.SearchBindingReview(candidate, assignment, placed);
            if (!review) return false;
            if (index > 0 && review.Context.SourcePin != m_Contexts[0].SourcePin) return false;
            // Preserve assignment/manifest order, independent of placement order.
            m_Volumes.Insert(review.Volume);
            m_Contexts.Insert(review.Context);
            index++;
        }
        return true;
    }

    void Finish(string reason)
    {
        m_Done = true;
        if (GetGame()) GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).Remove(Attempt);
        if (reason != "") Print("[HC Search Binding] refused: " + reason);
        m_Owner = null;
        m_Config = null;
        m_Manifest = null;
        m_Sites = null;
        m_Volumes.Clear();
        m_Contexts.Clear();
    }

    void Attempt()
    {
        if (m_Done || m_Stopped || !m_Claimed) return;
        if (!GetGame() || !GetGame().IsServer() || !HCInteriorRules.SearchAdmitted() || !IsEnabled(m_Settings) || !m_Owner || m_Owner != HCInteriorsModule.Get())
        {
            Finish("server/admission/settings/interior owner no longer active");
            return;
        }
        if (!BuildInputs())
        {
            Finish("placed/reviewed storage/context identity missing or changed");
            return;
        }
        m_Attempts++;
        HCSearchSupplyPlan plan = m_Provider.Prepare(m_Config.Epoch, SOURCE_ID, m_Contexts[0].SourcePin, m_Volumes, m_Config.InitializeNewEpoch);
        if (m_Done || m_Stopped || !GetGame() || !GetGame().IsServer() || !HCInteriorRules.SearchAdmitted() || !IsEnabled(m_Settings) || !m_Owner || m_Owner != HCInteriorsModule.Get())
        {
            m_Provider.Abandon(plan);
            Finish("owner/admission stopped during supply preparation");
            return;
        }
        if (!plan)
        {
            if (m_Attempts >= MAX_ATTEMPTS)
            {
                m_Provider.Abandon(plan);
                Finish("native supply unavailable after " + m_Attempts.ToString() + " attempts; see [HC Search Supply] reason");
                return;
            }
            GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(Attempt, RETRY_MS, false);
            return;
        }
        if (!m_Owner.BindSearchEconomy(plan.Registry, plan.Manifest, m_Contexts, plan.InitializeNewEpoch))
        {
            m_Provider.Abandon(plan);
            // Open may have written journals. Never retry a refused bind.
            Finish("economy bind refused; preserve journal/source evidence; no retry");
            return;
        }
        Print("[HC Search Binding] finite native supply bound; runtime acceptance PENDING");
        // Economy now owns the registry. Only its Stop may retire a bound plan.
        Finish("");
    }

    override void OnStop()
    {
        m_Stopped = true;
        Finish("");
        m_Settings = null;
        if (s_Instance == this) s_Instance = null;
    }
}
