// Native 1.30.164289: 4_World/Entities/ManBase/PlayerBase.c:6924 MessageStatus.
// Lazy per-house search (contract sections 6 and 8, T5). A search targets a House only when
// (a) the House class is `Search: covered` in the loaded template pack, (b) the cursor hit
// lies inside a template search-site sphere, and (c) the player stands within 2.5 m of that
// site's world centre (the existing 6.25 m^2 pickup check). The first valid search start binds
// the site: ONE bounded GetObjectsAtPosition3D over the site sphere registers and journals the
// stock CE items already present. Nothing is created, split, duplicated or refunded; the only
// move is the server-side TakeToDst in HCSearchSupplyRegistry.Move.
//
// Native snapshot 1.30.164289 (paths relative to the installed native cache):
//   3_Game/Entities/Object.c:873 ModelToWorld; :874 WorldToModel; :287 GetPosition; :305 GetOrientation
//   4_World/Entities/BuildingBase/... Building.c:485 class House : BuildingBase
//   ActionTarget: GetObject, GetParent, GetComponentIndex, GetCursorHitPos
//   3_Game/Global/Game.c:1120 IsServer; GetTickTime
// Whether the cursor on baked building geometry yields a usable ActionTarget is CAP-09 and
// unobserved: if it does not, only placed props are searchable (the pilot path), and that is
// the documented fallback. Runtime acceptance stays pending.
class HCSearchHouseHit
{
    Object Structure;
    string BuildingClass;
    string InstanceId;
    string SiteId;
    int TemplateSiteId;
    int Room;
    vector Center;
    float Radius;
    ref array<string> Groups = new array<string>;
}

// One active house in the least-recently-used list.
class HCSearchHouseSlot
{
    string InstanceId;
    Object Structure;
    float LastUsed;
    ref array<string> Sites = new array<string>;
    ref array<string> Supplies = new array<string>;
}

class HCSearchHouseSession
{
    ref HCInteriorSite Site;
    ActionData Owner;
    PlayerBase Actor;
    string ActorId;
    int Row;
    string InstanceId;
}

class HCSearchHouses
{
    static const float BIND_RADIUS_SQ = 6.25;
    static const float COMMIT_AFTER = 5.5;
    static const float DEADLINE = 15.0;
    static const float EMPTY_RETRY = 60.0;
    static const int MAX_SESSIONS = 12;
    static const int PER_SITE = 3;
    static const int MAX_CLASSES = 1024;
    static const int MAX_GROUP_ITEMS = 1024;
    static const int MAX_SITES = 24;
    static const int MAX_EMPTY = 256;
    static const string SOURCE_ID = "stock-ce-template-houses-v2";
    protected HCSettings m_Settings;
    protected bool m_Started;
    protected bool m_Fault;
    protected bool m_Busy;
    protected bool m_ReadinessReported;
    protected int m_RecycleActiveNext;
    protected int m_RecycleDetachedNext;
    protected float m_WindowStart;
    protected int m_Queries;
    protected ref HCSearchHouseJournal m_Journal;
    protected ref HCSearchSupplyRegistry m_Registry;
    protected ref HCSearchSupplyProvider m_Provider = new HCSearchSupplyProvider;
    protected ref array<ref HCSearchHouseSlot> m_Slots = new array<ref HCSearchHouseSlot>;
    protected ref array<ref HCSearchHouseSlot> m_DetachedSlots = new array<ref HCSearchHouseSlot>;
    protected ref array<ref HCSearchHouseSession> m_Sessions = new array<ref HCSearchHouseSession>;
    protected ref map<string, float> m_Empty = new map<string, float>;
    protected string m_Refusal;

    void Start(HCSettings settings)
    {
        if (m_Started || !settings) return;
        m_Settings = settings;
        m_Started = true;
    }

    bool Started() { return m_Started; }
    int ActiveCount() { return m_Slots.Count(); }
    int SessionCount() { return m_Sessions.Count(); }

