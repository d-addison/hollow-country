// LC-T304/306, #90/#92/#119. Native evidence: scripts-1.30.164289/
// 1_Core/proto/EnScript.c:380,385,389,394,407 (arrays),
// 1_Core/proto/EnString.c:199,240 (Length/IndexOf),
// 1_Core/proto/EnConvert.c:30 (int.ToString), 1_Core/proto/EnDebug.c:96 (Print),
// 3_Game/Entities/Man.c:21 (GetIdentity), 3_Game/gameplay.c:368 (identity GetId).
// All clock/place/fact operations
// delegate to installed project helpers. No live coordinates in lead DTOs.
// Integration seams for the lead: HCAskForNews and HCShelterCatalog do not
// exist in this base checkout. Their owners can call Get().Rumour(pos) for the
// news body / SetLeadSlot text, and HCNoteLedger.Get().Create(sceneId, reviewed
// anchor, Get().Select()) for a scene/shelter note. No unknown types are stubbed.
class HCLeadPolicy
{
    protected static ref HCWorldData s_Places;

    static HCWorldPlace Place(string id)
    {
        if (!s_Places) { s_Places = HCWorldData.Fresh(1); }
        return s_Places.Place(id);
    }

    static bool Build(HCWorldFact fact, HCWorldLead lead, string placeId, string kind, int now)
    {
        if (!fact || !lead || placeId == "" || fact.PlaceId != placeId || fact.At < 1 || now - fact.At < 1800 || fact.Expires <= now) { return false; }
        if (kind != "PLACE" && kind != "CACHE" && kind != "EVENT" && kind != "DANGER") { return false; }
        lead.Kind = kind;
        lead.TargetPlaceId = placeId;
        lead.Expires = fact.Expires;
        if (lead.Expires > now + 259200) { lead.Expires = now + 259200; }
        lead.TextId = fact.Kind;
        return true;
    }

    static bool KnownPlace(string id)
    {
        // Reuse the world's authored named-place catalog, never coordinate input.
        return Place(id) != null;
    }

    static bool Valid(HCWorldLead row)
    {
        if (!row || !KnownPlace(row.TargetPlaceId) || !HCWorldLimits.Token(row.TextId) || row.Expires < 1) { return false; }
        return row.Kind == "PLACE" || row.Kind == "CACHE" || row.Kind == "EVENT" || row.Kind == "DANGER";
    }

    static string Kind(string factKind)
    {
        if (factKind == "PLACE" || factKind == "party_passed" || factKind == "ABANDONED" || factKind == "abandoned") { return "PLACE"; }
        if (factKind == "CACHE" || factKind == "cache_found" || factKind == "cache_stocked") { return "CACHE"; }
        if (factKind == "EVENT" || factKind == "herd_moving" || factKind == "herd_passed" || factKind == "scene_started") { return "EVENT"; }
        if (factKind == "DANGER" || factKind == "SHOTS_HEARD" || factKind == "shots_heard" || factKind == "holdout_raided" || factKind == "RAIDED" || factKind == "BODY_FOUND" || factKind == "STOLEN" || factKind == "CACHE_EMPTIED") { return "DANGER"; }
        return "";
    }

    static string Text(HCWorldLead lead)
    {
        if (!Valid(lead)) { return ""; }
        string placeName = Place(lead.TargetPlaceId).Name;
        string report = "People passed through " + placeName + " some time ago.";
        if (lead.Kind == "CACHE") { report = "There was word of a cache around " + placeName + " earlier. It may already be empty."; }
        if (lead.Kind == "EVENT") { report = "Something was happening around " + placeName + " earlier."; }
        if (lead.Kind == "DANGER") { report = "Earlier reports warned of trouble around " + placeName + "."; }
        if (lead.TextId == "SHOTS_HEARD" || lead.TextId == "shots_heard") { report = "Shots were heard near " + placeName + " some time ago."; }
        if (lead.TextId == "herd_moving" || lead.TextId == "herd_passed") { report = "A herd was reported passing the area around " + placeName + " earlier."; }
        return report + " This is old news; things may have changed.";
    }

    static HCWorldLead Copy(HCWorldLead row)
    {
        HCWorldLead copy = new HCWorldLead;
        copy.Id = row.Id;
        copy.Kind = row.Kind;
        copy.TargetPlaceId = row.TargetPlaceId;
        copy.Source = row.Source;
        copy.GroupId = row.GroupId;
        copy.Expires = row.Expires;
        copy.TextId = row.TextId;
        return copy;
    }
}

class HCLeadModule : HCModule
{
    protected static HCLeadModule s_Instance;
    protected ref HCLeadStore m_Store;
    protected ref array<ref HCWorldLead> m_Catalog = new array<ref HCWorldLead>();
    protected ref array<ref HCWorldFact> m_Facts = new array<ref HCWorldFact>();
    protected int m_Cursor;
    protected int m_SelectionCursor;
    protected float m_Elapsed = 60;
    protected bool m_AdmissionPrinted;

    static HCLeadModule Get()
    {
        if (s_Instance && s_Instance.m_Store && s_Instance.m_Store.Healthy()) { return s_Instance; }
        return null;
    }

    override string GetName() { return "Leads"; }
    override bool IsEnabled(HCSettings settings) { return settings && settings.EnableLeads; }
    override void OnStart(HCSettings settings)
    {
        if (!IsEnabled(settings) || s_Instance) { return; }
        if (!m_AdmissionPrinted)
        {
            Print(HCV2Admission.Line("Leads", true, "EXP-S2", HCV2Gates.Qualified("EXP-S2")));
            m_AdmissionPrinted = true;
        }
        m_Store = new HCLeadStore;
        if (!m_Store.Open()) { return; }
        s_Instance = this;
    }

