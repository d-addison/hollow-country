// AI_ENCOUNTER (event family 5) on HC site patrols. An encounter binds an
// already-owned, route-qualified HCXAISitePatrol near the event anchor; it never
// spawns, moves, equips or deletes an actor and never restores one after a
// restart. Kills count only when the killed eAIBase belongs to the bound
// patrol's native group, read inside EEKilled before Expansion's cleanup.
//
// Readiness comes from live director state, not from expansion-ai.json or a
// trusted receipt: the director must be in "run" (ownership reconciled, routes
// qualified, patrols created) and this process gets its own session token
// "xai-<ownership session>-<UTC seconds>" for the lease journal.
//
// Expansion APIs (read-only reference, ai_scripts/core_scripts of the pinned
// build): ExpansionStatic.GetTimestamp(bool useUTC)
// core_scripts/3_Game/DayZExpansion_Core/ExpansionStatic.c:1748;
// eAIDynamicPatrol.m_Group (public field)
// ai_scripts/4_World/DayZExpansion_AI/Classes/Patrols/eAIDynamicPatrol.c:45.
// Native: Game.GetWorldName 3_Game/Global/Game.c:934.
// W5 review (b): one request scans at most 66 states x 128 qualified points;
// no new tick work, actors or route qualification. Refuse beyond 600 m.
class HCXAIEncounters : Managed
{
    static const int MAX_KILLS = 16;
    protected static HCXAIEncounters s_Active;

    protected ref HCXAIJournal m_Journal;
    protected ref array<ref HCXAIEncounter> m_Bindings = new array<ref HCXAIEncounter>();
    protected string m_Token;
    protected string m_State = "waiting for sites";
    protected bool m_Armed;
    protected bool m_Settled;

    static HCXAIEncounters Active() { return s_Active; }

    void Open()
    {
        if (!GetGame() || !GetGame().IsServer()) { return; }
        s_Active = this;
    }

    void Close()
    {
        m_Armed = false;
        m_Settled = true;
        m_State = "closed";
        m_Bindings.Clear();
        m_Journal = null;
        if (s_Active == this) { s_Active = null; }
    }

    bool Armed() { return m_Armed; }
    bool Settled() { return m_Settled; }
    string State() { return m_State; }

    // Arms once, after the director reaches "run"; a director that ends in
    // off/refused/stopped (or never reconciled ownership) settles unarmed.
    void Step()
    {
        if (m_Armed || m_Settled) { return; }
        HCXAISiteDirector director = HCXAISiteDirector.Active();
        if (!director) { return; }
        string phase = director.Phase();
        if (phase == "off" || phase == "refused" || phase == "stopped")
        {
            this.Settle("site director " + phase);
            return;
        }
        if (phase != "run") { return; }
        string token = HCXAISiteRules.EncounterToken(director.OwnedSession(), ExpansionStatic.GetTimestamp(true));
        if (token == "")
        {
            this.Settle("ownership session not reconciled");
            return;
        }
        HCXAIJournal journal = HCXAIJournal.Open(token, 64, true);  // 64 rows: the journal maximum
        if (!journal)
        {
            this.Settle("lease journal refused");
            return;
        }
        m_Journal = journal;
        m_Token = token;
        m_Armed = true;
        m_Settled = true;
        m_State = "armed";
        Print("[HC Expansion AI] encounters armed: session=" + m_Token + "; AI_ENCOUNTER binds qualified HC site patrols; no actors are spawned");
    }

    protected void Settle(string reason)
    {
        m_Settled = true;
        m_State = "not armed (" + reason + ")";
        Print("[HC Expansion AI] encounters not armed: " + reason + "; AI_ENCOUNTER stays unready");
    }

    // Qualified routes whose native patrol object exists.
    int QualifiedCount()
    {
        HCXAISiteDirector director = HCXAISiteDirector.Active();
        if (!director) { return 0; }
        int count = 0;
        foreach (HCXAISiteState state : director.States())
        {
            if (state.Transient) { continue; } // materializer patrols keep their own lifecycle
            if (state.Site.Checkpoint) { continue; }
            if (state.Qualified && state.Patrol) { count++; }
        }
        return count;
    }

