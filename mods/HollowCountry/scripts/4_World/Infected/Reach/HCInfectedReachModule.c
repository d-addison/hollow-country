// #137 infected anti-cheese reach service (server only, on by default, gated on
// the existing settings.EnableInfected). Admission is event-driven: a CHASE or
// FIGHT infected whose own native target is an elevated or seated player asks
// for one of 16 fixed slots; nothing scans the world or other players.
// Bound: OnTick (HCServer cadence, TickIntervalMs) evaluates at most 6 live
// slots inside a cooperative 4 ms HCWorkBudget slice, cursor retained. Each
// evaluation issues at most 4 native queries (1 line ray, 1 floor ray or vehicle
// lookup, 1 vehicle-contact or platform ray, 1 navmesh sample) -> <=24 per tick.
// Per landed swing, the infected adds at most one ray (see HCInfectedReachNative.c).
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
    int VaultType = -1;
    float VaultAt;
    float VaultStartY;
    float NextVault;
}

class HCInfectedReachVehicle
{
    Transport Vehicle;
    float NextHit;
    float Expires;
}

class HCInfectedReachModule : HCModule
{
    static const int SLOTS = 16;
    static const int EVALUATIONS = 6;
    static const int VEHICLES = 8;
    protected static HCInfectedReachModule s_Instance;
    protected bool m_Running;
    protected ref array<ref HCInfectedReachState> m_States = new array<ref HCInfectedReachState>;
    protected ref array<ref HCInfectedReachVehicle> m_Vehicles = new array<ref HCInfectedReachVehicle>;
    protected ref set<Object> m_Hits = new set<Object>;
    protected ref HCWorkBudget m_Budget = new HCWorkBudget;
    protected ref PGFilter m_Filter;
    protected int m_Cursor;
    protected int m_Live;
    protected int m_VaultActive;
    protected int m_VaultAttempts;
    protected int m_VaultLandings;
    protected bool m_VaultRetired;
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
        HCModuleReadiness.HCDerive(m_Operational, m_Running, "", "", "reach_evaluator_started");
        return m_Operational;
    }

    override bool IsEnabled(HCSettings settings)
    {
        return settings && settings.EnableInfected;
    }

    override void OnStart(HCSettings settings)
    {
        if (!GetGame().IsServer() || !IsEnabled(settings) || m_Running) { return; }
        HCInfectedReachPolicy.HCThreatResetBudget();
        m_States.Clear();
        for (int i = 0; i < SLOTS; i++)
        {
            m_States.Insert(null);
        }
        m_Vehicles.Clear();
        m_Filter = new PGFilter;
        // Same walkable filter as HCInfectedNavigation.c:110-111.
        m_Filter.SetFlags(PGPolyFlags.WALK | PGPolyFlags.DOOR | PGPolyFlags.INSIDE, PGPolyFlags.DISABLED | PGPolyFlags.UNREACHABLE | PGPolyFlags.SWIM | PGPolyFlags.SWIM_SEA | PGPolyFlags.LADDER | PGPolyFlags.JUMP | PGPolyFlags.CLIMB | PGPolyFlags.CRAWL | PGPolyFlags.CROUCH, PGPolyFlags.NONE);
        m_Filter.SetCost(PGAreaType.DOOR_CLOSED, 1000);
        m_Running = true;
        s_Instance = this;
        m_SummaryAfter = GetGame().GetTickTime() + 60;
        Print(HCV2Admission.Line("InfectedReach", true, "W5-137", false));
        Print("[HC Reach] started slots=16 evaluations_per_tick=6 vehicles=8 vault=experiment runtime=PENDING");
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

    bool VaultRetired() { return m_VaultRetired; }

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
        state.Expires = now + 10;
        state.LastReachHit = now;
        state.BackoffAfter = now;
        state.NextVault = now + 2;
        m_States.Set(vacant, state);
        m_Live++;
        m_Admitted++;
        return vacant;
    }

    protected void Release(int slot, HCInfectedReachState state)
    {
        if (state.VaultAt > 0 && m_VaultActive > 0) { m_VaultActive--; }
        m_States.Set(slot, null);
        if (m_Live > 0) { m_Live--; }
    }

    override void OnTick(float deltaTime)
    {
        if (!m_Running || m_States.Count() != SLOTS) { return; }
        float now = GetGame().GetTickTime();
        m_Budget.HCReset(EVALUATIONS);
        int deferred = 0;
        for (int scanned = 0; scanned < SLOTS; scanned++)
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
            }
            m_Cursor = (m_Cursor + 1) % SLOTS;
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
            Release(slot, state);
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
            Release(slot, state);
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
        else if (vertical >= 0.8)
        {
            state.Vehicle = FloorVehicle(target);
            state.OnVehicle = state.Vehicle != null;
        }
        // Bounded lifetime: context refreshes up to 180 s after admission.
        if (vertical >= 0.8 || state.InVehicle)
        {
            state.Expires = Math.Min(now + 10, state.Admitted + 180);
        }

        state.LineClear = LineCheck(infected, target);
        state.LineAt = now;
        state.VehicleContact = -1;
        if (state.Vehicle)
        {
            state.VehicleContact = ContactDistance(infected, state.Vehicle, 1.9);
            state.VehicleAt = now;
        }

        if (!HCInfectedReachPolicy.HCForcedMovementSupported()) { return; }
        state.OffNavmesh = false;
        if (vertical >= 0.8 && !state.InVehicle)
        {
            state.OffNavmesh = !OnWalkableNavmesh(aim);
        }

        VaultOutcome(state, infected, now);
        if (!state.InVehicle && state.Phase == HCInfectedReachPolicy.PhaseNone() && state.VaultType < 0)
        {
            float facing = FacingDegrees(infected, dx, dz, horizontal);
            bool ahead = false;
            if (HCInfectedReachPolicy.VaultType(vertical) >= 0 && horizontal <= 1.6)
            {
                ahead = ContactDistance(infected, null, 1.2) >= 0;
            }
            if (HCInfectedReachPolicy.MayVault(vertical, horizontal, facing, ahead, now, state.NextVault, m_VaultActive, m_VaultRetired))
            {
                state.VaultType = HCInfectedReachPolicy.VaultType(vertical);
                state.NextVault = now + 15;
            }
        }

        if (state.Phase == HCInfectedReachPolicy.PhaseNone() && now >= state.BackoffAfter)
        {
            if (HCInfectedReachPolicy.Unreachable(vertical, horizontal, state.OffNavmesh, now - state.LastReachHit, now - state.Admitted))
            {
                state.Phase = HCInfectedReachPolicy.PhaseRetreat();
                state.PhaseSince = now;
                state.Side = 1;
                if (Math.RandomInt(0, 2) == 0) { state.Side = -1; }
                m_Backoffs++;
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
    protected Transport FloorVehicle(PlayerBase target)
    {
        vector origin = target.GetPosition() + "0 0.3 0";
        vector finish = target.GetPosition() + "0 -0.6 0";
        vector contact;
        vector normal;
        int component;
        m_Hits.Clear();
        bool hit = DayZPhysics.RaycastRV(origin, finish, contact, normal, component, m_Hits, null, target, true, false, ObjIntersectFire);
        if (!hit || m_Hits.Count() == 0) { return null; }
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
        if (!GetGame().GetWorld().GetAIWorld().SampleNavmeshPosition(position, 0.5, m_Filter, sampled)) { return false; }
        return Math.AbsFloat(sampled[1] - position[1]) <= 0.7;
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

    // Vault experiment bookkeeping; the infected starts the native command.
    void VaultStarted(HCInfectedReachState state, float startY, float now, int type)
    {
        state.VaultAt = now;
        state.VaultStartY = startY;
        m_VaultActive++;
        m_VaultAttempts++;
        Print("[HC Reach] vault attempt type=" + type.ToString() + " attempts=" + m_VaultAttempts.ToString() + " experiment runtime=PENDING");
    }

    protected void VaultOutcome(HCInfectedReachState state, ZombieBase infected, float now)
    {
        if (state.VaultAt <= 0 || now - state.VaultAt < 3) { return; }
        state.VaultAt = 0;
        if (m_VaultActive > 0) { m_VaultActive--; }
        int rise = Math.Round((infected.GetPosition()[1] - state.VaultStartY) * 100);
        string landed = "0";
        if (HCInfectedReachPolicy.VaultLanded(state.VaultStartY, infected.GetPosition()[1]))
        {
            landed = "1";
            m_VaultLandings++;
        }
        Print("[HC Reach] vault outcome landed_on_top=" + landed + " rise_cm=" + rise.ToString() + " attempts=" + m_VaultAttempts.ToString() + " landings=" + m_VaultLandings.ToString());
        if (!m_VaultRetired && HCInfectedReachPolicy.VaultRetired(m_VaultAttempts, m_VaultLandings))
        {
            m_VaultRetired = true;
            Print("[HC Reach] vault experiment retired: native limit observed attempts=" + m_VaultAttempts.ToString() + " landings=0; reach strike and vehicle battering remain");
        }
    }

    // Per-vehicle spacing shared by every infected: one hit per 2 s, <=8 vehicles.
    float VehicleNextHit(Transport vehicle)
    {
        foreach (HCInfectedReachVehicle entry : m_Vehicles)
        {
            if (entry.Vehicle == vehicle) { return entry.NextHit; }
        }
        if (m_Vehicles.Count() >= VEHICLES) { return 1000000000; }
        return 0;
    }

    bool ReserveVehicleHit(Transport vehicle, float now)
    {
        if (!vehicle) { return false; }
        foreach (HCInfectedReachVehicle entry : m_Vehicles)
        {
            if (entry.Vehicle == vehicle)
            {
                if (now < entry.NextHit) { return false; }
                entry.NextHit = now + 2;
                entry.Expires = now + 60;
                return true;
            }
        }
        if (m_Vehicles.Count() >= VEHICLES) { return false; }
        HCInfectedReachVehicle created = new HCInfectedReachVehicle;
        created.Vehicle = vehicle;
        created.NextHit = now + 2;
        created.Expires = now + 60;
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
        if (!m_FirstStrike)
        {
            m_FirstStrike = true;
            Print("[HC Reach] first elevated strike landed zone=leg via DamageSystem.CloseCombatDamageName, runtime=PENDING");
        }
    }

    void CountBatter()
    {
        m_Batters++;
        if (!m_FirstBatter)
        {
            m_FirstBatter = true;
            Print("[HC Reach] first vehicle batter via DamageSystem.CloseCombatDamage, vehicle damage/sound runtime=PENDING");
        }
    }

    protected void Summary(float now)
    {
        if (now < m_SummaryAfter) { return; }
        m_SummaryAfter = now + 60;
        if (m_Admitted == 0 && m_Refused == 0) { return; }
        Print("[HC Reach] summary active=" + m_Live.ToString() + " admitted=" + m_Admitted.ToString() + " refused=" + m_Refused.ToString() + " strikes=" + m_Strikes.ToString() + " blocked=" + m_Blocked.ToString() + " batters=" + m_Batters.ToString() + " backoffs=" + m_Backoffs.ToString() + " vaults=" + m_VaultAttempts.ToString() + " landed=" + m_VaultLandings.ToString());
        m_Admitted = 0;
        m_Refused = 0;
        m_Strikes = 0;
        m_Blocked = 0;
        m_Batters = 0;
        m_Backoffs = 0;
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
        Register(new HCInfectedReachModule);
    }
}
