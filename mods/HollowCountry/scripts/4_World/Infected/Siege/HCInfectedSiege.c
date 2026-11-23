// Infected siege of elevated havens (wh-nav-c, 2026-11-22; navelev-design.md O3).
// The engine has no ladder or climb for infected. When an infected that targeted a player gives up on an
// elevated spot (HCNavHavenCensus.OnGiveUp, subscribed here; no Reach or Navigation file changes), the
// spot is sieged instead:
//   1. Open.   One row per target player (at most MaxSieges), holding up to 6 infected that gave up.
//   2. Gather. After GatherSeconds, with the player still up and within 25 m, the siege starts. The anchor
//              is the navmesh point under the player's feet, or the bottom of the nearest ladder of the
//              building under the player (ladder_guard). Members whose native group has a pack behaviour
//              get one SetWaypoints([anchor]); a lone infected is never steered (no position writes, no
//              group moves: the 11-21 crash lesson in HCNativeInfectedPack.Release).
//   3. Noise.  Every NoiseSeconds one real native noise at a member's OWN position (HCSearchNoise.EmitAt),
//              at most one per tick server-wide. The engine propagates it; nothing is pulled.
//   4. Reinforce. At most one batch (<=2 bodies) per siege, spawned through HCHordeReinforce.HCCreate at a
//              ring 320..360 m from the anchor (HCHidden: out of sight of every player). Reinforcements
//              are NEVER steered: no waypoint is written to any group of a body this module created (a
//              new body may have joined a wild group of agents we did not create). They only come
//              through real perception, e.g. the noise of step 3. A per-player window
//              (ReinforcePerPlayerWindow bodies per 10 minutes, keyed by the persistent player id kept
//              server-side, never logged) caps what one player can draw; when every window slot is in use
//              the batch is refused (reason=window_full) instead of recycling another player's slot.
//   5. End.    The player comes down (dy under the reach band), walks 25 m from the spot the siege opened
//              at, or 180 s pass (an end with no live member, a dead or gone target counts as left). Every
//              group the siege waypointed is parked in place, mirroring HCNativeInfectedPack.Release:
//              one waypoint at a live member's current position (radius 1), members stay in their native
//              group, no group move and no DeleteGroup (the 11-21 crash). Native perception then drives.
// An infected sits in at most one siege row. A siege with no usable anchor (no navmesh point and no ladder)
// is refused: it is not counted as started and nothing is gathered, noised or reinforced.
// Knowledge: the infected only know what the give-up event told them (the player and where they stood).
// Doors, positions and inventories are never touched. Runtime only, never persisted: no stored format.
// Lines (formats are fixed):
//   [HC Nav] siege start anchor=<mesh|ladder|none> members=<m> n=<count>
//   [HC Nav] siege end reason=<down|left|timeout> n=<count of ends for the reason> members= secs= noise= reinforced=
//   [HC Nav] siege refused reason=<no_anchor|window_full|no_identity> n=<count for the reason>
//   [HC Use] module=InfectedSiege feature=siege_started|siege_noise|ladder_guard|reinforce count=<n>
// siege_started is registered at start and counted only for a usable anchor (mesh or ladder); the other
// three register on their first real event, so a feature a scenario cannot exercise is not listed as a
// registered counter at zero.
// Bounds: <=8 sieges, <=6 members each, 4 evaluations per tick in a 2 ms HCWorkBudget slice (one navmesh
// sample, one ray and <=8 ladder reads each), <=1 noise per tick, reinforce under HCHordeReinforce caps
// (2 creates per tick, 256 leases) and the per-player window.
// Native evidence, installed scripts-1.30.164289: 3_Game/Entities/Building.c:23-25 GetLaddersCount,
// GetLadderPosTop, GetLadderPosBottom (coordinate space unobserved: |bottom - building| > 50 m is read as
// model-space and converted with Object.c:873 ModelToWorld, still far is ignored); 3_Game/AI/AIAgent.c:7
// GetGroup; AIGroup.c:14 GetBehaviour; AIGroupBehaviour.c:7 WaypointParams, :27 SetWaypoints;
// AIWorld.c:122 SampleNavmeshPosition; Global/DayZPhysics.c:199 RaycastRV; constants.c:35 ObjIntersectGeom;
// Entities/DayZAnimal.c:193 GetAIAgent; Object.c:215 IsPendingDeletion, :287 GetPosition, :467 GetType,
// :517 IsAlive; EntityAI.c:879 GetHierarchyRoot; EnMath.c Sin/Cos/RandomFloat/Sqrt;
// Game.c:914 GetTickTime, :1120 IsServer, :691 ObjectDelete.