    // Called once after template admission. Open/recover only the bounded journal;
    // CE/Hive may not exist yet. Supply registry and entity discovery stay lazy.
    void ReportReadiness()
    {
        if (m_ReadinessReported) return;
        m_ReadinessReported = true;
        int templatesLoaded;
        int serviceStarted;
        int journalHealthy;
        int markerPresent;
        int armed;
        if (HCInteriorTemplates.Loaded()) templatesLoaded = 1;
        if (m_Started) serviceStarted = 1;
        if (HCInteriorRules.SearchOptIn()) markerPresent = 1;
        if (templatesLoaded && m_Started && !m_Fault && m_Settings && m_Settings.EnableInteriors && m_Settings.EnableSearch && HCInteriorRules.SearchAdmitted())
        {
            if (OpenJournal()) journalHealthy = 1;
            if (journalHealthy && markerPresent) armed = 1;
        }
        string report = "[HC Search Houses] armed=" + armed.ToString() + " templates_loaded=" + templatesLoaded.ToString() + " service_started=" + serviceStarted.ToString() + " journal_healthy=" + journalHealthy.ToString();
        report = report + " marker_present=" + markerPresent.ToString() + "; supply=lazy stock CE; runtime acceptance PENDING";
        Print("" + report);
    }

    // No journal or entity is touched here beyond forgetting handles; consumed supplies stay
    // consumed in the journal.
    void Stop()
    {
        foreach (HCSearchHouseSession session : m_Sessions)
        {
            if (session.Site) session.Site.Owner = null;
        }
        m_Sessions.Clear();
        m_Slots.Clear();
        m_DetachedSlots.Clear();
        if (m_Registry) m_Registry.Retire();
        m_Registry = null;
        m_Journal = null;
        m_Settings = null;
        m_Started = false;
    }

    static House HouseOf(ActionTarget target)
    {
        if (!target) return null;
        House building = House.Cast(target.GetObject());
        if (!building) building = House.Cast(target.GetParent());
        return building;
    }

    // The pilot cabinets (HCInteriorCatalog.SearchType) also inherit House. The pilot sees
    // them first, so they are never House targets.
    static bool IsHouseTarget(ActionTarget target)
    {
        House building = HouseOf(target);
        if (!building) return false;
        return !HCInteriorCatalog.SearchType(building.GetType());
    }

    bool Gate(PlayerBase player)
    {
        m_Refusal = HCRefusal.SERVICE;
        if (!m_Started || m_Fault || !m_Settings || !GetGame() || !GetGame().IsServer()) return false;
        bool ready = true;
        if (m_Journal && !m_Journal.Healthy()) ready = false;
        bool alive = player && player.IsAlive() && !player.IsUnconscious() && player.GetIdentity();
        if (!HCInteriorRules.MaySearch(true, m_Settings.EnableInteriors, m_Settings.EnableSearch, HCInteriorRules.SearchAdmitted(), ready, alive, true)) return false;
        m_Refusal = HCRefusal.HANDS;
        if (player.GetHumanInventory().GetEntityInHands()) return false;
        m_Refusal = "";
        return true;
    }

    // The last refusal reason of Gate/Resolve/CanStart/Begin; "" when admitted.
    string Refusal() { return m_Refusal; }

    static string RefusalText(string reason)
    {
        if (reason == HCRefusal.BUSY) return "Someone is already searching here.";
        if (reason == HCRefusal.CAPACITY) return "Too many searches in progress; try again shortly.";
        if (reason == HCRefusal.NO_SITE) return "Nothing to search at this spot.";
        if (reason == HCRefusal.NOTHING) return "Nothing searchable here.";
        if (reason == HCRefusal.HANDS) return "Empty your hands to search.";
        return "Search unavailable: the search service is not ready on this server.";
    }

    // Shared per-player+reason window; class only, never player identity in the RPT.
    void ReportRefusal(PlayerBase player, ActionTarget target)
    {
        HCRefusalReport.RefusalMessage(player, m_Refusal, HouseOf(target), RefusalText(m_Refusal));
    }

    static bool SiteShapeValid(HCInteriorTemplateSearchSite site)
    {
        if (!site || !site.Center || site.Center.Count() != 3 || !site.Groups) return false;
        if (!(site.Radius >= 0.25 && site.Radius <= 8.0)) return false;
        if (site.Groups.Count() < 1 || site.Groups.Count() > 8) return false;
        return HCInteriorRules.SaneVector(Vector(site.Center[0], site.Center[1], site.Center[2]), 1024.0);
    }

