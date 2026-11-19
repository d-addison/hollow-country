// LC-T304/306, #90/#92/#119. Native evidence: scripts-1.30.164289/
// 1_Core/proto/EnScript.c:380,385,389,394,407 (arrays),
// 1_Core/proto/EnString.c:199,240 (Length/IndexOf),
// 1_Core/proto/EnConvert.c:30 (int.ToString), 1_Core/proto/EnDebug.c:96 (Print),
// 3_Game/Entities/Man.c:21 (GetIdentity), 3_Game/gameplay.c:368 (identity GetId).
// All clock/place/fact operations
// delegate to installed project helpers. No live coordinates in lead DTOs.
// 1_Core/proto/EnString.c:113 Substring.
// Scene notes and news use this same deterministic place-level wording.
class HCLeadPolicy
{
    protected static ref HCWorldData s_Places;

    // Token-safe solo ownership for native (base64) identity IDs. Preserve the
    // HCWorldLimits.Token alphabet, including '/', and map other characters.
    // Native scripts-1.30.164289/1_Core/proto/EnString.c:113 Substring,
    // :199 Length, :240 IndexOf. No native identity value is modified.
    static string SoloGroup(string identityId)
    {
        string alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-.:/";
        string key = "solo:";
        int keyIndex;
        while (keyIndex < identityId.Length())
        {
            string character = identityId.Substring(keyIndex, 1);
            if (alphabet.IndexOf(character) < 0) { character = "_"; }
            key = key + character;
            keyIndex = keyIndex + 1;
        }
        return key;
    }

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
        if (factKind == "dead_drop_supplied" || factKind == "holdout_occupied") { return "CACHE"; }
        if (factKind == "faction_clash" || factKind == "holdout_alert" || factKind.IndexOf("_pushed_") > 0) { return "DANGER"; }
        if (factKind == "picker_searched" || factKind == "holdout_traces" || factKind == "holdout_dormant") { return "PLACE"; }
        if (factKind == "morse_lead" || factKind.IndexOf("_survivors_") > 0) { return "EVENT"; }
        if (factKind == "camp_probe_warning" || factKind == "camp_neighbours_lost" || factKind == "camp_probe_signs") { return "DANGER"; }
        if (factKind.IndexOf("camp_") == 0) { return "PLACE"; }
        if (factKind == "PLACE" || factKind == "party_passed" || factKind == "ABANDONED" || factKind == "abandoned") { return "PLACE"; }
        if (factKind == "CACHE" || factKind == "cache_found" || factKind == "cache_stocked") { return "CACHE"; }
        if (factKind == "EVENT" || factKind == "herd_moving" || factKind == "herd_passed" || factKind == "scene_started") { return "EVENT"; }
        if (factKind == "DANGER" || factKind == "SHOTS_HEARD" || factKind == "shots_heard" || factKind == "holdout_raided" || factKind == "RAIDED" || factKind == "BODY_FOUND" || factKind == "STOLEN" || factKind == "CACHE_EMPTIED") { return "DANGER"; }
        return "";
    }

    // Preserve recognition of vanilla papers written before this wording pass.
    static string LegacyText(HCWorldLead lead)
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

    static string FactionName(string id)
    {
        if (id == "locals") { return "Locals"; }
        if (id == "volunteers") { return "Volunteers"; }
        if (id == "scavengers") { return "Scavengers"; }
        if (id == "raiders") { return "Raiders"; }
        if (id == "travellers") { return "Travellers"; }
        return "An unknown group";
    }

    static string Text(HCWorldLead lead)
    {
        if (!Valid(lead)) { return ""; }
        string placeName = Place(lead.TargetPlaceId).Name;
        string report;
        string kind = lead.TextId;
        if (kind == "holdout_occupied") { report = "Smoke was seen again from a house near " + placeName + "."; }
        if (kind == "holdout_alert") { report = "Armed occupants were on alert near " + placeName + "."; }
        if (kind == "holdout_dormant") { report = "A previously occupied house fell quiet near " + placeName + "."; }
        if (kind == "holdout_traces") { report = "Traces of a temporary holdout were found near " + placeName + "."; }
        if (kind == "STOLEN" || kind == "CACHE_EMPTIED") { report = "Crates were emptied near " + placeName + "."; }
        if (kind == "picker_searched") { report = "Scavengers were seen picking through houses near " + placeName + "."; }
        if (kind == "dead_drop_supplied") { report = "A drop was restocked near " + placeName + "."; }
        if (kind == "cache_found" || kind == "cache_stocked") { report = "Supplies were reported in a cache near " + placeName + "."; }
        if (kind == "faction_clash") { report = "Two groups fought over " + placeName + "."; }
        if (kind == "holdout_raided" || kind == "RAIDED") { report = "A holdout was raided near " + placeName + "."; }
        if (kind == "BODY_FOUND") { report = "A body and a discarded message were found near " + placeName + "."; }
        if (kind == "ABANDONED" || kind == "abandoned") { report = "A camp was abandoned near " + placeName + "."; }
        if (kind == "scene_started") { report = "Someone left signs of a recent stop near " + placeName + "."; }
        if (kind == "morse_lead") { report = "A coded radio message mentioned an earlier event near " + placeName + "."; }
        if (kind == "camp_settlement") { report = "A camp was growing into a settlement near " + placeName + "."; }
        if (kind == "camp_visitor") { report = "Travellers visited a camp near " + placeName + "."; }
        if (kind == "camp_neighbours_lost") { report = "A camp lost contact with its neighbours near " + placeName + "."; }
        if (kind == "camp_probe_retreat") { report = "Strangers withdrew from a camp near " + placeName + "."; }
        if (kind == "camp_probe_signs") { report = "Signs of strangers watching a camp were found near " + placeName + "."; }
        if (kind == "camp_probe_warning") { report = "A camp received a warning from strangers near " + placeName + "."; }
        if (report == "" && kind.IndexOf("camp_") == 0) { report = "Activity was reported around a camp near " + placeName + "."; }
        int pushed = kind.IndexOf("_pushed_");
        if (pushed > 0)
        {
            string winner = kind.Substring(0, pushed);
            int loserAt = pushed + 8;
            string loser = kind.Substring(loserAt, kind.Length() - loserAt);
            report = FactionName(winner) + " pushed " + FactionName(loser) + " out of " + placeName + ".";
        }
        int survivors = kind.IndexOf("_survivors_");
        if (survivors > 0)
        {
            string faction = kind.Substring(0, survivors);
            int countAt = survivors + 11;
            string tally = kind.Substring(countAt, kind.Length() - countAt);
            int ofAt = tally.IndexOf("_of_");
            report = "Survivors from " + FactionName(faction) + " were reported near " + placeName + ".";
            if (ofAt > 0)
            {
                string remaining = tally.Substring(0, ofAt);
                int totalAt = ofAt + 4;
                string total = tally.Substring(totalAt, tally.Length() - totalAt);
                report = FactionName(faction) + " reported " + remaining + " of " + total + " people surviving near " + placeName + ".";
            }
        }
        if (report == "") { return LegacyText(lead); }
        return report + " This is old news; things may have changed.";
    }

    static bool PrepareSceneLead(HCWorldLead lead, string sceneId, string placeId, int now)
    {
        if (!lead || now < 1) { return false; }
        if (Valid(lead) && lead.Expires > now) { return true; }
        if (!KnownPlace(placeId)) { return false; }
        lead.Kind = "PLACE";
        lead.TargetPlaceId = placeId;
        lead.TextId = "scene_started";
        lead.Source = "scene";
        lead.Id = sceneId;
        lead.Expires = now + 259200;
        return true;
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

// Preserve idempotent success for existing note/news callers; radio only
// displays a newly retained receipt. The existing 5/group, 64/store cap owns it.
enum HCLeadReceiveResult
{
    REFUSED = 0,
    HELD = 1,
    RETAINED = 2
}

class HCLeadModule : HCModule
{
    protected static HCLeadModule s_Instance;
    protected ref HCLeadStore m_Store;
    protected ref array<ref HCWorldLead> m_Catalog = new array<ref HCWorldLead>();
    protected ref array<ref HCWorldFact> m_Facts = new array<ref HCWorldFact>();
    protected int m_Cursor;
    protected int m_SelectionCursor;
    protected int m_ShelterCursor;
    protected float m_Elapsed = 60;
    protected float m_LogElapsed = 600;
    protected string m_LastSummary;
    protected bool m_AdmissionPrinted;
    protected ref HCOperationalStatus m_Status = new HCOperationalStatus;

    static HCLeadModule Get()
    {
        if (s_Instance && s_Instance.m_Store && s_Instance.m_Store.Healthy()) { return s_Instance; }
        return null;
    }

    override string GetName() { return "Leads"; }
    override bool IsEnabled(HCSettings settings) { return settings && settings.EnableLeads; }
    override HCOperationalStatus HCGetOperationalStatus() { return m_Status; }
    // HC-1 reads this status; the store's own Fault() already names the failing step once.
    void HCStartRefused(string reason)
    {
        m_Status.HCPublish("refused", reason);
        Print("[HC Leads] start refused reason=" + reason);
    }
    override void OnStart(HCSettings settings)
    {
        if (!IsEnabled(settings) || s_Instance) { return; }
        if (!m_AdmissionPrinted)
        {
            Print(HCV2Admission.Line("Leads", true, "EXP-S2", HCV2Gates.Qualified("EXP-S2")));
            m_AdmissionPrinted = true;
        }
        m_Store = new HCLeadStore;
        if (!m_Store.Open())
        {
            HCStartRefused("lead_store_unavailable");
            return;
        }
        s_Instance = this;
        m_Status.HCPublish("ready", "lead_store_open");
    }

    override void OnTick(float deltaTime)
    {
        if (!Get() || deltaTime <= 0) { return; }
        m_Elapsed += deltaTime;
        m_LogElapsed += deltaTime;
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
        // LC-T306: refresh one shelter lead slot per minute from the lead catalog.
        int shelters = HCShelterCatalog.Count();
        if (shelters > 0)
        {
            if (m_ShelterCursor >= shelters) { m_ShelterCursor = 0; }
            HCWorldLead slotLead = Select();
            if (slotLead) { HCShelterCatalog.SetLeadSlot(m_ShelterCursor, HCLeadPolicy.Text(slotLead)); }
            m_ShelterCursor++;
        }
        if (changed && !m_Store.Save()) { return; }
        array<string> groups = new array<string>();
        foreach (HCWorldLead active : m_Store.Data.Leads)
        {
            if (groups.Find(active.GroupId) < 0) { groups.Insert(active.GroupId); }
        }
        string summary = "[HollowCountry] V2 leads active=" + m_Store.Data.Leads.Count().ToString() + " groups=" + groups.Count().ToString();
        if (summary != m_LastSummary || m_LogElapsed >= 600)
        {
            Print("" + summary);
            m_LastSummary = summary;
            m_LogElapsed = 0;
        }
    }

    override void OnStop()
    {
        s_Instance = null;
        m_Status.HCStop();
    }

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

    // Newest eligible fact, retaining the same 30-minute delay as other leads.
    HCWorldLead Latest()
    {
        HCWorldModule world = HCWorldModule.Get();
        if (!Get() || !world) { return null; }
        world.GetRecentFacts(604800, m_Facts);
        int checked;
        foreach (HCWorldFact fact : m_Facts)
        {
            checked = checked + 1;
            if (checked > 32) { break; }
            HCWorldLead candidate = new HCWorldLead;
            if (!HCLeadPolicy.Build(fact, candidate, fact.PlaceId, HCLeadPolicy.Kind(fact.Kind), HCWorldClock.UTC())) { continue; }
            if (!HCLeadPolicy.Valid(candidate)) { continue; }
            candidate.Id = fact.Kind + "-" + fact.PlaceId + "-" + fact.At.ToString();
            candidate.Source = "world";
            return candidate;
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
        return ReceiveResult(offer, groupId, source) != HCLeadReceiveResult.REFUSED;
    }

    int ReceiveResult(HCWorldLead offer, string groupId, string source)
    {
        if (!Get() || !HCLeadPolicy.Valid(offer) || offer.Expires <= HCWorldClock.UTC() || !HCWorldLimits.Token(groupId) || !HCWorldLimits.Token(source)) { return HCLeadReceiveResult.REFUSED; }
        int count;
        foreach (HCWorldLead prior : m_Store.Data.Leads)
        {
            if (prior.GroupId != groupId) { continue; }
            // Review P1: HCLeadStore.Valid counts expired rows until the 60 s prune,
            // so the per-group cap counts them too or Save would fault the store.
            count++;
            if (prior.Expires <= HCWorldClock.UTC()) { continue; }
            if (prior.TargetPlaceId == offer.TargetPlaceId && prior.TextId == offer.TextId) { return HCLeadReceiveResult.HELD; }
        }
        if (count >= 5 || m_Store.Data.Leads.Count() >= 64) { return HCLeadReceiveResult.REFUSED; }
        HCWorldLead received = HCLeadPolicy.Copy(offer);
        received.Id = m_Store.NextId("lead");
        received.GroupId = groupId;
        received.Source = source;
        m_Store.Data.Leads.Insert(received);
        if (!m_Store.Save()) { return HCLeadReceiveResult.REFUSED; }
        return HCLeadReceiveResult.RETAINED;
    }

    void ReceivePlayer(HCWorldLead offer, PlayerBase player, string source)
    {
        if (!player || !player.IsAlive() || !player.GetIdentity()) { return; }
        HCGroupService groups = HCGroupService.Get();
        string groupId = HCLeadPolicy.SoloGroup(player.GetIdentity().GetId());
        if (groups) { groupId = groups.HCLeadGroup(player); }
        if (groupId == "") { return; }
        if (Receive(offer, groupId, source))
        {
            Print("[HollowCountry] V2 lead received source=" + source + " place=" + offer.TargetPlaceId);
        }
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
// group-owned files. Solo keys sanitize the server identity for lead storage.
modded class HCGroupService
{
    string HCLeadGroup(PlayerBase player)
    {
        if (!m_Healthy || !m_State || !player || !player.GetIdentity()) { return ""; }
        HCGroupRecord group = HCGroupRules.FindGroup(m_State, player.GetIdentity().GetId());
        if (!group) { return HCLeadPolicy.SoloGroup(player.GetIdentity().GetId()); }
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