// Lease owner for siege reinforcements. HCHordeReinforce deletes a hidden body once its pack is no longer
// active; this pack stays active exactly while its siege lives. It is never started: no group, no members.
class HCSiegeReinforcePack : HCNativeInfectedPack
{
    protected bool m_SiegeLive;
    void HCSetLive(bool live) { m_SiegeLive = live; }
    override bool HCReinforceActive() { return m_SiegeLive; }
}

class HCInfectedSiegeRow
{
    PlayerBase Target;
    ref array<DayZInfected> Members = new array<DayZInfected>;
    ref array<AIGroup> Waypointed = new array<AIGroup>;
    vector Origin;
    vector Anchor;
    string AnchorKind = "none";
    float BaseY;
    float Opened;
    float NextNoise;
    float NextReinforce;
    bool Active;
    bool ReinforceDone;
    int ReinforceLeft;
    int ReinforceTries;
    int GatherCursor;
    int Noises;
    int Reinforced;
    ref HCSiegeReinforcePack Pack;
}

class HCInfectedSiegeListener : HCNavGiveUpListener
{
    override void OnGiveUp(DayZInfected infected, EntityAI target, vector anchor, string reason)
    {
        HCInfectedSiegeModule module = HCInfectedSiegeModule.Active();
        if (module) { module.HCGiveUp(infected, target, anchor); }
    }
}

class HCInfectedSiegeModule : HCModule
{
    protected static HCInfectedSiegeModule s_Instance;
    protected ref HCInfectedSiegeConfig m_Limits;
    protected ref HCInfectedSiegeListener m_Listener;
    protected ref array<ref HCInfectedSiegeRow> m_Rows = new array<ref HCInfectedSiegeRow>;
    protected ref HCWorkBudget m_Budget = new HCWorkBudget;
    protected ref set<Object> m_Hits = new set<Object>;
    protected ref array<string> m_WindowPlayer = new array<string>;
    protected ref map<string, int> m_Refused = new map<string, int>;
    protected ref array<float> m_WindowStart = new array<float>;
    protected ref array<int> m_WindowUsed = new array<int>;
    protected ref HCOperationalStatus m_Operational = new HCOperationalStatus;
    protected bool m_Running;
    protected string m_Refusal;
    protected int m_Cursor;
    protected int m_Started;
    protected int m_EndedDown;
    protected int m_EndedLeft;
    protected int m_EndedTimeout;
    protected float m_NoiseAt = -1;

    override string GetName() { return "InfectedSiege"; }

    override bool IsEnabled(HCSettings settings)
    {
        return settings && settings.EnableInfected;
    }

    override void RegisterUses()
    {
        HCModuleReadiness.HCRegisterUse(GetName(), "siege_started");
    }

    override HCOperationalStatus HCGetOperationalStatus()
    {
        if (m_Limits && !m_Limits.Enabled) { m_Operational.HCPublish("off", "siege_operator_off"); }
        else { HCModuleReadiness.HCDerive(m_Operational, m_Running, m_Refusal, "", "siege_listener_subscribed"); }
        return m_Operational;
    }

