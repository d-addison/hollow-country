// Infected siege of elevated havens (wh-nav-c, 2026-11-22; navelev-design.md O3).
// The engine has no ladder or climb for infected. When an infected that targeted a player gives up on an
// elevated spot (HCNavHavenCensus.OnGiveUp, subscribed here; no Reach or Navigation file changes), the
// spot is sieged instead:
//   1. Open.   One row per target player (at most MaxSieges), holding up to 6 infected that gave up.
//   2. Settle. After GatherSeconds, with the player still up and within 25 m, the siege starts. The anchor
//              is the navmesh point under the LAST-KNOWN position (the give-up event's position, never the
//              player's live position), or the bottom of the nearest ladder of the building there
//              (ladder_guard); it marks the siege site and is never a movement goal. No
//              waypoint is ever written: no native pack group is steered to the anchor, so infected that
//              gave up come back only through real perception and noise (no position writes, no group
//              moves: the 11-21 crash lesson in HCNativeInfectedPack.Release).
//   3. Noise.  Every NoiseSeconds one real native noise at a member's OWN position (HCSearchNoise.EmitAtScaled),
//              at most one per tick server-wide. The strength is amplified by InfectedSiege.NoiseStrengthMultiplier
//              (NoiseSystem.AddNoisePos external_strenght_multiplier, installed 3_Game/Noise.c:7), default 17: the
//              installed NoiseActionDefault strength is 10, so 10 x 17 = 170 m of assumed hearing radius (strength
//              read as metres, unobserved; the environment reduction only shortens it), clamped so strength x
//              multiplier never passes 250 m (HCInfectedSiegePolicy.HCNoiseMultiplier). The engine propagates the
//              noise and the ambient population that hears it comes through vanilla perception; nothing is pulled.
//   4. No spawns. A siege never spawns infected (owner 2026-11-23, #354: the old reinforce ring needed a 320 m
//              spawn inside a hearing radius of about 10 m and was inert). The siege relies on the ambient
//              population only. The retired key InfectedSiege.ReinforcePerPlayerWindow is ignored (reported once
//              at start when an operator set it) and the started line says reinforce=off.
//   5. End.    The player comes down (dy under the reach band), walks 25 m from the spot the siege opened
//              at, or 180 s pass (a dead or gone target counts as left). A row with no live member left
//              ends at once with reason no_live_member and its slot is released
//              in the same evaluation. Ending only withdraws the siege; the live player position is read
//              for these end tests and the open-time haven gate, never to place, steer or target anything. Nothing
//              is restored by hand: this module wrote no waypoint to any group, so no group is left on a
//              last waypoint and there is nothing to park; members stay in their native group.
// An infected sits in at most one siege row. A siege with no usable anchor (no navmesh point and no ladder)
// is refused: it is not counted as started and nothing is noised.
// Knowledge: the infected only know what the give-up event told them (the player and where they stood).
// Doors, positions and inventories are never touched. Runtime only, never persisted: no stored format.
// Lines (formats are fixed):
//   [HC Nav] siege started max= gather= noise= noise_mult=<effective> noise_base=<config strength> reinforce=off
//   [HC Nav] siege start anchor=<mesh|ladder|none> members=<m> n=<count>
//   [HC Nav] siege end reason=<down|left|timeout|no_live_member> n=<count of ends for the reason> members= secs= noise= active=
//   [HC Nav] siege refused reason=<no_anchor> n=<count for the reason>
// Start, refused and end lines share one throttle (first 8 per count, then every 16th).
//   [HC Use] module=InfectedSiege feature=siege_started|siege_noise|ladder_guard count=<n>
// siege_started is registered at start and counted only for a usable anchor (mesh or ladder); the other
// two register on their first real event, so a feature a scenario cannot exercise is not listed as a
// registered counter at zero.
// Bounds: <=8 sieges, <=6 members each, 4 evaluations per tick in a 2 ms HCWorkBudget slice (one navmesh
// sample, one ray and <=8 ladder reads each), <=1 noise per tick and per siege per NoiseSeconds, and the
// 180 s siege timeout (NoiseSeconds is at least 10, so at most 18 noises per siege).
// Native evidence, installed scripts-1.30.164289: 3_Game/Entities/Building.c:23-25 GetLaddersCount,
// GetLadderPosTop, GetLadderPosBottom (coordinate space unobserved: |bottom - building| > 50 m is read as
// model-space and converted with Object.c:873 ModelToWorld, still far is ignored); 3_Game/AI/AIAgent.c:7
// AIWorld.c:122 SampleNavmeshPosition; Global/DayZPhysics.c:199 RaycastRV; constants.c:35 ObjIntersectGeom;
// Entities/DayZAnimal.c:193 GetAIAgent; 3_Game/Noise.c:7 AddNoisePos; Object.c:215 IsPendingDeletion, :287 GetPosition, :467 GetType,
// :517 IsAlive; EntityAI.c:879 GetHierarchyRoot; EnMath.c Sin/Cos/RandomFloat/Sqrt;
// Game.c:914 GetTickTime, :1120 IsServer, :691 ObjectDelete.

