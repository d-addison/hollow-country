// #144 spec/plan/task: share HCSearchHouses sessions, journal and supply registry.
// The picker port owns lease/body membership; HCValid must recheck that binding,
// never infer membership from proximity. No provider means refusal, never ready.
// No Expansion calls here. Native scripts-1.30.164289 evidence:
// 3_Game/Global/Game.c:1120 IsServer, :914 GetTickTime;
// 3_Game/Entities/Man.c:21 GetIdentity; Object.c:287 GetPosition, :467 GetType, :873 ModelToWorld;
// 3_Game/gameplay.c:368 GetId, :375 GetPlayer, :636 GetGame;
// Object.c:517 IsAlive; 4_World/Entities/ManBase/PlayerBase.c:3925 IsUnconscious;
// 1_Core/proto/EnConvert.c:210 DistanceSq; EnScript.c:380 Count, :394 Find,
// :407 Insert, :463 Remove; EnDebug.c:96 Print; gameplay.c:636 GetGame.
// Uses the original registry's sole TakeToDst path. Integration must first add
// HCSearchActorId/HCSearchActorAuthorized hooks to HCSearchNativeSupply.c (report item 4).
// Existing EnableSearch/EnableInteriors and interior_search.disable are opt-outs.
class auditsearch_PickerAuthority
{
    bool HCValid(PlayerBase actor, string actorId) { return false; }
}

class auditsearch_SupplyRegistry : HCSearchSupplyRegistry
{
    HCSearchHouses HCHouses; // Weak back-reference; the house owner owns this registry.

    override string HCSearchActorId(PlayerBase actor)
    {
        // Human identity continues through the same original validation.
        if (actor && actor.GetIdentity())
        {
            if (actor.GetIdentity().GetPlayer() != actor) return "";
            return actor.GetIdentity().GetId();
        }
        if (!HCHouses) return "";
        return HCHouses.HCPickerActorId(actor);
    }

    override bool HCSearchActorAuthorized(PlayerBase actor, string actorId)
    {
        return actorId != "" && HCSearchActorId(actor) == actorId;
    }
}