    override void OnStart(HCSettings settings)
    {
        if (!GetGame().IsServer() || !IsEnabled(settings) || m_Running) { return; }
        m_Limits = new HCInfectedSiegeConfig;
        m_Limits.HCLoad();
        m_Limits.HCLog();
        if (!m_Limits.Enabled) { m_Operational.HCPublish("off", "siege_operator_off"); return; }
        m_Refusal = "";
        m_Rows.Clear();
        m_WindowPlayer.Clear();
        m_WindowStart.Clear();
        m_WindowUsed.Clear();
        m_Cursor = 0;
        m_NoiseAt = -1;
        m_Listener = new HCInfectedSiegeListener;
        if (!HCNavHavenCensus.HCSubscribe(m_Listener))
        {
            m_Listener = null;
            m_Refusal = "siege_listener_refused";
            Print("[HC Nav] siege subscribe refused reason=listener_cap runtime=PENDING");
            return;
        }
        m_Running = true;
        s_Instance = this;
        Print("[HC Nav] siege started max=" + m_Limits.MaxSieges.ToString() + " gather=" + m_Limits.GatherSeconds.ToString() + " noise=" + m_Limits.NoiseSeconds.ToString() + " window=" + m_Limits.ReinforcePerPlayerWindow.ToString() + " runtime=PENDING");
    }

    override void OnStop()
    {
        if (m_Listener) { HCNavHavenCensus.HCUnsubscribe(m_Listener); }
        m_Listener = null;
        m_Running = false;
        for (int index = 0; index < m_Rows.Count(); index++)
        {
            if (m_Rows[index].Pack) { m_Rows[index].Pack.HCSetLive(false); }
            HCPark(m_Rows[index]);
        }
        m_Rows.Clear();
        if (s_Instance == this) { s_Instance = null; }
    }

    static HCInfectedSiegeModule Active()
    {
        if (!s_Instance || !s_Instance.m_Running) { return null; }
        return s_Instance;
    }

    // ---- Open ----------------------------------------------------------------------------------------

    // Called by the census for every give-up. Opens or joins the siege of the native target; the
    // infected only contributes what it knows: its own body and the player it lost.
    void HCGiveUp(DayZInfected infected, EntityAI target, vector anchor)
    {
        if (!m_Running || !infected || !target) { return; }
        PlayerBase player = PlayerBase.Cast(target);
        if (!player || !player.IsAlive() || player.GetCommand_Vehicle()) { return; }
        float band = HCInfectedTuning.Get().Reach.ElevatedMin;
        float dy = player.GetPosition()[1] - infected.GetPosition()[1];
        if (!HCInfectedSiegePolicy.HCHaven(dy, band)) { return; }
        if (HCInfectedSiegePolicy.HCHorizontal(infected.GetPosition(), player.GetPosition()) > HCInfectedSiegePolicy.LEAVE_METRES) { return; }
        for (int taken = 0; taken < m_Rows.Count(); taken++)
        {
            if (m_Rows[taken].Members.Find(infected) >= 0) { return; }
        }
        HCInfectedSiegeRow row = HCRowOf(player);
        if (!row)
        {
            if (m_Rows.Count() >= m_Limits.MaxSieges) { return; }
            row = new HCInfectedSiegeRow;
            row.Target = player;
            row.Origin = player.GetPosition();
            row.BaseY = infected.GetPosition()[1];
            row.Opened = GetGame().GetTickTime();
            m_Rows.Insert(row);
        }
        if (row.Members.Count() >= HCInfectedSiegePolicy.MAX_MEMBERS) { return; }
        row.Members.Insert(infected);
    }

    protected HCInfectedSiegeRow HCRowOf(PlayerBase player)
    {
        for (int index = 0; index < m_Rows.Count(); index++)
        {
            if (m_Rows[index].Target == player) { return m_Rows[index]; }
        }
        return null;
    }

    // ---- Tick ----------------------------------------------------------------------------------------