    // Pure geometry/class check: no scan, no I/O, no state change.
    HCSearchHouseHit Resolve(PlayerBase player, ActionTarget target)
    {
        if (!Gate(player)) return null;
        m_Refusal = HCRefusal.SERVICE;
        if (!target || !HCInteriorTemplates.Loaded()) return null;
        m_Refusal = HCRefusal.NOTHING;
        House building = HouseOf(target);
        if (!building) return null;
        string cls = building.GetType();
        HCInteriorTemplateClassRow classRow = HCInteriorTemplates.ClassRow(cls);
        if (!classRow || classRow.Search != "covered") return null;
        HCInteriorTemplate layout = HCInteriorTemplates.Template(cls);
        if (!layout || !layout.SearchSites) return null;
        vector orientation = building.GetOrientation();
        // Near-level instances use the full house transforms below.
        if (!HCInteriorRules.TiltAcceptable(orientation, HCInteriorRules.MAX_HOUSE_TILT_DEGREES)) return null;
        vector offset = building.WorldToModel(target.GetCursorHitPos());
        vector standing = player.GetPosition();
        m_Refusal = HCRefusal.NO_SITE;
        HCInteriorTemplateSearchSite best;
        vector bestWorld;
        float bestGap = 1000000.0;
        int examined;
        foreach (HCInteriorTemplateSearchSite site : layout.SearchSites)
        {
            examined++;
            if (examined > MAX_SITES) break;
            if (!SiteShapeValid(site)) continue;
            vector centre = Vector(site.Center[0], site.Center[1], site.Center[2]);
            float gap = vector.DistanceSq(offset, centre);
            if (gap > site.Radius * site.Radius || gap >= bestGap) continue;
            vector world = building.ModelToWorld(centre);
            if (vector.DistanceSq(standing, world) > BIND_RADIUS_SQ) continue;
            best = site;
            bestGap = gap;
            bestWorld = world;
        }
        if (!best) return null;
        m_Refusal = HCRefusal.NOTHING;
        HCSearchHouseHit hit = new HCSearchHouseHit;
        hit.Structure = building;
        hit.BuildingClass = cls;
        hit.InstanceId = cls + "_" + HCInteriorRules.TransformKey(building.GetPosition(), orientation);
        hit.TemplateSiteId = best.Id;
        hit.SiteId = hit.InstanceId + "_site" + best.Id.ToString() + "_v2";
        hit.Room = best.Room;
        hit.Center = bestWorld;
        hit.Radius = best.Radius;
        foreach (string groupId : best.Groups) hit.Groups.Insert(groupId);
        if (!HCSearchRules.TextValid(hit.SiteId, 768)) return null;
        m_Refusal = "";
        return hit;
    }

    HCSearchHouseSession SessionOfSite(string siteId)
    {
        foreach (HCSearchHouseSession session : m_Sessions)
        {
            if (session.Site && session.Site.Id == siteId) return session;
        }
        return null;
    }

    HCSearchHouseSession SessionOf(ActionData data)
    {
        foreach (HCSearchHouseSession session : m_Sessions)
        {
            if (session.Owner == data) return session;
        }
        return null;
    }

    bool OwnsAction(ActionData data)
    {
        return m_Started && data && SessionOf(data) != null;
    }

    int OpenRow(string siteId, PlayerBase player)
    {
        if (!m_Journal || !m_Journal.Healthy()) return -1;
        int index;
        int fallback = -1;
        while (m_Journal && m_Registry && index < m_Journal.Count())
        {
            HCSearchHouseRow row = m_Journal.Row(index);
            if (row && row.SiteId == siteId && row.Phase == 0 && m_Registry && m_Registry.Find(row.SupplyId))
            {
                if (fallback < 0) fallback = index;
                // A changed/out-of-range/full-size first item must not hide a usable
                // later row. Never rebind, replace or consume the skipped supply.
                if (m_Registry.CanTransfer(EntryOf(row), player)) return index;
            }
            index++;
        }
        // Preserve the distinct supply/inventory-unavailable response when rows exist.
        return fallback;
    }

    // A resolved hit still needs a free site and a free session slot.
    bool Admit(PlayerBase player, HCSearchHouseHit hit)
    {
        if (!hit) return false;
        m_Refusal = HCRefusal.BUSY;
        if (SessionOfSite(hit.SiteId)) return false;
        m_Refusal = HCRefusal.CAPACITY;
        if (m_Sessions.Count() >= MAX_SESSIONS) return false;
        m_Refusal = "";
        return true;
    }

    bool CanStart(PlayerBase player, ActionTarget target)
    {
        if (!Admit(player, Resolve(player, target)))
        {
            ReportRefusal(player, target);
            return false;
        }
        // Let Begin report a depleted site as empty. The journal still forbids refill.
        return true;
    }

