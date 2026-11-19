// W5 #121 native evidence in scripts-1.30.164289:
// 3_Game/Entities/DayZInfected.c:39-40 SetStanceVariation/SetIdleState,
// :107 GetInputController, :117 GetCommand_Move; DayZCreatureAIInputController.c:
// 3-4 OverrideMovementSpeed/GetMovementSpeed; DayZAnimal.c:193 GetAIAgent;
// 3_Game/Entities/DayZInfectedInputController.c:9 GetMindState;
// 3_Game/Global/Game.c:1120 IsServer; 1_Core/proto/EnScript.c:380 Count;
// 3_Game/Entities/Object.c:517 IsAlive; EntityAI.c:946 EEDelete.
// 3_Game/AI/AIAgent.c:6 SetKeepInIdle. ZombieBase.c:10 m_StanceVariation,
// :113 IsZombieMilitary, :198-277 command order,
// :349 HandleDeath, :981 EEHitBy, :1090 IsCrawling, :1060 IsBeingBackstabbed.
// Per command: O(1), no allocation. Posture is applied ONCE in MOVE/calm;
// role changes invalidate that one-shot write; no per-frame reassertion is used.
// Dormancy borrows native crawlers at tracked corpses or catalog rooms.
// Never forces StartCommand_Crawl: :811-826 is an injury transition, not a
// reversible lying/standing animation. W56 requests the same native crawl
// transition for newly materialized living bodies; they never stand back up.
modded class ZombieBase
{
    // Failed-roll backoff on HC-14's existing clock/cursor; no callback or IO.
    static const float HC_VARIETY_RETRY_SECONDS = 600;
    protected float m_HCVarietyNextTry;
    protected int m_HCVarietyRole = -1;
    protected bool m_HCVarietyPosture;
    protected bool m_HCVarietySpeed;
    protected bool m_HCVarietyDormant;
    protected bool m_HCVarietyTriedDormant;
    protected float m_HCVarietySleepUntil;
    protected string m_HCVarietyPlace;
    protected int m_HCVarietyObserverCursor;

    int HCVarietyRole() { return m_HCVarietyRole; }
    string HCVarietyPlace() { return m_HCVarietyPlace; }
    bool HCVarietyDormant() { return m_HCVarietyDormant; }
    bool HCVarietyTriedDormant() { return m_HCVarietyTriedDormant; }
    float HCVarietySleepUntil() { return m_HCVarietySleepUntil; }

    int HCVarietyObserverOffset(int count)
    {
        if (count < 1) { return 0; }
        int offset = m_HCVarietyObserverCursor % count;
        m_HCVarietyObserverCursor = (offset + 1) % count;
        return offset;
    }

    void HCVarietyAssign(int role, string place)
    {
        if (m_HCVarietyRole != role) { m_HCVarietyPosture = false; }
        m_HCVarietyRole = role;
        m_HCVarietyPlace = place;
    }

    bool HCVarietyCanTry(float now)
    {
        return !m_HCVarietyTriedDormant && now >= 0 && now >= m_HCVarietyNextTry;
    }

    bool HCVarietySleep(float now, bool permitted)
    {
        // Only a started hold consumes the single rest. A failed roll holds
        // for the named cooldown, even if the bounded cursor revisits sooner.
        // Repeated calls cannot extend a hold or restart a completed actor.
        if (!HCVarietyCanTry(now)) { return false; }
        if (!GetGame().IsServer() || !HCInfectedVarietyModule.VarietyActive()) { return false; }
        if (!HCPostureAdmission.HCCanEnter("native_crawler_idle") || !(now >= 0)) { return false; }
        if (!IsAlive() || !IsCrawling() || IsBeingBackstabbed()) { return false; }
        if (!permitted)
        {
            m_HCVarietyNextTry = now + HC_VARIETY_RETRY_SECONDS;
            return false;
        }
        // Refusals below are candidate-specific (aggro'd, or the native handles are
        // absent): hold them for the same cooldown so the bounded cursor does not
        // re-evaluate them every visit. The pre-checks above stay hold-free: they
        // mean "not a candidate" (gate off, dead, not crawling, backstab) and must
        // flip the instant the state does. The single rest is still not consumed.
        DayZInfectedInputController controller = GetInputController();
        if (!controller)
        {
            m_HCVarietyNextTry = now + HC_VARIETY_RETRY_SECONDS;
            return false;
        }
        if (controller.GetMindState() != DayZInfectedConstants.MINDSTATE_CALM)
        {
            // Named, validated hold (lod.json VarietyNonCalmHoldSeconds, default 600 s).
            m_HCVarietyNextTry = now + HCInfectedLOD.HCVarietyNonCalmHoldSeconds();
            return false;
        }
        AIAgent agent = GetAIAgent();
        if (!agent)
        {
            m_HCVarietyNextTry = now + HC_VARIETY_RETRY_SECONDS;
            return false;
        }
        agent.SetKeepInIdle(true);
        m_HCVarietyTriedDormant = true;
        m_HCVarietyDormant = true;
        m_HCVarietySleepUntil = now + 60;
        return true;
    }

    // Fresh living body only, while the caller proves it unseen. Use the SAME
    // crawl transition request consumed by vanilla ZombieBase.c:811-826; no
    // health edits, resurrection, direct command takeover or reverse crawl.
    // The native handler owns m_IsCrawling and SetSynchDirty (:820-822).
    bool HCVarietyFreshCrawler(float now, string place, int role)
    {
        if (!GetGame().IsServer() || !HCInfectedVarietyModule.VarietyActive()) { return false; }
        if (!IsAlive() || IsBeingBackstabbed() || m_HCVarietyTriedDormant) { return false; }
        DayZInfectedInputController freshInput = GetInputController();
        AIAgent freshAgent = GetAIAgent();
        if (!freshInput || !freshAgent || freshInput.GetMindState() != DayZInfectedConstants.MINDSTATE_CALM) { return false; }
        HCVarietyAssign(role, place);
        m_CrawlTransition = 0;
        freshAgent.SetKeepInIdle(true);
        m_HCVarietyTriedDormant = true;
        m_HCVarietyDormant = true;
        m_HCVarietySleepUntil = 0;
        return true;
    }

    bool HCVarietyWake()
    {
        if (!m_HCVarietyDormant) { return false; }
        m_HCVarietyDormant = false;
        m_HCVarietySleepUntil = 0;
        // The native finisher owns its own keep-idle latch. Never clear it.
        // Death owns the final FSM too: cleanup must not restart a dead actor.
        if (IsAlive() && !IsBeingBackstabbed())
        {
            AIAgent agent = GetAIAgent();
            if (agent) { agent.SetKeepInIdle(false); }
        }
        return true;
    }

    void HCVarietyRelease()
    {
        HCVarietyWake();
        if (m_HCVarietySpeed)
        {
            DayZInfectedInputController controller = GetInputController();
            if (controller) { controller.OverrideMovementSpeed(false, 0); }
        }
        m_HCVarietySpeed = false;
        m_HCVarietyPosture = false;
        m_HCVarietyRole = -1;
        m_HCVarietyPlace = "";
    }

    // N8 EntityAI.c:946 deletion hook; no replacement object or loot is made.
    override void EEDelete(EntityAI parent)
    {
        if (GetGame() && GetGame().IsServer()) { HCVarietyRelease(); }
        super.EEDelete(parent);
    }

    override bool ModCommandHandlerBefore(float pDt, int pCurrentCommandID, bool pCurrentCommandFinished)
    {
        bool consumed = super.ModCommandHandlerBefore(pDt, pCurrentCommandID, pCurrentCommandFinished);
        if (!GetGame().IsServer() || m_HCVarietyRole < 0) { return consumed; }
        DayZInfectedInputController controller = GetInputController();
        if (m_HCVarietySpeed && controller)
        {
            controller.OverrideMovementSpeed(false, 0);
            m_HCVarietySpeed = false;
        }
        if (!HCInfectedVarietyModule.VarietyActive()) { HCVarietyRelease(); return consumed; }
        if (!IsAlive() || IsBeingBackstabbed()) { HCVarietyWake(); return consumed; }
        if (consumed || pCurrentCommandFinished || pCurrentCommandID != DayZInfectedConstants.COMMANDID_MOVE) { return consumed; }
        if (!controller || m_HCVarietyDormant || IsCrawling()) { return consumed; }
        int mind = controller.GetMindState();
        if (!m_HCVarietyPosture && mind == DayZInfectedConstants.MINDSTATE_CALM && HCPostureAdmission.HCCanEnter("native_stance_idle"))
        {
            DayZInfectedCommandMove move = GetCommand_Move();
            if (move)
            {
                // ZombieBase.c:96-99 admits 0..3. Its HandleMindStateChange
                // :450-477 owns idle 0/1/2 and wake transitions. Leave it intact.
                m_StanceVariation = HCInfectedVarietyPolicy.HCStanceForRole(m_HCVarietyRole, IsZombieMilitary());
                move.SetStanceVariation(m_StanceVariation);
                m_HCVarietyPosture = true;
            }
        }
        // Leave vaults, hits, attacks, crawling and native stops intact. Never
        // creates movement or increases the AI's own requested movement speed.
        if (mind == DayZInfectedConstants.MINDSTATE_FIGHT) { return consumed; }
        float nativeSpeed = controller.GetMovementSpeed();
        float limit = HCInfectedVarietyPolicy.MovementLimit(m_HCVarietyRole, nativeSpeed);
        if (nativeSpeed > limit)
        {
            controller.OverrideMovementSpeed(true, limit);
            m_HCVarietySpeed = true;
        }
        return consumed;
    }

    override void EEHitBy(TotalDamageResult damageResult, int damageType, EntityAI source, int component, string dmgZone, string ammo, vector modelPos, float speedCoef)
    {
        if (GetGame().IsServer())
        {
            if (HCVarietyWake()) { HCInfectedVarietyModule.HCRecordDamageWake(); }
        }
        super.EEHitBy(damageResult, damageType, source, component, dmgZone, ammo, modelPos, speedCoef);
    }
}