    override void OnTick(float deltaTime)
    {
        if (!m_Running || m_Rows.Count() == 0) { return; }
        float now = GetGame().GetTickTime();
        m_Budget.HCReset(HCInfectedSiegePolicy.EVALUATIONS_PER_TICK, HCInfectedSiegePolicy.SLICE_MILLISECONDS);
        int visited = 0;
        int total = m_Rows.Count();
        while (visited < total && m_Budget.HCContinue())
        {
            if (m_Cursor >= m_Rows.Count()) { m_Cursor = 0; }
            if (m_Rows.Count() == 0) { return; }
            HCInfectedSiegeRow row = m_Rows[m_Cursor];
            visited++;
            if (HCEvaluate(row, now)) { m_Cursor++; }
        }
    }

    // Returns false when the row ended (the cursor then already points at the next row).
    protected bool HCEvaluate(HCInfectedSiegeRow row, float now)
    {
        HCPrune(row);
        PlayerBase player = row.Target;
        if (!player || !player.IsAlive() || row.Members.Count() == 0)
        {
            HCEnd(row, HCInfectedSiegePolicy.END_LEFT, now);
            return false;
        }
        float horizontal = HCInfectedSiegePolicy.HCHorizontal(player.GetPosition(), row.Origin);
        string reason = HCInfectedSiegePolicy.HCEndReason(player.GetPosition()[1], row.BaseY, horizontal, now - row.Opened, HCInfectedTuning.Get().Reach.ElevatedMin);
        if (reason != "")
        {
            HCEnd(row, reason, now);
            return false;
        }
        if (!row.Active)
        {
            if (now - row.Opened >= m_Limits.GatherSeconds) { return HCActivate(row, now); }
            return true;
        }
        HCGather(row);
        HCNoise(row, now);
        HCReinforce(row, now);
        return true;
    }

    protected void HCPrune(HCInfectedSiegeRow row)
    {
        for (int index = row.Members.Count() - 1; index >= 0; index--)
        {
            DayZInfected member = row.Members[index];
            if (!member || !member.IsAlive() || member.IsPendingDeletion()) { row.Members.RemoveOrdered(index); }
        }
    }

    // ---- Activate and gather --------------------------------------------------------------------------

    // False when the siege was refused and its row removed (the caller's cursor then points at the next row).
    protected bool HCActivate(HCInfectedSiegeRow row, float now)
    {
        PlayerBase player = row.Target;
        vector feet = player.GetPosition();
        row.Active = true;
        row.NextNoise = now;
        row.NextReinforce = now;
        vector sampled;
        if (GetGame().GetWorld() && GetGame().GetWorld().GetAIWorld() && GetGame().GetWorld().GetAIWorld().SampleNavmeshPosition(feet, HCInfectedSiegePolicy.ANCHOR_SAMPLE_METRES, HCNavFilters.HCFor(HCNavFilters.PROFILE_OUTDOOR), sampled))
        {
            row.Anchor = sampled;
            row.AnchorKind = "mesh";
        }
        vector bottom;
        if (HCLadderBottom(player, bottom))
        {
            row.Anchor = bottom;
            row.AnchorKind = "ladder";
        }
        if (row.AnchorKind == "none")
        {
            HCRefuse("no_anchor");
            int refusedAt = m_Rows.Find(row);
            if (refusedAt >= 0) { m_Rows.Remove(refusedAt); }
            return false;
        }
        HCModuleReadiness.HCUseGuarded(GetName(), "siege_started", row);
        m_Started++;
        if (HCInfectedSiegePolicy.HCPrintStart(m_Started))
        {
            Print("[HC Nav] siege start anchor=" + row.AnchorKind + " members=" + row.Members.Count().ToString() + " n=" + m_Started.ToString() + " runtime=PENDING");
        }
        return true;
    }

