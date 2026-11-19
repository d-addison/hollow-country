// HC-5/#148/#139: observed gestures and durable betrayal, no dialogue.
// Existing provider calls below retain their prior citations. New provider
// emote/cease-fire calls go through the installed native HCXSignalProvider.
// LC-T403..406 / EXP-L1/L2/L3/L6. Installed Expansion addons/ai_scripts.pbo:
// 4_World/DayZExpansion_AI/Classes/Targets/eAIPlayerTargetInformation.c:58 CalculateThreat;
// Classes/Targets/eAIEntityTargetInformation.c:24 GetEntity; eAITargetInformationState.c:7-21
// public threat/LOS state (active threat otherwise decays slowly:58-102);
// Entities/AI/eAIBase.c:4118 eAI_OnNoiseEvent, :9755 RaiseWeapon (clears queued shots),
// :10860-10874 Expansion_SetEmote/Expansion_PlayEmote; :9743 CanRaiseWeapon;
// Entities/DayZPlayerImplement.c:22 member slot, :234 GetGroup;
// Classes/eAIGroup.c:671 GetFaction, :685 GetName, :1123 IsInCombat;
// Classes/Patrols/eAIDynamicPatrol.c:637 stable configured group name;
// 3_Game/DayZExpansion_AI/Factions/eAIFaction.c:104 guard semantics.
// Native scripts-1.30.164289: 3_Game/Global/DayZPhysics.c:199 RaycastRV;
// 4_World/Entities/DayZPlayerImplement.c:4005 IsRaised;
// 3_Game/Entities/Object.c:287 GetPosition, :517 IsAlive, :630,636 weapon tests;
// 3_Game/Entities/Man.c:21 GetIdentity, :81 GetHumanInventory;
// 3_Game/Systems/Inventory/HumanInventory.c:16 GetEntityInHands;
// 4_World/Entities/ManBase/PlayerBase.c:1892 GetEmoteManager, :3925 IsUnconscious;
// 4_World/Classes/EmoteManager.c:1026 CanPlayEmote;
// 3_Game/constants.c:368,393 greeting/hold; Global/Game.c:1535 GetTime.
// Raid death hook: native 4_World/Entities/ManBase/PlayerBase.c:1214
// EEKilled(Object killer); :1255 EEHitBy (exact parameters retained below);
// Expansion GetGroup reference is listed above.
class HCXStance
{
    static bool Owns(eAIBase ai)
    {
        return HCXAIQualification.EncountersEnabled() && ai && ai.GetGroup() && HCXFactions.Known(HCXFactions.Id(ai.GetGroup().GetFaction()));
    }
    static int Relation(eAIBase ai, PlayerBase player)
    {
        string theirs = "Travellers";
        if (player.GetGroup())
        {
            string mapped = HCXFactions.Id(player.GetGroup().GetFaction());
            if (mapped != "") { theirs = mapped; }
        }
        return HCXFactions.Relation(HCXFactions.Id(ai.GetGroup().GetFaction()), theirs);
    }
    // Hostile factions may be fought in legitimate self-defence even when a
    // hit/kill defence record exists. Betrayal requires a non-hostile relation.
    static bool HCRememberKill(eAIBase actor, PlayerBase player)
    {
        if (!actor || !player) { return false; }
        return HCXStance.Relation(actor, player) >= 0;
    }
    static bool RaisedWeapon(PlayerBase player)
    {
        EntityAI hands = player.GetHumanInventory().GetEntityInHands();
        return player.IsRaised() && hands && (hands.IsWeapon() || hands.IsMeleeWeapon());
    }
    // Fresh geometry supplements provider LOS, never discovers a player itself.
    static bool Visible(eAIBase ai, PlayerBase player)
    {
        vector contact;
        vector normal;
        int component;
        set<Object> hits = new set<Object>();
        vector chest = player.GetPosition() + Vector(0, 1.2, 0);
        bool blocked = DayZPhysics.RaycastRV(ai.GetPosition() + Vector(0, 1.6, 0), chest, contact, normal, component, hits, null, ai);
        if (!blocked) { return true; }
        return hits.Find(player) >= 0 && vector.Distance(contact, chest) < 0.8;
    }
}
class HCXWarning
{
    int Started = -1;
    int LastSeen = -1;
    bool Hostile;
    int LastWaveSerial;
    int NextWarning;
}
// Extend the existing HC defence record, not a second hit classifier. This
// accessor is declared before the hook that calls it; rescue policy stays owned
// by HCXDefence.OnHit. The later eAIBase link calls super before reading it.
modded class HCXDefence
{
    static bool HCHitRecorded(eAIBase actor, PlayerBase player)
    {
        if (!s_Running || !actor || !player) { return false; }
        HCXGrudge grudge = HCXDefence.Find(actor.GetGroup(), player);
        if (!grudge || grudge.Until <= GetGame().GetTime()) { return false; }
        return grudge.Kind == HCXDefencePolicy.KIND_HIT || grudge.Kind == HCXDefencePolicy.KIND_KILL;
    }
}
modded class eAIBase
{
    int HCXLastGunfire = -1;
    bool HCXLivingRefused;
    override void EEHitBy(TotalDamageResult damageResult, int damageType, EntityAI source, int component, string dmgZone, string ammo, vector modelPos, float speedCoef)
    {
        super.EEHitBy(damageResult, damageType, source, component, dmgZone, ammo, modelPos, speedCoef);
        if (!GetGame() || !GetGame().IsServer() || !HCXStance.Owns(this)) { return; }
        PlayerBase attacker = HCXDefence.AttackerOf(source);
        if (HCXDefence.HCHitRecorded(this, attacker) && HCXStance.Relation(this, attacker) >= 0) { HCXEmoteObservation.Remember(this, attacker); }
    }
    override void EEKilled(Object killer)
    {
        if (GetGame() && GetGame().IsServer())
        {
            HCXAISiteDirector raidDirector = HCXAISiteDirector.Active();
            if (raidDirector) { raidDirector.RecordDeath(GetGroup()); }
            // Durable betrayal depends on faction relation, not the defence
            // record super.OnKill creates for the bounded survivor response.
            PlayerBase attacker = HCXDefence.AttackerOf(EntityAI.Cast(killer));
            if (HCXStance.Owns(this) && HCXStance.HCRememberKill(this, attacker)) { HCXEmoteObservation.Remember(this, attacker); }
        }
        super.EEKilled(killer);
    }
    override void eAI_OnNoiseEvent(EntityAI source, vector position, float lifetime, eAINoiseParams params, float strengthMultiplier)
    {
        super.eAI_OnNoiseEvent(source, position, lifetime, params, strengthMultiplier);
        if (!HCXStance.Owns(this) || !params || params.m_Type != eAINoiseType.SHOT || !source) { return; }
        // Observe only the delivered physical noise, bounded by its audible range
        // and our reduced hearing. No player scan, target or position forwarding.
        float audible = Math.Min(80, Math.Min(m_eAI_NoiseInvestigationDistanceLimit, params.m_Strength * strengthMultiplier));
        vector heard = position;
        if (heard == vector.Zero) { heard = source.GetPosition(); }
        if (audible > 0 && vector.Distance(GetPosition(), heard) <= audible) { HCXLastGunfire = GetGame().GetTime(); }
    }
}
modded class eAIPlayerTargetInformation
{
    protected ref map<eAIBase, ref HCXWarning> m_HCWarnings = new map<eAIBase, ref HCXWarning>();

    override float CalculateThreat(eAIBase ai = null, eAITargetInformationState state = null)
    {
        PlayerBase player = PlayerBase.Cast(GetEntity());
        if (!HCXStance.Owns(ai) || !player || !player.GetIdentity()) { return super.CalculateThreat(ai, state); }
        if (!GetGame() || !GetGame().IsServer()) { return super.CalculateThreat(ai, state); }
        // Hit/kill hooks persist accepted aggression before this evaluation.
        // Surrender refuses cease-fire while a live hit/kill record exists;
        // native perception still gates whether defence can raise threat.
        bool defenceHostile = !ai.HCXLivingRefused && HCXAIQualification.ProviderProblem() == "" && HCXDefence.Hostile(ai, player, state);
        bool observed = state && state.m_LOS && player.IsAlive() && !player.IsUnconscious() && HCXStance.Visible(ai, player);
        if (!ai.HCXLivingRefused && HCXAIQualification.ProviderProblem() == "" && HCXEmoteObservation.Surrender(ai, player, observed))
        {
            state.m_ThreatLevel = 0;
            state.m_ThreatLevelActive = 0;
            state.m_AggressionTimeout = 0;
            HCXWarning surrenderedWarning;
            if (m_HCWarnings.Find(ai, surrenderedWarning))
            {
                surrenderedWarning.Started = -1;
                surrenderedWarning.LastSeen = -1;
                surrenderedWarning.Hostile = false;
            }
            return 0;
        }
        if (defenceHostile)
        {
            float defence = HCXDefencePolicy.Threat(super.CalculateThreat(ai, state), true);
            if (state && defence > state.m_ThreatLevelActive) { state.m_ThreatLevelActive = defence; }
            return defence;
        }
        // Grudges are consulted only after real perception. Persisted identity
        // is never used to discover a player or supply a target position.
        if (observed && !ai.HCXLivingRefused && HCXAIQualification.ProviderProblem() == "" && HCXEmoteObservation.Grudge(ai, player))
        {
            state.m_ThreatLevelActive = HCXDefencePolicy.Threat(state.m_ThreatLevelActive, true);
            return state.m_ThreatLevelActive;
        }
        int nowMs = GetGame().GetTime();
        eAITarget current = ai.GetTarget();
        bool currentPlayer = current && current.GetEntity() == player;
        HCXWarning warning;
        if (!m_HCWarnings.Find(ai, warning))
        {
            int expiredIndex = m_HCWarnings.Count() - 1;
            while (expiredIndex >= 0)
            {
                eAIBase priorActor = m_HCWarnings.GetKey(expiredIndex);
                if (!priorActor || !priorActor.IsAlive() || !priorActor.GetGroup()) { m_HCWarnings.Remove(priorActor); }
                expiredIndex--;
            }
            if (m_HCWarnings.Count() >= 8) { return 0; }
            warning = new HCXWarning();
            m_HCWarnings.Insert(ai, warning);
        }
        // Refuse unseen, stale or invalid evidence. Facts are read only after
        // native perception has established LOS and a fresh ray agrees.
        string admissionProblem = HCXAIQualification.ProviderProblem();
        if (!observed || nowMs < 0 || ai.HCXLivingRefused || admissionProblem != "")
        {
            warning.Started = -1;
            warning.LastSeen = -1;
            warning.Hostile = false;
            if (state)
            {
                state.m_ThreatLevel = 0;
                state.m_ThreatLevelActive = 0;
                state.m_AggressionTimeout = 0;
            }
            if (currentPlayer) { ai.RaiseWeapon(false); }
            // W5 review (a): delivered noise cannot identify this unseen target.
            // Native perception owns discovery; never retain a threat floor to
            // manufacture LOS. Both provider threat caches are cleared above.
            return 0;
        }
        warning.LastWaveSerial = HCXEmoteObservation.Wave(ai, player, observed, warning.LastWaveSerial);
        // A lost observation or server stall starts a new warning, never accrues
        // unseen time toward hostility.
        if (warning.LastSeen < 0 || nowMs < warning.LastSeen || nowMs - warning.LastSeen > 2000)
        {
            warning.Started = -1;
            warning.Hostile = false;
        }
        warning.LastSeen = nowMs;
        bool gunfire = ai.HCXLastGunfire >= 0 && nowMs >= ai.HCXLastGunfire && nowMs - ai.HCXLastGunfire <= 10000;
        int stance = HCStancePolicy.Evaluate(HCXStance.RaisedWeapon(player), vector.Distance(ai.GetPosition(), player.GetPosition()), gunfire, HCXStance.Relation(ai, player));
        if (stance == HCStancePolicy.WATCH)
        {
            if (warning.Started >= 0) { Print("[HollowCountry] Stance de-escalated: weapon lowered or outside caution range"); }
            warning.Started = -1;
            warning.Hostile = false;
            // Drop active cached aggression immediately as well as the return
            // value; Expansion otherwise decays active hostility over time.
            state.m_ThreatLevelActive = 0.1;
            state.m_AggressionTimeout = 0;
            if (currentPlayer) { ai.RaiseWeapon(false); }
            return 0.1;
        }
        if (warning.Started < 0)
        {
            // Finite gesture warning, no NPC text and no scripted warning shot.
            // Unsupported control refuses without progressing toward fire.
            if (!currentPlayer || !HCStancePolicy.WarningDue(nowMs, warning.NextWarning)) { state.m_ThreatLevelActive = 0.15; return 0.15; }
            ai.RaiseWeapon(false);
            if (!HCXEmoteObservation.Warn(ai, player)) { state.m_ThreatLevelActive = 0.15; return 0.15; }
            warning.NextWarning = nowMs + 30000;
            warning.Started = nowMs;
            state.m_ThreatLevelActive = 0.15;
            Print("[HollowCountry] Stance warning: gesture; lower weapon to de-escalate; runtime=PENDING");
            return 0.15;
        }
        // Let the warning animation finish, then aim using the provider's
        // already perceived target. HC never supplies its position to the AI.
        if (nowMs - warning.Started >= 2000 && currentPlayer && ai.CanRaiseWeapon()) { ai.RaiseWeapon(true); }
        if (nowMs - warning.Started < 8000) { return 0.2; }
        if (!warning.Hostile)
        {
            warning.Hostile = true;
            Print("[HollowCountry] Stance hostile: raised weapon persisted after 8s warning");
        }
        return 0.6;
    }
}
class HCXLivingModule : HCModule
{
    protected ref HCXCheckpointProps m_Checkpoints;
    protected int m_ActorCursor;
    protected string m_Refusal;
    protected bool m_Started;
    protected ref HCOperationalStatus m_Operational = new HCOperationalStatus;
    override string GetName() { return "v2-expansion-living-world"; }