    int OpenCount()
    {
        int count = 0;
        foreach (HCXAIEncounter binding : m_Bindings)
        {
            if (!binding.Released) { count++; }
        }
        return count;
    }

    bool SiteBound(string siteId)
    {
        foreach (HCXAIEncounter binding : m_Bindings)
        {
            if (!binding.Released && binding.SiteId == siteId) { return true; }
        }
        return false;
    }

    // World-level: the event context carries only the world name. The anchor
    // bound (600 m) is enforced by StartEncounter; authored trigger configs
    // reach at least 600 m so the event anchor can activate the patrol.
    bool Ready(string world)
    {
        if (!m_Armed || !m_Journal) { return false; }
        if (!GetGame() || !HCBuildIdentity.SameWorld(world, GetGame().GetWorldName())) { return false; }
        HCXAISiteDirector director = HCXAISiteDirector.Active();
        if (!director || director.Phase() != "run") { return false; }
        if (this.OpenCount() >= HCAILimits.Get().MaxEncounters) { return false; }
        foreach (HCXAISiteState state : director.States())
        {
            if (state.Transient) { continue; } // materializer patrols keep their own lifecycle
            if (state.Site.Checkpoint) { continue; }
            if (state.Qualified && state.Patrol && !this.SiteBound(state.Site.Id)) { return true; }
        }
        return false;
    }

    HCXAIEncounter FindEncounter(string lease)
    {
        foreach (HCXAIEncounter binding : m_Bindings)
        {
            if (binding.Id == lease) { return binding; }
        }
        return null;
    }

    // Binds the nearest eligible patrol: qualified, native patrol present, not
    // bound to another open encounter, some qualified point within 600 m of
    // the anchor. Intent is journaled first. No transient actor path is needed.
    bool StartEncounter(string lease, string session, string missionId, vector anchor, int actorCap)
    {
        if (!m_Armed || !m_Journal || actorCap < 1) { return false; }
        if (lease == "" || session == "" || missionId == "") { return false; }
        HCXAIEncounter existing = this.FindEncounter(lease);
        if (existing)
        {
            return existing.Session == session && existing.MissionId == missionId && !existing.Released;
        }
        if (this.OpenCount() >= HCAILimits.Get().MaxEncounters || m_Bindings.Count() >= HCAILimits.Get().MaxEncounters * 2)
        {
            Print("[HC Expansion AI] encounter refused: lease=" + lease + " mission=" + missionId + " reason=open encounter cap");
            return false;
        }
        HCXAISiteDirector director = HCXAISiteDirector.Active();
        if (!director || director.Phase() != "run") { return false; }
        HCXAISiteState chosen;
        float chosenGap = 0;
        string nearestId = "none";
        float nearestGap = 0;
        string nearestProblem = "no site states";
        foreach (HCXAISiteState state : director.States())
        {
            if (state.Transient) { continue; } // materializer patrols keep their own lifecycle
            if (state.Site.Checkpoint) { continue; }
            float gap = HCXAISiteRules.RouteGap(state.PatrolPoints, anchor);
            bool patrolled = state.Patrol != null;
            string problem = HCXAISiteRules.EncounterProblem(state.Qualified, patrolled, this.SiteBound(state.Site.Id), gap, director.HCActivationRadius(state.Site, false));
            if (nearestId == "none" || gap < nearestGap)
            {
                nearestId = state.Site.Id;
                nearestGap = gap;
                nearestProblem = problem;
            }
            if (problem == "" && (!chosen || gap < chosenGap))
            {
                chosen = state;
                chosenGap = gap;
            }
        }
        if (!chosen)
        {
            Print("[HC Expansion AI] encounter refused: lease=" + lease + " mission=" + missionId + " nearest=" + nearestId + " gap=" + nearestGap.ToString() + " reason=" + nearestProblem);
            return false;
        }
        if (!m_Journal.PrepareBegin(lease, session, missionId) || !m_Journal.Begin(lease, session, missionId))
        {
            Print("[HC Expansion AI] encounter refused: lease=" + lease + " mission=" + missionId + " reason=lease journal refused the intent");
            return false;
        }
        HCXAIEncounter binding = new HCXAIEncounter();
        binding.Id = lease;
        binding.Session = session;
        binding.MissionId = missionId;
        binding.SiteId = chosen.Site.Id;
        binding.Gap = chosenGap;
        m_Bindings.Insert(binding);
        Print("[HC Expansion AI] encounter bound: lease=" + lease + " mission=" + missionId + " site=" + binding.SiteId + " gap=" + chosenGap.ToString() + " m; the site patrol stays director-owned");
        return true;
    }

