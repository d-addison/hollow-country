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
// without the requested research report no per-frame posture reassertion is used.
// Dormancy borrows ONLY native crawlers already near a tracked real corpse.
// Never forces StartCommand_Crawl: :811-826 is an injury transition, not a
// reversible lying/standing animation. Fresh-body spawning needs a shared lease.
modded class ZombieBase
{
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
        m_HCVarietyRole = role;
        m_HCVarietyPlace = place;
    }

    bool HCVarietySleep(float now, bool permitted)
    {
        // One attempt per existing native entity, including refusal. Repeated
        // calls cannot extend a hold or restart a completed/dead actor.
        if (m_HCVarietyTriedDormant) { return false; }
        m_HCVarietyTriedDormant = true;
        if (!GetGame().IsServer() || !HCInfectedVarietyModule.VarietyActive()) { return false; }
        if (!HCPostureAdmission.HCCanEnter("native_crawler_idle") || !(now >= 0)) { return false; }
        if (!permitted || !IsAlive() || !IsCrawling() || IsBeingBackstabbed()) { return false; }
        DayZInfectedInputController controller = GetInputController();
        if (!controller || controller.GetMindState() != DayZInfectedConstants.MINDSTATE_CALM) { return false; }
        AIAgent agent = GetAIAgent();
        if (!agent) { return false; }
        agent.SetKeepInIdle(true);
        m_HCVarietyDormant = true;
        m_HCVarietySleepUntil = now + 60;
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
        if (!m_HCVarietyPosture && mind == DayZInfectedConstants.MINDSTATE_CALM)
        {
            DayZInfectedCommandMove move = GetCommand_Move();
            if (move)
            {
                // Native stance values 0..3, idle 0 is the native calm idle.
                m_StanceVariation = m_HCVarietyRole;
                if (IsZombieMilitary()) { m_StanceVariation = 2; }
                move.SetStanceVariation(m_StanceVariation);
                move.SetIdleState(0);
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
        // The module also owns group scaling: posture off must not label that
        // running service off. These are observed owner states, not wake proof.
        m_HCVarietyStatus.HCPublish("ready", "variety_or_scaling_owner_running_rest_wake_unverified");
        if (m_Variety && !VarietyActive())
        {
            m_HCVarietyStatus.HCPublish("degraded", "infected_owner_unavailable_rest_wake_unverified");
        }
    }

    override void OnTick(float deltaTime)
    {
        super.OnTick(deltaTime);
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
