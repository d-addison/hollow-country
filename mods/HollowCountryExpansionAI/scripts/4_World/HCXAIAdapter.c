// Original calls against pinned Expansion 1.9.84. Qualification remains pending.
// Timing API inspected in scripts-1.30.164289: EnSystem.c:106 TickCount;
// 3_Game/Global/Game.c:914 GetTickTime; EnScript.c:902/917 map Set/Find.
// Trusted server ports. No RPC/JSON capability flag installs these hooks.
// Begin/MemberCreated/MemberGone/End must be durable, idempotent ledger operations.
// False is uncertain, never permission to free reservations or repeat creation.
class HCXAIHooks
{
    HCXAIAdmission Admission(string worldSession) { return null; }
    bool RouteQualified(string surveySha256, string loadoutSha256) { return false; }
    bool BeginLease(string lease, string session, string missionId, int actors, int items) { return false; }
    bool MemberCreated(string lease, int index, Object actor) { return false; }
    bool MemberGone(string lease, int index) { return false; }
    bool EndLease(string lease) { return false; }
    HCObserverTransitionInput Observers(string worldSession, string lease, int index, Object actor, vector position) { return null; }
}
class HCXAIService
{
    protected static ref HCXAIAdapter s_Adapter;
    static HCXAIAdapter Adapter() { return s_Adapter; }
    static void Bind(HCXAIAdapter adapter)
    {
        s_Adapter = adapter;
    }
}
class HCXAIAdapter extends HCModule
{
    protected bool m_ReadinessLogged;
    protected float m_ReadinessStarted;
    protected string m_ReadinessDependency;
    protected float m_ReadinessProbeAfter;
    protected int m_LastQualifiedPatrolCount = -1;
    protected float m_QualifiedProbeAfter;
    protected ref HCXAISiteDirector m_Sites;
    // AI_ENCOUNTER on the director's own qualified patrols (HCXAIEncounters.c).
    protected ref HCXAIEncounters m_Encounters;
    protected ref HCXAICampRoutine m_CampRoutine;
    protected ref HCAICaravan m_Caravan;
    protected bool m_CaravanRequested;
    protected ref HCWorkBudget m_AdjunctWork = new HCWorkBudget;
    protected int m_AdjunctCursor;
    protected ref map<string, int> m_StagePeaks = new map<string, int>;

    // Declared here so the later operational modded link can publish cached
    // adjunct status without an earlier link calling an undeclared method.
    void HCPublishCaravanStatus(bool boot) {}

    // #190: the provider keeps actor/item refs after a successful bind. Drop
    // them whenever the caravan is not on an active leg (refusal, quarantine,
    // lost). A returned leg keeps them: HCConfirmedReturn still reads the
    // actor to unload, and the next bind or HCClose clears them. Script
    // references only: no entity is deleted or moved, so no stock is
    // duplicated or removed.
    protected void HCDropCaravanHandles()
    {
        if (!m_Caravan || !m_Caravan.m_IO) { return; }
        bool held = m_Caravan.m_IO.LeftActor || m_Caravan.m_IO.RightActor;
        if (m_Caravan.m_IO.LeftItem || m_Caravan.m_IO.RightItem) { held = true; }
        if (!held || m_Caravan.HCActive()) { return; }
        if (m_Caravan.m_State && m_Caravan.m_State.Leg == "returned") { return; }
        m_Caravan.m_IO.HCClear();
        Print("[HC Caravan] HC-36 provider handles released leg_inactive=1 runtime=PENDING");
    }