    // The context contract of section 6: one existing HCInteriorSearchContext per bound site.
    HCInteriorSearchContext BuildContext(HCSearchHouseHit hit)
    {
        string pin = HCInteriorTemplates.SourcePin();
        HCInteriorTemplate layout = HCInteriorTemplates.Template(hit.BuildingClass);
        if (!layout || !HCSearchRules.PinValid(pin) || hit.Groups.Count() < 1 || hit.Groups.Count() > 8) return null;
        HCInteriorSearchContext context = new HCInteriorSearchContext;
        context.InstanceId = hit.InstanceId;
        context.LayoutId = layout.TemplateId;
        context.History = "";
        context.Room = "room-" + hit.Room.ToString();
        context.SourcePin = pin;
        context.EvidencePin = pin;
        // The index lists a per-template Sha256 the reader does not expose; the pack pin is
        // the closest exposed digest (reported as a deviation).
        context.MeasuredRecordSha256 = pin;
        map<string, bool> seen = new map<string, bool>;
        int groupIndex;
        foreach (string groupId : hit.Groups)
        {
            HCInteriorSearchGroup group = HCInteriorTemplates.Group(groupId);
            if (!group || !group.Items || group.Items.Count() < 1 || group.Items.Count() > MAX_GROUP_ITEMS) return null;
            if (groupIndex > 0) context.GroupId = context.GroupId + "+";
            context.GroupId = context.GroupId + groupId;
            groupIndex++;
            foreach (string itemClass : group.Items)
            {
                if (seen.Contains(itemClass)) continue;
                if (!HCSearchRules.TextValid(itemClass, 128) || context.Items.Count() >= MAX_CLASSES) return null;
                seen.Set(itemClass, true);
                context.Items.Insert(itemClass);
            }
        }
        if (!HCSearchRules.TextValid(context.InstanceId, 768) || !HCSearchRules.TextValid(context.LayoutId, 128) || !HCSearchRules.TextValid(context.Room, 128) || !HCSearchRules.TextValid(context.GroupId, 128)) return null;
        return context;
    }

    HCSearchSiteVolume BuildVolume(HCSearchHouseHit hit)
    {
        HCInteriorSearchContext context = BuildContext(hit);
        if (!context || context.Items.Count() < 1) return null;
        HCSearchSiteVolume volume = new HCSearchSiteVolume;
        volume.SiteId = hit.SiteId;
        volume.Center = hit.Center;
        volume.Radius = hit.Radius;
        foreach (string itemClass : context.Items) volume.Classes.Insert(itemClass);
        return volume;
    }

    // At most MaxBindQueriesPerTick scans in one tick (and never more than MaxTickWorkItems).
    bool ChargeQuery()
    {
        float now = GetGame().GetTickTime();
        if (now != m_WindowStart)
        {
            m_WindowStart = now;
            m_Queries = 0;
        }
        int limit = m_Settings.MaxBindQueriesPerTick;
        if (limit > m_Settings.MaxTickWorkItems) limit = m_Settings.MaxTickWorkItems;
        if (m_Queries >= limit) return false;
        m_Queries++;
        return true;
    }

    HCSearchScanBudget NewBudget()
    {
        HCSearchScanBudget budget = new HCSearchScanBudget;
        budget.ObjectsLeft = 4096;
        budget.ContainersLeft = 256;
        budget.SlotsLeft = 4096;
        return budget;
    }

    bool OpenJournal()
    {
        if (m_Journal) return m_Journal.Healthy();
        if (m_Fault) return false;
        string pin = HCInteriorTemplates.SourcePin();
        string worldName = HCBuildIdentity.CanonicalWorld(GetGame().GetWorldName());
        string build = HCBuildIdentity.Canonical();
        HCSearchHouseJournal journal = new HCSearchHouseJournal;
        if (!journal.Open(SOURCE_ID, pin, worldName, build))
        {
            m_Fault = true;
            return false;
        }
        m_Journal = journal;
        return true;
    }

    bool EnsureJournal()
    {
        if (!OpenJournal()) return false;
        if (m_Registry) return true;
        if (m_Fault) return false;
        string pin = HCInteriorTemplates.SourcePin();
        string worldName = HCBuildIdentity.CanonicalWorld(GetGame().GetWorldName());
        string build = HCBuildIdentity.Canonical();
        HCSearchSupplyRegistry registry = new HCSearchSupplyRegistry;
        if (!registry.BindLazySource(SOURCE_ID, pin, worldName, build))
        {
            m_Fault = true;
            Print("[HC Search Houses] lazy registry refused; house search stays refused");
            return false;
        }
        m_Registry = registry;
        return true;
    }

