// Optional gc-actors-reach.json; absent fields retain these defaults, explicit false opts out.
// Native scripts-1.30.164289: 1_Core/proto/EnSystem.c:397 FileExist;
// 3_Game/tools/JsonFileLoader.c:69 LoadData; 1_Core/proto/EnDebug.c:96 Print;
// 1_Core/proto/EnConvert.c:30,115 int/float ToString.
// Bounded HCGroupIO + HCJsonSchema loader; HCJsonFields retains optional-field guards; no engine/Expansion gameplay calls added.
class GCActorsReachConfig
{
    bool Enabled = true;
    int Slots = 16;
    int EvaluationsPerTick = 6;
    int Vehicles = 8;
    float ContextSeconds = 10;
    float MaxLifetimeSeconds = 180;
    float InitialVaultDelaySeconds = 2;
    float VehicleContactMetres = 1.9;
    float VaultContactMetres = 1.2;
    float NavmeshSampleMetres = 0.5;
    float NavmeshHeightToleranceMetres = 0.7;
    float VaultOutcomeSeconds = 3;
    float VehicleHitSeconds = 2;
    float VehicleMemorySeconds = 60;
    float SummarySeconds = 60;
    float WorkSliceMilliseconds = 4;
    float DoorNavmeshCost = 1000;
    float AdmitHorizontalMetres = 6;

    protected string m_LastRefusal;
    void HCRefuse(string reason)
    {
        if (m_LastRefusal == reason) { return; }
        m_LastRefusal = reason;
        Print("[HC Reach] config_refused=" + reason + " defaults_retained runtime=PENDING");
    }

    bool HCValid(string key, float value, float low, float high)
    {
        // Local ceilings remain effective until the lead merges the shared registry rows.
        if (!(value >= low && value <= high)) { HCRefuse(key); return false; }
        string fullKey = "ActorReach." + key;
        if (HCOperatorSettingsRegistry.HCFind(fullKey) && !HCOperatorSettingsRegistry.HCValid(fullKey, value)) { HCRefuse(key); return false; }
        return true;
    }

    void HCLoad()
    {
        string path = "$profile:HollowCountry/gc-actors-reach.json";
        if (!FileExist(path)) { return; }
        string text;
        string error;
        GCActorsReachConfig decoded;
        if (!HCGroupIO.Read(path, 4096, text)) { HCRefuse("read"); return; }
        if (!HCJsonSchemaLoader<GCActorsReachConfig>.HCLoadData(text, decoded, error) || !decoded) { HCRefuse("json"); return; }
        if (HCJsonFields.Has(text, "Enabled")) { Enabled = decoded.Enabled; }
        if (HCJsonFields.Has(text, "Slots") && HCValid("Slots", decoded.Slots, 1, 16)) { Slots = decoded.Slots; }
        if (HCJsonFields.Has(text, "EvaluationsPerTick") && HCValid("EvaluationsPerTick", decoded.EvaluationsPerTick, 1, 6)) { EvaluationsPerTick = decoded.EvaluationsPerTick; }
        if (HCJsonFields.Has(text, "Vehicles") && HCValid("Vehicles", decoded.Vehicles, 1, 8)) { Vehicles = decoded.Vehicles; }
        if (HCJsonFields.Has(text, "ContextSeconds") && HCValid("ContextSeconds", decoded.ContextSeconds, 1, 180)) { ContextSeconds = decoded.ContextSeconds; }
        if (HCJsonFields.Has(text, "MaxLifetimeSeconds") && HCValid("MaxLifetimeSeconds", decoded.MaxLifetimeSeconds, 1, 180)) { MaxLifetimeSeconds = decoded.MaxLifetimeSeconds; }
        if (HCJsonFields.Has(text, "InitialVaultDelaySeconds") && HCValid("InitialVaultDelaySeconds", decoded.InitialVaultDelaySeconds, 0.1, 15)) { InitialVaultDelaySeconds = decoded.InitialVaultDelaySeconds; }
        if (HCJsonFields.Has(text, "VehicleContactMetres") && HCValid("VehicleContactMetres", decoded.VehicleContactMetres, 0.1, 1.9)) { VehicleContactMetres = decoded.VehicleContactMetres; }
        if (HCJsonFields.Has(text, "VaultContactMetres") && HCValid("VaultContactMetres", decoded.VaultContactMetres, 0.1, 1.2)) { VaultContactMetres = decoded.VaultContactMetres; }
        if (HCJsonFields.Has(text, "NavmeshSampleMetres") && HCValid("NavmeshSampleMetres", decoded.NavmeshSampleMetres, 0.05, 0.5)) { NavmeshSampleMetres = decoded.NavmeshSampleMetres; }
        if (HCJsonFields.Has(text, "NavmeshHeightToleranceMetres") && HCValid("NavmeshHeightToleranceMetres", decoded.NavmeshHeightToleranceMetres, 0.05, 0.7)) { NavmeshHeightToleranceMetres = decoded.NavmeshHeightToleranceMetres; }
        if (HCJsonFields.Has(text, "VaultOutcomeSeconds") && HCValid("VaultOutcomeSeconds", decoded.VaultOutcomeSeconds, 1, 10)) { VaultOutcomeSeconds = decoded.VaultOutcomeSeconds; }
        if (HCJsonFields.Has(text, "VehicleHitSeconds") && HCValid("VehicleHitSeconds", decoded.VehicleHitSeconds, 2, 60)) { VehicleHitSeconds = decoded.VehicleHitSeconds; }
        if (HCJsonFields.Has(text, "VehicleMemorySeconds") && HCValid("VehicleMemorySeconds", decoded.VehicleMemorySeconds, 2, 60)) { VehicleMemorySeconds = decoded.VehicleMemorySeconds; }
        if (HCJsonFields.Has(text, "SummarySeconds") && HCValid("SummarySeconds", decoded.SummarySeconds, 1, 600)) { SummarySeconds = decoded.SummarySeconds; }
        if (HCJsonFields.Has(text, "WorkSliceMilliseconds") && HCValid("WorkSliceMilliseconds", decoded.WorkSliceMilliseconds, 0.1, 4)) { WorkSliceMilliseconds = decoded.WorkSliceMilliseconds; }
        if (HCJsonFields.Has(text, "DoorNavmeshCost") && HCValid("DoorNavmeshCost", decoded.DoorNavmeshCost, 1, 1000)) { DoorNavmeshCost = decoded.DoorNavmeshCost; }
        if (HCJsonFields.Has(text, "AdmitHorizontalMetres") && HCValid("AdmitHorizontalMetres", decoded.AdmitHorizontalMetres, 2, 6)) { AdmitHorizontalMetres = decoded.AdmitHorizontalMetres; }
        if (ContextSeconds > MaxLifetimeSeconds) { ContextSeconds = MaxLifetimeSeconds; }
        if (EvaluationsPerTick > Slots) { EvaluationsPerTick = Slots; }
        if (VehicleMemorySeconds < VehicleHitSeconds) { VehicleMemorySeconds = VehicleHitSeconds; }
    }