    // The bottom (world space) of the ladder of the building under the player whose top is nearest to the
    // player. False without a building, a ladder in range or a coordinate space that checks out.
    protected bool HCLadderBottom(PlayerBase player, out vector bottom)
    {
        vector feet = player.GetPosition();
        vector contact;
        vector normal;
        int component;
        m_Hits.Clear();
        bool hit = DayZPhysics.RaycastRV(feet + "0 0.3 0", feet + "0 -1.2 0", contact, normal, component, m_Hits, null, player, true, false, ObjIntersectGeom);
        if (!hit || m_Hits.Count() == 0) { return false; }
        Object surface = m_Hits.Get(0);
        Building host = Building.Cast(surface);
        if (!host)
        {
            EntityAI part = EntityAI.Cast(surface);
            if (part) { host = Building.Cast(part.GetHierarchyRoot()); }
        }
        if (!host) { return false; }
        int count = host.GetLaddersCount();
        if (count > HCInfectedSiegePolicy.LADDER_SCAN) { count = HCInfectedSiegePolicy.LADDER_SCAN; }
        vector hostPosition = host.GetPosition();
        float best = HCInfectedSiegePolicy.LADDER_TOP_METRES;
        bool found = false;
        for (int index = 0; index < count; index++)
        {
            vector rawBottom = host.GetLadderPosBottom(index);
            vector rawTop = host.GetLadderPosTop(index);
            vector worldBottom = rawBottom;
            vector worldTop = rawTop;
            if (!HCInfectedSiegePolicy.HCLadderSpaceOk(rawBottom, hostPosition))
            {
                worldBottom = host.ModelToWorld(rawBottom);
                worldTop = host.ModelToWorld(rawTop);
                if (!HCInfectedSiegePolicy.HCLadderSpaceOk(worldBottom, hostPosition)) { continue; }
            }
            float gap = vector.Distance(worldTop, feet);
            if (gap < best)
            {
                best = gap;
                bottom = worldBottom;
                found = true;
            }
        }
        return found;
    }

    // One member per call (round-robin): a member whose native group has a pack behaviour is sent to the
    // anchor once per group. A lone infected has no such group and is left to its native chase (no
    // steering, no group moves).
    protected void HCGather(HCInfectedSiegeRow row)
    {
        if (row.AnchorKind == "none") { return; }
        if (row.GatherCursor >= row.Members.Count()) { row.GatherCursor = 0; }
        DayZInfected member = row.Members[row.GatherCursor];
        row.GatherCursor++;
        AIAgent agent = member.GetAIAgent();
        if (!agent) { return; }
        AIGroup group = agent.GetGroup();
        if (!group || row.Waypointed.Find(group) >= 0) { return; }
        row.Waypointed.Insert(group);
        BehaviourGroupInfectedPack behaviour = BehaviourGroupInfectedPack.Cast(group.GetBehaviour());
        if (!behaviour) { return; }
        ref array<ref BehaviourGroupInfectedPackWaypointParams> route = new array<ref BehaviourGroupInfectedPackWaypointParams>;
        route.Insert(new BehaviourGroupInfectedPackWaypointParams(row.Anchor, HCInfectedSiegePolicy.GATHER_RADIUS_METRES));
        behaviour.SetWaypoints(route, 0, true, false);
        if (row.AnchorKind == "ladder") { HCModuleReadiness.HCUseGuarded(GetName(), "ladder_guard", member); }
    }

    // ---- Noise ---------------------------------------------------------------------------------------

    protected void HCNoise(HCInfectedSiegeRow row, float now)
    {
        if (now < row.NextNoise || now == m_NoiseAt) { return; }
        DayZInfected source = row.Members[0];
        if (!source) { return; }
        m_NoiseAt = now;
        row.NextNoise = now + m_Limits.NoiseSeconds;
        row.Noises++;
        HCSearchNoise.EmitAt(source, source.GetPosition());
        HCModuleReadiness.HCUseGuarded(GetName(), "siege_noise", source);
    }

    // ---- Reinforce -----------------------------------------------------------------------------------