    override string GetName() { return "optional-expansion-human-ai"; }
    // Site readiness and optional adjuncts publish their own admission state.
    override bool IsEnabled(HCSettings settings) { return true; }
    override void OnStart(HCSettings settings)
    {
        if (!GetGame() || !GetGame().IsServer()) { return; }
        m_AdjunctCursor = 0;
        m_StagePeaks.Clear();
        m_ReadinessStarted = GetGame().GetTickTime();
        m_ReadinessProbeAfter = 0;
        m_ReadinessDependency = "";
        // HC sites (patrols, scavengers, holdouts) admit themselves from engine
        // observations; the retired lease profile is never loaded.
        // Seed the V2 encounters flag from the preference before the director binds
        // sites, so checkpoint sites are kept even though HCXLivingModule starts later.
        HCXAIQualification.SetEncountersEnabled(settings && settings.EnableEncounters);
        m_Sites = new HCXAISiteDirector();
        m_Sites.Start();
        // AI_ENCOUNTER readiness comes from the director's live state. The lease
        // spawner path (expansion-ai.json profile, local hook port, trusted
        // receipt verifiers) is retired: it is no longer installed or loaded.
        m_Encounters = new HCXAIEncounters();
        m_Encounters.Open();
        m_CampRoutine = new HCXAICampRoutine();
        m_CampRoutine.Open(settings);
        HCXAIService.Bind(this);
        HCXAICaravanAdapter caravanPort = new HCXAICaravanAdapter();
        m_Caravan = new HCAICaravan();
        m_CaravanRequested = settings && settings.EnableEncounters;
        m_Caravan.Open(settings, caravanPort);
        this.HCPublishCaravanStatus(true);
        // Locals, not `new X` arguments: the native compiler trap (review w23-sitbind).
        HCXAISituationAdapter situationPort = new HCXAISituationAdapter();
        HCSituationActors.HCBind(situationPort);
        HCXAIRaidAdapter raidPort = new HCXAIRaidAdapter();
        HCCampRaidActors.HCBind(raidPort);
        HCSituationActors.HCBindRaid(raidPort);
        HCXAITransitAdapter transitPort = new HCXAITransitAdapter();
        HCSituationActors.HCBindTransit(transitPort);
        HCReached.Mark("expansion_ai.service_bind");
        this.LogAddonChecks();
        Print("[HC Expansion AI] retired: expansion-ai.json lease profile, local hook port and receipt verifiers are not loaded; AI_ENCOUNTER gates on site director run + per-process session + a qualified site patrol");
        this.LogReadiness("server start");
    }
    bool ExpansionAISettingsLoaded()
    {
        return HCXExpansionBridge.HCSettings() != null;
    }
    // Refresh at settlement and on qualified controller count changes.
    // Qualified patrols are not a count of live AI groups.
    void HCRefreshReadiness()
    {
        // #271: boot 114 loaded Expansion settings at start. The later 277 s
        // HC Ready receipt waited on HC source-page checks + the shared road
        // graph loader + 88 candidate bindings, not Expansion initialization.
        // Cached status only; retain the original admission and final receipt.
        float now = GetGame().GetTickTime();
        if (now >= m_ReadinessProbeAfter)
        {
            m_ReadinessProbeAfter = now + 15;
            HCOperationalStatus status = this.HCGetOperationalStatus();
            string dependency = status.HCState() + ":" + status.HCReason();
            if (dependency != m_ReadinessDependency)
            {
                m_ReadinessDependency = dependency;
                string line = "[HC AIStartup] state=" + status.HCState() + " reason=" + status.HCReason();
                float elapsed = now - m_ReadinessStarted;
                Print(line + " elapsed_s=" + elapsed.ToString() + " admission_unchanged=1 runtime=PENDING");
            }
        }
        // There cannot be a qualified encounter before settlement. Once
        // settled, the count scan is diagnostic only: sample it every 15 s.
        if (!m_Encounters.Settled()) { return; }
        if (m_ReadinessLogged && now < m_QualifiedProbeAfter) { return; }
        m_QualifiedProbeAfter = now + 15;
        int qualified = m_Encounters.QualifiedCount();
        if ((!m_ReadinessLogged && m_Encounters.Settled()) || (m_ReadinessLogged && qualified != m_LastQualifiedPatrolCount))
        {
            this.LogReadiness("encounters settled or qualified patrol count changed");
        }
    }
    void LogReadiness(string trigger)
    {
        if (!m_Encounters || !m_Sites) { return; }
        Print(m_Sites.HCLocalitySummary());
        if (m_Encounters.Settled()) { m_ReadinessLogged = true; }
        bool ready = m_Encounters.Ready(GetGame().GetWorldName());
        int qualified = m_Encounters.QualifiedCount();
        m_LastQualifiedPatrolCount = qualified;
        bool loaded = this.ExpansionAISettingsLoaded();
        string settingsState = "not loaded";
        if (loaded) { settingsState = "loaded"; }
        string globals = this.GlobalsProblem();
        if (globals == "") { globals = "fair"; }
        Print("[HC Expansion AI] readiness (" + trigger + ") AI_ENCOUNTER Ready=" + ready.ToString() + "; encounters=" + m_Encounters.State() + "; sites=" + m_Sites.Phase() + "; qualified_patrols=" + qualified.ToString() + "; expansion_ai_settings=" + settingsState + "; globals=" + globals + "; expansion-ai.json and receipt verifiers retired");
    }
    void LogAddonChecks()
    {
        bool provider = GetGame().ConfigIsExisting("CfgPatches DayZExpansion_AI_Scripts");
        bool animations = GetGame().ConfigIsExisting("CfgPatches DayZExpansion_AI_Animations");
        Print("[HC Expansion AI] installed CfgPatches DayZExpansion_AI_Scripts=" + provider.ToString() + " DayZExpansion_AI_Animations=" + animations.ToString() + "; names alone do not verify artifact/version pin");
        // Exercise the base late-bound selection (HCEventAISelection) once, so startup logs
        // whether HC Events resolves this addon's provider; it only constructs a script object.
        HCEventAIProvider selected = HCEventAISelection.Create();
        string selectedName = "none";
        if (selected) { selectedName = selected.ClassName(); }
        Print("[HC Expansion AI] base event AI provider selection=" + selectedName + "; AI_ENCOUNTER Ready stays false until the site director runs with a qualified patrol");
    }
    // First unfair or unsettled Expansion AI global, or "" when fair.
    string GlobalsProblem()
    {
        if (eAIBase.s_eAI_UnlimitedReload != 0 || eAIBase.s_eAI_UnlimitedReloadAll != 0) { return "unlimited reload mask set"; }
        // On a server GetAI() returns the instance even before Load(); only loaded settings are settled.
        if (!this.ExpansionAISettingsLoaded()) { return "Expansion AI settings not loaded"; }
        ExpansionAISettings settings = HCXExpansionBridge.HCSettings();
        if (!settings) { return "Expansion AI settings not loaded"; }
        if (settings.EnableFlankingOutsideCombat) { return "EnableFlankingOutsideCombat must be false"; }
        if (settings.CanRecruitFriendly || settings.CanRecruitGuards) { return "CanRecruitFriendly/CanRecruitGuards must be false"; }
        if (settings.DamageMultiplier != 1 || settings.DamageReceivedMultiplier != 1) { return "DamageMultiplier/DamageReceivedMultiplier must be 1"; }
        return "";
    }
    // Expansion bridge callbacks remain callable. They only recorded retired
    // spawner slots/kills; live site encounters observe their own actors through
    // HCXAIEncounters, so there is no lease bookkeeping to perform here.
    void RecordDelete(Object actor) {}
    void RecordDeath(Object actor, string participantId) {}
    // Raw ticks use the same counter as HC Perf; divide by that window's
    // ticks_per_ms. Log only a new peak above the cooperative 16 ms target.
    protected void HCStageCost(string stage, int began)
    {
        int ticks = TickCount(began);
        if (ticks < 160000) { return; }
        int peak;
        if (m_StagePeaks.Find(stage, peak) && ticks <= peak) { return; }
        m_StagePeaks.Set(stage, ticks);
        Print("[HC Expansion AI] tick_stage=" + stage + " ticks_max=" + ticks.ToString() + " runtime=PENDING");
    }