    void HCLog()
    {
        Print("[HC Reach] effective WorkSliceMilliseconds=" + WorkSliceMilliseconds.ToString() + " DoorNavmeshCost=" + DoorNavmeshCost.ToString() + " AdmitHorizontalMetres=" + AdmitHorizontalMetres.ToString() + " runtime=PENDING");
        Print("[HC Reach] effective Enabled=" + HCV2Admission.OnOff(Enabled) + " runtime=PENDING");
        Print("[HC Reach] effective" + " Slots=" + Slots.ToString() + " EvaluationsPerTick=" + EvaluationsPerTick.ToString() + " Vehicles=" + Vehicles.ToString() + " runtime=PENDING");
        Print("[HC Reach] effective" + " ContextSeconds=" + ContextSeconds.ToString() + " MaxLifetimeSeconds=" + MaxLifetimeSeconds.ToString() + " InitialVaultDelaySeconds=" + InitialVaultDelaySeconds.ToString() + " runtime=PENDING");
        Print("[HC Reach] effective" + " VehicleContactMetres=" + VehicleContactMetres.ToString() + " VaultContactMetres=" + VaultContactMetres.ToString() + " NavmeshSampleMetres=" + NavmeshSampleMetres.ToString() + " runtime=PENDING");
        Print("[HC Reach] effective" + " NavmeshHeightToleranceMetres=" + NavmeshHeightToleranceMetres.ToString() + " VaultOutcomeSeconds=" + VaultOutcomeSeconds.ToString() + " VehicleHitSeconds=" + VehicleHitSeconds.ToString() + " runtime=PENDING");
        Print("[HC Reach] effective" + " VehicleMemorySeconds=" + VehicleMemorySeconds.ToString() + " SummarySeconds=" + SummarySeconds.ToString() + " runtime=PENDING");
    }
}

// #137 infected anti-cheese reach service (server only, on by default, gated on
// the existing settings.EnableInfected). Admission is event-driven: a CHASE or
// FIGHT infected whose own native target is an elevated or seated player asks
// for one of at most 16 configured slots; nothing scans the world or other players.
// Bound: OnTick (HCServer cadence, TickIntervalMs) evaluates at most 6 live
// slots inside a cooperative 4 ms HCWorkBudget slice, cursor retained. Each
// evaluation issues at most 4 native queries (1 line ray, 1 floor ray or vehicle
// lookup, 1 vehicle-contact or platform ray, 1 navmesh sample) -> <=24 per tick.
// Per landed swing, the infected adds at most one ray (see HCInfectedReachNative.c).
// Climb (2026-11-20): an in-band candidate (target 0.5-2.2 m up, <=2.5 m away, facing
// it, not seated) takes one more HCWorkBudget unit for <=2 rays (forward obstacle,
// downward top) and, on a cache miss (<=1 per slot per RouteCacheSeconds), two navmesh
// samples plus one FindPath (AIWorld.c:98); probes are paced to 1 per slot per second.
// The infected then plays the NATIVE StartCommand_Vault (DayZInfected.c:109) with the
// vanilla GetVaultType band (ZombieBase.c:401) of the measured obstacle; the vanilla
// HandleVault owns WasLand and the end of the command. No position write anywhere.
// Ladder discovery (HCInfectedLadderPolicy) reuses the floor-ray hit; ladder climb off.
// Vehicle hit spacing uses <=8 entries with 60 s expiry. No allocation per tick.
// Native evidence, installed scripts-1.30.164289:
// 3_Game/Global/Game.c:914 GetTickTime, :931 GetWorld, :1120 IsServer;
// 3_Game/Global/World.c:116 GetAIWorld; 3_Game/AI/AIWorld.c:59 PGFilter, :65 SetFlags,
// :67 SetCost, :122 SampleNavmeshPosition; 3_Game/Global/DayZPhysics.c:199 RaycastRV;
// 3_Game/constants.c:33 ObjIntersectFire; 3_Game/Entities/Object.c:287 GetPosition,
// :314 GetDirection, :517 IsAlive; 3_Game/Entities/EntityAI.c:879 GetHierarchyRoot;
// 3_Game/human.c:716 HumanCommandVehicle.GetTransport, :1528 GetCommand_Vehicle;
// 3_Game/Vehicles/Transport.c:66/:68 Transport; 3_Game/Entities/DayZInfected.c:1-18
// command/mind enums, :107 GetInputController; DayZInfectedInputController.c:9
// GetMindState, :10 GetTargetEntity; 1_Core/proto/EnMath3D.c:18 Vector;
// 1_Core/proto/EnConvert.c:156 Normalized, :196 Distance; EnMath.c:38 RandomInt,
// :225 AbsFloat, :305 Sqrt, :379 Acos, :16 RAD2DEG, :553 Min; EnScript.c:380/:385/
// :399/:407/:463 array Count/Clear/Get/Insert/Remove, :743/:744/:750 set
// Count/Clear/Get; EnConvert.c:30 int.ToString; EnDebug.c:96 Print.
// Offline tests prove only the policy. Native attack/vault/heading/vehicle damage
// behaviour, DayZDiag and normal PBO/server runs remain PENDING.
class HCInfectedReachState
{
    ZombieBase Infected;
    PlayerBase Target;
    float Admitted;
    float Expires;
    float LineAt = -100;
    bool LineClear;
    float LastReachHit;
    float NextStrike;
    Transport Vehicle;
    bool InVehicle;
    bool OnVehicle;
    float VehicleContact = -1;
    float VehicleAt = -100;
    bool OffNavmesh;
    int Phase;
    float PhaseSince;
    int Side = 1;
    float BackoffAfter;
    int ClimbType = -1;
    float ClimbAt;
    float ClimbHeight;
    float VaultAt;
    float VaultStartY;
    float VaultLandAt;
    float VaultEndAt;
    bool VaultSeen;
    float NextVault;
    float RouteAt = -100;
    bool RouteOk;
    Object FloorObject;
    bool LadderChecked;
}