    protected void HCReinforce(HCInfectedSiegeRow row, float now)
    {
        if (row.ReinforceDone || now < row.NextReinforce) { return; }
        PlayerBase player = row.Target;
        string playerId = HCPlayerId(player);
        if (playerId == "")
        {
            row.ReinforceDone = true;
            HCRefuse("no_identity");
            return;
        }
        int slot = HCWindowSlot(playerId, now);
        if (slot < 0)
        {
            row.ReinforceDone = true;
            HCRefuse("window_full");
            return;
        }
        if (row.ReinforceLeft == 0 && row.ReinforceTries == 0)
        {
            row.ReinforceLeft = HCInfectedSiegePolicy.HCBatch(m_Limits.ReinforcePerPlayerWindow, m_WindowUsed[slot]);
            if (row.ReinforceLeft == 0) { row.ReinforceDone = true; return; }
        }
        if (row.ReinforceTries >= HCInfectedSiegePolicy.REINFORCE_TRIES || row.ReinforceLeft <= 0 || row.AnchorKind == "none")
        {
            row.ReinforceDone = true;
            return;
        }
        row.ReinforceTries++;
        row.NextReinforce = now + HCInfectedSiegePolicy.REINFORCE_GAP_SECONDS;
        DayZInfected template = row.Members[0];
        if (!template) { return; }
        vector entry = HCRingPoint(row.Anchor);
        if (!HCNavMesh(entry)) { return; }
        if (!row.Pack)
        {
            row.Pack = new HCSiegeReinforcePack;
            row.Pack.HCSetLive(true);
        }
        ZombieBase body = HCHordeReinforce.HCCreate(template.GetType(), entry, row.Pack);
        if (!body) { return; }
        // Unsteered by design: no waypoint is written to the new body's group (it may be a wild group).
        row.ReinforceLeft--;
        row.Reinforced++;
        m_WindowUsed.Set(slot, m_WindowUsed[slot] + 1);
        HCModuleReadiness.HCUseGuarded(GetName(), "reinforce", body);
    }

    // A point on the hidden ring around the anchor; the caller still needs a navmesh point and HCHidden.
    protected vector HCRingPoint(vector anchor)
    {
        float angle = Math.RandomFloat(0, 6.2831853);
        float metres = Math.RandomFloat(HCInfectedSiegePolicy.RING_MIN_METRES, HCInfectedSiegePolicy.RING_MAX_METRES);
        vector point = anchor;
        point[0] = anchor[0] + Math.Sin(angle) * metres;
        point[2] = anchor[2] + Math.Cos(angle) * metres;
        return point;
    }

    // Snaps the point onto the outdoor navmesh; false when there is none within the sample radius.
    protected bool HCNavMesh(out vector point)
    {
        if (!GetGame().GetWorld() || !GetGame().GetWorld().GetAIWorld()) { return false; }
        vector sampled;
        if (!GetGame().GetWorld().GetAIWorld().SampleNavmeshPosition(point, HCInfectedSiegePolicy.RING_SAMPLE_METRES, HCNavFilters.HCFor(HCNavFilters.PROFILE_OUTDOOR), sampled)) { return false; }
        point = sampled;
        return true;
    }

    // The persistent id of the player, used only as a server-side key (never logged). Empty without one.
    protected string HCPlayerId(PlayerBase player)
    {
        if (!player || !player.GetIdentity()) { return ""; }
        return player.GetIdentity().GetId();
    }