    // Least recently used first, never one with an owning session.
    bool ReleaseIdle()
    {
        int index = m_Slots.Count() - 1;
        while (index >= 0)
        {
            if (!m_Slots[index].Structure && !SlotBusy(m_Slots[index])) return ReleaseAt(index);
            index = index - 1;
        }
        int oldest = -1;
        index = 0;
        while (index < m_Slots.Count())
        {
            if (!SlotBusy(m_Slots[index]) && (oldest < 0 || m_Slots[index].LastUsed < m_Slots[oldest].LastUsed)) oldest = index;
            index++;
        }
        if (oldest < 0) return false;
        return ReleaseAt(oldest);
    }

    bool SlotBusy(HCSearchHouseSlot slot)
    {
        foreach (HCSearchHouseSession session : m_Sessions)
        {
            if (session.InstanceId == slot.InstanceId) return true;
        }
        return false;
    }

    // Forgets this house's registry handles only. The journal keeps every depletion, and a
    // later approach rebinds the same persistent ids.
    bool ReleaseAt(int index)
    {
        HCSearchHouseSlot slot = m_Slots[index];
        foreach (string supplyId : slot.Supplies)
        {
            if (m_Registry && !m_Registry.Forget(supplyId)) return false;
        }
        m_Slots.Remove(index);
        if (slot.Sites.Count() > 0) { m_DetachedSlots.Insert(slot); }
        return true;
    }

    // Native 1.30.164289: 3_Game/Entities/Object.c:287 GetPosition;
    // 3_Game/Global/Game.c:945 GetPlayers is called by the module tick owner.
    bool SpentOutsideRange(HCSearchHouseSlot slot, array<Man> players)
    {
        if (SlotBusy(slot) || slot.Sites.Count() < 1) { return false; }
        foreach (string siteId : slot.Sites)
        {
            if (!m_Journal.SiteSettled(siteId)) { return false; }
        }
        foreach (Man observer : players)
        {
            if (!observer) { continue; }
            if (!slot.Structure) { return false; }
            if (vector.DistanceSq(observer.GetPosition(), slot.Structure.GetPosition()) <= 2500.0) { return false; }
        }
        return true;
    }

    // Detached LRU handles retain only bounded binding metadata until range is safe.
    void RecycleSpentBindings(array<Man> players)
    {
        if (!m_Journal || !m_Journal.Healthy() || m_Busy || !players) { return; }
        int limit = m_Settings.MaxTickWorkItems;
        if (limit > 32) { limit = 32; }
        if (limit < 1) { return; }
        int activeLimit = limit / 2;
        if (activeLimit < 1) { activeLimit = 1; }
        if (activeLimit > m_Slots.Count()) { activeLimit = m_Slots.Count(); }
        int inspected = 0;
        while (inspected < activeLimit && m_Slots.Count() > 0)
        {
            if (m_RecycleActiveNext >= m_Slots.Count()) { m_RecycleActiveNext = 0; }
            if (SpentOutsideRange(m_Slots[m_RecycleActiveNext], players)) { ReleaseAt(m_RecycleActiveNext); }
            else { m_RecycleActiveNext++; }
            inspected++;
        }
        int detachedLimit = limit - inspected;
        if (detachedLimit > m_DetachedSlots.Count()) { detachedLimit = m_DetachedSlots.Count(); }
        inspected = 0;
        while (inspected < detachedLimit && m_DetachedSlots.Count() > 0)
        {
            if (m_RecycleDetachedNext >= m_DetachedSlots.Count()) { m_RecycleDetachedNext = 0; }
            HCSearchHouseSlot detached = m_DetachedSlots[m_RecycleDetachedNext];
            if (SpentOutsideRange(detached, players))
            {
                foreach (string releasedSite : detached.Sites) { m_Journal.ReleaseSite(releasedSite); }
                m_DetachedSlots.Remove(m_RecycleDetachedNext);
            }
            else { m_RecycleDetachedNext++; }
            inspected++;
        }
    }