class HCInfectedReachVehicle
{
    Transport Vehicle;
    float NextHit;
    float Expires;
}

class HCInfectedReachModule : HCModule
{
    protected ref GCActorsReachConfig m_Limits;
    protected static HCInfectedReachModule s_Instance;
    protected bool m_Running;
    protected ref array<ref HCInfectedReachState> m_States = new array<ref HCInfectedReachState>;
    protected ref array<ref HCInfectedReachVehicle> m_Vehicles = new array<ref HCInfectedReachVehicle>;
    protected ref set<Object> m_Hits = new set<Object>;
    protected ref HCWorkBudget m_Budget = new HCWorkBudget;
    protected ref PGFilter m_Filter;
    protected ref PGFilter m_RouteFilter;
    protected ref HCInfectedClimbConfig m_Climb;
    protected ref TVectorArray m_Path = new TVectorArray;
    protected int m_Cursor;
    protected int m_Live;
    protected int m_VaultActive;
    protected bool m_ClimbRetired;
    protected int m_ClimbTotal;
    protected int m_ClimbTotalOnTop;
    protected int m_ClimbStarted;
    protected int m_ClimbLanded;
    protected int m_ClimbOnTop;
    protected int m_ClimbFailed;
    protected int m_ClimbNoCommand;
    protected int m_WaitFacing;
    protected int m_WaitBusy;
    protected int m_WaitObstacle;
    protected int m_WaitRoute;
    protected int m_ClimbOutcomeLines;
    protected bool m_FirstClimb;
    protected int m_LadderSeen;
    protected int m_LadderEligible;
    protected bool m_FirstLadder;
    protected int m_Strikes;
    protected int m_Blocked;
    protected int m_Batters;
    protected int m_Backoffs;
    protected int m_Refused;
    protected int m_Admitted;
    protected float m_SummaryAfter;
    protected bool m_FirstStrike;
    protected bool m_FirstBatter;
    protected bool m_FirstBackoff;

    override string GetName() { return "InfectedReach"; }

    protected ref HCOperationalStatus m_Operational = new HCOperationalStatus;

    // Wave 16: cached readiness from the live started flag (never hard-coded).
    override HCOperationalStatus HCGetOperationalStatus()
    {
        if (m_Limits && !m_Limits.Enabled) { m_Operational.HCPublish("off", "reach_operator_off"); }
        else { HCModuleReadiness.HCDerive(m_Operational, m_Running, "", "", "reach_evaluator_started"); }
        return m_Operational;
    }

    override bool IsEnabled(HCSettings settings)
    {
        return settings && settings.EnableInfected;
    }

    override void OnStart(HCSettings settings)
    {
        if (!GetGame().IsServer() || !IsEnabled(settings) || m_Running) { return; }
        m_Limits = new GCActorsReachConfig;
        m_Limits.HCLoad();
        m_Limits.HCLog();
        if (!m_Limits.Enabled) { m_Operational.HCPublish("off", "reach_operator_off"); return; }
        HCInfectedReachPolicy.HCThreatResetBudget();
        m_States.Clear();
        m_Cursor = 0;
        for (int i = 0; i < m_Limits.Slots; i++)
        {
            m_States.Insert(null);
        }
        m_Vehicles.Clear();
        m_Filter = new PGFilter;
        // Same walkable filter as HCInfectedNavigation.c:110-111.
        m_Filter.SetFlags(PGPolyFlags.WALK | PGPolyFlags.DOOR | PGPolyFlags.INSIDE, PGPolyFlags.DISABLED | PGPolyFlags.UNREACHABLE | PGPolyFlags.SWIM | PGPolyFlags.SWIM_SEA | PGPolyFlags.LADDER | PGPolyFlags.JUMP | PGPolyFlags.CLIMB | PGPolyFlags.CRAWL | PGPolyFlags.CROUCH, PGPolyFlags.NONE);
        m_Filter.SetCost(PGAreaType.DOOR_CLOSED, m_Limits.DoorNavmeshCost);
        // Climb route check: what native infected locomotion may traverse, including
        // native jump/climb links (those already drive the vanilla vault).
        m_RouteFilter = new PGFilter;
        m_RouteFilter.SetFlags(PGPolyFlags.WALK | PGPolyFlags.DOOR | PGPolyFlags.INSIDE | PGPolyFlags.JUMP | PGPolyFlags.CLIMB, PGPolyFlags.DISABLED | PGPolyFlags.UNREACHABLE | PGPolyFlags.SWIM | PGPolyFlags.SWIM_SEA | PGPolyFlags.LADDER | PGPolyFlags.CRAWL | PGPolyFlags.CROUCH, PGPolyFlags.NONE);
        m_RouteFilter.SetCost(PGAreaType.DOOR_CLOSED, m_Limits.DoorNavmeshCost);
        m_Climb = new HCInfectedClimbConfig;
        m_Climb.HCLoad();
        m_Climb.HCLog();
        m_ClimbRetired = false;
        m_ClimbTotal = 0;
        m_ClimbTotalOnTop = 0;
        m_ClimbOutcomeLines = 0;
        m_Running = true;
        s_Instance = this;
        m_SummaryAfter = GetGame().GetTickTime() + m_Limits.SummarySeconds;
        Print(HCV2Admission.Line("InfectedReach", true, "W5-137", false));
        string started = "[HC Reach] started slots=" + m_Limits.Slots.ToString() + " evaluations_per_tick=" + m_Limits.EvaluationsPerTick.ToString();
        Print(started + " vehicles=" + m_Limits.Vehicles.ToString() + " runtime=PENDING");
        string capabilities = "[HC Reach] capabilities extended_reach=" + HCV2Admission.OnOff(HCInfectedReachPolicy.HCExtendedReachSupported());
        Print(capabilities + " forced_movement=" + HCV2Admission.OnOff(HCInfectedReachPolicy.HCForcedMovementSupported()) + " runtime=PENDING");
        string climbLine = "[HC Reach] capabilities climb=" + HCV2Admission.OnOff(ClimbActive()) + " command=StartCommand_Vault bands=vanilla_GetVaultType";
        Print(climbLine + " ladder_climb=" + HCV2Admission.OnOff(HCInfectedLadderPolicy.HC_LADDER_CLIMB_SUPPORTED) + " ladder_reason=" + HCInfectedLadderPolicy.HC_LADDER_REFUSAL + " ladder_discovery=shadow runtime=PENDING");
    }