    // The player's reinforcement window slot, created on demand. A slot whose window has run out is reclaimed;
    // with every slot in a live window the answer is -1 (refused), never another player's slot.
    protected int HCWindowSlot(string playerId, float now)
    {
        int expired = -1;
        for (int index = 0; index < m_WindowPlayer.Count(); index++)
        {
            bool over = HCInfectedSiegePolicy.HCWindowExpired(now, m_WindowStart[index]);
            if (m_WindowPlayer[index] == playerId)
            {
                if (over)
                {
                    m_WindowStart.Set(index, now);
                    m_WindowUsed.Set(index, 0);
                }
                return index;
            }
            if (over && expired < 0) { expired = index; }
        }
        if (m_WindowPlayer.Count() < HCInfectedSiegePolicy.WINDOW_SLOTS)
        {
            m_WindowPlayer.Insert(playerId);
            m_WindowStart.Insert(now);
            m_WindowUsed.Insert(0);
            return m_WindowPlayer.Count() - 1;
        }
        if (expired < 0) { return -1; }
        m_WindowPlayer.Set(expired, playerId);
        m_WindowStart.Set(expired, now);
        m_WindowUsed.Set(expired, 0);
        return expired;
    }

    // A refusal with a reason code; one count per reason, the line is bounded like the start line.
    protected void HCRefuse(string reason)
    {
        int count = 1;
        if (m_Refused.Contains(reason)) { count = m_Refused.Get(reason) + 1; }
        m_Refused.Set(reason, count);
        if (HCInfectedSiegePolicy.HCPrintStart(count))
        {
            Print("[HC Nav] siege refused reason=" + reason + " n=" + count.ToString() + " runtime=PENDING");
        }
    }

    // Parks every group the siege waypointed, mirroring HCNativeInfectedPack.Release: one waypoint at a live
    // member's current position (radius 1), loop off. No group move, no DeleteGroup, members stay native.
    // At most 6 groups x 6 members, compared directly; a group without a live member of this row cannot be
    // parked (no position to hold).
    protected void HCPark(HCInfectedSiegeRow row)
    {
        for (int slot = 0; slot < row.Waypointed.Count(); slot++)
        {
            AIGroup group = row.Waypointed[slot];
            if (!group) { continue; }
            BehaviourGroupInfectedPack behaviour = BehaviourGroupInfectedPack.Cast(group.GetBehaviour());
            if (!behaviour) { continue; }
            for (int index = 0; index < row.Members.Count(); index++)
            {
                DayZInfected member = row.Members[index];
                if (!member || member.IsPendingDeletion()) { continue; }
                AIAgent agent = member.GetAIAgent();
                if (!agent || agent.GetGroup() != group) { continue; }
                ref array<ref BehaviourGroupInfectedPackWaypointParams> hold = new array<ref BehaviourGroupInfectedPackWaypointParams>;
                hold.Insert(new BehaviourGroupInfectedPackWaypointParams(member.GetPosition(), 1));
                behaviour.SetWaypoints(hold, 0, true, false);
                break;
            }
        }
        row.Waypointed.Clear();
    }

    // ---- End -----------------------------------------------------------------------------------------

    protected void HCEnd(HCInfectedSiegeRow row, string reason, float now)
    {
        int count;
        if (reason == HCInfectedSiegePolicy.END_DOWN) { m_EndedDown++; count = m_EndedDown; }
        else if (reason == HCInfectedSiegePolicy.END_TIMEOUT) { m_EndedTimeout++; count = m_EndedTimeout; }
        else { m_EndedLeft++; count = m_EndedLeft; }
        if (row.Pack) { row.Pack.HCSetLive(false); }
        HCPark(row);
        string line = "[HC Nav] siege end reason=" + reason + " n=" + count.ToString() + " members=" + row.Members.Count().ToString();
        int seconds = Math.Round(now - row.Opened);
        Print(line + " secs=" + seconds.ToString() + " noise=" + row.Noises.ToString() + " reinforced=" + row.Reinforced.ToString() + " active=" + HCV2Admission.OnOff(row.Active) + " runtime=PENDING");
        int index = m_Rows.Find(row);
        if (index >= 0) { m_Rows.Remove(index); }
    }
}

modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        HCInfectedSiegeModule siegeModule = new HCInfectedSiegeModule;
        Register(siegeModule);
    }
}