    HCSearchHouseSlot Touch(HCSearchHouseHit hit)
    {
        float now = GetGame().GetTickTime();
        foreach (HCSearchHouseSlot known : m_Slots)
        {
            if (known.InstanceId != hit.InstanceId) continue;
            known.Structure = hit.Structure;
            known.LastUsed = now;
            return known;
        }
        if (m_Slots.Count() >= m_Settings.HCSearchCap("MaxActiveInteriors", m_Settings.MaxActiveInteriors) && !ReleaseIdle()) return null;
        int detachedIndex = m_DetachedSlots.Count() - 1;
        while (detachedIndex >= 0)
        {
            if (m_DetachedSlots[detachedIndex].InstanceId == hit.InstanceId) { m_DetachedSlots.Remove(detachedIndex); }
            detachedIndex = detachedIndex - 1;
        }
        HCSearchHouseSlot slot = new HCSearchHouseSlot;
        slot.InstanceId = hit.InstanceId;
        slot.Structure = hit.Structure;
        slot.LastUsed = now;
        m_Slots.Insert(slot);
        return slot;
    }

    bool Remembered(string siteId)
    {
        float when;
        if (!m_Empty.Find(siteId, when)) return false;
        return GetGame().GetTickTime() - when < EMPTY_RETRY;
    }

    void Remember(string siteId)
    {
        if (m_Empty.Count() >= MAX_EMPTY) m_Empty.Clear();
        m_Empty.Set(siteId, GetGame().GetTickTime());
    }

    // A site that already has journal rows: re-register the stored persistent ids.
    bool Activate(HCSearchHouseSlot slot, HCSearchHouseHit hit)
    {
        if (Remembered(hit.SiteId)) return true;
        HCSearchSiteVolume volume = BuildVolume(hit);
        if (!volume) return false;
        int index;
        bool complete = true;
        while (index < m_Journal.Count())
        {
            HCSearchHouseRow row = m_Journal.Row(index);
            index++;
            if (!row) { continue; }
            if (row.SiteId != hit.SiteId || row.Phase != 0 || m_Registry.Find(row.SupplyId)) { continue; }
            if (!ChargeQuery()) return false;
            HCSearchScanBudget budget = NewBudget();
            array<EntityAI> found = new array<EntityAI>;
            m_Provider.Collect(volume, budget, row.SupplyId, row.ItemClass, found);
            // Overflow means absence cannot be proven: refuse, never "absent".
            if (budget.Overflow) return false;
            if (found.Count() > 0 && m_Registry.RegisterOwned(found[0], m_Provider.RecordId(row.SupplyId))) slot.Supplies.Insert(row.SupplyId);
            else complete = false;
        }
        // A temporarily absent stored handle is retryable, never a permanent empty
        // activation. Already rebound rows remain usable during this retry window.
        if (complete) slot.Sites.Insert(hit.SiteId);
        else Remember(hit.SiteId);
        return true;
    }

    // First valid start: one bounded scan, then register and journal what CE already placed.
    bool Bind(HCSearchHouseSlot slot, HCSearchHouseHit hit)
    {
        bool newBinding = !m_Journal.SiteBound(hit.SiteId) || m_Journal.BindingReleased(hit.SiteId);
        if (newBinding && m_Journal.SiteCount() >= m_Settings.HCSearchCap("MaxBoundSearchSites", m_Settings.MaxBoundSearchSites))
        {
            Print("[HC Search Houses] site cap reached: " + m_Journal.SiteCount().ToString());
            return false;
        }
        if (!m_Journal.HasCapacity() || Remembered(hit.SiteId)) return false;
        HCSearchSiteVolume volume = BuildVolume(hit);
        if (!volume)
        {
            Remember(hit.SiteId);
            Print("[HC Search Houses] site context invalid for " + hit.SiteId + "; refused");
            return false;
        }
        if (!ChargeQuery()) return false;
        HCSearchScanBudget budget = NewBudget();
        array<EntityAI> found = new array<EntityAI>;
        m_Provider.Collect(volume, budget, "", "", found);
        if (budget.Overflow)
        {
            Remember(hit.SiteId);
            Print("[HC Search Houses] scan incomplete (" + budget.Reason + "); site refused");
            return false;
        }
        int registered;
        foreach (EntityAI candidate : found)
        {
            if (registered >= PER_SITE) break;
            string supplyId = HCSearchSupplyRegistry.PersistentId(candidate);
            if (supplyId == "" || m_Journal.SupplyKnown(supplyId)) continue;
            if (!m_Registry.RegisterOwned(candidate, m_Provider.RecordId(supplyId))) continue;
            if (!m_Journal.Add(hit.SiteId, supplyId, candidate.GetType()))
            {
                m_Registry.Forget(supplyId);
                break;
            }
            slot.Supplies.Insert(supplyId);
            registered++;
        }
        if (registered < 1)
        {
            // Nothing journaled and no cap spent: CE may simply not have populated yet.
            Remember(hit.SiteId);
            return false;
        }
        slot.Sites.Insert(hit.SiteId);
        return true;
    }