    override void OnStop()
    {
        HCInfectedReachPolicy.HCThreatResetBudget();
        m_Running = false;
        m_States.Clear();
        m_Vehicles.Clear();
        m_Live = 0;
        m_VaultActive = 0;
        if (s_Instance == this) { s_Instance = null; }
    }

    static HCInfectedReachModule Active()
    {
        if (!s_Instance || !s_Instance.m_Running) { return null; }
        return s_Instance;
    }

    bool ClimbActive() { return m_Running && m_Climb && m_Climb.Enabled && !m_ClimbRetired; }

    // Horizontal admission window (O4, default 6 m); 4 m until the module has loaded its limits.
    float AdmitHorizontal()
    {
        if (!m_Limits) { return 4; }
        return m_Limits.AdmitHorizontalMetres;
    }

    // Lowest target elevation worth a slot: reach band or climb band.
    float ProbeMinHeight()
    {
        float low = HCInfectedTuning.Get().Reach.ElevatedMin;
        if (ClimbActive() && m_Climb.MinHeightMetres < low) { low = m_Climb.MinHeightMetres; }
        return low;
    }

    // Re-check on the start frame (arithmetic only, no queries).
    bool ClimbStillValid(ZombieBase infected, float vertical, float horizontal, float dx, float dz)
    {
        if (!ClimbActive()) { return false; }
        if (!HCInfectedReachPolicy.ClimbBand(vertical, horizontal, m_Climb.MinHeightMetres, m_Climb.MaxHeightMetres, m_Climb.MaxHorizontalMetres)) { return false; }
        return FacingDegrees(infected, dx, dz, horizontal) <= m_Climb.FacingDegrees;
    }

    HCInfectedReachState StateFor(ZombieBase infected, int slot)
    {
        if (slot < 0 || slot >= m_States.Count()) { return null; }
        HCInfectedReachState state = m_States.Get(slot);
        if (!state || state.Infected != infected) { return null; }
        return state;
    }

    // Called by the infected itself at most once per second while it has no slot.
    int Admit(ZombieBase infected, PlayerBase target, float now)
    {
        if (!m_Running || !infected || !target) { return -1; }
        int vacant = -1;
        for (int i = 0; i < m_States.Count(); i++)
        {
            HCInfectedReachState held = m_States.Get(i);
            if (held && held.Infected == infected) { return i; }
            if (!held && vacant < 0) { vacant = i; }
        }
        if (vacant < 0)
        {
            m_Refused++;
            return -1;
        }
        HCInfectedReachState state = new HCInfectedReachState;
        state.Infected = infected;
        state.Target = target;
        state.Admitted = now;
        state.Expires = now + m_Limits.ContextSeconds;
        state.LastReachHit = now;
        state.BackoffAfter = now;
        state.NextVault = now + m_Limits.InitialVaultDelaySeconds;
        m_States.Set(vacant, state);
        m_Live++;
        m_Admitted++;
        return vacant;
    }

    protected void Release(int slot, HCInfectedReachState state, float now)
    {
        if (state.VaultAt > 0) { ClimbResolve(state, state.Infected, now, true); }
        m_States.Set(slot, null);
        if (m_Live > 0) { m_Live--; }
    }

    override void OnTick(float deltaTime)
    {
        if (!m_Running || m_States.Count() != m_Limits.Slots) { return; }
        float now = GetGame().GetTickTime();
        m_Budget.HCReset(m_Limits.EvaluationsPerTick, m_Limits.WorkSliceMilliseconds);
        int deferred = 0;
        for (int scanned = 0; scanned < m_Limits.Slots; scanned++)
        {
            HCInfectedReachState state = m_States.Get(m_Cursor);
            if (state)
            {
                if (!m_Budget.HCContinue())
                {
                    // Cursor stays on the unevaluated slot for the next tick.
                    deferred = m_Live;
                    break;
                }
                Evaluate(m_Cursor, state, now);
                HCReached.Mark("infected_reach.evaluate");
            }
            m_Cursor = (m_Cursor + 1) % m_Limits.Slots;
        }
        m_Budget.HCDeferred(GetName(), deferred);
        ExpireVehicles(now);
        Summary(now);
    }

