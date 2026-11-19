// W5 #122, READ ONLY. Native scripts-1.30.164289 evidence:
// 3_Game/Global/Game.c:945 GetPlayers (once per capture, cached for leads);
// Entities/Object.c:287 GetPosition, :517 IsAlive; Entities/Man.c:21 GetIdentity;
// 3_Game/gameplay.c:362,368 PlayerIdentityBase.GetName/GetId, :636 GetGame;
// 1_Core/proto/EnScript.c:94 Cast, :380,385,394,407 Count/Clear/Find/Insert;
// EnConvert.c:30 int.ToString. All other APIs below are existing HC public seams.
// Each Describe emits <=64 points. Players inspect <=64 roster slots with a
// cursor. Holdouts <=24 clones; drops <=8 handles; shelters <=6 catalog rows;
// events ONE runtime clone (existing store ceiling 4MiB) + <=32 rows/8
// two-vertex objective lines;
// leads <=8 cached players (cursor), <=8*64 store rows + <=64 result rows;
// materializer candidates <=36 ledger rows. No spatial queries or entity scans.
// Missing public read paths (pickers, camps, scenes, pins, active proposal queue)
// are documented in docs/DEBUG_MAP.md, never inferred from catalogs/profile files.
class HCDebugPlayersContributor : HCDebugContributor
{
    protected ref array<Man> m_Roster = new array<Man>;
    ref array<Man> Players = new array<Man>;
    protected int m_Cursor;

    override void HCDescribe(HCDebugSnapshot snapshot)
    {
        m_Roster.Clear();
        Players.Clear();
        GetGame().GetPlayers(m_Roster);
        int work = m_Roster.Count();
        if (work > 64) { work = 64; }
        for (int index = 0; index < work; index++)
        {
            if (m_Cursor >= m_Roster.Count()) { m_Cursor = 0; }
            int slot = m_Cursor;
            m_Cursor++;
            Man player = m_Roster[slot];
            if (!player || !player.IsAlive() || !player.GetIdentity()) { continue; }
            Players.Insert(player);
            snapshot.AddPoint("players", "roster-" + slot.ToString(), player.GetPosition(), player.GetIdentity().GetName(), "Live server player; id is a transient roster slot");
        }
        m_Roster.Clear();
    }
}

class HCDebugHoldoutsContributor : HCDebugContributor
{
    override void HCDescribe(HCDebugSnapshot snapshot)
    {
        HCHoldouts holdouts = HCHoldouts.Get();
        if (!holdouts) { return; }
        int work = holdouts.Count();
        if (work > 24) { work = 24; }
        for (int index = 0; index < work; index++)
        {
            HCWorldHoldout row = holdouts.Snapshot(index);
            if (!row) { continue; }
            snapshot.AddPoint("holdouts", row.Id, row.HousePos, row.PlaceId, row.State + " / " + row.Routine + " occupants=" + row.Occupants.ToString());
        }
    }
}

class HCDebugDeadDropsContributor : HCDebugContributor
{
    override void HCDescribe(HCDebugSnapshot snapshot)
    {
        HCDeadDrops drops = HCDeadDrops.Get();
        if (!drops) { return; }
        int work = drops.Count();
        if (work > 8) { work = 8; }
        for (int index = 0; index < work; index++)
        {
            EntityAI cache = drops.Cache(index);
            if (!cache) { continue; }
            snapshot.AddPoint("dead_drops", drops.CacheId(index), cache.GetPosition(), drops.CacheId(index), "Live bound cache; no inventory content exported");
        }
    }
}

class HCDebugSheltersContributor : HCDebugContributor
{
    override void HCDescribe(HCDebugSnapshot snapshot)
    {
        int work = HCShelterCatalog.Count();
        if (work > 64) { work = 64; }
        for (int index = 0; index < work; index++)
        {
            HCShelterEntry shelter = HCShelterCatalog.Get(index);
            if (!shelter) { continue; }
            string state = "Catalog site; not placed. ";
            if (shelter.Placed) { state = "Catalog reports placed. "; }
            snapshot.AddPoint("shelters", shelter.Name, shelter.Position, shelter.Name, state + shelter.History);
        }
    }
}