    int Prepare(HCSearchHouseSlot slot, HCSearchHouseHit hit, PlayerBase player)
    {
        if (slot.Sites.Find(hit.SiteId) < 0)
        {
            bool ready;
            if (m_Journal.SiteBound(hit.SiteId)) ready = Activate(slot, hit);
            else ready = Bind(slot, hit);
            if (!ready) return -1;
        }
        return OpenRow(hit.SiteId, player);
    }

    HCSearchEntry EntryOf(HCSearchHouseRow row)
    {
        HCSearchEntry entry = new HCSearchEntry;
        entry.SiteId = row.SiteId;
        entry.SupplyId = row.SupplyId;
        entry.ItemClass = row.ItemClass;
        return entry;
    }

    string ActorId(PlayerBase player)
    {
        if (!player || !player.GetIdentity() || player.GetIdentity().GetPlayer() != player) return "";
        string actorId = player.GetIdentity().GetId();
        if (!HCSearchRules.TextValid(actorId, 128)) return "";
        return actorId;
    }

    void Tell(PlayerBase player, string text)
    {
        if (player) player.MessageStatus(text);
    }

    void Begin(ActionData data)
    {
        HCInteriorActionData action = HCInteriorActionData.Cast(data);
        if (!action || !data.m_Player) return;
        HCSearchHouseHit hit = Resolve(data.m_Player, data.m_Target);
        if (!Admit(data.m_Player, hit))
        {
            ReportRefusal(data.m_Player, data.m_Target);
            return;
        }
        string actorId = ActorId(data.m_Player);
        m_Refusal = HCRefusal.SERVICE;
        if (actorId == "" || !EnsureJournal())
        {
            ReportRefusal(data.m_Player, data.m_Target);
            return;
        }
        m_Refusal = "";
        HCSearchHouseSlot slot = Touch(hit);
        if (!slot)
        {
            HCRefusalReport.ActionRefusalMessage(data, HCRefusal.CAPACITY, "Too many buildings are being searched; try again shortly.");
            return;
        }
        int row = Prepare(slot, hit, data.m_Player);
        // Candidate preflight invokes native inventory callbacks, including Stop.
        if (!Gate(data.m_Player) || !m_Journal || !m_Registry)
        {
            HCRefusalReport.ActionRefusalMessage(data, HCRefusal.SUPPLY, "Search unavailable: supply or inventory room changed.");
            return;
        }
        if (row < 0)
        {
            HCRefusalReport.ActionRefusalMessage(data, HCRefusal.NOTHING, "Nothing here to search.");
            return;
        }
        HCSearchHouseRow entry = m_Journal.Row(row);
        if (!m_Registry.CanTransfer(EntryOf(entry), data.m_Player))
        {
            HCRefusalReport.ActionRefusalMessage(data, HCRefusal.SUPPLY, "Search unavailable: supply or inventory room changed.");
            return;
        }
        // Ephemeral wrapper so the action, the noise hook and the session logic stay shared.
        HCInteriorSite site = new HCInteriorSite;
        site.Id = hit.SiteId;
        site.SlotId = row;
        site.Target = hit.Structure;
        site.Point = hit.Center;
        site.Phase = 0;
        site.Owner = data;
        site.StartedAt = GetGame().GetTickTime();
        site.Deadline = site.StartedAt + DEADLINE;
        HCSearchHouseSession session = new HCSearchHouseSession;
        session.Site = site;
        session.Owner = data;
        session.Actor = data.m_Player;
        session.ActorId = actorId;
        session.Row = row;
        session.InstanceId = hit.InstanceId;
        m_Sessions.Insert(session);
        action.Site = site;
    }