    protected void Evaluate(int slot, HCInfectedReachState state, float now)
    {
        ZombieBase infected = state.Infected;
        PlayerBase target = state.Target;
        if (!infected || !target || !infected.IsAlive() || !target.IsAlive())
        {
            Release(slot, state, now);
            return;
        }
        DayZInfectedInputController controller = infected.GetInputController();
        bool engaged = false;
        bool sameTarget = false;
        if (controller)
        {
            int mind = controller.GetMindState();
            engaged = mind == DayZInfectedConstants.MINDSTATE_CHASE || mind == DayZInfectedConstants.MINDSTATE_FIGHT;
            sameTarget = controller.GetTargetEntity() == target;
        }
        vector own = infected.GetPosition();
        vector aim = target.GetPosition();
        float distance = vector.Distance(own, aim);
        if (!HCInfectedReachPolicy.Keep(true, sameTarget, engaged, distance, now, state.Expires))
        {
            Release(slot, state, now);
            return;
        }
        float vertical = aim[1] - own[1];
        float dx = aim[0] - own[0];
        float dz = aim[2] - own[2];
        float horizontal = Math.Sqrt(dx * dx + dz * dz);

        HumanCommandVehicle seat = target.GetCommand_Vehicle();
        state.InVehicle = false;
        state.OnVehicle = false;
        state.Vehicle = null;
        if (seat)
        {
            state.Vehicle = seat.GetTransport();
            state.InVehicle = state.Vehicle != null;
        }
        else if (vertical >= HCInfectedTuning.Get().Reach.ElevatedMin)
        {
            state.Vehicle = FloorVehicle(state, target);
            state.OnVehicle = state.Vehicle != null;
        }
        // Bounded lifetime: context refresh never extends the configured admission deadline.
        if (vertical >= ProbeMinHeight() || state.InVehicle)
        {
            state.Expires = Math.Min(now + m_Limits.ContextSeconds, state.Admitted + m_Limits.MaxLifetimeSeconds);
        }

        state.LineClear = LineCheck(infected, target);
        state.LineAt = now;
        state.VehicleContact = -1;
        if (state.Vehicle)
        {
            state.VehicleContact = ContactDistance(infected, state.Vehicle, m_Limits.VehicleContactMetres);
            state.VehicleAt = now;
        }

        ClimbEvaluate(state, infected, own, aim, vertical, horizontal, dx, dz, now);
        LadderShadow(state, infected, target, vertical);

        if (!HCInfectedReachPolicy.HCForcedMovementSupported()) { return; }
        state.OffNavmesh = false;
        if (vertical >= HCInfectedTuning.Get().Reach.ElevatedMin && !state.InVehicle)
        {
            state.OffNavmesh = !OnWalkableNavmesh(aim);
        }

        if (state.Phase == HCInfectedReachPolicy.PhaseNone() && now >= state.BackoffAfter)
        {
            if (HCInfectedReachPolicy.Unreachable(vertical, horizontal, m_Limits.AdmitHorizontalMetres, state.OffNavmesh, now - state.LastReachHit, now - state.Admitted))
            {
                state.Phase = HCInfectedReachPolicy.PhaseRetreat();
                state.PhaseSince = now;
                state.Side = 1;
                if (Math.RandomInt(0, 2) == 0) { state.Side = -1; }
                m_Backoffs++;
                HCModuleReadiness.HCUse("InfectedReach", "backoff_started");
                HCNavHavenCensus.OnGiveUp(infected, target, aim, "backoff");
                if (!m_FirstBackoff)
                {
                    m_FirstBackoff = true;
                    Print("[HC Reach] first backoff: target unreachable, retreat-circle-wait via native controller overrides, heading runtime=PENDING");
                }
            }
        }
    }

    // Downward ray under the target: the first object is a Transport (roof,
    // bed or hood) or a part of one. Terrain, buildings and rocks return null.
    protected Transport FloorVehicle(HCInfectedReachState state, PlayerBase target)
    {
        state.FloorObject = null;
        vector origin = target.GetPosition() + "0 0.3 0";
        vector finish = target.GetPosition() + "0 -0.6 0";
        vector contact;
        vector normal;
        int component;
        m_Hits.Clear();
        bool hit = DayZPhysics.RaycastRV(origin, finish, contact, normal, component, m_Hits, null, target, true, false, ObjIntersectFire);
        if (!hit || m_Hits.Count() == 0) { return null; }
        state.FloorObject = m_Hits.Get(0);
        return HCRootVehicle(m_Hits.Get(0));
    }

    static Transport HCRootVehicle(Object hitObject)
    {
        if (!hitObject) { return null; }
        Transport direct = Transport.Cast(hitObject);
        if (direct) { return direct; }
        EntityAI entity = EntityAI.Cast(hitObject);
        if (!entity) { return null; }
        return Transport.Cast(entity.GetHierarchyRoot());
    }

    // One ray, infected head (vanilla GetAttackPitch +1.8 estimate) to target
    // knee. Walls or floors before the last 0.3 m block the strike.
    bool LineCheck(ZombieBase infected, PlayerBase target)
    {
        vector origin = infected.GetPosition() + "0 1.8 0";
        vector finish = target.GetPosition() + "0 0.5 0";
        vector contact;
        vector normal;
        int component;
        m_Hits.Clear();
        bool hit = DayZPhysics.RaycastRV(origin, finish, contact, normal, component, m_Hits, null, infected, true, false, ObjIntersectFire);
        bool hitTarget = false;
        if (hit && m_Hits.Count() > 0)
        {
            Object first = m_Hits.Get(0);
            EntityAI firstEntity = EntityAI.Cast(first);
            hitTarget = first == target || (firstEntity && firstEntity.GetHierarchyRoot() == target);
        }
        return HCInfectedReachPolicy.LineClear(hit, hitTarget, vector.Distance(origin, contact), vector.Distance(origin, finish));
    }