class HCInfectedSiegeRow
{
    PlayerBase Target;
    ref array<DayZInfected> Members = new array<DayZInfected>;
    vector Origin;
    vector LastKnown;
    vector Anchor;
    vector NoisePos;
    string AnchorKind = "none";
    float BaseY;
    float Opened;
    float NextNoise;
    bool Active;
    int Noises;
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
    protected ref map<string, int> m_Refused = new map<string, int>;
    protected ref HCOperationalStatus m_Operational = new HCOperationalStatus;
    protected bool m_Running;
    protected string m_Refusal;
    protected int m_Cursor;
    protected int m_Started;
    protected int m_EndedDown;
    protected int m_EndedLeft;
    protected int m_EndedTimeout;
    protected int m_EndedNoMember;
    protected float m_NoiseAt = -1;
    protected float m_NoiseMult = 1;
    protected float m_NoiseBase;

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
        m_Cursor = 0;
        m_NoiseAt = -1;
        m_NoiseBase = HCConfigHelper.GetFloat(HCSearchNoise.NOISE_PATH + " strength", 0);
        m_NoiseMult = HCInfectedSiegePolicy.HCNoiseMultiplier(m_Limits.NoiseStrengthMultiplier, m_NoiseBase);
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
        Print("[HC Nav] siege started max=" + m_Limits.MaxSieges.ToString() + " gather=" + m_Limits.GatherSeconds.ToString() + " noise=" + m_Limits.NoiseSeconds.ToString() + " noise_mult=" + m_NoiseMult.ToString() + " noise_base=" + m_NoiseBase.ToString() + " reinforce=off runtime=PENDING");
    }

    override void OnStop()
    {
        if (m_Listener) { HCNavHavenCensus.HCUnsubscribe(m_Listener); }
        m_Listener = null;
        m_Running = false;
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
        vector known = HCKnownPoint(infected, anchor);
        HCInfectedSiegeRow row = HCRowOf(player);
        if (!row)
        {
            if (m_Rows.Count() >= m_Limits.MaxSieges) { return; }
            row = new HCInfectedSiegeRow;
            row.Target = player;
            row.Origin = known;
            row.BaseY = infected.GetPosition()[1];
            row.Opened = GetGame().GetTickTime();
            m_Rows.Insert(row);
        }
        row.LastKnown = known;
        if (row.Members.Count() >= HCInfectedSiegePolicy.MAX_MEMBERS) { return; }
        row.Members.Insert(infected);
    }

    // What the give-up event told the infected: the position it was given, or its own position when that
    // is invalid or further than the siege radius from it. Never the target's live position.
    protected vector HCKnownPoint(DayZInfected infected, vector anchor)
    {
        vector own = infected.GetPosition();
        if (!HCInfectedStore.ValidPosition(anchor)) { return own; }
        if (HCInfectedSiegePolicy.HCHorizontal(own, anchor) > HCInfectedSiegePolicy.LEAVE_METRES) { return own; }
        return anchor;
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
        if (row.Members.Count() == 0)
        {
            HCEnd(row, HCInfectedSiegePolicy.END_NO_LIVE_MEMBER, now);
            return false;
        }
        PlayerBase player = row.Target;
        if (!player || !player.IsAlive())
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
        HCNoise(row, now);
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

    // ---- Activate --------------------------------------------------------------------------

    // False when the siege was refused and its row removed (the caller's cursor then points at the next row).
    protected bool HCActivate(HCInfectedSiegeRow row, float now)
    {
        PlayerBase player = row.Target;
        vector feet = row.LastKnown;
        row.Active = true;
        row.NextNoise = now;
        vector sampled;
        if (GetGame().GetWorld() && GetGame().GetWorld().GetAIWorld() && GetGame().GetWorld().GetAIWorld().SampleNavmeshPosition(feet, HCInfectedSiegePolicy.ANCHOR_SAMPLE_METRES, HCNavFilters.HCFor(HCNavFilters.PROFILE_OUTDOOR), sampled))
        {
            row.Anchor = sampled;
            row.AnchorKind = "mesh";
        }
        vector bottom;
        if (HCLadderBottom(player, feet, bottom))
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
        if (row.AnchorKind == "ladder") { HCModuleReadiness.HCUseGuarded(GetName(), "ladder_guard", row); }
        m_Started++;
        if (HCInfectedSiegePolicy.HCPrintStart(m_Started))
        {
            Print("[HC Nav] siege start anchor=" + row.AnchorKind + " members=" + row.Members.Count().ToString() + " n=" + m_Started.ToString() + " runtime=PENDING");
        }
        return true;
    }

    // The bottom (world space) of the ladder of the building under the last-known position whose top is
    // nearest to it. False without a building, a ladder in range or a coordinate space that checks out.
    protected bool HCLadderBottom(PlayerBase player, vector feet, out vector bottom)
    {
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

    // ---- Noise ---------------------------------------------------------------------------------------

    protected void HCNoise(HCInfectedSiegeRow row, float now)
    {
        if (now < row.NextNoise || now == m_NoiseAt) { return; }
        DayZInfected source = row.Members[0];
        if (!source) { return; }
        m_NoiseAt = now;
        row.NextNoise = now + m_Limits.NoiseSeconds;
        row.Noises++;
        row.NoisePos = source.GetPosition();
        HCSearchNoise.EmitAtScaled(source, row.NoisePos, m_NoiseMult);
        HCModuleReadiness.HCUseGuarded(GetName(), "siege_noise", source);
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

    // ---- End -----------------------------------------------------------------------------------------

    protected void HCEnd(HCInfectedSiegeRow row, string reason, float now)
    {
        int count;
        if (reason == HCInfectedSiegePolicy.END_DOWN) { m_EndedDown++; count = m_EndedDown; }
        else if (reason == HCInfectedSiegePolicy.END_TIMEOUT) { m_EndedTimeout++; count = m_EndedTimeout; }
        else if (reason == HCInfectedSiegePolicy.END_NO_LIVE_MEMBER) { m_EndedNoMember++; count = m_EndedNoMember; }
        else { m_EndedLeft++; count = m_EndedLeft; }
        // The slot is released first, in this call; the line is throttled like the start line (first 8, then every 16th).
        int index = m_Rows.Find(row);
        if (index >= 0) { m_Rows.Remove(index); }
        if (!HCInfectedSiegePolicy.HCPrintStart(count)) { return; }
        string line = "[HC Nav] siege end reason=" + reason + " n=" + count.ToString() + " members=" + row.Members.Count().ToString();
        int seconds = Math.Round(now - row.Opened);
        Print(line + " secs=" + seconds.ToString() + " noise=" + row.Noises.ToString() + " active=" + HCV2Admission.OnOff(row.Active) + " runtime=PENDING");
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