    // Wave 16: started = OnStart ran; a provider/fairness refusal seen on a live actor is a real degradation
    // and reports its own text (bounded to 128 characters by HCOperationalStatus).
    override HCOperationalStatus HCGetOperationalStatus()
    {
        HCModuleReadiness.HCDerive(m_Operational, m_Started, "", m_Refusal, "living_world_providers_installed");
        return m_Operational;
    }
    override bool IsEnabled(HCSettings settings) { return settings && settings.EnableEncounters; }
    override void OnStart(HCSettings settings)
    {
        Print(HCV2Admission.Line("Factions", true, "EXP-L2", HCV2Gates.Qualified("EXP-L2")));
        Print(HCV2Admission.Line("Stance", true, "EXP-L3", HCV2Gates.Qualified("EXP-L3")));
        Print(HCV2Admission.Line("AskForNews", false, "EXP-L6", false));
        Print(HCV2Admission.Line("Checkpoints", true, "EXP-L1", HCV2Gates.Qualified("EXP-L1")));
        HCXAIQualification.SetEncountersEnabled(true);
        HCAskForNews.Configure(false);
        HCXEmoteObservation.Start();
        HCXEmoteObservation.Install(new HCXNativeSignalProvider());
        m_Checkpoints = new HCXCheckpointProps();
        m_Checkpoints.Start();
        m_Refusal = "";
        m_Started = true;
    }
    override void OnTick(float deltaTime)
    {
        if (m_Checkpoints) { m_Checkpoints.Step(); }
        // One actor checked per tick. No world/player discovery scan.
        array<eAIBase> actors = eAIBase.eAI_GetAll();
        if (!actors || actors.Count() == 0) { return; }
        m_ActorCursor = m_ActorCursor % actors.Count();
        eAIBase actor = actors[m_ActorCursor];
        m_ActorCursor++;
        if (!HCXStance.Owns(actor)) { return; }
        HCXEmoteObservation.Tick(actor);
        string problem = HCXAIQualification.ProviderProblem();
        if (problem == "" && (!actor.HCXAI_Fair() || actor.m_eAI_LootingBehavior != 0)) { problem = "actor finite-ammo/fairness/looting NONE assertion"; }
        if (problem != m_Refusal)
        {
            m_Refusal = problem;
            if (problem != "") { Print("[HollowCountry] Living AI admission refused: " + problem); }
        }
        if (problem != "")
        {
            actor.HCXLivingRefused = true;
            actor.RaiseWeapon(false);
            // Safety stop for provider setting drift, never an inventory move.
            actor.eAI_SetLootingBehavior(0);
        }
        else
        {
            actor.HCXLivingRefused = false;
        }
    }
    override void OnStop()
    {
        m_Started = false;
        HCAskForNews.Configure(false);
        HCXEmoteObservation.Stop();
        HCXAIQualification.SetEncountersEnabled(false);
    }
}
modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        Register(new HCXLivingModule());
    }
}