    // Distance from the infected's waist along its facing (or toward the
    // vehicle) to the first contact. With a vehicle, only that vehicle counts.
    // Returns -1 when nothing (or something else) is hit within the range.
    float ContactDistance(ZombieBase infected, Transport vehicle, float range)
    {
        vector origin = infected.GetPosition() + "0 1.0 0";
        vector heading = infected.GetDirection();
        if (vehicle)
        {
            vector toward = vehicle.GetPosition() - infected.GetPosition();
            heading = Vector(toward[0], 0, toward[2]).Normalized();
        }
        if (vehicle == null)
        {
            origin = infected.GetPosition() + "0 0.5 0";
        }
        vector finish = origin + heading * range;
        vector contact;
        vector normal;
        int component;
        m_Hits.Clear();
        bool hit = DayZPhysics.RaycastRV(origin, finish, contact, normal, component, m_Hits, null, infected, true, false, ObjIntersectFire);
        if (!hit) { return -1; }
        if (vehicle)
        {
            if (m_Hits.Count() == 0 || HCRootVehicle(m_Hits.Get(0)) != vehicle) { return -1; }
        }
        else if (m_Hits.Count() > 0 && PlayerBase.Cast(m_Hits.Get(0)))
        {
            return -1;
        }
        return vector.Distance(origin, contact);
    }

    protected bool OnWalkableNavmesh(vector position)
    {
        if (!GetGame().GetWorld() || !GetGame().GetWorld().GetAIWorld()) { return true; }
        vector sampled;
        if (!GetGame().GetWorld().GetAIWorld().SampleNavmeshPosition(position, m_Limits.NavmeshSampleMetres, m_Filter, sampled)) { return false; }
        return Math.AbsFloat(sampled[1] - position[1]) <= m_Limits.NavmeshHeightToleranceMetres;
    }

    static float FacingDegrees(ZombieBase infected, float dx, float dz, float horizontal)
    {
        vector facing = infected.GetDirection();
        float flat = Math.Sqrt(facing[0] * facing[0] + facing[2] * facing[2]);
        if (flat <= 0.001 || horizontal <= 0.001) { return 180; }
        float cosine = (facing[0] * dx + facing[2] * dz) / (flat * horizontal);
        if (cosine > 1) { cosine = 1; }
        if (cosine < -1) { cosine = -1; }
        return Math.Acos(cosine) * Math.RAD2DEG;
    }

    // Climb candidate: cheap gates first, then one extra budget unit for the rays
    // and the (cached) route check. Sets ClimbType; the infected starts the native
    // command on its next MOVE frame (HCInfectedReachNative.c).
    protected void ClimbEvaluate(HCInfectedReachState state, ZombieBase infected, vector own, vector aim, float vertical, float horizontal, float dx, float dz, float now)
    {
        ClimbResolve(state, infected, now, false);
        // A chosen climb the infected never started (no MOVE frame, band left) expires.
        if (state.ClimbType >= 0 && now - state.ClimbAt > 2) { state.ClimbType = -1; }
        if (!ClimbActive() || state.InVehicle || state.VaultAt > 0 || state.ClimbType >= 0) { return; }
        if (now < state.NextVault || infected.IsCrawling()) { return; }
        if (!HCInfectedReachPolicy.ClimbBand(vertical, horizontal, m_Climb.MinHeightMetres, m_Climb.MaxHeightMetres, m_Climb.MaxHorizontalMetres)) { return; }
        float facing = FacingDegrees(infected, dx, dz, horizontal);
        if (!HCInfectedReachPolicy.ClimbMayStart(facing, m_Climb.FacingDegrees, now, state.NextVault, m_VaultActive, m_Climb.Concurrent, m_ClimbRetired))
        {
            if (facing > m_Climb.FacingDegrees) { m_WaitFacing++; }
            else { m_WaitBusy++; }
            return;
        }
        if (!m_Budget.HCContinue()) { return; }
        state.NextVault = now + 1;
        float height = ObstacleHeight(infected, state.Target, dx, dz, horizontal);
        if (!HCInfectedReachPolicy.ClimbObstacle(height, m_Climb.MaxHeightMetres))
        {
            m_WaitObstacle++;
            return;
        }
        if (RouteExists(state, own, aim, now))
        {
            m_WaitRoute++;
            return;
        }
        state.ClimbType = infected.GetVaultType(height);
        state.ClimbAt = now;
        state.ClimbHeight = height;
        state.NextVault = now + m_Climb.CooldownSeconds;
    }

    // Forward ray at knee height along the horizontal direction to the target, then
    // a downward ray just past the contact for the obstacle top, both against
    // collision geometry (ObjIntersectGeom, constants.c:35). Returns the top height
    // above the infected's feet, or -1 for no object, a creature/player, terrain, or
    // no upward-facing top.
    protected float ObstacleHeight(ZombieBase infected, PlayerBase target, float dx, float dz, float horizontal)
    {
        if (horizontal <= 0.05) { return -1; }
        vector heading = Vector(dx / horizontal, 0, dz / horizontal);
        vector feet = infected.GetPosition();
        vector origin = feet + "0 0.4 0";
        vector finish = origin + heading * m_Limits.VaultContactMetres;
        vector contact;
        vector normal;
        int component;
        m_Hits.Clear();
        bool hit = DayZPhysics.RaycastRV(origin, finish, contact, normal, component, m_Hits, null, infected, true, false, ObjIntersectGeom);
        if (!hit || m_Hits.Count() == 0) { return -1; }
        Object blocker = m_Hits.Get(0);
        if (PlayerBase.Cast(blocker) || DayZCreature.Cast(blocker)) { return -1; }
        vector probe = contact + heading * 0.3;
        vector high = Vector(probe[0], feet[1] + m_Climb.MaxHeightMetres + 0.5, probe[2]);
        vector low = Vector(probe[0], feet[1] + 0.1, probe[2]);
        vector topContact;
        vector topNormal;
        m_Hits.Clear();
        bool top = DayZPhysics.RaycastRV(high, low, topContact, topNormal, component, m_Hits, null, target, true, false, ObjIntersectGeom);
        if (!top || topNormal[1] < 0.5) { return -1; }
        return topContact[1] - feet[1];
    }