    bool SessionValid(ActionData data, HCSearchHouseSession session)
    {
        if (!data || !session || session.Owner != data || session.Actor != data.m_Player || !data.m_Player) return false;
        if (!data.m_Player.GetIdentity() || data.m_Player.GetIdentity().GetPlayer() != data.m_Player) return false;
        return session.ActorId != "" && session.ActorId == data.m_Player.GetIdentity().GetId();
    }

    bool CanContinue(ActionData data)
    {
        HCSearchHouseSession session = SessionOf(data);
        if (!session || !SessionValid(data, session) || !session.Site) return false;
        float now = GetGame().GetTickTime();
        if (now < session.Site.StartedAt || now > session.Site.Deadline) return false;
        // The same cursor target must still be a valid hit inside the same site sphere.
        HCSearchHouseHit hit = Resolve(data.m_Player, data.m_Target);
        return hit && hit.SiteId == session.Site.Id;
    }

    bool StillAuthorized(PlayerBase player, string actorId)
    {
        if (!Gate(player) || !m_Journal || !m_Journal.Healthy()) return false;
        return player.GetIdentity().GetId() == actorId;
    }

    int Finish(int index, string actorId, int phase)
    {
        HCSearchHouseRow row = m_Journal.Row(index);
        if (phase != 2 && phase != 4) phase = 3;
        row.Phase = phase;
        if (!m_Journal.Write(index, "result", actorId, phase))
        {
            row.Phase = 3;
            phase = 3;
        }
        m_Busy = false;
        return phase;
    }

    void Commit(ActionData data)
    {
        if (!GetGame().IsServer()) { return; }
        if (!CanContinue(data))
        {
            if (data) { HCRefusalReport.ActionRefusalMessage(data, HCRefusal.SESSION, "Search stopped; target or session changed."); }
            return;
        }
        HCSearchHouseSession session = SessionOf(data);
        HCInteriorSite site = session.Site;
        if (site.Phase != 0) { return; }
        if (GetGame().GetTickTime() - site.StartedAt < COMMIT_AFTER)
        {
            HCRefusalReport.ActionRefusalMessage(data, HCRefusal.TOO_EARLY, "Search stopped; action completed too early. Please try again.");
            return;
        }
        bool journalReady = m_Journal && m_Journal.Healthy();
        if (m_Busy || !SessionValid(data, session) || !journalReady)
        {
            HCRefusalReport.ActionRefusalMessage(data, HCRefusal.STORAGE, "Search stopped; this storage is unavailable.");
            return;
        }
        int index = session.Row;
        HCSearchHouseRow row = m_Journal.Row(index);
        if (!row || row.Phase != 0 || row.SiteId != site.Id)
        {
            site.Phase = 3;
            HCRefusalReport.ActionRefusalMessage(data, HCRefusal.STORAGE, "Search stopped; this storage is unavailable.");
            return;
        }
        HCSearchEntry entry = EntryOf(row);
        if (!m_Registry.CanTransfer(entry, data.m_Player))
        {
            HCRefusalReport.ActionRefusalMessage(data, HCRefusal.SUPPLY, "Search unavailable: supply, inventory or service changed.");
            return;
        }
        string actorId = session.ActorId;
        // Exclude reentry BEFORE journal I/O or native callbacks, as the pilot does.
        site.Phase = 1;
        m_Busy = true;
        row.Phase = 1;
        int phase = 3;
        if (m_Journal.Write(index, "claim", actorId, 1))
        {
            phase = 4;
            if (StillAuthorized(data.m_Player, actorId) && m_Journal.Write(index, "attempt", actorId, 1) && StillAuthorized(data.m_Player, actorId))
            {
                phase = m_Registry.Transfer(entry, data.m_Player);
            }
            phase = Finish(index, actorId, phase);
        }
        else
        {
            row.Phase = 3;
            m_Busy = false;
        }
        site.Phase = 3;
        if (phase == 2) site.Phase = 2;
        if (phase == 2) Tell(data.m_Player, "Search complete.");
        else HCRefusalReport.ActionRefusalMessage(data, HCRefusal.STORAGE, "Search stopped; this storage is unavailable.");
    }

    void End(ActionData data)
    {
        HCInteriorActionData action = HCInteriorActionData.Cast(data);
        int index = m_Sessions.Count() - 1;
        while (index >= 0)
        {
            if (m_Sessions[index].Owner == data)
            {
                if (m_Sessions[index].Site) m_Sessions[index].Site.Owner = null;
                m_Sessions.Remove(index);
            }
            index = index - 1;
        }
        if (action) action.Site = null;
    }
}