class HCDebugEventsContributor : HCDebugContributor
{
    override void HCDescribe(HCDebugSnapshot snapshot)
    {
        HCEventModule events = HCEventModule.Get();
        if (!events || !events.Runtime()) { return; }
        HCEventRuntimeState state = events.Runtime().Snapshot();
        if (!state || !state.Runs) { return; }
        int work = state.Runs.Count();
        if (work > 32) { work = 32; }
        for (int index = 0; index < work; index++)
        {
            HCEventRun run = state.Runs[index];
            if (!run || !run.Objective || run.Phase == HCEventRunPhase.CLOSED) { continue; }
            HCEventMission objective = run.Objective;
            string id = run.EventId.ToString();
            snapshot.AddPoint("events", id, objective.Source, objective.Id, "Event phase=" + run.Phase.ToString() + " family=" + objective.Family.ToString());
            if (objective.Family == HCEventFamily.DELIVERY)
            {
                snapshot.AddPoint("events", id + "-destination", objective.Destination, objective.Id + " destination", "Delivery objective; line is not a surveyed path");
                if (index < 8)
                {
                    array<vector> objectiveLine = new array<vector>;
                    objectiveLine.Insert(objective.Source);
                    objectiveLine.Insert(objective.Destination);
                    snapshot.AddRoute("events", id, objectiveLine, "Delivery objective (straight line)");
                }
            }
        }
    }
}

class HCDebugLeadsContributor : HCDebugContributor
{
    protected ref HCDebugPlayersContributor m_Players;
    protected int m_Cursor;

    void HCDebugLeadsContributor(HCDebugPlayersContributor players) { m_Players = players; }

    override void HCDescribe(HCDebugSnapshot snapshot)
    {
        HCLeadModule leads = HCLeadModule.Get();
        HCGroupService groups = HCGroupService.Get();
        if (!leads || !m_Players || !m_Players.Players) { return; }
        array<string> seen = new array<string>;
        int work = m_Players.Players.Count();
        if (work > 8) { work = 8; }
        int emitted;
        for (int index = 0; index < work; index++)
        {
            if (m_Cursor >= m_Players.Players.Count()) { m_Cursor = 0; }
            PlayerBase player = PlayerBase.Cast(m_Players.Players[m_Cursor]);
            m_Cursor++;
            if (!player || !player.GetIdentity()) { continue; }
            string groupId = HCLeadPolicy.SoloGroup(player.GetIdentity().GetId());
            if (groups) { groupId = groups.HCLeadGroup(player); }
            if (groupId == "" || seen.Find(groupId) >= 0) { continue; }
            seen.Insert(groupId);
            array<ref HCWorldLead> received;
            leads.GroupLeads(groupId, received);
            if (!received) { continue; }
            for (int leadIndex = 0; leadIndex < received.Count(); leadIndex++)
            {
                if (emitted >= 64) { return; }
                emitted++;
                HCWorldLead lead = received[leadIndex];
                if (!lead) { continue; }
                HCWorldPlace place = HCLeadPolicy.Place(lead.TargetPlaceId);
                if (!place) { continue; }
                snapshot.AddPoint("leads", lead.Id, place.Position, place.Name, HCLeadPolicy.Text(lead));
            }
        }
    }
}

class HCDebugMaterializerCandidatesContributor : HCDebugContributor
{
    override void HCDescribe(HCDebugSnapshot snapshot)
    {
        HCWorldModule world = HCWorldModule.Get();
        if (!world) { return; }
        int work = HCWorldLimits.HOLDOUTS + HCWorldLimits.PARTIES;
        if (work > 64) { work = 64; }
        for (int index = 0; index < work; index++)
        {
            HCWorldProposal row = world.MaterializerRow(index);
            if (!row) { continue; }
            snapshot.AddPoint("materializer_candidates", row.Id, row.Position, row.Kind + " / " + row.PlaceId, "Eligible ledger candidate only; not a queued proposal or live body. Actor cap=" + row.ActorCap.ToString());
        }
    }
}

// HC-25: aggregate reads owner caches only. No module callbacks, player/entity
// traversal, native settings, store reads or provider readiness probes.
class HCDebugOperationalContributor : HCDebugContributor
{
    override void HCDescribe(HCDebugSnapshot snapshot)
    {
        array<string> rows = HCOperationalContributors.HCRows(GetGame().GetTickTime());
        for (int index = 0; index < rows.Count(); index++)
        {
            snapshot.HCAddOperational(rows[index]);
        }
        HCDebugDocument document = snapshot.HCDocument();
        document.operationalTruncated += HCOperationalContributors.HCRefused();
    }
}