    override void OnTick(float deltaTime)
    {
        if (!GetGame() || !GetGame().IsServer()) { return; }
        // Keep the site's maintenance priority. After a long native call, yield
        // adjunct work rather than adding it to the same module tick. A retained
        // round-robin cursor prevents a costly adjunct starving the next one.
        // Stop starting adjunct stages at 12 ms, leaving 4 ms of the 16 ms
        // target for the final stage. Atomic native work can still exceed it.
        m_AdjunctWork.HCReset(3, 12);
        int began = TickCount(0);
        int moduleBegan = began;
        if (m_Sites) { m_Sites.Step(); }
        this.HCStageCost("sites", began);
        for (int step = 0; step < 3; step++)
        {
            if (TickCount(moduleBegan) >= 120000 || !m_AdjunctWork.HCContinue()) { break; }
            int stage = m_AdjunctCursor;
            m_AdjunctCursor = (m_AdjunctCursor + 1) % 3;
            began = TickCount(0);
            if (stage == 0)
            {
                if (m_CampRoutine) { m_CampRoutine.Step(); }
                this.HCStageCost("camp", began);
            }
            else if (stage == 1)
            {
                if (m_Caravan) { m_Caravan.Step(); this.HCDropCaravanHandles(); }
                this.HCPublishCaravanStatus(false);
                this.HCStageCost("caravan", began);
            }
            else
            {
                if (m_Encounters) { m_Encounters.Step(); this.HCRefreshReadiness(); }
                this.HCStageCost("encounters", began);
            }
        }
    }
    override void OnStop()
    {
        // A rejected/replaced owner must not clear the live owner's ports.
        if (HCXAIService.Adapter() == this)
        {
            HCSituationActors.HCBind(null);
            HCCampRaidActors.HCBind(null);
            HCSituationActors.HCBindRaid(null);
            HCSituationActors.HCBindTransit(null);
        }
        if (m_Caravan) { m_Caravan.HCClose(); }
        m_CaravanRequested = false;
        this.HCPublishCaravanStatus(false);
        m_Caravan = null;
        if (m_CampRoutine) { m_CampRoutine.Close(); }
        if (m_Encounters) { m_Encounters.Close(); }
        if (m_Sites) { m_Sites.Stop(); }
    }
}
// AI_ENCOUNTER provider: binds an already-owned, qualified HC site patrol near
// the event anchor (HCXAIEncounters). It never spawns actors.
class HCExpansionAIEventProvider extends HCEventAIProvider
{
    override bool Ready(string world)
    {
        HCXAIEncounters encounters = HCXAIEncounters.Active();
        return encounters && encounters.Ready(world);
    }
    override bool Start(string lease, string session, string missionId, vector anchor, int actorCap)
    {
        HCXAIEncounters encounters = HCXAIEncounters.Active();
        return encounters && encounters.StartEncounter(lease, session, missionId, anchor, actorCap);
    }
    override HCEventObjectiveEvidence Observe(string lease, PlayerBase participant)
    {
        HCXAIEncounters encounters = HCXAIEncounters.Active();
        if (!encounters) { return null; }
        return encounters.ObserveEncounter(lease, participant);
    }
    override bool Stop(string lease)
    {
        HCXAIEncounters encounters = HCXAIEncounters.Active();
        return encounters && encounters.StopEncounter(lease);
    }
    override bool Gone(string lease)
    {
        // No encounters object: nothing is bound in this process.
        HCXAIEncounters encounters = HCXAIEncounters.Active();
        if (!encounters) { return true; }
        return encounters.GoneEncounter(lease);
    }
}
modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        Register(new HCXAIAdapter());
    }
}
// Narrow original observation/getter extension; no provider source is replaced.
// Expansion AI hook implementations live in HCXExpansionBridge.c.