    // Called from eAIBase.EEKilled after super, while GetGroup() still answers.
    void RecordKill(eAIGroup group, string participantId)
    {
        if (!group || participantId == "") { return; }
        HCXAISiteDirector director = HCXAISiteDirector.Active();
        if (!director) { return; }
        foreach (HCXAIEncounter binding : m_Bindings)
        {
            if (binding.Released) { continue; }
            foreach (HCXAISiteState state : director.States())
            {
                if (state.Site.Id != binding.SiteId || !state.Patrol || state.Patrol.m_Group != group) { continue; }
                int killCount = binding.Kills.Count();
                if (killCount >= HCXAIEncounters.MAX_KILLS) { return; }
                HCXAIKill kill = new HCXAIKill();
                kill.ParticipantId = participantId;
                kill.Token = binding.Id + ":kill:" + killCount.ToString();
                binding.Kills.Insert(kill);
                Print("[HC Expansion AI] encounter kill observed: lease=" + binding.Id + " site=" + binding.SiteId + " kill=" + killCount.ToString());
                return;
            }
        }
    }

    // Evidence for a living participant who killed a member of the bound patrol.
    // The first observed participant keeps the receipt.
    HCEventObjectiveEvidence ObserveEncounter(string lease, PlayerBase participant)
    {
        HCXAIEncounter binding = this.FindEncounter(lease);
        if (!binding || binding.Released) { return null; }
        if (!participant || !participant.IsAlive() || !participant.GetIdentity()) { return null; }
        string participantId = participant.GetIdentity().GetId();
        if (participantId == "") { return null; }
        if (binding.ReceiptToken == "")
        {
            foreach (HCXAIKill kill : binding.Kills)
            {
                if (kill.ParticipantId == participantId)
                {
                    binding.ReceiptToken = kill.Token;
                    binding.ReceiptParticipant = participantId;
                    break;
                }
            }
        }
        if (binding.ReceiptToken == "" || binding.ReceiptParticipant != participantId) { return null; }
        HCEventObjectiveEvidence evidence = new HCEventObjectiveEvidence();
        evidence.Observed = true;
        evidence.Lease = binding.Id;
        evidence.Session = binding.Session;
        evidence.ParticipantId = participantId;
        evidence.Sequence = 1;
        evidence.Token = binding.ReceiptToken;
        return evidence;
    }

    // Releases the binding only; the patrol keeps patrolling for the director.
    bool StopEncounter(string lease)
    {
        HCXAIEncounter binding = this.FindEncounter(lease);
        if (!binding) { return false; }
        binding.Released = true;
        return true;
    }

    // True once the journal row is closed prunable. An unknown lease (a prior
    // process, or a refused start) owns nothing here and is gone.
    bool GoneEncounter(string lease)
    {
        HCXAIEncounter binding = this.FindEncounter(lease);
        if (!binding) { return true; }
        if (!binding.Released) { return false; }
        if (!binding.Ended)
        {
            if (!m_Journal || !m_Journal.End(lease, true)) { return false; }
            binding.Ended = true;
        }
        int index = m_Bindings.Find(binding);
        if (index >= 0) { m_Bindings.RemoveOrdered(index); }
        return true;
    }
}