    override void OnTick(float deltaTime)
    {
        if (!Get() || deltaTime <= 0) { return; }
        m_Elapsed += deltaTime;
        if (m_Elapsed < 60) { return; }
        m_Elapsed = 0;
        int now = HCWorldClock.UTC();
        bool changed;
        for (int expiredIndex = m_Store.Data.Leads.Count() - 1; expiredIndex >= 0; expiredIndex--)
        {
            if (m_Store.Data.Leads[expiredIndex].Expires <= now)
            {
                m_Store.Data.Leads.RemoveOrdered(expiredIndex);
                changed = true;
            }
        }
        for (int catalogIndex = m_Catalog.Count() - 1; catalogIndex >= 0; catalogIndex--)
        {
            if (m_Catalog[catalogIndex].Expires <= now) { m_Catalog.RemoveOrdered(catalogIndex); }
        }
        HCWorldModule world = HCWorldModule.Get();
        if (world)
        {
            world.GetRecentFacts(604800, m_Facts);
            int work = m_Facts.Count();
            if (work > 32) { work = 32; }
            for (int stepIndex = 0; stepIndex < work; stepIndex++)
            {
                if (m_Cursor >= m_Facts.Count()) { m_Cursor = 0; }
                HCWorldFact fact = m_Facts[m_Cursor++];
                if (!HCLeadPolicy.KnownPlace(fact.PlaceId)) { continue; }
                HCWorldLead candidate = new HCWorldLead;
                if (!HCLeadPolicy.Build(fact, candidate, fact.PlaceId, HCLeadPolicy.Kind(fact.Kind), now)) { continue; }
                candidate.Id = fact.Kind + "-" + fact.PlaceId + "-" + fact.At.ToString();
                candidate.Source = "world";
                bool duplicate = false;
                foreach (HCWorldLead existing : m_Catalog)
                {
                    if (existing.Id == candidate.Id) { duplicate = true; break; }
                }
                if (!duplicate && m_Catalog.Count() < 64) { m_Catalog.Insert(candidate); }
            }
        }
        if (changed && !m_Store.Save()) { return; }
        array<string> groups = new array<string>();
        foreach (HCWorldLead active : m_Store.Data.Leads)
        {
            if (groups.Find(active.GroupId) < 0) { groups.Insert(active.GroupId); }
        }
        Print("[HollowCountry] V2 leads active=" + m_Store.Data.Leads.Count().ToString() + " groups=" + groups.Count().ToString());
    }

    override void OnStop() { s_Instance = null; }

    HCWorldLead Select()
    {
        int now = HCWorldClock.UTC();
        for (int selectIndex = 0; selectIndex < m_Catalog.Count(); selectIndex++)
        {
            if (m_SelectionCursor >= m_Catalog.Count()) { m_SelectionCursor = 0; }
            HCWorldLead candidate = m_Catalog[m_SelectionCursor++];
            if (candidate.Expires > now) { return HCLeadPolicy.Copy(candidate); }
        }
        return null;
    }

    // Filled by the talk adapter; position is intentionally unused in selection.
    string Rumour(vector pos)
    {
        HCWorldLead lead = Select();
        if (!lead) { return ""; }
        return HCLeadPolicy.Text(lead);
    }

    bool Receive(HCWorldLead offer, string groupId, string source)
    {
        if (!Get() || !HCLeadPolicy.Valid(offer) || offer.Expires <= HCWorldClock.UTC() || !HCWorldLimits.Token(groupId) || !HCWorldLimits.Token(source)) { return false; }
        int count;
        foreach (HCWorldLead prior : m_Store.Data.Leads)
        {
            if (prior.GroupId != groupId) { continue; }
            // Review P1: HCLeadStore.Valid counts expired rows until the 60 s prune,
            // so the per-group cap counts them too or Save would fault the store.
            count++;
            if (prior.Expires <= HCWorldClock.UTC()) { continue; }
            if (prior.TargetPlaceId == offer.TargetPlaceId && prior.TextId == offer.TextId) { return true; }
        }
        if (count >= 5 || m_Store.Data.Leads.Count() >= 64) { return false; }
        HCWorldLead received = HCLeadPolicy.Copy(offer);
        received.Id = m_Store.NextId("lead");
        received.GroupId = groupId;
        received.Source = source;
        m_Store.Data.Leads.Insert(received);
        return m_Store.Save();
    }

    void ReceivePlayer(HCWorldLead offer, PlayerBase player, string source)
    {
        HCGroupService groups = HCGroupService.Get();
        if (!groups) { return; }
        string groupId = groups.HCLeadGroup(player);
        if (groupId != "") { Receive(offer, groupId, source); }
    }

    void GroupLeads(string groupId, out array<ref HCWorldLead> output)
    {
        output = new array<ref HCWorldLead>();
        if (!Get()) { return; }
        foreach (HCWorldLead row : m_Store.Data.Leads)
        {
            if (row.GroupId == groupId && row.Expires > HCWorldClock.UTC()) { output.Insert(HCLeadPolicy.Copy(row)); }
        }
    }
}

// Resolve membership from authoritative state at delivery time, without editing
// group-owned files or persisting player identities in the lead ledger.
modded class HCGroupService
{
    string HCLeadGroup(PlayerBase player)
    {
        if (!m_Healthy || !player || !player.GetIdentity()) { return ""; }
        HCGroupRecord group = HCGroupRules.FindGroup(m_State, player.GetIdentity().GetId());
        if (!group) { return ""; }
        return "group-" + group.Id.ToString();
    }
}

modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        Register(new HCLeadModule);
        Register(new HCRadioChatter);
        Register(new HCNoteLedger);
        Register(new HCBodyStories);
    }
}