    // True when native locomotion has a navmesh route to the target, so the native
    // AI keeps the job. Cached per slot for RouteCacheSeconds. A target off the
    // walkable navmesh (car roofs, wrecks, crates, wall tops) has no route.
    protected bool RouteExists(HCInfectedReachState state, vector own, vector aim, float now)
    {
        if (now - state.RouteAt < m_Climb.RouteCacheSeconds) { return state.RouteOk; }
        state.RouteAt = now;
        state.RouteOk = true;
        // Fail closed: without a navmesh verdict the native AI keeps the job.
        if (!GetGame().GetWorld() || !GetGame().GetWorld().GetAIWorld()) { return true; }
        state.RouteOk = false;
        AIWorld navigation = GetGame().GetWorld().GetAIWorld();
        vector goal;
        if (!navigation.SampleNavmeshPosition(aim, m_Limits.NavmeshSampleMetres, m_RouteFilter, goal)) { return false; }
        if (Math.AbsFloat(goal[1] - aim[1]) > m_Limits.NavmeshHeightToleranceMetres) { return false; }
        vector start;
        if (!navigation.SampleNavmeshPosition(own, 1.0, m_RouteFilter, start)) { return false; }
        m_Path.Clear();
        if (!navigation.FindPath(start, goal, m_RouteFilter, m_Path) || m_Path.Count() == 0) { return false; }
        state.RouteOk = HCInfectedReachPolicy.RouteReaches(m_Path.Get(m_Path.Count() - 1), goal);
        return state.RouteOk;
    }

    void ClimbStarted(HCInfectedReachState state, float startY, float now, int type, bool command, float vertical, float horizontal)
    {
        state.ClimbType = -1;
        state.VaultAt = now;
        state.VaultStartY = startY;
        state.VaultLandAt = 0;
        state.VaultEndAt = 0;
        state.VaultSeen = false;
        m_VaultActive++;
        m_ClimbStarted++;
        if (command) { HCModuleReadiness.HCUse("InfectedReach", "vault_started"); }
        m_ClimbTotal++;
        if (!command) { m_ClimbNoCommand++; }
        if (m_FirstClimb) { return; }
        m_FirstClimb = true;
        int heightCm = Math.Round(state.ClimbHeight * 100);
        int verticalCm = Math.Round(vertical * 100);
        int horizontalCm = Math.Round(horizontal * 100);
        string line = "[HC Reach] first climb started type=" + type.ToString() + " obstacle_cm=" + heightCm.ToString() + " target_up_cm=" + verticalCm.ToString();
        Print(line + " target_away_cm=" + horizontalCm.ToString() + " command=" + HCV2Admission.OnOff(command) + " via native StartCommand_Vault runtime=PENDING");
    }

    // Outcome once the native vault command has ended (the infected is back in a
    // non-vault command), at the OutcomeCapSeconds cap, or on slot release.
    void ClimbResolve(HCInfectedReachState state, ZombieBase infected, float now, bool force)
    {
        if (!state || state.VaultAt <= 0 || !m_Climb) { return; }
        bool ended = state.VaultEndAt > 0;
        if (!force && !ended && now - state.VaultAt < m_Climb.OutcomeCapSeconds) { return; }
        float rise = 0;
        bool alive = infected && infected.IsAlive();
        if (infected) { rise = infected.GetPosition()[1] - state.VaultStartY; }
        bool landed = state.VaultLandAt > 0;
        bool onTop = alive && HCInfectedReachPolicy.ClimbOnTop(rise, state.ClimbHeight);
        if (landed) { m_ClimbLanded++; }
        if (onTop)
        {
            m_ClimbOnTop++;
            m_ClimbTotalOnTop++;
        }
        if (!landed && !onTop) { m_ClimbFailed++; }
        if (m_ClimbOutcomeLines < 8)
        {
            m_ClimbOutcomeLines++;
            string end = "native";
            if (!ended) { end = "cap"; }
            if (force && !ended) { end = "released"; }
            int riseCm = Math.Round(rise * 100);
            int heightCm = Math.Round(state.ClimbHeight * 100);
            string line = "[HC Reach] climb outcome obstacle_cm=" + heightCm.ToString() + " rise_cm=" + riseCm.ToString() + " vault_seen=" + HCV2Admission.OnOff(state.VaultSeen);
            Print(line + " landed=" + HCV2Admission.OnOff(landed) + " on_top=" + HCV2Admission.OnOff(onTop) + " end=" + end + " runtime=PENDING");
        }
        state.VaultAt = 0;
        state.VaultLandAt = 0;
        state.VaultEndAt = 0;
        state.VaultSeen = false;
        if (m_VaultActive > 0) { m_VaultActive--; }
        if (!m_ClimbRetired && HCInfectedReachPolicy.ClimbRetired(m_ClimbTotal, m_ClimbTotalOnTop, m_Climb.RetireAttempts))
        {
            m_ClimbRetired = true;
            Print("[HC Reach] climb retired for this session: native vault never ended on top attempts=" + m_ClimbTotal.ToString() + " on_top=0; reach strike and vehicle battering remain");
        }
    }