// Variety-owned read of the shared lod.json config (same source as the posed
// budget): the non-calm crawler hold. Inactive LOD or no config reads the default.
modded class HCInfectedLOD
{
    static float HCVarietyNonCalmHoldSeconds()
    {
        if (!HCInfectedLOD.Active()) { return HCInfectedVarietyPolicy.DEFAULT_NONCALM_HOLD_SECONDS; }
        return s_Config.VarietyNonCalmHoldSeconds;
    }
}

// Extend HC-14's existing registered lifecycle, without a second registration,
// scheduler, player scan, season clock or infected/LOD roster. Core invokes the
// cached HC-1 hook; getters do no config IO or new capability experiments.
modded class HCInfectedVarietyModule
{
    protected ref HCPostureAdmission m_HCPostures;
    protected ref HCOperationalStatus m_HCVarietyStatus = new HCOperationalStatus;

    override bool IsEnabled(HCSettings settings)
    {
        bool requested = super.IsEnabled(settings);
        if (!m_HCPostures) { m_HCPostures = new HCPostureAdmission; }
        // Core does not start disabled modules. Cache/print their off result
        // here from the single original preference observation, with no scan.
        if (!requested)
        {
            m_HCPostures.HCStart(false);
            m_HCVarietyStatus.HCPublish("off", "operator_preference");
        }
        return requested;
    }

    override void OnStart(HCSettings settings)
    {
        super.OnStart(settings);
        if (!GetGame().IsServer() || !m_Running)
        {
            m_HCVarietyStatus.HCPublish("off", "owner_inactive");
            Print("[HC Plan] HC-45 posture=all support=off wake=off state=off reason=owner_inactive checked=0/4 runtime=PENDING");
            return;
        }
        if (!m_HCPostures) { m_HCPostures = new HCPostureAdmission; }
        m_HCPostures.HCStart(m_Variety);
        HCRefreshVarietyStatus();
    }

    // O(1) on the existing lifecycle tick; no scan, config IO, experiment or
    // callback. Startup order can change VarietyActive after our OnStart.
    // Publish once per observed transition; HC-1 getters remain passive.
    void HCRefreshVarietyStatus()
    {
        if (!m_Running) { return; }
        string state = "ready";
        string reason = "group_scaling_owner_running_postures_off";
        if (m_Variety)
        {
            state = "refused";
            reason = "rest_wake_native_proof_pending";
            if (!VarietyActive()) { reason = "infected_owner_unavailable_rest_wake_unverified"; }
            else if (m_HCPostures)
            {
                HCOperationalStatus postures = m_HCPostures.HCStatus();
                state = postures.HCState();
                reason = postures.HCReason();
            }
        }
        if (m_HCVarietyStatus.HCState() == state && m_HCVarietyStatus.HCReason() == reason) { return; }
        m_HCVarietyStatus.HCPublish(state, reason);
    }

    override void OnTick(float deltaTime)
    {
        super.OnTick(deltaTime);
        if (!m_Running) { return; }
        HCRefreshVarietyStatus();
        if (m_HCPostures) { m_HCPostures.HCSlice(); }
    }

    override HCOperationalStatus HCGetOperationalStatus()
    {
        return m_HCVarietyStatus;
    }

    override void OnStop()
    {
        super.OnStop();
        if (m_HCPostures) { m_HCPostures.HCStop(); }
        m_HCPostures = null;
        m_HCVarietyStatus.HCPublish("off", "variety_owner_stopped");
    }
}

// Reuse the infected relay's existing conservative two-ray geometry helper.
// It proves geometry only, never native vision or actual human audibility.
modded class HCAlertChain
{
    bool HCVarietyClear(vector origin, ZombieBase recipient)
    {
        return ClearGeometry(origin, null, recipient);
    }
}

modded class HCNativeInfectedPack
{
    // Called once when migration remembers an admitted real-noise destination.
    // Existing <=6 member roster only; no transfer, refill or runner promotion.
    override void HCVarietyWalkerHerd()
    {
        if (!HCInfectedVarietyModule.VarietyActive() || m_Members.Count() > 6) { return; }
        foreach (ZombieBase walker : m_Members)
        {
            if (!walker || !walker.IsAlive()) { continue; }
            walker.HCVarietyAssign(0, walker.HCVarietyPlace());
        }
    }
}