modded class HCSearchHouses
{
    protected string m_HCPickerRefusal;
    protected bool m_HCPickerReported;

    void HCRefuse(string reason)
    {
        if (m_HCPickerRefusal == reason) return;
        m_HCPickerRefusal = reason;
        if (reason != "") Print("[HC Search Pickers] refused reason=" + reason + " runtime=PENDING");
    }

    override HCSearchSupplyRegistry HCMakeRegistry()
    {
        auditsearch_SupplyRegistry registry = new auditsearch_SupplyRegistry;
        registry.HCHouses = this;
        return registry;
    }

    bool HCPickerGate(PlayerBase actor, string actorId, auditsearch_PickerAuthority authority)
    {
        m_Refusal = "picker_authority_or_search_unavailable";
        if (!m_Started || m_Fault || !m_Settings || !GetGame() || !GetGame().IsServer()) return false;
        if (!m_Settings.EnableInteriors || !m_Settings.EnableSearch || !HCInteriorRules.SearchAdmitted()) return false;
        if (m_Journal && !m_Journal.Healthy()) return false;
        if (!actor || !actor.IsAlive() || actor.IsUnconscious() || actor.GetIdentity()) return false;
        if (!HCSearchRules.TextValid(actorId, 128) || !authority) return false;
        return authority.HCValid(actor, actorId);
    }

    HCSearchHouseHit HCResolvePicker(PlayerBase actor, House building, int templateSiteId)
    {
        if (!building || !HCInteriorTemplates.Loaded()) return null;
        HCInteriorTemplate layout = HCInteriorTemplates.Template(building.GetType());
        if (!layout || !layout.SearchSites) return null;
        array<ref HCInteriorTemplateSearchSite> sites = layout.SearchSites;
        int inspected;
        foreach (HCInteriorTemplateSearchSite candidate : sites)
        {
            inspected++;
            if (inspected > HCSearchHouses.MAX_SITES) break;
            if (!SiteShapeValid(candidate) || candidate.Id != templateSiteId) continue;
            vector centre = Vector(candidate.Center[0], candidate.Center[1], candidate.Center[2]);
            return HCResolveHousePoint(actor, building, building.ModelToWorld(centre));
        }
        return null;
    }

    // Drop only expired picker locks. Same fixed session cap as actions; no new
    // supply cache, scheduler or persisted grant token. Explicit release is free.
    void HCExpirePickers()
    {
        int index = m_Sessions.Count() - 1;
        float now = GetGame().GetTickTime();
        while (index >= 0)
        {
            HCSearchHouseSession candidate = m_Sessions[index];
            if (candidate.PickerAuthority && candidate.Site)
            {
                if (now < candidate.Site.StartedAt || now > candidate.Site.Deadline) m_Sessions.Remove(index);
            }
            index = index - 1;
        }
    }

    HCSearchHouseSession HCReservePicker(PlayerBase actor, House building, int templateSiteId, string actorId, auditsearch_PickerAuthority authority)
    {
        if (!HCPickerGate(actor, actorId, authority))
        {
            HCRefuse("picker_authority_or_search_unavailable");
            return null;
        }
        // Fixed <=MAX_SESSIONS lock checks and <=HCSearchHouses.MAX_SITES geometry
        // checks. Bind/Activate charge the existing shared SEARCH_BIND consumer;
        // do not pre-spend its forced unit before the actual native scan.
        HCExpirePickers();
        HCSearchHouseHit hit = HCResolvePicker(actor, building, templateSiteId);
        if (!Admit(actor, hit) || m_Busy) return null;
        if (!EnsureJournal()) return null;
        HCSearchHouseSlot slot = Touch(hit);
        if (!slot) return null;
        // Install the reservation BEFORE preflight so the registry identity hook
        // and callbacks see the same lock as players. Roll back metadata only.
        HCInteriorSite site = new HCInteriorSite;
        site.Id = hit.SiteId;
        site.Target = hit.Structure;
        site.Point = hit.Center;
        site.StartedAt = GetGame().GetTickTime();
        site.Deadline = site.StartedAt + HCSearchHouses.DEADLINE;
        HCSearchHouseSession session = new HCSearchHouseSession;
        session.Site = site;
        session.Actor = actor;
        session.ActorId = actorId;
        session.InstanceId = hit.InstanceId;
        session.Row = -1; // Provisional: no journal row selected until Prepare returns.
        session.PickerAuthority = authority;
        m_Sessions.Insert(session);
        int rowIndex = Prepare(slot, hit, actor);
        if (rowIndex < 0 || !HCPickerGate(actor, actorId, authority) || m_Sessions.Find(session) < 0)
        {
            HCReleasePicker(session);
            return null;
        }
        session.Row = rowIndex;
        site.SlotId = rowIndex;
        HCSearchHouseRow row = m_Journal.Row(rowIndex);
        HCSearchEntry transferEntry;
        if (row) { transferEntry = EntryOf(row); }
        if (!row || !m_Registry.CanTransfer(transferEntry, actor) || !HCReservationAuthorized(session))
        {
            HCReleasePicker(session);
            return null;
        }
        HCRefuse("");
        if (!m_HCPickerReported)
        {
            m_HCPickerReported = true;
            Print(HCV2Admission.Line("PickerHouseSearch", true, "picker_house_search", false) + " runtime=PENDING");
        }
        return session;
    }

    // Borrow the exact native item for the picker's existing custody/deposit
    // owner. No manifest copy, no second move, no logical inventory credit.
    EntityAI HCPickerItem(HCSearchHouseSession session)
    {
        if (!session || !session.PickerAuthority || !HCReservationAuthorized(session)) return null;
        if (!m_Journal || !m_Registry || !m_Journal.Healthy()) return null;
        HCSearchHouseRow row = m_Journal.Row(session.Row);
        if (!row || row.SiteId != session.Site.Id) return null;
        HCSearchOwnedSupply supply = m_Registry.Find(row.SupplyId);
        if (!supply) return null;
        return supply.ItemHandle;
    }

    void HCReleasePicker(HCSearchHouseSession session)
    {
        if (!session || !session.PickerAuthority || m_Busy) return;
        int index = m_Sessions.Find(session);
        if (index >= 0) m_Sessions.Remove(index);
    }

    string HCPickerActorId(PlayerBase actor)
    {
        array<ref HCSearchHouseSession> sessions = m_Sessions;
        foreach (HCSearchHouseSession session : sessions)
        {
            if (session.Actor != actor || !session.PickerAuthority || !session.Site) continue;
            if (!HCReservationAuthorized(session)) return "";
            return session.ActorId;
        }
        return "";
    }

    override bool HCReservationAuthorized(HCSearchHouseSession session)
    {
        if (!session || !session.PickerAuthority) return super.HCReservationAuthorized(session);
        if (m_Sessions.Find(session) < 0 || !session.Site) return false;
        if (!HCPickerGate(session.Actor, session.ActorId, session.PickerAuthority)) return false;
        float now = GetGame().GetTickTime();
        if (now < session.Site.StartedAt || now > session.Site.Deadline) return false;
        float gap = vector.DistanceSq(session.Actor.GetPosition(), session.Site.Point);
        return gap >= 0.0 && gap <= HCSearchHouses.BIND_RADIUS_SQ;
    }
}