    // Shadow ladder discovery (ladder climb disabled by evidence, see
    // HCInfectedLadderPolicy): once per slot when the target is above the vault band,
    // read the ladders of the building under the target. Reuses the floor-ray hit.
    protected void LadderShadow(HCInfectedReachState state, ZombieBase infected, PlayerBase target, float vertical)
    {
        if (state.LadderChecked || state.InVehicle || !state.FloorObject || !m_Climb) { return; }
        if (vertical <= m_Climb.MaxHeightMetres) { return; }
        state.LadderChecked = true;
        Building host = Building.Cast(state.FloorObject);
        if (!host)
        {
            EntityAI part = EntityAI.Cast(state.FloorObject);
            if (part) { host = Building.Cast(part.GetHierarchyRoot()); }
        }
        if (!host) { return; }
        vector bottom;
        vector top;
        bool modelSpace;
        int index = HCInfectedLadderPolicy.NearestLadder(host, target.GetPosition(), infected.GetPosition(), bottom, top, modelSpace);
        if (index < 0) { return; }
        bool eligible = HCInfectedLadderPolicy.VariantMayClimb(infected);
        m_LadderSeen++;
        if (eligible) { m_LadderEligible++; }
        if (m_FirstLadder) { return; }
        m_FirstLadder = true;
        string space = "raw";
        if (modelSpace) { space = "model"; }
        int riseCm = Math.Round((top[1] - bottom[1]) * 100);
        int seconds = Math.Round(HCInfectedLadderPolicy.ClimbSeconds(top[1] - bottom[1]));
        string line = "[HC Reach] ladder candidate building=" + host.GetType() + " ladder=" + index.ToString() + " rise_cm=" + riseCm.ToString() + " space=" + space;
        Print(line + " variant_eligible=" + HCV2Admission.OnOff(eligible) + " slow_climb_s=" + seconds.ToString() + " climb=off reason=" + HCInfectedLadderPolicy.HC_LADDER_REFUSAL + " runtime=PENDING");
    }

    // Per-vehicle spacing shared by every infected: one hit per 2 s, <=8 vehicles.
    float VehicleNextHit(Transport vehicle)
    {
        array<ref HCInfectedReachVehicle> vehicles = m_Vehicles;
        foreach (HCInfectedReachVehicle entry : vehicles)
        {
            if (entry.Vehicle == vehicle) { return entry.NextHit; }
        }
        if (m_Vehicles.Count() >= m_Limits.Vehicles) { return 1000000000; }
        return 0;
    }

    bool ReserveVehicleHit(Transport vehicle, float now)
    {
        if (!vehicle) { return false; }
        array<ref HCInfectedReachVehicle> vehicles = m_Vehicles;
        foreach (HCInfectedReachVehicle entry : vehicles)
        {
            if (entry.Vehicle == vehicle)
            {
                if (now < entry.NextHit) { return false; }
                entry.NextHit = now + m_Limits.VehicleHitSeconds;
                entry.Expires = now + m_Limits.VehicleMemorySeconds;
                return true;
            }
        }
        if (m_Vehicles.Count() >= m_Limits.Vehicles) { return false; }
        HCInfectedReachVehicle created = new HCInfectedReachVehicle;
        created.Vehicle = vehicle;
        created.NextHit = now + m_Limits.VehicleHitSeconds;
        created.Expires = now + m_Limits.VehicleMemorySeconds;
        m_Vehicles.Insert(created);
        return true;
    }

    protected void ExpireVehicles(float now)
    {
        for (int i = m_Vehicles.Count() - 1; i >= 0; i--)
        {
            if (!m_Vehicles[i].Vehicle || now >= m_Vehicles[i].Expires) { m_Vehicles.Remove(i); }
        }
    }

    void CountStrike(bool landed)
    {
        if (!landed)
        {
            m_Blocked++;
            return;
        }
        m_Strikes++;
        HCModuleReadiness.HCUse("InfectedReach", "strike_landed");
        if (!m_FirstStrike)
        {
            m_FirstStrike = true;
            Print("[HC Reach] first elevated strike landed zone=leg via DamageSystem.CloseCombatDamageName, runtime=PENDING");
        }
    }

    void CountBatter()
    {
        m_Batters++;
        HCModuleReadiness.HCUse("InfectedReach", "vehicle_battered");
        if (!m_FirstBatter)
        {
            m_FirstBatter = true;
            Print("[HC Reach] first vehicle batter via DamageSystem.CloseCombatDamage, vehicle damage/sound runtime=PENDING");
        }
    }

    protected void Summary(float now)
    {
        if (now < m_SummaryAfter) { return; }
        m_SummaryAfter = now + m_Limits.SummarySeconds;
        if (m_Admitted == 0 && m_Refused == 0 && m_ClimbStarted == 0 && m_Live == 0) { return; }
        string summary = "[HC Reach] summary active=" + m_Live.ToString() + " admitted=" + m_Admitted.ToString() + " refused=" + m_Refused.ToString();
        summary = summary + " strikes=" + m_Strikes.ToString() + " blocked=" + m_Blocked.ToString() + " batters=" + m_Batters.ToString();
        summary = summary + " backoffs=" + m_Backoffs.ToString() + " vaults=" + m_ClimbStarted.ToString() + " landed=" + m_ClimbLanded.ToString();
        summary = summary + " on_top=" + m_ClimbOnTop.ToString() + " failed=" + m_ClimbFailed.ToString() + " no_command=" + m_ClimbNoCommand.ToString();
        summary = summary + " climb_wait=facing:" + m_WaitFacing.ToString() + ",busy:" + m_WaitBusy.ToString() + ",no_obstacle:" + m_WaitObstacle.ToString() + ",route:" + m_WaitRoute.ToString();
        Print(summary + " ladders=seen:" + m_LadderSeen.ToString() + ",eligible:" + m_LadderEligible.ToString() + " climb=" + HCV2Admission.OnOff(ClimbActive()));
        m_Admitted = 0;
        m_Refused = 0;
        m_Strikes = 0;
        m_Blocked = 0;
        m_Batters = 0;
        m_Backoffs = 0;
        m_ClimbStarted = 0;
        m_ClimbLanded = 0;
        m_ClimbOnTop = 0;
        m_ClimbFailed = 0;
        m_ClimbNoCommand = 0;
        m_WaitFacing = 0;
        m_WaitBusy = 0;
        m_WaitObstacle = 0;
        m_WaitRoute = 0;
        m_LadderSeen = 0;
        m_LadderEligible = 0;
    }

    void Landed(HCInfectedReachState state, float now)
    {
        if (state) { state.LastReachHit = now; }
    }
}

modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        HCInfectedReachModule reachModule = new HCInfectedReachModule;
        Register(reachModule);
    }
}
